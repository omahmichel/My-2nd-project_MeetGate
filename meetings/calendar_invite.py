from datetime import timedelta, timezone as datetime_timezone

from django.utils import timezone


def _escape_ical_text(value):
    # Escape text characters that have special meaning in iCalendar.
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def _format_utc(value):
    # Convert an aware datetime to the UTC timestamp used by iCalendar.
    return (
        value.astimezone(datetime_timezone.utc)
        .strftime("%Y%m%dT%H%M%SZ")
    )


def _fold_ical_line(line):
    # Fold long UTF-8 calendar lines without splitting a character.
    remaining = line.encode("utf-8")
    folded = []
    first_line = True

    while remaining:
        byte_limit = 75 if first_line else 74
        chunk = remaining[:byte_limit]

        while chunk:
            try:
                text = chunk.decode("utf-8")
                break
            except UnicodeDecodeError:
                chunk = chunk[:-1]
        else:
            text = ""

        prefix = "" if first_line else " "
        folded.append(prefix + text)
        remaining = remaining[len(chunk):]
        first_line = False

    return "\r\n".join(folded)


def build_calendar_attachment(meeting):
    # Build a portable .ics attachment for a MeetGate Zoom meeting.
    start_time = meeting.start_time
    end_time = start_time + timedelta(
        minutes=meeting.duration_minutes
    )

    host_name = (
        meeting.host.get_full_name().strip()
        or meeting.host.email
    )

    description_lines = [
        f"MeetGate meeting hosted by {host_name}.",
        f"Duration: {meeting.duration_minutes} minutes",
        f"Zoom Meeting ID: {meeting.zoom_meeting_id or 'Not available'}",
        f"Password: {meeting.meeting_password or 'Not required'}",
        f"Join link: {meeting.join_url or 'Not available'}",
    ]
    description = "\n".join(description_lines)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//MeetGate//Meeting Invitation//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:meetgate-meeting-{meeting.pk}@meetgatehq.com",
        f"DTSTAMP:{_format_utc(timezone.now())}",
        f"DTSTART:{_format_utc(start_time)}",
        f"DTEND:{_format_utc(end_time)}",
        f"SUMMARY:{_escape_ical_text(meeting.topic)}",
        f"DESCRIPTION:{_escape_ical_text(description)}",
        "LOCATION:Zoom",
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
    ]

    if meeting.join_url:
        lines.append(f"URL:{meeting.join_url}")

    lines.extend(
        [
            "END:VEVENT",
            "END:VCALENDAR",
        ]
    )

    folded_lines = [_fold_ical_line(line) for line in lines]
    ical_text = "\r\n".join(folded_lines) + "\r\n"

    return {
        "filename": f"meetgate-meeting-{meeting.pk}.ics",
        "content": ical_text.encode("utf-8"),
    }
