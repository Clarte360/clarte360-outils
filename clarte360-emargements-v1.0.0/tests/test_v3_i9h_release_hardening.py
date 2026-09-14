from __future__ import annotations

from pathlib import Path

from db import make_engine, init_db
from production_readiness import runtime_readiness
from ui_guard import user_message


ROOT = Path(__file__).resolve().parents[1]


def _engine(tmp_path):
    eng = make_engine(f"sqlite:///{tmp_path / 'i9h.db'}")
    init_db(eng)
    return eng


def test_runtime_readiness_never_exposes_secret_values(tmp_path):
    eng = _engine(tmp_path)
    secrets = {
        "microsoft_graph": {
            "tenant_id": "TENANT-ULTRA-SECRET",
            "client_id": "CLIENT-ULTRA-SECRET",
            "certificate_path": "/private/cert.pem",
        },
        "pip_connector": {
            "launch_signing_key": "PIP-SIGNING-ULTRA-SECRET",
            "outbox_path": "/private/outbox.jsonl",
        },
    }
    diag = runtime_readiness(
        eng,
        base_url="https://gestion.clarte360.com",
        mail_config={"enabled": True, "password": "SMTP-ULTRA-SECRET"},
        secrets=secrets,
        project_root=ROOT,
    )
    rendered = repr(diag)
    assert diag["ready"] is True
    assert "ULTRA-SECRET" not in rendered
    assert "TENANT-" not in rendered
    assert "/private/" not in rendered


def test_runtime_readiness_optional_connectors_do_not_block_hub(tmp_path):
    eng = _engine(tmp_path)
    diag = runtime_readiness(
        eng,
        base_url="https://gestion.clarte360.com",
        mail_config={"enabled": False},
        secrets={},
        project_root=ROOT,
    )
    assert diag["ready"] is True
    states = {c["name"]: c["status"] for c in diag["checks"]}
    assert states["Microsoft 365 / Teams"] == "A_VERIFIER"
    assert states["Connecteur PIP"] == "A_VERIFIER"


def test_runtime_readiness_blocks_missing_public_url(tmp_path):
    eng = _engine(tmp_path)
    diag = runtime_readiness(eng, base_url="", project_root=ROOT)
    assert diag["ready"] is False
    assert any(c["name"] == "URL publique" and c["blocking"] for c in diag["checks"])


def test_ui_error_message_is_business_facing():
    msg = user_message("ABC123", subject="Le calendrier")
    assert "ABC123" in msg
    assert "Traceback" not in msg
    assert "Exception" not in msg
    assert "Le calendrier" in msg


def test_no_streamlit_exception_widget_in_user_app():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "st.exception(" not in source


def test_no_obvious_hardcoded_secret_assignments_in_runtime_files():
    runtime_files = [
        "app.py", "services.py", "worker.py", "graph_client.py", "pip_connector.py",
        "mailer.py", "security.py", "persistent_session.py", "production_readiness.py",
    ]
    forbidden = [
        "launch_signing_key='", 'launch_signing_key="',
        "client_secret='", 'client_secret="',
        "smtp_password='", 'smtp_password="',
    ]
    for name in runtime_files:
        text = (ROOT / name).read_text(encoding="utf-8").lower()
        for needle in forbidden:
            assert needle not in text, f"secret literal pattern in {name}: {needle}"


def test_release_check_exists_and_is_read_only_oriented():
    text = (ROOT / "release_check.py").read_text(encoding="utf-8")
    assert "pytest" in text
    assert "compileall" in text
    assert "systemctl" not in text
    assert "git push" not in text.lower()
