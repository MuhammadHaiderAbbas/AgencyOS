"""Email service.

Configured via SMTP env vars. If not configured we log to audit and print,
so the site stays completely working and earning-capable (demo notifications).
When SMTP is set we send real HTML emails via `smtplib`.

Env:
  SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_USE_TLS
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..config import settings
from ..db import db, now

log = logging.getLogger("agencyos.email")


def configured() -> bool:
    s = settings()
    return bool(s.smtp_host and s.smtp_from)


def _smtp_settings():
    s = settings()
    return s


def send_email(to: str, subject: str, html: str, text: str | None = None, org_id: str | None = None, kind: str = "generic") -> dict:
    s = _smtp_settings()
    # always log / store attempt
    try:
        db().insert("audit_logs", {"org_id": org_id, "action": f"email:{kind}", "target": to, "detail": subject[:120], "created_at": now()})
    except Exception:
        pass

    if not s.smtp_host or not s.smtp_from:
        # demo mode: pretend sent, log
        log.info("Email (mock) to=%s subject=%s", to, subject)
        return {"ok": True, "mock": True, "to": to}

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = s.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        alt = text or html.replace("<br>", "\n")
        msg.attach(MIMEText(alt, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
        host = s.smtp_host
        port = s.smtp_port or 587
        with smtplib.SMTP(host, port, timeout=15) as server:
            if s.smtp_use_tls:
                server.starttls()
            if s.smtp_user and s.smtp_password:
                server.login(s.smtp_user, s.smtp_password)
            server.sendmail(s.smtp_from, [to], msg.as_string())
        log.info("Email sent to %s (%s)", to, subject)
        return {"ok": True}
    except Exception as e:
        log.exception("Email failed to %s", to)
        return {"ok": False, "error": str(e)[:300]}


# convenience templates

def notify_deployment(to: str, project_name: str, url: str, org_id: str | None = None):
    return send_email(to, f"Your site {project_name} is live",
                      f"<h2>{project_name} is live 🚀</h2><p><a href='{url}'>{url}</a></p><p>Health check passed.</p>", org_id=org_id, kind="deploy")


def notify_booking_admin(admin_email: str, project_name: str, data: dict, org_id: str | None = None):
    rows = "".join(f"<tr><td style='padding:6px;border:1px solid #ddd'><b>{k}</b></td><td style='padding:6px;border:1px solid #ddd'>{v}</td></tr>" for k, v in data.items())
    return send_email(admin_email, f"New booking — {project_name}",
                      f"<h3>New booking for {project_name}</h3><table>{rows}</table>", org_id=org_id, kind="booking")


def notify_enquiry(admin_email: str, project_name: str, data: dict, org_id: str | None = None):
    return send_email(admin_email, f"New enquiry — {project_name}",
                      f"<h3>Enquiry for {project_name}</h3><p><b>{data.get('name')}</b> &lt;{data.get('email')}&gt;</p><p>{data.get('message')}</p>", org_id=org_id, kind="enquiry")
