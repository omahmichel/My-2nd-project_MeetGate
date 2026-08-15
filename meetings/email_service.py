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
        raise ResendEmailError(
            "Resend API key is not configured."
        )

    if not from_email:
        raise ResendEmailError(
            "Resend sender email is not configured."
        )

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
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
        raise ResendEmailError(
            "Resend could not be reached."
        ) from exc

    if not response.ok:
        logger.warning(
            "Resend rejected an email request with HTTP %s.",
            response.status_code,
        )
        raise ResendEmailError(
            "Resend rejected the email request."
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise ResendEmailError(
            "Resend returned an invalid response."
        ) from exc

    if not data.get("id"):
        raise ResendEmailError(
            "Resend did not return an email ID."
        )

    return data["id"]
