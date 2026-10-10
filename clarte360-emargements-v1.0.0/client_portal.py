"""P4: espace Client/DRH, habilitations explicites et cloisonnement documentaire.

Le CRM-0 est le référentiel transitoire des contacts. Ce module ne crée ni
nouveau fichier client maître, ni facture, ni prescripteur financier. Les
rattachements GDA sont des AUTORISATIONS, jamais une réplique du CRM n°17.
"""
from __future__ import annotations

import hashlib
import io
import json
import secrets
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text

from db import audit, execute, one, q, utcnow_iso
from persistent_session import revoke_subject_sessions
from security import hash_password, verify_password

ROLES = frozenset(('CLIENT_ADMIN', 'PRESCRIPTEUR'))
CLIENT_CATEGORIES = frozenset(('JUSTIFICATIF_CLIENT', 'ATTESTATION_CLIENT', 'DOCUMENT_CLIENT_RECU'))
DOC_SHAREABLE_CATEGORIES = frozenset(('JUSTIFICATIF_CLIENT', 'ATTESTATION_CLIENT'))
UPLOAD_EXTENSIONS = frozenset(('.pdf', '.docx', '.xlsx', '.txt', '.csv', '.png', '.jpg', '.jpeg'))
MIN_AGGREGATE = 5


def _admin(engine, email):
    if not email or not one(engine, 'SELECT id FROM admins WHERE lower(email)=lower(:e) AND active=1', {'e':str(email)}):
        raise PermissionError('Opération réservée à une administration active.')


def _ident(engine, account_id, *, activated=True):
    acc=one(engine, '''SELECT cp.*,c.public_id crm_public_id,c.first_name,c.last_name,c.email crm_email,
        c.company,c.status crm_status
        FROM client_portal_accounts cp JOIN crm_contacts c ON c.id=cp.crm_contact_id
        WHERE cp.id=:i AND cp.active=1''', {'i':account_id})
    if not acc or acc['email'].strip().lower()!=str(acc['crm_email']).strip().lower():
        raise PermissionError('Compte Client indisponible ou informations de contact à actualiser.')
    if str(acc.get('crm_status') or '').strip().upper() in ('ARCHIVE', 'ARCHIVÉ', 'ARCHIVED'):
        raise PermissionError('Contact CRM archivé : accès Client suspendu.')
    if activated and not acc.get('password_hash'):
        raise PermissionError('Espace Client non activé.')
    return acc


def _action(engine, action_id):
    a=one(engine, 'SELECT id,action_no,title,status,nature,prestation_type,start_date,end_date,mode,location,client_name,archived_at FROM actions WHERE id=:a', {'a':action_id})
    if not a: raise ValueError('Action introuvable.')
    return a


def _is_individual_action(a):
    # En cas de doute, aucune donnée d'assiduité ou de contenu de BC n'est exposée.
    kind=' '.join(str(a.get(field) or '') for field in ('nature', 'prestation_type')).upper()
    return any(w in kind for w in ('BILAN','COACH','ACCOMPAGNEMENT','INDIVIDUEL'))


def create_client_portal_account(engine, crm_contact_id, actor):
    """Un compte de connexion lié à un contact CRM, sans dupliquer sa fiche métier."""
    _admin(engine,actor)
    c=one(engine,'SELECT * FROM crm_contacts WHERE id=:c',{'c':crm_contact_id})
    if not c:raise ValueError('Sélectionnez un contact du CRM existant.')
    if str(c.get('status') or '').strip().upper() in ('ARCHIVE', 'ARCHIVÉ', 'ARCHIVED'):
        raise PermissionError('Un contact CRM archivé ne peut pas recevoir un compte Client actif.')
    email=str(c.get('email') or '').strip().lower()
    if '@' not in email or len(email)>254:raise ValueError('Contact CRM sans adresse e-mail valable.')
    existing=one(engine,'SELECT * FROM client_portal_accounts WHERE crm_contact_id=:c',{'c':crm_contact_id})
    if existing:
        if existing['email']!=email:raise ValueError('E-mail modifié dans le CRM : mise à jour de l’accès à arbitrer par un administrateur.')
        return existing['id']
    by_email=one(engine,'SELECT id FROM client_portal_accounts WHERE email=:e',{'e':email})
    if by_email:raise ValueError('Cet e-mail dispose déjà d’un accès Client lié à un autre contact CRM.')
    now=utcnow_iso()
    account_id=execute(engine,'''INSERT INTO client_portal_accounts(crm_contact_id,email,active,created_at,updated_at)
        VALUES(:c,:e,1,:t,:t)''',{'c':crm_contact_id,'e':email,'t':now})
    audit(engine,'CLIENT_PORTAL_ACCOUNT_CREATED',actor=actor,entity_type='client_portal_account',entity_id=account_id,
          details={'crm_contact_id':crm_contact_id,'without_action_rights':True})
    return account_id


def list_client_accounts_admin(engine,actor):
    _admin(engine,actor)
    return q(engine,'''SELECT cp.id,cp.crm_contact_id,cp.email,cp.active,cp.password_hash IS NOT NULL AS activated,
            c.public_id,c.first_name,c.last_name,c.company
        FROM client_portal_accounts cp JOIN crm_contacts c ON c.id=cp.crm_contact_id
        ORDER BY cp.id DESC''')


def set_client_account_active(engine,account_id,active,actor):
    _admin(engine,actor)
    acc=one(engine,'SELECT id,active FROM client_portal_accounts WHERE id=:i',{'i':account_id})
    if not acc:raise ValueError('Compte Client introuvable.')
    execute(engine,'UPDATE client_portal_accounts SET active=:v,updated_at=:t WHERE id=:i',
            {'v':1 if active else 0,'t':utcnow_iso(),'i':account_id})
    if not active:
        # La réactivation du compte ne ressuscite aucune habilitation antérieure.
        now=utcnow_iso()
        execute(engine,'UPDATE client_action_grants SET revoked_at=:n WHERE account_id=:i AND revoked_at IS NULL',
                {'n':now,'i':account_id})
        execute(engine,'UPDATE client_document_shares SET revoked_at=:n WHERE account_id=:i AND revoked_at IS NULL',
                {'n':now,'i':account_id})
        revoke_subject_sessions(engine,'CLIENT',account_id)
    audit(engine,'CLIENT_PORTAL_ACCOUNT_ACTIVE_CHANGED',actor=actor,entity_type='client_portal_account',entity_id=account_id,
          details={'active':bool(active)})


def reconcile_client_contact_email(engine,account_id,actor):
    """Après changement d'e-mail CRM, exiger une nouvelle invitation ET des droits nouveaux."""
    _admin(engine,actor)
    acc=one(engine,'''SELECT cp.id,cp.email,c.email crm_email FROM client_portal_accounts cp
                    JOIN crm_contacts c ON c.id=cp.crm_contact_id WHERE cp.id=:i''',{'i':account_id})
    if not acc:raise ValueError('Compte Client introuvable.')
    email=str(acc['crm_email'] or '').strip().lower()
    if '@' not in email or len(email)>254:raise ValueError('E-mail CRM invalide.')
    conflict=one(engine,'SELECT id FROM client_portal_accounts WHERE email=:e AND id<>:i',{'e':email,'i':account_id})
    if conflict:raise ValueError('Cette adresse appartient déjà à un autre accès Client.')
    now=utcnow_iso()
    with engine.begin() as db:
        db.execute(text('UPDATE client_portal_accounts SET email=:e,password_hash=NULL,updated_at=:n WHERE id=:i'),
                   {'e':email,'n':now,'i':account_id})
        db.execute(text('UPDATE client_portal_tokens SET used_at=:n WHERE account_id=:i AND used_at IS NULL'),
                   {'n':now,'i':account_id})
        db.execute(text('UPDATE client_action_grants SET revoked_at=:n WHERE account_id=:i AND revoked_at IS NULL'),
                   {'n':now,'i':account_id})
        db.execute(text('UPDATE client_document_shares SET revoked_at=:n WHERE account_id=:i AND revoked_at IS NULL'),
                   {'n':now,'i':account_id})
    revoke_subject_sessions(engine,'CLIENT',account_id)
    audit(engine,'CLIENT_PORTAL_CRM_EMAIL_RECONCILED',actor=actor,entity_type='client_portal_account',entity_id=account_id,
          details={'requires_new_invitation':True,'requires_new_grants':True})
    return email


def issue_client_access_token(engine,account_id,actor,kind='INVITE',ttl_hours=72):
    """Le jeton brut n'est jamais stocké; son partage reste manuel/contrôlé."""
    _admin(engine,actor)
    kind=str(kind or '').upper()
    if kind not in ('INVITE','RESET'):raise ValueError('Type de jeton non autorisé.')
    _ident(engine,account_id,activated=False)
    ttl=max(1,min(168,int(ttl_hours)))
    token=secrets.token_urlsafe(32)
    digest=hashlib.sha256(token.encode()).hexdigest()
    expires=(datetime.now(timezone.utc)+timedelta(hours=ttl)).isoformat()
    now=utcnow_iso()
    with engine.begin() as db:
        db.execute(text('UPDATE client_portal_tokens SET used_at=:n WHERE account_id=:i AND used_at IS NULL'),{'n':now,'i':account_id})
        db.execute(text('''INSERT INTO client_portal_tokens(account_id,token_hash,token_kind,expires_at,created_at)
            VALUES(:i,:h,:k,:e,:n)'''),{'i':account_id,'h':digest,'k':kind,'e':expires,'n':now})
        if kind=='RESET':
            db.execute(text('UPDATE client_portal_accounts SET password_hash=NULL,updated_at=:n WHERE id=:i'),{'n':now,'i':account_id})
    revoke_subject_sessions(engine,'CLIENT',account_id)
    audit(engine,'CLIENT_PORTAL_ACCESS_TOKEN_ISSUED',actor=actor,entity_type='client_portal_account',entity_id=account_id,
          details={'kind':kind,'ttl_hours':ttl})
    return token


def redeem_client_access_token(engine,token,password):
    """Consommation atomique d'un jeton, révocation des sessions précédentes."""
    if len(str(password or ''))<12:raise ValueError('Choisissez un mot de passe d’au moins 12 caractères.')
    digest=hashlib.sha256(str(token or '').encode()).hexdigest()
    now=datetime.now(timezone.utc)
    with engine.begin() as db:
        row=db.execute(text('''SELECT t.id,t.account_id,t.expires_at,t.used_at,cp.active,cp.email,c.email crm_email
            FROM client_portal_tokens t JOIN client_portal_accounts cp ON cp.id=t.account_id
            JOIN crm_contacts c ON c.id=cp.crm_contact_id
            WHERE t.token_hash=:h'''),{'h':digest}).mappings().first()
        if not row or row['used_at'] or not row['active'] or str(row['email']).lower()!=str(row['crm_email']).lower():
            raise ValueError('Lien non valide ou déjà utilisé.')
        try:expiry=datetime.fromisoformat(row['expires_at'])
        except (ValueError,TypeError):raise ValueError('Lien non valide ou expiré.')
        if expiry.tzinfo is None:expiry=expiry.replace(tzinfo=timezone.utc)
        if now>=expiry:raise ValueError('Lien non valide ou expiré.')
        updated=db.execute(text('UPDATE client_portal_tokens SET used_at=:n WHERE id=:i AND used_at IS NULL'),
                           {'n':now.isoformat(),'i':row['id']}).rowcount
        if updated!=1:raise ValueError('Lien déjà utilisé.')
        db.execute(text('UPDATE client_portal_accounts SET password_hash=:p,updated_at=:n WHERE id=:i'),
                   {'p':hash_password(password),'n':now.isoformat(),'i':row['account_id']})
        db.execute(text('UPDATE client_portal_tokens SET used_at=:n WHERE account_id=:i AND used_at IS NULL'),
                   {'n':now.isoformat(),'i':row['account_id']})
    revoke_subject_sessions(engine,'CLIENT',row['account_id'])
    audit(engine,'CLIENT_PORTAL_PASSWORD_ACTIVATED',actor='client_portal',entity_type='client_portal_account',entity_id=row['account_id'],
          details={'token_kind':'INVITE_OR_RESET'})
    return int(row['account_id'])


def verify_client_login(engine,email,password):
    """PBKDF2 et limite de 5 échecs par 15 min; empreinte d'e-mail au stockage."""
    normalized=str(email or '').strip().lower()
    if not normalized or not password or len(normalized)>254:return None
    eh=hashlib.sha256(normalized.encode()).hexdigest()
    now=datetime.now(timezone.utc)
    row=one(engine,'SELECT * FROM client_login_attempts WHERE email_hash=:h',{'h':eh})
    if row and row.get('locked_until'):
        try:locked=datetime.fromisoformat(row['locked_until'])
        except (ValueError,TypeError):locked=now
        if locked.tzinfo is None:locked=locked.replace(tzinfo=timezone.utc)
        if now<locked:return None
    acc=one(engine,'SELECT id,password_hash,active FROM client_portal_accounts WHERE email=:e',{'e':normalized})
    current=None
    if acc and acc['active'] and acc.get('password_hash'):
        try:current=_ident(engine,acc['id'])
        except PermissionError:pass
    if current and verify_password(password,current['password_hash']):
        execute(engine,'DELETE FROM client_login_attempts WHERE email_hash=:h',{'h':eh})
        execute(engine,'UPDATE client_portal_accounts SET last_login_at=:t WHERE id=:i',{'t':utcnow_iso(),'i':acc['id']})
        return current
    first=now
    if row and row.get('last_failed_at'):
        try:first=datetime.fromisoformat(row['last_failed_at'])
        except (ValueError,TypeError):first=now
        if first.tzinfo is None:first=first.replace(tzinfo=timezone.utc)
    old_count=int(row.get('failed_count') or 0) if row and (now-first).total_seconds()<900 else 0
    count=old_count+1
    until=(now+timedelta(minutes=15)).isoformat() if count>=5 else None
    if row:
        execute(engine,'''UPDATE client_login_attempts SET failed_count=:n,last_failed_at=:t,locked_until=:u
                    WHERE email_hash=:h''',{'n':count,'t':now.isoformat(),'u':until,'h':eh})
    else:
        execute(engine,'''INSERT INTO client_login_attempts(email_hash,failed_count,last_failed_at,locked_until)
                VALUES(:h,:n,:t,:u)''',{'h':eh,'n':count,'t':now.isoformat(),'u':until})
    return None


def client_portal_identity(engine,account_id):
    return _ident(engine,account_id)


def grant_client_action(engine,account_id,action_id,actor,role='PRESCRIPTEUR',*,can_download=False,can_upload=False):
    _admin(engine,actor)
    _ident(engine,account_id,activated=False)
    action=_action(engine,action_id)
    if _is_individual_action(action) and (can_download or can_upload):
        raise PermissionError('Aucun accès documentaire Client aux bilans ou coachings individuels par le portail P4.')
    role=str(role).strip().upper()
    if role not in ROLES:raise ValueError('Rôle Client non reconnu.')
    now=utcnow_iso()
    current=one(engine,'SELECT id FROM client_action_grants WHERE account_id=:c AND action_id=:a',{'c':account_id,'a':action_id})
    params={'c':account_id,'a':action_id,'r':role,'d':int(bool(can_download)),'u':int(bool(can_upload)),'n':now,'by':actor}
    if current:
        execute(engine,'''UPDATE client_action_grants SET role=:r,can_download=:d,can_upload=:u,
          revoked_at=NULL,granted_by=:by,granted_at=:n WHERE account_id=:c AND action_id=:a''',params)
    else:
        execute(engine,'''INSERT INTO client_action_grants(account_id,action_id,role,can_download,can_upload,granted_by,granted_at)
          VALUES(:c,:a,:r,:d,:u,:by,:n)''',params)
    audit(engine,'CLIENT_ACTION_ACCESS_GRANTED',action_id,actor,'client_portal_account',account_id,
          {'role':role,'download':bool(can_download),'upload':bool(can_upload)})


def revoke_client_action(engine,account_id,action_id,actor):
    _admin(engine,actor)
    execute(engine,'''UPDATE client_action_grants SET revoked_at=COALESCE(revoked_at,:n),can_download=0,can_upload=0
           WHERE account_id=:c AND action_id=:a AND revoked_at IS NULL''',
            {'n':utcnow_iso(),'c':account_id,'a':action_id})
    # Revoking and re-granting the action must not silently revive document shares.
    execute(engine,'''UPDATE client_document_shares SET revoked_at=:n
       WHERE account_id=:c AND revoked_at IS NULL AND document_reference_id IN
         (SELECT id FROM document_references WHERE action_id=:a)''',
       {'n':utcnow_iso(),'c':account_id,'a':action_id})
    audit(engine,'CLIENT_ACTION_ACCESS_REVOKED',action_id,actor,'client_portal_account',account_id,{})


def client_action_permission(engine,account_id,action_id,permission='view'):
    """Tous les appels métier revérifient le compte, le contact CRM et l'action."""
    _ident(engine,account_id)
    a=_action(engine,action_id)
    grant=one(engine,'''SELECT role,can_download,can_upload,granted_at FROM client_action_grants
           WHERE account_id=:c AND action_id=:a AND revoked_at IS NULL''',{'c':account_id,'a':action_id})
    if not grant:raise PermissionError('Action non autorisée pour cet Espace Client.')
    permission=str(permission or '').lower()
    # P5: la nature peut changer apres l'attribution d'une autorisation.
    # Protection fail-closed pour les documents des bilans et coachings.
    if permission in ('download','upload') and _is_individual_action(a):
        raise PermissionError('Aucun acces documentaire Client pour une action individuelle.')
    if permission=='download' and not grant['can_download']:raise PermissionError('Téléchargement non autorisé.')
    if permission=='upload' and not grant['can_upload']:raise PermissionError('Dépôt non autorisé.')
    return a,grant


def list_client_actions(engine,account_id):
    _ident(engine,account_id)
    return q(engine,'''SELECT a.id,a.action_no,a.title,a.status,a.nature,a.prestation_type,
            a.start_date,a.end_date,a.mode,ca.role,ca.can_download,ca.can_upload
        FROM client_action_grants ca JOIN actions a ON a.id=ca.action_id
        WHERE ca.account_id=:c AND ca.revoked_at IS NULL ORDER BY a.start_date DESC,a.id DESC''',{'c':account_id})


def client_action_summary(engine,account_id,action_id):
    """Métadonnées administratives seulement ; jamais noms, réponses, profils ou scores individuels."""
    a,grant=client_action_permission(engine,account_id,action_id)
    result={k:a.get(k) for k in ('id','action_no','title','status','nature','prestation_type','start_date','end_date','mode','location')}
    result['role']=grant['role']
    result['can_download']=bool(grant['can_download'])
    result['can_upload']=bool(grant['can_upload'])
    result['collective_training']=False
    if not _is_individual_action(a) and str(a.get('prestation_type') or '').upper()=='FORMATION':
        total=one(engine,'SELECT COUNT(*) n FROM participants WHERE action_id=:a AND active=1',{'a':action_id})['n']
        if total>=MIN_AGGREGATE:
            result['collective_training']=True
            result['participants_count']=total
            result['sessions_count']=one(engine,"SELECT COUNT(*) n FROM slots WHERE action_id=:a AND COALESCE(status,'')<>'ANNULE'",{'a':action_id})['n']
    return result


def client_public_schedule(engine,account_id,action_id):
    summary=client_action_summary(engine,account_id,action_id)
    if not summary['collective_training']:return []
    return q(engine,'''SELECT slot_date,start_time,end_time,status FROM slots
        WHERE action_id=:a AND COALESCE(status,'')<>'ANNULE'
        ORDER BY slot_date,start_time,id''',{'a':action_id})


def list_admin_client_grants(engine,actor,action_id=None):
    _admin(engine,actor)
    clause='AND g.action_id=:a' if action_id is not None else ''
    args={'a':action_id} if action_id is not None else {}
    return q(engine,f'''SELECT g.account_id,g.action_id,g.role,g.can_download,g.can_upload,g.revoked_at,
         a.action_no,a.title,c.email,c.crm_contact_id,cc.company
         FROM client_action_grants g JOIN actions a ON a.id=g.action_id
         JOIN client_portal_accounts c ON c.id=g.account_id
         JOIN crm_contacts cc ON cc.id=c.crm_contact_id
         WHERE 1=1 {clause} ORDER BY a.id DESC,g.account_id''',args)


def _approved_client_document(engine,reference_id,action_id):
    d=one(engine,'''SELECT dr.*,sf.storage_path,sf.sha256,sf.mime_type,sf.size_bytes
        FROM document_references dr JOIN stored_files sf ON sf.id=dr.stored_file_id
        WHERE dr.id=:i AND dr.action_id=:a''',{'i':reference_id,'a':action_id})
    if not d:raise PermissionError('Document non autorisé dans cette action.')
    if d.get('beneficiary_id') is not None or d.get('participant_id') is not None:
        raise PermissionError('Un document individuel ne peut pas être transmis au client.')
    if d.get('audience')!='CLIENT_ONLY' or str(d.get('category') or '').upper() not in CLIENT_CATEGORIES:
        raise PermissionError('Document ne relevant pas de l’Espace Client.')
    return d


def create_client_delivery(engine,action_id,data,display_name,admin_email,category='JUSTIFICATIF_CLIENT',revision_reason=None):
    """Dépôt administratif en brouillon, à VALIDER puis PUBLIER puis PARTAGER."""
    _admin(engine,admin_email)
    a=_action(engine,action_id)
    if _is_individual_action(a):raise PermissionError('Aucune livraison individuelle de bilan ou coaching à un tiers depuis P4.')
    category=str(category or '').upper()
    if category not in DOC_SHAREABLE_CATEGORIES:raise ValueError('Catégorie de remise Client non autorisée.')
    from services import store_document
    return store_document(engine,data,display_name,category,admin_email,action_id=action_id,
        audience='CLIENT_ONLY',visible_to_beneficiary=False,publish=False,
        revision_reason=revision_reason,allowed_extensions=UPLOAD_EXTENSIONS)


def share_client_document(engine,reference_id,account_id,admin_email):
    _admin(engine,admin_email)
    d=one(engine,'SELECT action_id FROM document_references WHERE id=:i',{'i':reference_id})
    if not d:raise ValueError('Document introuvable.')
    client_action_permission(engine,account_id,d['action_id'],'download')
    ref=_approved_client_document(engine,reference_id,d['action_id'])
    if str(ref.get('category')).upper() not in DOC_SHAREABLE_CATEGORIES:
        raise PermissionError('Ce document reçu d’un client n’est pas un justificatif à diffuser.')
    if ref.get('deleted_at') or ref.get('publication_status')!='PUBLIE' or ref.get('validation_status') not in ('VALIDE','FINALISE'):
        raise PermissionError('Le document doit être validé ET publié avant sa transmission.')
    if ref.get('superseded_at') and ref.get('publication_status')!='PUBLIE':
        raise PermissionError('Version remplacée.')
    # L'ancienne version reçue par un Client demeure visible jusqu'au partage
    # EXPLICITE de la suivante. Lors d'un nouveau partage, retirer l'ancienne.

    now=utcnow_iso()
    old=one(engine,'SELECT id FROM client_document_shares WHERE document_reference_id=:d AND account_id=:c',{'d':reference_id,'c':account_id})
    if ref.get('logical_key'):
        execute(engine,'''UPDATE client_document_shares SET revoked_at=:n
          WHERE account_id=:c AND document_reference_id<>:r AND revoked_at IS NULL
            AND document_reference_id IN
              (SELECT id FROM document_references WHERE logical_key=:k AND action_id=:a)''',
          {'n':now,'c':account_id,'r':reference_id,'k':ref['logical_key'],'a':d['action_id']})
    if old:
        execute(engine,'UPDATE client_document_shares SET revoked_at=NULL,published_at=:n,published_by=:by WHERE id=:i',
                {'i':old['id'],'n':now,'by':admin_email})
    else:
        execute(engine,'''INSERT INTO client_document_shares(document_reference_id,account_id,published_at,published_by)
                  VALUES(:d,:c,:n,:by)''',{'d':reference_id,'c':account_id,'n':now,'by':admin_email})
    audit(engine,'CLIENT_DOCUMENT_SHARED',d['action_id'],admin_email,'document_reference',reference_id,
          {'client_portal_account_id':account_id})


def list_admin_client_document_shares(engine,reference_id,admin_email):
    _admin(engine,admin_email)
    ref=one(engine,'SELECT id FROM document_references WHERE id=:i',{'i':reference_id})
    if not ref:raise ValueError('Référence documentaire introuvable.')
    return q(engine,'''SELECT sh.account_id,sh.published_at,sh.revoked_at,cp.email
       FROM client_document_shares sh JOIN client_portal_accounts cp ON cp.id=sh.account_id
       WHERE sh.document_reference_id=:d ORDER BY sh.published_at DESC,sh.account_id''',{'d':reference_id})


def revoke_client_document(engine,reference_id,account_id,admin_email):
    _admin(engine,admin_email)
    d=one(engine,'SELECT action_id FROM document_references WHERE id=:i',{'i':reference_id})
    execute(engine,'UPDATE client_document_shares SET revoked_at=:n WHERE document_reference_id=:d AND account_id=:c AND revoked_at IS NULL',
            {'n':utcnow_iso(),'d':reference_id,'c':account_id})
    audit(engine,'CLIENT_DOCUMENT_ACCESS_REVOKED',d.get('action_id') if d else None,admin_email,'document_reference',reference_id,
          {'client_portal_account_id':account_id})


def list_client_documents(engine,account_id,action_id):
    client_action_permission(engine,account_id,action_id,'download')
    rows=q(engine,'''SELECT dr.id,dr.action_id,dr.category,dr.audience,dr.display_name,dr.created_at,
          dr.published_at,dr.validation_status,dr.publication_status,dr.version_no,
          dr.beneficiary_id,dr.participant_id,dr.deleted_at,dr.superseded_at,
          sf.mime_type,sf.sha256,sf.size_bytes,sf.storage_path
          FROM client_document_shares sh JOIN document_references dr ON dr.id=sh.document_reference_id
          JOIN stored_files sf ON sf.id=dr.stored_file_id
          WHERE sh.account_id=:c AND sh.revoked_at IS NULL AND dr.action_id=:a
          AND dr.deleted_at IS NULL AND dr.audience='CLIENT_ONLY'
          AND dr.beneficiary_id IS NULL AND dr.participant_id IS NULL
          AND dr.publication_status IN ('PUBLIE','REMPLACE') AND dr.validation_status IN ('VALIDE','FINALISE')
          ORDER BY dr.published_at DESC,dr.id DESC''',{'c':account_id,'a':action_id})
    return [d for d in rows if str(d['category']).upper() in DOC_SHAREABLE_CATEGORIES]


def read_client_document(engine,reference_id,account_id,action_id):
    allowed={d['id']:d for d in list_client_documents(engine,account_id,action_id)}
    d=allowed.get(reference_id)
    if not d:raise PermissionError('Document non partagé avec ce compte.')
    path=Path(d['storage_path'])
    if not path.is_file():raise FileNotFoundError('Fichier indisponible.')
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=d['sha256']:
        raise ValueError('Intégrité documentaire non vérifiée.')
    audit(engine,'CLIENT_DOCUMENT_DOWNLOADED',action_id,f'client_portal:{account_id}',
          'document_reference',reference_id,{'bytes':len(data)})
    return data


def export_client_action_zip(engine,account_id,action_id):
    client_action_permission(engine,account_id,action_id,'download')
    docs=list_client_documents(engine,account_id,action_id)
    buf=io.BytesIO(); manifest=[]
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        for d in docs:
            # Aucun nom brut n'est utilisé comme chemin interne ; les métadonnées restent dans le manifeste.
            ext=Path(d['display_name']).suffix.lower()
            if ext not in UPLOAD_EXTENSIONS:ext='.bin'
            name=f"documents/document_{d['id']}_v{int(d.get('version_no') or 1)}{ext}"
            data=read_client_document(engine,d['id'],account_id,action_id)
            z.writestr(name,data)
            manifest.append({'reference_id':d['id'],'file':name,'sha256':d['sha256'],'version':d.get('version_no') or 1,
                             'category':d['category'],'source':'GDA_CLIENT_P4'})
        z.writestr('manifest.json',json.dumps({'action_id':action_id,'documents':manifest},ensure_ascii=False,indent=2))
    audit(engine,'CLIENT_DOCUMENTS_ZIP_EXPORTED',action_id,str(account_id),'client_portal_account',account_id,
          {'count':len(manifest)})
    return buf.getvalue()


def client_upload_document(engine,account_id,action_id,data,display_name):
    """Un dépôt du client reste brouillon interne tant que l'admin ne le valide pas."""
    a,grant=client_action_permission(engine,account_id,action_id,'upload')
    if _is_individual_action(a):raise PermissionError('Dépôt client indisponible pour cette action individuelle.')
    from services import store_document
    r=store_document(engine,data,display_name,'DOCUMENT_CLIENT_RECU',f'client_portal:{account_id}',
        action_id=action_id,audience='CLIENT_ONLY',visible_to_beneficiary=False,
        publish=False,allowed_extensions=UPLOAD_EXTENSIONS,max_file_mb=10,
        logical_namespace=f'CLIENT_ACCOUNT:{account_id}')
    audit(engine,'CLIENT_DOCUMENT_RECEIVED',action_id,f'client_portal:{account_id}','document_reference',r[0],
          {'publication':'BROUILLON','size':len(data)})
    return r


def list_client_submissions(engine,account_id,action_id):
    action,_=client_action_permission(engine,account_id,action_id)
    if _is_individual_action(action):
        raise PermissionError('Aucun acces documentaire Client pour une action individuelle.')
    return q(engine,'''SELECT id,display_name,created_at,publication_status,validation_status
       FROM document_references WHERE action_id=:a AND uploaded_by=:by AND category='DOCUMENT_CLIENT_RECU'
         AND deleted_at IS NULL ORDER BY id DESC''',{'a':action_id,'by':f'client_portal:{account_id}'})


def client_go14_contract_snapshot():
    """Documente une frontière, n'ouvre PAS GO-14 ni l'accès à Compétences & Projets."""
    return {'identity_source':'CRM17_TARGET_CRM0_TEMP','action_source':'GDA','client_scope':'EXPLICIT_PER_ACTION',
      'document_scope':'EXPLICIT_PER_ACCOUNT','password_owner':'GDA_PORTAL_TRANSITION',
      'tool_connector':'UNCHANGED_GENERIC_HUB','competences_projets_go14':'NOT_OPEN'}
