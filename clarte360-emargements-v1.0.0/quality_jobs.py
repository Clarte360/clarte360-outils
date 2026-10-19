"""GO4 worker integrations: bounded background watch, independent notification flow.

The existing worker remains the scheduler. No extra URL, service installation or
network call is made at import. Organization settings are disabled initially.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import smtplib
import threading
import time
from xml.sax.saxutils import escape

from db import audit, q, one

_watch_lock = threading.Lock()
_watch_thread = None
_notification_lock = threading.Lock()
_notification_thread = None


def _safe_audit(engine, code, **kwargs):
    try:
        audit(engine, code, **kwargs)
    except Exception:
        # A database/audit outage must not abort Teams and the other worker jobs.
        # No sensitive exception text is emitted in the fallback log.
        import logging
        logging.getLogger(__name__).error('%s: journal indisponible', code)


def _collect_watch_cycle(engine, now):
    from quality_service import QualityActor, require_admin
    from quality_watch import collect_source, WatchBusyError, get_schedule
    from zoneinfo import ZoneInfo
    started = time.monotonic()
    settings = q(engine, '''SELECT organization_id,updated_by FROM quality_watch_settings
      WHERE enabled=1 AND configuration_validated=1''')
    for configured in settings:
        try:
            actor = QualityActor('ADMIN', configured['updated_by'], configured['organization_id'])
            require_admin(engine, actor)
            schedule = get_schedule(engine, actor)
            local = now.astimezone(ZoneInfo(schedule['timezone']))
            due = local.replace(day=1, hour=schedule['hour'], minute=schedule['minute'], second=0, microsecond=0)
            if local < due:
                continue
            # Max five sources per worker cycle. Successful sources are never replayed
            # in that month; failed automatic calls wait a day, manual controls remain
            # available immediately. This keeps provider failures from a retry loop.
            sources = q(engine, '''SELECT s.id,s.last_successful_month,
              (SELECT MAX(r.started_at) FROM quality_watch_runs r WHERE r.source_id=s.id AND r.trigger='MONTHLY') last_attempt
              FROM quality_watch_sources s WHERE s.organization_id=:o AND s.active=1 AND s.configuration_validated=1
              ORDER BY s.id''', {'o': actor.organization_id})
            attempts = 0
            for source in sources:
                if source['last_successful_month'] == local.strftime('%Y-%m'):
                    continue
                if source.get('last_attempt'):
                    previous = datetime.fromisoformat(source['last_attempt'].replace('Z', '+00:00'))
                    if previous > now - timedelta(days=1):
                        continue
                if attempts >= 5:
                    break
                try:
                    collect_source(engine, actor, source['id'], trigger='MONTHLY',
                                   now=now + timedelta(seconds=time.monotonic() - started))
                except WatchBusyError:
                    pass
                except Exception as error:
                    _safe_audit(engine, 'QUALITY_WATCH_JOB_FAILED', actor='quality_worker', entity_type='quality_watch_source',
                          entity_id=source['id'], details={'error_type': type(error).__name__})
                attempts += 1
        except Exception as error:
            _safe_audit(engine, 'QUALITY_WATCH_CONFIGURATION_FAILED', actor='quality_worker', entity_type='organization',
                  entity_id=configured['organization_id'], details={'error_type': type(error).__name__})


def start_due_watch_jobs(engine, now=None):
    """A daemon worker avoids delaying Teams, existing reminders and connectors."""
    global _watch_thread
    if not one(engine, 'SELECT organization_id FROM quality_watch_settings WHERE enabled=1 AND configuration_validated=1 LIMIT 1'):
        return False
    with _watch_lock:
        if _watch_thread is not None and _watch_thread.is_alive():
            return False
        _watch_thread = threading.Thread(target=_collect_watch_cycle,
                                         args=(engine, now or datetime.now(timezone.utc)),
                                         name='clarte360-quality-watch', daemon=True)
        _watch_thread.start()
        return True


def process_quality_notifications(engine, smtp, base_url, *, send_mail=None, now=None):
    """Both global SMTP and per-organization consent must enable delivery."""
    from quality_notifications import process_outbox, schedule_reminders, RetryableDeliveryError
    schedule_reminders(engine, now=now)
    if not smtp.get('enabled'):
        return process_outbox(engine, dry_run=True, now=now)
    if send_mail is None:
        from mailer import send_mail

    def provider(to, subject, body, *, idempotency_key):
        try:
            send_mail(dict(smtp), to, subject, '<p>' + escape(body).replace('\n', '<br>') + '</p>')
        except (smtplib.SMTPConnectError, smtplib.SMTPAuthenticationError, smtplib.SMTPSenderRefused,
                smtplib.SMTPRecipientsRefused, smtplib.SMTPDataError, ConnectionRefusedError) as error:
            raise RetryableDeliveryError('Refus explicite avant acceptation') from error
        # Legacy SMTP cannot guarantee a provider idempotency key. The outbox claims
        # once, and holds any uncertain result; it never promises exactly-once SMTP.
        return {'accepted': True, 'receipt': 'SMTP a accepté la remise'}

    return process_outbox(engine, provider, base_url=base_url, now=now, dry_run=False)


def start_quality_notification_jobs(engine, smtp, base_url, *, send_mail=None, now=None):
    """A slow SMTP provider must not delay Teams or the existing reminders.

    Only one GO4 delivery thread runs in a worker process. Database claims also
    protect against a second process. Provider ambiguity remains held in outbox.
    """
    global _notification_thread
    with _notification_lock:
        if _notification_thread is not None and _notification_thread.is_alive():
            return False

        def deliver():
            try:
                process_quality_notifications(engine, dict(smtp), base_url, send_mail=send_mail, now=now)
            except Exception as error:
                _safe_audit(engine, 'QUALITY_NOTIFICATION_JOB_FAILED', actor='quality_worker',
                            details={'error_type': type(error).__name__})

        _notification_thread = threading.Thread(target=deliver, name='clarte360-quality-notifications', daemon=True)
        _notification_thread.start()
        return True


def run_quality_jobs(engine, smtp, base_url, *, send_mail=None, now=None):
    """Failure isolation: no Quality failure aborts the existing worker cycle."""
    result = {'watch_started': False, 'notifications': None, 'errors': []}
    try:
        result['watch_started'] = start_due_watch_jobs(engine, now=now)
    except Exception as error:
        result['errors'].append(type(error).__name__)
        _safe_audit(engine, 'QUALITY_WATCH_SCHEDULER_FAILED', actor='quality_worker', details={'error_type': type(error).__name__})
    try:
        if smtp.get('enabled'):
            result['notifications'] = {'background': True, 'started': start_quality_notification_jobs(
                engine, smtp, base_url, send_mail=send_mail, now=now)}
        else:
            result['notifications'] = process_quality_notifications(engine, smtp, base_url, send_mail=send_mail, now=now)
    except Exception as error:
        result['errors'].append(type(error).__name__)
        _safe_audit(engine, 'QUALITY_NOTIFICATION_JOB_FAILED', actor='quality_worker', details={'error_type': type(error).__name__})
    return result
