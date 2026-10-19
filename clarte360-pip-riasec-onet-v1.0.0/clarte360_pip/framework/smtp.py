from __future__ import annotations
import logging
import smtplib
import ssl
from email.message import EmailMessage
from .config import SmtpSettings
from .validation import validate_email

LOG = logging.getLogger(__name__)
MESSAGES = {
    'CONFIG': "Le service d'envoi n'est pas configure. Le telechargement reste disponible.",
    'RECIPIENT': "L'adresse destinataire a ete refusee. Verifiez votre adresse e-mail.",
    'AUTH': "Le service d'envoi est temporairement indisponible (authentification).",
    'SENDER': "Le service d'envoi est temporairement indisponible (expediteur).",
    'CONTENT': "Le message ou sa piece jointe a ete refuse par le service d'envoi.",
    'CONNECTION': "La connexion au service d'envoi n'a pas abouti.",
    'TLS': "La connexion securisee au service d'envoi n'a pas abouti.",
    'MESSAGE': "Le message n'a pas pu etre prepare. Le telechargement reste disponible.",
    'SMTP': "L'envoi n'a pas abouti. Le telechargement reste disponible.",
}


def _failure(category, exc=None):
    # Never log smtp_error, recipients, settings, a token, a password or report content.
    code = getattr(exc, 'smtp_code', None)
    LOG.warning('PIP_MAIL_FAILED category=%s smtp_code=%s', category, code if isinstance(code, int) else '-')
    return False, MESSAGES[category]


def send_email(settings: SmtpSettings, subject: str, body: str, to_email: str | None = None,
               attachments: list[tuple[str, bytes, str]] | None = None) -> tuple[bool, str]:
    if not settings.configured:
        return _failure('CONFIG')
    try:
        recipient = validate_email(to_email or settings.to_email)
    except ValueError:
        return _failure('RECIPIENT')
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = settings.from_email
        msg['To'] = recipient
        msg.set_content(body)
        for filename, content, mime_type in attachments or []:
            maintype, _, subtype = str(mime_type or 'application/octet-stream').partition('/')
            msg.add_attachment(content, maintype=maintype or 'application', subtype=subtype or 'octet-stream', filename=filename)
        with smtplib.SMTP_SSL(settings.server, settings.port, timeout=15, context=ssl.create_default_context()) as smtp:
            smtp.login(settings.username, settings.password)
            refused = smtp.send_message(msg)
            if refused:
                return _failure('RECIPIENT')
        return True, 'Message accepte par le service de messagerie.'
    except smtplib.SMTPAuthenticationError as exc:
        return _failure('AUTH', exc)
    except smtplib.SMTPRecipientsRefused as exc:
        return _failure('RECIPIENT', exc)
    except smtplib.SMTPSenderRefused as exc:
        return _failure('SENDER', exc)
    except smtplib.SMTPDataError as exc:
        return _failure('CONTENT', exc)
    except ssl.SSLError as exc:
        return _failure('TLS', exc)
    except (smtplib.SMTPServerDisconnected, TimeoutError, ConnectionError) as exc:
        return _failure('CONNECTION', exc)
    except smtplib.SMTPException as exc:
        return _failure('SMTP', exc)
    except OSError as exc:
        return _failure('CONNECTION', exc)
    except (ValueError, TypeError) as exc:
        return _failure('MESSAGE', exc)
    except Exception as exc:
        return _failure('SMTP', exc)
