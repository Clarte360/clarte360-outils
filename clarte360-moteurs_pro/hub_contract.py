import base64, hashlib, hmac, json, time
from validation import validate_email, validate_name, validate_safe_id
TOOL_ID='moteurs-professionnels'
ALLOWED_ROLES={'admin','intervenant'}
ALLOWED_SCOPES={'MOTEURS_RUN','MOTEURS_RESUME','MOTEURS_STATUS'}
ALLOWED_SOURCES={'GESTION_ACTIONS_I9','GESTION_ACTIONS_I9_H1'}

def _b64d(s): return base64.urlsafe_b64decode(s + '=' * (-len(s)%4))
def verify_launch_token(token, secret, now=None):
    if not token or len(token)>8192: raise ValueError('Jeton Hub invalide.')
    try: p64,s64=token.split('.',1); raw=_b64d(p64); sig=_b64d(s64)
    except Exception: raise ValueError('Jeton Hub mal formé.')
    expected=hmac.new(secret.encode(),raw,hashlib.sha256).digest()
    if not hmac.compare_digest(sig,expected): raise ValueError('Signature Hub invalide.')
    if len(raw)>16384: raise ValueError('Contexte Hub trop volumineux.')
    try: p=json.loads(raw.decode('utf-8'))
    except Exception: raise ValueError('Contexte Hub invalide.')
    if p.get('tool_id') != TOOL_ID: raise ValueError('Outil Hub incorrect.')
    if p.get('hub_source') not in ALLOWED_SOURCES: raise ValueError('Source Hub incorrecte.')
    if p.get('role') not in ALLOWED_ROLES: raise ValueError('Rôle Hub non autorisé.')
    for k in ('beneficiary_id','action_id','participant_id','prescription_id'): validate_safe_id(p.get(k),k)
    scopes=set(p.get('scopes',p.get('rights',[])))
    if 'MOTEURS_RUN' not in scopes or not scopes.issubset(ALLOWED_SCOPES): raise ValueError('Droits Hub invalides.')
    now=int(now if now is not None else time.time()); exp=int(p.get('exp',0)); iat=int(p.get('iat',now))
    if exp<=now or exp-iat>7*86400: raise ValueError('Jeton Hub expiré ou durée invalide.')
    ben=p.get('beneficiary') or {}
    if ben:
        validate_name(ben.get('prenom'),'Prénom'); validate_name(ben.get('nom'),'Nom'); validate_email(ben.get('email'))
    return p
