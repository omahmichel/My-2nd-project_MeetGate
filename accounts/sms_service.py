import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


def _normalize_mnotify_phone(phone_number):
    """Convert Ghana international format to mNotify's documented local format."""
    normalized = phone_number.strip().replace(" ", "")

    if normalized.startswith("+233"):
        return "0" + normalized[4:]

    if normalized.startswith("+"):
        return normalized[1:]

    return normalized


def _send_with_mnotify(*, phone_number, message):
    api_key = getattr(settings, "MNOTIFY_API_KEY", "").strip()
    sender_id = getattr(settings, "MNOTIFY_SENDER_ID", "MeetGate").strip()
    api_url = getattr(
        settings,
        "MNOTIFY_API_URL",
        "https://api.mnotify.com/api/sms/quick",
    ).strip()

    if not api_key:
        raise RuntimeError("MNOTIFY_API_KEY is not configured.")

    if not sender_id:
        raise RuntimeError("MNOTIFY_SENDER_ID is not configured.")

    if len(sender_id) > 11:
        raise RuntimeError(
            "MNOTIFY_SENDER_ID must be 11 characters or fewer."
        )

    request_url = f"{api_url}?{urlencode({'key': api_key})}"

    payload = {
        "recipient": [_normalize_mnotify_phone(phone_number)],
        "sender": sender_id,
        "message": message,
        "is_schedule": False,
        "schedule_date": "",
        "sms_type": "otp",
    }

    request = Request(
        request_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(
            f"mNotify rejected the SMS request with HTTP {exc.code}."
        ) from exc
    except URLError as exc:
        raise RuntimeError(
            "Could not connect to mNotify SMS service."
        ) from exc

    try:
        response_data = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "mNotify returned an invalid response."
        ) from exc

    status = str(response_data.get("status", "")).lower()

    if status and status != "success":
        provider_message = response_data.get(
            "message",
            "mNotify could not send the SMS.",
        )
        raise RuntimeError(str(provider_message))

    return True


def send_sms(*, phone_number, message):
    backend = getattr(settings, "SMS_BACKEND", "console").lower()

    if backend == "console":
        print("=" * 72)
        print(f"MeetGate SMS to {phone_number}")
        print(message)
        print("=" * 72)
        return True

    if backend == "mnotify":
        return _send_with_mnotify(
            phone_number=phone_number,
            message=message,
        )

    raise RuntimeError(
        f"Unsupported SMS_BACKEND: {backend}"
    )
