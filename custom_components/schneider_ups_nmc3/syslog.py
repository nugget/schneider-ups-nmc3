"""Syslog parsing for Schneider Electric UPS NMC3."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

RFC5424_RE = re.compile(
    r"^<(?P<priority>\d+)>(?P<version>\d+) "
    r"(?P<timestamp>\S+) "
    r"(?P<hostname>\S+) "
    r"(?P<app_name>\S+) "
    r"(?P<proc_id>\S+) "
    r"(?P<msg_id>\S+) "
    r"(?P<structured_data>\S+) "
    r"(?P<message>.*)$"
)

SEVERITY = {
    0: "emergency",
    1: "alert",
    2: "critical",
    3: "error",
    4: "warning",
    5: "notice",
    6: "informational",
    7: "debug",
}

FACILITY = {
    0: "kernel",
    1: "user",
    2: "mail",
    3: "daemon",
    4: "auth",
    5: "syslog",
    6: "lpr",
    7: "news",
    8: "uucp",
    9: "clock",
    10: "authpriv",
    11: "ftp",
    12: "ntp",
    13: "audit",
    14: "alert",
    15: "cron",
    16: "local0",
    17: "local1",
    18: "local2",
    19: "local3",
    20: "local4",
    21: "local5",
    22: "local6",
    23: "local7",
}


class SyslogParseError(ValueError):
    """Raised when a syslog message cannot be parsed."""


@dataclass(frozen=True)
class SyslogEvent:
    """A parsed NMC syslog event."""

    priority: int
    facility: str
    severity: str
    timestamp: datetime
    hostname: str
    app_name: str
    proc_id: str
    msg_id: str
    structured_data: str
    message: str
    event_category: str | None
    event_text: str


def parse_syslog_message(raw: bytes | str) -> SyslogEvent:
    """Parse an NMC syslog message."""
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    text = text.strip()
    match = RFC5424_RE.match(text)
    if match is None:
        raise SyslogParseError("Unsupported syslog message format")

    priority = int(match.group("priority"))
    timestamp = datetime.fromisoformat(match.group("timestamp"))
    message = match.group("message")

    return SyslogEvent(
        priority=priority,
        facility=FACILITY.get(priority // 8, "unknown"),
        severity=SEVERITY.get(priority % 8, "unknown"),
        timestamp=timestamp,
        hostname=match.group("hostname"),
        app_name=match.group("app_name"),
        proc_id=match.group("proc_id"),
        msg_id=match.group("msg_id"),
        structured_data=match.group("structured_data"),
        message=message,
        event_category=_event_category(match.group("proc_id"), match.group("msg_id")),
        event_text=message,
    )


def _event_category(proc_id: str, msg_id: str) -> str | None:
    """Build an event category from RFC5424 proc and message identifiers."""
    parts = [part for part in (proc_id, msg_id) if part != "-"]
    if not parts:
        return None

    return " ".join(parts)
