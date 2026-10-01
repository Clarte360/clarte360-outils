from __future__ import annotations
import json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from clarte360_ipip.framework.validation import ValidationError, validate_safe_id
from .model import validate_answers

SCHEMA='clarte360.ipipneo.questionnaire.v1'

def _ensure_run_writable(root: Path, run_id: str)->None:
    rid=validate_safe_id(run_id,'run_id')
    if (root/'completed'/f'{rid}.json').exists():
        raise ValidationError('Cette passation est terminée et verrouillée en écriture.')

def _path(root: Path, run_id: str)->Path:
    rid=validate_safe_id(run_id,'run_id')
    return root/'runs'/f'{rid}.json'

def save_progress(root: Path, run_id: str, *, reference_version: str, answers: dict[int,Any], current_block: int)->Path:
    _ensure_run_writable(root,run_id)
    clean=validate_answers(answers)
    if not 0<=int(current_block)<=11: raise ValidationError('Progression invalide.')
    p=_path(root,run_id); p.parent.mkdir(parents=True,exist_ok=True)
    payload={'schema':SCHEMA,'run_id':run_id,'reference_version':reference_version,'answers':{str(k):v for k,v in sorted(clean.items())},'current_block':int(current_block),'updated_at':datetime.now(timezone.utc).isoformat()}
    fd,tmp=tempfile.mkstemp(prefix='.ipip-',suffix='.tmp',dir=p.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(payload,f,ensure_ascii=False,indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return p

def load_progress(root: Path, run_id: str, *, expected_reference_version: str)->dict[str,Any] | None:
    p=_path(root,run_id)
    if not p.exists(): return None
    try: payload=json.loads(p.read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError) as exc: raise ValidationError('Sauvegarde de passation illisible.') from exc
    if payload.get('schema')!=SCHEMA or payload.get('run_id')!=run_id: raise ValidationError('Sauvegarde de passation incohérente.')
    if payload.get('reference_version')!=expected_reference_version: raise ValidationError('La version du questionnaire sauvegardé ne correspond plus au référentiel actif.')
    payload['answers']=validate_answers(payload.get('answers',{}))
    block=int(payload.get('current_block',0))
    if not 0<=block<=11: raise ValidationError('Progression sauvegardée invalide.')
    payload['current_block']=block
    return payload

def save_scoring_result(root: Path, run_id: str, result: dict[str,Any])->Path:
    """Persist a deterministic scoring snapshot next to the questionnaire run."""
    _ensure_run_writable(root,run_id)
    rid=validate_safe_id(run_id,'run_id')
    p=root/'scores'/f'{rid}.json'; p.parent.mkdir(parents=True,exist_ok=True)
    payload={'schema':'clarte360.ipipneo.scoring.v1','run_id':rid,'result':result,'updated_at':datetime.now(timezone.utc).isoformat()}
    fd,tmp=tempfile.mkstemp(prefix='.ipip-score-',suffix='.tmp',dir=p.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(payload,f,ensure_ascii=False,indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return p
