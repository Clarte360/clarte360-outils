from __future__ import annotations

import json

import pytest

from clarte360_cp.connectors.cav3_ai import Cav3AIError, Cav3AISettings
from clarte360_cp.connectors.rome_matching_ai import analyze_rome_matching


class FakeResponses:
    def __init__(self, result):
        self.result = result
        self.calls = []
    def create(self, **kwargs):
        self.calls.append(kwargs)
        return type("Response", (), {"status": "completed", "output_text": json.dumps(self.result),
                                      "usage": None})()


class FakeClient:
    def __init__(self, result):
        self.responses = FakeResponses(result)


JOB = {"rome_code": "M1203", "label": "Comptable"}
ITEMS = [{"key": "SAVOIR:117781", "category": "SAVOIR", "label": "Comptabilité client"}]
EXPERIENCES = [{"id": "exp-1", "title": "Gestionnaire de comptes", "kind": "EMPLOI", "period": "2020–2024",
                "organization": "Organisation privée ne doit pas sortir", "evidence": "Suivi des règlements clients."}]
SETTINGS = Cav3AISettings("synthetic-key", "synthetic-model")


def valid_result():
    return {"propositions": [{"rome_item_key": "SAVOIR:117781", "statut_propose": "ACQUIS_POTENTIEL",
                              "experience_refs": ["exp-1"], "raisonnement": "Suivi des règlements clients à examiner.",
                              "question_en_seance": "Quelles vérifications réalisiez-vous ?"}], "incertitudes": []}


def test_uses_minimized_payload_and_no_storage():
    client = FakeClient(valid_result())
    result = analyze_rome_matching(JOB, ITEMS, EXPERIENCES, SETTINGS, client=client)
    call = client.responses.calls[0]
    sent = json.loads(call["input"])
    assert call["store"] is False
    assert "Organisation privée ne doit pas sortir" not in call["input"]
    assert sent["attendus_rome"][0]["key"] == "SAVOIR:117781"
    assert sent["experiences_confirmees_ou_a_revoir"][0]["nature_parcours"] == "EMPLOI"
    assert "Un niveau d’exercice discuté en séance est un repère contextuel" in call["instructions"]
    assert result["metadata"]["prompt_version"]


def test_rejects_unknown_evidence_reference():
    result = valid_result()
    result["propositions"][0]["experience_refs"] = ["unknown"]
    with pytest.raises(Cav3AIError, match="expérience absente"):
        analyze_rome_matching(JOB, ITEMS, EXPERIENCES, SETTINGS, client=FakeClient(result))


def test_rejects_acquis_suggestion_without_evidence():
    result = valid_result()
    result["propositions"][0]["experience_refs"] = []
    with pytest.raises(Cav3AIError, match="acquis potentiel"):
        analyze_rome_matching(JOB, ITEMS, EXPERIENCES, SETTINGS, client=FakeClient(result))


def test_rejects_duplicate_inputs_before_calling_ai():
    client = FakeClient(valid_result())
    with pytest.raises(Cav3AIError, match="dupliquées"):
        analyze_rome_matching(JOB, ITEMS + ITEMS, EXPERIENCES, SETTINGS, client=client)
    assert client.responses.calls == []


@pytest.mark.parametrize("mutate", [
    lambda result: result.update({"decision_finale": "COMPETENT"}),
    lambda result: result["propositions"][0].update({"score": 0.99}),
    lambda result: result["propositions"][0].update({"raisonnement": "x" * 1801}),
])
def test_rejects_extra_or_oversized_ai_fields(mutate):
    result = valid_result()
    mutate(result)
    with pytest.raises(Cav3AIError):
        analyze_rome_matching(JOB, ITEMS, EXPERIENCES, SETTINGS, client=FakeClient(result))
