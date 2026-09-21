import json, math, re
from datetime import datetime

MAX_JSON_BYTES = 2 * 1024 * 1024
NAME_RE = re.compile(r"^[^\W\d_]+(?:[ '\u2019-][^\W\d_]+)*$", re.UNICODE)
EMAIL_RE = re.compile(r"^[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")

def _text(v, label, max_len, required=False):
    s = str(v or '').strip()
    if required and not s: raise ValueError(f"{label} est obligatoire.")
    if len(s) > max_len: raise ValueError(f"{label} est trop long.")
    if any(ord(c) < 32 and c not in '\n\t' for c in s): raise ValueError(f"{label} contient des caractères interdits.")
    return s

def validate_name(v, label='Nom'):
    s=_text(v,label,100,True)
    if not NAME_RE.fullmatch(s): raise ValueError(f"{label} contient des caractères non autorisés.")
    return s

def validate_email(v):
    s=_text(v,'Adresse e-mail',254,True)
    if '\r' in s or '\n' in s or not EMAIL_RE.fullmatch(s): raise ValueError("Adresse e-mail invalide.")
    return s

def validate_phone(v):
    s=_text(v,'Téléphone',40,False)
    if not s: return ''
    if not re.fullmatch(r"\+?[0-9 .()\-]+",s): raise ValueError("Téléphone invalide.")
    n=len(re.sub(r'\D','',s))
    if n<7 or n>15: raise ValueError("Téléphone invalide.")
    return s

def validate_short_text(v,label='Texte',max_len=160,required=False): return _text(v,label,max_len,required)
def validate_free_text(v,label='Texte',max_len=5000,required=False): return _text(v,label,max_len,required)

def validate_safe_id(v,label='Identifiant'):
    s=_text(v,label,160,True)
    if '..' in s or not SAFE_ID_RE.fullmatch(s): raise ValueError(f"{label} invalide.")
    return s

def validate_position(v):
    if isinstance(v,bool): raise ValueError('Position invalide.')
    try: x=float(v)
    except Exception: raise ValueError('Position invalide.')
    if not math.isfinite(x) or int(x)!=x or not 0<=int(x)<=10: raise ValueError('Position hors limites (0 à 10).')
    return int(x)

def validate_code(v):
    s=str(v or '').strip()
    if not re.fullmatch(r'\d{6}',s): raise ValueError("Le code doit contenir exactement 6 chiffres.")
    return s

def validate_progress_payload(payload, allowed_cursor_ids=None):
    if not isinstance(payload,dict): raise ValueError('Le JSON doit contenir un objet.')
    ben=payload.get('beneficiaire')
    if not isinstance(ben,dict): raise ValueError('Bénéficiaire manquant ou invalide.')
    validate_name(ben.get('prenom'),'Prénom'); validate_name(ben.get('nom'),'Nom'); validate_email(ben.get('email'))
    validate_short_text(ben.get('consultant',''),'Consultant',160,False)
    order=payload.get('cursor_order_displayed',payload.get('cursor_order',[]))
    if not isinstance(order,list) or len(order)>60: raise ValueError('Ordre des curseurs invalide.')
    seen=set(); allowed=set(map(str,allowed_cursor_ids or []))
    for cid in order:
        cid=validate_safe_id(cid,'ID curseur')
        if cid in seen: raise ValueError('ID curseur dupliqué dans le JSON.')
        if allowed and cid not in allowed: raise ValueError('Le JSON contient un curseur inconnu.')
        seen.add(cid)
    pos=payload.get('positions',{})
    if not isinstance(pos,dict) or len(pos)>60: raise ValueError('Positions invalides.')
    for cid,val in pos.items():
        cid=validate_safe_id(cid,'ID curseur')
        if allowed and cid not in allowed: raise ValueError('Le JSON contient un curseur inconnu.')
        validate_position(val)
    for key in ('passation_root_id','session_id','passation_id'):
        if payload.get(key): validate_safe_id(payload[key],key)
    return payload

def decode_progress_bytes(data, allowed_cursor_ids=None):
    if not isinstance(data,(bytes,bytearray)): raise ValueError('Fichier JSON invalide.')
    if len(data)>MAX_JSON_BYTES: raise ValueError('Fichier JSON trop volumineux (2 Mo maximum).')
    try: payload=json.loads(bytes(data).decode('utf-8'))
    except Exception: raise ValueError('Le fichier doit être un JSON UTF-8 valide.')
    return validate_progress_payload(payload,allowed_cursor_ids)
