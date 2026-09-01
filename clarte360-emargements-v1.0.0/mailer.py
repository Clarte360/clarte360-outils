from __future__ import annotations
import smtplib, ssl
from email.message import EmailMessage

def send_mail(cfg, to_email, subject, html_body):
    msg=EmailMessage();msg['Subject']=subject;msg['From']=f"{cfg.get('from_name','Clarté360')} <{cfg['from_email']}>";msg['To']=to_email
    msg.set_content('Veuillez consulter ce message au format HTML.');msg.add_alternative(html_body,subtype='html')
    sec=cfg.get('security','ssl').lower();host=cfg['host'];port=int(cfg.get('port',465))
    if sec=='ssl':
        with smtplib.SMTP_SSL(host,port,context=ssl.create_default_context()) as s:
            if cfg.get('username'):s.login(cfg['username'],cfg['password'])
            s.send_message(msg)
    else:
        with smtplib.SMTP(host,port,timeout=30) as s:
            if sec=='starttls':s.starttls(context=ssl.create_default_context())
            if cfg.get('username'):s.login(cfg['username'],cfg['password'])
            s.send_message(msg)
