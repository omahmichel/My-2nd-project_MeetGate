from datetime import timedelta, timezone as datetime_timezone

import requests
from django.conf import settings
from django.utils import timezone

from .models import ZoomConnection


class ZoomIntegrationError(Exception):
    pass


def _refresh_access_token(connection):
    # Refresh expired Zoom access tokens without asking the user to reconnect.
    response = requests.post(
        "https://zoom.us/oauth/token",
        params={
            "grant_type": "refresh_token",
            "refresh_token": connection.refresh_token,
        },
        auth=(
            settings.ZOOM_CLIENT_ID,
            settings.ZOOM_CLIENT_SECRET,
        ),
        timeout=20,
    )

    if not response.ok:
        raise ZoomIntegrationError(
            "Your Zoom connection has expired. "
            "Please reconnect your Zoom account."
        )

    token_data = response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get(
        "refresh_token",
        connection.refresh_token,
    )
    expires_in = token_data.get("expires_in", 3600)

    if not access_token:
        raise ZoomIntegrationError(
            "Zoom did not return a valid access token."
        )

    connection.access_token = access_token
    connection.refresh_token = refresh_token
    connection.token_expires_at = (
        timezone.now()
        + timedelta(seconds=expires_in)
    )

    if token_data.get("scope"):
        connection.scopes = token_data["scope"]

    connection.save(
        update_fields=[
            "access_token",
            "refresh_token",
            "token_expires_at",
            "scopes",
            "updated_at",
        ]
    )

    return access_token


def _get_access_token(user):
    connection = ZoomConnection.objects.filter(
        user=user
    ).first()

    if connection is None:
        raise ZoomIntegrationError(
            "Connect your Zoom account before creating a meeting."
        )

    # Refresh slightly early so the token cannot expire mid-request.
    refresh_threshold = timezone.now() + timedelta(seconds=60)

    if connection.token_expires_at <= refresh_threshold:
        return _refresh_access_token(connection)

    return connection.access_token


def create_zoom_meeting(
    *,
    user,
    topic,
    description,
    start_time,
    duration_minutes,
):
    access_token = _get_access_token(user)

    # Send Zoom a UTC timestamp so scheduling is consistent.
    zoom_start_time = (
        start_time.astimezone(datetime_timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    response = requests.post(
        "https://api.zoom.us/v2/users/me/meetings",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={
            "topic": topic,
            "type": 2,
            "start_time": zoom_start_time,
            "duration": duration_minutes,
            "timezone": "UTC",
            "agenda": description,
            "settings": {
                "join_before_host": False,
            },
        },
        timeout=20,
    )

    if not response.ok:
        try:
            error_data = response.json()
            zoom_message = (
                error_data.get("message")
                or error_data.get("reason")
            )
        except ValueError:
            zoom_message = None

        raise ZoomIntegrationError(
            zoom_message
            or "Zoom could not create the meeting."
        )

    meeting_data = response.json()

    if not meeting_data.get("id"):
        raise ZoomIntegrationError(
            "Zoom created an invalid meeting response."
        )

    return meeting_data

def update_zoom_meeting(
    *,
    user,
    zoom_meeting_id,
    topic,
    description,
    start_time,
    duration_minutes,
):
    if not zoom_meeting_id:
        raise ZoomIntegrationError(
            "This meeting is not linked to a Zoom meeting."
        )

    access_token = _get_access_token(user)

    # Send Zoom a UTC timestamp so scheduling remains consistent.
    zoom_start_time = (
        start_time.astimezone(datetime_timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    response = requests.patch(
        f"https://api.zoom.us/v2/meetings/{zoom_meeting_id}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={
            "topic": topic,
            "type": 2,
            "start_time": zoom_start_time,
            "duration": duration_minutes,
            "timezone": "UTC",
            "agenda": description,
        },
        timeout=20,
    )

    if not response.ok:
        try:
            error_data = response.json()
            zoom_message = (
                error_data.get("message")
                or error_data.get("reason")
            )
        except ValueError:
            zoom_message = None

        raise ZoomIntegrationError(
            zoom_message
            or "Zoom could not update the meeting."
        )

    return True

def delete_zoom_meeting(
    *,
    user,
    zoom_meeting_id,
):
    if not zoom_meeting_id:
        raise ZoomIntegrationError(
            "This meeting is not linked to a Zoom meeting."
        )

    access_token = _get_access_token(user)

    response = requests.delete(
        f"https://api.zoom.us/v2/meetings/{zoom_meeting_id}",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=20,
    )

    if response.status_code != 204:
        try:
            error_data = response.json()
            zoom_message = (
                error_data.get("message")
                or error_data.get("reason")
            )
        except ValueError:
            zoom_message = None

        raise ZoomIntegrationError(
            zoom_message
            or "Zoom could not delete the meeting."
        )

    return True
