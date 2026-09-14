import base64, hashlib, hmac, json, time
from validation import ValidationError, safe_id
TOOL_ID='boussole-valeurs'
ALLOWED_ROLES={'admin','intervenant'}
ALLOWED_SCOPES={'BOUSSOLE_RUN','BOUSSOLE_RESUME','BOUSSOLE_STATUS','BOUSSOLE_DOCUMENT_READ'}
MAX_TOKEN=8192

def _b64d(s): return base64.urlsafe_b64decode(s + '='*((4-len(s)%4)%4))
def verify_launch_token(token, secret, now=None):
    if not token or len(token)>MAX_TOKEN or '.' not in token: raise ValidationError('Jeton Hub invalide.')
    p,sig=token.rsplit('.',1)
    expected=hmac.new(secret.encode(),p.encode(),hashlib.sha256).digest()
    try: got=_b64d(sig)
    except Exception: raise ValidationError('Signature Hub invalide.')
    if not hmac.compare_digest(expected,got): raise ValidationError('Signature Hub invalide.')
    try: payload=json.loads(_b64d(p).decode('utf-8'))
    except Exception: raise ValidationError('Contenu du jeton Hub invalide.')
    if not isinstance(payload,dict) or payload.get('tool_id')!=TOOL_ID: raise ValidationError('Outil Hub incompatible.')
    if payload.get('hub_source') not in {'GESTION_ACTIONS_I9','GESTION_ACTIONS_I9_H1'}: raise ValidationError('Source Hub incompatible.')
    if payload.get('role') not in ALLOWED_ROLES: raise ValidationError('Rôle prescripteur non autorisé.')
    for k in ('beneficiary_id','action_id','participant_id','prescription_id'): safe_id(payload.get(k),k)
    scopes=payload.get('scopes',[])
    if not isinstance(scopes,list) or 'BOUSSOLE_RUN' not in scopes or any(x not in ALLOWED_SCOPES for x in scopes): raise ValidationError('Droits Hub invalides.')
    n=int(time.time() if now is None else now); exp=int(payload.get('exp',0)); iat=int(payload.get('iat',0))
    if exp<=n or iat>n+300 or exp-iat>7*86400: raise ValidationError('Jeton Hub expiré ou incohérent.')
    return payload

def status_event(payload,status,document_ref=None):
    if status not in {'opened','in_progress','completed','error'}: raise ValidationError('Statut Hub invalide.')
    out={'tool_id':TOOL_ID,'status':status,'prescription_id':safe_id(payload['prescription_id'],'prescription_id'),'beneficiary_id':safe_id(payload['beneficiary_id'],'beneficiary_id'),'action_id':safe_id(payload['action_id'],'action_id')}
    if document_ref: out['document_ref']=safe_id(document_ref,'document_ref')
    return out
