from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest

from clarte360_cp.connectors.gda_documents import (
    GDAError, GDADocumentClient, GDASettings, load_gda_settings, renew_session_launch_token,
)
from clarte360_cp.connectors.gestion_actions import verify_launch_token


class Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit=-1):
        return self.payload


def source(data=b"pdf bytes", *, kind="DOCUMENT_NON_ASSOCIE"):
    return {
        "source_ref": "doc-123", "source_kind": kind, "source_version": "1",
        "mime_type": "application/pdf", "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def test_settings_require_https_and_bound_parameters():
    assert not load_gda_settings({"GESTION_ACTIONS_CONNECTOR": {"API_BASE_URL": "http://gda"}}).configured
    settings = load_gda_settings({"GESTION_ACTIONS_CONNECTOR": {
        "API_BASE_URL": "https://gda.example/", "TIMEOUT_SECONDS": 500, "MAX_FILE_MB": 100,
    }})
    assert settings.base_url == "https://gda.example"
    assert settings.timeout_seconds == 60
    assert settings.max_file_bytes == 50 * 1024 * 1024
    signed = load_gda_settings({"GESTION_ACTIONS_CONNECTOR": {"API_BASE_URL": "https://gda.test"}, "COMPETENCES_PROJETS_CONNECTOR": {"LAUNCH_SIGNING_KEY": "k" * 40}})
    assert signed.configured


def test_active_server_session_can_refresh_gda_token_but_preserves_scope():
    from tests.helpers import payload
    from clarte360_cp.connectors.gestion_actions import build_launch_token
    original_payload = payload()
    original_payload["iat"], original_payload["exp"] = 1000, 1600
    original = verify_launch_token(build_launch_token(original_payload, "k" * 40), "k" * 40, now_epoch=1000)
    renewed = renew_session_launch_token(original, "k" * 40, now=2000)
    checked = verify_launch_token(renewed, "k" * 40, now_epoch=2050)
    assert checked.actor_id == original.actor_id
    assert checked.prescription_id == original.prescription_id
    assert checked.scopes == original.scopes
    assert checked.exp > 900


def test_list_uses_bearer_token_and_returns_only_valid_descriptors():
    seen = {}

    def opener(req, timeout):
        seen.update(url=req.full_url, headers=dict(req.header_items()), timeout=timeout)
        return Response({"sources": [source()]})

    client = GDADocumentClient(GDASettings("https://gda.example", 9, request_signing_key="k" * 40), "signed-launch", opener=opener)
    rows = client.list_sources()
    assert rows[0]["source_ref"] == "doc-123"
    assert seen["url"] == "https://gda.example/api/cp/v1/sources/list"
    assert seen["headers"]["Authorization"] == "Bearer signed-launch"
    assert "signed-launch" not in seen["url"]
    body = json.dumps({"tool_id": "COMPETENCES_PROJETS"}, ensure_ascii=False, separators=(",", ":")).encode()
    stamp = seen["headers"]["X-cp-timestamp"]
    path = "/api/cp/v1/sources/list"
    signable = f"POST\n{path}\n{stamp}\n{hashlib.sha256(body).hexdigest()}".encode()
    assert hmac.compare_digest(seen["headers"]["X-cp-signature"], hmac.new(b"k" * 40, signable, hashlib.sha256).hexdigest())


def test_source_download_checks_size_and_hash_before_returning_bytes():
    data = b"document content"
    client = GDADocumentClient(GDASettings("https://gda.example", request_signing_key="k" * 40), "signed-launch", opener=lambda *_a, **_k: Response({
        "source": source(data), "content_b64": base64.b64encode(data).decode(),
    }))
    metadata, returned = client.get_source("doc-123")
    assert metadata["sha256"] == hashlib.sha256(data).hexdigest()
    assert returned == data

    broken = GDADocumentClient(GDASettings("https://gda.example", request_signing_key="k" * 40), "signed-launch", opener=lambda *_a, **_k: Response({
        "source": source(data), "content_b64": base64.b64encode(b"tampered").decode(),
    }))
    with pytest.raises(GDAError, match="intégrité"):
        broken.get_source("doc-123")


def test_forbidden_source_kind_is_rejected_even_if_returned_by_gda():
    client = GDADocumentClient(GDASettings("https://gda.example", request_signing_key="k" * 40), "signed-launch", opener=lambda *_a, **_k: Response({
        "sources": [source(kind="ONET_REPORT")],
    }))
    with pytest.raises(GDAError, match="pas admis"):
        client.list_sources()


def test_source_descriptor_accepts_known_depositor_roles_and_rejects_unknown_roles():
    client = GDADocumentClient(GDASettings("https://gda.example", request_signing_key="k" * 40), "signed-launch", opener=lambda *_a, **_k: Response({
        "sources": [{**source(), "created_by_role": "ADMINISTRATEUR", "created_by_ref": "ADMIN-9"}],
    }))
    assert client.list_sources()[0]["created_by_role"] == "ADMINISTRATEUR"

    invalid = GDADocumentClient(GDASettings("https://gda.example", request_signing_key="k" * 40), "signed-launch", opener=lambda *_a, **_k: Response({
        "sources": [{**source(), "created_by_role": "INCONNU", "created_by_ref": "ADMIN-9"}],
    }))
    with pytest.raises(GDAError, match="rôle du déposant"):
        invalid.list_sources()


def test_upload_is_explicitly_unassociated_and_hash_is_sent():
    data = b"user selected document"
    seen = {}

    def opener(req, timeout):
        seen["body"] = json.loads(req.data)
        return Response({"source": source(data)})

    client = GDADocumentClient(GDASettings("https://gda.example", request_signing_key="k" * 40), "signed-launch", opener=opener)
    result = client.put_unlinked("cv.pdf", data)
    assert result["source_ref"] == "doc-123"
    assert seen["body"]["association"] is None
    assert seen["body"]["sha256"] == hashlib.sha256(data).hexdigest()
    assert base64.b64decode(seen["body"]["content_b64"]) == data


def test_finalized_delivery_requires_idempotent_receipt():
    client = GDADocumentClient(GDASettings("https://gda.example", request_signing_key="k" * 40), "signed-launch", opener=lambda *_a, **_k: Response({
        "receipt": {"status": "REPLAYED", "event_id": "evt-1"},
    }))
    assert client.return_finalized({"event_id": "evt-1"})["status"] == "REPLAYED"

    rejected = GDADocumentClient(GDASettings("https://gda.example", request_signing_key="k" * 40), "signed-launch", opener=lambda *_a, **_k: Response({
        "receipt": {"status": "REJECTED"},
    }))
    with pytest.raises(GDAError, match="pas confirmé"):
        rejected.return_finalized({"event_id": "evt-1"})
