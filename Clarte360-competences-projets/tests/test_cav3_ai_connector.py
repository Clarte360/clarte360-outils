from __future__ import annotations

import json
import sys
import types

import pytest

from clarte360_cp.connectors.cav3_ai import Cav3AIError, Cav3AISettings, ai_ready, analyze_cav3, api_client


def settings():
    return Cav3AISettings("synthetic-key", "synthetic-model")


def context():
    return {
        "schema": "GO22_CAV3_INPUT_V1", "response_version": 1,
        "response_sha256": "a" * 64, "source_fingerprint": "b" * 64,
        "reponses": {"schema": "GO22_CAV1_CAV2_REPONSES_UNIQUES_V2", "cav1": {}, "cav2": {}},
        "sources": [{"kind": "APS", "id": "synthetic-source"}],
        "evidence": {"pip": {"status": "FICTIF", "rows": []}},
        "perspective_entreprise": "synthetic perspective",
    }


def result():
    return {"directions": [{"proposition": "Explorer", "evidence": ["CAV1:1"],
                            "source_refs": ["synthetic-source"], "question_en_seance": "Qu'en pensez-vous ?"}],
            "points_a_eclaircir": [], "incertitudes": ["Contexte à vérifier"],
            "source_refs": ["synthetic-source"]}


class FakeResponses:
    def __init__(self, output_text=None, error=None):
        self.output_text = output_text if output_text is not None else json.dumps(result())
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return type("Response", (), {"output_text": self.output_text, "status": "completed",
                                     "usage": type("Usage", (), {"input_tokens": 10, "output_tokens": 20})()})()


class FakeClient:
    def __init__(self, **kwargs):
        self.responses = FakeResponses()


def test_shared_contract_requires_key_and_defaults_model():
    with pytest.raises(Cav3AIError, match="clé IA partagée"):
        Cav3AISettings.from_mapping({})
    assert Cav3AISettings.from_mapping({"api_key": "synthetic"}).model == "gpt-5-mini"


def test_shared_contract_accepts_existing_environment_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-environment-key")
    settings = Cav3AISettings.from_streamlit_secrets()
    assert settings.api_key == "synthetic-environment-key"
    assert settings.model == "gpt-5-mini"
    assert ai_ready() is True


def test_api_client_matches_existing_timeout_and_retry_contract(monkeypatch):
    calls = []
    class OpenAI:
        def __init__(self, **kwargs): calls.append(kwargs)
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=OpenAI))
    api_client(Cav3AISettings("synthetic-key", "gpt-5-mini"))
    assert calls == [{"api_key": "synthetic-key", "timeout": 35.0, "max_retries": 0}]


def test_analysis_uses_responses_json_schema_without_storage_and_hashes_result():
    client = FakeClient()
    output = analyze_cav3(context(), settings(), client=client, monotonic=iter([2.0, 2.125]).__next__)
    call = client.responses.calls[0]
    sent = json.loads(call["input"])
    assert call["store"] is False
    assert call["text"]["format"]["type"] == "json_schema"
    assert sent["source_evidence"]["pip"]["status"] == "FICTIF"
    assert "cv" not in json.dumps(sent).lower()
    assert output["result"] == result()
    assert output["provider"] == "openai"
    assert output["metadata"]["source_refs"] == ["synthetic-source"]
    assert len(output["metadata"]["output_hash"]) == 64
    assert output["metadata"]["duration_seconds"] == 0.125


def test_unknown_context_never_calls_provider():
    client = FakeClient()
    invalid = {**context(), "schema": "OTHER"}
    with pytest.raises(Cav3AIError):
        analyze_cav3(invalid, settings(), client=client)
    assert client.responses.calls == []


def test_cav3_payload_is_allowlisted_and_provider_input_is_bounded():
    client = FakeClient()
    source = context()
    source["sources"][0]["private_notes"] = "do not transmit"
    source["response_sha256"] = "private-fingerprint"
    analyze_cav3(source, settings(), client=client)
    payload = client.responses.calls[0]["input"]
    assert "private_notes" not in payload
    assert "private-fingerprint" not in payload

    client = FakeClient()
    oversized = context()
    oversized["reponses"] = {"schema": "GO22_CAV1_CAV2_REPONSES_UNIQUES_V2",
                              "cav1": {"long": "x" * (49 * 1024)}, "cav2": {}}
    with pytest.raises(Cav3AIError, match="trop volumineuses"):
        analyze_cav3(oversized, settings(), client=client)
    assert client.responses.calls == []


def test_model_setting_has_a_safe_length_limit():
    with pytest.raises(Cav3AIError, match="modèle IA configuré"):
        Cav3AISettings.from_mapping({"api_key": "synthetic", "model": "x" * 121})


def test_provider_error_does_not_echo_credentials_or_body():
    secret = "synthetic-secret-not-to-leak"
    exc = RuntimeError(secret)
    exc.status_code = 403
    with pytest.raises(Cav3AIError) as err:
        analyze_cav3(context(), settings(), client=FakeClientWithError(exc))
    assert "403" in str(err.value)
    assert secret not in str(err.value)


class FakeClientWithError:
    def __init__(self, error):
        self.responses = FakeResponses(error=error)


def test_invalid_ai_output_and_unknown_source_refs_are_rejected():
    with pytest.raises(Cav3AIError, match="JSON lisible"):
        analyze_cav3(context(), settings(), client=FakeClientWithOutput("{"))
    invalid = result()
    invalid["source_refs"] = ["not-allowed"]
    with pytest.raises(Cav3AIError, match="référence inconnue"):
        analyze_cav3(context(), settings(), client=FakeClientWithOutput(json.dumps(invalid)))


def test_ai_output_is_rejected_when_it_adds_fields_or_exceeds_text_limits():
    extra = {**result(), "verdict": "METIER_VALIDÉ"}
    with pytest.raises(Cav3AIError, match="schéma attendu"):
        analyze_cav3(context(), settings(), client=FakeClientWithOutput(json.dumps(extra)))
    oversized = result()
    oversized["directions"][0]["proposition"] = "x" * 701
    with pytest.raises(Cav3AIError, match="limites du format"):
        analyze_cav3(context(), settings(), client=FakeClientWithOutput(json.dumps(oversized)))


class FakeClientWithOutput:
    def __init__(self, output):
        self.responses = FakeResponses(output_text=output)
