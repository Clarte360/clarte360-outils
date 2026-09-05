from __future__ import annotations
import json, io, csv, zipfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from sqlalchemy import text
from db import q, one, execute, audit, new_token, utcnow_iso
from security import hash_password, verify_password, seal_short_secret, open_short_secret

ROOT=Path(__file__).resolve().parent
SIG_DIR=ROOT/'data'/'signatures'; SIG_DIR.mkdir(parents=True,exist_ok=True)

def parse_dt(date_s,time_s,tz_name='Europe/Paris'):
    return datetime.fromisoformat(f"{date_s}T{time_s}").replace(tzinfo=ZoneInfo(tz_name))

def slot_duration_hours(slot):
    a=datetime.fromisoformat(f"2000-01-01T{slot['start_time']}")
    b=datetime.fromisoformat(f"2000-01-01T{slot['end_time']}")
    if b<=a: b+=timedelta(days=1)
    return round((b-a).total_seconds()/3600,2)


def slot_start_end(slot, tz_name='Europe/Paris'):
    start=parse_dt(slot['slot_date'],slot['start_time'],tz_name)
    end=parse_dt(slot['slot_date'],slot['end_time'],tz_name)
    if end<=start:
        end+=timedelta(days=1)
    return start,end

def email_event_due_utc(slot,event_type,tz_name='Europe/Paris'):
    start,end=slot_start_end(slot,tz_name)
    if event_type=='INITIAL':
        due=end+timedelta(minutes=int(slot.get('send_offset_min') or 0))
    elif event_type=='RELANCE_1':
        due=end+timedelta(minutes=int(slot.get('reminder1_offset_min') or 0))
    elif event_type=='RELANCE_2':
        due=end+timedelta(minutes=int(slot.get('reminder2_offset_min') or 0))
    else:
        raise ValueError(f'Type d’événement inconnu : {event_type}')
    return due.astimezone(ZoneInfo('UTC'))

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
    try: pin_cipher=seal_short_secret(pin)
    except Exception: pin_cipher=None
    pid=execute(engine,"""INSERT INTO participants(action_id,individual_action_no,last_name,birth_name,first_name,birth_date,email,employee_id,company_name,phone,pin_hash,pin_recovery_cipher,created_at)
    VALUES(:aid,:individual_action_no,:last_name,:birth_name,:first_name,:birth_date,:email,:employee_id,:company_name,:phone,:pin_hash,:pin_recovery_cipher,:created_at)""",{
     'aid':aid, **{k:d.get(k) for k in ['individual_action_no','last_name','birth_name','first_name','birth_date','email','employee_id','company_name','phone']},
     'pin_hash':hash_password(pin),'pin_recovery_cipher':pin_cipher,'created_at':utcnow_iso()})
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
        for et in ('INITIAL','RELANCE_1','RELANCE_2'):
          due=email_event_due_utc(s,et,tz_name).isoformat()
          execute(engine,"""INSERT OR IGNORE INTO email_events(participant_id,slot_id,event_type,due_at) VALUES(:p,:s,:e,:d)""",{'p':p['id'],'s':s['id'],'e':et,'d':due})
          execute(engine,"""UPDATE email_events SET due_at=:d,last_error=NULL WHERE participant_id=:p AND slot_id=:s AND event_type=:e AND status='PENDING'""",{'p':p['id'],'s':s['id'],'e':et,'d':due})
    audit(engine,'SIGNATURE_REQUESTS_PREPARED',aid,'system','action',aid,{'base_url':base_url})



def activate_action(engine, aid, actor):
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':aid})
    if not a: return False,['Action introuvable.']
    issues=[]
    participants=q(engine,'SELECT * FROM participants WHERE action_id=:a AND active=1',{'a':aid})
    slots=q(engine,'SELECT * FROM slots WHERE action_id=:a ORDER BY slot_date,start_time',{'a':aid})
    if not participants: issues.append('Aucun participant actif.')
    if bool(a.get('use_attendance',1)) and not slots: issues.append("Aucun créneau d'émargement.")
    if bool(a.get('use_attendance',1)) and slots and float(a.get('planned_hours') or 0)>0:
        total=round(sum(slot_duration_hours(x) for x in slots),2)
        planned=round(float(a.get('planned_hours') or 0),2)
        if abs(total-planned)>0.01:
            issues.append(f'Calendrier incohérent : {total:g} h planifiées pour {planned:g} h prévues.')
    if bool(a.get('use_attendance',1)):
        missing=[f"{x['first_name']} {x['last_name']}" for x in participants if not (x.get('email') or '').strip()]
        if missing: issues.append('Email manquant pour : '+', '.join(missing))
    if issues: return False,issues
    execute(engine,"UPDATE actions SET status='ACTIVE',updated_at=:u WHERE id=:a",{'u':utcnow_iso(),'a':aid})
    audit(engine,'ACTION_ACTIVATED',aid,actor,'action',aid,{'participants':len(participants),'slots':len(slots)})
    return True,[]

def set_action_draft(engine, aid, actor, reason='Retour en brouillon'):
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':aid})
    if not a: return False,'Action introuvable.'
    execute(engine,"UPDATE actions SET status='BROUILLON',updated_at=:u WHERE id=:a",{'u':utcnow_iso(),'a':aid})
    audit(engine,'ACTION_RETURNED_TO_DRAFT',aid,actor,'action',aid,{'reason':reason})
    return True,''

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
      'format':'CLARTE360-EMARGEMENTS','version':'1.1.1','exported_at':utcnow_iso(),
      'action':one(engine,'SELECT * FROM actions WHERE id=:a',{'a':aid}),
      'participants':q(engine,'SELECT id,action_id,individual_action_no,last_name,birth_name,first_name,birth_date,email,employee_id,company_name,phone,active,created_at FROM participants WHERE action_id=:a',{'a':aid}),
      'slots':q(engine,'SELECT * FROM slots WHERE action_id=:a',{'a':aid}),
      'signatures':q(engine,'SELECT x.* FROM signatures x JOIN participants p ON p.id=x.participant_id WHERE p.action_id=:a',{'a':aid}),
      'attendance':q(engine,'SELECT x.* FROM attendance_status x JOIN participants p ON p.id=x.participant_id WHERE p.action_id=:a',{'a':aid}),
      'trainer_countersignatures':q(engine,'SELECT x.* FROM trainer_countersignatures x JOIN slots s ON s.id=x.slot_id WHERE s.action_id=:a',{'a':aid}),
      'email_events':q(engine,'SELECT e.* FROM email_events e JOIN participants p ON p.id=e.participant_id WHERE p.action_id=:a',{'a':aid}),
      'quality_campaigns':q(engine,'SELECT * FROM quality_campaigns WHERE action_id=:a',{'a':aid}),
      'quality_responses':q(engine,'SELECT r.* FROM quality_responses r JOIN quality_campaigns c ON c.id=r.campaign_id WHERE c.action_id=:a',{'a':aid}),
      'quality_email_events':q(engine,'SELECT e.* FROM quality_email_events e JOIN quality_campaigns c ON c.id=e.campaign_id WHERE c.action_id=:a',{'a':aid}),
      'quality_issues':q(engine,'SELECT * FROM quality_issues WHERE action_id=:a',{'a':aid}),
      'improvement_actions':q(engine,'SELECT * FROM improvement_actions WHERE action_id=:a',{'a':aid}),
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

# ---- V1.1 attendance, rescheduling, catch-up and trainer functions ----
def local_dt(iso_value, tz_name='Europe/Paris'):
    if not iso_value: return None
    dt=datetime.fromisoformat(iso_value)
    if dt.tzinfo is None: dt=dt.replace(tzinfo=ZoneInfo('UTC'))
    return dt.astimezone(ZoneInfo(tz_name))

def participant_duplicate(engine, aid, last_name, first_name, birth_date=None, email=None):
    rows=q(engine,"SELECT * FROM participants WHERE action_id=:a AND UPPER(last_name)=UPPER(:l) AND UPPER(first_name)=UPPER(:f)",{'a':aid,'l':last_name.strip(),'f':first_name.strip()})
    for r in rows:
        if birth_date and r.get('birth_date')==birth_date: return r
        if email and r.get('email') and r['email'].lower()==email.strip().lower(): return r
    return None

def set_attendance_status(engine,pid,sid,status,reason,actor):
    p=one(engine,'SELECT action_id FROM participants WHERE id=:p',{'p':pid}); now=utcnow_iso()
    sig=one(engine,"SELECT id FROM signatures WHERE participant_id=:p AND slot_id=:s AND status='VALIDE'",{'p':pid,'s':sid})
    if status=='ABSENT' and sig:
        return False, "Impossible de déclarer ABSENT : une signature valide existe déjà pour ce créneau."
    execute(engine,"""INSERT INTO attendance_status(participant_id,slot_id,status,reason,actor,created_at,updated_at)
      VALUES(:p,:s,:st,:r,:a,:n,:n) ON CONFLICT(participant_id,slot_id) DO UPDATE SET status=excluded.status,reason=excluded.reason,actor=excluded.actor,updated_at=excluded.updated_at""",
      {'p':pid,'s':sid,'st':status,'r':reason or None,'a':actor,'n':now})
    audit(engine,'ATTENDANCE_STATUS_CHANGED',p['action_id'] if p else None,actor,'attendance',f'{pid}/{sid}',{'status':status,'reason':reason})
    return True, ''

def create_catchup_slot(engine, original_sid, date_s,start_s,end_s, participant_ids, actor, reason='Rattrapage'):
    old=one(engine,'SELECT * FROM slots WHERE id=:s',{'s':original_sid})
    sid=add_slot(engine,old['action_id'],date_s,start_s,end_s,actor,old['send_offset_min'],old['reminder1_offset_min'],old['reminder2_offset_min'],old['close_offset_min'])
    execute(engine,"UPDATE slots SET parent_slot_id=:p,slot_kind='RATTRAPAGE',change_reason=:r WHERE id=:s",{'p':original_sid,'r':reason,'s':sid})
    # Only selected participants are expected on this catch-up slot.
    allp=q(engine,'SELECT id FROM participants WHERE action_id=:a AND active=1',{'a':old['action_id']})
    selected=set(int(x) for x in participant_ids)
    for p in allp:
        if p['id'] not in selected: set_attendance_status(engine,p['id'],sid,'NON_CONCERNE','Non inscrit au rattrapage',actor)
    audit(engine,'CATCHUP_SLOT_CREATED',old['action_id'],actor,'slot',sid,{'parent_slot_id':original_sid,'participants':list(selected)})
    return sid

def safe_update_slot(engine,sid,d,actor):
    evidence=one(engine,"SELECT (SELECT COUNT(*) FROM signatures WHERE slot_id=:s)+(SELECT COUNT(*) FROM attendance_status WHERE slot_id=:s AND status IN ('ABSENT','PRESENT_REGULARISE')) n",{'s':sid})['n']
    if evidence: return False,"Ce créneau contient déjà une preuve (signature/absence). Il ne peut plus être réécrit : utilisez Report / Rattrapage."
    update_slot(engine,sid,d,actor); return True,''

def trainer_token(engine,aid):
    t=one(engine,'SELECT token FROM trainer_access_tokens WHERE action_id=:a AND active=1 ORDER BY id DESC',{'a':aid})
    if t:return t['token']
    token=new_token(24);execute(engine,'INSERT INTO trainer_access_tokens(action_id,token,created_at) VALUES(:a,:t,:c)',{'a':aid,'t':token,'c':utcnow_iso()});return token

def trainer_url(engine,aid,base_url): return f"{base_url.rstrip('/')}?trainer_token={trainer_token(engine,aid)}"

def countersign_slot(engine,sid,name,email,actor,declaration):
    s=one(engine,'SELECT action_id FROM slots WHERE id=:s',{'s':sid})
    execute(engine,"""INSERT INTO trainer_countersignatures(slot_id,trainer_name,trainer_email,signed_at,declaration_text,method,actor)
      VALUES(:s,:n,:e,:at,:d,'NOM_PRENOM',:a) ON CONFLICT(slot_id) DO UPDATE SET trainer_name=excluded.trainer_name,trainer_email=excluded.trainer_email,signed_at=excluded.signed_at,declaration_text=excluded.declaration_text,actor=excluded.actor""",
      {'s':sid,'n':name,'e':email or None,'at':utcnow_iso(),'d':declaration,'a':actor})
    audit(engine,'TRAINER_COUNTERSIGNED',s['action_id'] if s else None,actor,'slot',sid,{'trainer_name':name})

def can_issue_certificate(engine,pid):
    p=one(engine,'SELECT action_id FROM participants WHERE id=:p',{'p':pid});
    if not p:return False,['Participant introuvable']
    slots=q(engine,"SELECT * FROM slots WHERE action_id=:a AND status NOT IN ('ANNULE','REPORTE')",{'a':p['action_id']}); problems=[]
    for s in slots:
        att=one(engine,'SELECT status FROM attendance_status WHERE participant_id=:p AND slot_id=:s',{'p':pid,'s':s['id']})
        sig=one(engine,"SELECT id FROM signatures WHERE participant_id=:p AND slot_id=:s AND status='VALIDE'",{'p':pid,'s':s['id']})
        if att and att['status']=='NON_CONCERNE': continue
        if att and att['status']=='ABSENT': problems.append(f"Absence non rattrapée sur le créneau #{s['id']}"); continue
        if not sig: problems.append(f"Signature manquante sur le créneau #{s['id']}")
        if not one(engine,'SELECT id FROM trainer_countersignatures WHERE slot_id=:s',{'s':s['id']}): problems.append(f"Contresignature intervenant manquante sur le créneau #{s['id']}")
    return not problems,problems

def update_participant(engine,pid,d,actor):
    p=one(engine,'SELECT * FROM participants WHERE id=:p',{'p':pid})
    if not p: return False,'Participant introuvable.'
    keys=['individual_action_no','last_name','birth_name','first_name','birth_date','email','employee_id','company_name','phone','active']
    vals={k:d.get(k,p.get(k)) for k in keys}; vals['p']=pid
    execute(engine,'UPDATE participants SET '+','.join(f'{k}=:{k}' for k in keys)+' WHERE id=:p',vals)
    audit(engine,'PARTICIPANT_UPDATED',p['action_id'],actor,'participant',pid,{'before':{k:p.get(k) for k in keys},'after':vals})
    return True,''

def reset_participant_pin(engine,pid,actor):
    import secrets
    p=one(engine,'SELECT action_id FROM participants WHERE id=:p',{'p':pid})
    if not p: return None
    pin=f'{secrets.randbelow(10000):04d}'
    try: cipher=seal_short_secret(pin)
    except Exception: cipher=None
    execute(engine,'UPDATE participants SET pin_hash=:h,pin_recovery_cipher=:c WHERE id=:p',{'h':hash_password(pin),'c':cipher,'p':pid})
    audit(engine,'PARTICIPANT_PIN_RESET',p['action_id'],actor,'participant',pid,{})
    return pin

def participant_pin_for_authorized_display(engine,pid,actor,action_id=None):
    p=one(engine,'SELECT id,action_id,pin_recovery_cipher FROM participants WHERE id=:p',{'p':pid})
    if not p or (action_id is not None and int(p['action_id'])!=int(action_id)): return None
    pin=open_short_secret(p.get('pin_recovery_cipher'))
    audit(engine,'PARTICIPANT_PIN_VIEWED',p['action_id'],actor,'participant',pid,{'recoverable':bool(pin)})
    return pin

def report_slot(engine,sid,date_s,start_s,end_s,actor,reason='Report'):
    old=one(engine,'SELECT * FROM slots WHERE id=:s',{'s':sid})
    if not old: return None
    evidence=one(engine,"SELECT (SELECT COUNT(*) FROM signatures WHERE slot_id=:s)+(SELECT COUNT(*) FROM attendance_status WHERE slot_id=:s AND status='ABSENT') n",{'s':sid})['n']
    if evidence: return None
    execute(engine,"UPDATE slots SET status='REPORTE',change_reason=:r,updated_at=:u WHERE id=:s",{'r':reason,'u':utcnow_iso(),'s':sid})
    ns=add_slot(engine,old['action_id'],date_s,start_s,end_s,actor,old['send_offset_min'],old['reminder1_offset_min'],old['reminder2_offset_min'],old['close_offset_min'])
    execute(engine,"UPDATE slots SET parent_slot_id=:p,slot_kind='REPORT',change_reason=:r WHERE id=:s",{'p':sid,'r':reason,'s':ns})
    audit(engine,'SLOT_REPORTED',old['action_id'],actor,'slot',ns,{'from_slot_id':sid,'reason':reason})
    return ns

def catchup_for_absence(engine,pid,original_sid):
    rows=q(engine,"SELECT s.* FROM slots s WHERE s.parent_slot_id=:o AND s.slot_kind='RATTRAPAGE' AND s.status NOT IN ('ANNULE','REPORTE')",{'o':original_sid})
    for s in rows:
        att=one(engine,'SELECT status FROM attendance_status WHERE participant_id=:p AND slot_id=:s',{'p':pid,'s':s['id']})
        if att and att['status']=='NON_CONCERNE': continue
        sig=one(engine,"SELECT id FROM signatures WHERE participant_id=:p AND slot_id=:s AND status='VALIDE'",{'p':pid,'s':s['id']})
        if sig: return s
    return None

# Replace certificate completeness logic with catch-up aware version.
def can_issue_certificate(engine,pid, require_closed=False):
    p=one(engine,'SELECT action_id FROM participants WHERE id=:p',{'p':pid})
    if not p:return False,['Participant introuvable']
    action=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':p['action_id']})
    problems=[]
    if require_closed and action and normalize_action_status(action.get('status')) not in ('CLOTUREE','ARCHIVEE'):
        problems.append("Action non clôturée.")
    slots=q(engine,"SELECT * FROM slots WHERE action_id=:a AND status NOT IN ('ANNULE','REPORTE') ORDER BY slot_date,start_time",{'a':p['action_id']})
    tz_name=organization_runtime_config(engine,p['action_id'])['timezone'];now=datetime.now(ZoneInfo(tz_name))
    for sl in slots:
        att=one(engine,'SELECT status FROM attendance_status WHERE participant_id=:p AND slot_id=:s',{'p':pid,'s':sl['id']})
        sig=one(engine,"SELECT id FROM signatures WHERE participant_id=:p AND slot_id=:s AND status='VALIDE'",{'p':pid,'s':sl['id']})
        if att and att['status']=='NON_CONCERNE': continue
        # A valid signature always takes precedence over a stale absence marker.
        if sig:
            if not one(engine,'SELECT id FROM trainer_countersignatures WHERE slot_id=:s',{'s':sl['id']}):
                problems.append(f"Contresignature intervenant manquante sur le créneau #{sl['id']}")
            continue
        if att and att['status']=='ABSENT':
            if not one(engine,'SELECT id FROM trainer_countersignatures WHERE slot_id=:s',{'s':sl['id']}):
                problems.append(f"Contresignature intervenant manquante sur le créneau absent #{sl['id']}")
            if not catchup_for_absence(engine,pid,sl['id']):
                problems.append(f"Absence non rattrapée sur le créneau #{sl['id']}")
            continue
        try:
            if parse_dt(sl['slot_date'],sl['end_time']) > now:
                problems.append(f"Créneau #{sl['id']} non encore achevé")
                continue
        except Exception: pass
        problems.append(f"Signature manquante sur le créneau #{sl['id']}")
        if not one(engine,'SELECT id FROM trainer_countersignatures WHERE slot_id=:s',{'s':sl['id']}):
            problems.append(f"Contresignature intervenant manquante sur le créneau #{sl['id']}")
    return not problems,problems


def action_can_close(engine, aid):
    parts=q(engine,'SELECT id FROM participants WHERE action_id=:a AND active=1',{'a':aid})
    issues=[]
    for p in parts:
        ok,pp=can_issue_certificate(engine,p['id'],require_closed=False)
        issues.extend(pp)
    # de-duplicate while preserving order
    seen=set(); clean=[]
    for x in issues:
        if x not in seen: clean.append(x); seen.add(x)
    return not clean, clean


def close_action(engine, aid, actor):
    ok,issues=action_can_close(engine,aid)
    if not ok:return False,issues
    execute(engine,"UPDATE actions SET status='CLOTUREE',updated_at=:u WHERE id=:a",{'u':utcnow_iso(),'a':aid})
    audit(engine,'ACTION_CLOSED',aid,actor,'action',aid,{})
    try: schedule_final_bundle(engine,aid,3,actor)
    except Exception: pass
    return True,[]


def admin_password_ok(engine,email,password):
    a=one(engine,'SELECT password_hash FROM admins WHERE email=:e AND active=1',{'e':email})
    return bool(a and __import__('security').verify_password(password,a['password_hash']))


def purge_participant(engine,pid,actor):
    p=one(engine,'SELECT * FROM participants WHERE id=:p',{'p':pid})
    if not p:return False,'Participant introuvable.'
    sigs=q(engine,'SELECT signature_path FROM signatures WHERE participant_id=:p',{'p':pid})
    for r in sigs:
        try:
            fp=Path(r.get('signature_path') or '')
            if fp.is_file(): fp.unlink()
        except Exception: pass
    # Quality issues/actions created from this participant's campaigns must not survive
    # a deliberate administrative purge of the participant.
    campaigns=q(engine,'SELECT id FROM quality_campaigns WHERE participant_id=:p',{'p':pid})
    for c in campaigns:
        issue_ids=[x['id'] for x in q(engine,'SELECT id FROM quality_issues WHERE campaign_id=:c',{'c':c['id']})]
        for iid in issue_ids: execute(engine,'DELETE FROM improvement_actions WHERE issue_id=:i',{'i':iid})
        execute(engine,'DELETE FROM quality_issues WHERE campaign_id=:c',{'c':c['id']})
    # Remove participant-specific audit rows before cascading the database records.
    execute(engine,"DELETE FROM audit_log WHERE action_id=:a AND ((entity_type='participant' AND entity_id=:pid) OR (entity_type='attendance' AND entity_id LIKE :pref) OR (entity_type='signature' AND entity_id LIKE :pref))",{'a':p['action_id'],'pid':str(pid),'pref':f'{pid}/%'})
    execute(engine,'DELETE FROM participants WHERE id=:p',{'p':pid})
    audit(engine,'PARTICIPANT_PURGED',p['action_id'],actor,'action',p['action_id'],{'participant_id':pid})
    return True,''


def purge_action(engine,aid,actor):
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':aid})
    if not a:return False,'Action introuvable.'
    sigs=q(engine,'SELECT x.signature_path FROM signatures x JOIN participants p ON p.id=x.participant_id WHERE p.action_id=:a',{'a':aid})
    for r in sigs:
        try:
            fp=Path(r.get('signature_path') or '')
            if fp.is_file(): fp.unlink()
        except Exception: pass
    issue_ids=[x['id'] for x in q(engine,'SELECT id FROM quality_issues WHERE action_id=:a',{'a':aid})]
    for iid in issue_ids: execute(engine,'DELETE FROM improvement_actions WHERE issue_id=:i',{'i':iid})
    execute(engine,'DELETE FROM improvement_actions WHERE action_id=:a',{'a':aid})
    execute(engine,'DELETE FROM quality_issues WHERE action_id=:a',{'a':aid})
    execute(engine,'DELETE FROM audit_log WHERE action_id=:a',{'a':aid})
    execute(engine,'DELETE FROM actions WHERE id=:a',{'a':aid})
    audit(engine,'ACTION_PURGED',None,actor,'action',aid,{'deleted_action_id':aid})
    return True,''


def list_trainers(engine,active_only=False):
    return q(engine,'SELECT * FROM trainers'+(" WHERE active=1" if active_only else '')+' ORDER BY full_name')

def add_trainer(engine,name,email,phone,actor):
    now=utcnow_iso(); tid=execute(engine,'INSERT INTO trainers(full_name,email,phone,created_at,updated_at) VALUES(:n,:e,:p,:c,:c)',{'n':name.strip(),'e':email.strip().lower() or None,'p':phone.strip() or None,'c':now})
    audit(engine,'TRAINER_CREATED',None,actor,'trainer',tid,{'name':name,'email':email}); return tid

def create_trainer_invitation(engine,tid,actor,valid_hours=72):
    import secrets
    t=one(engine,'SELECT * FROM trainers WHERE id=:i',{'i':tid})
    if not t or not (t.get('email') or '').strip(): return None
    token=secrets.token_urlsafe(32)
    expires=(datetime.now(ZoneInfo('UTC'))+timedelta(hours=valid_hours)).isoformat()
    execute(engine,'UPDATE trainers SET invite_token=:t,invite_expires_at=:e,invited_at=:n,updated_at=:n WHERE id=:i',
            {'t':token,'e':expires,'n':utcnow_iso(),'i':tid})
    audit(engine,'TRAINER_INVITED',None,actor,'trainer',tid,{'email':t.get('email'),'valid_hours':valid_hours})
    return token

def trainer_by_invite(engine,token):
    if not token:return None
    t=one(engine,'SELECT * FROM trainers WHERE invite_token=:t AND active=1',{'t':token})
    if not t:return None
    exp=t.get('invite_expires_at')
    if exp and datetime.fromisoformat(exp)<datetime.now(ZoneInfo('UTC')): return None
    return t

def accept_trainer_invitation(engine,token,password):
    t=trainer_by_invite(engine,token)
    if not t:return False,'Invitation invalide ou expirée.'
    if len(password)<10:return False,'Le mot de passe doit comporter au moins 10 caractères.'
    execute(engine,'UPDATE trainers SET password_hash=:p,invite_token=NULL,invite_expires_at=NULL,updated_at=:u WHERE id=:i',
            {'p':hash_password(password),'u':utcnow_iso(),'i':t['id']})
    audit(engine,'TRAINER_ACCOUNT_ACTIVATED',None,t.get('email') or 'trainer','trainer',t['id'],{})
    return True,''

def verify_trainer_login(engine,email,password):
    from security import verify_password
    t=one(engine,"SELECT * FROM trainers WHERE LOWER(email)=LOWER(:e) AND active=1",{'e':(email or '').strip()})
    if not t or not t.get('password_hash') or not verify_password(password,t['password_hash']): return None
    execute(engine,'UPDATE trainers SET last_login_at=:n WHERE id=:i',{'n':utcnow_iso(),'i':t['id']})
    return t

def trainer_actions(engine,trainer_id):
    return q(engine,"SELECT * FROM actions WHERE trainer_id=:t AND status<>'ARCHIVEE' ORDER BY COALESCE(start_date,''),action_no",{'t':trainer_id})

def set_trainer_active(engine,tid,active,actor):
    execute(engine,'UPDATE trainers SET active=:x,updated_at=:u WHERE id=:i',{'x':1 if active else 0,'u':utcnow_iso(),'i':tid}); audit(engine,'TRAINER_STATUS_CHANGED',None,actor,'trainer',tid,{'active':bool(active)})

def purge_trainer(engine,tid,actor):
    t=one(engine,'SELECT * FROM trainers WHERE id=:i',{'i':tid})
    if not t:return False,'Intervenant introuvable.'
    execute(engine,'UPDATE actions SET trainer_id=NULL,trainer_name=NULL,trainer_email=NULL WHERE trainer_id=:i',{'i':tid})
    execute(engine,'DELETE FROM trainer_access_tokens WHERE trainer_id=:i',{'i':tid})
    execute(engine,'DELETE FROM trainers WHERE id=:i',{'i':tid})
    audit(engine,'TRAINER_PURGED',None,actor,'trainer',tid,{'name':t.get('full_name')}); return True,''

def assign_trainer(engine,aid,tid,actor):
    execute(engine,'UPDATE trainer_access_tokens SET active=0 WHERE action_id=:a',{'a':aid})
    if not tid:
        execute(engine,'UPDATE actions SET trainer_id=NULL,trainer_name=NULL,trainer_email=NULL,updated_at=:u WHERE id=:a',{'u':utcnow_iso(),'a':aid}); return
    t=one(engine,'SELECT * FROM trainers WHERE id=:i AND active=1',{'i':tid})
    if not t:return
    execute(engine,'UPDATE actions SET trainer_id=:i,trainer_name=:n,trainer_email=:e,updated_at=:u WHERE id=:a',{'i':tid,'n':t['full_name'],'e':t.get('email'),'u':utcnow_iso(),'a':aid})
    audit(engine,'TRAINER_ASSIGNED',aid,actor,'trainer',tid,{'name':t['full_name']})

def trainer_token(engine,aid,trainer_id=None):
    t=one(engine,'SELECT token FROM trainer_access_tokens WHERE action_id=:a AND active=1 ORDER BY id DESC',{'a':aid})
    if t:return t['token']
    token=new_token(24);execute(engine,'INSERT INTO trainer_access_tokens(action_id,trainer_id,token,created_at) VALUES(:a,:i,:t,:c)',{'a':aid,'i':trainer_id,'t':token,'c':utcnow_iso()});return token

def trainer_url(engine,aid,base_url):
    a=one(engine,'SELECT trainer_id FROM actions WHERE id=:a',{'a':aid})
    return f"{base_url.rstrip('/')}?trainer_token={trainer_token(engine,aid,(a or {}).get('trainer_id'))}"


def create_trainer_password_reset(engine,email,valid_minutes=60):
    t=one(engine,"SELECT * FROM trainers WHERE LOWER(email)=LOWER(:e) AND active=1",{'e':(email or '').strip()})
    if not t: return None,None
    token=new_token(32); now=utcnow_iso(); expires=(datetime.now(ZoneInfo('UTC'))+timedelta(minutes=valid_minutes)).isoformat()
    execute(engine,'INSERT INTO trainer_password_resets(trainer_id,token,expires_at,created_at) VALUES(:i,:t,:e,:c)',{'i':t['id'],'t':token,'e':expires,'c':now})
    execute(engine,'UPDATE trainers SET reset_requested_at=:n,updated_at=:n WHERE id=:i',{'n':now,'i':t['id']})
    audit(engine,'TRAINER_PASSWORD_RESET_REQUESTED',None,t.get('email') or 'trainer','trainer',t['id'],{})
    return t,token

def trainer_by_reset_token(engine,token):
    if not token: return None
    row=one(engine,"""SELECT t.*,r.id reset_id,r.expires_at,r.used_at FROM trainer_password_resets r JOIN trainers t ON t.id=r.trainer_id
      WHERE r.token=:t AND t.active=1 ORDER BY r.id DESC LIMIT 1""",{'t':token})
    if not row or row.get('used_at'): return None
    try:
        if datetime.fromisoformat(row['expires_at']) < datetime.now(ZoneInfo('UTC')): return None
    except Exception: return None
    return row

def complete_trainer_password_reset(engine,token,password):
    t=trainer_by_reset_token(engine,token)
    if not t:return False,'Lien invalide ou expiré.'
    if len(password)<10:return False,'Le mot de passe doit comporter au moins 10 caractères.'
    now=utcnow_iso(); execute(engine,'UPDATE trainers SET password_hash=:p,updated_at=:u WHERE id=:i',{'p':hash_password(password),'u':now,'i':t['id']})
    execute(engine,'UPDATE trainer_password_resets SET used_at=:u WHERE id=:r',{'u':now,'r':t['reset_id']})
    audit(engine,'TRAINER_PASSWORD_RESET_COMPLETED',None,t.get('email') or 'trainer','trainer',t['id'],{})
    return True,''

def trainer_action_authorized(engine,trainer_id,action_id):
    return bool(one(engine,"SELECT id FROM actions WHERE id=:a AND trainer_id=:t",{'a':action_id,'t':trainer_id}))

def trainer_action_dashboard(engine,trainer_id,action_id,tz_name='Europe/Paris'):
    a=one(engine,'SELECT * FROM actions WHERE id=:a AND trainer_id=:t',{'a':action_id,'t':trainer_id})
    if not a:return None
    slots=q(engine,"SELECT * FROM slots WHERE action_id=:a AND status NOT IN ('ANNULE','REPORTE') ORDER BY slot_date,start_time",{'a':action_id})
    parts=q(engine,'SELECT * FROM participants WHERE action_id=:a AND active=1 ORDER BY last_name,first_name',{'a':action_id})
    now=datetime.now(ZoneInfo(tz_name)); next_slot=None
    for sl in slots:
        try:
            start,_=slot_start_end(sl,tz_name)
            if start>=now: next_slot=sl; break
        except Exception: pass
    return {'action':a,'slots':slots,'participants':parts,'next_slot':next_slot}

def create_trainer_report(engine,action_id,trainer_id,report_type,subject,description,quality_relevant=False,attachment_path=None,attachment_name=None):
    if not trainer_action_authorized(engine,trainer_id,action_id): return None
    now=utcnow_iso(); rid=execute(engine,"""INSERT INTO trainer_reports(action_id,trainer_id,report_type,subject,description,status,quality_relevant,attachment_path,attachment_name,created_at,updated_at)
      VALUES(:a,:t,:rt,:s,:d,'NOUVEAU',:q,:ap,:an,:c,:c)""",{'a':action_id,'t':trainer_id,'rt':report_type,'s':subject,'d':description,'q':1 if quality_relevant else 0,'ap':attachment_path,'an':attachment_name,'c':now})
    if quality_relevant:
        execute(engine,"""INSERT INTO quality_issues(action_id,issue_type,title,description,status,owner,created_at) VALUES(:a,:i,:t,:d,'OUVERTE','Administration',:c)""",{'a':action_id,'i':'SIGNALEMENT_INTERVENANT','t':subject,'d':description,'c':now})
    audit(engine,'TRAINER_REPORT_CREATED',action_id,f'trainer:{trainer_id}','trainer_report',rid,{'report_type':report_type,'quality_relevant':bool(quality_relevant),'attachment_name':attachment_name})
    return rid

def trainer_reports(engine,action_id,trainer_id):
    return q(engine,'SELECT * FROM trainer_reports WHERE action_id=:a AND trainer_id=:t ORDER BY created_at DESC',{'a':action_id,'t':trainer_id})

def purge_slot(engine,sid,actor):
    sl=one(engine,'SELECT * FROM slots WHERE id=:s',{'s':sid})
    if not sl:return False,'Créneau introuvable.'
    sigs=q(engine,'SELECT signature_path FROM signatures WHERE slot_id=:s',{'s':sid})
    for r in sigs:
        try:
            fp=Path(r.get('signature_path') or '')
            if fp.is_file(): fp.unlink()
        except Exception: pass
    execute(engine,"DELETE FROM audit_log WHERE action_id=:a AND ((entity_type='slot' AND entity_id=:sid) OR (entity_type='attendance' AND entity_id LIKE :suff) OR (entity_type='signature' AND entity_id LIKE :suff))",{'a':sl['action_id'],'sid':str(sid),'suff':f'%/{sid}'})
    execute(engine,'DELETE FROM slots WHERE id=:s',{'s':sid})
    audit(engine,'SLOT_PURGED',sl['action_id'],actor,'action',sl['action_id'],{'slot_id':sid,'date':sl.get('slot_date'),'start':sl.get('start_time'),'end':sl.get('end_time')})
    return True,''

# ---- V2 transferable organisation / agency / modular quality foundation ----
def ensure_default_organization(engine, name='Clarté360'):
    org=one(engine,'SELECT * FROM organizations ORDER BY id LIMIT 1')
    if org:return org['id']
    now=utcnow_iso()
    return execute(engine,"""INSERT INTO organizations(name,legal_name,timezone,privacy_contact,created_at,updated_at)
      VALUES(:n,:n,'Europe/Paris','contact@clarte360.com',:c,:c)""",{'n':name,'c':now})

def upsert_organization(engine, org_id, data, actor):
    now=utcnow_iso(); fields=['name','legal_name','address','postal_code','city','country','siret','rcs','naf','vat_id','nda','website','general_email','phone','timezone','privacy_contact','privacy_notice','logo_path','favicon_path','primary_color','secondary_color','email_from_name','email_from_address','retention_months']
    if org_id:
        sets=','.join(f'{k}=:{k}' for k in fields); execute(engine,f'UPDATE organizations SET {sets},updated_at=:updated_at WHERE id=:id',{**{k:data.get(k) for k in fields},'updated_at':now,'id':org_id}); oid=org_id
    else:
        cols=','.join(fields); vals=','.join(':'+k for k in fields); oid=execute(engine,f'INSERT INTO organizations({cols},created_at,updated_at) VALUES({vals},:created_at,:updated_at)',{**{k:data.get(k) for k in fields},'created_at':now,'updated_at':now})
    audit(engine,'ORGANIZATION_SAVED',actor=actor,entity_type='organization',entity_id=oid,details={'name':data.get('name')}); return oid

def add_agency(engine, organization_id, data, actor):
    now=utcnow_iso(); aid=execute(engine,"""INSERT INTO agencies(organization_id,name,address,postal_code,city,country,siret,nda,email,phone,created_at,updated_at)
      VALUES(:o,:n,:a,:p,:c,:co,:s,:nda,:e,:ph,:x,:x)""",{'o':organization_id,'n':data['name'],'a':data.get('address'),'p':data.get('postal_code'),'c':data.get('city'),'co':data.get('country'),'s':data.get('siret'),'nda':data.get('nda'),'e':data.get('email'),'ph':data.get('phone'),'x':now})
    audit(engine,'AGENCY_CREATED',actor=actor,entity_type='agency',entity_id=aid,details={'name':data['name']}); return aid

def archive_action(engine, aid, actor):
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':aid})
    if not a:return False,'Action introuvable.'
    execute(engine,"UPDATE actions SET status='ARCHIVEE',archived_at=:t,updated_at=:t WHERE id=:a",{'t':utcnow_iso(),'a':aid}); audit(engine,'ACTION_ARCHIVED',aid,actor,'action',aid,{}); return True,''

def set_action_modules(engine, aid, prestation_type, attendance, hot, cold, trainer_feedback, organization_id=None, agency_id=None, actor='system'):
    execute(engine,"""UPDATE actions SET prestation_type=:p,use_attendance=:e,use_quality_hot=:h,use_quality_cold=:c,use_trainer_feedback=:t,
      organization_id=:o,agency_id=:g,updated_at=:u WHERE id=:a""",{'p':prestation_type,'e':int(bool(attendance)),'h':int(bool(hot)),'c':int(bool(cold)),'t':int(bool(trainer_feedback)),'o':organization_id,'g':agency_id,'u':utcnow_iso(),'a':aid})
    audit(engine,'ACTION_MODULES_UPDATED',aid,actor,'action',aid,{'prestation_type':prestation_type,'attendance':attendance,'hot':hot,'cold':cold,'trainer_feedback':trainer_feedback})

def create_questionnaire_template(engine, organization_id, code, version, prestation_type, campaign_kind, title, questions, actor='system'):
    now=utcnow_iso(); tid=execute(engine,"""INSERT INTO questionnaire_templates(organization_id,code,version,prestation_type,campaign_kind,title,created_at)
      VALUES(:o,:c,:v,:p,:k,:t,:d)""",{'o':organization_id,'c':code,'v':version,'p':prestation_type,'k':campaign_kind,'t':title,'d':now})
    for pos,item in enumerate(questions,1):
        execute(engine,"""INSERT INTO questionnaire_questions(template_id,question_code,rubric_code,response_type,question_text,position,required)
          VALUES(:t,:q,:r,:y,:x,:p,:req)""",{'t':tid,'q':item['question_code'],'r':item['rubric_code'],'y':item['response_type'],'x':item['question_text'],'p':pos,'req':int(bool(item.get('required')))})
    audit(engine,'QUESTIONNAIRE_TEMPLATE_CREATED',actor=actor,entity_type='questionnaire_template',entity_id=tid,details={'code':code,'version':version}); return tid

def create_quality_campaign(engine, action_id, template_id, campaign_kind, due_at, participant_id=None, trainer_id=None, actor='system'):
    token=new_token(24); cid=execute(engine,"""INSERT INTO quality_campaigns(action_id,participant_id,trainer_id,template_id,campaign_kind,due_at,token,created_at)
      VALUES(:a,:p,:tr,:t,:k,:d,:x,:c)""",{'a':action_id,'p':participant_id,'tr':trainer_id,'t':template_id,'k':campaign_kind,'d':due_at,'x':token,'c':utcnow_iso()})
    audit(engine,'QUALITY_CAMPAIGN_CREATED',action_id,actor,'quality_campaign',cid,{'kind':campaign_kind}); return cid,token

def save_quality_response(engine,campaign_id,question_id,answer,actor='beneficiary'):
    qu=one(engine,'SELECT * FROM questionnaire_questions WHERE id=:q',{'q':question_id}); camp=one(engine,'SELECT * FROM quality_campaigns WHERE id=:c',{'c':campaign_id})
    if not qu or not camp: raise ValueError('Campagne ou question introuvable')
    execute(engine,"""INSERT INTO quality_responses(campaign_id,question_id,rubric_code,response_type,question_text_snapshot,answer_json,answered_at)
      VALUES(:c,:q,:r,:t,:x,:a,:d) ON CONFLICT(campaign_id,question_id) DO UPDATE SET answer_json=excluded.answer_json,answered_at=excluded.answered_at""",{'c':campaign_id,'q':question_id,'r':qu['rubric_code'],'t':qu['response_type'],'x':qu['question_text'],'a':json.dumps(answer,ensure_ascii=False),'d':utcnow_iso()})
    audit(engine,'QUALITY_RESPONSE_SAVED',camp['action_id'],actor,'quality_campaign',campaign_id,{'rubric_code':qu['rubric_code']})

# ---- V2 consolidated foundation helpers ----
ACTION_STATUSES = ('BROUILLON','PLANIFIEE','ACTIVE','A_CLOTURER','CLOTUREE','ARCHIVEE')
PRESTATION_TYPES = ('FORMATION','BILAN_COMPETENCES','VAE','COACHING','MENTORAT','AUTRE')

def normalize_action_status(status):
    legacy={'TERMINEE':'CLOTUREE','ARCHIVE':'ARCHIVEE'}
    return legacy.get((status or '').upper(), (status or 'BROUILLON').upper())

def migrate_legacy_action_statuses(engine, actor='system'):
    changed=0
    for old,new in [('TERMINEE','CLOTUREE'),('ARCHIVE','ARCHIVEE')]:
        rows=q(engine,'SELECT id FROM actions WHERE status=:s',{'s':old})
        if rows:
            execute(engine,'UPDATE actions SET status=:n,archived_at=CASE WHEN :n="ARCHIVEE" THEN COALESCE(archived_at,:u) ELSE archived_at END,updated_at=:u WHERE status=:s',{'n':new,'u':utcnow_iso(),'s':old})
            changed += len(rows)
    if changed: audit(engine,'LEGACY_STATUSES_NORMALIZED',actor=actor,entity_type='action',details={'count':changed})
    return changed

def list_organizations(engine, active_only=False):
    return q(engine,'SELECT * FROM organizations '+('WHERE active=1 ' if active_only else '')+'ORDER BY name,id')

def get_organization(engine, org_id=None):
    if org_id is None:
        return one(engine,'SELECT * FROM organizations WHERE active=1 ORDER BY id LIMIT 1')
    return one(engine,'SELECT * FROM organizations WHERE id=:i',{'i':org_id})

def list_agencies(engine, organization_id, active_only=False):
    return q(engine,'SELECT * FROM agencies WHERE organization_id=:o '+('AND active=1 ' if active_only else '')+'ORDER BY name,id',{'o':organization_id})

def update_agency(engine, agency_id, data, actor):
    old=one(engine,'SELECT * FROM agencies WHERE id=:i',{'i':agency_id})
    if not old: raise ValueError('Agence introuvable')
    fields=['name','address','postal_code','city','country','siret','nda','email','phone','active']
    vals={k:data.get(k,old.get(k)) for k in fields}; vals.update({'id':agency_id,'u':utcnow_iso()})
    execute(engine,'UPDATE agencies SET '+','.join(f'{k}=:{k}' for k in fields)+',updated_at=:u WHERE id=:id',vals)
    audit(engine,'AGENCY_UPDATED',actor=actor,entity_type='agency',entity_id=agency_id,details={'name':vals['name']})

def set_agency_active(engine, agency_id, active, actor):
    execute(engine,'UPDATE agencies SET active=:a,updated_at=:u WHERE id=:i',{'a':int(bool(active)),'u':utcnow_iso(),'i':agency_id})
    audit(engine,'AGENCY_ACTIVATION_CHANGED',actor=actor,entity_type='agency',entity_id=agency_id,details={'active':bool(active)})

def unarchive_action(engine, aid, actor):
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':aid})
    if not a:return False,'Action introuvable.'
    if normalize_action_status(a.get('status'))!='ARCHIVEE': return False,"L'action n'est pas archivée."
    execute(engine,"UPDATE actions SET status='CLOTUREE',archived_at=NULL,updated_at=:t WHERE id=:a",{'t':utcnow_iso(),'a':aid})
    audit(engine,'ACTION_UNARCHIVED',aid,actor,'action',aid,{})
    return True,''

def search_actions(engine, text_query='', statuses=None, include_archived=True, agency_id=None, prestation_type=None):
    wh=[]; p={}
    if text_query.strip():
        p['q']='%'+text_query.strip().lower()+'%'
        wh.append("(LOWER(a.action_no) LIKE :q OR LOWER(a.title) LIKE :q OR LOWER(COALESCE(a.client_name,'')) LIKE :q OR EXISTS (SELECT 1 FROM participants p2 WHERE p2.action_id=a.id AND (LOWER(p2.last_name) LIKE :q OR LOWER(p2.first_name) LIKE :q OR LOWER(COALESCE(p2.email,'')) LIKE :q)))")
    if statuses:
        vals=[normalize_action_status(x) for x in statuses]
        slots=[]
        for i,v in enumerate(vals): p[f's{i}']=v; slots.append(f':s{i}')
        wh.append('a.status IN ('+','.join(slots)+')')
    elif not include_archived: wh.append("a.status<>'ARCHIVEE'")
    if agency_id is not None: wh.append('a.agency_id=:g'); p['g']=agency_id
    if prestation_type: wh.append('a.prestation_type=:pt'); p['pt']=prestation_type
    sql='SELECT a.*,g.name agency_name,o.name organization_name FROM actions a LEFT JOIN agencies g ON g.id=a.agency_id LEFT JOIN organizations o ON o.id=a.organization_id'
    if wh: sql+=' WHERE '+' AND '.join(wh)
    sql+=' ORDER BY a.id DESC'
    return q(engine,sql,p)

def action_has_sent_quality(engine, aid):
    return bool(one(engine,"SELECT id FROM quality_campaigns WHERE action_id=:a AND status IN ('SENT','COMPLETED') LIMIT 1",{'a':aid}))

def safe_set_action_modules(engine, aid, prestation_type, attendance, hot, cold, trainer_feedback, organization_id=None, agency_id=None, actor='system'):
    pt=(prestation_type or '').upper()
    if pt not in PRESTATION_TYPES: raise ValueError('Type de prestation invalide')
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':aid})
    if not a: raise ValueError('Action introuvable')
    if action_has_sent_quality(engine,aid):
        changed = int(bool(hot))!=int(a.get('use_quality_hot') or 0) or int(bool(cold))!=int(a.get('use_quality_cold') or 0) or int(bool(trainer_feedback))!=int(a.get('use_trainer_feedback') or 0) or pt!=(a.get('prestation_type') or 'FORMATION')
        if changed: raise ValueError("Impossible de modifier les modules qualité ou le type de prestation après l'envoi d'une campagne qualité.")
    set_action_modules(engine,aid,pt,attendance,hot,cold,trainer_feedback,organization_id,agency_id,actor)

def organization_runtime_config(engine, action_id=None):
    org=None; agency=None
    if action_id:
        a=one(engine,'SELECT organization_id,agency_id FROM actions WHERE id=:a',{'a':action_id})
        if a:
            if a.get('organization_id'): org=get_organization(engine,a['organization_id'])
            if a.get('agency_id'): agency=one(engine,'SELECT * FROM agencies WHERE id=:i',{'i':a['agency_id']})
    org=org or get_organization(engine)
    return {'organization':org or {},'agency':agency or {},'timezone':(org or {}).get('timezone') or 'Europe/Paris'}

# ---- V2 increment 2: functional quality engine ----
QUALITY_CATALOG_PATH = ROOT / 'quality_catalog.json'
QUALITY_KINDS = ('HOT','COLD','TRAINER')

def seed_standard_questionnaires(engine, organization_id=None, actor='system'):
    """Install the validated standard V2 questionnaire pack once per organisation.

    Stable question/rubric codes are preserved. Re-running is idempotent.
    """
    if not QUALITY_CATALOG_PATH.exists():
        return 0
    catalog=json.loads(QUALITY_CATALOG_PATH.read_text(encoding='utf-8'))
    created=0
    for tpl in catalog:
        exists=one(engine,"SELECT id FROM questionnaire_templates WHERE organization_id IS :o AND code=:c AND version=:v",{'o':organization_id,'c':tpl['code'],'v':tpl['version']})
        if exists: continue
        create_questionnaire_template(engine,organization_id,tpl['code'],tpl['version'],tpl['prestation_type'],tpl['campaign_kind'],tpl['title'],tpl['questions'],actor)
        created+=1
    return created

def get_standard_template(engine, organization_id, prestation_type, campaign_kind):
    pt=(prestation_type or 'FORMATION').upper(); kind=(campaign_kind or '').upper()
    # Trainer questionnaire is intentionally common to all prestations.
    target_pt='ALL' if kind=='TRAINER' else pt
    return one(engine,"""SELECT * FROM questionnaire_templates
      WHERE active=1 AND campaign_kind=:k AND prestation_type=:p AND (organization_id=:o OR organization_id IS NULL)
      ORDER BY CASE WHEN organization_id=:o THEN 0 ELSE 1 END,id DESC LIMIT 1""",{'k':kind,'p':target_pt,'o':organization_id})

def _action_end_moment(engine, action, tz_name='Europe/Paris'):
    """Return the real end moment of the latest planned session when a calendar exists.

    Falls back to the administrative action end date only when no session exists.
    Overnight sessions are correctly carried to the next day.
    """
    slots=q(engine,"""SELECT slot_date,start_time,end_time FROM slots
      WHERE action_id=:a AND COALESCE(status,'PREVU') NOT IN ('ANNULE','REPORTE')
      ORDER BY slot_date,start_time,end_time""",{'a':action['id']})
    latest=None
    for slot in slots:
        begin=parse_dt(slot['slot_date'],slot['start_time'],tz_name)
        finish=parse_dt(slot['slot_date'],slot['end_time'],tz_name)
        if finish<=begin:
            finish+=timedelta(days=1)
        if latest is None or finish>latest:
            latest=finish
    if latest is not None:
        return latest
    if action.get('end_date'):
        d=datetime.fromisoformat(action['end_date']).date()
        return datetime.combine(d,datetime.min.time().replace(hour=12),tzinfo=ZoneInfo(tz_name))
    return None

def _action_end_date(engine, action):
    tz_name=organization_runtime_config(engine,action.get('id'))['timezone'] if action.get('id') else 'Europe/Paris'
    end=_action_end_moment(engine,action,tz_name)
    return end.date().isoformat() if end else None

def _add_months(d, months):
    import calendar
    y=d.year+(d.month-1+months)//12; m=(d.month-1+months)%12+1
    return d.replace(year=y,month=m,day=min(d.day,calendar.monthrange(y,m)[1]))

def standard_quality_due(engine, action_id, campaign_kind, tz_name=None):
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':action_id})
    if not a: raise ValueError('Action introuvable')
    tz_name=tz_name or organization_runtime_config(engine,action_id)['timezone']
    end_moment=_action_end_moment(engine,a,tz_name)
    if not end_moment: raise ValueError("La date de fin de l'action est nécessaire pour planifier les questionnaires qualité.")
    kind=campaign_kind.upper(); pt=(a.get('prestation_type') or 'FORMATION').upper()
    if kind in ('HOT','TRAINER'):
        # A chaud / intervenant : jamais avant la fin réelle de la dernière séance.
        local=end_moment
    else:
        d=end_moment.date()
        if a.get('quality_cold_due_date'):
            due_date=datetime.fromisoformat(a['quality_cold_due_date']).date()
        elif pt=='BILAN_COMPETENCES':
            due_date=_add_months(d,6)
        else:
            due_date=d+timedelta(days=90)
        local=datetime.combine(due_date,datetime.min.time().replace(hour=12),tzinfo=ZoneInfo(tz_name))
    return local.astimezone(ZoneInfo('UTC')).isoformat()

def reschedule_pending_quality_campaigns(engine, action_id, actor='system'):
    """Recalculate only quality campaigns that have not been sent yet.

    SENT/COMPLETED campaigns are evidence and are never silently moved.
    """
    campaigns=q(engine,"SELECT * FROM quality_campaigns WHERE action_id=:a AND status='PENDING' ORDER BY id",{'a':action_id})
    changed=0
    for camp in campaigns:
        due=standard_quality_due(engine,action_id,camp['campaign_kind'])
        old_due=camp.get('due_at')
        if old_due!=due:
            execute(engine,'UPDATE quality_campaigns SET due_at=:d WHERE id=:c',{'d':due,'c':camp['id']})
            changed+=1
        due_dt=datetime.fromisoformat(due)
        offsets=(2,7) if camp['campaign_kind'] in ('HOT','TRAINER') else (7,14)
        event_due={
            'INITIAL': due_dt,
            'REMINDER_1': due_dt+timedelta(days=offsets[0]),
            'REMINDER_2': due_dt+timedelta(days=offsets[1]),
        }
        for event_type,dt in event_due.items():
            iso=dt.astimezone(ZoneInfo('UTC')).isoformat()
            execute(engine,"""UPDATE quality_email_events SET due_at=:d,last_error=NULL
              WHERE campaign_id=:c AND event_type=:e AND status='PENDING'""",{'d':iso,'c':camp['id'],'e':event_type})
        execute(engine,'UPDATE quality_campaigns SET reminder1_due_at=:r1,reminder2_due_at=:r2 WHERE id=:c',
                {'r1':event_due['REMINDER_1'].astimezone(ZoneInfo('UTC')).isoformat(),
                 'r2':event_due['REMINDER_2'].astimezone(ZoneInfo('UTC')).isoformat(),'c':camp['id']})
    if changed:
        audit(engine,'QUALITY_CAMPAIGNS_RESCHEDULED',action_id,actor,'action',action_id,{'campaigns':changed})
    return changed

def quality_token_url(token, base_url):
    return f"{base_url.rstrip('/')}?quality_token={token}"

def create_quality_campaign_safe(engine, action_id, template_id, campaign_kind, due_at, participant_id=None, trainer_id=None, actor='system'):
    recipient_kind='TRAINER' if trainer_id else 'BENEFICIARY'
    existing=one(engine,"""SELECT * FROM quality_campaigns WHERE action_id=:a AND participant_id IS :p AND trainer_id IS :tr
      AND template_id=:t AND campaign_kind=:k""",{'a':action_id,'p':participant_id,'tr':trainer_id,'t':template_id,'k':campaign_kind})
    if existing: return existing['id'],existing['token'],False
    cid,token=create_quality_campaign(engine,action_id,template_id,campaign_kind,due_at,participant_id,trainer_id,actor)
    execute(engine,'UPDATE quality_campaigns SET recipient_kind=:r WHERE id=:i',{'r':recipient_kind,'i':cid})
    return cid,token,True

def prepare_quality_campaigns(engine, action_id, base_url, actor='system'):
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':action_id})
    if not a: raise ValueError('Action introuvable')
    org_id=a.get('organization_id'); seed_standard_questionnaires(engine,org_id,actor)
    created=[]
    parts=q(engine,"SELECT * FROM participants WHERE action_id=:a AND active=1 AND email IS NOT NULL AND TRIM(email)<>''",{'a':action_id})
    plan=[]
    if a.get('use_quality_hot'): plan.append('HOT')
    if a.get('use_quality_cold'): plan.append('COLD')
    for kind in plan:
        tpl=get_standard_template(engine,org_id,a.get('prestation_type'),kind)
        if not tpl: raise ValueError(f'Aucun questionnaire standard {kind} pour {a.get("prestation_type")}')
        due=standard_quality_due(engine,action_id,kind)
        for p in parts:
            cid,token,is_new=create_quality_campaign_safe(engine,action_id,tpl['id'],kind,due,participant_id=p['id'],actor=actor)
            if is_new:
                schedule_quality_email_events(engine,cid,due,kind)
                created.append({'campaign_id':cid,'kind':kind,'recipient':f"{p['first_name']} {p['last_name']}",'url':quality_token_url(token,base_url)})
    if a.get('use_trainer_feedback') and a.get('trainer_id'):
        tr=one(engine,"SELECT * FROM trainers WHERE id=:i AND active=1 AND email IS NOT NULL AND TRIM(email)<>''",{'i':a['trainer_id']})
        if tr:
            tpl=get_standard_template(engine,org_id,a.get('prestation_type'),'TRAINER')
            due=standard_quality_due(engine,action_id,'TRAINER')
            cid,token,is_new=create_quality_campaign_safe(engine,action_id,tpl['id'],'TRAINER',due,trainer_id=tr['id'],actor=actor)
            if is_new:
                schedule_quality_email_events(engine,cid,due,'TRAINER')
                created.append({'campaign_id':cid,'kind':'TRAINER','recipient':tr['full_name'],'url':quality_token_url(token,base_url)})
    reschedule_pending_quality_campaigns(engine,action_id,actor)
    audit(engine,'QUALITY_CAMPAIGNS_PREPARED',action_id,actor,'action',action_id,{'created':len(created)})
    return created

def schedule_quality_email_events(engine,campaign_id,due_at,campaign_kind):
    due=datetime.fromisoformat(due_at)
    if due.tzinfo is None: due=due.replace(tzinfo=ZoneInfo('UTC'))
    # Standard: hot/trainer J+2/J+7, cold +7/+14.
    offsets=(2,7) if campaign_kind in ('HOT','TRAINER') else (7,14)
    ds=[due,due+timedelta(days=offsets[0]),due+timedelta(days=offsets[1])]
    for et,d in zip(('INITIAL','REMINDER_1','REMINDER_2'),ds):
        execute(engine,"""INSERT OR IGNORE INTO quality_email_events(campaign_id,event_type,due_at,created_at)
          VALUES(:c,:e,:d,:n)""",{'c':campaign_id,'e':et,'d':d.astimezone(ZoneInfo('UTC')).isoformat(),'n':utcnow_iso()})
    execute(engine,'UPDATE quality_campaigns SET reminder1_due_at=:r1,reminder2_due_at=:r2 WHERE id=:c',{'r1':ds[1].astimezone(ZoneInfo('UTC')).isoformat(),'r2':ds[2].astimezone(ZoneInfo('UTC')).isoformat(),'c':campaign_id})

def quality_campaign_context(engine, token):
    return one(engine,"""SELECT c.*,qt.title questionnaire_title,qt.version questionnaire_version,qt.prestation_type,
      a.action_no,a.title action_title,a.subtitle,a.client_name,a.trainer_name,a.organization_id,a.agency_id,
      p.first_name,p.last_name,p.email participant_email,t.full_name trainer_full_name,t.email trainer_email
      FROM quality_campaigns c JOIN questionnaire_templates qt ON qt.id=c.template_id JOIN actions a ON a.id=c.action_id
      LEFT JOIN participants p ON p.id=c.participant_id LEFT JOIN trainers t ON t.id=c.trainer_id WHERE c.token=:x""",{'x':token})

def quality_questions(engine,campaign_id):
    return q(engine,"""SELECT qq.* FROM questionnaire_questions qq JOIN quality_campaigns c ON c.template_id=qq.template_id
      WHERE c.id=:c AND qq.active=1 ORDER BY qq.position,qq.id""",{'c':campaign_id})

def quality_existing_answers(engine,campaign_id):
    rows=q(engine,'SELECT question_id,answer_json FROM quality_responses WHERE campaign_id=:c',{'c':campaign_id})
    out={}
    for r in rows:
        try: out[r['question_id']]=json.loads(r['answer_json'])
        except Exception: out[r['question_id']]=r['answer_json']
    return out

def complete_quality_campaign(engine,campaign_id,answers,actor='beneficiary'):
    camp=one(engine,'SELECT * FROM quality_campaigns WHERE id=:c',{'c':campaign_id})
    if not camp: raise ValueError('Campagne introuvable')
    questions=quality_questions(engine,campaign_id)
    for qu in questions:
        ans=answers.get(qu['id'])
        if qu.get('required') and (ans is None or ans=='' or ans==[]):
            raise ValueError('Merci de répondre à toutes les questions obligatoires.')
        if ans is not None and ans!='': save_quality_response(engine,campaign_id,qu['id'],ans,actor)
    now=utcnow_iso(); execute(engine,"UPDATE quality_campaigns SET status='COMPLETED',completed_at=:n WHERE id=:c",{'n':now,'c':campaign_id})
    execute(engine,"UPDATE quality_email_events SET status='SKIPPED' WHERE campaign_id=:c AND status='PENDING'",{'c':campaign_id})
    _create_issue_from_quality(engine,campaign_id,answers,actor)
    audit(engine,'QUALITY_CAMPAIGN_COMPLETED',camp['action_id'],actor,'quality_campaign',campaign_id,{})
    # V2.2 candidate: a completed cold evaluation is a second, independent client transmission.
    if camp.get('campaign_kind')=='COLD':
        action=one(engine,'SELECT transmit_final_bundle FROM actions WHERE id=:a',{'a':camp['action_id']}) or {}
        recipients=configured_final_recipients(engine,camp['action_id']) if action.get('transmit_final_bundle') else []
        if recipients:
            queue_client_transmission(engine,camp['action_id'],'COLD',f'evaluation_a_froid_{campaign_id}.pdf',recipients,actor,campaign_id=campaign_id)

def _create_issue_from_quality(engine,campaign_id,answers,actor):
    camp=one(engine,'SELECT action_id FROM quality_campaigns WHERE id=:c',{'c':campaign_id}); questions={x['id']:x for x in quality_questions(engine,campaign_id)}
    flagged=[]
    for qid,ans in answers.items():
        qu=questions.get(qid)
        if not qu or qu.get('rubric_code') not in ('R12','I06'): continue
        text=json.dumps(ans,ensure_ascii=False) if not isinstance(ans,str) else ans
        low=text.lower().strip()
        if low and low not in ('non','aucun','aucune','non applicable','n/a'):
            flagged.append((qu,text))
    if not flagged:return
    exists=one(engine,'SELECT id FROM quality_issues WHERE campaign_id=:c AND status<>"CLOTUREE"',{'c':campaign_id})
    if exists:return
    issue_type='RECLAMATION' if any('réclamation' in t.lower() for _,t in flagged) else 'DIFFICULTE_ALEA'
    desc='\n'.join(f"{qu['question_code']} — {t}" for qu,t in flagged)
    iid=execute(engine,"""INSERT INTO quality_issues(action_id,campaign_id,issue_type,title,description,status,created_at)
      VALUES(:a,:c,:t,:x,:d,'OUVERTE',:n)""",{'a':camp['action_id'],'c':campaign_id,'t':issue_type,'x':'Signalement issu d’un questionnaire qualité','d':desc,'n':utcnow_iso()})
    audit(engine,'QUALITY_ISSUE_CREATED',camp['action_id'],actor,'quality_issue',iid,{'source':'questionnaire'})

def list_quality_campaigns(engine,action_id):
    return q(engine,"""SELECT c.*,qt.title questionnaire_title,qt.version,p.first_name,p.last_name,p.email participant_email,
      t.full_name trainer_full_name,t.email trainer_email FROM quality_campaigns c JOIN questionnaire_templates qt ON qt.id=c.template_id
      LEFT JOIN participants p ON p.id=c.participant_id LEFT JOIN trainers t ON t.id=c.trainer_id WHERE c.action_id=:a ORDER BY c.due_at,c.id""",{'a':action_id})

def force_quality_event_now(engine,campaign_id,event_type='INITIAL'):
    ev=one(engine,'SELECT id FROM quality_email_events WHERE campaign_id=:c AND event_type=:e',{'c':campaign_id,'e':event_type})
    if not ev: return False
    execute(engine,"UPDATE quality_email_events SET due_at=:n,status='PENDING',last_error=NULL WHERE id=:i AND status<>'SENT'",{'n':utcnow_iso(),'i':ev['id']})
    return True

def list_quality_issues(engine,action_id=None):
    sql='SELECT * FROM quality_issues';p={}
    if action_id is not None: sql+=' WHERE action_id=:a';p['a']=action_id
    return q(engine,sql+' ORDER BY id DESC',p)

# ---- V2 increment 3: quality steering, issues and improvement actions ----
def quality_dashboard(engine, organization_id=None, agency_id=None, prestation_type=None, date_from=None, date_to=None):
    wh=[];p={}
    if organization_id: wh.append('a.organization_id=:o');p['o']=organization_id
    if agency_id: wh.append('a.agency_id=:g');p['g']=agency_id
    if prestation_type: wh.append('a.prestation_type=:pt');p['pt']=prestation_type
    if date_from: wh.append('COALESCE(a.end_date,a.start_date,a.created_at)>=:df');p['df']=date_from
    if date_to: wh.append('COALESCE(a.start_date,a.end_date,a.created_at)<=:dt');p['dt']=date_to
    where=(' WHERE '+' AND '.join(wh)) if wh else ''
    actions=q(engine,'SELECT a.* FROM actions a'+where,p); aids=[a['id'] for a in actions]
    if not aids:return {'actions':0,'campaigns':0,'completed':0,'response_rate':0,'issues_open':0,'improvements_open':0,'scores':[],'nps':[]}
    marks=','.join(':a'+str(i) for i in range(len(aids))); pp={f'a{i}':v for i,v in enumerate(aids)}
    camps=q(engine,f'SELECT * FROM quality_campaigns WHERE action_id IN ({marks})',pp); completed=sum(c['status']=='COMPLETED' for c in camps)
    responses=q(engine,f'''SELECT r.*,qq.question_code FROM quality_responses r JOIN quality_campaigns c ON c.id=r.campaign_id JOIN questionnaire_questions qq ON qq.id=r.question_id WHERE c.action_id IN ({marks})''',pp)
    scores=[];nps=[]
    for r in responses:
        try: val=json.loads(r.get('answer_json') or 'null')
        except: val=None
        if isinstance(val,(int,float)):
            (nps if r.get('response_type')=='NPS' else scores).append(float(val))
    issues=one(engine,f"SELECT COUNT(*) n FROM quality_issues WHERE action_id IN ({marks}) AND status<>'CLOTUREE'",pp)['n']
    improvements=one(engine,f"SELECT COUNT(*) n FROM improvement_actions WHERE action_id IN ({marks}) AND status<>'TERMINEE'",pp)['n']
    return {'actions':len(actions),'campaigns':len(camps),'completed':completed,'response_rate':round(100*completed/len(camps),1) if camps else 0,'issues_open':issues,'improvements_open':improvements,'scores':scores,'nps':nps}

def quality_question_stats(engine, organization_id=None, agency_id=None, prestation_type=None):
    wh=[];p={}
    if organization_id: wh.append('a.organization_id=:o');p['o']=organization_id
    if agency_id: wh.append('a.agency_id=:g');p['g']=agency_id
    if prestation_type: wh.append('a.prestation_type=:pt');p['pt']=prestation_type
    where=(' WHERE '+' AND '.join(wh)) if wh else ''
    rows=q(engine,'''SELECT qq.question_code,qq.rubric_code,r.response_type,r.answer_json FROM quality_responses r JOIN questionnaire_questions qq ON qq.id=r.question_id JOIN quality_campaigns c ON c.id=r.campaign_id JOIN actions a ON a.id=c.action_id'''+where,p)
    agg={}
    for r in rows:
      k=(r['rubric_code'],r['question_code']); x=agg.setdefault(k,{'Rubrique':k[0],'Question':k[1],'Réponses':0,'Moyenne':None,'NPS':None,'_vals':[]})
      try:v=json.loads(r.get('answer_json') or 'null')
      except:v=None
      if v is not None:x['Réponses']+=1
      if isinstance(v,(int,float)):x['_vals'].append(float(v))
    out=[]
    for x in agg.values():
      vals=x.pop('_vals'); x['Moyenne']=round(sum(vals)/len(vals),2) if vals else None; out.append(x)
    return sorted(out,key=lambda x:(x['Rubrique'],x['Question']))

def create_quality_issue(engine, action_id, issue_type, title, description='', owner=None, actor='system'):
    iid=execute(engine,"INSERT INTO quality_issues(action_id,issue_type,title,description,status,owner,created_at) VALUES(:a,:t,:x,:d,'OUVERTE',:o,:c)",{'a':action_id,'t':issue_type,'x':title,'d':description or None,'o':owner or None,'c':utcnow_iso()});audit(engine,'QUALITY_ISSUE_CREATED',action_id,actor,'quality_issue',iid,{'manual':True});return iid

def update_quality_issue(engine, issue_id, status, owner=None, actor='system'):
    i=one(engine,'SELECT * FROM quality_issues WHERE id=:i',{'i':issue_id}); closed=utcnow_iso() if status=='CLOTUREE' else None
    execute(engine,'UPDATE quality_issues SET status=:s,owner=:o,closed_at=:c WHERE id=:i',{'s':status,'o':owner or None,'c':closed,'i':issue_id});audit(engine,'QUALITY_ISSUE_UPDATED',i.get('action_id') if i else None,actor,'quality_issue',issue_id,{'status':status})

def create_improvement_action(engine, action_id, title, description='', owner=None, due_at=None, issue_id=None, actor='system'):
    iid=execute(engine,"INSERT INTO improvement_actions(issue_id,action_id,title,description,owner,due_at,status,created_at) VALUES(:i,:a,:t,:d,:o,:due,'A_FAIRE',:c)",{'i':issue_id,'a':action_id,'t':title,'d':description or None,'o':owner or None,'due':due_at or None,'c':utcnow_iso()});audit(engine,'IMPROVEMENT_ACTION_CREATED',action_id,actor,'improvement_action',iid,{});return iid

def update_improvement_action(engine, improvement_id, status, actor='system'):
    x=one(engine,'SELECT * FROM improvement_actions WHERE id=:i',{'i':improvement_id}); done=utcnow_iso() if status=='TERMINEE' else None
    execute(engine,'UPDATE improvement_actions SET status=:s,completed_at=:d WHERE id=:i',{'s':status,'d':done,'i':improvement_id});audit(engine,'IMPROVEMENT_ACTION_UPDATED',x.get('action_id') if x else None,actor,'improvement_action',improvement_id,{'status':status})

# --- V2.2 LOT 2: beneficiaires permanents + portail documentaire ---
BENEFICIARY_DOC_DIR=ROOT/'data'/'documents'/'blobs'
BENEFICIARY_DOC_DIR.mkdir(parents=True,exist_ok=True)
DEFAULT_ALLOWED_EXTENSIONS={'.pdf','.doc','.docx','.xls','.xlsx','.ppt','.pptx','.txt','.csv','.jpg','.jpeg','.png','.webp','.zip'}
DEFAULT_MAX_FILE_MB=25

def _norm_identity(value):
    import unicodedata, re
    value=unicodedata.normalize('NFKD',str(value or '')).encode('ascii','ignore').decode('ascii').upper().strip()
    return re.sub(r'[^A-Z0-9]+',' ',value).strip()

def find_beneficiary_candidates(engine,last_name,first_name,birth_date,limit=8):
    """Recherche aide a la decision. Jamais de fusion automatique."""
    if not birth_date:
        return []
    rows=q(engine,"SELECT * FROM beneficiaries WHERE birth_date=:b AND active=1 ORDER BY last_name,first_name",{'b':birth_date})
    from difflib import SequenceMatcher
    nl=_norm_identity(last_name); nf=_norm_identity(first_name)
    out=[]
    for r in rows:
        sl=SequenceMatcher(None,nl,_norm_identity(r['last_name'])).ratio()
        sf=SequenceMatcher(None,nf,_norm_identity(r['first_name'])).ratio()
        score=round((sl*.65+sf*.35)*100)
        exact=(nl==_norm_identity(r['last_name']) and nf==_norm_identity(r['first_name']))
        if exact or score>=68:
            x=dict(r);x['match_score']=100 if exact else score;x['exact_match']=exact;out.append(x)
    return sorted(out,key=lambda x:(not x['exact_match'],-x['match_score']))[:limit]

def create_beneficiary(engine,last_name,first_name,birth_date,email=None,birth_name=None,phone=None,actor='system'):
    if not (last_name and first_name and birth_date):
        raise ValueError('Nom, prenom et date de naissance sont obligatoires pour creer un beneficiaire permanent.')
    now=utcnow_iso(); public_id='BEN-'+new_token(9).replace('-','').replace('_','')[:12].upper()
    bid=execute(engine,"""INSERT INTO beneficiaries(public_id,last_name,first_name,birth_date,birth_name,current_email,phone,active,created_at,updated_at)
        VALUES(:u,:l,:f,:b,:bn,:e,:p,1,:c,:c)""",{'u':public_id,'l':str(last_name).strip().upper(),'f':str(first_name).strip().title(),'b':birth_date,'bn':birth_name,'e':(email or '').strip().lower() or None,'p':phone,'c':now})
    audit(engine,'BENEFICIARY_CREATED',actor=actor,entity_type='beneficiary',entity_id=bid,details={'public_id':public_id})
    return bid

def link_participant_to_beneficiary(engine,participant_id,beneficiary_id,actor='system'):
    p=one(engine,'SELECT * FROM participants WHERE id=:p',{'p':participant_id}); b=one(engine,'SELECT * FROM beneficiaries WHERE id=:b',{'b':beneficiary_id})
    if not p or not b: raise ValueError('Participant ou beneficiaire introuvable.')
    execute(engine,'UPDATE participants SET beneficiary_id=:b WHERE id=:p',{'b':beneficiary_id,'p':participant_id})
    audit(engine,'PARTICIPANT_LINKED_TO_BENEFICIARY',p['action_id'],actor,'participant',participant_id,{'beneficiary_id':beneficiary_id})
    return beneficiary_id

def create_beneficiary_from_participant(engine,participant_id,actor='system'):
    p=one(engine,'SELECT * FROM participants WHERE id=:p',{'p':participant_id})
    if not p: raise ValueError('Participant introuvable.')
    if p.get('beneficiary_id'): return p['beneficiary_id']
    bid=create_beneficiary(engine,p['last_name'],p['first_name'],p.get('birth_date'),p.get('email'),p.get('birth_name'),p.get('phone'),actor)
    return link_participant_to_beneficiary(engine,participant_id,bid,actor)

def beneficiary_for_participant(engine,participant_id):
    return one(engine,"""SELECT b.* FROM participants p JOIN beneficiaries b ON b.id=p.beneficiary_id WHERE p.id=:p""",{'p':participant_id})

def beneficiary_participations(engine,beneficiary_id):
    return q(engine,"""SELECT p.id participant_id,p.email participant_email,p.active participant_active,a.*
        FROM participants p JOIN actions a ON a.id=p.action_id WHERE p.beneficiary_id=:b ORDER BY COALESCE(a.start_date,a.created_at) DESC""",{'b':beneficiary_id})

def create_beneficiary_portal_invitation(engine,beneficiary_id,email=None,actor='system',valid_hours=72):
    b=one(engine,'SELECT * FROM beneficiaries WHERE id=:b',{'b':beneficiary_id})
    if not b: raise ValueError('Beneficiaire introuvable.')
    target=(email or b.get('current_email') or '').strip().lower()
    if not target or '@' not in target: raise ValueError('Une adresse email personnelle valide est obligatoire.')
    now=datetime.now(ZoneInfo('UTC')); token=new_token(32); exp=(now+timedelta(hours=valid_hours)).isoformat()
    acc=one(engine,'SELECT * FROM beneficiary_portal_accounts WHERE beneficiary_id=:b',{'b':beneficiary_id})
    if acc:
        changing=bool(acc.get('password_hash') and (acc.get('email') or '').lower()!=target.lower())
        execute(engine,"""UPDATE beneficiary_portal_accounts SET email=CASE WHEN :chg=1 THEN email ELSE :e END,pending_email=CASE WHEN :chg=1 THEN :e ELSE NULL END,invite_token=:t,invite_expires_at=:x,invited_at=:n,active=1,updated_at=:n WHERE beneficiary_id=:b""",{'e':target,'chg':1 if changing else 0,'t':token,'x':exp,'n':now.isoformat(),'b':beneficiary_id})
        if not changing:
            execute(engine,'UPDATE beneficiaries SET current_email=:e,updated_at=:u WHERE id=:b',{'e':target,'u':utcnow_iso(),'b':beneficiary_id})
    else:
        execute(engine,"""INSERT INTO beneficiary_portal_accounts(beneficiary_id,email,active,invite_token,invite_expires_at,invited_at,created_at,updated_at)
            VALUES(:b,:e,1,:t,:x,:n,:n,:n)""",{'b':beneficiary_id,'e':target,'t':token,'x':exp,'n':now.isoformat()})
        execute(engine,'UPDATE beneficiaries SET current_email=:e,updated_at=:u WHERE id=:b',{'e':target,'u':utcnow_iso(),'b':beneficiary_id})
    audit(engine,'BENEFICIARY_PORTAL_INVITED',actor=actor,entity_type='beneficiary',entity_id=beneficiary_id,details={'email':target})
    return token

def beneficiary_by_invite(engine,token):
    return one(engine,"""SELECT b.*,pa.email portal_email,pa.pending_email,pa.invite_expires_at,pa.password_hash,pa.active portal_active FROM beneficiary_portal_accounts pa JOIN beneficiaries b ON b.id=pa.beneficiary_id WHERE pa.invite_token=:t""",{'t':token})

def accept_beneficiary_invitation(engine,token,password):
    b=beneficiary_by_invite(engine,token)
    if not b or not b.get('portal_active'): return False,'Invitation invalide.'
    try: exp=datetime.fromisoformat(b['invite_expires_at'])
    except Exception: return False,'Invitation invalide.'
    if exp < datetime.now(ZoneInfo('UTC')): return False,'Invitation expiree.'
    if len(password or '')<10: return False,'Le mot de passe doit contenir au moins 10 caracteres.'
    now=utcnow_iso();acc=one(engine,'SELECT * FROM beneficiary_portal_accounts WHERE beneficiary_id=:b',{'b':b['id']}); verified=(acc.get('pending_email') or acc.get('email'))
    execute(engine,"""UPDATE beneficiary_portal_accounts SET email=:e,pending_email=NULL,password_hash=:p,email_verified_at=:n,invite_token=NULL,invite_expires_at=NULL,updated_at=:n WHERE beneficiary_id=:b""",{'e':verified,'p':hash_password(password),'n':now,'b':b['id']})
    execute(engine,'UPDATE beneficiaries SET current_email=:e,updated_at=:n WHERE id=:b',{'e':verified,'n':now,'b':b['id']})
    audit(engine,'BENEFICIARY_PORTAL_ACTIVATED',actor=verified or 'beneficiary',entity_type='beneficiary',entity_id=b['id'],details={'email_verified':verified})
    return True,'Espace personnel active.'

def verify_beneficiary_login(engine,email,password):
    acc=one(engine,"""SELECT pa.*,b.public_id,b.last_name,b.first_name FROM beneficiary_portal_accounts pa JOIN beneficiaries b ON b.id=pa.beneficiary_id WHERE lower(pa.email)=lower(:e) AND pa.active=1 AND b.active=1""",{'e':(email or '').strip()})
    if not acc or not acc.get('password_hash') or not verify_password(password,acc['password_hash']): return None
    execute(engine,'UPDATE beneficiary_portal_accounts SET last_login_at=:n WHERE id=:i',{'n':utcnow_iso(),'i':acc['id']})
    return acc

def create_beneficiary_password_reset(engine,email,valid_minutes=60):
    acc=one(engine,"""SELECT pa.*,b.first_name,b.last_name,b.current_email FROM beneficiary_portal_accounts pa
      JOIN beneficiaries b ON b.id=pa.beneficiary_id
      WHERE lower(pa.email)=lower(:e) AND pa.active=1 AND b.active=1""",{'e':(email or '').strip()})
    if not acc or not acc.get('password_hash'): return None,None
    token=new_token(32); now=utcnow_iso(); expires=(datetime.now(ZoneInfo('UTC'))+timedelta(minutes=valid_minutes)).isoformat()
    execute(engine,'INSERT INTO beneficiary_password_resets(beneficiary_id,token,expires_at,created_at) VALUES(:i,:t,:e,:c)',{'i':acc['beneficiary_id'],'t':token,'e':expires,'c':now})
    audit(engine,'BENEFICIARY_PASSWORD_RESET_REQUESTED',actor=acc.get('email') or 'beneficiary',entity_type='beneficiary',entity_id=acc['beneficiary_id'],details={})
    return acc,token

def beneficiary_by_reset_token(engine,token):
    if not token: return None
    row=one(engine,"""SELECT pa.*,b.first_name,b.last_name,r.id reset_id,r.expires_at,r.used_at
      FROM beneficiary_password_resets r JOIN beneficiary_portal_accounts pa ON pa.beneficiary_id=r.beneficiary_id
      JOIN beneficiaries b ON b.id=r.beneficiary_id
      WHERE r.token=:t AND pa.active=1 AND b.active=1 ORDER BY r.id DESC LIMIT 1""",{'t':token})
    if not row or row.get('used_at'): return None
    try:
        if datetime.fromisoformat(row['expires_at']) < datetime.now(ZoneInfo('UTC')): return None
    except Exception: return None
    return row

def complete_beneficiary_password_reset(engine,token,password):
    acc=beneficiary_by_reset_token(engine,token)
    if not acc:return False,'Lien invalide ou expiré.'
    if len(password or '')<10:return False,'Le mot de passe doit comporter au moins 10 caractères.'
    now=utcnow_iso()
    execute(engine,'UPDATE beneficiary_portal_accounts SET password_hash=:p,updated_at=:u WHERE beneficiary_id=:i',{'p':hash_password(password),'u':now,'i':acc['beneficiary_id']})
    execute(engine,'UPDATE beneficiary_password_resets SET used_at=:u WHERE id=:r',{'u':now,'r':acc['reset_id']})
    audit(engine,'BENEFICIARY_PASSWORD_RESET_COMPLETED',actor=acc.get('email') or 'beneficiary',entity_type='beneficiary',entity_id=acc['beneficiary_id'],details={})
    return True,''

def update_beneficiary_email(engine,beneficiary_id,new_email,actor='system'):
    e=(new_email or '').strip().lower()
    if not e or '@' not in e: raise ValueError('Adresse email invalide.')
    other=one(engine,"SELECT beneficiary_id FROM beneficiary_portal_accounts WHERE (lower(email)=lower(:e) OR lower(COALESCE(pending_email,:empty))=lower(:e)) AND beneficiary_id<>:b",{'e':e,'b':beneficiary_id,'empty':''})
    if other: raise ValueError('Cette adresse email est deja utilisee par un autre espace.')
    token=create_beneficiary_portal_invitation(engine,beneficiary_id,e,actor)
    audit(engine,'BENEFICIARY_EMAIL_CHANGE_REQUESTED',actor=actor,entity_type='beneficiary',entity_id=beneficiary_id,details={'pending_email':e})
    return token

def set_beneficiary_portal_active(engine,beneficiary_id,active,actor='system'):
    execute(engine,'UPDATE beneficiary_portal_accounts SET active=:a,updated_at=:u WHERE beneficiary_id=:b',{'a':1 if active else 0,'u':utcnow_iso(),'b':beneficiary_id})
    audit(engine,'BENEFICIARY_PORTAL_STATUS_CHANGED',actor=actor,entity_type='beneficiary',entity_id=beneficiary_id,details={'active':bool(active)})

def store_document(engine,data:bytes,display_name,category,actor='system',action_id=None,beneficiary_id=None,participant_id=None,audience='ACTION_BENEFICIARIES',visible_to_beneficiary=True,max_file_mb=DEFAULT_MAX_FILE_MB,allowed_extensions=None):
    import hashlib, mimetypes
    if not data: raise ValueError('Fichier vide.')
    if len(data)>int(max_file_mb)*1024*1024: raise ValueError(f'Fichier trop volumineux (maximum {max_file_mb} Mo).')
    ext=Path(display_name or '').suffix.lower(); allowed=set(allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS)
    if ext not in allowed: raise ValueError('Type de fichier non autorise.')
    digest=hashlib.sha256(data).hexdigest(); row=one(engine,'SELECT * FROM stored_files WHERE sha256=:h',{'h':digest})
    if row:
        sfid=row['id']; path=Path(row['storage_path'])
        if not path.is_file(): path.write_bytes(data)
    else:
        path=BENEFICIARY_DOC_DIR/digest
        if not path.exists(): path.write_bytes(data)
        sfid=execute(engine,"""INSERT INTO stored_files(sha256,storage_path,size_bytes,mime_type,extension,created_at,last_verified_at) VALUES(:h,:p,:s,:m,:e,:c,:c)""",{'h':digest,'p':str(path),'s':len(data),'m':mimetypes.guess_type(display_name)[0] or 'application/octet-stream','e':ext,'c':utcnow_iso()})
    rid=execute(engine,"""INSERT INTO document_references(stored_file_id,action_id,beneficiary_id,participant_id,category,display_name,audience,visible_to_beneficiary,uploaded_by,created_at)
        VALUES(:f,:a,:b,:p,:c,:n,:au,:v,:u,:d)""",{'f':sfid,'a':action_id,'b':beneficiary_id,'p':participant_id,'c':category,'n':display_name,'au':audience,'v':1 if visible_to_beneficiary else 0,'u':actor,'d':utcnow_iso()})
    audit(engine,'DOCUMENT_REFERENCE_CREATED',action_id,actor,'document_reference',rid,{'sha256':digest,'deduplicated':bool(row),'display_name':display_name,'beneficiary_id':beneficiary_id})
    return rid,digest,bool(row)

def list_action_documents(engine,action_id,include_deleted=False):
    clause='' if include_deleted else 'AND dr.deleted_at IS NULL'
    return q(engine,f"""SELECT dr.*,sf.sha256,sf.storage_path,sf.size_bytes,sf.mime_type,sf.extension FROM document_references dr JOIN stored_files sf ON sf.id=dr.stored_file_id WHERE dr.action_id=:a {clause} ORDER BY dr.created_at DESC""",{'a':action_id})

def list_beneficiary_documents(engine,beneficiary_id):
    return q(engine,"""SELECT DISTINCT dr.*,sf.sha256,sf.storage_path,sf.size_bytes,sf.mime_type,sf.extension,a.action_no,a.title
      FROM document_references dr JOIN stored_files sf ON sf.id=dr.stored_file_id
      LEFT JOIN actions a ON a.id=dr.action_id
      LEFT JOIN participants p ON p.action_id=dr.action_id AND p.beneficiary_id=:b
      WHERE dr.deleted_at IS NULL AND dr.visible_to_beneficiary=1 AND (
        dr.beneficiary_id=:b OR dr.participant_id IN (SELECT id FROM participants WHERE beneficiary_id=:b) OR
        (dr.audience='ACTION_BENEFICIARIES' AND dr.action_id IN (SELECT action_id FROM participants WHERE beneficiary_id=:b))
      ) ORDER BY dr.created_at DESC""",{'b':beneficiary_id})

def delete_document_reference(engine,reference_id,actor='system'):
    r=one(engine,'SELECT * FROM document_references WHERE id=:i AND deleted_at IS NULL',{'i':reference_id})
    if not r: return False
    execute(engine,'UPDATE document_references SET deleted_at=:d WHERE id=:i',{'d':utcnow_iso(),'i':reference_id})
    remaining=one(engine,'SELECT COUNT(*) n FROM document_references WHERE stored_file_id=:f AND deleted_at IS NULL',{'f':r['stored_file_id']})['n']
    if not remaining:
        sf=one(engine,'SELECT * FROM stored_files WHERE id=:f',{'f':r['stored_file_id']})
        try:
            if sf and Path(sf['storage_path']).is_file(): Path(sf['storage_path']).unlink()
        except Exception: pass
        execute(engine,'DELETE FROM document_references WHERE stored_file_id=:f AND deleted_at IS NOT NULL',{'f':r['stored_file_id']})
        execute(engine,'DELETE FROM stored_files WHERE id=:f',{'f':r['stored_file_id']})
    audit(engine,'DOCUMENT_REFERENCE_DELETED',r.get('action_id'),actor,'document_reference',reference_id,{'physical_deleted':not bool(remaining)})
    return True

def document_storage_stats(engine):
    r=one(engine,'SELECT COALESCE(SUM(size_bytes),0) bytes,COUNT(*) files FROM stored_files') or {'bytes':0,'files':0}
    refs=one(engine,'SELECT COUNT(*) n FROM document_references WHERE deleted_at IS NULL')['n']
    return {'bytes':int(r['bytes'] or 0),'files':int(r['files'] or 0),'references':int(refs or 0)}

def beneficiary_portal_zip(engine,beneficiary_id):
    docs=list_beneficiary_documents(engine,beneficiary_id);bio=io.BytesIO()
    used=set()
    with zipfile.ZipFile(bio,'w',zipfile.ZIP_DEFLATED) as z:
        for d in docs:
            base=(d.get('action_no') or 'GENERAL')+'/'+(d.get('display_name') or ('document'+(d.get('extension') or '')))
            name=base;n=2
            while name in used:
                p=Path(base);name=str(p.with_name(f'{p.stem}_{n}{p.suffix}'));n+=1
            used.add(name)
            path=Path(d['storage_path'])
            if path.is_file(): z.writestr(name,path.read_bytes())
    audit(engine,'BENEFICIARY_PORTAL_ZIP_CREATED',actor='beneficiary',entity_type='beneficiary',entity_id=beneficiary_id,details={'documents':len(docs)})
    return bio.getvalue()

# ---- V2.2 lot 3: fin d'action, transmission client, qualite direction ----
FINAL_BUNDLE_ROOT = ROOT / 'data' / 'final_bundles'
FINAL_BUNDLE_ROOT.mkdir(parents=True, exist_ok=True)

def set_action_client_contacts(engine, action_id, admin_email=None, training_email=None, quality_email=None, billing_email=None, other_email=None, actor='system'):
    vals={'client_admin_email':admin_email,'client_training_email':training_email,'client_quality_email':quality_email,'client_billing_email':billing_email,'client_other_email':other_email}
    execute(engine,"""UPDATE actions SET client_admin_email=:client_admin_email,client_training_email=:client_training_email,client_quality_email=:client_quality_email,
      client_billing_email=:client_billing_email,client_other_email=:client_other_email,updated_at=:u WHERE id=:a""",{**vals,'u':utcnow_iso(),'a':action_id})
    audit(engine,'CLIENT_CONTACTS_UPDATED',action_id,actor,'action',action_id,{k:bool(v) for k,v in vals.items()})

def action_client_recipients(engine, action_id, purpose='FINAL'):
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':action_id}) or {}
    keys=['client_admin_email','client_training_email','client_other_email'] if purpose=='FINAL' else ['client_quality_email','client_admin_email','client_other_email']
    out=[]
    for k in keys:
        e=(a.get(k) or '').strip()
        if e and e.lower() not in [x.lower() for x in out]: out.append(e)
    return out

def _safe_filename(v):
    import re
    return re.sub(r'[^A-Za-z0-9._-]+','_',str(v or '').strip()).strip('_') or 'document'

def participant_final_zip(engine, participant_id):
    import io, zipfile
    from pdf_utils import individual_pdf, certificate_pdf
    p=one(engine,'SELECT * FROM participants WHERE id=:p',{'p':participant_id});
    if not p: raise ValueError('Participant introuvable')
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':p['action_id']})
    if normalize_action_status(a.get('status')) not in ('CLOTUREE','ARCHIVEE'): raise ValueError("L'action doit etre cloturee.")
    ok,issues=can_issue_certificate(engine,participant_id,require_closed=True)
    if not ok: raise ValueError('Dossier incomplet : '+' ; '.join(issues[:5]))
    bio=io.BytesIO(); base=f"{_safe_filename(p['last_name'])}_{_safe_filename(p['first_name'])}"
    with zipfile.ZipFile(bio,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr(f'{base}/01_emargement_individuel.pdf',individual_pdf(engine,participant_id))
        z.writestr(f'{base}/02_certificat_realisation.pdf',certificate_pdf(engine,participant_id))
        hot=q(engine,"SELECT id FROM quality_campaigns WHERE participant_id=:p AND campaign_kind='HOT' AND status='COMPLETED' ORDER BY id DESC LIMIT 1",{'p':participant_id})
        if hot:
            try:
                from pdf_utils import quality_response_pdf
                z.writestr(f'{base}/03_evaluation_a_chaud.pdf',quality_response_pdf(engine,hot[0]['id']))
            except Exception: pass
        for d in list_beneficiary_documents(engine,p.get('beneficiary_id')) if p.get('beneficiary_id') else []:
            if d.get('action_id')==a['id']:
                fp=Path(d['storage_path'])
                if fp.is_file(): z.writestr(f"{base}/documents/{_safe_filename(d['display_name'])}",fp.read_bytes())
    return bio.getvalue()

def action_final_bundle(engine, action_id, persist=True, actor='system'):
    import io, zipfile
    from pdf_utils import collective_pdf
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':action_id});
    if not a: raise ValueError('Action introuvable')
    if normalize_action_status(a.get('status')) not in ('CLOTUREE','ARCHIVEE'): raise ValueError("L'action doit etre cloturee.")
    parts=q(engine,'SELECT * FROM participants WHERE action_id=:a AND active=1 ORDER BY last_name,first_name',{'a':action_id})
    bio=io.BytesIO()
    with zipfile.ZipFile(bio,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('00_emargement_collectif.pdf',collective_pdf(engine,action_id))
        for p in parts:
            pzip=participant_final_zip(engine,p['id'])
            with zipfile.ZipFile(io.BytesIO(pzip),'r') as pz:
                for n in pz.namelist(): z.writestr(n,pz.read(n))
        for c in list_quality_campaigns(engine,action_id):
            if c.get('status')=='COMPLETED':
                try:
                    from pdf_utils import quality_response_pdf
                    z.writestr(f"qualite/{c['campaign_kind']}_{c['id']}.pdf",quality_response_pdf(engine,c['id']))
                except Exception: pass
    data=bio.getvalue()
    if persist:
        bundle_date=(a.get('end_date') or datetime.now().date().isoformat())[:10]
        try: prefix=datetime.fromisoformat(bundle_date).strftime('%y%m%d')
        except Exception: prefix=datetime.now().strftime('%y%m%d')
        fp=FINAL_BUNDLE_ROOT/f"{prefix} {_safe_filename(a['action_no'])} DOCS STAGIAIRES.zip"; fp.write_bytes(data); now=utcnow_iso()
        execute(engine,'UPDATE actions SET final_bundle_generated_at=:n,final_bundle_path=:p WHERE id=:a',{'n':now,'p':str(fp),'a':action_id})
        audit(engine,'FINAL_BUNDLE_GENERATED',action_id,actor,'action',action_id,{'path':str(fp),'bytes':len(data)})
        if a.get('transmit_final_bundle'):
            recipients=configured_final_recipients(engine,action_id)
            if recipients:
                queue_client_transmission(engine,action_id,'FINAL',fp.name,recipients,actor)
    return data

def schedule_final_bundle(engine, action_id, delay_hours=3, actor='system'):
    from datetime import datetime, timezone, timedelta
    due=(datetime.now(timezone.utc)+timedelta(hours=delay_hours)).isoformat()
    execute(engine,'UPDATE actions SET final_bundle_due_at=:d WHERE id=:a',{'d':due,'a':action_id}); audit(engine,'FINAL_BUNDLE_SCHEDULED',action_id,actor,'action',action_id,{'due_at':due}); return due

def generate_due_final_bundles(engine, actor='worker'):
    now=utcnow_iso(); rows=q(engine,"SELECT id FROM actions WHERE status='CLOTUREE' AND final_bundle_due_at IS NOT NULL AND final_bundle_due_at<=:n AND final_bundle_generated_at IS NULL",{'n':now}); done=[]
    for r in rows:
        try: action_final_bundle(engine,r['id'],True,actor); done.append(r['id'])
        except Exception as ex: audit(engine,'FINAL_BUNDLE_FAILED',r['id'],actor,'action',r['id'],{'error':str(ex)[:500]})
    return done

def quality_management_summary(engine, **filters):
    base=quality_dashboard(engine,**filters); stats=quality_question_stats(engine,filters.get('organization_id'),filters.get('agency_id'),filters.get('prestation_type'))
    rubric={}
    for r in stats:
        code=r.get('rubric_code') or 'AUTRE'; rubric.setdefault(code,[])
        if r.get('average') is not None: rubric[code].append(float(r['average']))
    rubric_avg={k:round(sum(v)/len(v),2) for k,v in rubric.items() if v}
    nps=base.get('nps') or []; nps_score=None
    if nps: nps_score=round(100*(sum(x>=9 for x in nps)-sum(x<=6 for x in nps))/len(nps),1)
    return {**base,'rubric_averages':rubric_avg,'nps_score':nps_score}

def configure_final_transmission(engine, action_id, enabled=False, to_quality=True, to_training=True, other_first_name=None, other_last_name=None, other_email=None, actor='system'):
    execute(engine,"""UPDATE actions SET transmit_final_bundle=:e,send_final_to_quality=:q,send_final_to_training=:t,final_other_first_name=:of,final_other_last_name=:ol,final_other_email=:oe,updated_at=:u WHERE id=:a""",
      {'e':int(bool(enabled)),'q':int(bool(to_quality)),'t':int(bool(to_training)),'of':other_first_name,'ol':other_last_name,'oe':other_email,'u':utcnow_iso(),'a':action_id})
    audit(engine,'FINAL_TRANSMISSION_CONFIGURED',action_id,actor,'action',action_id,{'enabled':bool(enabled),'quality':bool(to_quality),'training':bool(to_training),'other':bool(other_email)})

def configured_final_recipients(engine, action_id):
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':action_id}) or {};out=[]
    if a.get('send_final_to_quality') and a.get('client_quality_email'): out.append(a['client_quality_email'].strip())
    if a.get('send_final_to_training') and a.get('client_training_email'): out.append(a['client_training_email'].strip())
    if a.get('final_other_email'): out.append(a['final_other_email'].strip())
    return list(dict.fromkeys(x for x in out if x))

def queue_client_transmission(engine, action_id, transmission_type, document_name, recipients, actor='system', campaign_id=None):
    ids=[]
    for email in recipients:
        email=(email or '').strip()
        if not email: continue
        exists=one(engine,"SELECT id FROM client_transmissions WHERE action_id=:a AND transmission_type=:t AND lower(recipient_email)=lower(:e) AND COALESCE(campaign_id,0)=COALESCE(:cid,0) AND status IN ('PENDING','SENDING','SENT')",{'a':action_id,'t':transmission_type,'e':email,'cid':campaign_id})
        if exists: continue
        ids.append(execute(engine,"INSERT INTO client_transmissions(action_id,transmission_type,recipient_email,document_name,campaign_id,status,created_at) VALUES(:a,:t,:e,:d,:cid,'PENDING',:c)",{'a':action_id,'t':transmission_type,'e':email,'d':document_name,'cid':campaign_id,'c':utcnow_iso()}))
    if ids: audit(engine,'CLIENT_TRANSMISSION_QUEUED',action_id,actor,'action',action_id,{'type':transmission_type,'recipients':recipients,'document':document_name,'campaign_id':campaign_id})
    return ids

def portal_retention_candidates(engine, months=12, warning_days=30):
    from datetime import datetime, timezone
    cutoff=_add_months(datetime.now(timezone.utc).date(),-months).isoformat()
    return q(engine,"""SELECT b.*,pa.email portal_email,pa.portal_warning_sent_at,pa.portal_purge_due_at,MAX(COALESCE(a.end_date,a.start_date,a.created_at)) last_action_date FROM beneficiaries b JOIN beneficiary_portal_accounts pa ON pa.beneficiary_id=b.id LEFT JOIN participants p ON p.beneficiary_id=b.id LEFT JOIN actions a ON a.id=p.action_id WHERE pa.active=1 GROUP BY b.id HAVING last_action_date IS NOT NULL AND substr(last_action_date,1,10)<=:c""",{'c':cutoff})

def mark_portal_retention_warning(engine, beneficiary_id, warning_days=30, actor='worker'):
    now=datetime.now(ZoneInfo('UTC')); due=now+timedelta(days=warning_days)
    execute(engine,'UPDATE beneficiary_portal_accounts SET portal_warning_sent_at=:w,portal_purge_due_at=:d,updated_at=:w WHERE beneficiary_id=:b',{'w':now.isoformat(),'d':due.isoformat(),'b':beneficiary_id})
    audit(engine,'BENEFICIARY_PORTAL_RETENTION_WARNING',actor=actor,entity_type='beneficiary',entity_id=beneficiary_id,details={'purge_due_at':due.isoformat()})
    return due.isoformat()

def due_portal_purges(engine, months=12):
    cutoff=_add_months(datetime.now(ZoneInfo('UTC')).date(),-months).isoformat()
    return q(engine,"""SELECT b.id,b.first_name,b.last_name,pa.email portal_email,pa.portal_purge_due_at,MAX(COALESCE(a.end_date,a.start_date,a.created_at)) last_action_date
      FROM beneficiaries b JOIN beneficiary_portal_accounts pa ON pa.beneficiary_id=b.id
      LEFT JOIN participants p ON p.beneficiary_id=b.id LEFT JOIN actions a ON a.id=p.action_id
      WHERE pa.active=1 AND pa.portal_warning_sent_at IS NOT NULL AND pa.portal_purge_due_at IS NOT NULL AND pa.portal_purge_due_at<=:n
      GROUP BY b.id HAVING last_action_date IS NOT NULL AND substr(last_action_date,1,10)<=:c""",{'n':utcnow_iso(),'c':cutoff})

def purge_beneficiary_portal_documents(engine, beneficiary_id, actor='system'):
    refs=q(engine,"SELECT id FROM document_references WHERE beneficiary_id=:b AND deleted_at IS NULL",{'b':beneficiary_id})
    for r in refs: delete_document_reference(engine,r['id'],actor)
    set_beneficiary_portal_active(engine,beneficiary_id,False,actor)
    audit(engine,'BENEFICIARY_PORTAL_PURGED',actor=actor,entity_type='beneficiary',entity_id=beneficiary_id,details={'portal_documents_removed':len(refs),'regulatory_archives_preserved':True})
    return len(refs)
