from test_v218_model import load_app, seed


def test_expression_contract_rejects_identical_fake_reformulation():
    mod, st = load_app(); seed(mod, st)
    mod.ai_ready = lambda: True
    mod.response_json = lambda *a, **k: {
        'statut':'reformulation_expression',
        'texte_propose':'Donc du coup je suis content du coup.',
        'raison_courte':'',
        'question_clarification':''
    }
    result = mod.assess_response_expression('Donc du coup je suis content du coup.')
    assert result['statut'] == 'echec_technique'
    assert result['texte_propose'] == ''


def test_expression_contract_accepts_real_reformulation():
    mod, st = load_app(); seed(mod, st)
    mod.ai_ready = lambda: True
    mod.response_json = lambda *a, **k: {
        'statut':'reformulation_expression',
        'texte_propose':'Je suis satisfait lorsque mes apprenants réussissent leur examen et sont fiers de leurs acquis.',
        'raison_courte':'Formulation orale et répétitive.',
        'question_clarification':''
    }
    result = mod.assess_response_expression("Donc c'est quand mes apprenants réussissent du coup et ils sont fiers du coup.")
    assert result['statut'] == 'reformulation_expression'
    assert result['texte_propose'].startswith('Je suis satisfait')


def test_no_ai_does_not_claim_weak_text_is_clean():
    mod, st = load_app(); seed(mod, st)
    mod.ai_ready = lambda: False
    result = mod.assess_response_expression("Donc du coup je fais ça en fait et du coup je continue.")
    assert result['statut'] == 'echec_technique'


def test_module4_can_keep_two_hypotheses_same_cycle():
    mod, st = load_app(); seed(mod, st)
    cycle={'id':'C1','voie':'situation','exchanges':[{'question':'Q','reponse_validee':'R'}], 'reorientation_count':0}
    options=[{'nom':'Autonomie','definition':'A'}, {'nom':'Créativité','definition':'C'}, {'nom':'Reconnaissance','definition':'R'}]
    mod._module4_apply_hypothesis_decisions(cycle, options, {'Autonomie':'Oui','Créativité':'Peut-être','Reconnaissance':'Non'})
    assert cycle['result']=='hypotheses_retenues'
    assert cycle['stage']=='termine'
    assert cycle['selected_hypotheses']==['Autonomie','Créativité']
    basket={x['nom']:x for x in st.session_state.hypothesis_basket}
    assert set(basket)=={'Autonomie','Créativité'}
    assert basket['Autonomie']['decision_module4']=='oui'
    assert basket['Créativité']['decision_module4']=='peut_etre'
    assert st.session_state.module4_rejected_hypotheses[0]['nom']=='Reconnaissance'
