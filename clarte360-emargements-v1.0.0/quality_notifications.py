"""GO4 transactional notification outbox. No mail is sent merely by importing it.

An accepted email is not a read receipt. Ambiguous delivery is held for review,
never blindly retried. Tests inject a provider; SMTP is disabled by default.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets

from sqlalchemy import text
from db import utcnow_iso


class RetryableDeliveryError(Exception):
    """Provider guarantees that no message was accepted."""


class DeliveryUncertainError(Exception):
    """Acceptance cannot be determined; automatic retry could duplicate a mail."""


def init_notification_schema(conn):
    conn.execute(text('''CREATE TABLE IF NOT EXISTS quality_notification_outbox (
      id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, history_id INTEGER,
      source_key TEXT NOT NULL, organization_id INTEGER NOT NULL, recipient_role TEXT NOT NULL,
      recipient_id TEXT NOT NULL, channel TEXT NOT NULL DEFAULT 'EMAIL', event_kind TEXT NOT NULL,
      audience TEXT NOT NULL, due_at TEXT, deadline_snapshot TEXT,
      status TEXT NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0,
      claim_token TEXT, claimed_at TEXT, accepted_at TEXT, provider_receipt TEXT,
      last_error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(source_key,recipient_role,recipient_id,channel))'''))
    conn.execute(text('CREATE INDEX IF NOT EXISTS ix_quality_outbox_pending ON quality_notification_outbox(status,due_at,id)'))


def enqueue_event_tx(conn, event_id, history_id, kind, audience='PUBLIC'):
    from quality_service import _one, _rows, _event_tx, _requester, _permissions_tx, _subject_active_tx, QualityActor
    event = _event_tx(conn, event_id)
    if not event:
        return 0
    org = event.get('effective_organization_id')
    if not org:
        return 0
    recipients = {('ADMIN', r['email'].lower()) for r in _rows(conn, 'SELECT email FROM admins WHERE active=1')}
    recipients.add(_requester(event))
    if event.get('assigned_role') and event.get('assigned_id'):
        recipients.add((event['assigned_role'], str(event['assigned_id'])))
    recipients.update((g['role'], g['subject_id']) for g in _rows(conn, 'SELECT role,subject_id FROM quality_access_grants WHERE event_id=:e AND revoked_at IS NULL', {'e': event_id}))
    added = 0
    for role, key in sorted(recipients):
        if not _subject_active_tx(conn, role, key):
            continue
        actor = QualityActor(role, key, org)
        permissions = _permissions_tx(conn, actor, event)
        if not permissions['read'] or (audience == 'INTERNAL' and not permissions['internal']):
            continue
        source_key = f'go4:{event_id}:{history_id}'
        params = {'event': event_id, 'history': history_id, 'source': source_key, 'org': org,
                  'role': role, 'key': key, 'kind': kind, 'audience': audience, 'now': utcnow_iso(),
                  'action': event.get('action_id')}
        # Both durable pointer and outbox are committed with the business event.
        added += conn.execute(text('''INSERT OR IGNORE INTO quality_notification_outbox(
          event_id,history_id,source_key,organization_id,recipient_role,recipient_id,event_kind,audience,created_at,updated_at)
          VALUES(:event,:history,:source,:org,:role,:key,:kind,:audience,:now,:now)'''), params).rowcount
        conn.execute(text('''INSERT OR IGNORE INTO workspace_notifications(source_system,source_event_id,recipient_role,
          recipient_key,action_id,event_code,category,target_kind,target_id,display_text,created_at)
          VALUES('GDA',:source,:role,:key,:action,'QUALITY_STATUS','INFO','QUALITY',:event,
          'Votre suivi Qualité a été actualisé',:now)'''), params)
    return added


def invalidate_pending_tx(conn, event_id):
    """A schedule edit or closure supersedes pending deadline reminders atomically."""
    conn.execute(text('''UPDATE quality_notification_outbox SET status='CANCELLED',last_error='Échéance remplacée ou action close',updated_at=:n
      WHERE event_id=:e AND event_kind='REMINDER' AND status IN ('PENDING','RETRY')'''), {'e': event_id, 'n': utcnow_iso()})
    conn.execute(text("DELETE FROM workspace_notifications WHERE source_system='GDA' AND source_event_id LIKE :prefix"),
                 {'prefix': f'go4:reminder:{event_id}:%'})


def schedule_reminders(engine, now=None):
    from quality_service import _rows, _event_tx, FINAL
    now = now or datetime.now(timezone.utc)
    added = 0
    with engine.begin() as conn:
        rows = _rows(conn, '''SELECT qe.id,s.reminder_days FROM quality_events qe JOIN quality_organization_settings s
          ON s.organization_id=qe.organization_id WHERE s.reminder_days IS NOT NULL AND qe.deleted_at IS NULL
          AND qe.due_at IS NOT NULL AND qe.go4_managed=1''')
        for row in rows:
            ev = _event_tx(conn, row['id'])
            if ev['status'] in FINAL:
                continue
            due = datetime.fromisoformat(ev['due_at'].replace('Z', '+00:00'))
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if now < due - timedelta(days=int(row['reminder_days'])):
                continue
            history = conn.execute(text('SELECT MAX(id) FROM quality_event_history WHERE quality_event_id=:e'), {'e': ev['id']}).scalar()
            # Unique per effective deadline, not per worker pass or current row version.
            key = f'go4:reminder:{ev["id"]}:{ev["due_at"]}'
            from quality_service import _permissions_tx, QualityActor, _subject_active_tx
            recipients = {('ADMIN', a['email'].lower()) for a in _rows(conn, 'SELECT email FROM admins WHERE active=1')}
            if ev.get('assigned_id'):
                recipients.add((ev['assigned_role'], ev['assigned_id']))
            for role, rid in recipients:
                if not _subject_active_tx(conn, role, rid) or not _permissions_tx(conn, QualityActor(role, rid, ev['organization_id']), ev)['read']:
                    continue
                added += conn.execute(text('''INSERT OR IGNORE INTO quality_notification_outbox(event_id,history_id,source_key,organization_id,
                  recipient_role,recipient_id,event_kind,audience,due_at,deadline_snapshot,created_at,updated_at)
                  VALUES(:e,:h,:key,:o,:role,:rid,'REMINDER','INTERNAL',:due,:snapshot,:n,:n)'''),
                  {'e': ev['id'], 'h': history, 'key': key, 'o': ev['organization_id'], 'role': role, 'rid': rid,
                   'due': (due - timedelta(days=int(row['reminder_days']))).isoformat(), 'snapshot': ev['due_at'], 'n': now.isoformat()}).rowcount
                conn.execute(text('''INSERT OR IGNORE INTO workspace_notifications(source_system,source_event_id,recipient_role,recipient_key,
                  action_id,event_code,category,target_kind,target_id,display_text,created_at)
                  VALUES('GDA',:source,:r,:k,:a,'QUALITY_STATUS','ACTION','QUALITY',:e,'Une échéance Qualité est à examiner',:n)'''),
                  {'source': key, 'r': role, 'k': rid, 'a': ev.get('action_id'), 'e': str(ev['id']), 'n': now.isoformat()})
    return added


def _recipient_email_tx(conn, role, key):
    from quality_service import _one
    queries = {
        'ADMIN': 'SELECT email FROM admins WHERE lower(email)=:k AND active=1',
        'TRAINER': 'SELECT email FROM trainers WHERE id=:k AND active=1',
        'BENEFICIARY': 'SELECT email FROM beneficiary_portal_accounts WHERE beneficiary_id=:k AND active=1',
        'CLIENT': 'SELECT email FROM client_portal_accounts WHERE id=:k AND active=1',
    }
    row = _one(conn, queries[role], {'k': key})
    return (row or {}).get('email')


def process_outbox(engine, send_email=None, *, base_url='', now=None, dry_run=True, limit=50):
    """Deliver only when explicitly enabled globally and per organization.

    Provider signature: send_email(to, subject, body, idempotency_key=...). It must
    return an accepted receipt. Definite pre-accept failures use RetryableDeliveryError.
    Every other uncertain error is held for manual review. A crash after claim is
    also held, making the unavoidable SMTP acknowledgement gap explicit.
    """
    from quality_service import _rows, _one, _access_tx, QualityActor, FINAL
    now = now or datetime.now(timezone.utc)
    result = {'accepted': 0, 'retry': 0, 'unknown': 0, 'cancelled': 0, 'pending': 0}
    if dry_run or send_email is None:
        with engine.connect() as conn:
            result['pending'] = _one(conn, "SELECT COUNT(*) n FROM quality_notification_outbox WHERE status IN ('PENDING','RETRY')")['n']
        return result
    from urllib.parse import urlsplit
    url = urlsplit(base_url)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('URL authentifiée HTTPS de l’application requise pour les notifications.')
    with engine.begin() as conn:
        conn.execute(text('''UPDATE quality_notification_outbox SET status='UNKNOWN',last_error='Interruption après prise en charge : vérifier avant toute reprise',updated_at=:n
          WHERE status='SENDING' AND claimed_at<:old'''), {'n': now.isoformat(), 'old': (now-timedelta(minutes=15)).isoformat()})
        jobs = _rows(conn, '''SELECT o.id FROM quality_notification_outbox o JOIN quality_organization_settings s ON s.organization_id=o.organization_id
          WHERE s.email_enabled=1 AND o.status IN ('PENDING','RETRY') AND (o.due_at IS NULL OR o.due_at<=:n) ORDER BY o.id LIMIT :lim''',
          {'n': now.isoformat(), 'lim': max(1, min(200, int(limit)))})
    for candidate in jobs:
        claim = secrets.token_hex(12)
        with engine.begin() as conn:
            job = _one(conn, 'SELECT * FROM quality_notification_outbox WHERE id=:i', {'i': candidate['id']})
            if not job or job['status'] not in ('PENDING', 'RETRY'):
                continue
            settings = _one(conn, 'SELECT email_enabled FROM quality_organization_settings WHERE organization_id=:o',
                            {'o': job['organization_id']})
            if not settings or not settings['email_enabled']:
                # A user may disable delivery while an earlier provider call is in
                # progress. Consent is re-read for every claim, never cached per lot.
                continue
            try:
                actor = QualityActor(job['recipient_role'], job['recipient_id'], job['organization_id'])
                ev, perms = _access_tx(conn, actor, job['event_id'])
                if ev.get('data_classification') != 'REAL':
                    raise PermissionError('Les essais ou données non qualifiées n’envoient pas de courriel automatique')
                if job['audience'] == 'INTERNAL' and not perms['internal'] and job['event_kind'] != 'REMINDER':
                    raise PermissionError('Audience révoquée')
                if job['event_kind'] == 'REMINDER' and (ev['status'] in FINAL or ev['due_at'] != job['deadline_snapshot']):
                    raise PermissionError('Échéance obsolète')
                recipient = _recipient_email_tx(conn, actor.role, actor.key)
                if not recipient or '@' not in recipient:
                    raise PermissionError('Adresse indisponible')
            except (PermissionError, ValueError, TypeError):
                conn.execute(text("UPDATE quality_notification_outbox SET status='CANCELLED',last_error='Accès ou destinataire non valable',updated_at=:n WHERE id=:i"), {'i': job['id'], 'n': now.isoformat()})
                result['cancelled'] += 1
                continue
            claimed = conn.execute(text("""UPDATE quality_notification_outbox SET status='SENDING',attempts=attempts+1,claim_token=:c,claimed_at=:n,updated_at=:n
              WHERE id=:i AND status IN ('PENDING','RETRY')"""), {'i': job['id'], 'c': claim, 'n': now.isoformat()}).rowcount
            if not claimed:
                continue
        # No title, case reference, attachment, reply, diagnosis or internal note in mail.
        body = 'Une information vous attend dans votre espace Qualité. Connectez-vous pour la consulter.\n' + base_url.rstrip('/')
        status, error, receipt = 'ACCEPTED', None, None
        try:
            reply = send_email(recipient, 'CLARTÉ360 — Suivi Qualité', body,
                               idempotency_key=f'{job["source_key"]}:{job["recipient_role"]}:{job["recipient_id"]}:EMAIL')
            if not isinstance(reply, dict) or reply.get('accepted') is not True:
                raise DeliveryUncertainError('Accusé fournisseur absent')
            receipt = str(reply.get('receipt') or 'accepté par le fournisseur')[:200]
            result['accepted'] += 1
        except RetryableDeliveryError:
            status, error = 'RETRY', 'Échec avant acceptation ; reprise autorisée'
            result['retry'] += 1
        except Exception:
            status, error = 'UNKNOWN', 'Résultat d’envoi incertain ; vérification requise avant reprise'
            result['unknown'] += 1
        with engine.begin() as conn:
            conn.execute(text('''UPDATE quality_notification_outbox SET status=:s,last_error=:err,provider_receipt=:receipt,
              accepted_at=:accepted,updated_at=:n WHERE id=:i AND claim_token=:c'''),
              {'s': status, 'err': error, 'receipt': receipt, 'accepted': now.isoformat() if status == 'ACCEPTED' else None,
               'n': now.isoformat(), 'i': job['id'], 'c': claim})
    return result
