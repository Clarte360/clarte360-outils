from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import SmtpSettings


def send_email(settings: SmtpSettings, subject: str, body: str, to_email: str | None = None, attachments: list[tuple[str, bytes, str]] | None = None) -> tuple[bool, str]:
    if not settings.configured:
        return False, "Configuration SMTP absente."
    recipient = to_email or settings.to_email
    if not recipient:
        return False, "Destinataire SMTP absent."
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.from_email
    msg["To"] = recipient
    msg.set_content(body)
    for filename, content, mime_type in attachments or []:
        maintype, _, subtype = str(mime_type or "application/octet-stream").partition("/")
        msg.add_attachment(content, maintype=maintype or "application", subtype=subtype or "octet-stream", filename=filename)
    try:
        with smtplib.SMTP_SSL(settings.server, settings.port, timeout=15) as smtp:
            smtp.login(settings.username, settings.password)
            smtp.send_message(msg)
        return True, "Message envoye."
    except Exception:
        return False, "Echec d'envoi SMTP. Verifier la configuration serveur."
