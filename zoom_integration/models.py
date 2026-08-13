from django.conf import settings
from django.db import models


class ZoomConnection(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="zoom_connection",
    )

    zoom_user_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    zoom_email = models.EmailField(
        blank=True,
        default="",
    )

    access_token = models.TextField()

    refresh_token = models.TextField()

    token_expires_at = models.DateTimeField()

    scopes = models.TextField(
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - Zoom Connection"