"""J4 - Shared, access-checked in-app notifications for the four GDA spaces.

Notifications are pointers, NOT source-of-truth records. Reading a notification
never modifies a Quality case, document validation, CAPA or business workflow.
External connectors must authenticate before calling ingest_partner_event; this
module intentionally does NOT expose a public HTTP endpoint or shared secrets.
"""
from __future__ import annotations
from datetime import datetime,timezone
from sqlalchemy import text
from db import one,q,utcnow_iso

ROLES=frozenset(('ADMIN','TRAINER','BENEFICIARY','CLIENT'))
CATEGORIES=frozenset(('INFO','ACTION'))
TARGETS=frozenset(('ACTION','QUALITY','DOCUMENT','PROFESSIONAL_DOCUMENT','CAPA','MISSION'))
EVENT_CODES=frozenset(('QUALITY_NEW','QUALITY_REPLY','QUALITY_STATUS','QUALITY_CAPA','DOCUMENT_AVAILABLE','DOCUMENT_REVIEW','DOCUMENT_SHARED','PLANNING_CHANGED','MISSION_ASSIGNED','CLIENT_UPDATE'))
SOURCE_SYSTEMS=frozenset(('GDA','GESTION_CLIENTS','CONTRACTUALISATION'))

NOTIFICATION_SCHEMA=[
'''CREATE TABLE IF NOT EXISTS workspace_notifications (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 source_system TEXT NOT NULL,
 source_event_id TEXT NOT NULL,
 recipient_role TEXT NOT NULL,
 recipient_key TEXT NOT NULL,
 action_id INTEGER,
 event_code TEXT NOT NULL,
 category TEXT NOT NULL DEFAULT 'INFO',
 target_kind TEXT NOT NULL,
 target_id TEXT NOT NULL,
 display_text TEXT NOT NULL,
 created_at TEXT NOT NULL,
 read_at TEXT,
 UNIQUE(source_system,source_event_id,recipient_role,recipient_key),
 FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE
)''',
'''CREATE INDEX IF NOT EXISTS ix_workspace_inbox ON workspace_notifications(recipient_role,recipient_key,read_at,id)''',
'''CREATE INDEX IF NOT EXISTS ix_workspace_action ON workspace_notifications(action_id)''',
'''CREATE TABLE IF NOT EXISTS external_notification_identity_links (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 source_system TEXT NOT NULL,
 external_subject_type TEXT NOT NULL,
 external_subject_id TEXT NOT NULL,
 local_role TEXT NOT NULL,
 local_recipient_key TEXT NOT NULL,
 verified_by TEXT NOT NULL,
 verified_at TEXT NOT NULL,
 revoked_at TEXT,
 UNIQUE(source_system,external_subject_type,external_subject_id,local_role,local_recipient_key)
)'''
]

def _role(role,key):
    role=str(role or '').upper().strip()
    if role not in ROLES:raise ValueError('Rôle de notification inconnu.')
    if role=='ADMIN':
        key=str(key or '').strip().lower()
        if not key or '@' not in key or len(key)>254:raise ValueError('Compte administrateur invalide.')
    else:
        try:key=str(int(key))
        except (ValueError,TypeError):raise ValueError('Identifiant de compte invalide.')
        if int(key)<1:raise ValueError('Identifiant de compte invalide.')
    return role,key

def _authorized(engine,role,key,action_id=None,target_kind=None,target_id=None,*,allow_pending_client=False):
    """Every listing and acknowledgment is checked against *current* permissions."""
    if role=='ADMIN':
        if not one(engine,"SELECT id FROM admins WHERE lower(email)=:e AND active=1",{'e':key}):return False
    elif role=='TRAINER':
        if not one(engine,'SELECT id FROM trainers WHERE id=:i AND active=1',{'i':int(key)}):return False
        if action_id is not None:
            from services import trainer_action_authorized
            if not trainer_action_authorized(engine,int(key),int(action_id)):return False
        elif target_kind not in (None,'PROFESSIONAL_DOCUMENT'):return False
    elif role=='BENEFICIARY':
        if not one(engine,'''SELECT b.id FROM beneficiaries b JOIN beneficiary_portal_accounts p ON p.beneficiary_id=b.id
                WHERE b.id=:i AND b.active=1 AND p.active=1''',{'i':int(key)}):return False
        if action_id is not None:
            if not one(engine,'SELECT id FROM participants WHERE beneficiary_id=:b AND action_id=:a AND active=1',{'b':int(key),'a':int(action_id)}):return False
        elif target_kind is not None:return False
    elif role=='CLIENT':
        try:
            if allow_pending_client:
                from client_portal import _ident
                _ident(engine,int(key),activated=False)
                if action_id is None:return False
                grant=one(engine,'SELECT id,can_download FROM client_action_grants WHERE account_id=:c AND action_id=:a AND revoked_at IS NULL',{'c':int(key),'a':action_id})
                if not grant:return False
                if target_kind=='DOCUMENT' and not grant['can_download']:return False
            elif action_id is None:
                from client_portal import client_portal_identity
                client_portal_identity(engine,int(key))
            else:
                from client_portal import client_action_permission
                client_action_permission(engine,int(key),int(action_id),'view')
        except (PermissionError,ValueError,TypeError):return False
    if action_id is not None and not one(engine,'SELECT id FROM actions WHERE id=:a',{'a':int(action_id)}):return False
    if target_kind=='QUALITY':
        ev=one(engine,'SELECT id,action_id,trainer_id,beneficiary_id FROM quality_events WHERE id=:i',{'i':int(target_id)})
        if not ev or ev.get('action_id')!=action_id:return False
        if role=='CLIENT':return False  # BC and individual quality records are NEVER shared with a client.
        if role=='TRAINER' and ev.get('trainer_id')!=int(key):return False
        if role=='BENEFICIARY' and ev.get('beneficiary_id')!=int(key):return False
    elif target_kind=='CAPA':
        ca=one(engine,'SELECT e.action_id FROM quality_event_actions ca JOIN quality_events e ON e.id=ca.quality_event_id WHERE ca.id=:i',{'i':int(target_id)})
        if not ca or ca.get('action_id')!=action_id or role!='ADMIN':return False
    elif target_kind=='PROFESSIONAL_DOCUMENT':
        if role!='TRAINER' or action_id is not None:return False
        from services import trainer_shared_professional_documents
        if not any(int(row['id'])==int(target_id) for row in trainer_shared_professional_documents(engine,int(key))):return False
    elif target_kind=='DOCUMENT':
        dr=one(engine,'SELECT action_id,deleted_at FROM document_references WHERE id=:i',{'i':int(target_id)})
        if not dr or dr.get('action_id')!=action_id or dr.get('deleted_at'):return False
        if role=='TRAINER':
            from services import list_trainer_documents
            if not any(row['id']==int(target_id) for row in list_trainer_documents(engine,int(key),int(action_id))):return False
        elif role=='BENEFICIARY':
            from services import list_beneficiary_documents
            if not any(row['id']==int(target_id) for row in list_beneficiary_documents(engine,int(key))):return False
        elif role=='CLIENT':
            if allow_pending_client:
                share=one(engine,'SELECT id FROM client_document_shares WHERE document_reference_id=:d AND account_id=:a AND revoked_at IS NULL',{'d':int(target_id),'a':int(key)})
                if not share:return False
            else:
                from client_portal import list_client_documents
                try:items=list_client_documents(engine,int(key),int(action_id))
                except (PermissionError,ValueError):return False
                if not any(row['id']==int(target_id) for row in items):return False
    return True

def enqueue(engine,*,source_system,source_event_id,recipient_role,recipient_key,action_id,event_code,category,target_kind,target_id,display_text,allow_pending_client=False):
    """Idempotent, non-sensitive pointer; no automatically delivered e-mail."""
    role,key=_role(recipient_role,recipient_key)
    source_system=str(source_system or '').upper().strip(); event_code=str(event_code or '').upper().strip()
    target_kind=str(target_kind or '').upper().strip(); category=str(category or '').upper().strip()
    if source_system not in SOURCE_SYSTEMS or event_code not in EVENT_CODES or target_kind not in TARGETS or category not in CATEGORIES:
        raise ValueError('Type de notification non reconnu.')
    source_event_id=str(source_event_id or '').strip()
    if not source_event_id or len(source_event_id)>190:raise ValueError('Référence événement non valide.')
    try:action_id=int(action_id) if action_id is not None else None
    except (ValueError,TypeError):raise ValueError('Référence action non valide.')
    target_id=str(target_id or '').strip()
    if not target_id or len(target_id)>100:raise ValueError('Cible de notification absente.')
    if target_kind in ('QUALITY','DOCUMENT','PROFESSIONAL_DOCUMENT','CAPA'):
        try:int(target_id)
        except ValueError:raise ValueError('Cible numérique attendue.')
    if target_kind in ('ACTION','MISSION') and (action_id is None or target_id!=str(action_id)):
        raise ValueError('La cible ne correspond pas au rattachement de l’action.')
    # Use generic wording, not a private document title, questionnaire, complaint or personal name.
    display_text=str(display_text or '').strip()
    if not display_text or len(display_text)>140:raise ValueError('Libellé générique invalide.')
    if not _authorized(engine,role,key,action_id,target_kind,target_id,allow_pending_client=allow_pending_client):return False
    with engine.begin() as db:
        count=db.execute(text('''INSERT OR IGNORE INTO workspace_notifications(
        source_system,source_event_id,recipient_role,recipient_key,action_id,event_code,category,target_kind,target_id,display_text,created_at)
        VALUES(:s,:e,:r,:k,:a,:ev,:c,:t,:id,:d,:now)'''),{
            's':source_system,'e':source_event_id,'r':role,'k':key,'a':action_id,'ev':event_code,'c':category,'t':target_kind,'id':target_id,'d':display_text,'now':utcnow_iso()}).rowcount
    return bool(count)

def inbox(engine,role,recipient_key,*,unread_only=True,limit=50):
    role,key=_role(role,recipient_key)
    if not _authorized(engine,role,key):return []
    lim=max(1,min(150,int(limit)))
    # No limitless historical query; filter by current rights after SQL pagination.
    sql='''SELECT * FROM workspace_notifications WHERE recipient_role=:r AND recipient_key=:k'''
    if unread_only:sql+=' AND read_at IS NULL'
    sql+=' ORDER BY id DESC LIMIT :lim'
    rows=q(engine,sql,{'r':role,'k':key,'lim':max(lim*8,400)})
    return [row for row in rows if _authorized(engine,role,key,row['action_id'],row['target_kind'],row['target_id'])][:lim]

def mark_read(engine,notification_id,role,recipient_key):
    role,key=_role(role,recipient_key)
    n=one(engine,'SELECT * FROM workspace_notifications WHERE id=:i AND recipient_role=:r AND recipient_key=:k',{'i':notification_id,'r':role,'k':key})
    if not n or not _authorized(engine,role,key,n.get('action_id'),n['target_kind'],n['target_id']):raise PermissionError('Notification non autorisée.')
    if n.get('read_at'):return False
    with engine.begin() as conn:
        return bool(conn.execute(text('UPDATE workspace_notifications SET read_at=:now WHERE id=:i AND read_at IS NULL'),{'now':utcnow_iso(),'i':notification_id}).rowcount)

def _admins(engine):
    return [r['email'].lower() for r in q(engine,'SELECT email FROM admins WHERE active=1 ORDER BY id')]

def notify_admins(engine,event_id,action_id,target_kind,entity_id,event_code,*,display='Nouvelle information à traiter'):
    added=0
    for email in _admins(engine):
        added+=int(enqueue(engine,source_system='GDA',source_event_id=str(event_id),recipient_role='ADMIN',recipient_key=email,action_id=action_id,event_code=event_code,category='ACTION',target_kind=target_kind,target_id=entity_id,display_text=display))
    return added

def quality_created(engine,event_id):
    ev=one(engine,'SELECT action_id FROM quality_events WHERE id=:i',{'i':event_id})
    if ev:notify_admins(engine,f'quality:new:{event_id}',ev['action_id'],'QUALITY',event_id,'QUALITY_NEW',display='Nouvelle fiche Qualité à examiner')

def quality_changed(engine,event_id,change_kind,change_key):
    ev=one(engine,'SELECT * FROM quality_events WHERE id=:i',{'i':event_id})
    if not ev:return 0
    recipients=[]
    if ev.get('trainer_id') and q(engine,"SELECT id FROM quality_source_links WHERE quality_event_id=:e AND source_kind='TRAINER_REPORT'",{'e':event_id}):recipients.append(('TRAINER',ev['trainer_id']))
    if ev.get('beneficiary_id') and q(engine,"SELECT id FROM quality_source_links WHERE quality_event_id=:e AND source_kind='BENEFICIARY_REPORT'",{'e':event_id}):recipients.append(('BENEFICIARY',ev['beneficiary_id']))
    added=0
    for role,rid in recipients:
        added+=int(enqueue(engine,source_system='GDA',source_event_id=f'quality:{change_kind}:{event_id}:{change_key}',recipient_role=role,recipient_key=rid,action_id=ev['action_id'],event_code='QUALITY_REPLY' if change_kind=='reply' else 'QUALITY_STATUS',category='INFO',target_kind='QUALITY',target_id=event_id,display_text='Une réponse Qualité est disponible' if change_kind=='reply' else 'Le suivi de votre demande a évolué'))
    return added

def document_available(engine,reference_id,actor):
    # Reuse existing permission-checked document recipients. This never creates
    # access that the underlying document services do not already grant.
    rows=q(engine,'SELECT document_reference_id,action_id,recipient_type,recipient_id FROM document_notifications WHERE document_reference_id=:d',{'d':reference_id})
    count=0
    for n in rows:
        count+=int(enqueue(engine,source_system='GDA',source_event_id=f'doc:published:{reference_id}',recipient_role=n['recipient_type'],recipient_key=n['recipient_id'],action_id=n['action_id'],event_code='DOCUMENT_AVAILABLE',category='INFO',target_kind='DOCUMENT',target_id=reference_id,display_text='Nouveau document disponible'))
    return count

def professional_document_shared(engine,document_id,trainer_id):
    """J6 - A private dossier document explicitly shared by administration.

    No action is necessary; access is re-checked against its current sharing flag.
    The document's title and category are not included in the alert.
    """
    return enqueue(engine,source_system='GDA',
        source_event_id=f'professional_document_shared:{int(document_id)}:{utcnow_iso()}',
        recipient_role='TRAINER',recipient_key=trainer_id,action_id=None,
        event_code='DOCUMENT_SHARED',category='INFO',target_kind='PROFESSIONAL_DOCUMENT',
        target_id=document_id,display_text='Nouveau document disponible dans votre dossier professionnel')


def document_needs_review(engine,reference_id,action_id,actor):
    if str(actor).lower().startswith(('trainer:','beneficiary:','client_portal:')):
        return notify_admins(engine,f'doc:review:{reference_id}',action_id,'DOCUMENT',reference_id,'DOCUMENT_REVIEW',display='Document déposé : validation à effectuer')
    return 0

def document_received(engine,reference_id,action_id,actor):
    """A user-upload notification for authorized admins, even on a published file.

    Reception alone is informational; a document awaiting administrative
    approval instead emits the actionable DOCUMENT_REVIEW notification.
    """
    if not str(actor or '').lower().startswith(('trainer:','beneficiary:','client_portal:')):
        return 0
    total=0
    for email in _admins(engine):
        total+=int(enqueue(engine,source_system='GDA',source_event_id=f'doc:received:{reference_id}',
            recipient_role='ADMIN',recipient_key=email,action_id=action_id,
            event_code='DOCUMENT_AVAILABLE',category='INFO',target_kind='DOCUMENT',target_id=reference_id,
            display_text='Nouveau document déposé dans un espace'))
    return total

def client_document_shared(engine,reference_id,account_id,action_id):
    return enqueue(engine,source_system='GDA',source_event_id=f'client_share:{reference_id}:{account_id}',recipient_role='CLIENT',recipient_key=account_id,action_id=action_id,event_code='DOCUMENT_SHARED',category='INFO',target_kind='DOCUMENT',target_id=reference_id,display_text='Nouveau document partagé',allow_pending_client=True)

def schedule_changed(engine,action_id,slot_id,event_id):
    # No forced client notification of individual session details.
    affected=q(engine,'''SELECT DISTINCT trainer_id FROM (
          SELECT at.trainer_id FROM action_trainers at WHERE at.action_id=:a AND at.active=1
          UNION SELECT a.trainer_id FROM actions a WHERE a.id=:a AND a.trainer_id IS NOT NULL
          UNION SELECT st.trainer_id FROM slot_trainers st JOIN slots sl ON sl.id=st.slot_id
            WHERE sl.action_id=:a AND st.active=1 AND st.assignment_status='ACTIVE'
        ) WHERE trainer_id IS NOT NULL''',{'a':action_id})
    count=0
    for tr in affected:
        count+=int(enqueue(engine,source_system='GDA',source_event_id=f'slot:{event_id}',recipient_role='TRAINER',recipient_key=tr['trainer_id'],action_id=action_id,event_code='PLANNING_CHANGED',category='INFO',target_kind='ACTION',target_id=action_id,display_text='Planning de votre action actualisé'))
    b=q(engine,'''SELECT DISTINCT p.beneficiary_id FROM participants p JOIN beneficiaries be ON be.id=p.beneficiary_id
    WHERE p.action_id=:a AND p.active=1 AND p.beneficiary_id IS NOT NULL AND be.active=1''',{'a':action_id})
    for bb in b:
        count+=int(enqueue(engine,source_system='GDA',source_event_id=f'slot:{event_id}',recipient_role='BENEFICIARY',recipient_key=bb['beneficiary_id'],action_id=action_id,event_code='PLANNING_CHANGED',category='INFO',target_kind='ACTION',target_id=action_id,display_text='Votre planning a été actualisé'))
    return count

def bind_external_identity(engine,source_system,subject_type,external_id,local_role,local_key,*,admin_email):
    """Explicit verified mapping (no guessing identity by same name/email)."""
    source_system=str(source_system or '').upper()
    if source_system not in {'GESTION_CLIENTS','CONTRACTUALISATION'}:raise ValueError('Application externe non autorisée.')
    if not _authorized(engine,'ADMIN',str(admin_email).strip().lower()):raise PermissionError('Administrateur requis.')
    role,key=_role(local_role,local_key)
    if not str(subject_type or '').strip() or not str(external_id or '').strip():raise ValueError('Identité externe invalide.')
    # Role validity for a notification is checked again at delivery time.
    with engine.begin() as db:
        return bool(db.execute(text('''INSERT OR IGNORE INTO external_notification_identity_links(
        source_system,external_subject_type,external_subject_id,local_role,local_recipient_key,verified_by,verified_at)
        VALUES(:s,:t,:id,:r,:k,:by,:at)'''),{'s':source_system,'t':subject_type,'id':str(external_id),'r':role,'k':key,'by':admin_email,'at':utcnow_iso()}).rowcount)

def ingest_partner_event(engine,event,*,authenticated_source):
    """Private adapter only; external auth/HMAC transport belongs to a future connector.

    Stable versioned event: {version:1, source_system:'GESTION_CLIENTS',event_id,
    action_no, recipient:{subject_type,subject_id,role},type:'CLIENT_UPDATE'}.
    Not a public endpoint; caller MUST establish authenticated_source externally.
    """
    if not authenticated_source or authenticated_source not in {'GESTION_CLIENTS','CONTRACTUALISATION'}:
        raise PermissionError('Connecteur authentifié requis.')
    if not isinstance(event,dict) or event.get('version')!=1 or event.get('source_system')!=authenticated_source:
        raise ValueError('Contrat d’événement non conforme.')
    if event.get('type') not in {'CLIENT_UPDATE','MISSION_ASSIGNED'}:
        raise ValueError('Nature événement non autorisée.')
    ext=str(event.get('event_id') or '').strip()
    if not ext or len(ext)>140:raise ValueError('Référence événement invalide.')
    recipient=event.get('recipient') or {}
    mapped=one(engine,'''SELECT local_role,local_recipient_key FROM external_notification_identity_links
        WHERE source_system=:s AND external_subject_type=:t AND external_subject_id=:i AND local_role=:r AND revoked_at IS NULL''',
        {'s':authenticated_source,'t':str(recipient.get('subject_type') or ''),'i':str(recipient.get('subject_id') or ''),'r':str(recipient.get('role') or '')})
    if not mapped:return False
    action=one(engine,'SELECT id FROM actions WHERE action_no=:n',{'n':str(event.get('action_no') or '')})
    if not action:return False
    return enqueue(engine,source_system=authenticated_source,source_event_id=ext,recipient_role=mapped['local_role'],recipient_key=mapped['local_recipient_key'],action_id=action['id'],event_code=event['type'],category='INFO' if event['type']=='CLIENT_UPDATE' else 'ACTION',target_kind='ACTION' if event['type']=='CLIENT_UPDATE' else 'MISSION',target_id=action['id'],display_text='Mise à jour de votre dossier' if event['type']=='CLIENT_UPDATE' else 'Nouvelle mission à consulter')