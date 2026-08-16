import logging

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


class ResendEmailError(Exception):
    """Raised when a transactional email cannot be delivered to Resend."""


def send_resend_email(*, to_email, subject, message):
    """Send one plain-text transactional email through the Resend HTTPS API."""
    api_key = settings.RESEND_API_KEY
    from_email = settings.RESEND_FROM_EMAIL

    if not api_key:
        # Log configuration state without ever logging the secret itself.
        logger.error(
            "Resend configuration error: RESEND_API_KEY is missing."
        )
        raise ResendEmailError(
            "Resend API key is not configured."
        )

    if not from_email:
        logger.error(
            "Resend configuration error: RESEND_FROM_EMAIL is missing."
        )
        raise ResendEmailError(
            "Resend sender email is not configured."
        )

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "MeetGate/1.0",
            },
            json={
                "from": from_email,
                "to": [to_email],
                "subject": subject,
                "text": message,
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.error(
            "Resend network error: %s.",
            exc.__class__.__name__,
        )
        raise ResendEmailError(
            "Resend could not be reached."
        ) from exc

    if not response.ok:
        error_type = "unknown"
        error_message = "No error message returned."

        try:
            error_data = response.json()
            if isinstance(error_data, dict):
                error_type = str(
                    error_data.get("name")
                    or error_data.get("type")
                    or "unknown"
                )
                error_message = str(
                    error_data.get("message")
                    or "No error message returned."
                )
        except ValueError:
            error_type = "invalid_json"

        logger.error(
            "Resend rejected email request: HTTP %s; type=%s; message=%s",
            response.status_code,
            error_type,
            error_message,
        )
        raise ResendEmailError(
            "Resend rejected the email request."
        )

    try:
        data = response.json()
    except ValueError as exc:
        logger.error(
            "Resend response error: successful response was not valid JSON."
        )
        raise ResendEmailError(
            "Resend returned an invalid response."
        ) from exc

    if not data.get("id"):
        logger.error(
            "Resend response error: successful response had no email ID."
        )
        raise ResendEmailError(
            "Resend did not return an email ID."
        )

    return data["id"]
