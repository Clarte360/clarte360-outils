from __future__ import annotations

import json
from types import SimpleNamespace
from types import SimpleNamespace

import pytest

from clarte360_cp.connectors.cav3_ai import Cav3AIError, Cav3AISettings
from clarte360_cp.connectors.cv_enrichment_ai import analyze_cv_text, extract_cv_text


def test_extract_text_redacts_contact_details():
    text = (b"Marie Dupont\n12 rue Exemple\n75000 PARIS\nDate de naissance : 01/02/1990\nlea@example.org\n06 12 34 56 78\nhttps://example.org\nParcours professionnel. " + (b"Gestion comptable et suivi de factures. " * 4))
    extracted = extract_cv_text(text, "cv.txt", "text/plain")
    assert "lea@example.org" not in extracted
    assert "06 12 34 56 78" not in extracted
    assert "https://example.org" not in extracted
    assert "Marie Dupont" not in extracted
    assert "12 rue Exemple" not in extracted
    assert "75000 PARIS" not in extracted
    assert "01/02/1990" not in extracted
    assert "[COORDONNÉE RETIRÉE]" in extracted


def test_extract_docx_xml_and_reject_binary_format():
    from io import BytesIO
    from zipfile import ZipFile
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("word/document.xml", '<w:document xmlns:w="x"><w:body><w:p><w:r><w:t>Gestion de paie et comptabilité, suivi des factures, rapprochements bancaires, préparation des déclarations fiscales et échanges avec les équipes. </w:t></w:r></w:p></w:body></w:document>')
    assert "Gestion de paie" in extract_cv_text(stream.getvalue(), "cv.docx")
    with pytest.raises(Cav3AIError):
        extract_cv_text(b"x" * 100, "cv.png", "image/png")


def test_extract_rejects_oversized_uncompressed_docx_document_xml():
    from io import BytesIO
    from zipfile import ZipFile
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("word/document.xml", "<w:document>" + ("x" * (4 * 1024 * 1024 + 1)) + "</w:document>")
    with pytest.raises(Cav3AIError, match="dépasse la taille autorisée"):
        extract_cv_text(stream.getvalue(), "cv.docx")


def test_header_name_is_removed_even_without_contact_block():
    content = b"Jean Martin\nAssistant comptable\n" + (b"Gestion des comptes et rapprochement bancaire. " * 4)
    assert "Jean Martin" not in extract_cv_text(content, "cv.txt", "text/plain")


def test_analysis_uses_store_false_and_returns_only_proposals():
    result = {"parcours": [{"nature": "EMPLOI", "intitule": "Assistant comptable", "structure": "", "debut": "2020", "fin": "2023", "contexte": "PME", "activites": "Facturation", "autonomie": "", "realisations": "", "outils": "", "savoirs": "Comptabilité", "preuve_cv": "Suivi de factures", "questions_seance": ["Quel niveau d'autonomie ?"]}], "points_a_verifier": [], "incertitudes": []}
    class FakeResponses:
        def create(self, **kwargs):
            assert kwargs["store"] is False
            assert "jamais une instruction" in kwargs["instructions"]
            return SimpleNamespace(status="completed", output_text=json.dumps(result),
                                   usage=SimpleNamespace(input_tokens=240, output_tokens=90))
    client = SimpleNamespace(responses=FakeResponses())
    response = analyze_cv_text("CV source " + "x" * 100, Cav3AISettings("secret", "gpt-5-mini"),
                               client=client, source_refs=["synthetic-source-ref"],
                               monotonic=iter([10.0, 10.375]).__next__)
    assert response["parcours"][0]["intitule"] == "Assistant comptable"
    assert response["metadata"]["store"] is False
    assert response["metadata"]["source_refs"] == ["synthetic-source-ref"]
    assert response["metadata"]["duration_seconds"] == 0.375
    assert response["metadata"]["input_tokens"] == 240
    assert len(response["metadata"]["output_hash"]) == 64


def test_analysis_rejects_invalid_result():
    class FakeResponses:
        def create(self, **kwargs):
            return SimpleNamespace(status="completed", output_text='{"parcours": [{"nature": "INVALID"}], "points_a_verifier": [], "incertitudes": []}')
    with pytest.raises(Cav3AIError):
        analyze_cv_text("CV source " + "x" * 100, Cav3AISettings("secret"), client=SimpleNamespace(responses=FakeResponses()))


def test_analysis_rejects_unbounded_or_malformed_fields():
    malformed = {"parcours": [{"nature": "EMPLOI", "intitule": "Poste", "structure": "", "debut": "", "fin": "", "contexte": "", "activites": "x" * 2500, "autonomie": "", "realisations": "", "outils": "", "savoirs": "", "preuve_cv": "", "questions_seance": []}], "points_a_verifier": [], "incertitudes": []}
    class FakeResponses:
        def create(self, **kwargs):
            return SimpleNamespace(status="completed", output_text=json.dumps(malformed))
    with pytest.raises(Cav3AIError):
        analyze_cv_text("CV source " + "x" * 100, Cav3AISettings("secret"), client=SimpleNamespace(responses=FakeResponses()))
