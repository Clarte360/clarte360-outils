from __future__ import annotations
import json, os, re, shutil, tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STORE_DIR = ROOT / 'data' / 'import_sources'
META_PATH = STORE_DIR / 'sources.json'
STORE_DIR.mkdir(parents=True, exist_ok=True)


def _key(kind: str):
    return str(kind or '').strip().upper()

def _slug(kind: str):
    s=re.sub(r'[^a-zA-Z0-9_-]+','_',_key(kind)).strip('_').lower()
    return s or 'source'

def _meta():
    if not META_PATH.exists(): return {}
    try:return json.loads(META_PATH.read_text(encoding='utf-8'))
    except Exception:return {}

def _write_meta(data):
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    tmp=META_PATH.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,META_PATH)

def source_info(kind: str): return _meta().get(_key(kind)) or {}

def set_external_path(kind: str, path: str | None):
    data=_meta(); key=_key(kind); info=data.get(key) or {};info['external_path']=(path or '').strip();data[key]=info;_write_meta(data);return info

def _target(kind: str, suffix: str):
    suffix=suffix.lower() if suffix.lower() in ('.xlsm','.xlsx','.csv') else '.xlsm'
    return STORE_DIR/f'{_slug(kind)}_source_latest{suffix}'

def save_uploaded_source(kind: str, filename: str, content: bytes):
    suffix=Path(filename or '').suffix or '.xlsm';target=_target(kind,suffix);STORE_DIR.mkdir(parents=True,exist_ok=True)
    fd,temp_name=tempfile.mkstemp(prefix='upload_',suffix=suffix,dir=STORE_DIR)
    try:
        with os.fdopen(fd,'wb') as f:f.write(content)
        os.replace(temp_name,target)
    finally:
        if os.path.exists(temp_name):os.unlink(temp_name)
    data=_meta();key=_key(kind);info=data.get(key) or {};info.update({'snapshot_path':str(target),'original_name':filename,'updated_at':datetime.now(timezone.utc).isoformat(),'size':len(content)});data[key]=info;_write_meta(data);return info

def refresh_from_external(kind: str):
    info=source_info(kind);src=Path(info.get('external_path') or '')
    if not str(src):raise ValueError('Aucun chemin source serveur n’est configuré.')
    if not src.is_file():raise FileNotFoundError(f'Source introuvable sur le serveur : {src}')
    target=_target(kind,src.suffix);fd,temp_name=tempfile.mkstemp(prefix='snapshot_',suffix=src.suffix,dir=STORE_DIR);os.close(fd)
    try:shutil.copy2(src,temp_name);os.replace(temp_name,target)
    finally:
        if os.path.exists(temp_name):os.unlink(temp_name)
    data=_meta();key=_key(kind);info=data.get(key) or {};info.update({'snapshot_path':str(target),'original_name':src.name,'updated_at':datetime.now(timezone.utc).isoformat(),'size':target.stat().st_size});data[key]=info;_write_meta(data);return info

def read_snapshot(kind: str):
    info=source_info(kind);p=Path(info.get('snapshot_path') or '')
    if not str(p) or not p.is_file():return None,info
    return p.read_bytes(),info

def copy_source_metadata(source_kind: str, target_kind: str, overwrite=False):
    """Migration helper: duplicate legacy metadata under a generic profile key."""
    data=_meta();src=data.get(_key(source_kind)) or {};dst=data.get(_key(target_kind)) or {}
    if not src or (dst and not overwrite): return dst
    data[_key(target_kind)]={**src};_write_meta(data);return data[_key(target_kind)]
