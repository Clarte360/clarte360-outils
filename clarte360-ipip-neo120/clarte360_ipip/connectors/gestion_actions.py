from __future__ import annotations
import base64, hashlib, hmac, json, os, tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from clarte360_ipip.framework.config import PERSISTENT_DATA_DIR, TOOL_ID
from clarte360_ipip.framework.validation import ValidationError, validate_epoch_window, validate_safe_id, validate_string_list, validate_person_name, validate_optional_short_text

OUTBOX_SCHEMA='clarte360.ipipneo.gestion-actions.event.v1'
OUTBOUND_CONTRACT_VERSION='IPIP-GA-OUTBOUND-1.0'
ALLOWED_SCOPES={'IPIP_RUN','IPIP_RESUME','IPIP_STATUS','IPIP_RESULT_READ'}
ALLOWED_EVENT_TYPES={'CONSULTE','EN_COURS','TERMINE','ERREUR'}

class LaunchTokenError(ValueError): pass

def _b64url_decode(v:str)->bytes:
    try: return base64.urlsafe_b64decode((v+'='*(-len(v)%4)).encode('ascii'))
    except Exception as exc: raise LaunchTokenError('Jeton de lancement illisible.') from exc

def _canonical_json(payload:Mapping[str,Any])->bytes:
    return json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')

def build_launch_token(payload:Mapping[str,Any], signing_key:str)->str:
    raw=_canonical_json(payload); pp=base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')
    sig=hmac.new(signing_key.encode(),pp.encode('ascii'),hashlib.sha256).digest()
    return pp+'.'+base64.urlsafe_b64encode(sig).decode('ascii').rstrip('=')

@dataclass(frozen=True)
class LaunchContext:
    beneficiary_id:str; action_id:str; prescription_id:str; participant_id:str|None
    beneficiary_first_name:str|None; beneficiary_last_name:str|None; action_number:str|None; action_title:str|None
    scopes:tuple[str,...]; hub_source:str

def verify_launch_token(token:str, signing_key:str, now_epoch:int|None=None)->LaunchContext:
    if not token or '.' not in token or len(token)>8192: raise LaunchTokenError('Jeton de lancement manquant ou invalide.')
    if not signing_key or len(signing_key.strip())<24: raise LaunchTokenError('Clé de validation du connecteur non configurée.')
    try:
        pp,sp=token.split('.',1); supplied=_b64url_decode(sp)
        expected=hmac.new(signing_key.encode(),pp.encode('ascii'),hashlib.sha256).digest()
    except Exception as exc: raise LaunchTokenError('Jeton de lancement illisible.') from exc
    if not hmac.compare_digest(expected,supplied): raise LaunchTokenError('Signature du jeton de lancement invalide.')
    try: payload=json.loads(_b64url_decode(pp).decode('utf-8'))
    except Exception as exc: raise LaunchTokenError('Contenu du jeton de lancement invalide.') from exc
    if not isinstance(payload,dict): raise LaunchTokenError('Contenu du jeton de lancement invalide.')
    try:
        validate_epoch_window(payload.get('iat'),payload.get('exp'),now_epoch=now_epoch)
        tool=str(payload.get('tool_id') or TOOL_ID)
        if tool!=TOOL_ID: raise ValidationError('Ce lien de lancement est destiné à un autre outil.')
        hub=str(payload.get('hub_source') or 'GESTION_ACTIONS_I9')
        if hub not in {'GESTION_ACTIONS_I9','GESTION_ACTIONS_I9_H1'}: raise ValidationError('Source Hub du jeton non reconnue.')
        scopes=validate_string_list(payload.get('scopes',payload.get('rights',[])),'Droits/scopes',allowed=ALLOWED_SCOPES,max_items=10)
        if 'IPIP_RUN' not in scopes: raise ValidationError('Le jeton ne contient pas le droit IPIP_RUN.')
        return LaunchContext(
            validate_safe_id(payload.get('beneficiary_id'),'beneficiary_id') or '',
            validate_safe_id(payload.get('action_id'),'action_id') or '',
            validate_safe_id(payload.get('prescription_id'),'prescription_id') or '',
            validate_safe_id(payload.get('participant_id'),'participant_id',required=False),
            validate_person_name(payload.get('beneficiary_first_name'),'Prénom bénéficiaire') if payload.get('beneficiary_first_name') else None,
            validate_person_name(payload.get('beneficiary_last_name'),'Nom bénéficiaire') if payload.get('beneficiary_last_name') else None,
            validate_optional_short_text(payload.get('action_number'),'Numéro action') if payload.get('action_number') else None,
            validate_optional_short_text(payload.get('action_title'),'Intitulé action') if payload.get('action_title') else None,
            scopes,hub)
    except ValidationError as exc: raise LaunchTokenError(str(exc)) from exc

def _utcnow(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _atomic_json(path:Path,payload:Mapping[str,Any]):
    path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(prefix='.ipip-ga-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(payload,f,ensure_ascii=False,indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
def _event_id(t:str,p:Mapping[str,Any])->str: return hashlib.sha256(t.encode()+b'\0'+_canonical_json(p)).hexdigest()[:32]
def _outbox_root(root:Path|None=None): return (root or PERSISTENT_DATA_DIR)/'connector_outbox'/'gestion_actions'

def bind_prescription(root:Path,ctx:LaunchContext,run_id:str)->str:
    rid=validate_safe_id(run_id,'run_id') or ''
    folder=root/'prescriptions'; folder.mkdir(parents=True,exist_ok=True); p=folder/f'{ctx.prescription_id}.json'
    existing=json.loads(p.read_text(encoding='utf-8')) if p.exists() else None
    if existing:
        for k,v in [('beneficiary_id',ctx.beneficiary_id),('action_id',ctx.action_id),('participant_id',ctx.participant_id)]:
            if existing.get(k)!=v: raise LaunchTokenError('Cette prescription est déjà liée à un autre contexte bénéficiaire/action.')
        return validate_safe_id(existing.get('run_id'),'run_id') or ''
    _atomic_json(p,{'schema':'clarte360.ipipneo.prescription.v1','prescription_id':ctx.prescription_id,'beneficiary_id':ctx.beneficiary_id,'action_id':ctx.action_id,'participant_id':ctx.participant_id,'run_id':rid,'created_at':_utcnow()})
    return rid

def prescription_status(root:Path,ctx:LaunchContext)->str:
    p=root/'prescriptions'/f'{ctx.prescription_id}.json'
    if not p.exists(): return 'NOUVEAU'
    d=json.loads(p.read_text(encoding='utf-8')); rid=d['run_id']
    return 'TERMINE' if (root/'completed'/f'{rid}.json').exists() else 'EN_COURS'

def report_document_ref(root:Path,run_id:str)->dict[str,Any]:
    from clarte360_ipip.completion import load_completion
    c=load_completion(root,run_id)
    if not c: raise ValueError('Passation non terminée.')
    p=Path(c['report_path']); content=p.read_bytes(); digest=hashlib.sha256(content).hexdigest()
    if digest!=c['report_sha256']: raise ValueError('Empreinte du rapport incohérente.')
    return {'report_id':hashlib.sha256((run_id+':'+digest).encode()).hexdigest()[:32],'file_name':p.name,'mime_type':'application/pdf','sha256':digest,'size_bytes':len(content),'storage_ref':str(p.relative_to(root)) if p.is_relative_to(root) else str(p)}

@dataclass(frozen=True)
class GestionActionsPort:
    signing_key:str|None=None; root:Path|None=None
    @property
    def enabled(self): return bool(self.signing_key and self.signing_key.strip())
    def resolve_launch(self,token:str)->LaunchContext:
        if not self.enabled: raise LaunchTokenError('Connecteur Gestion des actions non configuré.')
        return verify_launch_token(token,self.signing_key or '')
    def publish_event(self,event_type:str,payload:dict[str,Any])->Path:
        if event_type not in ALLOWED_EVENT_TYPES: raise ValueError('Type événement IPIP non autorisé.')
        for field in ('beneficiary_id','action_id','prescription_id','passation_id','participant_id'):
            if payload.get(field) is not None: validate_safe_id(payload.get(field),field,required=False)
        eid=_event_id(event_type,payload); root=_outbox_root(self.root); pending=root/'pending'/f'{eid}.json'; delivered=root/'delivered'/f'{eid}.json'
        if delivered.exists(): return delivered
        if pending.exists(): return pending
        env={'schema':OUTBOX_SCHEMA,'event_id':eid,'idempotency_key':eid,'event_type':event_type,'tool_id':TOOL_ID,'contract_version':OUTBOUND_CONTRACT_VERSION,'created_at':_utcnow(),'status':'PENDING','attempts':0,'last_attempt_at':None,'last_error':None,'payload':payload}
        _atomic_json(pending,env); audit=root/'events.jsonl'; audit.parent.mkdir(parents=True,exist_ok=True)
        with audit.open('a',encoding='utf-8') as f: f.write(json.dumps(env,ensure_ascii=False,separators=(',',':'))+'\n')
        return pending
    def signed_delivery_headers(self,envelope:Mapping[str,Any])->dict[str,str]:
        if not self.enabled: raise LaunchTokenError('Clé HMAC non configurée.')
        sig=hmac.new((self.signing_key or '').encode(),_canonical_json(envelope),hashlib.sha256).hexdigest()
        return {'X-Clarte360-Tool':TOOL_ID,'X-Clarte360-Event-Id':str(envelope.get('event_id') or ''),'X-Clarte360-Signature':'sha256='+sig}
    def pending_events(self):
        f=_outbox_root(self.root)/'pending'; return sorted(f.glob('*.json')) if f.exists() else []
    def retry_pending(self,sender:Callable[[dict[str,Any]],None],limit:int=50):
        ok=failed=0
        for p in self.pending_events()[:max(0,int(limit))]:
            e=json.loads(p.read_text(encoding='utf-8')); e['attempts']=int(e.get('attempts',0))+1; e['last_attempt_at']=_utcnow()
            try: sender(e)
            except Exception as exc: e['status']='PENDING'; e['last_error']=str(exc)[:500]; _atomic_json(p,e); failed+=1; continue
            e['status']='DELIVERED'; e['delivered_at']=_utcnow(); e['last_error']=None; target=_outbox_root(self.root)/'delivered'/p.name; _atomic_json(target,e); p.unlink(missing_ok=True); ok+=1
        return {'delivered':ok,'failed':failed}
