from django.conf import settings
from django.db import models


class AccountProfile(models.Model):
    ACCOUNT_TYPE_CHOICES = [
        ("participant", "Participant"),
        ("host", "Meeting Host"),
        ("organisation", "Organisation"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPE_CHOICES,
        default="participant",
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True,
        default="",
    )

    mobile_verified = models.BooleanField(default=False)

    # Stable Google account identifier used to link Google sign-ins.
    google_sub = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.get_account_type_display()}"

class PhoneOTP(models.Model):
    PURPOSE_CHOICES = [
        ("verify_mobile", "Verify Mobile"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="phone_otps",
    )
    phone_number = models.CharField(max_length=20)
    purpose = models.CharField(
        max_length=30,
        choices=PURPOSE_CHOICES,
        default="verify_mobile",
    )

    # Store only a one-way hash of the OTP, never the raw code.
    otp_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    last_sent_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "purpose", "is_used"],
                name="phoneotp_lookup_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.purpose}"
