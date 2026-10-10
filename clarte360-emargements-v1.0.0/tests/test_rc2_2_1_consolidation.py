from pathlib import Path

import pytest

import pip_connector
import services
from db import make_engine, init_db, execute
from services import (
    add_participant,
    create_action,
    create_beneficiary,
    create_tool_prescription,
    link_participant_to_beneficiary,
    seed_tool_catalog,
    update_tool_prescription_status,
)


def _eng():
    e = make_engine('sqlite:///:memory:')
    init_db(e)
    seed_tool_catalog(e)
    return e


def _seed_action(e, no='RC221-001'):
    aid = create_action(e, {
        'action_no': no,
        'title': 'Recette consolidation outils',
        'subtitle': None,
        'nature': 'BILAN_COMPETENCES',
        'mode': 'INDIVIDUEL',
        'client_name': 'Client',
        'client_type': 'Particulier',
        'group_code': None,
        'planned_hours': 3,
        'expected_participants': 1,
        'admin_email': 'admin@example.org',
        'trainer_name': None,
        'trainer_email': None,
        'location': 'Online',
        'notes': None,
        'source': 'TEST',
    }, 'test')
    pid, _ = add_participant(e, aid, {
        'last_name': 'DUPONT',
        'first_name': 'Anne',
        'birth_date': '1990-01-01',
        'email': 'anne@example.org',
    }, 'test')
    bid = create_beneficiary(e, 'DUPONT', 'Anne', '1990-01-01', 'anne@example.org', actor='test')
    link_participant_to_beneficiary(e, pid, bid, 'test')
    return aid, pid, bid


def test_pip_launch_ignores_business_expiry_but_blocks_termine(monkeypatch):
    row = {
        'tool_code': 'PIP_RIASEC_ONET',
        'status': 'EN_COURS',
        'expires_at': '2000-01-01T00:00:00+00:00',
        'base_url': 'https://pip-riasec.clarte360.com',
        'beneficiary_id': 12,
        'action_id': 34,
        'participant_id': 56,
        'prescription_id': 'PR-PIP-1',
        'beneficiary_first_name': 'Anne',
        'beneficiary_last_name': 'Dupont',
        'action_number': 'A-1',
        'action_title': 'Action',
    }
    monkeypatch.setattr(services, 'one', lambda *a, **k: row)
    monkeypatch.setattr(pip_connector, 'build_pip_launch_token', lambda **kw: 'TOKEN')
    monkeypatch.setattr(pip_connector, 'build_pip_launch_url', lambda base, token: f'{base}?launch={token}')
    assert services.build_pip_prescription_launch(None, 'PR-PIP-1', 'K' * 48).endswith('?launch=TOKEN')
    row['status'] = 'TERMINE'
    with pytest.raises(ValueError, match='terminée'):
        services.build_pip_prescription_launch(None, 'PR-PIP-1', 'K' * 48)


def test_ipip_launch_blocks_termine_and_contract_is_exposed(monkeypatch):
    row = {
        'tool_code': 'IPIP_NEO120',
        'status': 'EN_COURS',
        'base_url': 'https://ipip-neo120.clarte360.com',
        'beneficiary_id': 12,
        'action_id': 34,
        'participant_id': 56,
        'prescription_id': 'PR-IPIP-1',
    }
    monkeypatch.setattr(services, 'one', lambda *a, **k: row)
    url = services.build_ipip_prescription_launch(None, 'PR-IPIP-1', 'K' * 48)
    assert 'mode=accompagnement' in url and 'launch=' in url
    row['status'] = 'TERMINE'
    with pytest.raises(ValueError, match='terminée'):
        services.build_ipip_prescription_launch(None, 'PR-IPIP-1', 'K' * 48)


def test_new_pip_and_ipip_prescription_allowed_only_after_previous_termine():
    e = _eng()
    aid, pid, bid = _seed_action(e)
    first_pip = create_tool_prescription(e, 'PIP_RIASEC_ONET', bid, aid, pid, actor='admin')
    with pytest.raises(ValueError, match='déjà prescrit'):
        create_tool_prescription(e, 'PIP_RIASEC_ONET', bid, aid, pid, actor='admin')
    update_tool_prescription_status(e, first_pip['prescription_id'], 'TERMINE', 'connector')
    second_pip = create_tool_prescription(e, 'PIP_RIASEC_ONET', bid, aid, pid, actor='admin')
    assert second_pip['prescription_id'] != first_pip['prescription_id']

    first_ipip = create_tool_prescription(e, 'IPIP_NEO120', bid, aid, pid, actor='admin')
    with pytest.raises(ValueError, match='déjà prescrit'):
        create_tool_prescription(e, 'IPIP_NEO120', bid, aid, pid, actor='admin')
    update_tool_prescription_status(e, first_ipip['prescription_id'], 'TERMINE', 'connector')
    second_ipip = create_tool_prescription(e, 'IPIP_NEO120', bid, aid, pid, actor='admin')
    assert second_ipip['prescription_id'] != first_ipip['prescription_id']


def test_package_contains_both_ipip_app_and_service_sides_and_worker_consumption():
    app = Path('app.py').read_text(encoding='utf-8')
    worker = Path('worker.py').read_text(encoding='utf-8')
    assert "pr.get('tool_code')=='IPIP_NEO120'" in app
    assert "ctx.get('tool_code')=='IPIP_NEO120'" in app
    assert hasattr(services, 'build_ipip_prescription_launch')
    assert hasattr(services, 'consume_ipip_outbox')
    assert 'consume_ipip_outbox' in worker
    assert 'refresh_ipip_connector_runtime_status' in worker
    assert 'teams_changed + pip_changed + ipip_changed' in worker


def test_beneficiary_portal_keeps_multiple_tools_and_does_not_reopen_finished_signed_passation():
    app = Path('app.py').read_text(encoding='utf-8')
    start = app.index('def beneficiary_portal_page')
    end = app.index('def footer')
    block = app[start:end]
    from navigation_p3 import BENEFICIARY_SCREENS
    assert any(section.key == 'tools' and 'Mes outils' in section.label for section in BENEFICIARY_SCREENS)
    assert "if selected_section=='tools':" in block
    assert "pr.get('tool_code')=='PIP_RIASEC_ONET'" in block
    assert "pr.get('tool_code')=='IPIP_NEO120'" in block
    assert "('PIP_RIASEC_ONET','IPIP_NEO120')" in block
    assert 'une nouvelle passation nécessite une nouvelle prescription' in block
    assert 'OUVRIR CET OUTIL' in block


def test_registry_specialized_launch_types_are_explicit_and_other_tools_remain_guarded():
    e = _eng()
    pip = services.one(e, "SELECT * FROM tool_catalog WHERE tool_code='PIP_RIASEC_ONET'")
    ipip = services.one(e, "SELECT * FROM tool_catalog WHERE tool_code='IPIP_NEO120'")
    assert pip['launch_type'] == 'EXTERNAL_SIGNED'
    assert ipip['launch_type'] == 'EXTERNAL_SIGNED'
    arbitrary = services.upsert_tool_catalog(e, {
        'tool_code': 'DEMO_SIGNED', 'name': 'Demo', 'base_url': 'https://example.org', 'launch_type': 'EXTERNAL_SIGNED'
    })
    assert arbitrary['launch_type'] == 'HUB_REDIRECT'


def test_ipip_secret_contract_is_documented_without_real_secret():
    import tomllib
    data = tomllib.loads(Path('.streamlit/secrets.example.toml').read_text(encoding='utf-8'))
    sec = data['IPIP_CONNECTOR']
    assert set(sec) >= {'LAUNCH_SIGNING_KEY','OUTBOX_PENDING_DIR','DATA_ROOT'}
    assert 'REMPLACER' in sec['LAUNCH_SIGNING_KEY']
    assert sec['DATA_ROOT'] == '/var/lib/clarte360/ipip-neo120'
