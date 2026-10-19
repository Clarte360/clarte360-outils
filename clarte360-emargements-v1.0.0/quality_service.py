"""GO4: one persistent Quality action, additive history and server permissions.

The existing quality_events row is canonical. quality_event_actions are optional
steps, never a second action to close. Public functions accept a context built by
the authenticated portal, then recheck its account and current permissions.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import mimetypes
import re
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path, PurePath

from sqlalchemy import text

from db import utcnow_iso


class ConflictError(ValueError):
    """The form's snapshot is stale; no changes have been made."""


@dataclass(frozen=True)
class QualityActor:
    role: str
    subject_id: str | int
    organization_id: int

    @property
    def key(self):
        return str(self.subject_id).strip().lower() if self.role == 'ADMIN' else str(int(self.subject_id))

    @property
    def label(self):
        return f'{self.role}:{self.key}'


STATUSES = ('NOUVEAU', 'EN_TRAITEMENT', 'EN_ATTENTE', 'A_VERIFIER', 'CLOTURE')
FINAL = frozenset(('CLOTURE', 'CLASSE_SANS_SUITE', 'REFUSE'))
NATURES = ('PREVENTIVE', 'CORRECTIVE', 'AMELIORATION')
CLASSIFICATIONS = ('REAL', 'TEST', 'A_EXAMINER')
ORIGINS = ('INTERNE', 'PREVENTION', 'RECLAMATION', 'SIGNALEMENT', 'DIFFICULTE',
           'AUDIT_INTERNE', 'AUDIT_EXTERNE', 'QUESTIONNAIRE', 'VEILLE',
           'SIGNALEMENT_INTERVENANT', 'SIGNALEMENT_BENEFICIAIRE', 'DEMANDE_CLIENT', 'LEGACY')
LEGACY_ATTACHMENT_ROOT = Path(__file__).resolve().parent / 'data' / 'trainer_reports'


def _rows(conn, sql, params=None):
    return [dict(r) for r in conn.execute(text(sql), params or {}).mappings().all()]


def _one(conn, sql, params=None):
    row = conn.execute(text(sql), params or {}).mappings().first()
    return dict(row) if row else None


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def init_quality_schema(conn):
    """Add columns/tables only; no rewrite, purge, inferred author or classification."""
    additions = {
        'quality_events': {
            'row_version': 'INTEGER NOT NULL DEFAULT 1', 'go4_managed': 'INTEGER NOT NULL DEFAULT 0',
            'action_nature': "TEXT NOT NULL DEFAULT 'AMELIORATION'",
            'data_classification': "TEXT NOT NULL DEFAULT 'A_EXAMINER'",
            'requester_role': 'TEXT', 'requester_id': 'TEXT', 'assigned_role': 'TEXT',
            'assigned_id': 'TEXT', 'delegation_status': 'TEXT', 'expected_result': 'TEXT',
            'sensitivity': "TEXT NOT NULL DEFAULT 'NORMAL'", 'retention_until': 'TEXT',
            'deleted_at': 'TEXT',
        },
        'quality_event_history': {'audience': "TEXT NOT NULL DEFAULT 'INTERNAL'"},
        'quality_event_messages': {'audience': "TEXT NOT NULL DEFAULT 'INTERNAL'", 'command_id': 'TEXT'},
    }
    for table, columns in additions.items():
        present = {r['name'] for r in _rows(conn, f'PRAGMA table_info({table})')}
        for name, definition in columns.items():
            if name not in present:
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {definition}'))
    statements = [
        '''CREATE TABLE IF NOT EXISTS quality_commands (
          organization_id INTEGER NOT NULL, actor_key TEXT NOT NULL, command_id TEXT NOT NULL,
          command_kind TEXT NOT NULL, payload_hash TEXT NOT NULL, event_id INTEGER,
          result_json TEXT NOT NULL, created_at TEXT NOT NULL,
          PRIMARY KEY(organization_id,actor_key,command_id))''',
        '''CREATE TABLE IF NOT EXISTS quality_access_grants (
          id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL,
          role TEXT NOT NULL, subject_id TEXT NOT NULL, can_internal INTEGER NOT NULL DEFAULT 0,
          can_validate INTEGER NOT NULL DEFAULT 0, granted_by TEXT NOT NULL, granted_at TEXT NOT NULL,
          revoked_at TEXT, grant_origin TEXT NOT NULL DEFAULT 'EXPLICIT', UNIQUE(event_id,role,subject_id),
          FOREIGN KEY(event_id) REFERENCES quality_events(id) ON DELETE CASCADE)''',
        '''CREATE TABLE IF NOT EXISTS quality_attachments (
          id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, filename TEXT NOT NULL,
          mime_type TEXT NOT NULL, byte_size INTEGER NOT NULL, sha256 TEXT NOT NULL, content BLOB,
          document_reference_id INTEGER, audience TEXT NOT NULL DEFAULT 'INTERNAL',
          author TEXT NOT NULL, version_no INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
          FOREIGN KEY(event_id) REFERENCES quality_events(id) ON DELETE CASCADE,
          FOREIGN KEY(document_reference_id) REFERENCES document_references(id) ON DELETE RESTRICT)''',
        '''CREATE TABLE IF NOT EXISTS quality_organization_settings (
          organization_id INTEGER PRIMARY KEY, deletion_enabled INTEGER NOT NULL DEFAULT 0,
          retention_days INTEGER, email_enabled INTEGER NOT NULL DEFAULT 0,
          reminder_days INTEGER, updated_by TEXT, updated_at TEXT,
          FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE RESTRICT)''',
        '''CREATE TABLE IF NOT EXISTS quality_deletion_receipts (
          id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, reference TEXT NOT NULL,
          organization_id INTEGER NOT NULL, actor TEXT NOT NULL, deleted_at TEXT NOT NULL,
          reason TEXT NOT NULL, categories_json TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS quality_migration_decisions (
          source_kind TEXT NOT NULL, source_id INTEGER NOT NULL, organization_id INTEGER,
          event_id INTEGER, outcome TEXT NOT NULL, reason TEXT NOT NULL,
          actor TEXT NOT NULL, created_at TEXT NOT NULL,
          PRIMARY KEY(source_kind,source_id))''',
        'CREATE INDEX IF NOT EXISTS ix_quality_go4_plan ON quality_events(organization_id,deleted_at,status)',
        'CREATE INDEX IF NOT EXISTS ix_quality_go4_requester ON quality_events(requester_role,requester_id)',
        'CREATE INDEX IF NOT EXISTS ix_quality_go4_delegate ON quality_events(assigned_role,assigned_id)',
    ]
    for sql in statements:
        conn.execute(text(sql))
    if 'grant_origin' not in {r['name'] for r in _rows(conn, 'PRAGMA table_info(quality_access_grants)')}:
        conn.execute(text("ALTER TABLE quality_access_grants ADD COLUMN grant_origin TEXT NOT NULL DEFAULT 'EXPLICIT'"))


def _subject_active_tx(conn, role, key):
    if role == 'ADMIN':
        return bool(_one(conn, "SELECT id FROM admins WHERE lower(email)=:k AND active=1 AND role IN ('ADMIN','SUPERADMIN','SUPER_ADMIN')", {'k': key}))
    if role == 'TRAINER':
        return bool(_one(conn, 'SELECT id FROM trainers WHERE id=:k AND active=1', {'k': key}))
    if role == 'BENEFICIARY':
        return bool(_one(conn, '''SELECT b.id FROM beneficiaries b JOIN beneficiary_portal_accounts p
          ON p.beneficiary_id=b.id WHERE b.id=:k AND b.active=1 AND p.active=1''', {'k': key}))
    if role == 'CLIENT':
        return bool(_one(conn, '''SELECT cp.id FROM client_portal_accounts cp JOIN crm_contacts c ON c.id=cp.crm_contact_id
          WHERE cp.id=:k AND cp.active=1 AND cp.password_hash IS NOT NULL
          AND lower(trim(cp.email))=lower(trim(c.email))
          AND upper(COALESCE(c.status,'')) NOT IN ('ARCHIVE','ARCHIVÉ','ARCHIVED')''', {'k': key}))
    return False


def _training_access_tx(conn, actor, action_id):
    action = _one(conn, 'SELECT * FROM actions WHERE id=:i', {'i': action_id})
    if not action or action.get('organization_id') != int(actor.organization_id):
        return False
    if actor.role == 'ADMIN':
        return True
    if actor.role == 'CLIENT':
        return bool(_one(conn, 'SELECT id FROM client_action_grants WHERE account_id=:k AND action_id=:a AND revoked_at IS NULL', {'k': actor.key, 'a': action_id}))
    if actor.role == 'BENEFICIARY':
        return bool(_one(conn, 'SELECT id FROM participants WHERE beneficiary_id=:k AND action_id=:a AND active=1', {'k': actor.key, 'a': action_id}))
    if actor.role == 'TRAINER':
        return bool(_one(conn, '''SELECT a.id FROM actions a WHERE a.id=:a AND
          (a.trainer_id=:k OR EXISTS (SELECT 1 FROM action_trainers at WHERE at.action_id=a.id AND at.trainer_id=:k AND at.active=1)
           OR EXISTS (SELECT 1 FROM slot_trainers st JOIN slots s ON s.id=st.slot_id
             WHERE s.action_id=a.id AND st.trainer_id=:k AND st.active=1 AND st.assignment_status='ACTIVE'))''', {'a': action_id, 'k': actor.key}))
    return False


def _actor_tx(conn, actor):
    if not isinstance(actor, QualityActor) or actor.role not in ('ADMIN', 'TRAINER', 'BENEFICIARY', 'CLIENT'):
        raise PermissionError('Connectez-vous dans un espace habilité.')
    try:
        key = actor.key
        org = int(actor.organization_id)
    except (ValueError, TypeError):
        raise PermissionError('Contexte de connexion invalide.') from None
    if org < 1 or not _subject_active_tx(conn, actor.role, key):
        raise PermissionError('Compte inactif ou accès révoqué.')
    if not _one(conn, 'SELECT id FROM organizations WHERE id=:o AND active=1', {'o': org}):
        raise PermissionError('Organisme non accessible.')
    if actor.role != 'ADMIN':
        actions = _rows(conn, 'SELECT id FROM actions WHERE organization_id=:o', {'o': org})
        linked = any(_training_access_tx(conn, actor, a['id']) for a in actions)
        # An explicit live mission on a general action is a narrow organization context.
        mission = _one(conn, '''SELECT id FROM quality_events WHERE organization_id=:o AND assigned_role=:r
          AND assigned_id=:k AND delegation_status IN ('PENDING','ACCEPTED','SUBMITTED') AND deleted_at IS NULL''',
          {'o': org, 'r': actor.role, 'k': key})
        if not linked and not mission:
            raise PermissionError('Aucune habilitation active dans cet organisme.')
    return actor


def require_actor(engine, actor):
    with engine.connect() as conn:
        return _actor_tx(conn, actor)


def require_admin(engine, actor):
    require_actor(engine, actor)
    if actor.role != 'ADMIN':
        raise PermissionError('Cette opération est réservée à l’administration habilitée.')
    return actor


def available_organizations(engine, role, subject_id):
    result = []
    with engine.connect() as conn:
        for org in _rows(conn, 'SELECT id,name FROM organizations WHERE active=1 ORDER BY name,id'):
            try:
                _actor_tx(conn, QualityActor(role, subject_id, org['id']))
            except (PermissionError, ValueError, TypeError):
                continue
            result.append(org)
    return result


def available_trainings(engine, actor):
    with engine.connect() as conn:
        _actor_tx(conn, actor)
        return [a for a in _rows(conn, 'SELECT id,action_no,title,prestation_type FROM actions WHERE organization_id=:o ORDER BY id DESC',
                {'o': actor.organization_id}) if _training_access_tx(conn, actor, a['id'])]


def _requester(event):
    if event.get('requester_role') and event.get('requester_id'):
        return event['requester_role'], str(event['requester_id'])
    if event.get('beneficiary_id') and event.get('origin') in ('SIGNALEMENT_BENEFICIAIRE', 'BENEFICIARY_REPORT'):
        return 'BENEFICIARY', str(event['beneficiary_id'])
    if event.get('trainer_id') and event.get('origin') in ('SIGNALEMENT_INTERVENANT', 'TRAINER_REPORT'):
        return 'TRAINER', str(event['trainer_id'])
    return 'ADMIN', str(event.get('created_by') or '').removeprefix('ADMIN:').lower()


def _event_tx(conn, event_id):
    return _one(conn, '''SELECT qe.*,COALESCE(qe.organization_id,a.organization_id) effective_organization_id,
      a.action_no,a.title action_title,a.prestation_type FROM quality_events qe
      LEFT JOIN actions a ON a.id=qe.action_id WHERE qe.id=:i AND qe.deleted_at IS NULL''', {'i': event_id})


def _permissions_tx(conn, actor, event):
    perms = dict.fromkeys(('read', 'update', 'respond', 'internal', 'assign', 'close', 'reopen', 'delete', 'add_step', 'upload'), False)
    if not event or event.get('effective_organization_id', event.get('organization_id')) != int(actor.organization_id):
        return perms
    own = _requester(event) == (actor.role, actor.key)
    grant = _one(conn, 'SELECT * FROM quality_access_grants WHERE event_id=:e AND role=:r AND subject_id=:k AND revoked_at IS NULL',
                 {'e': event['id'], 'r': actor.role, 'k': actor.key})
    admin = actor.role == 'ADMIN'
    if event.get('sensitivity') == 'RESTRICTED' and admin and not (own or grant):
        return perms
    assigned = (event.get('assigned_role'), str(event.get('assigned_id'))) == (actor.role, actor.key)
    assigned = assigned and event.get('delegation_status') in ('PENDING', 'ACCEPTED', 'SUBMITTED')
    if not admin and not (own or assigned or grant):
        return perms
    if not admin and event.get('action_id') and not _training_access_tx(conn, actor, event['action_id']):
        return perms
    if actor.role in ('CLIENT', 'BENEFICIARY') and not own:
        return perms
    perms['read'] = True
    live = event.get('status') not in FINAL
    perms['internal'] = admin or bool(grant and grant['can_internal'])
    perms['update'] = live and (admin or own or (assigned and event.get('delegation_status') == 'ACCEPTED') or bool(grant))
    perms['respond'] = perms['update']
    perms['upload'] = perms['update']
    perms['assign'] = admin and live
    perms['close'] = live and (admin or bool(grant and grant['can_validate']))
    perms['reopen'] = not live and (admin or bool(grant and grant['can_validate']))
    perms['delete'] = admin
    perms['add_step'] = admin and live
    return perms


def _access_tx(conn, actor, event_id, permission='read', expected_version=None):
    _actor_tx(conn, actor)
    event = _event_tx(conn, event_id)
    perms = _permissions_tx(conn, actor, event)
    if not perms.get(permission):
        raise PermissionError('Cette action n’est pas accessible avec vos droits actuels.')
    if expected_version is not None and int(expected_version) != event['row_version']:
        raise ConflictError('Cette action a été actualisée par une autre personne. Votre saisie est conservée ; relisez la version actualisée avant de réessayer.')
    return event, perms


def _required_version(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError('Relisez la fiche avant de confirmer cette modification.')


def _value(value, label, limit=10000, required=False):
    value = str(value or '').strip()
    if required and not value:
        raise ValueError(f'{label} est requis.')
    if len(value) > limit:
        raise ValueError(f'{label} est trop long (maximum {limit} caractères).')
    return value


def _due(value):
    if value is None or value == '':
        return None
    value = str(value)
    try:
        return date.fromisoformat(value[:10]).isoformat() if len(value) == 10 else datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError):
        raise ValueError('Échéance invalide : choisissez une date.') from None


def _hash_payload(payload):
    return hashlib.sha256(_json(payload).encode()).hexdigest()


def _command_tx(conn, actor, command_id, kind, payload):
    cid = _value(command_id, 'Identifiant de commande', 150, True)
    old = _one(conn, '''SELECT * FROM quality_commands WHERE organization_id=:o AND actor_key=:a AND command_id=:c''',
               {'o': actor.organization_id, 'a': actor.label, 'c': cid})
    if old and (old['command_kind'] != kind or old['payload_hash'] != _hash_payload(payload)):
        raise ValueError('Cette confirmation a déjà servi à une autre saisie. Ouvrez une nouvelle commande.')
    return json.loads(old['result_json']) if old else None


def _finish_command_tx(conn, actor, command_id, kind, payload, event_id, result):
    conn.execute(text('''INSERT INTO quality_commands(organization_id,actor_key,command_id,command_kind,payload_hash,event_id,result_json,created_at)
      VALUES(:o,:a,:c,:k,:h,:e,:r,:n)'''), {'o': actor.organization_id, 'a': actor.label, 'c': command_id,
      'k': kind, 'h': _hash_payload(payload), 'e': event_id, 'r': _json(result), 'n': utcnow_iso()})


def _history_tx(conn, event_id, actor, kind, before=None, after=None, audience='INTERNAL', notify=True):
    result = conn.execute(text('''INSERT INTO quality_event_history(quality_event_id,change_kind,actor,before_json,after_json,created_at,audience)
      VALUES(:e,:k,:a,:b,:v,:n,:aud)'''), {'e': event_id, 'k': kind, 'a': actor.label,
      'b': _json(before) if before is not None else None, 'v': _json(after) if after is not None else None,
      'n': utcnow_iso(), 'aud': audience})
    if notify:
        from quality_notifications import enqueue_event_tx
        enqueue_event_tx(conn, event_id, int(result.lastrowid), kind, audience)
    return int(result.lastrowid)


def _bump_tx(conn, event, values):
    now = utcnow_iso()
    changes = dict(values, row_version=event['row_version'] + 1, updated_at=now, go4_managed=1)
    sql = ','.join(f'{key}=:{key}' for key in changes)
    result = conn.execute(text(f'UPDATE quality_events SET {sql} WHERE id=:_e AND row_version=:_v AND deleted_at IS NULL'),
                          {**changes, '_e': event['id'], '_v': event['row_version']})
    if result.rowcount != 1:
        raise ConflictError('Une autre modification vient d’être enregistrée. Relisez la fiche ; votre saisie est conservée.')


def _create_action_tx(conn, actor, title, description='', *, origin='INTERNE', nature='PREVENTIVE', action_id=None,
                      classification='REAL', command_id, due_at=None, sensitivity='NORMAL'):
    _actor_tx(conn, actor)
    title = _value(title, 'L’intitulé', 250, True)
    description = _value(description, 'Le contexte')
    if nature not in NATURES or classification not in CLASSIFICATIONS or sensitivity not in ('NORMAL', 'RESTRICTED'):
        raise ValueError('Nature, qualification TEST/RÉEL ou confidentialité invalide.')
    if origin not in ORIGINS:
        raise ValueError('Origine invalide.')
    if action_id is not None and not _training_access_tx(conn, actor, action_id):
        raise PermissionError('Formation non accessible dans ce contexte.')
    if actor.role != 'ADMIN':
        origin = {'TRAINER': 'SIGNALEMENT_INTERVENANT', 'BENEFICIARY': 'SIGNALEMENT_BENEFICIAIRE', 'CLIENT': 'DEMANDE_CLIENT'}[actor.role]
        if actor.role != 'TRAINER':
            nature = 'AMELIORATION'
        if classification != 'REAL':
            raise PermissionError('La qualification d’essai relève de l’administration.')
        if sensitivity != 'NORMAL':
            raise PermissionError('Une restriction nominative doit être organisée par un référent administratif habilité.')
    due_at = _due(due_at)
    payload = dict(title=title, description=description, origin=origin, nature=nature, action_id=action_id,
                   classification=classification, due_at=due_at, sensitivity=sensitivity)
    old = _command_tx(conn, actor, command_id, 'CREATE', payload)
    if old is not None:
        if not _event_tx(conn, int(old['id'])):
            raise ValueError('L’action créée par cette commande a été supprimée. Elle n’est pas recréée automatiquement.')
        return int(old['id'])
    now = utcnow_iso()
    reference = 'Q-' + secrets.token_hex(5).upper()
    result = conn.execute(text('''INSERT INTO quality_events(public_id,organization_id,action_id,beneficiary_id,trainer_id,
      family,event_type,status,detected_at,origin,subject,description,due_at,created_by,created_at,updated_at,
      go4_managed,action_nature,data_classification,requester_role,requester_id,sensitivity)
      VALUES(:ref,:o,:aid,:b,:t,'QUALITE',:kind,'NOUVEAU',:n,:origin,:title,:description,:due,:by,:n,:n,
      1,:kind,:classification,:role,:rid,:sensitivity)'''), {
        'ref': reference, 'o': actor.organization_id, 'aid': action_id,
        'b': int(actor.key) if actor.role == 'BENEFICIARY' else None,
        't': int(actor.key) if actor.role == 'TRAINER' else None, 'kind': nature, 'n': now,
        'origin': origin, 'title': title, 'description': description, 'due': due_at, 'by': actor.label,
        'classification': classification, 'role': actor.role, 'rid': actor.key, 'sensitivity': sensitivity,
    })
    event_id = int(result.lastrowid)
    _history_tx(conn, event_id, actor, 'CREATION', after={'status': 'NOUVEAU', 'public_id': reference}, audience='PUBLIC')
    _finish_command_tx(conn, actor, command_id, 'CREATE', payload, event_id, {'id': event_id})
    return event_id


def create_action(engine, actor, title, description='', **kwargs):
    with engine.begin() as conn:
        return _create_action_tx(conn, actor, title, description, **kwargs)


def _public_event(event, actor, permissions):
    if permissions['internal']:
        return dict(event)
    fields = ('id', 'public_id', 'organization_id', 'action_id', 'action_no', 'action_title', 'prestation_type',
              'subject', 'status', 'origin', 'action_nature', 'data_classification', 'created_at', 'updated_at',
              'due_at', 'closed_at', 'row_version', 'delegation_status', 'expected_result', 'assigned_role',
              'assigned_id', 'owner_name')
    result = {k: event.get(k) for k in fields}
    # A mission grants its expected result, not access to personal intake or BC data.
    if _requester(event) == (actor.role, actor.key):
        result['description'] = event.get('description')
        result['closure_comment'] = event.get('closure_comment')
    else:
        result['description'] = event.get('expected_result') or ''
    return result


def _aliases_tx(conn, event_id):
    result = []
    for link in _rows(conn, 'SELECT source_kind,source_id FROM quality_source_links WHERE quality_event_id=:e', {'e': event_id}):
        result.append(f"{link['source_kind']}:{link['source_id']}")
        if link['source_kind'] == 'IMPROVEMENT_ACTION':
            result.append(f"PA-{link['source_id']:03d}")
    for step in _rows(conn, 'SELECT id FROM quality_event_actions WHERE quality_event_id=:e', {'e': event_id}):
        result.append(f"PA-{step['id']:03d}")
        result.append(f"QUALITY_EVENT_ACTION:{step['id']}")
    return sorted(set(result))


def list_actions(engine, actor, *, action_id=None, status=None, origin=None, nature=None, assigned_id=None,
                 classification=None, search=None, mine=False, prestation_type=None, due_before=None):
    with engine.connect() as conn:
        _actor_tx(conn, actor)
        rows = _rows(conn, '''SELECT qe.*,COALESCE(qe.organization_id,a.organization_id) effective_organization_id,
          a.action_no,a.title action_title,a.prestation_type FROM quality_events qe LEFT JOIN actions a ON a.id=qe.action_id
          WHERE COALESCE(qe.organization_id,a.organization_id)=:o AND qe.deleted_at IS NULL ORDER BY qe.created_at DESC,qe.id DESC''',
          {'o': actor.organization_id})
        result = []
        today = datetime.now(timezone.utc).date().isoformat()
        for event in rows:
            permissions = _permissions_tx(conn, actor, event)
            if not permissions['read']:
                continue
            row = _public_event(event, actor, permissions)
            if permissions['internal']:
                row['legacy_aliases'] = _aliases_tx(conn, event['id'])
            overdue = bool(event.get('due_at') and event['due_at'][:10] < today and event['status'] not in FINAL)
            row['overdue'] = overdue
            if action_id is not None and event.get('action_id') != int(action_id):
                continue
            if status == 'OPEN' and event['status'] in FINAL:
                continue
            if status == 'OVERDUE' and not overdue:
                continue
            if status and status not in ('OPEN', 'OVERDUE') and event['status'] != status:
                continue
            if origin and event['origin'] != origin:
                continue
            if nature and event['action_nature'] != nature:
                continue
            if classification and event['data_classification'] != classification:
                continue
            if assigned_id is not None and str(event.get('assigned_id')) != str(assigned_id):
                continue
            if mine and (event.get('assigned_role'), str(event.get('assigned_id'))) != (actor.role, actor.key):
                continue
            if prestation_type and event.get('prestation_type') != prestation_type:
                continue
            if due_before and (not event.get('due_at') or event['due_at'][:10] > _due(due_before)[:10]):
                continue
            if search:
                accessible_text = ' '.join(str(row.get(k) or '') for k in ('public_id', 'subject', 'description', 'action_no', 'expected_result'))
                accessible_text += ' ' + ' '.join(row.get('legacy_aliases', []))
                if str(search).casefold() not in accessible_text.casefold():
                    continue
            result.append(row)
        return result


def get_action(engine, actor, event_id):
    with engine.connect() as conn:
        ev, perms = _access_tx(conn, actor, event_id)
        all_messages = _rows(conn, 'SELECT * FROM quality_event_messages WHERE quality_event_id=:e ORDER BY created_at,id', {'e': event_id})
        if perms['internal']:
            messages = all_messages
            history = _rows(conn, 'SELECT * FROM quality_event_history WHERE quality_event_id=:e ORDER BY id', {'e': event_id})
        else:
            legacy_direction = {'BENEFICIARY': 'VERS_BENEFICIAIRE', 'TRAINER': 'VERS_INTERVENANT', 'CLIENT': 'VERS_CLIENT'}[actor.role]
            messages = [{k: m.get(k) for k in ('id', 'message', 'created_at', 'direction', 'audience', 'author')}
                        for m in all_messages if m['audience'] == 'PUBLIC' or
                        (m['direction'] == legacy_direction and _requester(ev) == (actor.role, actor.key))]
            if _requester(ev) != (actor.role, actor.key):
                # The mission contains its instruction/expected result. Assigning a
                # task alone does not disclose a requester's personal conversation.
                messages = [m for m in messages if m.get('author') == actor.label]
            # History records can contain private before/after payloads. Only deliberate
            # public records, projected to status/date, can leave the internal workspace.
            history = []
            for h in _rows(conn, "SELECT * FROM quality_event_history WHERE quality_event_id=:e AND audience='PUBLIC' ORDER BY id", {'e': event_id}):
                after = json.loads(h.get('after_json') or '{}')
                projected = {k: after[k] for k in ('status', 'outcome', 'public_id') if k in after}
                history.append({'id': h['id'], 'change_kind': h['change_kind'], 'created_at': h['created_at'],
                                'actor': 'Vous' if h['actor'] == actor.label else 'Équipe Qualité',
                                'after_json': _json(projected), 'before_json': None})
        steps = _rows(conn, 'SELECT * FROM quality_event_actions WHERE quality_event_id=:e ORDER BY id', {'e': event_id})
        if not perms['internal']:
            steps = []  # Internal checks are not disclosed by a mission assignment.
        attachments = _rows(conn, '''SELECT id,filename,mime_type,byte_size,sha256,audience,author,version_no,created_at
          FROM quality_attachments WHERE event_id=:e ORDER BY id''', {'e': event_id})
        if not perms['internal']:
            attachments = [a for a in attachments if a['audience'] == 'PUBLIC' and
                           (_requester(ev) == (actor.role, actor.key) or a['author'] == actor.label)]
        attachments.extend(_legacy_attachments_tx(conn, actor, ev, perms))
        projected = _public_event(ev, actor, perms)
        if perms['internal']:
            projected['legacy_aliases'] = _aliases_tx(conn, event_id)
        return {'event': projected, 'steps': steps, 'actions': steps,
                'messages': messages, 'history': history, 'attachments': attachments, 'permissions': perms}


def _propagate_status_tx(conn, event_id, status):
    sources = _rows(conn, 'SELECT source_kind,source_id FROM quality_source_links WHERE quality_event_id=:e', {'e': event_id})
    now = utcnow_iso()
    for src in sources:
        if src['source_kind'] in ('TRAINER_REPORT', 'BENEFICIARY_REPORT'):
            table = {'TRAINER_REPORT': 'trainer_reports', 'BENEFICIARY_REPORT': 'beneficiary_reports'}[src['source_kind']]
            projected = 'CLOTURE' if status == 'CLOTURE' else 'TRAITE' if status in FINAL or status == 'A_VERIFIER' else 'NOUVEAU' if status == 'NOUVEAU' else 'EN_COURS'
            conn.execute(text(f'UPDATE {table} SET status=:s,updated_at=:n,closed_at=:c WHERE id=:i'),
                         {'s': projected, 'n': now, 'c': now if status in FINAL else None, 'i': src['source_id']})
        elif src['source_kind'] == 'QUALITY_ISSUE':
            conn.execute(text('UPDATE quality_issues SET status=:s,closed_at=:c,updated_at=:n WHERE id=:i'),
                         {'s': 'CLOTUREE' if status in FINAL else 'OUVERTE', 'c': now if status in FINAL else None, 'n': now, 'i': src['source_id']})
        elif src['source_kind'] == 'IMPROVEMENT_ACTION':
            conn.execute(text('UPDATE improvement_actions SET status=:s,completed_at=:c WHERE id=:i'),
                         {'s': 'TERMINEE' if status == 'CLOTURE' else 'ANNULEE' if status in FINAL else 'EN_COURS',
                          'c': now if status == 'CLOTURE' else None, 'i': src['source_id']})


def _message_tx(conn, actor, event, message, audience):
    now = utcnow_iso()
    direction = 'INTERNE' if audience == 'INTERNAL' else 'PUBLIC'
    result = conn.execute(text('''INSERT INTO quality_event_messages(quality_event_id,direction,author,message,channel,created_at,audience)
      VALUES(:e,:d,:a,:m,'PORTAIL',:n,:aud)'''), {'e': event['id'], 'd': direction, 'a': actor.label, 'm': message, 'n': now, 'aud': audience})
    # Legacy admin_response remains a compatible projection of the last public answer.
    if audience == 'PUBLIC' and actor.role == 'ADMIN':
        for src in _rows(conn, "SELECT source_kind,source_id FROM quality_source_links WHERE quality_event_id=:e AND source_kind IN ('TRAINER_REPORT','BENEFICIARY_REPORT')", {'e': event['id']}):
            table = 'trainer_reports' if src['source_kind'] == 'TRAINER_REPORT' else 'beneficiary_reports'
            conn.execute(text(f'UPDATE {table} SET admin_response=:m,updated_at=:n WHERE id=:i'), {'m': message, 'n': now, 'i': src['source_id']})
    return int(result.lastrowid)


def update_action(engine, actor, event_id, *, expected_version, comment='', audience='PUBLIC', status=None,
                  title=None, description=None, due_at=None, nature=None, classification=None):
    _required_version(expected_version)
    with engine.begin() as conn:
        ev, permissions = _access_tx(conn, actor, event_id, 'update', expected_version)
        if audience not in ('PUBLIC', 'INTERNAL') or (audience == 'INTERNAL' and not permissions['internal']):
            raise PermissionError('Cette audience n’est pas autorisée.')
        if status in FINAL:
            raise ValueError('Utilisez Clôturer pour saisir le bilan et vérifier les étapes dans la même fenêtre.')
        if status and status not in STATUSES:
            raise ValueError('Statut invalide.')
        if actor.role != 'ADMIN' and any(x is not None for x in (status, title, description, due_at, nature, classification)):
            raise PermissionError('Vous pouvez ajouter une avancée ou proposer la validation de votre mission.')
        values = {}
        if status is not None: values['status'] = status
        if title is not None: values['subject'] = _value(title, 'L’intitulé', 250, True)
        if description is not None: values['description'] = _value(description, 'Le contexte')
        if due_at is not None: values['due_at'] = _due(due_at)
        if nature is not None:
            if nature not in NATURES: raise ValueError('Nature invalide.')
            values['action_nature'] = nature
        if classification is not None:
            if classification not in CLASSIFICATIONS: raise ValueError('Qualification TEST/RÉEL invalide.')
            values['data_classification'] = classification
        changes = {k: v for k, v in values.items() if ev.get(k) != v}
        comment = _value(comment, 'L’avancée')
        if not changes and not comment:
            return False
        _bump_tx(conn, ev, changes)
        if 'due_at' in changes:
            from quality_notifications import invalidate_pending_tx
            invalidate_pending_tx(conn, event_id)
        if 'status' in changes:
            _propagate_status_tx(conn, event_id, changes['status'])
        if comment:
            mid = _message_tx(conn, actor, ev, comment, audience)
            _history_tx(conn, event_id, actor, 'AVANCEE', after={'message_id': mid}, audience=audience)
        if changes:
            # Detailed administrative changes stay internal; status is separately public.
            _history_tx(conn, event_id, actor, 'MODIFICATION', before={k: ev.get(k) for k in changes}, after=changes,
                        audience='INTERNAL')
            if 'status' in changes:
                _history_tx(conn, event_id, actor, 'STATUT', before={'status': ev['status']}, after={'status': changes['status']}, audience='PUBLIC')
        return True


def close_action(engine, actor, event_id, *, expected_version, summary, step_outcomes=None, outcome='RESOLVED', command_id):
    _required_version(expected_version)
    summary = _value(summary, 'Le travail réalisé et le résultat constaté', required=True)
    if outcome not in ('RESOLVED', 'CANCELLED', 'NO_FOLLOWUP'):
        raise ValueError('Issue de clôture invalide.')
    normalized = {str(k): v for k, v in (step_outcomes or {}).items()}
    payload = {'event_id': event_id, 'summary': summary, 'steps': normalized, 'outcome': outcome, 'version': expected_version}
    with engine.begin() as conn:
        _access_tx(conn, actor, event_id)
        old = _command_tx(conn, actor, command_id, 'CLOSE', payload)
        if old is not None: return True
        ev, _ = _access_tx(conn, actor, event_id, 'close', expected_version)
        steps = _rows(conn, "SELECT * FROM quality_event_actions WHERE quality_event_id=:e AND status NOT IN ('TERMINEE','ANNULEE')", {'e': event_id})
        if set(normalized) - {str(s['id']) for s in steps}:
            raise ValueError('Une étape a changé depuis l’ouverture de cette fenêtre. Relisez la fiche.')
        checked = []
        for step in steps:
            decision = normalized.get(str(step['id'])) or {}
            issue = decision.get('outcome')
            if issue not in ('VERIFIED', 'ABANDONED'):
                raise ValueError(f'Il reste une étape à traiter : {step["title"]}. Choisissez son issue ici ; aucune modification n’a été enregistrée.')
            reason = _value(decision.get('reason'), 'Le motif d’abandon', required=issue == 'ABANDONED')
            checked.append((step, issue, reason or summary))
        # All validation completes before any mutation. One transaction covers Q-003,
        # its steps, projections, immutable history and the notification queue.
        now = utcnow_iso()
        for step, issue, reason in checked:
            state = 'TERMINEE' if issue == 'VERIFIED' else 'ANNULEE'
            conn.execute(text('''UPDATE quality_event_actions SET status=:s,effectiveness_result=:r,completed_at=:c,updated_at=:n
              WHERE id=:i'''), {'s': state, 'r': reason, 'c': now if issue == 'VERIFIED' else None, 'n': now, 'i': step['id']})
            source = _one(conn, "SELECT source_id FROM quality_capa_source_links WHERE quality_event_action_id=:i AND source_kind='IMPROVEMENT_ACTION'", {'i': step['id']})
            if source:
                conn.execute(text('UPDATE improvement_actions SET status=:s,completed_at=:c WHERE id=:i'), {'s': state, 'c': now if issue == 'VERIFIED' else None, 'i': source['source_id']})
        final_status = 'CLOTURE' if outcome == 'RESOLVED' else 'CLASSE_SANS_SUITE'
        values = {'status': final_status, 'closure_comment': summary, 'closure_decision': outcome, 'closed_at': now,
                  'closed_by': actor.label, 'effectiveness_result': summary,
                  'effectiveness_checked_at': now, 'effectiveness_checked_by': actor.label}
        _bump_tx(conn, ev, values)
        _propagate_status_tx(conn, event_id, final_status)
        _history_tx(conn, event_id, actor, 'CLOTURE', before={'status': ev['status']},
                    after={**values, 'steps': [{'id': s['id'], 'outcome': issue, 'reason': reason} for s, issue, reason in checked]}, audience='PUBLIC')
        from quality_notifications import invalidate_pending_tx
        invalidate_pending_tx(conn, event_id)
        _finish_command_tx(conn, actor, command_id, 'CLOSE', payload, event_id, {'closed': True})
        return True


def reopen_action(engine, actor, event_id, *, expected_version, reason, command_id):
    _required_version(expected_version)
    reason = _value(reason, 'Le motif de réouverture', required=True)
    payload = {'event_id': event_id, 'version': expected_version, 'reason': reason}
    with engine.begin() as conn:
        _access_tx(conn, actor, event_id)
        old = _command_tx(conn, actor, command_id, 'REOPEN', payload)
        if old is not None: return True
        ev, _ = _access_tx(conn, actor, event_id, 'reopen', expected_version)
        previous = {k: ev.get(k) for k in ('status', 'closed_at', 'closed_by', 'closure_comment', 'closure_decision', 'effectiveness_result')}
        values = {'status': 'EN_TRAITEMENT', 'closed_at': None, 'closed_by': None,
                  'closure_comment': None, 'closure_decision': None, 'effectiveness_result': None,
                  'effectiveness_checked_at': None, 'effectiveness_checked_by': None}
        _bump_tx(conn, ev, values)
        _propagate_status_tx(conn, event_id, 'EN_TRAITEMENT')
        _history_tx(conn, event_id, actor, 'REOUVERTURE', before=previous, after={'status': 'EN_TRAITEMENT', 'reason': reason}, audience='PUBLIC')
        _finish_command_tx(conn, actor, command_id, 'REOPEN', payload, event_id, {'reopened': True})
        return True


def eligible_delegates(engine, actor, event_id):
    with engine.connect() as conn:
        ev, _ = _access_tx(conn, actor, event_id, 'assign')
        choices = [{'role': 'ADMIN', 'id': a['email'].lower(), 'label': a.get('full_name') or a['email']}
                   for a in _rows(conn, "SELECT email,full_name FROM admins WHERE active=1 AND role IN ('ADMIN','SUPERADMIN','SUPER_ADMIN') ORDER BY id")]
        for trainer in _rows(conn, 'SELECT id,full_name FROM trainers WHERE active=1 ORDER BY full_name,id'):
            candidate = QualityActor('TRAINER', trainer['id'], actor.organization_id)
            try: _actor_tx(conn, candidate)
            except PermissionError: continue
            if ev.get('action_id') and not _training_access_tx(conn, candidate, ev['action_id']):
                continue
            choices.append({'role': 'TRAINER', 'id': trainer['id'], 'label': trainer['full_name']})
        return choices


def assign_action(engine, actor, event_id, *, expected_version, delegate_role, delegate_id, expected_result, due_at=None, command_id):
    _required_version(expected_version)
    expected_result = _value(expected_result, 'Le résultat attendu', required=True)
    target = QualityActor(delegate_role, delegate_id, actor.organization_id)
    if delegate_role not in ('ADMIN', 'TRAINER'):
        raise PermissionError('Choisissez une personne existante habilitée à réaliser cette mission.')
    payload = {'event_id': event_id, 'version': expected_version, 'role': delegate_role, 'id': target.key, 'expected_result': expected_result, 'due_at': _due(due_at)}
    with engine.begin() as conn:
        _access_tx(conn, actor, event_id)
        old = _command_tx(conn, actor, command_id, 'ASSIGN', payload)
        if old is not None: return True
        ev, _ = _access_tx(conn, actor, event_id, 'assign', expected_version)
        _actor_tx(conn, target)
        if ev.get('action_id') and not _training_access_tx(conn, target, ev['action_id']):
            raise PermissionError('Cette personne n’est pas habilitée sur la formation concernée.')
        if target.role == 'ADMIN':
            label = _one(conn, 'SELECT full_name,email FROM admins WHERE lower(email)=:k', {'k': target.key})
            name = label.get('full_name') or label['email']
        else:
            name = _one(conn, 'SELECT full_name FROM trainers WHERE id=:k', {'k': target.key})['full_name']
        values = {'assigned_role': target.role, 'assigned_id': target.key, 'owner_name': name,
                  'expected_result': expected_result, 'delegation_status': 'PENDING'}
        if due_at is not None: values['due_at'] = _due(due_at)
        _bump_tx(conn, ev, values)
        if ev.get('sensitivity') == 'RESTRICTED' and target.role == 'ADMIN':
            # Explicit assignment is a narrow read grant for that existing administrator.
            conn.execute(text('''INSERT INTO quality_access_grants(event_id,role,subject_id,granted_by,granted_at,grant_origin)
              VALUES(:e,'ADMIN',:k,:a,:n,'ASSIGNMENT') ON CONFLICT(event_id,role,subject_id) DO UPDATE SET
              grant_origin=CASE WHEN revoked_at IS NOT NULL THEN 'ASSIGNMENT' ELSE grant_origin END,
              can_internal=CASE WHEN revoked_at IS NOT NULL THEN 0 ELSE can_internal END,
              can_validate=CASE WHEN revoked_at IS NOT NULL THEN 0 ELSE can_validate END,
              revoked_at=NULL,granted_by=:a,granted_at=:n'''),
              {'e': event_id, 'k': target.key, 'a': actor.label, 'n': utcnow_iso()})
        # Earlier mission-only grants expire; independent explicit grants are preserved.
        if (ev.get('assigned_role'), str(ev.get('assigned_id'))) != (target.role, target.key):
            conn.execute(text('''UPDATE quality_access_grants SET revoked_at=:n WHERE event_id=:e AND role=:r AND subject_id=:k
              AND grant_origin='ASSIGNMENT' AND revoked_at IS NULL'''),
              {'n': utcnow_iso(), 'e': event_id, 'r': ev.get('assigned_role'), 'k': ev.get('assigned_id')})
        _history_tx(conn, event_id, actor, 'AFFECTATION', before={k: ev.get(k) for k in values}, after=values, audience='PUBLIC')
        from quality_notifications import invalidate_pending_tx
        invalidate_pending_tx(conn, event_id)
        _finish_command_tx(conn, actor, command_id, 'ASSIGN', payload, event_id, {'assigned': True})
        return True


def respond_assignment(engine, actor, event_id, *, expected_version, decision, comment='', command_id):
    _required_version(expected_version)
    if decision not in ('ACCEPT', 'REFUSE', 'SUBMIT'):
        raise ValueError('Réponse de mission invalide.')
    comment = _value(comment, 'Le motif ou le résultat', required=decision in ('REFUSE', 'SUBMIT'))
    payload = {'event_id': event_id, 'version': expected_version, 'decision': decision, 'comment': comment}
    with engine.begin() as conn:
        _access_tx(conn, actor, event_id)
        old = _command_tx(conn, actor, command_id, 'MISSION', payload)
        if old is not None: return True
        ev, _ = _access_tx(conn, actor, event_id, expected_version=expected_version)
        if (ev.get('assigned_role'), str(ev.get('assigned_id'))) != (actor.role, actor.key) or ev['status'] in FINAL:
            raise PermissionError('Cette mission ne vous est plus confiée.')
        if decision in ('ACCEPT', 'REFUSE') and ev.get('delegation_status') != 'PENDING':
            raise ValueError('Cette mission a déjà reçu une réponse.')
        if decision == 'SUBMIT' and ev.get('delegation_status') != 'ACCEPTED':
            raise ValueError('Acceptez d’abord la mission avant de proposer sa validation.')
        state = {'ACCEPT': 'ACCEPTED', 'REFUSE': 'REFUSED', 'SUBMIT': 'SUBMITTED'}[decision]
        values = {'delegation_status': state}
        if decision == 'ACCEPT': values['status'] = 'EN_TRAITEMENT'
        if decision == 'SUBMIT': values['status'] = 'A_VERIFIER'
        _bump_tx(conn, ev, values)
        if 'status' in values: _propagate_status_tx(conn, event_id, values['status'])
        if decision == 'REFUSE':
            conn.execute(text('''UPDATE quality_access_grants SET revoked_at=:n WHERE event_id=:e
              AND role=:r AND subject_id=:k AND grant_origin='ASSIGNMENT' AND revoked_at IS NULL'''),
              {'n': utcnow_iso(), 'e': event_id, 'r': actor.role, 'k': actor.key})
        if comment: _message_tx(conn, actor, ev, comment, 'PUBLIC')
        _history_tx(conn, event_id, actor, 'MISSION_' + decision, before={'delegation_status': ev.get('delegation_status')}, after=values, audience='PUBLIC')
        _finish_command_tx(conn, actor, command_id, 'MISSION', payload, event_id, {'recorded': True})
        return True


def add_step(engine, actor, event_id, title, *, expected_version, description=''):
    _required_version(expected_version)
    title = _value(title, 'L’étape', 250, True)
    description = _value(description, 'Le détail de l’étape')
    with engine.begin() as conn:
        ev, _ = _access_tx(conn, actor, event_id, 'add_step', expected_version)
        now = utcnow_iso()
        row = conn.execute(text('''INSERT INTO quality_event_actions(quality_event_id,title,description,status,created_by,created_at,updated_at)
          VALUES(:e,:t,:d,'A_FAIRE',:a,:n,:n)'''), {'e': event_id, 't': title, 'd': description, 'a': actor.label, 'n': now})
        sid = int(row.lastrowid)
        _bump_tx(conn, ev, {})
        _history_tx(conn, event_id, actor, 'ETAPE_AJOUTEE', after={'step_id': sid, 'title': title}, audience='INTERNAL')
        return sid


def plan_counts(engine, actor, **filters):
    rows = list_actions(engine, actor, **filters)
    return {
        'total': len(rows), 'open': sum(r['status'] not in FINAL for r in rows),
        'unassigned': sum(r['status'] not in FINAL and (not r.get('assigned_id') or r.get('delegation_status') == 'REFUSED') for r in rows),
        'waiting': sum(r['status'] == 'EN_ATTENTE' for r in rows),
        'to_validate': sum(r['status'] == 'A_VERIFIER' for r in rows),
        'closed': sum(r['status'] in FINAL for r in rows),
        'overdue': sum(bool(r.get('overdue')) for r in rows),
        'resolved': sum(r['status'] == 'CLOTURE' and r.get('closure_decision') == 'RESOLVED' for r in rows),
        'cancelled': sum(r['status'] in ('REFUSE', 'CLASSE_SANS_SUITE') for r in rows),
        'test': sum(r.get('data_classification') == 'TEST' for r in rows),
    }


def _export_cell(value):
    value = str(value if value is not None else '')
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else value


def export_plan_csv(engine, actor, **filters):
    rows = list_actions(engine, actor, **filters)
    out = io.StringIO(newline='')
    writer = csv.writer(out, delimiter=';')
    writer.writerow(['CLARTÉ360 — Plan unique Qualité', 'GO4 V1.0', utcnow_iso()])
    writer.writerow(['Organisme', actor.organization_id, 'Filtres', _json(filters)])
    writer.writerow(['Méthode', 'Une ligne par action ; étapes facultatives non additionnées ; annulations exclues des retards'])
    writer.writerow(['Essais', 'Exclus' if filters.get('classification') == 'REAL' else 'Inclus selon la qualification indiquée'])
    writer.writerow(['Référence', 'Ouverture', 'Origine', 'Nature', 'Formation', 'Action à réaliser', 'Contexte',
                     'Résultat attendu', 'Responsable', 'Statut', 'Échéance', 'Dernière avancée', 'Bilan', 'Clôture', 'TEST/RÉEL', 'Étapes'])
    for row in rows:
        case = get_action(engine, actor, row['id'])  # Check rights again for detail/export.
        messages = case['messages']
        writer.writerow([_export_cell(v) for v in (
            row['public_id'], row['created_at'], row['origin'], row['action_nature'], row.get('action_no'), row['subject'],
            row.get('description'), row.get('expected_result'), row.get('owner_name'), row['status'], row.get('due_at'),
            messages[-1]['message'] if messages else '', row.get('closure_comment'), row.get('closed_at'), row['data_classification'],
            ' | '.join(f"{s['title']} : {s['status']}" for s in case['steps']))])
    return ('\ufeff' + out.getvalue()).encode('utf-8')


def export_plan_pdf(engine, actor, **filters):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from xml.sax.saxutils import escape
    rows = list_actions(engine, actor, **filters)
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    story = [Paragraph('CLARTÉ360 — Plan unique Qualité', styles['Title']),
             Paragraph(escape(f'Export {utcnow_iso()} — Organisme {actor.organization_id}'), styles['Normal']),
             Paragraph(escape('Filtres : ' + _json(filters)), styles['Normal']),
             Paragraph('Méthode : une action par référence ; les étapes ne sont pas des actions supplémentaires. Les annulations ne sont pas des réussites.', styles['Normal']),
             Spacer(1, 12)]
    for row in rows:
        case = get_action(engine, actor, row['id'])
        story.append(Paragraph(escape(row['public_id'] + ' — ' + row['subject']), styles['Heading2']))
        for label, value in [('Statut', row['status']), ('Nature', row['action_nature']), ('Origine', row['origin']),
                             ('Qualification', row['data_classification']), ('Responsable', row.get('owner_name')),
                             ('Échéance', row.get('due_at')), ('Contexte', row.get('description')),
                             ('Résultat attendu', row.get('expected_result')), ('Bilan', row.get('closure_comment'))]:
            if value:
                story.append(Paragraph(escape(f'{label} : {value}'), styles['Normal']))
        for message in case['messages']:
            story.append(Paragraph(escape(f"{message['created_at']} — {message['message']}"), styles['Normal']))
        story.append(Spacer(1, 10))
    SimpleDocTemplate(output, pagesize=A4, title='Plan unique Qualité', author='CLARTÉ360').build(story)
    return output.getvalue()


def _validate_attachment(data, filename):
    if not isinstance(data, bytes) or not data or len(data) > 10 * 1024 * 1024:
        raise ValueError('Pièce vide ou trop volumineuse (maximum 10 Mo).')
    filename = PurePath(str(filename).replace('\\', '/')).name
    filename = re.sub(r'[^\w.() -]', '_', filename, flags=re.UNICODE)[:180]
    extension = PurePath(filename).suffix.lower()
    allowed = {'.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
               '.txt': 'text/plain', '.csv': 'text/csv', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
               '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
    if extension not in allowed:
        raise ValueError('Type de pièce non autorisé : PDF, image, texte, DOCX ou XLSX.')
    if extension == '.pdf' and not data.startswith(b'%PDF-'):
        raise ValueError('Le contenu ne correspond pas à un PDF.')
    if extension == '.png' and not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Le contenu ne correspond pas à une image PNG.')
    if extension in ('.jpg', '.jpeg') and not data.startswith(b'\xff\xd8\xff'):
        raise ValueError('Le contenu ne correspond pas à une image JPEG.')
    if extension in ('.txt', '.csv'):
        try: data.decode('utf-8-sig')
        except UnicodeError: raise ValueError('Le texte doit être encodé en UTF-8.') from None
    if extension in ('.docx', '.xlsx'):
        import zipfile
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = archive.namelist()
                required = 'word/document.xml' if extension == '.docx' else 'xl/workbook.xml'
                if required not in names or '[Content_Types].xml' not in names:
                    raise ValueError('Le contenu ne correspond pas au document annoncé.')
                if any('vbaproject' in n.lower() or n.startswith('/') or '..' in PurePath(n).parts for n in names):
                    raise ValueError('Document contenant une entrée non autorisée.')
                if sum(i.file_size for i in archive.infolist()) > 50 * 1024 * 1024:
                    raise ValueError('Document décompressé trop volumineux.')
        except zipfile.BadZipFile:
            raise ValueError('Document Office invalide.') from None
    return filename, allowed[extension]


def add_attachment(engine, actor, event_id, *, expected_version, data, filename, audience='INTERNAL', command_id):
    _required_version(expected_version)
    filename, mime = _validate_attachment(data, filename)
    digest = hashlib.sha256(data).hexdigest()
    payload = {'event_id': event_id, 'version': expected_version, 'filename': filename, 'sha256': digest, 'audience': audience}
    with engine.begin() as conn:
        _access_tx(conn, actor, event_id)
        old = _command_tx(conn, actor, command_id, 'ATTACHMENT', payload)
        if old is not None: return old['id']
        ev, perms = _access_tx(conn, actor, event_id, 'upload', expected_version)
        if audience not in ('PUBLIC', 'INTERNAL') or (audience == 'INTERNAL' and not perms['internal']):
            raise PermissionError('Audience de pièce non autorisée.')
        result = conn.execute(text('''INSERT INTO quality_attachments(event_id,filename,mime_type,byte_size,sha256,content,audience,author,created_at)
          VALUES(:e,:f,:m,:s,:h,:content,:aud,:a,:n)'''), {'e': event_id, 'f': filename, 'm': mime, 's': len(data), 'h': digest,
          'content': data, 'aud': audience, 'a': actor.label, 'n': utcnow_iso()})
        attachment_id = int(result.lastrowid)
        _bump_tx(conn, ev, {})
        _history_tx(conn, event_id, actor, 'PIECE_AJOUTEE', after={'attachment_id': attachment_id, 'sha256': digest}, audience=audience)
        _finish_command_tx(conn, actor, command_id, 'ATTACHMENT', payload, event_id, {'id': attachment_id})
        return attachment_id


def _legacy_attachments_tx(conn, actor, event, permissions):
    """Expose original report attachments by a controlled source identifier.

    No source path is ever sent to the interface. Original files are neither
    moved nor overwritten during adoption, and remain owned by their report.
    """
    if not permissions['internal'] and _requester(event) != (actor.role, actor.key):
        return []
    result = []
    tables = {'TRAINER_REPORT': ('trainer_reports', 'TRAINER', 'trainer_id'),
              'BENEFICIARY_REPORT': ('beneficiary_reports', 'BENEFICIARY', 'beneficiary_id')}
    for source in _rows(conn, 'SELECT source_kind,source_id FROM quality_source_links WHERE quality_event_id=:e', {'e': event['id']}):
        if source['source_kind'] not in tables:
            continue
        table, role, id_column = tables[source['source_kind']]
        report = _one(conn, f'SELECT * FROM {table} WHERE id=:i', {'i': source['source_id']})
        if not report or not report.get('attachment_path'):
            continue
        if not permissions['internal'] and (actor.role, actor.key) != (role, str(report[id_column])):
            continue
        filename = PurePath(str(report.get('attachment_name') or report['attachment_path']).replace('\\', '/')).name
        filename = re.sub(r'[^\w.() -]', '_', filename)[:180] or 'piece_historique'
        result.append({'id': f'legacy:{source["source_kind"]}:{source["source_id"]}', 'filename': filename,
                       'mime_type': mimetypes.guess_type(filename)[0] or 'application/octet-stream', 'byte_size': None,
                       'sha256': None, 'audience': 'PUBLIC', 'author': f'{role}:{report[id_column]}',
                       'version_no': 1, 'created_at': report['created_at']})
    return result


def read_attachment(engine, actor, event_id, attachment_id):
    with engine.connect() as conn:
        event, perms = _access_tx(conn, actor, event_id)
        if isinstance(attachment_id, str) and attachment_id.startswith('legacy:'):
            metadata = next((row for row in _legacy_attachments_tx(conn, actor, event, perms) if row['id'] == attachment_id), None)
            if not metadata:
                raise PermissionError('Pièce historique non accessible.')
            _, kind, source_id = attachment_id.split(':')
            table = {'TRAINER_REPORT': 'trainer_reports', 'BENEFICIARY_REPORT': 'beneficiary_reports'}[kind]
            report = _one(conn, f'SELECT attachment_path FROM {table} WHERE id=:i', {'i': source_id})
            try:
                root = LEGACY_ATTACHMENT_ROOT.resolve(strict=True)
                path = Path(report['attachment_path']).resolve(strict=True)
                if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size > 10 * 1024 * 1024:
                    raise ValueError('Pièce historique hors du répertoire autorisé ou trop volumineuse.')
                with path.open('rb') as file:
                    data = file.read(10 * 1024 * 1024 + 1)
                if not data or len(data) > 10 * 1024 * 1024:
                    raise ValueError('Pièce historique vide ou trop volumineuse.')
            except OSError:
                raise ValueError('Pièce historique indisponible ; faire vérifier sa copie par l’administration.') from None
            # Legacy uploads were validated by extension in RC2. Their original
            # bytes are preserved for authorized download; no document is executed.
            return {'data': data, 'filename': metadata['filename'], 'mime_type': 'application/octet-stream'}
        attachment = _one(conn, 'SELECT * FROM quality_attachments WHERE id=:i AND event_id=:e', {'i': attachment_id, 'e': event_id})
        if not attachment or (attachment['audience'] != 'PUBLIC' and not perms['internal']):
            raise PermissionError('Pièce non accessible.')
        if not perms['internal'] and _requester(event) != (actor.role, actor.key) and attachment['author'] != actor.label:
            raise PermissionError('Pièce non accessible.')
        if attachment.get('document_reference_id'):
            # Document grants remain independent; an action link never widens them.
            from services import read_document_for_actor
            data = read_document_for_actor(engine, attachment['document_reference_id'], actor.role, actor.subject_id, event.get('action_id'))
        else:
            data = attachment['content']
        if hashlib.sha256(data).hexdigest() != attachment['sha256']:
            raise ValueError('Intégrité de la pièce à contrôler.')
        return {'data': data, 'filename': attachment['filename'], 'mime_type': attachment['mime_type']}


def set_access_grant(engine, actor, event_id, *, expected_version, role, subject_id, can_internal=False, can_validate=False, revoke=False):
    """A named existing referent may receive rights on one sensitive case only."""
    _required_version(expected_version)
    with engine.begin() as conn:
        ev, _ = _access_tx(conn, actor, event_id, expected_version=expected_version)
        if actor.role != 'ADMIN':
            raise PermissionError('Seule l’administration habilitée gère ces droits.')
        target = QualityActor(role, subject_id, actor.organization_id)
        if role not in ('ADMIN', 'TRAINER'):
            raise PermissionError('Les accès internes ne sont pas ouverts aux demandeurs externes.')
        previous = _one(conn, 'SELECT * FROM quality_access_grants WHERE event_id=:e AND role=:r AND subject_id=:k',
                        {'e': event_id, 'r': role, 'k': target.key})
        if revoke:
            if not previous or previous['revoked_at']:
                return False
        else:
            _actor_tx(conn, target)
            if ev.get('action_id') and not _training_access_tx(conn, target, ev['action_id']):
                raise PermissionError('Personne non habilitée sur cette formation.')
            if previous and previous['revoked_at'] is None and previous.get('grant_origin') == 'EXPLICIT' and bool(previous['can_internal']) == bool(can_internal) and bool(previous['can_validate']) == bool(can_validate):
                return False
        conn.execute(text('''INSERT INTO quality_access_grants(event_id,role,subject_id,can_internal,can_validate,granted_by,granted_at,revoked_at)
          VALUES(:e,:r,:k,:ci,:cv,:a,:n,:rev) ON CONFLICT(event_id,role,subject_id) DO UPDATE SET
          can_internal=:ci,can_validate=:cv,granted_by=:a,granted_at=:n,revoked_at=:rev,grant_origin='EXPLICIT' '''),
          {'e': event_id, 'r': role, 'k': target.key, 'ci': int(bool(can_internal)), 'cv': int(bool(can_validate)),
           'a': actor.label, 'n': utcnow_iso(), 'rev': utcnow_iso() if revoke else None})
        _bump_tx(conn, ev, {})
        _history_tx(conn, event_id, actor, 'HABILITATION', after={'role': role, 'subject_id': target.key, 'revoked': bool(revoke),
          'can_internal': bool(can_internal), 'can_validate': bool(can_validate)}, audience='INTERNAL')
        return True


def eligible_referents(engine, actor, event_id):
    """Existing authorized people only; grants add no organization hierarchy."""
    with engine.connect() as conn:
        ev, _ = _access_tx(conn, actor, event_id)
        if actor.role != 'ADMIN':
            raise PermissionError('Seule l’administration habilitée gère ces droits.')
        people = [{'role': 'ADMIN', 'id': row['email'].lower(), 'label': row.get('full_name') or row['email']}
                  for row in _rows(conn, "SELECT email,full_name FROM admins WHERE active=1 AND role IN ('ADMIN','SUPERADMIN','SUPER_ADMIN') ORDER BY id")]
        for row in _rows(conn, 'SELECT id,full_name FROM trainers WHERE active=1 ORDER BY full_name,id'):
            target = QualityActor('TRAINER', row['id'], actor.organization_id)
            try:
                _actor_tx(conn, target)
            except PermissionError:
                continue
            if not ev.get('action_id') or _training_access_tx(conn, target, ev['action_id']):
                people.append({'role': 'TRAINER', 'id': row['id'], 'label': row['full_name']})
        return people


def access_grants(engine, actor, event_id):
    with engine.connect() as conn:
        _access_tx(conn, actor, event_id)
        if actor.role != 'ADMIN':
            raise PermissionError('Seule l’administration habilitée consulte ces droits.')
        rows = _rows(conn, 'SELECT * FROM quality_access_grants WHERE event_id=:e ORDER BY role,subject_id', {'e': event_id})
        for row in rows:
            row['account_active'] = _subject_active_tx(conn, row['role'], row['subject_id'])
        return rows


def delivery_status(engine, actor, event_id):
    with engine.connect() as conn:
        _access_tx(conn, actor, event_id)
        if actor.role != 'ADMIN':
            raise PermissionError('Le suivi de remise est réservé à l’administration habilitée.')
        return _rows(conn, '''SELECT id,recipient_role,recipient_id,event_kind,status,attempts,accepted_at,last_error,created_at,updated_at
          FROM quality_notification_outbox WHERE event_id=:e ORDER BY id''', {'e': event_id})


def configure_organization(engine, actor, *, deletion_enabled=None, retention_days=None, email_enabled=None, reminder_days=None):
    require_admin(engine, actor)
    if retention_days is not None and (not isinstance(retention_days, int) or not 0 <= retention_days <= 36500):
        raise ValueError('Durée de conservation invalide.')
    if reminder_days is not None and (not isinstance(reminder_days, int) or not 0 <= reminder_days <= 365):
        raise ValueError('Délai de rappel invalide.')
    values = {k: v for k, v in locals().copy().items() if k in ('deletion_enabled', 'retention_days', 'email_enabled', 'reminder_days') and v is not None}
    if deletion_enabled and retention_days is None:
        raise ValueError('Renseignez explicitement la durée de conservation avant d’autoriser la suppression unitaire.')
    with engine.begin() as conn:
        _actor_tx(conn, actor)
        conn.execute(text('INSERT OR IGNORE INTO quality_organization_settings(organization_id) VALUES(:o)'), {'o': actor.organization_id})
        if values:
            conn.execute(text('UPDATE quality_organization_settings SET ' + ','.join(k + '=:' + k for k in values) + ',updated_by=:a,updated_at=:n WHERE organization_id=:o'),
                         {**values, 'a': actor.label, 'n': utcnow_iso(), 'o': actor.organization_id})


def _deletion_preview_tx(conn, actor, event_id):
    ev, _ = _access_tx(conn, actor, event_id, 'delete')
    settings = _one(conn, 'SELECT * FROM quality_organization_settings WHERE organization_id=:o', {'o': actor.organization_id}) or {}
    blockers = []
    if not settings.get('deletion_enabled') or settings.get('retention_days') is None:
        blockers.append('La politique de conservation et le droit de suppression doivent être configurés par l’administration.')
    now = datetime.now(timezone.utc)
    if ev.get('retention_until') and ev['retention_until'][:10] >= now.date().isoformat():
        blockers.append('La conservation requise de cette action n’est pas échue.')
    if settings.get('retention_days') is not None:
        created = datetime.fromisoformat(ev['created_at'].replace('Z', '+00:00'))
        created = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
        if (now - created).days < settings['retention_days']:
            blockers.append('Le délai de conservation de cette action n’est pas écoulé.')
    categories = {}
    for table, column in [('quality_event_messages', 'quality_event_id'), ('quality_event_history', 'quality_event_id'),
                          ('quality_event_actions', 'quality_event_id'), ('quality_attachments', 'event_id'), ('quality_notification_outbox', 'event_id')]:
        categories[table] = _one(conn, f'SELECT COUNT(*) n FROM {table} WHERE {column}=:e', {'e': event_id})['n']
    sources = _rows(conn, 'SELECT * FROM quality_source_links WHERE quality_event_id=:e', {'e': event_id})
    for src in sources:
        if src['source_kind'] == 'QUALITY_ISSUE':
            others = _rows(conn, '''SELECT ia.id FROM improvement_actions ia WHERE ia.issue_id=:i AND NOT EXISTS
              (SELECT 1 FROM quality_capa_source_links l JOIN quality_event_actions s ON s.id=l.quality_event_action_id
               WHERE l.source_kind='IMPROVEMENT_ACTION' AND l.source_id=ia.id AND s.quality_event_id=:e)''', {'i': src['source_id'], 'e': event_id})
            if others: blockers.append('Une ancienne mesure liée reste utilisée ailleurs ; rapprochez son historique avant suppression.')
    return {'event_id': event_id, 'reference': ev['public_id'], 'can_delete': not blockers, 'allowed': not blockers,
            'blockers': blockers, 'reasons': blockers, 'categories': categories,
            'training_preserved': True, 'shared_documents_preserved': True, 'sources': sources}


def deletion_preview(engine, actor, event_id):
    with engine.connect() as conn:
        return _deletion_preview_tx(conn, actor, event_id)


def delete_action(engine, actor, event_id, expected_version, reason, command_id):
    _required_version(expected_version)
    reason = _value(reason, 'Le motif de suppression', 500, True)
    payload = {'event_id': event_id, 'version': expected_version, 'reason': reason}
    with engine.begin() as conn:
        _actor_tx(conn, actor)
        old = _command_tx(conn, actor, command_id, 'DELETE', payload)
        if old is not None: return old
        ev, _ = _access_tx(conn, actor, event_id, 'delete', expected_version)
        preview = _deletion_preview_tx(conn, actor, event_id)
        if preview['blockers']:
            raise ValueError(' '.join(preview['blockers']))
        # Claim the expected row version before any receipt or cascade. Competing
        # commands cannot both certify deletion of the same version.
        _bump_tx(conn, ev, {})
        now = utcnow_iso()
        result = conn.execute(text('''INSERT INTO quality_deletion_receipts(event_id,reference,organization_id,actor,deleted_at,reason,categories_json)
          VALUES(:e,:ref,:o,:a,:n,:r,:categories)'''), {'e': event_id, 'ref': ev['public_id'], 'o': actor.organization_id,
          'a': actor.label, 'n': now, 'r': reason, 'categories': _json(preview['categories'])})
        # Keep source tombstones, so a later reconciliation cannot resurrect a deletion.
        sources = list(preview['sources'])
        steps = _rows(conn, '''SELECT l.source_id FROM quality_capa_source_links l JOIN quality_event_actions s ON s.id=l.quality_event_action_id
          WHERE s.quality_event_id=:e AND l.source_kind='IMPROVEMENT_ACTION' ''', {'e': event_id})
        sources += [{'source_kind': 'IMPROVEMENT_ACTION', 'source_id': s['source_id']} for s in steps]
        for src in sources:
            conn.execute(text('''INSERT INTO quality_migration_decisions(source_kind,source_id,organization_id,event_id,outcome,reason,actor,created_at)
              VALUES(:k,:i,:o,NULL,'DELETED','Suppression unitaire autorisée',:a,:n) ON CONFLICT(source_kind,source_id)
              DO UPDATE SET event_id=NULL,outcome='DELETED',reason='Suppression unitaire autorisée',actor=:a,created_at=:n'''),
              {'k': src['source_kind'], 'i': src['source_id'], 'o': actor.organization_id, 'a': actor.label, 'n': now})
        for src in sorted(sources, key=lambda s: s['source_kind'] != 'IMPROVEMENT_ACTION'):
            table = {'IMPROVEMENT_ACTION': 'improvement_actions', 'TRAINER_REPORT': 'trainer_reports',
                     'BENEFICIARY_REPORT': 'beneficiary_reports', 'QUALITY_ISSUE': 'quality_issues'}.get(src['source_kind'])
            if table: conn.execute(text(f'DELETE FROM {table} WHERE id=:i'), {'i': src['source_id']})
        conn.execute(text("DELETE FROM workspace_notifications WHERE target_kind='QUALITY' AND target_id=:e"), {'e': str(event_id)})
        conn.execute(text('DELETE FROM quality_notification_outbox WHERE event_id=:e'), {'e': event_id})
        # Explicit children also protect SQLite connections with a historical FK setup.
        for table, column in [('quality_capa_source_links', 'quality_event_action_id')]:
            conn.execute(text(f'DELETE FROM {table} WHERE {column} IN (SELECT id FROM quality_event_actions WHERE quality_event_id=:e)'), {'e': event_id})
        for table, column in [('quality_attachments', 'event_id'), ('quality_access_grants', 'event_id'), ('quality_event_messages', 'quality_event_id'),
                              ('quality_event_history', 'quality_event_id'), ('quality_event_actions', 'quality_event_id'), ('quality_source_links', 'quality_event_id')]:
            conn.execute(text(f'DELETE FROM {table} WHERE {column}=:e'), {'e': event_id})
        # Watch records remain immutable; their decision preserves the deleted reference.
        if _one(conn, "SELECT name FROM sqlite_master WHERE type='table' AND name='quality_watch_decisions'"):
            # Explicit SET NULL keeps a tombstone even on historical SQLite handles
            # whose foreign-key pragma was not enabled. Sources/items remain intact.
            conn.execute(text('UPDATE quality_watch_decisions SET action_id=NULL WHERE action_id=:e'), {'e': event_id})
            conn.execute(text('UPDATE quality_watch_action_links SET action_id=NULL WHERE action_id=:e'), {'e': event_id})
        conn.execute(text('UPDATE quality_review_points SET quality_event_id=NULL WHERE quality_event_id=:e'), {'e': event_id})
        conn.execute(text('DELETE FROM quality_events WHERE id=:e'), {'e': event_id})
        answer = {'deleted': True, 'receipt_id': int(result.lastrowid), 'reference': ev['public_id']}
        _finish_command_tx(conn, actor, command_id, 'DELETE', payload, event_id, answer)
        return answer


def _legacy_decision_tx(conn, actor, kind, source_id, event_id, outcome, reason):
    conn.execute(text('''INSERT INTO quality_migration_decisions(source_kind,source_id,organization_id,event_id,outcome,reason,actor,created_at)
      VALUES(:k,:i,:o,:e,:out,:r,:a,:n) ON CONFLICT(source_kind,source_id) DO UPDATE SET
      event_id=:e,outcome=:out,reason=:r,actor=:a,created_at=:n'''),
      {'k': kind, 'i': source_id, 'o': actor.organization_id, 'e': event_id, 'out': outcome, 'r': reason, 'a': actor.label, 'n': utcnow_iso()})


def _legacy_event_tx(conn, actor, source, kind):
    """Import a distinct source, without attributing its authorship to the importer."""
    now = source.get('created_at') or utcnow_iso()
    role, rid = None, None
    if kind == 'BENEFICIARY_REPORT': role, rid = 'BENEFICIARY', str(source['beneficiary_id'])
    if kind == 'TRAINER_REPORT': role, rid = 'TRAINER', str(source['trainer_id'])
    origin = {'BENEFICIARY_REPORT': 'SIGNALEMENT_BENEFICIAIRE', 'TRAINER_REPORT': 'SIGNALEMENT_INTERVENANT'}.get(kind, 'LEGACY')
    legacy_state = source.get('status') or 'NOUVEAU'
    status = {'CLOTURE': 'CLOTURE', 'CLOTUREE': 'CLOTURE', 'TERMINEE': 'CLOTURE', 'ANNULEE': 'CLASSE_SANS_SUITE',
              'TRAITE': 'A_VERIFIER', 'EN_COURS': 'EN_TRAITEMENT', 'A_VERIFIER': 'A_VERIFIER', 'EN_ATTENTE': 'EN_ATTENTE'}.get(legacy_state, 'NOUVEAU')
    author = source.get('created_by') or (f'{role}:{rid}' if role else 'LEGACY:AUTHOR_NOT_RECORDED')
    ref = 'Q-H-' + kind.split('_')[0][:3] + '-' + str(source['id'])
    result = conn.execute(text('''INSERT INTO quality_events(public_id,organization_id,action_id,campaign_id,beneficiary_id,trainer_id,
      family,event_type,status,detected_at,origin,subject,description,due_at,owner_name,created_by,created_at,updated_at,
      closed_at,closure_comment,go4_managed,action_nature,data_classification,requester_role,requester_id)
      VALUES(:ref,:o,:aid,:campaign,:bid,:tid,'QUALITE','AMELIORATION',:s,:n,:origin,:subject,:description,:due,:owner,:author,:n,:updated,
      :closed,:answer,1,'AMELIORATION','A_EXAMINER',:role,:rid)'''),
      {'ref': ref, 'o': actor.organization_id, 'aid': source.get('action_id'), 'campaign': source.get('campaign_id'),
       'bid': source.get('beneficiary_id'), 'tid': source.get('trainer_id'), 's': status, 'n': now,
       'origin': origin, 'subject': source.get('subject') or source.get('title') or 'Action historique',
       'description': source.get('description'), 'due': source.get('due_at'), 'owner': source.get('owner'),
       'author': author, 'updated': source.get('updated_at') or now,
       'closed': source.get('closed_at') or source.get('completed_at'), 'answer': source.get('admin_response'), 'role': role, 'rid': rid})
    event_id = int(result.lastrowid)
    conn.execute(text('INSERT INTO quality_source_links(quality_event_id,source_kind,source_id,linked_by,linked_at) VALUES(:e,:k,:i,:a,:n)'),
                 {'e': event_id, 'k': kind, 'i': source['id'], 'a': actor.label, 'n': utcnow_iso()})
    _history_tx(conn, event_id, actor, 'REPRISE_HISTORIQUE', after={'source_kind': kind, 'source_id': source['id'], 'original_author': author,
                'original_created_at': now, 'original_status': legacy_state}, audience='INTERNAL', notify=False)
    if source.get('admin_response'):
        direction = 'VERS_BENEFICIAIRE' if role == 'BENEFICIARY' else 'VERS_INTERVENANT' if role == 'TRAINER' else 'INTERNE'
        conn.execute(text('''INSERT INTO quality_event_messages(quality_event_id,direction,author,message,channel,created_at,audience)
          VALUES(:e,:d,'LEGACY:ADMIN_AUTHOR_NOT_RECORDED',:m,'REPRISE',:n,:aud)'''),
          {'e': event_id, 'd': direction, 'm': source['admin_response'], 'n': source.get('updated_at') or now,
           'aud': 'PUBLIC' if role else 'INTERNAL'})
    _legacy_decision_tx(conn, actor, kind, source['id'], event_id, 'MAPPED', 'Source autonome reprise ; auteur et texte historiques conservés.')
    return event_id


def migrate_legacy(engine, actor, *, general_source_ids=None):
    """Repeatable, non-destructive correspondence. General or ambiguous sources
    require an explicit choice; titles alone never merge requests or permissions.

    general_source_ids is an explicit set of (source_kind, id) selected in this
    organization's administrative context. Omitting it never guesses a tenant.
    """
    require_admin(engine, actor)
    explicit = {(str(k), int(i)) for k, i in (general_source_ids or [])}
    result = {'events_adopted': 0, 'sources_created': 0, 'steps_created': 0, 'already_mapped': 0,
              'unresolved': [], 'mappings': []}
    with engine.begin() as conn:
        _actor_tx(conn, actor)
        for ev in _rows(conn, '''SELECT qe.*,COALESCE(qe.organization_id,a.organization_id) effective_organization_id
          FROM quality_events qe LEFT JOIN actions a ON a.id=qe.action_id
          WHERE (COALESCE(qe.organization_id,a.organization_id)=:o OR COALESCE(qe.organization_id,a.organization_id) IS NULL)
          AND qe.deleted_at IS NULL''', {'o': actor.organization_id}):
            if ev.get('go4_managed'):
                continue
            if not ev.get('effective_organization_id') and ('QUALITY_EVENT', ev['id']) not in explicit:
                result['unresolved'].append({'kind': 'QUALITY_EVENT', 'source_id': ev['id'],
                  'reason': 'Organisme non renseigné : ancienne action générale, choix administratif explicite requis.'})
                continue
            role, rid = _requester(ev)
            conn.execute(text('''UPDATE quality_events SET organization_id=:o,go4_managed=1,requester_role=:r,requester_id=:k
              WHERE id=:e'''), {'o': actor.organization_id, 'r': role, 'k': rid, 'e': ev['id']})
            _history_tx(conn, ev['id'], actor, 'ADOPTION_GO4', after={'reference_preserved': ev['public_id']}, notify=False)
            result['events_adopted'] += 1
        tables = [('TRAINER_REPORT', 'trainer_reports'), ('BENEFICIARY_REPORT', 'beneficiary_reports'),
                  ('QUALITY_ISSUE', 'quality_issues'), ('IMPROVEMENT_ACTION', 'improvement_actions')]
        for kind, table in tables:
            for src in _rows(conn, f'''SELECT src.*,a.organization_id source_organization_id FROM {table} src
              LEFT JOIN actions a ON a.id=src.action_id WHERE a.organization_id=:o OR src.action_id IS NULL ORDER BY src.id''', {'o': actor.organization_id}):
                prior = _one(conn, 'SELECT outcome,event_id FROM quality_migration_decisions WHERE source_kind=:k AND source_id=:i', {'k': kind, 'i': src['id']})
                if prior and prior['outcome'] == 'DELETED':
                    continue
                linked = _one(conn, 'SELECT quality_event_id FROM quality_source_links WHERE source_kind=:k AND source_id=:i', {'k': kind, 'i': src['id']})
                if kind == 'IMPROVEMENT_ACTION' and not linked:
                    linked = _one(conn, '''SELECT s.quality_event_id FROM quality_capa_source_links l JOIN quality_event_actions s ON s.id=l.quality_event_action_id
                      WHERE l.source_kind=:k AND l.source_id=:i''', {'k': kind, 'i': src['id']})
                if linked:
                    ev = _event_tx(conn, linked['quality_event_id'])
                    if ev and ev.get('effective_organization_id') == actor.organization_id:
                        _legacy_decision_tx(conn, actor, kind, src['id'], ev['id'], 'MAPPED', 'Correspondance explicite RC2 conservée.')
                        result['already_mapped'] += 1
                        result['mappings'].append({'kind': kind, 'source_id': src['id'], 'event_id': ev['id']})
                        # Import an older last reply only if no identical public reply is
                        # already represented. The original unknown author stays unknown.
                        if kind in ('TRAINER_REPORT', 'BENEFICIARY_REPORT') and src.get('admin_response'):
                            direction = 'VERS_INTERVENANT' if kind == 'TRAINER_REPORT' else 'VERS_BENEFICIAIRE'
                            present = _one(conn, '''SELECT id FROM quality_event_messages WHERE quality_event_id=:e AND message=:m
                              AND (direction=:d OR audience='PUBLIC')''', {'e': ev['id'], 'm': src['admin_response'], 'd': direction})
                            if not present:
                                conn.execute(text('''INSERT INTO quality_event_messages(quality_event_id,direction,author,message,channel,created_at,audience)
                                  VALUES(:e,:d,'LEGACY:ADMIN_AUTHOR_NOT_RECORDED',:m,'REPRISE',:n,'PUBLIC')'''),
                                  {'e': ev['id'], 'd': direction, 'm': src['admin_response'], 'n': src.get('updated_at') or src['created_at']})
                    continue
                if not src.get('source_organization_id') and (kind, src['id']) not in explicit:
                    item = {'kind': kind, 'source_id': src['id'], 'reason': 'Organisme non renseigné : choix administratif explicite requis.'}
                    result['unresolved'].append(item)
                    continue
                # Detect plausible old twins, but require explicit reconciliation;
                # a subject matching cannot justify merging identities or history.
                if kind in ('TRAINER_REPORT', 'BENEFICIARY_REPORT', 'QUALITY_ISSUE'):
                    candidates = _rows(conn, '''SELECT id FROM quality_events WHERE action_id IS :a AND subject=:s
                      AND COALESCE(description,'')=:d AND organization_id=:o AND deleted_at IS NULL''',
                      {'a': src.get('action_id'), 's': src.get('subject') or src.get('title'), 'd': src.get('description') or '', 'o': actor.organization_id})
                    if candidates:
                        reason = 'Rapprochement ambigu : lien humain nécessaire ; aucune fusion par intitulé.'
                        _legacy_decision_tx(conn, actor, kind, src['id'], None, 'REVIEW', reason)
                        result['unresolved'].append({'kind': kind, 'source_id': src['id'], 'reason': reason, 'candidate_ids': [c['id'] for c in candidates]})
                        continue
                if kind == 'IMPROVEMENT_ACTION' and src.get('issue_id'):
                    parent = _one(conn, "SELECT quality_event_id FROM quality_source_links WHERE source_kind='QUALITY_ISSUE' AND source_id=:i", {'i': src['issue_id']})
                    if not parent:
                        reason = 'L’ancienne affaire liée doit être rapprochée avant sa mesure.'
                        _legacy_decision_tx(conn, actor, kind, src['id'], None, 'REVIEW', reason)
                        result['unresolved'].append({'kind': kind, 'source_id': src['id'], 'reason': reason})
                        continue
                    event_id = parent['quality_event_id']
                    parent_event = _event_tx(conn, event_id)
                    if not parent_event or parent_event.get('effective_organization_id') != actor.organization_id:
                        raise PermissionError('Rattachement historique inter-organismes interdit.')
                    step = conn.execute(text('''INSERT INTO quality_event_actions(quality_event_id,title,description,owner_name,due_at,status,
                      created_by,created_at,updated_at,completed_at) VALUES(:e,:t,:d,:own,:due,:s,:a,:n,:n,:c)'''),
                      {'e': event_id, 't': src['title'], 'd': src.get('description'), 'own': src.get('owner'), 'due': src.get('due_at'),
                       's': src['status'], 'a': 'LEGACY:AUTHOR_NOT_RECORDED', 'n': src['created_at'], 'c': src.get('completed_at')})
                    conn.execute(text('''INSERT INTO quality_capa_source_links(quality_event_action_id,source_kind,source_id,linked_by,linked_at)
                      VALUES(:e,'IMPROVEMENT_ACTION',:i,:a,:n)'''), {'e': int(step.lastrowid), 'i': src['id'], 'a': actor.label, 'n': utcnow_iso()})
                    _legacy_decision_tx(conn, actor, kind, src['id'], event_id, 'MAPPED', 'Mesure devenue étape de son affaire explicitement liée.')
                    _history_tx(conn, event_id, actor, 'ETAPE_HISTORIQUE', after={'step_id': int(step.lastrowid), 'source_id': src['id']}, notify=False)
                    result['steps_created'] += 1
                else:
                    event_id = _legacy_event_tx(conn, actor, src, kind)
                    result['sources_created'] += 1
                result['mappings'].append({'kind': kind, 'source_id': src['id'], 'event_id': event_id})
    return result


def reconcile_legacy_source(engine, actor, event_id, source_kind, source_id, *, expected_version):
    """Confirm one exact historical correspondence, without merging distinct authors.

    General sources are assigned only through this explicit administrative choice.
    Existing sources, text, creation dates and replies remain in place.
    """
    _required_version(expected_version)
    from services import _QUALITY_SOURCE_TABLES, _quality_link_tx
    if source_kind not in _QUALITY_SOURCE_TABLES:
        raise ValueError('Cette source doit être reprise depuis son affaire ou comme action autonome.')
    with engine.begin() as conn:
        ev, _ = _access_tx(conn, actor, event_id, expected_version=expected_version)
        if actor.role != 'ADMIN':
            raise PermissionError('Le rapprochement historique est réservé à l’administration habilitée.')
        prior = _one(conn, 'SELECT * FROM quality_migration_decisions WHERE source_kind=:k AND source_id=:i',
                     {'k': source_kind, 'i': source_id})
        if prior and (prior['outcome'] == 'DELETED' or prior['organization_id'] != actor.organization_id):
            raise PermissionError('Cette source ne peut plus être rattachée dans cet organisme.')
        table = _QUALITY_SOURCE_TABLES[source_kind]
        src = _one(conn, f'SELECT * FROM {table} WHERE id=:i', {'i': source_id})
        if not src:
            raise ValueError('Source historique introuvable.')
        if src.get('action_id') != ev.get('action_id'):
            raise PermissionError('Le rattachement entre formations différentes est interdit.')
        if ev.get('action_id'):
            training = _one(conn, 'SELECT organization_id FROM actions WHERE id=:i', {'i': ev['action_id']})
            if not training or training['organization_id'] != actor.organization_id:
                raise PermissionError('Organisme de la source non compatible.')
            linked = _quality_link_tx(conn, event_id, source_kind, source_id, actor.label)
        else:
            if source_kind != 'QUALITY_ISSUE' or (src.get('title') != ev['subject'] or (src.get('description') or '') != (ev.get('description') or '')):
                raise ValueError('Une correspondance exacte de l’affaire générale est requise.')
            if src.get('campaign_id') and src['campaign_id'] != ev.get('campaign_id'):
                raise ValueError('Campagne historique incompatible.')
            existing = _one(conn, 'SELECT quality_event_id FROM quality_source_links WHERE source_kind=:k AND source_id=:i',
                            {'k': source_kind, 'i': source_id})
            if existing and existing['quality_event_id'] != event_id:
                raise ValueError('Source déjà rattachée à une autre action.')
            linked = not existing
            if linked:
                conn.execute(text('''INSERT INTO quality_source_links(quality_event_id,source_kind,source_id,linked_by,linked_at)
                  VALUES(:e,:k,:i,:a,:n)'''), {'e': event_id, 'k': source_kind, 'i': source_id, 'a': actor.label, 'n': utcnow_iso()})
                _history_tx(conn, event_id, actor, 'SOURCE_LIEE', after={'source_kind': source_kind, 'source_id': source_id}, notify=False)
        if not linked:
            return False
        _bump_tx(conn, ev, {})
        if source_kind in ('TRAINER_REPORT', 'BENEFICIARY_REPORT') and src.get('admin_response'):
            direction = 'VERS_INTERVENANT' if source_kind == 'TRAINER_REPORT' else 'VERS_BENEFICIAIRE'
            present = _one(conn, '''SELECT id FROM quality_event_messages WHERE quality_event_id=:e AND message=:m
              AND (direction=:d OR audience='PUBLIC')''', {'e': event_id, 'm': src['admin_response'], 'd': direction})
            if not present:
                conn.execute(text('''INSERT INTO quality_event_messages(quality_event_id,direction,author,message,channel,created_at,audience)
                  VALUES(:e,:d,'LEGACY:ADMIN_AUTHOR_NOT_RECORDED',:m,'REPRISE',:n,'PUBLIC')'''),
                  {'e': event_id, 'd': direction, 'm': src['admin_response'], 'n': src.get('updated_at') or src['created_at']})
        _legacy_decision_tx(conn, actor, source_kind, source_id, event_id, 'MAPPED',
                            'Correspondance exacte confirmée explicitement ; source et auteur conservés.')
        return True
