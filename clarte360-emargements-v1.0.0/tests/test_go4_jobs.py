"""GO4 worker boundaries: fake SQLite, blocked network, controlled daemon lifetimes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import smtplib
import socket
import threading
from types import SimpleNamespace

import pytest

from db import execute, init_db, make_engine, one, q, utcnow_iso
import quality_jobs as jobs
import quality_service as quality
import quality_watch as watch


NOW = datetime(2026, 10, 19, 10, 0, tzinfo=timezone.utc)
PORTAL = 'https://portal.example.invalid'
ADMIN = 'jobs-admin@example.invalid'


@pytest.fixture(autouse=True)
def offline_and_isolated_threads(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Real network and DNS are forbidden in GO4 worker tests')

    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)
    for name in ('_watch_thread', '_notification_thread'):
        previous = getattr(jobs, name, None)
        assert previous is None or not previous.is_alive(), 'Another test left a GO4 thread running'
        monkeypatch.setattr(jobs, name, None)
    yield
    for name in ('_watch_thread', '_notification_thread'):
        thread = getattr(jobs, name, None)
        if thread is not None:
            thread.join(3)
            assert not thread.is_alive(), 'A GO4 test did not release its daemon thread'


@pytest.fixture
def env(tmp_path):
    engine = make_engine('sqlite:///' + str(tmp_path / 'fictitious-jobs.sqlite'))
    init_db(engine)
    stamp = utcnow_iso()
    orgs = [execute(engine, '''INSERT INTO organizations(name,active,created_at,updated_at)
        VALUES(:name,1,:n,:n)''', {'name': 'Fictitious jobs organization ' + str(i), 'n': stamp})
        for i in (1, 2)]
    execute(engine, '''INSERT INTO admins(email,password_hash,full_name,role,active,created_at)
        VALUES(:e,'fictitious','Fictitious admin','ADMIN',1,:n)''', {'e': ADMIN, 'n': stamp})
    actors = [quality.QualityActor('ADMIN', ADMIN, oid) for oid in orgs]
    yield engine, actors
    engine.dispose()


def add_source(engine, actor, name, *, active=True):
    return watch.save_source(engine, actor, name=name, category='TECHNOLOGIE',
        url='https://feeds.example.com/' + name, format='JSON', active=active,
        configuration_validated=True, point_zero=NOW - timedelta(days=30))


def activate_schedule(engine, actor):
    return watch.save_schedule(engine, actor, enabled=True, configuration_validated=True,
        timezone='Europe/Paris', hour=9, minute=0)


def add_notification(engine, actor):
    return quality.create_action(engine, actor, 'Contexte fictif privé à ne pas inclure dans le mail',
        command_id='worker-fictitious-action')


def test_worker_inactive_by_default_keeps_notifications_pending_without_sender(env):
    engine, actors = env
    add_notification(engine, actors[0])
    calls = []
    result = jobs.run_quality_jobs(engine, {'enabled': False}, PORTAL,
        send_mail=lambda *args, **kwargs: calls.append(args), now=NOW)
    assert result['watch_started'] is False and result['errors'] == []
    assert result['notifications']['pending'] == 1 and calls == []
    assert jobs._watch_thread is None and jobs._notification_thread is None
    assert one(engine, 'SELECT status FROM quality_notification_outbox')['status'] == 'PENDING'


def test_global_smtp_does_not_override_organization_opt_out(env):
    engine, actors = env
    add_notification(engine, actors[0])
    calls = []
    result = jobs.process_quality_notifications(engine, {'enabled': True}, PORTAL,
        send_mail=lambda *args, **kwargs: calls.append(args), now=NOW)
    assert result['accepted'] == 0 and calls == []
    assert one(engine, 'SELECT status FROM quality_notification_outbox')['status'] == 'PENDING'


@pytest.mark.parametrize('failing_part', ['watch', 'notifications'])
def test_one_job_failure_and_broken_audit_do_not_abort_other_worker_flow(monkeypatch, failing_part, caplog):
    reached = []

    def watch_start(*args, **kwargs):
        reached.append('watch')
        if failing_part == 'watch':
            raise RuntimeError('PRIVATE exception context')
        return True

    def notifications(*args, **kwargs):
        reached.append('notifications')
        if failing_part == 'notifications':
            raise RuntimeError('PRIVATE exception context')
        return {'pending': 0}

    def broken_audit(*args, **kwargs):
        raise OSError('PRIVATE audit context')

    monkeypatch.setattr(jobs, 'start_due_watch_jobs', watch_start)
    monkeypatch.setattr(jobs, 'process_quality_notifications', notifications)
    monkeypatch.setattr(jobs, 'audit', broken_audit)
    result = jobs.run_quality_jobs(None, {'enabled': False}, PORTAL, now=NOW)
    reached.append('existing-RC2-worker-continues')
    assert reached == ['watch', 'notifications', 'existing-RC2-worker-continues']
    assert result['errors'] == ['RuntimeError']
    assert 'journal indisponible' in caplog.text and 'PRIVATE' not in caplog.text
    if failing_part == 'watch':
        assert result['notifications'] == {'pending': 0}
    else:
        assert result['watch_started'] is True


def test_source_error_and_broken_audit_preserve_later_sources(env, monkeypatch, caplog):
    engine, actors = env
    actor = actors[0]
    activate_schedule(engine, actor)
    ids = [add_source(engine, actor, name) for name in ('first', 'second')]
    visited = []

    def collect(engine_arg, actor_arg, source_id, **kwargs):
        visited.append(source_id)
        if source_id == ids[0]:
            raise RuntimeError('PRIVATE source body')
        return {'status': 'SUCCESS'}

    monkeypatch.setattr(watch, 'collect_source', collect)
    monkeypatch.setattr(jobs, 'audit', lambda *args, **kwargs: (_ for _ in ()).throw(OSError('PRIVATE audit body')))
    jobs._collect_watch_cycle(engine, NOW)
    assert visited == ids
    assert 'QUALITY_WATCH_JOB_FAILED' in caplog.text and 'PRIVATE' not in caplog.text


def test_revoked_schedule_owner_and_broken_audit_preserve_other_organization(env, monkeypatch, caplog):
    engine, actors = env
    for actor in actors:
        activate_schedule(engine, actor)
        add_source(engine, actor, 'source-' + str(actor.organization_id))
    execute(engine, 'UPDATE quality_watch_settings SET updated_by=:who WHERE organization_id=:o',
        {'who': 'revoked@example.invalid', 'o': actors[0].organization_id})
    visited = []
    monkeypatch.setattr(watch, 'collect_source', lambda engine_arg, actor_arg, source_id, **kwargs:
        visited.append(actor_arg.organization_id))
    monkeypatch.setattr(jobs, 'audit', lambda *args, **kwargs: (_ for _ in ()).throw(OSError('PRIVATE audit body')))
    jobs._collect_watch_cycle(engine, NOW)
    assert visited == [actors[1].organization_id]
    assert 'QUALITY_WATCH_CONFIGURATION_FAILED' in caplog.text and 'PRIVATE' not in caplog.text


def test_each_source_receives_fresh_clock_for_its_lease(env, monkeypatch):
    engine, actors = env
    activate_schedule(engine, actors[0])
    ids = [add_source(engine, actors[0], name) for name in ('clock-a', 'clock-b', 'clock-c')]
    ticks = iter([100.0, 100.0, 161.0, 223.0])
    monkeypatch.setattr(jobs, 'time', SimpleNamespace(monotonic=lambda: next(ticks)))
    started = []

    def collect(engine_arg, actor_arg, source_id, *, trigger, now):
        assert trigger == 'MONTHLY'
        started.append((source_id, now))

    monkeypatch.setattr(watch, 'collect_source', collect)
    jobs._collect_watch_cycle(engine, NOW)
    assert started == list(zip(ids, [NOW, NOW + timedelta(seconds=61), NOW + timedelta(seconds=123)]))


def test_calendar_respects_local_due_time_monthly_success_daily_backoff_and_batch_limit(env, monkeypatch):
    engine, actors = env
    actor = actors[0]
    activate_schedule(engine, actor)
    completed = add_source(engine, actor, 'already-completed')
    recent = add_source(engine, actor, 'recent-failure')
    add_source(engine, actor, 'inactive', active=False)
    eligible = [add_source(engine, actor, 'eligible-' + str(i)) for i in range(6)]
    execute(engine, 'UPDATE quality_watch_sources SET last_successful_month=:month WHERE id=:i',
        {'month': '2026-10', 'i': completed})
    previous = NOW - timedelta(hours=12)
    src, run, _, _ = watch._claim_run(engine, actor, recent, 'MONTHLY', previous)
    watch._finish_run(engine, actor, src, run, {}, [], 0, 0, previous.isoformat(), 'Fictitious earlier failure')
    visited = []
    monkeypatch.setattr(watch, 'collect_source', lambda engine_arg, actor_arg, source_id, **kwargs: visited.append(source_id))
    # Europe/Paris changes to UTC+1 by 1 November; 07:00 UTC is before 09:00 local.
    jobs._collect_watch_cycle(engine, datetime(2026, 11, 1, 7, tzinfo=timezone.utc))
    assert visited == []
    jobs._collect_watch_cycle(engine, NOW)
    assert visited == eligible[:5]


@pytest.mark.parametrize('kind', ['watch', 'notifications'])
def test_simultaneous_worker_passes_start_only_one_daemon(env, monkeypatch, kind):
    engine, actors = env
    entered, release = threading.Event(), threading.Event()
    starts = []
    ready = threading.Barrier(2)

    def blocked_cycle(*args, **kwargs):
        starts.append(kind)
        entered.set()
        assert release.wait(3)

    if kind == 'watch':
        activate_schedule(engine, actors[0])
        monkeypatch.setattr(jobs, '_collect_watch_cycle', blocked_cycle)
        start = lambda: jobs.start_due_watch_jobs(engine, now=NOW)
        thread_name = '_watch_thread'
    else:
        monkeypatch.setattr(jobs, 'process_quality_notifications', blocked_cycle)
        start = lambda: jobs.start_quality_notification_jobs(engine, {'enabled': True}, PORTAL, now=NOW)
        thread_name = '_notification_thread'

    def simultaneous_start():
        ready.wait(timeout=3)
        return start()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(simultaneous_start) for _ in range(2)]
            results = [future.result(timeout=3) for future in futures]
        assert entered.wait(2)
        assert sorted(results) == [False, True] and starts == [kind]
        thread = getattr(jobs, thread_name)
        assert thread.is_alive() and thread.daemon
    finally:
        release.set()
        thread = getattr(jobs, thread_name)
        if thread is not None:
            thread.join(3)
    assert not thread.is_alive()


def test_blocked_provider_does_not_block_worker_or_start_second_delivery(env):
    engine, actors = env
    add_notification(engine, actors[0])
    quality.configure_organization(engine, actors[0], email_enabled=True)
    entered, release, continued = threading.Event(), threading.Event(), threading.Event()
    calls, outcomes, failures = [], [], []

    def provider(config, recipient, subject, body):
        calls.append((recipient, subject, body))
        entered.set()
        assert release.wait(4)

    def existing_worker():
        try:
            outcomes.append(jobs.run_quality_jobs(engine, {'enabled': True}, PORTAL, send_mail=provider, now=NOW))
        except BaseException as error:
            failures.append(error)
        finally:
            continued.set()

    worker = threading.Thread(target=existing_worker)
    worker.start()
    try:
        assert entered.wait(2), 'The fictitious provider was not reached'
        assert continued.wait(1), 'The existing worker is blocked by the new provider'
        assert failures == [] and outcomes[0]['notifications'] == {'background': True, 'started': True}
        assert one(engine, 'SELECT status FROM quality_notification_outbox')['status'] == 'SENDING'
        second = jobs.run_quality_jobs(engine, {'enabled': True}, PORTAL, send_mail=provider, now=NOW)
        assert second['notifications'] == {'background': True, 'started': False} and len(calls) == 1
        assert 'Contexte fictif privé' not in calls[0][2] and PORTAL in calls[0][2]
    finally:
        release.set()
        worker.join(3)
        if jobs._notification_thread is not None:
            jobs._notification_thread.join(3)
    assert not worker.is_alive() and not jobs._notification_thread.is_alive()
    assert one(engine, 'SELECT status FROM quality_notification_outbox')['status'] == 'ACCEPTED'


def test_background_notification_failure_and_unavailable_audit_end_cleanly(env, monkeypatch, caplog):
    engine, _ = env

    def failing_process(*args, **kwargs):
        raise RuntimeError('PRIVATE provider context')

    monkeypatch.setattr(jobs, 'process_quality_notifications', failing_process)
    monkeypatch.setattr(jobs, 'audit', lambda *args, **kwargs: (_ for _ in ()).throw(OSError('PRIVATE audit context')))
    result = jobs.run_quality_jobs(engine, {'enabled': True}, PORTAL, now=NOW)
    jobs._notification_thread.join(3)
    assert result['notifications'] == {'background': True, 'started': True}
    assert not jobs._notification_thread.is_alive()
    assert 'QUALITY_NOTIFICATION_JOB_FAILED' in caplog.text and 'PRIVATE' not in caplog.text


@pytest.mark.parametrize('error,expected', [
    (smtplib.SMTPDataError(550, b'Fictitious DATA refusal'), 'RETRY'),
    (TimeoutError('Fictitious lost acknowledgement'), 'UNKNOWN'),
])
def test_legacy_smtp_adapter_distinguishes_definite_refusal_and_ambiguity(env, error, expected):
    engine, actors = env
    add_notification(engine, actors[0])
    quality.configure_organization(engine, actors[0], email_enabled=True)
    calls = []

    def refused(config, recipient, subject, body):
        calls.append(recipient)
        raise error

    jobs.process_quality_notifications(engine, {'enabled': True}, PORTAL, send_mail=refused, now=NOW)
    assert one(engine, 'SELECT status FROM quality_notification_outbox')['status'] == expected
    assert len(calls) == 1
    if expected == 'UNKNOWN':
        jobs.process_quality_notifications(engine, {'enabled': True}, PORTAL, send_mail=refused, now=NOW)
        assert len(calls) == 1
