"""
Email notifications for new tenders.

Sends one email per department. Each department's tenders are grouped
in a single digest email sent to that department's contact.
Uses SMTP credentials from .env file.
"""

import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from dotenv import load_dotenv

from .paths import ENV_PATH, PREVIEWS_DIR

load_dotenv(ENV_PATH)


def build_email_html(contact: str, department: str, tenders: list[dict],
                     reviewer_banner: dict | None = None) -> str:
    """Build an HTML email body for a single department's tender digest.

    reviewer_banner: when set, prepends a yellow "REVIEW MODE" banner
    showing the routing proposal the reviewer is expected to verify before
    forwarding. Expected keys:
        intended_email: str  — the real recipient this digest is meant for
        department:     str  — redundant with `department` arg, shown for clarity
    """

    date_str = datetime.now().strftime("%d.%m.%Y")

    banner_html = ""
    if reviewer_banner:
        banner_html = f"""
        <div style="background:#fff3cd; border:2px solid #ffc107; padding:14px 18px; margin:0 0 20px 0; border-radius:6px;">
            <div style="font-weight:bold; color:#856404; font-size:1.05em;">⚠️ REVIEW MODE — not yet sent to team</div>
            <div style="margin-top:6px; color:#856404; font-size:0.9em;">
                This digest was routed to department <strong>{reviewer_banner.get("department", department)}</strong> → intended recipient <strong>{reviewer_banner.get("intended_email", "")}</strong>.<br>
                Please verify: matched keywords look right? Recipient address correct?<br>
                If yes, forward this email to the intended recipient. If no, reply with corrections or update <code>routing_config.xlsx</code>.
            </div>
        </div>
        """

    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; max-width: 800px; margin: 0 auto; }}
            h1 {{ color: #1a5276; border-bottom: 2px solid #1a5276; padding-bottom: 10px; }}
            h2 {{ color: #2c3e50; margin-top: 30px; }}
            .tender {{ background: #f8f9fa; border-left: 4px solid #1a5276; padding: 12px 16px; margin: 10px 0; }}
            .tender-name {{ font-weight: bold; color: #1a5276; }}
            .tender-org {{ color: #666; font-size: 0.9em; }}
            .tender-deadline {{ color: #c0392b; font-weight: bold; }}
            .tender-desc {{ color: #555; font-size: 0.9em; margin-top: 6px; }}
            .stats {{ background: #eaf2f8; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            .footer {{ color: #999; font-size: 0.8em; margin-top: 30px; border-top: 1px solid #ddd; padding-top: 10px; }}
            a {{ color: #1a5276; }}
        </style>
    </head>
    <body>
        {banner_html}
        <h1>{department} — New Tender Alert</h1>
        <p>Hi {contact},</p>
        <div class="stats">
            <strong>{len(tenders)} new tender(s)</strong> matched your area ({department}) — {date_str}
        </div>
    """

    # Sort: AI-summarized on top (relevant first, then not relevant), unsummarized at bottom
    def sort_key(t):
        summary = (t.get("ai_summary", "") or "").lower()
        has_summary = bool(t.get("ai_summary"))
        is_irrelevant = "not relevant" in summary or "skip" in summary
        if has_summary and not is_irrelevant:
            priority = 0  # relevant AI summary — top
        elif has_summary and is_irrelevant:
            priority = 1  # NOT RELEVANT summary — below relevant but still above unsummarized
        else:
            priority = 2  # no summary — bottom
        return (priority, t.get("deadline", "zzz"))

    # Human-readable labels for Hilma's eForms procedure-type codes.
    # Blank / unknown codes pass through unchanged so nothing silently disappears.
    PROCEDURE_LABELS = {
        "open": "open (avoin)",
        "restricted": "restricted (rajattu)",
        "neg-wo-call": "negotiated without call",
        "neg-w-call": "negotiated with call",
        "comp-dial": "competitive dialogue",
        "comp-tend": "competitive tendering",
        "innovation": "innovation partnership",
        "dps": "dynamic purchasing system",
        "des-cont": "design contest",
    }

    for t in sorted(tenders, key=sort_key):
        name = t.get("name", "N/A")
        org = t.get("organisation", "")
        deadline = t.get("deadline", "No deadline specified")
        question_deadline = t.get("question_deadline", "")
        procedure_type_raw = t.get("procedure_type", "") or ""
        procedure_type = PROCEDURE_LABELS.get(procedure_type_raw, procedure_type_raw)
        # Scoring mechanism — AI-extracted quality/price weights, or the
        # qualitative basis ("price-only") when no explicit percentages given.
        qw = t.get("quality_weight")
        pw = t.get("price_weight")
        sb = t.get("scoring_basis", "") or ""
        if qw is not None and pw is not None:
            scoring_display = f"Quality {qw}% / Price {pw}%"
        elif sb and sb != "unknown":
            scoring_display = sb.replace("-", " ").capitalize()
        else:
            scoring_display = ""

        # Contract / reservations flags (AI-extracted, may be None)
        ci = t.get("contract_included")
        ra = t.get("reservations_allowed")
        contract_display = {True: "Yes", False: "No"}.get(ci, "")
        reservations_display = {True: "Allowed", False: "Not allowed"}.get(ra, "")

        desc = t.get("description_short", t.get("description", "")[:200])
        url = t.get("url", "")

        ai_summary = t.get("ai_summary", "")
        summary_source = t.get("_summary_source", "")
        category = t.get("category", "")

        # Convert markdown bold (**text**) to HTML <strong> tags
        if ai_summary:
            ai_summary_html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', ai_summary)
            ai_summary_html = ai_summary_html.replace("\n", "<br>")
        else:
            ai_summary_html = ""

        # Source indicator — only shown for detail-enriched tenders
        if summary_source == "detail":
            source_tag = '<span style="background:#2ecc71; color:white; padding:2px 8px; border-radius:3px; font-size:0.75em; font-weight:bold;">DETAIL PAGE — 6 tabs</span>'
        else:
            source_tag = ""

        # Category badge — shows what type of tender this is
        category_badges = {
            "open_competition": ("Competition", "#2c3e50"),
            "early_signal": ("Info Request", "#7f8c8d"),
            "dynamic_purchasing": ("Dynamic Procurement", "#2c3e50"),
            "direct_award": ("Direct Award", "#95a5a6"),
        }
        badge_text, badge_color = category_badges.get(category, ("", ""))
        category_tag = f'<span style="background:{badge_color}; color:white; padding:2px 8px; border-radius:3px; font-size:0.75em;">{badge_text}</span> ' if badge_text else ""

        html += f"""
        <div class="tender">
            <div class="tender-name">
                {category_tag}{'<a href="' + url + '">' + name + '</a>' if url else name}
            </div>
            <div class="tender-org">{org}</div>
            <div>Deadline: <span class="tender-deadline">{deadline}</span></div>
            {'<div style="font-size:0.85em; color:#566573;">Questions due: ' + question_deadline + '</div>' if question_deadline else ''}
            {'<div style="font-size:0.85em; color:#566573;">Procedure: ' + procedure_type + '</div>' if procedure_type else ''}
            {'<div style="font-size:0.85em; color:#566573;">Scoring: ' + scoring_display + '</div>' if scoring_display else ''}
            {'<div style="font-size:0.85em; color:#566573;">Contract included: ' + contract_display + '</div>' if contract_display else ''}
            {'<div style="font-size:0.85em; color:#566573;">Reservations: ' + reservations_display + '</div>' if reservations_display else ''}
            {'<div style="font-size:0.8em; color:#666;">CPV: ' + t.get("cpv_codes", "")[:60] + (' | Value: €{:,.0f}'.format(t["estimated_value"]) if t.get("estimated_value") and t["estimated_value"] > 0 else '') + '</div>' if t.get("cpv_codes") else ''}
            {'<div class="tender-desc" style="background:#eef6ff; padding:8px; margin-top:8px; border-radius:4px; font-size:0.9em; line-height:1.5;">' + source_tag + ('<br>' if source_tag else '') + ai_summary_html + '</div>' if ai_summary_html else ''}
            {'<div class="tender-desc">' + desc + '</div>' if desc and not ai_summary else ''}
        </div>
        """

    html += f"""
        <div class="footer">
            <p>This is an automated notification from CGI Tender Intelligence.<br>
            To change your routing rules, edit the file <code>routing_config.xlsx</code>.</p>
        </div>
    </body>
    </html>
    """
    return html


def send_email(to_email: str, subject: str, html_body: str,
               ics_body: str | None = None,
               ics_filename: str = "tender_deadlines.ics") -> bool:
    """Send an email via SMTP. Credentials from .env.

    If `ics_body` is provided, attach it as `ics_filename`. Email clients
    (Outlook, Apple Mail, Gmail) recognize the `text/calendar` MIME type and
    offer one-click "Add to calendar". No external iCal library required.

    When SMTP credentials aren't set, the HTML body is written as a preview
    file next to the scraper, and — if an ics_body is supplied — the calendar
    file is written alongside so it can still be inspected.
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_user or not smtp_password:
        print(f"  [SMTP] No SMTP credentials in .env — email NOT sent to {to_email}")
        print(f"  [SMTP] Would have sent: {subject}")
        filename = f"email_preview_{to_email.replace('@', '_at_')}_{subject[:30].replace(' ', '_')}.html"
        filepath = str(PREVIEWS_DIR / filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_body)
        print(f"  [SMTP] Email preview saved to {filename}")
        if ics_body:
            ics_preview = filepath.replace(".html", ".ics")
            with open(ics_preview, "w", encoding="utf-8", newline="") as f:
                f.write(ics_body)
            print(f"  [SMTP] iCal preview saved to {os.path.basename(ics_preview)}")
        return False

    # Build a `mixed` outer MIME (so attachments are first-class) wrapping
    # an `alternative` for the HTML body.
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(html_body, "html"))
    msg.attach(body_part)

    if ics_body:
        # Attach as an application/ics part so any mail client will render
        # it as a calendar invite attachment. Some clients also accept
        # `text/calendar; method=PUBLISH`, but using MIMEBase with a
        # Content-Disposition of attachment is the most portable option.
        ics_part = MIMEBase("text", "calendar", method="PUBLISH", name=ics_filename)
        ics_part.set_payload(ics_body)
        encoders.encode_base64(ics_part)
        ics_part.add_header("Content-Disposition", f'attachment; filename="{ics_filename}"')
        msg.attach(ics_part)

    try:
        # Explicit 30 s timeout — without it, a hung SMTP server during a
        # nightly maintenance window wedges the whole pipeline indefinitely.
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, to_email, msg.as_string())
        print(f"  [SMTP] Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        print(f"  [SMTP] Failed to send to {to_email}: {e}")
        return False


def send_notifications(notifications: dict[str, list[tuple[dict, dict]]], max_emails: int = 0) -> dict:
    """Send one email per department. Returns send stats.
    max_emails: if > 0, only send the N largest department emails.

    Reviewer-gate mode:
        Set REVIEWER_MODE=1 and REVIEWER_EMAIL=reviewer@cgi.com to route
        ALL per-department digests to a single reviewer mailbox instead of
        the real BU-leader addresses. Matches the MVP stakeholder directive
        "ei spämmää yet" — one human gates the first-wave emails, verifies
        the routing, and forwards manually. Remove the flag once pilot
        confirms routing quality.
    """
    sent = 0
    failed = 0
    previewed = 0
    delivered_tp_ids: set[str] = set()
    date_str = datetime.now().strftime("%d.%m.%Y")

    # Regroup: from email -> [(tender, rule)] to department -> {email, contact, tenders}
    by_department: dict[str, dict] = {}
    for email, tenders_with_rules in notifications.items():
        for tender, rule in tenders_with_rules:
            dept = rule.get("department", "General")
            if dept not in by_department:
                by_department[dept] = {
                    "email": rule.get("email", email),
                    "contact": rule.get("contact", "Team"),
                    "tenders": [],
                }
            by_department[dept]["tenders"].append(tender)

    # Limit to N largest departments if requested
    if max_emails > 0:
        by_department = dict(sorted(by_department.items(), key=lambda x: -len(x[1]["tenders"]))[:max_emails])

    # Reviewer-gate override
    reviewer_mode = os.getenv("REVIEWER_MODE", "0") == "1"
    reviewer_email = os.getenv("REVIEWER_EMAIL", "").strip()
    if reviewer_mode and not reviewer_email:
        print("  [REVIEWER] REVIEWER_MODE=1 but REVIEWER_EMAIL is empty — falling back to per-department addresses.")
        reviewer_mode = False
    if reviewer_mode:
        print(f"  [REVIEWER] Reviewer gate active. All digests → {reviewer_email} for human verification.")

    # Send one email per department
    for dept, info in by_department.items():
        tenders = info["tenders"]
        if not tenders:
            continue

        intended_email = info["email"]
        intended_contact = info["contact"]

        if reviewer_mode:
            target_email = reviewer_email
            subject = (
                f"[REVIEW → {dept}] {len(tenders)} new tenders ({date_str}) — "
                f"would go to {intended_email}"
            )
            html = build_email_html(
                intended_contact, dept, tenders,
                reviewer_banner={
                    "intended_email": intended_email,
                    "department": dept,
                },
            )
        else:
            target_email = intended_email
            subject = f"CGI Tender Alert: {dept} — {len(tenders)} new tenders ({date_str})"
            html = build_email_html(intended_contact, dept, tenders)

        # Build an iCal attachment with question + tender deadlines for this
        # department's tenders. None if no parseable deadlines were found.
        try:
            from .ical import build_tender_ics
            ics_body = build_tender_ics(tenders)
        except Exception as e:
            print(f"  [iCal] Failed to build .ics for {dept}: {type(e).__name__}: {e}")
            ics_body = None

        ics_filename = f"cgi_tender_deadlines_{dept.replace(' ', '_')}.ics"
        result = send_email(target_email, subject, html,
                            ics_body=ics_body, ics_filename=ics_filename)
        if result:
            sent += 1
            # Only tenders whose email actually went out should be marked
            # notified — otherwise a single SMTP failure silently consumes
            # this batch forever.
            for t in tenders:
                tp_id = t.get("tp_id")
                if tp_id:
                    delivered_tp_ids.add(str(tp_id))
        else:
            # Check if it was previewed (no SMTP) vs actual failure
            previewed += 1

    return {
        "sent": sent,
        "failed": failed,
        "previewed": previewed,
        "departments": len(by_department),
        "delivered_tp_ids": delivered_tp_ids,
    }
