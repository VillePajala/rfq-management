"""Reply tracker — claim-state updater driven by service-mailbox replies.

STUB. Skeleton only — fill in during the Azure-team build phase.

Spec: docs/project_spec.md § 3.4 (claim tracking via email reply).

Intended flow:
  1. Poll the agent's service mailbox via Microsoft Graph Mail every 2 h
     on weekdays (separate Container Apps Job, cron-triggered).
  2. For each unread message, parse subject for `[TENDER-<tp_id>]`.
  3. Resolve sender → CGI employee email.
  4. Update the tender's claim state in storage:
        status=claimed, claimed_by=<email>, claimed_at=<utc>
     unless body matches an unclaim keyword (EI / NOT ME / PASS).
  5. Mark the message read (so we don't reprocess).
  6. Commit, exit. Dashboard regen picks it up on next render.

Auto-reply filtering: ignore messages with header
`Auto-Submitted: auto-replied`, `X-Autoreply: yes`, or subject containing
"Automatic reply" / "Poissaoloviesti" / "Out of Office".

Auth: Entra App Registration with `Mail.Read` + `Mail.ReadWrite` scoped
to the service mailbox via Application Access Policy. Same MSAL pattern
as `app/sharepoint.py`.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv

from .paths import ENV_PATH

load_dotenv(ENV_PATH)

# Subject pattern emitted by notify.py: `[TENDER-<tp_id>] <name> — <dept>`
TENDER_ID_RE = re.compile(r"\[TENDER-([\w-]+)\]")

# Body keywords that release a claim ("not me", "pass", "ei minulle")
UNCLAIM_KEYWORDS = ("ei", "not me", "pass", "en ota")

# Headers / subject markers indicating an out-of-office or auto-reply
AUTOREPLY_HEADER_MARKERS = ("auto-replied", "auto-generated")
AUTOREPLY_SUBJECT_MARKERS = (
    "automatic reply",
    "poissaoloviesti",
    "out of office",
    "ulkona toimistosta",
)


def parse_tender_id(subject: str) -> Optional[str]:
    """Extract tp_id from the digest subject. Returns None if absent."""
    if not subject:
        return None
    match = TENDER_ID_RE.search(subject)
    return match.group(1) if match else None


def is_autoreply(headers: dict, subject: str) -> bool:
    """Best-effort heuristic to skip OOF / auto-reply messages."""
    auto_submitted = (headers.get("Auto-Submitted") or "").lower()
    x_autoreply = (headers.get("X-Autoreply") or "").lower()
    if any(m in auto_submitted for m in AUTOREPLY_HEADER_MARKERS):
        return True
    if x_autoreply in ("yes", "true"):
        return True
    subj_lower = (subject or "").lower()
    return any(m in subj_lower for m in AUTOREPLY_SUBJECT_MARKERS)


def poll_mailbox():
    """Poll the service mailbox for new replies and update claim state.

    TODO: implement Graph Mail call (`/users/{mailbox}/messages?$filter=isRead eq false`),
    iterate, call `_record_claim` / `_release_claim` per message, mark read.
    """
    raise NotImplementedError(
        "reply_tracker.poll_mailbox not implemented. See docstring + spec § 3.4."
    )


def _record_claim(tp_id: str, sender_email: str, when: datetime | None = None) -> None:
    """Persist the claim. TODO: storage schema + write."""
    raise NotImplementedError


def _release_claim(tp_id: str, sender_email: str) -> None:
    """Drop a claim when the reply matches an unclaim keyword. TODO."""
    raise NotImplementedError


if __name__ == "__main__":
    poll_mailbox()
