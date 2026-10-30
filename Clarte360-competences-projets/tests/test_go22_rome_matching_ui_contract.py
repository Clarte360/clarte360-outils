from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_phase_two_and_three_are_real_accompanist_workflows():
    ui = (ROOT / "clarte360_cp/ui/accompagnateur.py").read_text(encoding="utf-8")
    workshop = (ROOT / "clarte360_cp/ui/rome_workshop.py").read_text(encoding="utf-8")
    assert "render_rome_target_selection(ctx, view.snapshot.case_id)" in ui
    assert "render_rome_matching(ctx, view.snapshot.case_id)" in ui
    assert "render_rome_clarification(ctx, view.snapshot.case_id)" in ui
    assert "render_rome_investigations(ctx, view.snapshot.case_id)" in ui
    assert "Charger la fiche à jour depuis l’API" in workshop
    assert "Utiliser la fiche locale datée" in workshop
    assert "read_local_rome_metadata()" in workshop
    assert "Le bénéficiaire n’a pas de recherche ROME externe à faire" in workshop
    assert "MétierScope — rechercher un métier" not in workshop
    assert "ne prouve pas qu’un diplôme est légalement obligatoire" in workshop
    assert "Retenir ce métier" in workshop
    assert "st.checkbox(item.label" in workshop
    assert "st.multiselect(\"Élément(s) du parcours qui étayent ce savoir\"" in workshop
    assert "Préparer les rapprochements avec l’IA" in workshop
    assert "Enregistrer le rapprochement de la sélection" in workshop
    assert "selected_item_keys=[item.key for item in selected]" in workshop
    assert workshop.index("st.checkbox(item.label") < workshop.index("Préparer les rapprochements avec l’IA")
    assert "len(selected) > 40" in workshop
    assert "Études (avec ou sans diplôme)" in workshop
    assert "Apprentissage personnel / autodidacte" in workshop
    assert workshop.index("Synthèse des propositions IA — à discuter, non validées") < workshop.index("Détail des pistes IA à confronter")
    assert "Pistes d’acquis" in workshop
    assert "Points à confirmer avec le bénéficiaire" in workshop
    assert "une action d’investigation ciblée sera reliée à chaque métier ROME retenu" in workshop
    assert "le bénéficiaire renseigne toujours le questionnaire de retour" in workshop
    assert "aucune liste de sites n’est à parcourir systématiquement" in workshop
    assert "Confier une nouvelle investigation" in workshop
    assert "Transmettre cette action au bénéficiaire" in workshop
    beneficiary = (ROOT / "clarte360_cp/ui/beneficiaire.py").read_text(encoding="utf-8")
    assert "save_intersession_draft" in beneficiary
    assert "submit_intersession_response" in beneficiary
    assert "Envoyer mon retour à l’accompagnateur" in beneficiary


def test_beneficiary_receives_read_only_confirmed_match_and_diploma_rule():
    ui = (ROOT / "clarte360_cp/ui/beneficiaire.py").read_text(encoding="utf-8")
    assert "Aucune saisie n'est attendue" not in ui
    assert "Les savoirs rapprochés de votre parcours" in ui
    assert "études même sans diplôme" in ui
    assert "source officielle confirme" in ui
