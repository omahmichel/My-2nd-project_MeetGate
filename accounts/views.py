from datetime import timedelta
import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import AccountProfile, PhoneOTP
from .serializers import (
    GoogleAuthSerializer,
    LoginSerializer,
    MobileOTPSendSerializer,
    MobileOTPVerifySerializer,
    RegisterSerializer,
)
from .sms_service import send_sms


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response(
            serializer.validated_data,
            status=status.HTTP_200_OK,
        )

class GoogleClientConfigView(generics.GenericAPIView):
    permission_classes = [AllowAny]

    def get(self, request):
        client_id = getattr(settings, "GOOGLE_CLIENT_ID", "").strip()

        if not client_id:
            return Response(
                {"detail": "Google authentication is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {"client_id": client_id},
            status=status.HTTP_200_OK,
        )


class GoogleAuthView(generics.GenericAPIView):
    serializer_class = GoogleAuthSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        client_id = getattr(settings, "GOOGLE_CLIENT_ID", "").strip()

        if not client_id:
            return Response(
                {"detail": "Google authentication is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            google_user = id_token.verify_oauth2_token(
                serializer.validated_data["credential"],
                google_requests.Request(),
                client_id,
            )
        except ValueError:
            return Response(
                {"detail": "Invalid Google credential."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        google_sub = str(google_user.get("sub", "")).strip()
        email = str(google_user.get("email", "")).strip().lower()
        email_verified = google_user.get("email_verified") is True
        first_name = str(google_user.get("given_name", "")).strip()
        last_name = str(google_user.get("family_name", "")).strip()
        account_type = serializer.validated_data["account_type"]

        if not google_sub or not email or not email_verified:
            return Response(
                {"detail": "Google account information could not be verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            profile = (
                AccountProfile.objects.select_related("user")
                .filter(google_sub=google_sub)
                .first()
            )
            is_new_user = False

            if profile is not None:
                user = profile.user
            else:
                user = User.objects.filter(email__iexact=email).first()

                if user is not None:
                    profile, _ = AccountProfile.objects.get_or_create(
                        user=user,
                        defaults={"account_type": account_type},
                    )

                    if profile.google_sub and profile.google_sub != google_sub:
                        return Response(
                            {
                                "detail": (
                                    "This email is already linked to "
                                    "another Google account."
                                )
                            },
                            status=status.HTTP_409_CONFLICT,
                        )

                    profile.google_sub = google_sub
                    profile.save(
                        update_fields=["google_sub", "updated_at"]
                    )
                else:
                    user = User(
                        username=email,
                        email=email,
                        first_name=first_name,
                        last_name=last_name,
                    )
                    user.set_unusable_password()
                    user.save()

                    profile = AccountProfile.objects.create(
                        user=user,
                        account_type=account_type,
                        phone_number="",
                        mobile_verified=False,
                        google_sub=google_sub,
                    )
                    is_new_user = True

            if not user.is_active:
                return Response(
                    {"detail": "This account has been disabled."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            changed = []

            if not user.first_name and first_name:
                user.first_name = first_name
                changed.append("first_name")

            if not user.last_name and last_name:
                user.last_name = last_name
                changed.append("last_name")

            if changed:
                user.save(update_fields=changed)

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "is_new_user": is_new_user,
                "user": {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "account_type": profile.account_type,
                    "phone_number": profile.phone_number,
                    "mobile_verified": profile.mobile_verified,
                },
            },
            status=status.HTTP_200_OK,
        )


class SendMobileOTPView(generics.GenericAPIView):
    serializer_class = MobileOTPSendSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]
        now = timezone.now()

        recent_otp = PhoneOTP.objects.filter(
            user=request.user,
            purpose="verify_mobile",
            is_used=False,
        ).first()

        if recent_otp and recent_otp.last_sent_at > now - timedelta(seconds=60):
            return Response(
                {
                    "detail": (
                        "Please wait 60 seconds before requesting another OTP."
                    )
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            # Keep OTP/profile changes consistent with SMS delivery.
            # Any RuntimeError from the SMS provider rolls this transaction back.
            with transaction.atomic():
                PhoneOTP.objects.filter(
                    user=request.user,
                    purpose="verify_mobile",
                    is_used=False,
                ).update(is_used=True)

                otp = f"{secrets.randbelow(900000) + 100000}"

                PhoneOTP.objects.create(
                    user=request.user,
                    phone_number=phone_number,
                    purpose="verify_mobile",
                    otp_hash=make_password(otp),
                    expires_at=now + timedelta(minutes=10),
                    last_sent_at=now,
                )

                profile = request.user.profile
                if profile.phone_number != phone_number:
                    profile.phone_number = phone_number
                    profile.mobile_verified = False
                    profile.save(
                        update_fields=[
                            "phone_number",
                            "mobile_verified",
                            "updated_at",
                        ]
                    )

                send_sms(
                    phone_number=phone_number,
                    message=(
                        f"Your MeetGate verification code is {otp}. "
                        "It expires in 10 minutes."
                    ),
                )
        except RuntimeError:
            return Response(
                {
                    "detail": (
                        "The verification SMS could not be sent. "
                        "Please try again."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "detail": "Verification code sent.",
                "phone_number": phone_number,
            },
            status=status.HTTP_200_OK,
        )


class VerifyMobileOTPView(generics.GenericAPIView):
    serializer_class = MobileOTPVerifySerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]
        otp_value = serializer.validated_data["otp"]

        otp_record = PhoneOTP.objects.filter(
            user=request.user,
            phone_number=phone_number,
            purpose="verify_mobile",
            is_used=False,
        ).first()

        if otp_record is None:
            return Response(
                {"detail": "No active OTP was found for this number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp_record.expires_at <= timezone.now():
            otp_record.is_used = True
            otp_record.save(update_fields=["is_used"])
            return Response(
                {"detail": "The OTP has expired. Request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp_record.failed_attempts >= 5:
            otp_record.is_used = True
            otp_record.save(update_fields=["is_used"])
            return Response(
                {"detail": "Too many failed attempts. Request a new OTP."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if not check_password(otp_value, otp_record.otp_hash):
            otp_record.failed_attempts += 1
            otp_record.save(update_fields=["failed_attempts"])
            return Response(
                {
                    "detail": "Incorrect OTP.",
                    "attempts_left": max(
                        0,
                        5 - otp_record.failed_attempts,
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_record.is_used = True
        otp_record.save(update_fields=["is_used"])

        profile = request.user.profile
        profile.phone_number = phone_number
        profile.mobile_verified = True
        profile.save(
            update_fields=[
                "phone_number",
                "mobile_verified",
                "updated_at",
            ]
        )

        return Response(
            {
                "detail": "Mobile number verified successfully.",
                "phone_number": phone_number,
                "mobile_verified": True,
            },
            status=status.HTTP_200_OK,
        )
