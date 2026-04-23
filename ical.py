"""iCal (.ics) generator for tender deadline reminders.

Attached to the digest email so recipients can drop deadlines straight
into their Outlook / Apple Calendar / Google Calendar with one click.

Per tender we emit up to two VEVENTs:
  - Question deadline (`question_deadline`) — when present
  - Tender deadline   (`deadline`)          — when present

Source timestamps from the scraper look like:
    29.4.2026 16.00 (UTC+03:00)      Finnish, dot-separated
    29/04/2026 16:00 (UTC+03:00)     English, slash-separated
    21.4.2026 11.20.14 (UTC+03:00)   with seconds
We convert to UTC and emit `DTSTART:<YYYYMMDDTHHMMSSZ>` — no TZ definition
needed in the .ics, which keeps the output portable.
"""
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Helsinki local time — honours DST automatically (EET = UTC+2 winter,
# EEST = UTC+3 summer). Used as the fallback tz when a scraped timestamp
# doesn't have an explicit (UTC+HH:MM) suffix.
_HELSINKI = ZoneInfo("Europe/Helsinki")


_DATE_RE = re.compile(
    r"^\s*"
    r"(?P<d>\d{1,2})[./](?P<m>\d{1,2})[./](?P<y>\d{4})"   # date
    r"\s+"
    r"(?P<h>\d{1,2})[.:](?P<mi>\d{2})(?:[.:](?P<s>\d{2}))?"   # time
    r"(?:\s+\(UTC(?P<tz_sign>[+\-])(?P<tz_h>\d{1,2}):?(?P<tz_m>\d{2})\))?"  # optional (UTC+03:00)
    r"\s*$"
)


def parse_tender_date(raw: str) -> datetime | None:
    """Parse a scraped deadline string into a timezone-aware UTC datetime.

    Returns None when the input doesn't match known formats.
    """
    if not raw:
        return None
    m = _DATE_RE.match(raw)
    if not m:
        return None
    try:
        d, mo, y = int(m.group("d")), int(m.group("m")), int(m.group("y"))
        h, mi = int(m.group("h")), int(m.group("mi"))
        s = int(m.group("s") or 0)
        tz_sign = m.group("tz_sign")
        if tz_sign:
            tz_h = int(m.group("tz_h") or 0)
            tz_m = int(m.group("tz_m") or 0)
            offset = timedelta(hours=tz_h, minutes=tz_m)
            if tz_sign == "-":
                offset = -offset
            tz = timezone(offset)
            local = datetime(y, mo, d, h, mi, s, tzinfo=tz)
        else:
            # Naive timestamp — interpret as Helsinki local time. ZoneInfo
            # handles DST automatically (EET winter / EEST summer), so
            # a naive "15.1.2026 10:00" correctly becomes UTC 08:00, and
            # "15.7.2026 10:00" correctly becomes UTC 07:00.
            local = datetime(y, mo, d, h, mi, s, tzinfo=_HELSINKI)
        return local.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _ics_escape(s: str) -> str:
    """Escape special characters per RFC 5545 (iCalendar)."""
    if not s:
        return ""
    return (
        s.replace("\\", "\\\\")
         .replace(";", "\\;")
         .replace(",", "\\,")
         .replace("\n", "\\n")
         .replace("\r", "")
    )


def _fmt_ics_utc(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _vevent(uid: str, summary: str, start_utc: datetime,
            description: str = "", url: str = "",
            duration_minutes: int = 30) -> list[str]:
    """Build one VEVENT as a list of iCal-format lines."""
    end_utc = start_utc + timedelta(minutes=duration_minutes)
    now_utc = datetime.now(timezone.utc)
    lines = [
        "BEGIN:VEVENT",
        f"UID:{_ics_escape(uid)}",
        f"DTSTAMP:{_fmt_ics_utc(now_utc)}",
        f"DTSTART:{_fmt_ics_utc(start_utc)}",
        f"DTEND:{_fmt_ics_utc(end_utc)}",
        f"SUMMARY:{_ics_escape(summary)}",
    ]
    if description:
        lines.append(f"DESCRIPTION:{_ics_escape(description)}")
    if url:
        lines.append(f"URL:{_ics_escape(url)}")
    lines.append("END:VEVENT")
    return lines


def build_tender_ics(tenders: list[dict]) -> str | None:
    """Build a full VCALENDAR containing deadline events for the given tenders.

    Returns the .ics text, or None if no parseable deadlines were found.
    """
    events: list[str] = []
    for t in tenders:
        tp_id = str(t.get("tp_id", "") or "")
        name = t.get("name", "Tender") or "Tender"
        url = t.get("url", "") or ""
        description_bits = []
        if t.get("organisation"):
            description_bits.append(f"Organisation: {t['organisation']}")
        if url:
            description_bits.append(f"Link: {url}")
        description = "\n".join(description_bits)

        # Question deadline → event
        q_raw = t.get("question_deadline")
        q_dt = parse_tender_date(q_raw) if q_raw else None
        if q_dt:
            events.extend(_vevent(
                uid=f"tender-{tp_id}-questions@cgi-tender-agent",
                summary=f"Questions due: {name}",
                start_utc=q_dt,
                description=description,
                url=url,
            ))

        # Tender deadline → event
        d_raw = t.get("deadline")
        d_dt = parse_tender_date(d_raw) if d_raw else None
        if d_dt:
            events.extend(_vevent(
                uid=f"tender-{tp_id}-deadline@cgi-tender-agent",
                summary=f"Tender deadline: {name}",
                start_utc=d_dt,
                description=description,
                url=url,
            ))

    if not events:
        return None

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CGI Tender Intelligence//Tender Deadlines//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        *events,
        "END:VCALENDAR",
    ]
    # RFC 5545 mandates CRLF line endings
    return "\r\n".join(lines) + "\r\n"
