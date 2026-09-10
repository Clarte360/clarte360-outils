from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import SmtpSettings


def send_email(settings: SmtpSettings, subject: str, body: str, to_email: str | None = None) -> tuple[bool, str]:
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
    try:
        with smtplib.SMTP_SSL(settings.server, settings.port, timeout=15) as smtp:
            smtp.login(settings.username, settings.password)
            smtp.send_message(msg)
        return True, "Message envoye."
    except Exception:
        return False, "Echec d'envoi SMTP. Verifier la configuration serveur."
