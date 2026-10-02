from __future__ import annotations
import json, uuid
from pathlib import Path
import streamlit as st
from clarte360_ipip.framework.config import APP_SHORT_NAME, SITE_ICON_PATH, LOGO_PATH, PERSISTENT_DATA_DIR, RESOURCES_DIR
from clarte360_ipip.framework.branding import apply_framework_css
from clarte360_ipip.framework.validation import ValidationError
from clarte360_ipip.questionnaire import load_progress, load_questionnaire, next_item, previous_item, resume_item, save_progress, save_scoring_result
from clarte360_ipip.scoring import score_questionnaire
from clarte360_ipip.interpretation import load_interpretation, interpret_scoring
from clarte360_ipip.feedback import SCALE, save_feedback, load_feedback
from clarte360_ipip.reporting import generate_report, beneficiary_report_filename
from clarte360_ipip.completion import is_completed, mark_completed, load_completion
from clarte360_ipip.version import APP_VERSION
from clarte360_ipip.connectors.gestion_actions import GestionActionsPort, LaunchTokenError, bind_prescription, prescription_status, report_document_ref, require_scope
from clarte360_ipip.framework.config import load_gestion_actions_settings
from clarte360_ipip.framework.session import initialize_session, touch_activity
from clarte360_ipip.framework.rgpd import build_information_record, information_is_current, load_information_record, render_non_clinical_notice, render_rgpd_information, save_information_record
from clarte360_ipip.framework.timeout import enforce_timeout
from clarte360_ipip.ui.sidebar import render_sidebar
from clarte360_ipip.ui.pages import render_auxiliary_page, render_home
from clarte360_ipip.ui.questionnaire import render_question
from clarte360_ipip.ui.results import render_results

st.set_page_config(page_title=APP_SHORT_NAME,page_icon=str(SITE_ICON_PATH) if SITE_ICON_PATH.exists() else 'C360',layout='centered')
apply_framework_css()
q=load_questionnaire(RESOURCES_DIR/'ipip'/'REFERENTIEL_MAITRE_IPIP_NEO120_FR_V1_0.json')
iref=load_interpretation(RESOURCES_DIR/'ipip'/'REFERENTIEL_INTERPRETATION_CLARTE360_IPIP_NEO120_V1_0.json')
for k,v in {'run_id':uuid.uuid4().hex,'answers':{},'current_item':1,'started':False,'stage':'questionnaire','launch_ctx':None,'feedback_draft':{}}.items(): st.session_state.setdefault(k,v)
initialize_session()

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
    status_before_bind=prescription_status(PERSISTENT_DATA_DIR,ctx)
    if status_before_bind=='EN_COURS':
        require_scope(ctx,'IPIP_RESUME')
    elif status_before_bind=='TERMINE':
        require_scope(ctx,'IPIP_RESULT_READ')
    bound=bind_prescription(PERSISTENT_DATA_DIR,ctx,st.session_state.run_id)
    if bound != st.session_state.run_id:
        st.session_state.run_id=bound
        saved=load_progress(PERSISTENT_DATA_DIR,bound,expected_reference_version=q.version)
        if saved:
            st.session_state.answers=saved['answers']; st.session_state.current_item=resume_item(saved['answers'],saved.get('current_item')); st.session_state.started=True
            st.session_state.stage='completed' if prescription_status(PERSISTENT_DATA_DIR,ctx)=='TERMINE' else ('results' if len(saved['answers'])==120 else 'questionnaire')
    require_scope(ctx,'IPIP_STATUS')
    ga.publish_event('CONSULTE',{'beneficiary_id':ctx.beneficiary_id,'action_id':ctx.action_id,'prescription_id':ctx.prescription_id,'participant_id':ctx.participant_id,'passation_id':st.session_state.run_id})
except LaunchTokenError as exc:
    st.error(str(exc)); st.stop()

# Framework J1: navigation/sidebar/timeout centralises autour du metier IPIP conserve.
enforce_timeout()
current_status=prescription_status(PERSISTENT_DATA_DIR,ctx)
render_sidebar(current_status)
page=st.session_state.get('navigation_page','accueil')
info_record=load_information_record(PERSISTENT_DATA_DIR,st.session_state.run_id)
info_current=information_is_current(info_record,q.version)
st.session_state.rgpd_acceptance=info_record

if page=='accueil':
    target=render_home(reference_version=q.version,started=st.session_state.started,information_current=info_current)
    if target:
        st.session_state.navigation_page=target; touch_activity('home_navigation'); st.rerun()
    st.stop()
if page=='information':
    st.title('Avant de commencer')
    understood,proceed=render_rgpd_information(show_confirmation=True,reference_version=q.version)
    if st.button('Confirmer et poursuivre',type='primary',use_container_width=True,disabled=not (understood and proceed)):
        record=build_information_record(ctx=ctx,reference_version=q.version,understood=understood,proceed=proceed)
        save_information_record(PERSISTENT_DATA_DIR,st.session_state.run_id,record)
        st.session_state.rgpd_acceptance=record
        if not st.session_state.started:
            st.session_state.started=True
            save_progress(PERSISTENT_DATA_DIR,st.session_state.run_id,reference_version=q.version,answers=st.session_state.answers,current_item=st.session_state.current_item)
            c=st.session_state.launch_ctx
            ga.publish_event('EN_COURS',{'beneficiary_id':c.beneficiary_id,'action_id':c.action_id,'prescription_id':c.prescription_id,'participant_id':c.participant_id,'passation_id':st.session_state.run_id})
        st.session_state.navigation_page='passation'; touch_activity('information_confirmed'); st.rerun()
    st.stop()
if render_auxiliary_page(page,q.version):
    st.stop()
if page=='passation' and not info_current:
    st.warning('Avant de poursuivre, vous devez prendre connaissance des informations relatives à la passation et à vos données.')
    if st.button('Lire les informations',type='primary',use_container_width=True):
        st.session_state.navigation_page='information'; touch_activity('information_required'); st.rerun()
    st.stop()


def persist():
    touch_activity('persist')
    save_progress(PERSISTENT_DATA_DIR,st.session_state.run_id,reference_version=q.version,answers=st.session_state.answers,current_item=st.session_state.current_item)
    c=st.session_state.launch_ctx
    require_scope(c,'IPIP_STATUS')
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

st.title('Profil de fonctionnement professionnel')
st.caption('IPIP-NEO-120 — adaptation française Clarté360 • modèle des cinq grands facteurs (Big Five)')
render_non_clinical_notice()

# A completed run is read-only even in technical-resume mode.
if is_completed(PERSISTENT_DATA_DIR,st.session_state.run_id):
    require_scope(ctx,'IPIP_RESULT_READ')
    comp=load_completion(PERSISTENT_DATA_DIR,st.session_state.run_id); report=Path(comp['report_path'])
    st.success('Cette passation est terminée et verrouillée. Les réponses ne peuvent plus être modifiées.')
    if report.exists():
        report_name=beneficiary_report_filename(ctx.beneficiary_first_name,ctx.beneficiary_last_name)
        st.download_button('Télécharger mon rapport PDF',report.read_bytes(),file_name=report_name,mime='application/pdf',use_container_width=True)
    st.stop()

if not st.session_state.started:
    st.session_state.navigation_page='accueil'
    st.rerun()

if st.session_state.stage=='questionnaire':
    item_no=int(st.session_state.current_item)
    st.caption(f"Progression de la passation • {len(st.session_state.answers)} réponse(s) enregistrée(s)")
    selected=render_question(q,item_no,st.session_state.answers)
    left,right=st.columns(2)
    if left.button('← PRÉCÉDENT',use_container_width=True,disabled=item_no==1):
        # A selected answer is saved even when the beneficiary navigates backward.
        if selected is not None:
            st.session_state.answers[item_no]=selected
        st.session_state.current_item=previous_item(item_no)
        persist(); st.rerun()
    next_label='TERMINER LE QUESTIONNAIRE' if item_no==120 else 'SUIVANT →'
    if right.button(next_label,type='primary',use_container_width=True):
        if selected is None:
            st.error('Choisissez une réponse avant de continuer.')
        else:
            st.session_state.answers[item_no]=selected
            if item_no<120:
                st.session_state.current_item=next_item(item_no)
                persist(); st.rerun()
            elif len(st.session_state.answers)!=120:
                missing=[n for n in range(1,121) if n not in st.session_state.answers]
                st.session_state.current_item=missing[0]
                persist()
                st.error('Une réponse manque encore. La passation reprend automatiquement à la première affirmation non renseignée.')
                st.rerun()
            else:
                persist(); score_and_interpret(); st.session_state.stage='results'; st.rerun()

if st.session_state.stage in {'results','feedback_results'}:
    _,interp=load_result_files()
    if not interp:
        _,interp=score_and_interpret()
    if st.session_state.stage=='feedback_results':
        st.info('Vous consultez vos résultats pendant le questionnaire de ressenti. Vos réponses déjà saisies sont conservées.')
    render_results(interp)
    if st.session_state.stage=='feedback_results':
        if st.button('← Retour à mon ressenti',type='primary',use_container_width=True):
            st.session_state.stage='feedback'; touch_activity('feedback_return'); st.rerun()
    elif st.button('Continuer vers mon ressenti',type='primary',use_container_width=True):
        st.session_state.stage='feedback'; touch_activity('feedback'); st.rerun()

if st.session_state.stage=='feedback':
    _,interp=load_result_files()
    st.header('Mon ressenti sur mes résultats')
    st.write('Ces réponses ne modifient **jamais** votre score. Elles servent à préparer le dialogue avec votre accompagnateur.')
    draft=st.session_state.get('feedback_draft',{})
    opts=list(SCALE)
    def idx(key, choices):
        value=draft.get(key)
        return choices.index(value) if value in choices else None
    global_r=st.radio('Dans quelle mesure le profil présenté vous ressemble-t-il ?',opts,index=idx('global',opts),format_func=lambda x:SCALE[x])
    dominant=st.radio('Les dimensions et facettes qui ressortent le plus correspondent-elles à votre perception de votre fonctionnement ?',opts,index=idx('dominants',opts),format_func=lambda x:SCALE[x])
    nuances=st.radio('Le rapport rend-il suffisamment compte des nuances et contrastes de votre façon de fonctionner ?',opts,index=idx('nuances',opts),format_func=lambda x:SCALE[x])
    useful=st.radio('Ces résultats vous aident-ils à mieux comprendre votre fonctionnement dans un contexte professionnel ?',opts,index=idx('useful',opts),format_func=lambda x:SCALE[x])
    facet_choices=['']+[f"{x['code']} — {x['display_fr']}" for x in interp['facets']]
    over=st.selectbox('Un domaine ou une facette vous paraît-il présenté comme plus marqué que dans votre ressenti ? (facultatif)',facet_choices,index=facet_choices.index(draft.get('over','')) if draft.get('over','') in facet_choices else 0)
    under=st.selectbox('Un domaine ou une facette vous paraît-il présenté comme moins marqué que dans votre ressenti ? (facultatif)',facet_choices,index=facet_choices.index(draft.get('under','')) if draft.get('under','') in facet_choices else 0)
    dialogue_choices=['oui','non']
    dialogue=st.radio('Souhaitez-vous approfondir certains éléments avec votre accompagnateur ?',dialogue_choices,index=idx('dialogue',dialogue_choices),format_func=lambda x:'Oui' if x=='oui' else 'Non')
    free=st.text_area('Qu’aimeriez-vous retenir, nuancer ou approfondir à partir de ce profil ? (facultatif)',value=draft.get('free',''),max_chars=4000)
    current_draft={'global':global_r,'dominants':dominant,'nuances':nuances,'useful':useful,'over':over,'under':under,'dialogue':dialogue,'free':free}
    st.session_state.feedback_draft=current_draft
    if st.button('Revoir mes résultats',use_container_width=True):
        st.session_state.stage='feedback_results'; touch_activity('feedback_results'); st.rerun()
    if st.button('Valider mon ressenti et générer mon rapport',type='primary',use_container_width=True):
        if None in (global_r,dominant,nuances,useful,dialogue): st.error('Merci de répondre aux questions obligatoires avant de valider.')
        else:
            # J7: valider les droits nécessaires AVANT toute mutation de clôture.
            # Un jeton incomplet ne doit jamais laisser une passation localement TERMINE.
            c=st.session_state.launch_ctx
            require_scope(c,'IPIP_RESULT_READ')
            require_scope(c,'IPIP_STATUS')
            fb={'global':global_r,'dominants':dominant,'nuances':nuances,'useful':useful,'over':over,'under':under,'dialogue':dialogue,'free':free}
            save_feedback(PERSISTENT_DATA_DIR,st.session_state.run_id,fb)
            report=PERSISTENT_DATA_DIR/'reports'/f'{st.session_state.run_id}_v1.pdf'
            sha=generate_report(report,interpretation=interp,feedback=fb,app_version=APP_VERSION,reference_version=q.version,interpretation_version=iref.version,beneficiary_identity={'first_name': c.beneficiary_first_name, 'last_name': c.beneficiary_last_name},logo_path=LOGO_PATH)
            mark_completed(PERSISTENT_DATA_DIR,st.session_state.run_id,report_path=str(report),report_sha256=sha,report_version=APP_VERSION)
            report_name=beneficiary_report_filename(c.beneficiary_first_name,c.beneficiary_last_name)
            doc=report_document_ref(PERSISTENT_DATA_DIR,st.session_state.run_id,prescription_id=c.prescription_id,display_file_name=report_name)
            require_scope(c,'IPIP_STATUS')
            ga.publish_event('TERMINE',{'beneficiary_id':c.beneficiary_id,'action_id':c.action_id,'prescription_id':c.prescription_id,'participant_id':c.participant_id,'passation_id':st.session_state.run_id,'status':'TERMINE','documents':[doc],'reference_version':q.version,'interpretation_version':iref.version,'app_version':APP_VERSION})
            st.session_state.stage='completed'; st.rerun()

if st.session_state.stage=='completed':
    require_scope(ctx,'IPIP_RESULT_READ')
    comp=load_completion(PERSISTENT_DATA_DIR,st.session_state.run_id); report=Path(comp['report_path'])
    st.success('Votre passation est terminée. Elle est désormais verrouillée en écriture.')
    st.write('Vous pouvez consulter ou télécharger votre rapport. Pour effectuer une nouvelle passation en mode accompagnement, une nouvelle prescription devra être créée par votre accompagnateur.')
    if report.exists():
        report_name=beneficiary_report_filename(ctx.beneficiary_first_name,ctx.beneficiary_last_name)
        st.download_button('Télécharger mon rapport PDF',report.read_bytes(),file_name=report_name,mime='application/pdf',use_container_width=True)
