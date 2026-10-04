import re

from flask import Blueprint, current_app, jsonify, request

from backend.services.email import EmailNotConfiguredError, send_email
from backend.services.html import contact_email_html
from backend.utils import clean_text

public_bp = Blueprint("public", __name__)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@public_bp.route("/contact", methods=["POST"])
def contact():
    data = request.get_json() or {}
    try:
        name = clean_text(data.get("name"), "name", required=True, max_length=255)
        email = clean_text(data.get("email"), "email", required=True, max_length=255).lower()
        subject = clean_text(data.get("subject", "LedgerPulse website inquiry"), "subject", max_length=255)
        message = clean_text(data.get("message"), "message", required=True, max_length=10000)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not EMAIL_RE.fullmatch(email):
        return jsonify({"error": "Please enter a valid email address"}), 400

    destination = (current_app.config.get("CONTACT_INBOX_EMAIL") or current_app.config.get("SMTP_FROM_EMAIL") or "").strip()
    if not destination:
        return jsonify({"error": "Contact delivery is not configured", "message": "Configure CONTACT_INBOX_EMAIL or SMTP_FROM_EMAIL on the backend."}), 503

    body = f"New LedgerPulse website inquiry from {name} ({email}).\n\nSubject: {subject}\n\n{message}"
    html = contact_email_html(name, email, subject, message)
    try:
        message_id = send_email(
            to_email=destination,
            subject=f"LedgerPulse inquiry: {subject or 'Website contact'}",
            text_body=body,
            html_body=html,
            reply_to=email,
        )
    except EmailNotConfiguredError:
        return jsonify({"error": "Contact delivery is not configured", "message": "Configure SMTP on the backend before receiving website inquiries."}), 503
    except Exception:
        current_app.logger.exception("Contact form email delivery failed")
        return jsonify({"error": "Contact delivery failed", "message": "The inquiry could not be delivered. Please try again."}), 502

    return jsonify({"success": True, "messageId": message_id}), 200
