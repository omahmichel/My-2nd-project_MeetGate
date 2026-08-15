from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsMobileVerified

from zoom_integration.services import (
    ZoomIntegrationError,
    create_zoom_meeting,
    delete_zoom_meeting,
    update_zoom_meeting,
)

from .email_service import ResendEmailError, send_resend_email
from .models import Meeting, MeetingParticipant
from .serializers import MeetingParticipantSerializer, MeetingSerializer


class MeetingListCreateView(generics.ListCreateAPIView):
    serializer_class = MeetingSerializer
    permission_classes = [IsAuthenticated, IsMobileVerified]

    def get_queryset(self):
        return Meeting.objects.filter(
            host=self.request.user
        )

    def perform_create(self, serializer):
        # Create the real Zoom meeting before saving the local record.
        try:
            zoom_meeting = create_zoom_meeting(
                user=self.request.user,
                topic=serializer.validated_data["topic"],
                description=serializer.validated_data.get(
                    "description",
                    "",
                ),
                start_time=serializer.validated_data["start_time"],
                duration_minutes=serializer.validated_data[
                    "duration_minutes"
                ],
            )
        except ZoomIntegrationError as exc:
            raise serializers.ValidationError(
                {"zoom": str(exc)}
            ) from exc

        # Persist the Zoom identifiers returned by the Zoom API.
        serializer.save(
            host=self.request.user,
            zoom_meeting_id=str(zoom_meeting["id"]),
            join_url=zoom_meeting.get("join_url", ""),
            start_url=zoom_meeting.get("start_url", ""),
            meeting_password=zoom_meeting.get("password", ""),
        )


class MeetingDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MeetingSerializer
    permission_classes = [IsAuthenticated, IsMobileVerified]

    def get_queryset(self):
        return Meeting.objects.filter(
            host=self.request.user
        )

    def perform_update(self, serializer):
        meeting = self.get_object()

        # Use submitted values when present and preserve existing values
        # for fields omitted from the PATCH request.
        topic = serializer.validated_data.get(
            "topic",
            meeting.topic,
        )
        description = serializer.validated_data.get(
            "description",
            meeting.description,
        )
        start_time = serializer.validated_data.get(
            "start_time",
            meeting.start_time,
        )
        duration_minutes = serializer.validated_data.get(
            "duration_minutes",
            meeting.duration_minutes,
        )

        try:
            update_zoom_meeting(
                user=self.request.user,
                zoom_meeting_id=meeting.zoom_meeting_id,
                topic=topic,
                description=description,
                start_time=start_time,
                duration_minutes=duration_minutes,
            )
        except ZoomIntegrationError as exc:
            raise serializers.ValidationError(
                {"zoom": str(exc)}
            ) from exc

        serializer.save()

    def perform_destroy(self, instance):
        # Older meetings created before Zoom integration have no Zoom ID.
        # Delete those locally; only sync deletion when a Zoom ID exists.
        if instance.zoom_meeting_id:
            try:
                delete_zoom_meeting(
                    user=self.request.user,
                    zoom_meeting_id=instance.zoom_meeting_id,
                )
            except ZoomIntegrationError as exc:
                raise serializers.ValidationError(
                    {"zoom": str(exc)}
                ) from exc

        instance.delete()

class MeetingParticipantListCreateView(generics.ListCreateAPIView):
    serializer_class = MeetingParticipantSerializer
    permission_classes = [IsAuthenticated, IsMobileVerified]

    def get_meeting(self):
        # Hosts can manage participants only for meetings they own.
        return get_object_or_404(
            Meeting,
            pk=self.kwargs["meeting_id"],
            host=self.request.user,
        )

    def get_queryset(self):
        return MeetingParticipant.objects.filter(
            meeting=self.get_meeting()
        )

    def perform_create(self, serializer):
        meeting = self.get_meeting()
        email = serializer.validated_data["email"]

        if MeetingParticipant.objects.filter(
            meeting=meeting,
            email=email,
        ).exists():
            raise serializers.ValidationError(
                {
                    "email": (
                        "This participant has already been added "
                        "to the meeting."
                    )
                }
            )

        # Link the invitation to an existing MeetGate account when possible.
        user = User.objects.filter(
            email__iexact=email
        ).first()

        name = serializer.validated_data.get(
            "name",
            "",
        ).strip()

        if user and not name:
            name = user.get_full_name().strip() or user.email

        participant = serializer.save(
            meeting=meeting,
            user=user,
            name=name,
        )

        # Send the Zoom invitation only after the participant record is valid.
        display_name = participant.name or participant.email
        meeting_time = meeting.start_time.strftime("%A, %d %B %Y at %H:%M UTC")

        subject = f"MeetGate invitation: {meeting.topic}"
        message = (
            f"Hello {display_name},\n\n"
            f"You have been invited to a MeetGate meeting.\n\n"
            f"Meeting: {meeting.topic}\n"
            f"Date and time: {meeting_time}\n"
            f"Duration: {meeting.duration_minutes} minutes\n"
            f"Zoom Meeting ID: {meeting.zoom_meeting_id or 'Not available'}\n"
            f"Password: {meeting.meeting_password or 'Not required'}\n"
            f"Join link: {meeting.join_url or 'Not available'}\n\n"
            f"Hosted by: "
            f"{meeting.host.get_full_name().strip() or meeting.host.email}\n\n"
            "Regards,\n"
            "MeetGate"
        )

        try:
            # Send invitations through Resend over HTTPS so production does
            # not depend on SMTP ports that may be blocked by the host.
            send_resend_email(
                to_email=participant.email,
                subject=subject,
                message=message,
            )
        except ResendEmailError as exc:
            # Keep participant creation consistent if delivery fails.
            participant.delete()
            raise serializers.ValidationError(
                {
                    "email": (
                        "The invitation email could not be sent. "
                        "The participant was not added."
                    )
                }
            ) from exc


class MeetingParticipantDetailView(
    generics.RetrieveUpdateDestroyAPIView
):
    serializer_class = MeetingParticipantSerializer
    permission_classes = [IsAuthenticated, IsMobileVerified]

    def get_queryset(self):
        # Participant records remain isolated to the meeting host.
        return MeetingParticipant.objects.filter(
            meeting_id=self.kwargs["meeting_id"],
            meeting__host=self.request.user,
        )
