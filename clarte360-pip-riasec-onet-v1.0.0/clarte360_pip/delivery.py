"""Technical finalization: immutable accompanied PDFs and additive delivery.

No GDA imports/writes. Receipts are private PIP data, separate from PUBLIC studies.
SMTP acceptance is not a guarantee that the recipient has opened/received the mail.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from clarte360_pip.domain import RunMode
from clarte360_pip.framework.config import PERSISTENT_DATA_DIR
from clarte360_pip.framework.storage_io import atomic_json, storage_lock
from clarte360_pip.framework.validation import validate_safe_id
from clarte360_pip.framework.public_access import verified_public_email
from clarte360_pip.connectors.gestion_actions import (
    GestionActionsPort, persist_report_document, read_report_document,
    report_path, report_reference, REPORT_NAMES, MAX_REPORT_BYTES,
)

PIP_NAME = 'rapport_pip_riasec_clarte360.pdf'
ONET_NAME = 'rapport_onet_interest_profiler.pdf'


def _id(value):
    value = validate_safe_id(value, 'identifiant de passation')
    if value in {'.', '..'}:
        raise ValueError('Identifiant invalide.')
    return value


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def accompanied_scope(state):
    launch = state.get('launch_context')
    if not launch or launch.mode is not RunMode.ACCOMPANIMENT:
        raise ValueError('La publication documentaire est reservee au mode accompagne.')
    return {k: getattr(launch, k) for k in ('action_id', 'beneficiary_id', 'participant_id', 'prescription_id')} | {
        'passation_id': _id(state.get('passation_id'))}


def _validate_receipt(receipt, scope):
    if not isinstance(receipt, dict) or receipt.get('scope') != scope:
        raise ValueError('Suivi de livraison incoherent avec la passation.')


def accompanied_report(state, name: str, builder: Callable[[], bytes]) -> bytes:
    if name not in REPORT_NAMES:
        raise ValueError('Nom de rapport hors contrat.')
    scope = accompanied_scope(state)
    run = scope['passation_id']
    with storage_lock(PERSISTENT_DATA_DIR / '.locks' / f'build-{run}.lock'):
        refs = list(state.get('report_documents') or [])
        found = [ref for ref in refs if ref.get('file_name') == name]
        if len(found) > 1:
            raise ValueError('Plusieurs references pour le meme rapport.')
        if found:
            return read_report_document(run, found[0])
        path = report_path(run, name)
        if path.exists():  # interrupted snapshot after a successful file write
            if not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
                raise ValueError('Rapport enregistre invalide ou trop volumineux.')
            content = path.read_bytes()
            ref = report_reference(run, name, content)
        else:
            content = builder()
            ref = persist_report_document(run, name, content)
        refs.append(ref)
        state['report_documents'] = refs
        return content


def _legacy_published(scope):
    """Recover proof from PIP's journal; the old Boolean is not enough for two PDFs."""
    published = {}
    journal = PERSISTENT_DATA_DIR / 'connector_outbox' / 'gestion_actions' / 'events.jsonl'
    if journal.exists():
        with journal.open('rb') as handle:
            for raw in handle:
                if not raw.endswith(b'\n'):
                    break  # unfinished final record is never considered published
                if not raw.strip():
                    continue
                event = json.loads(raw)
                payload = event.get('payload') or {}
                if event.get('event_type') == 'TERMINE' and all(payload.get(k) == v for k, v in scope.items()):
                    for doc in payload.get('documents') or []:
                        if doc.get('file_name') in REPORT_NAMES:
                            published[doc['file_name']] = doc.get('sha256')
    return published


def publish_accompanied_reports(state, make_payload: Callable[[list], dict], port=None) -> int:
    scope = accompanied_scope(state)
    run = scope['passation_id']
    path = PERSISTENT_DATA_DIR / 'delivery' / 'accompanied' / f'{run}.json'
    port = port or GestionActionsPort(None)
    count = 0
    with storage_lock(PERSISTENT_DATA_DIR / '.locks' / f'publish-{run}.lock'):
        if path.exists():
            receipt = json.loads(path.read_text(encoding='utf-8'))
            _validate_receipt(receipt, scope)
        else:
            receipt = {'schema': 'clarte360.pip.delivery.v1', 'scope': scope,
                       'published_documents': _legacy_published(scope), 'pending_payload': None}
        published = receipt['published_documents']
        # Finish a previous intent using its frozen payload, not a new timestamp/version.
        intent = receipt.get('pending_payload')
        if intent:
            if any(intent.get(k) != v for k, v in scope.items()):
                raise ValueError('Intention de publication incoherente.')
            for doc in intent['documents']:
                read_report_document(run, doc)
            port.publish_event('TERMINE', intent)
            published.update({doc['file_name']: doc['sha256'] for doc in intent['documents']})
            receipt['pending_payload'] = None
            atomic_json(path, receipt)
            count += len(intent['documents'])
        refs = list(state.get('report_documents') or [])
        if len({doc['file_name'] for doc in refs}) != len(refs):
            raise ValueError('References de rapports dupliquees.')
        missing = []
        for doc in refs:
            if doc.get('file_name') not in REPORT_NAMES:
                raise ValueError('Rapport hors du contrat de transmission.')
            read_report_document(run, doc)
            name = doc['file_name']
            if name in published and published[name] != doc['sha256']:
                raise ValueError('Un rapport deja publie ne peut pas etre remplace.')
            if name not in published:
                missing.append(doc)
        if missing:
            payload = make_payload(missing)
            if any(payload.get(k) != v for k, v in scope.items()):
                raise ValueError('Publication hors de la prescription attendue.')
            receipt['pending_payload'] = payload
            atomic_json(path, receipt)
            port.publish_event('TERMINE', payload)
            published.update({doc['file_name']: doc['sha256'] for doc in missing})
            receipt['pending_payload'] = None
            atomic_json(path, receipt)
            count += len(missing)
        else:
            atomic_json(path, receipt)
        state.setdefault('delivery_state', {})['published_documents'] = dict(published)
        state['final_event_published'] = bool(refs) and all(d['file_name'] in published for d in refs)
    return count


def _email_receipt(state, address, names):
    participant = _id(state.get('public_participant_id'))
    run = _id(state.get('passation_id'))
    address_key = hashlib.sha256(address.encode('utf-8')).hexdigest()
    scope = {'participant_id': participant, 'passation_id': run, 'recipient_sha256': address_key}
    path = PERSISTENT_DATA_DIR / 'public' / 'report_delivery' / participant / f'{run}-{address_key}.json'
    if path.exists():
        record = json.loads(path.read_text(encoding='utf-8'))
        _validate_receipt(record, scope)
    else:
        record = {'schema': 'clarte360.pip.email-delivery.v1', 'scope': scope,
                  'sent': {}, 'attempts': {}, 'message': '', 'last_sent_at': None}
        # Preserve legacy "already sent" semantics on imported valid snapshots.
        # No fabricated proof of delivery: marked explicitly as legacy information.
        if not state.get('delivery_state', {}).get('email'):
            if state.get('final_report_email_sent'):
                record['sent'] = {name: 'legacy_snapshot' for name in names}
            elif state.get('final_report_email_attempted'):
                record['attempts'] = {name: {'count': 1, 'status': 'FAILED', 'at': None} for name in names}
    return path, record


def public_report_mail(state, attachments, settings, sender, *, retry=False, now=None):
    launch = state.get('launch_context')
    if not launch or launch.mode is not RunMode.PUBLIC:
        raise ValueError('Envoi de rapports e-mail reserve au mode public.')
    address = verified_public_email(state)
    if not address:
        return {'status': 'VERIFY', 'message': 'Confirmez votre adresse par un code avant l envoi.', 'sent_now': []}
    names = [item[0] for item in attachments]
    if len(set(names)) != len(names) or not set(names).issubset(REPORT_NAMES):
        raise ValueError('Pieces jointes invalides.')
    run = _id(state.get('passation_id'))
    current_time = now or datetime.now(timezone.utc)
    timestamp = current_time.isoformat(timespec='seconds')
    with storage_lock(PERSISTENT_DATA_DIR / '.locks' / f'email-{run}.lock', timeout=20):
        path, record = _email_receipt(state, address, names)
        unsent = [item for item in attachments if item[0] not in record['sent']]
        eligible = []
        for item in unsent:
            last = record['attempts'].get(item[0])
            if last is None:
                eligible.append(item)
            elif retry and last.get('count', 0) < 3:
                at = datetime.fromisoformat(last['at']) if last.get('at') else None
                if at is None or (current_time - at).total_seconds() >= 60:
                    eligible.append(item)
        sent_now = []
        if eligible:
            for name, content, mime in eligible:
                previous = record['attempts'].get(name) or {}
                record['attempts'][name] = {'count': previous.get('count', 0) + 1,
                                            'status': 'IN_PROGRESS', 'at': timestamp}
            # Persist before network IO: a crash cannot cause silent infinite re-sends.
            atomic_json(path, record)
            ok, message = sender(
                settings, 'Clarte360 - vos rapports PIP RIASEC',
                'Votre parcours est termine. Vos rapports sont joints pour votre usage personnel.\n\nClarte360 - www.clarte360.com',
                to_email=address, attachments=eligible)
            record['message'] = message
            for name, content, mime in eligible:
                record['attempts'][name]['status'] = 'SENT' if ok else 'FAILED'
                if ok:
                    record['sent'][name] = hashlib.sha256(content).hexdigest()
                    sent_now.append(name)
            if ok:
                record['last_sent_at'] = timestamp
            atomic_json(path, record)
        all_sent = all(name in record['sent'] for name in names)
        state['final_report_email_attempted'] = bool(record['attempts'] or record['sent'])
        state['final_report_email_sent'] = all_sent
        state['final_report_email_sent_at'] = record.get('last_sent_at')
        summary = {'sent_documents': list(record['sent']), 'attempted_documents': list(record['attempts']),
                   'recipient_sha256': record['scope']['recipient_sha256'], 'last_message': record.get('message', '')}
        state.setdefault('delivery_state', {})['email'] = summary
        return {'status': 'SENT' if all_sent else 'FAILED', 'sent_now': sent_now,
                'message': record.get('message') or 'L envoi precedent n est pas confirme. Verifiez votre messagerie avant de reessayer.',
                'recipient': address, 'can_retry': any((record['attempts'].get(item[0]) or {}).get('count', 0) < 3 for item in unsent)}
