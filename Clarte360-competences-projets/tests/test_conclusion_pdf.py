from clarte360_cp.reporting.conclusion_pdf import (
    render_action_plan_pdf, render_results_pdf, render_synthesis_pdf,
)


def test_final_conclusion_pdfs_are_generated_from_current_record():
    plan = render_action_plan_pdf({"version_no": 2, "items": [{
        "action": "Rencontrer deux professionnels du métier",
        "due": "Avant le prochain rendez-vous", "means": "Préparer les questions", "expected": "Deux retours documentés",
    }]})
    results = render_results_pdf({"version": 3, "content": {
        "parcours": "Expérience et études", "savoirs": "Comptabilité générale",
        "projet": "Chef comptable", "diploma_status": "Aucun diplôme obligatoire établi",
        "diploma_source": "Vérification officielle datée",
    }})
    synthesis = render_synthesis_pdf({"version": 1, "content": {
        "objectif": "Bilan de compétences", "projet": "Chef comptable",
        "conditions": "Consolider les savoirs", "plan": "Enquête et mise en pratique",
    }})
    for output in (plan, results, synthesis):
        assert output.startswith(b"%PDF-")
        assert len(output) > 1200
