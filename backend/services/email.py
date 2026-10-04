import smtplib
import uuid
from email.message import EmailMessage
from typing import Optional

from flask import current_app


class EmailNotConfiguredError(RuntimeError):
    pass


def _configured() -> bool:
    return bool(
        current_app.config.get("SMTP_HOST")
        and current_app.config.get("SMTP_FROM_EMAIL")
    )


def send_email(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
    attachment_name: Optional[str] = None,
    attachment_bytes: Optional[bytes] = None,
    reply_to: Optional[str] = None,
) -> str:
    if not _configured():
        raise EmailNotConfiguredError("SMTP is not configured")

    message = EmailMessage()
    from_name = current_app.config.get("SMTP_FROM_NAME") or "LedgerPulse"
    message["From"] = f"{from_name} <{current_app.config['SMTP_FROM_EMAIL']}>"
    message["To"] = to_email
    message["Subject"] = subject
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    if attachment_name and attachment_bytes is not None:
        message.add_attachment(
            attachment_bytes,
            maintype="application",
            subtype="pdf",
            filename=attachment_name,
        )

    host = current_app.config["SMTP_HOST"]
    port = current_app.config["SMTP_PORT"]
    use_ssl = current_app.config.get("SMTP_USE_SSL", False)
    use_tls = current_app.config.get("SMTP_USE_TLS", True)

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
            if current_app.config.get("SMTP_USERNAME"):
                smtp.login(current_app.config["SMTP_USERNAME"], current_app.config.get("SMTP_PASSWORD", ""))
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.ehlo()
            if use_tls:
                smtp.starttls()
                smtp.ehlo()
            if current_app.config.get("SMTP_USERNAME"):
                smtp.login(current_app.config["SMTP_USERNAME"], current_app.config.get("SMTP_PASSWORD", ""))
            smtp.send_message(message)

    return f"msg_{uuid.uuid4().hex}"
