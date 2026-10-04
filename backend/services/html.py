from html import escape


def invoice_email_html(company: str, invoice_number: str, issue_date: str, due_date: str, total: str, balance: str, terms: str, note: str = "") -> str:
    return f"""<!doctype html><html><body style=\"font-family:Arial,sans-serif;background:#f8fafc;padding:24px;color:#0f172a\"><div style=\"max-width:600px;margin:auto;background:white;border:1px solid #e2e8f0;border-radius:16px;padding:28px\"><h2>{escape(company)}</h2><p>Please find invoice <strong>{escape(invoice_number)}</strong> attached.</p><table style=\"width:100%;border-collapse:collapse\"><tr><td>Issue date</td><td>{escape(issue_date)}</td></tr><tr><td>Due date</td><td>{escape(due_date)}</td></tr><tr><td>Total</td><td><strong>{escape(total)}</strong></td></tr><tr><td>Balance due</td><td><strong>{escape(balance)}</strong></td></tr></table>{f'<p style=\"background:#fffbeb;padding:12px\">{escape(note)}</p>' if note else ''}<p><strong>Payment terms:</strong> {escape(terms)}</p><p>Sent via LedgerPulse.</p></div></body></html>"""


def contact_email_html(name: str, email: str, subject: str, message: str) -> str:
    return f"""<!doctype html><html><body style=\"font-family:Arial,sans-serif;background:#f8fafc;padding:24px;color:#0f172a\"><div style=\"max-width:640px;margin:auto;background:white;border:1px solid #e2e8f0;border-radius:16px;padding:28px\"><h2>New LedgerPulse website inquiry</h2><p><strong>Name:</strong> {escape(name)}</p><p><strong>Email:</strong> {escape(email)}</p><p><strong>Subject:</strong> {escape(subject or 'Website inquiry')}</p><hr style=\"border:none;border-top:1px solid #e2e8f0\"><p style=\"white-space:pre-wrap\">{escape(message)}</p></div></body></html>"""
