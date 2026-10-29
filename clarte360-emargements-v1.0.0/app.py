from __future__ import annotations
import io, os, json, csv, base64, re
from datetime import date, datetime, time as dt_time
from pathlib import Path
from urllib.parse import quote
import pandas as pd
import qrcode
from PIL import Image as PILImage
import streamlit as st
import streamlit.components.v1 as components
from streamlit_drawable_canvas import st_canvas

from branding import *
from db import make_engine, init_db, q, one, execute, audit, sha256_bytes, utcnow_iso
from security import hash_password, verify_password
from persistent_session import create_session, resolve_session, revoke_session, revoke_subject_sessions
from ui_guard import log_ui_exception, safe_call, user_message
from production_readiness import runtime_readiness
from services import *
from services import _duration_hms, _slot_participant_states
from purge_guard import preview_action_purge, certify_test_action, recover_action_purges, legacy_quality_orphans
from input_validation import validate_action_no, validate_short_text, validate_date_range, validate_participant_payload, validate_email, validate_full_name, InputValidationError
from excel_import import read_action_xlsm, list_action_numbers_for_profile, read_clarte360_xlsm, read_adca_xlsm, list_action_numbers
from pdf_utils import collective_pdf, individual_pdf, certificate_pdf, quality_response_pdf, teams_evidence_pdf, professional_cv_pdf
from mailer import send_mail, resolve_mail_config, validate_mail_config
from source_store import source_info, set_external_path, save_uploaded_source, refresh_from_external, read_snapshot, copy_source_metadata
from graph_client import GraphClient, graph_config_from_mapping, graph_config_missing
from signature_guard import signature_trace_is_valid, signature_trace_metrics
from qualification_ai import QualificationAIGateway, GlobalDossierAIGateway, extract_document_text, inspect_pdf_for_ai, PROMPT_VERSION, GLOBAL_PROMPT_VERSION
from workflow_navigation import prepare_action_qualification_navigation, mark_qualification_saved_for_action, prepare_return_to_action
from navigation_p3 import ADMIN_PAGES, screens_for_role, preferred_screen, authorized_action_choice, action_rows
from admin_navigation import (
    WORKSPACE_HOME, WORKSPACE_GENERAL, WORKSPACE_ACTIONS, WORKSPACES,
    GENERAL_PAGES, ACTION_PAGES, PAGE_SIZE, pages_for_workspace,
    workspace_for_route, valid_route, filter_sort_actions, page_slice,
    action_label, action_list_rows,
)
from portal_dashboard import beneficiary_dashboard, client_dashboard
from regional_settings import (format_timestamp as regional_timestamp,format_date as regional_date,
    format_wall_time as regional_wall_time,date_input_format as regional_date_input_format)
from mission_engagements import (
    action_mission_coverage,enable_action_mission_control,list_action_missions,
    list_trainer_missions,verify_mission_engagement,revise_mission,mission_outbox_pending,change_mission_status,
)
from client_portal import (
    client_portal_identity, verify_client_login, redeem_client_access_token,
    create_client_portal_account, list_client_accounts_admin, set_client_account_active,
    reconcile_client_contact_email,
    issue_client_access_token, grant_client_action, revoke_client_action,
    list_admin_client_grants, list_client_actions, client_action_summary,
    client_public_schedule, list_client_documents, read_client_document,
    export_client_action_zip, client_upload_document, list_client_submissions,
    create_client_delivery, share_client_document, revoke_client_document,
    list_admin_client_document_shares,
    DOC_SHAREABLE_CATEGORIES,
)


st.set_page_config(page_title=APP_NAME,page_icon=str(ICON_PATH),layout='wide',initial_sidebar_state='expanded')
st.markdown(CSS,unsafe_allow_html=True)

def secret(section,key,default=None):
    try:return st.secrets.get(section,{}).get(key,default)
    except:return default
DB_URL=secret('database','url',None); ENGINE=make_engine(DB_URL);init_db(ENGINE)
ensure_default_organization(ENGINE); migrate_legacy_action_statuses(ENGINE)
try:
    _org_for_import=get_organization(ENGINE)
    if _org_for_import:
        _pid=ensure_default_import_profile(ENGINE,_org_for_import['id'],'NO_CLAR','system')
        # Preserve the historical Clarté360 snapshot transparently under the new generic profile key.
        copy_source_metadata('CLARTE360',f'PROFILE_{_pid}')
except Exception:
    pass
try:
    _default_org=get_organization(ENGINE)
    seed_standard_questionnaires(ENGINE,_default_org.get('id') if _default_org else None,'system')
except Exception:
    pass
try:
    seed_tool_catalog(ENGINE,'system')
except Exception:
    pass
BASE_URL=secret('app','base_url','http://localhost:8501')
DISPLAY_PREFERENCES=get_regional_preferences(ENGINE)
TZ=DISPLAY_PREFERENCES['timezone']

def format_app_datetime(value, action_id=None):
    prefs=get_regional_preferences(ENGINE,action_id) if action_id else DISPLAY_PREFERENCES
    return regional_timestamp(value,prefs)

def format_app_date(value,action_id=None):
    prefs=get_regional_preferences(ENGINE,action_id) if action_id else DISPLAY_PREFERENCES
    return regional_date(value,prefs)

def format_app_time(value,action_id=None):
    prefs=get_regional_preferences(ENGINE,action_id) if action_id else DISPLAY_PREFERENCES
    return regional_wall_time(value,prefs)

def format_app_deadline(value,action_id=None):
    """Deadlines can be date-only OR UTC timestamps; never hide a real due hour."""
    if isinstance(value,datetime) or (isinstance(value,str) and ('T' in value or ' ' in value)):
        return format_app_datetime(value,action_id)
    return format_app_date(value,action_id)


def app_date_input_format():
    return regional_date_input_format(DISPLAY_PREFERENCES)

try:
    refresh_pip_connector_runtime_status(ENGINE,secret('pip_connector','launch_signing_key',''),secret('pip_connector','outbox_path',''),'system')
except Exception:
    pass
try:
    _ipip_sec=st.secrets.get('IPIP_CONNECTOR',{})
    refresh_ipip_connector_runtime_status(ENGINE,_ipip_sec.get('LAUNCH_SIGNING_KEY',''),_ipip_sec.get('OUTBOX_PENDING_DIR',''),'system')
except Exception:
    pass
_PIN_KEY=secret('security','participant_pin_key',secret('app','setup_key',''))
if _PIN_KEY: os.environ['CLARTE360_PIN_KEY']=str(_PIN_KEY)
TRAINER_REPORT_DIR=Path(__file__).resolve().parent/'data'/'trainer_reports'; TRAINER_REPORT_DIR.mkdir(parents=True,exist_ok=True)


def _rc2p_manage_structured_rows(ppid, table, rows, label_field, editable_fields, key_prefix):
    """RC2 provisoire: chaque tableau métier devient actionnable (modifier/supprimer)."""
    if not rows: return
    labels={f"{r.get(label_field) or 'Ligne'} — #{r['id']}":r for r in rows}
    with st.expander('Modifier ou supprimer une ligne du tableau'):
        lab=st.selectbox('Ligne à gérer',list(labels),key=f'{key_prefix}_row'); row=labels[lab]
        with st.form(f'{key_prefix}_edit_{row["id"]}'):
            vals={}
            for field,label,kind in editable_fields:
                if kind=='bool': vals[field]=st.checkbox(label,value=bool(row.get(field)))
                elif kind=='long': vals[field]=st.text_area(label,value=str(row.get(field) or ''),height=80)
                else: vals[field]=st.text_input(label,value=str(row.get(field) or ''))
            save=st.form_submit_button('Enregistrer les modifications')
        if save:
            update_professional_structured_row(ENGINE,table,row['id'],ppid,vals,st.session_state.admin_email);st.success('Ligne modifiée.');rerun()
        confirm=st.checkbox('Je confirme la suppression de cette ligne',key=f'{key_prefix}_del_confirm_{row["id"]}')
        if st.button('Supprimer la ligne',key=f'{key_prefix}_del_{row["id"]}',disabled=not confirm):
            delete_professional_structured_row(ENGINE,table,row['id'],ppid,st.session_state.admin_email);st.success('Ligne supprimée.');rerun()

def request_technical_context():
    try:
        h=st.context.headers
        ip=(h.get('X-Forwarded-For') or h.get('X-Real-IP') or '').split(',')[0].strip() or None
        ua=h.get('User-Agent') or None
        return ip,ua
    except Exception:
        return None,None

COOKIE_NAMES = {
    'ADMIN': 'c360_admin_session',
    'TRAINER': 'c360_trainer_session',
    'BENEFICIARY': 'c360_beneficiary_session',
    'CLIENT': 'c360_client_session',
}


def _session_ttl_hours():
    try:
        return max(1, min(int(secret('security','session_hours',12) or 12), 24*30))
    except Exception:
        return 12


def _browser_cookie(name):
    try:
        return st.context.cookies.get(name)
    except Exception:
        return None


def _emit_browser_cookie(name, value='', max_age=0, reload_page=False):
    """Pose/supprime un cookie opaque sans exposer le jeton dans l'URL."""
    secure = '; Secure' if str(BASE_URL).lower().startswith('https://') else ''
    cookie = f"{name}={value}; Path=/; Max-Age={int(max_age)}; SameSite=Strict{secure}"
    reload_js = "setTimeout(function(){window.parent.location.reload();},120);" if reload_page else ""
    script = f"""<script>
    (function(){{
      var c={json.dumps(cookie)};
      try {{ window.parent.document.cookie=c; }} catch(e) {{ document.cookie=c; }}
      {reload_js}
    }})();
    </script>"""
    components.html(script,height=0,width=0)


def _issue_persistent_session(role, subject_ref, actor='system'):
    ip,ua=request_technical_context()
    token=create_session(ENGINE,role,subject_ref,ttl_hours=_session_ttl_hours(),ip_address=ip,user_agent=ua)
    audit(ENGINE,'AUTH_SESSION_CREATED',actor=actor,entity_type=role.lower(),entity_id=subject_ref,details={'ttl_hours':_session_ttl_hours()})
    _emit_browser_cookie(COOKIE_NAMES[role],token,_session_ttl_hours()*3600,True)
    st.stop()


def _restore_role_session(role):
    token=_browser_cookie(COOKIE_NAMES[role])
    if not token:
        return None
    row=resolve_session(ENGINE,token,expected_type=role)
    if not row:
        _emit_browser_cookie(COOKIE_NAMES[role],'',0,False)
        return None
    return row


def _logout_persistent(role, session_keys):
    token=_browser_cookie(COOKIE_NAMES[role])
    if token:
        revoke_session(ENGINE,token)
    for key in session_keys:
        st.session_state.pop(key,None)
    _emit_browser_cookie(COOKIE_NAMES[role],'',0,True)
    st.stop()


def _restore_admin_session():
    if st.session_state.get('admin_email'):
        return True
    row=_restore_role_session('ADMIN')
    if not row:
        return False
    a=one(ENGINE,'SELECT * FROM admins WHERE email=:e AND active=1',{'e':row['subject_ref']})
    if not a:
        return False
    st.session_state.admin_email=a['email']
    st.session_state.admin_name=a.get('full_name') or a['email']
    audit(ENGINE,'AUTH_SESSION_RESTORED',actor=a['email'],entity_type='admin',entity_id=a['email'],details={'role':'ADMIN'})
    return True


def _restore_trainer_session():
    if st.session_state.get('trainer_portal_id'):
        return True
    row=_restore_role_session('TRAINER')
    if not row:
        return False
    tr=one(ENGINE,'SELECT * FROM trainers WHERE id=:i AND active=1',{'i':int(row['subject_ref'])})
    if not tr:
        return False
    st.session_state.trainer_portal_id=tr['id']
    st.session_state.trainer_portal_name=tr['full_name']
    audit(ENGINE,'AUTH_SESSION_RESTORED',actor=tr.get('email') or tr['full_name'],entity_type='trainer',entity_id=tr['id'],details={'role':'TRAINER'})
    return True


def _restore_beneficiary_session():
    if st.session_state.get('beneficiary_portal_id'):
        return True
    row=_restore_role_session('BENEFICIARY')
    if not row:
        return False
    bid=int(row['subject_ref'])
    b=one(ENGINE,'SELECT * FROM beneficiaries WHERE id=:b AND active=1',{'b':bid})
    acc=one(ENGINE,'SELECT * FROM beneficiary_portal_accounts WHERE beneficiary_id=:b AND active=1',{'b':bid})
    if not b or not acc:
        return False
    st.session_state.beneficiary_portal_id=bid
    audit(ENGINE,'AUTH_SESSION_RESTORED',actor=acc.get('email') or 'beneficiary',entity_type='beneficiary',entity_id=bid,details={'role':'BENEFICIARY'})
    return True


def _restore_client_session():
    if st.session_state.get('client_portal_id'):
        return True
    row=_restore_role_session('CLIENT')
    if not row:
        return False
    try:
        acc=client_portal_identity(ENGINE,int(row['subject_ref']))
    except (PermissionError,ValueError,TypeError):
        return False
    st.session_state.client_portal_id=acc['id']
    audit(ENGINE,'CLIENT_SESSION_RESTORED',actor='client_portal',entity_type='client_portal_account',
          entity_id=acc['id'],details={'role':'CLIENT'})
    return True


def _p3_sidebar_section(role, *, action_id=None, action_no=None, show_title=True):
    """Contextual vertical sidebar; no access is conferred by navigation."""
    screens=screens_for_role(role,action_selected=(action_id is not None))
    choices=[screen.key for screen in screens]
    key=f"p3_screen_{role.lower()}" if role=='BENEFICIARY' else f"p3_screen_{role.lower()}_{action_id}"
    prior=st.session_state.get(key)
    selected=preferred_screen(screens,prior)
    if prior!=selected:
        st.session_state[key]=selected
    if action_no:
        st.sidebar.caption(f"Action {action_no}")
    st.sidebar.markdown('#### Rubriques de mon espace')
    label_by_key={screen.key:screen.label for screen in screens}
    selection=st.sidebar.radio('Navigation contextuelle',choices,key=key,format_func=lambda value:label_by_key[value],label_visibility='collapsed')
    screen=next(x for x in screens if x.key==selection)
    if show_title:st.markdown(f"### {screen.title}")
    return selection


def _ui_incident(context, ex, *, action_id=None, entity_type=None, entity_id=None, subject='Cette fonction', level='error'):
    actor=st.session_state.get('admin_email') or st.session_state.get('trainer_portal_name') or 'utilisateur'
    ref=log_ui_exception(ENGINE,context,ex,action_id=action_id,actor=actor,entity_type=entity_type,entity_id=entity_id)
    getattr(st,level)(user_message(ref,subject=subject))
    return ref


def _run_ui_module(label, fn, *, action_id=None):
    try:
        return fn()
    except Exception as ex:
        if ex.__class__.__name__ in {'RerunException','StopException'}:
            raise
        _ui_incident(label,ex,action_id=action_id,subject='Ce module')
        return None


def privacy_notice_html(action_id=None):
    runtime=organization_runtime_config(ENGINE,action_id);org=runtime['organization'];name=org.get('name') or 'L’organisme'
    notice=org.get('privacy_notice') or "Les informations nécessaires à l'organisation de l'action et à la justification de sa réalisation sont traitées pour la gestion et la preuve de l'action."
    contact=org.get('privacy_contact') or org.get('general_email') or ''
    return f"<div style='font-size:0.9rem;background:#f6f8f8;padding:12px 14px;border-radius:10px;margin:8px 0'><b>Information sur vos données personnelles</b><br>{name} : {notice}{(' Pour exercer vos droits ou poser une question : <b>'+contact+'</b>.') if contact else ''}</div>"

def org_identity(action_id=None):
    runtime=organization_runtime_config(ENGINE,action_id);return runtime['organization']


def mail_cfg():
    try:
        return resolve_mail_config(dict(st.secrets))
    except Exception:
        return resolve_mail_config({})


def slot_start_offset_minutes(start_s,end_s):
    a=datetime.fromisoformat(f"2000-01-01T{start_s}")
    b=datetime.fromisoformat(f"2000-01-01T{end_s}")
    if b<=a:
        b+=__import__('datetime').timedelta(days=1)
    return -int((b-a).total_seconds()//60)


def friendly_mail_error(raw):
    if not raw:
        return ''
    txt=str(raw)
    low=txt.lower()
    if '535' in txt or 'authentication' in low or 'auth' in low:
        return "Authentification email refusée (ancienne configuration)."
    if 'timed out' in low or 'timeout' in low:
        return "Serveur email injoignable (délai dépassé)."
    if 'connection refused' in low:
        return "Connexion au serveur email refusée."
    if 'no recipient' in low:
        return "Adresse email destinataire absente."
    if 'unknown_delivery' in low or 'interrupted' in low:
        return "Envoi interrompu : vérification manuelle nécessaire avant renvoi."
    return "Erreur technique d’envoi. Le détail est conservé dans le journal administrateur."


def schedule_confirmation_html(action, participant, slots):
    org=org_identity(action.get('id')); org_name=org.get('name') or 'Organisme'
    rows=''.join(
        f"<tr><td style='padding:6px 10px;border-bottom:1px solid #ddd'>{datetime.fromisoformat(x['slot_date']).strftime('%d/%m/%Y')}</td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #ddd'>{x['start_time']}–{x['end_time']}</td></tr>"
        for x in slots
    )
    privacy=privacy_notice_html(action.get('id'))
    location=action.get('location') or 'Modalité / lieu à confirmer'
    return f"""<p>Bonjour {participant['first_name']},</p>
    <p>Nous vous confirmons le planning de votre action <strong>{action['title']}</strong> (n° {action['action_no']}).</p>
    <p><strong>Lieu / modalité :</strong> {location}</p>
    <table style='border-collapse:collapse'><thead><tr><th style='text-align:left;padding:6px 10px'>Date</th><th style='text-align:left;padding:6px 10px'>Horaire</th></tr></thead><tbody>{rows}</tbody></table>
    <p>Vous recevrez, pour chaque séance concernée par l’émargement électronique, votre lien personnel selon le paramétrage prévu.</p>
    {privacy}<p>{org_name}</p>"""


def send_schedule_confirmations(action_id, actor, participant_id=None):
    action=one(ENGINE,'SELECT * FROM actions WHERE id=:a',{'a':action_id})
    parts=q(ENGINE,'SELECT * FROM participants WHERE action_id=:a AND active=1 AND (:p IS NULL OR id=:p) ORDER BY last_name,first_name',{'a':action_id,'p':participant_id})
    slots=q(ENGINE,'SELECT * FROM slots WHERE action_id=:a ORDER BY slot_date,start_time',{'a':action_id})
    cfg=mail_cfg(); missing=validate_mail_config(cfg)
    if not cfg.get('enabled') or missing:
        return [],[(p.get('email') or f"{p['first_name']} {p['last_name']}", 'Configuration MAIL indisponible ou incomplète') for p in parts]
    org=org_identity(action_id); org_name=org.get('name') or 'Organisme'
    if org.get('email_from_name'): cfg['from_name']=org['email_from_name']
    if org.get('email_from_address'): cfg['from_email']=org['email_from_address']
    sent=[]; failed=[]
    for participant in parts:
        email=(participant.get('email') or '').strip()
        if not email:
            failed.append((f"{participant['first_name']} {participant['last_name']}",'Adresse email absente')); continue
        try:
            send_mail(cfg,email,f"{org_name} — Confirmation de votre planning — {action['action_no']}",schedule_confirmation_html(action,participant,slots))
            audit(ENGINE,'SCHEDULE_CONFIRMATION_SENT',action_id,actor,'participant',participant['id'],{'email':email,'slots':len(slots)})
            sent.append(email)
        except Exception as ex:
            audit(ENGINE,'SCHEDULE_CONFIRMATION_FAILED',action_id,actor,'participant',participant['id'],{'email':email,'error':str(ex)[:300]})
            failed.append((email,friendly_mail_error(ex)))
    return sent,failed



def send_planning_change_notifications(action_id, slot_id, actor):
    """I4 user-facing notification layer. Planning remains saved even if email is unavailable."""
    cfg=mail_cfg(); action=one(ENGINE,'SELECT * FROM actions WHERE id=:a',{'a':action_id})
    if not action:return [],['Action introuvable']
    if normalize_action_status(action.get('status')) in ('BROUILLON','PLANIFIEE'):
        ev=one(ENGINE,'SELECT id FROM planning_change_events WHERE action_id=:a AND slot_id=:s ORDER BY id DESC LIMIT 1',{'a':action_id,'s':slot_id}) if slot_id else None
        if ev: execute(ENGINE,"UPDATE planning_change_events SET notification_status='SKIPPED_DRAFT' WHERE id=:i",{'i':ev['id']})
        return [],[]
    sent,failed=send_schedule_confirmations(action_id,actor)
    slot=one(ENGINE,'SELECT * FROM slots WHERE id=:s',{'s':slot_id}) if slot_id else None
    org=org_identity(action_id); org_name=org.get('name') or 'Organisme'; trainer_sent=[]
    if cfg.get('enabled') and slot:
        for tr in list_slot_trainers(ENGINE,slot_id):
            email=(tr.get('email') or '').strip()
            if not email: continue
            body=f"""<p>Bonjour {tr['full_name']},</p><p>Le planning de l'action <strong>{action['action_no']} — {action['title']}</strong> a été modifié.</p>
            <p>Créneau concerné : <strong>{slot['slot_date']} — {slot['start_time']} à {slot['end_time']}</strong>.</p>
            <p><a href='{BASE_URL.rstrip('/')}?trainer_portal=1'>ACCÉDER À MON ESPACE INTERVENANT</a></p>{privacy_notice_html(action_id)}"""
            try:
                send_mail(cfg,email,f"{org_name} — Planning actualisé — {action['action_no']}",body)
                audit(ENGINE,'TRAINER_SCHEDULE_UPDATE_SENT',action_id,actor,'trainer',tr['trainer_id'],{'slot_id':slot_id,'email':email}); trainer_sent.append(email)
            except Exception as ex:
                audit(ENGINE,'TRAINER_SCHEDULE_UPDATE_FAILED',action_id,actor,'trainer',tr['trainer_id'],{'slot_id':slot_id,'email':email,'error':str(ex)[:300]})
                failed.append((email,friendly_mail_error(ex)))
    ev=one(ENGINE,'SELECT id FROM planning_change_events WHERE action_id=:a AND slot_id=:s ORDER BY id DESC LIMIT 1',{'a':action_id,'s':slot_id}) if slot_id else None
    if ev:
        execute(ENGINE,'UPDATE planning_change_events SET notification_status=:st WHERE id=:i',{'st':'SENT' if not failed else ('PARTIAL' if sent or trainer_sent else 'ERROR'),'i':ev['id']})
        from workspace_notifications import schedule_changed
        schedule_changed(ENGINE,action_id,slot_id,ev['id'])
    return sent+trainer_sent,failed


def send_participant_code_email(participant, action, pin):
    cfg=mail_cfg()
    if not participant.get('email') or not cfg.get('enabled'): return False, 'Email non envoyé (adresse ou configuration MAIL indisponible).'
    org=org_identity(action.get('id'));org_name=org.get('name') or 'Organisme'; subject=f"{org_name} — votre accès émargement — {action['action_no']}"
    body=f"""<p>Bonjour {participant['first_name']},</p><p>Vous êtes inscrit(e) à <strong>{action['title']}</strong>.</p><p>Votre code personnel pour l'émargement via QR code est : <strong style='font-size:20px'>{pin}</strong>.</p><p>Conservez ce code pendant l'action. Les liens personnels reçus par email permettent également d'émarger sans ressaisir ce code.</p>{privacy_notice_html(action.get('id'))}<p>{org_name}</p>"""
    try: send_mail(cfg,participant['email'],subject,body); return True,'Code envoyé par email.'
    except Exception as ex: return False,f'Envoi du code impossible : {friendly_mail_error(ex)}'


def sync_quality_schedule(action_id, actor):
    """Keep unsent quality deadlines aligned with the real calendar."""
    action=one(ENGINE,'SELECT * FROM actions WHERE id=:a',{'a':action_id})
    if not action:
        return
    try:
        if normalize_action_status(action.get('status')) in ('ACTIVE','A_CLOTURER') and (action.get('use_quality_hot') or action.get('use_quality_cold') or action.get('use_trainer_feedback')):
            prepare_quality_campaigns(ENGINE,action_id,BASE_URL,actor)
        else:
            reschedule_pending_quality_campaigns(ENGINE,action_id,actor)
    except ValueError:
        # During draft construction the calendar can temporarily be incomplete.
        pass

def activate_action_ui(a, location_key):
    """Single operational activation workflow, reusable from several tabs."""
    cover=action_mission_coverage(ENGINE,a['id'])
    if cover['mode']=='ENFORCE':
        if cover['ready']: st.success('Couverture des missions vérifiée pour cette action.')
        else:
            st.warning('Avant activation : '+ ' ; '.join(cover['issues']))
    else:
        st.caption('Action historique : contrôle des engagements en mode consultation. Le renforcer depuis Intervenants.')
    status=normalize_action_status(a.get('status'))
    if status not in ('BROUILLON','PLANIFIEE'):
        return False
    if st.button('✅ VALIDER LE PLANNING ET ACTIVER L’ACTION',type='primary',key=f'activate_{location_key}_{a["id"]}'):
        cfg=mail_cfg(); missing=validate_mail_config(cfg)
        if not cfg.get('enabled') or missing:
            st.error("Impossible d’activer les envois : la configuration MAIL n’est pas disponible ou est incomplète" + ((" ("+', '.join(missing)+")") if missing else '.'))
            return True
        ok_act,issues=activate_action(ENGINE,a['id'],st.session_state.admin_email)
        if not ok_act:
            st.error('Activation impossible : '+' ; '.join(issues))
            return True
        ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ)
        quality_created=[]
        try:
            if a.get('use_quality_hot') or a.get('use_quality_cold') or a.get('use_trainer_feedback'):
                quality_created=prepare_quality_campaigns(ENGINE,a['id'],BASE_URL,st.session_state.admin_email)
        except ValueError as ex:
            # Activation remains valid; quality setup is reported for correction.
            st.session_state['_action_flash']=(a['id'],'warning',f'Action activée. Qualité à vérifier : {ex}')
        slots_count=one(ENGINE,'SELECT COUNT(*) n FROM slots WHERE action_id=:a',{'a':a['id']})['n']
        sent=[];failed=[]
        if bool(a.get('use_attendance',1)) and slots_count:
            sent,failed=send_schedule_confirmations(a['id'],st.session_state.admin_email)
        if failed:
            msg='Action ACTIVÉE, mais certains emails de planning ont échoué : '+' ; '.join(f"{x}: {e}" for x,e in failed)
            st.session_state['_action_flash']=(a['id'],'warning',msg)
        elif sent:
            st.session_state['_action_flash']=(a['id'],'success',f'Action ACTIVÉE. Confirmation de planning envoyée à {len(sent)} participant(s).')
        else:
            st.session_state['_action_flash']=(a['id'],'success','Action ACTIVÉE. Les automatisations prévues sont maintenant opérationnelles.')
        rerun()
    return True

def send_trainer_invitation_email(trainer, token):
    cfg=mail_cfg()
    email=(trainer.get('email') or '').strip()
    if not email or not cfg.get('enabled'):
        return False, "Invitation non envoyée (email absent ou configuration MAIL indisponible)."
    org=org_identity(); org_name=(org or {}).get('name') or 'Organisme'
    if org and org.get('email_from_name'): cfg['from_name']=org['email_from_name']
    if org and org.get('email_from_address'): cfg['from_email']=org['email_from_address']
    url=f"{BASE_URL.rstrip('/')}?trainer_invite={quote(token)}"
    body=f"""<p>Bonjour {trainer['full_name']},</p>
    <p>Vous avez été référencé(e) comme formateur / accompagnant pour <strong>{org_name}</strong>.</p>
    <p>Pour créer votre accès personnel sécurisé, cliquez sur le bouton ci-dessous :</p>
    <p><a href='{url}' style='background:#008b8b;color:white;padding:12px 18px;text-decoration:none;border-radius:8px'>CRÉER MON ACCÈS INTERVENANT</a></p>
    <p>Votre espace vous permettra de consulter uniquement les actions qui vous sont affectées et d'accéder aux fonctions opérationnelles autorisées : planning, QR d'émargement, suivi, absences, relances et contresignature.</p>
    {privacy_notice_html()}<p>{org_name}</p>"""
    try:
        send_mail(cfg,email,f"{org_name} — Créez votre accès formateur / accompagnant",body)
        return True,'Invitation intervenant envoyée par email.'
    except Exception as ex:
        return False,f'Invitation non envoyée : {friendly_mail_error(ex)}'


def send_trainer_password_reset_email(trainer, token):
    cfg=mail_cfg(); email=(trainer.get('email') or '').strip()
    if not email or not cfg.get('enabled'): return False,'Email non envoyé (adresse ou configuration MAIL indisponible).'
    org=org_identity(); org_name=(org or {}).get('name') or 'Organisme'
    url=f"{BASE_URL.rstrip('/')}?trainer_reset={quote(token)}"
    body=f"""<p>Bonjour {trainer['full_name']},</p><p>Une demande de réinitialisation du mot de passe de votre espace intervenant {org_name} a été reçue.</p><p><a href='{url}' style='background:#008b8b;color:white;padding:12px 18px;text-decoration:none;border-radius:8px'>RÉINITIALISER MON MOT DE PASSE</a></p><p>Ce lien est temporaire. Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer ce message.</p>{privacy_notice_html()}"""
    try:
        send_mail(cfg,email,f"{org_name} — Réinitialisation de votre mot de passe intervenant",body); return True,'Email de réinitialisation envoyé.'
    except Exception as ex:
        return False,f'Email non envoyé : {friendly_mail_error(ex)}'


def send_beneficiary_invitation_email(beneficiary, token):
    email=(beneficiary.get('current_email') or beneficiary.get('portal_email') or '').strip()
    if not email: return False,'Adresse email personnelle absente.'
    org=org_identity(); link=f"{BASE_URL.rstrip('/')}?beneficiary_invite={quote(token)}"
    portal=f"{BASE_URL.rstrip('/')}?beneficiary_portal=1"
    body=f"""<p>Bonjour {beneficiary.get('first_name') or ''},</p><p>Votre espace personnel Clarté360 peut maintenant être activé.</p><p><a href='{link}'>ACTIVER MON ESPACE PERSONNEL</a></p><p><b>Ce lien d'activation est temporaire et ne sert qu'à créer votre accès.</b> Après activation, connectez-vous à tout moment depuis votre accès permanent :</p><p><a href='{portal}'>ACCÉDER À MON ESPACE BÉNÉFICIAIRE</a></p><p>Votre adresse email sert à la connexion mais ne constitue pas votre identité dans Clarté360.</p>{privacy_notice_html()}"""
    try:
        send_mail(mail_cfg(),email,f"{org.get('name') or 'Clarté360'} — activation de votre espace personnel",body)
        audit(ENGINE,'BENEFICIARY_PORTAL_INVITATION_EMAIL_SENT',actor=st.session_state.get('admin_email','system'),entity_type='beneficiary',entity_id=beneficiary.get('id'),details={'email':email})
        return True,'Invitation à l’espace bénéficiaire envoyée par email.'
    except Exception as ex:
        return False,f"Invitation créée mais email non envoyé : {friendly_mail_error(ex)}"

def trainer_reset_request_page():
    header('Clarté360 — Espace intervenant','Mot de passe oublié')
    with st.form('trainer_reset_request_form'):
        email=st.text_input('Votre adresse email').strip().lower()
        submit=st.form_submit_button('Recevoir un lien de réinitialisation',type='primary')
    if submit:
        tr,token=create_trainer_password_reset(ENGINE,email)
        if tr and token:
            ok,msg=send_trainer_password_reset_email(tr,token)
            audit(ENGINE,'TRAINER_PASSWORD_RESET_EMAIL_SENT' if ok else 'TRAINER_PASSWORD_RESET_EMAIL_FAILED',None,email,'trainer',tr['id'],{'message':msg})
        st.success("Si cette adresse correspond à un accès intervenant actif, un email de réinitialisation vient d'être envoyé.")
    st.link_button('Retour à la connexion',f"{BASE_URL.rstrip('/')}?trainer_portal=1")
    footer()

def trainer_reset_page(token):
    header('Clarté360 — Espace intervenant','Réinitialisation du mot de passe')
    tr=trainer_by_reset_token(ENGINE,token)
    if not tr:
        st.error('Ce lien est invalide, expiré ou a déjà été utilisé.')
        st.link_button('Demander un nouveau lien',f"{BASE_URL.rstrip('/')}?trainer_reset_request=1")
        footer(); return
    st.info(f"Accès de {tr['full_name']} — {tr.get('email') or ''}")
    with st.form('trainer_reset_form'):
        p1=st.text_input('Nouveau mot de passe',type='password')
        p2=st.text_input('Confirmez le nouveau mot de passe',type='password')
        submit=st.form_submit_button('Enregistrer le nouveau mot de passe',type='primary')
    if submit:
        if p1!=p2: st.error('Les deux mots de passe ne sont pas identiques.')
        else:
            ok,msg=complete_trainer_password_reset(ENGINE,token,p1)
            if ok:
                revoke_subject_sessions(ENGINE,'TRAINER',tr['id'])
                st.success('Votre mot de passe a été modifié. Vous pouvez maintenant vous connecter.')
                st.link_button('Se connecter',f"{BASE_URL.rstrip('/')}?trainer_portal=1")
            else: st.error(msg)
    footer()

def trainer_invitation_page(token):
    header('Clarté360 — Accès intervenant','Création de votre accès sécurisé')
    tr=trainer_by_invite(ENGINE,token)
    if not tr:
        st.error('Cette invitation est invalide ou a expiré. Demandez une nouvelle invitation à votre administrateur.')
        footer(); return
    st.info(f"Invitation pour {tr['full_name']} — {tr.get('email') or ''}")
    with st.form('trainer_accept_invite'):
        p1=st.text_input('Choisissez votre mot de passe',type='password')
        p2=st.text_input('Confirmez le mot de passe',type='password')
        ok=st.form_submit_button('CRÉER MON ACCÈS',type='primary')
    if ok:
        if p1!=p2: st.error('Les deux mots de passe ne correspondent pas.')
        else:
            done,msg=accept_trainer_invitation(ENGINE,token,p1)
            if done:
                st.success('Votre accès est créé. Vous pouvez maintenant vous connecter à votre espace intervenant.')
                st.link_button('Se connecter à mon espace intervenant',f"{BASE_URL.rstrip('/')}?trainer_portal=1")
            else: st.error(msg)
    footer()


def _trainer_actor(trainer):
    return f"trainer:{trainer.get('id')}:{trainer.get('email') or trainer.get('full_name') or ''}"

def _slot_label(sl):
    kind='' if (sl.get('slot_kind') or 'NORMAL')=='NORMAL' else f" — {sl.get('slot_kind')}"
    return f"{sl['slot_date']} — {sl['start_time']}–{sl['end_time']}{kind}"

def _trainer_slot_status_rows(action_id,slot_id):
    parts=q(ENGINE,'SELECT * FROM participants WHERE action_id=:a AND active=1 ORDER BY last_name,first_name',{'a':action_id})
    sigs={x['participant_id']:x for x in q(ENGINE,'SELECT * FROM signatures WHERE slot_id=:s',{'s':slot_id})}
    ats={x['participant_id']:x for x in q(ENGINE,'SELECT * FROM attendance_status WHERE slot_id=:s',{'s':slot_id})}
    rows=[]
    for p in parts:
        at=ats.get(p['id']); sig=sigs.get(p['id']); status='SIGNÉ' if sig else (at['status'] if at else 'EN ATTENTE')
        rows.append({'Participant':f"{p['last_name']} {p['first_name']}",'Statut':status,'Téléphone':p.get('phone') or '','Email':p.get('email') or ''})
    return parts,rows

def render_trainer_action(action, trainer):
    tid=trainer['id']; aid=action['id']; actor=_trainer_actor(trainer)
    data=trainer_action_dashboard(ENGINE,tid,aid,TZ)
    if not data:
        st.error("Cette action ne vous est pas affectée."); return
    a=data['action']; slots=data['slots']; parts=data['participants']; next_slot=data['next_slot']
    selected_section=_p3_sidebar_section('TRAINER',action_id=aid,action_no=a['action_no'])
    st.markdown(f"### {a['action_no']} — {a['title']}")
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Prestation',(a.get('prestation_type') or a.get('nature') or '—').replace('_',' '))
    c2.metric('Client',a.get('client_name') or '—')
    c3.markdown('**Modalité**'); c3.write(delivery_mode_label(a.get('delivery_mode')))  # J9: never truncate long labels in a metric
    c4.metric('Participants',len(parts))
    st.caption(f"Lieu / précision : {a.get('location') or 'Non renseigné'} · Période : {format_app_date(a.get('start_date'))} → {format_app_date(a.get('end_date'))} · Statut : {normalize_action_status(a.get('status'))}")
    if selected_section=='overview':
        if next_slot:
            st.success(f"Prochaine séance : {_slot_label(next_slot)}")
        elif slots:
            st.info('Aucune séance future : le calendrier affiché ci-dessous reprend les séances enregistrées.')
        else:
            st.warning('Aucun créneau n’est actuellement enregistré pour cette action.')

        # V3.1 corrective — synthèse opérationnelle des émargements pour l'intervenant.
        follow_rows=[]
        total_missing=total_absent=total_finalized=0
        for sl in slots:
            states=_slot_participant_states(ENGINE,sl['id'])
            missing=[x for x in states if x['status'] in ('EN_ATTENTE','PRESENT_REGULARISE')]
            absent=[x for x in states if x['status']=='ABSENT']
            signed=[x for x in states if x['status']=='SIGNE']
            cs_ok,cs_missing=required_slot_countersignatures_complete(ENGINE,sl['id'])
            total_missing += len(missing); total_absent += len(absent)
            finalized=(not missing and cs_ok)
            total_finalized += 1 if finalized else 0
            follow_rows.append({
                'Séance':f"{sl['slot_date']} — {sl['start_time']}–{sl['end_time']}",
                'Signatures bénéficiaires':f"{len(signed)}/{len(states)}" + (f" · {len(missing)} à régulariser" if missing else ' · complet'),
                'Absences signalées':len(absent),
                'Contresignature':'Validée' if cs_ok else f"{len(cs_missing)} attendue(s)",
                'État':'Finalisé' if finalized else 'À suivre'
            })
        if follow_rows:
            st.markdown('#### Suivi des émargements de cette action')
            m1,m2,m3,m4=st.columns(4)
            m1.metric('Signatures à régulariser',total_missing)
            m2.metric('Absences signalées',total_absent)
            m3.metric('Contresignatures à faire',sum(1 for r in follow_rows if r['Contresignature']!='Validée'))
            m4.metric('Créneaux finalisés',f"{total_finalized}/{len(follow_rows)}")
            st.dataframe(pd.DataFrame(follow_rows),use_container_width=True,hide_index=True)

        # H2 — visibilité immédiate de l'activation des espaces bénéficiaires avant la première séance.
        ben_rows=[]
        for p in parts:
            if p.get('beneficiary_id'):
                binfo=one(ENGINE,'SELECT id,public_id,first_name,last_name FROM beneficiaries WHERE id=:b',{'b':p['beneficiary_id']})
                ps=beneficiary_portal_status(ENGINE,p['beneficiary_id'])
                ben_rows.append({'Bénéficiaire':f"{(binfo or {}).get('last_name') or p.get('last_name','')} {(binfo or {}).get('first_name') or p.get('first_name','')}".strip(),
                                 'Espace personnel':ps['label'],
                                 'Dernière connexion':(ps.get('last_login_at') or '').replace('T',' ')[:16] or '—'})
            else:
                ben_rows.append({'Bénéficiaire':f"{p.get('last_name','')} {p.get('first_name','')}".strip(),'Espace personnel':'Non rattaché à une identité permanente','Dernière connexion':'—'})
        if ben_rows:
            st.markdown('#### Accès bénéficiaire avant séance')
            st.dataframe(pd.DataFrame(ben_rows),use_container_width=True,hide_index=True)

    # P3: single section rendered, no horizontal action tabs.
    # The contextual selection is initialized above this overview.

    if selected_section=='planning':
        if slots:
            cal=[]
            for sl in slots:
                signed=one(ENGINE,"SELECT COUNT(*) n FROM signatures WHERE slot_id=:s AND status='VALIDE'",{'s':sl['id']})['n']
                absent=one(ENGINE,"SELECT COUNT(*) n FROM attendance_status WHERE slot_id=:s AND status='ABSENT'",{'s':sl['id']})['n']
                cs_ok,cs_missing=required_slot_countersignatures_complete(ENGINE,sl['id'])
                cal.append({'Date':format_app_date(sl['slot_date']),'Début':format_app_time(sl['start_time']),'Fin':format_app_time(sl['end_time']),'Type':sl.get('slot_kind') or 'NORMAL','Signés':signed,'Absents':absent,'Contresigné':'Oui' if cs_ok else ('Manque '+str(len(cs_missing)))})
            st.dataframe(pd.DataFrame(cal),use_container_width=True,hide_index=True)
            ics=action_calendar_ics(ENGINE,aid,trainer_id=tid)
            if ics:
                st.download_button('📅 Ajouter / actualiser mes séances dans mon agenda (ICS)',ics,file_name=f"{a['action_no']}_planning_intervenant.ics",mime='text/calendar',key=f'tr_ics_{aid}')
        else: st.info('Aucun créneau.')

        scope=trainer_planning_scope(ENGINE,tid,aid)
        editable=[x for x in slots if scope['can_manage_action'] or x['id'] in scope['slot_ids']]
        if scope['can_manage_action'] or editable:
            st.markdown('#### Gérer le planning')
            if scope['can_manage_action']:
                st.success("Vous êtes autorisé à gérer le planning de cette action. Les garde-fous contractuels et les preuves historiques restent prioritaires.")
            else:
                st.info("Vous pouvez modifier uniquement les créneaux explicitement autorisés par l'administration.")
            if editable:
                emap={_slot_label(x):x for x in editable}; elab=st.selectbox('Créneau à déplacer',list(emap),key=f'tr_plan_edit_{aid}'); es=emap[elab]
                with st.form(f'tr_plan_edit_form_{es["id"]}'):
                    c1,c2,c3=st.columns(3)
                    nd=c1.date_input('Nouvelle date',value=date.fromisoformat(es['slot_date']),format=app_date_input_format())
                    ns=c2.time_input('Nouveau début',value=dt_time.fromisoformat(es['start_time']))
                    ne=c3.time_input('Nouvelle fin',value=dt_time.fromisoformat(es['end_time']))
                    save_plan=st.form_submit_button('Enregistrer ce déplacement',type='primary')
                if save_plan:
                    ok,msg=trainer_update_slot(ENGINE,tid,es['id'],nd.isoformat(),ns.strftime('%H:%M'),ne.strftime('%H:%M'),actor,base_url=BASE_URL)
                    if ok:
                        sent,failed=send_planning_change_notifications(aid,es['id'],actor)
                        if failed: st.warning('Planning enregistré. Certaines notifications email n’ont pas pu être envoyées.')
                        else: st.success('Planning enregistré et synchronisé.'); rerun()
                    else: st.error(msg)

                with st.expander('📅 Reporter ce créneau'):
                    c1,c2,c3=st.columns(3)
                    rd=c1.date_input('Date du report',value=date.fromisoformat(es['slot_date']),key=f'tr_rep_d_{es["id"]}',format=app_date_input_format())
                    rs=c2.time_input('Début du report',value=dt_time.fromisoformat(es['start_time']),key=f'tr_rep_s_{es["id"]}')
                    re_=c3.time_input('Fin du report',value=dt_time.fromisoformat(es['end_time']),key=f'tr_rep_e_{es["id"]}')
                    reason=st.text_input('Motif du report',key=f'tr_rep_reason_{es["id"]}')
                    if st.button('Reporter cette séance',key=f'tr_rep_btn_{es["id"]}'):
                        nsid,msg=trainer_report_slot(ENGINE,tid,es['id'],rd.isoformat(),rs.strftime('%H:%M'),re_.strftime('%H:%M'),actor,reason or 'Report intervenant',base_url=BASE_URL)
                        if nsid:
                            sent,failed=send_planning_change_notifications(aid,nsid,actor)
                            if failed: st.warning('Report enregistré. Certaines notifications email n’ont pas pu être envoyées.')
                            else: st.success('Report enregistré et synchronisé.'); rerun()
                        else: st.error(msg)
            if scope['can_manage_action']:
                with st.expander('➕ Ajouter une séance'):
                    with st.form(f'tr_plan_add_{aid}'):
                        c1,c2,c3=st.columns(3)
                        ad=c1.date_input('Date',value=date.today(),key=f'tr_add_d_{aid}',format=app_date_input_format())
                        ast=c2.time_input('Début',value=dt_time(9,0),key=f'tr_add_s_{aid}')
                        aet=c3.time_input('Fin',value=dt_time(10,30),key=f'tr_add_e_{aid}')
                        add_plan=st.form_submit_button('Ajouter cette séance')
                    if add_plan:
                        nsid,msg=trainer_add_slot(ENGINE,tid,aid,ad.isoformat(),ast.strftime('%H:%M'),aet.strftime('%H:%M'),actor,base_url=BASE_URL)
                        if nsid:
                            sent,failed=send_planning_change_notifications(aid,nsid,actor)
                            if failed: st.warning('Séance ajoutée. Certaines notifications email n’ont pas pu être envoyées.')
                            else: st.success('Séance ajoutée et synchronisée.'); rerun()
                        else: st.error(msg)
        else:
            st.caption("Le planning est en lecture seule. L'administration peut vous accorder un droit de gestion sur l'action ou sur certains créneaux.")
    if selected_section=='teams':
        if not action_module_enabled(ENGINE,aid,'TEAMS'):
            st.info('Le module Teams n’est pas activé pour cette action.')
        else:
            room=teams_room(ENGINE,aid)
            if room and room.get('join_web_url'):
                st.success('Réunion Teams disponible.')
                st.link_button('REJOINDRE LA RÉUNION TEAMS',room['join_web_url'],type='primary')
                nxt=teams_next_meeting(ENGINE,aid)
                if nxt: st.caption(f"Prochaine réunion Teams : {nxt.get('slot_date')} — {nxt.get('start_time')}–{nxt.get('end_time')}")
            else:
                st.info('Création/synchronisation Teams en cours. Aucune action n’est nécessaire.')
            troles=[r for r in teams_roles(ENGINE,aid) if r.get('trainer_id')==tid and r.get('active')]
            if troles:
                slots_by_id={x['id']:x for x in q(ENGINE,'SELECT * FROM slots WHERE action_id=:a',{'a':aid})}
                rows=[]
                for r in troles:
                    sl=slots_by_id.get(r.get('slot_id')) or {}
                    rows.append({'Séance':f"{sl.get('slot_date','—')} — {sl.get('start_time','—')}–{sl.get('end_time','—')}", 'Rôle Teams':'Coorganisateur' if str(r.get('role')).upper()=='COORGANIZER' else 'Présentateur'})
                st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
            evidence=teams_occurrence_evidence(ENGINE,aid)
            st.markdown('#### Réunions réellement constatées')
            has_report=False
            for ev in evidence:
                rep=ev.get('report'); conns=ev.get('connections') or []
                if not rep:
                    st.caption(f"{ev.get('slot_date')} — {ev.get('start_time')}–{ev.get('end_time')} : rapport Microsoft non encore récupéré.")
                    continue
                has_report=True
                st.success(f"{ev.get('slot_date')} — {ev.get('start_time')}–{ev.get('end_time')} : réunion Teams constatée · {len(conns)} connexion(s).")
                st.dataframe(pd.DataFrame([{'Identité / pseudo Teams':r.get('display_name') or '—','Email':r.get('email') or '—','Entrée':(r.get('join_time_utc') or '')[11:19] or '—','Sortie':(r.get('leave_time_utc') or '')[11:19] or '—','Durée':_duration_hms(r.get('duration_seconds')),'Rapprochement':(f"{r.get('participant_first_name','')} {r.get('participant_last_name','')}".strip() if r.get('participant_id') else 'Non rapproché')} for r in conns]),use_container_width=True,hide_index=True)
            if has_report:
                st.download_button('🖨️ Imprimer les preuves Teams de cette action',teams_evidence_pdf(ENGINE,aid,technical=False),file_name=f"{a['action_no']}_preuves_Teams.pdf",mime='application/pdf',key=f'tr_teams_pdf_{aid}')
    if selected_section=='signatures':
        if not slots:
            st.info('Aucun créneau à gérer.')
        else:
            smap={_slot_label(x):x for x in slots}; smap_labels=list(smap)
            requested_slot=st.query_params.get('slot_id')
            try: requested_slot=int(requested_slot) if requested_slot is not None else None
            except Exception: requested_slot=None
            sidx=next((i for i,k in enumerate(smap_labels) if smap[k]['id']==requested_slot),0)
            sl=smap[st.selectbox('Créneau à gérer',smap_labels,index=sidx,key=f'tr_slot_{aid}') ]
            qr=qrcode.make(public_slot_url(sl,BASE_URL)); buf=io.BytesIO(); qr.save(buf,format='PNG')
            c1,c2=st.columns([1,2]); c1.image(buf.getvalue(),width=220); c2.markdown('**QR d’émargement**'); c2.caption('Vous pouvez présenter ce QR code aux participants. Le code personnel reste nécessaire sur la page QR.')
            parts2,rows=_trainer_slot_status_rows(aid,sl['id']); st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
            if parts2:
                pmap={f"{p['last_name']} {p['first_name']}":p for p in parts2}; pp=pmap[st.selectbox('Participant à gérer',list(pmap),key=f'tr_part_{aid}_{sl["id"]}') ]
                sig_now=one(ENGINE,"SELECT id,signed_at FROM signatures WHERE participant_id=:p AND slot_id=:s AND status='VALIDE'",{'p':pp['id'],'s':sl['id']})
                if sig_now:
                    st.success('Signature déjà enregistrée pour ce participant sur ce créneau. Aucune relance ni changement de présence n’est nécessaire.')
                else:
                    st.markdown('**Participant sans signature : était-il présent ?**')
                    c1,c2=st.columns(2)
                    if c1.button('OUI — PRÉSENT, À RÉGULARISER',key=f'tr_present_{aid}_{sl["id"]}_{pp["id"]}',use_container_width=True):
                        ok,msg=set_attendance_status(ENGINE,pp['id'],sl['id'],'PRESENT_REGULARISE','Présence attestée par intervenant — signature bénéficiaire à régulariser',actor)
                        if ok: st.success('Présence attestée. La signature bénéficiaire reste à régulariser.'); rerun()
                        else: st.error(msg)
                    if c2.button('NON — ABSENT',key=f'tr_abs_{aid}_{sl["id"]}_{pp["id"]}',use_container_width=True):
                        ok,msg=set_attendance_status(ENGINE,pp['id'],sl['id'],'ABSENT','Déclaré absent par intervenant',actor)
                        if ok: st.success('Absence enregistrée.'); rerun()
                        else: st.error(msg)
                    contact=[]
                    if pp.get('phone'): contact.append(f"📞 {pp['phone']}")
                    if pp.get('email'): contact.append(f"✉️ {pp['email']}")
                    if contact: st.caption('Contact : '+' · '.join(contact))
                    if pp.get('phone'): st.link_button('📞 APPELER LE PARTICIPANT',f"tel:{pp['phone']}",use_container_width=True)
                    if st.button('✉️ RELANCER LA SIGNATURE PAR EMAIL',key=f'tr_rem_{aid}_{sl["id"]}_{pp["id"]}',disabled=not bool(pp.get('email')),use_container_width=True):
                        ensure_tokens_and_events(ENGINE,aid,BASE_URL,TZ); url=token_url(ENGINE,pp['id'],sl['id'],BASE_URL); cfg=mail_cfg(); org=org_identity(aid)
                        body=f"<p>Bonjour {pp['first_name']},</p><p>Merci de régulariser votre émargement pour le {sl['slot_date']} de {sl['start_time']} à {sl['end_time']}.</p><p><a href='{url}'>SIGNER / RÉGULARISER</a></p>{privacy_notice_html(aid)}"
                        try:
                            send_mail(cfg,pp['email'],f"{org.get('name') or 'Organisme'} — émargement — {a['action_no']}",body); audit(ENGINE,'TRAINER_MANUAL_REMINDER',aid,actor,'participant',pp['id'],{'slot_id':sl['id']}); st.success('Relance envoyée.')
                        except Exception as ex: st.error(f'Envoi impossible : {friendly_mail_error(ex)}')
            st.markdown('#### Contresignature du créneau')
            existing=list_slot_countersignatures(ENGINE,sl['id'])
            for cs in existing:
                st.success(f"Contresigné par {cs['trainer_name']} le {local_dt(cs['signed_at'],TZ).strftime('%d/%m/%Y à %H:%M')} — preuve {cs.get('method') or 'historique'}")
            mine=next((x for x in existing if x.get('trainer_id')==trainer['id']),None)
            eligible,why,_=slot_countersignature_eligibility(ENGINE,sl['id'],trainer_id=trainer['id'])
            if mine:
                st.info('Votre contresignature est enregistrée et constitue une preuve historique non modifiable.')
            else:
                if not eligible: st.warning(why)
                st.markdown('##### Mode de signature')
                tr_mode=st.radio('Mode de signature',['Signature manuscrite','Nom et prénom + certification'],horizontal=True,key=f'tr_mode_{aid}_{sl["id"]}')
                tr_canvas=None; typed_name=trainer['full_name']
                if tr_mode=='Signature manuscrite':
                    st.caption('Signez dans le cadre avec votre doigt, votre stylet ou votre souris.')
                    st.info('Signez dans le cadre gris ci-dessous avec la souris, le doigt ou un stylet.')
                    tr_canvas=st_canvas(fill_color='rgba(255,255,255,0)',stroke_width=4,stroke_color='#0F172A',background_color='#EEF2F3',height=190,width=520,drawing_mode='freedraw',display_toolbar=True,update_streamlit=True,key=f'tr_csig_rc4_{aid}_{sl["id"]}_{trainer["id"]}')
                else:
                    typed_name=st.text_input('Nom et prénom',value=trainer['full_name'],key=f'tr_typed_{aid}_{sl["id"]}')
                    st.caption('La saisie du nom et la certification ci-dessous constituent la preuve de contresignature numérique.')
                cert=st.checkbox("Je certifie l'exactitude des présences et absences indiquées pour ce créneau.",key=f'tr_cert_{aid}_{sl["id"]}')
                if st.button('CONTRESIGNER CE CRÉNEAU',type='primary',key=f'tr_sign_{aid}_{sl["id"]}',disabled=not eligible):
                    if not cert: st.error('La certification est obligatoire.')
                    elif tr_mode=='Nom et prénom + certification' and not typed_name.strip(): st.error('Nom et prénom obligatoires.')
                    elif tr_mode=='Signature manuscrite' and (tr_canvas is None or not signature_trace_is_valid(tr_canvas.image_data)): st.error('La signature semble vide ou trop courte. Merci d’apposer une signature manuscrite complète dans le cadre.')
                    else:
                        sig_bytes=None
                        if tr_mode=='Signature manuscrite':
                            img=PILImage.fromarray(tr_canvas.image_data.astype('uint8'),'RGBA').convert('RGB');buf=io.BytesIO();img.save(buf,format='PNG');sig_bytes=buf.getvalue()
                        ip,ua=request_technical_context()
                        ok,msg=countersign_slot(ENGINE,sl['id'],typed_name.strip(),trainer.get('email'),actor,"Je certifie l'exactitude des présences et absences indiquées pour ce créneau.",trainer_id=trainer['id'],signature_bytes=sig_bytes,ip_address=ip,user_agent=ua)
                        if ok: st.success('Contresignature enregistrée.'); rerun()
                        else: st.error(msg)
    if selected_section=='access':
        st.caption("Accès limité aux participants de cette action. Toute consultation, tout renvoi et toute régénération sont journalisés.")
        if not parts: st.info('Aucun participant.')
        else:
            pmap={f"{p['last_name']} {p['first_name']}":p for p in parts}; pp=pmap[st.selectbox('Participant',list(pmap),key=f'code_part_{aid}') ]
            state_key=f'_trainer_pin_{aid}_{pp["id"]}'
            c1,c2=st.columns(2)
            if c1.button('Afficher le code personnel existant',key=f'view_pin_{aid}_{pp["id"]}',use_container_width=True):
                pin=participant_pin_for_authorized_display(ENGINE,pp['id'],actor,aid); st.session_state[state_key]=pin or ''
            pin=st.session_state.get(state_key)
            if pin:
                st.code(pin,language=None); st.caption('Ce code est une donnée d’accès : communiquez-le uniquement au participant concerné.')
                if c2.button('Renvoyer ce code par email',key=f'send_pin_{aid}_{pp["id"]}',disabled=not bool(pp.get('email')),use_container_width=True):
                    ok,msg=send_participant_code_email(pp,a,pin); audit(ENGINE,'TRAINER_PARTICIPANT_PIN_EMAIL_SENT' if ok else 'TRAINER_PARTICIPANT_PIN_EMAIL_FAILED',aid,actor,'participant',pp['id'],{'message':msg});
                    if ok: st.success(msg)
                    else: st.warning(msg)
            elif pin=='':
                st.warning("Le code historique n'est pas récupérable dans cette version de la base. Générez volontairement un nouveau code pour permettre son affichage futur.")
            confirm=st.checkbox("Je confirme vouloir générer un NOUVEAU code et invalider l'ancien.",key=f'pin_reset_confirm_{aid}_{pp["id"]}')
            if st.button('Générer un nouveau code',key=f'pin_reset_{aid}_{pp["id"]}',disabled=not confirm):
                newpin=reset_participant_pin(ENGINE,pp['id'],actor); st.session_state[state_key]=newpin; st.success('Nouveau code généré. L’ancien code est désormais invalide.'); rerun()
    if selected_section=='documents':
        # J4 common inbox appears at top of this space, not inside every rubric.
        docs=list_trainer_documents(ENGINE,tid,aid)
        if docs:
            for d in docs:
                path=Path(d['storage_path'])
                if path.is_file():
                    data=read_document_for_actor(ENGINE,d['id'],'TRAINER',tid,action_id=aid)
                    st.download_button(d['display_name'],data,file_name=d['display_name'],key=f"tr_doc_dl_{d['id']}")
        else: st.info('Aucun document mis à disposition pour cette action.')
        if trainer.get('can_upload_documents'):
            st.markdown('#### Déposer un document pour tous les bénéficiaires de cette action')
            updoc=st.file_uploader('Document',type=['pdf','json','doc','docx','xls','xlsx','ppt','pptx','txt','csv','jpg','jpeg','png','webp','zip'],key=f'tr_course_doc_{aid}')
            if st.button('Déposer dans Documents de cours',key=f'tr_course_doc_btn_{aid}',disabled=updoc is None):
                try:
                    progress=st.progress(0,text='Traitement du fichier après transfert par le navigateur...')
                    rid,h,dedup=store_document_for_actor(ENGINE,'TRAINER',tid,updoc.getvalue(),updoc.name,aid,category='COURS',
                        progress_callback=lambda label,ratio: progress.progress(int(ratio*100),text=label))
                    st.success('Document déposé. '+('Le contenu existait déjà : aucune seconde copie physique n’a été créée.' if dedup else 'Nouveau fichier physique enregistré.'));rerun()
                except Exception as ex: _ui_incident('operation_interface',ex)
        else: st.caption("Le dépôt de documents n'est pas autorisé pour votre compte. L'administrateur peut activer ce droit.")
        if docs:
            zdoc=export_action_documents_zip(ENGINE,aid,'TRAINER',tid)
            st.download_button('Télécharger les documents autorisés de cette action (ZIP)',zdoc,
                file_name=f'documents_action_{aid}_intervenant.zip',mime='application/zip',key=f'tr_doc_zip_{aid}')
    if selected_section=='tools':
        if not trainer_can_prescribe_tools(ENGINE,tid,aid):
            st.info("La prescription d'outils Clarté360 n'est pas activée pour vous sur cette action.")
        else:
            st.success("Vous êtes autorisé à prescrire les outils du catalogue global Clarté360 aux bénéficiaires rattachés à cette action.")
            linked=q(ENGINE,"""SELECT p.id participant_id,b.id beneficiary_id,b.public_id,b.first_name,b.last_name
              FROM participants p JOIN beneficiaries b ON b.id=p.beneficiary_id
              WHERE p.action_id=:a AND p.active=1 AND b.active=1 ORDER BY b.last_name,b.first_name""",{'a':aid})
            tools=action_allowed_tools(ENGINE,aid)
            if not linked: st.warning('Les outils sont disponibles, mais aucun participant de cette action n’est encore rattaché à une identité bénéficiaire permanente. L’administrateur doit effectuer ce rattachement avant toute prescription.')
            elif not tools: st.warning("Aucun outil n'a été autorisé par l'administrateur pour cette action.")
            else:
                bmap={f"{x['last_name']} {x['first_name']} — {x['public_id']}":x for x in linked}
                tmap={f"{x['name']} — {x.get('tool_version') or 'version non précisée'}":x for x in tools}
                with st.form(f'tr_tool_prescribe_{aid}'):
                    bl=st.selectbox('Bénéficiaire',list(bmap)); tl=st.selectbox('Outil',list(tmap)); due=st.date_input('Échéance indicative',value=None,format=app_date_input_format())
                    submit_tool=st.form_submit_button('PRESCRIRE CET OUTIL',type='primary')
                if submit_tool:
                    bx=bmap[bl]; tx=tmap[tl]
                    try:
                        pr=create_tool_prescription(ENGINE,tx['tool_code'],bx['beneficiary_id'],aid,bx['participant_id'],prescriber_type='TRAINER',prescriber_id=tid,prescriber_role='INTERVENANT',due_at=due.isoformat() if due else None,actor=actor)
                        st.success(f"Prescription créée : {pr['prescription_id']}"); rerun()
                    except ValueError as ex: st.error(str(ex))
            hist=[x for x in list_tool_prescriptions(ENGINE,action_id=aid,trainer_id=tid) if x.get('status')!='ANNULE']
            if hist:
                st.dataframe(pd.DataFrame([{'Bénéficiaire':f"{x['beneficiary_last_name']} {x['beneficiary_first_name']}",'Outil':x['tool_name'],'Créateur':'Moi' if (x.get('prescriber_type')=='TRAINER' and str(x.get('prescriber_id'))==str(tid)) else 'Autre utilisateur','Créée':format_app_datetime(x['created_at']),'Échéance':format_app_deadline(x.get('due_at')),'Statut':x['status'].replace('_',' ')} for x in hist]),use_container_width=True,hide_index=True)
                hmap={f"{x['beneficiary_last_name']} {x['beneficiary_first_name']} — {x['tool_name']} — {x['prescription_id']}":x for x in hist}
                hh=hmap[st.selectbox('Prescription existante',list(hmap),key=f'tr_tool_existing_{aid}')]
                # J6 - follow-up allowed for an action-authorized trainer even if another user created it.
                choices=trainer_tool_followup_choices(ENGINE,tid,hh['prescription_id'])
                if choices:
                    choice=st.selectbox('Suivi pédagogique de cette prescription',choices,
                        format_func=lambda value:value.replace('_',' ').capitalize(),
                        key=f'j6_followup_{hh["id"]}')
                    if st.button('Enregistrer mon suivi',key=f'j6_followup_save_{hh["id"]}'):
                        try:
                            trainer_update_tool_followup(ENGINE,tid,hh['prescription_id'],choice,actor)
                            st.success('Suivi pédagogique enregistré, avec historique.');rerun()
                        except (PermissionError,ValueError) as ex:st.warning(str(ex))
                else:
                    st.caption('Suivi manuel indisponible : droits, état final ou connecteur protégé.')
                owns=(hh.get('prescriber_type')=='TRAINER' and str(hh.get('prescriber_id'))==str(tid))
                if st.button('SUPPRIMER MA PRESCRIPTION',key=f'tr_tool_cancel_{hh["id"]}',
                    disabled=not owns or hh.get('status') in ('TERMINE','REVU_EN_SEANCE')):
                    ok,msg=cancel_tool_prescription_owned(ENGINE,hh['prescription_id'],'TRAINER',tid,actor)
                    if ok: st.success('Prescription supprimée de votre liste active et conservée dans la piste d’audit.');rerun()
                    else: st.warning(msg)
                if not owns: st.caption('Cette prescription a été créée par un autre utilisateur : vous ne pouvez pas la supprimer.')

    if selected_section=='quality':
        camp=one(ENGINE,"""SELECT qc.*,qt.title questionnaire_title FROM quality_campaigns qc JOIN questionnaire_templates qt ON qt.id=qc.template_id
          WHERE qc.action_id=:a AND qc.trainer_id=:t AND qc.campaign_kind='TRAINER' ORDER BY qc.id DESC LIMIT 1""",{'a':aid,'t':tid})
        if not a.get('use_trainer_feedback'):
            st.info("Le questionnaire qualité intervenant n'est pas activé pour cette action.")
        elif not camp:
            st.info("Le questionnaire est activé mais n'a pas encore été généré. Il sera créé selon le calendrier qualité de l'action.")
        elif camp.get('status')=='COMPLETED':
            st.success('Votre questionnaire intervenant a été complété.')
            with st.expander('VOIR MES RÉPONSES',expanded=False):
                ans=q(ENGINE,"""SELECT qq.question_text,r.response_type,r.answer_json FROM quality_responses r
                  JOIN questionnaire_questions qq ON qq.id=r.question_id WHERE r.campaign_id=:c ORDER BY qq.position,qq.id""",{'c':camp['id']})
                view=[]
                for x in ans:
                    try: val=json.loads(x.get('answer_json') or 'null')
                    except Exception: val=x.get('answer_json')
                    view.append({'Question':x['question_text'],'Réponse':val})
                if view: st.dataframe(pd.DataFrame(view),use_container_width=True,hide_index=True)
            # J3: only beneficiary HOT/COLD results, never TRAINER/NPS as a /5 average.
            bstats=quality_question_stats(ENGINE,action_id=aid,campaign_kinds=('HOT','COLD'))
            bcamps=q(ENGINE,"SELECT campaign_kind,status FROM quality_campaigns WHERE action_id=:a AND campaign_kind IN ('HOT','COLD')",{'a':aid})
            completed=sum(1 for x in bcamps if x['status']=='COMPLETED')
            if bcamps:
                st.markdown('#### Résultats des bénéficiaires de cette action')
                total_notes=sum(x['Notes valides 1-5'] for x in bstats)
                total_score=sum(x['_sum_1_5'] for x in bstats)
                c1,c2=st.columns(2)
                c1.metric('Moyenne des réponses',f"{total_score/total_notes:.2f}/5" if total_notes else '—')
                c2.metric('Questionnaires reçus',f"{completed}/{len(bcamps)}")
                if bstats:
                    st.dataframe(pd.DataFrame([{'Thème':x['Rubrique'],'Question':x['Question'],'Réponses':x['Réponses'],'Moyenne':x['Moyenne'] if x['Moyenne'] is not None else '—'} for x in bstats]),use_container_width=True,hide_index=True)
        else:
            st.info(f"Questionnaire disponible : {camp.get('questionnaire_title') or 'Retour intervenant'}")
            st.link_button('OUVRIR LE QUESTIONNAIRE',quality_token_url(camp['token'],BASE_URL),type='primary')
    if selected_section=='reports':
        st.caption("Vous pouvez transmettre une observation, une difficulté, un incident, un problème logistique ou une demande de contact à l'administration.")
        with st.form(f'tr_report_{aid}',clear_on_submit=True):
            rt=st.selectbox('Nature',['Observation','Difficulté','Incident','Problème logistique','Besoin de contact','Autre'])
            subject=st.text_input('Objet *'); desc=st.text_area('Description *',height=150)
            st.caption('Ce signalement sera automatiquement intégré au suivi qualité, avec la nature sélectionnée ci-dessus.')
            up=_j4_report_file_uploader('Joindre éventuellement un document (10 Mo max)',types=['pdf','docx','xlsx','png','jpg','jpeg','txt'],key=f'tr_report_file_{aid}')
            submit=st.form_submit_button('TRANSMETTRE À L’ADMINISTRATION',type='primary')
        if submit:
            if not subject.strip() or not desc.strip(): st.error('Objet et description sont obligatoires.')
            elif up is not None and up.size>10*1024*1024: st.error('Le fichier dépasse 10 Mo.')
            else:
                ap=an=None
                if up is not None:
                    safe=re.sub(r'[^A-Za-z0-9._-]+','_',up.name)[:120]; an=up.name; ap=str(TRAINER_REPORT_DIR/f"{aid}_{tid}_{int(datetime.now().timestamp())}_{safe}"); Path(ap).write_bytes(up.getvalue())
                rid=create_trainer_report(ENGINE,aid,tid,rt,subject.strip(),desc.strip(),True,ap,an)
                if rid: st.success('Votre message a été transmis à l’administration et journalisé.')
                else: st.error('Transmission impossible : action non autorisée.')
        history=trainer_reports(ENGINE,aid,tid)
        if history:
            _j4_portal_threads('TRAINER',tid,history)
            st.markdown('#### Mes transmissions récentes')
            st.dataframe(pd.DataFrame([{'Date':format_app_datetime(x['created_at']),'Nature':x['report_type'],'Objet':x['subject'],'Statut':x['status'].replace('_',' '),'Réponse administration':x.get('admin_response') or ''} for x in history]),use_container_width=True,hide_index=True)

def trainer_portal_page():
    _restore_trainer_session()
    if not st.session_state.get('trainer_portal_id'):
        header('Clarté360 — Espace intervenant','Accès réservé aux intervenants')
        with st.form('trainer_login'):
            email=st.text_input('Email').strip().lower(); pw=st.text_input('Mot de passe',type='password'); ok=st.form_submit_button('Se connecter',type='primary')
        if ok:
            tr=verify_trainer_login(ENGINE,email,pw)
            if tr:
                st.session_state.trainer_portal_id=tr['id']; st.session_state.trainer_portal_name=tr['full_name']; _issue_persistent_session('TRAINER',tr['id'],tr.get('email') or tr['full_name'])
            else: st.error('Identifiants intervenant incorrects ou accès non encore créé.')
        st.link_button('Mot de passe oublié ?',f"{BASE_URL.rstrip('/')}?trainer_reset_request=1")
        footer(); return
    tid=st.session_state.trainer_portal_id
    tr=one(ENGINE,'SELECT * FROM trainers WHERE id=:i AND active=1',{'i':tid})
    if not tr:
        st.session_state.pop('trainer_portal_id',None); st.session_state.pop('trainer_portal_name',None); rerun()
    header('Clarté360 — Espace intervenant',f"Bienvenue {tr['full_name']}")
    _j4_notification_drawer('TRAINER',tid)
    top1,top2=st.columns([4,1])
    top1.caption('Espace personnel sécurisé : seules vos missions et vos données autorisées sont accessibles.')
    if top2.button('Se déconnecter',use_container_width=True):
        _logout_persistent('TRAINER',['trainer_portal_id','trainer_portal_name'])
    acts=trainer_actions(ENGINE,tid)
    if not acts:
        st.info('Aucune action ne vous est actuellement affectée. Votre dossier personnel reste accessible.')
    # J6 - the personal dashboard and the current action are distinct views.
    # A J4 notification forces the relevant action view, with its authorization checked below.
    pending_notice=st.session_state.get('j4_trainer_action')
    if pending_notice is not None:
        st.session_state['_j6_next_trainer_view']='Mes interventions'
    next_view=st.session_state.pop('_j6_next_trainer_view',None)
    if next_view:st.session_state['j6_trainer_view']=next_view
    views=('Accueil personnel','Mon dossier professionnel','Mes missions','Mes interventions','Mes échanges')
    if st.session_state.get('j6_trainer_view') not in views:
        st.session_state['j6_trainer_view']='Accueil personnel'
    st.sidebar.markdown('### Mon espace personnel')
    selected_view=st.sidebar.radio('Choisir mon espace',views,key='j6_trainer_view')
    if selected_view=='Mon dossier professionnel':
        st.markdown('### Mon dossier professionnel')
        person=professional_person_for_trainer(ENGINE,tid)
        if not person or not person.get('active'):
            st.info("Aucun dossier professionnel individuel n'est encore lié à votre compte. Contactez l'administration.")
        else:
            prof=get_professional_360(ENGINE,person['professional_person_id'])
            st.markdown(f"#### {prof.get('display_name') or tr['full_name']}")
            st.caption(f"Profession : {prof.get('title') or 'non renseignée'} · Collaboration : {_collaboration_label(prof.get('collaboration_type'))}")
            if prof.get('summary'):st.write(prof['summary'])
            st.markdown('#### Documents expressément partagés avec moi')
            shared=trainer_shared_professional_documents(ENGINE,tid)
            if not shared:st.info("Aucun document professionnel n'a été partagé par l'administration.")
            for item in shared:
                with st.container():
                    c1,c2=st.columns([3,1]);c1.write(f"{item['display_name']} · {item['category']}")
                    try:
                        # Authorization checked on each rerender; no cached bytes in session.
                        safe=trainer_shared_professional_document_bytes(ENGINE,tid,item['id'])
                        c2.download_button('Télécharger',safe['data'],safe['name'],
                            safe.get('mime_type') or 'application/octet-stream',key=f'j6_prof_dl_{item["id"]}')
                    except (PermissionError,FileNotFoundError) as ex:st.warning(str(ex))
            st.caption('Les notes internes, les preuves IA et les documents non partagés restent réservés à l’administration.')
        footer();return
    if selected_view=='Mes missions':
        st.markdown('### Mes missions et affectations')
        personal_missions=list_trainer_missions(ENGINE,tid)
        if personal_missions:
            st.caption('Documents acceptés et missions confiées. Les références en préparation restent informatives.')
            st.dataframe(pd.DataFrame([{'Action':m['action_no'],'Mission':m['mission_id'],
                'Rôle':m.get('role') or '', 'État':m['status'],
                'Document accepté':m.get('document_ref') if m['status']=='VERIFIE' else 'À vérifier',
                'Version':m.get('document_version') if m['status']=='VERIFIE' else '',
                'Archive':'Oui' if not m['active'] else 'Non'} for m in personal_missions]),
                use_container_width=True,hide_index=True)
        else:st.info('Aucun engagement associé aux interventions.')
        st.caption('Missions liées aux actions qui vous sont affectées. Les documents acceptés sont référencés ici ; leur gestion reste dans Contractualisation.')
        st.dataframe(pd.DataFrame([{'Action':a['action_no'],'Intitulé':a['title'],
            'Client':a.get('client_name') or '—','Début':a.get('start_date') or '—',
            'Fin':a.get('end_date') or '—','Statut':normalize_action_status(a.get('status'))} for a in acts]),
            use_container_width=True,hide_index=True)
        st.info('Les versions et preuves des engagements restent historisées, y compris après remplacement.')
        footer();return
    if selected_view=='Mes échanges':
        st.markdown('### Mes échanges avec Clarté360')
        myids=[int(a['id']) for a in acts]
        # Filter on both the authenticated trainer AND his currently authorized actions.
        all_reports=[]
        for aid in myids:all_reports.extend(trainer_reports(ENGINE,aid,tid))
        all_reports.sort(key=lambda x:(x.get('created_at') or '',int(x.get('id') or 0)),reverse=True)
        if all_reports:
            _j4_portal_threads('TRAINER',tid,all_reports)
            st.dataframe(pd.DataFrame([{'Date':format_app_datetime(x.get('created_at')),
                'Objet':x['subject'],'Statut':str(x.get('status') or '').replace('_',' '),
                'Réponse administration':x.get('admin_response') or ''} for x in all_reports[:80]]),use_container_width=True,hide_index=True)
        else:st.info('Aucune transmission enregistrée pour vos actions actuellement accessibles.')
        st.caption("Pour envoyer un nouveau signalement, ouvrez l'action concernée, puis « Signaler / informer ».")
        footer();return
    if selected_view=='Mes interventions':
        if not acts:
            st.info('Aucune action autorisée à ouvrir.'); footer();return
        labels={f"{a['action_no']} — {a['title']} — {normalize_action_status(a.get('status'))}":a for a in acts}
        requested_action=st.query_params.get('action_id')
        try: requested_action=int(requested_action) if requested_action is not None else None
        except Exception:requested_action=None
        from_notification=st.session_state.pop('j4_trainer_action',None)
        if from_notification is not None:requested_action=from_notification
        label_options=list(labels)
        if requested_action and any(row['id']==requested_action for row in acts):
            preferred=next(k for k,v in labels.items() if v['id']==requested_action)
            st.session_state['trainer_action_choice']=preferred
        if st.session_state.get('trainer_action_choice') not in label_options:
            st.session_state['trainer_action_choice']=label_options[0]
        st.sidebar.markdown('#### Action en cours')
        lab=st.sidebar.selectbox('Action à ouvrir',label_options,key='trainer_action_choice')
        if st.button('← Revenir à mon accueil personnel',key='j6_trainer_back_home'):
            st.session_state['_j6_next_trainer_view']='Accueil personnel';rerun()
        render_trainer_action(labels[lab],tr)
        footer(labels[lab]['id']);return
    # Global attendance and action list are limited to the personal homepage.
    st.markdown('### Tableau de bord de mes interventions')
    tasks=trainer_countersign_tasks(ENGINE,tid)
    # Tableau de bord global : obligations de l'intervenant + signatures bénéficiaires à suivre.
    global_missing=global_absent=global_finalized=global_slots=0
    for aa in acts:
        dd=trainer_action_dashboard(ENGINE,tid,aa['id'],TZ) or {}
        for sl in dd.get('slots') or []:
            tz_name=organization_runtime_config(ENGINE,aa['id'])['timezone']
            _,slot_end=slot_start_end(sl,tz_name)
            if datetime.now(slot_end.tzinfo) < slot_end:
                continue  # L'avenir n'est jamais à régulariser.
            global_slots += 1
            states=_slot_participant_states(ENGINE,sl['id'])
            missing=[x for x in states if x['status'] in ('EN_ATTENTE','PRESENT_REGULARISE')]
            absent=[x for x in states if x['status']=='ABSENT']
            cs_ok,_=required_slot_countersignatures_complete(ENGINE,sl['id'])
            global_missing += len(missing); global_absent += len(absent)
            if not missing and cs_ok: global_finalized += 1
    st.markdown('#### Suivi de mes émargements')
    d1,d2,d3,d4=st.columns(4)
    d1.metric('Créneaux à contresigner / finaliser',len(tasks))
    d2.metric('Signatures bénéficiaires à régulariser',global_missing)
    d3.metric('Absences signalées',global_absent)
    d4.metric('Créneaux finalisés',f"{global_finalized}/{global_slots}" if global_slots else '0')
    if tasks: st.info('Des créneaux nécessitent encore votre intervention. Ouvrez l’action concernée pour voir le détail bénéficiaire par bénéficiaire.')
    elif global_missing: st.warning('Aucune contresignature immédiatement réalisable, mais des signatures bénéficiaires restent à régulariser.')
    else: st.success('Aucune contresignature ni signature bénéficiaire en attente actuellement.')
    cards=[]
    for a in acts:
        data=trainer_action_dashboard(ENGINE,tid,a['id'],TZ); nxt=data.get('next_slot') if data else None
        cards.append({'Action':a['action_no'],'Intitulé':a['title'],'Client':a.get('client_name') or '','Début':a.get('start_date') or '','Fin':a.get('end_date') or '','Prochaine séance':_slot_label(nxt) if nxt else '—','Statut':normalize_action_status(a.get('status'))})
    st.dataframe(pd.DataFrame(cards),use_container_width=True,hide_index=True)
    st.caption('Pour agir sur une action, choisissez « Mes interventions » dans le menu personnel.')
    footer();return


def beneficiary_invitation_page(token):
    header('Clarté360 — Activation de mon espace','Création de votre accès personnel')
    b=beneficiary_by_invite(ENGINE,token)
    if not b:
        st.warning("Ce lien d’activation a déjà été utilisé, a expiré ou n’est plus valide.")
        st.info("Si votre espace a déjà été activé, utilisez désormais l’accès permanent bénéficiaire.")
        st.link_button('SE CONNECTER À MON ESPACE',f"{BASE_URL.rstrip('/')}?beneficiary_portal=1",type='primary')
        footer(); return
    st.info(f"Espace de {b['first_name']} {b['last_name']} — {b.get('portal_email') or b.get('current_email')}")
    with st.form('beneficiary_invite_accept'):
        p1=st.text_input('Choisissez un mot de passe (10 caractères minimum)',type='password')
        p2=st.text_input('Confirmez le mot de passe',type='password')
        ok=st.form_submit_button('ACTIVER MON ESPACE',type='primary')
    if ok:
        if p1!=p2: st.error('Les deux mots de passe sont différents.')
        else:
            done,msg=accept_beneficiary_invitation(ENGINE,token,p1)
            if done:
                st.success(msg);st.link_button('ACCÉDER À MON ESPACE',f"{BASE_URL.rstrip('/')}?beneficiary_portal=1")
            else: st.error(msg)
    footer()

def send_beneficiary_password_reset_email(acc, token):
    email=(acc.get('email') or '').strip()
    if not email: return False,'Adresse email absente.'
    org=org_identity(); org_name=(org or {}).get('name') or 'Clarté360'
    url=f"{BASE_URL.rstrip('/')}?beneficiary_reset={quote(token)}"
    body=f"""<p>Bonjour {acc.get('first_name') or ''},</p><p>Une demande de réinitialisation du mot de passe de votre espace bénéficiaire {org_name} a été reçue.</p><p><a href='{url}'>RÉINITIALISER MON MOT DE PASSE</a></p><p>Ce lien est temporaire. Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.</p>{privacy_notice_html()}"""
    try:
        send_mail(mail_cfg(),email,f"{org_name} — Réinitialisation de votre mot de passe bénéficiaire",body); return True,'Email de réinitialisation envoyé.'
    except Exception as ex:
        return False,f'Email non envoyé : {friendly_mail_error(ex)}'

def beneficiary_reset_request_page():
    header('Clarté360 — Espace bénéficiaire','Mot de passe oublié')
    with st.form('beneficiary_reset_request_form'):
        email=st.text_input('Votre adresse email').strip().lower()
        submit=st.form_submit_button('Recevoir un lien de réinitialisation',type='primary')
    if submit:
        acc,token=create_beneficiary_password_reset(ENGINE,email)
        if acc and token:
            ok,msg=send_beneficiary_password_reset_email(acc,token)
            audit(ENGINE,'BENEFICIARY_PASSWORD_RESET_EMAIL_SENT' if ok else 'BENEFICIARY_PASSWORD_RESET_EMAIL_FAILED',actor=email,entity_type='beneficiary',entity_id=acc['beneficiary_id'],details={'message':msg})
        st.success("Si cette adresse correspond à un espace bénéficiaire actif, un email de réinitialisation vient d'être envoyé.")
    st.link_button('Retour à la connexion',f"{BASE_URL.rstrip('/')}?beneficiary_portal=1")
    footer()

def beneficiary_reset_page(token):
    header('Clarté360 — Espace bénéficiaire','Choisir un nouveau mot de passe')
    acc=beneficiary_by_reset_token(ENGINE,token)
    if not acc:
        st.error('Lien invalide, expiré ou déjà utilisé.')
        st.link_button('Demander un nouveau lien',f"{BASE_URL.rstrip('/')}?beneficiary_reset_request=1")
        footer(); return
    with st.form('beneficiary_reset_form'):
        p1=st.text_input('Nouveau mot de passe (10 caractères minimum)',type='password')
        p2=st.text_input('Confirmez le mot de passe',type='password')
        submit=st.form_submit_button('ENREGISTRER LE NOUVEAU MOT DE PASSE',type='primary')
    if submit:
        if p1!=p2: st.error('Les deux mots de passe sont différents.')
        else:
            ok,msg=complete_beneficiary_password_reset(ENGINE,token,p1)
            if ok:
                revoke_subject_sessions(ENGINE,'BENEFICIARY',acc['beneficiary_id'])
                st.success('Votre mot de passe a été modifié.')
                st.link_button('SE CONNECTER À MON ESPACE',f"{BASE_URL.rstrip('/')}?beneficiary_portal=1",type='primary')
            else: st.error(msg)
    footer()

def beneficiary_portal_page():
    _restore_beneficiary_session()
    if not st.session_state.get('beneficiary_portal_id'):
        header('Clarté360 — Espace bénéficiaire','Mes formations, mon planning et mes documents')
        with st.form('beneficiary_login'):
            email=st.text_input('Email').strip().lower();pw=st.text_input('Mot de passe',type='password');ok=st.form_submit_button('Se connecter',type='primary')
        if ok:
            acc=verify_beneficiary_login(ENGINE,email,pw)
            if acc:
                st.session_state.beneficiary_portal_id=acc['beneficiary_id'];_issue_persistent_session('BENEFICIARY',acc['beneficiary_id'],acc.get('email') or 'beneficiary')
            else: st.error('Identifiants incorrects ou espace non activé.')
        st.link_button('Mot de passe oublié',f"{BASE_URL.rstrip('/')}?beneficiary_reset_request=1")
        footer();return
    bid=st.session_state.beneficiary_portal_id
    b=one(ENGINE,'SELECT * FROM beneficiaries WHERE id=:b AND active=1',{'b':bid})
    acc=one(ENGINE,'SELECT * FROM beneficiary_portal_accounts WHERE beneficiary_id=:b AND active=1',{'b':bid})
    if not b or not acc:
        st.session_state.pop('beneficiary_portal_id',None);rerun()
    header('Clarté360 — Espace bénéficiaire',f"Bienvenue {b['first_name']} {b['last_name']}")
    _j4_notification_drawer('BENEFICIARY',bid)
    c1,c2=st.columns([4,1]);c1.caption(f"Identifiant interne : {b['public_id']} · Connexion : {acc['email']}")
    if c2.button('Se déconnecter',use_container_width=True): _logout_persistent('BENEFICIARY',['beneficiary_portal_id'])
    all_acts=beneficiary_participations(ENGINE,bid)
    act_map={int(a['id']):a for a in all_acts}
    if '_p3_next_beneficiary_action' in st.session_state:
        requested=st.session_state.pop('_p3_next_beneficiary_action')
        st.session_state['p3_beneficiary_action_id']=authorized_action_choice(act_map,requested)
        st.session_state['p3_screen_beneficiary']='journey'
    current_action=authorized_action_choice(act_map,st.session_state.get('p3_beneficiary_action_id'))
    if st.session_state.get('p3_beneficiary_action_id')!=current_action:
        st.session_state['p3_beneficiary_action_id']=current_action
    st.sidebar.markdown('#### Mes actions')
    selected_action_id=st.sidebar.selectbox('Action à consulter',[None]+list(act_map),
        key='p3_beneficiary_action_id',
        format_func=lambda value:'Toutes mes actions' if value is None else
        f"{act_map[value]['action_no']} — {act_map[value]['title']}")
    chosen_action=act_map.get(selected_action_id)
    selected_section=_p3_sidebar_section('BENEFICIARY',action_id=selected_action_id,
        action_no=chosen_action['action_no'] if chosen_action else None)
    acts=all_acts if selected_action_id is None else [chosen_action]
    docs=list_beneficiary_documents(ENGINE,bid)
    pending=q(ENGINE,"""SELECT qc.*,a.action_no,qt.title FROM quality_campaigns qc JOIN actions a ON a.id=qc.action_id JOIN questionnaire_templates qt ON qt.id=qc.template_id
      WHERE qc.participant_id IN (SELECT id FROM participants WHERE beneficiary_id=:b) AND qc.status<>'COMPLETED' ORDER BY qc.due_at""",{'b':bid})
    completed=q(ENGINE,"""SELECT qc.*,a.action_no,a.title action_title,qt.title FROM quality_campaigns qc JOIN actions a ON a.id=qc.action_id JOIN questionnaire_templates qt ON qt.id=qc.template_id
      WHERE qc.participant_id IN (SELECT id FROM participants WHERE beneficiary_id=:b) AND qc.status='COMPLETED' ORDER BY COALESCE(qc.completed_at,qc.created_at) DESC""",{'b':bid})
    prescriptions=list_tool_prescriptions(ENGINE,beneficiary_id=bid,include_cancelled=False)
    doc_notifications=list_document_notifications(ENGINE,'BENEFICIARY',bid)
    if selected_action_id is not None:
        docs=action_rows(docs,selected_action_id)
        pending=action_rows(pending,selected_action_id)
        completed=action_rows(completed,selected_action_id)
        prescriptions=action_rows(prescriptions,selected_action_id)
        doc_notifications=action_rows(doc_notifications,selected_action_id)
    # P3 navigation: action first, then authorized contextual section.

    if selected_section=='home':
        # J7: a true personal multi-action dashboard, never reusing a filtered action
        # selection to hide other legitimate appointments or outstanding work.
        overview=beneficiary_dashboard(ENGINE,bid)
        st.markdown('#### Mon tableau de bord personnel')
        b1,b2,b3=st.columns(3)
        b1.metric('Parcours enregistrés',len(overview['actions']))
        b2.metric('Documents disponibles',len(overview['documents']))
        b3.metric('Actions à réaliser',len(overview['pending_campaigns'])+len(overview['pending_tools']))
        b4,b5,b6=st.columns(3)
        b4.metric('Rendez-vous à venir',len(overview['upcoming']))
        b5.metric('Signatures à régulariser',overview['signatures_to_review'])
        b6.metric('Demandes envoyées',len(overview['reports']))
        personal_view=st.radio('Mon espace personnel',['Mon activité','Mes documents','Mes échanges'],
            horizontal=True,key='j7_benef_home_view')
        if personal_view=='Mon activité':
            st.markdown('##### Mes prochains rendez-vous')
            if overview['upcoming']:
                st.caption('Vue de restitution en lecture seule : le planning se modifie dans chaque action.')
                st.dataframe(pd.DataFrame([{'Action':r['action_no'],'Date':format_app_date(r['slot_date']),
                    'Début':r['start_time'],'Fin':r['end_time']} for r in overview['upcoming'][:8]]),
                    use_container_width=True,hide_index=True)
            else:st.info('Aucun rendez-vous planifié prochainement.')
            st.markdown('##### Mes travaux et questionnaires à faire')
            if overview['pending_campaigns']:
                st.caption('Vue de restitution en lecture seule : ouvrez l’action pour répondre au questionnaire.')
                st.dataframe(pd.DataFrame([{'Action':r['action_no'],'Questionnaire':r['title'],
                    'Échéance':format_app_deadline(r.get('due_at'))} for r in overview['pending_campaigns'][:12]]),
                    use_container_width=True,hide_index=True)
            if overview['pending_tools']:
                st.caption(f"Outils à réaliser ou suivre : {len(overview['pending_tools'])}")
            if not overview['pending_campaigns'] and not overview['pending_tools']:
                st.success('Aucun travail ou questionnaire en attente.')
        if personal_view=='Mes documents':
            st.caption('Documents disponibles dans vos actions autorisées, jamais ceux des autres bénéficiaires.')
            for document in overview['documents'][:20]:
                st.write(f"{document.get('action_no') or 'Général'} — {document['display_name']}")
            if not overview['documents']:st.info('Aucun document partagé.')
            st.caption('Ouvrez le dossier concerné dans le menu pour télécharger le document autorisé.')
        if personal_view=='Mes échanges':
            st.caption('Retrouvez vos signalements, les réponses de l’administration et leur état.')
            for report in overview['reports'][:20]:
                st.write(f"{report.get('action_no') or 'Action'} — {report['subject']} · {report['status']}")
                if report.get('admin_response'):st.caption(f"Réponse : {report['admin_response']}")
            if not overview['reports']:st.info('Aucune demande envoyée.')
        st.markdown('#### Mes formations et accompagnements')
        if all_acts:
            st.dataframe(pd.DataFrame([{'Action':a['action_no'],'Intitulé':a['title'],
                'Prestation':a.get('prestation_type') or a.get('nature'),'Début':a.get('start_date') or '',
                'Fin':a.get('end_date') or '','Statut':normalize_action_status(a.get('status'))}
                for a in all_acts]),use_container_width=True,hide_index=True)
            st.markdown('#### Ouvrir une action')
            for a in all_acts:
                c1,c2=st.columns([5,1])
                c1.markdown(f"**{a['action_no']} — {a['title']}**")
                c1.caption(f"{a.get('prestation_type') or a.get('nature') or 'Action'} · {normalize_action_status(a.get('status'))}")
                if c2.button('Ouvrir',key=f"p3_open_benef_action_{a['id']}"):
                    st.session_state['_p3_next_beneficiary_action']=a['id']
                    rerun()
        else:st.info('Aucun parcours inscrit.')

    if selected_section=='journey':
        if acts: st.dataframe(pd.DataFrame([{'Action':a['action_no'],'Intitulé':a['title'],'Client':a.get('client_name') or '','Lieu / modalité':a.get('location') or a.get('mode') or '','Période':f"{a.get('start_date') or '—'} → {a.get('end_date') or '—'}"} for a in acts]),use_container_width=True,hide_index=True)
        else: st.info('Aucun parcours.')
    if selected_section=='planning':
        rows=[]
        for a in acts:
            for sl in q(ENGINE,"SELECT * FROM slots WHERE action_id=:a AND status NOT IN ('ANNULE','REPORTE') ORDER BY slot_date,start_time",{'a':a['id']}): rows.append({'Action':a['action_no'],'Date':format_app_date(sl['slot_date']),'Début':format_app_time(sl['start_time']),'Fin':format_app_time(sl['end_time']),'Type':sl.get('slot_kind') or 'NORMAL'})
        if rows: st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        else: st.info('Aucun créneau disponible.')
        if acts:
            st.markdown('#### Mes calendriers')
            for aa in acts:
                ics=action_calendar_ics(ENGINE,aa['id'],beneficiary_id=bid)
                if ics:
                    st.download_button(f"📅 {aa['action_no']} — ajouter / actualiser dans mon agenda",ics,file_name=f"{aa['action_no']}_planning.ics",mime='text/calendar',key=f'benef_ics_{aa["id"]}')
    def _show_docs(rows,empty,key_prefix='docs'):
        if not rows: st.info(empty);return
        for d in rows:
            path=Path(d['storage_path'])
            if path.is_file():
                data=read_document_for_actor(ENGINE,d['id'],'BENEFICIARY',bid)
                st.download_button(f"{d.get('action_no') or 'Général'} — {d['display_name']}",data,file_name=d['display_name'],key=f"bdl_{key_prefix}_{d['id']}")
    if selected_section=='teams':
        meetings=[]
        for aa in acts:
            room=teams_room(ENGINE,aa['id']) if action_module_enabled(ENGINE,aa['id'],'TEAMS') else None
            if room and room.get('join_web_url'): meetings.append((aa,room))
        if not meetings: st.info('Aucune réunion Teams active pour vos actions.')
        for aa,room in meetings:
            st.markdown(f"**{aa['action_no']} — {aa['title']}**")
            st.link_button('REJOINDRE LA RÉUNION TEAMS',room['join_web_url'])
            nxt=teams_next_meeting(ENGINE,aa['id'])
            if nxt: st.caption(f"Prochaine séance : {nxt.get('slot_date')} — {nxt.get('start_time')}–{nxt.get('end_time')}")
            pp=one(ENGINE,'SELECT id FROM participants WHERE action_id=:a AND beneficiary_id=:b AND active=1',{'a':aa['id'],'b':bid})
            if pp:
                evs=teams_participant_evidence(ENGINE,aa['id'],pp['id'])
                hist=[]
                for ev in evs:
                    occ=ev['occurrence']; rep=ev.get('report')
                    hist.append({'Séance':f"{occ.get('slot_date')} — {occ.get('start_time')}–{occ.get('end_time')}",'Réunion Microsoft':'Constatée' if rep else 'Rapport en attente','Ma présence Teams':_duration_hms(ev.get('seconds')) if ev.get('seconds') else ('Non observée' if rep else '—')})
                if hist: st.dataframe(pd.DataFrame(hist),use_container_width=True,hide_index=True)
    if selected_section=='tools':
        if not prescriptions:
            st.info('Aucun outil Clarté360 ne vous est actuellement prescrit.')
        else:
            for pr in prescriptions:
                st.markdown(f"**{pr['tool_name']}** — {pr['action_no']} · Statut : {pr['status'].replace('_',' ')}")
                if pr.get('due_at'): st.caption(f"Échéance : {pr['due_at']}")
                if pr.get('status')=='TERMINE':
                    if pr.get('tool_code') in ('PIP_RIASEC_ONET','IPIP_NEO120'):
                        st.success('Passation terminée — une nouvelle passation nécessite une nouvelle prescription.')
                        st.divider()
                        continue
                    st.success('Outil terminé — vous pouvez le rouvrir à tout moment depuis votre espace.')
                try:
                    if pr.get('tool_code')=='PIP_RIASEC_ONET':
                        key=secret('pip_connector','launch_signing_key','')
                        launch_url=build_pip_prescription_launch(ENGINE,pr['prescription_id'],key,valid_seconds=3600)
                    elif pr.get('tool_code')=='IPIP_NEO120':
                        key=secret('IPIP_CONNECTOR','LAUNCH_SIGNING_KEY','')
                        launch_url=build_ipip_prescription_launch(ENGINE,pr['prescription_id'],key,valid_seconds=3600)
                    else:
                        launch_url=(pr.get('base_url') or '').strip()
                        if not launch_url:
                            raise ValueError("URL de l'outil non configurée.")
                    st.link_button('OUVRIR CET OUTIL',launch_url,type='primary')
                except ValueError as ex:
                    st.warning(str(ex))
                st.divider()
    if selected_section=='documents':
        _show_docs([d for d in docs if d['category']!='COURS'],'Aucun document administratif disponible.','admin')
        # J4: email preference controls removed; in-app alerts are automatic.

    if selected_section=='courses':
        _show_docs([d for d in docs if d['category']=='COURS'],'Aucun document de cours disponible.','cours')
        st.markdown('#### Déposer mes documents / résultats d’applications')
        st.caption('Vous pouvez déposer plusieurs fichiers PDF ou JSON issus des outils Clarté360. Ils restent rattachés à votre espace et à l’action choisie.')
        if acts:
            amap={f"{aa['action_no']} — {aa['title']}":aa for aa in acts}; al=st.selectbox('Action concernée',list(amap),key='benef_upload_action'); aa=amap[al]
            uploads=st.file_uploader('Mes fichiers',type=['pdf','json'],accept_multiple_files=True,key='benef_app_results')
            if st.button('DÉPOSER DANS MON ESPACE',type='primary',disabled=not bool(uploads),key='benef_upload_btn'):
                pp=one(ENGINE,'SELECT id FROM participants WHERE action_id=:a AND beneficiary_id=:b AND active=1',{'a':aa['id'],'b':bid})
                done=0
                progress=st.progress(0,text='Vérification et enregistrement des fichiers sélectionnés')
                total=len(uploads or [])
                for index,up in enumerate(uploads or []):
                    try:
                        store_document_for_actor(ENGINE,'BENEFICIARY',bid,up.getvalue(),up.name,aa['id'],beneficiary_id=bid,
                            participant_id=(pp or {}).get('id'),category='BENEFICIAIRE',
                            progress_callback=lambda label,ratio: progress.progress(int(((index+ratio)/total)*100),text=label))
                        done+=1
                    except Exception as ex: st.error(f"{up.name} : {ex}")
                if done: st.success(f'{done} fichier(s) déposé(s) dans votre espace.'); rerun()
    if selected_section=='questionnaires':
        actionable=[x for x in pending if quality_campaign_availability(x)=='OPEN']
        if not pending: st.success('Aucune action à réaliser actuellement.')
        for x in pending:
            availability=quality_campaign_availability(x)
            if availability=='OPEN':
                st.link_button(f"{x['action_no']} — {x['title']}",quality_token_url(x['token'],BASE_URL))
            else:
                due=local_dt(x.get('due_at')) if x.get('due_at') else None
                label=due.strftime('%d/%m/%Y à %H:%M') if due else 'la date prévue'
                st.markdown(f"**🔒 {x['action_no']} — {x['title']}**")
                st.caption(f"Disponible à partir du {label}. Ce questionnaire ne peut pas être rempli avant son échéance.")
        if completed:
            st.markdown('#### Questionnaires terminés')
            for x in completed:
                try:
                    data=quality_response_pdf(ENGINE,x['id'])
                    st.download_button(f"✅ {x['action_no']} — {x['title']}",data,file_name=f"{x['action_no']}_questionnaire_{x['id']}.pdf",mime='application/pdf',key=f"benef_qpdf_{x['id']}")
                except Exception as ex:
                    ref=log_ui_exception(ENGINE,'beneficiary_quality_pdf',ex,action_id=x.get('action_id'),actor='beneficiary',entity_type='quality_campaign',entity_id=x['id'])
                    st.caption(f"{x['action_no']} — questionnaire terminé. PDF momentanément indisponible (référence {ref}).")
    if selected_section=='signatures':
        st.caption('Vous pouvez consulter vos propres preuves de présence. Le certificat définitif n’est disponible qu’après clôture administrative de l’action ; cette clôture ne supprime pas les évaluations à froid programmées.')
        for aa in acts:
            pp=one(ENGINE,'SELECT id FROM participants WHERE action_id=:a AND beneficiary_id=:b AND active=1',{'a':aa['id'],'b':bid})
            if not pp: continue
            st.markdown(f"**{aa['action_no']} — {aa['title']}**")
            rows=[]
            for sl in q(ENGINE,'SELECT * FROM slots WHERE action_id=:a ORDER BY slot_date,start_time',{'a':aa['id']}):
                sig=one(ENGINE,"SELECT * FROM signatures WHERE participant_id=:p AND slot_id=:s AND status='VALIDE'",{'p':pp['id'],'s':sl['id']})
                cs_ok,_=required_slot_countersignatures_complete(ENGINE,sl['id'])
                te=next((x for x in teams_participant_evidence(ENGINE,aa['id'],pp['id']) if int(x['occurrence']['slot_id'])==int(sl['id'])),None)
                rows.append({'Séance':f"{sl['slot_date']} — {sl['start_time']}–{sl['end_time']}",'Mon émargement':'Signé' if sig else 'Non signé','Contresignature':'Validée' if cs_ok else 'En attente','Présence Teams':_duration_hms(te.get('seconds')) if te and te.get('seconds') else ('Non observée' if te and te.get('report') else 'Rapport en attente')})
            if rows: st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
            try:
                epdf=individual_pdf(ENGINE,pp['id'])
                st.download_button(f"✍️ Consulter ma feuille d’émargement — {aa['action_no']}",epdf,file_name=f"{aa['action_no']}_emargement.pdf",mime='application/pdf',key=f"benef_epdf2_{pp['id']}")
            except Exception: pass
            ok_cert,issues=can_issue_certificate(ENGINE,pp['id'],require_closed=True)
            if normalize_action_status(aa.get('status'))=='CLOTUREE' and ok_cert:
                st.download_button(f"🎓 Certificat de réalisation définitif — {aa['action_no']}",certificate_pdf(ENGINE,pp['id']),file_name=f"{aa['action_no']}_certificat_realisation.pdf",mime='application/pdf',key=f"benef_cert_{pp['id']}")
            elif normalize_action_status(aa.get('status'))!='CLOTUREE':
                st.info('Certificat final : disponible uniquement lorsque l’administration aura clôturé cette action.')
            else:
                st.warning('Certificat final momentanément indisponible : '+ ' ; '.join(issues[:3]))
            st.divider()

    if selected_section=='reports':
        st.caption("Vous pouvez transmettre une observation, une difficulté, un incident, un problème logistique ou une demande de contact à l'administration. Votre historique reste visible après traitement.")
        if acts:
            amap={f"{aa['action_no']} — {aa['title']}":aa for aa in acts}
            with st.form('beneficiary_report_form',clear_on_submit=True):
                al=st.selectbox('Action concernée',list(amap),key='benef_report_action'); aa=amap[al]
                rt=st.selectbox('Nature',['Observation','Difficulté','Incident','Problème logistique','Besoin de contact','Autre'],key='benef_report_type')
                subject=st.text_input('Objet *',key='benef_report_subject'); desc=st.text_area('Description *',height=150,key='benef_report_desc')
                st.caption('Ce signalement sera automatiquement intégré au suivi qualité, avec la nature sélectionnée ci-dessus.')
                up=_j4_report_file_uploader('Joindre éventuellement un document (10 Mo max)',types=['pdf','docx','xlsx','png','jpg','jpeg','txt','json'],key='benef_report_file')
                submit=st.form_submit_button('TRANSMETTRE À L’ADMINISTRATION',type='primary')
            if submit:
                if not subject.strip() or not desc.strip(): st.error('Objet et description sont obligatoires.')
                elif up is not None and up.size>10*1024*1024: st.error('Le fichier dépasse 10 Mo.')
                else:
                    ap=an=None
                    if up is not None:
                        safe=re.sub(r'[^A-Za-z0-9._-]+','_',up.name)[:120]; an=up.name; ap=str(TRAINER_REPORT_DIR/f"benef_{aa['id']}_{bid}_{int(datetime.now().timestamp())}_{safe}"); Path(ap).write_bytes(up.getvalue())
                    rid=create_beneficiary_report(ENGINE,aa['id'],bid,rt,subject.strip(),desc.strip(),True,ap,an)
                    if rid: st.success("Votre signalement a été transmis à l'administration et journalisé."); rerun()
                    else: st.error('Transmission impossible pour cette action.')
        hist=beneficiary_reports(ENGINE,beneficiary_id=bid)
        if hist:
            _j4_portal_threads('BENEFICIARY',bid,hist)
            st.markdown('#### Mes signalements')
            st.dataframe(pd.DataFrame([{'Date':format_app_datetime(x['created_at']),'Action':x['action_no'],'Nature':x['report_type'],'Objet':x['subject'],'Statut':x['status'].replace('_',' '),'Réponse administration':x.get('admin_response') or ''} for x in hist]),use_container_width=True,hide_index=True)
        else: st.info('Aucun signalement transmis.')
    if selected_section=='archives':
        st.caption('Vous pouvez télécharger à tout moment une copie des documents actuellement mis à disposition dans votre portail.')
        if acts:
            st.markdown('#### Archives documentaires par action (uniquement vos documents autorisés)')
            for act in acts:
                archive=export_action_documents_zip(ENGINE,act['id'],'BENEFICIARY',bid)
                st.download_button(f"Documents de l’action {act['action_no']} (ZIP)",archive,
                    file_name=f"{act['action_no']}_mes_documents.zip",mime='application/zip',
                    key=f'benef_zip_action_{act["id"]}')
        z=beneficiary_portal_zip(ENGINE,bid)
        st.download_button('TÉLÉCHARGER MON ESPACE EN ZIP',z,file_name=f"{b['public_id']}_ESPACE_CLARTE360.zip",mime='application/zip',type='primary')
        _show_docs(docs,'Aucun document disponible.','archives')
    if selected_section=='profile':
        st.markdown('#### Mon compte')
        st.caption('Ces informations sont visibles uniquement depuis votre espace personnel.')
        st.write(f"Nom : {b['last_name']} {b['first_name']}")
        st.write(f"Adresse de connexion : {acc['email']}")
        st.link_button('Gérer mon mot de passe',f"{BASE_URL.rstrip('/')}?beneficiary_reset_request=1")
    footer(selected_action_id)

def footer(action_id=None):
    org=org_identity(action_id);parts=[]
    if org:
        parts.append(' — '.join(x for x in [org.get('legal_name') or org.get('name'),org.get('address'),(' '.join(x for x in [org.get('postal_code'),org.get('city')] if x))] if x))
        parts.append(' — '.join(x for x in [('SIRET : '+org.get('siret')) if org.get('siret') else '',('NDA : '+org.get('nda')) if org.get('nda') else '',org.get('general_email') or '',org.get('website') or ''] if x))
    text='<br>'.join(x for x in parts if x) or (LEGAL_LINE_1+'<br>'+LEGAL_LINE_2)
    st.markdown(f"<div class='c360-footer'>{text}</div>",unsafe_allow_html=True)

def header(title=APP_NAME,sub='Gestion sécurisée des présences, signatures et justificatifs'):
    img=base64.b64encode(LOGO_PATH.read_bytes()).decode() if LOGO_PATH.exists() else ''
    st.markdown(f"<div class='c360-header'><img src='data:image/png;base64,{img}'><div><div class='c360-title'>{title}</div><div class='c360-subtitle'>{sub} — Version {APP_VERSION}</div></div></div>",unsafe_allow_html=True)
def rerun(): st.rerun()
def get_ip(): return request_technical_context()[0]
def get_ua(): return request_technical_context()[1]

def setup_or_login():
    count=one(ENGINE,'SELECT COUNT(*) n FROM admins')['n']
    if count==0:
        header(sub="Première mise en service")
        st.info("Aucun administrateur n'existe encore. Créez le premier compte. Cette étape n'apparaîtra qu'une fois.")
        setup_key=st.text_input('Clé de mise en service',type='password')
        email=st.text_input('Email administrateur').strip().lower();name=st.text_input('Nom et prénom');p1=st.text_input('Mot de passe',type='password');p2=st.text_input('Confirmer le mot de passe',type='password')
        if st.button('Créer le compte administrateur',type='primary'):
            expected=secret('app','setup_key','')
            if expected and setup_key!=expected: st.error('Clé de mise en service incorrecte.');return False
            if not email or len(p1)<10 or p1!=p2: st.error('Email requis, mot de passe d’au moins 10 caractères et confirmation identique.');return False
            execute(ENGINE,'INSERT INTO admins(email,password_hash,full_name,created_at) VALUES(:e,:p,:n,:c)',{'e':email,'p':hash_password(p1),'n':name,'c':utcnow_iso()});audit(ENGINE,'ADMIN_CREATED',actor=email,entity_type='admin',details={'email':email});st.success('Compte créé. Connectez-vous.');st.session_state.clear();rerun()
        footer();return False
    if _restore_admin_session(): return True
    header('Clarté360 — Gestion des actions — Administration','Espace administrateur')
    c1,c2=st.columns([1,1]);
    with c1:
        email=st.text_input('Email').strip().lower();pw=st.text_input('Mot de passe',type='password')
        if st.button('Se connecter',type='primary',use_container_width=True):
            a=one(ENGINE,'SELECT * FROM admins WHERE email=:e AND active=1',{'e':email})
            if a and verify_password(pw,a['password_hash']): st.session_state.admin_email=email;st.session_state.admin_name=a.get('full_name') or email;_issue_persistent_session('ADMIN',email,email)
            else: st.error('Identifiants incorrects.')
    with c2:
        st.markdown("<div class='c360-card'><h3>À quoi sert cet espace ?</h3>Créer ou importer une action, définir ses créneaux, gérer les stagiaires, suivre les signatures, relancer et générer les justificatifs.</div>",unsafe_allow_html=True)
    st.caption('Accès administration uniquement. Les espaces intervenant et bénéficiaire disposent de leurs propres liens directs.')
    footer();return False

def signature_page(token=None,slot_token=None):
    header('Clarté360 — Émargement','Signature de présence sur smartphone, tablette ou ordinateur')
    if token:
        row=one(ENGINE,"""SELECT t.token,p.*,a.title,a.subtitle,a.action_no,a.id action_id,s.id slot_id,s.slot_date,s.start_time,s.end_time,s.send_offset_min,s.close_offset_min
          FROM signature_tokens t JOIN participants p ON p.id=t.participant_id JOIN slots s ON s.id=t.slot_id JOIN actions a ON a.id=p.action_id WHERE t.token=:t""",{'t':token})
        if not row: st.error('Lien invalide ou expiré.');footer();return
        if one(ENGINE,'SELECT * FROM signatures WHERE participant_id=:p AND slot_id=:s',{'p':row['id'],'s':row['slot_id']}): st.success('Votre présence a déjà été émargée pour ce créneau. Merci.');footer();return
        render_sign_form(row,method='EMAIL')
    else:
        slot=one(ENGINE,"""SELECT s.*,a.title,a.subtitle,a.action_no,a.id action_id FROM slots s JOIN actions a ON a.id=s.action_id WHERE s.public_token=:t""",{'t':slot_token})
        if not slot: st.error('QR code invalide.');footer();return
        st.markdown(f"<div class='c360-card'><b>{slot['title']}</b><br>{slot['slot_date']} — {slot['start_time']} à {slot['end_time']}</div>",unsafe_allow_html=True)
        last=st.text_input('Votre nom').strip();pin=st.text_input('Votre code personnel à 4 chiffres',type='password').strip()
        if st.button('M’identifier',type='primary'):
            candidates=q(ENGINE,'SELECT * FROM participants WHERE action_id=:a AND UPPER(last_name)=UPPER(:n) AND active=1',{'a':slot['action_id'],'n':last})
            match=next((p for p in candidates if p.get('pin_hash') and verify_password(pin,p['pin_hash'])),None)
            if not match: st.error('Nom ou code incorrect.');footer();return
            st.session_state.qr_participant_id=match['id']
        pid=st.session_state.get('qr_participant_id')
        if pid:
            p=one(ENGINE,'SELECT * FROM participants WHERE id=:p AND action_id=:a',{'p':pid,'a':slot['action_id']})
            row={**slot,**p,'slot_id':slot['id'],'id':p['id']}
            if one(ENGINE,'SELECT * FROM signatures WHERE participant_id=:p AND slot_id=:s',{'p':p['id'],'s':slot['id']}): st.success('Votre présence a déjà été émargée pour ce créneau.');footer();return
            render_sign_form(row,method='QR')
    footer()

def render_sign_form(row,method):
    st.markdown(f"<div class='c360-card'><h3>{row['first_name']} {row['last_name']}</h3><b>{row['title']}</b><br>N° action : {row['action_no']}<br>Date : {row['slot_date']}<br>Créneau : {row['start_time']}–{row['end_time']}</div>",unsafe_allow_html=True)
    is_late=False
    try:
        from zoneinfo import ZoneInfo
        end=parse_dt(row['slot_date'],row['end_time'],TZ); now=datetime.now(ZoneInfo(TZ)); opening=end+__import__('datetime').timedelta(minutes=int(row.get('send_offset_min') or -10)); closing=end+__import__('datetime').timedelta(minutes=int(row.get('close_offset_min') or 1440))
        if now < opening:
            st.info(f"L’émargement ouvrira à {opening.strftime('%d/%m/%Y %H:%M')}."); return
        is_late=now > closing
    except Exception:
        pass
    if is_late:
        st.warning("RÉGULARISATION A POSTERIORI — cette signature sera horodatée à sa date réelle et le document indiquera explicitement qu'elle a été recueillie après le créneau.")
        declaration="Je certifie avoir effectivement participé au créneau indiqué ci-dessus et signe cette feuille d'émargement a posteriori."
        late_reason=st.text_input('Motif de la régularisation (oubli, problème technique, autre)')
    else:
        declaration="Je certifie avoir participé au créneau de formation ou d'accompagnement indiqué ci-dessus."
        late_reason=''
    absent=one(ENGINE,"SELECT status FROM attendance_status WHERE participant_id=:p AND slot_id=:s",{'p':row['id'],'s':row['slot_id']})
    if absent and absent['status']=='ABSENT':
        st.error("Vous êtes actuellement déclaré absent sur ce créneau. Une régularisation nécessite d'abord la correction de ce statut par l'administrateur ou l'intervenant."); return
    st.write(declaration)
    st.markdown(privacy_notice_html(row.get('action_id')),unsafe_allow_html=True)
    consent=st.checkbox("Je confirme l’exactitude de ces informations et reconnais avoir pris connaissance de l’information sur mes données personnelles.")
    sig_mode=st.radio('Mode de signature',['Signature manuscrite','Nom et prénom + certification'],horizontal=True)
    canvas=None; typed_name=''
    if sig_mode=='Signature manuscrite':
        st.caption('Signez dans le cadre avec votre doigt, votre stylet ou votre souris.')
        st.info('Signez dans le cadre gris ci-dessous avec la souris, le doigt ou un stylet.')
        canvas=st_canvas(fill_color='rgba(255,255,255,0)',stroke_width=4,stroke_color='#0F172A',background_color='#EEF2F3',height=190,width=520,drawing_mode='freedraw',display_toolbar=True,update_streamlit=True,key=f"sig_{row['id']}_{row['slot_id']}")
    else:
        typed_name=st.text_input('Saisissez vos nom et prénom',value=f"{row['first_name']} {row['last_name']}")
        st.caption("La validation associe votre identité saisie, votre déclaration et l'horodatage réel à la preuve d'émargement.")
    if st.button('VALIDER MON ÉMARGEMENT',type='primary',use_container_width=True):
        if not consent: st.error('Veuillez confirmer les informations.');return
        if sig_mode=='Signature manuscrite':
            if not signature_trace_is_valid(canvas.image_data): st.error('La signature semble vide ou trop courte. Merci d’apposer une signature manuscrite complète dans le cadre.');return
            img=PILImage.fromarray(canvas.image_data.astype('uint8'),'RGBA').convert('RGB');buf=io.BytesIO();img.save(buf,format='PNG');b=buf.getvalue();digest=sha256_bytes(b)
            path=SIG_DIR/f"sig_{row['action_id']}_{row['id']}_{row['slot_id']}_{digest[:12]}.png";path.write_bytes(b); sig_method='MANUSCRITE'; signer=f"{row['first_name']} {row['last_name']}"
        else:
            if not typed_name.strip(): st.error('Nom et prénom obligatoires.'); return
            proof=f"{typed_name.strip()}|{declaration}|{row['id']}|{row['slot_id']}".encode('utf-8'); digest=sha256_bytes(proof); path=''; sig_method='NOM_PRENOM'; signer=typed_name.strip()
        try:
            execute(ENGINE,"""INSERT INTO signatures(participant_id,slot_id,signed_at,signature_path,signature_sha256,signer_name,method,access_method,signature_method,is_late,late_reason,ip_address,user_agent,declaration_text)
              VALUES(:p,:s,:at,:path,:h,:n,:m,:m,:sm,:late,:lr,:ip,:ua,:d)""",{'p':row['id'],'s':row['slot_id'],'at':utcnow_iso(),'path':str(path),'h':digest,'n':signer,'m':method,'sm':sig_method,'late':1 if is_late else 0,'lr':late_reason or None,'ip':get_ip(),'ua':get_ua(),'d':declaration})
            execute(ENGINE,'UPDATE signature_tokens SET used_at=:u WHERE participant_id=:p AND slot_id=:s',{'u':utcnow_iso(),'p':row['id'],'s':row['slot_id']})
            execute(ENGINE,"DELETE FROM attendance_status WHERE participant_id=:p AND slot_id=:s AND status='ABSENT'",{'p':row['id'],'s':row['slot_id']})
            audit(ENGINE,'SIGNATURE_RECORDED',row['action_id'],f"participant:{row['id']}",'signature',f"{row['id']}/{row['slot_id']}",{'method':method,'sha256':digest})
            st.success(f"Votre présence a bien été enregistrée à {datetime.now(ZoneInfo(TZ)).strftime('%H:%M')}. Merci.");st.balloons()
        except Exception: st.info('Cet émargement a déjà été enregistré.')

def trainer_page(token):
    row=one(ENGINE,"""SELECT t.action_id,t.trainer_id token_trainer_id,a.* FROM trainer_access_tokens t JOIN actions a ON a.id=t.action_id WHERE t.token=:t AND t.active=1""",{'t':token})
    if not row: header('Clarté360 — Intervenant');st.error('Accès intervenant invalide.');footer();return
    if row.get('token_trainer_id') and st.session_state.get('trainer_portal_id')!=row.get('token_trainer_id'):
        header('Clarté360 — Intervenant'); st.error("Ce lien opérationnel nécessite d'abord une connexion à votre espace intervenant."); st.link_button('Se connecter',f"{BASE_URL.rstrip('/')}?trainer_portal=1"); footer(); return
    header('Clarté360 — Espace intervenant','Suivi, QR code, absences, relances et contresignature')
    st.markdown(f"<div class='c360-card'><b>{row['action_no']} — {row['title']}</b><br>Intervenant : {row.get('trainer_name') or 'Non renseigné'}</div>",unsafe_allow_html=True)
    slots=q(ENGINE,'SELECT * FROM slots WHERE action_id=:a ORDER BY slot_date,start_time',{'a':row['action_id']});parts=q(ENGINE,'SELECT * FROM participants WHERE action_id=:a AND active=1 ORDER BY last_name,first_name',{'a':row['action_id']})
    if not slots: st.info('Aucun créneau.');footer();return
    sc={f"{x['slot_date']} {x['start_time']}–{x['end_time']} #{x['id']}":x for x in slots}; lab=st.selectbox('Créneau',list(sc));slot=sc[lab]
    qr=qrcode.make(public_slot_url(slot,BASE_URL));buf=io.BytesIO();qr.save(buf,format='PNG');c1,c2=st.columns([1,2]);c1.image(buf.getvalue(),width=220);c2.caption('Présentez ce QR code aux participants pour émarger.')
    sigs=q(ENGINE,'SELECT * FROM signatures WHERE slot_id=:s',{'s':slot['id']});sm={x['participant_id']:x for x in sigs};ats=q(ENGINE,'SELECT * FROM attendance_status WHERE slot_id=:s',{'s':slot['id']});am={x['participant_id']:x for x in ats}
    rows=[]
    for p in parts:
        at=am.get(p['id']); x=sm.get(p['id']); status='SIGNÉ' if x else (at['status'] if at else 'EN ATTENTE')
        rows.append({'Participant':f"{p['last_name']} {p['first_name']}",'Statut':status,'Téléphone':p.get('phone') or '','Email':p.get('email') or ''})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    pc={f"{p['last_name']} {p['first_name']}":p for p in parts}; pl=st.selectbox('Participant à gérer',list(pc));pp=pc[pl]
    c1,c2=st.columns(2)
    if c1.button('Marquer ABSENT',use_container_width=True):
        ok,msg=set_attendance_status(ENGINE,pp['id'],slot['id'],'ABSENT','Déclaré par intervenant',f"trainer:{row.get('trainer_email') or row.get('trainer_name')}")
        if ok: st.success('Absence enregistrée.');rerun()
        else: st.error(msg)
    if c2.button('Remettre EN ATTENTE',use_container_width=True): set_attendance_status(ENGINE,pp['id'],slot['id'],'EN_ATTENTE','Correction intervenant',f"trainer:{row.get('trainer_email') or row.get('trainer_name')}");rerun()
    if pp.get('email') and st.button('Relancer ce participant par email'):
        ensure_tokens_and_events(ENGINE,row['action_id'],BASE_URL,TZ);url=token_url(ENGINE,pp['id'],slot['id'],BASE_URL);cfg=mail_cfg();org=org_identity(row['action_id']);subject=f"{org.get('name') or 'Organisme'} — émargement — {row['action_no']}";body=f"<p>Bonjour {pp['first_name']},</p><p>Merci de régulariser votre émargement pour le {slot['slot_date']} de {slot['start_time']} à {slot['end_time']}.</p><p><a href='{url}'>SIGNER / RÉGULARISER</a></p>{privacy_notice_html(row['action_id'])}"
        try: send_mail(cfg,pp['email'],subject,body);audit(ENGINE,'TRAINER_MANUAL_REMINDER',row['action_id'],'trainer','participant',pp['id'],{'slot_id':slot['id']});st.success('Relance envoyée.')
        except Exception as ex: _ui_incident('envoi_email',ex,subject='L’envoi de l’email')
    st.markdown('### Contresignature du créneau')
    existing=list_slot_countersignatures(ENGINE,slot['id'])
    for cs in existing: st.success(f"Contresigné par {cs['trainer_name']} le {local_dt(cs['signed_at'],TZ).strftime('%d/%m/%Y à %H:%M')}")
    assigned=list_slot_trainers(ENGINE,slot['id'])
    legacy_tid=None
    if len(assigned)==1: legacy_tid=assigned[0]['trainer_id']
    elif row.get('trainer_email'):
        match=[x for x in assigned if x.get('email') and x['email'].lower()==row['trainer_email'].lower()]
        if len(match)==1: legacy_tid=match[0]['trainer_id']
    eligible,why,_=slot_countersignature_eligibility(ENGINE,slot['id'],trainer_id=legacy_tid)
    if assigned and legacy_tid is None:
        st.warning('Ce lien historique ne permet pas d’identifier sans ambiguïté l’intervenant en co-animation. Utilisez l’Espace intervenant personnel pour contresigner.')
    else:
        if not eligible: st.warning(why)
        name=st.text_input('Nom et prénom de l’intervenant',value=row.get('trainer_name') or '')
        legacy_mode=st.radio('Mode de signature',['Signature manuscrite','Nom et prénom + certification'],horizontal=True,key=f'legacy_mode_{slot["id"]}')
        legacy_canvas=None
        if legacy_mode=='Signature manuscrite':
            st.info('Signez dans le cadre gris ci-dessous avec la souris, le doigt ou un stylet.')
            legacy_canvas=st_canvas(fill_color='rgba(255,255,255,0)',stroke_width=4,stroke_color='#0F172A',background_color='#EEF2F3',height=190,width=520,drawing_mode='freedraw',display_toolbar=True,update_streamlit=True,key=f'legacy_csig_v32_{slot["id"]}')
        cert=st.checkbox("Je certifie l'exactitude des présences et absences indiquées pour ce créneau.",key=f'legacy_cert_{slot["id"]}')
        if st.button('CONTRESIGNER CE CRÉNEAU',type='primary',disabled=(not eligible or (bool(assigned) and legacy_tid is None))):
            if not name.strip() or not cert: st.error('Nom et certification obligatoires.')
            elif legacy_mode=='Signature manuscrite' and (legacy_canvas is None or not signature_trace_is_valid(legacy_canvas.image_data)): st.error('La signature semble vide ou trop courte. Merci d’apposer une signature manuscrite complète dans le cadre.')
            else:
                sig_bytes=None
                if legacy_mode=='Signature manuscrite':
                    img=PILImage.fromarray(legacy_canvas.image_data.astype('uint8'),'RGBA').convert('RGB');buf=io.BytesIO();img.save(buf,format='PNG');sig_bytes=buf.getvalue()
                ip,ua=request_technical_context()
                ok,msg=countersign_slot(ENGINE,slot['id'],name.strip(),row.get('trainer_email'),f"trainer:{name.strip()}","Je certifie l'exactitude des présences et absences indiquées pour ce créneau.",trainer_id=legacy_tid,signature_bytes=sig_bytes,ip_address=ip,user_agent=ua)
                if ok: st.success('Contresignature enregistrée.');rerun()
                else: st.error(msg)
    footer()

def quality_page(token):
    ctx=quality_campaign_context(ENGINE,token)
    if not ctx:
        header('Questionnaire qualité','Lien sécurisé');st.error('Lien de questionnaire invalide ou expiré.');footer();return
    runtime=organization_runtime_config(ENGINE,ctx['action_id']);org=runtime['organization'];org_name=org.get('name') or 'Organisme'
    header(f"{org_name} — Qualité",ctx['questionnaire_title'])
    if ctx.get('status')=='COMPLETED':
        st.success('Votre questionnaire a déjà été enregistré. Merci pour votre retour.');footer();return
    if not quality_campaign_is_open(ctx):
        due=local_dt(ctx.get('due_at')) if ctx.get('due_at') else None
        label=due.strftime('%d/%m/%Y à %H:%M') if due else 'la date prévue'
        st.info(f'Ce questionnaire sera disponible à partir du {label}. Il ne peut pas être rempli avant cette échéance.')
        footer();return
    respondent=ctx.get('trainer_full_name') or f"{ctx.get('first_name') or ''} {ctx.get('last_name') or ''}".strip()
    st.markdown(f"<div class='c360-card'><b>{ctx['action_title']}</b><br>N° action : {ctx['action_no']}<br>Répondant : {respondent}<br>Questionnaire : {ctx['questionnaire_title']} — version {ctx['questionnaire_version']}</div>",unsafe_allow_html=True)
    privacy=org.get('privacy_notice') or "Les informations recueillies sont utilisées pour le suivi de l’action et l’amélioration de la qualité des prestations."
    contact=org.get('privacy_contact') or org.get('general_email') or ''
    st.info(f"Données personnelles : {privacy}" + (f" Contact : {contact}" if contact else ''))
    questions=quality_questions(ENGINE,ctx['id']);existing=quality_existing_answers(ENGINE,ctx['id']);answers={}
    response_types={q.get('response_type') for q in questions}
    if 'SCALE_1_5' in response_types:
        st.info("Pour chaque affirmation notée de 1 à 5, la note 1 correspond au niveau d’appréciation le plus faible et la note 5 au niveau d’appréciation le plus élevé. Choisissez la note qui reflète le mieux votre appréciation.")
    if 'NPS_0_10' in response_types:
        st.info("Pour les questions notées de 0 à 10, 0 correspond au niveau le plus faible et 10 au niveau le plus élevé.")
    with st.form(f"quality_{ctx['id']}"):
        for qu in questions:
            label=qu['question_text'] + (' *' if qu.get('required') else '')
            current=existing.get(qu['id'])
            rt=qu['response_type']; key=f"q_{ctx['id']}_{qu['id']}"
            if rt=='SCALE_1_5':
                opts=['— Choisir —',1,2,3,4,5,'N/A'];idx=opts.index(current) if current in opts else 0
                v=st.selectbox(label,opts,index=idx,key=key,help=f"Code {qu['question_code']} — rubrique {qu['rubric_code']}")
                answers[qu['id']]=None if v=='— Choisir —' else v
            elif rt=='NPS_0_10':
                opts=['— Choisir —']+list(range(11));idx=opts.index(current) if current in opts else 0
                v=st.selectbox(label,opts,index=idx,key=key,help=f"Code {qu['question_code']}")
                answers[qu['id']]=None if v=='— Choisir —' else v
            elif rt=='CHOICE_SINGLE':
                lo=qu['question_text'].lower()
                if 'fréquence' in lo: opts=['— Choisir —','Jamais','Rarement','Parfois','Souvent','Très souvent']
                elif 'difficult' in lo or 'réclamation' in lo or 'aléa' in lo: opts=['— Choisir —','Non','Oui - difficulté / aléa','Oui - réclamation','Je souhaite être recontacté(e)']
                elif 'besoin complémentaire' in lo: opts=['— Choisir —','Non','Oui','Je ne sais pas encore']
                elif 'type d’intervention' in lo: opts=['— Choisir —','Formation','Bilan de compétences','VAE','Coaching','Mentorat','Autre']
                else: opts=['— Choisir —','Oui','Non','Non applicable']
                idx=opts.index(current) if current in opts else 0;v=st.selectbox(label,opts,index=idx,key=key,help=f"Code {qu['question_code']}");answers[qu['id']]=None if v=='— Choisir —' else v
            else:
                answers[qu['id']]=st.text_area(label,value=current if isinstance(current,str) else '',key=key,help=f"Code {qu['question_code']} — rubrique {qu['rubric_code']}")
        consent=st.checkbox("Je confirme que mes réponses correspondent à mon appréciation et j’ai pris connaissance de l’information sur les données personnelles.")
        submit=st.form_submit_button('ENREGISTRER MON QUESTIONNAIRE',type='primary',use_container_width=True)
    if submit:
        if not consent: st.error('Merci de confirmer avant l’enregistrement.');return
        try:
            actor='trainer' if ctx.get('trainer_id') else 'beneficiary';complete_quality_campaign(ENGINE,ctx['id'],answers,actor);st.success('Merci. Votre questionnaire a bien été enregistré.');st.balloons()
        except ValueError as ex: st.error(str(ex))
    footer()

def _crm_interests(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, tuple):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
        return [x.strip() for x in value.split(",") if x.strip()]
    return []

def _j4_report_file_uploader(label,*,types,key):
    """Constrain signalement uploads to 10 MB without reducing the separate
    business-document allowance (25 MB). Older Streamlit versions still use
    the server-wide 50 MB caption, but business validation always blocks >10.
    """
    import inspect
    options={'type':types,'key':key}
    try:
        if 'max_upload_size' in inspect.signature(st.file_uploader).parameters:
            options['max_upload_size']=10
    except (ValueError,TypeError):
        pass
    return st.file_uploader(label,**options)

# J4 - one permission-controlled notification drawer across the four workspaces.
def _j4_notification_drawer(role,actor_id):
    from workspace_notifications import inbox,mark_read
    rows=inbox(ENGINE,role,actor_id,unread_only=True,limit=100)
    st.sidebar.markdown(f"### 🔔 Notifications ({len(rows)})")
    show_history=st.sidebar.checkbox('Voir les notifications consultées',key=f'j4_history_{role}_{actor_id}')
    shown=inbox(ENGINE,role,actor_id,unread_only=False,limit=100) if show_history else rows
    with st.sidebar.expander('Boîte de notifications',expanded=bool(rows)):
        if not shown:st.caption('Aucune notification dans cette liste.')
        for notice in shown[:35]:
            prefix='À traiter' if notice['category']=='ACTION' else 'Information'
            st.caption(f"{prefix} · {notice['display_text']} · {format_app_datetime(notice['created_at'])}")
            if notice.get('read_at'):st.caption('Consultée')
            if st.button('Ouvrir',key=f'j4_open_{role}_{actor_id}_{notice["id"]}',use_container_width=True):
                try:
                    # Access is checked in mark_read AND at the destination.
                    mark_read(ENGINE,notice['id'],role,actor_id)
                    _j4_notification_destination(role,notice)
                    rerun()
                except PermissionError:st.warning('Cet accès a été retiré ; la notification n’est plus accessible.')

def _j4_notification_destination(role,notice):
    kind=notice['target_kind'];aid=notice.get('action_id')
    if role=='ADMIN':
        if kind in ('QUALITY','CAPA'):
            st.session_state['j4_jump_quality']=int(notice['target_id']) if kind=='QUALITY' else int(one(ENGINE,'SELECT quality_event_id FROM quality_event_actions WHERE id=:i',{'i':int(notice['target_id'])})['quality_event_id'])
            st.session_state['admin_workspace']=WORKSPACE_GENERAL
            st.session_state['nav']='Qualité'
        elif aid:
            st.session_state['admin_workspace']=WORKSPACE_ACTIONS
            st.session_state['admin_actions_view']='detail'
            st.session_state['nav']='Actions'
            st.session_state['p3_admin_action_id']=int(aid)
            st.session_state[f'p3_screen_admin_action_{aid}']='action_documents' if kind=='DOCUMENT' else 'action_parametres'
    elif role=='TRAINER':
        if kind=='PROFESSIONAL_DOCUMENT':
            st.session_state['_j6_next_trainer_view']='Mon dossier professionnel'
            return
        if kind=='QUALITY':st.session_state['j4_focus_event_id']=int(notice['target_id'])
        st.session_state['j4_trainer_action']=int(aid)
        st.session_state[f'p3_screen_trainer_{aid}']='reports' if kind=='QUALITY' else 'documents' if kind=='DOCUMENT' else 'planning' if notice['event_code']=='PLANNING_CHANGED' else 'overview'
    elif role=='BENEFICIARY':
        if kind=='QUALITY':st.session_state['j4_focus_event_id']=int(notice['target_id'])
        st.session_state['p3_beneficiary_action_id']=int(aid)
        st.session_state['p3_screen_beneficiary']='reports' if kind=='QUALITY' else 'documents' if kind=='DOCUMENT' else 'planning' if notice['event_code']=='PLANNING_CHANGED' else 'journey'
    elif role=='CLIENT':
        st.session_state['p4_client_action_id']=int(aid)
        st.session_state[f'p3_screen_client_{aid}']='documents' if kind=='DOCUMENT' else 'actions'

def _j4_portal_threads(role,subject_id,reports):
    from services import quality_portal_thread
    kind='TRAINER_REPORT' if role=='TRAINER' else 'BENEFICIARY_REPORT'
    highlighted=st.session_state.get('j4_focus_event_id')
    for report in reports[:25]:
        link=one(ENGINE,'SELECT quality_event_id FROM quality_source_links WHERE source_kind=:k AND source_id=:i',{'k':kind,'i':report['id']})
        if not link:continue
        ev_id=link['quality_event_id']
        try:thread=quality_portal_thread(ENGINE,ev_id,role,subject_id)
        except PermissionError:continue
        prefix='🔔 Réponse reçue : ' if ev_id==highlighted else 'Suivi de ma demande : '
        with st.expander(prefix+str(report['subject']),expanded=(ev_id==highlighted)):
            st.caption(f"Fiche {thread['public_id']} · État : {thread['status']}")
            if not thread['messages']:st.caption('Aucune réponse reçue à ce jour.')
            for message in thread['messages']:
                st.write(format_app_datetime(message['created_at'])+ ' — Administration : '+message['message'])

def _set_admin_workspace(destination):
    """Switch spaces only after explicit confirmation; do not alter rights."""
    if destination not in WORKSPACES:
        return
    st.session_state['admin_workspace']=destination
    st.session_state.pop('j5_pending_space',None)
    if destination != WORKSPACE_HOME:
        st.session_state['nav']=valid_route(destination,None)
    else:
        st.session_state.pop('nav',None)
    if destination==WORKSPACE_ACTIONS:
        st.session_state['admin_actions_view']='list'


def _request_admin_workspace(destination):
    current=st.session_state.get('admin_workspace',WORKSPACE_HOME)
    if current==destination:
        return
    # Forms buffer values before submit: require acknowledgement for a change
    # of workspace, rather than silently destroying an unsaved input.
    if current==WORKSPACE_HOME or st.session_state.get('nav') in ('Tableau de bord', 'Actions') and st.session_state.get('admin_actions_view','list')=='list':
        _set_admin_workspace(destination)
    else:
        st.session_state['j5_pending_space']=destination


def _admin_workspace_home():
    header('Clarté360 — Accueil administrateur','Choisissez votre espace de travail. Vous pourrez passer de l’un à l’autre sans vous déconnecter.')
    c1,c2=st.columns(2)
    with c1:
        st.subheader('Administration générale')
        st.write('Qualité et CAPA, relances, intervenants, clients/DRH, contacts, études et paramètres de l’organisme.')
        if st.button('Ouvrir Administration générale',key='j5_home_general',use_container_width=True,type='primary'):
            _set_admin_workspace(WORKSPACE_GENERAL);rerun()
    with c2:
        st.subheader('Gestion des actions')
        st.write('Créer ou importer une action, retrouver les dossiers, puis gérer les paramètres et les 12 rubriques de chaque action.')
        if st.button('Ouvrir Gestion des actions',key='j5_home_actions',use_container_width=True,type='primary'):
            _set_admin_workspace(WORKSPACE_ACTIONS);rerun()
    st.caption('La navigation ne modifie ni vos habilitations ni les données des dossiers.')
    footer()


def sidebar():
    st.sidebar.image(str(LOGO_PATH),width=70)
    st.sidebar.markdown(f"**{st.session_state.get('admin_name','Administrateur')}**")
    _j4_notification_drawer('ADMIN',st.session_state.get('admin_email'))
    workspace=st.session_state.get('admin_workspace',WORKSPACE_HOME)
    if workspace not in WORKSPACES:
        workspace=WORKSPACE_HOME
        st.session_state['admin_workspace']=workspace
    st.sidebar.markdown('#### Espaces administrateur')
    if st.sidebar.button('🏠 Accueil administrateur',key='j5_goto_home',use_container_width=True):
        _request_admin_workspace(WORKSPACE_HOME);rerun()
    if workspace!=WORKSPACE_GENERAL and st.sidebar.button('⚙️ Administration générale',key='j5_goto_general',use_container_width=True):
        _request_admin_workspace(WORKSPACE_GENERAL);rerun()
    if workspace!=WORKSPACE_ACTIONS and st.sidebar.button('📁 Gestion des actions',key='j5_goto_actions',use_container_width=True):
        _request_admin_workspace(WORKSPACE_ACTIONS);rerun()
    pending=st.session_state.get('j5_pending_space')
    if pending in WORKSPACES and pending!=workspace:
        st.sidebar.warning('Les saisies non enregistrées seront perdues si vous changez d’espace. Confirmez avant de poursuivre.')
        if st.sidebar.button('Confirmer le changement',key='j5_confirm_change',use_container_width=True):
            _set_admin_workspace(pending);rerun()
        if st.sidebar.button('Rester ici',key='j5_cancel_change',use_container_width=True):
            st.session_state.pop('j5_pending_space',None);rerun()
    pages=pages_for_workspace(workspace)
    if pages:
        st.sidebar.markdown('#### ' + ('Administration générale' if workspace==WORKSPACE_GENERAL else 'Gestion des actions'))
        current=valid_route(workspace,st.session_state.get('nav'))
        if st.session_state.get('nav')!=current:
            st.session_state['nav']=current
        page=st.sidebar.radio('Navigation',pages,key='nav',format_func=lambda value:ADMIN_PAGES.get(value,value))
    else:
        page='__home__'
    st.sidebar.divider()
    if workspace==WORKSPACE_GENERAL:
        if st.sidebar.button('🔄 MAJ WORKER — toutes les actions',use_container_width=True,help='Recalcule les files automatiques sans envoyer de doublons.'):
            try:
                result=refresh_all_worker_events(ENGINE,BASE_URL,TZ,st.session_state.get('admin_email') or 'admin')
                st.sidebar.success(f"Files préparées : {result.get('actions',0)} action(s), {result.get('teams_reminders',0)} nouveau(x) rappel(s) Teams, {result.get('teams_pending',0)} en attente. Aucun courriel envoyé par ce bouton.")
                if result.get('teams_failed',0):
                    st.sidebar.warning(f"{result['teams_failed']} rappel(s) Teams en échec / à vérifier dans le journal des communications (SMTP/worker).")
                if not mail_cfg().get('enabled'):
                    st.sidebar.warning('SMTP désactivé : les rappels Teams ne pourront pas partir tant que la messagerie ne sera pas opérationnelle.')
            except Exception as ex:
                _ui_incident('admin_refresh_worker_all',ex,subject='La mise à jour Worker',level='warning')
    if st.sidebar.button('Se déconnecter',use_container_width=True):
        _logout_persistent('ADMIN',['admin_email','admin_name','nav','admin_workspace','admin_actions_view','j5_pending_space'])
    return page


def admin_general_dashboard():
    header('Clarté360 — Administration générale','Pilotage de l’organisme, des intervenants, des clients et de la Qualité')
    st.subheader('Domaines de gestion')
    entries=[('Qualité','Fiches à traiter, enquêtes et CAPA'),('Relances','Relances et régularisations'),
             ('Intervenants / Partenaires','Dossiers, qualifications et prestations'),
             ('Espace Client / DRH','Comptes et habilitations Clients'),
             ('Contacts / Prospects','Contacts et prospection'),('Études PIP/O*NET','Études et référencement'),
             ('Paramètres','Organisme et configuration générale')]
    for i in range(0,len(entries),2):
        cols=st.columns(2)
        for column,(route,description) in zip(cols,entries[i:i+2]):
            with column:
                st.markdown('**'+route+'**')
                st.caption(description)
                if st.button('Ouvrir '+route,key='j5_general_link_'+str(i)+route,use_container_width=True):
                    st.session_state['_next_nav']=route;rerun()
    st.caption('Les listes d’actions et la création/import figurent exclusivement dans Gestion des actions.')
    footer()

def create_action_screen(prefill=None,participants_prefill=None):
    # Lors d'un import, le brouillon reste en session jusqu'à création ou annulation.
    # Cela évite la perte des champs lors d'un rerun Streamlit ou d'une frappe sur Entrée.
    if st.session_state.get('import_create_active'):
        prefill = st.session_state.get('import_prefill') or prefill
        participants_prefill = st.session_state.get('import_parts') or participants_prefill

    p=prefill or {}
    imported_parts=participants_prefill or []

    header('Clarté360 — Nouvelle action','Création et paramétrage d’une action')

    if st.session_state.get('import_create_active'):
        st.info("Action préremplie depuis la base Excel. Les données importées restent conservées tant que l’action n’est pas créée ou que vous n’annulez pas l’import.")
        if st.button("Annuler cet import et repartir sur une action vide", key="cancel_import_draft"):
            for k in ['import_create_active','import_prefill','import_parts']:
                st.session_state.pop(k,None)
            rerun()

    # Compatibilité avec le mapping actuel excel_import.py : date_start/date_end
    raw_start = p.get('start_date') or p.get('date_start')
    raw_end = p.get('end_date') or p.get('date_end')
    try:
        start_default = date.fromisoformat(str(raw_start)[:10]) if raw_start else date.today()
    except Exception:
        start_default = date.today()
    try:
        end_default = date.fromisoformat(str(raw_end)[:10]) if raw_end else date.today()
    except Exception:
        end_default = date.today()

    mode_options=['INTRA','INTER','INDIVIDUEL']
    mode_default=(p.get('mode') or 'INTRA').upper()
    if mode_default not in mode_options:
        mode_default='INTRA'

    expected_default = int(p.get('expected_participants') or len(imported_parts) or 1)
    prestation_labels={'Formation':'FORMATION','Bilan de compétences':'BILAN_COMPETENCES','VAE':'VAE','Coaching':'COACHING','Mentorat':'MENTORAT','Autre':'AUTRE'}
    imported_pt=(p.get('prestation_type') or 'FORMATION').upper()
    default_pt=next((k for k,v in prestation_labels.items() if v==imported_pt),'Formation')
    prestation_label=st.selectbox('Type de prestation *',list(prestation_labels),index=list(prestation_labels).index(default_pt),key='new_action_prestation_type')
    prestation_type=prestation_labels[prestation_label]; nature=prestation_label
    modality_codes=allowed_delivery_modes(prestation_type)
    modality_labels={delivery_mode_label(x):x for x in modality_codes}
    imported_mod=p.get('delivery_mode'); imported_mod=imported_mod if imported_mod in modality_codes else modality_codes[0]

    # CRM-0 : recherche/rattachement du donneur d'ordre avant création de l'action.
    crm_prefill_id=st.session_state.get('crm_prefill_contact_id') or p.get('crm_contact_id')
    if not crm_prefill_id and p.get('crm_contact_public_id'):
        imported_contact=one(ENGINE,'SELECT id FROM crm_contacts WHERE public_id=:r',
                             {'r':p.get('crm_contact_public_id')})
        crm_prefill_id=imported_contact['id'] if imported_contact else None
    crm_prefill=one(ENGINE,'SELECT * FROM crm_contacts WHERE id=:i',{'i':crm_prefill_id}) if crm_prefill_id else None
    crm_mode=st.radio('Le client existe déjà dans le CRM ?', ['Oui','Non'],index=0 if crm_prefill else 1,horizontal=True,key='new_action_crm_mode')
    selected_crm=None; create_crm_from_action=False
    if crm_mode=='Oui':
        search=st.text_input('Rechercher le client / prospect',value='',placeholder='Nom, entreprise, e-mail ou téléphone',key='new_action_crm_search')
        crm_rows=find_crm_contacts(ENGINE,search,100)
        if crm_prefill and all(x['id']!=crm_prefill['id'] for x in crm_rows): crm_rows=[crm_prefill]+crm_rows
        if crm_rows:
            crm_opts={'— Sélectionner explicitement un donneur d’ordre —':None,
                **{f"{x['first_name']} {x['last_name']} — {x.get('company') or 'Particulier'} — {x['email']}":x for x in crm_rows}}
            default_label=next((k for k,v in crm_opts.items() if crm_prefill and v and v['id']==crm_prefill['id']),
                               '— Sélectionner explicitement un donneur d’ordre —')
            crm_label=st.selectbox('Client / prospect CRM',list(crm_opts),index=list(crm_opts).index(default_label),key='new_action_crm_pick')
            selected_crm=crm_opts[crm_label]
            if selected_crm:
                st.caption(f"Sélectionné : {selected_crm['public_id']} — centres d’intérêt : {', '.join(_crm_interests(selected_crm.get('interests_json'))) or '—'}")
        else: st.warning('Aucun contact trouvé. Passez sur « Non » pour créer une nouvelle fiche CRM avec l’action.')
    else:
        create_crm_from_action=True
        st.caption('Un donneur d’ordre et un contact de référence sont obligatoires : la fiche CRM0 sera créée avec l’action, sans droit Client/DRH automatique.')

    # J17 — rattachement explicite au catalogue dès la création. Jamais de première prestation implicite.
    creation_services=list_services(ENGINE,active_only=True)
    creation_service_map={f"{x['name']} — {x['service_code']}":x for x in creation_services}
    imported_title_hint=(p.get('title') or '').strip()
    if imported_title_hint:
        matches=find_service_matches(ENGINE,imported_title_hint,5)
        if matches:
            st.caption('Prestations proches détectées pour l’intitulé importé : '+ ' · '.join(x['name'] for x in matches))
    with st.expander('Créer rapidement une prestation absente du catalogue',expanded=False):
        fams=list_service_families(ENGINE,active_only=True)
        if fams:
            with st.form('j17_quick_service_create'):
                qs_name=st.text_input('Nom de la nouvelle prestation',value=imported_title_hint)
                qs_code=st.text_input('Code prestation')
                fmap={x['name']:x['id'] for x in fams}; qs_fam=st.selectbox('Famille',list(fmap))
                qs_scope=st.selectbox('Portée',['MIXTE','INDIVIDUEL','COLLECTIF'])
                qs_go=st.form_submit_button('Créer la prestation')
            if qs_go:
                try:
                    sid=add_service(ENGINE,qs_code,qs_name,family_id=fmap[qs_fam],delivery_scope=qs_scope,actor=st.session_state.admin_email,source='MANUEL')
                    st.session_state['_j17_new_service_id']=sid; st.success('Prestation créée. Elle est maintenant disponible pour cette action.'); rerun()
                except ValueError as ex: st.error(str(ex))
        else: st.warning('Créez d’abord une famille de prestations dans Intervenants / Partenaires > Prestations.')

    with st.form('new_action', enter_to_submit=False):
        action_no=st.text_input('N° D’ACTION *',value=p.get('action_no','')).strip().upper()
        title=st.text_input('Intitulé *',value=p.get('title',''))
        subtitle=st.text_input('Intitulé complémentaire',value=p.get('subtitle') or '')
        service_labels=['— Prestation non encore rattachée —']+list(creation_service_map)
        service_idx=0; wanted_service=st.session_state.get('_j17_new_service_id')
        if wanted_service:
            service_idx=next((i for i,k in enumerate(service_labels) if k in creation_service_map and int(creation_service_map[k]['id'])==int(wanted_service)),0)
        action_service_label=st.selectbox('Prestation Clarté360 liée à cette action',service_labels,index=service_idx,help='Le titre de l’action reste libre. Le rattachement à une prestation est explicite et n’est jamais choisi automatiquement.')
        cqs1,cqs2=st.columns(2)
        action_min_level=cqs1.selectbox('Niveau humain minimum requis',[0,1,2,3,4],index=3,format_func=lambda x:f"{x}/4 — {QUALIFICATION_LEVEL_LABELS[x]}")
        action_require_criteria=cqs2.checkbox('Exiger tous les critères obligatoires démontrés',value=False)

        c1,c2=st.columns(2)
        start_date=c1.date_input('Date de début',value=start_default,format=app_date_input_format())
        end_date=c2.date_input('Date de fin',value=end_default,format=app_date_input_format())

        c1,c2,c3,c4=st.columns(4)
        mode=c1.selectbox('Organisation',mode_options,index=mode_options.index(mode_default))
        planned=c2.number_input('Durée contractuelle prévue (h)',min_value=0.0,step=.5,value=float(p.get('planned_hours') or 0))
        expected=c3.number_input('Nombre prévu de stagiaires',min_value=1,step=1,value=expected_default)
        group=c4.text_input('Code de groupe / session INTER',value=p.get('group_code') or '')

        c1,c2=st.columns(2)
        selected_client_name=((selected_crm.get('company') or f"{selected_crm.get('first_name','')} {selected_crm.get('last_name','')}").strip() if selected_crm else None)
        client=c1.text_input('Client / entreprise *',value=selected_client_name or p.get('client_name') or '',
                              disabled=bool(selected_crm),help='L’identité sélectionnée dans le CRM prime : aucun rattachement ne repose sur une simple similitude de nom.')
        client_type_default='Professionnel' if selected_crm and selected_crm.get('company') else ('Particulier' if selected_crm else 'Non précisé')
        client_types=['Non précisé','Professionnel','Particulier']; client_type=c2.selectbox('Type client',client_types,index=client_types.index(client_type_default))
        crm_new_fn=crm_new_ln=crm_new_email=crm_new_phone=crm_new_job=''
        if crm_mode=='Non' and create_crm_from_action:
            st.markdown('**Nouvelle fiche CRM liée à cette action**')
            r1,r2=st.columns(2); crm_new_fn=r1.text_input('Prénom contact CRM *'); crm_new_ln=r2.text_input('Nom contact CRM *')
            r1,r2=st.columns(2); crm_new_email=r1.text_input('E-mail contact CRM *'); crm_new_phone=r2.text_input('Téléphone contact CRM')
            crm_new_job=st.text_input('Fonction contact CRM')

        orgs=list_organizations(ENGINE,active_only=True)
        org_opts={o['name']:o['id'] for o in orgs}
        org_labels=list(org_opts)
        imported_org=p.get('organization_id')
        org_index=next((i for i,lab in enumerate(org_labels) if org_opts[lab]==imported_org),0)
        org_label=st.selectbox('Organisme',org_labels,index=org_index)
        organization_id=org_opts[org_label]
        agencies=list_agencies(ENGINE,organization_id,active_only=True)
        agency_opts={'— Siège / aucune agence —':None,**{g['name']:g['id'] for g in agencies}}
        agency_label=st.selectbox('Agence / établissement',list(agency_opts))
        agency_id=agency_opts[agency_label]

        st.markdown('**Modules activés pour cette action**')
        m1,m2,m3,m4,m5=st.columns(5)
        use_attendance=m1.checkbox('Émargement',value=True)
        use_hot=m2.checkbox('Évaluation à chaud',value=False)
        use_cold=m3.checkbox('Évaluation à froid',value=False)
        use_trainer=m4.checkbox('Retour intervenant',value=False)
        use_teams=m5.checkbox('Gestion Teams',value=False,help='À cocher dès la création si les rendez-vous Teams doivent être gérés automatiquement. Le lieu/modalité reste libre et n’active jamais Teams à lui seul.')

        trainers=list_trainers(ENGINE,active_only=True)
        trainer_opts={'— Aucun intervenant référencé —':None,**{f"{t['full_name']} — {t.get('email') or 'sans email'}":t['id'] for t in trainers}}
        trainer_labels=list(trainer_opts)
        imported_trainer=(p.get('trainer_name') or '').strip().lower()
        trainer_index=0
        if imported_trainer:
            for i,lab in enumerate(trainer_labels):
                if imported_trainer in lab.lower():
                    trainer_index=i
                    break

        c1,c2,c3=st.columns(3)
        trainer_label=c1.selectbox('Intervenant référent',trainer_labels,index=trainer_index)
        modality_label=c2.selectbox('Modalité',list(modality_labels),index=modality_codes.index(imported_mod),help='Liste contrôlée selon le type de prestation.')
        delivery_mode=modality_labels[modality_label]
        location=c3.text_input('Lieu / précision',value=p.get('location') or '',help='Adresse, salle, site client, Teams ou précision utile.')

        admins=q(ENGINE,'SELECT email,full_name FROM admins WHERE active=1 ORDER BY full_name,email')
        admin_opts={f"{x.get('full_name') or x['email']} — {x['email']}":x['email'] for x in admins}
        cur_admin=next((k for k,v in admin_opts.items() if v==st.session_state.get('admin_email')),list(admin_opts)[0] if admin_opts else '')
        admin_label=st.selectbox('Administrateur référent',list(admin_opts),index=list(admin_opts).index(cur_admin) if cur_admin in admin_opts else 0)
        admin_email=admin_opts.get(admin_label,st.session_state.get('admin_email',''))
        notes=st.text_area('Observations')

        if imported_parts:
            st.markdown('### Participant(s) détecté(s) dans la base')
            st.caption("Ces fiches seront créées automatiquement dans l’action au moment où vous cliquerez sur « Créer l’action ».")
            preview_rows=[]
            for x in imported_parts:
                preview_rows.append({
                    'Nom':x.get('last_name') or '',
                    'Nom de naissance':x.get('birth_name') or '',
                    'Prénom':x.get('first_name') or '',
                    'Date de naissance':x.get('birth_date') or '',
                    'Email':x.get('email') or '',
                    'Entreprise':x.get('company_name') or '',
                    'Téléphone':x.get('phone') or '',
                    'N° action':x.get('individual_action_no') or action_no,
                })
            st.dataframe(pd.DataFrame(preview_rows),use_container_width=True,hide_index=True)
        elif st.session_state.get('import_create_active'):
            st.warning("Aucun participant n’a été détecté dans la source Excel pour cette action. L’action peut être créée, mais aucun stagiaire ne sera ajouté automatiquement.")

        ok=st.form_submit_button('Créer l’action',type='primary')

    if ok:
        try:
            action_no=validate_action_no(action_no)
            title=validate_short_text(title,'Intitulé',required=True,max_len=200)
            validate_date_range(start_date,end_date)
        except ValueError as ex:
            st.error(str(ex)); return
        if not action_no or not title:
            st.error('Le n° d’action et l’intitulé sont obligatoires.')
        elif one(ENGINE,'SELECT id FROM actions WHERE action_no=:n',{'n':action_no}):
            st.error('Ce numéro d’action existe déjà.')
        elif crm_mode=='Oui' and not selected_crm:
            st.error('Sélectionnez le contact Client/Donneur d’ordre dans le CRM.')
        elif crm_mode=='Non' and (not crm_new_fn.strip() or not crm_new_ln.strip() or not crm_new_email.strip()):
            st.error('Le nouveau donneur d’ordre nécessite un contact complet : prénom, nom et e-mail.')
        else:
            try:
                aid=create_action_with_client(ENGINE,{
                'action_no':action_no,
                'title':title,
                'subtitle':subtitle or None,
                'nature':nature,
                'mode':mode,
                'delivery_mode':delivery_mode,
                'client_name':client or None,
                'client_type':client_type,
                'group_code':group or None,
                'planned_hours':planned,
                'expected_participants':int(expected),
                'admin_email':admin_email,
                'trainer_name':p.get('trainer_name') or None,
                'trainer_email':p.get('trainer_email') or None,
                'location':location or None,
                'notes':notes or None,
                'source':p.get('source') or 'SAISIE MANUELLE'
                },st.session_state.admin_email,crm_contact_id=selected_crm['id'] if selected_crm else None,
                new_crm_contact={'first_name':crm_new_fn,'last_name':crm_new_ln,'email':crm_new_email,
                    'phone':crm_new_phone or None,'job_title':crm_new_job or None,'company':client or None}
                    if crm_mode=='Non' else None)
            except (ValueError,InputValidationError) as ex:
                st.error(str(ex));return

            # J17 — rattachement prestation/action immédiatement après création.
            selected_action_service=creation_service_map.get(action_service_label)
            if selected_action_service:
                set_action_service_requirement(ENGINE,aid,selected_action_service['id'],st.session_state.admin_email,action_min_level,action_require_criteria)
            st.session_state.pop('_j17_new_service_id',None)

            # J7: l’identité client et sa liaison CRM sont déjà enregistrées dans
            # la même transaction que l’action, sans ouverture automatique d’accès.
            st.session_state.pop('crm_prefill_contact_id',None)

            if trainer_opts.get(trainer_label):
                chosen_tid=trainer_opts[trainer_label]
                pp=professional_person_for_trainer(ENGINE,chosen_tid)
                if pp and selected_action_service:
                    aok,amsg=assign_action_professional(ENGINE,aid,pp['professional_person_id'],st.session_state.admin_email,role='REFERENT',is_referent=True)
                    if not aok:
                        st.session_state['_j17_creation_qualification_notice']=f"Intervenant référent non affecté : {amsg} Ouvrez l’onglet Intervenants de l’action pour étudier/valider sa qualification."
                else:
                    # Compatibilité : sans prestation liée, aucune qualification ne peut être conclue.
                    assign_trainer(ENGINE,aid,chosen_tid,st.session_state.admin_email)

            safe_set_action_modules(
                ENGINE,aid,prestation_type,use_attendance,use_hot,use_cold,use_trainer,
                organization_id,agency_id,st.session_state.admin_email
            )
            if use_teams:
                set_generic_action_module(ENGINE,aid,'TEAMS',True,st.session_state.admin_email)
            execute(ENGINE,'UPDATE actions SET start_date=:s,end_date=:e WHERE id=:a',
                    {'s':start_date.isoformat(),'e':end_date.isoformat(),'a':aid})
            if p.get('client_quality_email') or p.get('client_training_email') or p.get('quality_contact_name') or p.get('training_contact_name'):
                execute(ENGINE,'''UPDATE actions SET quality_contact_name=:qn,client_quality_email=:qe,training_contact_name=:tn,client_training_email=:te,training_contact_phone=:tp WHERE id=:a''',
                    {'qn':p.get('quality_contact_name'),'qe':p.get('client_quality_email'),'tn':p.get('training_contact_name'),'te':p.get('client_training_email'),'tp':p.get('training_contact_phone'),'a':aid})

            pins=[]
            for participant_data in imported_parts:
                pdata=participant_data.copy()
                # Le n° de l'action importée fait foi si la fiche participant ne le contient pas.
                if not pdata.get('individual_action_no'):
                    pdata['individual_action_no']=action_no
                pid,pin=add_participant(ENGINE,aid,pdata,st.session_state.admin_email)
                pins.append((pid,pin))

            # Le brouillon d'import n'est effacé qu'après création réussie.
            for k in ['import_create_active','import_prefill','import_parts']:
                st.session_state.pop(k,None)

            st.session_state.selected_action=aid
            st.session_state['p3_admin_action_id']=aid
            if imported_parts:
                st.success(f'Action créée avec {len(imported_parts)} participant(s) importé(s).')
            else:
                st.success('Action créée. Étape suivante : ajoutez les participants, puis les intervenants et le calendrier. La validation finale sera proposée lorsque le dossier sera cohérent.')
            st.session_state['_next_nav']='Actions'
            rerun()
    footer()

def import_screen():
    header('Clarté360 — Import','Importer une action depuis la base de gestion de l’organisme ou depuis un fichier CSV')
    orgs=list_organizations(ENGINE,active_only=True)
    if not orgs:
        st.warning('Aucun organisme actif n’est configuré.')
        footer(); return
    org_opts={o['name']:o['id'] for o in orgs}
    org_label=st.selectbox('Organisme porteur de l’action',list(org_opts),key='import_org')
    oid=org_opts[org_label]
    profiles=list_import_profiles(ENGINE,oid,active_only=True)
    tab1,tab2=st.tabs(['Base de gestion de l’organisme','CSV participants'])
    with tab1:
        if not profiles:
            st.warning("Aucun profil d’import actif pour cet organisme. Créez-le dans Paramètres > Imports.")
        else:
            profile_opts={p['name']:p['id'] for p in profiles}
            plabel=st.selectbox("Profil d’import",list(profile_opts),key='import_profile')
            profile=get_import_profile(ENGINE,profile_opts[plabel])
            store_key=f"PROFILE_{profile['id']}"
            info=source_info(store_key)
            st.caption(f"Clé action : {profile['action_key']} · Onglets : {profile['action_sheet']} / {profile['participant_sheet']}")
            if info.get('snapshot_path'):
                st.info(f"Copie de travail mémorisée : {info.get('original_name') or Path(info['snapshot_path']).name}. Vous pouvez rechercher plusieurs actions sans recharger le fichier.")
            f=st.file_uploader('Charger / actualiser la base de gestion (.xlsm/.xlsx)',type=['xlsm','xlsx'],key=f"profile_file_{profile['id']}")
            mode=st.selectbox('Mode de l’action',['INTRA','INTER','INDIVIDUEL'],key=f"profile_mode_{profile['id']}")
            n=st.text_input("N° d’action à rechercher",key=f"profile_no_{profile['id']}").strip().upper()
            if st.button('Lire l’action',type='primary',key=f"read_profile_{profile['id']}") and n:
                try:
                    if f:
                        raw=f.getvalue(); save_uploaded_source(store_key,f.name,raw)
                    else:
                        raw,_=read_snapshot(store_key)
                    if not raw:
                        st.error("Chargez la base une première fois. Sa copie de travail sera ensuite conservée sur le VPS.")
                    else:
                        data,parts=read_action_xlsm(raw,n,profile,mode)
                        if not data:
                            st.error('Action introuvable dans la source configurée.')
                        else:
                            data['organization_id']=oid
                            st.session_state.import_prefill=data
                            st.session_state.import_parts=parts
                            st.success(f"Action trouvée — {len(parts)} participant(s) détecté(s). Source métier : {data.get('source_sheet')}.")
                except Exception as e:
                    _ui_incident('import_excel',e,subject='La lecture du fichier Excel')
            current=st.session_state.get('import_prefill') or {}
            if current.get('import_profile_id')==profile.get('id'):
                st.json({k:v for k,v in current.items() if k not in ['default_start','default_end']})
                if st.button('Créer cette action dans Clarté360 — Gestion des actions',key=f"create_profile_{profile['id']}"):
                    st.session_state.import_create_active=True;st.session_state['_next_nav']='Nouvelle action';rerun()
    with tab2:
        st.caption('Colonnes reconnues : no_action, nom, nom_naissance, prenom, date_naissance, email, matricule, entreprise, telephone.')
        sample='no_action,nom,nom_naissance,prenom,date_naissance,email,matricule,entreprise,telephone\nACTION001,DURAND,,Marie,1985-02-14,marie@example.com,M001,SOCIETE EXEMPLE,0600000000\n'
        st.download_button('Télécharger un modèle CSV',sample.encode(),'modele_participants.csv','text/csv')
        cf=st.file_uploader('CSV participants',type=['csv'],key='csvp')
        if cf:
            try:
                df=pd.read_csv(cf,sep=None,engine='python',dtype=str).fillna('');st.dataframe(df,use_container_width=True)
                action_no=st.text_input('N° action auquel rattacher ces participants').strip().upper();a=one(ENGINE,'SELECT * FROM actions WHERE action_no=:n',{'n':action_no}) if action_no else None
                if st.button('Importer les participants dans cette action'):
                    if not a: st.error('Action introuvable.')
                    elif a.get('organization_id') and a.get('organization_id')!=oid: st.error("Cette action appartient à un autre organisme.")
                    else:
                        count=0
                        for _,r in df.iterrows():
                            last=(r.get('nom') or r.get('NOM') or '').strip();first=(r.get('prenom') or r.get('PRENOM') or '').strip()
                            if not last or not first: continue
                            add_participant(ENGINE,a['id'],{'individual_action_no':(r.get('no_action') or action_no).strip(),'last_name':last,'birth_name':(r.get('nom_naissance') or '').strip() or None,'first_name':first,'birth_date':(r.get('date_naissance') or '').strip() or None,'email':(r.get('email') or '').strip() or None,'employee_id':(r.get('matricule') or '').strip() or None,'company_name':(r.get('entreprise') or '').strip() or None,'phone':(r.get('telephone') or '').strip() or None},st.session_state.admin_email);count+=1
                        st.success(f'{count} participant(s) importé(s).')
            except Exception as e: _ui_incident('import_csv',e,subject='La lecture du fichier CSV')
    footer()

def _j5_action_participants_summary():
    """One bounded query for totals and first participant; no 200x N+1 lookup."""
    rows=q(ENGINE,"""SELECT a.id action_id,
        (SELECT COUNT(*) FROM participants p WHERE p.action_id=a.id) participant_count,
        (SELECT TRIM(COALESCE(p.first_name,'') || ' ' || COALESCE(p.last_name,''))
          FROM participants p WHERE p.action_id=a.id ORDER BY p.id LIMIT 1) first_participant
        FROM actions a""")
    return {int(r['action_id']):r for r in rows}


def _j5_action_table(rows,*,with_open=False):
    st.caption('Vue de restitution : sélectionnez un dossier ci-dessous pour le modifier dans ses rubriques.')
    st.dataframe(pd.DataFrame([{
        'Action':a['action_no'], 'Intitulé':a['title'],
        'Client':a.get('client_name') or '—',
        'Stagiaires':int(a.get('participant_count') or 0),
        'Premier stagiaire':a.get('first_participant') or '—',
        'Début':a.get('start_date') or '—',
        'Statut':normalize_action_status(a.get('status')),
    } for a in rows]),use_container_width=True,hide_index=True)


def dashboard():
    header('Clarté360 — Gestion des actions','Tableau de bord des dossiers et interventions')
    acts=q(ENGINE,'SELECT id,status FROM actions')
    counts={s:sum(normalize_action_status(a['status'])==s for a in acts) for s in ('ACTIVE','BROUILLON','PLANIFIEE','ARCHIVEE')}
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Actions actives',counts['ACTIVE'])
    c2.metric('Brouillons',counts['BROUILLON'])
    c3.metric('Planifiées',counts['PLANIFIEE'])
    c4.metric('Archivées',counts['ARCHIVEE'])
    st.caption('Les archives sont exclues par défaut de la liste des actions ; les brouillons restent accessibles.')
    c1,c2,c3=st.columns(3)
    if c1.button('📁 Rechercher ou ouvrir une action',key='j5_db_list',use_container_width=True,type='primary'):
        st.session_state['admin_actions_view']='list';st.session_state['_next_action_view']='list';st.session_state['_next_nav']='Actions';rerun()
    if c2.button('➕ Nouvelle action',key='j5_db_create',use_container_width=True):
        st.session_state['_next_nav']='Nouvelle action';rerun()
    if c3.button('📥 Importer une action',key='j5_db_import',use_container_width=True):
        st.session_state['_next_nav']='Importer une action';rerun()
    st.subheader('Actions récemment créées')
    actions=search_actions(ENGINE,'',include_archived=False)
    if actions:
        summary=_j5_action_participants_summary()
        rows=action_list_rows(actions[:5],summary)
        _j5_action_table(rows)
    else:st.info('Aucune action hors archives.')
    footer()


def actions_list():
    """List first, then one action and its original 12 handlers; no duplicate menu."""
    if st.session_state.get('admin_actions_view')!='detail':
        header('Clarté360 — Gestion des actions','Rechercher, créer, importer ou reprendre un dossier')
        top1,top2=st.columns(2)
        if top1.button('➕ Nouvelle action',key='j5_actions_create',use_container_width=True):
            st.session_state['_next_nav']='Nouvelle action';rerun()
        if top2.button('📥 Importer une action',key='j5_actions_import',use_container_width=True):
            st.session_state['_next_nav']='Importer une action';rerun()
        st.subheader('Liste des actions')
        c1,c2=st.columns([4,1])
        term=c1.text_input('Recherche : action, intitulé, client ou stagiaire',key='j5_actions_query')
        include_archived=c2.checkbox('Afficher les archives',value=False,key='j5_show_archives')
        all_rows=search_actions(ENGINE,term,include_archived=True)
        summary=_j5_action_participants_summary()
        all_rows=action_list_rows(all_rows,summary)
        years=['Toutes']+sorted({str(a.get('start_date') or '')[:4] for a in all_rows if a.get('start_date')},reverse=True)
        prestations=['Toutes']+sorted({str(a.get('prestation_type')) for a in all_rows if a.get('prestation_type')})
        c1,c2,c3=st.columns(3)
        status=c1.selectbox('Statut',['Tous','ACTIVE','A_CLOTURER','PLANIFIEE','BROUILLON','CLOTUREE','ARCHIVEE'],key='j5_filter_status')
        year=c2.selectbox('Année',years,key='j5_filter_year')
        prestation=c3.selectbox('Type de prestation',prestations,key='j5_filter_pt')
        result=filter_sort_actions(all_rows,include_archived=include_archived,status=status,year=year,prestation=prestation)
        if status=='ARCHIVEE' and not include_archived:
            st.info('Cochez « Afficher les archives » pour consulter les dossiers archivés.')
        st.caption(f'{len(result)} action(s) trouvée(s), classées par statut puis date récente. Archives masquées par défaut.')
        if not result:
            st.info('Aucune action ne correspond aux filtres.')
            footer();return
        pcol,ccol=st.columns([2,1]);size=pcol.selectbox('Actions par page',[25,50],key='j5_page_size')
        maxpage=max(1,(len(result)+size-1)//size)
        if int(st.session_state.get('j5_page_index') or 1)>maxpage:
            st.session_state['j5_page_index']=maxpage
        page=ccol.number_input('Page',min_value=1,max_value=maxpage,value=1,key='j5_page_index')
        visible,page,total=page_slice(result,page=page,size=size)
        st.caption(f'Page {page} sur {total}')
        _j5_action_table(visible)
        labels={a['id']:action_label(a) for a in visible}
        chosen=st.selectbox('Sélectionner une action à ouvrir',list(labels),key='j5_action_select',format_func=lambda n:labels[n])
        if st.button('OUVRIR / GÉRER CETTE ACTION',key='j5_actions_open',type='primary'):
            st.session_state['selected_action']=chosen
            st.session_state['p3_admin_action_id']=chosen
            st.session_state['admin_actions_view']='detail'
            rerun()
        footer();return
    # Detail only: one contextual navigation, without duplicating the action listing.
    st.sidebar.markdown('#### Dossier ouvert')
    if st.sidebar.button('← Retour à la liste des actions',key='j5_return_list',use_container_width=True):
        st.session_state['admin_actions_view']='list';rerun()
    all_rows=search_actions(ENGINE,'',include_archived=True)
    if not all_rows:
        st.warning('Aucune action existante.');st.session_state['admin_actions_view']='list';return
    summary=_j5_action_participants_summary()
    all_rows=action_list_rows(all_rows,summary)
    action_ids=[a['id'] for a in all_rows]
    remembered=authorized_action_choice(action_ids,st.session_state.get('p3_admin_action_id'))
    if remembered is None:
        st.session_state['admin_actions_view']='list'
        st.warning('Cette action n’est plus accessible. Revenez à la liste.')
        return
    labels={a['id']:action_label(a) for a in all_rows}
    aid=st.sidebar.selectbox('Choisir une action',action_ids,key='p3_admin_action_id',
        format_func=lambda value:labels.get(value,str(value)))
    st.session_state.selected_action=aid
    st.caption('Gestion du dossier sélectionné — pour changer de dossier, utilisez le sélecteur latéral ou revenez à la liste.')
    action_detail(aid)
    a=one(ENGINE,'SELECT * FROM actions WHERE id=:a',{'a':aid})
    if st.session_state.get(f'p3_screen_admin_action_{aid}')=='action_parametres':
        with st.expander('🗑️ Supprimer un dossier d’essai (contrôle renforcé)'):
            st.warning("Réservé exclusivement aux données fictives. Les dossiers réels, preuves réglementaires et données confidentielles ne doivent jamais être effacés par ce circuit.")
            # Recovery is a separate, explicit administrative decision. Never repair silently.
            recovery=st.button('Vérifier les purges interrompues',key=f'purge_recovery_{aid}')
            if recovery:
                states=recover_action_purges(ENGINE)
                st.info(f"Journal contrôlé : {len(states)} opération(s) à examiner.")
                if any(row.get('status')=='ERROR' for row in states):
                    st.error('Restauration ou nettoyage à reprendre avant toute purge.')
            try:
                preview=preview_action_purge(ENGINE,aid)
            except Exception as exc:
                preview=None
                st.error('Prévisualisation indisponible : '+str(exc))
            if preview:
                st.write(f"Action : {preview['action_no']} — {preview['title']}")
                st.caption('Inventaire préalable de toutes les dépendances connues. Aucun fichier ne sera touché avant une deuxième confirmation.')
                st.dataframe([{'Élément':key,'Enregistrements':value} for key,value in sorted(preview['counts'].items())],
                    hide_index=True,use_container_width=True)
                st.caption(f"Fichiers à retirer si non partagés : {sum(bool(x['exists']) for x in preview['files'])} ; documents partagés préservés : {preview['shared_files_kept']}.")
                st.caption('Les anciennes fiches Qualité sans action ne sont ni rattachées ni supprimées par supposition.')
                try:
                    orphans=legacy_quality_orphans(ENGINE)
                    st.caption('Fiches historiques sans action (lecture seule) : '+', '.join(f'{key}={value}' for key,value in orphans.items()))
                except Exception:
                    pass
                st.markdown('**Étape 1 — Attester qu’il s’agit exclusivement d’un essai fictif**')
                st.caption('La référence ou le titre contenant ESSAI ne constitue jamais une preuve suffisante.')
                evidence=st.text_area('Justification et contrôle de l’absence de données réelles (au moins 24 caractères)',key=f'purge_evidence_{aid}')
                certification=st.text_input(f"Taper exactement : JE CERTIFIE ESSAI {a['action_no']}",key=f'purge_certification_{aid}')
                password=st.text_input('Mot de passe administrateur pour certifier',type='password',key=f'purge_cert_pw_{aid}')
                if st.button('Enregistrer mon attestation d’essai',key=f'purge_cert_button_{aid}'):
                    ok,msg=certify_test_action(ENGINE,aid,st.session_state.admin_email,
                        evidence=evidence,confirmation=certification,password=password)
                    if ok: st.success(msg);rerun()
                    else: st.error(msg)
                st.markdown('**Étape 2 — Confirmer après avoir relu les dépendances**')
                confirm=st.text_input(f"Taper exactement : SUPPRIMER ESSAI {a['action_no']}",key=f'purge_final_confirm_{aid}')
                pw=st.text_input('Mot de passe administrateur avant suppression',type='password',key=f'delacpw{aid}')
                if st.button('🗑️ SUPPRIMER DÉFINITIVEMENT CE DOSSIER FICTIF',key=f'delac{aid}'):
                    if not admin_password_ok(ENGINE,st.session_state.admin_email,pw):
                        st.error('Mot de passe administrateur incorrect.')
                    else:
                        ok,msg=purge_action(ENGINE,aid,st.session_state.admin_email,
                            confirmation=confirm,preview_fingerprint=preview['fingerprint'])
                        if ok:
                            st.session_state.pop('selected_action',None)
                            st.success(msg);rerun()
                        else:st.error(msg)
    footer()

def action_detail(aid):
    a=one(ENGINE,'SELECT * FROM actions WHERE id=:a',{'a':aid});pr=action_progress(ENGINE,aid)
    st.markdown(f"<div class='c360-card'><h3>{a['action_no']} — {a['title']}</h3>{a.get('subtitle') or ''}<br><b>{a['mode']}</b> · {delivery_mode_label(a.get('delivery_mode'))} — Durée prévue : {a['planned_hours']:g} h — Statut : {a['status']}</div>",unsafe_allow_html=True)
    flash=st.session_state.pop('_action_flash',None)
    if flash and flash[0]==aid:
        if flash[1]=='success': st.success(flash[2])
        elif flash[1]=='warning': st.warning(flash[2])
        else: st.info(flash[2])
    c1,c2,c3,c4=st.columns(4);c1.metric('Participants',pr['participants']);c2.metric('Créneaux',pr['slots']);c3.metric('Signatures',f"{pr['signed']}/{pr['expected']}");c4.metric('Avancement',f"{pr['percent']} %")
    selected=_p3_sidebar_section('ADMIN_ACTION',action_id=aid,action_no=a['action_no'],show_title=False)
    tab_specs=[
        ('action_parametres', action_settings_tab),('action_participants', participants_tab),('action_intervenants', action_trainers_tab),
        ('action_calendrier', calendar_tab),('action_teams', teams_tab),('action_outils', action_tools_tab),
        ('action_contractualisation', contractualization_tab),('action_envois', dispatch_tab),('action_suivi', tracking_tab),
        ('action_qualite', quality_tab),('action_documents', documents_tab),('action_journal', audit_tab)]
    for ctx,fn in tab_specs:
        if ctx==selected:
            _run_ui_module(ctx,lambda fn=fn: fn(a),action_id=a['id'])
            break

def action_settings_tab(a):
    st.subheader('Paramètres de l’action')
    prestation_labels={'Formation':'FORMATION','Bilan de compétences':'BILAN_COMPETENCES','VAE':'VAE','Coaching':'COACHING','Mentorat':'MENTORAT','Autre':'AUTRE'}
    reverse_pt={v:k for k,v in prestation_labels.items()}; current_pt=a.get('prestation_type') or 'FORMATION'; current_label=reverse_pt.get(current_pt,'Formation')
    orgs=list_organizations(ENGINE,active_only=True); org_opts={o['name']:o['id'] for o in orgs}; current_org=a.get('organization_id') or (next(iter(org_opts.values())) if org_opts else None); current_org_label=next((k for k,v in org_opts.items() if v==current_org),next(iter(org_opts),'—'))
    agencies=list_agencies(ENGINE,current_org,active_only=True) if current_org else []; agency_opts={'— Siège / aucune agence —':None,**{g['name']:g['id'] for g in agencies}}; current_agency_label=next((k for k,v in agency_opts.items() if v==a.get('agency_id')),'— Siège / aucune agence —')
    teams_mod=action_module(ENGINE,a['id'],'TEAMS') or {}
    pt_label=st.selectbox('Type de prestation',list(prestation_labels),index=list(prestation_labels).index(current_label),key=f'action_pt_{a["id"]}')
    selected_pt=prestation_labels[pt_label]; modality_codes=allowed_delivery_modes(selected_pt); modality_labels={delivery_mode_label(x):x for x in modality_codes}
    current_mod=a.get('delivery_mode') if a.get('delivery_mode') in modality_codes else modality_codes[0]
    with st.form(f'action_settings_{a["id"]}'):
        c1,c2=st.columns(2);title=c1.text_input('Intitulé',value=a['title']);subtitle=c2.text_input('Intitulé complémentaire',value=a.get('subtitle') or '')
        c1,c2=st.columns(2);start_date=c1.date_input('Date de début',value=date.fromisoformat(a['start_date']) if a.get('start_date') else date.today(),format=app_date_input_format());end_date=c2.date_input('Date de fin',value=date.fromisoformat(a['end_date']) if a.get('end_date') else date.today(),format=app_date_input_format())
        c1,c2=st.columns(2);mode=c1.selectbox('Organisation',['INTRA','INTER','INDIVIDUEL'],index=['INTRA','INTER','INDIVIDUEL'].index(a['mode']));current_status=normalize_action_status(a.get('status'));c2.text_input('Statut',value=current_status,disabled=True);status=current_status
        c1,c2,c3=st.columns(3);planned=c1.number_input('Durée prévue (h)',min_value=0.0,step=.5,value=float(a.get('planned_hours') or 0));expected=c2.number_input('Nombre prévu de participants',min_value=1,step=1,value=int(a.get('expected_participants') or 1));group=c3.text_input('Code groupe / session',value=a.get('group_code') or '')
        c1,c2=st.columns(2);client=c1.text_input('Client / entreprise',value=a.get('client_name') or '');client_type=c2.selectbox('Type client',['Non précisé','Professionnel','Particulier'],index=['Non précisé','Professionnel','Particulier'].index(a.get('client_type')) if a.get('client_type') in ['Non précisé','Professionnel','Particulier'] else 0)
        c1,c2=st.columns(2); org_label=c1.selectbox('Organisme',list(org_opts),index=list(org_opts).index(current_org_label) if current_org_label in org_opts else 0); agency_label=c2.selectbox('Agence / établissement',list(agency_opts),index=list(agency_opts).index(current_agency_label) if current_agency_label in agency_opts else 0)
        st.markdown('**Modules activés**');m1,m2,m3,m4,m5=st.columns(5);use_attendance=m1.checkbox('Émargement',value=bool(a.get('use_attendance',1)));use_hot=m2.checkbox('Évaluation à chaud',value=bool(a.get('use_quality_hot',0)));use_cold=m3.checkbox('Évaluation à froid',value=bool(a.get('use_quality_cold',0)));use_trainer=m4.checkbox('Retour intervenant',value=bool(a.get('use_trainer_feedback',0)));use_teams=m5.checkbox('Gestion Teams',value=bool(teams_mod.get('enabled',0)),help='Module indépendant : le mode online/mixte ne l’active jamais automatiquement.')
        trainers=list_trainers(ENGINE,active_only=True); trainer_opts={'— Aucun intervenant référencé —':None,**{f"{t['full_name']} — {t.get('email') or 'sans email'}":t['id'] for t in trainers}}; trainer_labels=list(trainer_opts); current_idx=next((i for i,l in enumerate(trainer_labels) if trainer_opts[l]==a.get('trainer_id')),0)
        c1,c2,c3=st.columns(3);trainer_label=c1.selectbox('Intervenant référent',trainer_labels,index=current_idx);modality_label=c2.selectbox('Modalité',list(modality_labels),index=modality_codes.index(current_mod));delivery_mode=modality_labels[modality_label];location=c3.text_input('Lieu / précision',value=a.get('location') or '')
        admins=q(ENGINE,'SELECT email,full_name FROM admins WHERE active=1 ORDER BY full_name,email');admin_opts={f"{x.get('full_name') or x['email']} — {x['email']}":x['email'] for x in admins};cur_email=a.get('admin_email') or st.session_state.admin_email;cur_admin=next((k for k,v in admin_opts.items() if v==cur_email),list(admin_opts)[0] if admin_opts else '');admin_label=st.selectbox('Administrateur référent',list(admin_opts),index=list(admin_opts).index(cur_admin) if cur_admin in admin_opts else 0);admin_email=admin_opts.get(admin_label,cur_email);notes=st.text_area('Observations',value=a.get('notes') or '')
        save=st.form_submit_button('Enregistrer les modifications',type='primary')
    if save:
        try:
            nature=pt_label
            update_action(ENGINE,a['id'],{'title':title,'subtitle':subtitle or None,'nature':nature,'mode':mode,'delivery_mode':delivery_mode,'client_name':client or None,'client_type':client_type,'group_code':group or None,'planned_hours':float(planned),'expected_participants':int(expected),'admin_email':admin_email,'trainer_name':a.get('trainer_name'),'trainer_email':a.get('trainer_email'),'location':location or None,'notes':notes or None,'status':status},st.session_state.admin_email)
            safe_set_action_modules(ENGINE,a['id'],prestation_labels[pt_label],use_attendance,use_hot,use_cold,use_trainer,org_opts.get(org_label),agency_opts.get(agency_label),st.session_state.admin_email)
            current_teams=bool((action_module(ENGINE,a['id'],'TEAMS') or {}).get('enabled'))
            if current_teams != bool(use_teams):
                eff=set_generic_action_module(ENGINE,a['id'],'TEAMS',use_teams,st.session_state.admin_email)
                if use_teams: st.session_state['_action_flash']=(a['id'],'success',f"Teams activé à partir du prochain créneau futur ({eff}).")
            execute(ENGINE,'UPDATE actions SET start_date=:s,end_date=:e WHERE id=:a',{'s':start_date.isoformat(),'e':end_date.isoformat(),'a':a['id']})
            assign_trainer(ENGINE,a['id'],trainer_opts.get(trainer_label),st.session_state.admin_email);st.success('Action mise à jour.');rerun()
        except ValueError as ex: st.error(str(ex))
    # J7 — explicit customer identity is independent from any Client portal rights.
    st.markdown('### Client / donneur d’ordre')
    customer=action_ordering_client(ENGINE,a['id'])
    if customer:
        st.caption(f"Référence : {customer['customer_ref']} · {customer['display_name']} — aucun droit Client/DRH automatique")
    else:
        st.warning('Aucun donneur d’ordre de référence : confirmer le rattachement CRM pour ce dossier historique.')
    if st.button('GÉRER LES ACCÈS CLIENT / DRH DE CETTE ACTION',key=f'j7_client_grants_{a["id"]}'):
        st.session_state['p4_access_action_id']=a['id']
        st.session_state['p4_admin_client_section']='Habilitations par action'
        st.session_state['_next_nav']='Espace Client / DRH'
        rerun()
    current_status=normalize_action_status(a.get('status'))
    if current_status in ('BROUILLON','PLANIFIEE'):
        st.markdown('### Validation opérationnelle')
        st.info("Tant que l’action reste en BROUILLON, aucun email automatique d’émargement ni questionnaire qualité ne peut partir. L’action restera modifiable après activation.")
        activate_action_ui(a,'settings')
    elif current_status in ('ACTIVE','A_CLOTURER'):
        st.success("Action ACTIVE — elle reste entièrement modifiable. Les changements futurs recalculent les échéances d’envoi et les campagnes qualité non encore envoyées.")
        if st.button('Renvoyer le planning actualisé aux participants',key=f'resend_schedule{a["id"]}'):
            sent,failed=send_schedule_confirmations(a['id'],st.session_state.admin_email)
            if sent: st.success(f'Planning envoyé à {len(sent)} participant(s).')
            if failed: st.warning('Échec pour : '+' ; '.join(f"{x}: {e}" for x,e in failed))
    if current_status=='CLOTUREE':
        if st.button('Archiver cette action',key=f'archive{a["id"]}'):
            archive_action(ENGINE,a['id'],st.session_state.admin_email);rerun()
    elif current_status=='ARCHIVEE':
        if st.button('Réactiver depuis les archives',key=f'unarchive{a["id"]}'):
            unarchive_action(ENGINE,a['id'],st.session_state.admin_email);rerun()

def action_tools_tab(a):
    st.subheader('Hub Clarté360 — outils prescrits')
    st.caption("Le catalogue est générique : Gestion des Actions orchestre les accès sans recopier les moteurs métier des outils.")
    linked=q(ENGINE,"""SELECT p.id participant_id,b.id beneficiary_id,b.public_id,b.first_name,b.last_name
      FROM participants p JOIN beneficiaries b ON b.id=p.beneficiary_id WHERE p.action_id=:a AND p.active=1 AND b.active=1 ORDER BY b.last_name,b.first_name""",{'a':a['id']})
    compatible_tools=list_tool_catalog(ENGINE,active_only=True,prescription_only=True)
    allowed_tools_all=action_allowed_tools(ENGINE,a['id'],active_only=False)
    by_code={x['tool_code']:x for x in compatible_tools}
    for x in allowed_tools_all:
        by_code.setdefault(x['tool_code'],x)
    selectable_tools=sorted(by_code.values(),key=lambda x:(x.get('name') or '',x.get('tool_code') or ''))
    allowed_tools=action_allowed_tools(ENGINE,a['id'])
    with st.expander('Outils autorisés sur cette action',expanded=not bool(allowed_tools)):
        st.caption("L'administrateur peut ajouter ou retirer librement les outils de cette action. Le catalogue global reste inchangé.")
        cmap={x['name']:x for x in selectable_tools}
        current_codes={x['tool_code'] for x in allowed_tools_all}
        defaults=[label for label,x in cmap.items() if x['tool_code'] in current_codes]
        selected=st.multiselect('Outils disponibles pour cette action',list(cmap),default=defaults,key=f'action_tools_allow_{a["id"]}')
        wanted={cmap[x]['tool_code'] for x in selected}
        if wanted != current_codes:
            changed=[]
            for tx in selectable_tools:
                code=tx['tool_code']
                should_allow=code in wanted
                was_allowed=code in current_codes
                if should_allow != was_allowed:
                    ok,msg=set_action_tool_allowed(ENGINE,a['id'],code,should_allow,st.session_state.admin_email)
                    if not ok:
                        st.error(msg or f"Impossible de modifier l'autorisation de {tx.get('name') or code}.")
                    else:
                        changed.append((tx.get('name') or code,should_allow))
            if changed:
                added=[name for name,allowed in changed if allowed]
                removed=[name for name,allowed in changed if not allowed]
                messages=[]
                if added: messages.append('Ajouté : '+', '.join(added))
                if removed: messages.append('Retiré : '+', '.join(removed))
                st.success(' · '.join(messages))
    tools=action_allowed_tools(ENGINE,a['id'])
    c1,c2,c3=st.columns(3);c1.metric('Bénéficiaires rattachés',len(linked));c2.metric('Outils autorisés',len(tools));c3.metric('Prescriptions',len([x for x in list_tool_prescriptions(ENGINE,action_id=a['id']) if x.get('status')!='ANNULE']))
    if linked and tools:
        bmap={f"{x['last_name']} {x['first_name']} — {x['public_id']}":x for x in linked}; tmap={x['name']:x for x in tools}
        with st.form(f'admin_tool_prescribe_{a["id"]}'):
            bl=st.selectbox('Bénéficiaire',list(bmap)); tl=st.selectbox('Outil Clarté360',list(tmap)); due=st.date_input('Échéance indicative',value=None,key=f'tool_due_{a["id"]}',format=app_date_input_format())
            submit=st.form_submit_button('PRESCRIRE CET OUTIL',type='primary')
        if submit:
            bx=bmap[bl]; tx=tmap[tl]
            try:
                pr=create_tool_prescription(ENGINE,tx['tool_code'],bx['beneficiary_id'],a['id'],bx['participant_id'],prescriber_type='ADMIN',prescriber_id=st.session_state.admin_email,prescriber_role='ADMINISTRATEUR',due_at=due.isoformat() if due else None,actor=st.session_state.admin_email)
                st.success(f"Prescription créée : {pr['prescription_id']}"); rerun()
            except ValueError as ex: st.error(str(ex))
    elif not linked:
        st.warning('Aucun bénéficiaire permanent n’est encore rattaché à cette action. Les outils du catalogue sont bien disponibles globalement, mais une prescription doit toujours viser une identité bénéficiaire permanente.')
        unlinked=q(ENGINE,"SELECT * FROM participants WHERE action_id=:a AND active=1 AND beneficiary_id IS NULL ORDER BY last_name,first_name",{'a':a['id']})
        if unlinked:
            st.markdown('#### Rattacher le bénéficiaire pour prescrire')
            umap={f"{x['last_name']} {x['first_name']}":x for x in unlinked}
            ulab=st.selectbox('Participant à rattacher',list(umap),key=f'tool_ben_link_{a["id"]}')
            up=umap[ulab]
            if not up.get('birth_date'):
                st.info('Ajoutez sa date de naissance dans l’onglet Participants avant de créer son identité permanente.')
            elif not up.get('email'):
                st.info('Ajoutez son adresse email dans l’onglet Participants avant de créer son espace personnel.')
            else:
                candidates=find_beneficiary_candidates(ENGINE,up['last_name'],up['first_name'],up['birth_date'])
                if candidates:
                    cmap={f"{x['last_name']} {x['first_name']} — {x['birth_date']} — {x['public_id']}":x for x in candidates}
                    cl=st.selectbox('Identité permanente existante possible',list(cmap),key=f'tool_ben_candidate_{up["id"]}')
                    if st.button('RATTACHER CETTE IDENTITÉ',key=f'tool_ben_link_existing_{up["id"]}'):
                        link_participant_to_beneficiary(ENGINE,up['id'],cmap[cl]['id'],st.session_state.admin_email);st.success('Identité permanente rattachée. Les outils sont maintenant prescriptibles pour ce bénéficiaire.');rerun()
                    st.caption('Si cette correspondance n’est pas la bonne, utilisez l’onglet Participants pour créer une nouvelle identité après vérification.')
                else:
                    if st.button('CRÉER L’IDENTITÉ PERMANENTE + ENVOYER L’INVITATION',key=f'tool_ben_create_{up["id"]}',type='primary'):
                        try:
                            bid=create_beneficiary_from_participant(ENGINE,up['id'],st.session_state.admin_email);tok=create_beneficiary_portal_invitation(ENGINE,bid,up.get('email'),st.session_state.admin_email);bb=one(ENGINE,'SELECT * FROM beneficiaries WHERE id=:b',{'b':bid});okb,msgb=send_beneficiary_invitation_email(bb,tok)
                            if okb: st.success('Identité permanente créée et invitation envoyée. Les outils sont maintenant prescriptibles pour ce bénéficiaire.')
                            else: st.warning('Identité permanente créée. '+msgb)
                            rerun()
                        except Exception as ex: _ui_incident('operation_interface',ex)
    else:
        st.info('Aucun outil n’est actuellement autorisé sur cette action. Sélectionnez au moins un outil dans « Outils autorisés sur cette action ».')
    rows=list_tool_prescriptions(ENGINE,action_id=a['id'])
    if rows:
        st.markdown('#### Prescriptions de cette action')
        st.dataframe(pd.DataFrame([{'Prescription':x['prescription_id'],'Bénéficiaire':f"{x['beneficiary_last_name']} {x['beneficiary_first_name']}",'Outil':x['tool_name'],'Créateur':'Administrateur' if x.get('prescriber_type')=='ADMIN' else 'Intervenant','Statut':x['status'].replace('_',' '),'Créée':format_app_datetime(x['created_at']),'Échéance':format_app_deadline(x.get('due_at'))} for x in rows if x.get('status')!='ANNULE']),use_container_width=True,hide_index=True)
        rmap={f"{x['prescription_id']} — {x['beneficiary_last_name']} {x['beneficiary_first_name']} — {x['tool_name']}":x for x in rows}; rl=st.selectbox('Prescription à gérer',list(rmap),key=f'presc_manage_{a["id"]}'); rr=rmap[rl]
        if rr.get('tool_code')=='PIP_RIASEC_ONET':
            try: _meta=json.loads(rr.get('metadata_json') or '{}')
            except Exception: _meta={}
            _summary=_meta.get('pip_result_summary') if isinstance(_meta,dict) else None
            if _summary:
                # P1: administration gère le statut de la prescription, pas les scores
                # ou rapports personnels d'investigation du bénéficiaire.
                st.caption('Résultat PIP reçu et conservé dans le dossier individuel. Consultation réservée au bénéficiaire et à son accompagnateur habilité.')
        statuses=['A_FAIRE','ENVOYE','CONSULTE','EN_COURS','TERMINE','A_REVOIR_EN_SEANCE','REVU_EN_SEANCE','ANNULE']; ns=st.selectbox('Statut',statuses,index=statuses.index(rr['status']) if rr['status'] in statuses else 0,key=f'presc_status_{rr["id"]}')
        if st.button('Enregistrer le statut',key=f'presc_status_save_{rr["id"]}'):
            update_tool_prescription_status(ENGINE,rr['prescription_id'],ns,st.session_state.admin_email,{'source':'admin_ui'});st.success('Statut mis à jour.');rerun()
        owns=(rr.get('prescriber_type')=='ADMIN' and str(rr.get('prescriber_id') or '')==str(st.session_state.admin_email))
        if st.button('SUPPRIMER MA PRESCRIPTION',key=f'presc_cancel_{rr["id"]}',disabled=(not owns or rr.get('status')=='ANNULE')):
            ok,msg=cancel_tool_prescription_owned(ENGINE,rr['prescription_id'],'ADMIN',st.session_state.admin_email,st.session_state.admin_email)
            if ok: st.success('Prescription supprimée de la liste active et conservée dans la piste d’audit.');rerun()
            else: st.warning(msg)
        if not owns and rr.get('status')!='ANNULE': st.caption('Suppression indisponible : cette prescription a été créée par un autre utilisateur.')
    with st.expander('⚙️ Catalogue central des outils Clarté360'):
        cat=list_tool_catalog(ENGINE,active_only=False)
        if cat:
            st.dataframe(pd.DataFrame([{'Code':x['tool_code'],'Nom':x['name'],'Catégorie':x['category'],'Actif':'Oui' if x['active'] else 'Non','Prescriptible':'Oui' if x['prescription_allowed'] else 'Non','Accès':'Connexion sécurisée PIP' if x['tool_code']=='PIP_RIASEC_ONET' else ('Lien direct vers l’outil' if x['launch_type']!='INTERNAL' else 'Interne')} for x in cat]),use_container_width=True,hide_index=True)
        st.caption("La version technique n'est pas utilisée pour autoriser ou prescrire un outil. Les outils actifs et prescriptibles sont disponibles pour toutes les actions.")
        existing_map={'➕ Nouvel outil':None}
        for x in cat:
            existing_map[f"{x['name']} — {x['tool_code']}"]=x
        selected_label=st.selectbox('Outil du catalogue',list(existing_map),key=f'tool_catalog_select_{a["id"]}')
        selected_tool=existing_map[selected_label]
        if selected_tool:
            pip_selected=selected_tool.get('tool_code')=='PIP_RIASEC_ONET'
            c1,c2=st.columns(2)
            c1.text_input('Code outil',value=selected_tool.get('tool_code') or '',disabled=True,key=f'cat_code_{selected_tool["id"]}')
            c2.text_input('Nom outil',value=selected_tool.get('name') or '',disabled=True,key=f'cat_name_{selected_tool["id"]}')
            c1,c2=st.columns(2)
            c1.text_input('Catégorie',value=selected_tool.get('category') or '',disabled=True,key=f'cat_cat_{selected_tool["id"]}')
            c2.text_input('URL de base vérifiée',value=selected_tool.get('base_url') or '',disabled=True,key=f'cat_url_{selected_tool["id"]}')
            access_label='Connexion sécurisée PIP' if pip_selected else ('Interne' if selected_tool.get('launch_type')=='INTERNAL' else 'Lien direct vers l’outil')
            st.text_input('Mode d’accès',value=access_label,disabled=True,key=f'cat_access_{selected_tool["id"]}')
            active=st.checkbox('Actif',value=bool(selected_tool.get('active')),key=f'cat_active_{selected_tool["id"]}')
            presc=st.checkbox('Prescription autorisée',value=bool(selected_tool.get('prescription_allowed')),key=f'cat_presc_{selected_tool["id"]}')
            if active!=bool(selected_tool.get('active')) or presc!=bool(selected_tool.get('prescription_allowed')):
                try:
                    upsert_tool_catalog(ENGINE,{'tool_code':selected_tool['tool_code'],'name':selected_tool['name'],'category':selected_tool.get('category') or 'OUTIL','base_url':selected_tool.get('base_url'),'active':active,'prescription_allowed':presc,'allowed_publics':['BENEFICIAIRE']},st.session_state.admin_email)
                    st.success('Catalogue mis à jour automatiquement.'); rerun()
                except ValueError as ex: st.error(str(ex))
            with st.expander('Supprimer cet outil du catalogue'):
                st.caption("La suppression physique n'est possible que si l'outil n'a jamais été prescrit ni autorisé sur une action. Sinon, désactivez-le.")
                tconfirm=st.text_input('Saisissez SUPPRIMER',key=f'tool_delete_confirm_{selected_tool["id"]}')
                if st.button('Supprimer définitivement cet outil',key=f'tool_delete_{selected_tool["id"]}',disabled=tconfirm!='SUPPRIMER'):
                    try: delete_tool_catalog_if_unused(ENGINE,selected_tool['id'],st.session_state.admin_email);st.success('Outil supprimé du catalogue.');rerun()
                    except ValueError as ex: st.error(str(ex))
        else:
            with st.form(f'tool_catalog_add_{a["id"]}'):
                c1,c2=st.columns(2)
                code=c1.text_input('Code outil')
                name=c2.text_input('Nom outil')
                c1,c2=st.columns(2)
                category=c1.text_input('Catégorie',value='OUTIL')
                base_url=c2.text_input('URL de base vérifiée')
                st.caption('Les nouveaux outils sont créés comme applications autonomes avec ouverture directe. Le PIP conserve son connecteur sécurisé spécifique.')
                active=st.checkbox('Actif',value=True)
                presc=st.checkbox('Prescription autorisée',value=True)
                save_tool=st.form_submit_button('AJOUTER AU CATALOGUE')
            if save_tool:
                try:
                    upsert_tool_catalog(ENGINE,{'tool_code':code,'name':name,'category':category,'base_url':base_url,'active':active,'prescription_allowed':presc,'allowed_publics':['BENEFICIAIRE']},st.session_state.admin_email)
                    st.success('Outil ajouté au catalogue.'); rerun()
                except ValueError as ex: st.error(str(ex))


def teams_tab(a):
    st.subheader('Microsoft Teams')
    mod=action_module(ENGINE,a['id'],'TEAMS') or {}
    if not mod.get('enabled'):
        st.info('Teams est désactivé pour cette action. La modalité de la prestation ne l’active jamais automatiquement.')
        return

    room=teams_room(ENGINE,a['id'])
    nxt=teams_next_meeting(ENGINE,a['id'])
    if nxt:
        st.success(f"Prochaine réunion Teams : {nxt.get('slot_date')} — {nxt.get('start_time')}–{nxt.get('end_time')}")
    else:
        st.info('Aucune prochaine réunion Teams planifiée.')

    if room and room.get('join_web_url'):
        st.link_button('OUVRIR LE LIEN TEAMS DE L’ACTION',room['join_web_url'],type='primary')
        st.caption('Le calendrier Clarté360 reste la source métier. Les changements de séance sont synchronisés automatiquement.')
    else:
        st.info('Création/synchronisation Teams en cours. Aucune action n’est nécessaire.')

    occ=teams_occurrences(ENGINE,a['id'])
    if occ:
        st.markdown('#### Séances gérées par Teams')
        st.caption("Vue de restitution issue du calendrier. Les séances se modifient dans l'onglet Calendrier.")
        st.dataframe(pd.DataFrame([{'Séance':f"{x['slot_date']} — {x['start_time']}–{x['end_time']}",
            'Statut':'Présence récupérée' if x.get('attendance_report_id') else ('Planifiée' if x.get('status')=='PLANNED' else x.get('status') or '—')} for x in occ]),use_container_width=True,hide_index=True)

    roles=teams_roles(ENGINE,a['id'])
    if roles:
        st.markdown('#### Intervenants Teams')
        st.caption("Vue dérivée des affectations. Les intervenants et leurs rôles se gèrent dans l'onglet Intervenants.")
        slots_by_id={x['id']:x for x in q(ENGINE,'SELECT * FROM slots WHERE action_id=:a',{'a':a['id']})}
        role_rows=[]
        for x in roles:
            sl=slots_by_id.get(x.get('slot_id')) or {}
            role_rows.append({'Intervenant':x.get('display_name') or x.get('email'),
                'Séance':f"{sl.get('slot_date','—')} — {sl.get('start_time','—')}–{sl.get('end_time','—')}",
                'Rôle':'Coorganisateur' if str(x.get('role')).upper()=='COORGANIZER' else 'Présentateur',
                'Identité Microsoft':'Vérifiée' if x.get('entra_user_id') else 'À vérifier'})
        st.dataframe(pd.DataFrame(role_rows),use_container_width=True,hide_index=True)

        trainer_ids=[]
        for x in roles:
            if x.get('trainer_id') and x.get('trainer_id') not in trainer_ids: trainer_ids.append(x.get('trainer_id'))
        for tid in trainer_ids:
            ident=trainer_microsoft_identity(ENGINE,tid) or {}
            c1,c2=st.columns([3,1])
            with c1:
                st.write(f"**{ident.get('full_name') or 'Intervenant'}** — {ident.get('microsoft_email') or ident.get('email') or 'email non renseigné'}")
                status=ident.get('entra_status') or 'UNCHECKED'
                labels={'VERIFIED':'Identité Microsoft vérifiée','INVITED':'Invitation Microsoft envoyée','NOT_FOUND':'Aucune identité Microsoft trouvée','CREATION_REQUESTED':'Création demandée','CREATION_BLOCKED':'Création non autorisée par la configuration','ERROR':'Vérification en erreur','UNCHECKED':'À vérifier'}
                st.caption(labels.get(status,status))
            with c2:
                if not ident.get('entra_user_id') and status not in ('CREATION_REQUESTED','INVITED'):
                    if st.button('Créer l’identité Microsoft',key=f'entra_create_{a["id"]}_{tid}'):
                        request_trainer_microsoft_identity_creation(ENGINE,tid,st.session_state.admin_email)
                        queue_teams_sync(ENGINE,a['id'],None,'IDENTITY_CREATION_REQUESTED',st.session_state.admin_email)
                        st.success('Demande enregistrée. Une recherche d’identité existante sera effectuée avant toute création.'); rerun()

    evidence=teams_occurrence_evidence(ENGINE,a['id'])
    if evidence:
        st.markdown('#### Réunions Teams réellement constatées')
        st.caption('Microsoft Graph est la source externe. Les données récupérées sont conservées sur le VPS avec leurs références techniques et leur empreinte SHA-256.')
        for ev in evidence:
            rep=ev.get('report'); conns=ev.get('connections') or []
            label=f"{ev.get('slot_date')} — {ev.get('start_time')}–{ev.get('end_time')}"
            if not rep:
                # Future sessions are simply planned; do not suggest a missing report before the meeting has happened.
                try:
                    slot_row=one(ENGINE,'SELECT * FROM slots WHERE id=:s',{'s':ev.get('slot_id')}) if ev.get('slot_id') else None
                    tz_name=organization_runtime_config(ENGINE,a['id']).get('timezone') or TZ or 'Europe/Paris'
                    current_local=datetime.now(ZoneInfo(tz_name))
                    if slot_row:
                        _, slot_end = slot_start_end(slot_row,tz_name)
                    else:
                        slot_end = None
                except Exception:
                    slot_end = None; current_local = None
                if slot_end is not None and current_local is not None and current_local < slot_end:
                    st.info(f"{label} — réunion planifiée. Le rapport Microsoft sera recherché automatiquement après la séance.")
                else:
                    st.info(f"{label} — rapport Microsoft en attente de récupération. Ce statut ne signifie pas absence.")
                continue
            tz_name=organization_runtime_config(ENGINE,a['id']).get('timezone') or TZ or 'Europe/Paris'
            ms=rep.get('meeting_start_utc'); me=rep.get('meeting_end_utc')
            try:
                ms_local=local_dt(ms,tz_name) if ms else None
                me_local=local_dt(me,tz_name) if me else None
                meeting_seconds=int((me_local-ms_local).total_seconds()) if ms_local and me_local else 0
                actual_start=ms_local.strftime('%d/%m/%Y %H:%M:%S') if ms_local else '—'
                actual_end=me_local.strftime('%d/%m/%Y %H:%M:%S') if me_local else '—'
            except Exception:
                meeting_seconds=0; actual_start=ms or '—'; actual_end=me or '—'
            st.success(f"{label} — réunion Microsoft constatée · {len(conns)} connexion(s).")
            m1,m2,m3,m4=st.columns(4)
            m1.metric('Début réel',actual_start)
            m2.metric('Fin réelle',actual_end)
            m3.metric('Durée réunion',_duration_hms(meeting_seconds))
            m4.metric('Connexions',len(conns))
            rows=[]
            for r in conns:
                match=(f"{r.get('participant_first_name','')} {r.get('participant_last_name','')}".strip() if r.get('participant_id') else 'Non rapproché')
                if not r.get('participant_id'):
                    sug=suggest_teams_participant_match(ENGINE,a['id'],r.get('display_name'))
                    if sug: match=f"Suggestion : {sug.get('first_name','')} {sug.get('last_name','')} — à confirmer"
                try:
                    j=local_dt(r.get('join_time_utc'),tz_name).strftime('%d/%m/%Y %H:%M:%S') if r.get('join_time_utc') else '—'
                    l=local_dt(r.get('leave_time_utc'),tz_name).strftime('%d/%m/%Y %H:%M:%S') if r.get('leave_time_utc') else '—'
                except Exception:
                    j=r.get('join_time_utc') or '—'; l=r.get('leave_time_utc') or '—'
                rows.append({'Identité / pseudo Teams':r.get('display_name') or '—','Email Microsoft':r.get('email') or '—','Rôle':r.get('role') or '—','Entrée':j,'Sortie':l,'Durée exacte':_duration_hms(r.get('duration_seconds')),'Rapprochement Clarté360':match})
            st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
            cpdf1,cpdf2=st.columns(2)
            cpdf1.download_button('🖨️ Preuve de cette réunion',teams_evidence_pdf(ENGINE,a['id'],rep['id'],technical=True),file_name=f"{a['action_no']}_{ev.get('slot_date') or 'reunion'}_preuve_Teams_technique.pdf",mime='application/pdf',key=f'adm_team_pdf_{rep["id"]}')
            with cpdf2:
                with st.expander('Références techniques'):
                    st.code(f"OnlineMeeting ID: {rep.get('online_meeting_id') or '—'}\nAttendanceReport ID: {rep.get('report_id') or '—'}\nSHA-256 Graph: {rep.get('raw_sha256') or 'rapport historique sans empreinte'}\nRécupéré: {rep.get('retrieved_at') or '—'}")
        if any(ev.get('report') for ev in evidence):
            st.download_button('🖨️ Rapport technique Teams — TOUTE L’ACTION',teams_evidence_pdf(ENGINE,a['id'],technical=True),file_name=f"{a['action_no']}_rapport_Teams_complet.pdf",mime='application/pdf',type='primary',key=f'adm_team_all_{a["id"]}')

    recon=teams_attendance_reconciliation(ENGINE,a['id'])
    if recon:
        st.markdown('#### Rapprochement présence Teams / émargement')
        st.caption('La présence Teams complète la preuve d’émargement. Une absence de rapport Microsoft n’est jamais affichée comme une absence du participant.')
        st.dataframe(pd.DataFrame([{'Séance':f"{x['slot_date']} — {x['start_time']}",'Participant':x['participant'],'Présence Teams':'Oui' if x['teams_present'] else ('Non observée' if any(ev.get('report') and ev.get('slot_id')==x['slot_id'] for ev in evidence) else 'Rapport en attente'),'Durée Teams':_duration_hms(x['teams_seconds']) if x['teams_present'] else '—','Émargé':'Oui' if x['signed'] else 'Non','Absent déclaré':'Oui' if x['absent'] else 'Non','À vérifier':'Oui' if x['anomaly'] else ''} for x in recon]),use_container_width=True,hide_index=True)

    unmatched=teams_unmatched_attendance(ENGINE,a['id'])
    if unmatched:
        st.warning(f"{len(unmatched)} connexion(s) Teams ne correspondent pas automatiquement à un participant. Elles restent visibles comme preuve de réunion et ne sont jamais attribuées sans confirmation.")
        participants=q(ENGINE,'SELECT id,first_name,last_name,email FROM participants WHERE action_id=:a AND active=1 ORDER BY last_name,first_name',{'a':a['id']})
        pmap={f"{p.get('first_name','')} {p.get('last_name','')} — {p.get('email') or 'sans email'}":p['id'] for p in participants}
        for u in unmatched:
            suggestion=suggest_teams_participant_match(ENGINE,a['id'],u.get('display_name'))
            title=f"{u.get('slot_date') or 'Réunion non rapprochée'} — {u.get('display_name') or 'Participant Teams'} — {_duration_hms(u.get('duration_seconds'))}"
            with st.expander(title):
                if suggestion: st.info(f"Suggestion uniquement : {suggestion.get('first_name')} {suggestion.get('last_name')}. Une confirmation humaine reste obligatoire.")
                choice=st.selectbox('Rattacher à', ['— Ne pas rattacher —']+list(pmap), key=f"teams_match_{u['attendance_record_id']}")
                if choice!='— Ne pas rattacher —' and st.button('Confirmer ce rapprochement',key=f"teams_match_ok_{u['attendance_record_id']}"):
                    confirm_teams_attendance_identity(ENGINE,u['attendance_record_id'],pmap[choice],st.session_state.admin_email); st.success('Rapprochement confirmé et tracé.'); rerun()

    with st.expander('Administration avancée Microsoft 365'):
        try:
            cfg=graph_config_from_mapping(dict(st.secrets))
        except Exception:
            cfg=graph_config_from_mapping({})
        missing=graph_config_missing(cfg) if cfg.get('enabled') else ['configuration Microsoft Graph non activée']
        if missing: st.warning('Connexion Microsoft 365 non prête. Vérifiez la configuration serveur.')
        else: st.success(f"Connexion Microsoft 365 prête — organisateur technique : {cfg.get('organizer_upn') or '—'}.")
        if room:
            st.write(f"Dernière synchronisation : {room.get('last_sync_at') or '—'}")
        if st.button('Forcer la synchronisation maintenant',key=f'teams_sync_now_{a["id"]}'):
            queue_teams_sync(ENGINE,a['id'],None,'MANUAL_SYNC',st.session_state.admin_email)
            st.success('Synchronisation de secours demandée.');rerun()


def action_trainers_tab(a):
    st.subheader('Intervenants de l’action')
    creation_notice=st.session_state.pop('_j17_creation_qualification_notice',None)
    if creation_notice: st.warning(creation_notice)
    st.success("Cette action peut comporter plusieurs intervenants. Ajouter un intervenant ne remplace pas les intervenants déjà affectés.")
    st.caption("Le référent coordonne l’action ; les co-intervenants et remplaçants restent rattachés selon leurs droits.")
    # J11 — l'affectation opérationnelle part désormais du dossier professionnel stable.
    req=get_action_service_requirement(ENGINE,a['id'])
    with st.expander('Prestation Clarté360 et exigence de qualification',expanded=not bool(req)):
        services=list_services(ENGINE,active_only=True)
        if services:
            sm={f"{x['name']} — {x['service_code']}":x for x in services}
            labels=['— Prestation non encore rattachée —']+list(sm); idx=0
            if req:
                idx=next((i for i,l in enumerate(labels) if l in sm and sm[l]['id']==req['service_id']),0)
            lab=st.selectbox('Prestation réellement réalisée dans cette action',labels,index=idx,key=f"act_svc_{a['id']}")
            level=st.selectbox('Niveau humain minimum requis',[0,1,2,3,4],index=int((req or {}).get('minimum_human_level',3)),format_func=lambda x:f"{x}/4 — {QUALIFICATION_LEVEL_LABELS[x]}",key=f"act_lvl_{a['id']}")
            complete=st.checkbox('Exiger que tous les critères obligatoires soient démontrés',value=bool((req or {}).get('require_required_complete')),key=f"act_req_{a['id']}")
            if st.button('Enregistrer les exigences de cette action',key=f"act_svc_save_{a['id']}"):
                if lab not in sm: st.error('Choisissez explicitement une prestation Clarté360. Aucune prestation n’est sélectionnée par défaut.')
                else:
                    ok,msg=set_action_service_requirement(ENGINE,a['id'],sm[lab]['id'],st.session_state.admin_email,level,complete)
                    if ok: st.success('Prestation et exigence de qualification enregistrées.');rerun()
                    else: st.error(msg)
        else: st.warning('Aucune prestation active dans le référentiel Clarté360.')
    candidates=action_intervenant_candidates(ENGINE,a['id'],include_unqualified=True)
    trainers=list_trainers(ENGINE,active_only=True)  # compatibilité historique pour retrait/remplacement
    current=action_assigned_professional_statuses(ENGINE,a['id'])
    if current:
        st.markdown('#### Contrôle qualification des intervenants déjà affectés')
        st.dataframe(pd.DataFrame([{
            'Intervenant':x['full_name'],'Email':x.get('email') or '',
            'Rôle action':x.get('role') or 'INTERVENANT','Référent':'Oui' if x.get('is_referent') else 'Non',
            'Qualification':x.get('eligibility_status') or 'A_VERIFIER',
            'Niveau humain':(f"{x['human_value']}/4" if x.get('human_value') is not None else '—'),
            'Motif':x.get('eligibility_reason') or '',
            'Gestion planning action':'Oui' if x.get('can_manage_planning') else 'Non',
            'Prescription outils':'Oui' if x.get('can_prescribe_tools') else 'Non'
        } for x in current]),use_container_width=True,hide_index=True)
        for x in current:
            if not x.get('eligible') and x.get('professional_person_id'):
                c1,c2=st.columns([4,1])
                c1.warning(f"{x['full_name']} — {x.get('eligibility_status')}: {x.get('eligibility_reason')}")
                if c2.button('Étudier / valider cette qualification',key=f"j17_study_{a['id']}_{x['professional_person_id']}"):
                    # RC2-2-2 RC1 : navigation métier testable Action -> bonne qualification -> retour Action.
                    prepare_action_qualification_navigation(
                        st.session_state, a['id'], x['professional_person_id'],
                        int(req['service_id']) if req else None,
                    )
                    rerun()
        st.markdown('#### Droits de gestion du planning')
        st.caption("Un droit action permet d'ajouter et de déplacer les créneaux de l'action sous garde-fous. Un droit créneau limite l'intervenant à ce seul créneau.")
        pmap={f"{x['full_name']} — {x.get('role') or 'INTERVENANT'}":x for x in current}
        plab=st.selectbox('Intervenant — droit action',list(pmap),key=f'at_plan_perm_sel_{a["id"]}')
        px=pmap[plab]
        pval=st.checkbox("Autoriser la gestion du planning de l'action",value=bool(px.get('can_manage_planning')),key=f'at_plan_perm_{a["id"]}_{px["trainer_id"]}')
        if st.button('Enregistrer ce droit planning',key=f'at_plan_perm_save_{a["id"]}_{px["trainer_id"]}'):
            ok,msg=set_action_trainer_planning_permission(ENGINE,a['id'],px['trainer_id'],pval,st.session_state.admin_email)
            if ok: st.success('Droit planning mis à jour.');rerun()
            else: st.error(msg)
        tval=st.checkbox("Autoriser la prescription d'outils Clarté360",value=bool(px.get('can_prescribe_tools')),key=f'at_tool_perm_{a["id"]}_{px["trainer_id"]}')
        if st.button('Enregistrer ce droit de prescription',key=f'at_tool_perm_save_{a["id"]}_{px["trainer_id"]}'):
            ok,msg=set_action_trainer_prescription_permission(ENGINE,a['id'],px['trainer_id'],tval,st.session_state.admin_email)
            if ok: st.success('Droit de prescription mis à jour.');rerun()
            else: st.error(msg)
    else:
        st.info('Aucun intervenant actif n’est rattaché à cette action.')

    if candidates:
        opts={f"{x.get('full_name') or x['professional_person_id']} — {x['eligibility_status']}" + (f" — niveau {x['human_value']}/4" if x.get('human_value') is not None else ''):x for x in candidates}
        with st.form(f'add_action_trainer_{a["id"]}'):
            c1,c2,c3=st.columns([3,2,1])
            lab=c1.selectbox('Ajouter un intervenant à cette action',list(opts),key=f'at_add_{a["id"]}')
            selected=opts[lab]
            st.caption(selected['eligibility_reason'])
            role=c2.selectbox('Rôle sur l’action',['INTERVENANT','REFERENT'],key=f'at_role_{a["id"]}')
            make_ref=c3.checkbox('Référent',value=role=='REFERENT',key=f'at_ref_{a["id"]}')
            exception=st.checkbox('Affectation exceptionnelle malgré une adéquation non validée',value=False,key=f'at_exc_{a["id"]}',disabled=bool(selected['eligible']))
            reason=st.text_input('Motif / commentaire éventuel' + (' — obligatoire en cas d’exception' if not selected['eligible'] else ''),key=f'at_reason_{a["id"]}')
            submit=st.form_submit_button('Ajouter / mettre à jour cet intervenant',type='primary')
        if submit:
            ref=make_ref or role=='REFERENT'
            ok,msg=assign_action_professional(ENGINE,a['id'],selected['professional_person_id'],st.session_state.admin_email,role='REFERENT' if ref else role,is_referent=ref,reason=reason or None,allow_exception=exception)
            if ok:
                if ref and selected.get('trainer_id'): assign_trainer(ENGINE,a['id'],selected['trainer_id'],st.session_state.admin_email)
                st.success('Affectation action enregistrée depuis le dossier professionnel.');rerun()
            else: st.error(msg)

    if current:
        cmap={f"{x['full_name']} — {x.get('role') or 'INTERVENANT'}":x for x in current}
        lab=st.selectbox('Retirer un intervenant de l’action',list(cmap),key=f'at_remove_sel_{a["id"]}')
        why=st.text_input('Motif du retrait',key=f'at_remove_reason_{a["id"]}')
        if st.button('Retirer de l’action',key=f'at_remove_{a["id"]}'):
            x=cmap[lab]
            ok,msg=unassign_action_trainer(ENGINE,a['id'],x['trainer_id'],st.session_state.admin_email,why or None)
            if ok: st.success("Affectation action désactivée. Les affectations de créneaux et l’historique ne sont pas effacés.");rerun()
            else: st.error(msg)

    # J8: operational mission coverage and existing-document references only.
    st.markdown('### Missions et engagements')
    cover=action_mission_coverage(ENGINE,a['id'])
    st.caption('GDA contrôle les affectations et références d’engagement. Les contrats sont produits et acceptés hors de cette application (Contractualisation n°13) ; les fournisseurs et factures relèvent de Gestion Clients n°17.')
    if cover['mode']!='ENFORCE':
        st.warning('Contrôle des missions en consultation pour cette action historique. Aucune modification rétroactive de son statut.')
        if st.button('Activer le contrôle obligatoire pour cette action',key=f'j8_mode_{a["id"]}'):
            enable_action_mission_control(ENGINE,a['id'],st.session_state.admin_email,'ENFORCE');st.success('Contrôle activé.');rerun()
    elif cover['issues']:
        st.warning('Conditions à vérifier : '+' ; '.join(cover['issues']))
    else: st.success('Missions couvertes et références documentaires vérifiées.')
    missions=list_action_missions(ENGINE,a['id'])
    if missions:
        st.dataframe(pd.DataFrame([{'Mission':m['mission_id'],'Intervenant':m['full_name'],
            'Référent de suivi':'Oui' if m['is_followup_responsible'] else 'Non',
            'Collaboration':m.get('collaboration_type') or 'À définir',
            'Document':m.get('document_ref') or 'À prévoir',
            'Version':m.get('document_version') or '',
            'Engagement':m['status'],'Archive':'Historique' if not m['active'] else 'En cours'}
            for m in missions]),use_container_width=True,hide_index=True)
        current_missions={f"{m['full_name']} — {m['mission_id']} — {m['status']}":m for m in missions if m['active']}
        if current_missions:
            selected_label=st.selectbox('Mission à suivre',list(current_missions),key=f'j8_mission_select_{a["id"]}')
            chosen=current_missions[selected_label]
            if chosen['status']!='VERIFIE':
                with st.expander('Demander / refuser / annuler un engagement',expanded=False):
                    with st.form(f'j8_status_mission_{chosen["mission_id"]}'):
                        decision=st.selectbox('Décision',['DEMANDE','REFUSE','ANNULE'])
                        reason=st.text_input('Motif motivé et historisé')
                        do=st.form_submit_button('Enregistrer cette décision de mission')
                    if do:
                        try:
                            change_mission_status(ENGINE,chosen['mission_id'],st.session_state.admin_email,decision,reason)
                            st.success('Décision enregistrée dans l’historique de la mission.');rerun()
                        except (ValueError,PermissionError) as ex:st.error(str(ex))
                with st.form(f'j8_verify_mission_{chosen["mission_id"]}'):
                    st.caption('Saisir uniquement les références d’un document réellement accepté, contrôlé par l’administration.')
                    ref=st.text_input('Référence du document accepté')
                    version=st.text_input('Version du document')
                    accepted=st.text_input('Date/heure réelle d’acceptation (ISO 8601, avec fuseau)',placeholder='2026-10-10T13:00:00+02:00')
                    supplier=st.text_input('Référence fournisseur n°17 (sous-traitant uniquement)',value=chosen.get('supplier_id') or '')
                    contract=st.text_input('Référence Contractualisation n°13 (si disponible)',value=chosen.get('external_contract_ref') or '')
                    cost_ref=st.text_input('Référence engagement financier n°17 (sans montant)',value=chosen.get('cost_commitment_ref') or '')
                    description=st.text_area('Mission / suivi défini')
                    submit=st.form_submit_button('Attester le contrôle du document accepté')
                if submit:
                    try:
                        verify_mission_engagement(ENGINE,chosen['mission_id'],st.session_state.admin_email,
                            document_ref=ref,document_version=version,accepted_at=accepted,
                            supplier_id=supplier or None,external_contract_ref=contract or None,
                            cost_commitment_ref=cost_ref or None,description=description)
                        st.success('Engagement vérifié et historisé. Interface fournisseur prête à être raccordée.');rerun()
                    except ValueError as ex:st.error(str(ex))
            else:
                st.info('La référence documentaire vérifiée est conservée. Pour tout avenant, créer une révision.')
                with st.expander('Annuler une mission vérifiée (avec conservation de la preuve)'):
                    cancel_reason=st.text_input('Motif de l’annulation contractuelle',key=f'j8_cancel_reason_{chosen["mission_id"]}')
                    if st.button('Confirmer l’annulation de cette mission',key=f'j8_cancel_{chosen["mission_id"]}'):
                        try:
                            change_mission_status(ENGINE,chosen['mission_id'],st.session_state.admin_email,'ANNULE',cancel_reason)
                            st.success('Mission annulée et historisée ; l’activation est recontrôlée.');rerun()
                        except (ValueError,PermissionError) as ex:st.error(str(ex))
                with st.form(f'j8_revise_{chosen["mission_id"]}'):
                    why=st.text_input('Motif de l’avenant ou du remplacement')
                    rev=st.form_submit_button('Créer une nouvelle révision de mission')
                if rev:
                    try:revise_mission(ENGINE,chosen['mission_id'],st.session_state.admin_email,why);rerun()
                    except ValueError as ex:st.error(str(ex))
        with st.expander('Traçabilité vers Gestion Clients n°17 (sans transmission automatique)'):
            st.caption('Événements versionnés prêts pour un raccordement authentifié. Aucune facture ni paiement ne sont créés dans GDA.')
            st.json(mission_outbox_pending(ENGINE,a['id']))
    else:st.info('Aucune mission préparée : affecter d’abord les intervenants dans cette action.')

    st.markdown('### Affectations par créneau')
    slots=q(ENGINE,"SELECT * FROM slots WHERE action_id=:a AND status NOT IN ('ANNULE') ORDER BY slot_date,start_time",{'a':a['id']})
    if not slots:
        st.info('Aucun créneau à affecter.'); return
    smap={_slot_label(x):x for x in slots}
    slab=st.selectbox('Créneau',list(smap),key=f'st_slot_{a["id"]}'); sl=smap[slab]
    assigned=list_slot_trainers(ENGINE,sl['id'],active_only=True)
    if assigned:
        st.dataframe(pd.DataFrame([{'Intervenant':x['full_name'],'Rôle':x['role'],'Statut':x['assignment_status'],'Gestion de ce créneau':'Oui' if x.get('can_manage_planning') else 'Non'} for x in assigned]),use_container_width=True,hide_index=True)
        sman={f"{x['full_name']} — {x['role']}":x for x in assigned}
        slabp=st.selectbox('Intervenant — droit sur ce créneau',list(sman),key=f'st_plan_perm_sel_{sl["id"]}')
        sp=sman[slabp]
        sval=st.checkbox('Autoriser la modification de ce créneau',value=bool(sp.get('can_manage_planning')),key=f'st_plan_perm_{sl["id"]}_{sp["trainer_id"]}')
        if st.button('Enregistrer le droit de ce créneau',key=f'st_plan_perm_save_{sl["id"]}_{sp["trainer_id"]}'):
            ok,msg=set_slot_trainer_planning_permission(ENGINE,sl['id'],sp['trainer_id'],sval,st.session_state.admin_email)
            if ok: st.success('Droit créneau mis à jour.');rerun()
            else: st.error(msg)
    else:
        st.warning('Aucun intervenant actif n’est affecté à ce créneau.')
    if candidates:
        opts={f"{x.get('full_name') or x['professional_person_id']} — {x['eligibility_status']}" + (f" — niveau {x['human_value']}/4" if x.get('human_value') is not None else ''):x for x in candidates}
        with st.form(f'slot_assign_{sl["id"]}'):
            c1,c2=st.columns(2)
            tlab=c1.selectbox('Intervenant',list(opts),key=f'st_add_tr_{sl["id"]}')
            selected_slot=opts[tlab]
            st.caption(selected_slot['eligibility_reason'])
            srole=c2.selectbox('Rôle sur ce créneau',['PRINCIPAL','CO_INTERVENANT','REMPLACANT'],key=f'st_add_role_{sl["id"]}')
            sexception=st.checkbox('Affectation exceptionnelle malgré une adéquation non validée',value=False,key=f'st_exc_{sl["id"]}',disabled=bool(selected_slot['eligible']))
            sreason=st.text_input('Motif / commentaire' + (' — obligatoire en cas d’exception' if not selected_slot['eligible'] else ''),key=f'st_add_reason_{sl["id"]}')
            sadd=st.form_submit_button('Affecter à ce créneau',type='primary')
        if sadd:
            ok,msg=assign_slot_professional(ENGINE,sl['id'],selected_slot['professional_person_id'],st.session_state.admin_email,srole,sreason or None,allow_exception=sexception)
            if ok: st.success('Affectation créneau enregistrée depuis le dossier professionnel.');rerun()
            else: st.error(msg)
    if assigned:
        amap={f"{x['full_name']} — {x['role']}":x for x in assigned}
        rlab=st.selectbox('Affectation à retirer / remplacer',list(amap),key=f'st_manage_{sl["id"]}')
        old=amap[rlab]; c1,c2=st.columns(2)
        if c1.button('Retirer du créneau',key=f'st_remove_{sl["id"]}_{old["trainer_id"]}'):
            ok,msg=unassign_slot_trainer(ENGINE,sl['id'],old['trainer_id'],st.session_state.admin_email,'Retrait manuel')
            if ok: st.success('Affectation désactivée et historisée.');rerun()
            else: st.error(msg)
        replacement_opts={k:v for k,v in ({f"{t['full_name']} — {t.get('email') or 'sans email'}":t for t in trainers}).items() if v['id']!=old['trainer_id']}
        if replacement_opts:
            rep_lab=c2.selectbox('Remplaçant',list(replacement_opts),key=f'st_rep_sel_{sl["id"]}_{old["trainer_id"]}')
            rep_reason=st.text_input('Motif du remplacement',key=f'st_rep_reason_{sl["id"]}_{old["trainer_id"]}')
            if st.button('Enregistrer le remplacement',key=f'st_rep_btn_{sl["id"]}_{old["trainer_id"]}'):
                nt=replacement_opts[rep_lab];ok,msg=replace_slot_trainer(ENGINE,sl['id'],old['trainer_id'],nt['id'],st.session_state.admin_email,rep_reason or 'Remplacement')
                if ok: st.success('Remplacement enregistré sans effacer l’affectation initiale.');rerun()
                else: st.error(msg)
    hist=trainer_assignment_history(ENGINE,a['id'],sl['id'])
    if hist:
        with st.expander('Historique des affectations de ce créneau'):
            st.dataframe(pd.DataFrame([{
                'Date':format_app_datetime(x['created_at']),'Intervenant':x.get('full_name') or f"#{x.get('trainer_id')}",
                'Événement':x['event_type'],'Ancien rôle':x.get('old_role') or '', 'Nouveau rôle':x.get('new_role') or '',
                'Ancien statut':x.get('old_status') or '', 'Nouveau statut':x.get('new_status') or '', 'Motif':x.get('reason') or ''
            } for x in hist]),use_container_width=True,hide_index=True)

def participants_tab(a):
    st.subheader('Participants')
    parts=q(ENGINE,'SELECT * FROM participants WHERE action_id=:a ORDER BY last_name,first_name',{'a':a['id']})
    if parts:
        df=pd.DataFrame([{k:p.get(k) for k in ['id','individual_action_no','last_name','birth_name','first_name','birth_date','email','employee_id','company_name','phone']} for p in parts]);st.dataframe(df,use_container_width=True,hide_index=True)
    with st.expander('Ajouter un participant',expanded=not parts):
        with st.form(f'addp{a["id"]}'):
            c1,c2,c3=st.columns(3);last=c1.text_input('Nom *');birth=c2.text_input('Nom de naissance');first=c3.text_input('Prénom *')
            c1,c2,c3=st.columns(3);bdate=c1.text_input('Date de naissance (JJ/MM/AAAA)');email=c2.text_input('Email (facultatif)');emp=c3.text_input('Matricule entreprise')
            c1,c2,c3=st.columns(3);company=c1.text_input('Entreprise / client');phone=c2.text_input('Téléphone');indno=c3.text_input('N° action individuel (INTER)',value=a['action_no'] if a['mode']!='INTER' else '')
            send_code=st.checkbox('Envoyer immédiatement par email le code QR personnel et la notice sur les données (si une adresse email est renseignée)',value=True)
            create_portal=st.checkbox('Créer / rattacher un espace personnel au stagiaire',value=False,help='Option facultative. Une adresse email personnelle et une date de naissance sont obligatoires. Aucun rattachement incertain n’est automatique.')
            submit=st.form_submit_button('Ajouter',type='primary')
        if submit:
            if not last.strip() or not first.strip(): st.error('Nom et prénom obligatoires.')
            else:
                
                try: birth_iso=datetime.strptime(bdate.strip(),'%d/%m/%Y').date().isoformat() if bdate.strip() else None
                except ValueError: st.error('Date de naissance invalide : utilisez JJ/MM/AAAA.');return
                try:
                    vp=validate_participant_payload({'individual_action_no':indno.strip() or None,'last_name':last,'birth_name':birth or None,'first_name':first,'birth_date':birth_iso,'email':email or None,'employee_id':emp or None,'company_name':company or None,'phone':phone or None})
                except ValueError as ex:
                    st.error(str(ex)); return
                last,birth,first,birth_iso,email,emp,company,phone,indno=vp['last_name'],vp.get('birth_name') or '',vp['first_name'],vp.get('birth_date'),vp.get('email') or '',vp.get('employee_id') or '',vp.get('company_name') or '',vp.get('phone') or '',vp.get('individual_action_no') or ''
                dup=participant_duplicate(ENGINE,a['id'],last,first,birth_iso,email)
                if dup: st.error(f"Participant potentiellement déjà présent : {dup['last_name']} {dup['first_name']}.");return
                pid,pin=add_participant(ENGINE,a['id'],{'individual_action_no':indno.strip() or None,'last_name':last.strip().upper(),'birth_name':birth.strip().upper() or None,'first_name':first.strip().title(),'birth_date':birth_iso,'email':email.strip() or None,'employee_id':emp.strip() or None,'company_name':company.strip() or None,'phone':phone.strip() or None},st.session_state.admin_email)
                st.success(f"Participant ajouté. Code QR personnel : {pin}");st.code(pin);st.info('Le code n’est pas conservé en clair. En cas d’oubli, il sera réinitialisé.');
                if send_code and email.strip():
                    pp=one(ENGINE,'SELECT * FROM participants WHERE id=:p',{'p':pid})
                    okm,msgm=send_participant_code_email(pp,a,pin)
                    if okm:
                        st.success(msgm)
                    else:
                        st.warning(msgm)
                if create_portal:
                    pp=one(ENGINE,'SELECT * FROM participants WHERE id=:p',{'p':pid})
                    if not pp.get('birth_date') or not pp.get('email') or '@' not in pp.get('email',''):
                        st.warning('Participant ajouté, mais espace personnel non créé : date de naissance et email personnel valide sont obligatoires.')
                    else:
                        cand=find_beneficiary_candidates(ENGINE,pp['last_name'],pp['first_name'],pp['birth_date'])
                        exact=[x for x in cand if x.get('exact_match')]
                        if len(exact)==1:
                            link_participant_to_beneficiary(ENGINE,pid,exact[0]['id'],st.session_state.admin_email)
                            st.success('Participant rattaché automatiquement à son identité bénéficiaire permanente existante.')
                        elif cand:
                            st.warning('Participant ajouté. Une correspondance bénéficiaire possible existe, mais elle n’est pas certaine : utilisez la rubrique « Espace bénéficiaire » ci-dessous pour confirmer manuellement.')
                        else:
                            bid=create_beneficiary_from_participant(ENGINE,pid,st.session_state.admin_email)
                            tok=create_beneficiary_portal_invitation(ENGINE,bid,pp['email'],st.session_state.admin_email)
                            bb=one(ENGINE,'SELECT * FROM beneficiaries WHERE id=:b',{'b':bid});okb,msgb=send_beneficiary_invitation_email(bb,tok)
                            if okb: st.success(msgb)
                            else: st.warning(msgb)
                has_slots=bool(one(ENGINE,'SELECT COUNT(*) n FROM slots WHERE action_id=:a',{'a':a['id']})['n'])
                if has_slots:
                    ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ)
                sync_quality_schedule(a['id'],st.session_state.admin_email)
                if has_slots and normalize_action_status(a.get('status')) in ('ACTIVE','A_CLOTURER') and email.strip():
                    sent,failed=send_schedule_confirmations(a['id'],st.session_state.admin_email,participant_id=pid)
                    if sent: st.success('Le planning existant a été envoyé automatiquement à ce nouveau participant.')
                    elif failed: st.warning('Participant ajouté, mais son planning n’a pas pu être envoyé : '+failed[0][1])
                rerun()
    if parts:
        ids={f"{p['last_name']} {p['first_name']}":p['id'] for p in parts}
        with st.expander('✏️ Modifier un participant'):
            emap={f"{p['last_name']} {p['first_name']}":p for p in parts};el=st.selectbox('Participant à modifier',list(emap),key=f'editp{a["id"]}');ep=emap[el]
            with st.form(f'editpf{a["id"]}_{ep["id"]}'):
                c1,c2,c3=st.columns(3);ln=c1.text_input('Nom',value=ep.get('last_name') or '');bn=c2.text_input('Nom de naissance',value=ep.get('birth_name') or '');fn=c3.text_input('Prénom',value=ep.get('first_name') or '')
                bd='';
                if ep.get('birth_date'):
                    try: bd=datetime.fromisoformat(ep['birth_date']).strftime('%d/%m/%Y')
                    except Exception: bd=ep['birth_date']
                c1,c2,c3=st.columns(3);bds=c1.text_input('Date de naissance JJ/MM/AAAA',value=bd);em=c2.text_input('Email',value=ep.get('email') or '');emp=c3.text_input('Matricule',value=ep.get('employee_id') or '')
                c1,c2,c3=st.columns(3);co=c1.text_input('Entreprise',value=ep.get('company_name') or '');ph=c2.text_input('Téléphone',value=ep.get('phone') or '');ino=c3.text_input('N° action individuel',value=ep.get('individual_action_no') or '')
                savep=st.form_submit_button('Enregistrer les modifications')
            if savep:
                try: bdi=datetime.strptime(bds.strip(),'%d/%m/%Y').date().isoformat() if bds.strip() else None
                except ValueError: st.error('Date invalide : utilisez JJ/MM/AAAA.');bdi='__ERR__'
                if bdi!='__ERR__':
                    try:
                        vp=validate_participant_payload({'last_name':ln,'birth_name':bn or None,'first_name':fn,'birth_date':bdi,'email':em or None,'employee_id':emp or None,'company_name':co or None,'phone':ph or None,'individual_action_no':ino or None})
                        update_participant(ENGINE,ep['id'],{**vp,'active':1},st.session_state.admin_email);st.success('Participant modifié.');rerun()
                    except ValueError as ex: st.error(str(ex))
        with st.expander('🗑️ Supprimer définitivement un participant'):
            lab=st.selectbox('Participant à supprimer', ['—']+list(ids),key=f'delp{a["id"]}')
            if lab!='—':
                st.warning('Cette suppression efface définitivement ce participant et ses signatures, statuts de présence, relances, jetons et traces participant liées à cette action.')
                confirm=st.text_input(f"Saisissez SUPPRIMER {lab} pour confirmer",key=f'delptext{a["id"]}');pw=st.text_input('Votre mot de passe administrateur',type='password',key=f'delppw{a["id"]}')
                if st.button('🗑️ SUPPRIMER DÉFINITIVEMENT',key=f'delpbtn{a["id"]}'):
                    if confirm.strip()!=f'SUPPRIMER {lab}': st.error('Confirmation incorrecte.')
                    elif not admin_password_ok(ENGINE,st.session_state.admin_email,pw): st.error('Mot de passe administrateur incorrect.')
                    else:
                        okd,msgd=purge_participant(ENGINE,ids[lab],st.session_state.admin_email)
                        if okd:
                            st.success('Participant supprimé intégralement.')
                            rerun()
                        else:
                            st.error(msgd)
        st.markdown('### 👤 Espace bénéficiaire permanent')
        plab=st.selectbox('Participant pour l’espace personnel',list(ids),key=f'beneficiary_manage_{a["id"]}')
        pid_sel=ids[plab]; pp=one(ENGINE,'SELECT * FROM participants WHERE id=:p',{'p':pid_sel}); linked=beneficiary_for_participant(ENGINE,pid_sel)
        if linked:
            acc=one(ENGINE,'SELECT * FROM beneficiary_portal_accounts WHERE beneficiary_id=:b',{'b':linked['id']})
            st.success(f"Rattaché à {linked['public_id']} — {linked['first_name']} {linked['last_name']}")
            ps=beneficiary_portal_status(ENGINE,linked['id'])
            st.caption(f"Email de connexion : {(acc or {}).get('email') or linked.get('current_email') or 'non configuré'}")
            if ps['state']=='ACTIVE':
                st.success('Espace bénéficiaire activé.' + (f" Dernière connexion : {ps['last_login_at'].replace('T',' ')[:16]}" if ps.get('last_login_at') else ''))
            elif ps['state']=='INVITE':
                st.warning('Invitation envoyée, mais le bénéficiaire n’a pas encore activé son espace.')
            elif ps['state']=='DESACTIVE':
                st.error('Espace bénéficiaire désactivé.')
            else:
                st.info(ps['label'])
            c1,c2=st.columns(2)
            if c1.button('Envoyer / renouveler l’invitation espace',key=f'ben_inv_{pid_sel}',disabled=not bool(pp.get('email'))):
                try:
                    tok=create_beneficiary_portal_invitation(ENGINE,linked['id'],pp.get('email'),st.session_state.admin_email);bb=one(ENGINE,'SELECT * FROM beneficiaries WHERE id=:b',{'b':linked['id']});okb,msgb=send_beneficiary_invitation_email(bb,tok)
                    if okb: st.success(msgb)
                    else: st.warning(msgb)
                except Exception as ex: _ui_incident('operation_interface',ex)
            new_email=c2.text_input('Nouvel email de connexion',value=(acc or {}).get('email') or linked.get('current_email') or '',key=f'ben_email_{pid_sel}')
            if st.button('Enregistrer le nouvel email sans recréer la personne',key=f'ben_email_save_{pid_sel}'):
                try:
                    tok=update_beneficiary_email(ENGINE,linked['id'],new_email,st.session_state.admin_email)
                    target=dict(linked);target['current_email']=new_email
                    okb,msgb=send_beneficiary_invitation_email(target,tok)
                    if okb: st.success('Demande de changement enregistrée. La nouvelle adresse deviendra l’identifiant de connexion après vérification par email.')
                    else: st.warning(msgb)
                    rerun()
                except Exception as ex: _ui_incident('operation_interface',ex)
        else:
            if not pp.get('birth_date'):
                st.info('Ajoutez d’abord une date de naissance pour rechercher ou créer une identité bénéficiaire permanente.')
            else:
                cand=find_beneficiary_candidates(ENGINE,pp['last_name'],pp['first_name'],pp['birth_date'])
                if cand:
                    st.warning('Correspondance(s) possible(s) trouvée(s). Vérifiez avant de rattacher : aucune fusion n’est automatique.')
                    cmap={f"{x['last_name']} {x['first_name']} — {x['birth_date']} — {x['public_id']} — correspondance {x['match_score']} %":x for x in cand}
                    cl=st.selectbox('Espace existant possible',list(cmap),key=f'ben_candidate_{pid_sel}')
                    if st.button('CONFIRMER LE RATTACHEMENT À CET ESPACE',key=f'ben_link_{pid_sel}'):
                        link_participant_to_beneficiary(ENGINE,pid_sel,cmap[cl]['id'],st.session_state.admin_email);st.success('Rattachement effectué après confirmation.');rerun()
                st.caption('Si aucune correspondance n’est la bonne, vous pouvez créer une nouvelle identité.')
                can_create=bool(pp.get('email') and '@' in pp.get('email',''))
                if st.button('Créer une nouvelle identité + espace personnel',key=f'ben_create_{pid_sel}',disabled=not can_create):
                    try:
                        bid=create_beneficiary_from_participant(ENGINE,pid_sel,st.session_state.admin_email);tok=create_beneficiary_portal_invitation(ENGINE,bid,pp.get('email'),st.session_state.admin_email);bb=one(ENGINE,'SELECT * FROM beneficiaries WHERE id=:b',{'b':bid});okb,msgb=send_beneficiary_invitation_email(bb,tok)
                        if okb: st.success(msgb)
                        else: st.warning(msgb)
                        rerun()
                    except Exception as ex: _ui_incident('operation_interface',ex)
                if not can_create: st.info('Une adresse email personnelle valide est obligatoire pour créer l’espace.')

        st.markdown('**Réinitialiser un code personnel QR**')
        rlab=st.selectbox('Participant concerné',list(ids),key=f'pinreset{a["id"]}')
        if st.button('Générer un nouveau code à 4 chiffres',key=f'pinbtn{a["id"]}'):
            newpin=reset_participant_pin(ENGINE,ids[rlab],st.session_state.admin_email);st.success('Nouveau code généré :');st.code(newpin);pp=one(ENGINE,'SELECT * FROM participants WHERE id=:p',{'p':ids[rlab]});okm,msgm=send_participant_code_email(pp,a,newpin)
            if okm:
                st.success(msgm)
            else:
                st.info(msgm)

def calendar_tab(a):
    st.subheader('Calendrier et créneaux')
    slots=q(ENGINE,'SELECT * FROM slots WHERE action_id=:a ORDER BY slot_date,start_time',{'a':a['id']})
    total=sum(slot_duration_hours(s) for s in slots);delta=round(total-float(a['planned_hours'] or 0),2)
    if abs(delta)<0.01:
        st.markdown(f"<div class='c360-ok'>✅ Calendrier cohérent : <b>{total:g} h / {a['planned_hours']:g} h</b></div>",unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='c360-warn'>⚠️ Total des créneaux : <b>{total:g} h</b> — durée prévue : <b>{a['planned_hours']:g} h</b> — écart : <b>{delta:+g} h</b></div>",unsafe_allow_html=True)

    if normalize_action_status(a.get('status')) in ('BROUILLON','PLANIFIEE'):
        st.markdown('### Validation du planning')
        if abs(delta)<0.01 and slots:
            st.info('Le calendrier est cohérent. Vous pouvez maintenant valider le planning : l’action deviendra ACTIVE et le planning sera envoyé aux participants concernés.')
            activate_action_ui(a,'calendar')
        else:
            st.caption('La validation sera disponible lorsque le calendrier sera cohérent avec la durée prévue.')

    if slots:
        display=[]
        for i,x in enumerate(slots,1):
            initial='Au début' if int(x.get('send_offset_min') or 0)==slot_start_offset_minutes(x['start_time'],x['end_time']) else f"{x['send_offset_min']} min / fin"
            display.append({'Séance':i,'Date':format_app_date(x['slot_date']),'Début':format_app_time(x['start_time']),'Fin':format_app_time(x['end_time']),'Durée':slot_duration_hours(x),'Envoi initial':initial})
        st.dataframe(pd.DataFrame(display),use_container_width=True,hide_index=True)

    st.markdown('### Ajouter une nouvelle séance')
    last_date=date.fromisoformat(slots[-1]['slot_date']) if slots else date.today()
    last_start=dt_time.fromisoformat(slots[-1]['start_time']) if slots else dt_time(9,0)
    last_end=dt_time.fromisoformat(slots[-1]['end_time']) if slots else dt_time(10,30)
    with st.form(f'addslot_{a["id"]}',clear_on_submit=False):
        c1,c2,c3=st.columns(3)
        d=c1.date_input('Date de la nouvelle séance',value=last_date,key=f'd{a["id"]}',format=app_date_input_format())
        stt=c2.time_input('Début',value=last_start,key=f's{a["id"]}')
        ett=c3.time_input('Fin',value=last_end,key=f'e{a["id"]}')
        c1,c2,c3=st.columns(3)
        send_mode=c1.selectbox('Envoi du lien d’émargement',['Au début du créneau','10 min avant la fin','À la fin du créneau','Personnalisé'],key=f'sendmode{a["id"]}')
        custom=c2.number_input('Décalage personnalisé (min / fin)',min_value=-1440,max_value=1440,value=0,step=5,key=f'customsend{a["id"]}',disabled=send_mode!='Personnalisé')
        close=c3.number_input('Émargement possible après la fin pendant (min)',min_value=0,max_value=10080,value=1440,step=60,key=f'add_close_offset_{a["id"]}')
        st.caption('Les relances d’émargement sont manuelles. Aucun rappel automatique n’est programmé.')
        add=st.form_submit_button('➕ AJOUTER CETTE NOUVELLE SÉANCE',type='primary')
    if add:
        if send_mode=='Au début du créneau': send=slot_start_offset_minutes(stt.strftime('%H:%M'),ett.strftime('%H:%M'))
        elif send_mode=='10 min avant la fin': send=-10
        elif send_mode=='À la fin du créneau': send=0
        else: send=int(custom)
        add_slot(ENGINE,a['id'],d.isoformat(),stt.strftime('%H:%M'),ett.strftime('%H:%M'),st.session_state.admin_email,int(send),20,120,int(close))
        if one(ENGINE,'SELECT COUNT(*) n FROM participants WHERE action_id=:a AND active=1',{'a':a['id']})['n']:
            ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ)
        sync_quality_schedule(a['id'],st.session_state.admin_email)
        rerun()

    if not slots:
        return

    st.markdown('### Dupliquer une séance')
    st.caption('La dernière date du calendrier est proposée comme source. Après duplication, la nouvelle date deviendra automatiquement la source suivante.')
    dates=sorted(set(x['slot_date'] for x in slots))
    src=st.selectbox('Date source',dates,index=len(dates)-1,key=f'dupsrc{a["id"]}')
    src_date=date.fromisoformat(src)
    dst=st.date_input('Nouvelle date',value=src_date+__import__('datetime').timedelta(days=7),key=f'dup{a["id"]}',format=app_date_input_format())
    if st.button('Dupliquer cette journée vers la nouvelle date',key=f'dupbtn{a["id"]}'):
        if dst.isoformat()==src:
            st.error('La nouvelle date doit être différente de la date source.')
        else:
            for x in [z for z in slots if z['slot_date']==src]:
                add_slot(ENGINE,a['id'],dst.isoformat(),x['start_time'],x['end_time'],st.session_state.admin_email,x['send_offset_min'],x['reminder1_offset_min'],x['reminder2_offset_min'],x['close_offset_min'])
            ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ);sync_quality_schedule(a['id'],st.session_state.admin_email);rerun()

    with st.expander('✏️ Modifier une séance existante',expanded=False):
        edit_choices={f"Séance {i} — {x['slot_date']} {x['start_time']}–{x['end_time']}":x for i,x in enumerate(slots,1)}
        edit_lab=st.selectbox('Séance à modifier',list(edit_choices),key=f'editsel{a["id"]}');es=edit_choices[edit_lab]
        st.warning(f"Vous modifiez réellement {edit_lab}. Pour créer une autre séance, utilisez la zone « Ajouter une nouvelle séance » ci-dessus.")
        current_begin=int(es.get('send_offset_min') or 0)==slot_start_offset_minutes(es['start_time'],es['end_time'])
        with st.form(f'editslot{es["id"]}'):
            c1,c2,c3=st.columns(3);ed=c1.date_input('Date',value=date.fromisoformat(es['slot_date']),format=app_date_input_format());est=c2.time_input('Début',value=dt_time.fromisoformat(es['start_time']));eet=c3.time_input('Fin',value=dt_time.fromisoformat(es['end_time']))
            c1,c2=st.columns(2)
            edit_send_mode=c1.selectbox('Envoi initial',['Au début du créneau','Personnalisé'],index=0 if current_begin else 1)
            esend=c2.number_input('Décalage personnalisé (min / fin)',min_value=-1440,max_value=1440,value=int(es['send_offset_min']),step=5,disabled=edit_send_mode!='Personnalisé')
            eclose=st.number_input('Émargement possible après la fin pendant (min)',min_value=0,max_value=10080,value=int(es['close_offset_min']),step=60)
            st.caption('Relances automatiques désactivées : les relances restent manuelles.')
            reason=st.text_input('Motif de modification (recommandé si l’action a commencé)');save_slot=st.form_submit_button('Enregistrer les modifications de cette séance')
        if save_slot:
            final_send=slot_start_offset_minutes(est.strftime('%H:%M'),eet.strftime('%H:%M')) if edit_send_mode=='Au début du créneau' else int(esend)
            ok,msg=safe_update_slot(ENGINE,es['id'],{'slot_date':ed.isoformat(),'start_time':est.strftime('%H:%M'),'end_time':eet.strftime('%H:%M'),'send_offset_min':final_send,'reminder1_offset_min':int(es['reminder1_offset_min']),'reminder2_offset_min':int(es['reminder2_offset_min']),'close_offset_min':int(eclose),'reason':reason},st.session_state.admin_email)
            if ok:
                propagate_planning_change(ENGINE,a['id'],es['id'],'ADMIN_UPDATE',st.session_state.admin_email,base_url=BASE_URL,details={'reason':reason or None})
                sent,failed=send_planning_change_notifications(a['id'],es['id'],st.session_state.admin_email)
                if failed: st.warning('Séance modifiée et synchronisée. Certaines notifications email n’ont pas pu être envoyées.')
                else: st.success('Séance modifiée, échéances recalculées et personnes concernées informées.')
                rerun()
            else: st.error(msg)

    with st.expander('📅 Reporter une séance non encore réalisée',expanded=False):
        rep_choices={f"Séance {i} — {x['slot_date']} {x['start_time']}–{x['end_time']}":x for i,x in enumerate(slots,1)}
        rep_lab=st.selectbox('Séance à reporter',list(rep_choices),key=f'repsel{a["id"]}');rsrc=rep_choices[rep_lab]
        c1,c2,c3=st.columns(3);rpd=c1.date_input('Nouvelle date',value=date.fromisoformat(rsrc['slot_date']),key=f'rpd{rsrc["id"]}',format=app_date_input_format());rps=c2.time_input('Nouveau début',value=dt_time.fromisoformat(rsrc['start_time']),key=f'rps{rsrc["id"]}');rpe=c3.time_input('Nouvelle fin',value=dt_time.fromisoformat(rsrc['end_time']),key=f'rpe{rsrc["id"]}')
        rpr=st.text_input('Motif du report',key=f'rpr{rsrc["id"]}')
        if st.button('REPORTER CETTE SÉANCE',key=f'report{rsrc["id"]}'):
            ns=report_slot(ENGINE,rsrc['id'],rpd.isoformat(),rps.strftime('%H:%M'),rpe.strftime('%H:%M'),st.session_state.admin_email,rpr or 'Report')
            if ns:
                propagate_planning_change(ENGINE,a['id'],ns,'ADMIN_REPORT',st.session_state.admin_email,base_url=BASE_URL,details={'from_slot_id':rsrc['id'],'reason':rpr or 'Report'})
                sent,failed=send_planning_change_notifications(a['id'],ns,st.session_state.admin_email)
                if failed: st.warning('Séance reportée et synchronisée. Certaines notifications email n’ont pas pu être envoyées.')
                else: st.success('Séance reportée, échéances recalculées et personnes concernées informées.')
                rerun()
            else: st.error('Cette séance contient déjà une preuve ou ne peut plus être reportée. Utilisez absence/rattrapage si elle a déjà eu lieu.')

    with st.expander('🗑️ Supprimer une séance',expanded=False):
        choices={f"Séance {i} — {x['slot_date']} {x['start_time']}–{x['end_time']}":x['id'] for i,x in enumerate(slots,1)}
        ch=st.selectbox('Séance',list(choices),key=f'dels{a["id"]}');sid_del=choices[ch]
        if st.button('Supprimer cette séance si elle ne contient aucune preuve'):
            ok,msg=delete_slot(ENGINE,sid_del,st.session_state.admin_email)
            if ok:
                sync_quality_schedule(a['id'],st.session_state.admin_email)
                st.success('Séance supprimée.')
                rerun()
            else:
                st.error(msg)
        st.warning('Suppression définitive avec preuves : uniquement pour une erreur de saisie ou un dossier de test.')
        conf=st.text_input(f'Saisissez SUPPRIMER SEANCE {sid_del}',key=f'delsconf{a["id"]}');pw=st.text_input('Votre mot de passe administrateur',type='password',key=f'delspw{a["id"]}')
        if st.button('🗑️ SUPPRIMER DÉFINITIVEMENT LA SÉANCE',key=f'delshard{a["id"]}'):
            if conf.strip()!=f'SUPPRIMER SEANCE {sid_del}' or not admin_password_ok(ENGINE,st.session_state.admin_email,pw): st.error('Confirmation ou mot de passe incorrect.')
            else:
                ok,msg=purge_slot(ENGINE,sid_del,st.session_state.admin_email)
                if ok:
                    sync_quality_schedule(a['id'],st.session_state.admin_email)
                    st.success('Séance supprimée intégralement.')
                    rerun()
                else:
                    st.error(msg)

def dispatch_tab(a):
    st.subheader('Envois automatiques et relances')
    parts=q(ENGINE,'SELECT * FROM participants WHERE action_id=:a AND active=1',{'a':a['id']});slots=q(ENGINE,'SELECT * FROM slots WHERE action_id=:a ORDER BY slot_date,start_time',{'a':a['id']})
    if not parts or not slots: st.info('Ajoutez d’abord au moins un participant et un créneau.');return
    active_status=normalize_action_status(a.get('status')) in ('ACTIVE','A_CLOTURER')
    if not active_status:
        st.info('Action en BROUILLON : les échéances peuvent être préparées, mais le worker est bloqué et aucun email automatique ne partira avant activation.')
        st.markdown('### Activer l’action')
        activate_action_ui(a,'dispatch')
    if st.button('Préparer / actualiser toutes les demandes de signature',type='primary'):
        ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ);st.success('Liens personnels et envoi automatique initial préparés.');rerun()
    events=q(ENGINE,"""SELECT e.*,p.last_name,p.first_name,p.email,s.slot_date,s.start_time,s.end_time FROM email_events e JOIN participants p ON p.id=e.participant_id JOIN slots s ON s.id=e.slot_id WHERE p.action_id=:a ORDER BY e.due_at""",{'a':a['id']})
    if events:
        evrows=[]
        tzname=organization_runtime_config(ENGINE,a['id'])['timezone']
        for e in events:
            due=local_dt(e['due_at'],tzname).strftime('%d/%m/%Y %H:%M') if e.get('due_at') else ''
            sent_local=local_dt(e['sent_at'],tzname).strftime('%d/%m/%Y %H:%M') if e.get('sent_at') else ''
            evrows.append({'Nom':e['last_name'],'Prénom':e['first_name'],'Email':e.get('email') or '','Date séance':format_app_date(e['slot_date']),'Début':format_app_time(e['start_time']),'Fin':format_app_time(e['end_time']),'Type':e['event_type'],'Échéance (heure locale)':due,'Statut':e['status'],'Envoyé le':sent_local,'Dernière anomalie':friendly_mail_error(e.get('last_error'))})
        st.dataframe(pd.DataFrame(evrows),use_container_width=True,hide_index=True)
        st.caption("Historique technique des événements d'envoi : non supprimable pour conserver la traçabilité. Les relances se pilotent ci-dessous.")
    st.markdown('### Envoi / relance manuelle')
    smtp_enabled=bool(mail_cfg().get('enabled'))
    if smtp_enabled and active_status:
        email_parts=[p for p in parts if p.get('email')]
        if email_parts:
            pc={f"{p['last_name']} {p['first_name']} — {p['email']}":p for p in email_parts};pl=st.selectbox('Participant à relancer',list(pc),key=f'mailp{a["id"]}');pp=pc[pl]
            sc={f"{x['slot_date']} {x['start_time']}–{x['end_time']}":x for x in slots};sl=st.selectbox('Créneau à relancer',list(sc),key=f'mails{a["id"]}');ss=sc[sl]
            already_signed=one(ENGINE,"SELECT id FROM signatures WHERE participant_id=:p AND slot_id=:s AND status='VALIDE'",{'p':pp['id'],'s':ss['id']})
            if already_signed: st.success('Ce participant a déjà signé ce créneau : aucune relance d’émargement n’est nécessaire.')
            if st.button('Envoyer maintenant le lien personnel',disabled=bool(already_signed)):
                ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ);url=token_url(ENGINE,pp['id'],ss['id'],BASE_URL)
                cfg=mail_cfg();subject=f"Clarté360 — émargement — {a['action_no']}";body=f"<p>Bonjour {pp['first_name']},</p><p>Merci d'émarger votre présence pour <strong>{a['title']}</strong>, le {ss['slot_date']} de {ss['start_time']} à {ss['end_time']}.</p><p><a href='{url}' style='background:#008080;color:white;padding:12px 18px;text-decoration:none;border-radius:8px'>SIGNER MA PRÉSENCE</a></p><p>Ce lien personnel ne nécessite pas le code QR à 4 chiffres.</p>{privacy_notice_html(a['id'])}"
                try:
                    send_mail(cfg,pp['email'],subject,body);audit(ENGINE,'MANUAL_EMAIL_SENT',a['id'],st.session_state.admin_email,'participant',pp['id'],{'slot_id':ss['id'],'email':pp['email']});st.success('Email envoyé.')
                except Exception as ex: _ui_incident('envoi_email',ex,subject='L’envoi de l’email')
    elif not smtp_enabled:
        st.info('L’envoi manuel sera disponible dès que la configuration MAIL sera activée.')
    else:
        st.info('L’envoi manuel est disponible après activation de l’action.')

    st.markdown('### Journal des communications I9')
    current_reminder_config=get_online_reminder_preferences(ENGINE,a['id'])
    st.caption(f"Rappels Teams : premier à H−{current_reminder_config['online_reminder_first_minutes']} min, deuxième à H−{current_reminder_config['online_reminder_second_minutes']} min. Consultez ici A_ENVOYER (programmé), ENVOYE, ECHEC ou ANNULE. « MAJ WORKER » prépare la file mais n’expédie pas les emails.")
    if action_module_enabled(ENGINE,a['id'],'TEAMS') and not smtp_enabled:
        st.warning('Messagerie SMTP non activée : les rappels Teams sont préparés mais ne peuvent pas être envoyés.')
    comm=communication_journal(ENGINE,a['id'])
    if comm:
        status_labels={'A_ENVOYER':'À envoyer','EN_FILE':'En file','ENVOYE':'Envoyé','ECHEC':'Échec','RELANCE':'Relancé','ANNULE':'Annulé'}
        rows=[]
        for e in comm:
            who=(e.get('participant_first_name') or '')+' '+(e.get('participant_last_name') or '') if e.get('participant_id') else (e.get('trainer_name') or '')
            slot_label=(f"{e.get('slot_date')} {e.get('start_time')}–{e.get('end_time')}" if e.get('slot_date') else '')
            rows.append({'Type':e['communication_type'],'Destinataire':who.strip() or e.get('recipient_email') or '','Email':e.get('recipient_email') or '','Créneau':slot_label,'Déclenchement':'Automatique' if e.get('trigger_mode')=='AUTO' else 'Manuel','Statut':status_labels.get(e.get('status'),e.get('status')),'Prévu':e.get('due_at') or '','Envoyé':e.get('sent_at') or '','Anomalie':friendly_mail_error(e.get('last_error'))})
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        st.caption("Journal de traçabilité : les lignes envoyées ou annulées ne sont pas supprimées. Les nouvelles relances se gèrent dans les commandes de l'écran.")
    else:
        st.caption('Aucune communication I9 enregistrée pour cette action.')

    st.markdown('### Contresignatures intervenants')
    refresh_countersign_communications(ENGINE)
    pending_cs=[]
    for slx in slots:
        # A countersignature is not "awaited" before the slot has ended, unless every participant
        # already has a final status (e.g. all signatures collected early).
        tz_name=organization_runtime_config(ENGINE,a['id']).get('timezone') or TZ or 'Europe/Paris'
        current_local=datetime.now(ZoneInfo(tz_name))
        _, slot_end=slot_start_end(slx,tz_name)
        states=_slot_participant_states(ENGINE,slx['id'])
        all_final=bool(states) and not any(x.get('status')=='EN_ATTENTE' for x in states)
        if current_local < slot_end and not all_final:
            continue
        signed_ids={int(x['trainer_id']) for x in list_slot_countersignatures(ENGINE,slx['id']) if x.get('trainer_id') is not None}
        for tr in list_slot_trainers(ENGINE,slx['id']):
            if int(tr['trainer_id']) not in signed_ids:
                pending_cs.append((slx,tr))
    if not pending_cs:
        st.success('Toutes les contresignatures requises sont enregistrées.')
    else:
        st.warning(f"{len(pending_cs)} contresignature(s) intervenant encore attendue(s).")
        for slx,tr in pending_cs:
            c1,c2=st.columns([3,1]); c1.write(f"{slx['slot_date']} {slx['start_time']}–{slx['end_time']} — {tr.get('full_name') or 'Intervenant'} — {tr.get('email') or 'email absent'}")
            if c2.button('RELANCER',key=f"admin_cs_rem_{slx['id']}_{tr['trainer_id']}",disabled=not bool(tr.get('email')),use_container_width=True):
                try:
                    direct=f"{BASE_URL.rstrip('/')}?trainer_portal=1&action_id={a['id']}&slot_id={slx['id']}"
                    org=org_identity(a['id']); cfg=mail_cfg(); body=f"<p>Bonjour {tr.get('full_name') or ''},</p><p>Votre contresignature est toujours attendue pour le créneau du <strong>{slx['slot_date']} de {slx['start_time']} à {slx['end_time']}</strong>.</p><p><a href='{direct}'>FINALISER ET CONTRESIGNER</a></p><p>Le lien reste utilisable tant que votre contresignature n'est pas enregistrée.</p>"
                    send_mail(cfg,tr['email'],f"{org.get('name') or 'Organisme'} — rappel de contresignature — {a['action_no']}",body)
                    audit(ENGINE,'ADMIN_COUNTERSIGN_REMINDER',a['id'],st.session_state.admin_email,'slot',slx['id'],{'trainer_id':tr['trainer_id'],'email':tr['email']}); st.success('Rappel envoyé.')
                except Exception as ex: _ui_incident('envoi_email',ex,subject='Le rappel de contresignature')

    st.markdown('### Accès restreint intervenant')
    turl=trainer_url(ENGINE,a['id'],BASE_URL);st.code(turl);st.caption('Ce lien donne accès uniquement au suivi opérationnel de cette action : QR, absences, relances et contresignature.')
    st.markdown('### QR code d’un créneau')
    choices={f"{s['slot_date']} — {s['start_time']}–{s['end_time']}":s for s in slots};lab=st.selectbox('Choisir le créneau',list(choices),key=f'qr{a["id"]}');slot=choices[lab];url=public_slot_url(slot,BASE_URL)
    qr=qrcode.make(url);buf=io.BytesIO();qr.save(buf,format='PNG');c1,c2=st.columns([1,2]);c1.image(buf.getvalue(),width=220);c2.code(url);c2.caption('Le stagiaire saisit son nom et son code personnel à 4 chiffres avant de signer.')
    st.markdown('### Liens individuels')
    ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ)
    slot2=slot
    links=[]
    for p in parts: links.append({'Participant':f"{p['last_name']} {p['first_name']}",'Email':p.get('email'),'Lien':token_url(ENGINE,p['id'],slot2['id'],BASE_URL)})
    st.dataframe(pd.DataFrame(links),use_container_width=True,hide_index=True)

def tracking_tab(a):
    st.subheader('Suivi des signatures')
    parts=q(ENGINE,'SELECT * FROM participants WHERE action_id=:a AND active=1 ORDER BY last_name,first_name',{'a':a['id']});slots=q(ENGINE,'SELECT * FROM slots WHERE action_id=:a ORDER BY slot_date,start_time',{'a':a['id']});sigs=q(ENGINE,'SELECT * FROM signatures WHERE slot_id IN (SELECT id FROM slots WHERE action_id=:a)',{'a':a['id']});sm={(x['participant_id'],x['slot_id']):x for x in sigs}
    rows=[]
    for p in parts:
        r={'Participant':f"{p['last_name']} {p['first_name']}"}
        for s in slots:
            x=sm.get((p['id'],s['id']));at=one(ENGINE,'SELECT status FROM attendance_status WHERE participant_id=:p AND slot_id=:s',{'p':p['id'],'s':s['id']});r[f"{s['slot_date']} {s['start_time']}"]=('✅ '+local_dt(x['signed_at'],TZ).strftime('%H:%M')+(' · a posteriori' if x.get('is_late') else '')) if x else ('❌ ABSENT' if at and at['status']=='ABSENT' else ('➖' if at and at['status']=='NON_CONCERNE' else '⏳'))
        r['Heures justifiées']=actual_hours_for_participant(ENGINE,p['id']);rows.append(r)
    if rows: st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    pending=[(p,s) for p in parts for s in slots if (p['id'],s['id']) not in sm]
    st.caption(f"{len(pending)} signature(s) encore attendue(s).")
    st.markdown('### Gestion présence / absence')
    if parts and slots:
        pc={f"{p['last_name']} {p['first_name']}":p for p in parts};sc={f"{s['slot_date']} {s['start_time']}–{s['end_time']} #{s['id']}":s for s in slots};c1,c2=st.columns(2);pp=pc[c1.selectbox('Participant',list(pc),key=f'atp{a["id"]}')];ss=sc[c2.selectbox('Créneau',list(sc),key=f'ats{a["id"]}')];reason=st.text_input('Motif / observation',key=f'atr{a["id"]}')
        c1,c2=st.columns(2)
        if c1.button('Marquer ABSENT',key=f'abs{a["id"]}'):
            oka,msga=set_attendance_status(ENGINE,pp['id'],ss['id'],'ABSENT',reason,st.session_state.admin_email)
            if oka: rerun()
            else: st.error(msga)
        if c2.button('Remettre EN ATTENTE',key=f'wait{a["id"]}'): set_attendance_status(ENGINE,pp['id'],ss['id'],'EN_ATTENTE',reason,st.session_state.admin_email);rerun()
        st.markdown('### Créer une séance de rattrapage')
        absent=q(ENGINE,"""SELECT p.* FROM attendance_status x JOIN participants p ON p.id=x.participant_id WHERE x.slot_id=:s AND x.status='ABSENT'""",{'s':ss['id']});opts={f"{p['last_name']} {p['first_name']}":p['id'] for p in absent};sel=st.multiselect('Absents concernés',list(opts),default=list(opts));c1,c2,c3=st.columns(3);rd=c1.date_input('Date du rattrapage',key=f'rd{a["id"]}',format=app_date_input_format());rs=c2.time_input('Début rattrapage',value=dt_time(9,0),key=f'rs{a["id"]}');re=c3.time_input('Fin rattrapage',value=dt_time(12,0),key=f're{a["id"]}')
        if st.button('Créer le créneau de rattrapage',key=f'catch{a["id"]}'):
            if not sel: st.error('Sélectionnez au moins un participant absent.')
            else: ns=create_catchup_slot(ENGINE,ss['id'],rd.isoformat(),rs.strftime('%H:%M'),re.strftime('%H:%M'),[opts[x] for x in sel],st.session_state.admin_email);ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ);st.success(f'Rattrapage créé : créneau #{ns}.');rerun()

# J2 : one administrative workbench for one canonical Quality case.
# Called identically from the general dashboard and an action's Quality tab.
def render_quality_case_workbench(action_id=None, action_ids=None, key='quality', status_filter=None, focus_event_id=None):
    events=list_quality_events(ENGINE,action_id=action_id)
    if focus_event_id is not None: events=[event for event in events if event['id']==int(focus_event_id)]
    if action_ids is not None:
        permitted=set(action_ids)
        events=[x for x in events if x.get('action_id') in permitted]
    if status_filter=='open':
        events=[x for x in events if x.get('status') not in {'CLOTURE','REFUSE','CLASSE_SANS_SUITE'}]
    st.markdown('### Fiches Qualité et actions correctives')
    if not events:
        st.info('Aucune fiche Qualité dans ce périmètre.')
        return
    closed={'CLOTURE','REFUSE','CLASSE_SANS_SUITE'}
    st.caption('Une fiche commune aux deux niveaux de navigation. Les réponses et les changements de statut restent historisés ; les destinataires concernés reçoivent une notification interne.')
    st.dataframe(pd.DataFrame([{'Réf.':x['public_id'],'Action':x.get('action_no') or '—',
        'Origine':x.get('origin') or '—','Nature':x.get('event_type') or '—','Objet':x.get('subject') or '',
        'Statut':x.get('status') or '—','Responsable':x.get('owner_name') or '—'} for x in events]),use_container_width=True,hide_index=True)
    labels={f"{ev['public_id']} — {ev.get('action_no') or 'sans action'} — {ev.get('subject') or ''}":ev for ev in events}
    selected=st.selectbox('Ouvrir une fiche Qualité',list(labels),key=f'{key}_j2_case_select')
    ev=labels[selected]; case=quality_case(ENGINE,ev['id'])
    st.markdown(f"#### {ev['public_id']} — {ev.get('subject') or ''}")
    st.caption(f"Action : {ev.get('action_no') or 'non rattachée'} · Source : {ev.get('origin') or '—'} · Statut : {ev['status']}")
    st.write(ev.get('description') or 'Aucune description enregistrée.')
    # J3: concise triage for a questionnaire's R12/I06 comment, same canonical case.
    if ev.get('family')=='QUESTIONNAIRES' and ev.get('origin') in ('QUESTIONNAIRE_R12_I06','QUESTIONNAIRE_POINT_FAIBLE','QUESTIONNAIRE') and ev.get('status') not in {'CLOTURE','REFUSE','CLASSE_SANS_SUITE'}:
        with st.expander('Traitement court de cette remarque questionnaire',expanded=False):
            decisions={'Prendre en compte':'PRISE_EN_COMPTE','Demander des précisions':'RETOUR_DEMANDE',
                'Classer avec justification':'CLASSE','Ouvrir une action corrective':'PLAN_ACTION'}
            with st.form(f'{key}_j3_short_event_{ev["id"]}'):
                decision_label=st.selectbox('Décision rapide',list(decisions))
                short_comment=st.text_area('Motif / réponse — toujours historisé')
                submitted=st.form_submit_button('Valider le traitement court')
            if submitted:
                try:
                    quality_short_treatment(ENGINE,st.session_state.admin_email,decisions[decision_label],short_comment,event_id=ev['id'])
                    st.success('Décision ajoutée à la chronologie. Les notifications internes sont disponibles.');rerun()
                except ValueError as ex:st.error(str(ex))
    with st.form(f'{key}_quality_edit_{ev["id"]}'):
        state_list=list(QUALITY_EVENT_STATUSES)
        c1,c2,c3=st.columns(3)
        new_status=c1.selectbox('Statut Qualité',state_list,index=state_list.index(ev['status']) if ev['status'] in state_list else 0)
        choices=quality_owner_choices(ENGINE)
        labels_owner=['— Non affecté —']+[x['label'] for x in choices]
        old_label=next((x['label'] for x in choices if x['owner_name']==(ev.get('owner_name') or '')),'— Non affecté —')
        selected_owner=c2.selectbox('Responsable',labels_owner,index=labels_owner.index(old_label))
        old_date=None
        try:old_date=date.fromisoformat(str(ev.get('due_at') or '')[:10]) if ev.get('due_at') else None
        except ValueError:pass
        new_date=c3.date_input('Échéance',value=old_date,format=app_date_input_format())
        severity=['MINEURE','MAJEURE','CRITIQUE']; urgency=['NORMALE','HAUTE','URGENTE']
        col1,col2=st.columns(2)
        new_severity=col1.selectbox('Gravité',severity,index=severity.index(ev['severity']) if ev.get('severity') in severity else 0)
        new_urgency=col2.selectbox('Urgence',urgency,index=urgency.index(ev['urgency']) if ev.get('urgency') in urgency else 0)
        qual=st.text_area('Qualification / analyse',value=ev.get('qualification') or '')
        immediate=st.text_area('Mesure immédiate',value=ev.get('immediate_action') or '')
        cause=st.text_area('Analyse des causes',value=ev.get('cause_analysis') or '')
        criteria=st.text_area('Vérification d’efficacité attendue',value=ev.get('effectiveness_criteria') or '')
        effective=st.text_area('Résultat de la vérification',value=ev.get('effectiveness_result') or '')
        closure=st.text_area('Décision et motif de clôture / classement',value=ev.get('closure_comment') or '')
        saved=st.form_submit_button('Enregistrer la fiche Qualité',type='primary')
    if saved:
        try:
            owner=next((x['owner_name'] for x in choices if x['label']==selected_owner),None)
            updated=update_quality_event(ENGINE,ev['id'],st.session_state.admin_email,status=new_status,
                owner_name=owner,severity=new_severity,urgency=new_urgency,due_at=new_date.isoformat() if new_date else None,
                qualification=qual,immediate_action=immediate,cause_analysis=cause,
                effectiveness_criteria=criteria,effectiveness_result=effective,closure_comment=closure)
            st.success('Fiche enregistrée, décision historisée.' if updated else 'Aucune modification à enregistrer.');rerun()
        except ValueError as ex:st.error(str(ex))
    st.markdown('#### Notes, réponses et historique de correspondance')
    links=case['sources']
    directions={'Note interne (administration)':'INTERNE'}
    if any(x['source_kind']=='TRAINER_REPORT' for x in links):directions['Réponse à l’intervenant']='VERS_INTERVENANT'
    if any(x['source_kind']=='BENEFICIARY_REPORT' for x in links):directions['Réponse au bénéficiaire']='VERS_BENEFICIAIRE'
    with st.form(f'{key}_quality_message_{ev["id"]}',clear_on_submit=True):
        channel_label=st.selectbox('Destinataire de la note / réponse',list(directions))
        message=st.text_area('Nouveau message — conserve les réponses précédentes')
        send=st.form_submit_button('Enregistrer le message')
    if send:
        try:
            add_quality_case_message(ENGINE,ev['id'],st.session_state.admin_email,message,directions[channel_label])
            st.success('Message ajouté à la chronologie de la fiche.');rerun()
        except ValueError as ex:st.error(str(ex))
    messages=case['messages']
    if messages:
        st.dataframe(pd.DataFrame([{'Date':format_app_datetime(x['created_at']),'Auteur':x['author'],'Type':x['direction'],
            'Destinataire':x.get('recipient') or '—','Message':x['message']} for x in messages]),use_container_width=True,hide_index=True)
    else:st.caption('Aucun échange enregistré pour cette fiche.')
    with st.expander('Historique immuable des décisions et changements',expanded=False):
        histories=case['history']
        if histories:
            st.dataframe(pd.DataFrame([{'Date':format_app_datetime(x['created_at']),'Auteur':x['actor'],'Modification':x['change_kind'],
               'Avant':x.get('before_json') or '—','Après':x.get('after_json') or '—'} for x in histories]),
               use_container_width=True,hide_index=True)
        else:st.caption('Fiche issue d’une version antérieure : historique des changements non encore disponible.')
        if links:
            st.caption('Sources d’origine conservées : '+', '.join(f"{x['source_kind']} #{x['source_id']}" for x in links))
    st.markdown('#### Actions correctives et préventives')
    capas=case['actions']
    if capas:
        st.dataframe(pd.DataFrame([{'N°':x['id'],'Action':x['title'],'Responsable':x.get('owner_name') or '—',
            'Échéance':format_app_deadline(x.get('due_at')),'Statut':x['status']} for x in capas]),use_container_width=True,hide_index=True)
        ca_map={f"#{x['id']} — {x['title']}":x for x in capas}
        csel=st.selectbox('Modifier une action corrective',list(ca_map),key=f'{key}_capa_sel_{ev["id"]}')
        ca=ca_map[csel]
        with st.form(f'{key}_capa_update_{ca["id"]}'):
            capa_statuses=['A_FAIRE','EN_COURS','EN_ATTENTE','A_VERIFIER','TERMINEE','ANNULEE']
            c1,c2=st.columns(2)
            cst=c1.selectbox('Statut CAPA',capa_statuses,index=capa_statuses.index(ca['status']))
            cowner=c2.text_input('Responsable CAPA',value=ca.get('owner_name') or '')
            evidence=st.text_input('Référence de preuve',value=ca.get('evidence_ref') or '')
            effic=st.text_area('Résultat d’efficacité',value=ca.get('effectiveness_result') or '')
            csave=st.form_submit_button('Enregistrer l’action corrective')
        if csave:
            update_quality_event_action(ENGINE,ca['id'],st.session_state.admin_email,status=cst,
                owner_name=cowner,evidence_ref=evidence,effectiveness_result=effic)
            st.success('Action corrective mise à jour et historisée.');rerun()
    with st.expander('Ajouter une action corrective ou préventive',expanded=False):
        with st.form(f'{key}_new_capa_{ev["id"]}',clear_on_submit=True):
            title=st.text_input('Action à réaliser')
            description=st.text_area('Description')
            responsible=st.text_input('Responsable de l’action')
            due=st.date_input('Échéance',value=None,format=app_date_input_format())
            create=st.form_submit_button('Ajouter au plan d’action')
        if create and title.strip():
            add_quality_event_action(ENGINE,ev['id'],title.strip(),st.session_state.admin_email,
               description,owner_name=responsible,due_at=due.isoformat() if due else None)
            st.success('CAPA ajoutée à la fiche de référence.');rerun()


def quality_legacy_reconciliation_widget(action_id=None,scope_ids=None,key='quality_reconcile'):
    unmatched=quality_unlinked_sources(ENGINE,action_id=action_id)
    if scope_ids is not None:
        permitted=set(scope_ids);unmatched=[x for x in unmatched if x.get('action_id') in permitted]
    if not unmatched:return
    with st.expander(f'Données Qualité historiques non rapprochées ({len(unmatched)})',expanded=False):
        st.caption('Ces enregistrements ne sont PAS supprimés ni fusionnés sur une ressemblance. Ils restent consultables ; un rapprochement exige une confirmation explicite.')
        st.dataframe(pd.DataFrame([{'Type':x['source_kind'],'ID source':x['id'],
            'Action interne':x.get('action_id'),'Objet':x.get('subject') or x.get('title') or '—',
            'Statut historique':x.get('status') or '—'} for x in unmatched]),use_container_width=True,hide_index=True)
        suggestions=suggest_quality_links(ENGINE,action_id=action_id)
        if scope_ids is not None:suggestions=[x for x in suggestions if x['action_id'] in permitted]
        if suggestions:
            m={f"{x['source_kind']} #{x['source_id']} → {x['public_id']}":x for x in suggestions}
            choice=st.selectbox('Rapprochement exact proposé (à confirmer)',list(m),key=f'{key}_select')
            selection=m[choice]
            confirmation=st.checkbox('J’ai comparé les deux références et confirme ce lien',key=f'{key}_confirmed')
            if st.button('Confirmer le rattachement historique',disabled=not confirmation,key=f'{key}_submit'):
                try:
                    link_quality_source(ENGINE,selection['id'],selection['source_kind'],selection['source_id'],st.session_state.admin_email)
                    st.success('Rattachement historique confirmé sans supprimer les sources.');rerun()
                except ValueError as ex: st.error(str(ex))
        else:st.caption('Aucune correspondance unique ne peut être proposée en toute sécurité.')

# J3 - simple, shared survey campaign overview and concise review controls.
def render_quality_campaign_pilotage(action_id=None,organization_id=None,prestation_type=None,key='quality_j3'):
    overview=quality_campaign_pilotage(ENGINE,organization_id=organization_id,
        prestation_type=prestation_type,action_id=action_id)
    dashboard=quality_dashboard_v31(ENGINE,organization_id=organization_id,
        prestation_type=prestation_type,action_id=action_id)
    st.markdown('### Indicateurs questionnaires — échelles séparées')
    st.caption('Les notes /5 utilisent exclusivement les réponses 1–5 valides. NPS (0–10), N/A et textes ne sont jamais mélangés aux moyennes sur 5.')
    cols=st.columns(5)
    groups=[('HOT','À chaud'),('COLD','À froid'),('TRAINER','Intervenant'),('CLIENT','Client / prescripteur'),('OPCO','OPCO')]
    for col,(kind,label) in zip(cols,groups):
        record=dashboard['by_kind'].get(kind,{})
        if kind=='CLIENT':
            other=dashboard['by_kind'].get('PRESCRIBER',{})
            first=quality_campaign_pilotage_summary(ENGINE,organization_id,prestation_type,action_id,('CLIENT','PRESCRIBER'))
            val=first.get('score');completed=first['completed'];total=first['invitations']
        else:
            val=record.get('score');completed=record.get('responses',0);total=record.get('invitations',0)
        col.metric(label, '—' if val is None else f'{val:.2f}/5',f'{completed}/{total} réponse(s)' if total else 'Aucune campagne')
    st.markdown('### Campagnes, échéances, envois et relances')
    rows=overview['rows']
    if not rows:
        st.info('Aucune campagne qualité pour ce périmètre.')
    else:
        formatted=[]
        for r in rows:
            formatted.append({'ID':r['id'],'Action':r['action_no'],'Type':r['campaign_kind'],
              'Questionnaire':r['questionnaire_title'],'Répondant':r.get('respondent') or '—',
              'Statut':r['status'],'Disponibilité':r['availability'],
              'Échéance':format_app_deadline(r.get('due_at')),
              'Envoi initial': 'Oui' if r['initial_sent'] else 'Non',
              'Relances envoyées':r['sent_reminders'],'Relances en attente':r['pending_reminders'],
              'Répondu le':str(r.get('completed_at') or '')[:16]})
        st.dataframe(pd.DataFrame(formatted),use_container_width=True,hide_index=True)
        selector={f"#{r['id']} — {r['action_no']} — {r['campaign_kind']} — {r.get('respondent') or 'sans nom'}":r for r in rows}
        choice=st.selectbox('Ouvrir une campagne',list(selector),key=f'{key}_campaign')
        camp=selector[choice]
        st.caption(f"Statut : {camp['status']} · Envois : {camp['sent_reminders']} relance(s) réalisée(s) · Échéance : {camp.get('due_at') or '—'}")
        c1,c2=st.columns(2)
        if c1.button('Préparer une relance manuelle',key=f'{key}_remind_{camp["id"]}',disabled=camp['status']=='COMPLETED'):
            try:
                queue_quality_manual_reminder(ENGINE,camp['id'],st.session_state.admin_email)
                st.success('Relance placée dans la file du worker ; le même questionnaire est réutilisé.');rerun()
            except ValueError as ex:st.warning(str(ex))
        if camp['status']=='COMPLETED':
            try:
                pdf=quality_response_pdf(ENGINE,camp['id'])
                c2.download_button('PDF du questionnaire reçu',pdf,f"{camp['action_no']}_qualite_{camp['id']}.pdf",'application/pdf',key=f'{key}_pdf_{camp["id"]}')
            except Exception as ex:_ui_incident('pdf_qualite_j3',ex,subject='Le PDF questionnaire')
        with st.expander('Traçabilité des envois (lecture seule)',expanded=False):
            hist=quality_campaign_email_history(ENGINE,camp['id'])
            if hist:st.dataframe(pd.DataFrame([{k:v for k,v in h.items() if k!='last_error'} for h in hist]),use_container_width=True,hide_index=True)
            else:st.caption('Aucun envoi enregistré.')
    st.markdown('### Analyses des réponses par rubrique')
    summary=quality_management_summary(ENGINE,organization_id=organization_id,
        prestation_type=prestation_type,action_id=action_id)
    if summary.get('nps_score') is not None:
        st.caption(f"NPS : {summary['nps_score']:+g} (calculé séparément à partir des réponses de 0 à 10 ; non affiché sur 5).")
    stats=quality_question_stats(ENGINE,organization_id=organization_id,
        prestation_type=prestation_type,action_id=action_id)
    if not stats:st.info('Aucune réponse reçue pour les filtres sélectionnés.')
    else:
        groups={}
        for row in stats:groups.setdefault(row['Rubrique'],[]).append(row)
        summaries=[]
        for rubric,records in groups.items():
            valid=sum(x['Notes valides 1-5'] for x in records)
            total=sum(x['_sum_1_5'] for x in records)
            summaries.append({'Thème':rubric,'Questions':len(records),
                'Réponses enregistrées':sum(x['Réponses'] for x in records),
                'Notes 1–5':valid,'Moyenne /5':round(total/valid,2) if valid else None})
        st.dataframe(pd.DataFrame(summaries),use_container_width=True,hide_index=True)
        selected_rubric=st.selectbox('Explorer un thème',list(groups),key=f'{key}_rubric')
        with st.expander(f'Détail — {selected_rubric}',expanded=False):
            data=[{'Question':x['Question'],'Échelle':x['Échelle'],'Réponses':x['Réponses'],
                'Notes 1–5':x['Notes valides 1-5'],'Moyenne /5':x['Moyenne']} for x in groups[selected_rubric]]
            st.dataframe(pd.DataFrame(data),use_container_width=True,hide_index=True)


def render_quality_short_review(action_id=None,scope_ids=None,key='quality_j3'):
    pts=quality_review_points(ENGINE,action_id=action_id,open_only=True)
    if scope_ids is not None:
        allowed=set(scope_ids);pts=[p for p in pts if p['action_id'] in allowed]
    st.markdown('### Notes faibles des questionnaires (≤ 3/5)')
    if not pts:
        st.success('Aucun point faible en attente de première qualification dans ce périmètre.')
        return
    st.dataframe(pd.DataFrame([{'ID':x['id'],'Action':x['action_no'],'Questionnaire':x['campaign_kind'],
         'Question':x['question_text'],'Note /5':x['score'],'Statut':x['status']} for x in pts]),use_container_width=True,hide_index=True)
    choices={f"#{x['id']} — {x['action_no']} — {x['campaign_kind']} — {x['score']}/5 — {x['question_text'][:70]}":x for x in pts}
    option=st.selectbox('Examiner une réponse',list(choices),key=f'{key}_review_select')
    selected=choices[option]
    st.caption(f"Origine : campagne #{selected['campaign_id']} · Réponse #{selected.get('response_id') or '—'} · Question : {selected['question_code']}")
    decisions={"Prendre en compte et suivre":'PRISE_EN_COMPTE',
        "Demander des précisions":'RETOUR_DEMANDE',
        "Classer avec justification":'CLASSE',
        "Créer une action corrective (CAPA)":'PLAN_ACTION'}
    with st.form(f'{key}_quick_review_form_{selected["id"]}',clear_on_submit=True):
        label=st.selectbox('Traitement court',list(decisions))
        reason=st.text_area('Analyse / réponse / justification — conservée dans l’historique')
        submitted=st.form_submit_button('Enregistrer la décision',type='primary')
    if submitted:
        try:
            quality_short_treatment(ENGINE,st.session_state.admin_email,decisions[label],reason,point_id=selected['id'])
            st.success('Décision enregistrée dans la fiche Qualité de référence et historisée.');rerun()
        except ValueError as ex:st.error(str(ex))


def render_quality_history(action_id=None,scope_ids=None,key='quality_j3'):
    st.markdown('### Historique des événements et des décisions')
    events=list_quality_events(ENGINE,action_id=action_id)
    if scope_ids is not None:events=[x for x in events if x.get('action_id') in set(scope_ids)]
    pts=quality_review_points(ENGINE,action_id=action_id,open_only=False)
    if scope_ids is not None:pts=[x for x in pts if x['action_id'] in set(scope_ids)]
    if pts:
        with st.expander(f'Décisions relatives aux notes faibles ({len(pts)})',expanded=False):
            st.dataframe(pd.DataFrame([{'Action':x['action_no'],'Campagne':x['campaign_kind'],
                'Question':x['question_text'],'Note /5':x['score'],'Décision':x.get('decision') or 'À examiner',
                'Commentaire':x.get('decision_comment') or '', 'Traitée par':x.get('reviewed_by') or '—',
                'Date':format_app_datetime(x.get('reviewed_at'))} for x in pts]),use_container_width=True,hide_index=True)
    if not events:st.caption('Aucune fiche Qualité historisée dans ce périmètre.');return
    st.dataframe(pd.DataFrame([{'Référence':x['public_id'],'Action':x.get('action_no') or '—',
        'Origine':x.get('origin') or '—','Objet':x.get('subject') or '',
        'Statut':x['status'],'Dernière mise à jour':format_app_datetime(x.get('updated_at'))} for x in events]),use_container_width=True,hide_index=True)
    choices={f"{x['public_id']} — {x.get('subject') or ''}":x for x in events}
    selected=choices[st.selectbox('Lire la chronologie de la fiche',list(choices),key=f'{key}_history_select')]
    case=quality_case(ENGINE,selected['id'])
    st.caption(f"Fiche {selected['public_id']} · Statut : {selected['status']} · Action : {selected.get('action_no') or '—'}")
    st.write(selected.get('description') or 'Aucune description.')
    if case['messages']:
        st.markdown('**Messages et réponses successifs**')
        st.dataframe(pd.DataFrame([{'Date':format_app_datetime(m['created_at']),'Auteur':m['author'],
            'Type':m['direction'],'Message':m['message']} for m in case['messages']]),use_container_width=True,hide_index=True)
    if case['history']:
        with st.expander('Journal des décisions et changements',expanded=False):
            st.dataframe(pd.DataFrame([{'Date':format_app_datetime(m['created_at']),'Auteur':m['actor'],
                'Opération':m['change_kind'],'Avant':m.get('before_json') or '',
                'Après':m.get('after_json') or ''} for m in case['history']]),use_container_width=True,hide_index=True)
    if case['sources']:
        st.caption('Sources liées : '+', '.join(f"{x['source_kind']} #{x['source_id']}" for x in case['sources']))
    if case['actions']:
        st.dataframe(pd.DataFrame([{'Action CAPA':x['title'],'Statut':x['status'],
            'Responsable':x.get('owner_name') or '—','Échéance':format_app_deadline(x.get('due_at'))} for x in case['actions']]),use_container_width=True,hide_index=True)


def quality_tab(a):
    st.subheader('Qualité de l’action')
    enabled=[]
    if a.get('use_quality_hot'):enabled.append('à chaud')
    if a.get('use_quality_cold'):enabled.append('à froid')
    if a.get('use_trainer_feedback'):enabled.append('retour intervenant')
    st.caption('Modules activés : '+(', '.join(enabled) if enabled else 'aucun')+'. Une même fiche et un même historique sont utilisés dans la Qualité générale et dans cette action.')
    views=st.tabs(['À traiter','Enquêtes et indicateurs','Historique'])
    with views[0]:
        render_quality_short_review(action_id=a['id'],key=f'quality_action_{a["id"]}')
        # J2 common administrative Quality case; no legacy competing edit screen.
        render_quality_case_workbench(action_id=a['id'],key=f"quality_action_{a['id']}",status_filter='open')
    with views[1]:
        try:
            due=standard_quality_due(ENGINE,a['id'],'HOT')
            date_ref=local_dt(due,organization_runtime_config(ENGINE,a['id'])['timezone'])
            st.caption('Fin de référence : '+date_ref.strftime('%d/%m/%Y'))
            if a.get('use_quality_cold'):
                st.caption('Évaluation à froid : M+6 pour le bilan de compétences ; J+90 ou date spécifique pour les autres prestations.')
            if st.button('Préparer les campagnes qualité standard',key=f'prepquality{a["id"]}',disabled=not bool(enabled)):
                try:
                    made=prepare_quality_campaigns(ENGINE,a['id'],BASE_URL,st.session_state.admin_email)
                    st.success(f'{len(made)} campagne(s) créée(s).' if made else 'Campagnes existantes conservées et échéances vérifiées.');rerun()
                except ValueError as ex:st.error(str(ex))
        except ValueError:
            st.warning('Renseigner la date de fin ou le planning avant de préparer les campagnes standard.')
        render_quality_campaign_pilotage(action_id=a['id'],key=f'quality_action_{a["id"]}')
    with views[2]:
        render_quality_history(action_id=a['id'],key=f'quality_action_{a["id"]}')
        quality_legacy_reconciliation_widget(action_id=a['id'],key=f"quality_legacy_action_{a['id']}")


def documents_tab(a):
    st.subheader('Documents et archivage')
    st.markdown('### Contacts client et transmission')
    with st.expander('Destinataires client',expanded=False):
        with st.form(f'client_contacts_{a["id"]}'):
            ca=st.text_input('Contact administratif',value=a.get('client_admin_email') or '')
            cf=st.text_input('Contact formation / accompagnement',value=a.get('client_training_email') or '')
            cq=st.text_input('Contact qualité',value=a.get('client_quality_email') or '')
            cb=st.text_input('Contact facturation',value=a.get('client_billing_email') or '')
            co=st.text_input('Autre contact',value=a.get('client_other_email') or '')
            transmit=st.checkbox('Transmettre le dossier final stagiaire au client',value=bool(a.get('transmit_final_bundle')))
            tq=st.checkbox('Responsable qualité / donneur d’ordre',value=bool(a.get('send_final_to_quality',1)))
            tf=st.checkbox('Contact mise en place',value=bool(a.get('send_final_to_training',1)))
            c1,c2,c3=st.columns(3);of=c1.text_input('Autre — prénom',value=a.get('final_other_first_name') or '');ol=c2.text_input('Autre — nom',value=a.get('final_other_last_name') or '');oe=c3.text_input('Autre — email',value=a.get('final_other_email') or '')
            sv=st.form_submit_button('Enregistrer les destinataires')
        if sv:
            try:
                set_action_client_contacts(ENGINE,a['id'],ca,cf,cq,cb,co,st.session_state.admin_email)
                configure_final_transmission(ENGINE,a['id'],transmit,tq,tf,of,ol,oe,st.session_state.admin_email)
                st.success('Destinataires enregistrés.');rerun()
            except ValueError as ex:
                st.error(str(ex))
    if normalize_action_status(a.get('status')) in ('CLOTUREE','ARCHIVEE'):
        try:
            bundle=action_final_bundle(ENGINE,a['id'],False,st.session_state.admin_email)
            st.download_button('Télécharger le dossier final collectif',bundle,f"{a['action_no']}_dossier_final.zip",'application/zip',use_container_width=True)
            st.caption('Destinataires dossier final : '+(', '.join(action_client_recipients(ENGINE,a['id'],'FINAL')) or 'aucun contact configuré')+' · Qualité à froid : '+(', '.join(action_client_recipients(ENGINE,a['id'],'QUALITY')) or 'aucun contact qualité configuré'))
        except Exception as ex: _ui_incident('dossier_final',ex,subject='Le dossier final',level='warning')
    transmissions=q(ENGINE,"SELECT transmission_type,recipient_email,document_name,status,sent_at,last_error,created_at FROM client_transmissions WHERE action_id=:a ORDER BY id DESC",{'a':a['id']})
    if transmissions:
        st.markdown('### Journal des transmissions client')
        st.dataframe(pd.DataFrame(transmissions),use_container_width=True,hide_index=True)
        st.caption("Historique de preuve des transmissions : lecture seule volontaire. Les destinataires futurs se modifient dans « Destinataires client ».")
    completed_quality=[c for c in list_quality_campaigns(ENGINE,a['id']) if c.get('status')=='COMPLETED']
    if completed_quality:
        st.markdown('### Évaluations qualité PDF')
        for c in completed_quality:
            who=c.get('trainer_full_name') or f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip() or 'Répondant'
            try:
                data=quality_response_pdf(ENGINE,c['id'])
                st.download_button(f"{c['campaign_kind']} — {who}",data,f"{a['action_no']}_{c['campaign_kind']}_{c['id']}.pdf",'application/pdf',key=f"doc_quality_{c['id']}")
            except Exception as ex: _ui_incident('pdf_qualite_action',ex,action_id=a['id'],entity_type='quality_campaign',entity_id=c['id'],subject='Le PDF qualité',level='warning')
    st.markdown('### Bibliothèque documentaire de l’action')
    stats=document_storage_stats(ENGINE);st.caption(f"Stockage physique mutualisé : {stats['files']} fichier(s), {stats['bytes']/1024/1024:.2f} Mo, {stats['references']} référence(s) logique(s).")
    with st.expander('Déposer un document par n° d’action',expanded=False):
        st.caption(f"Action sélectionnée : {a['action_no']}. Les supports de cours sont communs au groupe. Les autres pièces ne sont jamais partagées automatiquement.")
        category=st.selectbox('Destinataires et catégorie',
           ['COURS','ADMINISTRATIF_INDIVIDUEL','ADMINISTRATIF','CLIENT_CONTRACTUEL'],
           format_func=lambda x:{'COURS':'Support pédagogique collectif',
             'ADMINISTRATIF_INDIVIDUEL':'Document administratif pour UN bénéficiaire',
             'ADMINISTRATIF':'Document interne - administration',
             'CLIENT_CONTRACTUEL':'Pièce du donneur d’ordre - administration / futur espace client'}[x],
           key=f'doccat_{a["id"]}')
        target=None
        if category=='ADMINISTRATIF_INDIVIDUEL':
            people=q(ENGINE,'''SELECT p.id participant_id,b.id beneficiary_id,b.last_name,b.first_name
              FROM participants p JOIN beneficiaries b ON b.id=p.beneficiary_id
              WHERE p.action_id=:a AND p.active=1 ORDER BY b.last_name,b.first_name''',{'a':a['id']})
            if people:
                lab=st.selectbox('Destinataire nominatif',
                   [f"{p['last_name']} {p['first_name']} (participation #{p['participant_id']})" for p in people],
                   key=f'doc_person_{a["id"]}')
                target=people[[f"{p['last_name']} {p['first_name']} (participation #{p['participant_id']})" for p in people].index(lab)]
            else: st.warning('Aucun bénéficiaire lié à cette action. Rattacher le participant avant le dépôt individuel.')
        updoc=st.file_uploader('Fichier (25 Mo maximum)',type=['pdf','json','doc','docx','xls','xlsx','ppt','pptx','txt','csv','jpg','jpeg','png','webp','zip'],key=f'action_doc_{a["id"]}')
        publish_now=st.checkbox('Publier immédiatement aux destinataires autorisés',value=True,key=f'action_doc_publish_{a["id"]}')
        st.caption('Un brouillon reste réservé à l’administration. Enregistrer et publier sont deux opérations distinctes.')
        revision_reason=st.text_input('Motif d’une nouvelle version finalisée (si nécessaire)',key=f'action_doc_reason_{a["id"]}')
        if st.button('DÉPOSER LE DOCUMENT',type='primary',key=f'action_doc_btn_{a["id"]}',disabled=updoc is None or (category=='ADMINISTRATIF_INDIVIDUEL' and target is None)):
            try:
                progress=st.progress(0,text='Traitement du document après transfert par le navigateur...')
                rid,h,dedup=store_document_for_actor(ENGINE,'ADMIN',st.session_state.admin_email,updoc.getvalue(),updoc.name,a['id'],
                   category=category,beneficiary_id=(target or {}).get('beneficiary_id'),participant_id=(target or {}).get('participant_id'),
                   publish=publish_now,revision_reason=revision_reason,
                   progress_callback=lambda label,ratio:progress.progress(int(ratio*100),text=label))
                st.success('Document enregistré dans le périmètre choisi. '+('Contenu déjà connu.' if dedup else 'Nouveau fichier.'));rerun()
            except (ValueError,PermissionError) as ex: st.error(str(ex))
            except Exception as ex: _ui_incident('operation_interface',ex)
    refs=list_admin_documents(ENGINE,st.session_state.admin_email,a['id'])
    if refs:
        st.dataframe(pd.DataFrame([{'Nom':d['display_name'],'Catégorie':d['category'],
             'Version':d.get('version_no') or 1,'Publication':d.get('publication_status') or 'PUBLIE',
             'Validation':d.get('validation_status') or 'A_VERIFIER','Provenance':d.get('source_kind') or 'HUMAIN',
             'Taille (Ko)':round(d['size_bytes']/1024,1),'SHA-256':d['sha256'][:16]+'…',
             'Déposé par':d.get('uploaded_by') or ''} for d in refs]),use_container_width=True,hide_index=True)
        rmap={f"#{d['id']} — {d['display_name']}":d for d in refs};rl=st.selectbox('Document à gérer',list(rmap),key=f'docref_{a["id"]}');rr=rmap[rl];path=Path(rr['storage_path'])
        cdl,cdel=st.columns(2)
        if path.is_file():
            try:
                doc_bytes=read_document_for_actor(ENGINE,rr['id'],'ADMIN',st.session_state.admin_email,action_id=a['id'])
                cdl.download_button('Télécharger',doc_bytes,file_name=rr['display_name'],key=f'adm_doc_dl_{rr["id"]}',use_container_width=True)
            except PermissionError:
                cdl.caption('Pièce individuelle confidentielle : contenu réservé au bénéficiaire et à son intervenant habilité.')
        st.caption(f"Version {rr.get('version_no') or 1} · Publication {rr.get('publication_status') or 'PUBLIE'} · "
                   f"Validation {rr.get('validation_status') or 'A_VERIFIER'} · Conservation {rr.get('retention_class') or 'À définir'}")
        with st.expander('Publication et validation',expanded=False):
            cpub,cval,cfin=st.columns(3)
            published=rr.get('publication_status')=='PUBLIE'
            if cpub.button('Retirer de la publication' if published else 'Publier la version',key=f'doc_pub_{rr["id"]}'):
                try:
                    set_document_publication(ENGINE,rr['id'],not published,st.session_state.admin_email)
                    st.success('Publication mise à jour.');rerun()
                except (ValueError,PermissionError) as ex:st.error(str(ex))
            if cval.button('Valider',key=f'doc_validate_{rr["id"]}',disabled=rr.get('validation_status')=='FINALISE'):
                try:set_document_validation(ENGINE,rr['id'],'VALIDE',st.session_state.admin_email);st.success('Validé.');rerun()
                except (ValueError,PermissionError) as ex:st.error(str(ex))
            if cfin.button('Finaliser / verrouiller',key=f'doc_finalize_{rr["id"]}',disabled=rr.get('validation_status')=='FINALISE'):
                try:set_document_validation(ENGINE,rr['id'],'FINALISE',st.session_state.admin_email);st.success('Version verrouillée.');rerun()
                except (ValueError,PermissionError) as ex:st.error(str(ex))
        with st.expander('Historique des versions (métadonnées)',expanded=False):
            st.dataframe(pd.DataFrame(list_document_versions_admin(ENGINE,rr['id'],st.session_state.admin_email)),
                         use_container_width=True,hide_index=True)
        confirmation=cdel.checkbox('Confirmer le retrait de la liste',key=f'adm_doc_confirm_{rr["id"]}')
        if cdel.button('Archiver la référence',key=f'adm_doc_del_{rr["id"]}',disabled=not confirmation,use_container_width=True):
            delete_document_reference(ENGINE,rr['id'],st.session_state.admin_email)
            st.success('Référence archivée ; le fichier et la traçabilité restent conservés selon les règles de conservation applicables.');rerun()
    else: st.info('Aucun document de bibliothèque pour cette action.')

    if refs:
        try:
            zdocs=export_action_documents_zip(ENGINE,a['id'],'ADMIN',st.session_state.admin_email)
            st.download_button('Exporter uniquement les documents de bibliothèque autorisés (ZIP)',zdocs,
                f"{a['action_no']}_documents_autorises.zip",'application/zip',key=f'admin_doc_zip_{a["id"]}')
        except Exception as ex: _ui_incident('export_documents_action',ex,action_id=a['id'],level='warning')
    try:
        cpdf=collective_pdf(ENGINE,a['id']);st.download_button('Télécharger la feuille collective PDF',cpdf,f"{a['action_no']}_emargement_collectif.pdf",'application/pdf')
    except Exception as e: _ui_incident('pdf_collectif',e,action_id=a['id'],subject='Le PDF collectif')
    parts=q(ENGINE,'SELECT * FROM participants WHERE action_id=:a ORDER BY last_name,first_name',{'a':a['id']})
    if parts:
        labels={f"{p['last_name']} {p['first_name']}":p for p in parts};lab=st.selectbox('Participant',list(labels),key=f'docp{a["id"]}');p=labels[lab]
        st.caption(f"Durée réellement justifiée : {actual_hours_for_participant(ENGINE,p['id']):g} h / {float(a.get('planned_hours') or 0):g} h prévues.")
        c1,c2=st.columns(2)
        ipdf=individual_pdf(ENGINE,p['id']);c1.download_button('Feuille individuelle PDF',ipdf,f"{a['action_no']}_{p['last_name']}_{p['first_name']}_emargement.pdf",'application/pdf',use_container_width=True)
        preview=certificate_pdf(ENGINE,p['id'],draft=True);c2.download_button('Aperçu certificat — NON DÉFINITIF',preview,f"{a['action_no']}_{p['last_name']}_{p['first_name']}_certificat_APERCU.pdf",'application/pdf',use_container_width=True)
        ok_pre,issues_pre=can_issue_certificate(ENGINE,p['id'],require_closed=False)
        if normalize_action_status(a.get('status'))!='CLOTUREE':
            if ok_pre:
                st.info("Toutes les preuves de ce participant sont réunies. L'action doit maintenant être clôturée pour éditer le certificat définitif.")
            else:
                st.warning('Certificat définitif encore bloqué : '+ ' ; '.join(issues_pre[:5]))
        ok_close,close_issues=action_can_close(ENGINE,a['id'])
        if normalize_action_status(a.get('status'))!='CLOTUREE':
            if st.button('✅ Clôturer l’action et autoriser les certificats définitifs',type='primary',disabled=not ok_close,key=f'close_action_{a["id"]}'):
                okc,ic=close_action(ENGINE,a['id'],st.session_state.admin_email)
                if okc:
                    st.success('Action clôturée.')
                    rerun()
                else:
                    st.error(' ; '.join(ic))
            if not ok_close: st.caption('Clôture impossible : '+ ' ; '.join(close_issues[:6]))
        ok_cert,issues=can_issue_certificate(ENGINE,p['id'],require_closed=True)
        if ok_cert:
            cert=certificate_pdf(ENGINE,p['id']);st.download_button('Certificat de réalisation DÉFINITIF',cert,f"{a['action_no']}_{p['last_name']}_{p['first_name']}_certificat_realisation.pdf",'application/pdf',use_container_width=True)
        elif normalize_action_status(a.get('status'))=='CLOTUREE': st.warning('Certificat définitif indisponible : '+ ' ; '.join(issues[:5]))
    js=export_action_json(ENGINE,a['id']);st.download_button('Exporter le dossier JSON portable',js,f"{a['action_no']}_dossier.json",'application/json')
    try:
        pdfs={'emargement_collectif.pdf':collective_pdf(ENGINE,a['id'])};z=export_action_zip(ENGINE,a['id'],pdfs);st.download_button('Exporter l’archive complète ZIP',z,f"{a['action_no']}_archive_complete.zip",'application/zip')
    except Exception as e: _ui_incident('archive_action',e,action_id=a['id'],subject='La génération de l’archive')

def audit_tab(a):
    st.subheader('Piste d’audit')
    logs=q(ENGINE,'SELECT * FROM audit_log WHERE action_id=:a ORDER BY id DESC',{'a':a['id']})
    if logs: st.dataframe(pd.DataFrame(logs),use_container_width=True,hide_index=True)

def reminders_screen():
    header('Clarté360 — Relances','Relances manuelles et régularisations à traiter')
    orgs=list_organizations(ENGINE,active_only=True); om={'Tous':None,**{o['name']:o['id'] for o in orgs}}
    c1,c2=st.columns(2); ol=c1.selectbox('Organisme',list(om),key='rem_org'); kind=c2.selectbox('Type de questionnaire',['Tous','HOT','COLD','TRAINER'],key='rem_kind')
    qrows=quality_reminders(ENGINE,organization_id=om[ol],kind=None if kind=='Tous' else kind)
    st.subheader('Questionnaires non revenus')
    if not qrows: st.success('Aucun questionnaire en attente pour ces filtres.')
    else:
        display=[]
        for r in qrows:
            who=r.get('trainer_full_name') or f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
            display.append({'Sélection':False,'Campagne':r['campaign_id'],'Action':r['action_no'],'Type':r['campaign_kind'],'Répondant':who,'Email':r.get('trainer_email') or r.get('participant_email') or '','Statut':r['status'],'Relances manuelles':r.get('manual_reminder_count') or 0})
        df=pd.DataFrame(display)
        edited=st.data_editor(df,use_container_width=True,hide_index=True,disabled=[c for c in df.columns if c!='Sélection'],key='quality_reminders_editor')
        selected_ids=[int(x) for x in edited.loc[edited['Sélection']==True,'Campagne'].tolist()]
        if st.button('Relancer les questionnaires sélectionnés',type='primary',disabled=not selected_ids):
            ok=0; errors=[]
            for cid in selected_ids:
                try: queue_quality_manual_reminder(ENGINE,cid,st.session_state.admin_email);ok+=1
                except Exception as ex: errors.append(f'#{cid}: erreur technique'); log_ui_exception(ENGINE,'quality_manual_reminder_batch',ex,actor=st.session_state.get('admin_email','admin'),entity_type='quality_campaign',entity_id=cid)
            if ok: st.success(f'{ok} relance(s) manuelle(s) placée(s) dans la file du worker. Aucun nouveau questionnaire n’a été créé.')
            if errors: st.warning(' · '.join(errors))
            rerun()
    st.subheader('Émargements à régulariser')
    arows=attendance_regularization_items(ENGINE,organization_id=om[ol])
    if not arows: st.success('Aucun émargement en attente de régularisation.')
    else:
        st.dataframe(pd.DataFrame([{'Action':r['action_no'],'Date':format_app_date(r['slot_date']),'Horaire':f"{format_app_time(r['start_time'])}–{format_app_time(r['end_time'])}",'Participant':f"{r['last_name']} {r['first_name']}",'Email':r.get('email') or ''} for r in arows]),use_container_width=True,hide_index=True)
        st.caption('La régularisation elle-même reste réalisée dans la fiche de l’action afin de conserver les contrôles de preuve et d’absence existants.')
    footer()

def quality_management_screen():
    header('Clarté360 — Pilotage Qualité','Suivi transversal des enquêtes, difficultés, signalements et plans d’amélioration')
    direct=st.session_state.get('j4_jump_quality')
    if direct:
        case=one(ENGINE,'SELECT id,action_id FROM quality_events WHERE id=:i',{'i':direct})
        if case:
            st.info('Ouverture directe de la fiche Qualité depuis une notification ; le dossier reste ouvert jusqu’à sa clôture métier, indépendamment de la notification lue.')
            if st.button('Retour au pilotage Qualité',key='j4_return_quality'):
                st.session_state.pop('j4_jump_quality',None);rerun()
            render_quality_case_workbench(action_id=case.get('action_id'),key='j4_direct',focus_event_id=direct)
            return
        st.session_state.pop('j4_jump_quality',None)

    orgs=list_organizations(ENGINE,active_only=True)
    orgmap={'Tous':None,**{x['name']:x['id'] for x in orgs}}
    c1,c2,c3=st.columns(3)
    org_label=c1.selectbox('Organisme',list(orgmap),key='qm_org')
    prestation=c2.selectbox('Prestation',['Tous','FORMATION','BILAN_COMPETENCES','VAE','COACHING','MENTORAT','AUTRE'],key='qm_pt')
    org_id=orgmap[org_label];kind=None if prestation=='Tous' else prestation
    actions=q(ENGINE,'SELECT id,action_no,title,organization_id,prestation_type FROM actions ORDER BY action_no')
    if org_id:actions=[a for a in actions if a.get('organization_id')==org_id]
    if kind:actions=[a for a in actions if (a.get('prestation_type') or '').upper()==kind]
    options={'Toutes les actions':None,**{f"{a['action_no']} — {a['title']}":a['id'] for a in actions}}
    selected=c3.selectbox('Action',list(options),key='qm_action')
    action_id=options[selected]
    filtered_ids=[action_id] if action_id is not None else [a['id'] for a in actions]
    # When no filter is active, allow visibility of historical orphan QE cases in
    # read-only history (never attach them to an action by assumption).
    scope_ids=None if action_id is None and org_id is None and kind is None else filtered_ids
    counts=quality_source_counts(ENGINE,filtered_ids)
    plan=quality_plan_counts(ENGINE,filtered_ids)
    if scope_ids is None:
        orphans=[x for x in list_quality_events(ENGINE) if x.get('action_id') is None]
        if orphans:
            st.warning(f'{len(orphans)} fiche(s) Qualité historique(s) sans action : consultables dans Historique. Aucun rattachement automatique.')
    views=st.tabs(['À traiter','Enquêtes et indicateurs','Historique'])
    with views[0]:
        st.markdown('### Points Qualité à traiter')
        stats=st.columns(4)
        for col,(label,key) in zip(stats,[('Notes ≤ 3/5','review_points'),('Difficultés / aléas','difficulties'),
            ('Réclamations','complaints'),('Signalements / contacts','reports')]):col.metric(label,counts[key])
        stats2=st.columns(4)
        for col,(label,key) in zip(stats2,[('Non-conformités','nonconformities'),('Incidents','incidents'),
            ('Suggestions','suggestions'),('Autres','other')]):col.metric(label,counts[key])
        st.markdown('### Plan d’action Qualité')
        pcols=st.columns(5)
        for col,(label,key) in zip(pcols,[('Total','total'),('En cours','in_progress'),('À vérifier','to_verify'),
            ('Clôturées','closed'),('En retard','overdue')]):col.metric(label,plan[key])
        render_quality_short_review(action_id=action_id,scope_ids=scope_ids,key='quality_global')
        # J2 case is identical here and in action Quality; only the scope differs.
        render_quality_case_workbench(action_id=action_id,action_ids=scope_ids,key='quality_global',status_filter='open')
        with st.expander('Créer un événement Qualité',expanded=False):
            if actions:
                amap={f"{x['action_no']} — {x['title']}":x['id'] for x in actions}
                selected_action=st.selectbox('Action concernée',list(amap),key='qm_ev_action')
                family=st.selectbox('Famille',['EXPRESSION','CONFORMITE','QUESTIONNAIRES','AUDIT','TECHNIQUE','AMELIORATION'],key='qm_ev_family')
                event_type=st.selectbox('Nature',['INFORMATION','OBSERVATION','SUGGESTION','DIFFICULTE','RECLAMATION','NON_CONFORMITE','INCIDENT','ECART_DOCUMENTAIRE','ECART_ORGANISATIONNEL','OPPORTUNITE'],key='qm_ev_type')
                subject=st.text_input('Objet',key='qm_ev_subject')
                details=st.text_area('Description',key='qm_ev_details')
                severity=st.selectbox('Gravité',['MINEURE','MAJEURE','CRITIQUE'],key='qm_ev_severity')
                if st.button('Créer la fiche Qualité',disabled=not subject.strip(),key='qm_ev_create'):
                    create_quality_event(ENGINE,family,event_type,subject.strip(),details.strip(),st.session_state.admin_email,action_id=amap[selected_action],severity=severity)
                    st.success('Fiche créée et historisée.');rerun()
            else:st.caption('Aucune action dans ce périmètre.')
    with views[1]:
        render_quality_campaign_pilotage(action_id=action_id,organization_id=org_id,prestation_type=kind,key='quality_global')
    with views[2]:
        render_quality_history(action_id=action_id,scope_ids=scope_ids,key='quality_global')
        quality_legacy_reconciliation_widget(action_id=action_id,
            scope_ids=scope_ids,key='quality_legacy_global')
        plan_rows=quality_general_action_plan(ENGINE,action_id=action_id)
        if scope_ids is not None and action_id is None:plan_rows=[x for x in plan_rows if x.get('action_no') in {a['action_no'] for a in actions}]
        if plan_rows:
            with st.expander("Suivi du plan d'action général — consolidé et preuves",expanded=False):
                st.dataframe(pd.DataFrame([{'Événement':x['event_ref'],'Action':x.get('action_no') or '—',
                    'Décision':x.get('action_title_capa') or '', 'Responsable':x.get('owner_name') or '',
                    'Échéance':format_app_deadline(x.get('due_at')), 'Statut':x.get('status') or '',
                    'Efficacité':x.get('effectiveness_result') or ''} for x in plan_rows]),use_container_width=True,hide_index=True)
    footer()


def studies_screen():
    header('Clarté360 — Études PIP/O*NET','Pilotage méthodologique pseudonymisé')
    study_dir=secret('pip_connector','study_dir','')
    storage=pip_study_storage_status(study_dir)
    if not storage['ready']:
        if storage['reason']=='NOT_CONFIGURED':
            st.warning("Le stockage pseudonymisé PIP n'est pas configuré (`pip_connector.study_dir`).")
        else:
            st.error(f"Stockage d'études PIP indisponible : {storage['reason']}. Vérifier le répertoire configuré sur le VPS.")
        footer(); return
    st.caption(f"Stockage d'études opérationnel · {storage['json_files']} fichier(s) source pseudonymisé(s).")
    records=load_pip_study_records(study_dir)
    if not records:
        st.info("Aucun enregistrement d'étude pseudonymisé disponible.")
        footer(); return
    st.caption("Cet espace lit uniquement les enregistrements de recherche pseudonymisés produits par le PIP RC5. Aucune identité, adresse e-mail ou téléphone n'est affiché ou exporté.")
    c1,c2,c3,c4=st.columns(4)
    journeys=['Tous']+sorted({str(r.get('journey')) for r in records if r.get('journey')})
    timings=['Tous']+sorted({str(r.get('onet_selected_timing')) for r in records if r.get('onet_selected_timing')})
    banks=['Toutes']+sorted({str(r.get('pip_bank_version')) for r in records if r.get('pip_bank_version')})
    statuses=['Tous','COMMENCE','TERMINE','ABANDONNE']
    journey=c1.selectbox('Parcours',journeys); timing=c2.selectbox('Moment O*NET',timings); bank=c3.selectbox('Banque PIP',banks); status=c4.selectbox('Statut',statuses)
    filters={'journey':None if journey=='Tous' else journey,'timing':None if timing=='Tous' else timing,'bank_version':None if bank=='Toutes' else bank,'status':None if status=='Tous' else status,'consent':True}
    filtered=filter_study_records(records,filters); sm=study_summary(filtered)
    a,b,c,d=st.columns(4);a.metric('Enregistrements',sm['total']);b.metric('Terminés',sm['terminees']);c.metric('PIP + O*NET',sm['pip_onet']);d.metric('Consentements recherche',sm['consentements'])
    st.caption(f"PIP seul : {sm['pip_seul']} · PRE-PIP : {sm['pre_pip']} · POST-PIP : {sm['post_pip']} · Commencés : {sm['commencees']} · Abandons observables : {sm['abandons']}")
    st.markdown('### Qualité des items PIP')
    iq=study_item_quality(filtered)
    if iq: st.dataframe(pd.DataFrame(iq),use_container_width=True,hide_index=True)
    else: st.info("Pas encore de réponses 1–5 exploitables dans ce filtre.")
    st.markdown('### Comparaison PIP ↔ O*NET')
    pairs=study_onet_pairs(filtered)
    st.write(f"{len(pairs)} passation(s) consentie(s) comportent les deux instruments. PRE et POST restent séparés ; aucun score n'est fusionné ou recalculé par Gestion des actions.")
    st.markdown('### Export pseudonymisé')
    purpose=st.text_input("Finalité de l'export",value='Pilotage méthodologique PIP/O*NET')
    e1,e2=st.columns(2)
    if e1.button('Préparer CSV pseudonymisé',disabled=not bool(purpose.strip())):
        data=export_study_csv(ENGINE,filtered,st.session_state.admin_email,purpose.strip(),filters);st.session_state['_study_export_csv']=data
    if e2.button('Préparer XLSX pseudonymisé',disabled=not bool(purpose.strip())):
        data=export_study_xlsx(ENGINE,filtered,st.session_state.admin_email,purpose.strip(),filters);st.session_state['_study_export_xlsx']=data
    if st.session_state.get('_study_export_csv'): st.download_button('Télécharger CSV',st.session_state['_study_export_csv'],'clarte360_etude_pip_onet_pseudonymisee.csv','text/csv')
    if st.session_state.get('_study_export_xlsx'): st.download_button('Télécharger XLSX',st.session_state['_study_export_xlsx'],'clarte360_etude_pip_onet_pseudonymisee.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    st.markdown('### Journal des exports')
    hist=q(ENGINE,'SELECT actor,purpose,format,record_count,schema_version,exported_at FROM study_export_events ORDER BY id DESC LIMIT 50')
    if hist:
        st.dataframe(pd.DataFrame(hist),use_container_width=True,hide_index=True)
        st.caption("Journal des exports : lecture seule volontaire pour préserver la traçabilité des extractions pseudonymisées.")
    footer()


def crm_screen():
    header('Clarté360 — Contacts / Prospects','CRM-0 RC2 : fiche compacte, notes, tâches et actions liées')
    st.caption("CRM opérationnel léger. Les données CRM restent strictement séparées des études pseudonymisées PIP/O*NET.")

    with st.expander('➕ Ajouter un contact / prospect', expanded=False):
        with st.form('crm_add_contact'):
            c1,c2=st.columns(2); fn=c1.text_input('Prénom *'); ln=c2.text_input('Nom *')
            c1,c2=st.columns(2); em=c1.text_input('E-mail *'); ph=c2.text_input('Téléphone')
            c1,c2=st.columns(2); job=c1.text_input('Fonction'); comp=c2.text_input('Entreprise')
            interests=st.text_input("Centres d'intérêt (séparés par des virgules)")
            c1,c2=st.columns(2); marketing=c1.checkbox('Consentement marketing explicite recueilli'); rgpd=c2.text_input("Version information RGPD",value='I9-G')
            add=st.form_submit_button('AJOUTER LE CONTACT',type='primary')
        if add:
            try:
                cc=create_crm_contact(ENGINE,fn,ln,em,phone=ph or None,job_title=job or None,company=comp or None,
                    interests=[x.strip() for x in interests.split(',') if x.strip()],marketing_consent=marketing,
                    rgpd_notice_version=rgpd or None,actor=st.session_state.admin_email)
                st.session_state['crm_selected_contact_id']=cc['id']; st.success('Contact ajouté.'); rerun()
            except ValueError as ex: st.error(str(ex))

    rows=list_crm_contacts(ENGINE)
    if not rows:
        st.info('Aucun contact / prospect enregistré.'); footer(); return

    # Tableau CRM compact avec commandes directes.
    st.markdown('### Contacts')
    search=st.text_input('🔎 Rechercher dans le CRM',placeholder='Nom, entreprise, e-mail ou téléphone',key='crm_table_search')
    filtered=find_crm_contacts(ENGINE,search,250) if search.strip() else rows
    if not filtered:
        st.info('Aucun contact correspondant à cette recherche.')
    else:
        hdr=st.columns([1.25,1.6,2.0,1.5,1.0,.8,.8])
        for col,label in zip(hdr,['ID','Nom','E-mail','Entreprise','Statut','Ouvrir','Suppr.']): col.caption(f'**{label}**')
        for x in filtered:
            cols=st.columns([1.25,1.6,2.0,1.5,1.0,.8,.8])
            cols[0].write(x['public_id']); cols[1].write(f"{x['first_name']} {x['last_name']}")
            cols[2].write(x.get('email') or '—'); cols[3].write(x.get('company') or '—'); cols[4].write((x.get('status') or '').replace('_',' '))
            if cols[5].button('✏️',key=f"crm_open_{x['id']}",help='Ouvrir / modifier la fiche'):
                st.session_state['crm_selected_contact_id']=x['id']; rerun()
            if cols[6].button('🗑️',key=f"crm_delete_{x['id']}",help='Supprimer définitivement la fiche CRM'):
                st.session_state['crm_delete_contact_id']=x['id']; st.session_state['crm_selected_contact_id']=x['id']; rerun()

    delete_id=st.session_state.get('crm_delete_contact_id')
    if delete_id:
        dc=one(ENGINE,'SELECT * FROM crm_contacts WHERE id=:i',{'i':delete_id})
        if dc:
            linked=list_crm_action_links(ENGINE,delete_id); tasks=list_crm_tasks(ENGINE,delete_id); events=list_crm_events(ENGINE,delete_id,500)
            with st.container(border=True):
                st.error(f"Suppression définitive de la fiche CRM {dc['public_id']} — {dc['first_name']} {dc['last_name']}")
                st.caption(f"Seront supprimés : fiche CRM, {len(tasks)} tâche(s), {len(events)} événement(s)/note(s) et {len(linked)} liaison(s) avec des actions. Les actions elles-mêmes, les bénéficiaires et les études PIP/O*NET ne seront jamais supprimés.")
                conf=st.text_input(f"Saisissez SUPPRIMER {dc['public_id']}",key=f'crm_del_conf_{delete_id}')
                pw=st.text_input('Votre mot de passe administrateur',type='password',key=f'crm_del_pw_{delete_id}')
                c1,c2=st.columns(2)
                if c1.button('🗑️ SUPPRIMER DÉFINITIVEMENT',type='primary',key=f'crm_del_confirm_{delete_id}'):
                    if conf.strip()!=f"SUPPRIMER {dc['public_id']}": st.error('Confirmation incorrecte.')
                    elif not admin_password_ok(ENGINE,st.session_state.admin_email,pw): st.error('Mot de passe administrateur incorrect.')
                    else:
                        ok,msg=purge_crm_contact(ENGINE,delete_id,st.session_state.admin_email)
                        if ok:
                            st.session_state.pop('crm_delete_contact_id',None); st.session_state.pop('crm_selected_contact_id',None)
                            st.success('Fiche CRM et contenu CRM supprimés. Les actions et autres référentiels sont conservés.'); rerun()
                        else: st.error(msg)
                if c2.button('ANNULER',key=f'crm_del_cancel_{delete_id}'):
                    st.session_state.pop('crm_delete_contact_id',None); rerun()

    rows=list_crm_contacts(ENGINE)
    selected_id=st.session_state.get('crm_selected_contact_id')
    if selected_id and not any(x['id']==selected_id for x in rows): selected_id=None
    if not selected_id: selected_id=rows[0]['id']
    cmap={f"{x['public_id']} — {x['first_name']} {x['last_name']} — {x['email']}":x for x in rows}
    labels=list(cmap); default_idx=next((i for i,k in enumerate(labels) if cmap[k]['id']==selected_id),0)
    label=st.selectbox('Fiche ouverte',labels,index=default_idx,key='crm_open_select'); c=cmap[label]
    st.session_state['crm_selected_contact_id']=c['id']

    st.markdown(f"## {c['first_name']} {c['last_name']} — {c['public_id']}")
    k1,k2,k3,k4=st.columns(4)
    k1.metric('Statut',(c.get('status') or '—').replace('_',' ')); k2.metric('Marketing','Oui' if c.get('marketing_consent') else 'Non')
    k3.metric('Source',(c.get('source') or '—').replace('_',' ')); k4.metric('Actions liées',len(list_crm_action_links(ENGINE,c['id'])))
    st.caption(f"Créé : {format_app_datetime(c.get('created_at'))} · Dernière activité : {format_app_datetime(c.get('updated_at'))}")

    tab_fiche,tab_suivi,tab_actions,tab_timeline=st.tabs(['👤 Fiche','📝 Notes & tâches','🔗 Actions liées','🕘 Timeline'])
    with tab_fiche:
        with st.form(f"crm_profile_{c['id']}"):
            r1,r2,r3=st.columns(3); fn=r1.text_input('Prénom',value=c.get('first_name') or ''); ln=r2.text_input('Nom',value=c.get('last_name') or ''); em=r3.text_input('E-mail',value=c.get('email') or '')
            r1,r2,r3=st.columns(3); ph=r1.text_input('Téléphone',value=c.get('phone') or ''); job=r2.text_input('Fonction',value=c.get('job_title') or ''); comp=r3.text_input('Entreprise',value=c.get('company') or '')
            ints=', '.join(_crm_interests(c.get('interests_json'))); interests=st.text_input("Centres d'intérêt",value=ints)
            save_profile=st.form_submit_button('💾 ENREGISTRER LA FICHE',type='primary')
        if save_profile:
            try:
                update_crm_contact(ENGINE,c['id'],first_name=fn,last_name=ln,email=em,phone=ph or None,job_title=job or None,company=comp or None,
                    interests=[x.strip() for x in interests.split(',') if x.strip()],actor=st.session_state.admin_email)
                st.success('Fiche mise à jour.'); rerun()
            except ValueError as ex: st.error(str(ex))
        r1,r2=st.columns(2)
        statuses=['NOUVEAU','A_CONTACTER','CONTACTE','A_RELANCER','OPPORTUNITE','CLIENT','SANS_SUITE','ARCHIVE']
        ns=r1.selectbox('Statut CRM',statuses,index=statuses.index(c['status']) if c['status'] in statuses else 0,key=f"crm_status_{c['id']}")
        if r1.button('Enregistrer le statut',key=f"crm_status_save_{c['id']}"):
            update_crm_status(ENGINE,c['id'],ns,st.session_state.admin_email); st.success('Statut mis à jour.'); rerun()
        consent=r2.checkbox('Consentement marketing',value=bool(c.get('marketing_consent')),key=f"crm_consent_{c['id']}")
        if r2.button('Enregistrer le consentement',key=f"crm_consent_save_{c['id']}"):
            set_crm_marketing_consent(ENGINE,c['id'],consent,st.session_state.admin_email,c.get('rgpd_notice_version') or 'I9-G'); st.success('Consentement mis à jour et tracé.'); rerun()

    with tab_suivi:
        left,right=st.columns(2)
        with left:
            st.markdown('#### Notes')
            with st.form(f"crm_note_{c['id']}",clear_on_submit=True):
                note=st.text_area('Nouvelle note',placeholder='Appel effectué, besoin identifié, prochaine étape...',height=110)
                note_ok=st.form_submit_button('AJOUTER LA NOTE')
            if note_ok:
                try: add_crm_note(ENGINE,c['id'],note,st.session_state.admin_email); st.success('Note ajoutée.'); rerun()
                except ValueError as ex: st.error(str(ex))
            notes=[]
            for e in list_crm_events(ENGINE,c['id'],100):
                if e.get('event_type')!='NOTE': continue
                try: d=json.loads(e.get('details_json') or '{}')
                except Exception: d={}
                notes.append((e,d.get('note') or ''))
            if not notes: st.caption('Aucune note.')
            for e,text in notes:
                with st.container(border=True):
                    st.write(text); st.caption(f"{format_app_datetime(e.get('created_at'))} · {e.get('actor') or ''}")
                    if st.button('🗑️ Supprimer la note',key=f"crm_note_del_{e['id']}"):
                        delete_crm_note(ENGINE,c['id'],e['id'],st.session_state.admin_email); rerun()
        with right:
            st.markdown('#### Tâches / actions commerciales')
            with st.form(f"crm_task_{c['id']}",clear_on_submit=True):
                task_title=st.text_input('Nouvelle tâche / action à mener'); due=st.date_input('Échéance',value=None,format=app_date_input_format()); task_notes=st.text_input('Commentaire')
                task_ok=st.form_submit_button('AJOUTER LA TÂCHE')
            if task_ok:
                try:
                    create_crm_task(ENGINE,c['id'],task_title,due_at=due.isoformat() if due else None,notes=task_notes or None,actor=st.session_state.admin_email); st.success('Tâche ajoutée.'); rerun()
                except ValueError as ex: st.error(str(ex))
            tasks=list_crm_tasks(ENGINE,c['id'])
            if not tasks: st.caption('Aucune tâche.')
            for t in tasks:
                with st.expander(f"{'✅' if t['status']=='FAIT' else '⬜'} {t['title']} — {t.get('due_at') or 'sans échéance'}"):
                    title=st.text_input('Objet',value=t['title'],key=f"crm_task_title_{t['id']}")
                    due_val=date.fromisoformat(t['due_at']) if t.get('due_at') else None
                    due2=st.date_input('Échéance',value=due_val,key=f"crm_task_due_{t['id']}",format=app_date_input_format())
                    notes2=st.text_input('Commentaire',value=t.get('notes') or '',key=f"crm_task_notes_{t['id']}")
                    status2=st.selectbox('Statut',['A_FAIRE','FAIT'],index=0 if t['status']=='A_FAIRE' else 1,key=f"crm_task_status_{t['id']}")
                    b1,b2=st.columns(2)
                    if b1.button('💾 Enregistrer',key=f"crm_task_save_{t['id']}"):
                        update_crm_task(ENGINE,t['id'],title=title,due_at=due2.isoformat() if due2 else None,notes=notes2 or None,status=status2,actor=st.session_state.admin_email); rerun()
                    if b2.button('🗑️ Supprimer',key=f"crm_task_delete_{t['id']}"):
                        delete_crm_task(ENGINE,t['id'],st.session_state.admin_email); rerun()

    with tab_actions:
        links=list_crm_action_links(ENGINE,c['id'])
        if links:
            for x in links:
                cols=st.columns([1.3,2.2,1.1,1.6,.7])
                cols[0].write(x['action_no']); cols[1].write(x['title']); cols[2].write(x['status']); cols[3].write(f"{x.get('start_date') or '—'} → {x.get('end_date') or '—'}")
                if cols[4].button('✖',key=f"crm_unlink_{c['id']}_{x['action_id']}",help="Retirer uniquement la liaison CRM"):
                    unlink_crm_contact_action(ENGINE,c['id'],x['action_id'],st.session_state.admin_email); rerun()
        else: st.info('Aucune action liée à ce contact pour le moment.')
        if st.button('➕ CRÉER UNE ACTION POUR CE CONTACT',key=f"crm_new_action_{c['id']}"):
            st.session_state['crm_prefill_contact_id']=c['id']; st.session_state['_next_nav']='Nouvelle action'; rerun()
        acts=q(ENGINE,"SELECT id,action_no,title,status FROM actions ORDER BY created_at DESC,id DESC LIMIT 500")
        linked_ids={x['action_id'] for x in links}; candidates=[a for a in acts if a['id'] not in linked_ids]
        if candidates:
            amap={f"{a['action_no']} — {a['title']} — {a['status']}":a for a in candidates}
            al=st.selectbox('Rattacher une action existante',list(amap),key=f"crm_link_action_{c['id']}")
            if st.button('RATTACHER CETTE ACTION',key=f"crm_link_btn_{c['id']}"):
                link_crm_contact_action(ENGINE,c['id'],amap[al]['id'],'CLIENT',st.session_state.admin_email); st.success('Action rattachée.'); rerun()

    with tab_timeline:
        evs=list_crm_events(ENGINE,c['id'],200)
        if not evs: st.info('Aucun événement.')
        else:
            timeline=[]
            for e in evs:
                try: d=json.loads(e.get('details_json') or '{}')
                except Exception: d={}
                detail=d.get('note') or d.get('activity') or d.get('title') or ', '.join(f"{k}: {v}" for k,v in d.items() if k not in {'fields'} and v not in (None,''))
                timeline.append({'Date':format_app_datetime(e.get('created_at')),'Événement':e['event_type'].replace('_',' '),'Détail':detail or '','Auteur':e.get('actor') or ''})
            st.dataframe(pd.DataFrame(timeline),use_container_width=True,hide_index=True)
    footer()

def contractualization_tab(a):
    st.subheader('Contractualisation')
    st.caption("I9 prépare le branchement vers l'application Contractualisation sans recopier son moteur juridique ni sa génération PDF.")
    linked=q(ENGINE,"SELECT p.id participant_id,b.id beneficiary_id,b.public_id,b.first_name,b.last_name FROM participants p JOIN beneficiaries b ON b.id=p.beneficiary_id WHERE p.action_id=:a AND p.active=1 AND b.active=1 ORDER BY b.last_name,b.first_name",{'a':a['id']})
    if linked:
        bmap={f"{x['last_name']} {x['first_name']} — {x['public_id']}":x for x in linked}
        with st.form(f"contract_prep_{a['id']}"):
            bl=st.selectbox('Bénéficiaire',list(bmap)); ct=st.text_input('Type de contractualisation',value='A_DEFINIR')
            aps=st.text_input('Référence APS éventuelle')
            go=st.form_submit_button('PRÉPARER LE CONTEXTE CONTRACTUALISATION',type='primary')
        if go:
            x=bmap[bl]
            prepare_contractualization_case(ENGINE,a['id'],x['beneficiary_id'],x['participant_id'],contract_type=ct or 'A_DEFINIR',aps_ref=aps or None,actor=st.session_state.admin_email)
            st.success('Contexte préparé et tracé.'); rerun()
    else:
        st.info('Aucun bénéficiaire permanent rattaché à cette action.')
    cases=list_contractualization_cases(ENGINE,action_id=a['id'])
    if cases:
        st.dataframe(pd.DataFrame([{'Bénéficiaire':f"{x['last_name']} {x['first_name']}",'Statut':x['status'].replace('_',' '),
          'Type':x.get('contract_type') or '','NO_CLAR':x.get('no_clar') or '','PDF':x.get('pdf_ref') or '',
          'JSON':x.get('json_ref') or '','Mis à jour':format_app_datetime(x['updated_at'])} for x in cases]),use_container_width=True,hide_index=True)
        cmap={f"#{x['id']} — {x['last_name']} {x['first_name']} — {x['status']}":x for x in cases}
        cl=st.selectbox('Dossier à mettre à jour',list(cmap),key=f"contract_case_{a['id']}"); cc=cmap[cl]
        statuses=['A_PREPARER','EN_COURS','GENEREE','SIGNEE','ANNULEE']
        ns=st.selectbox('Statut contractualisation',statuses,index=statuses.index(cc['status']) if cc['status'] in statuses else 0,key=f"contract_status_{cc['id']}")
        c1,c2=st.columns(2)
        pdf=c1.text_input('Référence PDF retournée',value=cc.get('pdf_ref') or '',key=f"contract_pdf_{cc['id']}")
        js=c2.text_input('Référence JSON retournée',value=cc.get('json_ref') or '',key=f"contract_json_{cc['id']}")
        if st.button('Enregistrer le retour Contractualisation',key=f"contract_save_{cc['id']}"):
            update_contractualization_case(ENGINE,cc['id'],ns,pdf_ref=pdf or None,json_ref=js or None,actor=st.session_state.admin_email)
            st.success('Dossier mis à jour.'); rerun()


def _collaboration_label(code):
    return {'A_DEFINIR':'À définir','SALARIE':'Salarié','STAGIAIRE':'Stagiaire','SOUS_TRAITANT':'Sous-traitant','MANDATAIRE_ASSOCIE':'Mandataire / Associé'}.get(code,code or 'À définir')

def _collaboration_select(label, key, value='A_DEFINIR'):
    values=list(PROFESSIONAL_COLLABORATION_TYPES)
    idx=values.index(value) if value in values else 0
    return st.selectbox(label,values,index=idx,key=key,format_func=_collaboration_label)

def professionals_screen():
    header('Clarté360 — Intervenants & partenaires', 'Dossiers professionnels et pilotage transversal')
    if st.session_state.get('_j2_open_ppid') or st.session_state.get('_j14_open_documents') or st.session_state.get('_j17_focus_service_id') is not None:
        st.session_state['_j6_next_professional_workspace']='Dossiers professionnels'
    next_workspace=st.session_state.pop('_j6_next_professional_workspace',None)
    if next_workspace:st.session_state['j6_professional_workspace']=next_workspace
    choices=('Accueil intervenants','Dossiers professionnels','Pilotage & référentiels')
    if st.session_state.get('j6_professional_workspace') not in choices:
        st.session_state['j6_professional_workspace']='Accueil intervenants'
    scope=st.radio('Espace de travail',choices,horizontal=True,key='j6_professional_workspace')
    if scope=='Accueil intervenants':
        st.markdown('### Accueil Intervenants & Partenaires')
        c1,c2=st.columns(2)
        with c1:
            st.markdown('#### Dossiers professionnels')
            st.caption('Ouvrir un intervenant ou un candidat, puis consulter ses sept rubriques sans tableau répété.')
            if st.button('Ouvrir les dossiers',key='j6_prof_enter_list',use_container_width=True):
                st.session_state.pop('j6_professional_selected',None)
                st.session_state['_j6_next_professional_workspace']='Dossiers professionnels';rerun()
        with c2:
            st.markdown('#### Pilotage & référentiels')
            st.caption('Candidatures, qualifications humaines, alertes, prestations et suivi transversal.')
            if st.button('Ouvrir le pilotage',key='j6_prof_enter_pilotage',use_container_width=True):
                st.session_state['_j6_next_professional_workspace']='Pilotage & référentiels';rerun()
        dash=professional_dashboard_metrics(ENGINE)
        cc=st.columns(4)
        for col,title,key in zip(cc,['Intervenants actifs','Candidats actifs','Qualifications','Alertes actives'],
                ['active_intervenants','active_candidates','qualified_intervenants','active_alerts']):
            col.metric(title,dash[key])
        return
    if scope=='Dossiers professionnels':
        _j6_professional_dossiers();return
    _j6_professional_pilotage()

def _j6_professional_dossiers():
    st.subheader('Dossiers professionnels')
    people_all=professional_people_operational_view(ENGINE,include_inactive=True)
    incoming=st.session_state.pop('_j2_open_ppid',None)
    if incoming and any(x['professional_person_id']==incoming for x in people_all):
        st.session_state['j6_professional_selected']=incoming
    selected=st.session_state.get('j6_professional_selected')
    if selected and not any(x['professional_person_id']==selected for x in people_all):
        st.session_state.pop('j6_professional_selected',None);selected=None
    if not selected:
        dash=professional_dashboard_metrics(ENGINE)
        d1,d2,d3,d4=st.columns(4)
        d1.metric('Intervenants actifs',dash['active_intervenants']); d2.metric('Avec qualification',dash['qualified_intervenants'])
        d3.metric('Candidats actifs',dash['active_candidates']); d4.metric('Alertes actives',dash['active_alerts'])

        c1,c2,c3=st.columns([2,1,1])
        search_person=c1.text_input('Rechercher un intervenant',placeholder='Nom, email, ville...',key='j9_people_search')
        active_filter=c2.selectbox('État',['Actifs','Tous','Inactifs'],key='j9_active_filter')
        status_filter=c3.selectbox('Dossiers',['Intervenants','Tous','Candidats'],key='j9_status_filter')
        needle=(search_person or '').strip().lower()
        people=[]
        for x in people_all:
            if active_filter=='Actifs' and not x.get('active'): continue
            if active_filter=='Inactifs' and x.get('active'): continue
            if status_filter=='Intervenants' and x.get('principal_status')!='INTERVENANT': continue
            if status_filter=='Candidats' and x.get('principal_status')!='CANDIDAT': continue
            hay=' '.join(str(x.get(k) or '') for k in ('display_name','profile_email','trainer_email','city','country')).lower()
            if needle and needle not in hay: continue
            people.append(x)
        if people:
            df=pd.DataFrame([{'Intervenant':x['display_name'],'Collaboration':x.get('collaboration_label') or _collaboration_label(x.get('collaboration_type')),'Qualifications':x['qualification_count'],'Conformité':x.get('compliance_label') or 'À vérifier','Prochaine révision':x.get('next_review') or '—','Missions':x.get('mission_count') or 0,'À faire':x.get('todo_count') or 0,'État':'Actif' if x['active'] else 'Inactif'} for x in people])
            st.dataframe(df,use_container_width=True,hide_index=True)
            st.markdown('#### Gérer un dossier de la liste')
            amap={f"{x['display_name']} — {x['principal_status']} — {'Actif' if x['active'] else 'Inactif'}":x for x in people}
            alab=st.selectbox('Sélectionner une ligne',list(amap),key='rc2p_people_action'); ap=amap[alab]
            a1,a2,a3=st.columns(3)
            if a1.button('Ouvrir / modifier',key='rc2p_open_person'):
                st.session_state['j6_professional_selected']=ap['professional_person_id'];rerun()
            if ap.get('active'):
                if a2.button('Inactiver',key='rc2p_inactivate_person'):
                    set_professional_active(ENGINE,ap['professional_person_id'],False,st.session_state.admin_email,'Inactivation depuis la liste');st.success('Dossier inactivé.');rerun()
            else:
                if a2.button('Réactiver',key='rc2p_reactivate_person'):
                    set_professional_active(ENGINE,ap['professional_person_id'],True,st.session_state.admin_email,'Réactivation depuis la liste');st.success('Dossier réactivé.');rerun()
            deps=professional_delete_dependencies(ENGINE,ap['professional_person_id'])
            with a3:
                if deps: st.caption('Suppression physique indisponible : ' + ' ; '.join(deps))
                else:
                    confirm=st.checkbox('Confirmer suppression',key='rc2p_delete_confirm')
                    if st.button('Supprimer définitivement',key='rc2p_delete_person',disabled=not confirm):
                        delete_professional_if_unused(ENGINE,ap['professional_person_id'],st.session_state.admin_email);st.success('Dossier supprimé.');rerun()
        else: st.info('Aucun dossier ne correspond aux filtres.')
        st.caption('Deux portes d’entrée administratives vers le même dossier professionnel : candidature à étudier ou intervenant déjà retenu.')
        ccreate1,ccreate2=st.columns(2)
        with ccreate1:
            with st.expander('Créer un candidat manuellement',expanded=not bool(people)):
                with st.form('j2_create_candidate'):
                    c1,c2=st.columns(2); cn=c1.text_input('Nom et prénom *'); ce=c2.text_input('Email')
                    c1,c2=st.columns(2); cp=c1.text_input('Téléphone'); cc=_collaboration_select('Type de collaboration avec Clarté360','rc222_create_candidate_collab','A_DEFINIR')
                    cadd=st.form_submit_button('Créer le dossier candidat',type='primary')
                if cadd:
                    try:
                        ppid=create_professional_candidate(ENGINE,cn,ce,cp,cc,st.session_state.admin_email)
                        st.session_state['j6_professional_selected']=ppid;st.session_state['_j14_open_documents']=ppid;st.success('Dossier candidat créé. Ajoutez maintenant ses documents.');rerun()
                    except ValueError as ex: st.error(str(ex))
        with ccreate2:
            with st.expander('Ajouter directement un intervenant',expanded=False):
                st.caption("À utiliser lorsqu’une décision humaine d’intégration est déjà prise. Aucun faux parcours de candidature n’est créé.")
                with st.form('j31_create_intervenant'):
                    c1,c2=st.columns(2); inn=c1.text_input('Nom et prénom *',key='j31_in_name'); ine=c2.text_input('Email',key='j31_in_email')
                    c1,c2=st.columns(2); inp=c1.text_input('Téléphone',key='j31_in_phone'); inc=_collaboration_select('Type de collaboration avec Clarté360','j31_in_collab','A_DEFINIR')
                    iadd=st.form_submit_button('Créer le dossier intervenant',type='primary')
                if iadd:
                    try:
                        ppid=create_professional_intervenant(ENGINE,inn,ine,inp,inc,st.session_state.admin_email)
                        st.session_state['j6_professional_selected']=ppid;st.session_state['_j14_open_documents']=ppid;st.success('Dossier intervenant créé. Ajoutez maintenant ses documents avant l’analyse globale.');rerun()
                    except ValueError as ex: st.error(str(ex))
        return
    st.caption('Dossier unique : sept rubriques, sans répétition du tableau général.')
    cback,cselect=st.columns([1,3])
    if cback.button('← Retour à la liste',key='j6_prof_back_list'):
        st.session_state.pop('j6_professional_selected',None)
        st.session_state.pop('_j6_last_selected',None)
        rerun()
    people_for_open=people_all
    pmap={f"{x.get('display_name') or x.get('full_name') or x.get('title') or x['professional_person_id']} — {x['principal_status']} — {x['professional_person_id']}":x for x in people_for_open}
    keys=list(pmap)
    current=next((k for k,v in pmap.items() if v['professional_person_id']==selected),keys[0])
    # Set index from selected dossier without relying on hidden prior list selection.
    if st.session_state.get('j2_person_manage') not in keys or st.session_state.get('_j6_last_selected')!=selected:
        st.session_state['j2_person_manage']=current
        st.session_state['_j6_last_selected']=selected
    with cselect:
        plab=st.selectbox('Changer de dossier professionnel',keys,key='j2_person_manage')
    ppid=pmap[plab]['professional_person_id']
    if ppid!=selected:st.session_state['j6_professional_selected']=ppid;rerun()
    prof=get_professional_360(ENGINE,ppid)
    st.markdown(f"### {prof.get('display_name') or prof.get('full_name') or ppid}")
    st.caption(f"{prof['principal_status']} · {prof['candidate_work_status'].replace('_',' ')} · {ppid}")
    # RC2-2-2 P3 : navigation pilotable, indispensable pour les deep-links métier.
    dossier_screens=['Synthèse','Parcours professionnel','Conformité & collaboration','Analyse IA','Qualifications','Missions / Affectations','CV Clarté360']
    screen_key=f'rc222_dossier_screen_{ppid}'
    if st.session_state.pop('_j14_open_documents',None)==ppid:
        st.session_state[screen_key]='Analyse IA'
    if st.session_state.get('_j17_focus_service_id') is not None:
        st.session_state[screen_key]='Qualifications'
    screen_default=st.session_state.get(screen_key,'Synthèse')
    if screen_default not in dossier_screens: screen_default='Synthèse'
    st.markdown('#### Rubriques du dossier professionnel')
    screen=st.selectbox('Rubrique à consulter',dossier_screens,
        index=dossier_screens.index(screen_default),key=screen_key)
    ps=screen=='Synthèse'; pex=screen=='Parcours professionnel'; preg=screen=='Conformité & collaboration'; pdocs=screen=='Analyse IA'; pqual=screen=='Qualifications'; pmissions=screen=='Missions / Affectations'; pcv=screen=='CV Clarté360'
    pwf=ps and prof['principal_status']=='CANDIDAT'; ped=pex; pcert=pex
    with st.expander('ⓘ Comprendre cet écran'):
        help_by_screen={
          'Synthèse':"Cockpit DRH : identité, état du dossier, conformité, qualifications, alertes et prochaine action. Les décisions restent humaines.",
          'Parcours professionnel':"Expériences, spécialités, diplômes, langues, certifications et habilitations. Saisie manuelle ou propositions IA explicitement acceptées.",
          'Conformité & collaboration':"Relation avec Clarté360, fournisseur lié et conformité. Ces éléments ne prouvent pas à eux seuls une compétence sur une prestation.",
          'Analyse IA':"Déposez les documents, autorisez l’analyse, vérifiez les faits proposés puis instruisez les prestations. L’IA prépare ; elle ne décide pas.",
          'Qualifications':"Revue humaine par prestation. Les propositions IA, preuves et points ouverts sont des aides ; le niveau effectif reste humain.",
          'Missions / Affectations':"Vue opérationnelle des Actions auxquelles la personne est affectée et de l’état de qualification associé.",
          'CV Clarté360':"CV généré depuis le dossier structuré et les qualifications validées humainement."
        }
        st.caption(help_by_screen[screen])
    if ps:
        cockpit=professional_cockpit_summary(ENGINE,ppid)
        st.markdown('#### Vue rapide du dossier')
        c1,c2,c3,c4=st.columns(4)
        c1.metric('Statut',cockpit['status_label']); c2.metric('Collaboration',cockpit['collaboration_label'])
        c3.metric('Complétude dossier',f"{cockpit['completion_percent']} %"); c4.metric('Conformité',cockpit['compliance_label'])
        c1,c2,c3,c4=st.columns(4)
        c1.metric('Qualifications validées',cockpit['validated_qualifications']); c2.metric('Points à traiter',cockpit['open_points'])
        c3.metric('Alertes / révisions',cockpit['active_alerts']); c4.metric('Missions',cockpit['mission_count'])
        if cockpit['assignable_services']:
            st.success('Affectable aujourd’hui sur : ' + ', '.join(cockpit['assignable_services'][:6]))
        else:
            st.info("Aucune prestation n’est actuellement confirmée comme affectable à partir des qualifications humaines enregistrées.")
        if cockpit['next_actions']:
            st.markdown('**À faire maintenant**')
            for item in cockpit['next_actions'][:5]: st.write('• '+item)
        st.markdown('#### Identité')
        st.caption('Le nom et le prénom sont des données d’identité distinctes du titre professionnel.')
        if not (prof.get('first_name') and prof.get('last_name')):
            st.info(f"Identité historique à structurer : {prof.get('display_name') or prof.get('full_name') or 'non renseignée'}")
        with st.form(f'rc22_identity_{ppid}'):
            c1,c2=st.columns(2)
            first_name=c1.text_input('Prénom *',value=prof.get('first_name') or '')
            last_name=c2.text_input('Nom *',value=prof.get('last_name') or '')
            identity_save=st.form_submit_button('Enregistrer le nom et le prénom')
        if identity_save:
            try:
                update_professional_identity(ENGINE,ppid,first_name,last_name,st.session_state.admin_email)
                st.success('Identité mise à jour. Le titre professionnel reste indépendant.');rerun()
            except ValueError as ex: st.error(str(ex))
        st.markdown('#### Profil professionnel')
        with st.form(f'j2_profile_{ppid}'):
            c1,c2=st.columns(2); title=c1.text_input('Titre professionnel',value=prof.get('title') or '');coll=_collaboration_select('Type de collaboration avec Clarté360',f'rc222_collab_{ppid}',prof.get('collaboration_type') or 'A_DEFINIR')
            summary=st.text_area('Résumé professionnel',value=prof.get('summary') or '',height=120)
            c1,c2=st.columns(2); email=c1.text_input('Email professionnel',value=prof.get('profile_email') or prof.get('trainer_email') or '');phone=c2.text_input('Téléphone',value=prof.get('profile_phone') or prof.get('trainer_phone') or '')
            c1,c2,c3=st.columns(3); city=c1.text_input('Ville',value=prof.get('city') or '');country=c2.text_input('Pays',value=prof.get('country') or '');website=c3.text_input('Site web',value=prof.get('website') or '')
            linkedin=st.text_input('LinkedIn',value=prof.get('linkedin_url') or '');notes=st.text_area('Notes internes',value=prof.get('notes_internal') or '',height=90)
            save=st.form_submit_button('Enregistrer le profil',type='primary')
        if save:
            try:update_professional_profile(ENGINE,ppid,{'title':title,'summary':summary,'collaboration_type':coll,'email':email,'phone':phone,'city':city,'country':country,'website':website,'linkedin_url':linkedin,'notes_internal':notes},st.session_state.admin_email);st.success('Profil enregistré.');rerun()
            except ValueError as ex:st.error(str(ex))
        with st.expander('Réinitialiser les analyses et les données professionnelles de ce dossier'):
            preview=professional_reset_preview(ENGINE,ppid)
            st.warning('Cette opération remet le dossier professionnel à zéro pour une nouvelle instruction. Elle conserve l’identité, le statut CANDIDAT/INTERVENANT, le caractère actif/inactif, les documents déposés, les liaisons fournisseur et les affectations aux actions/plannings.')
            st.caption(f"Documents conservés : {preview['documents_preserved']} · Analyses IA : {preview['counts'].get('professional_global_ai_runs',0)} · Qualifications : {preview['counts'].get('person_service_qualifications',0)} · Expériences : {preview['counts'].get('professional_experiences',0)} · Diplômes : {preview['counts'].get('professional_education',0)}")
            reset_phrase=f"REINITIALISER {ppid}"
            reset_confirm=st.text_input(f"Pour confirmer, saisissez exactement : {reset_phrase}",key=f'rc22_reset_confirm_{ppid}')
            reset_pw=st.text_input('Votre mot de passe administrateur',type='password',key=f'rc22_reset_pw_{ppid}')
            if st.button('Purger les analyses et remettre le dossier professionnel à zéro',key=f'rc22_reset_btn_{ppid}',disabled=reset_confirm.strip()!=reset_phrase):
                try:
                    info=reset_professional_dossier(ENGINE,ppid,st.session_state.admin_email,reset_pw)
                    st.success('Dossier professionnel réinitialisé. Les documents, l’identité, le statut et les affectations ont été conservés. Une sauvegarde technique a été créée avant purge.');rerun()
                except ValueError as ex: st.error(str(ex))
    if pwf:
        comp=candidate_completeness(ENGINE,ppid)
        st.markdown('#### Suivi de la candidature')
        st.progress(comp['percent']/100.0,text=f"Complétude du dossier : {comp['percent']} % ({comp['done']}/{comp['total']})")
        cols=st.columns(2)
        for i,(label,ok) in enumerate(comp['checks'].items()): cols[i%2].write(('✓ ' if ok else '○ ')+label)
        if prof['principal_status']=='CANDIDAT':
            st.caption('Le candidat reste non affectable tant qu’une validation humaine explicite ne transforme pas ce même dossier en intervenant.')
            normal_states=['NOUVEAU','INCOMPLET','EN_ETUDE','ENTRETIEN_A_PREVOIR','PRET_DECISION']
            current=prof['candidate_work_status'] if prof['candidate_work_status'] in normal_states else 'NOUVEAU'
            with st.form(f'j3_status_{ppid}'):
                ns=st.selectbox('État de travail',normal_states,index=normal_states.index(current)); nr=st.text_input('Commentaire / motif'); nsave=st.form_submit_button('Mettre à jour l’état')
            if nsave:
                try:set_candidate_work_status(ENGINE,ppid,ns,st.session_state.admin_email,nr or None);st.success('État de candidature mis à jour.');rerun()
                except ValueError as ex:st.error(str(ex))
            with st.expander('Demander un complément'):
                with st.form(f'j3_complement_{ppid}'):
                    req=st.text_area('Complément demandé *'); reqgo=st.form_submit_button('Enregistrer la demande')
                if reqgo:
                    try:request_candidate_complement(ENGINE,ppid,req,st.session_state.admin_email);st.success('Demande de complément enregistrée.');rerun()
                    except ValueError as ex:st.error(str(ex))
            requests=candidate_open_requests(ENGINE,ppid)
            if requests:
                st.write('**Compléments en attente**')
                for r in requests:
                    c1,c2=st.columns([5,1]); c1.write(r['request_text'])
                    if c2.button('Résolu',key=f"j3_resolve_{r['id']}"):
                        resolve_candidate_request(ENGINE,r['id'],st.session_state.admin_email);rerun()
            st.markdown('#### Décision humaine')
            reason=st.text_area('Motif / commentaire de décision',key=f'j3_decision_reason_{ppid}')
            c1,c2,c3=st.columns(3)
            if c1.button('Valider comme intervenant',type='primary',key=f'j3_validate_{ppid}'):
                try:decide_candidate(ENGINE,ppid,'VALIDER',st.session_state.admin_email,reason or None);st.success('Candidature validée : le même dossier est désormais INTERVENANT.');rerun()
                except ValueError as ex:st.error(str(ex))
            if c2.button('Refuser',key=f'j3_refuse_{ppid}'):
                try:decide_candidate(ENGINE,ppid,'REFUSER',st.session_state.admin_email,reason or None);rerun()
                except ValueError as ex:st.error(str(ex))
            if c3.button('Abandonner',key=f'j3_abandon_{ppid}'):
                try:decide_candidate(ENGINE,ppid,'ABANDONNER',st.session_state.admin_email,reason or None);rerun()
                except ValueError as ex:st.error(str(ex))
        else:
            if prof.get('origin')=='ADMIN_DIRECT_INTERVENANT':
                st.info("Intervenant créé directement par l’administration : aucun parcours de candidature artificiel. L’adéquation compétences / prestations sera gérée dans l’étape de qualification.")
            else:
                st.success('Dossier validé comme intervenant. La candidature est clôturée et l’historique reste conservé.')
        hist=candidate_workflow_history(ENGINE,ppid)
        if hist:
            st.write('**Historique du workflow**')
            st.dataframe(pd.DataFrame([{'Date':format_app_datetime(x['created_at']),'Événement':x['event_type'],'De':x.get('old_work_status') or '','Vers':x.get('new_work_status') or '','Commentaire':x.get('comment') or '','Auteur':x['actor']} for x in hist]),use_container_width=True,hide_index=True)
    if preg:
        reg=prof.get('regulatory_status') or {}
        st.markdown('#### Entité fournisseur liée')
        st.caption("Gestion Clients reste la source de vérité de l’entité économique. Ici, on conserve uniquement la liaison avec la personne professionnelle et son historique.")
        slinks=list_professional_supplier_links(ENGINE,ppid)
        if slinks:
            st.dataframe(pd.DataFrame([{'Fournisseur':x['supplier_id'],'Relation':x['relationship_type'],'Début':x.get('valid_from') or '','Fin':x.get('valid_to') or '','Statut':x['status'],'Synchronisation':x['sync_status']} for x in slinks]),use_container_width=True,hide_index=True)
        with st.expander('Lier / changer d’entité fournisseur'):
            with st.form(f'j10_supplier_{ppid}'):
                sid=st.text_input('Identifiant fournisseur Gestion Clients *',help="Identifiant stable fourni par Gestion Clients. La raison sociale et les données économiques ne sont pas recopiées ici.")
                rt=st.selectbox('Type de relation',['PROFESSIONAL','INDEPENDENT','SALARIE','SOUS_TRAITANT','PARTENAIRE','AUTRE'])
                c1,c2=st.columns(2); vf=c1.text_input('Début (AAAA-MM-JJ)'); vt=c2.text_input('Fin prévue (AAAA-MM-JJ)')
                slsave=st.form_submit_button('Enregistrer la liaison',type='primary')
            if slsave:
                try:
                    link_professional_supplier(ENGINE,ppid,sid,rt,vf or None,vt or None,st.session_state.admin_email)
                    st.success('Liaison enregistrée. Elle pourra être synchronisée avec Gestion Clients sans recopier la fiche fournisseur.');rerun()
                except ValueError as ex: st.error(str(ex))
        st.caption("Ces informations décrivent l’activité professionnelle propre de l’intervenant. Lorsqu’elles relèvent d’une entité fournisseur distincte, la source de vérité restera Gestion Clients et sera projetée ici lors du raccordement.")
        with st.form(f'j21_reg_{ppid}'):
            own=st.radio('Origine des informations',['Activité propre de l’intervenant','Entité fournisseur liée'],index=1 if reg.get('ownership_mode')=='SUPPLIER_PROJECTION' else 0,horizontal=True)
            st.markdown('#### Déclaration d’activité (NDA)')
            c1,c2=st.columns(2); nda=c1.selectbox('Dispose d’un NDA ?',['NON_RENSEIGNE','OUI','NON'],index=['NON_RENSEIGNE','OUI','NON'].index(reg.get('nda_status') or 'NON_RENSEIGNE')); ndanum=c2.text_input('Numéro de déclaration d’activité',value=reg.get('nda_number') or '')
            c1,c2=st.columns(2); ndareg=c1.text_input('DREETS / région',value=reg.get('nda_region') or ''); ndadate=c2.date_input('Date de déclaration',value=(datetime.fromisoformat(str(reg.get('nda_declared_at'))[:10]).date() if reg.get('nda_declared_at') else None),format=app_date_input_format())
            ndanotes=st.text_area('Notes NDA',value=reg.get('nda_notes') or '',height=70)
            st.markdown('#### Certification Qualiopi')
            c1,c2=st.columns(2); qstat=c1.selectbox('Certification Qualiopi ?',['NON_RENSEIGNE','OUI','NON'],index=['NON_RENSEIGNE','OUI','NON'].index(reg.get('qualiopi_status') or 'NON_RENSEIGNE')); qcert=c2.text_input('Organisme certificateur',value=reg.get('qualiopi_certifier') or '')
            qref=st.text_input('Référence / n° du certificat',value=reg.get('qualiopi_certificate_ref') or '')
            c1,c2=st.columns(2); qfrom=c1.date_input('Valide depuis',value=(datetime.fromisoformat(str(reg.get('qualiopi_valid_from'))[:10]).date() if reg.get('qualiopi_valid_from') else None),format=app_date_input_format()); quntil=c2.date_input('Valide jusqu’au',value=(datetime.fromisoformat(str(reg.get('qualiopi_valid_until'))[:10]).date() if reg.get('qualiopi_valid_until') else None),format=app_date_input_format())
            st.write('**Catégories d’actions couvertes par le certificat**')
            q1,q2=st.columns(2); scope_training=q1.checkbox('Actions de formation',value=bool(reg.get('qualiopi_scope_training'))); scope_bilan=q2.checkbox('Bilans de compétences',value=bool(reg.get('qualiopi_scope_bilan')))
            q3,q4=st.columns(2); scope_vae=q3.checkbox('Actions permettant de faire valider les acquis de l’expérience (VAE)',value=bool(reg.get('qualiopi_scope_vae'))); scope_app=q4.checkbox('Actions de formation par apprentissage',value=bool(reg.get('qualiopi_scope_apprentissage')))
            qnotes=st.text_area('Notes Qualiopi',value=reg.get('qualiopi_notes') or '',height=70)
            regsave=st.form_submit_button('Enregistrer NDA / Qualiopi',type='primary')
        if regsave:
            try:
                update_professional_regulatory_status(ENGINE,ppid,{'ownership_mode':'SUPPLIER_PROJECTION' if own=='Entité fournisseur liée' else 'PERSONAL_ACTIVITY','nda_status':nda,'nda_number':ndanum,'nda_region':ndareg,'nda_declared_at':ndadate.isoformat() if ndadate else None,'nda_notes':ndanotes,'qualiopi_status':qstat,'qualiopi_certifier':qcert,'qualiopi_certificate_ref':qref,'qualiopi_valid_from':qfrom.isoformat() if qfrom else None,'qualiopi_valid_until':quntil.isoformat() if quntil else None,'qualiopi_scope_training':scope_training,'qualiopi_scope_bilan':scope_bilan,'qualiopi_scope_vae':scope_vae,'qualiopi_scope_apprentissage':scope_app,'qualiopi_notes':qnotes},st.session_state.admin_email)
                st.success('Informations NDA / Qualiopi enregistrées.');rerun()
            except ValueError as ex:st.error(str(ex))
        st.info('Les justificatifs se déposent dans Analyse IA avec les catégories « NDA justificatif » ou « Certificat Qualiopi ».')
    if pex:
        if prof['experiences']:
            st.dataframe(pd.DataFrame(prof['experiences'])[['role_title','organization','start_date','end_date','current_role']],use_container_width=True,hide_index=True)
            _rc2p_manage_structured_rows(ppid,'professional_experiences',prof['experiences'],'role_title',[('role_title','Fonction','text'),('organization','Organisation','text'),('start_date','Début','text'),('end_date','Fin','text'),('current_role','Poste actuel','bool'),('description','Description','long')],f'rc2p_exp_{ppid}')
        with st.expander('Ajouter une expérience'):
            with st.form(f'j2_exp_{ppid}'):
                c1,c2=st.columns(2); role=c1.text_input('Fonction *');org=c2.text_input('Organisation');desc=st.text_area('Description');expadd=st.form_submit_button('Ajouter')
            if expadd:
                try:add_professional_experience(ENGINE,ppid,role,org,description=desc,actor=st.session_state.admin_email);rerun()
                except ValueError as ex:st.error(str(ex))
        if prof['specialties']:
            st.dataframe(pd.DataFrame([{'Spécialité':x['specialty'],'Notes':x.get('notes') or ''} for x in prof['specialties']]),use_container_width=True,hide_index=True)
            _rc2p_manage_structured_rows(ppid,'professional_specialties',prof['specialties'],'specialty',[('specialty','Spécialité','text'),('notes','Notes','long')],f'rc2p_spec_{ppid}')
        with st.form(f'j2_spec_{ppid}'):
            sp=st.text_input('Ajouter une spécialité');spa=st.form_submit_button('Ajouter la spécialité')
        if spa and sp.strip():add_professional_specialty(ENGINE,ppid,sp,actor=st.session_state.admin_email);rerun()
    if ped:
        if prof['education']:
            st.dataframe(pd.DataFrame(prof['education'])[['diploma_title','institution','field','obtained_date']],use_container_width=True,hide_index=True)
            _rc2p_manage_structured_rows(ppid,'professional_education',prof['education'],'diploma_title',[('diploma_title','Diplôme / formation','text'),('institution','Établissement','text'),('field','Domaine','text'),('obtained_date','Date obtenue','text'),('description','Description','long')],f'rc2p_edu_{ppid}')
        with st.expander('Ajouter un diplôme / une formation'):
            with st.form(f'j2_edu_{ppid}'):
                c1,c2=st.columns(2); dip=c1.text_input('Diplôme / formation *');inst=c2.text_input('Établissement');field=st.text_input('Domaine');eduadd=st.form_submit_button('Ajouter')
            if eduadd:
                try:add_professional_education(ENGINE,ppid,dip,inst,field,actor=st.session_state.admin_email);rerun()
                except ValueError as ex:st.error(str(ex))
        if prof['languages']:
            st.dataframe(pd.DataFrame(prof['languages'])[['language','level','evidence']],use_container_width=True,hide_index=True)
            _rc2p_manage_structured_rows(ppid,'professional_languages',prof['languages'],'language',[('language','Langue','text'),('level','Niveau','text'),('evidence','Preuve / précision','text')],f'rc2p_lang_{ppid}')
        with st.form(f'j2_lang_{ppid}'):
            c1,c2=st.columns(2);lang=c1.text_input('Langue');lvl=c2.text_input('Niveau');ev=st.text_input('Preuve / précision');la=st.form_submit_button('Ajouter / mettre à jour la langue')
        if la and lang.strip():add_professional_language(ENGINE,ppid,lang,lvl,ev,st.session_state.admin_email);rerun()
    if pcert:
        if prof['certifications']:
            st.dataframe(pd.DataFrame(prof['certifications'])[['certification_type','name','issuer','reference','valid_until']],use_container_width=True,hide_index=True)
            _rc2p_manage_structured_rows(ppid,'professional_certifications',prof['certifications'],'name',[('certification_type','Type','text'),('name','Nom','text'),('issuer','Organisme émetteur','text'),('reference','Référence','text'),('obtained_date','Date obtenue','text'),('valid_until','Valide jusqu’au','text'),('description','Description','long')],f'rc2p_cert_{ppid}')
        with st.form(f'j2_cert_{ppid}'):
            c1,c2=st.columns(2);ctype=c1.selectbox('Type',['CERTIFICATION','HABILITATION','ATTESTATION']);cname=c2.text_input('Nom *');issuer=st.text_input('Organisme émetteur');ref=st.text_input('Référence');ca=st.form_submit_button('Ajouter')
        if ca:
            try:add_professional_certification(ENGINE,ppid,cname,ctype,issuer,ref,actor=st.session_state.admin_email);rerun()
            except ValueError as ex:st.error(str(ex))
    if pqual:
        st.markdown('#### Adéquation compétences / prestations Clarté360')
        st.caption("Évaluation humaine directe, utilisable pour un candidat comme pour un intervenant. L’IA viendra ensuite proposer des éléments sans jamais remplacer une validation humaine verrouillée.")
        matrix=list_person_service_qualifications(ENGINE,ppid,active_services_only=True)
        if matrix:
            matrix_rows=[]
            for x in matrix:
                ai_value=x.get('ai_value')
                ai_evidence=int(x.get('ai_evidence_count') or 0)
                ai_positive=int(x.get('ai_positive_criteria_count') or 0)
                if ai_value is None:
                    ai_reading='Non analysé'
                elif ai_evidence==0 and ai_positive==0:
                    ai_reading='Aucun élément repéré'
                elif int(ai_value or 0)==0:
                    ai_reading='Éléments repérés — niveau global bloqué'
                elif int(ai_value)<3:
                    ai_reading='Rapprochement partiel'
                else:
                    ai_reading='Rapprochement fort'
                human_value=x.get('human_value')
                matrix_rows.append({
                    'Prestation':x['service_name'],'Univers':x.get('family') or '',
                    'Décision humaine':(f"{human_value} — {QUALIFICATION_LEVEL_LABELS.get(human_value,'')}" if human_value is not None else 'Non évalué'),
                    'Preuves validées':x.get('evidence_count') or 0,
                    'Lecture IA':ai_reading,
                    'Proposition IA':(f"{ai_value} — {QUALIFICATION_LEVEL_LABELS.get(ai_value,'')}" if ai_value is not None else '—'),
                    'Confiance analyse':(f"{float(x.get('ai_confidence') or 0):.0%}" if ai_value is not None else '—'),
                    'Critères IA':(f"{x.get('ai_criteria_count') or 0}/{x.get('criteria_count') or 0}" if ai_value is not None else '—'),
                    'Preuves IA':ai_evidence,
                    'Révision':x.get('review_due_at') or ''
                })
            st.dataframe(pd.DataFrame(matrix_rows),use_container_width=True,hide_index=True)
            st.caption("La décision humaine est prioritaire. Lorsqu'elle existe, l'analyse IA reste une aide et un historique de préparation ; elle ne remplace jamais le niveau validé.")
            qmap={f"{x['service_name']} — {x.get('family') or 'Sans univers'}":x for x in matrix}
            focus_sid=st.session_state.pop('_j17_focus_service_id',None)
            qlabels=list(qmap); qidx=0
            if focus_sid is not None:
                qidx=next((i for i,k in enumerate(qlabels) if int(qmap[k]['service_id'])==int(focus_sid)),0)
                st.info('Qualification ouverte depuis une action : vérifiez les preuves et critères puis prenez la décision humaine.')
            qlab=st.selectbox('Prestation à évaluer',qlabels,index=qidx,key=f'j4_service_{ppid}'); qrow=qmap[qlab]
            qdetail=get_person_service_qualification(ENGINE,ppid,qrow['service_id']); qcurrent=qdetail.get('qualification') or {}
            summary=qualification_adequacy_summary(ENGINE,ppid,qrow['service_id'])
            c1,c2,c3,c4=st.columns(4)
            c1.metric('Critères évalués',f"{summary['criteria_assessed']}/{summary['criteria_total']}")
            c2.metric('Obligatoires au niveau attendu',f"{summary['required_ok']}/{summary['required_total']}")
            c3.metric('Preuves',summary['evidence_count'])
            c4.metric('Niveau final',qcurrent.get('human_value') if qcurrent.get('human_value') is not None else '—')

            st.markdown('##### Analyse IA assistée')
            st.caption("Cette zone exploite directement la dernière analyse globale lancée depuis l’onglet Analyse IA. Il n’est plus nécessaire de refaire tourner l’IA prestation par prestation : critères, preuves et niveau proposé sont matérialisés ici à partir du même passage IA. Pour réanalyser après ajout de nouvelles pièces, relancez simplement l’analyse globale dans Analyse IA.")
            if qcurrent.get('ai_value') is not None:
                ai_evidence=[]; ai_missing=[]
                try: ai_evidence=json.loads(qcurrent.get('ai_evidence_json') or '[]')
                except Exception: pass
                try: ai_missing=json.loads(qcurrent.get('ai_missing_json') or '[]')
                except Exception: pass
                a1,a2,a3=st.columns(3);a1.metric('Proposition IA',f"{qcurrent.get('ai_value')} — {QUALIFICATION_LEVEL_LABELS.get(qcurrent.get('ai_value'),'')}");a2.metric('Confiance',f"{float(qcurrent.get('ai_confidence') or 0):.0%}");a3.metric('Analyse',format_app_datetime(qcurrent.get('ai_updated_at')))
                st.write('**Justification IA :** '+(qcurrent.get('ai_rationale') or 'Non renseignée'))
                if ai_evidence:
                    st.write('**Preuves repérées par l’IA — à décider humainement**')
                    st.caption("Ces éléments sont des propositions IA. Ils ne sont comptés comme preuves validées qu’après acceptation humaine.")
                    ep=list_ai_evidence_proposals(ENGINE,ppid,qrow['service_id'],latest_only=True)
                    if ep:
                        for pev in ep:
                            label=(pev.get('criterion_label') or 'Preuve générale')+' — '+(pev.get('document_name') or pev.get('source_label') or 'source IA')
                            with st.expander(label):
                                st.write(pev.get('evidence_text') or '')
                                st.caption(f"Identité : {pev.get('identity_status')} · Niveau soutenu : {pev.get('supports_level')} · Statut : {pev.get('status')}")
                                if pev.get('identity_status')=='INCOHERENT': st.error("Identité incohérente : cette pièce ne peut pas être validée comme preuve tant que l’anomalie n’est pas résolue.")
                                if pev.get('status')=='PROPOSEE':
                                    ec1,ec2=st.columns(2)
                                    if ec1.button('Accepter comme preuve',key=f'j16_ev_accept_{pev["id"]}',disabled=pev.get('identity_status')=='INCOHERENT'):
                                        try: decide_ai_evidence_proposal(ENGINE,pev['id'],True,st.session_state.admin_email);st.success('Preuve acceptée humainement.');rerun()
                                        except ValueError as ex: st.error(str(ex))
                                    if ec2.button('Rejeter cette preuve',key=f'j16_ev_reject_{pev["id"]}'):
                                        decide_ai_evidence_proposal(ENGINE,pev['id'],False,st.session_state.admin_email);st.info('Preuve rejetée.');rerun()
                    else:
                        st.dataframe(pd.DataFrame([{'Source':x.get('source',''),'Élément factuel':x.get('fact',''),'Niveau soutenu':x.get('supports_level','')} for x in ai_evidence]),use_container_width=True,hide_index=True)
                if ai_missing:
                    st.write('**Points manquants / à vérifier :**')
                    for x in ai_missing: st.write('• '+str(x))
                if qdetail.get('review_points'):
                    st.markdown('##### Points à vérifier — décision humaine')
                    for rp in qdetail['review_points']:
                        status=rp.get('status') or 'OUVERT'
                        with st.expander(f"{rp.get('label') or 'Point à vérifier'} — {status.replace('_',' ').title()}"):
                            if rp.get('human_comment'): st.caption('Commentaire : '+str(rp['human_comment']))
                            with st.form(f'rc222_review_point_{rp["id"]}'):
                                opts=['OUVERT','LEVE','CONFIRME','NON_PERTINENT']
                                choice=st.selectbox('Statut',opts,index=opts.index(status) if status in opts else 0,format_func=lambda x:{'OUVERT':'À vérifier','LEVE':'Levé','CONFIRME':'Confirmé','NON_PERTINENT':'Non pertinent'}[x])
                                rcomment=st.text_area('Commentaire humain',value=rp.get('human_comment') or '',height=70)
                                rsave=st.form_submit_button('Enregistrer la décision')
                            if rsave:
                                (reopen_qualification_review_point(ENGINE,rp['id'],st.session_state.admin_email,rcomment or None) if choice=='OUVERT' else decide_qualification_review_point(ENGINE,rp['id'],choice,st.session_state.admin_email,rcomment or None));st.success('Point mis à jour.');rerun()
                if qcurrent.get('human_value') is not None and qcurrent.get('human_locked'):
                    st.info("Une validation humaine existe : cette proposition IA est conservée pour comparaison et ne peut pas la remplacer automatiquement.")
                pending_criteria=[x for x in list_ai_criterion_proposals(ENGINE,ppid,qrow['service_id'],latest_only=True) if x.get('status')=='PROPOSEE']
                pending_evidence=[x for x in list_ai_evidence_proposals(ENGINE,ppid,qrow['service_id'],latest_only=True) if x.get('status')=='PROPOSEE' and x.get('identity_status')!='INCOHERENT']
                if pending_criteria or pending_evidence:
                    st.caption(f"Pré-instruction IA disponible : {len(pending_criteria)} critère(s) proposé(s) et {len(pending_evidence)} preuve(s) à examiner. Utilisez le préremplissage ci-dessous pour préparer la grille ; cela ne constitue pas une validation humaine.")

            st.markdown('##### Évaluation humaine par critère')
            if qdetail['criteria']:
                cp={int(x['criterion_id']):x for x in list_ai_criterion_proposals(ENGINE,ppid,qrow['service_id'],latest_only=True)}
                st.caption("Une seule grille de décision : la proposition IA prépare la lecture ; le niveau retenu reste une décision humaine de 0 à 4.")
                prefill_key=f'rc222_prefill_{ppid}_{qrow["service_id"]}'
                if st.button('Préremplir l’évaluation à partir de l’analyse IA',key=f'rc222_prefill_btn_{ppid}_{qrow["service_id"]}'):
                    st.session_state[prefill_key]=True
                retained={}; comments={}
                for cr in qdetail['criteria']:
                    pr=cp.get(int(cr['id'])) or {}
                    proposed=int(pr.get('proposed_level') or 0)
                    current=cr.get('assessment_value')
                    initial=int(current) if current is not None else (proposed if st.session_state.get(prefill_key) else 0)
                    st.markdown(f"**{cr['label']}**" + (' *' if cr.get('required') else ''))
                    c1,c2,c3=st.columns([2,2,4])
                    c1.write(f"IA : {proposed}/4" if pr else 'IA : —')
                    retained[cr['id']]=c2.selectbox('Niveau retenu humain',[0,1,2,3,4],index=initial,key=f'rc222_level_{ppid}_{cr["id"]}',label_visibility='collapsed')
                    comments[cr['id']]=c3.text_input('Commentaire',value=cr.get('assessment_comment') or '',key=f'rc222_comment_{ppid}_{cr["id"]}',label_visibility='collapsed',placeholder='Commentaire / point à vérifier')
                    evlinks=[e for e in qdetail.get('evidence_links',[]) if e.get('criterion_id')==cr['id']]
                    if evlinks: st.caption('Preuves associées : ' + ' · '.join(str(e.get('document_name') or e.get('source_label') or e.get('relevance_comment') or 'preuve') for e in evlinks))
                    if pr.get('rationale'): st.caption('Justification IA : '+str(pr['rationale']))
                st.caption('Ces niveaux sont enregistrés avec la validation finale ci-dessous : une seule action humaine valide la grille et la prestation.')
            else:
                st.warning("Aucun critère n’est défini pour cette prestation. Créez la grille dans Intervenants / Partenaires > Prestations avant de valider une adéquation détaillée.")
            st.markdown('##### Preuves de qualification')
            if qdetail['evidence']:
                st.dataframe(pd.DataFrame([{'Date':format_app_date(e['created_at']),'Type':e['evidence_type'],'Critère':next((c['label'] for c in qdetail['criteria'] if c['id']==e.get('criterion_id')),''),'Document':e.get('document_name') or '','Preuve':e.get('evidence_text') or e.get('source_label') or ''} for e in qdetail['evidence']]),use_container_width=True,hide_index=True)
                emap={f"#{e['id']} — {e.get('document_name') or e.get('evidence_text') or e.get('source_label') or e['evidence_type']}":e for e in qdetail['evidence']}
                elab=st.selectbox('Preuve à gérer',list(emap),key=f'rc21_evidence_manage_{ppid}_{qrow["service_id"]}'); ee=emap[elab]
                with st.expander('Modifier / retirer la preuve'):
                    criteria_options=[('Preuve générale',None)]+[(cr['label'],cr['id']) for cr in qdetail['criteria']]
                    docs=prof.get('documents') or []; doc_options={'Aucun document':None}; doc_options.update({f"{d['display_name']} — {d['category']}":d['id'] for d in docs})
                    criterion_labels=[x[0] for x in criteria_options]; current_criterion=next((x[0] for x in criteria_options if x[1]==ee.get('criterion_id')),'Preuve générale')
                    doc_labels=list(doc_options); current_doc=next((lab for lab,val in doc_options.items() if val==ee.get('professional_document_id')),'Aucun document')
                    with st.form(f'rc21_evidence_edit_{ee["id"]}'):
                        etype=st.selectbox('Type',QUALIFICATION_EVIDENCE_TYPES,index=QUALIFICATION_EVIDENCE_TYPES.index(ee.get('evidence_type')) if ee.get('evidence_type') in QUALIFICATION_EVIDENCE_TYPES else 0)
                        ecrit=st.selectbox('Critère',criterion_labels,index=criterion_labels.index(current_criterion))
                        edoclab2=st.selectbox('Document',doc_labels,index=doc_labels.index(current_doc))
                        etxt2=st.text_area('Description / preuve',value=ee.get('evidence_text') or '',height=80)
                        esource2=st.text_input('Source / libellé',value=ee.get('source_label') or '')
                        esave=st.form_submit_button('Enregistrer les modifications')
                    if esave:
                        try:
                            update_qualification_evidence(ENGINE,ee['id'],st.session_state.admin_email,etype,etxt2 or None,dict(criteria_options)[ecrit],doc_options[edoclab2],esource2 or None)
                            st.success('Preuve modifiée.');rerun()
                        except ValueError as ex: st.error(str(ex))
                    confirm_remove=st.checkbox('Je confirme le retrait de cette preuve de la qualification',key=f'rc21_evidence_remove_confirm_{ee["id"]}')
                    if st.button('Retirer / supprimer cette preuve',key=f'rc21_evidence_remove_{ee["id"]}',disabled=not confirm_remove):
                        try: delete_qualification_evidence(ENGINE,ee['id'],st.session_state.admin_email);st.success('Preuve retirée avec traçabilité.');rerun()
                        except ValueError as ex: st.error(str(ex))
            with st.expander('Ajouter une preuve'):
                docs=prof.get('documents') or []; doc_options={'Aucun document':None}; doc_options.update({f"{d['display_name']} — {d['category']}":d['id'] for d in docs})
                edoclab=st.selectbox('Document du dossier',list(doc_options),key=f'rc21_add_evidence_doc_{ppid}_{qrow["service_id"]}'); edoc=doc_options[edoclab]
                selected_doc=next((d for d in docs if d['id']==edoc),None)
                inferred=(selected_doc.get('category') if selected_doc else 'AUTRE') or 'AUTRE'
                inferred=inferred.upper()
                if inferred not in QUALIFICATION_EVIDENCE_TYPES:
                    inferred='DOCUMENT' if edoc else 'AUTRE'
                with st.form(f'j4_evidence_{ppid}_{qrow["service_id"]}'):
                    et=st.selectbox('Type de preuve',QUALIFICATION_EVIDENCE_TYPES,index=QUALIFICATION_EVIDENCE_TYPES.index(inferred) if inferred in QUALIFICATION_EVIDENCE_TYPES else 0)
                    criteria_options=[('Preuve générale',None)]+[(cr['label'],cr['id']) for cr in qdetail['criteria']]
                    ecl=st.selectbox('Rattacher à un critère',[x[0] for x in criteria_options]); ecid=dict(criteria_options)[ecl]
                    etxt=st.text_area('Description / autre preuve',height=80); ego=st.form_submit_button('Ajouter la preuve')
                if ego:
                    try:add_qualification_evidence(ENGINE,ppid,qrow['service_id'],st.session_state.admin_email,et,etxt or None,ecid,edoc);st.success('Preuve ajoutée.');rerun()
                    except ValueError as ex:st.error(str(ex))
            st.markdown('##### Validation humaine de la prestation')
            current_level=int(qcurrent.get('human_value') or 0)
            summary_live=qualification_adequacy_summary(ENGINE,ppid,qrow['service_id'])
            pending_required=[]
            if qdetail['criteria']:
                for cr in qdetail['criteria']:
                    if cr.get('required') and int(retained.get(cr['id'],0)) < int(cr.get('minimum_level') or 0): pending_required.append(cr)
            if pending_required:
                st.warning('Critères obligatoires sous le niveau minimal : ' + ', '.join(str(x.get('label')) for x in pending_required))
            with st.form(f'j4_service_form_{ppid}_{qrow["service_id"]}'):
                hv=st.selectbox('Niveau global validé',[0,1,2,3,4],index=current_level,format_func=lambda x:f"{x} — {QUALIFICATION_LEVEL_LABELS[x]}")
                hc=st.text_area('Commentaire de validation',value=qcurrent.get('human_comment') or '',height=90)
                rd=st.date_input('Date de révision prévue (facultatif)',value=(datetime.fromisoformat(str(qcurrent.get('review_due_at'))[:10]).date() if qcurrent.get('review_due_at') else None),format=app_date_input_format())
                exception_reason=st.text_area('Motif de dérogation (obligatoire si un critère obligatoire reste insuffisant)',height=70,disabled=not bool(pending_required))
                hsave=st.form_submit_button('Valider la qualification',type='primary')
            if hsave:
                try:
                    for cr in qdetail['criteria']:
                        set_human_criterion_assessment(ENGINE,ppid,cr['id'],retained[cr['id']],st.session_state.admin_email,comments[cr['id']] or None,True)
                    set_human_service_qualification(ENGINE,ppid,qrow['service_id'],hv,st.session_state.admin_email,hc or None,True,rd.isoformat() if rd else None,exception_reason or None,True)
                    st.session_state.pop(prefill_key,None)
                    # Le retour Action relira l'éligibilité depuis la base : aucun statut n'est mis en cache.
                    mark_qualification_saved_for_action(st.session_state,ppid)
                    st.success('Grille et qualification humaine enregistrées en une seule validation.');rerun()
                except ValueError as ex:st.error(str(ex))
            return_action_id=st.session_state.get('_rc222_return_action_id')
            return_ppid=st.session_state.get('_rc222_return_action_ppid')
            return_sid=st.session_state.get('_rc222_return_action_service_id')
            if return_action_id and return_ppid==ppid and (return_sid is None or int(return_sid)==int(qrow['service_id'])):
                refreshed=action_professional_eligibility(ENGINE,int(return_action_id),ppid)
                if st.session_state.pop('_rc222_qualification_saved_for_action',False):
                    if refreshed.get('eligible'):
                        st.success('Qualification enregistrée : cette personne répond maintenant aux exigences humaines de l’action d’origine.')
                    else:
                        st.warning('Qualification enregistrée. L’éligibilité de l’action a été recalculée : '+str(refreshed.get('reason') or 'des exigences restent à traiter.'))
                st.markdown('##### Retour à l’action d’origine')
                st.caption('Éligibilité recalculée maintenant : '+str(refreshed.get('status') or 'A_VERIFIER')+' — '+str(refreshed.get('reason') or ''))
                if st.button('← Retour à l’action et à ses intervenants',key=f'rc222_return_action_{return_action_id}_{ppid}_{qrow["service_id"]}'):
                    prepare_return_to_action(
                        st.session_state, return_action_id, bool(refreshed.get('eligible')),
                        refreshed.get('reason'), refreshed.get('status'),
                    )
                    rerun()
            if qdetail['history']:
                with st.expander('Historique de qualification'):
                    st.dataframe(pd.DataFrame([{'Date':format_app_datetime(h['created_at']),'Événement':h['event_type'],'Ancien niveau':h.get('old_human_value'),'Nouveau niveau':h.get('new_human_value'),'Commentaire':h.get('comment') or '','Auteur':h['actor']} for h in qdetail['history']]),use_container_width=True,hide_index=True)
        else:
            st.info('Aucune prestation active dans le référentiel.')
    if pmissions:
        st.markdown('#### Missions / Affectations')
        st.caption("Vue opérationnelle des actions auxquelles cette personne est affectée. La qualification utilisée reste contrôlée par les règles de l’action.")
        missions=professional_missions_view(ENGINE,ppid)
        st.caption('Historique des lettres de mission / engagements : références consultables ; aucune émission ni signature dans Gestion des Actions.')
        prow=one(ENGINE,'SELECT trainer_id FROM professional_persons WHERE professional_person_id=:p',{'p':ppid})
        if prow and prow.get('trainer_id'):
            j8_history=list_trainer_missions(ENGINE,prow['trainer_id'])
            if j8_history:
                st.dataframe(pd.DataFrame([{'Action':m['action_no'],'Mission':m['mission_id'],
                    'État':m['status'],'Document':m.get('document_ref') or '—',
                    'Version':m.get('document_version') or '—','Période':(m.get('period_start') or '')+' / '+(m.get('period_end') or ''),
                    'En cours':'Oui' if m['active'] else 'Non'} for m in j8_history]),use_container_width=True,hide_index=True)
        if missions:
            st.dataframe(pd.DataFrame([{'Action':m.get('action_no') or '', 'Intitulé':m.get('title') or '', 'Dates':m.get('dates') or '', 'Prestation':m.get('service_name') or 'À définir', 'Rôle':m.get('role') or '', 'Référent':'Oui' if m.get('is_referent') else 'Non', 'Qualification':m.get('eligibility_status') or '', 'Niveau humain':m.get('human_value') if m.get('human_value') is not None else '—'} for m in missions]),use_container_width=True,hide_index=True)
        else:
            st.info('Aucune mission ou affectation active enregistrée pour cette personne.')
    if pcv:
        st.markdown('#### CV Clarté360')
        st.caption("Le CV est généré uniquement à partir du dossier professionnel et des qualifications validées humainement. Aucune compétence n’est inventée ou déduite.")
        cv_status_internal=professional_cv_status(ENGINE,ppid,'INTERNE')
        cv_status_client=professional_cv_status(ENGINE,ppid,'CLIENT')
        cvi,cvc=st.columns(2)
        with cvi:
            st.markdown('**Version interne**')
            st.caption(cv_status_internal['label'])
            st.caption('Dossier complet : coordonnées professionnelles, informations de collaboration et éléments internes utiles à Clarté360.')
            if st.button('Préparer le CV interne',key=f'j8_cv_internal_{ppid}'):
                data=professional_cv_pdf(ENGINE,ppid,'INTERNE'); name=f"CV_CLARTE360_INTERNE_{ppid}.pdf"; ver=record_professional_cv_generation(ENGINE,ppid,'INTERNE',name,data,st.session_state.admin_email); st.session_state[f'j8_cv_data_{ppid}_INTERNE']=(data,name,ver)
            if st.session_state.get(f'j8_cv_data_{ppid}_INTERNE'):
                data,name,ver=st.session_state[f'j8_cv_data_{ppid}_INTERNE']; st.download_button(f'Télécharger le CV interne - version {ver}',data,name,'application/pdf',key=f'j8_dl_internal_{ppid}')
        with cvc:
            st.markdown('**Version client**')
            st.caption(cv_status_client['label'])
            st.caption('Version de présentation : les coordonnées personnelles, notes internes et informations administratives non nécessaires ne sont pas diffusées.')
            if st.button('Préparer le CV client',key=f'j8_cv_client_{ppid}',type='primary'):
                data=professional_cv_pdf(ENGINE,ppid,'CLIENT'); name=f"CV_CLARTE360_CLIENT_{ppid}.pdf"; ver=record_professional_cv_generation(ENGINE,ppid,'CLIENT',name,data,st.session_state.admin_email); st.session_state[f'j8_cv_data_{ppid}_CLIENT']=(data,name,ver)
            if st.session_state.get(f'j8_cv_data_{ppid}_CLIENT'):
                data,name,ver=st.session_state[f'j8_cv_data_{ppid}_CLIENT']; st.download_button(f'Télécharger le CV client - version {ver}',data,name,'application/pdf',key=f'j8_dl_client_{ppid}')
        hist=professional_cv_history(ENGINE,ppid)
        if hist:
            st.markdown('##### Historique des générations')
            st.dataframe(pd.DataFrame([{'Date':format_app_datetime(x.get('generated_at')),'Version':x['version_no'],'Audience':'Interne' if x['audience']=='INTERNE' else 'Client','Fichier':x['file_name'],'Généré par':x['generated_by']} for x in hist]),use_container_width=True,hide_index=True)
    if pdocs:
        if prof['documents']:
            st.dataframe(pd.DataFrame([{'Document':x['display_name'],'Catégorie':x['category'],'Valide jusqu’au':format_app_date(x.get('valid_until')),'Ajouté le':format_app_date(x['created_at'])} for x in prof['documents']]),use_container_width=True,hide_index=True)
            with st.expander('Ouvrir / modifier un document du tableau'):
                dmap={f"{d['display_name']} — {d['category']}":d for d in prof['documents']}; dlab=st.selectbox('Document à gérer',list(dmap),key=f'rc2p_doc_manage_{ppid}'); dm=dmap[dlab]
                try:
                    with open(dm['storage_path'],'rb') as fh: st.download_button('Ouvrir / télécharger le document',fh.read(),file_name=dm['display_name'],mime=dm.get('mime_type') or 'application/octet-stream',key=f'rc2p_doc_open_{ppid}_{dm["id"]}')
                except Exception: st.caption('Le fichier physique n’est pas accessible depuis cette session.')
                with st.form(f'rc2p_doc_edit_{ppid}_{dm["id"]}'):
                    dn=st.text_input('Nom affiché',value=dm['display_name']); dc=st.selectbox('Catégorie',PROFESSIONAL_DOCUMENT_CATEGORIES,index=PROFESSIONAL_DOCUMENT_CATEGORIES.index(dm['category'])); dv=st.date_input('Valide jusqu’au',value=(datetime.fromisoformat(str(dm.get('valid_until'))[:10]).date() if dm.get('valid_until') else None),format=app_date_input_format()); dx=st.text_area('Notes',value=dm.get('notes') or '')
                    dsave=st.form_submit_button('Enregistrer les modifications')
                if dsave:
                    update_professional_document_metadata(ENGINE,ppid,dm['id'],dn,dc,dv.isoformat() if dv else None,dx,st.session_state.admin_email);st.success('Document modifié.');rerun()
                st.caption('Visibilité du document : INTERNE par défaut. Le partage avec l’intervenant nécessite une décision explicite.')
                current_shared=(dm.get('visibility')=='INTERVENANT')
                share=st.checkbox('Partager ce document dans l’espace personnel de cet intervenant',value=current_shared,key=f'j6_share_prof_doc_{ppid}_{dm["id"]}')
                if share!=current_shared and st.button('Enregistrer la visibilité',key=f'j6_share_save_{ppid}_{dm["id"]}'):
                    set_professional_document_visibility(ENGINE,ppid,dm['id'],'INTERVENANT' if share else 'INTERNE',st.session_state.admin_email)
                    st.success('Visibilité actualisée.');rerun()
        with st.form(f'j2_doc_{ppid}'):
            up=st.file_uploader('Ajouter un document',type=['pdf','doc','docx','jpg','jpeg','png','webp']);cat=st.selectbox('Catégorie',PROFESSIONAL_DOCUMENT_CATEGORIES);valid=st.date_input('Valide jusqu’au (si applicable)',value=None,format=app_date_input_format());da=st.form_submit_button('Ajouter le document',type='primary')
        if da and up:
            try:store_professional_document(ENGINE,ppid,up.getvalue(),up.name,cat,st.session_state.admin_email,valid_until=valid.isoformat() if valid else None);st.success('Document ajouté.');rerun()
            except ValueError as ex:st.error(str(ex))
        if prof['documents']:
            st.markdown('#### Analyse globale du dossier')
            st.caption("Analyse de l'ensemble des pièces disponibles pour préparer le dossier professionnel et repérer les prestations pertinentes. L'IA propose ; vous validez ou rejetez chaque proposition.")
            j14_model=str(secret('openai','model','gpt-5-mini') or 'gpt-5-mini'); j14_key=str(secret('openai','api_key',os.environ.get('OPENAI_API_KEY','')) or '')
            j14_gateway=GlobalDossierAIGateway(j14_key,j14_model)
            ai_state=professional_global_ai_reanalysis_state(ENGINE,ppid)
            if ai_state.get('latest_run'):
                st.caption(f"Empreintes SHA-256 : {len(ai_state['unchanged_documents'])} document(s) inchangé(s) ne seront pas retransmis à l'IA ; {len(ai_state['to_analyze_documents'])} nouveau(x) ou modifié(s) ; {len(ai_state['removed_documents'])} retiré(s) depuis la dernière analyse.")
            if ai_state.get('duplicate_active_documents'):
                st.info(f"{len(ai_state['duplicate_active_documents'])} doublon(s) binaire(s) détecté(s) : une seule copie par empreinte SHA-256 sera utilisée par l'analyse.")
            if ai_state.get('new_versions'):
                for ver in ai_state['new_versions']:
                    st.info(f"Nouvelle version détectée : {ver['current'].get('display_name')} — l'empreinte SHA-256 diffère de la version analysée précédemment.")
            candidates=ai_state['to_analyze_documents'] if ai_state.get('latest_run') else ai_state['active_unique_documents']
            j14_doc_map={f"{d['display_name']} — {d['category']} — {str(d.get('sha256') or '')[:12]}…":d for d in candidates if (d.get('extension') or '').lower().lstrip('.') in ('pdf','docx','txt','md','csv','jpg','jpeg','png','webp')}
            if ai_state.get('latest_run') and not j14_doc_map and not ai_state.get('removed_documents'):
                st.success("Aucun document nouveau, modifié ou retiré depuis la dernière analyse : relancer l'IA serait inutile et n'est pas proposé.")
            j14_sel=st.multiselect('Documents nouveaux ou modifiés à analyser' if ai_state.get('latest_run') else 'Documents à analyser globalement',list(j14_doc_map),default=list(j14_doc_map),key=f'j14_global_docs_{ppid}')
            if ai_state.get('removed_documents'):
                st.caption("Le retrait de document(s) sera aussi pris en compte : les faits qui provenaient exclusivement de ces pièces seront retirés de la base factuelle avant recalcul des 26 prestations.")
            j14_consent=st.checkbox("Je confirme que cette analyse IA est autorisée et que les documents nouveaux ou modifiés sélectionnés peuvent être transmis pour préparer le dossier.",key=f'j14_global_consent_{ppid}')
            can_analyze=bool(j14_gateway.ready and j14_consent and (j14_sel or ai_state.get('removed_documents') or not ai_state.get('latest_run')))
            if st.button('Analyser globalement le dossier',type='primary',key=f'j14_global_analyze_{ppid}',disabled=not can_analyze):
                try:
                    delta_ids=[j14_doc_map[x]['id'] for x in j14_sel]
                    payload=build_global_professional_ai_payload(ENGINE,ppid,delta_ids); safe=[]; images=[]; files=[]
                    for label in j14_sel:
                        d=j14_doc_map[label]; ext=(d.get('extension') or '').lower().lstrip('.')
                        if ext in ('jpg','jpeg','png','webp'):
                            try:
                                raw=open(d.get('storage_path') or '','rb').read()
                                mime={'jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png','webp':'image/webp'}[ext]
                                images.append({'document_id':d['id'],'name':d['display_name'],'category':d['category'],'data_url':f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"})
                                safe.append({'document_id':d['id'],'name':d['display_name'],'category':d['category'],'text':'[IMAGE TRANSMISE AU MODELE]'})
                            except Exception:
                                safe.append({'document_id':d['id'],'name':d['display_name'],'category':d['category'],'text':'[IMAGE NON LISIBLE - A VERIFIER]'})
                        elif ext=='pdf':
                            pdf_info=inspect_pdf_for_ai(d.get('storage_path') or '',18000)
                            txt=pdf_info.get('text') or ''
                            marker='[PDF TEXTE]'
                            if pdf_info.get('is_hybrid'):
                                marker='[PDF HYBRIDE : TEXTE EXTRAIT + PAGES VISUELLES TRANSMISES AU MODELE]'
                            elif pdf_info.get('needs_multimodal'):
                                marker='[PDF SCANNE TRANSMIS AU MODELE COMME FICHIER]'
                            safe.append({'document_id':d['id'],'name':d['display_name'],'category':d['category'],'text':(marker+'\n'+txt).strip()})
                            if pdf_info.get('needs_multimodal'):
                                try:
                                    raw=open(d.get('storage_path') or '','rb').read()
                                    files.append({'document_id':d['id'],'name':d['display_name'],'category':d['category'],'data_url':f"data:application/pdf;base64,{base64.b64encode(raw).decode('ascii')}",'pdf_mode':'HYBRIDE' if pdf_info.get('is_hybrid') else 'SCANNE'})
                                except Exception:
                                    safe[-1]['text'] += '\n[PARTIE VISUELLE NON LISIBLE - A VERIFIER]'
                        else:
                            safe.append({'document_id':d['id'],'name':d['display_name'],'category':d['category'],'text':extract_document_text(d.get('storage_path') or '',d.get('extension') or '',18000)})
                    payload['document_contents']=safe; payload['document_images']=images; payload['document_files']=files; payload['documents']=[{k:v for k,v in d.items() if k!='storage_path'} for d in payload['documents']]
                    if ai_state.get('latest_run'):
                        payload['_base_facts']=ai_state.get('base_facts')
                    res=j14_gateway.analyze(payload)
                    covered_ids=[int(d['id']) for d in ai_state.get('unchanged_documents') or []]+[int(x) for x in delta_ids]
                    save_global_professional_ai_analysis(ENGINE,ppid,res['result'],st.session_state.admin_email,res['provider'],res['model'],res['prompt_version'],res['request_hash'],res.get('usage'),covered_ids,res.get('run_metrics'))
                    st.session_state.pop(f'rc21_ai_failed_{ppid}',None)
                    st.success("Analyse globale enregistrée. Les documents dont l'empreinte était inchangée n'ont pas été retransmis ; leurs faits antérieurs ont été réutilisés. Les 26 prestations ont ensuite été recalculées sur la base factuelle consolidée.");rerun()
                except Exception as ex:
                    st.session_state[f'rc21_ai_failed_{ppid}']=str(ex)
                    st.error(f"L'analyse globale n'a pas pu aboutir. Aucun résultat partiel n'a été enregistré. Les documents restent conservés. Détail : {ex}")
            grun=latest_global_professional_ai_run(ENGINE,ppid)
            if st.session_state.get(f'rc21_ai_failed_{ppid}') and grun:
                st.warning("La dernière tentative d'analyse a échoué. Les résultats affichés ci-dessous proviennent de la dernière analyse réussie et peuvent être antérieurs aux documents actuellement sélectionnés.")
            if grun:
                gout=json.loads(grun.get('output_json') or '{}'); alerts=gout.get('identity_alerts') or []
                if alerts:
                    st.error('Points d’identité à vérifier : ' + ' | '.join(str(x) for x in alerts))
                created=str(grun.get('created_at') or '')
                st.caption(f"Dernière analyse réussie : {format_app_datetime(created)} — modèle {grun.get('model') or '—'} — prompt {grun.get('prompt_version') or '—'}")
                with st.expander('Détails techniques IA — analyse'):
                    c1,c2,c3,c4=st.columns(4)
                    c1.metric('Durée',f"{float(grun.get('duration_seconds') or 0):.1f} s")
                    c2.metric('Appels API',int(grun.get('api_call_count') or 0))
                    c3.metric('Retries',int(grun.get('retry_count') or 0))
                    c4.metric('Statut',grun.get('status') or 'SUCCESS')
                    c1,c2,c3=st.columns(3)
                    c1.metric('Tokens entrée',int(grun.get('input_tokens') or 0))
                    c2.metric('Tokens sortie',int(grun.get('output_tokens') or 0))
                    c3.metric('Tokens total',int(grun.get('total_tokens') or 0))
                    if grun.get('estimated_cost') is not None: st.caption(f"Coût estimé : ${float(grun['estimated_cost']):.4f}")
                    try: sent_ids=[int(x) for x in json.loads(grun.get('selected_document_ids_json') or '[]')]
                    except Exception: sent_ids=[]
                    sent_docs=[d.get('display_name') for d in (prof.get('documents') or []) if int(d.get('id') or 0) in sent_ids]
                    st.write('Documents réellement transmis : ' + (', '.join(sent_docs) if sent_docs else 'aucun / non disponible'))
                    st.caption('Les dates sont affichées dans le fuseau local configuré de l’application ; les secrets et clés techniques ne sont jamais exposés.')
                svc_names={int(s['id']):s['name'] for s in list_services(ENGINE,active_only=True)}
                svc_rows=[]
                for data in gout.get('service_candidates') or []:
                    sid=int(data.get('service_id') or 0); level=int(data.get('service_level') or 0)
                    evn=len(data.get('evidence') or []); positive=sum(1 for c in (data.get('criteria') or []) if int(c.get('proposed_level') or 0)>0)
                    if evn==0 and positive==0: lecture='Aucun élément repéré'
                    elif level==0: lecture='Éléments repérés — niveau global bloqué'
                    elif level<3: lecture='Rapprochement partiel'
                    else: lecture='Rapprochement fort'
                    below=data.get('required_criteria_below_min') or []
                    svc_rows.append({'Prestation':svc_names.get(sid,f'Prestation #{sid}'),'Lecture IA':lecture,
                      'Critères avec éléments':f"{positive}/{len(data.get('criteria') or [])}",
                      'Obligatoires à vérifier':len(below),'Preuves repérées':evn,'Points ouverts':len(data.get('missing_points') or []),
                      'Niveau IA indicatif':f"{level}/4",'Confiance analyse':f"{float(data.get('confidence') or 0):.0%}"})
                if svc_rows:
                    st.markdown('##### Résultat IA sur l’ensemble des prestations')
                    st.caption("Les 26 prestations sont directement disponibles dans l’onglet Qualifications. Il n’y a plus d’étape « Retenir pour instruction ». Un niveau 0/4 n’est plus assimilé automatiquement à une absence de rapprochement lorsqu’il existe des éléments probants.")
                    st.dataframe(pd.DataFrame(svc_rows),use_container_width=True,hide_index=True)
                pending=[x for x in grun.get('suggestions',[]) if x.get('status')=='PROPOSE' and x.get('suggestion_type')!='SERVICE_CANDIDATE']
                if pending:
                    labels={'PROFILE':'Profil','SPECIALTY':'Spécialité','EXPERIENCE':'Expérience','EDUCATION':'Diplôme / formation','CERTIFICATION':'Certification / habilitation','LANGUAGE':'Langue','IDENTITY_ALERT':'Alerte identité','MISSING_POINT':'Point à vérifier'}
                    for sug in pending:
                        data=json.loads(sug.get('payload_json') or '{}'); st.markdown(f"**{labels.get(sug['suggestion_type'],sug['suggestion_type'])}** — {json.dumps(data,ensure_ascii=False)}")
                        cacc,crej=st.columns(2)
                        if cacc.button('Accepter',key=f"j14_acc_{sug['id']}",disabled=sug['suggestion_type'] in ('IDENTITY_ALERT','MISSING_POINT')):
                            review_professional_ai_suggestion(ENGINE,sug['id'],'ACCEPTE',st.session_state.admin_email);rerun()
                        if crej.button('Rejeter / classer',key=f"j14_rej_{sug['id']}"):
                            review_professional_ai_suggestion(ENGINE,sug['id'],'REJETE',st.session_state.admin_email);rerun()
        if prof['documents']:
            with st.expander('Archiver un document obsolète'):
                amap={f"{d['display_name']} — {d['category']}":d['id'] for d in prof['documents']}
                alab=st.selectbox('Document à archiver',list(amap),key=f'j7_archive_doc_{ppid}')
                aconfirm=st.checkbox('Je confirme que ce document doit quitter le dossier actif',key=f'j7_archive_confirm_{ppid}')
                if st.button('Archiver le document',key=f'j7_archive_btn_{ppid}',disabled=not aconfirm):
                    try:archive_professional_document(ENGINE,ppid,amap[alab],st.session_state.admin_email);st.success('Document archivé.');rerun()
                    except ValueError as ex:st.error(str(ex))
    st.caption("Les signalements et remontées des intervenants sont traités dans l'écran Qualité, qui constitue le point de gestion unique de ces événements.")


def _j6_professional_pilotage():
    st.subheader('Pilotage & référentiels des intervenants')
    st.caption('Candidatures, qualifications et recherche, alertes et référentiel des prestations.')
    sub_candidates,sub_matrix,sub_alertes,sub_prestations=st.tabs(['Candidats','Qualifications & recherche','Alertes','Prestations'])
    with sub_candidates:
        st.subheader('Candidats')
        st.caption('Vue de pilotage des candidatures. La décision de transformer un candidat en intervenant reste humaine et se réalise dans son dossier professionnel.')
        candidates=[x for x in professional_people_operational_view(ENGINE,include_inactive=True) if x.get('principal_status')=='CANDIDAT']
        c1,c2=st.columns([2,1]); cq=c1.text_input('Rechercher un candidat',placeholder='Nom, email, ville...',key='j9_candidate_search'); cs=c2.selectbox('État de candidature',['TOUS','NOUVEAU','INCOMPLET','EN_ETUDE','COMPLEMENT_DEMANDE','ENTRETIEN_A_PREVOIR','PRET_DECISION','REFUSE','ABANDONNE'],key='j9_candidate_state')
        nq=(cq or '').strip().lower(); shown=[]
        for x in candidates:
            if cs!='TOUS' and x.get('candidate_work_status')!=cs: continue
            hay=' '.join(str(x.get(k) or '') for k in ('display_name','profile_email','trainer_email','city')).lower()
            if nq and nq not in hay: continue
            shown.append(x)
        if shown:
            st.dataframe(pd.DataFrame([{'Candidat':x['display_name'],'Origine':x.get('origin') or '—','État':x['candidate_work_status'].replace('_',' ').title(),'Complétude':f"{x.get('completion_percent') or 0} %",'Manquants':x.get('missing_items') or '—','Prestations revendiquées':x.get('claimed_services') or 'Non renseigné','Dernière activité':format_app_datetime(x.get('last_activity')),'À faire':x.get('next_action') or 'Étudier'} for x in shown]),use_container_width=True,hide_index=True)
            cmap={f"{x['display_name']} — {x['candidate_work_status'].replace('_',' ')}":x for x in shown}; clab=st.selectbox('Candidat à gérer',list(cmap),key='rc2p_candidate_action'); cp=cmap[clab]
            ca1,ca2,ca3=st.columns(3)
            if ca1.button('Ouvrir / étudier',key='rc2p_candidate_open'):
                st.session_state['_j2_open_ppid']=cp['professional_person_id'];st.session_state['_rc2p_focus_candidate']=cp['professional_person_id'];st.session_state['j9_status_filter']='Tous';rerun()
            if cp.get('active') and ca2.button('Inactiver',key='rc2p_candidate_inactivate'):
                set_professional_active(ENGINE,cp['professional_person_id'],False,st.session_state.admin_email,'Inactivation candidat depuis la liste');rerun()
            deps=professional_delete_dependencies(ENGINE,cp['professional_person_id'])
            with ca3:
                if not deps:
                    cdel=st.checkbox('Confirmer suppression',key='rc2p_candidate_del_confirm')
                    if st.button('Supprimer définitivement',key='rc2p_candidate_delete',disabled=not cdel): delete_professional_if_unused(ENGINE,cp['professional_person_id'],st.session_state.admin_email);rerun()
                else: st.caption('Suppression physique indisponible : ' + ' ; '.join(deps) + '. Inactivation/archivage uniquement.')
        else: st.info('Aucun candidat ne correspond aux filtres.')

    with sub_matrix:
        st.subheader('Qualifications & pilotage DRH')
        st.caption("Vue de décision issue des dossiers professionnels. Les propositions IA restent dans le détail du dossier ; seule la validation humaine fait foi.")
        mx=collective_qualification_matrix(ENGINE,include_candidates=False,include_inactive=False,active_services_only=True)
        status_labels={'A_INSTRUIRE':'À instruire','POINTS_OUVERTS':'Points ouverts','REVISION_ECHUE':'Révision échue','REVISION_PROCHAINE':'Révision prochaine','QUALIFICATION_VALIDEE':'Qualification validée','NON_EVALUEE':'Non évaluée'}
        c1,c2=st.columns([2,1])
        wanted=c1.multiselect('Priorités à afficher',list(status_labels),default=list(status_labels),format_func=lambda x:status_labels[x],key='p4_status_filter')
        search=c2.text_input('Rechercher',placeholder='Intervenant ou prestation',key='p4_matrix_search').strip().lower()
        shown=[x for x in mx if x.get('management_status') in wanted and (not search or search in (x['name']+' '+x['service_name']).lower())]
        if shown:
            st.dataframe(pd.DataFrame([{
                'Intervenant':x['name'],'Prestation':x['service_name'],'Statut':status_labels.get(x['management_status'],x['management_status']),
                'Niveau humain':(f"{x['human_value']} — {QUALIFICATION_LEVEL_LABELS.get(x['human_value'],'')}" if x.get('human_value') is not None else '—'),
                'Critères obligatoires':f"{x['required_ok']}/{x['required_total']}" if x['required_total'] else '—',
                'Points à traiter':x.get('open_points_count') or 0,'Preuves':x['evidence_count'],
                'Validation':x.get('human_validated_at') or '—','Révision':x.get('review_due_at') or '—'
            } for x in shown]),use_container_width=True,hide_index=True)
            amap={f"{x['name']} — {x['service_name']} — {status_labels.get(x['management_status'],x['management_status'])}":x for x in shown}
            alab=st.selectbox('Qualification à traiter',list(amap),key='p4_open_qualification'); ar=amap[alab]
            if st.button('Ouvrir le dossier sur cette qualification',key='p4_open_qualification_btn'):
                st.session_state['_j2_open_ppid']=ar['professional_person_id']; st.session_state['_rc222_dossier_screen']='Qualifications';st.session_state['_j6_next_professional_workspace']='Dossiers professionnels'; st.session_state['_j17_focus_service_id']=ar['service_id']; st.session_state['j9_status_filter']='Tous'; rerun()
        else:
            st.info('Aucune qualification ne correspond aux filtres.')
        st.markdown('#### Rechercher un intervenant pour une prestation')
        active_svcs=list_services(ENGINE,active_only=True)
        if active_svcs:
            msmap={f"{x['name']} — {x['service_code']}":x for x in active_svcs}
            mlabel=st.selectbox('Prestation recherchée',list(msmap),key='j6_service_search'); msvc=msmap[mlabel]
            c1,c2,c3=st.columns(3)
            mlevel=c1.selectbox('Niveau humain minimum',[0,1,2,3,4],index=3,format_func=lambda x:f"{x} — {QUALIFICATION_LEVEL_LABELS[x]}",key='j6_min_level')
            mcollab=c2.selectbox('Type de collaboration avec Clarté360',['TOUS']+list(PROFESSIONAL_COLLABORATION_TYPES),key='j6_collab',format_func=lambda x:'Tous' if x=='TOUS' else _collaboration_label(x))
            mcity=c3.text_input('Ville contient',key='j6_city')
            mreq=st.checkbox('Exiger que tous les critères obligatoires renseignés atteignent leur niveau minimal',value=False,key='j6_required_complete')
            found=search_qualified_professionals(ENGINE,msvc['id'],mlevel,mreq,mcollab,mcity,False)
            if found:
                st.success(f"{len(found)} intervenant(s) correspondant aux critères humains validés.")
                st.dataframe(pd.DataFrame([{'Intervenant':x['name'],'Niveau humain':f"{x['human_value']} — {QUALIFICATION_LEVEL_LABELS[x['human_value']]}",'Collaboration':_collaboration_label(x['collaboration_type']),'Ville':x.get('city') or '','Critères requis':f"{x['required_ok']}/{x['required_total']}" if x['required_total'] else '—','Points à traiter':x.get('open_points_count') or 0,'Preuves':x['evidence_count'],'Révision':x.get('review_due_at') or ''} for x in found]),use_container_width=True,hide_index=True)
                st.caption("Résultats alphabétiques : l’application aide à identifier les personnes répondant aux critères humains ; elle ne choisit jamais l’intervenant.")
            else: st.info('Aucun intervenant actif ne correspond actuellement à ces critères de qualification humaine.')
        else: st.info('Aucune prestation active dans le référentiel.')
    with sub_prestations:
        st.subheader('Référentiel des prestations Clarté360')
        st.caption("Les familles sont des données maîtresses : aucune famille n'est saisie librement. Les prestations et critères restent administrables et versionnés sans modification du code.")

        # --- J15 : familles de prestations ---
        st.markdown('### Familles de prestations')
        families=list_service_families(ENGINE)
        if families:
            st.dataframe(pd.DataFrame([{
                'Famille':x['name'],'Code':x['family_code'],'Prestations':x.get('service_count') or 0,
                'Ordre':x['sort_order'],'Version':x['current_version'],'Actif':'Oui' if x['active'] else 'Non'
            } for x in families]),use_container_width=True,hide_index=True)
        with st.expander('Ajouter une famille'):
            with st.form('j15_add_family',clear_on_submit=True):
                c1,c2=st.columns(2); fcode=c1.text_input('Code stable *'); fname=c2.text_input('Nom de la famille *')
                fdesc=st.text_area('Description',height=70); forder=st.number_input('Ordre d’affichage',min_value=0,max_value=999,value=100,step=10)
                fadd=st.form_submit_button('Créer la famille',type='primary')
            if fadd:
                try:
                    add_service_family(ENGINE,fcode,fname,fdesc or None,forder,st.session_state.admin_email)
                    st.success('Famille créée.');rerun()
                except ValueError as ex: st.error(str(ex))
        if families:
            fmap={f"{x['name']} — {x['family_code']}":x for x in families}; flabel=st.selectbox('Famille à gérer',list(fmap),key='j15_family_manage'); fam=fmap[flabel]
            with st.form(f"j15_family_edit_{fam['id']}"):
                c1,c2=st.columns([3,1]); efname=c1.text_input('Nom de la famille',value=fam['name']); eford=c2.number_input('Ordre',0,999,int(fam['sort_order']),10)
                efdesc=st.text_area('Description de la famille',value=fam.get('description') or '',height=70); efactive=st.checkbox('Famille active',value=bool(fam['active']))
                efreason=st.text_input('Motif de modification',value='Mise à jour administrative'); efsave=st.form_submit_button('Enregistrer la famille')
            if efsave:
                try:
                    update_service_family(ENGINE,fam['id'],{'name':efname,'description':efdesc or None,'sort_order':eford,'active':efactive},st.session_state.admin_email,efreason or 'Mise à jour famille')
                    st.success('Famille mise à jour. Les prestations rattachées ont suivi le renommage.');rerun()
                except ValueError as ex: st.error(str(ex))
            with st.expander('Supprimer / fusionner cette famille'):
                attached=int(fam.get('service_count') or 0)
                targets=[x for x in families if x['id']!=fam['id'] and x['active']]
                st.caption(f"{attached} prestation(s) actuellement rattachée(s). Si la famille est utilisée, choisissez une famille de destination : toutes les prestations seront réaffectées avant suppression.")
                target_map={'— Aucune —':None}; target_map.update({x['name']:x['id'] for x in targets})
                tgt=st.selectbox('Famille de destination',list(target_map),key=f'j15_family_target_{fam["id"]}')
                confirm=st.text_input('Saisissez SUPPRIMER',key=f'j15_family_delete_confirm_{fam["id"]}')
                if st.button('Supprimer la famille',key=f'j15_family_delete_{fam["id"]}',disabled=confirm!='SUPPRIMER'):
                    try:
                        delete_service_family(ENGINE,fam['id'],st.session_state.admin_email,target_map[tgt]);st.success('Famille supprimée et prestations réaffectées si nécessaire.');rerun()
                    except ValueError as ex: st.error(str(ex))

        # --- J15 : catalogue filtrable et réaffectation en masse ---
        st.markdown('### Prestations')
        families=list_service_families(ENGINE); active_families=[x for x in families if x['active']]
        all_services=list_services(ENGINE)
        c1,c2,c3=st.columns([2,1,1])
        sf_search=c1.text_input('Rechercher une prestation',placeholder='Nom ou code...',key='j15_service_search')
        fam_filter_map={'Toutes':None}; fam_filter_map.update({x['name']:x['id'] for x in families})
        sf_family=c2.selectbox('Famille',list(fam_filter_map),key='j15_service_family_filter')
        sf_state=c3.selectbox('État',['Actives','Toutes','Inactives'],key='j15_service_state')
        services_rows=list(all_services)
        if fam_filter_map[sf_family] is not None: services_rows=[x for x in services_rows if x.get('family_id')==fam_filter_map[sf_family]]
        if sf_state=='Actives': services_rows=[x for x in services_rows if x['active']]
        elif sf_state=='Inactives': services_rows=[x for x in services_rows if not x['active']]
        if sf_search.strip():
            needle=sf_search.strip().lower(); services_rows=[x for x in services_rows if needle in x['name'].lower() or needle in x['service_code'].lower()]
        if services_rows:
            st.dataframe(pd.DataFrame([{
                'Code':x['service_code'],'Prestation':x['name'],'Famille':x.get('family_master_name') or x.get('family') or '',
                'Portée':x['delivery_scope'].replace('_',' ').title(),'Critères':x.get('criterion_count') or 0,'Personnes qualifiées':x.get('qualified_people_count') or 0,'Version':x['current_version'],
                'Source':x['source'].replace('_',' ').title(),'Actif':'Oui' if x['active'] else 'Non'
            } for x in services_rows]),use_container_width=True,hide_index=True,height=min(520,70+35*len(services_rows)))
        else: st.info('Aucune prestation ne correspond aux filtres.')

        with st.expander('Réaffecter plusieurs prestations à une famille'):
            svc_opts={f"{x['name']} — {x['service_code']}":x['id'] for x in all_services}
            selected=st.multiselect('Prestations à déplacer',list(svc_opts),key='j15_bulk_services')
            dest_opts={x['name']:x['id'] for x in active_families}
            dest=st.selectbox('Nouvelle famille',list(dest_opts) if dest_opts else ['—'],key='j15_bulk_family')
            if st.button('Réaffecter les prestations sélectionnées',key='j15_bulk_apply',disabled=not selected or not dest_opts):
                try:
                    n=reassign_services_to_family(ENGINE,[svc_opts[x] for x in selected],dest_opts[dest],st.session_state.admin_email,'Réaffectation en masse J15')
                    st.success(f'{n} prestation(s) réaffectée(s).');rerun()
                except ValueError as ex: st.error(str(ex))

        with st.expander('Ajouter une prestation',expanded=not bool(all_services)):
            if not active_families: st.warning('Créez d’abord au moins une famille active.')
            with st.form('j15_add_service',clear_on_submit=True):
                c1,c2=st.columns(2); scode=c1.text_input('Code stable *'); sname=c2.text_input('Nom de la prestation *')
                c1,c2=st.columns(2)
                family_names=[x['name'] for x in active_families]
                sfamily_name=c1.selectbox('Famille *',family_names if family_names else ['—'])
                sscope=c2.selectbox('Portée',['MIXTE','INDIVIDUEL','COLLECTIF'])
                sdesc=st.text_area('Description',height=100); sadd=st.form_submit_button('Créer la prestation',type='primary',disabled=not bool(active_families))
            if sadd:
                try:
                    fid=next(x['id'] for x in active_families if x['name']==sfamily_name)
                    add_service(ENGINE,scode,sname,description=sdesc or None,delivery_scope=sscope,actor=st.session_state.admin_email,family_id=fid)
                    st.success('Prestation créée.');rerun()
                except ValueError as ex: st.error(str(ex))

        # Gestion détaillée : le tableau filtre, puis cette sélection ouvre directement la ligne de travail.
        all_services=list_services(ENGINE)
        if all_services:
            smap={f"{x['name']} — {x['service_code']}":x for x in all_services}; slab=st.selectbox('Ouvrir / gérer une prestation',list(smap),key='j15_service_manage'); svc=smap[slab]
            svc_detail=get_service(ENGINE,svc['id'])
            fam_names=[x['name'] for x in active_families] or [svc_detail.get('family') or '—']
            curfam=svc_detail.get('family') or fam_names[0]
            if curfam not in fam_names: fam_names.append(curfam)
            with st.form(f"j15_service_edit_{svc['id']}"):
                c1,c2=st.columns(2); ename=c1.text_input('Nom',value=svc_detail['name']); efamily_name=c2.selectbox('Famille',fam_names,index=fam_names.index(curfam))
                scopes=['MIXTE','INDIVIDUEL','COLLECTIF']; escope=st.selectbox('Portée',scopes,index=scopes.index(svc_detail['delivery_scope']) if svc_detail['delivery_scope'] in scopes else 0)
                edesc=st.text_area('Description',value=svc_detail.get('description') or '',height=100); eactive=st.checkbox('Prestation active',value=bool(svc_detail['active']))
                ereason=st.text_input('Motif de la modification',value='Mise à jour administrative'); esave=st.form_submit_button('Enregistrer la prestation')
            if esave:
                try:
                    family_id=next(x['id'] for x in active_families if x['name']==efamily_name)
                    update_service(ENGINE,svc['id'],{'name':ename,'family_id':family_id,'description':edesc or None,'delivery_scope':escope,'active':eactive},st.session_state.admin_email,ereason or 'Mise à jour prestation')
                    st.success('Prestation mise à jour et versionnée.');rerun()
                except (ValueError,StopIteration) as ex: st.error(str(ex) or 'Famille invalide.')
            with st.expander('Supprimer cette prestation'):
                st.caption('Suppression possible uniquement sans dépendance. Sinon, inactivez la prestation pour préserver l’historique.')
                sdel=st.text_input('Saisissez SUPPRIMER',key=f'j15_service_delete_confirm_{svc["id"]}')
                if st.button('Supprimer définitivement la prestation',key=f'j15_service_delete_{svc["id"]}',disabled=sdel!='SUPPRIMER'):
                    try: delete_service(ENGINE,svc['id'],st.session_state.admin_email);st.success('Prestation supprimée.');rerun()
                    except ValueError as ex: st.error(str(ex))

            st.markdown('#### Critères de compétence')
            st.caption("Grille d’instruction humaine. Les critères initiaux J15 sont des adaptations métier Clarté360, administrables et versionnées ; ils ne constituent pas une qualification automatique.")
            criteria=list_service_criteria(ENGINE,svc['id'])
            if criteria:
                st.dataframe(pd.DataFrame([{
                    'Code':x['criterion_code'],'Catégorie':SERVICE_CRITERION_CATEGORIES.get(x['category'],x['category']),
                    'Critère':x['label'],'Obligatoire':'Oui' if x['required'] else 'Non','Niveau min.':x['minimum_level'],
                    'Preuves acceptées':' ; '.join(json.loads(x.get('accepted_evidence_json') or '[]')),
                    'Origine':(x.get('source_kind') or 'ADAPTATION_CLARTE360').replace('_',' ').title(),
                    'Version':x['current_version'],'Actif':'Oui' if x['active'] else 'Non'
                } for x in criteria]),use_container_width=True,hide_index=True,height=min(520,70+35*len(criteria)))
            else: st.warning("Aucun critère défini pour cette prestation : une instruction détaillée de qualification n'est pas possible tant que la grille n'est pas créée.")

            with st.expander('Ajouter un critère de compétence'):
                with st.form(f"j15_add_criterion_{svc['id']}",clear_on_submit=True):
                    c1,c2=st.columns(2); ccode=c1.text_input('Code critère *'); ccat=c2.selectbox('Catégorie',list(SERVICE_CRITERION_CATEGORIES),format_func=lambda x:SERVICE_CRITERION_CATEGORIES[x])
                    clabel=st.text_input('Libellé du critère *'); cdesc=st.text_area('Description',height=90)
                    c1,c2,c3,c4=st.columns(4); creq=c1.checkbox('Obligatoire'); cmin=c2.selectbox('Niveau minimal',[0,1,2,3,4],index=3); cweight=c3.number_input('Pondération',min_value=0.0,value=0.0,step=0.1); cvalid=c4.number_input('Validité (mois)',min_value=0,step=1,value=0)
                    cevidence=st.text_input('Preuves acceptables (séparées par ;)',placeholder='CV ; diplôme ; certification ; mission ; entretien')
                    csource=st.selectbox('Origine',['ADAPTATION_CLARTE360','METHODE_PROFESSIONNELLE','REFERENTIEL_RECONNU','SOURCE_SCIENTIFIQUE','AIDE_REFLEXION'])
                    csref=st.text_input('Référence / justification de l’origine',value='Adaptation métier Clarté360')
                    cadd=st.form_submit_button('Ajouter le critère')
                if cadd:
                    try:
                        ev=[x.strip().upper() for x in cevidence.split(';') if x.strip()]
                        add_service_criterion(ENGINE,svc['id'],ccode,ccat,clabel,cdesc or None,creq,cweight if cweight>0 else None,cmin,ev,cvalid or None,st.session_state.admin_email,csource,csref or None)
                        st.success('Critère ajouté et versionné.');rerun()
                    except ValueError as ex: st.error(str(ex))
            if criteria:
                cmap={f"{x['label']} — {x['criterion_code']}":x for x in criteria}; clab=st.selectbox('Ouvrir / gérer un critère',list(cmap),key=f"j15_criterion_manage_{svc['id']}"); cr=cmap[clab]
                try: current_evidence=json.loads(cr.get('accepted_evidence_json') or '[]')
                except Exception: current_evidence=[]
                with st.form(f"j15_criterion_edit_{cr['id']}"):
                    categories=list(SERVICE_CRITERION_CATEGORIES); ecat=st.selectbox('Catégorie du critère',categories,index=categories.index(cr['category']),format_func=lambda x:SERVICE_CRITERION_CATEGORIES[x])
                    elabel=st.text_input('Libellé',value=cr['label']); edesc2=st.text_area('Description du critère',value=cr.get('description') or '',height=90)
                    c1,c2,c3,c4=st.columns(4); ereq=c1.checkbox('Obligatoire',value=bool(cr['required'])); emin=c2.selectbox('Niveau minimal',[0,1,2,3,4],index=int(cr['minimum_level'])); eweight=c3.number_input('Pondération',min_value=0.0,value=float(cr.get('weight') or 0),step=0.1); evalid=c4.number_input('Validité (mois)',min_value=0,step=1,value=int(cr.get('validity_months') or 0))
                    eevidence=st.text_input('Preuves acceptables',value=' ; '.join(current_evidence)); ecactive=st.checkbox('Critère actif',value=bool(cr['active']))
                    sources=['ADAPTATION_CLARTE360','METHODE_PROFESSIONNELLE','REFERENTIEL_RECONNU','SOURCE_SCIENTIFIQUE','AIDE_REFLEXION']; current_source=cr.get('source_kind') or 'ADAPTATION_CLARTE360'
                    esource=st.selectbox('Origine',sources,index=sources.index(current_source) if current_source in sources else 0); esref=st.text_input('Référence / justification',value=cr.get('source_reference') or '')
                    ecreason=st.text_input('Motif de modification du critère',value='Mise à jour administrative'); ecsave=st.form_submit_button('Enregistrer le critère')
                if ecsave:
                    try:
                        ev=[x.strip().upper() for x in eevidence.split(';') if x.strip()]
                        update_service_criterion(ENGINE,cr['id'],{'category':ecat,'label':elabel,'description':edesc2 or None,'required':ereq,'minimum_level':emin,'weight':eweight if eweight>0 else None,'validity_months':evalid or None,'accepted_evidence':ev,'active':ecactive,'source_kind':esource,'source_reference':esref or None},st.session_state.admin_email,ecreason or 'Mise à jour critère')
                        st.success('Critère mis à jour et versionné.');rerun()
                    except ValueError as ex: st.error(str(ex))
                cdel=st.checkbox('Je confirme vouloir supprimer définitivement ce critère',key=f'j15_criterion_delete_confirm_{cr["id"]}')
                if st.button('Supprimer définitivement le critère',key=f'j15_criterion_delete_{cr["id"]}',disabled=not cdel):
                    try: delete_service_criterion(ENGINE,cr['id'],st.session_state.admin_email);st.success('Critère supprimé.');rerun()
                    except ValueError as ex: st.error(str(ex))
            with st.expander('Historique des versions de la prestation'):
                versions=service_versions(ENGINE,svc['id'])
                if versions: st.dataframe(pd.DataFrame([{'Version':x['version_no'],'Date':format_app_datetime(x['created_at']),'Par':x['changed_by'],'Motif':x.get('change_reason') or '','Actif':'Oui' if x['active'] else 'Non'} for x in versions]),use_container_width=True,hide_index=True)
    with sub_alertes:
        st.subheader('Alertes & maintien des qualifications')
        st.caption("Surveillance des échéances du dossier professionnel. Une alerte n'annule jamais automatiquement une qualification humaine : elle signale qu'une vérification ou une décision est nécessaire.")
        c1,c2=st.columns([1,2]); warning=c1.selectbox('Anticipation',[30,60,90,120,180],index=2,format_func=lambda x:f'{x} jours',key='j7_warning_days')
        show_candidates=c2.checkbox('Inclure les candidats',value=True,key='j7_include_candidates')
        alerts=professional_maintenance_alerts(ENGINE,warning_days=warning,include_candidates=show_candidates)
        expired=sum(1 for x in alerts if x['status']=='EXPIRE'); upcoming=sum(1 for x in alerts if x['status']=='A_RENOUVELER')
        m1,m2,m3=st.columns(3);m1.metric('Alertes actives',len(alerts));m2.metric('Échues',expired);m3.metric('À renouveler / revoir',upcoming)
        if alerts:
            st.dataframe(pd.DataFrame([{'État':'Échu' if a['status']=='EXPIRE' else 'À renouveler / revoir','Personne':a['name'],'Statut':a['principal_status'].title(),'Nature':a['kind'].replace('_',' ').title(),'Élément':a['label'],'Échéance':a['due_date'],'Jours':a['days_remaining']} for a in alerts]),use_container_width=True,hide_index=True)
            amap={f"{a['name']} — {a['label']} — {a['due_date']}":a for a in alerts}
            alabel=st.selectbox('Traiter une alerte',list(amap),key='j7_alert_choice'); aa=amap[alabel]
            with st.form('j7_alert_action'):
                act=st.radio('Action',['Marquer comme traitée','Reporter le rappel'],horizontal=True)
                snooze=st.text_input('Rappeler à partir du (AAAA-MM-JJ)',value='',disabled=act!='Reporter le rappel')
                comment=st.text_area('Commentaire / décision prise',height=80)
                go=st.form_submit_button('Enregistrer',type='primary')
            if go:
                try:
                    act_on_professional_maintenance_alert(ENGINE,aa['professional_person_id'],aa['alert_key'],'TRAITE' if act=='Marquer comme traitée' else 'REPORTE',st.session_state.admin_email,comment or None,snooze or None)
                    st.success('Suivi de maintenance enregistré.');rerun()
                except ValueError as ex:st.error(str(ex))
        else:
            st.success("Aucune échéance active dans la période surveillée.")




def settings_screen():
    header('Clarté360 — Paramètres','Administration de l’application')
    tabg,tabo,tabag,tabi,taba,tabdiag=st.tabs(['Général','Organisme','Agences / établissements','Imports','Administrateurs','Diagnostic I9'])
    with tabg:
        st.subheader('Paramètres régionaux et horaires')
        st.caption('Les formats de date/heure changent seulement l’affichage. Les preuves restent UTC et les heures de planning ne sont pas décalées. Les délais des rappels Teams pilotent réellement leur programmation.')
        orgs_reg=list_organizations(ENGINE)
        if orgs_reg:
            labels={f"{o['name']} — #{o['id']}":o for o in orgs_reg}
            selected_reg=st.selectbox('Organisme concerné',list(labels),key='regional_org')
            regional_org=labels[selected_reg]
            current_reg=get_regional_preferences(ENGINE)
            from regional_settings import preferences_from_org,online_reminders_from_org
            current_reg=preferences_from_org(regional_org)
            current_reminders=online_reminders_from_org(regional_org)
            with st.form(f'regional_settings_{regional_org["id"]}'):
                common=['Europe/Paris','Europe/Budapest','Europe/London','UTC','America/New_York']
                known=regional_org.get('timezone') or 'Europe/Paris'
                zone_options=common + (['Autre fuseau IANA…'] if known in common else ['Autre fuseau IANA…'])
                selection=st.selectbox('Fuseau horaire de référence',zone_options,index=common.index(known) if known in common else len(common))
                tz_custom=st.text_input('Fuseau IANA personnalisé',value=known if known not in common else '',disabled=selection!='Autre fuseau IANA…')
                c1,c2=st.columns(2)
                dd=c1.selectbox('Format de la date',['FR','ISO','US'],index=['FR','ISO','US'].index(current_reg['display_date_format']),
                    format_func=lambda k:{'FR':'JJ/MM/AAAA','ISO':'AAAA-MM-JJ','US':'MM/JJ/AAAA'}[k])
                hh=c2.selectbox('Format de l’heure',['24H','12H'],index=['24H','12H'].index(current_reg['display_time_format']),
                    format_func=lambda k:'24 heures' if k=='24H' else '12 heures (AM/PM)')
                language=st.selectbox('Langue de présentation régionale',['fr','en'],
                    index=['fr','en'].index(current_reg['display_language']),
                    format_func=lambda k:'Français' if k=='fr' else 'Anglais (traduction complète non disponible)')
                st.markdown('#### Programmation des rappels – formations en ligne (Teams)')
                st.caption('Délais en minutes avant chaque séance. 120 = 2 heures ; 15 = 15 minutes. Les valeurs sont communes aux séances Teams de cet organisme.')
                c1,c2=st.columns(2)
                first_reminder=c1.number_input('Premier rappel (minutes avant)',min_value=1,max_value=10080,step=1,
                    value=current_reminders['online_reminder_first_minutes'],key=f'online_reminder_first_{regional_org["id"]}')
                second_reminder=c2.number_input('Deuxième rappel (minutes avant)',min_value=1,max_value=10080,step=1,
                    value=current_reminders['online_reminder_second_minutes'],key=f'online_reminder_second_{regional_org["id"]}')
                st.caption('Pour essayer : 5 et 2 minutes, puis remettre manuellement 120 et 15. Aucun retour automatique aux valeurs habituelles.')
                apply_reg=st.form_submit_button('Enregistrer les paramètres régionaux',type='primary')
            if apply_reg:
                try:
                    save_regional_preferences(ENGINE,regional_org['id'],timezone_name=tz_custom if selection=='Autre fuseau IANA…' else selection,
                        date_format=dd,time_format=hh,language=language,actor=st.session_state.admin_email,
                        first_reminder_minutes=first_reminder,second_reminder_minutes=second_reminder)
                    st.success('Paramètres régionaux et rappels Teams enregistrés. Le worker actualise les prochaines échéances.');rerun()
                except ValueError as exc:st.error(str(exc))
            st.caption('Aperçu : '+regional_timestamp('2026-10-10T11:02:00+00:00',current_reg))
            if current_reg['display_language']=='en':
                st.info('Le réglage EN concerne le format régional et le futur raccordement des traductions ; les écrans métier restent actuellement en français.')
        st.write(f"URL publique configurée : `{BASE_URL}`")
        smtp_enabled=bool(mail_cfg().get('enabled'));st.write('Email automatique (secret MAIL) :', '✅ activé' if smtp_enabled else '⚠️ non activé')
        st.markdown(privacy_notice_html(),unsafe_allow_html=True)
        st.caption('Les paramètres sensibles sont stockés dans .streamlit/secrets.toml sur le VPS et ne doivent jamais être envoyés sur GitHub.')
    with tabo:
        st.subheader('Identité des organismes')
        orgs=list_organizations(ENGINE)
        choices={'— Nouvel organisme —':None,**{f"{o['name']} — #{o['id']}":o['id'] for o in orgs}}
        selected=st.selectbox('Organisme à configurer',list(choices),key='organization_manage')
        oid=choices[selected]
        org=get_organization(ENGINE,oid) if oid else {}
        if orgs:
            st.dataframe(pd.DataFrame([{'ID':o['id'],'Nom':o['name'],'Ville':o.get('city'),'SIRET':o.get('siret'),'NDA':o.get('nda'),'Fuseau':o.get('timezone'),'Actif':bool(o.get('active'))} for o in orgs]),use_container_width=True,hide_index=True)
        with st.form(f'organization_settings_{oid or "new"}'):
            c1,c2=st.columns(2); name=c1.text_input('Nom commercial *',value=org.get('name') or ''); legal=c2.text_input('Raison sociale',value=org.get('legal_name') or '')
            address=st.text_input('Adresse du siège',value=org.get('address') or ''); c1,c2,c3=st.columns(3); postal=c1.text_input('Code postal',value=org.get('postal_code') or ''); city=c2.text_input('Ville',value=org.get('city') or ''); country=c3.text_input('Pays',value=org.get('country') or 'France')
            c1,c2,c3,c4=st.columns(4); siret=c1.text_input('SIRET',value=org.get('siret') or ''); rcs=c2.text_input('RCS',value=org.get('rcs') or ''); naf=c3.text_input('NAF',value=org.get('naf') or ''); vat=c4.text_input('TVA / Id CEE',value=org.get('vat_id') or '')
            c1,c2,c3=st.columns(3); nda=c1.text_input('NDA',value=org.get('nda') or ''); website=c2.text_input('Site web',value=org.get('website') or ''); phone=c3.text_input('Téléphone',value=org.get('phone') or '')
            c1,c2=st.columns(2); general_email=c1.text_input('Email général',value=org.get('general_email') or ''); tz=c2.text_input('Fuseau horaire IANA (modifier dans Général)',value=org.get('timezone') or 'Europe/Paris',disabled=True)
            c1,c2=st.columns(2); privacy_contact=c1.text_input('Contact RGPD',value=org.get('privacy_contact') or ''); retention=c2.number_input('Conservation indicative (mois)',min_value=0,step=1,value=int(org.get('retention_months') or 0))
            privacy_notice=st.text_area('Notice RGPD',value=org.get('privacy_notice') or '',height=130)
            c1,c2=st.columns(2); from_name=c1.text_input('Nom affiché expéditeur',value=org.get('email_from_name') or ''); from_address=c2.text_input('Adresse expéditeur (si différente du secret SMTP)',value=org.get('email_from_address') or '')
            active=st.checkbox('Organisme actif',value=bool(org.get('active',1)))
            save_org=st.form_submit_button('Enregistrer l’organisme',type='primary')
        if save_org:
            if not name.strip(): st.error('Nom commercial obligatoire.')
            else:
                try:
                    from zoneinfo import ZoneInfo; ZoneInfo(tz.strip())
                    new_oid=upsert_organization(ENGINE,oid,{'name':name.strip(),'legal_name':legal.strip() or None,'address':address.strip() or None,'postal_code':postal.strip() or None,'city':city.strip() or None,'country':country.strip() or None,'siret':siret.strip() or None,'rcs':rcs.strip() or None,'naf':naf.strip() or None,'vat_id':vat.strip() or None,'nda':nda.strip() or None,'website':website.strip() or None,'general_email':general_email.strip() or None,'phone':phone.strip() or None,'timezone':tz.strip(),'privacy_contact':privacy_contact.strip() or None,'privacy_notice':privacy_notice.strip() or None,'logo_path':org.get('logo_path'),'favicon_path':org.get('favicon_path'),'primary_color':org.get('primary_color'),'secondary_color':org.get('secondary_color'),'email_from_name':from_name.strip() or None,'email_from_address':from_address.strip() or None,'retention_months':int(retention) or None},st.session_state.admin_email)
                    execute(ENGINE,'UPDATE organizations SET active=:a WHERE id=:i',{'a':1 if active else 0,'i':new_oid})
                    st.success('Organisme enregistré.');rerun()
                except ValueError as ex: st.error(str(ex))
                except Exception as ex: _ui_incident('parametres_organisme',ex,subject='L’enregistrement des paramètres')
        if oid:
            with st.expander('Supprimer cet organisme'):
                deps=organization_delete_dependencies(ENGINE,oid)
                if deps:
                    st.info("Cet organisme possède des dépendances métier : la suppression physique est bloquée. Utilisez la case « Organisme actif » pour l'inactiver.")
                    st.caption('Dépendances : '+', '.join(f"{x['kind']}={x['count']}" for x in deps))
                else:
                    st.warning("Suppression physique réservée aux organismes créés par erreur et encore inutilisés. Les agences et profils d'import de configuration associés seront également supprimés.")
                    oconfirm=st.text_input('Saisissez SUPPRIMER',key=f'org_delete_confirm_{oid}')
                    if st.button("Supprimer définitivement l'organisme",key=f'org_delete_{oid}',disabled=oconfirm!='SUPPRIMER'):
                        try: delete_organization_if_unused(ENGINE,oid,st.session_state.admin_email);st.success('Organisme supprimé.');rerun()
                        except ValueError as ex: st.error(str(ex))
    with tabag:
        st.subheader('Agences / établissements')
        org=get_organization(ENGINE)
        if not org: st.warning('Configurez d’abord l’organisme.')
        else:
            agencies=list_agencies(ENGINE,org['id'])
            if agencies: st.dataframe(pd.DataFrame(agencies)[['id','name','city','siret','nda','email','active']],use_container_width=True,hide_index=True)
            with st.expander('Ajouter une agence / un établissement',expanded=not agencies):
                with st.form('add_agency_form'):
                    c1,c2=st.columns(2); aname=c1.text_input('Nom *'); aemail=c2.text_input('Email'); aaddress=st.text_input('Adresse'); c1,c2,c3=st.columns(3); apostal=c1.text_input('Code postal'); acity=c2.text_input('Ville'); acountry=c3.text_input('Pays',value='France'); c1,c2,c3=st.columns(3); asiret=c1.text_input('SIRET'); anda=c2.text_input('NDA'); aphone=c3.text_input('Téléphone'); aadd=st.form_submit_button('Ajouter')
                if aadd:
                    if not aname.strip(): st.error('Nom obligatoire.')
                    else:
                        try: add_agency(ENGINE,org['id'],{'name':aname.strip(),'address':aaddress.strip() or None,'postal_code':apostal.strip() or None,'city':acity.strip() or None,'country':acountry.strip() or None,'siret':asiret.strip() or None,'nda':anda.strip() or None,'email':aemail.strip() or None,'phone':aphone.strip() or None},st.session_state.admin_email);rerun()
                        except ValueError as ex: st.error(str(ex))
            if agencies:
                amap={f"{x['name']} — {x.get('city') or ''}":x for x in agencies}; alab=st.selectbox('Agence à gérer',list(amap),key='agency_manage'); ag=amap[alab]
                with st.form('edit_agency_form'):
                    c1,c2=st.columns(2); ename=c1.text_input('Nom',value=ag['name']); eemail=c2.text_input('Email',value=ag.get('email') or ''); eaddress=st.text_input('Adresse',value=ag.get('address') or ''); c1,c2,c3=st.columns(3); epostal=c1.text_input('Code postal',value=ag.get('postal_code') or ''); ecity=c2.text_input('Ville',value=ag.get('city') or ''); ecountry=c3.text_input('Pays',value=ag.get('country') or ''); c1,c2,c3=st.columns(3); esiret=c1.text_input('SIRET',value=ag.get('siret') or ''); enda=c2.text_input('NDA',value=ag.get('nda') or ''); ephone=c3.text_input('Téléphone',value=ag.get('phone') or ''); eactive=st.checkbox('Agence active',value=bool(ag.get('active'))); esave=st.form_submit_button('Enregistrer les modifications')
                if esave:
                    try: update_agency(ENGINE,ag['id'],{'name':ename.strip(),'address':eaddress.strip() or None,'postal_code':epostal.strip() or None,'city':ecity.strip() or None,'country':ecountry.strip() or None,'siret':esiret.strip() or None,'nda':enda.strip() or None,'email':eemail.strip() or None,'phone':ephone.strip() or None,'active':int(eactive)},st.session_state.admin_email);rerun()
                    except ValueError as ex: st.error(str(ex))
                with st.expander('Supprimer cette agence / cet établissement'):
                    adeps=agency_delete_dependencies(ENGINE,ag['id'])
                    if adeps:
                        st.info("Suppression physique bloquée car cette agence est utilisée. Décochez « Agence active » pour l'archiver fonctionnellement.")
                        st.caption('Dépendances : '+', '.join(f"{x['kind']}={x['count']}" for x in adeps))
                    else:
                        aconfirm=st.text_input('Saisissez SUPPRIMER',key=f'agency_delete_confirm_{ag["id"]}')
                        if st.button("Supprimer définitivement l'agence",key=f'agency_delete_{ag["id"]}',disabled=aconfirm!='SUPPRIMER'):
                            try: delete_agency_if_unused(ENGINE,ag['id'],st.session_state.admin_email);st.success('Agence supprimée.');rerun()
                            except ValueError as ex: st.error(str(ex))
    with tabi:
        st.subheader("Profils d’import par organisme")
        st.caption("La source et son mapping appartiennent à l’organisme. Le cœur de l’application ne dépend plus d’un nom de base Clarté360 ou ADCA.")
        orgs=list_organizations(ENGINE,active_only=True)
        if not orgs:
            st.warning('Configurez d’abord un organisme.')
        else:
            org_map={o['name']:o['id'] for o in orgs}
            ilabel=st.selectbox('Organisme',list(org_map),key='settings_import_org'); ioid=org_map[ilabel]
            profiles=list_import_profiles(ENGINE,ioid)
            if profiles:
                st.dataframe(pd.DataFrame([{'ID':p['id'],'Nom':p['name'],'Code':p['code'],'Clé action':p['action_key'],'Onglet action':p['action_sheet'],'Onglet participants':p['participant_sheet'],'Actif':bool(p['active'])} for p in profiles]),use_container_width=True,hide_index=True)
            edit_opts={'— Nouveau profil —':None,**{f"{p['name']} ({p['code']})":p['id'] for p in profiles}}
            edit_label=st.selectbox('Configurer',list(edit_opts),key='settings_import_profile'); pid=edit_opts[edit_label]
            current=get_import_profile(ENGINE,pid) if pid else {}
            with st.form('import_profile_form'):
                c1,c2=st.columns(2); code=c1.text_input('Code profil *',value=current.get('code') or ''); name=c2.text_input('Nom affiché *',value=current.get('name') or '')
                c1,c2,c3=st.columns(3); action_key=c1.text_input("Colonne clé de l’action *",value=current.get('action_key') or ''); action_sheet=c2.text_input('Onglet action',value=current.get('action_sheet') or 'CONV ADM'); participant_sheet=c3.text_input('Onglet participants',value=current.get('participant_sheet') or 'STAGIAIRE')
                st.caption("Le mapping ci-dessous est optionnel. Sans mapping, les noms de colonnes historiques du moteur sont utilisés. Vous pouvez remplacer uniquement les champs qui diffèrent.")
                mapping=st.text_area('Mapping JSON',value=current.get('mapping_json') or '{}',height=180,help='Exemple : {"title":["INTITULE"],"participant_email":["MAIL"]}')
                active=st.checkbox('Profil actif',value=bool(current.get('active',1)))
                savep=st.form_submit_button('Enregistrer le profil',type='primary')
            if savep:
                try:
                    new_id=save_import_profile(ENGINE,pid,ioid,{'code':code,'name':name,'source_type':'EXCEL','action_key':action_key,'action_sheet':action_sheet,'participant_sheet':participant_sheet,'mapping_json':mapping,'config_json':current.get('config_json') or '{}','active':active},st.session_state.admin_email)
                    st.success('Profil enregistré.'); rerun()
                except Exception as ex: _ui_incident('operation_interface',ex)
            if pid:
                store_key=f'PROFILE_{pid}'; info=source_info(store_key)
                st.markdown('#### Source mémorisée pour ce profil')
                st.write(info.get('snapshot_path') or 'Aucune copie de travail mémorisée.')
                with st.form(f'import_path_{pid}'):
                    path=st.text_input('Chemin source sur le VPS / volume monté (optionnel)',value=info.get('external_path') or '')
                    savepath=st.form_submit_button('Enregistrer le chemin')
                if savepath:
                    set_external_path(store_key,path); st.success('Chemin enregistré.')
                st.caption("Un chemin Windows local (C:\\...) n’est pas accessible directement depuis le VPS. Utilisez alors le chargement de fichier dans l’écran Importer une action.")
                if st.button('Actualiser la copie depuis le chemin serveur',disabled=not bool(info.get('external_path')),key=f'refresh_profile_{pid}'):
                    try: refresh_from_external(store_key); st.success('Copie de travail actualisée.')
                    except Exception as ex: _ui_incident('operation_interface',ex)
                with st.expander("Supprimer ce profil d'import"):
                    st.caption("La suppression retire uniquement la configuration du profil dans l'application ; elle ne supprime jamais le fichier source externe.")
                    pconfirm=st.text_input('Saisissez SUPPRIMER',key=f'import_profile_delete_confirm_{pid}')
                    if st.button("Supprimer définitivement ce profil d'import",key=f'import_profile_delete_{pid}',disabled=pconfirm!='SUPPRIMER'):
                        try: delete_import_profile(ENGINE,pid,st.session_state.admin_email);st.success("Profil d'import supprimé.");rerun()
                        except ValueError as ex: st.error(str(ex))

    with taba:
        st.subheader('Administrateurs autorisés')
        admins=q(ENGINE,'SELECT id,email,full_name,active,role,created_at FROM admins ORDER BY id')
        st.dataframe(pd.DataFrame(admins),use_container_width=True,hide_index=True)
        with st.expander('Changer mon mot de passe'):
            with st.form('change_my_pw'):
                oldpw=st.text_input('Mot de passe actuel',type='password');np1=st.text_input('Nouveau mot de passe',type='password');np2=st.text_input('Confirmer le nouveau mot de passe',type='password');cpw=st.form_submit_button('Changer mon mot de passe')
            if cpw:
                if not admin_password_ok(ENGINE,st.session_state.admin_email,oldpw): st.error('Mot de passe actuel incorrect.')
                elif len(np1)<10 or np1!=np2: st.error('Le nouveau mot de passe doit comporter au moins 10 caractères et les deux saisies doivent être identiques.')
                else: execute(ENGINE,'UPDATE admins SET password_hash=:p WHERE email=:e',{'p':hash_password(np1),'e':st.session_state.admin_email});audit(ENGINE,'ADMIN_PASSWORD_CHANGED',actor=st.session_state.admin_email,entity_type='admin',details={});revoke_subject_sessions(ENGINE,'ADMIN',st.session_state.admin_email);st.success('Mot de passe modifié. Reconnectez-vous pour poursuivre.');_logout_persistent('ADMIN',['admin_email','admin_name','nav'])
        with st.expander('Ajouter un administrateur'):
            with st.form('add_admin'):
                n=st.text_input('Nom et prénom');e=st.text_input('Email').strip().lower();p1=st.text_input('Mot de passe initial',type='password');p2=st.text_input('Confirmer',type='password');add=st.form_submit_button('Créer administrateur')
            if add:
                try:
                    e=validate_email(e,'E-mail administrateur',required=True)
                    n=validate_full_name(n,'Nom et prénom',required=False) or ''
                except ValueError as ex:
                    st.error(str(ex)); e=None
                if e:
                    if len(p1)<10 or p1!=p2: st.error('Mot de passe d’au moins 10 caractères et confirmation identique requis.')
                    elif one(ENGINE,'SELECT id FROM admins WHERE email=:e',{'e':e}): st.error('Cet email existe déjà.')
                    else: execute(ENGINE,"INSERT INTO admins(email,password_hash,full_name,active,role,created_at) VALUES(:e,:p,:n,1,'ADMIN',:c)",{'e':e,'p':hash_password(p1),'n':n.strip() or None,'c':utcnow_iso()});audit(ENGINE,'ADMIN_CREATED',actor=st.session_state.admin_email,entity_type='admin',details={'email':e});st.success('Administrateur créé.');rerun()
        others=[x for x in admins if x['email']!=st.session_state.admin_email]
        if others:
            st.markdown('**Activer / désactiver / supprimer**')
            amap={f"{x.get('full_name') or x['email']} — {x['email']}":x for x in others};al=st.selectbox('Administrateur',list(amap),key='adm_manage');aa=amap[al]
            c1,c2=st.columns(2)
            if c1.button('Désactiver' if aa['active'] else 'Réactiver',key='adm_toggle'):
                execute(ENGINE,'UPDATE admins SET active=:x WHERE id=:i',{'x':0 if aa['active'] else 1,'i':aa['id']});audit(ENGINE,'ADMIN_STATUS_CHANGED',actor=st.session_state.admin_email,entity_type='admin',entity_id=aa['id'],details={'active':not bool(aa['active'])});rerun()
            with c2.expander('🗑️ Supprimer'):
                pw=st.text_input('Votre mot de passe',type='password',key='admdelpw');conf=st.text_input('Saisissez SUPPRIMER',key='admdelconf')
                if st.button('Supprimer cet administrateur',key='admdel'):
                    if conf!='SUPPRIMER' or not admin_password_ok(ENGINE,st.session_state.admin_email,pw): st.error('Confirmation ou mot de passe incorrect.')
                    else: execute(ENGINE,'DELETE FROM admins WHERE id=:i',{'i':aa['id']});audit(ENGINE,'ADMIN_PURGED',actor=st.session_state.admin_email,entity_type='admin',entity_id=aa['id'],details={'email':aa['email']});rerun()
    with tabdiag:
        st.subheader('Diagnostic de préparation I9')
        st.caption('Contrôle en lecture seule. Aucune valeur de secret, identifiant Graph ou détail technique sensible n’est affiché.')
        try:
            sec=dict(st.secrets)
        except Exception:
            sec={}
        diag=runtime_readiness(ENGINE,base_url=BASE_URL,mail_config=mail_cfg(),secrets=sec,project_root=Path(__file__).resolve().parent)
        if diag['ready']:
            st.success(f"Socle prêt pour la recette technique — {diag['ok_count']}/{diag['total_count']} contrôles au vert.")
        else:
            st.error('Un ou plusieurs contrôles bloquants doivent être corrigés avant déploiement.')
        st.dataframe(pd.DataFrame([{'Contrôle':c['name'],'État':c['status'],'Information':c['message']} for c in diag['checks']]),use_container_width=True,hide_index=True)
        st.info('Les connecteurs externes peuvent rester « à vérifier » tant que leur recette réelle n’a pas été effectuée. Cela ne bloque pas les autres modules.')
    footer()

def tool_launch_page(token):
    header('Clarté360 — Outil prescrit','Accès sécurisé')
    ctx=resolve_prescription_launch_token(ENGINE,token,'beneficiary-launch')
    if not ctx:
        st.error('Ce lien de lancement est invalide, expiré ou déjà utilisé. Retournez dans votre espace bénéficiaire pour générer un nouvel accès.')
        st.link_button('RETOUR À MON ESPACE',f"{BASE_URL.rstrip('/')}?beneficiary_portal=1")
        footer(); return
    st.success(f"Outil prescrit : {ctx['tool_name']}")
    st.caption(f"Prescription {ctx['prescription_id']} · Statut : {ctx['status'].replace('_',' ')}")
    if ctx.get('launch_type')=='HUB_REDIRECT' and ctx.get('base_url'):
        st.info("L'accès a été validé par le Hub Clarté360. Vous pouvez maintenant ouvrir l'outil.")
        st.link_button("OUVRIR L'OUTIL",ctx['base_url'],type='primary')
    elif ctx.get('launch_type')=='EXTERNAL_SIGNED':
        if ctx.get('tool_code')=='PIP_RIASEC_ONET':
            try:
                key=secret('pip_connector','launch_signing_key','')
                url=build_pip_prescription_launch(ENGINE,ctx['prescription_id'],key,valid_seconds=900)
                st.info("Votre accès sécurisé Clarté360 au PIP RIASEC / O*NET est prêt.")
                st.link_button("OUVRIR LE PIP RIASEC / O*NET",url,type='primary')
            except Exception as ex:
                _ui_incident('pip_prescription_launch',ex,action_id=ctx.get('action_id'),entity_type='tool_prescription',entity_id=ctx.get('prescription_id'),subject='Le lancement PIP est temporairement indisponible',level='warning')
        elif ctx.get('tool_code')=='IPIP_NEO120':
            try:
                key=secret('IPIP_CONNECTOR','LAUNCH_SIGNING_KEY','')
                url=build_ipip_prescription_launch(ENGINE,ctx['prescription_id'],key,valid_seconds=900)
                st.info("Votre accès sécurisé Clarté360 au profil de fonctionnement professionnel est prêt.")
                st.link_button("OUVRIR LE PROFIL DE FONCTIONNEMENT",url,type='primary')
            except Exception as ex:
                _ui_incident('ipip_prescription_launch',ex,action_id=ctx.get('action_id'),entity_type='tool_prescription',entity_id=ctx.get('prescription_id'),subject='Le lancement IPIP est temporairement indisponible',level='warning')
        elif ctx.get('base_url'):
            # Les autres applications Clarté360 restent autonomes : Gestion des Actions
            # autorise la prescription et le passage depuis l'espace bénéficiaire, puis
            # laisse l'application utiliser son propre mécanisme d'identification,
            # de sauvegarde et de reprise. Aucun secret Hub n'est requis ici.
            st.info("Prescription validée par Clarté360. L’outil s’ouvre ensuite avec son propre système d’accès et de sauvegarde.")
            st.link_button(f"OUVRIR {ctx.get('tool_name') or 'L’OUTIL'}",ctx['base_url'],type='primary')
        else:
            st.warning("L’URL de cet outil n’est pas configurée.")
    elif ctx.get('base_url'):
        st.link_button("OUVRIR L'OUTIL",ctx['base_url'],type='primary')
    else:
        st.warning("Le contrat de lancement de cet outil n'est pas encore configuré.")
    footer()

# P4 - Espace Client / DRH. Les autorisations sont revérifiées par les services
# pour chaque requête. La navigation seule ne confère aucun droit.
def client_invitation_page(token):
    header('Clarté360 — Activer mon Espace Client', 'Invitation personnelle et limitée dans le temps')
    with st.form('client_invite_activate'):
        p1=st.text_input('Choisir un mot de passe (12 caractères minimum)',type='password')
        p2=st.text_input('Confirmer le mot de passe',type='password')
        ok=st.form_submit_button('ACTIVER MON ESPACE',type='primary')
    if ok:
        if p1!=p2:
            st.error('Les mots de passe ne correspondent pas.')
        else:
            try:
                redeem_client_access_token(ENGINE,token,p1)
                st.success('Accès activé. Connectez-vous avec votre e-mail professionnel.')
                st.link_button('OUVRIR MON ESPACE CLIENT',f"{BASE_URL.rstrip('/')}?client_portal=1")
            except (ValueError,PermissionError) as ex:
                st.error(str(ex))
    footer()


def client_portal_page():
    _restore_client_session()
    if not st.session_state.get('client_portal_id'):
        header('Clarté360 — Espace Client / DRH','Accès réservé aux contacts expressément habilités')
        with st.form('client_portal_login'):
            email=st.text_input('E-mail').strip().lower()
            password=st.text_input('Mot de passe',type='password')
            submitted=st.form_submit_button('SE CONNECTER',type='primary')
        if submitted:
            acc=verify_client_login(ENGINE,email,password)
            if acc:
                st.session_state.client_portal_id=acc['id']
                _issue_persistent_session('CLIENT',acc['id'],'client_portal')
            else: st.error('Identifiants incorrects ou accès non activé.')
        st.caption('Première connexion ou mot de passe oublié : demandez un lien personnel à votre interlocuteur Clarté360.')
        footer();return
    account_id=st.session_state.client_portal_id
    try:identity=client_portal_identity(ENGINE,account_id)
    except PermissionError:
        _logout_persistent('CLIENT',['client_portal_id','p4_client_action_id','p3_screen_client']);return
    header('Clarté360 — Espace Client / DRH', f"Bienvenue {identity['first_name']} {identity['last_name']}")
    _j4_notification_drawer('CLIENT',account_id)
    c1,c2=st.columns([4,1])
    c1.caption('Suivi des seules actions pour lesquelles votre accès a été explicitement autorisé.')
    if c2.button('Se déconnecter',key='client_logout',use_container_width=True):
        _logout_persistent('CLIENT',['client_portal_id','p4_client_action_id','p3_screen_client'])
    acts=list_client_actions(ENGINE,account_id)
    allowed={int(a['id']):a for a in acts}
    if '_j7_client_open_action' in st.session_state:
        wanted=st.session_state.pop('_j7_client_open_action')
        authorized=authorized_action_choice(allowed,wanted)
        if authorized is not None:
            st.session_state['p4_client_action_id']=authorized
            st.session_state[f'p3_screen_client_{authorized}']='actions'
    candidate=authorized_action_choice(allowed,st.session_state.get('p4_client_action_id'))
    if st.session_state.get('p4_client_action_id')!=candidate:
        st.session_state['p4_client_action_id']=candidate
    st.sidebar.markdown('#### Dossiers autorisés')
    selected_action_id=st.sidebar.selectbox('Action à consulter',[None]+list(allowed),key='p4_client_action_id',
        format_func=lambda x:'Toutes mes actions' if x is None else f"{allowed[x]['action_no']} — {allowed[x]['title']}")
    section=_p3_sidebar_section('CLIENT',action_id=selected_action_id,
        action_no=allowed[selected_action_id]['action_no'] if selected_action_id else None)
    if section=='home':
        st.markdown('#### Mon tableau de bord Client / DRH')
        dashboard=client_dashboard(ENGINE,account_id)
        d1,d2,d3=st.columns(3)
        d1.metric('Actions autorisées',len(dashboard['actions']))
        d2.metric('Actions en cours',dashboard['active_actions'])
        d3.metric('Documents explicitement partagés',dashboard['shared_documents'])
        st.markdown('##### Mes prestations')
        st.caption('Vue de restitution en lecture seule ; les habilitations se gèrent uniquement par l’administrateur.')
        if acts:
            st.dataframe(pd.DataFrame([{'Référence':a['action_no'],'Prestation':a['title'],
                'Statut':a['status'],'Période':f"{a.get('start_date') or '—'} / {a.get('end_date') or '—'}",
                'Rôle':a['role']} for a in dashboard['actions']]),use_container_width=True,hide_index=True)
            st.markdown('##### Ouvrir un dossier autorisé')
            for action in dashboard['actions']:
                left,right=st.columns([5,1]);left.write(f"**{action['action_no']} — {action['title']}**")
                if right.button('Ouvrir',key=f"j7_client_open_{action['id']}"):
                    st.session_state['_j7_client_open_action']=action['id'];rerun()
            if dashboard['collective_sessions']:
                st.markdown('##### Prochains créneaux collectifs communicables')
                st.dataframe(pd.DataFrame(dashboard['collective_sessions']),use_container_width=True,hide_index=True)
        else:st.info('Aucune action ne vous est actuellement attribuée.')
        st.caption('Votre tableau ne donne jamais accès aux résultats individuels, réponses BC, scores ou documents non habilités.')
    if section=='profile':
        st.markdown('#### Mon identité de contact')
        st.write(f"**{identity['first_name']} {identity['last_name']}**")
        st.write(f"**E-mail :** {identity['email']}")
        st.write(f"**Organisation renseignée dans le CRM :** {identity.get('company') or '—'}")
        st.caption('Une modification de ces données s’effectue auprès de Clarté360, dans le module CRM de référence.')
    if section=='actions':
        if selected_action_id is None:
            st.info('Choisissez une action dans le menu vertical pour voir ses informations.')
        else:
            a=client_action_summary(ENGINE,account_id,selected_action_id)
            st.write(f"**{a['action_no']} — {a['title']}**")
            st.write(f"**Statut :** {a.get('status') or '—'} · **Période :** {a.get('start_date') or '—'} au {a.get('end_date') or '—'}")
            st.write(f"**Rôle habilité :** {a['role'].replace('_',' ')}")
            if a.get('collective_training'):
                d1,d2=st.columns(2);d1.metric('Inscrits (collectif)',a['participants_count']);d2.metric('Créneaux planifiés',a['sessions_count'])
            else:st.caption('Les données individuelles de parcours et de bilan ne sont pas accessibles ici.')
    if section=='planning':
        if selected_action_id is None:st.info('Sélectionnez une action.')
        else:
            slots=client_public_schedule(ENGINE,account_id,selected_action_id)
            # Tableau de restitution en lecture seule; accès et édition par commandes métiers dédiées.
            if slots:st.dataframe(pd.DataFrame([{'Date':format_app_date(x['slot_date']),'Début':format_app_time(x['start_time']),'Fin':format_app_time(x['end_time'])} for x in slots]),use_container_width=True,hide_index=True)
            else:st.info('Aucun calendrier collectif communicable pour cette action.')
    if section=='documents':
        if selected_action_id is None:st.info('Sélectionnez une action.')
        else:
            scope=client_action_summary(ENGINE,account_id,selected_action_id)
            if scope['can_download']:
                docs=list_client_documents(ENGINE,account_id,selected_action_id)
                if not docs:st.info('Aucun document validé, publié et partagé avec votre compte.')
                for doc in docs:
                    a,b=st.columns([4,1]);a.write(f"{doc['display_name']} · v{doc.get('version_no') or 1}")
                    data=read_client_document(ENGINE,doc['id'],account_id,selected_action_id)
                    b.download_button('TÉLÉCHARGER',data,file_name=doc['display_name'],key=f'cl_doc_{doc["id"]}',use_container_width=True)
            else:st.caption('La consultation des documents n’est pas autorisée pour ce dossier.')
            if scope['can_upload']:
                st.markdown('#### Transmettre une pièce à Clarté360')
                st.caption('Les pièces déposées restent internes jusqu’à leur revue et ne sont jamais diffusées aux bénéficiaires.')
                file=st.file_uploader('Choisir un document (10 Mo maximum)',type=['pdf','docx','xlsx','txt','csv','png','jpg','jpeg'],key=f'client_upload_{selected_action_id}')
                if st.button('TRANSMETTRE LE DOCUMENT',disabled=file is None,key=f'client_upload_submit_{selected_action_id}'):
                    try:
                        client_upload_document(ENGINE,account_id,selected_action_id,file.getvalue(),file.name)
                        st.success('Pièce reçue et classée comme brouillon administratif.');rerun()
                    except (ValueError,PermissionError) as ex:st.error(str(ex))
                submitted=list_client_submissions(ENGINE,account_id,selected_action_id)
                if submitted:
                    st.markdown('##### Mes pièces transmises')
                    # Tableau de restitution en lecture seule; accès et édition par commandes métiers dédiées.
                    st.dataframe(pd.DataFrame([{'Document':r['display_name'],'Date':format_app_datetime(r['created_at']),
                        'Traitement':'Reçu / en revue' if r['validation_status']=='A_VERIFIER' else 'Vérifié'} for r in submitted]),use_container_width=True,hide_index=True)
    if section=='quality':
        if selected_action_id is None:st.info('Sélectionnez une action.')
        else:
            summary=client_action_summary(ENGINE,account_id,selected_action_id)
            st.write(f"**Suivi administratif :** {summary.get('status') or '—'}")
            st.info('Seules les informations de suivi autorisées sont accessibles. Les réponses aux questionnaires, avis individuels, notes et résultats personnels restent confidentiels.')
    if section=='contact':
        st.write('Pour toute question administrative concernant une action, contactez votre interlocuteur Clarté360.')
        st.link_button('CONTACTER CLARTÉ360','mailto:contact@clarte360.com')
    if section=='archives':
        if selected_action_id is None:st.info('Sélectionnez une action pour télécharger son dossier autorisé.')
        else:
            summary=client_action_summary(ENGINE,account_id,selected_action_id)
            if summary['can_download']:
                buf=export_client_action_zip(ENGINE,account_id,selected_action_id)
                st.download_button('TÉLÉCHARGER LES JUSTIFICATIFS AUTORISÉS (ZIP)',buf,
                    file_name=f"{summary['action_no']}_justificatifs_clarte360.zip",mime='application/zip',key=f'client_zip_{selected_action_id}')
            else:st.info('Aucun export documentaire autorisé pour ce dossier.')
    footer(selected_action_id)


def admin_client_portal_screen():
    _admin_actor=st.session_state.get('admin_email')
    header('Clarté360 — Gestion des accès Client / DRH', 'Comptes rattachés au CRM existant et habilitations par action')
    st.info('Le CRM existant reste le référentiel transitoire. Aucun droit Client n’est accordé automatiquement par une liaison CRM.')
    st.sidebar.markdown('#### Gestion Espace Client')
    section=st.sidebar.radio('Administration Client',['Comptes et invitations','Habilitations par action','Justificatifs Client','Contrôles'],key='p4_admin_client_section')
    accounts=list_client_accounts_admin(ENGINE,_admin_actor)
    if section=='Comptes et invitations':
        st.markdown('#### Comptes rattachés à des contacts CRM')
        if accounts:
            # Tableau de restitution en lecture seule; accès et édition par commandes métiers dédiées.
            st.dataframe(pd.DataFrame([{'Compte':x['id'],'Contact CRM':x['public_id'],
                'Nom':f"{x['first_name']} {x['last_name']}",'E-mail':x['email'],
                'Actif':bool(x['active']),'Accès activé':bool(x['activated'])} for x in accounts]),use_container_width=True,hide_index=True)
        with st.form('client_add_account'):
            term=st.text_input('Rechercher un contact CRM (nom, société, e-mail)')
            search=st.form_submit_button('RECHERCHER')
        if search:st.session_state['p4_crm_term']=term
        contacts=find_crm_contacts(ENGINE,st.session_state.get('p4_crm_term') or '',100)
        if contacts:
            opts={f"{x['public_id']} — {x['first_name']} {x['last_name']} · {x['email']}":x for x in contacts}
            chosen=st.selectbox('Contact existant',list(opts),key='p4_contact_for_account')
            if st.button('CRÉER / RETROUVER LE COMPTE',key='p4_account_add'):
                try:create_client_portal_account(ENGINE,opts[chosen]['id'],_admin_actor);st.success('Compte prêt pour une attribution explicite.');rerun()
                except (ValueError,PermissionError) as ex:st.error(str(ex))
        if accounts:
            aid_map={f"#{x['id']} — {x['first_name']} {x['last_name']} · {x['email']}":x for x in accounts}
            al=st.selectbox('Compte à administrer',list(aid_map),key='p4_account_manage');acc=aid_map[al]
            left,right=st.columns(2)
            if left.button('ÉMETTRE UN LIEN D’ACTIVATION / RÉINITIALISATION',key='p4_make_invite'):
                try:
                    kind='RESET' if acc['activated'] else 'INVITE'
                    raw=issue_client_access_token(ENGINE,acc['id'],_admin_actor,kind=kind)
                    st.session_state['p4_generated_invite']={'account_id':acc['id'],'url':f"{BASE_URL.rstrip('/')}?client_invite={quote(raw)}"}
                except (ValueError,PermissionError) as ex:st.error(str(ex))
            if right.button('DÉSACTIVER' if acc['active'] else 'RÉACTIVER',key='p4_toggle_account'):
                set_client_account_active(ENGINE,acc['id'],not bool(acc['active']),_admin_actor);rerun()
            crm_contact=one(ENGINE,'SELECT email FROM crm_contacts WHERE id=:i',{'i':acc['crm_contact_id']})
            if crm_contact and str(crm_contact['email']).strip().lower()!=str(acc['email']).strip().lower():
                st.warning('E-mail modifié dans le CRM : l’accès reste suspendu jusqu’au nouvel accord de droits.')
                if st.button('METTRE A JOUR L’E-MAIL ET REVOQUER LES ANCIENS DROITS',key='p4_reconcile_email'):
                    try:
                        reconcile_client_contact_email(ENGINE,acc['id'],_admin_actor)
                        st.session_state.pop('p4_generated_invite',None)
                        st.success('E-mail mis à jour. Émettez une nouvelle invitation et attribuez les nouveaux droits.');rerun()
                    except (ValueError,PermissionError) as ex:st.error(str(ex))
            if st.session_state.get('p4_generated_invite',{}).get('account_id')==acc['id']:
                st.warning('Lien à usage unique : ne le transmettre qu’au contact destinataire par un canal approprié. Il ne sera pas enregistré dans le CRM ni envoyé automatiquement.')
                st.code(st.session_state['p4_generated_invite']['url'],language='text')
                if st.button('MASQUER LE LIEN',key='p4_hide_invite'):st.session_state.pop('p4_generated_invite',None);rerun()
    if section=='Habilitations par action':
        if not accounts:st.info('Créez d’abord un compte Client lié au CRM.')
        else:
            actions=search_actions(ENGINE,'',include_archived=False)
            if not actions:st.info('Aucune action à habiliter.')
            else:
                choices={f"{x['action_no']} — {x['title']}":x for x in actions}
                focus_id=st.session_state.pop('p4_access_action_id',None)
                if focus_id is not None:
                    match=next((label for label,row in choices.items() if int(row['id'])==int(focus_id)),None)
                    if match:st.session_state['p4_access_action']=match
                selected=st.selectbox('Action / dossier',list(choices),key='p4_access_action');a=choices[selected]
                acct={f"#{x['id']} · {x['email']} ({x['company'] or 'Particulier'})":x for x in accounts if x['active']}
                if acct:
                    with st.form('client_grant_form'):
                        ac=st.selectbox('Compte à habiliter',list(acct));role=st.selectbox('Rôle sur ce dossier',['CLIENT_ADMIN','PRESCRIPTEUR'])
                        can_down=st.checkbox('Peut télécharger les justificatifs explicitement partagés',value=False)
                        can_up=st.checkbox('Peut déposer des documents administratifs',value=False)
                        apply=st.form_submit_button('VALIDER CETTE HABILITATION',type='primary')
                    if apply:
                        try:
                            grant_client_action(ENGINE,acct[ac]['id'],a['id'],_admin_actor,role,
                                                can_download=can_down,can_upload=can_up)
                            st.success('Habilitation enregistrée et journalisée.');rerun()
                        except (ValueError,PermissionError) as ex:st.error(str(ex))
                grants=list_admin_client_grants(ENGINE,_admin_actor,a['id'])
                for g in grants:
                    c1,c2=st.columns([4,1])
                    c1.write(f"#{g['account_id']} · {g['email']} · {g['role']} · Télécharger : {'oui' if g['can_download'] else 'non'} · Déposer : {'oui' if g['can_upload'] else 'non'}")
                    if g['revoked_at']:c2.caption('Révoqué')
                    elif c2.button('RÉVOQUER',key=f'p4_revoke_{g["account_id"]}_{a["id"]}'):
                        revoke_client_action(ENGINE,g['account_id'],a['id'],_admin_actor);rerun()
    if section=='Justificatifs Client':
        acts=search_actions(ENGINE,'',include_archived=False)
        if not acts:st.info('Aucune action disponible.')
        else:
            opts={f"{x['action_no']} — {x['title']}":x for x in acts}
            label=st.selectbox('Action',list(opts),key='p4_docs_action');a=opts[label]
            st.caption('Les pièces nominatives, les contrats/factures CRM et les réponses individuelles ne peuvent pas être partagés par cet espace.')
            with st.form(f'client_document_upload_{a["id"]}'):
                typ=st.selectbox('Nature du justificatif',sorted(DOC_SHAREABLE_CATEGORIES))
                uploaded=st.file_uploader('Pièce justificative pour le client',type=['pdf','docx','xlsx','txt','csv','png','jpg','jpeg'])
                confirmation=st.checkbox('Je confirme que cette pièce ne contient aucune donnée personnelle individuelle de bénéficiaire et peut être remise au client.',value=False)
                save=st.form_submit_button('ENREGISTRER EN BROUILLON')
            if save:
                if not uploaded:st.error('Sélectionnez d’abord un document.')
                elif not confirmation:st.error('Vérification humaine de confidentialité obligatoire avant ce dépôt.')
                else:
                    try:
                        create_client_delivery(ENGINE,a['id'],uploaded.getvalue(),uploaded.name,_admin_actor,typ)
                        st.success('Brouillon enregistré. Il n’est visible par aucun client.');rerun()
                    except (ValueError,PermissionError) as ex:st.error(str(ex))
            raw=list_action_documents(ENGINE,a['id'],include_deleted=True)
            docs=[x for x in raw if str(x.get('audience'))=='CLIENT_ONLY']
            for d in docs:
                st.markdown(f"**{d['display_name']}** · {d['category']} · {d.get('validation_status') or '—'} / {d.get('publication_status') or '—'}")
                if d.get('deleted_at'):st.caption('Référence archivée — accès documentaire suspendu.')
                if d.get('superseded_at') and d.get('publication_status')!='PUBLIE':st.caption('Ancienne version ; conserver la visibilité historique uniquement pour les destinataires déjà autorisés.')
                c1,c2,c3=st.columns(3)
                if c1.button('VALIDER',key=f'client_validate_{d["id"]}',disabled=bool(d.get('deleted_at') or d.get('superseded_at') or d.get('validation_status')=='FINALISE')):
                    try:set_document_validation(ENGINE,d['id'],'VALIDE',_admin_actor);rerun()
                    except (ValueError,PermissionError) as ex:st.error(str(ex))
                if c2.button('PUBLIER',key=f'client_publish_{d["id"]}',disabled=bool(d.get('deleted_at') or d.get('superseded_at') or d.get('category') not in DOC_SHAREABLE_CATEGORIES or d.get('validation_status') not in ('VALIDE','FINALISE'))):
                    try:set_document_publication(ENGINE,d['id'],True,_admin_actor);rerun()
                    except (ValueError,PermissionError) as ex:st.error(str(ex))
                if c3.button('ARCHIVER',key=f'client_archive_{d["id"]}',disabled=bool(d.get('deleted_at'))):
                    delete_document_reference(ENGINE,d['id'],_admin_actor);rerun()
                recipients=[g for g in list_admin_client_grants(ENGINE,_admin_actor,a['id']) if not g['revoked_at'] and g['can_download']]
                if recipients and not d.get('deleted_at') and not d.get('superseded_at') and d['publication_status']=='PUBLIE' and d['validation_status'] in ('VALIDE','FINALISE') and d['category'] in DOC_SHAREABLE_CATEGORIES:
                    rmap={f"#{g['account_id']} · {g['email']}":g for g in recipients}
                    target=st.selectbox('Destinataire explicite',list(rmap),key=f'p4_share_recipient_{d["id"]}')
                    if st.button('PARTAGER AVEC CE COMPTE',key=f'p4_share_doc_{d["id"]}'):
                        try:share_client_document(ENGINE,d['id'],rmap[target]['account_id'],_admin_actor);st.success('Partage individuel enregistré.');rerun()
                        except (ValueError,PermissionError) as ex:st.error(str(ex))
                for share in list_admin_client_document_shares(ENGINE,d['id'],_admin_actor):
                    col_left,col_right=st.columns([4,1])
                    col_left.caption(f"#{share['account_id']} · {share['email']} · " + ('Accès révoqué' if share['revoked_at'] else 'Document remis'))
                    if not share['revoked_at'] and col_right.button('RÉVOQUER CETTE REMISE',key=f'p4_revoke_share_{d["id"]}_{share["account_id"]}'):
                        revoke_client_document(ENGINE,d['id'],share['account_id'],_admin_actor);rerun()
    if section=='Contrôles':
        st.markdown('#### Périmètre de confidentialité')
        st.write('**CRM maître :** Gestion Clients n°17 (CRM0 transitoire, sans seconde base de contacts).')
        st.write('**Droits :** attribution et révocation individuelles par action.')
        st.write('**Documents :** validations, publications et partages indépendants.')
        st.write('**Bilan de compétences :** aucune restitution personnelle au donneur d’ordre dans P4.')
        st.write('**Contractualisation/factures :** à ouvrir depuis Gestion Clients n°17 une fois son interface opérationnelle.')
        st.caption('GO-14 Compétences & Projets reste suspendu. Aucun lancement dédié n’est créé en P4.')
    footer()


# ROUTING PUBLIC SIGNATURE
params=st.query_params
if params.get('tool_launch'):
    _run_ui_module('tool_launch',lambda: tool_launch_page(params.get('tool_launch')));st.stop()
if params.get('client_invite'):
    _run_ui_module('client_invitation',lambda: client_invitation_page(params.get('client_invite')));st.stop()
if params.get('client_portal'):
    _run_ui_module('client_portal',client_portal_page);st.stop()
if 'beneficiary_invite' in params:
    token=params.get('beneficiary_invite')
    if token: _run_ui_module('beneficiary_invitation',lambda: beneficiary_invitation_page(token))
    else: _run_ui_module('beneficiary_portal',beneficiary_portal_page)
    st.stop()
if params.get('beneficiary_reset_request'):
    _run_ui_module('beneficiary_reset_request',beneficiary_reset_request_page);st.stop()
if params.get('beneficiary_reset'):
    _run_ui_module('beneficiary_reset',lambda: beneficiary_reset_page(params.get('beneficiary_reset')));st.stop()
if params.get('beneficiary_portal'):
    _run_ui_module('beneficiary_portal',beneficiary_portal_page);st.stop()
if params.get('quality_token'):
    _run_ui_module('quality_public',lambda: quality_page(params.get('quality_token')));st.stop()
if params.get('trainer_invite'):
    _run_ui_module('trainer_invitation',lambda: trainer_invitation_page(params.get('trainer_invite')));st.stop()
if params.get('trainer_reset_request'):
    _run_ui_module('trainer_reset_request',trainer_reset_request_page);st.stop()
if params.get('trainer_reset'):
    _run_ui_module('trainer_reset',lambda: trainer_reset_page(params.get('trainer_reset')));st.stop()
if params.get('trainer_portal'):
    _run_ui_module('trainer_portal',trainer_portal_page);st.stop()
if params.get('trainer_token'):
    _run_ui_module('trainer_restricted',lambda: trainer_page(params.get('trainer_token')));st.stop()
if params.get('token'):
    _run_ui_module('signature_email',lambda: signature_page(token=params.get('token')));st.stop()
if params.get('slot_token'):
    _run_ui_module('signature_qr',lambda: signature_page(slot_token=params.get('slot_token')));st.stop()

if not setup_or_login(): st.stop()
if '_next_nav' in st.session_state:
    next_route=st.session_state.pop('_next_nav')
    st.session_state['admin_workspace']=workspace_for_route(next_route)
    st.session_state['nav']=next_route
    if next_route=='Actions':
        next_view=st.session_state.pop('_next_action_view',None)
        if next_view in ('detail','list'):
            st.session_state['admin_actions_view']=next_view
        else:
            requested=st.session_state.get('p3_admin_action_id') or st.session_state.get('selected_action')
            authorized=authorized_action_choice([x['id'] for x in q(ENGINE,'SELECT id FROM actions')],requested)
            if authorized is not None:
                st.session_state['p3_admin_action_id']=authorized
            st.session_state['admin_actions_view']='detail' if authorized is not None else 'list'
page=sidebar()
if page=='__home__': _run_ui_module('administration_accueil',_admin_workspace_home)
elif page=='Tableau de bord':
    if st.session_state.get('admin_workspace')==WORKSPACE_ACTIONS:
        _run_ui_module('dashboard',dashboard)
    else:
        _run_ui_module('dashboard_general',admin_general_dashboard)
elif page=='Nouvelle action':
    if st.session_state.get('import_create_active'):
        _run_ui_module('nouvelle_action_import',lambda: create_action_screen(st.session_state.get('import_prefill'),st.session_state.get('import_parts')))
    else:
        _run_ui_module('nouvelle_action',create_action_screen)
elif page=='Importer une action': _run_ui_module('import_actions',import_screen)
elif page=='Actions': _run_ui_module('actions',actions_list)
elif page=='Relances': _run_ui_module('relances',reminders_screen)
elif page=='Qualité': _run_ui_module('qualite',quality_management_screen)
elif page=='Études PIP/O*NET': _run_ui_module('etudes_pip_onet',studies_screen)
elif page=='Contacts / Prospects': _run_ui_module('crm',crm_screen)
elif page=='Espace Client / DRH': _run_ui_module('espace_client_drh_admin',admin_client_portal_screen)
elif page=='Intervenants / Partenaires': _run_ui_module('intervenants_partenaires',professionals_screen)
elif page=='Paramètres': _run_ui_module('parametres',settings_screen)
