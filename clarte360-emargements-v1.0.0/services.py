from __future__ import annotations
import json, io, csv, zipfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from sqlalchemy import text
from db import q, one, execute, audit, new_token, utcnow_iso
from security import hash_password

ROOT=Path(__file__).resolve().parent
SIG_DIR=ROOT/'data'/'signatures'; SIG_DIR.mkdir(parents=True,exist_ok=True)

def parse_dt(date_s,time_s,tz_name='Europe/Paris'):
    return datetime.fromisoformat(f"{date_s}T{time_s}").replace(tzinfo=ZoneInfo(tz_name))

def slot_duration_hours(slot):
    a=datetime.fromisoformat(f"2000-01-01T{slot['start_time']}")
    b=datetime.fromisoformat(f"2000-01-01T{slot['end_time']}")
    if b<=a: b+=timedelta(days=1)
    return round((b-a).total_seconds()/3600,2)

def create_action(engine, d, actor):
    now=utcnow_iso()
    aid=execute(engine,"""INSERT INTO actions(action_no,title,subtitle,nature,mode,client_name,client_type,group_code,planned_hours,expected_participants,status,admin_email,trainer_name,trainer_email,location,notes,source,created_at,updated_at)
    VALUES(:action_no,:title,:subtitle,:nature,:mode,:client_name,:client_type,:group_code,:planned_hours,:expected_participants,'BROUILLON',:admin_email,:trainer_name,:trainer_email,:location,:notes,:source,:created_at,:updated_at)""",{**d,"created_at":now,"updated_at":now})
    audit(engine,'ACTION_CREATED',aid,actor,'action',aid,d); return aid

def update_action(engine, aid, d, actor):
    keys=['title','subtitle','nature','mode','client_name','client_type','group_code','planned_hours','expected_participants','admin_email','trainer_name','trainer_email','location','notes','status']
    sets=','.join(f"{k}=:{k}" for k in keys)
    p={k:d.get(k) for k in keys};p.update({'id':aid,'u':utcnow_iso()})
    execute(engine,f"UPDATE actions SET {sets},updated_at=:u WHERE id=:id",p);audit(engine,'ACTION_UPDATED',aid,actor,'action',aid,d)

def add_participant(engine, aid, d, actor):
    pin = d.pop('pin', None) or f"{__import__('secrets').randbelow(10000):04d}"
    pid=execute(engine,"""INSERT INTO participants(action_id,individual_action_no,last_name,birth_name,first_name,birth_date,email,employee_id,company_name,phone,pin_hash,created_at)
    VALUES(:aid,:individual_action_no,:last_name,:birth_name,:first_name,:birth_date,:email,:employee_id,:company_name,:phone,:pin_hash,:created_at)""",{
     'aid':aid, **{k:d.get(k) for k in ['individual_action_no','last_name','birth_name','first_name','birth_date','email','employee_id','company_name','phone']},
     'pin_hash':hash_password(pin),'created_at':utcnow_iso()})
    audit(engine,'PARTICIPANT_ADDED',aid,actor,'participant',pid,{'last_name':d.get('last_name'),'first_name':d.get('first_name')})
    return pid,pin

def delete_participant(engine,pid,actor):
    p=one(engine,'SELECT action_id,last_name,first_name FROM participants WHERE id=:id',{'id':pid});
    if not p:return
    execute(engine,'DELETE FROM participants WHERE id=:id',{'id':pid});audit(engine,'PARTICIPANT_DELETED',p['action_id'],actor,'participant',pid,p)

def add_slot(engine, aid, date_s,start_s,end_s,actor,send=-10,r1=20,r2=120,close=1440):
    now=utcnow_iso(); public=new_token(18)
    sid=execute(engine,"""INSERT INTO slots(action_id,slot_date,start_time,end_time,original_start_time,original_end_time,send_offset_min,reminder1_offset_min,reminder2_offset_min,close_offset_min,public_token,created_at,updated_at)
      VALUES(:a,:d,:s,:e,:s,:e,:send,:r1,:r2,:close,:t,:c,:c)""",{'a':aid,'d':date_s,'s':start_s,'e':end_s,'send':send,'r1':r1,'r2':r2,'close':close,'t':public,'c':now})
    audit(engine,'SLOT_ADDED',aid,actor,'slot',sid,{'date':date_s,'start':start_s,'end':end_s});return sid

def update_slot(engine,sid,d,actor):
    old=one(engine,'SELECT * FROM slots WHERE id=:id',{'id':sid});
    if not old:return
    execute(engine,"""UPDATE slots SET slot_date=:slot_date,start_time=:start_time,end_time=:end_time,send_offset_min=:send_offset_min,reminder1_offset_min=:reminder1_offset_min,reminder2_offset_min=:reminder2_offset_min,close_offset_min=:close_offset_min,updated_at=:u WHERE id=:id""",{**d,'u':utcnow_iso(),'id':sid})
    audit(engine,'SLOT_UPDATED',old['action_id'],actor,'slot',sid,{'before':old,'after':d})

def delete_slot(engine,sid,actor):
    old=one(engine,'SELECT * FROM slots WHERE id=:id',{'id':sid});
    if not old:return False,'Créneau introuvable.'
    signed=one(engine,'SELECT COUNT(*) n FROM signatures WHERE slot_id=:id',{'id':sid})['n']
    if signed:return False,"Impossible : ce créneau contient déjà des signatures."
    execute(engine,'DELETE FROM slots WHERE id=:id',{'id':sid});audit(engine,'SLOT_DELETED',old['action_id'],actor,'slot',sid,old);return True,''

def ensure_tokens_and_events(engine, aid, base_url,tz_name='Europe/Paris'):
    participants=q(engine,'SELECT * FROM participants WHERE action_id=:a AND active=1',{'a':aid})
    slots=q(engine,'SELECT * FROM slots WHERE action_id=:a',{'a':aid})
    for p in participants:
      for s in slots:
        tok=one(engine,'SELECT * FROM signature_tokens WHERE participant_id=:p AND slot_id=:s',{'p':p['id'],'s':s['id']})
        if not tok:
          token=new_token(24); execute(engine,'INSERT INTO signature_tokens(participant_id,slot_id,token,created_at) VALUES(:p,:s,:t,:c)',{'p':p['id'],'s':s['id'],'t':token,'c':utcnow_iso()})
        end=parse_dt(s['slot_date'],s['end_time'],tz_name)
        timings={'INITIAL':s['send_offset_min'],'RELANCE_1':s['reminder1_offset_min'],'RELANCE_2':s['reminder2_offset_min']}
        for et,off in timings.items():
          due=(end+timedelta(minutes=off)).astimezone(ZoneInfo('UTC')).isoformat()
          execute(engine,"""INSERT OR IGNORE INTO email_events(participant_id,slot_id,event_type,due_at) VALUES(:p,:s,:e,:d)""",{'p':p['id'],'s':s['id'],'e':et,'d':due})
          execute(engine,"""UPDATE email_events SET due_at=:d WHERE participant_id=:p AND slot_id=:s AND event_type=:e AND status='PENDING'""",{'p':p['id'],'s':s['id'],'e':et,'d':due})
    audit(engine,'SIGNATURE_REQUESTS_PREPARED',aid,'system','action',aid,{'base_url':base_url})

def token_url(engine,participant_id,slot_id,base_url):
    t=one(engine,'SELECT token FROM signature_tokens WHERE participant_id=:p AND slot_id=:s',{'p':participant_id,'s':slot_id})
    return f"{base_url.rstrip('/')}?token={t['token']}" if t else None

def public_slot_url(slot,base_url): return f"{base_url.rstrip('/')}?slot_token={slot['public_token']}"

def action_progress(engine,aid):
    pc=one(engine,'SELECT COUNT(*) n FROM participants WHERE action_id=:a AND active=1',{'a':aid})['n']
    sc=one(engine,'SELECT COUNT(*) n FROM slots WHERE action_id=:a',{'a':aid})['n']
    sig=one(engine,'SELECT COUNT(*) n FROM signatures x JOIN participants p ON p.id=x.participant_id WHERE p.action_id=:a AND x.status="VALIDE"',{'a':aid})['n']
    expected=pc*sc
    return {'participants':pc,'slots':sc,'signed':sig,'expected':expected,'percent':round(sig*100/expected) if expected else 0}

def actual_hours_for_participant(engine,pid):
    rows=q(engine,'SELECT s.* FROM signatures x JOIN slots s ON s.id=x.slot_id WHERE x.participant_id=:p AND x.status="VALIDE"',{'p':pid})
    return round(sum(slot_duration_hours(s) for s in rows),2)

def export_action_json(engine,aid):
    data={
      'format':'CLARTE360-EMARGEMENTS','version':'1.0','exported_at':utcnow_iso(),
      'action':one(engine,'SELECT * FROM actions WHERE id=:a',{'a':aid}),
      'participants':q(engine,'SELECT id,action_id,individual_action_no,last_name,birth_name,first_name,birth_date,email,employee_id,company_name,phone,active,created_at FROM participants WHERE action_id=:a',{'a':aid}),
      'slots':q(engine,'SELECT * FROM slots WHERE action_id=:a',{'a':aid}),
      'signatures':q(engine,'SELECT x.* FROM signatures x JOIN participants p ON p.id=x.participant_id WHERE p.action_id=:a',{'a':aid}),
      'audit':q(engine,'SELECT * FROM audit_log WHERE action_id=:a ORDER BY id',{'a':aid}),
    }
    return json.dumps(data,ensure_ascii=False,indent=2,default=str).encode('utf-8')

def export_action_zip(engine,aid,pdf_files:dict[str,bytes]|None=None):
    js=export_action_json(engine,aid); buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
      z.writestr('action.json',js)
      if pdf_files:
        for name,b in pdf_files.items(): z.writestr(f'documents/{name}',b)
      sigs=q(engine,'SELECT x.signature_path FROM signatures x JOIN participants p ON p.id=x.participant_id WHERE p.action_id=:a',{'a':aid})
      for s in sigs:
        p=Path(s['signature_path'])
        if p.exists(): z.write(p,f'signatures/{p.name}')
    return buf.getvalue()
