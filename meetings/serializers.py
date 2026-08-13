from django.utils import timezone
from rest_framework import serializers

from .models import Meeting, MeetingParticipant


class MeetingSerializer(serializers.ModelSerializer):
    host_name = serializers.SerializerMethodField()

    class Meta:
        model = Meeting

        fields = [
            "id",
            "host",
            "host_name",
            "topic",
            "description",
            "start_time",
            "duration_minutes",
            "status",
            "zoom_meeting_id",
            "join_url",
            "start_url",
            "meeting_password",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "host",
            "host_name",
            "status",
            "zoom_meeting_id",
            "join_url",
            "start_url",
            "meeting_password",
            "created_at",
            "updated_at",
        ]

    def get_host_name(self, obj):
        full_name = obj.host.get_full_name().strip()

        return full_name or obj.host.email

    def validate_start_time(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError(
                "Meeting start time must be in the future."
            )

        return value

    def validate_duration_minutes(self, value):
        if value < 5:
            raise serializers.ValidationError(
                "Meeting duration must be at least 5 minutes."
            )

        if value > 480:
            raise serializers.ValidationError(
                "Meeting duration cannot exceed 480 minutes."
            )

        return value

class MeetingParticipantSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(
        source="user.id",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = MeetingParticipant
        fields = [
            "id",
            "meeting",
            "user_id",
            "name",
            "email",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "meeting",
            "user_id",
            "created_at",
            "updated_at",
        ]

    def validate_email(self, value):
        return value.strip().lower()
