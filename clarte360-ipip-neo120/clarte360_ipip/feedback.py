from __future__ import annotations
import json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from clarte360_ipip.framework.validation import ValidationError, validate_safe_id

SCHEMA='clarte360.ipipneo.feedback.v1'
SCALE={1:'Pas du tout',2:'Plutôt non',3:'Partagé(e)',4:'Plutôt oui',5:'Tout à fait'}

def validate_feedback(data: dict[str,Any])->dict[str,Any]:
    out={}
    for key in ('global','dominants','nuances','useful'):
        try: v=int(data[key])
        except (KeyError,TypeError,ValueError) as exc: raise ValidationError(f'Réponse de ressenti manquante : {key}.') from exc
        if v not in SCALE: raise ValidationError(f'Réponse de ressenti invalide : {key}.')
        out[key]=v
    dialogue=str(data.get('dialogue','')).strip().lower()
    if dialogue not in {'oui','non'}: raise ValidationError('Réponse dialogue invalide.')
    out['dialogue']=dialogue
    for key in ('over','under','free'):
        out[key]=str(data.get(key,'')).strip()[:4000]
    return out

def save_feedback(root:Path,run_id:str,data:dict[str,Any])->Path:
    rid=validate_safe_id(run_id,'run_id')
    if (root/'completed'/f'{rid}.json').exists(): raise ValidationError('Cette passation est terminée et verrouillée en écriture.')
    clean=validate_feedback(data)
    p=root/'feedback'/f'{rid}.json'; p.parent.mkdir(parents=True,exist_ok=True)
    payload={'schema':SCHEMA,'run_id':rid,'feedback':clean,'updated_at':datetime.now(timezone.utc).isoformat()}
    fd,tmp=tempfile.mkstemp(prefix='.ipip-feedback-',suffix='.tmp',dir=p.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(payload,f,ensure_ascii=False,indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return p

def load_feedback(root:Path,run_id:str)->dict[str,Any]|None:
    rid=validate_safe_id(run_id,'run_id'); p=root/'feedback'/f'{rid}.json'
    if not p.exists(): return None
    raw=json.loads(p.read_text(encoding='utf-8'))
    if raw.get('schema')!=SCHEMA or raw.get('run_id')!=rid: raise ValidationError('Ressenti incohérent.')
    return validate_feedback(raw.get('feedback',{}))
