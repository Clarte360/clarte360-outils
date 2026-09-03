from __future__ import annotations
import smtplib, ssl
from email.message import EmailMessage


def _ci_dict(d):
    return {str(k).lower(): v for k, v in dict(d or {}).items()}


def _pick(d, *names, default=None):
    low = _ci_dict(d)
    for name in names:
        if name.lower() in low and low[name.lower()] not in (None, ''):
            return low[name.lower()]
    return default


def resolve_mail_config(secrets_container):
    """Return one normalized mail configuration.

    V2.1 prefers the existing Clarte360 [MAIL] secret convention, while keeping
    backward compatibility with [mail] and legacy [smtp]. Key names are matched
    case-insensitively and several common aliases are accepted.
    """
    root = dict(secrets_container or {})
    section = root.get('MAIL') or root.get('mail') or root.get('smtp') or root.get('SMTP') or {}
    sec = _ci_dict(section)

    security = _pick(sec, 'security', 'encryption', 'mode', default=None)
    use_ssl = _pick(sec, 'use_ssl', 'ssl', default=None)
    use_tls = _pick(sec, 'use_tls', 'starttls', 'tls', default=None)
    if not security:
        if str(use_ssl).lower() in ('1','true','yes','on'):
            security = 'ssl'
        elif str(use_tls).lower() in ('1','true','yes','on'):
            security = 'starttls'
        else:
            security = 'ssl'

    enabled_raw = _pick(sec, 'enabled', 'active', default=True if section else False)
    enabled = str(enabled_raw).lower() not in ('0','false','no','off','none','')

    cfg = {
        'enabled': enabled,
        'host': _pick(sec, 'host', 'server', 'smtp_host', 'smtp_server'),
        'port': int(_pick(sec, 'port', 'smtp_port', default=465) or 465),
        'username': _pick(sec, 'username', 'user', 'login', 'smtp_username'),
        'password': _pick(sec, 'password', 'pass', 'smtp_password'),
        'from_email': _pick(sec, 'from_email', 'from_address', 'sender', 'sender_email', 'email'),
        'from_name': _pick(sec, 'from_name', 'sender_name', 'name', default='Clarté360'),
        'security': str(security).lower(),
        '_source': 'MAIL' if root.get('MAIL') else ('mail' if root.get('mail') else ('smtp' if root.get('smtp') else 'SMTP')),
    }
    return cfg


def validate_mail_config(cfg):
    missing=[]
    for key in ('host','from_email'):
        if not cfg.get(key): missing.append(key)
    if cfg.get('username') and not cfg.get('password'): missing.append('password')
    return missing


def send_mail(cfg, to_email, subject, html_body):
    missing=validate_mail_config(cfg)
    if missing:
        raise ValueError('Configuration email incomplète : '+', '.join(missing))
    msg=EmailMessage();msg['Subject']=subject;msg['From']=f"{cfg.get('from_name','Clarté360')} <{cfg['from_email']}>";msg['To']=to_email
    msg.set_content('Veuillez consulter ce message au format HTML.');msg.add_alternative(html_body,subtype='html')
    sec=str(cfg.get('security','ssl')).lower();host=cfg['host'];port=int(cfg.get('port',465))
    if sec=='ssl':
        with smtplib.SMTP_SSL(host,port,context=ssl.create_default_context()) as s:
            if cfg.get('username'):s.login(cfg['username'],cfg['password'])
            s.send_message(msg)
    else:
        with smtplib.SMTP(host,port,timeout=30) as s:
            if sec in ('starttls','tls'):s.starttls(context=ssl.create_default_context())
            if cfg.get('username'):s.login(cfg['username'],cfg['password'])
            s.send_message(msg)
