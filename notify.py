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
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def build_email_html(contact: str, department: str, tenders: list[dict]) -> str:
    """Build an HTML email body for a single department's tender digest."""

    date_str = datetime.now().strftime("%d.%m.%Y")

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

    for t in sorted(tenders, key=sort_key):
        name = t.get("name", "N/A")
        org = t.get("organisation", "")
        deadline = t.get("deadline", "No deadline specified")
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


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email via SMTP. Credentials from .env."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_user or not smtp_password:
        print(f"  [SMTP] No SMTP credentials in .env — email NOT sent to {to_email}")
        print(f"  [SMTP] Would have sent: {subject}")
        filename = f"email_preview_{to_email.replace('@', '_at_')}_{subject[:30].replace(' ', '_')}.html"
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_body)
        print(f"  [SMTP] Email preview saved to {filename}")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
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
    """
    sent = 0
    failed = 0
    previewed = 0
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

    # Send one email per department
    for dept, info in by_department.items():
        tenders = info["tenders"]
        if not tenders:
            continue

        subject = f"CGI Tender Alert: {dept} — {len(tenders)} new tenders ({date_str})"
        html = build_email_html(info["contact"], dept, tenders)

        result = send_email(info["email"], subject, html)
        if result:
            sent += 1
        else:
            # Check if it was previewed (no SMTP) vs actual failure
            previewed += 1

    return {"sent": sent, "failed": failed, "previewed": previewed, "departments": len(by_department)}
