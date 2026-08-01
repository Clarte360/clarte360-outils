from test_v218_model import load_app, seed


def test_review_items_can_be_reopened_and_do_not_block_themselves():
    mod, st = load_app(); seed(mod, st)
    st.session_state.session_review_items=[{"id":"r1","terme":"Sécurité financière","definition":"Disposer de ressources suffisantes.","statut":"a_revoir_en_seance"}]
    work=mod._new_value_work("examen_seance")
    work.update({"original_name":"Sécurité financière","nom_initial":"Sécurité financière","nom_final":"Sécurité financière","origin_snapshot":dict(st.session_state.session_review_items[0])})
    st.session_state.session_review_items=[]
    location,_=mod._active_value_location("Sécurité financière")
    assert location==""
    mod._restore_current_module3_origin(work)
    assert st.session_state.session_review_items[0]["terme"]=="Sécurité financière"


def test_pending_value_is_restored_when_user_leaves_without_decision():
    mod, st = load_app(); seed(mod, st)
    original={"id":"p1","nom_final":"Sécurité financière","nom_initial":"La sécurité financier","definition_personnelle":"Peur d'être en manque financière","source":"migration_v2137"}
    work=dict(original)
    work.update({"source":"examen_attente","source_initiale":"migration_v2137","original_name":"Sécurité financière","origin_snapshot":dict(original)})
    mod._restore_current_module3_origin(work)
    assert len(st.session_state.values_to_examine)==1
    assert st.session_state.values_to_examine[0]["nom_final"]=="Sécurité financière"


def test_definitive_deletion_removes_all_business_content():
    mod, st = load_app(); seed(mod, st)
    name="Sécurité financière"
    st.session_state.central_validated_values=[{"nom_final":name,"statut":"validee"}]
    st.session_state.values_to_examine=[{"nom_final":name,"definition_personnelle":"Définition"}]
    st.session_state.session_review_items=[{"terme":name,"statut":"a_revoir_en_seance"}]
    st.session_state.validation={name:{"fondamentale":True}}
    st.session_state.personal_defs={name:"Définition"}
    st.session_state.value_records={name:{"nom_propose":name,"statut":"en_cours_analyse"}}
    st.session_state.hypothesis_status={name:"a_examiner"}
    st.session_state.trace=[{"action":"test","details":name}]
    st.session_state.answer_metadata={"m3_def_securite":{"version_officielle":"Définition de Sécurité financière"}}
    mod._purge_value_everywhere(name,"La sécurité financier")
    assert st.session_state.central_validated_values==[]
    assert st.session_state.values_to_examine==[]
    assert st.session_state.session_review_items==[]
    assert name not in st.session_state.validation
    assert name not in st.session_state.personal_defs
    assert name not in st.session_state.value_records
    assert name not in st.session_state.hypothesis_status
    assert st.session_state.trace==[]
    assert st.session_state.answer_metadata=={}
