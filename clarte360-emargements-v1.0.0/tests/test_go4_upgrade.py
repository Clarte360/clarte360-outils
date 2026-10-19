"""R08/R11/R25: upgrade an actual RC2 schema with fictitious retained records.

The SQL fixture was generated from an isolated copy of official RC2 db.py and its
two schema dependencies. It is not a fresh GO4 database populated after init_db.
Full generation provenance accompanies the acceptance evidence.
"""
from collections import Counter
import hashlib
from pathlib import Path
import sqlite3

from db import init_db, make_engine, one, q
import quality_service as quality


FIXTURE = Path(__file__).parent / 'fixtures' / 'rc2_upgrade.sql'
FIXTURE_SHA256 = '4c1f2e71a41475a6997a228e5de2c0aabecb5ffd1dc5e4db11ce38b32a22f087'
SHARED_BYTES = b'Document partage purement fictif RC2 -> GO4.\n'


def _identifier(value):
    return '"' + value.replace('"', '""') + '"'


def _snapshot(path):
    with sqlite3.connect(path) as conn:
        names = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        result = {}
        for name in names:
            columns = tuple(row[1] for row in conn.execute('PRAGMA table_info(' + _identifier(name) + ')'))
            rows = conn.execute('SELECT ' + ','.join(map(_identifier, columns)) + ' FROM ' + _identifier(name)).fetchall()
            result[name] = {'columns': columns, 'rows': Counter(rows)}
        return result


def _assert_original_rows_preserved(path, original, *, append_tables=()):
    current = _snapshot(path)
    assert original.keys() <= current.keys(), 'An original RC2 table disappeared'
    with sqlite3.connect(path) as conn:
        for name, data in original.items():
            assert set(data['columns']) <= set(current[name]['columns']), 'RC2 columns removed from ' + name
            rows = Counter(conn.execute('SELECT ' + ','.join(map(_identifier, data['columns'])) +
                                        ' FROM ' + _identifier(name)).fetchall())
            if name in append_tables:
                assert not (data['rows'] - rows), 'Historical RC2 values altered in ' + name
            else:
                assert rows == data['rows'], 'RC2 rows changed before explicit action in ' + name
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []


def test_rc2_upgrade_preserves_existing_data_and_explicit_adoption_is_repeatable(tmp_path, monkeypatch):
    fixture_bytes = FIXTURE.read_bytes()
    assert hashlib.sha256(fixture_bytes).hexdigest() == FIXTURE_SHA256
    db_path = tmp_path / 'actual_rc2_schema.sqlite'
    with sqlite3.connect(db_path) as conn:
        conn.executescript(fixture_bytes.decode('utf-8'))
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    monkeypatch.chdir(tmp_path)
    shared_file = tmp_path / 'shared' / 'fixture_shared.txt'
    shared_file.parent.mkdir()
    shared_file.write_bytes(SHARED_BYTES)
    original = _snapshot(db_path)
    assert 'go4_managed' not in original['quality_events']['columns']
    assert 'quality_campaign_contracts' not in original
    assert 'quality_commands' not in original

    engine = make_engine('sqlite:///' + str(db_path))
    try:
        init_db(engine)
        _assert_original_rows_preserved(db_path, original)
        after_first_init = _snapshot(db_path)
        init_db(engine)
        _assert_original_rows_preserved(db_path, original)
        assert _snapshot(db_path) == after_first_init, 'A second init_db is not idempotent'
        for table in ('quality_migration_decisions', 'quality_campaign_contracts', 'quality_notification_outbox',
                      'quality_commands', 'quality_deletion_receipts'):
            assert one(engine, 'SELECT COUNT(*) n FROM ' + table)['n'] == 0
        assert one(engine, 'SELECT id,source FROM actions WHERE action_no=\'ESSAI2\'') == {'id': 410, 'source': 'TEST'}
        event = one(engine, 'SELECT * FROM quality_events WHERE id=201')
        assert event['go4_managed'] == 0 and event['data_classification'] == 'A_EXAMINER'
        assert shared_file.read_bytes() == SHARED_BYTES

        actor = quality.QualityActor('ADMIN', 'migration.admin@example.invalid', 301)
        explicit_general = [('IMPROVEMENT_ACTION', 402)]
        first = quality.migrate_legacy(engine, actor, general_source_ids=explicit_general)
        assert first['events_adopted'] == 1
        assert first['sources_created'] == 3 and first['steps_created'] == 1
        assert first['already_mapped'] == 1 and first['unresolved'] == []
        canonical_tables = ('quality_events', 'quality_event_actions', 'quality_event_messages',
                            'quality_event_history', 'quality_source_links', 'quality_capa_source_links')
        _assert_original_rows_preserved(db_path, original, append_tables=canonical_tables)
        after_adoption = _snapshot(db_path)
        second = quality.migrate_legacy(engine, actor, general_source_ids=explicit_general)
        assert second['events_adopted'] == second['sources_created'] == second['steps_created'] == 0
        assert second['already_mapped'] == 5 and second['unresolved'] == []
        _assert_original_rows_preserved(db_path, original, append_tables=canonical_tables)
        repeated = _snapshot(db_path)
        assert all(repeated[table] == after_adoption[table] for table in canonical_tables)
        assert one(engine, 'SELECT COUNT(*) n FROM quality_events')['n'] == 4
        assert one(engine, 'SELECT COUNT(*) n FROM quality_event_actions')['n'] == 2
        assert one(engine, 'SELECT COUNT(*) n FROM quality_migration_decisions')['n'] == 5
        assert one(engine, 'SELECT COUNT(*) n FROM quality_notification_outbox')['n'] == 0
        assert one(engine, 'SELECT COUNT(*) n FROM quality_campaign_contracts')['n'] == 0
        assert all(row['data_classification'] == 'A_EXAMINER' for row in q(engine, 'SELECT data_classification FROM quality_events'))

        beneficiary = quality.QualityActor('BENEFICIARY', 501, 301)
        case = quality.get_action(engine, beneficiary, 201)
        assert case['event']['public_id'] == 'Q-RC2-201'
        assert [(row['id'], row['author'], row['message'], row['created_at']) for row in case['messages']] == [
            (301, 'admin.historique@example.invalid', 'Reponse historique avec auteur connu.', '2026-09-12T16:45:00+00:00')]
        assert one(engine, 'SELECT created_by,created_at FROM quality_events WHERE id=201') == {
            'created_by': 'BENEFICIARY:501', 'created_at': '2026-09-10T08:15:00+00:00'}
        trainer_event = one(engine, "SELECT qe.* FROM quality_events qe JOIN quality_source_links l ON l.quality_event_id=qe.id WHERE l.source_kind='TRAINER_REPORT' AND l.source_id=102")
        assert trainer_event['created_by'] == 'TRAINER:801'
        assert trainer_event['created_at'] == '2026-09-10T08:15:00+00:00'
        trainer_reply = one(engine, 'SELECT author,message,created_at FROM quality_event_messages WHERE quality_event_id=:e', {'e': trainer_event['id']})
        assert trainer_reply == {'author': 'LEGACY:ADMIN_AUTHOR_NOT_RECORDED',
                                'message': 'Reponse ancienne dont auteur non enregistre.',
                                'created_at': '2026-09-12T16:45:00+00:00'}
        assert one(engine, 'SELECT question_text_snapshot,answer_json,answered_at FROM quality_responses WHERE id=1301') == {
            'question_text_snapshot': 'Votre satisfaction origine RC2 ?', 'answer_json': '{"value":4}',
            'answered_at': '2026-09-12T16:45:00+00:00'}
        assert one(engine, 'SELECT question_text FROM questionnaire_questions WHERE id=1201')['question_text'] == 'Libelle actuel non retroactif'
        assert q(engine, 'SELECT id,stored_file_id,action_id,deleted_at FROM document_references ORDER BY id') == [
            {'id': 901, 'stored_file_id': 801, 'action_id': 410, 'deleted_at': None},
            {'id': 902, 'stored_file_id': 801, 'action_id': 411, 'deleted_at': None}]
        assert one(engine, 'SELECT sha256 FROM stored_files WHERE id=801')['sha256'] == hashlib.sha256(shared_file.read_bytes()).hexdigest()
        assert shared_file.read_bytes() == SHARED_BYTES
        assert one(engine, "SELECT id FROM actions WHERE action_no='ESSAI2'")['id'] == 410
    finally:
        engine.dispose()
