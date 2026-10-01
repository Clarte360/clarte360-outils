from __future__ import annotations
import json, uuid
from pathlib import Path
import streamlit as st
from clarte360_ipip.framework.config import APP_SHORT_NAME, LOGO_PATH, PERSISTENT_DATA_DIR, RESOURCES_DIR
from clarte360_ipip.framework.branding import apply_framework_css
from clarte360_ipip.framework.validation import ValidationError
from clarte360_ipip.questionnaire import block_items, load_progress, load_questionnaire, save_progress, save_scoring_result
from clarte360_ipip.scoring import score_questionnaire
from clarte360_ipip.interpretation import load_interpretation, interpret_scoring
from clarte360_ipip.feedback import SCALE, save_feedback, load_feedback
from clarte360_ipip.reporting import generate_report
from clarte360_ipip.completion import is_completed, mark_completed, load_completion
from clarte360_ipip.version import APP_VERSION
from clarte360_ipip.connectors.gestion_actions import GestionActionsPort, LaunchTokenError, bind_prescription, prescription_status, report_document_ref
from clarte360_ipip.framework.config import load_gestion_actions_settings

st.set_page_config(page_title=APP_SHORT_NAME,page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else 'C360',layout='centered')
apply_framework_css()
q=load_questionnaire(RESOURCES_DIR/'ipip'/'REFERENTIEL_MAITRE_IPIP_NEO120_FR_V1_0.json')
iref=load_interpretation(RESOURCES_DIR/'ipip'/'REFERENTIEL_INTERPRETATION_CLARTE360_IPIP_NEO120_V1_0.json')
for k,v in {'run_id':uuid.uuid4().hex,'answers':{},'block':0,'started':False,'stage':'questionnaire','launch_ctx':None}.items(): st.session_state.setdefault(k,v)

# ACCOMPAGNEMENT: Gestion des Actions is the source of truth. The beneficiary never handles a JSON save.
launch_token=str(st.query_params.get('launch','') or '')
if not launch_token:
    st.error('Accès accompagnement invalide : ouvrez cet outil depuis Gestion des Actions.')
    st.stop()
try:
    ga_settings=load_gestion_actions_settings(st.secrets)
    ga=GestionActionsPort(ga_settings.launch_signing_key)
    ctx=ga.resolve_launch(launch_token)
    st.session_state.launch_ctx=ctx
    bound=bind_prescription(PERSISTENT_DATA_DIR,ctx,st.session_state.run_id)
    if bound != st.session_state.run_id:
        st.session_state.run_id=bound
        saved=load_progress(PERSISTENT_DATA_DIR,bound,expected_reference_version=q.version)
        if saved:
            st.session_state.answers=saved['answers']; st.session_state.block=saved['current_block']; st.session_state.started=True
            st.session_state.stage='completed' if prescription_status(PERSISTENT_DATA_DIR,ctx)=='TERMINE' else ('results' if len(saved['answers'])==120 else 'questionnaire')
    ga.publish_event('CONSULTE',{'beneficiary_id':ctx.beneficiary_id,'action_id':ctx.action_id,'prescription_id':ctx.prescription_id,'participant_id':ctx.participant_id,'passation_id':st.session_state.run_id})
except LaunchTokenError as exc:
    st.error(str(exc)); st.stop()


def persist():
    save_progress(PERSISTENT_DATA_DIR,st.session_state.run_id,reference_version=q.version,answers=st.session_state.answers,current_block=st.session_state.block)
    c=st.session_state.launch_ctx
    ga.publish_event('EN_COURS',{'beneficiary_id':c.beneficiary_id,'action_id':c.action_id,'prescription_id':c.prescription_id,'participant_id':c.participant_id,'passation_id':st.session_state.run_id})

def score_and_interpret():
    result=score_questionnaire(q,st.session_state.answers); save_scoring_result(PERSISTENT_DATA_DIR,st.session_state.run_id,result.to_dict())
    interp=interpret_scoring(result,iref)
    p=PERSISTENT_DATA_DIR/'interpretations'/f'{st.session_state.run_id}.json'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(interp,ensure_ascii=False,indent=2),encoding='utf-8')
    return result,interp

def load_result_files():
    sp=PERSISTENT_DATA_DIR/'scores'/f'{st.session_state.run_id}.json'; ip=PERSISTENT_DATA_DIR/'interpretations'/f'{st.session_state.run_id}.json'
    if not sp.exists() or not ip.exists(): return None,None
    return json.loads(sp.read_text(encoding='utf-8'))['result'],json.loads(ip.read_text(encoding='utf-8'))

st.title('Clarté360')
st.subheader('Profil de fonctionnement professionnel')
st.caption('IPIP-NEO-120 — adaptation française Clarté360 • modèle des cinq grands facteurs (Big Five)')
st.info(q.disclaimer)

# A completed run is read-only even in technical-resume mode.
if is_completed(PERSISTENT_DATA_DIR,st.session_state.run_id):
    comp=load_completion(PERSISTENT_DATA_DIR,st.session_state.run_id); report=Path(comp['report_path'])
    st.success('Cette passation est terminée et verrouillée. Les réponses ne peuvent plus être modifiées.')
    if report.exists(): st.download_button('Télécharger mon rapport PDF',report.read_bytes(),file_name='Clarte360_Profil_fonctionnement.pdf',mime='application/pdf',use_container_width=True)
    st.stop()

if not st.session_state.started:
    st.markdown('<div class="clarte-hero"><b>Comment ai-je tendance à fonctionner ?</b><br/>Cet outil explore cinq grandes dimensions de personnalité et 30 facettes. Il ne vous classe pas dans un type et ne cherche pas à dire ce qui serait “bon” ou “mauvais”.</div>',unsafe_allow_html=True)
    st.write('Vous allez répondre à **120 affirmations**, présentées par blocs de 10. Décrivez-vous tel que vous êtes généralement aujourd’hui, et non tel que vous souhaiteriez être.')
    st.write('Il n’y a pas de bonne ou de mauvaise réponse. Aucun résultat n’est affiché pendant la passation.')
    if st.button('Commencer',type='primary',use_container_width=True): st.session_state.started=True; persist(); st.rerun()
    st.stop()

if st.session_state.stage=='questionnaire':
    items=block_items(q,st.session_state.block,10)
    st.progress(len(st.session_state.answers)/120,text=f"Progression : {len(st.session_state.answers)} / 120 réponses")
    st.caption(f"Bloc {st.session_state.block+1} sur 12")
    local={}
    for item in items:
        current=st.session_state.answers.get(item.item_no); options=[1,2,3,4,5]; idx=options.index(current) if current in options else None
        local[item.item_no]=st.radio(f"{item.item_no}. {item.text_fr}",options,index=idx,format_func=lambda x:q.response_scale[x],key=f'i{item.item_no}')
    left,right=st.columns(2)
    if left.button('← Bloc précédent',use_container_width=True,disabled=st.session_state.block==0):
        for n,v in local.items():
            if v is not None: st.session_state.answers[n]=v
        st.session_state.block-=1; persist(); st.rerun()
    if right.button('Enregistrer et continuer →',type='primary',use_container_width=True):
        missing=[n for n,v in local.items() if v is None]
        if missing: st.error('Répondez aux 10 affirmations de ce bloc avant de continuer.')
        else:
            st.session_state.answers.update(local)
            if st.session_state.block<11: st.session_state.block+=1; persist(); st.rerun()
            else:
                persist(); score_and_interpret(); st.session_state.stage='results'; st.rerun()

if st.session_state.stage=='results':
    _,interp=load_result_files()
    if not interp:
        _,interp=score_and_interpret()
    st.success('Votre profil est calculé. Il décrit des tendances, pas des catégories ni un diagnostic.')
    st.header('Les 5 grandes dimensions')
    for d in interp['domains']:
        st.subheader(d['display_fr'])
        st.progress(float(d['index_0_100'])/100.0,text=f"Repère descriptif : {d['index_0_100']:.0f}/100 — {d['tendency_label']}")
        st.write(d['plain_definition'])
        st.caption(f"Terme scientifique : {d['scientific_term']}")
    st.header('Les 30 facettes')
    for d in interp['domains']:
        with st.expander(d['display_fr'],expanded=False):
            for f in [x for x in interp['facets'] if x['domain']==d['code']]:
                st.markdown(f"**{f['display_fr']}** — {f['tendency_label']}")
                st.progress(float(f['index_0_100'])/100.0)
                st.write(f['plain_definition'])
                st.write(f"**Lecture :** {f['tendency_text']}")
                st.caption(f"À explorer : {f['debrief_question']}")
    st.info(interp['non_normative_notice'])
    if st.button('Continuer vers mon ressenti',type='primary',use_container_width=True): st.session_state.stage='feedback'; st.rerun()

if st.session_state.stage=='feedback':
    _,interp=load_result_files()
    st.header('Mon ressenti sur mes résultats')
    st.write('Ces réponses ne modifient **jamais** votre score. Elles servent à préparer le dialogue avec votre accompagnateur.')
    opts=list(SCALE)
    global_r=st.radio('Dans quelle mesure le profil présenté vous ressemble-t-il ?',opts,index=None,format_func=lambda x:SCALE[x])
    dominant=st.radio('Les dimensions et facettes qui ressortent le plus correspondent-elles à votre perception de votre fonctionnement ?',opts,index=None,format_func=lambda x:SCALE[x])
    nuances=st.radio('Le rapport rend-il suffisamment compte des nuances et contrastes de votre façon de fonctionner ?',opts,index=None,format_func=lambda x:SCALE[x])
    useful=st.radio('Ces résultats vous aident-ils à mieux comprendre votre fonctionnement dans un contexte professionnel ?',opts,index=None,format_func=lambda x:SCALE[x])
    facet_choices=['']+[f"{x['code']} — {x['display_fr']}" for x in interp['facets']]
    over=st.selectbox('Un domaine ou une facette vous paraît-il présenté comme plus marqué que dans votre ressenti ? (facultatif)',facet_choices)
    under=st.selectbox('Un domaine ou une facette vous paraît-il présenté comme moins marqué que dans votre ressenti ? (facultatif)',facet_choices)
    dialogue=st.radio('Souhaitez-vous approfondir certains éléments avec votre accompagnateur ?', ['oui','non'],index=None,format_func=lambda x:'Oui' if x=='oui' else 'Non')
    free=st.text_area('Qu’aimeriez-vous retenir, nuancer ou approfondir à partir de ce profil ? (facultatif)',max_chars=4000)
    if st.button('Valider mon ressenti et générer mon rapport',type='primary',use_container_width=True):
        if None in (global_r,dominant,nuances,useful,dialogue): st.error('Merci de répondre aux questions obligatoires avant de valider.')
        else:
            fb={'global':global_r,'dominants':dominant,'nuances':nuances,'useful':useful,'over':over,'under':under,'dialogue':dialogue,'free':free}
            save_feedback(PERSISTENT_DATA_DIR,st.session_state.run_id,fb)
            report=PERSISTENT_DATA_DIR/'reports'/f'{st.session_state.run_id}_v1.pdf'
            sha=generate_report(report,interpretation=interp,feedback=fb,app_version=APP_VERSION,reference_version=q.version,interpretation_version=iref.version)
            mark_completed(PERSISTENT_DATA_DIR,st.session_state.run_id,report_path=str(report),report_sha256=sha)
            c=st.session_state.launch_ctx
            doc=report_document_ref(PERSISTENT_DATA_DIR,st.session_state.run_id)
            ga.publish_event('TERMINE',{'beneficiary_id':c.beneficiary_id,'action_id':c.action_id,'prescription_id':c.prescription_id,'participant_id':c.participant_id,'passation_id':st.session_state.run_id,'status':'TERMINE','documents':[doc],'reference_version':q.version,'interpretation_version':iref.version,'app_version':APP_VERSION})
            st.session_state.stage='completed'; st.rerun()

if st.session_state.stage=='completed':
    comp=load_completion(PERSISTENT_DATA_DIR,st.session_state.run_id); report=Path(comp['report_path'])
    st.success('Votre passation est terminée. Elle est désormais verrouillée en écriture.')
    st.write('Vous pouvez consulter ou télécharger votre rapport. Pour effectuer une nouvelle passation en mode accompagnement, une nouvelle prescription devra être créée par votre accompagnateur.')
    if report.exists(): st.download_button('Télécharger mon rapport PDF',report.read_bytes(),file_name='Clarte360_Profil_fonctionnement.pdf',mime='application/pdf',use_container_width=True)
