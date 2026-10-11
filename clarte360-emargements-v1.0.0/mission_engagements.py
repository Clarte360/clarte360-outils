"""P5-RC2 / J8 - Mission coverage and evidence references (NOT a contract factory).

GDA owns operational assignments. Contractualisation 13 owns document workflows;
Gestion Clients 17 owns suppliers, financial commitments, invoices and payments.
The outbox is a versioned interface proposal, NOT a live API sender.
"""
from __future__ import annotations
import json
import uuid
from sqlalchemy import text
from db import q, one, audit, utcnow_iso

MISSION_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS action_mission_policy (
      action_id INTEGER PRIMARY KEY, control_mode TEXT NOT NULL DEFAULT 'PREVIEW',
      enabled_by TEXT, enabled_at TEXT NOT NULL,
      CHECK(control_mode IN ('PREVIEW','ENFORCE')),
      FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE)""",
    """CREATE TABLE IF NOT EXISTS action_mission_engagements (
      mission_id TEXT PRIMARY KEY, action_id INTEGER NOT NULL, trainer_id INTEGER NOT NULL,
      professional_person_id TEXT, supplier_id TEXT, contract_kind TEXT NOT NULL DEFAULT 'A_DEFINIR',
      role TEXT NOT NULL DEFAULT 'INTERVENANT', is_followup_responsible INTEGER NOT NULL DEFAULT 0,
      mission_description TEXT NOT NULL DEFAULT '', period_start TEXT, period_end TEXT,
      status TEXT NOT NULL DEFAULT 'A_PREPARER', active INTEGER NOT NULL DEFAULT 1,
      document_ref TEXT, document_version TEXT, accepted_at TEXT, checked_by TEXT,
      external_contract_ref TEXT, cost_commitment_ref TEXT, revised_from TEXT,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      CHECK(status IN ('A_PREPARER','DEMANDE','VERIFIE','REFUSE','ANNULE','REMPLACE')),
      CHECK(contract_kind IN ('A_DEFINIR','LETTRE_SALARIE','LETTRE_MANDATAIRE','CONTRAT_SOUS_TRAITANCE','AUTRE_A_VERIFIER')),
      CHECK(is_followup_responsible IN (0,1)),CHECK(active IN (0,1)),
      FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE,
      FOREIGN KEY(trainer_id) REFERENCES trainers(id) ON DELETE RESTRICT,
      FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT,
      FOREIGN KEY(revised_from) REFERENCES action_mission_engagements(mission_id) ON DELETE SET NULL)""",
    """CREATE TABLE IF NOT EXISTS action_mission_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT NOT NULL UNIQUE,
      mission_id TEXT NOT NULL, action_id INTEGER NOT NULL, event_type TEXT NOT NULL,
      actor TEXT NOT NULL, event_payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
      FOREIGN KEY(mission_id) REFERENCES action_mission_engagements(mission_id) ON DELETE CASCADE,
      FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE)""",
    """CREATE TABLE IF NOT EXISTS action_mission_outbox (
      event_key TEXT PRIMARY KEY, action_id INTEGER NOT NULL, mission_id TEXT NOT NULL,
      destination TEXT NOT NULL, interface_version TEXT NOT NULL DEFAULT 'gda.mission.v1',
      event_type TEXT NOT NULL, envelope_json TEXT NOT NULL, delivery_status TEXT NOT NULL DEFAULT 'A_RACCORDER',
      created_at TEXT NOT NULL,
      FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE,
      FOREIGN KEY(mission_id) REFERENCES action_mission_engagements(mission_id) ON DELETE CASCADE)""",
    "CREATE INDEX IF NOT EXISTS ix_j8_missions_action ON action_mission_engagements(action_id,active,status)",
    "CREATE INDEX IF NOT EXISTS ix_j8_missions_trainer ON action_mission_engagements(trainer_id,active)",
    "CREATE INDEX IF NOT EXISTS ix_j8_outbox_action ON action_mission_outbox(action_id,created_at)",
)

CONTRACT_KINDS={
    'SALARIE':'LETTRE_SALARIE',
    'MANDATAIRE_ASSOCIE':'LETTRE_MANDATAIRE',
    'SOUS_TRAITANT':'CONTRAT_SOUS_TRAITANCE',
}


def enable_action_mission_control(engine,action_id,actor,mode='ENFORCE'):
    """Opt-in for old actions. New customer-linked actions are enforced on creation."""
    if mode not in ('ENFORCE','PREVIEW'):raise ValueError('Mode de contrôle invalide.')
    if not one(engine,'SELECT id FROM admins WHERE LOWER(email)=LOWER(:e) AND active=1',{'e':str(actor or '').strip()}):
        raise PermissionError('Contrôle des missions réservé à l’administrateur actif.')
    existing=one(engine,'SELECT control_mode FROM action_mission_policy WHERE action_id=:a',{'a':action_id})
    if existing and existing['control_mode']=='ENFORCE' and mode!='ENFORCE':
        raise ValueError('Une action sous contrôle obligatoire ne peut pas revenir silencieusement en consultation.')
    with engine.begin() as conn:
        if not conn.execute(text('SELECT 1 FROM actions WHERE id=:a'),{'a':int(action_id)}).first():
            raise ValueError('Action introuvable.')
        now=utcnow_iso()
        conn.execute(text("""INSERT INTO action_mission_policy(action_id,control_mode,enabled_by,enabled_at)
          VALUES(:a,:m,:by,:n) ON CONFLICT(action_id) DO UPDATE SET
          control_mode=excluded.control_mode,enabled_by=excluded.enabled_by,enabled_at=excluded.enabled_at"""),
          {'a':int(action_id),'m':mode,'by':actor,'n':now})
    audit(engine,'J8_MISSION_CONTROL_MODE',action_id,actor,'action',action_id,{'mode':mode})
    return mode


def _mission_event(engine,mission,event_type,actor,details=None):
    """Append-only event and GC17 interface envelope; no external transmission."""
    now=utcnow_iso();event_key='gda-mission-'+uuid.uuid4().hex
    action=one(engine,'SELECT action_no,prestation_type FROM actions WHERE id=:a',{'a':mission['action_id']}) or {}
    payload={
        'format':'CLARTE360_GDA_MISSION_EVENT_V1','version':1,
        'event_id':event_key,'occurred_at':now,'event_type':event_type,
        'no_clar':action.get('action_no'),'gda_action_id':int(mission['action_id']),
        'mission_id':mission['mission_id'],'professional_person_id':mission.get('professional_person_id'),
        'supplier_id':mission.get('supplier_id'),'trainer_id':mission.get('trainer_id'),
        'role':mission.get('role'),'contract_kind':mission.get('contract_kind'),
        'engagement_status':mission.get('status'),'document_ref':mission.get('document_ref'),
        'document_version':mission.get('document_version'),
        'cost_commitment_ref':mission.get('cost_commitment_ref'),
        'contractualisation_ref':mission.get('external_contract_ref'),
        'period_start':mission.get('period_start'),'period_end':mission.get('period_end'),
        'details':details or {},
    }
    # Never place invoice amount/payment approval/individual learner details into this event.
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO action_mission_events
          (event_key,mission_id,action_id,event_type,actor,event_payload_json,created_at)
          VALUES(:k,:m,:a,:t,:by,:j,:n)"""),
          {'k':event_key,'m':mission['mission_id'],'a':mission['action_id'],'t':event_type,
           'by':actor,'j':json.dumps(details or {},ensure_ascii=False),'n':now})
        conn.execute(text("""INSERT INTO action_mission_outbox
          (event_key,action_id,mission_id,destination,event_type,envelope_json,created_at)
          VALUES(:k,:a,:m,'GESTION_CLIENTS_17',:t,:j,:n)"""),
          {'k':event_key,'a':mission['action_id'],'m':mission['mission_id'],'t':event_type,
           'j':json.dumps(payload,ensure_ascii=False,sort_keys=True),'n':now})
    return payload


def _kind_from_profile(engine,ppid):
    row=one(engine,'SELECT collaboration_type FROM professional_profiles WHERE professional_person_id=:p',{'p':ppid}) if ppid else None
    return CONTRACT_KINDS.get((row or {}).get('collaboration_type') or '', 'A_DEFINIR')


def _active_supplier(engine,ppid):
    if not ppid:return None
    row=one(engine,"""SELECT supplier_id FROM professional_supplier_links
        WHERE professional_person_id=:p AND status='ACTIVE' ORDER BY id DESC LIMIT 1""",{'p':ppid})
    return (row or {}).get('supplier_id')


def sync_mission_assignment(engine,action_id,trainer_id,actor='system',*,followup=None):
    """Idempotent projection of a real active assignment; never invent professionals."""
    at=one(engine,'SELECT * FROM action_trainers WHERE action_id=:a AND trainer_id=:t AND active=1',
           {'a':int(action_id),'t':int(trainer_id)})
    if not at:raise ValueError('Affectation active requise.')
    person=one(engine,'SELECT professional_person_id,active FROM professional_persons WHERE trainer_id=:t',{'t':trainer_id})
    ppid=(person or {}).get('professional_person_id')
    old=one(engine,"""SELECT * FROM action_mission_engagements WHERE action_id=:a AND trainer_id=:t
      AND active=1 ORDER BY created_at DESC LIMIT 1""",{'a':int(action_id),'t':int(trainer_id)})
    responsible=bool(at.get('is_referent')) if followup is None else bool(followup)
    if old:
        # A verified contract for one role is never silently reused after a role or
        # responsibility change: keep its evidence and reopen a new mission version.
        changed=(old.get('role')!=(at.get('role') or 'INTERVENANT') or
                 bool(old.get('is_followup_responsible'))!=bool(responsible))
        if changed and old['status']=='VERIFIE':
            revised=revise_mission(engine,old['mission_id'],actor,'Changement de rôle ou responsabilité de suivi')
            old=revised
        with engine.begin() as conn:
            conn.execute(text("""UPDATE action_mission_engagements SET
              role=:r,is_followup_responsible=:f,updated_at=:n
              WHERE mission_id=:m"""),{'r':at.get('role') or 'INTERVENANT','f':int(responsible),
                                   'n':utcnow_iso(),'m':old['mission_id']})
        return one(engine,'SELECT * FROM action_mission_engagements WHERE mission_id=:m',{'m':old['mission_id']})
    mid='MIS-'+uuid.uuid4().hex.upper()[:20]
    now=utcnow_iso();kind=_kind_from_profile(engine,ppid)
    supplier=_active_supplier(engine,ppid) if kind=='CONTRAT_SOUS_TRAITANCE' else None
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO action_mission_engagements
          (mission_id,action_id,trainer_id,professional_person_id,supplier_id,contract_kind,role,
          is_followup_responsible,created_at,updated_at)
          VALUES(:m,:a,:t,:p,:s,:k,:r,:f,:n,:n)"""),
          {'m':mid,'a':int(action_id),'t':int(trainer_id),'p':ppid,'s':supplier,
           'k':kind,'r':at.get('role') or 'INTERVENANT','f':int(responsible),'n':now})
    mission=one(engine,'SELECT * FROM action_mission_engagements WHERE mission_id=:m',{'m':mid})
    _mission_event(engine,mission,'MISSION_PREPARED',actor)
    return mission


def suspend_missions_for_trainer(engine,action_id,trainer_id,actor='system',reason='Retrait'):
    rows=q(engine,"""SELECT * FROM action_mission_engagements WHERE action_id=:a AND trainer_id=:t AND active=1""",
           {'a':action_id,'t':trainer_id})
    for m in rows:
        with engine.begin() as conn:
            conn.execute(text("""UPDATE action_mission_engagements SET active=0,status='REMPLACE',updated_at=:n
                WHERE mission_id=:m"""),{'m':m['mission_id'],'n':utcnow_iso()})
        new=one(engine,'SELECT * FROM action_mission_engagements WHERE mission_id=:m',{'m':m['mission_id']})
        _mission_event(engine,new,'MISSION_REPLACED',actor,{'reason':str(reason or '')[:240]})
    return len(rows)


def list_action_missions(engine,action_id,active_only=False):
    where=' AND m.active=1' if active_only else ''
    return q(engine,f"""SELECT m.*,t.full_name,pp.collaboration_type,a.action_no
      FROM action_mission_engagements m JOIN trainers t ON t.id=m.trainer_id
      JOIN actions a ON a.id=m.action_id
      LEFT JOIN professional_profiles pp ON pp.professional_person_id=m.professional_person_id
      WHERE m.action_id=:a{where} ORDER BY m.active DESC,m.is_followup_responsible DESC,m.created_at DESC""",
      {'a':int(action_id)})


def list_trainer_missions(engine,trainer_id):
    return q(engine,"""SELECT m.*,a.action_no,a.title FROM action_mission_engagements m
      JOIN actions a ON a.id=m.action_id WHERE m.trainer_id=:t
      ORDER BY m.active DESC,m.created_at DESC""",{'t':int(trainer_id)})


def verify_mission_engagement(engine,mission_id,actor,*,document_ref,document_version,
                               accepted_at,external_contract_ref=None,cost_commitment_ref=None,
                               description=None,supplier_id=None,period_start=None,period_end=None):
    """Manual administrative verification of a document already accepted elsewhere.

    This does not issue or sign a contract, and must never invent acceptance.
    Subsequent material changes require a new version/mission via amendment.
    """
    m=one(engine,'SELECT * FROM action_mission_engagements WHERE mission_id=:m',{'m':mission_id})
    if not m or not m['active']:raise ValueError('Mission absente ou remplacée.')
    action=one(engine,'SELECT status FROM actions WHERE id=:a',{'a':m['action_id']}) or {}
    if action.get('status') in ('CLOTUREE','ARCHIVEE'):
        raise ValueError('Action clôturée ou archivée : engagement non modifiable.')
    # An untrusted caller must never self-certify a contract. UI auth is not enough.
    administrator=one(engine,'SELECT id FROM admins WHERE LOWER(email)=LOWER(:e) AND active=1',{'e':str(actor or '').strip()})
    if not administrator:raise PermissionError('Contrôle d’engagement réservé à un administrateur actif.')
    a=one(engine,'SELECT * FROM action_trainers WHERE action_id=:a AND trainer_id=:t AND active=1',
          {'a':m['action_id'],'t':m['trainer_id']})
    if not a:raise ValueError('Intervenant non affecté activement.')
    if m['status']=='VERIFIE':raise ValueError('Document déjà vérifié : un avenant ou une révision est nécessaire.')
    fresh_kind=_kind_from_profile(engine,m['professional_person_id'])
    if fresh_kind=='A_DEFINIR':raise ValueError('Statut de collaboration non défini dans le dossier professionnel.')
    expected=fresh_kind
    for label,v in [('Référence du document',document_ref),('Version documentaire',document_version),('Date d’acceptation',accepted_at)]:
        if not str(v or '').strip():raise ValueError(label+' obligatoire.')
    from datetime import datetime
    try:
        accepted_date=datetime.fromisoformat(str(accepted_at).replace('Z','+00:00'))
        if accepted_date.tzinfo is None or accepted_date.utcoffset() is None:
            raise ValueError('Fuseau horaire obligatoire pour la preuve d’acceptation.')
    except ValueError as exc:raise ValueError('Date d’acceptation invalide ou sans fuseau horaire.') from exc
    if period_start and period_end and period_end<period_start:raise ValueError('Période de mission incohérente.')
    supplier=None
    if expected=='CONTRAT_SOUS_TRAITANCE':
        supplier=str(supplier_id or _active_supplier(engine,m['professional_person_id']) or '').strip()
        if not supplier:raise ValueError('Sous-traitant : fournisseur Gestion Clients n°17 requis.')
        linked={row['supplier_id'] for row in q(engine,"""SELECT supplier_id FROM professional_supplier_links
          WHERE professional_person_id=:p AND status='ACTIVE'""",{'p':m['professional_person_id']})}
        if supplier not in linked:raise ValueError('Fournisseur non lié activement au professionnel.')
    now=utcnow_iso()
    with engine.begin() as conn:
        conn.execute(text("""UPDATE action_mission_engagements SET status='VERIFIE',contract_kind=:k,
          document_ref=:d,document_version=:v,accepted_at=:acc,checked_by=:by,
          external_contract_ref=:ext,cost_commitment_ref=:cost,supplier_id=:supplier,
          mission_description=:desc,period_start=:s,period_end=:e,updated_at=:now
          WHERE mission_id=:m AND status<>'VERIFIE'"""),
          {'k':expected,'d':str(document_ref).strip()[:320],'v':str(document_version).strip()[:80],
           'acc':str(accepted_at),'by':str(actor),'ext':external_contract_ref or None,
           'cost':cost_commitment_ref or None,'supplier':supplier,
           'desc':str(description or m.get('mission_description') or '')[:1200],
           's':period_start or None,'e':period_end or None,'now':now,'m':mission_id})
    mission=one(engine,'SELECT * FROM action_mission_engagements WHERE mission_id=:m',{'m':mission_id})
    _mission_event(engine,mission,'MISSION_DOCUMENT_VERIFIED',actor,{'verification':'ADMIN_MANUAL_REFERENCE','signature_verified_by_gda':False})
    audit(engine,'J8_MISSION_ENGAGEMENT_VERIFIED',m['action_id'],actor,'mission',mission_id,
          {'document_ref':mission['document_ref'],'document_version':mission['document_version']})
    return mission


def revise_mission(engine,mission_id,actor,reason):
    """Keep the old verified proof immutable and prepare a new numbered work item."""
    if not one(engine,'SELECT id FROM admins WHERE LOWER(email)=LOWER(:e) AND active=1',{'e':str(actor or '').strip()}):
        raise PermissionError('Révision de mission réservée à l’administrateur actif.')
    old=one(engine,'SELECT * FROM action_mission_engagements WHERE mission_id=:m',{'m':mission_id})
    if not old or not old.get('active'):raise ValueError('Mission active introuvable.')
    if len(str(reason or '').strip())<5:raise ValueError('Motif de révision obligatoire.')
    now=utcnow_iso();newid='MIS-'+uuid.uuid4().hex.upper()[:20]
    with engine.begin() as conn:
        conn.execute(text("""UPDATE action_mission_engagements SET active=0,status='REMPLACE',updated_at=:n WHERE mission_id=:m"""),{'n':now,'m':mission_id})
        conn.execute(text("""INSERT INTO action_mission_engagements
            (mission_id,action_id,trainer_id,professional_person_id,supplier_id,contract_kind,
             role,is_followup_responsible,mission_description,period_start,period_end,status,active,revised_from,created_at,updated_at)
            VALUES(:m,:a,:t,:p,:s,:k,:r,:f,:d,:st,:en,'A_PREPARER',1,:old,:n,:n)"""),
            {'m':newid,'a':old['action_id'],'t':old['trainer_id'],'p':old['professional_person_id'],
             's':old['supplier_id'],'k':old['contract_kind'],'r':old['role'],
             'f':old['is_followup_responsible'],'d':old.get('mission_description') or '',
             'st':old['period_start'],'en':old['period_end'],'old':mission_id,'n':now})
    replaced=one(engine,'SELECT * FROM action_mission_engagements WHERE mission_id=:m',{'m':mission_id})
    created=one(engine,'SELECT * FROM action_mission_engagements WHERE mission_id=:m',{'m':newid})
    _mission_event(engine,replaced,'MISSION_REVISED',actor,{'replacement':newid,'reason':reason})
    _mission_event(engine,created,'MISSION_AMENDMENT_REQUESTED',actor,{'previous':mission_id,'reason':reason})
    return created


def action_mission_coverage(engine,action_id):
    policy=one(engine,'SELECT control_mode FROM action_mission_policy WHERE action_id=:a',{'a':action_id}) or {}
    mode=policy.get('control_mode') or 'PREVIEW'
    a=one(engine,'SELECT action_no,delivery_mode,status FROM actions WHERE id=:a',{'a':action_id})
    if not a:return {'mode':mode,'issues':['Action introuvable.'],'ready':False,'missions':[]}
    trainers=q(engine,"""SELECT at.trainer_id,at.is_referent,t.full_name,t.active trainer_active,
       pp.professional_person_id,pp.active professional_active
       FROM action_trainers at JOIN trainers t ON t.id=at.trainer_id
       LEFT JOIN professional_persons pp ON pp.trainer_id=t.id
       WHERE at.action_id=:a AND at.active=1""",{'a':action_id})
    missions=list_action_missions(engine,action_id,active_only=True)
    issues=[]
    # A substitute or co-intervenant assigned only to a slot must be formally
    # attached to the action before activation; no silent invented mission.
    slot_only=q(engine,"""SELECT DISTINCT st.trainer_id,t.full_name FROM slot_trainers st
      JOIN slots s ON s.id=st.slot_id JOIN trainers t ON t.id=st.trainer_id
      WHERE s.action_id=:a AND s.status NOT IN ('ANNULE','REPORTE')
      AND st.active=1 AND st.assignment_status='ACTIVE'
      AND NOT EXISTS(SELECT 1 FROM action_trainers at
        WHERE at.action_id=s.action_id AND at.trainer_id=st.trainer_id AND at.active=1)""",
      {'a':action_id})
    for missing in slot_only:
        issues.append(f"{missing['full_name']} : créneau affecté sans mission au niveau action.")
    if not trainers:issues.append('Aucun intervenant actif n’est désigné.')
    if not any(bool(t['is_referent']) and t['trainer_active'] and t.get('professional_active') for t in trainers):
        issues.append('Aucun responsable nominatif actif n’est désigné pour le suivi de cette action'+(' e-learning.' if a.get('delivery_mode')=='ELEARNING' else '.'))
    for t in trainers:
        ms=[m for m in missions if m['trainer_id']==t['trainer_id']]
        if not ms:
            issues.append(f"{t['full_name']} : mission non préparée.")
            continue
        if not t['trainer_active'] or not t.get('professional_active'):
            issues.append(f"{t['full_name']} : intervenant ou dossier professionnel inactif.")
        for m in ms:
            if m['status']!='VERIFIE' or not m.get('document_ref') or not m.get('document_version') or not m.get('accepted_at'):
                issues.append(f"{t['full_name']} : engagement non vérifié ({m['status']}).")
            if bool(m.get('is_followup_responsible')) != bool(t.get('is_referent')):
                issues.append(f"{t['full_name']} : responsabilité modifiée, avenant ou révision requise.")
            current_kind=_kind_from_profile(engine,m['professional_person_id'])
            if current_kind=='A_DEFINIR' or current_kind!=m['contract_kind']:
                issues.append(f"{t['full_name']} : statut de collaboration et type de document à recontrôler.")
            if current_kind=='CONTRAT_SOUS_TRAITANCE':
                suppliers={x['supplier_id'] for x in q(engine,"""SELECT supplier_id FROM professional_supplier_links
                     WHERE professional_person_id=:p AND status='ACTIVE'""",{'p':m['professional_person_id']})}
                if not m.get('supplier_id') or m['supplier_id'] not in suppliers:
                    issues.append(f"{t['full_name']} : référence fournisseur active requise.")
    return {'mode':mode,'issues':issues,'ready':not issues,'missions':missions,'action_no':a['action_no']}


def mission_outbox_pending(engine,action_id):
    """Read-only interface projection. Never mark transmitted, paid or approved here."""
    return [json.loads(x['envelope_json']) for x in q(engine,"""SELECT envelope_json FROM action_mission_outbox
       WHERE action_id=:a ORDER BY created_at,event_key""",{'a':action_id})]


def change_mission_status(engine,mission_id,actor,new_status,reason):
    """Track requests, refusals and cancellations without overwriting evidence."""
    allowed={'DEMANDE','REFUSE','ANNULE'}
    if new_status not in allowed:raise ValueError('Décision de mission non autorisée.')
    if len(str(reason or '').strip())<5:raise ValueError('Motif documenté obligatoire.')
    admin=one(engine,'SELECT id FROM admins WHERE LOWER(email)=LOWER(:e) AND active=1',{'e':str(actor or '').strip()})
    if not admin:raise PermissionError('Décision réservée à l’administrateur.')
    m=one(engine,'SELECT * FROM action_mission_engagements WHERE mission_id=:m',{'m':mission_id})
    if not m or not m['active']:raise ValueError('Mission absente ou inactive.')
    if m['status']=='VERIFIE' and new_status in ('DEMANDE','REFUSE'):
        raise ValueError('Engagement vérifié : conserver la preuve, créer un avenant ou annuler avec motif.')
    if m['status']==new_status:raise ValueError('Statut inchangé ; aucune transmission nouvelle.')
    now=utcnow_iso()
    with engine.begin() as conn:
        conn.execute(text('''UPDATE action_mission_engagements SET status=:s,
            active=CASE WHEN :s='ANNULE' THEN 0 ELSE active END,updated_at=:n WHERE mission_id=:m'''),
            {'s':new_status,'m':mission_id,'n':now})
    updated=one(engine,'SELECT * FROM action_mission_engagements WHERE mission_id=:m',{'m':mission_id})
    _mission_event(engine,updated,'MISSION_'+new_status,actor,{'reason':str(reason)[:700]})
    audit(engine,'J8_MISSION_STATUS_CHANGED',m['action_id'],actor,'mission',mission_id,
          {'from':m['status'],'to':new_status,'reason':str(reason)[:250]})
    return updated
