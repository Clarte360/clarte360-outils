from __future__ import annotations
import json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path
from clarte360_ipip.framework.validation import validate_safe_id

def completion_path(root:Path,run_id:str)->Path:
    return root/'completed'/f"{validate_safe_id(run_id,'run_id')}.json"

def is_completed(root:Path,run_id:str)->bool:
    return completion_path(root,run_id).exists()

def mark_completed(root:Path,run_id:str,*,report_path:str,report_sha256:str,report_version:str='1')->Path:
    rid=validate_safe_id(run_id,'run_id'); p=completion_path(root,rid); p.parent.mkdir(parents=True,exist_ok=True)
    payload={'schema':'clarte360.ipipneo.completion.v1','run_id':rid,'status':'TERMINE','report_path':report_path,'report_sha256':report_sha256,'report_version':str(report_version),'completed_at':datetime.now(timezone.utc).isoformat()}
    fd,tmp=tempfile.mkstemp(prefix='.ipip-complete-',suffix='.tmp',dir=p.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(payload,f,ensure_ascii=False,indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return p

def load_completion(root:Path,run_id:str):
    p=completion_path(root,run_id)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None
