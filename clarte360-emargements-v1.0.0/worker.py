from __future__ import annotations
import os,time
from datetime import datetime, timezone
from db import make_engine,init_db,q,execute,audit,one
from services import token_url
from mailer import send_mail

try:
 import tomllib
except ImportError:
 import tomli as tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def load_cfg():
    p=ROOT/'.streamlit'/'secrets.toml'
    data={}
    if p.exists(): data=tomllib.loads(p.read_text(encoding='utf-8'))
    return data

def run_once():
    cfg=load_cfg(); dburl=(cfg.get('database') or {}).get('url'); eng=make_engine(dburl);init_db(eng)
    smtp=cfg.get('smtp') or {}; app=cfg.get('app') or {}; base=app.get('base_url','http://localhost:8501')
    if not smtp.get('enabled'): return 0
    now=datetime.now(timezone.utc).isoformat()
    events=q(eng,"""SELECT e.*,p.email,p.first_name,p.last_name,a.title,a.action_no,s.slot_date,s.start_time,s.end_time
       FROM email_events e JOIN participants p ON p.id=e.participant_id JOIN slots s ON s.id=e.slot_id JOIN actions a ON a.id=p.action_id
       WHERE e.status='PENDING' AND e.due_at<=:n AND p.email IS NOT NULL AND TRIM(p.email)<>'' ORDER BY e.due_at LIMIT 50""",{'n':now})
    sent=0
    for e in events:
        if one(eng,'SELECT id FROM signatures WHERE participant_id=:p AND slot_id=:s AND status="VALIDE"',{'p':e['participant_id'],'s':e['slot_id']}):
            execute(eng,'UPDATE email_events SET status="SKIPPED" WHERE id=:id',{'id':e['id']});continue
        url=token_url(eng,e['participant_id'],e['slot_id'],base)
        label={'INITIAL':'demande d’émargement','RELANCE_1':'rappel d’émargement','RELANCE_2':'dernier rappel d’émargement'}.get(e['event_type'],'émargement')
        subject=f"Clarté360 — {label} — {e['action_no']}"
        body=f"""<p>Bonjour {e['first_name']},</p><p>Merci d'émarger votre présence pour <strong>{e['title']}</strong>, le {e['slot_date']} de {e['start_time']} à {e['end_time']}.</p><p><a href='{url}' style='background:#008080;color:white;padding:12px 18px;text-decoration:none;border-radius:8px'>SIGNER MA PRÉSENCE</a></p><p>Ce lien est personnel.</p>"""
        try:
            send_mail(smtp,e['email'],subject,body);execute(eng,'UPDATE email_events SET status="SENT",sent_at=:s,attempts=attempts+1 WHERE id=:id',{'s':datetime.now(timezone.utc).isoformat(),'id':e['id']});sent+=1
        except Exception as ex:
            execute(eng,'UPDATE email_events SET attempts=attempts+1,last_error=:er WHERE id=:id',{'er':str(ex)[:500],'id':e['id']})
    return sent

if __name__=='__main__':
    print('Clarté360 worker démarré')
    while True:
        try: run_once()
        except Exception as e: print('worker error',e)
        time.sleep(60)
