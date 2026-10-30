from __future__ import annotations

import importlib.util
import hashlib
import sys
import types
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from clarte360_cp.connectors.gestion_actions import (
    LaunchTokenError, verify_admin_upload_token, verify_launch_token,
)


class FakeGDA:
    prescription = {
        "prescription_id": "P-1", "beneficiary_id": 102, "action_id": 45,
        "participant_id": 207, "status": "A_FAIRE", "base_url": "https://cp.example/", "action_no": "ACT-025",
        "tool_active": 1, "prescription_allowed": 1,
    }


def _module(monkeypatch):
    db = types.ModuleType("db")
    services = types.ModuleType("services")
    def one(_engine, query, params):
        if "FROM tool_prescriptions" in query:
            return dict(FakeGDA.prescription)
        if "FROM trainers" in query:
            return {"id": int(params["i"]), "active": 1}
        if "FROM admins" in query:
            return {"id": int(params["i"]), "active": 1}
        if "FROM participants" in query:
            return {"id": int(params["p"])} if str(params["p"]) == "207" else None
        return None
    db.one = one
    services.trainer_action_authorized = lambda *_: True
    monkeypatch.setitem(sys.modules, "db", db)
    monkeypatch.setitem(sys.modules, "services", services)
    path = Path(__file__).parents[1] / "integration/gda_patch/cp_launch.py"
    spec = importlib.util.spec_from_file_location("cp_launch_patch_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_patch_emits_canonical_cp_v1_for_current_accompanist(monkeypatch):
    builder = _module(monkeypatch)
    url = builder.build_cp_launch(object(), "P-1", "ACCOMPAGNATEUR", 9, "k" * 40)
    token = parse_qs(urlsplit(url).query)["launch"][0]
    ctx = verify_launch_token(token, "k" * 40)
    assert ctx.actor_role.value == "ACCOMPAGNATEUR"
    assert ctx.actor_id == "9"
    assert ctx.beneficiary_id == "102" and ctx.action_id == "45" and ctx.action_no == "ACT-025"
    assert "CP_SOURCE_GDA_READ" in ctx.scopes
    assert "beneficiary" not in token


def test_patch_emits_beneficiary_scope_and_rejects_cross_account(monkeypatch):
    builder = _module(monkeypatch)
    url = builder.build_cp_launch(object(), "P-1", "BENEFICIAIRE", "102", "k" * 40)
    token = parse_qs(urlsplit(url).query)["launch"][0]
    ctx = verify_launch_token(token, "k" * 40)
    assert ctx.actor_role.value == "BENEFICIAIRE"
    assert ctx.actor_id == "102"
    assert "CP_SOURCE_GDA_READ" not in ctx.scopes
    with pytest.raises(PermissionError):
        builder.build_cp_launch(object(), "P-1", "BENEFICIAIRE", "999", "k" * 40)


def test_admin_link_is_upload_only_and_cannot_open_case(monkeypatch):
    builder = _module(monkeypatch)
    url = builder.build_cp_admin_upload_launch(object(), "P-1", 4, "k" * 40)
    token = parse_qs(urlsplit(url).query)["launch"][0]
    assert parse_qs(urlsplit(url).query)["mode"] == ["upload_only"]
    context = verify_admin_upload_token(token, "k" * 40)
    assert context.actor_id == "4"
    assert context.scopes == ("CP_SOURCE_ADMIN_PUT",)
    with pytest.raises(LaunchTokenError):
        verify_launch_token(token, "k" * 40)


def test_closed_or_expired_prescription_cannot_be_launched(monkeypatch):
    try:
        builder = _module(monkeypatch)
        FakeGDA.prescription["status"] = "TERMINE"
        with pytest.raises(ValueError, match="indisponible"):
            builder.build_cp_launch(object(), "P-1", "ACCOMPAGNATEUR", 9, "k" * 40)
        FakeGDA.prescription["status"] = "A_FAIRE"
        FakeGDA.prescription["prescription_allowed"] = 0
        # Disabling new prescriptions does not invalidate an existing assigned case.
        assert builder.build_cp_launch(object(), "P-1", "ACCOMPAGNATEUR", 9, "k" * 40).startswith("https://cp.example/")
        FakeGDA.prescription["expires_at"] = "2000-01-01T00:00:00+00:00"
        with pytest.raises(ValueError, match="indisponible"):
            builder.build_cp_launch(object(), "P-1", "ACCOMPAGNATEUR", 9, "k" * 40)
    finally:
        FakeGDA.prescription.pop("expires_at", None)
        FakeGDA.prescription["status"] = "A_FAIRE"
        FakeGDA.prescription["prescription_allowed"] = 1


def test_gda_launch_patch_exposes_existing_cp_case_to_any_assigned_trainer():
    patch = (Path(__file__).parents[1] / "integration/gda_patch/app.py.patch").read_text(encoding="utf-8")
    launch_block = patch.split("# Launch an existing C&P prescription", 1)[1].split("if not trainer_can_prescribe_tools", 1)[0]
    assert "list_tool_prescriptions(ENGINE,action_id=aid)" in launch_block
    assert "build_cp_launch(ENGINE" in launch_block
    assert "trainer_can_prescribe_tools" not in launch_block
    api = (Path(__file__).parents[1] / "integration/gda_patch/cp_hub_api.py").read_text(encoding="utf-8")
    assert '"/api/cp/v1/session/check"' in api
    assert '_authorize(self.engine, ctx, "CP_CASE_READ")' in api
    assert "str(pr.get(\"status\") or \"\").upper() not in" in api
    assert 'ext != ".pdf" or not content.startswith(b"%PDF-")' in api
    assert "cp_api_source_provenance" in api
    assert 'descriptor["created_by_role"]' in api
    assert 'descriptor["created_by_ref"]' in api
    assert '"role": str(ctx["actor_role"])' in api


def test_gda_source_audience_is_filtered_for_the_signed_role(monkeypatch, tmp_path):
    content = b"%PDF-1.4\nsynthetic GDA source\n"
    document = tmp_path / "synthetic-source.pdf"
    document.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    rows = [
        {"id": 100, "audience": "CLIENT_ONLY", "visible_to_beneficiary": 1, "document_kind": "", "category": "CV", "sha256": digest, "size_bytes": len(content), "mime_type": "application/pdf", "version_no": 1, "display_name": "synthetic-source.pdf", "created_at": "2026-10-24T00:00:00Z", "publication_status": "PUBLIE"},
        {"id": 101, "audience": "TRAINER_ONLY", "visible_to_beneficiary": 1, "document_kind": "", "category": "NOTE", "sha256": digest, "size_bytes": len(content), "mime_type": "application/pdf", "version_no": 1, "display_name": "synthetic-source.pdf", "created_at": "2026-10-24T00:00:00Z", "publication_status": "PUBLIE"},
        {"id": 102, "audience": "SHARED", "visible_to_beneficiary": 1, "document_kind": "", "category": "JUSTIFICATIF", "sha256": digest, "size_bytes": len(content), "mime_type": "application/pdf", "version_no": 1, "display_name": "synthetic-source.pdf", "created_at": "2026-10-24T00:00:00Z", "publication_status": "PUBLIE"},
        {"id": 103, "audience": "SHARED", "visible_to_beneficiary": 0, "document_kind": "", "category": "NOTE", "sha256": digest, "size_bytes": len(content), "mime_type": "application/pdf", "version_no": 1, "display_name": "synthetic-source.pdf", "created_at": "2026-10-24T00:00:00Z", "publication_status": "PUBLIE"},
        {"id": 104, "audience": "ADMIN_ONLY", "visible_to_beneficiary": 1, "document_kind": "", "category": "ADMIN", "sha256": digest, "size_bytes": len(content), "mime_type": "application/pdf", "version_no": 1, "display_name": "synthetic-source.pdf", "created_at": "2026-10-24T00:00:00Z", "publication_status": "PUBLIE"},
        {"id": 105, "audience": "SHARED", "visible_to_beneficiary": 1, "document_kind": "ONET_REPORT", "category": "ONET_REPORT", "sha256": digest, "size_bytes": len(content), "mime_type": "application/pdf", "version_no": 1, "display_name": "synthetic-source.pdf", "created_at": "2026-10-24T00:00:00Z", "publication_status": "PUBLIE"},
    ]
    query_calls = []
    db = types.ModuleType("db")
    db.make_engine = lambda _url: object()
    def one(_engine, sql, _params=None):
        if "SELECT sf.storage_path" in sql:
            return {"storage_path": str(document)}
        return None
    db.one = one
    def q(_engine, sql, params=None):
        query_calls.append((sql, params or {}))
        return rows
    db.q = q
    db.execute = lambda *_a, **_k: None
    db.utcnow_iso = lambda: "2026-10-24T00:00:00Z"
    services = types.ModuleType("services")
    services.DOC_PRIVATE = "PRIVATE"
    services.DEFAULT_ALLOWED_EXTENSIONS = {".pdf"}
    services.store_document = lambda *_a, **_k: (1, "hash", False)
    services.audit = lambda *_a, **_k: None
    monkeypatch.setitem(sys.modules, "db", db)
    monkeypatch.setitem(sys.modules, "services", services)
    secrets = tmp_path / "secrets.toml"
    secrets.write_text('[COMPETENCES_PROJETS_CONNECTOR]\nLAUNCH_SIGNING_KEY = "test-only-signing-key-1234567890"\n[database]\nurl = "sqlite://"\n', encoding="utf-8")
    monkeypatch.setenv("CLARTE360_SECRET_FILE", str(secrets))
    path = Path(__file__).parents[1] / "integration/gda_patch/cp_hub_api.py"
    spec = importlib.util.spec_from_file_location("cp_hub_api_audience_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    def visible(audience, visible_to_beneficiary=True, role="ACCOMPAGNATEUR"):
        return module._source_visible_to_actor(
            {"audience": audience, "visible_to_beneficiary": visible_to_beneficiary},
            {"actor_role": role},
        )

    assert visible("CLIENT_ONLY", True, "BENEFICIAIRE")
    assert not visible("TRAINER_ONLY", True, "BENEFICIAIRE")
    assert not visible("SHARED", False, "BENEFICIAIRE")
    assert visible("TRAINER_ONLY", False, "ACCOMPAGNATEUR")
    assert visible("CLIENT_ONLY", True, "ACCOMPAGNATEUR")
    assert not visible("ADMIN_ONLY", True, "ACCOMPAGNATEUR")
    assert not visible("SHARED", True, "ADMINISTRATEUR")

    engine = object()
    beneficiary = {"actor_role": "BENEFICIAIRE", "beneficiary_id": "B-1", "action_id": "A-1", "participant_id": "P-1"}
    trainer = {"actor_role": "ACCOMPAGNATEUR", "beneficiary_id": "B-1", "action_id": "A-1", "participant_id": "P-1"}
    beneficiary_sources = module._source_rows(engine, beneficiary)
    trainer_sources = module._source_rows(engine, trainer)
    assert {row["source_ref"] for row in beneficiary_sources} == {"100", "102"}
    assert {row["source_ref"] for row in trainer_sources} == {"100", "101", "102", "103"}
    assert all("storage_path" not in row for row in beneficiary_sources + trainer_sources)
    assert all("action_id=:a" in sql and "beneficiary_id=:b" in sql for sql, _ in query_calls)
    assert all(params["a"] == "A-1" and params["b"] == "B-1" for _, params in query_calls)

    opened, opened_bytes = module._read_source(engine, trainer, "101")
    assert opened["source_ref"] == "101" and opened_bytes == content
    with pytest.raises(PermissionError, match="NOT_FOUND"):
        module._read_source(engine, beneficiary, "101")
    with pytest.raises(PermissionError, match="NOT_FOUND"):
        module._read_source(engine, trainer, "104")
