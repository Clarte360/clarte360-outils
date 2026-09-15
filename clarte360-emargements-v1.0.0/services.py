from __future__ import annotations
import json, io, csv, zipfile, base64, hashlib, hmac, time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import quote, urlencode, urlsplit, urlunsplit, parse_qsl
from sqlalchemy import text
from db import q, one, execute, audit, new_token, utcnow_iso
from security import hash_password, verify_password, seal_short_secret, open_short_secret
from input_validation import (
    validate_action_payload, validate_participant_payload, validate_trainer_payload,
    validate_organization_payload, validate_agency_payload, validate_crm_payload,
    validate_email, validate_birth_date, validate_slot, validate_json_text,
    validate_short_text, validate_free_text, validate_positive_number, validate_code, InputValidationError
)

ROOT=Path(__file__).resolve().parent
SIG_DIR=ROOT/'data'/'signatures'; SIG_DIR.mkdir(parents=True,exist_ok=True)

DELIVERY_MODE_LABELS={
    'PRESENTIEL':'Présentiel',
    'DISTANCIEL_VISIO':'Distanciel-visioconférence',
    'HYBRIDE':'Hybride',
    'ELEARNING':'E-learning',
    'BLENDED':'Blended learning',
}

def allowed_delivery_modes(prestation_type):
    p=(prestation_type or 'FORMATION').upper().replace(' ','_')
    if p in ('BILAN_DE_COMPETENCES','BILAN_COMPETENCES','COACHING'):
        return ['PRESENTIEL','DISTANCIEL_VISIO','HYBRIDE']
    if p=='FORMATION':
        return ['PRESENTIEL','DISTANCIEL_VISIO','HYBRIDE','ELEARNING','BLENDED']
    return ['PRESENTIEL','DISTANCIEL_VISIO','HYBRIDE']

def normalize_delivery_mode(value,prestation_type='FORMATION'):
    raw=str(value or '').strip()
    aliases={
        'PRESENTIEL':'PRESENTIEL','PRÉSENTIEL':'PRESENTIEL',
        'DISTANCIEL':'DISTANCIEL_VISIO','DISTANCIEL-VISIOCONFÉRENCE':'DISTANCIEL_VISIO','DISTANCIEL-VISIOCONFERENCE':'DISTANCIEL_VISIO','VISIO':'DISTANCIEL_VISIO','VISIOCONFERENCE':'DISTANCIEL_VISIO','VISIOCONFÉRENCE':'DISTANCIEL_VISIO',
        'HYBRIDE':'HYBRIDE','E-LEARNING':'ELEARNING','ELEARNING':'ELEARNING','BLENDED LEARNING':'BLENDED','BLENDED':'BLENDED'
    }
    code=aliases.get(raw.upper(),raw.upper().replace('-','_').replace(' ','_')) if raw else None
    allowed=allowed_delivery_modes(prestation_type)
    if code not in allowed:
        if value is None or not raw: return allowed[0]
        raise ValueError('Modalité incompatible avec ce type de prestation.')
    return code

def delivery_mode_label(code):
    return DELIVERY_MODE_LABELS.get(code,code or 'Non renseignée')

def parse_dt(date_s,time_s,tz_name='Europe/Paris'):
    return datetime.fromisoformat(f"{date_s}T{time_s}").replace(tzinfo=ZoneInfo(tz_name))

def slot_duration_hours(slot):
    a=datetime.fromisoformat(f"2000-01-01T{slot['start_time']}")
    b=datetime.fromisoformat(f"2000-01-01T{slot['end_time']}")
    if b<=a: b+=timedelta(days=1)
    return round((b-a).total_seconds()/3600,2)


def validate_slot_offsets(send_offset_min, close_offset_min):
    send=int(send_offset_min); close=int(close_offset_min)
    if send < -1440 or send > 1440:
        raise ValueError('Le décalage personnalisé doit être compris entre -1440 et 1440 minutes.')
    if close < 0 or close > 10080:
        raise ValueError("La durée d'émargement après fin doit être comprise entre 0 et 10080 minutes.")
    return send,close


def slot_start_end(slot, tz_name='Europe/Paris'):
    start=parse_dt(slot['slot_date'],slot['start_time'],tz_name)
    end=parse_dt(slot['slot_date'],slot['end_time'],tz_name)
    if end<=start:
        end+=timedelta(days=1)
    return start,end

def email_event_due_utc(slot,event_type,tz_name='Europe/Paris'):
    start,end=slot_start_end(slot,tz_name)
    if event_type=='INITIAL':
        # V3 I3: the single automatic attendance request is due at the real slot start.
        due=start
    elif event_type=='RELANCE_1':
        due=end+timedelta(minutes=int(slot.get('reminder1_offset_min') or 0))
    elif event_type=='RELANCE_2':
        due=end+timedelta(minutes=int(slot.get('reminder2_offset_min') or 0))
    else:
        raise ValueError(f'Type d’événement inconnu : {event_type}')
    return due.astimezone(ZoneInfo('UTC'))

def create_action(engine, d, actor):
    now=utcnow_iso(); d=validate_action_payload(d)
    prestation=d.get('prestation_type') or d.get('nature') or 'FORMATION'
    d['delivery_mode']=normalize_delivery_mode(d.get('delivery_mode'),prestation)
    aid=execute(engine,"""INSERT INTO actions(action_no,title,subtitle,nature,mode,delivery_mode,client_name,client_type,group_code,planned_hours,expected_participants,status,admin_email,trainer_name,trainer_email,location,notes,source,created_at,updated_at)
    VALUES(:action_no,:title,:subtitle,:nature,:mode,:delivery_mode,:client_name,:client_type,:group_code,:planned_hours,:expected_participants,'BROUILLON',:admin_email,:trainer_name,:trainer_email,:location,:notes,:source,:created_at,:updated_at)""",{**d,"created_at":now,"updated_at":now})
    audit(engine,'ACTION_CREATED',aid,actor,'action',aid,d); return aid

def update_action(engine, aid, d, actor):
    d=dict(d); current=one(engine,'SELECT prestation_type,nature,delivery_mode FROM actions WHERE id=:a',{'a':aid}) or {}
    prestation=d.get('prestation_type') or current.get('prestation_type') or d.get('nature') or current.get('nature') or 'FORMATION'
    d['delivery_mode']=normalize_delivery_mode(d.get('delivery_mode',current.get('delivery_mode')),prestation)
    keys=['title','subtitle','nature','mode','delivery_mode','client_name','client_type','group_code','planned_hours','expected_participants','admin_email','trainer_name','trainer_email','location','notes','status']
    sets=','.join(f"{k}=:{k}" for k in keys)
    p={k:d.get(k) for k in keys};p.update({'id':aid,'u':utcnow_iso()})
    execute(engine,f"UPDATE actions SET {sets},updated_at=:u WHERE id=:id",p);audit(engine,'ACTION_UPDATED',aid,actor,'action',aid,d)

def add_participant(engine, aid, d, actor):
    d = validate_participant_payload(d)
    pin = d.pop('pin', None) or f"{__import__('secrets').randbelow(10000):04d}"
    try: pin_cipher=seal_short_secret(pin)
    except Exception: pin_cipher=None
    pid=execute(engine,"""INSERT INTO participants(action_id,individual_action_no,last_name,birth_name,first_name,birth_date,email,employee_id,company_name,phone,pin_hash,pin_recovery_cipher,created_at)
    VALUES(:aid,:individual_action_no,:last_name,:birth_name,:first_name,:birth_date,:email,:employee_id,:company_name,:phone,:pin_hash,:pin_recovery_cipher,:created_at)""",{
     'aid':aid, **{k:d.get(k) for k in ['individual_action_no','last_name','birth_name','first_name','birth_date','email','employee_id','company_name','phone']},
     'pin_hash':hash_password(pin),'pin_recovery_cipher':pin_cipher,'created_at':utcnow_iso()})
    audit(engine,'PARTICIPANT_ADDED',aid,actor,'participant',pid,{'last_name':d.get('last_name'),'first_name':d.get('first_name'),'birth_date_source':d.get('_birth_date_source')})
    # I9-B: exact permanent identity may be linked automatically only on the three exact identity fields.
    if d.get('birth_date'):
        try:
            exact=[x for x in find_beneficiary_candidates(engine,d.get('last_name'),d.get('first_name'),d.get('birth_date')) if x.get('exact_match')]
            if len(exact)==1:
                link_participant_to_beneficiary(engine,pid,exact[0]['id'],actor)
                audit(engine,'BENEFICIARY_AUTO_MATCH_EXACT',aid,actor,'participant',pid,{'beneficiary_id':exact[0]['id']})
            elif len(exact)>1:
                audit(engine,'BENEFICIARY_MATCH_AMBIGUOUS',aid,actor,'participant',pid,{'candidate_ids':[x['id'] for x in exact]})
        except Exception:
            pass
    # A participant added after activation receives a dedicated planning communication automatically.
    a=one(engine,'SELECT status FROM actions WHERE id=:a',{'a':aid}) or {}
    if str(a.get('status') or '').upper() in ('ACTIVE','A_CLOTURER') and (d.get('email') or '').strip():
        queue_communication(engine,aid,'PLANNING_CONFIRMATION',(d.get('email') or '').strip(),participant_id=pid,trigger_mode='AUTO',idempotency_key=f'planning:new-participant:{aid}:{pid}')
    return pid,pin

def delete_participant(engine,pid,actor):
    p=one(engine,'SELECT action_id,last_name,first_name FROM participants WHERE id=:id',{'id':pid});
    if not p:return
    execute(engine,'DELETE FROM participants WHERE id=:id',{'id':pid});audit(engine,'PARTICIPANT_DELETED',p['action_id'],actor,'participant',pid,p)



def _hhmm_minutes(value):
    h,m=[int(x) for x in str(value).split(':')[:2]]
    return h*60+m

def validate_no_action_slot_overlap(engine, action_id, date_s, start_s, end_s, exclude_slot_id=None):
    """Hard business invariant: one action cannot have overlapping active slots."""
    start=_hhmm_minutes(start_s); end=_hhmm_minutes(end_s)
    rows=q(engine,"""SELECT id,start_time,end_time FROM slots WHERE action_id=:a AND slot_date=:d
      AND status NOT IN ('ANNULE','REPORTE','REMPLACE')""",{'a':action_id,'d':date_s})
    for r in rows:
        if exclude_slot_id is not None and int(r['id'])==int(exclude_slot_id):
            continue
        rs=_hhmm_minutes(r['start_time']); re=_hhmm_minutes(r['end_time'])
        if start < re and end > rs:
            raise InputValidationError(f"Impossible : ce créneau chevauche déjà la séance {r['start_time']}–{r['end_time']} de cette action.")
    return True

def add_slot(engine, aid, date_s,start_s,end_s,actor,send=-10,r1=20,r2=120,close=1440):
    date_s,start_s,end_s=validate_slot(date_s,start_s,end_s)
    validate_no_action_slot_overlap(engine,aid,date_s,start_s,end_s)
    send,close=validate_slot_offsets(send,close)
    now=utcnow_iso(); public=new_token(18)
    sid=execute(engine,"""INSERT INTO slots(action_id,slot_date,start_time,end_time,original_start_time,original_end_time,send_offset_min,reminder1_offset_min,reminder2_offset_min,close_offset_min,public_token,created_at,updated_at)
      VALUES(:a,:d,:s,:e,:s,:e,:send,:r1,:r2,:close,:t,:c,:c)""",{'a':aid,'d':date_s,'s':start_s,'e':end_s,'send':send,'r1':r1,'r2':r2,'close':close,'t':public,'c':now})
    # V3 I2: a new slot inherits only the current referent as PRINCIPAL. Other action-level
    # intervenants are assigned explicitly to the slots where they actually intervene.
    ref=one(engine,"""SELECT at.trainer_id FROM action_trainers at WHERE at.action_id=:a AND at.active=1 AND at.is_referent=1
      ORDER BY at.id DESC LIMIT 1""",{'a':aid})
    if not ref:
        ref=one(engine,'SELECT trainer_id FROM actions WHERE id=:a AND trainer_id IS NOT NULL',{'a':aid})
    if ref and ref.get('trainer_id'):
        now2=utcnow_iso()
        execute(engine,"""INSERT INTO slot_trainers(slot_id,trainer_id,role,assignment_status,created_by,active,created_at,updated_at)
          VALUES(:s,:t,'PRINCIPAL','ACTIVE',:by,1,:n,:n)
          ON CONFLICT(slot_id,trainer_id) DO UPDATE SET role='PRINCIPAL',assignment_status='ACTIVE',active=1,created_by=excluded.created_by,updated_at=excluded.updated_at""",
          {'s':sid,'t':ref['trainer_id'],'by':actor,'n':now2})
        execute(engine,"""INSERT INTO trainer_assignment_history(scope_type,action_id,slot_id,trainer_id,event_type,new_role,new_status,actor,created_at)
          VALUES('SLOT',:a,:s,:t,'ASSIGNED','PRINCIPAL','ACTIVE',:by,:n)""",{'a':aid,'s':sid,'t':ref['trainer_id'],'by':actor,'n':now2})
    if action_module_enabled(engine,aid,'TEAMS'):
        mod=action_module(engine,aid,'TEAMS') or {}
        try:
            tz_name=organization_runtime_config(engine,aid)['timezone']
            sl=one(engine,'SELECT * FROM slots WHERE id=:s',{'s':sid})
            start,_=slot_start_end(sl,tz_name)
            if not mod.get('effective_from') and start>=datetime.now(ZoneInfo(tz_name)):
                execute(engine,"UPDATE action_modules SET effective_from=:f,updated_at=:u WHERE action_id=:a AND module_code='TEAMS'",{'f':start.isoformat(),'u':utcnow_iso(),'a':aid})
            queue_teams_sync(engine,aid,sid,'SLOT_ADDED',actor,{'slot_id':sid})
        except Exception:
            pass
    audit(engine,'SLOT_ADDED',aid,actor,'slot',sid,{'date':date_s,'start':start_s,'end':end_s});return sid

def update_slot(engine,sid,d,actor):
    d=dict(d); d['send_offset_min'],d['close_offset_min']=validate_slot_offsets(d.get('send_offset_min',-10),d.get('close_offset_min',1440))
    old=one(engine,'SELECT * FROM slots WHERE id=:id',{'id':sid});
    if not old:return
    d['slot_date'],d['start_time'],d['end_time']=validate_slot(d.get('slot_date'),d.get('start_time'),d.get('end_time'))
    validate_no_action_slot_overlap(engine,old['action_id'],d['slot_date'],d['start_time'],d['end_time'],exclude_slot_id=sid)
    execute(engine,"""UPDATE slots SET slot_date=:slot_date,start_time=:start_time,end_time=:end_time,send_offset_min=:send_offset_min,reminder1_offset_min=:reminder1_offset_min,reminder2_offset_min=:reminder2_offset_min,close_offset_min=:close_offset_min,updated_at=:u WHERE id=:id""",{**d,'u':utcnow_iso(),'id':sid})
    audit(engine,'SLOT_UPDATED',old['action_id'],actor,'slot',sid,{'before':old,'after':d})

def delete_slot(engine,sid,actor):
    old=one(engine,'SELECT * FROM slots WHERE id=:id',{'id':sid});
    if not old:return False,'Créneau introuvable.'
    signed=one(engine,'SELECT COUNT(*) n FROM signatures WHERE slot_id=:id',{'id':sid})['n']
    countersigned=one(engine,'SELECT COUNT(*) n FROM trainer_countersignatures_v3 WHERE slot_id=:id',{'id':sid})['n']
    if signed or countersigned:return False,"Impossible : ce créneau contient déjà des preuves de signature."
    execute(engine,'DELETE FROM slots WHERE id=:id',{'id':sid});audit(engine,'SLOT_DELETED',old['action_id'],actor,'slot',sid,old);return True,''

def ensure_tokens_and_events(engine, aid, base_url,tz_name='Europe/Paris'):
    participants=q(engine,'SELECT * FROM participants WHERE action_id=:a AND active=1',{'a':aid})
    slots=q(engine,'SELECT * FROM slots WHERE action_id=:a',{'a':aid})
    for p in participants:
      for s in slots:
        tok=one(engine,'SELECT * FROM signature_tokens WHERE participant_id=:p AND slot_id=:s',{'p':p['id'],'s':s['id']})
        if not tok:
          token=new_token(24); execute(engine,'INSERT INTO signature_tokens(participant_id,slot_id,token,created_at) VALUES(:p,:s,:t,:c)',{'p':p['id'],'s':s['id'],'t':token,'c':utcnow_iso()})
        due=email_event_due_utc(s,'INITIAL',tz_name).isoformat()
        execute(engine,"""INSERT OR IGNORE INTO email_events(participant_id,slot_id,event_type,due_at) VALUES(:p,:s,'INITIAL',:d)""",{'p':p['id'],'s':s['id'],'d':due})
        execute(engine,"""UPDATE email_events SET due_at=:d,last_error=NULL WHERE participant_id=:p AND slot_id=:s AND event_type='INITIAL' AND status='PENDING'""",{'p':p['id'],'s':s['id'],'d':due})
        # Pending V2 automatic reminders are neutralised, but already-sent historical events are preserved.
        execute(engine,"""UPDATE email_events SET status='SKIPPED',last_error='Désactivé par règle V3 I3'
          WHERE participant_id=:p AND slot_id=:s AND event_type IN ('RELANCE_1','RELANCE_2') AND status='PENDING'""",{'p':p['id'],'s':s['id']})
    audit(engine,'SIGNATURE_REQUESTS_PREPARED',aid,'system','action',aid,{'base_url':base_url,'automatic_events':['INITIAL']})



def activate_action(engine, aid, actor):
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':aid})
    if not a: return False,['Action introuvable.']
    issues=[]
    participants=q(engine,'SELECT * FROM participants WHERE action_id=:a AND active=1',{'a':aid})
    slots=q(engine,'SELECT * FROM slots WHERE action_id=:a ORDER BY slot_date,start_time',{'a':aid})
    if not participants: issues.append('Aucun participant actif.')
    expected=int(a.get('expected_participants') or 0)
    if expected>0 and len(participants)!=expected:
        issues.append(f'Nombre de participants incohérent : {len(participants)} inscrit(s) pour {expected} prévu(s).')
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
      'trainer_countersignatures_legacy':q(engine,'SELECT x.* FROM trainer_countersignatures x JOIN slots s ON s.id=x.slot_id WHERE s.action_id=:a',{'a':aid}),
      'trainer_countersignatures':q(engine,'SELECT x.* FROM trainer_countersignatures_v3 x JOIN slots s ON s.id=x.slot_id WHERE s.action_id=:a',{'a':aid}),
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
      sigs += q(engine,'SELECT x.signature_path FROM trainer_countersignatures_v3 x JOIN slots s ON s.id=x.slot_id WHERE s.action_id=:a',{'a':aid})
      for s in sigs:
        p=Path(s.get('signature_path') or '')
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

def _copy_slot_trainer_assignments(engine, original_sid, new_sid, actor, reason):
    """Copy current active assignments to a report/catch-up occurrence without altering history."""
    old=one(engine,'SELECT action_id FROM slots WHERE id=:s',{'s':original_sid})
    if not old:return
    # add_slot may have inherited the current referent; normalize the new occurrence to the original assignment set.
    inherited=q(engine,'SELECT * FROM slot_trainers WHERE slot_id=:s AND active=1',{'s':new_sid})
    source=q(engine,"SELECT * FROM slot_trainers WHERE slot_id=:s AND active=1 AND assignment_status='ACTIVE' ORDER BY id",{'s':original_sid})
    source_ids={x['trainer_id'] for x in source}
    for row in inherited:
        if row['trainer_id'] not in source_ids:
            execute(engine,"UPDATE slot_trainers SET active=0,assignment_status='INACTIVE',reason=:r,updated_at=:u WHERE id=:i",{'r':'Normalisation affectations report/rattrapage','u':utcnow_iso(),'i':row['id']})
    for row in source:
        assign_slot_trainer(engine,new_sid,row['trainer_id'],actor,row.get('role') or 'PRINCIPAL',reason)

def create_catchup_slot(engine, original_sid, date_s,start_s,end_s, participant_ids, actor, reason='Rattrapage'):
    old=one(engine,'SELECT * FROM slots WHERE id=:s',{'s':original_sid})
    sid=add_slot(engine,old['action_id'],date_s,start_s,end_s,actor,old['send_offset_min'],old['reminder1_offset_min'],old['reminder2_offset_min'],old['close_offset_min'])
    execute(engine,"UPDATE slots SET parent_slot_id=:p,slot_kind='RATTRAPAGE',change_reason=:r WHERE id=:s",{'p':original_sid,'r':reason,'s':sid})
    _copy_slot_trainer_assignments(engine,original_sid,sid,actor,'Rattrapage : '+str(reason or ''))
    # Only selected participants are expected on this catch-up slot.
    allp=q(engine,'SELECT id FROM participants WHERE action_id=:a AND active=1',{'a':old['action_id']})
    selected=set(int(x) for x in participant_ids)
    for p in allp:
        if p['id'] not in selected: set_attendance_status(engine,p['id'],sid,'NON_CONCERNE','Non inscrit au rattrapage',actor)
    audit(engine,'CATCHUP_SLOT_CREATED',old['action_id'],actor,'slot',sid,{'parent_slot_id':original_sid,'participants':list(selected)})
    return sid

def safe_update_slot(engine,sid,d,actor):
    evidence=one(engine,"SELECT (SELECT COUNT(*) FROM signatures WHERE slot_id=:s)+(SELECT COUNT(*) FROM attendance_status WHERE slot_id=:s AND status IN ('ABSENT','PRESENT_REGULARISE'))+(SELECT COUNT(*) FROM trainer_countersignatures_v3 WHERE slot_id=:s) n",{'s':sid})['n']
    if evidence: return False,"Ce créneau contient déjà une preuve (signature/absence). Il ne peut plus être réécrit : utilisez Report / Rattrapage."
    try:
        update_slot(engine,sid,d,actor); return True,''
    except InputValidationError as ex:
        return False,str(ex)

def trainer_token(engine,aid):
    t=one(engine,'SELECT token FROM trainer_access_tokens WHERE action_id=:a AND active=1 ORDER BY id DESC',{'a':aid})
    if t:return t['token']
    token=new_token(24);execute(engine,'INSERT INTO trainer_access_tokens(action_id,token,created_at) VALUES(:a,:t,:c)',{'a':aid,'t':token,'c':utcnow_iso()});return token

def trainer_url(engine,aid,base_url): return f"{base_url.rstrip('/')}?trainer_token={trainer_token(engine,aid)}"

def _slot_participant_states(engine, sid):
    slot=one(engine,'SELECT * FROM slots WHERE id=:s',{'s':sid})
    if not slot: return []
    parts=q(engine,'SELECT * FROM participants WHERE action_id=:a AND active=1 ORDER BY last_name,first_name',{'a':slot['action_id']})
    out=[]
    for p in parts:
        sig=one(engine,"SELECT id FROM signatures WHERE participant_id=:p AND slot_id=:s AND status='VALIDE'",{'p':p['id'],'s':sid})
        att=one(engine,'SELECT status,reason FROM attendance_status WHERE participant_id=:p AND slot_id=:s',{'p':p['id'],'s':sid})
        if sig:
            status='SIGNE'
        elif att and att.get('status') in ('ABSENT','NON_CONCERNE','PRESENT_REGULARISE'):
            status=att['status']
        else:
            status='EN_ATTENTE'
        out.append({'participant_id':p['id'],'name':f"{p['first_name']} {p['last_name']}",'status':status})
    return out


def slot_countersignature_eligibility(engine, sid, trainer_id=None, tz_name=None, now=None):
    """Server-side V3 I3 gate. UI state alone is never considered sufficient."""
    slot=one(engine,'SELECT * FROM slots WHERE id=:s',{'s':sid})
    if not slot: return False,'Créneau introuvable.',{}
    action=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':slot['action_id']})
    tz_name=tz_name or organization_runtime_config(engine,slot['action_id'])['timezone']
    current=now or datetime.now(ZoneInfo(tz_name))
    if current.tzinfo is None: current=current.replace(tzinfo=ZoneInfo(tz_name))
    _,end=slot_start_end(slot,tz_name)
    if (slot.get('status') or 'PREVU') in ('ANNULE','REPORTE'):
        return False,'Ce créneau annulé ou reporté ne peut pas être contresigné comme occurrence réalisée.',{}
    states=_slot_participant_states(engine,sid)
    pending=[x for x in states if x['status']=='EN_ATTENTE']
    if pending:
        # I9-B: before the scheduled end, countersignature opens immediately only when every participant status is final.
        # At/after the end the request is sent even if statuses remain pending, but the trainer must resolve them before signing.
        return False,'Situation non finalisée pour : '+', '.join(x['name'] for x in pending)+'.',{'pending':pending,'end':end.isoformat(),'slot_ended':current>=end}
    assigned=list_slot_trainers(engine,sid)
    if trainer_id is not None and assigned and int(trainer_id) not in {int(x['trainer_id']) for x in assigned}:
        return False,"Cet intervenant n'est pas affecté à ce créneau.",{}
    return True,'',{'participants':states,'assigned_trainers':assigned,'end':end.isoformat()}


def trainer_countersign_tasks(engine,trainer_id,now=None):
    rows=q(engine,"""SELECT s.* FROM slots s JOIN actions a ON a.id=s.action_id JOIN slot_trainers st ON st.slot_id=s.id
      WHERE st.trainer_id=:t AND st.active=1 AND st.assignment_status='ACTIVE' AND a.status IN ('ACTIVE','A_CLOTURER')
      AND COALESCE(s.status,'PREVU') NOT IN ('ANNULE','REPORTE') ORDER BY s.slot_date,s.start_time""",{'t':trainer_id})
    out=[]
    for sl in rows:
        if one(engine,'SELECT id FROM trainer_countersignatures_v3 WHERE slot_id=:s AND trainer_id=:t',{'s':sl['id'],'t':trainer_id}):continue
        tz=organization_runtime_config(engine,sl['action_id'])['timezone']; current=now or datetime.now(ZoneInfo(tz))
        if current.tzinfo is None:current=current.replace(tzinfo=ZoneInfo(tz))
        _,end=slot_start_end(sl,tz); states=_slot_participant_states(engine,sl['id']); pending=[x for x in states if x['status']=='EN_ATTENTE']
        if not pending or current>=end:
            x=dict(sl);x['pending_count']=len(pending);x['ready_to_sign']=not pending;out.append(x)
    return out


def list_slot_countersignatures(engine,sid):
    return q(engine,"""SELECT c.*,t.full_name assigned_trainer_name FROM trainer_countersignatures_v3 c
      LEFT JOIN trainers t ON t.id=c.trainer_id WHERE c.slot_id=:s ORDER BY c.signed_at,c.id""",{'s':sid})


def required_slot_countersignatures_complete(engine,sid):
    assigned=list_slot_trainers(engine,sid)
    signed=list_slot_countersignatures(engine,sid)
    if assigned:
        signed_ids={int(x['trainer_id']) for x in signed if x.get('trainer_id') is not None}
        missing=[x for x in assigned if int(x['trainer_id']) not in signed_ids]
        return not missing,missing
    # Legacy fallback: a historical countersignature is sufficient where no V3 assignment exists.
    return bool(signed),([] if signed else [{'full_name':'Intervenant'}])


def countersign_slot(engine,sid,name,email,actor,declaration,trainer_id=None,signature_bytes=None,ip_address=None,user_agent=None,now=None):
    """Create an immutable V3 countersignature after all server-side gates pass.

    signature_bytes is mandatory for V3 assigned trainers. Legacy unassigned test/data paths may
    still create a NOM_PRENOM proof so historical APIs remain readable during migration.
    """
    slot=one(engine,'SELECT * FROM slots WHERE id=:s',{'s':sid})
    if not slot:return False,'Créneau introuvable.'
    assigned=list_slot_trainers(engine,sid)
    if trainer_id is None and assigned:
        matches=[x for x in assigned if (email and x.get('email') and x['email'].lower()==email.lower()) or x.get('full_name','').strip().lower()==(name or '').strip().lower()]
        if len(matches)==1: trainer_id=matches[0]['trainer_id']
    ok,msg,_=slot_countersignature_eligibility(engine,sid,trainer_id=trainer_id,now=now)
    if not ok:return False,msg
    existing=one(engine,'SELECT id FROM trainer_countersignatures_v3 WHERE slot_id=:s AND trainer_id IS :t',{'s':sid,'t':trainer_id})
    if existing:return False,'Cette contresignature est déjà enregistrée et ne peut pas être modifiée.'
    method='NOM_PRENOM'; path=None; digest=None
    if assigned:
        if not signature_bytes:return False,'La signature manuscrite de l’intervenant est obligatoire.'
        digest=__import__('hashlib').sha256(signature_bytes).hexdigest()
        path=SIG_DIR/f"trainer_sig_{slot['action_id']}_{sid}_{trainer_id}_{digest[:12]}.png"
        path.write_bytes(signature_bytes); method='MANUSCRITE'
    elif signature_bytes:
        digest=__import__('hashlib').sha256(signature_bytes).hexdigest()
        path=SIG_DIR/f"trainer_sig_{slot['action_id']}_{sid}_legacy_{digest[:12]}.png"; path.write_bytes(signature_bytes); method='MANUSCRITE'
    signed_at=(now.astimezone(ZoneInfo('UTC')).isoformat() if now is not None and now.tzinfo else utcnow_iso())
    execute(engine,"""INSERT INTO trainer_countersignatures_v3(slot_id,trainer_id,trainer_name,trainer_email,signed_at,declaration_text,
      signature_path,signature_sha256,method,actor,ip_address,user_agent,created_at)
      VALUES(:s,:t,:n,:e,:at,:d,:p,:h,:m,:a,:ip,:ua,:c)""",
      {'s':sid,'t':trainer_id,'n':name,'e':email or None,'at':signed_at,'d':declaration,'p':str(path) if path else None,'h':digest,
       'm':method,'a':actor,'ip':ip_address,'ua':user_agent,'c':signed_at})
    audit(engine,'TRAINER_COUNTERSIGNED',slot['action_id'],actor,'slot',sid,{'trainer_id':trainer_id,'trainer_name':name,'method':method,'signature_sha256':digest})
    return True,''

def update_participant(engine,pid,d,actor):
    p=one(engine,'SELECT * FROM participants WHERE id=:p',{'p':pid})
    if not p: return False,'Participant introuvable.'
    merged={**p,**d}; merged=validate_participant_payload(merged)
    d={**d, **{k:merged.get(k) for k in ['individual_action_no','last_name','birth_name','first_name','birth_date','email','employee_id','company_name','phone']}}
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
    evidence=one(engine,"SELECT (SELECT COUNT(*) FROM signatures WHERE slot_id=:s)+(SELECT COUNT(*) FROM attendance_status WHERE slot_id=:s AND status='ABSENT')+(SELECT COUNT(*) FROM trainer_countersignatures_v3 WHERE slot_id=:s) n",{'s':sid})['n']
    if evidence: return None
    execute(engine,"UPDATE slots SET status='REPORTE',change_reason=:r,updated_at=:u WHERE id=:s",{'r':reason,'u':utcnow_iso(),'s':sid})
    ns=add_slot(engine,old['action_id'],date_s,start_s,end_s,actor,old['send_offset_min'],old['reminder1_offset_min'],old['reminder2_offset_min'],old['close_offset_min'])
    execute(engine,"UPDATE slots SET parent_slot_id=:p,slot_kind='REPORT',change_reason=:r WHERE id=:s",{'p':sid,'r':reason,'s':ns})
    _copy_slot_trainer_assignments(engine,sid,ns,actor,'Report : '+str(reason or ''))
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
            cs_ok,missing=required_slot_countersignatures_complete(engine,sl['id'])
            if not cs_ok:
                problems.append(f"Contresignature intervenant manquante sur le créneau #{sl['id']}" + (" : "+', '.join(x.get('full_name') or 'Intervenant' for x in missing) if missing else ''))
            continue
        if att and att['status']=='ABSENT':
            cs_ok,missing=required_slot_countersignatures_complete(engine,sl['id'])
            if not cs_ok:
                problems.append(f"Contresignature intervenant manquante sur le créneau absent #{sl['id']}" + (" : "+', '.join(x.get('full_name') or 'Intervenant' for x in missing) if missing else ''))
            if not catchup_for_absence(engine,pid,sl['id']):
                problems.append(f"Absence non rattrapée sur le créneau #{sl['id']}")
            continue
        try:
            if parse_dt(sl['slot_date'],sl['end_time']) > now:
                problems.append(f"Créneau #{sl['id']} non encore achevé")
                continue
        except Exception: pass
        problems.append(f"Signature manquante sur le créneau #{sl['id']}")
        cs_ok,missing=required_slot_countersignatures_complete(engine,sl['id'])
        if not cs_ok:
            problems.append(f"Contresignature intervenant manquante sur le créneau #{sl['id']}" + (" : "+', '.join(x.get('full_name') or 'Intervenant' for x in missing) if missing else ''))
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
    name,email,phone=validate_trainer_payload(name,email,phone)
    now=utcnow_iso(); tid=execute(engine,'INSERT INTO trainers(full_name,email,phone,created_at,updated_at) VALUES(:n,:e,:p,:c,:c)',{'n':name,'e':email,'p':phone,'c':now})
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
    """Return all non-archived actions for which the trainer has an active V3 assignment.

    Action-level assignments grant visibility to the action. Slot-level assignments also grant
    visibility so a punctual replacement remains able to reach the relevant action even if no
    action-level row was created explicitly.
    """
    return q(engine,"""SELECT DISTINCT a.* FROM actions a
      WHERE a.status<>'ARCHIVEE' AND (
        EXISTS (SELECT 1 FROM action_trainers at WHERE at.action_id=a.id AND at.trainer_id=:t AND at.active=1)
        OR EXISTS (SELECT 1 FROM slots s JOIN slot_trainers st ON st.slot_id=s.id
                   WHERE s.action_id=a.id AND st.trainer_id=:t AND st.active=1 AND st.assignment_status='ACTIVE')
        OR a.trainer_id=:t
      ) ORDER BY COALESCE(a.start_date,''),a.action_no""",{'t':trainer_id})


def list_action_trainers(engine, action_id, active_only=True):
    wh=" AND at.active=1" if active_only else ""
    return q(engine,f"""SELECT at.*,t.full_name,t.email,t.phone,t.microsoft_email,t.entra_user_id,t.entra_status,t.entra_last_verified_at,t.active trainer_active
      FROM action_trainers at JOIN trainers t ON t.id=at.trainer_id
      WHERE at.action_id=:a{wh}
      ORDER BY at.is_referent DESC, CASE at.role WHEN 'REFERENT' THEN 0 WHEN 'INTERVENANT' THEN 1 ELSE 2 END, t.full_name""",{'a':action_id})


def list_slot_trainers(engine, slot_id, active_only=True):
    wh=" AND st.active=1 AND st.assignment_status='ACTIVE'" if active_only else ""
    return q(engine,f"""SELECT st.*,t.full_name,t.email,t.phone,t.microsoft_email,t.entra_user_id,t.entra_status,t.entra_last_verified_at,t.active trainer_active
      FROM slot_trainers st JOIN trainers t ON t.id=st.trainer_id
      WHERE st.slot_id=:s{wh}
      ORDER BY CASE st.role WHEN 'PRINCIPAL' THEN 0 WHEN 'CO_INTERVENANT' THEN 1 WHEN 'REMPLACANT' THEN 2 ELSE 3 END, t.full_name""",{'s':slot_id})


def trainer_assignment_history(engine, action_id, slot_id=None):
    if slot_id is None:
        return q(engine,"""SELECT h.*,t.full_name FROM trainer_assignment_history h LEFT JOIN trainers t ON t.id=h.trainer_id
          WHERE h.action_id=:a ORDER BY h.created_at,h.id""",{'a':action_id})
    return q(engine,"""SELECT h.*,t.full_name FROM trainer_assignment_history h LEFT JOIN trainers t ON t.id=h.trainer_id
      WHERE h.action_id=:a AND h.slot_id=:s ORDER BY h.created_at,h.id""",{'a':action_id,'s':slot_id})


def _log_assignment(engine, scope_type, action_id, trainer_id, event_type, actor, *, slot_id=None,
                    old_role=None,new_role=None,old_status=None,new_status=None,reason=None):
    execute(engine,"""INSERT INTO trainer_assignment_history(scope_type,action_id,slot_id,trainer_id,event_type,
      old_role,new_role,old_status,new_status,reason,actor,created_at)
      VALUES(:scope,:a,:s,:t,:ev,:orole,:nrole,:ost,:nst,:r,:by,:n)""",
      {'scope':scope_type,'a':action_id,'s':slot_id,'t':trainer_id,'ev':event_type,'orole':old_role,
       'nrole':new_role,'ost':old_status,'nst':new_status,'r':reason,'by':actor,'n':utcnow_iso()})


def assign_action_trainer(engine, action_id, trainer_id, actor, role='INTERVENANT', is_referent=False, reason=None):
    """Add/reactivate an action-level trainer without removing other active trainers."""
    t=one(engine,'SELECT * FROM trainers WHERE id=:i AND active=1',{'i':trainer_id})
    if not t: return False,'Intervenant introuvable ou inactif.'
    role='REFERENT' if is_referent else (role or 'INTERVENANT').upper()
    now=utcnow_iso()
    if is_referent:
        # Only one referent is kept at action level. Other intervenants remain active.
        olds=q(engine,"SELECT * FROM action_trainers WHERE action_id=:a AND is_referent=1 AND active=1 AND trainer_id<>:t",{'a':action_id,'t':trainer_id})
        for old in olds:
            execute(engine,"UPDATE action_trainers SET is_referent=0,role=CASE WHEN role='REFERENT' THEN 'INTERVENANT' ELSE role END,updated_at=:u WHERE id=:i",{'u':now,'i':old['id']})
            _log_assignment(engine,'ACTION',action_id,old['trainer_id'],'REFERENT_CHANGED',actor,
                            old_role=old.get('role'),new_role='INTERVENANT',old_status='ACTIVE',new_status='ACTIVE',reason=reason)
    old=one(engine,'SELECT * FROM action_trainers WHERE action_id=:a AND trainer_id=:t',{'a':action_id,'t':trainer_id})
    execute(engine,"""INSERT INTO action_trainers(action_id,trainer_id,role,is_referent,active,created_at,updated_at)
      VALUES(:a,:t,:r,:ref,1,:n,:n)
      ON CONFLICT(action_id,trainer_id) DO UPDATE SET role=excluded.role,is_referent=excluded.is_referent,active=1,updated_at=excluded.updated_at""",
      {'a':action_id,'t':trainer_id,'r':role,'ref':1 if is_referent else 0,'n':now})
    _log_assignment(engine,'ACTION',action_id,trainer_id,'ASSIGNED' if not old or not old.get('active') else 'UPDATED',actor,
                    old_role=(old or {}).get('role'),new_role=role,old_status='ACTIVE' if old and old.get('active') else 'INACTIVE',new_status='ACTIVE',reason=reason)
    if is_referent:
        execute(engine,'UPDATE actions SET trainer_id=:i,trainer_name=:n,trainer_email=:e,updated_at=:u WHERE id=:a',
                {'i':trainer_id,'n':t['full_name'],'e':t.get('email'),'u':now,'a':action_id})
    audit(engine,'ACTION_TRAINER_ASSIGNED',action_id,actor,'trainer',trainer_id,{'role':role,'is_referent':bool(is_referent),'reason':reason})
    return True,''


def unassign_action_trainer(engine, action_id, trainer_id, actor, reason=None):
    row=one(engine,'SELECT * FROM action_trainers WHERE action_id=:a AND trainer_id=:t',{'a':action_id,'t':trainer_id})
    if not row or not row.get('active'): return False,'Affectation active introuvable.'
    now=utcnow_iso()
    execute(engine,'UPDATE action_trainers SET active=0,is_referent=0,updated_at=:u WHERE id=:i',{'u':now,'i':row['id']})
    _log_assignment(engine,'ACTION',action_id,trainer_id,'UNASSIGNED',actor,old_role=row.get('role'),old_status='ACTIVE',new_status='INACTIVE',reason=reason)
    # Do not erase historical/slot assignments. Current future/present slot rights remain explicit.
    if row.get('is_referent'):
        execute(engine,'UPDATE actions SET trainer_id=NULL,trainer_name=NULL,trainer_email=NULL,updated_at=:u WHERE id=:a AND trainer_id=:t',{'u':now,'a':action_id,'t':trainer_id})
    audit(engine,'ACTION_TRAINER_UNASSIGNED',action_id,actor,'trainer',trainer_id,{'reason':reason})
    return True,''


def assign_slot_trainer(engine, slot_id, trainer_id, actor, role='PRINCIPAL', reason=None, replaced_assignment_id=None):
    sl=one(engine,'SELECT * FROM slots WHERE id=:s',{'s':slot_id})
    t=one(engine,'SELECT * FROM trainers WHERE id=:i AND active=1',{'i':trainer_id})
    if not sl: return False,'Créneau introuvable.'
    if not t: return False,'Intervenant introuvable ou inactif.'
    role=(role or 'PRINCIPAL').upper()
    now=utcnow_iso(); old=one(engine,'SELECT * FROM slot_trainers WHERE slot_id=:s AND trainer_id=:t',{'s':slot_id,'t':trainer_id})
    execute(engine,"""INSERT INTO slot_trainers(slot_id,trainer_id,role,assignment_status,replaced_assignment_id,reason,created_by,active,created_at,updated_at)
      VALUES(:s,:t,:r,'ACTIVE',:rep,:why,:by,1,:n,:n)
      ON CONFLICT(slot_id,trainer_id) DO UPDATE SET role=excluded.role,assignment_status='ACTIVE',replaced_assignment_id=excluded.replaced_assignment_id,
        reason=excluded.reason,created_by=excluded.created_by,active=1,updated_at=excluded.updated_at""",
      {'s':slot_id,'t':trainer_id,'r':role,'rep':replaced_assignment_id,'why':reason,'by':actor,'n':now})
    _log_assignment(engine,'SLOT',sl['action_id'],trainer_id,'ASSIGNED' if not old or not old.get('active') else 'UPDATED',actor,
                    slot_id=slot_id,old_role=(old or {}).get('role'),new_role=role,
                    old_status=(old or {}).get('assignment_status') or 'INACTIVE',new_status='ACTIVE',reason=reason)
    # A punctual slot assignment grants action visibility without forcing action-level membership.
    audit(engine,'SLOT_TRAINER_ASSIGNED',sl['action_id'],actor,'slot',slot_id,{'trainer_id':trainer_id,'role':role,'reason':reason})
    return True,''


def unassign_slot_trainer(engine, slot_id, trainer_id, actor, reason=None, status='INACTIVE'):
    sl=one(engine,'SELECT * FROM slots WHERE id=:s',{'s':slot_id}); row=one(engine,'SELECT * FROM slot_trainers WHERE slot_id=:s AND trainer_id=:t',{'s':slot_id,'t':trainer_id})
    if not sl or not row or not row.get('active'): return False,'Affectation active introuvable.'
    now=utcnow_iso(); status=(status or 'INACTIVE').upper()
    execute(engine,'UPDATE slot_trainers SET active=0,assignment_status=:st,reason=:r,updated_at=:u WHERE id=:i',{'st':status,'r':reason,'u':now,'i':row['id']})
    _log_assignment(engine,'SLOT',sl['action_id'],trainer_id,'UNASSIGNED',actor,slot_id=slot_id,old_role=row.get('role'),old_status=row.get('assignment_status'),new_status=status,reason=reason)
    audit(engine,'SLOT_TRAINER_UNASSIGNED',sl['action_id'],actor,'slot',slot_id,{'trainer_id':trainer_id,'status':status,'reason':reason})
    return True,''


def replace_slot_trainer(engine, slot_id, old_trainer_id, new_trainer_id, actor, reason=None, role='REMPLACANT'):
    """Replace one active slot assignment while retaining immutable history of who was planned."""
    old=one(engine,'SELECT * FROM slot_trainers WHERE slot_id=:s AND trainer_id=:t AND active=1',{'s':slot_id,'t':old_trainer_id})
    if not old: return False,'Intervenant initial non affecté à ce créneau.'
    ok,msg=unassign_slot_trainer(engine,slot_id,old_trainer_id,actor,reason,status='REPLACED')
    if not ok: return ok,msg
    ok,msg=assign_slot_trainer(engine,slot_id,new_trainer_id,actor,role=role,reason=reason,replaced_assignment_id=old['id'])
    if ok:
        sl=one(engine,'SELECT action_id FROM slots WHERE id=:s',{'s':slot_id})
        audit(engine,'SLOT_TRAINER_REPLACED',sl['action_id'],actor,'slot',slot_id,{'old_trainer_id':old_trainer_id,'new_trainer_id':new_trainer_id,'reason':reason})
    return ok,msg


def set_trainer_active(engine,tid,active,actor):
    execute(engine,'UPDATE trainers SET active=:x,updated_at=:u WHERE id=:i',{'x':1 if active else 0,'u':utcnow_iso(),'i':tid}); audit(engine,'TRAINER_STATUS_CHANGED',None,actor,'trainer',tid,{'active':bool(active)})


def purge_trainer(engine,tid,actor):
    t=one(engine,'SELECT * FROM trainers WHERE id=:i',{'i':tid})
    if not t:return False,'Intervenant introuvable.'
    # I2: never purge a trainer that has assignment history or proofs; deactivate instead.
    used=one(engine,"""SELECT
      (SELECT COUNT(*) FROM action_trainers WHERE trainer_id=:i)+
      (SELECT COUNT(*) FROM slot_trainers WHERE trainer_id=:i)+
      (SELECT COUNT(*) FROM trainer_assignment_history WHERE trainer_id=:i)+
      (SELECT COUNT(*) FROM trainer_reports WHERE trainer_id=:i) n""",{'i':tid})['n']
    if used:
        return False,"Impossible de supprimer cet intervenant : des affectations ou preuves historiques existent. Désactivez son compte."
    execute(engine,'UPDATE actions SET trainer_id=NULL,trainer_name=NULL,trainer_email=NULL WHERE trainer_id=:i',{'i':tid})
    execute(engine,'DELETE FROM trainer_access_tokens WHERE trainer_id=:i',{'i':tid})
    execute(engine,'DELETE FROM trainers WHERE id=:i',{'i':tid})
    audit(engine,'TRAINER_PURGED',None,actor,'trainer',tid,{'name':t.get('full_name')}); return True,''


def assign_trainer(engine,aid,tid,actor):
    """V2-compatible setter: change the action REFERENT while preserving other I2 assignments."""
    old=one(engine,'SELECT trainer_id FROM actions WHERE id=:a',{'a':aid}) or {}; old_tid=old.get('trainer_id')
    if not tid:
        if old_tid:
            unassign_action_trainer(engine,aid,old_tid,actor,'Retrait du référent via compatibilité V2')
            # Deactivate the former referent on slots only; co-intervenants/remplaçants remain untouched.
            for sl in q(engine,'SELECT id FROM slots WHERE action_id=:a',{'a':aid}):
                row=one(engine,'SELECT * FROM slot_trainers WHERE slot_id=:s AND trainer_id=:t AND active=1',{'s':sl['id'],'t':old_tid})
                if row and row.get('role')=='PRINCIPAL': unassign_slot_trainer(engine,sl['id'],old_tid,actor,'Retrait du référent','INACTIVE')
        execute(engine,'UPDATE actions SET trainer_id=NULL,trainer_name=NULL,trainer_email=NULL,updated_at=:u WHERE id=:a',{'u':utcnow_iso(),'a':aid})
        return
    ok,msg=assign_action_trainer(engine,aid,tid,actor,role='REFERENT',is_referent=True,reason='Référent défini')
    if not ok:return
    # The legacy single-trainer setter means replacement: deactivate the former referent at action level,
    # while preserving any other I2 intervenants that were added explicitly.
    if old_tid and old_tid!=tid:
        oldar=one(engine,'SELECT * FROM action_trainers WHERE action_id=:a AND trainer_id=:t AND active=1',{'a':aid,'t':old_tid})
        if oldar: unassign_action_trainer(engine,aid,old_tid,actor,'Changement du référent via compatibilité V2')
    # Existing slots keep explicit co-intervenants. Replace only the former referent/principal.
    for sl in q(engine,'SELECT id FROM slots WHERE action_id=:a',{'a':aid}):
        if old_tid and old_tid!=tid:
            oldrow=one(engine,'SELECT * FROM slot_trainers WHERE slot_id=:s AND trainer_id=:t AND active=1',{'s':sl['id'],'t':old_tid})
            if oldrow and oldrow.get('role')=='PRINCIPAL': unassign_slot_trainer(engine,sl['id'],old_tid,actor,'Changement du référent','REPLACED')
        # Do not overwrite a role already explicitly configured for the new referent.
        cur=one(engine,'SELECT * FROM slot_trainers WHERE slot_id=:s AND trainer_id=:t AND active=1',{'s':sl['id'],'t':tid})
        if not cur: assign_slot_trainer(engine,sl['id'],tid,actor,'PRINCIPAL','Affectation du référent')
    execute(engine,'UPDATE trainer_access_tokens SET active=0 WHERE action_id=:a',{'a':aid})
    audit(engine,'TRAINER_ASSIGNED',aid,actor,'trainer',tid,{'name':(one(engine,'SELECT full_name FROM trainers WHERE id=:i',{'i':tid}) or {}).get('full_name'),'compatibility':'V2_REFERENT'})

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
    return bool(one(engine,"""SELECT a.id FROM actions a WHERE a.id=:a AND (
      a.trainer_id=:t
      OR EXISTS (SELECT 1 FROM action_trainers at WHERE at.action_id=a.id AND at.trainer_id=:t AND at.active=1)
      OR EXISTS (SELECT 1 FROM slots s JOIN slot_trainers st ON st.slot_id=s.id
                 WHERE s.action_id=a.id AND st.trainer_id=:t AND st.active=1 AND st.assignment_status='ACTIVE'))""",{'a':action_id,'t':trainer_id}))

def trainer_action_dashboard(engine,trainer_id,action_id,tz_name='Europe/Paris'):
    if not trainer_action_authorized(engine,trainer_id,action_id): return None
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':action_id})
    # I2 principle: an intervenant sees the slots to which they are really assigned.
    # The V2 compatibility trainer_id is accepted as a fallback for unmigrated databases.
    slots=q(engine,"""SELECT DISTINCT s.* FROM slots s WHERE s.action_id=:a AND s.status NOT IN ('ANNULE','REPORTE') AND (
      EXISTS (SELECT 1 FROM slot_trainers st WHERE st.slot_id=s.id AND st.trainer_id=:t AND st.active=1 AND st.assignment_status='ACTIVE')
      OR (NOT EXISTS (SELECT 1 FROM slot_trainers sx WHERE sx.slot_id=s.id AND sx.active=1) AND :t=(SELECT trainer_id FROM actions WHERE id=:a))
      ) ORDER BY s.slot_date,s.start_time""",{'a':action_id,'t':trainer_id})
    parts=q(engine,'SELECT * FROM participants WHERE action_id=:a AND active=1 ORDER BY last_name,first_name',{'a':action_id})
    now=datetime.now(ZoneInfo(tz_name)); next_slot=None
    for sl in slots:
        try:
            start,_=slot_start_end(sl,tz_name)
            if start>=now: next_slot=sl; break
        except Exception: pass
    action_assignment=one(engine,"SELECT * FROM action_trainers WHERE action_id=:a AND trainer_id=:t AND active=1",{'a':action_id,'t':trainer_id})
    return {'action':a,'slots':slots,'participants':parts,'next_slot':next_slot,'assignment':action_assignment}


def set_action_trainer_planning_permission(engine, action_id, trainer_id, allowed, actor):
    row=one(engine,'SELECT * FROM action_trainers WHERE action_id=:a AND trainer_id=:t AND active=1',{'a':action_id,'t':trainer_id})
    if not row: return False,"L'intervenant n'est pas affecté à cette action."
    execute(engine,'UPDATE action_trainers SET can_manage_planning=:v,updated_at=:u WHERE id=:i',{'v':1 if allowed else 0,'u':utcnow_iso(),'i':row['id']})
    audit(engine,'TRAINER_ACTION_PLANNING_PERMISSION_CHANGED',action_id,actor,'trainer',trainer_id,{'allowed':bool(allowed)})
    return True,''


def set_slot_trainer_planning_permission(engine, slot_id, trainer_id, allowed, actor):
    sl=one(engine,'SELECT action_id FROM slots WHERE id=:s',{'s':slot_id})
    row=one(engine,"SELECT * FROM slot_trainers WHERE slot_id=:s AND trainer_id=:t AND active=1 AND assignment_status='ACTIVE'",{'s':slot_id,'t':trainer_id})
    if not sl or not row: return False,"L'intervenant n'est pas affecté à ce créneau."
    execute(engine,'UPDATE slot_trainers SET can_manage_planning=:v,updated_at=:u WHERE id=:i',{'v':1 if allowed else 0,'u':utcnow_iso(),'i':row['id']})
    audit(engine,'TRAINER_SLOT_PLANNING_PERMISSION_CHANGED',sl['action_id'],actor,'slot',slot_id,{'trainer_id':trainer_id,'allowed':bool(allowed)})
    return True,''


def trainer_planning_scope(engine, trainer_id, action_id):
    """Return explicit I4 planning rights. Visibility alone never grants modification rights."""
    ar=one(engine,"SELECT * FROM action_trainers WHERE action_id=:a AND trainer_id=:t AND active=1",{'a':action_id,'t':trainer_id})
    whole=bool(ar and ar.get('can_manage_planning'))
    slot_ids={int(x['slot_id']) for x in q(engine,"""SELECT st.slot_id FROM slot_trainers st JOIN slots s ON s.id=st.slot_id
      WHERE s.action_id=:a AND st.trainer_id=:t AND st.active=1 AND st.assignment_status='ACTIVE' AND st.can_manage_planning=1""",{'a':action_id,'t':trainer_id})}
    return {'can_manage_action':whole,'slot_ids':slot_ids,'assignment':ar}


def slot_has_historical_evidence(engine, sid):
    """Central I4 evidence gate used by every trainer-side planning mutation."""
    r=one(engine,"""SELECT
      (SELECT COUNT(*) FROM signatures WHERE slot_id=:s AND status='VALIDE')+
      (SELECT COUNT(*) FROM attendance_status WHERE slot_id=:s AND status IN ('ABSENT','PRESENT_REGULARISE'))+
      (SELECT COUNT(*) FROM trainer_countersignatures_v3 WHERE slot_id=:s) n""",{'s':sid})
    return bool(r and r['n'])


def _active_action_slots(engine, action_id, exclude_slot_id=None):
    rows=q(engine,"SELECT * FROM slots WHERE action_id=:a AND status NOT IN ('ANNULE','REPORTE') ORDER BY slot_date,start_time",{'a':action_id})
    return [x for x in rows if exclude_slot_id is None or int(x['id'])!=int(exclude_slot_id)]


def _intervals_overlap(a_start,a_end,b_start,b_end):
    return a_start < b_end and b_start < a_end


def validate_trainer_planning_change(engine, trainer_id, action_id, *, slot_id=None, date_s=None, start_s=None, end_s=None, operation='UPDATE', now=None):
    """Server-side I4 guardrails. Returns (allowed, message, details)."""
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':action_id})
    if not a: return False,'Action introuvable.',{}
    if normalize_action_status(a.get('status')) in ('CLOTUREE','ARCHIVEE'):
        return False,'Une action clôturée ou archivée ne peut pas être modifiée par un intervenant.',{}
    scope=trainer_planning_scope(engine,trainer_id,action_id)
    op=(operation or 'UPDATE').upper()
    old=None
    if slot_id is not None:
        old=one(engine,'SELECT * FROM slots WHERE id=:s AND action_id=:a',{'s':slot_id,'a':action_id})
        if not old: return False,'Créneau introuvable.',{}
        if not scope['can_manage_action'] and int(slot_id) not in scope['slot_ids']:
            return False,"Vous n'êtes pas autorisé à modifier ce créneau.",{}
        if slot_has_historical_evidence(engine,slot_id):
            return False,'Ce créneau contient déjà une preuve historique et ne peut plus être modifié.',{}
    elif not scope['can_manage_action']:
        return False,"Seul un intervenant autorisé à gérer le planning de l'action peut ajouter une séance.",{}
    if op in ('UPDATE','REPORT') and old:
        assigned=list_slot_trainers(engine,slot_id)
        others=[x for x in assigned if int(x['trainer_id'])!=int(trainer_id)]
        if others and not scope['can_manage_action']:
            return False,"Ce créneau concerne un autre intervenant : une autorisation de gestion du planning de l'action est requise.",{'other_trainers':others}
    date_s=date_s or (old or {}).get('slot_date'); start_s=start_s or (old or {}).get('start_time'); end_s=end_s or (old or {}).get('end_time')
    if not (date_s and start_s and end_s): return False,'Date et horaires obligatoires.',{}
    tz_name=organization_runtime_config(engine,action_id)['timezone']
    candidate={'slot_date':date_s,'start_time':start_s,'end_time':end_s}
    try: start,end=slot_start_end(candidate,tz_name)
    except Exception: return False,'Date ou horaires invalides.',{}
    current=now or datetime.now(ZoneInfo(tz_name))
    if current.tzinfo is None: current=current.replace(tzinfo=ZoneInfo(tz_name))
    if old:
        _,old_end=slot_start_end(old,tz_name)
        if old_end <= current:
            return False,"Une séance déjà terminée ne peut pas être déplacée directement par un intervenant.",{}
    if a.get('start_date') and date_s < a['start_date']:
        return False,"La séance ne peut pas être placée avant la date de début de l'action.",{}
    if a.get('end_date') and date_s > a['end_date']:
        return False,"La séance ne peut pas être placée après la date de fin de l'action.",{}
    for other in _active_action_slots(engine,action_id,slot_id):
        os,oe=slot_start_end(other,tz_name)
        if _intervals_overlap(start,end,os,oe):
            return False,f"Chevauchement avec le créneau du {other['slot_date']} {other['start_time']}–{other['end_time']}.",{'conflict_slot_id':other['id']}
    # I4: an intervenant cannot silently change the contractual/scheduled volume of an existing slot.
    if old and abs(slot_duration_hours(old)-slot_duration_hours(candidate))>0.001:
        return False,"La modification changerait le volume horaire. Seule l'administration peut valider ce changement.",{}
    active=_active_action_slots(engine,action_id,slot_id)
    total=round(sum(slot_duration_hours(x) for x in active)+slot_duration_hours(candidate),2)
    planned=round(float(a.get('planned_hours') or 0),2)
    if not old and planned>0 and total>planned+0.001:
        return False,f"L'ajout porterait le planning à {total:g} h pour {planned:g} h contractuelles.",{'total_hours':total,'planned_hours':planned}
    # Detect conflicts for all trainers who would remain assigned to the slot.
    affected_ids={int(trainer_id)}
    if old:
        affected_ids.update(int(x['trainer_id']) for x in list_slot_trainers(engine,slot_id))
    for tid in affected_ids:
        other_slots=q(engine,"""SELECT DISTINCT s.* FROM slots s JOIN slot_trainers st ON st.slot_id=s.id
          WHERE st.trainer_id=:t AND st.active=1 AND st.assignment_status='ACTIVE' AND s.status NOT IN ('ANNULE','REPORTE')
            AND (:sid IS NULL OR s.id<>:sid)""",{'t':tid,'sid':slot_id})
        for oslot in other_slots:
            os,oe=slot_start_end(oslot,organization_runtime_config(engine,oslot['action_id'])['timezone'])
            # Comparing aware datetimes also catches overlaps across actions/timezones.
            if _intervals_overlap(start,end,os,oe):
                return False,"Un intervenant affecté à ce créneau est déjà engagé sur un autre créneau à cet horaire.",{'trainer_id':tid,'conflict_slot_id':oslot['id']}
    return True,'',{'start':start.isoformat(),'end':end.isoformat(),'total_hours':total,'planned_hours':planned,'scope':scope}


def propagate_planning_change(engine, action_id, slot_id, change_type, actor, *, base_url=None, tz_name=None, details=None):
    """Synchronize all implemented I4 dependants and record hooks for future Teams/notifications."""
    tz_name=tz_name or organization_runtime_config(engine,action_id)['timezone']
    participants=one(engine,'SELECT COUNT(*) n FROM participants WHERE action_id=:a AND active=1',{'a':action_id})['n']
    trainers=len(list_slot_trainers(engine,slot_id)) if slot_id else len(list_action_trainers(engine,action_id))
    attendance_synced=0
    if base_url:
        ensure_tokens_and_events(engine,action_id,base_url,tz_name); attendance_synced=1
    try:
        reschedule_pending_quality_campaigns(engine,action_id,actor); quality_synced=1
    except Exception:
        quality_synced=0
    teams=one(engine,"SELECT enabled FROM action_modules WHERE action_id=:a AND module_code='TEAMS'",{'a':action_id})
    teams_required=bool(teams and teams.get('enabled'))
    payload=details or {}
    eid=execute(engine,"""INSERT INTO planning_change_events(action_id,slot_id,change_type,actor,affected_participants,affected_trainers,
      attendance_synced,quality_synced,portals_synced,teams_required,teams_status,notification_status,details_json,created_at)
      VALUES(:a,:s,:c,:by,:p,:t,:att,:q,1,:tr,:ts,'PENDING',:d,:n)""",
      {'a':action_id,'s':slot_id,'c':change_type,'by':actor,'p':participants,'t':trainers,'att':attendance_synced,'q':quality_synced,
       'tr':1 if teams_required else 0,'ts':'PENDING_I7' if teams_required else 'NOT_ENABLED','d':json.dumps(payload,ensure_ascii=False,default=str),'n':utcnow_iso()})
    audit(engine,'PLANNING_CHANGE_PROPAGATED',action_id,actor,'slot',slot_id,{'change_type':change_type,'event_id':eid,'attendance':bool(attendance_synced),'quality':bool(quality_synced),'teams':'PENDING_I7' if teams_required else 'NOT_ENABLED'})
    return eid


def trainer_update_slot(engine, trainer_id, sid, date_s,start_s,end_s,actor, *, base_url=None, now=None):
    sl=one(engine,'SELECT * FROM slots WHERE id=:s',{'s':sid})
    if not sl:return False,'Créneau introuvable.'
    ok,msg,_=validate_trainer_planning_change(engine,trainer_id,sl['action_id'],slot_id=sid,date_s=date_s,start_s=start_s,end_s=end_s,operation='UPDATE',now=now)
    if not ok:return False,msg
    d={'slot_date':date_s,'start_time':start_s,'end_time':end_s,'send_offset_min':sl['send_offset_min'],'reminder1_offset_min':sl['reminder1_offset_min'],'reminder2_offset_min':sl['reminder2_offset_min'],'close_offset_min':sl['close_offset_min']}
    update_slot(engine,sid,d,actor)
    propagate_planning_change(engine,sl['action_id'],sid,'TRAINER_UPDATE',actor,base_url=base_url,details={'before':{'slot_date':sl['slot_date'],'start_time':sl['start_time'],'end_time':sl['end_time']},'after':{'slot_date':date_s,'start_time':start_s,'end_time':end_s}})
    return True,''


def trainer_add_slot(engine, trainer_id, action_id, date_s,start_s,end_s,actor, *, base_url=None, now=None):
    ok,msg,_=validate_trainer_planning_change(engine,trainer_id,action_id,date_s=date_s,start_s=start_s,end_s=end_s,operation='ADD',now=now)
    if not ok:return None,msg
    sid=add_slot(engine,action_id,date_s,start_s,end_s,actor)
    # The action-level planner owns the new slot operationally; preserve the inherited referent and add the editor when needed.
    if not one(engine,"SELECT id FROM slot_trainers WHERE slot_id=:s AND trainer_id=:t AND active=1",{'s':sid,'t':trainer_id}):
        assign_slot_trainer(engine,sid,trainer_id,actor,'PRINCIPAL','Séance ajoutée par intervenant')
    propagate_planning_change(engine,action_id,sid,'TRAINER_ADD',actor,base_url=base_url,details={'slot_date':date_s,'start_time':start_s,'end_time':end_s})
    return sid,''


def trainer_report_slot(engine, trainer_id, sid, date_s,start_s,end_s,actor,reason='Report', *, base_url=None, now=None):
    sl=one(engine,'SELECT * FROM slots WHERE id=:s',{'s':sid})
    if not sl:return None,'Créneau introuvable.'
    ok,msg,_=validate_trainer_planning_change(engine,trainer_id,sl['action_id'],slot_id=sid,date_s=date_s,start_s=start_s,end_s=end_s,operation='REPORT',now=now)
    if not ok:return None,msg
    ns=report_slot(engine,sid,date_s,start_s,end_s,actor,reason)
    if not ns:return None,'Ce créneau ne peut pas être reporté.'
    propagate_planning_change(engine,sl['action_id'],ns,'TRAINER_REPORT',actor,base_url=base_url,details={'from_slot_id':sid,'reason':reason})
    return ns,''


def action_calendar_ics(engine, action_id, *, trainer_id=None, beneficiary_id=None, prodid='-//Clarte360//Gestion des actions V3//FR'):
    """Generate a stable-UID ICS view. Re-downloading it reflects moves/reports without changing slot UIDs."""
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':action_id})
    if not a:return b''
    if trainer_id is not None and not trainer_action_authorized(engine,trainer_id,action_id): return b''
    if beneficiary_id is not None:
        allowed=one(engine,"SELECT p.id FROM participants p WHERE p.action_id=:a AND p.beneficiary_id=:b AND p.active=1",{'a':action_id,'b':beneficiary_id})
        if not allowed:return b''
    tz=organization_runtime_config(engine,action_id)['timezone']
    rows=q(engine,"SELECT * FROM slots WHERE action_id=:a ORDER BY slot_date,start_time,id",{'a':action_id})
    if trainer_id is not None:
        visible={int(x['id']) for x in (trainer_action_dashboard(engine,trainer_id,action_id,tz) or {}).get('slots',[])}
        rows=[x for x in rows if int(x['id']) in visible or x.get('status') in ('ANNULE','REPORTE')]
    def esc(v):
        return str(v or '').replace('\\','\\\\').replace(';','\\;').replace(',','\\,').replace('\n','\\n')
    lines=['BEGIN:VCALENDAR','VERSION:2.0',f'PRODID:{prodid}','CALSCALE:GREGORIAN','METHOD:PUBLISH']
    for sl in rows:
        start,end=slot_start_end(sl,tz)
        lines += ['BEGIN:VEVENT',f"UID:clarte360-slot-{sl['id']}@gestion-actions",f"DTSTAMP:{datetime.now(ZoneInfo('UTC')).strftime('%Y%m%dT%H%M%SZ')}",
                  f"DTSTART;TZID={tz}:{start.strftime('%Y%m%dT%H%M%S')}",f"DTEND;TZID={tz}:{end.strftime('%Y%m%dT%H%M%S')}",
                  f"SUMMARY:{esc(a['action_no']+' — '+a['title'])}",f"LOCATION:{esc(a.get('location') or '')}",f"DESCRIPTION:{esc((a.get('client_name') or '')+' — '+(sl.get('slot_kind') or 'NORMAL'))}"]
        if sl.get('status') in ('ANNULE','REPORTE'): lines.append('STATUS:CANCELLED')
        lines.append('END:VEVENT')
    lines.append('END:VCALENDAR')
    return ('\r\n'.join(lines)+'\r\n').encode('utf-8')


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
    data=validate_organization_payload(data)
    now=utcnow_iso(); fields=['name','legal_name','address','postal_code','city','country','siret','rcs','naf','vat_id','nda','website','general_email','phone','timezone','privacy_contact','privacy_notice','logo_path','favicon_path','primary_color','secondary_color','email_from_name','email_from_address','retention_months']
    if org_id:
        sets=','.join(f'{k}=:{k}' for k in fields); execute(engine,f'UPDATE organizations SET {sets},updated_at=:updated_at WHERE id=:id',{**{k:data.get(k) for k in fields},'updated_at':now,'id':org_id}); oid=org_id
    else:
        cols=','.join(fields); vals=','.join(':'+k for k in fields); oid=execute(engine,f'INSERT INTO organizations({cols},created_at,updated_at) VALUES({vals},:created_at,:updated_at)',{**{k:data.get(k) for k in fields},'created_at':now,'updated_at':now})
    audit(engine,'ORGANIZATION_SAVED',actor=actor,entity_type='organization',entity_id=oid,details={'name':data.get('name')}); return oid

def add_agency(engine, organization_id, data, actor):
    data=validate_agency_payload(data)
    now=utcnow_iso(); aid=execute(engine,"""INSERT INTO agencies(organization_id,name,address,postal_code,city,country,siret,nda,email,phone,created_at,updated_at)
      VALUES(:o,:n,:a,:p,:c,:co,:s,:nda,:e,:ph,:x,:x)""",{'o':organization_id,'n':data['name'],'a':data.get('address'),'p':data.get('postal_code'),'c':data.get('city'),'co':data.get('country'),'s':data.get('siret'),'nda':data.get('nda'),'e':data.get('email'),'ph':data.get('phone'),'x':now})
    audit(engine,'AGENCY_CREATED',actor=actor,entity_type='agency',entity_id=aid,details={'name':data['name']}); return aid

def archive_action(engine, aid, actor):
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':aid})
    if not a:return False,'Action introuvable.'
    execute(engine,"UPDATE actions SET status='ARCHIVEE',archived_at=:t,updated_at=:t WHERE id=:a",{'t':utcnow_iso(),'a':aid}); audit(engine,'ACTION_ARCHIVED',aid,actor,'action',aid,{}); return True,''

def set_action_modules(engine, aid, prestation_type, attendance, hot, cold, trainer_feedback, organization_id=None, agency_id=None, actor='system'):
    now=utcnow_iso()
    execute(engine,"""UPDATE actions SET prestation_type=:p,use_attendance=:e,use_quality_hot=:h,use_quality_cold=:c,use_trainer_feedback=:t,
      organization_id=:o,agency_id=:g,updated_at=:u WHERE id=:a""",{'p':prestation_type,'e':int(bool(attendance)),'h':int(bool(hot)),'c':int(bool(cold)),'t':int(bool(trainer_feedback)),'o':organization_id,'g':agency_id,'u':now,'a':aid})
    values={'ATTENDANCE':attendance,'QUALITY_HOT':hot,'QUALITY_COLD':cold,'TRAINER_FEEDBACK':trainer_feedback}
    for code,enabled in values.items():
        en=1 if enabled else 0
        execute(engine,"""INSERT INTO action_modules(action_id,module_code,enabled,enabled_at,enabled_by,created_at,updated_at)
          VALUES(:a,:m,:e,CASE WHEN :e=1 THEN :n ELSE NULL END,:by,:n,:n)
          ON CONFLICT(action_id,module_code) DO UPDATE SET enabled=excluded.enabled,
          enabled_at=CASE WHEN excluded.enabled=1 AND action_modules.enabled=0 THEN excluded.enabled_at ELSE action_modules.enabled_at END,
          enabled_by=excluded.enabled_by,updated_at=excluded.updated_at""",{'a':aid,'m':code,'e':en,'n':now,'by':actor})
    # Create future switches disabled if absent. TEAMS is intentionally never inferred
    # from mode/location and can only be enabled explicitly in a later increment.
    for code in ('BENEFICIARY_PORTAL','COURSE_DOCUMENTS','CLIENT_TRANSMISSION','TEAMS'):
        execute(engine,"""INSERT OR IGNORE INTO action_modules(action_id,module_code,enabled,enabled_by,created_at,updated_at)
          VALUES(:a,:m,0,:by,:n,:n)""",{'a':aid,'m':code,'by':actor,'n':now})
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

def list_import_profiles(engine, organization_id=None, active_only=False):
    wh=[]; params={}
    if organization_id is not None:
        wh.append('organization_id=:o'); params['o']=organization_id
    if active_only:
        wh.append('active=1')
    sql='SELECT * FROM organization_import_profiles'
    if wh:
        sql+=' WHERE '+' AND '.join(wh)
    sql+=' ORDER BY organization_id,name,id'
    return q(engine,sql,params)


def get_import_profile(engine, profile_id):
    return one(engine,'SELECT * FROM organization_import_profiles WHERE id=:i',{'i':profile_id})


def save_import_profile(engine, profile_id, organization_id, data, actor):
    now=utcnow_iso()
    fields=['code','name','source_type','action_key','action_sheet','participant_sheet','mapping_json','config_json','active']
    vals={
        'code':validate_code(data.get('code'),'Code profil',required=True,max_len=80).upper(),
        'name':validate_short_text(data.get('name'),'Nom du profil',required=True,max_len=160),
        'source_type':validate_code(data.get('source_type') or 'EXCEL','Type de source',required=True,max_len=30).upper(),
        'action_key':validate_short_text(data.get('action_key'),"Colonne clé de l'action",required=True,max_len=160),
        'action_sheet':validate_short_text(data.get('action_sheet') or 'CONV ADM','Onglet action',required=True,max_len=100),
        'participant_sheet':validate_short_text(data.get('participant_sheet') or 'STAGIAIRE','Onglet participants',required=True,max_len=100),
        'mapping_json':validate_json_text(data.get('mapping_json') if isinstance(data.get('mapping_json'),str) else json.dumps(data.get('mapping_json') or {},ensure_ascii=False),'Mapping JSON'),
        'config_json':validate_json_text(data.get('config_json') if isinstance(data.get('config_json'),str) else json.dumps(data.get('config_json') or {},ensure_ascii=False),'Configuration JSON'),
        'active':int(bool(data.get('active',True))),
    }
    if not vals['code'] or not vals['name'] or not vals['action_key']:
        raise ValueError("Code, nom et colonne clé d'action obligatoires.")
    for key in ('mapping_json','config_json'):
        try:
            json.loads(vals[key] or '{}')
        except Exception as ex:
            raise ValueError(f'{key} invalide : {ex}')
    if profile_id:
        execute(engine,'UPDATE organization_import_profiles SET '+','.join(f'{k}=:{k}' for k in fields)+',updated_at=:u WHERE id=:id',{**vals,'u':now,'id':profile_id})
        pid=profile_id; event='IMPORT_PROFILE_UPDATED'
    else:
        sql=("INSERT INTO organization_import_profiles(organization_id,code,name,source_type,action_key,action_sheet,participant_sheet,mapping_json,config_json,active,created_at,updated_at) "
             "VALUES(:o,:code,:name,:source_type,:action_key,:action_sheet,:participant_sheet,:mapping_json,:config_json,:active,:u,:u)")
        pid=execute(engine,sql,{**vals,'o':organization_id,'u':now})
        event='IMPORT_PROFILE_CREATED'
    audit(engine,event,actor=actor,entity_type='import_profile',entity_id=pid,details={'organization_id':organization_id,'code':vals['code'],'name':vals['name']})
    return pid


def set_import_profile_active(engine, profile_id, active, actor):
    execute(engine,'UPDATE organization_import_profiles SET active=:a,updated_at=:u WHERE id=:i',{'a':int(bool(active)),'u':utcnow_iso(),'i':profile_id})
    audit(engine,'IMPORT_PROFILE_ACTIVATION_CHANGED',actor=actor,entity_type='import_profile',entity_id=profile_id,details={'active':bool(active)})


def ensure_default_import_profile(engine, organization_id, action_key='NO_CLAR', actor='system'):
    existing=one(engine,'SELECT id FROM organization_import_profiles WHERE organization_id=:o ORDER BY id LIMIT 1',{'o':organization_id})
    if existing:
        return existing['id']
    return save_import_profile(engine,None,organization_id,{
        'code':'GESTION_PRINCIPALE','name':'Base de gestion principale','source_type':'EXCEL','action_key':action_key,
        'action_sheet':'CONV ADM','participant_sheet':'STAGIAIRE','mapping_json':'{}','config_json':'{}','active':True
    },actor)

def update_agency(engine, agency_id, data, actor):
    old=one(engine,'SELECT * FROM agencies WHERE id=:i',{'i':agency_id})
    if not old: raise ValueError('Agence introuvable')
    data=validate_agency_payload({**old,**data})
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
        iso=due_dt.astimezone(ZoneInfo('UTC')).isoformat()
        execute(engine,"""UPDATE quality_email_events SET due_at=:d,last_error=NULL
          WHERE campaign_id=:c AND event_type='INITIAL' AND status='PENDING'""",{'d':iso,'c':camp['id']})
        # V3 I5: no automatic quality reminders. Historical pending reminder rows are neutralized, never deleted.
        execute(engine,"UPDATE quality_email_events SET status='SKIPPED',last_error='V3 I5: relance automatique désactivée' WHERE campaign_id=:c AND event_type IN ('REMINDER_1','REMINDER_2') AND status='PENDING'",{'c':camp['id']})
        execute(engine,'UPDATE quality_campaigns SET reminder1_due_at=NULL,reminder2_due_at=NULL WHERE id=:c',{'c':camp['id']})
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
    if a.get('use_trainer_feedback'):
        trainers=q(engine,"""SELECT DISTINCT t.* FROM action_trainers at JOIN trainers t ON t.id=at.trainer_id
          WHERE at.action_id=:a AND at.active=1 AND t.active=1 AND t.email IS NOT NULL AND TRIM(t.email)<>'' ORDER BY t.full_name""",{'a':action_id})
        if not trainers and a.get('trainer_id'):
            tr=one(engine,"SELECT * FROM trainers WHERE id=:i AND active=1 AND email IS NOT NULL AND TRIM(email)<>''",{'i':a['trainer_id']})
            trainers=[tr] if tr else []
        tpl=get_standard_template(engine,org_id,a.get('prestation_type'),'TRAINER') if trainers else None
        due=standard_quality_due(engine,action_id,'TRAINER') if trainers else None
        for tr in trainers:
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
    execute(engine,"""INSERT OR IGNORE INTO quality_email_events(campaign_id,event_type,due_at,created_at)
      VALUES(:c,'INITIAL',:d,:n)""",{'c':campaign_id,'d':due.astimezone(ZoneInfo('UTC')).isoformat(),'n':utcnow_iso()})
    execute(engine,"UPDATE quality_email_events SET status='SKIPPED',last_error='V3 I5: relance automatique désactivée' WHERE campaign_id=:c AND event_type IN ('REMINDER_1','REMINDER_2') AND status='PENDING'",{'c':campaign_id})
    execute(engine,'UPDATE quality_campaigns SET reminder1_due_at=NULL,reminder2_due_at=NULL WHERE id=:c',{'c':campaign_id})

def queue_quality_manual_reminder(engine,campaign_id,actor='system'):
    camp=one(engine,'SELECT * FROM quality_campaigns WHERE id=:c',{'c':campaign_id})
    if not camp: raise ValueError('Campagne introuvable')
    if camp.get('status')=='COMPLETED': raise ValueError('Ce questionnaire est déjà complété.')
    count=int(camp.get('manual_reminder_count') or 0)+1
    et=f'MANUAL_{count}'
    now=utcnow_iso()
    execute(engine,"INSERT INTO quality_email_events(campaign_id,event_type,due_at,created_at) VALUES(:c,:e,:n,:n)",{'c':campaign_id,'e':et,'n':now})
    execute(engine,'UPDATE quality_campaigns SET manual_reminder_count=:x,last_manual_reminder_at=:n,last_manual_reminder_by=:b WHERE id=:c',{'x':count,'n':now,'b':actor,'c':campaign_id})
    audit(engine,'QUALITY_MANUAL_REMINDER_QUEUED',camp['action_id'],actor,'quality_campaign',campaign_id,{'count':count,'event_type':et})
    return et

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
    rows=q(engine,"""SELECT qq.question_code,qq.rubric_code,qq.question_text,r.response_type,r.answer_json FROM quality_responses r JOIN questionnaire_questions qq ON qq.id=r.question_id JOIN quality_campaigns c ON c.id=r.campaign_id JOIN actions a ON a.id=c.action_id"""+where,p)
    rubric_labels={'R01':'Information et objectifs','R02':'Organisation','R03':'Moyens et environnement','R04':'Supports et ressources','R05':'Intervenant / animation','R06':'Adaptation et accompagnement','R07':'Accessibilité','R08':'Atteinte des objectifs','R09':'Utilité / transfert','R10':'Satisfaction globale','R11':'Recommandation','R12':'Difficultés / réclamations','I06':'Difficultés / aléas'}
    agg={}
    for r in rows:
      k=(r['rubric_code'],r['question_code']); x=agg.setdefault(k,{'Rubrique':rubric_labels.get(k[0],k[0]),'Code rubrique':k[0],'Question':r.get('question_text') or k[1],'Code question':k[1],'Réponses':0,'Moyenne':None,'_vals':[]})
      try:v=json.loads(r.get('answer_json') or 'null')
      except:v=None
      if v is not None:x['Réponses']+=1
      if isinstance(v,(int,float)):x['_vals'].append(float(v))
    out=[]
    for x in agg.values():
      vals=x.pop('_vals'); x['Moyenne']=round(sum(vals)/len(vals),2) if vals else None; out.append(x)
    return sorted(out,key=lambda x:(x['Code rubrique'],x['Code question']))

def quality_reminders(engine, organization_id=None, agency_id=None, action_id=None, trainer_id=None, kind=None):
    wh=["c.status<>'COMPLETED'"]; p={}
    if organization_id: wh.append('a.organization_id=:o');p['o']=organization_id
    if agency_id: wh.append('a.agency_id=:g');p['g']=agency_id
    if action_id: wh.append('a.id=:a');p['a']=action_id
    if trainer_id: wh.append('c.trainer_id=:t');p['t']=trainer_id
    if kind: wh.append('c.campaign_kind=:k');p['k']=kind
    return q(engine,"""SELECT c.id campaign_id,c.campaign_kind,c.status,c.due_at,c.sent_at,c.manual_reminder_count,c.last_manual_reminder_at,c.last_manual_reminder_by,c.token,a.id action_id,a.action_no,a.title action_title,a.organization_id,a.agency_id,p.id participant_id,p.first_name,p.last_name,p.email participant_email,t.id trainer_id,t.full_name trainer_full_name,t.email trainer_email FROM quality_campaigns c JOIN actions a ON a.id=c.action_id LEFT JOIN participants p ON p.id=c.participant_id LEFT JOIN trainers t ON t.id=c.trainer_id WHERE """+' AND '.join(wh)+" ORDER BY c.due_at,c.id",p)

def attendance_regularization_items(engine, organization_id=None, agency_id=None, action_id=None, trainer_id=None):
    wh=["a.status NOT IN ('BROUILLON','ARCHIVEE')","p.active=1","s.status<>'ANNULE'"]; p={}
    if organization_id: wh.append('a.organization_id=:o');p['o']=organization_id
    if agency_id: wh.append('a.agency_id=:g');p['g']=agency_id
    if action_id: wh.append('a.id=:a');p['a']=action_id
    if trainer_id:
        wh.append('EXISTS (SELECT 1 FROM slot_trainers st WHERE st.slot_id=s.id AND st.trainer_id=:t AND st.active=1)');p['t']=trainer_id
    rows=q(engine,"""SELECT a.id action_id,a.action_no,a.title action_title,s.id slot_id,s.slot_date,s.start_time,s.end_time,p.id participant_id,p.first_name,p.last_name,p.email FROM actions a JOIN slots s ON s.action_id=a.id JOIN participants p ON p.action_id=a.id WHERE """+' AND '.join(wh)+" ORDER BY s.slot_date,s.start_time,p.last_name,p.first_name",p)
    out=[]
    for r in rows:
        _,end=slot_start_end(r,organization_runtime_config(engine,r['action_id'])['timezone'])
        if datetime.now(end.tzinfo)<end: continue
        sig=one(engine,"SELECT id FROM signatures WHERE participant_id=:p AND slot_id=:s AND status='VALIDE'",{'p':r['participant_id'],'s':r['slot_id']})
        att=one(engine,"SELECT status FROM attendance_status WHERE participant_id=:p AND slot_id=:s",{'p':r['participant_id'],'s':r['slot_id']})
        if sig or (att and att.get('status') in ('ABSENT','NON_CONCERNE','PRESENT_REGULARISE')): continue
        out.append(r)
    return out

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

# --- I9-B: journal universel des communications + contresignature automatique ---
def queue_communication(engine, action_id, communication_type, recipient_email, *, participant_id=None, trainer_id=None, slot_id=None, trigger_mode='AUTO', due_at=None, metadata=None, idempotency_key=None):
    now=utcnow_iso(); due=due_at or now
    if idempotency_key:
        existing=one(engine,'SELECT id FROM communication_events WHERE idempotency_key=:k',{'k':idempotency_key})
        if existing:return existing['id']
    return execute(engine,"""INSERT INTO communication_events(action_id,participant_id,trainer_id,slot_id,communication_type,recipient_email,trigger_mode,status,due_at,metadata_json,idempotency_key,created_at,updated_at)
      VALUES(:a,:p,:t,:s,:ct,:e,:tm,'A_ENVOYER',:d,:m,:k,:n,:n)""",{'a':action_id,'p':participant_id,'t':trainer_id,'s':slot_id,'ct':communication_type,'e':recipient_email or None,'tm':trigger_mode,'d':due,'m':json.dumps(metadata or {},ensure_ascii=False,default=str),'k':idempotency_key,'n':now})

def mark_communication(engine,event_id,status,*,sent_at=None,last_error=None):
    execute(engine,'UPDATE communication_events SET status=:s,sent_at=COALESCE(:at,sent_at),last_error=:er,updated_at=:u WHERE id=:i',{'s':status,'at':sent_at,'er':last_error,'u':utcnow_iso(),'i':event_id})

def communication_journal(engine,action_id):
    return q(engine,"""SELECT ce.*,p.first_name participant_first_name,p.last_name participant_last_name,t.full_name trainer_name,
      s.slot_date,s.start_time,s.end_time FROM communication_events ce
      LEFT JOIN participants p ON p.id=ce.participant_id LEFT JOIN trainers t ON t.id=ce.trainer_id LEFT JOIN slots s ON s.id=ce.slot_id
      WHERE ce.action_id=:a ORDER BY ce.created_at DESC,ce.id DESC""",{'a':action_id})

def refresh_countersign_communications(engine, *, now=None, tz_name=None):
    """Queue one trainer request only when the countersign workflow is actionable.

    Rules:
    - before slot end: queue immediately only when every participant status is already final;
    - at/after slot end: queue the request even if some participants still need to be qualified;
    - future slots with pending participants must not appear as outstanding countersignatures;
    - stale future requests created by older builds are cancelled, never sent early.
    """
    current_utc=now or datetime.now(ZoneInfo('UTC'))
    if current_utc.tzinfo is None:
        current_utc=current_utc.replace(tzinfo=ZoneInfo('UTC'))
    created=0
    slots=q(engine,"""SELECT s.* FROM slots s JOIN actions a ON a.id=s.action_id
      WHERE a.status IN ('ACTIVE','A_CLOTURER') AND COALESCE(s.status,'PREVU') NOT IN ('ANNULE','REPORTE')""")
    for sl in slots:
        local_tz=tz_name or organization_runtime_config(engine,sl['action_id'])['timezone']
        _,end=slot_start_end(sl,local_tz)
        states=_slot_participant_states(engine,sl['id'])
        pending=[x for x in states if x['status']=='EN_ATTENTE']
        all_final=bool(states) and not pending
        slot_ended=current_utc >= end.astimezone(ZoneInfo('UTC'))
        actionable=all_final or slot_ended

        # Clean up requests incorrectly pre-created by older releases for future slots.
        if not actionable:
            execute(engine,"""UPDATE communication_events SET status='ANNULE',last_error='Annulé automatiquement : créneau futur non encore à contresigner',updated_at=:u
              WHERE slot_id=:s AND communication_type='COUNTERSIGN_REQUEST' AND status IN ('A_ENVOYER','EN_FILE')""",
              {'u':utcnow_iso(),'s':sl['id']})
            continue

        due_iso=current_utc.astimezone(ZoneInfo('UTC')).isoformat()
        signed={int(x['trainer_id']) for x in list_slot_countersignatures(engine,sl['id']) if x.get('trainer_id') is not None}
        for tr in list_slot_trainers(engine,sl['id']):
            tid=int(tr['trainer_id'])
            if tid in signed or not (tr.get('email') or '').strip():
                continue
            key=f'countersign:{sl["id"]}:{tid}'
            existing=one(engine,'SELECT * FROM communication_events WHERE idempotency_key=:k ORDER BY id DESC LIMIT 1',{'k':key})
            if existing and existing.get('status')=='ENVOYE':
                continue
            if existing and existing.get('status') in ('ANNULE','ECHEC'):
                execute(engine,"""UPDATE communication_events SET status='A_ENVOYER',due_at=:d,last_error=NULL,updated_at=:u,metadata_json=:m
                  WHERE id=:i""",{'d':due_iso,'u':utcnow_iso(),'m':json.dumps({'reason':'ALL_FINAL' if all_final and not slot_ended else 'SLOT_END','pending_count':len(pending)},ensure_ascii=False),'i':existing['id']})
                created+=1
                continue
            eid=queue_communication(engine,sl['action_id'],'COUNTERSIGN_REQUEST',tr['email'],trainer_id=tid,slot_id=sl['id'],trigger_mode='AUTO',due_at=due_iso,metadata={'reason':'ALL_FINAL' if all_final and not slot_ended else 'SLOT_END','pending_count':len(pending)},idempotency_key=key)
            execute(engine,"UPDATE communication_events SET due_at=:d,updated_at=:u WHERE id=:i AND status='A_ENVOYER'",{'d':due_iso,'u':utcnow_iso(),'i':eid})
            created+=1
    return created

# --- V2.2 LOT 2: beneficiaires permanents + portail documentaire ---
BENEFICIARY_DOC_DIR=ROOT/'data'/'documents'/'blobs'
BENEFICIARY_DOC_DIR.mkdir(parents=True,exist_ok=True)
DEFAULT_ALLOWED_EXTENSIONS={'.pdf','.json','.doc','.docx','.xls','.xlsx','.ppt','.pptx','.txt','.csv','.jpg','.jpeg','.png','.webp','.zip'}
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
    d=validate_participant_payload({'last_name':last_name,'first_name':first_name,'birth_date':birth_date,'email':email,'birth_name':birth_name,'phone':phone},require_identity=True)
    if not d.get('birth_date'):
        raise ValueError('Nom, prénom et date de naissance sont obligatoires pour créer un bénéficiaire permanent.')
    last_name,first_name,birth_date,email,birth_name,phone=d['last_name'],d['first_name'],d['birth_date'],d['email'],d['birth_name'],d['phone']
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

def beneficiary_portal_status(engine, beneficiary_id):
    """Return a beneficiary-safe activation status for admin/trainer dashboards."""
    acc=one(engine,"SELECT beneficiary_id,email,active,invited_at,email_verified_at,last_login_at,password_hash,pending_email FROM beneficiary_portal_accounts WHERE beneficiary_id=:b",{'b':beneficiary_id})
    if not acc:
        return {'state':'ABSENT','label':'Aucun espace personnel','activated':False,'email':None,'last_login_at':None,'invited_at':None}
    activated=bool(acc.get('active') and acc.get('email_verified_at') and acc.get('password_hash'))
    if not acc.get('active'):
        state='DESACTIVE'; label='Espace désactivé'
    elif activated:
        state='ACTIVE'; label='Espace activé'
    elif acc.get('invited_at'):
        state='INVITE'; label='Invitation envoyée — activation en attente'
    else:
        state='A_ACTIVER'; label='Espace créé — activation en attente'
    return {'state':state,'label':label,'activated':activated,'email':acc.get('email'),'pending_email':acc.get('pending_email'),'last_login_at':acc.get('last_login_at'),'invited_at':acc.get('invited_at'),'email_verified_at':acc.get('email_verified_at')}

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
    vals={'client_admin_email':validate_email(admin_email,'Contact administratif'),'client_training_email':validate_email(training_email,'Contact formation / accompagnement'),'client_quality_email':validate_email(quality_email,'Contact qualité'),'client_billing_email':validate_email(billing_email,'Contact facturation'),'client_other_email':validate_email(other_email,'Autre contact')}
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
        label=r.get('Rubrique') or 'Autre'; rubric.setdefault(label,[])
        if r.get('Moyenne') is not None: rubric[label].append(float(r['Moyenne']))
    rubric_avg={k:round(sum(v)/len(v),2) for k,v in rubric.items() if v}
    nps=base.get('nps') or []; nps_score=None
    if nps: nps_score=round(100*(sum(x>=9 for x in nps)-sum(x<=6 for x in nps))/len(nps),1)
    weak=sorted([{'Rubrique':k,'Moyenne':v} for k,v in rubric_avg.items()],key=lambda x:x['Moyenne'])[:5]
    return {**base,'rubric_averages':rubric_avg,'nps_score':nps_score,'weak_points':weak}

def configure_final_transmission(engine, action_id, enabled=False, to_quality=True, to_training=True, other_first_name=None, other_last_name=None, other_email=None, actor='system'):
    if other_first_name: other_first_name=validate_participant_payload({'last_name':'X','first_name':other_first_name},require_identity=True)['first_name']
    if other_last_name: other_last_name=validate_participant_payload({'last_name':other_last_name,'first_name':'X'},require_identity=True)['last_name']
    other_email=validate_email(other_email,'Autre destinataire final')
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

# ---- V3 I7: Microsoft Teams / Graph ---------------------------------------

def action_module(engine, action_id, module_code):
    return one(engine,"SELECT * FROM action_modules WHERE action_id=:a AND module_code=:m",{'a':action_id,'m':module_code})


def action_module_enabled(engine, action_id, module_code):
    row=action_module(engine,action_id,module_code)
    return bool(row and row.get('enabled'))


def next_future_slot(engine, action_id, now=None):
    tz_name=organization_runtime_config(engine,action_id)['timezone']
    now=now or datetime.now(ZoneInfo(tz_name))
    rows=q(engine,"SELECT * FROM slots WHERE action_id=:a AND status NOT IN ('ANNULE','REMPLACE') ORDER BY slot_date,start_time,id",{'a':action_id})
    for sl in rows:
        start,_=slot_start_end(sl,tz_name)
        if start>now:
            return sl,start
    return None,None


def set_generic_action_module(engine, action_id, module_code, enabled, actor='system', effective_from=None, config=None):
    """Enable/disable an independent V3 module without deleting produced evidence.

    TEAMS activation is deliberately prospective: absent an explicit effective date, the
    first future slot becomes the effect boundary.  Past slots are never retrofitted.
    """
    code=(module_code or '').upper().strip()
    if code not in ('BENEFICIARY_PORTAL','COURSE_DOCUMENTS','CLIENT_TRANSMISSION','TEAMS'):
        raise ValueError('Module générique inconnu.')
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':action_id})
    if not a: raise ValueError('Action introuvable.')
    old=action_module(engine,action_id,code)
    now=utcnow_iso()
    eff=effective_from
    if code=='TEAMS' and enabled and not eff:
        _,start=next_future_slot(engine,action_id)
        eff=start.isoformat() if start else None
    # I8: Teams peut être activé dès la création de l'action, avant tout calendrier.
    # effective_from reste vide jusqu'au premier créneau futur.
    config_json=json.dumps(config or {},ensure_ascii=False) if config is not None else (old or {}).get('config_json')
    execute(engine,"""INSERT INTO action_modules(action_id,module_code,enabled,enabled_at,enabled_by,effective_from,config_json,created_at,updated_at)
      VALUES(:a,:m,:e,CASE WHEN :e=1 THEN :n ELSE NULL END,:by,:f,:c,:n,:n)
      ON CONFLICT(action_id,module_code) DO UPDATE SET enabled=excluded.enabled,
      enabled_at=CASE WHEN excluded.enabled=1 AND action_modules.enabled=0 THEN excluded.enabled_at ELSE action_modules.enabled_at END,
      enabled_by=excluded.enabled_by,effective_from=CASE WHEN excluded.enabled=1 THEN excluded.effective_from ELSE action_modules.effective_from END,
      config_json=COALESCE(excluded.config_json,action_modules.config_json),updated_at=excluded.updated_at""",
      {'a':action_id,'m':code,'e':1 if enabled else 0,'n':now,'by':actor,'f':eff,'c':config_json})
    if code=='TEAMS':
        if enabled:
            queue_teams_sync(engine,action_id,None,'ACTION_ACTIVATED',actor,{'effective_from':eff})
        else:
            # Existing room/reports are historical evidence; only future automation stops.
            execute(engine,"UPDATE teams_occurrences SET status='DISABLED',updated_at=:u WHERE action_id=:a AND status='PLANNED'",{'u':now,'a':action_id})
    audit(engine,'ACTION_MODULE_TOGGLED',action_id,actor,'action_module',code,{'enabled':bool(enabled),'effective_from':eff})
    return eff


def teams_room(engine, action_id):
    return one(engine,'SELECT * FROM teams_action_rooms WHERE action_id=:a',{'a':action_id})


def teams_occurrences(engine, action_id):
    return q(engine,"""SELECT o.*,s.slot_date,s.start_time,s.end_time FROM teams_occurrences o
      JOIN slots s ON s.id=o.slot_id WHERE o.action_id=:a ORDER BY s.slot_date,s.start_time,s.id""",{'a':action_id})


def teams_roles(engine, action_id, slot_id=None):
    sql='SELECT * FROM teams_participant_roles WHERE action_id=:a AND active=1'
    p={'a':action_id}
    if slot_id is not None:
        sql+=' AND (slot_id=:s OR slot_id IS NULL)';p['s']=slot_id
    return q(engine,sql+' ORDER BY display_name,email,id',p)


def queue_teams_sync(engine, action_id, slot_id, event_type, actor='system', details=None):
    now=utcnow_iso()
    # SQLite UNIQUE treats NULLs as distinct, so action-level events are manually deduplicated.
    if slot_id is None:
        row=one(engine,"SELECT id FROM teams_sync_events WHERE action_id=:a AND slot_id IS NULL AND event_type=:e AND status='PENDING'",{'a':action_id,'e':event_type})
        if row:return row['id']
    try:
        eid=execute(engine,"""INSERT INTO teams_sync_events(action_id,slot_id,event_type,status,details_json,created_at)
          VALUES(:a,:s,:e,'PENDING',:d,:n)""",{'a':action_id,'s':slot_id,'e':event_type,'d':json.dumps(details or {},ensure_ascii=False,default=str),'n':now})
    except Exception:
        row=one(engine,"SELECT id FROM teams_sync_events WHERE action_id=:a AND ((slot_id=:s) OR (slot_id IS NULL AND :s IS NULL)) AND event_type=:e",{'a':action_id,'s':slot_id,'e':event_type})
        return row['id'] if row else None
    audit(engine,'TEAMS_SYNC_QUEUED',action_id,actor,'teams_sync_event',eid,{'event_type':event_type,'slot_id':slot_id})
    return eid


def _teams_effective_slots(engine, action_id):
    mod=action_module(engine,action_id,'TEAMS')
    if not mod or not mod.get('enabled'):return []
    eff=mod.get('effective_from')
    tz_name=organization_runtime_config(engine,action_id)['timezone']
    rows=q(engine,"SELECT * FROM slots WHERE action_id=:a AND status NOT IN ('ANNULE','REMPLACE') ORDER BY slot_date,start_time,id",{'a':action_id})
    out=[]; now_local=datetime.now(ZoneInfo(tz_name)); e=None
    if eff:
        e=datetime.fromisoformat(eff)
        if e.tzinfo is None:e=e.replace(tzinfo=ZoneInfo(tz_name))
    for sl in rows:
        start,end=slot_start_end(sl,tz_name)
        if e and start<e:continue
        if not e and start<now_local:continue
        out.append((sl,start,end))
    return out


def refresh_teams_occurrences(engine, action_id, actor='system'):
    """Mirror future Teams-managed slots into the additive occurrence table."""
    rows=_teams_effective_slots(engine,action_id); now=utcnow_iso(); active_slot_ids=set()
    room=teams_room(engine,action_id)
    for sl,start,end in rows:
        active_slot_ids.add(int(sl['id']))
        execute(engine,"""INSERT INTO teams_occurrences(action_room_id,action_id,slot_id,scheduled_start_utc,scheduled_end_utc,status,created_at,updated_at)
          VALUES(:r,:a,:s,:b,:e,'PLANNED',:n,:n)
          ON CONFLICT(slot_id) DO UPDATE SET action_room_id=excluded.action_room_id,scheduled_start_utc=excluded.scheduled_start_utc,
          scheduled_end_utc=excluded.scheduled_end_utc,status=CASE WHEN teams_occurrences.attendance_report_id IS NULL THEN 'PLANNED' ELSE teams_occurrences.status END,
          updated_at=excluded.updated_at""",{'r':room.get('id') if room else None,'a':action_id,'s':sl['id'],'b':start.astimezone(ZoneInfo('UTC')).isoformat(),'e':end.astimezone(ZoneInfo('UTC')).isoformat(),'n':now})
    existing=q(engine,"SELECT id,slot_id,attendance_report_id FROM teams_occurrences WHERE action_id=:a",{'a':action_id})
    for x in existing:
        if int(x['slot_id']) not in active_slot_ids and not x.get('attendance_report_id'):
            execute(engine,"UPDATE teams_occurrences SET status='OUT_OF_SCOPE',updated_at=:n WHERE id=:i",{'n':now,'i':x['id']})
    audit(engine,'TEAMS_OCCURRENCES_REFRESHED',action_id,actor,'action',action_id,{'count':len(rows)})
    return len(rows)


def refresh_teams_trainer_roles(engine, action_id, actor='system'):
    """Persist desired advanced Teams roles. Guests are invited separately by the worker."""
    now=utcnow_iso(); effective=_teams_effective_slots(engine,action_id); wanted=set()
    for sl,_,_ in effective:
        for tr in list_slot_trainers(engine,sl['id'],active_only=True):
            email=(tr.get('microsoft_email') or tr.get('email') or '').strip().lower()
            if not email:continue
            key=(int(sl['id']),email);wanted.add(key)
            role='COORGANIZER' if (tr.get('role') or '').upper() in ('PRINCIPAL','REFERENT') else 'PRESENTER'
            stored_entra=(tr.get('entra_user_id') or '').strip() or None
            stored_status=(tr.get('entra_status') or 'UNCHECKED').strip()
            execute(engine,"""INSERT INTO teams_participant_roles(action_id,slot_id,trainer_id,email,display_name,entra_user_id,role,guest_status,active,created_at,updated_at)
              VALUES(:a,:s,:t,:e,:d,:u,:r,:gs,1,:n,:n)
              ON CONFLICT(action_id,slot_id,email) DO UPDATE SET trainer_id=excluded.trainer_id,display_name=excluded.display_name,
              entra_user_id=COALESCE(excluded.entra_user_id,teams_participant_roles.entra_user_id),role=excluded.role,guest_status=excluded.guest_status,active=1,updated_at=excluded.updated_at""",{'a':action_id,'s':sl['id'],'t':tr['trainer_id'],'e':email,'d':tr.get('full_name'),'u':stored_entra,'r':role,'gs':stored_status,'n':now})
    for row in q(engine,'SELECT id,slot_id,email FROM teams_participant_roles WHERE action_id=:a AND active=1',{'a':action_id}):
        if (int(row['slot_id']) if row.get('slot_id') is not None else None,(row.get('email') or '').lower()) not in wanted:
            execute(engine,'UPDATE teams_participant_roles SET active=0,updated_at=:n WHERE id=:i',{'n':now,'i':row['id']})
    return len(wanted)


def create_or_sync_teams_room(engine, action_id, graph_client, actor='worker'):
    if not action_module_enabled(engine,action_id,'TEAMS'):
        return None
    slots=_teams_effective_slots(engine,action_id)
    a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':action_id})
    room=teams_room(engine,action_id)
    # After the final session there may be no future slot, but the stable room must
    # remain usable to retrieve late Microsoft attendance reports.
    if not slots:
        if room and room.get('online_meeting_id'):
            return room
        raise ValueError("Aucun créneau Teams futur dans la période d'effet.")
    first_start=slots[0][1].astimezone(ZoneInfo('UTC')).isoformat()
    last_end=slots[-1][2].astimezone(ZoneInfo('UTC')).isoformat()
    subject=f"{a.get('action_no') or ''} — {a.get('title') or 'Action'}".strip(' —')
    if not room or not room.get('online_meeting_id'):
        payload=graph_client.create_online_meeting(subject,first_start,last_end)
        now=utcnow_iso()
        if room:
            execute(engine,"""UPDATE teams_action_rooms SET organizer_user_id=:u,organizer_upn=:up,online_meeting_id=:m,join_web_url=:j,
              subject=:s,lifecycle_status='ACTIVE',raw_json=:r,last_sync_at=:n,updated_at=:n WHERE id=:i""",
              {'u':graph_client.cfg.get('organizer_user_id'),'up':graph_client.cfg.get('organizer_upn'),'m':payload.get('id'),'j':payload.get('joinWebUrl'),'s':subject,'r':json.dumps(payload,ensure_ascii=False),'n':now,'i':room['id']})
            rid=room['id']
        else:
            rid=execute(engine,"""INSERT INTO teams_action_rooms(action_id,organizer_user_id,organizer_upn,online_meeting_id,join_web_url,subject,strategy,lifecycle_status,raw_json,last_sync_at,created_at,updated_at)
              VALUES(:a,:u,:up,:m,:j,:s,'STABLE_ACTION_LINK','ACTIVE',:r,:n,:n,:n)""",
              {'a':action_id,'u':graph_client.cfg.get('organizer_user_id'),'up':graph_client.cfg.get('organizer_upn'),'m':payload.get('id'),'j':payload.get('joinWebUrl'),'s':subject,'r':json.dumps(payload,ensure_ascii=False),'n':now})
        audit(engine,'TEAMS_ROOM_CREATED',action_id,actor,'teams_action_room',rid,{'meeting_id':payload.get('id'),'strategy':'STABLE_ACTION_LINK'})
    else:
        rid=room['id'];payload={'id':room.get('online_meeting_id'),'joinWebUrl':room.get('join_web_url')}
        # Keep the reusable action meeting window aligned with the managed schedule.
        graph_client.update_online_meeting(room['online_meeting_id'],{'startDateTime':first_start,'endDateTime':last_end,'subject':subject})
        execute(engine,"UPDATE teams_action_rooms SET subject=:s,last_sync_at=:n,updated_at=:n WHERE id=:i",{'s':subject,'n':utcnow_iso(),'i':rid})
        audit(engine,'TEAMS_ROOM_SYNCED',action_id,actor,'teams_action_room',rid,{'meeting_id':room.get('online_meeting_id')})
    refresh_teams_occurrences(engine,action_id,actor)
    execute(engine,'UPDATE teams_occurrences SET action_room_id=:r WHERE action_id=:a',{'r':rid,'a':action_id})
    refresh_teams_trainer_roles(engine,action_id,actor)
    return teams_room(engine,action_id)


def mark_teams_guest_invitation(engine, role_id, invitation, actor='worker'):
    user=(invitation or {}).get('invitedUser') or {}
    execute(engine,"""UPDATE teams_participant_roles SET entra_user_id=:u,invitation_id=:i,guest_status='INVITED',invited_at=:n,updated_at=:n WHERE id=:r""",
      {'u':user.get('id'),'i':(invitation or {}).get('id'),'n':utcnow_iso(),'r':role_id})
    row=one(engine,'SELECT * FROM teams_participant_roles WHERE id=:r',{'r':role_id}) or {}
    audit(engine,'TEAMS_GUEST_INVITED',row.get('action_id'),actor,'teams_participant_role',role_id,{'email':row.get('email')})


def _report_window(report):
    start=report.get('meetingStartDateTime') or report.get('startDateTime')
    end=report.get('meetingEndDateTime') or report.get('endDateTime')
    return start,end


def match_attendance_report_occurrence(engine, action_id, report, tolerance_minutes=30):
    """Match a Microsoft attendance report only inside the slot -30/+30 min window.

    Stable Teams links can generate many reports over time. A report outside the
    expanded slot window is deliberately left unmatched for administrator review.
    """
    start_s,end_s=_report_window(report)
    if not start_s:return None
    start=datetime.fromisoformat(start_s.replace('Z','+00:00'))
    end=datetime.fromisoformat((end_s or start_s).replace('Z','+00:00'))
    tol=timedelta(minutes=int(tolerance_minutes))
    candidates=q(engine,"SELECT * FROM teams_occurrences WHERE action_id=:a AND status NOT IN ('OUT_OF_SCOPE','DISABLED')",{'a':action_id})
    scored=[]
    for c in candidates:
        cs=datetime.fromisoformat(c['scheduled_start_utc'].replace('Z','+00:00'))
        ce=datetime.fromisoformat(c['scheduled_end_utc'].replace('Z','+00:00'))
        if end < cs-tol or start > ce+tol:
            continue
        overlap=max(0.0,(min(end,ce)-max(start,cs)).total_seconds())
        start_delta=abs((cs-start).total_seconds())
        scored.append((-overlap,start_delta,int(c['id']),c))
    return sorted(scored,key=lambda x:(x[0],x[1],x[2]))[0][3] if scored else None


def store_teams_attendance_report(engine, action_id, room_id, report, records, actor='worker'):
    rid=str(report.get('id') or '')
    if not rid:raise ValueError('Rapport Teams sans identifiant.')
    if one(engine,'SELECT id FROM teams_attendance_reports WHERE report_id=:r',{'r':rid}):return False
    occ=match_attendance_report_occurrence(engine,action_id,report)
    start,end=_report_window(report);now=utcnow_iso()
    report_raw=json.dumps({'report':report,'attendanceRecords':records or []},ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
    report_hash=hashlib.sha256(report_raw.encode('utf-8')).hexdigest()
    row_id=execute(engine,"""INSERT INTO teams_attendance_reports(action_room_id,occurrence_id,report_id,meeting_start_utc,meeting_end_utc,total_participants,raw_json,raw_sha256,retrieved_at)
      VALUES(:room,:o,:r,:s,:e,:n,:raw,:h,:d)""",{'room':room_id,'o':occ.get('id') if occ else None,'r':rid,'s':start,'e':end,'n':len(records or []),'raw':report_raw,'h':report_hash,'d':now})
    for rec in records or []:
        identity=rec.get('identity') or {};email=(rec.get('emailAddress') or '').strip() or None;display=rec.get('identity',{}).get('displayName') or rec.get('displayName')
        participant=None
        if email:
            participant=one(engine,"SELECT id FROM participants WHERE action_id=:a AND lower(email)=lower(:e) LIMIT 1",{'a':action_id,'e':email})
        intervals=rec.get('attendanceIntervals') or []
        if intervals:
            for iv in intervals:
                rec_raw=json.dumps(rec,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str); rec_hash=hashlib.sha256(rec_raw.encode('utf-8')).hexdigest()
                execute(engine,"""INSERT INTO teams_attendance_records(report_row_id,participant_id,display_name,email,join_time_utc,leave_time_utc,duration_seconds,role,identity_json,raw_json,raw_sha256,created_at)
                  VALUES(:r,:p,:d,:e,:j,:l,:du,:ro,:i,:raw,:h,:n)""",{'r':row_id,'p':participant.get('id') if participant else None,'d':display,'e':email,'j':iv.get('joinDateTime'),'l':iv.get('leaveDateTime'),'du':iv.get('durationInSeconds'),'ro':rec.get('role'),'i':json.dumps(identity,ensure_ascii=False),'raw':rec_raw,'h':rec_hash,'n':now})
        else:
            rec_raw=json.dumps(rec,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str); rec_hash=hashlib.sha256(rec_raw.encode('utf-8')).hexdigest()
            execute(engine,"""INSERT INTO teams_attendance_records(report_row_id,participant_id,display_name,email,duration_seconds,role,identity_json,raw_json,raw_sha256,created_at)
              VALUES(:r,:p,:d,:e,:du,:ro,:i,:raw,:h,:n)""",{'r':row_id,'p':participant.get('id') if participant else None,'d':display,'e':email,'du':rec.get('totalAttendanceInSeconds'),'ro':rec.get('role'),'i':json.dumps(identity,ensure_ascii=False),'raw':rec_raw,'h':rec_hash,'n':now})
    if occ:
        execute(engine,"UPDATE teams_occurrences SET attendance_report_id=:r,attendance_synced_at=:n,status='REPORT_RETRIEVED',last_error=NULL,updated_at=:n WHERE id=:o",{'r':rid,'n':now,'o':occ['id']})
    audit(engine,'TEAMS_ATTENDANCE_IMPORTED',action_id,actor,'teams_attendance_report',row_id,{'report_id':rid,'occurrence_id':occ.get('id') if occ else None,'records':len(records or [])})
    return True


def teams_attendance_reconciliation(engine, action_id):
    """Evidence comparison: Teams presence complements but never replaces attendance signature."""
    rows=[]
    for occ in teams_occurrences(engine,action_id):
        participants=q(engine,'SELECT * FROM participants WHERE action_id=:a AND active=1 ORDER BY last_name,first_name',{'a':action_id})
        report=one(engine,'SELECT * FROM teams_attendance_reports WHERE occurrence_id=:o ORDER BY id DESC LIMIT 1',{'o':occ['id']})
        for p in participants:
            signed=bool(one(engine,"SELECT id FROM signatures WHERE participant_id=:p AND slot_id=:s AND status='VALIDE'",{'p':p['id'],'s':occ['slot_id']}))
            absent=bool(one(engine,"SELECT id FROM attendance_status WHERE participant_id=:p AND slot_id=:s AND status='ABSENT'",{'p':p['id'],'s':occ['slot_id']}))
            presence=False;seconds=0
            if report:
                recs=q(engine,'SELECT * FROM teams_attendance_records WHERE report_row_id=:r AND participant_id=:p',{'r':report['id'],'p':p['id']})
                presence=bool(recs);seconds=sum(int(x.get('duration_seconds') or 0) for x in recs)
            anomaly=(presence and absent) or (signed and not presence and bool(report)) or (presence and not signed and not absent)
            rows.append({'slot_id':occ['slot_id'],'slot_date':occ['slot_date'],'start_time':occ['start_time'],'participant_id':p['id'],'participant':f"{p.get('first_name') or ''} {p.get('last_name') or ''}".strip(),'teams_present':presence,'teams_seconds':seconds,'signed':signed,'absent':absent,'anomaly':anomaly})
    return rows




def _duration_hms(seconds):
    seconds=max(0,int(seconds or 0)); h,rem=divmod(seconds,3600); m,s=divmod(rem,60)
    return f"{h:d} h {m:02d} min {s:02d} s" if h else f"{m:d} min {s:02d} s"

def teams_reports_for_action(engine, action_id):
    return q(engine,"""SELECT rep.*,room.online_meeting_id,room.organizer_upn,o.slot_id,s.slot_date,s.start_time,s.end_time
      FROM teams_attendance_reports rep JOIN teams_action_rooms room ON room.id=rep.action_room_id
      LEFT JOIN teams_occurrences o ON o.id=rep.occurrence_id LEFT JOIN slots s ON s.id=o.slot_id
      WHERE room.action_id=:a ORDER BY COALESCE(rep.meeting_start_utc,rep.retrieved_at),rep.id""",{'a':action_id})

def teams_report_connections(engine, report_row_id):
    return q(engine,"""SELECT ar.*,p.first_name participant_first_name,p.last_name participant_last_name,p.email participant_email
      FROM teams_attendance_records ar LEFT JOIN participants p ON p.id=ar.participant_id
      WHERE ar.report_row_id=:r ORDER BY COALESCE(ar.join_time_utc,''),ar.id""",{'r':report_row_id})

def teams_occurrence_evidence(engine, action_id):
    out=[]
    for occ in teams_occurrences(engine,action_id):
        rep=one(engine,'SELECT * FROM teams_attendance_reports WHERE occurrence_id=:o ORDER BY id DESC LIMIT 1',{'o':occ['id']})
        row=dict(occ); row['report']=rep; row['connections']=teams_report_connections(engine,rep['id']) if rep else []
        out.append(row)
    return out

def teams_participant_evidence(engine, action_id, participant_id):
    rows=[]
    for occ in teams_occurrences(engine,action_id):
        rep=one(engine,'SELECT * FROM teams_attendance_reports WHERE occurrence_id=:o ORDER BY id DESC LIMIT 1',{'o':occ['id']})
        recs=q(engine,'SELECT * FROM teams_attendance_records WHERE report_row_id=:r AND participant_id=:p ORDER BY id',{'r':rep['id'],'p':participant_id}) if rep else []
        rows.append({'occurrence':occ,'report':rep,'records':recs,'seconds':sum(int(x.get('duration_seconds') or 0) for x in recs)})
    return rows

def suggest_teams_participant_match(engine, action_id, display_name):
    """Suggest by normalized name only; never persists or auto-confirms."""
    import unicodedata,re as _re
    def norm(v):
        x=unicodedata.normalize('NFKD',str(v or '')).encode('ascii','ignore').decode().lower()
        return ' '.join(_re.findall(r'[a-z0-9]+',x))
    target=norm(display_name)
    if not target:return None
    parts=q(engine,'SELECT id,first_name,last_name,email FROM participants WHERE action_id=:a AND active=1',{'a':action_id})
    exact=[]
    for p in parts:
        vals={norm(f"{p.get('first_name','')} {p.get('last_name','')}"),norm(f"{p.get('last_name','')} {p.get('first_name','')}")}
        if target in vals: exact.append(p)
    return exact[0] if len(exact)==1 else None

# --- I9-C: identites Microsoft permanentes et rapprochement explicite ---
def trainer_microsoft_identity(engine, trainer_id):
    return one(engine,"SELECT id,full_name,email,microsoft_email,entra_user_id,entra_status,entra_last_verified_at,entra_creation_requested_at,entra_creation_requested_by FROM trainers WHERE id=:i",{'i':trainer_id})

def set_trainer_microsoft_email(engine, trainer_id, microsoft_email, actor='admin'):
    email=validate_email(microsoft_email,'Adresse Microsoft/Teams',required=False)
    execute(engine,"UPDATE trainers SET microsoft_email=:e,entra_user_id=NULL,entra_status='UNCHECKED',entra_last_verified_at=NULL,updated_at=:n WHERE id=:i",{'e':email,'n':utcnow_iso(),'i':trainer_id})
    audit(engine,'TRAINER_MICROSOFT_EMAIL_UPDATED',None,actor,'trainer',trainer_id,{'microsoft_email':email})
    return trainer_microsoft_identity(engine,trainer_id)

def mark_trainer_entra_identity(engine, trainer_id, user, actor='worker'):
    user=user or {}; uid=(user.get('id') or '').strip() or None
    if not uid: raise ValueError('Identité Microsoft sans identifiant Entra.')
    now=utcnow_iso()
    execute(engine,"UPDATE trainers SET entra_user_id=:u,entra_status='VERIFIED',entra_last_verified_at=:n,entra_creation_requested_at=NULL,entra_creation_requested_by=NULL,updated_at=:n WHERE id=:i",{'u':uid,'n':now,'i':trainer_id})
    execute(engine,"UPDATE teams_participant_roles SET entra_user_id=:u,guest_status='VERIFIED',updated_at=:n WHERE trainer_id=:i AND active=1",{'u':uid,'n':now,'i':trainer_id})
    audit(engine,'TRAINER_ENTRA_VERIFIED',None,actor,'trainer',trainer_id,{'entra_user_id':uid})
    return trainer_microsoft_identity(engine,trainer_id)

def mark_trainer_entra_not_found(engine, trainer_id, actor='worker'):
    now=utcnow_iso()
    execute(engine,"UPDATE trainers SET entra_user_id=NULL,entra_status='NOT_FOUND',entra_last_verified_at=:n,updated_at=:n WHERE id=:i",{'n':now,'i':trainer_id})
    execute(engine,"UPDATE teams_participant_roles SET entra_user_id=NULL,guest_status='NOT_FOUND',updated_at=:n WHERE trainer_id=:i AND active=1",{'n':now,'i':trainer_id})
    audit(engine,'TRAINER_ENTRA_NOT_FOUND',None,actor,'trainer',trainer_id,{})
    return trainer_microsoft_identity(engine,trainer_id)

def request_trainer_microsoft_identity_creation(engine, trainer_id, actor='admin'):
    t=trainer_microsoft_identity(engine,trainer_id)
    if not t: raise ValueError('Intervenant introuvable.')
    email=(t.get('microsoft_email') or t.get('email') or '').strip().lower()
    if not email: raise ValueError('Aucune adresse Microsoft/Teams disponible.')
    now=utcnow_iso()
    execute(engine,"UPDATE trainers SET entra_status='CREATION_REQUESTED',entra_creation_requested_at=:n,entra_creation_requested_by=:by,updated_at=:n WHERE id=:i",{'n':now,'by':actor,'i':trainer_id})
    audit(engine,'TRAINER_ENTRA_CREATION_REQUESTED',None,actor,'trainer',trainer_id,{'email':email})
    return True

def teams_next_meeting(engine, action_id, now=None):
    rows=teams_occurrences(engine,action_id)
    now=now or datetime.now(ZoneInfo('UTC'))
    candidates=[]
    for r in rows:
        if r.get('status') in ('OUT_OF_SCOPE','DISABLED'): continue
        try: start=datetime.fromisoformat(str(r.get('scheduled_start_utc')).replace('Z','+00:00'))
        except Exception: continue
        if start.tzinfo is None: start=start.replace(tzinfo=ZoneInfo('UTC'))
        if start>=now: candidates.append((start,r))
    if not candidates: return None
    return sorted(candidates,key=lambda x:x[0])[0][1]

def teams_unmatched_attendance(engine, action_id):
    return q(engine,"""SELECT ar.id attendance_record_id,ar.display_name,ar.email,ar.duration_seconds,rep.occurrence_id,o.slot_id,s.slot_date,s.start_time,s.end_time
      FROM teams_attendance_records ar JOIN teams_attendance_reports rep ON rep.id=ar.report_row_id
      LEFT JOIN teams_occurrences o ON o.id=rep.occurrence_id LEFT JOIN slots s ON s.id=o.slot_id
      JOIN teams_action_rooms room ON room.id=rep.action_room_id
      WHERE room.action_id=:a AND ar.participant_id IS NULL ORDER BY s.slot_date,s.start_time,ar.display_name,ar.id""",{'a':action_id})

def confirm_teams_attendance_identity(engine, attendance_record_id, participant_id, actor='admin'):
    rec=one(engine,"""SELECT ar.*,room.action_id FROM teams_attendance_records ar JOIN teams_attendance_reports rep ON rep.id=ar.report_row_id JOIN teams_action_rooms room ON room.id=rep.action_room_id WHERE ar.id=:i""",{'i':attendance_record_id})
    if not rec: raise ValueError('Présence Teams introuvable.')
    p=one(engine,'SELECT * FROM participants WHERE id=:p AND action_id=:a',{'p':participant_id,'a':rec['action_id']})
    if not p: raise ValueError('Participant incompatible avec cette action.')
    execute(engine,'UPDATE teams_attendance_records SET participant_id=:p WHERE id=:i',{'p':participant_id,'i':attendance_record_id})
    audit(engine,'TEAMS_ATTENDANCE_IDENTITY_CONFIRMED',rec['action_id'],actor,'teams_attendance_record',attendance_record_id,{'participant_id':participant_id,'teams_email':rec.get('email')})
    return True

# ---- V3 I9-D: Hub Clarte360 - catalogue & prescriptions -------------------

PRESCRIPTION_STATUSES = ('A_FAIRE','ENVOYE','CONSULTE','EN_COURS','TERMINE','A_REVOIR_EN_SEANCE','REVU_EN_SEANCE','ANNULE')


def _json_load(value, default):
    if value in (None, ''):
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _tool_registry_path():
    return ROOT/'config'/'tool_registry.json'


def load_tool_registry():
    """Load the deployment-aware Clarte360 tool registry.

    The registry is data, not executable code. Adding a future Hub-ready application no
    longer requires changing the I9 core: its audited deployment contract is added here.
    """
    path=_tool_registry_path()
    if not path.is_file():
        return []
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise ValueError('Registre des outils Clarté360 invalide.') from exc
    rows=data.get('tools',[]) if isinstance(data,dict) else []
    if not isinstance(rows,list):
        raise ValueError('Registre des outils Clarté360 invalide.')
    return [x for x in rows if isinstance(x,dict) and x.get('tool_code') and x.get('name')]


def seed_tool_catalog(engine, actor='system'):
    """Synchronise le catalogue avec le registre versionné Clarté360.

    Les outils non encore déployés peuvent être pré-enregistrés inactifs. Le registre ne
    contient aucun secret. URL, identité Hub et état de déploiement sont explicites.
    """
    now=utcnow_iso(); defaults=load_tool_registry()
    for d in defaults:
        active=1 if d.get('active',False) else 0
        pa=1 if d.get('prescription_allowed',False) else 0
        execute(engine,"""INSERT INTO tool_catalog(tool_code,name,category,base_url,tool_version,active,allowed_publics_json,
          compatible_prestations_json,prescription_allowed,launch_type,access_validity_hours,connector_code,connector_status,metadata_json,created_at,updated_at)
          VALUES(:tool_code,:name,:category,:base_url,:tool_version,:active,:publics,:prestations,:pa,:launch,:hours,:connector,:status,:meta,:n,:n)
          ON CONFLICT(tool_code) DO UPDATE SET name=excluded.name,category=excluded.category,base_url=excluded.base_url,
          tool_version=excluded.tool_version,active=excluded.active,allowed_publics_json=excluded.allowed_publics_json,
          compatible_prestations_json=excluded.compatible_prestations_json,prescription_allowed=excluded.prescription_allowed,
          launch_type=excluded.launch_type,access_validity_hours=excluded.access_validity_hours,connector_code=excluded.connector_code,
          connector_status=CASE WHEN tool_catalog.connector_status='CONNECTED' THEN tool_catalog.connector_status ELSE excluded.connector_status END,
          metadata_json=excluded.metadata_json,updated_at=excluded.updated_at""",
          {'tool_code':str(d['tool_code']).strip().upper(),'name':d['name'],'category':d.get('category','OUTIL'),'base_url':d.get('base_url'),
           'tool_version':d.get('tool_version'),'active':active,'publics':json.dumps(d.get('allowed_publics') or ['BENEFICIAIRE'],ensure_ascii=False),
           'prestations':json.dumps(d.get('compatible_prestations') or [],ensure_ascii=False),'pa':pa,'launch':d.get('launch_type','HUB_REDIRECT'),
           'hours':int(d.get('access_validity_hours') or 168),'connector':d.get('connector_code'),'status':d.get('connector_status','NOT_CONFIGURED'),
           'meta':json.dumps(d.get('metadata') or {},ensure_ascii=False),'n':now})
    return len(defaults)


def list_tool_catalog(engine, active_only=True, prescription_only=False, prestation_type=None, public='BENEFICIAIRE'):
    rows=q(engine,"SELECT * FROM tool_catalog ORDER BY category,name,tool_code")
    out=[]
    p=(prestation_type or '').upper().replace(' ','_')
    for row in rows:
        if active_only and not row.get('active'): continue
        if prescription_only and not row.get('prescription_allowed'): continue
        publics=_json_load(row.get('allowed_publics_json'),[])
        if public and publics and public.upper() not in [str(x).upper() for x in publics]: continue
        comps=_json_load(row.get('compatible_prestations_json'),[])
        if p and comps and p not in [str(x).upper() for x in comps]: continue
        row['allowed_publics']=publics; row['compatible_prestations']=comps
        out.append(row)
    return out


def upsert_tool_catalog(engine, data, actor='admin'):
    code=(data.get('tool_code') or '').strip().upper()
    name=(data.get('name') or '').strip()
    if not code or not name: raise ValueError('Code outil et nom obligatoires.')
    launch=(data.get('launch_type') or 'HUB_REDIRECT').strip().upper()
    if launch not in ('HUB_REDIRECT','EXTERNAL_SIGNED','INTERNAL'):
        raise ValueError('Type de lancement non reconnu.')
    now=utcnow_iso()
    existing=one(engine,'SELECT * FROM tool_catalog WHERE tool_code=:c',{'c':code})
    payload={
        'c':code,'n':name,'cat':(data.get('category') or 'OUTIL').strip().upper(),'url':(data.get('base_url') or '').strip() or None,
        'v':(data.get('tool_version') or '').strip() or None,'a':1 if data.get('active',True) else 0,
        'pub':json.dumps(data.get('allowed_publics') or ['BENEFICIAIRE'],ensure_ascii=False),
        'comp':json.dumps(data.get('compatible_prestations') if 'compatible_prestations' in data else _json_load((existing or {}).get('compatible_prestations_json'),[]),ensure_ascii=False),'pa':1 if data.get('prescription_allowed',True) else 0,
        'lt':launch,'iv':int(data.get('access_validity_hours') or (existing or {}).get('access_validity_hours') or 168),
        'rgpd':json.dumps(data.get('rgpd_rules') if 'rgpd_rules' in data else _json_load((existing or {}).get('rgpd_rules_json'),{}),ensure_ascii=False),
        'cc':((data.get('connector_code') if 'connector_code' in data else (existing or {}).get('connector_code')) or '').strip() or None,
        'cs':((data.get('connector_status') if 'connector_status' in data else (existing or {}).get('connector_status')) or 'NOT_CONFIGURED').strip().upper(),
        'meta':json.dumps(data.get('metadata') if 'metadata' in data else _json_load((existing or {}).get('metadata_json'),{}),ensure_ascii=False),'now':now
    }
    execute(engine,"""INSERT INTO tool_catalog(tool_code,name,category,base_url,tool_version,active,allowed_publics_json,compatible_prestations_json,
      prescription_allowed,launch_type,access_validity_hours,rgpd_rules_json,connector_code,connector_status,metadata_json,created_at,updated_at)
      VALUES(:c,:n,:cat,:url,:v,:a,:pub,:comp,:pa,:lt,:iv,:rgpd,:cc,:cs,:meta,:now,:now)
      ON CONFLICT(tool_code) DO UPDATE SET name=excluded.name,category=excluded.category,base_url=excluded.base_url,tool_version=excluded.tool_version,
      active=excluded.active,allowed_publics_json=excluded.allowed_publics_json,compatible_prestations_json=excluded.compatible_prestations_json,
      prescription_allowed=excluded.prescription_allowed,launch_type=excluded.launch_type,access_validity_hours=excluded.access_validity_hours,
      rgpd_rules_json=excluded.rgpd_rules_json,connector_code=excluded.connector_code,connector_status=excluded.connector_status,
      metadata_json=excluded.metadata_json,updated_at=excluded.updated_at""",payload)
    row=one(engine,'SELECT * FROM tool_catalog WHERE tool_code=:c',{'c':code})
    audit(engine,'TOOL_CATALOG_UPDATED' if existing else 'TOOL_CATALOG_CREATED',actor=actor,entity_type='tool_catalog',entity_id=row['id'],details={'tool_code':code})
    return row


def trainer_can_prescribe_tools(engine, trainer_id, action_id):
    row=one(engine,"SELECT can_prescribe_tools FROM action_trainers WHERE action_id=:a AND trainer_id=:t AND active=1",{'a':action_id,'t':trainer_id})
    return bool(row and row.get('can_prescribe_tools'))


def set_action_trainer_prescription_permission(engine, action_id, trainer_id, allowed, actor='admin'):
    row=one(engine,'SELECT * FROM action_trainers WHERE action_id=:a AND trainer_id=:t AND active=1',{'a':action_id,'t':trainer_id})
    if not row: return False,"L'intervenant n'est pas affecté à cette action."
    execute(engine,'UPDATE action_trainers SET can_prescribe_tools=:v,updated_at=:u WHERE id=:i',{'v':1 if allowed else 0,'u':utcnow_iso(),'i':row['id']})
    audit(engine,'TRAINER_TOOL_PRESCRIPTION_PERMISSION_CHANGED',action_id,actor,'trainer',trainer_id,{'allowed':bool(allowed)})
    return True,''


def _prescription_public_id():
    import secrets
    return 'PRX-'+secrets.token_hex(8).upper()


def create_tool_prescription(engine, tool_code, beneficiary_id, action_id, participant_id=None, *, prescriber_type='ADMIN', prescriber_id=None,
                             prescriber_role='ADMINISTRATEUR', due_at=None, expires_at=None, metadata=None, actor='system'):
    tool=one(engine,'SELECT * FROM tool_catalog WHERE tool_code=:c AND active=1 AND prescription_allowed=1',{'c':(tool_code or '').upper()})
    if not tool: raise ValueError('Outil indisponible ou non prescriptible.')
    ben=one(engine,'SELECT * FROM beneficiaries WHERE id=:b AND active=1',{'b':beneficiary_id})
    if not ben: raise ValueError('Bénéficiaire introuvable.')
    action=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':action_id})
    if not action: raise ValueError('Action introuvable.')
    if participant_id:
        linked=one(engine,'SELECT id FROM participants WHERE id=:p AND action_id=:a AND beneficiary_id=:b AND active=1',{'p':participant_id,'a':action_id,'b':beneficiary_id})
        if not linked: raise ValueError("Le participant n'est pas rattaché à ce bénéficiaire dans cette action.")
    else:
        linked=one(engine,'SELECT id FROM participants WHERE action_id=:a AND beneficiary_id=:b AND active=1 ORDER BY id LIMIT 1',{'a':action_id,'b':beneficiary_id})
        participant_id=(linked or {}).get('id')
        if not participant_id: raise ValueError("Ce bénéficiaire n'est pas rattaché à cette action.")
    # Compatibility is enforced by the generic catalogue contract.
    comps=_json_load(tool.get('compatible_prestations_json'),[])
    prestation=(action.get('prestation_type') or action.get('nature') or '').upper().replace(' ','_')
    if comps and prestation not in [str(x).upper() for x in comps]:
        raise ValueError('Cet outil n’est pas déclaré compatible avec cette prestation.')
    now=utcnow_iso()
    if not expires_at:
        expires_at=(datetime.now(ZoneInfo('UTC'))+timedelta(hours=int(tool.get('access_validity_hours') or 168))).isoformat()
    pid=_prescription_public_id()
    execute(engine,"""INSERT INTO tool_prescriptions(prescription_id,tool_id,tool_code,tool_version,beneficiary_id,action_id,participant_id,
      prescriber_type,prescriber_id,prescriber_role,created_at,due_at,expires_at,status,result_refs_json,metadata_json,updated_at)
      VALUES(:pid,:tid,:tc,:tv,:b,:a,:p,:pt,:pi,:pr,:n,:due,:exp,'A_FAIRE','[]',:m,:n)""",
      {'pid':pid,'tid':tool['id'],'tc':tool['tool_code'],'tv':tool.get('tool_version'),'b':beneficiary_id,'a':action_id,'p':participant_id,
       'pt':prescriber_type,'pi':str(prescriber_id) if prescriber_id is not None else None,'pr':prescriber_role,'n':now,'due':due_at,'exp':expires_at,
       'm':json.dumps(metadata or {},ensure_ascii=False)})
    execute(engine,"""INSERT INTO prescription_events(prescription_id,event_type,new_status,actor,details_json,created_at)
      VALUES(:p,'CREATED','A_FAIRE',:by,:d,:n)""",{'p':pid,'by':actor,'d':json.dumps({'tool_code':tool['tool_code']},ensure_ascii=False),'n':now})
    audit(engine,'TOOL_PRESCRIPTION_CREATED',action_id,actor,'tool_prescription',None,{'prescription_id':pid,'tool_code':tool['tool_code'],'beneficiary_id':beneficiary_id})
    return one(engine,'SELECT * FROM tool_prescriptions WHERE prescription_id=:p',{'p':pid})


def list_tool_prescriptions(engine, *, beneficiary_id=None, action_id=None, trainer_id=None, include_cancelled=True):
    wh=[]; params={}
    if beneficiary_id is not None: wh.append('tp.beneficiary_id=:b');params['b']=beneficiary_id
    if action_id is not None: wh.append('tp.action_id=:a');params['a']=action_id
    if trainer_id is not None:
        wh.append("EXISTS (SELECT 1 FROM action_trainers at WHERE at.action_id=tp.action_id AND at.trainer_id=:t AND at.active=1)");params['t']=trainer_id
    if not include_cancelled: wh.append("tp.status<>'ANNULE'")
    where=('WHERE '+' AND '.join(wh)) if wh else ''
    return q(engine,f"""SELECT tp.*,tc.name tool_name,tc.category tool_category,tc.base_url,tc.launch_type,tc.connector_status,
      b.public_id beneficiary_public_id,b.first_name beneficiary_first_name,b.last_name beneficiary_last_name,a.action_no,a.title action_title
      FROM tool_prescriptions tp JOIN tool_catalog tc ON tc.id=tp.tool_id JOIN beneficiaries b ON b.id=tp.beneficiary_id
      JOIN actions a ON a.id=tp.action_id {where} ORDER BY tp.created_at DESC,tp.id DESC""",params)


def update_tool_prescription_status(engine, prescription_id, new_status, actor='system', details=None, event_id=None):
    status=(new_status or '').upper()
    if status not in PRESCRIPTION_STATUSES: raise ValueError('Statut de prescription inconnu.')
    row=one(engine,'SELECT * FROM tool_prescriptions WHERE prescription_id=:p',{'p':prescription_id})
    if not row: raise ValueError('Prescription introuvable.')
    if event_id and one(engine,'SELECT id FROM prescription_events WHERE event_id=:e',{'e':event_id}): return row
    now=utcnow_iso(); fields={'CONSULTE':'first_viewed_at','EN_COURS':'started_at','TERMINE':'completed_at','REVU_EN_SEANCE':'reviewed_at','ANNULE':'cancelled_at'}
    extra=''; params={'s':status,'u':now,'p':prescription_id}
    if status in fields: extra=f",{fields[status]}=COALESCE({fields[status]},:u)"
    execute(engine,f'UPDATE tool_prescriptions SET status=:s,updated_at=:u{extra} WHERE prescription_id=:p',params)
    execute(engine,"""INSERT INTO prescription_events(prescription_id,event_type,old_status,new_status,actor,details_json,event_id,created_at)
      VALUES(:p,'STATUS_CHANGED',:o,:n,:a,:d,:e,:c)""",{'p':prescription_id,'o':row.get('status'),'n':status,'a':actor,
      'd':json.dumps(details or {},ensure_ascii=False),'e':event_id,'c':now})
    audit(engine,'TOOL_PRESCRIPTION_STATUS_CHANGED',row.get('action_id'),actor,'tool_prescription',None,{'prescription_id':prescription_id,'old':row.get('status'),'new':status})
    return one(engine,'SELECT * FROM tool_prescriptions WHERE prescription_id=:p',{'p':prescription_id})


def create_prescription_launch_token(engine, prescription_id, actor='beneficiary', valid_minutes=15):
    import secrets, hashlib
    row=one(engine,"""SELECT tp.*,tc.active tool_active,tc.prescription_allowed,tc.base_url,tc.launch_type,tc.connector_status
      FROM tool_prescriptions tp JOIN tool_catalog tc ON tc.id=tp.tool_id WHERE tp.prescription_id=:p""",{'p':prescription_id})
    if not row or row.get('status')=='ANNULE': raise ValueError('Prescription indisponible.')
    if not row.get('tool_active') or not row.get('prescription_allowed'): raise ValueError('Outil temporairement indisponible.')
    now=datetime.now(ZoneInfo('UTC'))
    if row.get('expires_at') and datetime.fromisoformat(row['expires_at']) < now: raise ValueError('Accès à cet outil expiré.')
    token=secrets.token_urlsafe(32); digest=hashlib.sha256(token.encode()).hexdigest(); exp=(now+timedelta(minutes=max(1,min(int(valid_minutes),60)))).isoformat()
    execute(engine,'INSERT INTO prescription_access_tokens(prescription_id,token_hash,created_at,expires_at,created_by) VALUES(:p,:h,:n,:e,:b)',
      {'p':prescription_id,'h':digest,'n':utcnow_iso(),'e':exp,'b':actor})
    return token


def resolve_prescription_launch_token(engine, token, actor='beneficiary'):
    import hashlib
    if not token: return None
    digest=hashlib.sha256(token.encode()).hexdigest()
    row=one(engine,"""SELECT pat.id token_id,pat.expires_at token_expires_at,pat.used_at,pat.revoked_at,tp.*,tc.name tool_name,tc.base_url,tc.launch_type,tc.connector_status
      FROM prescription_access_tokens pat JOIN tool_prescriptions tp ON tp.prescription_id=pat.prescription_id
      JOIN tool_catalog tc ON tc.id=tp.tool_id WHERE pat.token_hash=:h""",{'h':digest})
    if not row or row.get('revoked_at') or row.get('used_at'): return None
    now=datetime.now(ZoneInfo('UTC'))
    try:
        if datetime.fromisoformat(row['token_expires_at']) < now: return None
        if row.get('expires_at') and datetime.fromisoformat(row['expires_at']) < now: return None
    except Exception: return None
    execute(engine,'UPDATE prescription_access_tokens SET used_at=:u WHERE id=:i',{'u':utcnow_iso(),'i':row['token_id']})
    if row.get('status') in ('A_FAIRE','ENVOYE'):
        update_tool_prescription_status(engine,row['prescription_id'],'CONSULTE',actor,{'via':'hub_launch'})
        row['status']='CONSULTE'
    return row


def prescription_events(engine, prescription_id):
    return q(engine,'SELECT * FROM prescription_events WHERE prescription_id=:p ORDER BY created_at,id',{'p':prescription_id})

# ---- I9-H2.2: lancement Hub générique piloté par registre -----------------

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def _hub_role(row):
    raw=str(row.get('prescriber_role') or row.get('prescriber_type') or '').upper()
    return 'admin' if 'ADMIN' in raw else 'intervenant'


def _append_query_param(base_url, key, value):
    parts=urlsplit(str(base_url or ''))
    if parts.scheme not in ('http','https') or not parts.netloc:
        raise ValueError('URL de lancement de l’outil invalide.')
    query=dict(parse_qsl(parts.query,keep_blank_values=True)); query[str(key)]=str(value)
    return urlunsplit((parts.scheme,parts.netloc,parts.path,urlencode(query),parts.fragment))


def build_generic_tool_launch(engine, prescription_id, signing_key, valid_seconds=900):
    """Build a signed launch URL from tool_catalog.metadata_json.

    Supported profiles intentionally cover both contracts already prepared by Clarté360:
    - payload_b64_hmac: HMAC over the base64url payload string (Boussole family);
    - raw_json_hmac: HMAC over raw canonical JSON (older VPS-HUB-READY family).
    New tools are added through config/tool_registry.json, not by changing this function.
    """
    if not signing_key or len(str(signing_key).strip()) < 24:
        raise ValueError('Secret Hub Clarté360 non configuré.')
    row=one(engine,"""SELECT tp.*,tc.base_url,tc.launch_type,tc.metadata_json,tc.active tool_active,tc.prescription_allowed
      FROM tool_prescriptions tp JOIN tool_catalog tc ON tc.id=tp.tool_id WHERE tp.prescription_id=:p""",{'p':prescription_id})
    if not row or row.get('status')=='ANNULE': raise ValueError('Prescription indisponible.')
    if not row.get('tool_active') or not row.get('prescription_allowed'): raise ValueError('Outil temporairement indisponible.')
    meta=_json_load(row.get('metadata_json'),{}); profile=(meta or {}).get('hub_profile') or {}
    if not profile: raise ValueError('Contrat Hub de cet outil non configuré.')
    tool_id=profile.get('tool_id'); scopes=profile.get('scopes') or []
    if not tool_id or not isinstance(scopes,list): raise ValueError('Contrat Hub incomplet.')
    now=int(time.time()); ttl=max(60,min(int(valid_seconds or 900),7*86400))
    payload={
        'tool_id':tool_id,'hub_source':profile.get('hub_source','GESTION_ACTIONS_I9'),
        'beneficiary_id':str(row['beneficiary_id']),'action_id':str(row['action_id']),
        'participant_id':str(row.get('participant_id') or ''),'prescription_id':str(row['prescription_id']),
        'scopes':scopes,
    }
    role_field=profile.get('role_field','role'); payload[role_field]=_hub_role(row)
    time_model=profile.get('time_model','iat_exp')
    if time_model=='expires_at':
        payload['expires_at']=now+ttl
    else:
        payload['iat']=now; payload['exp']=now+ttl
    if profile.get('return_mode'):
        payload['return_mode']=profile['return_mode']
    # Prefill is optional and contains no secret; apps may ignore it.
    ben=one(engine,'SELECT first_name,last_name,current_email email FROM beneficiaries WHERE id=:b',{'b':row['beneficiary_id']}) or {}
    payload['beneficiary']={'prenom':ben.get('first_name') or '', 'nom':ben.get('last_name') or '', 'email':ben.get('email') or ''}
    raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    mode=profile.get('signature_mode','payload_b64_hmac')
    if mode=='payload_b64_hmac':
        p=_b64url(raw); sig=hmac.new(str(signing_key).encode(),p.encode(),hashlib.sha256).digest(); token=p+'.'+_b64url(sig)
    elif mode=='raw_json_hmac':
        p=_b64url(raw); sig=hmac.new(str(signing_key).encode(),raw,hashlib.sha256).digest(); token=p+'.'+_b64url(sig)
    else:
        raise ValueError('Mode de signature Hub non supporté.')
    return _append_query_param(row.get('base_url'),profile.get('query_param','hub_token'),token)


# ---- V3 I9-E: adaptateur PIP RC5 ------------------------------------------
def pip_connector_configured(signing_key):
    return bool(signing_key and len(str(signing_key).strip()) >= 24)


def build_pip_prescription_launch(engine, prescription_id, signing_key, valid_seconds=900):
    """Return a beneficiary-safe PIP URL carrying only the signed launch token."""
    from pip_connector import build_pip_launch_token, build_pip_launch_url
    row=one(engine,"""SELECT tp.*,tc.base_url,tc.launch_type,tc.connector_code,tc.connector_status
      FROM tool_prescriptions tp JOIN tool_catalog tc ON tc.id=tp.tool_id WHERE tp.prescription_id=:p""",{'p':prescription_id})
    if not row or row.get('tool_code')!='PIP_RIASEC_ONET': raise ValueError('Prescription PIP introuvable.')
    if row.get('status')=='ANNULE': raise ValueError('Prescription PIP annulée.')
    now=datetime.now(ZoneInfo('UTC'))
    if row.get('expires_at'):
        try:
            exp=datetime.fromisoformat(row['expires_at'])
            if exp.tzinfo is None: exp=exp.replace(tzinfo=ZoneInfo('UTC'))
            if exp < now: raise ValueError('Accès PIP expiré.')
        except ValueError: raise
        except Exception: pass
    tok=build_pip_launch_token(beneficiary_id=row['beneficiary_id'],action_id=row['action_id'],participant_id=row.get('participant_id'),
      prescription_id=row['prescription_id'],signing_key=signing_key,rights=['PIP_RIASEC','ONET60'],valid_seconds=valid_seconds)
    return build_pip_launch_url(row.get('base_url'),tok)


def _connector_cursor(engine, code):
    return one(engine,'SELECT * FROM connector_cursors WHERE connector_code=:c',{'c':code})


def _save_connector_cursor(engine, code, source_ref, offset, *, last_event_at=None, last_error=None):
    now=utcnow_iso()
    execute(engine,"""INSERT INTO connector_cursors(connector_code,source_ref,byte_offset,last_event_at,last_error,updated_at)
      VALUES(:c,:s,:o,:e,:er,:u) ON CONFLICT(connector_code) DO UPDATE SET source_ref=excluded.source_ref,
      byte_offset=excluded.byte_offset,last_event_at=COALESCE(excluded.last_event_at,connector_cursors.last_event_at),last_error=excluded.last_error,updated_at=excluded.updated_at""",
      {'c':code,'s':str(source_ref or ''),'o':int(offset or 0),'e':last_event_at,'er':last_error,'u':now})


def consume_pip_outbox(engine, outbox_path, limit=500, actor='worker'):
    """Consume the PIP RC5 durable JSONL outbox idempotently.

    The PIP remains owner of its snapshots/results. Gestion des Actions only consumes the
    minimal connector events currently emitted by RC5 (CONSULTE/EN_COURS/TERMINE + refs).
    """
    from pip_connector import read_outbox_from_offset, event_identity, PipConnectorError
    code='PIP_RC5'; cur=_connector_cursor(engine,code) or {}; start=int(cur.get('byte_offset') or 0)
    try:
        rows,next_offset=read_outbox_from_offset(outbox_path,start,limit)
    except Exception as exc:
        _save_connector_cursor(engine,code,outbox_path,start,last_error=str(exc)[:500])
        audit(engine,'PIP_OUTBOX_READ_FAILED',actor=actor,entity_type='connector',details={'error':str(exc)[:500]})
        return {'processed':0,'ignored':0,'errors':1,'offset':start}
    processed=ignored=errors=0; committed=start; last_event_at=None
    for after,raw,event in rows:
        payload=event.get('payload') or {}; event_id=event_identity(raw)
        try:
            pr=one(engine,"SELECT * FROM tool_prescriptions WHERE prescription_id=:p AND tool_code='PIP_RIASEC_ONET'",{'p':payload.get('prescription_id')})
            if not pr:
                raise ValueError('Prescription PIP inconnue dans le Hub.')
            # Strong anti-crossing checks: every technical identifier emitted by PIP must
            # agree with the prescription stored by the Hub.
            if str(pr.get('beneficiary_id')) != str(payload.get('beneficiary_id')) or str(pr.get('action_id')) != str(payload.get('action_id')):
                raise ValueError('Identifiants PIP incohérents avec la prescription.')
            if payload.get('participant_id') is not None and str(pr.get('participant_id')) != str(payload.get('participant_id')):
                raise ValueError('Participant PIP incohérent avec la prescription.')
            if one(engine,'SELECT id FROM prescription_events WHERE event_id=:e',{'e':event_id}):
                ignored+=1; committed=after; continue
            details={'source':'PIP_RC5','timestamp':event.get('timestamp'),'passation_id':payload.get('passation_id'),'app_version':payload.get('app_version')}
            update_tool_prescription_status(engine,pr['prescription_id'],event['event_type'],actor,details,event_id=event_id)
            # Persist only references actually emitted by RC5; no score/result is invented.
            refs=_json_load(pr.get('result_refs_json'),[])
            ref={'source':'PIP_RC5','passation_id':payload.get('passation_id'),'app_version':payload.get('app_version')}
            if ref not in refs and (ref['passation_id'] or ref['app_version']):
                refs.append(ref)
                execute(engine,'UPDATE tool_prescriptions SET result_refs_json=:r,updated_at=:u WHERE prescription_id=:p',{'r':json.dumps(refs,ensure_ascii=False),'u':utcnow_iso(),'p':pr['prescription_id']})
            processed+=1; committed=after; last_event_at=event.get('timestamp') or utcnow_iso()
        except Exception as exc:
            # Do not advance past a bad/crossed event: administrator can correct then retry.
            errors+=1
            _save_connector_cursor(engine,code,outbox_path,committed,last_event_at=last_event_at,last_error=str(exc)[:500])
            audit(engine,'PIP_OUTBOX_EVENT_REJECTED',actor=actor,entity_type='connector',details={'event_id':event_id,'error':str(exc)[:500]})
            return {'processed':processed,'ignored':ignored,'errors':errors,'offset':committed}
    _save_connector_cursor(engine,code,outbox_path,next_offset,last_event_at=last_event_at,last_error=None)
    if processed:
        audit(engine,'PIP_OUTBOX_CONSUMED',actor=actor,entity_type='connector',details={'processed':processed,'ignored':ignored,'offset':next_offset})
    return {'processed':processed,'ignored':ignored,'errors':errors,'offset':next_offset}

def refresh_pip_connector_runtime_status(engine, signing_key=None, outbox_path=None, actor='system'):
    """Expose configuration readiness without ever persisting a secret value."""
    key_ok=pip_connector_configured(signing_key)
    outbox_ok=bool(str(outbox_path or '').strip())
    status='CONNECTED' if key_ok and outbox_ok else ('LAUNCH_ONLY' if key_ok else 'NOT_CONFIGURED')
    row=one(engine,"SELECT id,connector_status FROM tool_catalog WHERE tool_code='PIP_RIASEC_ONET'")
    if row and row.get('connector_status')!=status:
        execute(engine,"UPDATE tool_catalog SET connector_status=:s,updated_at=:u WHERE id=:i",{'s':status,'u':utcnow_iso(),'i':row['id']})
        audit(engine,'PIP_CONNECTOR_STATUS_CHANGED',actor=actor,entity_type='tool_catalog',entity_id=row['id'],details={'status':status})
    return status

# I9-F — Espace Études PIP/O*NET. Les fichiers sources sont déjà pseudonymisés par le PIP RC5.
_STUDY_IDENTITY_KEYS={'identity','public_identity','first_name','last_name','name','email','phone','telephone','participant_id','public_participant_id','beneficiary_id'}

def _study_safe(value):
    if isinstance(value,dict):
        return {k:_study_safe(v) for k,v in value.items() if str(k).lower() not in _STUDY_IDENTITY_KEYS}
    if isinstance(value,list): return [_study_safe(v) for v in value]
    return value

def load_pip_study_records(study_dir):
    root=Path(study_dir).expanduser()
    if not root.is_dir(): return []
    rows=[]
    for path in sorted(root.glob('*.json')):
        try:
            raw=json.loads(path.read_text(encoding='utf-8'))
            if raw.get('schema')!='clarte360.pip.public-study.v1' or not raw.get('study_id'): continue
            safe=_study_safe(raw)
            safe['_source_file']=path.name
            rows.append(safe)
        except Exception:
            continue
    return rows

def _study_completed(r):
    ps=r.get('pip_state') or {}
    if ps.get('completed') is True: return True
    return bool(r.get('completed_at'))

def study_record_status(r):
    if _study_completed(r): return 'TERMINE'
    ps=r.get('pip_state') or {}; answers=ps.get('answers') or {}
    return 'COMMENCE' if answers else 'ABANDONNE'

def filter_study_records(records, filters=None):
    f=filters or {}; out=[]
    for r in records:
        completed=str(r.get('completed_at') or '')
        if f.get('date_from') and completed and completed[:10] < str(f['date_from']): continue
        if f.get('date_to') and completed and completed[:10] > str(f['date_to']): continue
        if f.get('journey') and r.get('journey')!=f['journey']: continue
        if f.get('timing') and r.get('onet_selected_timing')!=f['timing']: continue
        if f.get('bank_version') and r.get('pip_bank_version')!=f['bank_version']: continue
        if f.get('status') and study_record_status(r)!=f['status']: continue
        if f.get('consent') is not None and bool(r.get('study_consent')) != bool(f['consent']): continue
        out.append(r)
    return out

def study_summary(records):
    return {
      'total':len(records),'commencees':sum(study_record_status(r)=='COMMENCE' for r in records),
      'terminees':sum(study_record_status(r)=='TERMINE' for r in records),'abandons':sum(study_record_status(r)=='ABANDONNE' for r in records),
      'pip_seul':sum(r.get('journey')=='PIP_SEUL' for r in records),'pip_onet':sum(r.get('journey')=='PIP_PUIS_ONET60' for r in records),
      'pre_pip':sum(r.get('onet_selected_timing')=='PRE_PIP' for r in records),'post_pip':sum(r.get('onet_selected_timing')=='POST_PIP_RESULTS' for r in records),
      'consentements':sum(bool(r.get('study_consent')) for r in records),
    }

def study_item_quality(records):
    values={}
    for r in records:
        if not r.get('study_consent'): continue
        for item,val in ((r.get('pip_answers') or {}).items()):
            try: x=float(val)
            except (TypeError,ValueError): continue
            if 1 <= x <= 5: values.setdefault(str(item),[]).append(x)
    result=[]; total=max(1,sum(bool(r.get('study_consent')) for r in records))
    for item,xs in sorted(values.items()):
        n=len(xs); mean=sum(xs)/n; var=sum((x-mean)**2 for x in xs)/n
        dist={str(i):sum(x==i for x in xs) for i in range(1,6)}
        # Indicateur descriptif uniquement : part des réponses dans la modalité la plus fréquente.
        consensus=max(dist.values())/n if n else 0
        result.append({'item_id':item,'n':n,'response_rate':n/total,'mean':mean,'dispersion':var**0.5,'consensus':consensus,**{f'n_{i}':dist[str(i)] for i in range(1,6)}})
    return result

def study_onet_pairs(records):
    pairs=[]
    for r in records:
        if not r.get('study_consent') or r.get('journey')!='PIP_PUIS_ONET60': continue
        pip=r.get('pip_scoring') or {}; onet=r.get('onet_state') or {}
        if not pip or not onet: continue
        pairs.append({'study_id':r.get('study_id'),'timing':r.get('onet_selected_timing'),'pip_scoring':_study_safe(pip),'onet_state':_study_safe(onet)})
    return pairs

def _flatten_study_record(r):
    return {
      'study_id':r.get('study_id'),'journey':r.get('journey'),'onet_selected_timing':r.get('onet_selected_timing'),
      'pip_bank_version':r.get('pip_bank_version'),'study_consent':bool(r.get('study_consent')),
      'status':study_record_status(r),'completed_at':r.get('completed_at'),
      'pip_answers_json':json.dumps(r.get('pip_answers') or {},ensure_ascii=False,sort_keys=True),
      'pip_scoring_json':json.dumps(r.get('pip_scoring') or {},ensure_ascii=False,sort_keys=True),
      'onet_state_json':json.dumps(r.get('onet_state') or {},ensure_ascii=False,sort_keys=True),
      'feeling_json':json.dumps(r.get('feeling') or {},ensure_ascii=False,sort_keys=True),
    }

def export_study_csv(engine, records, actor, purpose, filters=None):
    rows=[_flatten_study_record(_study_safe(r)) for r in records if r.get('study_consent')]
    buf=io.StringIO(); fields=list(rows[0]) if rows else ['study_id','journey','onet_selected_timing','pip_bank_version','study_consent','status','completed_at','pip_answers_json','pip_scoring_json','onet_state_json','feeling_json']
    w=csv.DictWriter(buf,fieldnames=fields);w.writeheader();w.writerows(rows)
    execute(engine,"INSERT INTO study_export_events(actor,purpose,format,filters_json,schema_version,record_count,exported_at) VALUES(:a,:p,'CSV',:f,'clarte360.study-export.v1',:n,:d)",{'a':actor,'p':purpose,'f':json.dumps(filters or {},ensure_ascii=False,default=str),'n':len(rows),'d':utcnow_iso()})
    audit(engine,'STUDY_EXPORT_CREATED',actor=actor,entity_type='study_export',details={'format':'CSV','record_count':len(rows),'purpose':purpose,'schema':'clarte360.study-export.v1'})
    return buf.getvalue().encode('utf-8-sig')

def export_study_xlsx(engine, records, actor, purpose, filters=None):
    import pandas as pd
    rows=[_flatten_study_record(_study_safe(r)) for r in records if r.get('study_consent')]
    cols=['study_id','journey','onet_selected_timing','pip_bank_version','study_consent','status','completed_at','pip_answers_json','pip_scoring_json','onet_state_json','feeling_json']
    buf=io.BytesIO()
    with pd.ExcelWriter(buf,engine='openpyxl') as writer:
        pd.DataFrame(rows,columns=cols).to_excel(writer,index=False,sheet_name='ETUDE_PSEUDONYMISEE')
    execute(engine,"INSERT INTO study_export_events(actor,purpose,format,filters_json,schema_version,record_count,exported_at) VALUES(:a,:p,'XLSX',:f,'clarte360.study-export.v1',:n,:d)",{'a':actor,'p':purpose,'f':json.dumps(filters or {},ensure_ascii=False,default=str),'n':len(rows),'d':utcnow_iso()})
    audit(engine,'STUDY_EXPORT_CREATED',actor=actor,entity_type='study_export',details={'format':'XLSX','record_count':len(rows),'purpose':purpose,'schema':'clarte360.study-export.v1'})
    return buf.getvalue()


# --- I9-G : CRM léger + contrat d'intégration Contractualisation ---
CRM_STATUSES={'NOUVEAU','A_CONTACTER','CONTACTE','CONVERTI','SANS_SUITE'}
CONTRACTUALIZATION_STATUSES={'A_PREPARER','EN_COURS','GENEREE','SIGNEE','ANNULEE'}

def _crm_public_id():
    return 'CRM-'+new_token(8).upper()

def create_crm_contact(engine, first_name, last_name, email, *, phone=None, job_title=None, company=None, interests=None,
                       source='MANUEL', source_ref=None, email_verified_at=None, research_consent_at=None,
                       marketing_consent=False, rgpd_notice_version=None, actor='admin'):
    vd=validate_crm_payload(first_name,last_name,email,phone,job_title,company)
    fn,ln,em=vd['first_name'],vd['last_name'],vd['email']; phone=vd['phone']; job_title=vd['job_title']; company=vd['company']
    now=utcnow_iso(); pid=_crm_public_id()
    execute(engine,'''INSERT INTO crm_contacts(public_id,source,source_ref,first_name,last_name,email,email_verified_at,phone,job_title,company,
      interests_json,research_consent_at,marketing_consent,marketing_consent_at,rgpd_notice_version,status,created_at,updated_at)
      VALUES(:p,:s,:sr,:f,:l,:e,:ev,:ph,:j,:c,:i,:rc,:mc,:mca,:rv,'NOUVEAU',:n,:n)''',
      {'p':pid,'s':source or 'MANUEL','sr':source_ref,'f':fn,'l':ln,'e':em,'ev':email_verified_at,'ph':phone,'j':job_title,'c':company,
       'i':json.dumps(interests or [],ensure_ascii=False),'rc':research_consent_at,'mc':1 if marketing_consent else 0,
       'mca':now if marketing_consent else None,'rv':rgpd_notice_version,'n':now})
    row=one(engine,'SELECT * FROM crm_contacts WHERE public_id=:p',{'p':pid})
    audit(engine,actor,'CRM_CONTACT_CREATE','crm_contact',row['id'],{'source':source,'marketing_consent':bool(marketing_consent)})
    execute(engine,"INSERT INTO crm_events(contact_id,event_type,actor,details_json,created_at) VALUES(:c,'CREATE',:a,:d,:n)",
            {'c':row['id'],'a':actor,'d':json.dumps({'source':source},ensure_ascii=False),'n':now})
    return row

def list_crm_contacts(engine, status=None):
    sql='SELECT c.*,b.public_id beneficiary_public_id FROM crm_contacts c LEFT JOIN beneficiaries b ON b.id=c.beneficiary_id'
    pa={}
    if status:
        sql+=' WHERE c.status=:s'; pa['s']=status
    sql+=' ORDER BY c.updated_at DESC,c.id DESC'
    return q(engine,sql,pa)

def update_crm_status(engine, contact_id, status, actor='admin'):
    st=str(status or '').upper()
    if st not in CRM_STATUSES:
        raise ValueError('Statut CRM invalide.')
    old=one(engine,'SELECT * FROM crm_contacts WHERE id=:i',{'i':contact_id})
    if not old:
        raise ValueError('Contact introuvable.')
    now=utcnow_iso()
    execute(engine,'UPDATE crm_contacts SET status=:s,updated_at=:n WHERE id=:i',{'s':st,'n':now,'i':contact_id})
    execute(engine,"INSERT INTO crm_events(contact_id,event_type,actor,details_json,created_at) VALUES(:c,'STATUS',:a,:d,:n)",
            {'c':contact_id,'a':actor,'d':json.dumps({'old':old['status'],'new':st},ensure_ascii=False),'n':now})
    audit(engine,actor,'CRM_STATUS','crm_contact',contact_id,{'old':old['status'],'new':st})

def set_crm_marketing_consent(engine, contact_id, consent, actor='admin', rgpd_notice_version=None):
    row=one(engine,'SELECT * FROM crm_contacts WHERE id=:i',{'i':contact_id})
    if not row:
        raise ValueError('Contact introuvable.')
    now=utcnow_iso(); yes=bool(consent)
    execute(engine,'''UPDATE crm_contacts SET marketing_consent=:m,marketing_consent_at=:ca,marketing_revoked_at=:rv,
      rgpd_notice_version=COALESCE(:ver,rgpd_notice_version),updated_at=:n WHERE id=:i''',
      {'m':1 if yes else 0,'ca':now if yes else row.get('marketing_consent_at'),'rv':None if yes else now,
       'ver':rgpd_notice_version,'n':now,'i':contact_id})
    execute(engine,"INSERT INTO crm_events(contact_id,event_type,actor,details_json,created_at) VALUES(:c,'MARKETING_CONSENT',:a,:d,:n)",
            {'c':contact_id,'a':actor,'d':json.dumps({'consent':yes,'rgpd_notice_version':rgpd_notice_version},ensure_ascii=False),'n':now})
    audit(engine,actor,'CRM_MARKETING_CONSENT','crm_contact',contact_id,{'consent':yes})

def convert_crm_contact_to_beneficiary(engine, contact_id, birth_date, actor='admin'):
    c=one(engine,'SELECT * FROM crm_contacts WHERE id=:i',{'i':contact_id})
    if not c:
        raise ValueError('Contact introuvable.')
    if c.get('beneficiary_id'):
        return one(engine,'SELECT * FROM beneficiaries WHERE id=:i',{'i':c['beneficiary_id']})
    bd=str(birth_date or '').strip()
    if not bd:
        raise ValueError('La date de naissance est requise pour contrôler les doublons avant conversion.')
    cand=find_beneficiary_candidates(engine,c['last_name'],c['first_name'],bd,limit=10)
    exact=[x for x in cand if str(x.get('birth_date') or '')==bd]
    if len(exact)>1:
        raise ValueError('Plusieurs bénéficiaires correspondent exactement : validation manuelle requise.')
    if exact:
        b=exact[0]
    else:
        bid=create_beneficiary(engine,c['last_name'],c['first_name'],bd,email=c.get('email'),phone=c.get('phone'),actor=actor)
        b=one(engine,'SELECT * FROM beneficiaries WHERE id=:i',{'i':bid})
    now=utcnow_iso()
    execute(engine,"UPDATE crm_contacts SET beneficiary_id=:b,status='CONVERTI',converted_at=:n,updated_at=:n WHERE id=:i",
            {'b':b['id'],'n':now,'i':contact_id})
    execute(engine,"INSERT INTO crm_events(contact_id,event_type,actor,details_json,created_at) VALUES(:c,'CONVERT',:a,:d,:n)",
            {'c':contact_id,'a':actor,'d':json.dumps({'beneficiary_id':b['id'],'beneficiary_public_id':b['public_id']},ensure_ascii=False),'n':now})
    audit(engine,actor,'CRM_CONVERT','crm_contact',contact_id,{'beneficiary_id':b['id']})
    return b

def build_contractualization_context(engine, action_id, beneficiary_id, participant_id=None, *, contract_type='A_DEFINIR', aps_ref=None, aps_payload=None):
    a=one(engine,'SELECT * FROM actions WHERE id=:i',{'i':action_id})
    b=one(engine,'SELECT * FROM beneficiaries WHERE id=:i',{'i':beneficiary_id})
    if not a or not b:
        raise ValueError('Action ou bénéficiaire introuvable.')
    if participant_id:
        part=one(engine,'SELECT * FROM participants WHERE id=:i AND action_id=:a',{'i':participant_id,'a':action_id})
        if not part or part.get('beneficiary_id')!=beneficiary_id:
            raise ValueError('Participant incohérent avec l’action ou le bénéficiaire.')
    slots=q(engine,"SELECT slot_date,start_time,end_time,status FROM slots WHERE action_id=:a AND status!='ANNULE' ORDER BY slot_date,start_time",{'a':action_id})
    identity={'beneficiary_id':b['public_id'],'first_name':b['first_name'],'last_name':b['last_name'],'birth_date':b['birth_date'],
              'birth_name':b.get('birth_name'),'email':b.get('current_email'),'phone':b.get('phone')}
    return {'format':'CLARTE360_CONTRACTUALISATION_CONTEXT_V1','generated_at':utcnow_iso(),
      'action':{'action_id':a['id'],'no_clar':a.get('action_no'),'title':a.get('title'),'prestation_type':a.get('prestation_type') or a.get('nature'),
                'delivery_mode':a.get('delivery_mode'),'location':a.get('location'),'planned_hours':a.get('planned_hours'),
                'start_date':a.get('start_date'),'end_date':a.get('end_date')},
      'beneficiary':identity,'participant_id':participant_id,'contract_type':contract_type,
      'aps':{'reference':aps_ref,'payload':aps_payload},
      'calendar':[{'date':x['slot_date'],'start':x['start_time'],'end':x['end_time']} for x in slots]}

def prepare_contractualization_case(engine, action_id, beneficiary_id, participant_id=None, *, contract_type='A_DEFINIR', aps_ref=None, aps_payload=None, actor='admin'):
    ctx=build_contractualization_context(engine,action_id,beneficiary_id,participant_id,contract_type=contract_type,aps_ref=aps_ref,aps_payload=aps_payload)
    now=utcnow_iso()
    execute(engine,'''INSERT INTO contractualization_cases(action_id,beneficiary_id,participant_id,no_clar,prestation_type,contract_type,aps_ref,aps_payload_json,status,context_payload_json,created_at,updated_at)
      VALUES(:a,:b,:p,:n,:pt,:ct,:ar,:ap,'A_PREPARER',:cx,:now,:now)''',
      {'a':action_id,'b':beneficiary_id,'p':participant_id,'n':ctx['action']['no_clar'],'pt':ctx['action']['prestation_type'],
       'ct':contract_type,'ar':aps_ref,'ap':json.dumps(aps_payload,ensure_ascii=False) if aps_payload is not None else None,
       'cx':json.dumps(ctx,ensure_ascii=False),'now':now})
    row=one(engine,'SELECT * FROM contractualization_cases ORDER BY id DESC LIMIT 1')
    execute(engine,"INSERT INTO contractualization_events(case_id,event_type,new_status,actor,details_json,created_at) VALUES(:c,'PREPARE','A_PREPARER',:a,:d,:n)",
            {'c':row['id'],'a':actor,'d':json.dumps({'format':ctx['format']},ensure_ascii=False),'n':now})
    audit(engine,actor,'CONTRACTUALIZATION_PREPARE','contractualization_case',row['id'],{'action_id':action_id,'beneficiary_id':beneficiary_id})
    return row

def list_contractualization_cases(engine, action_id=None, beneficiary_id=None):
    wh=[]; pa={}
    sql='SELECT c.*,b.public_id beneficiary_public_id,b.first_name,b.last_name FROM contractualization_cases c JOIN beneficiaries b ON b.id=c.beneficiary_id'
    if action_id is not None:
        wh.append('c.action_id=:a'); pa['a']=action_id
    if beneficiary_id is not None:
        wh.append('c.beneficiary_id=:b'); pa['b']=beneficiary_id
    if wh:
        sql+=' WHERE '+' AND '.join(wh)
    sql+=' ORDER BY c.updated_at DESC,c.id DESC'
    return q(engine,sql,pa)

def update_contractualization_case(engine, case_id, status, *, external_ref=None, pdf_ref=None, json_ref=None, financing_refs=None, warnings=None, actor='admin'):
    st=str(status or '').upper()
    if st not in CONTRACTUALIZATION_STATUSES:
        raise ValueError('Statut de contractualisation invalide.')
    old=one(engine,'SELECT * FROM contractualization_cases WHERE id=:i',{'i':case_id})
    if not old:
        raise ValueError('Dossier de contractualisation introuvable.')
    now=utcnow_iso()
    execute(engine,'''UPDATE contractualization_cases SET status=:s,external_ref=COALESCE(:e,external_ref),pdf_ref=COALESCE(:p,pdf_ref),json_ref=COALESCE(:j,json_ref),
      financing_refs_json=COALESCE(:f,financing_refs_json),warnings_json=COALESCE(:w,warnings_json),updated_at=:n WHERE id=:i''',
      {'s':st,'e':external_ref,'p':pdf_ref,'j':json_ref,'f':json.dumps(financing_refs,ensure_ascii=False) if financing_refs is not None else None,
       'w':json.dumps(warnings,ensure_ascii=False) if warnings is not None else None,'n':now,'i':case_id})
    execute(engine,"INSERT INTO contractualization_events(case_id,event_type,old_status,new_status,actor,details_json,created_at) VALUES(:c,'STATUS',:o,:s,:a,:d,:n)",
            {'c':case_id,'o':old['status'],'s':st,'a':actor,'d':json.dumps({'external_ref':external_ref,'pdf_ref':pdf_ref,'json_ref':json_ref},ensure_ascii=False),'n':now})
    audit(engine,actor,'CONTRACTUALIZATION_STATUS','contractualization_case',case_id,{'old':old['status'],'new':st})
