from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import AccountProfile, PhoneOTP


class RegisterSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    account_type = serializers.ChoiceField(
        choices=AccountProfile.ACCOUNT_TYPE_CHOICES,
        write_only=True,
    )

    phone_number = serializers.CharField(
        max_length=20,
        write_only=True,
    )

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "password",
            "confirm_password",
            "account_type",
            "phone_number",
        ]
        extra_kwargs = {
            "first_name": {"required": True},
            "last_name": {"required": True},
            "email": {"required": True},
            "password": {
                "write_only": True,
                "min_length": 8,
            },
        }

    def validate_email(self, value):
        email = value.strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )

        return email

    def validate_phone_number(self, value):
        phone_number = value.strip().replace(" ", "")

        if not phone_number.startswith("+"):
            raise serializers.ValidationError(
                "Use international format, for example +233XXXXXXXXX."
            )

        digits = phone_number[1:]

        if not digits.isdigit() or len(digits) < 8 or len(digits) > 15:
            raise serializers.ValidationError(
                "Enter a valid international mobile number."
            )

        return phone_number

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "The passwords do not match."}
            )

        return data

    def create(self, validated_data):
        account_type = validated_data.pop("account_type")
        phone_number = validated_data.pop("phone_number")
        validated_data.pop("confirm_password")

        email = validated_data.pop("email")
        password = validated_data.pop("password")

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
        )

        AccountProfile.objects.create(
            user=user,
            account_type=account_type,
            phone_number=phone_number,
            mobile_verified=False,
        )

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    password = serializers.CharField(
        write_only=True,
        required=True,
    )

    def validate(self, data):
        email = data["email"].strip().lower()
        password = data["password"]

        user = authenticate(
            username=email,
            password=password,
        )

        if user is None:
            raise serializers.ValidationError(
                "Invalid email address or password."
            )

        if not user.is_active:
            raise serializers.ValidationError(
                "This account has been disabled."
            )

        refresh = RefreshToken.for_user(user)

        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "account_type": user.profile.account_type,
                "phone_number": user.profile.phone_number,
                "mobile_verified": user.profile.mobile_verified,
            },
        }

class MobileOTPSendSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)

    def validate_phone_number(self, value):
        phone_number = value.strip().replace(" ", "")
        if not phone_number.startswith("+"):
            raise serializers.ValidationError(
                "Use international format, for example +233XXXXXXXXX."
            )

        digits = phone_number[1:]
        if not digits.isdigit() or len(digits) < 8 or len(digits) > 15:
            raise serializers.ValidationError(
                "Enter a valid international mobile number."
            )

        return phone_number


class MobileOTPVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    otp = serializers.CharField(min_length=6, max_length=6)

    def validate_phone_number(self, value):
        phone_number = value.strip().replace(" ", "")
        if not phone_number.startswith("+"):
            raise serializers.ValidationError(
                "Use international format, for example +233XXXXXXXXX."
            )

        digits = phone_number[1:]
        if not digits.isdigit() or len(digits) < 8 or len(digits) > 15:
            raise serializers.ValidationError(
                "Enter a valid international mobile number."
            )

        return phone_number

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError(
                "OTP must contain exactly 6 digits."
            )

        return value

class GoogleAuthSerializer(serializers.Serializer):
    credential = serializers.CharField(write_only=True)
    account_type = serializers.ChoiceField(
        choices=AccountProfile.ACCOUNT_TYPE_CHOICES,
        required=False,
        default="participant",
    )
