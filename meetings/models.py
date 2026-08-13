from django.conf import settings
from django.db import models


class Meeting(models.Model):
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("ongoing", "Ongoing"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="meetings",
    )

    topic = models.CharField(max_length=200)

    description = models.TextField(
        blank=True,
        default="",
    )

    start_time = models.DateTimeField()

    duration_minutes = models.PositiveIntegerField(
        default=30,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="scheduled",
    )

    zoom_meeting_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    join_url = models.URLField(
        blank=True,
        default="",
    )

    start_url = models.URLField(
        blank=True,
        default="",
    )

    meeting_password = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_time"]

    def __str__(self):
        return f"{self.topic} - {self.host.email}"

class MeetingParticipant(models.Model):
    STATUS_CHOICES = [
        ("invited", "Invited"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
    ]

    meeting = models.ForeignKey(
        Meeting,
        on_delete=models.CASCADE,
        related_name="participants",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meeting_participations",
    )

    name = models.CharField(
        max_length=200,
        blank=True,
        default="",
    )

    email = models.EmailField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="invited",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["meeting", "email"],
                name="unique_meeting_participant_email",
            ),
        ]

    def __str__(self):
        return f"{self.email} - {self.meeting.topic}"
