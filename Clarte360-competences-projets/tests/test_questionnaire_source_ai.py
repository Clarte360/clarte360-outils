import json

import pytest

from clarte360_cp.connectors import questionnaire_source_ai as connector
from clarte360_cp.connectors.cav3_ai import Cav3AISettings
from clarte360_cp.domain.preparation_v2 import generate_questionnaire_v2


class FakeResponses:
    def __init__(self, output):
        self.output = output

    def create(self, **kwargs):
        assert kwargs["store"] is False
        return type("Response", (), {"status": "completed", "output_text": json.dumps(self.output)})()


class FakeClient:
    def __init__(self, output):
        self.responses = FakeResponses(output)


def _evidence(rows=(), *, code=""):
    return {"scale": "Rapport", "note": "Résultats à relire avec le bénéficiaire.",
            "profile_code": code, "rows": list(rows)}


def test_source_analysis_builds_aps_idea_and_report_evidence(monkeypatch):
    texts = {
        "CV_SOURCE": "CV texte lisible avec plusieurs expériences professionnelles, compétences, formations et activités détaillées dans le parcours.",
        "APS_OBJECTIF": "Dans son APS, Dominique évoque un métier de préparatrice en pharmacie. Le bilan explorera cette piste lors du prochain entretien.",
        "BOUSSOLE_VALEURS": "Autonomie : 4/5. Le rapport présente les valeurs professionnelles et leur incarnation dans plusieurs situations concrètes.",
        "MOTEURS_PRO": "Résultats moteurs du rapport. Les résultats sont présentés avec leurs définitions et une synthèse des motivations professionnelles.",
        "PREFERENCES_PRO": "Mode de travail : préférence pour travailler en équipe ou en autonomie. Le rapport présente les continuums et les activités préférées.",
        "IPIP_REPORT": "Rapport IPIP : organisation. Le document présente les dimensions et leur synthèse pour le fonctionnement professionnel.",
        "PIP_REPORT": "Code RIA - Réaliste, Investigateur, Artistique. Le rapport présente les familles d'intérêts professionnels et leurs descriptions.",
    }
    monkeypatch.setattr(connector, "extract_cv_text", lambda content, filename, mime, **kwargs: content.decode())
    rows = {
        "valeurs": [{"key":"V1", "label":"Autonomie", "explanation":"Autonomie déclarée dans le rapport.",
                     "score_display":"4/5", "pole_1":"", "pole_2":"", "evidence_quote":"Autonomie : 4/5"}],
        "moteurs": [],
        "preferences": [{"key":"PP1", "label":"Mode de travail", "explanation":"Préférence à explorer.",
                         "score_display":"", "pole_1":"En équipe", "pole_2":"En autonomie",
                         "evidence_quote":"Mode de travail : préférence pour travailler en équipe ou en autonomie."}],
        "ipip": [{"key":"IP1", "label":"Organisation", "explanation":"Résultat repris du rapport.",
                  "score_display":"", "pole_1":"", "pole_2":"", "evidence_quote":"Rapport IPIP : organisation."}],
        "pip": [{"key":"R", "label":"Réaliste", "explanation":"Dimension R du rapport.", "score_display":"",
                 "pole_1":"", "pole_2":"", "evidence_quote":"Réaliste"},
                {"key":"I", "label":"Investigateur", "explanation":"Dimension I du rapport.", "score_display":"",
                 "pole_1":"", "pole_2":"", "evidence_quote":"Investigateur"},
                {"key":"A", "label":"Artistique", "explanation":"Dimension A du rapport.", "score_display":"",
                 "pole_1":"", "pole_2":"", "evidence_quote":"Artistique"}],
    }
    output = {
        "ideas": [{"source_quote":"Dominique évoque un métier de préparatrice en pharmacie",
                   "wording":"Préparatrice en pharmacie",
                   "context_prompt":"Comment votre expérience en vente pourrait-elle éclairer votre intérêt pour la préparation en pharmacie ?"}],
        "valeurs": _evidence(rows["valeurs"]), "moteurs": _evidence(),
        "preferences": _evidence(rows["preferences"]), "ipip": _evidence(rows["ipip"]),
        "pip": _evidence(rows["pip"], code="RIA"),
    }
    source_rows = [{"purpose": purpose, "source_ref": f"ref-{purpose}", "label": purpose,
                    "name": f"{purpose}.pdf", "mime_type":"application/pdf", "content": text.encode()}
                   for purpose, text in texts.items()]
    analysis = connector.analyze_questionnaire_sources(source_rows, Cav3AISettings("test"),
                                                       client=FakeClient(output))
    source_map = {
        "APS_OBJECTIF": {"authorized":True, "source_ref":"ref-APS_OBJECTIF", "idea_details":analysis["ideas"]},
        "BOUSSOLE_VALEURS": {"authorized":True, "source_ref":"ref-BOUSSOLE_VALEURS",
                              "items":["Autonomie"], "result_summary":analysis["evidence"]["valeurs"]},
        "MOTEURS_PRO": {"authorized":True, "source_ref":"ref-MOTEURS_PRO",
                        "items":[], "result_summary":analysis["evidence"]["moteurs"]},
        "PREFERENCES_PRO": {"authorized":True, "source_ref":"ref-PREFERENCES_PRO",
                             "dimensions":analysis["preference_dimensions"],
                             "result_summary":analysis["evidence"]["preferences"]},
        "IPIP_REPORT": {"authorized":True, "source_ref":"ref-IPIP_REPORT", "status":"REEL",
                        "result_summary":analysis["evidence"]["ipip"]},
        "PIP_REPORT": {"authorized":True, "source_ref":"ref-PIP_REPORT", "status":"REEL",
                       "result_summary":analysis["evidence"]["pip"]},
    }
    questionnaire = generate_questionnaire_v2(source_map)
    assert questionnaire["ideas_active"][0]["wording"] == "Préparatrice en pharmacie"
    assert questionnaire["ideas_active"][0]["source_wording"] == output["ideas"][0]["source_quote"]
    assert "vente" in questionnaire["ideas_active"][0]["context_prompt"]
    assert questionnaire["cav2"]["valeurs"]["choices"] == ["Autonomie"]
    assert questionnaire["cav2"]["preferences"]["dimensions"][0]["pole_1"] == "En équipe"
    assert questionnaire["evidence"]["pip"]["profile_code"] == "RIA"


def test_source_analysis_rejects_unanchored_aps_idea(monkeypatch):
    monkeypatch.setattr(connector, "extract_cv_text", lambda content, filename, mime, **kwargs: content.decode())
    output = {"ideas":[{"source_quote":"Pharmacienne", "wording":"Pharmacienne",
                         "context_prompt":"Que souhaitez-vous explorer ?"}],
              **{key:_evidence() for key in ("valeurs", "moteurs", "preferences", "ipip", "pip")}}
    with pytest.raises(Exception, match="citation exacte de l’APS"):
        connector.analyze_questionnaire_sources(
            [{"purpose":"APS_OBJECTIF", "source_ref":"aps", "name":"aps.pdf", "mime_type":"application/pdf",
              "content":b"Dans son APS, une piste de preparatrice en pharmacie est ecrite ici. Le document contient suffisamment de texte pour lancer une analyse fidele."}],
            Cav3AISettings("test"), client=FakeClient(output))
