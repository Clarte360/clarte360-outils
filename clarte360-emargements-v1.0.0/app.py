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
from input_validation import validate_action_no, validate_short_text, validate_date_range, validate_participant_payload, validate_email, validate_full_name, InputValidationError
from excel_import import read_action_xlsm, list_action_numbers_for_profile, read_clarte360_xlsm, read_adca_xlsm, list_action_numbers
from pdf_utils import collective_pdf, individual_pdf, certificate_pdf, quality_response_pdf, teams_evidence_pdf
from mailer import send_mail, resolve_mail_config, validate_mail_config
from source_store import source_info, set_external_path, save_uploaded_source, refresh_from_external, read_snapshot, copy_source_metadata
from graph_client import GraphClient, graph_config_from_mapping, graph_config_missing
from signature_guard import signature_trace_is_valid, signature_trace_metrics

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
BASE_URL=secret('app','base_url','http://localhost:8501');TZ=secret('app','timezone','Europe/Paris')
try:
    refresh_pip_connector_runtime_status(ENGINE,secret('pip_connector','launch_signing_key',''),secret('pip_connector','outbox_path',''),'system')
except Exception:
    pass
_PIN_KEY=secret('security','participant_pin_key',secret('app','setup_key',''))
if _PIN_KEY: os.environ['CLARTE360_PIN_KEY']=str(_PIN_KEY)
TRAINER_REPORT_DIR=Path(__file__).resolve().parent/'data'/'trainer_reports'; TRAINER_REPORT_DIR.mkdir(parents=True,exist_ok=True)

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
    st.markdown(f"### {a['action_no']} — {a['title']}")
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Prestation',(a.get('prestation_type') or a.get('nature') or '—').replace('_',' '))
    c2.metric('Client',a.get('client_name') or '—')
    c3.metric('Modalité',delivery_mode_label(a.get('delivery_mode')))
    c4.metric('Participants',len(parts))
    st.caption(f"Lieu / précision : {a.get('location') or 'Non renseigné'} · Période : {a.get('start_date') or '—'} → {a.get('end_date') or '—'} · Statut : {normalize_action_status(a.get('status'))}")
    if next_slot:
        st.success(f"Prochaine séance : {_slot_label(next_slot)}")
    elif slots:
        st.info('Aucune séance future : le calendrier affiché ci-dessous reprend les séances enregistrées.')
    else:
        st.warning('Aucun créneau n’est actuellement enregistré pour cette action.')

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

    tab_plan,tab_teams,tab_em,tab_codes,tab_docs,tab_tools,tab_quality,tab_report=st.tabs(['📅 Planning','💻 Teams','✍️ Émargements / QR','🔐 Codes participants','📚 Documents','🧭 Outils Clarté360','📋 Qualité','📣 Signaler / informer'])
    with tab_plan:
        if slots:
            cal=[]
            for sl in slots:
                signed=one(ENGINE,"SELECT COUNT(*) n FROM signatures WHERE slot_id=:s AND status='VALIDE'",{'s':sl['id']})['n']
                absent=one(ENGINE,"SELECT COUNT(*) n FROM attendance_status WHERE slot_id=:s AND status='ABSENT'",{'s':sl['id']})['n']
                cs_ok,cs_missing=required_slot_countersignatures_complete(ENGINE,sl['id'])
                cal.append({'Date':sl['slot_date'],'Début':sl['start_time'],'Fin':sl['end_time'],'Type':sl.get('slot_kind') or 'NORMAL','Signés':signed,'Absents':absent,'Contresigné':'Oui' if cs_ok else ('Manque '+str(len(cs_missing)))})
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
                    nd=c1.date_input('Nouvelle date',value=date.fromisoformat(es['slot_date']))
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
                    rd=c1.date_input('Date du report',value=date.fromisoformat(es['slot_date']),key=f'tr_rep_d_{es["id"]}')
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
                        ad=c1.date_input('Date',value=date.today(),key=f'tr_add_d_{aid}')
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
    with tab_teams:
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
    with tab_em:
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
                st.caption('Signature manuscrite de l’intervenant')
                st.info('Signez dans le cadre gris ci-dessous avec la souris, le doigt ou un stylet.')
                tr_canvas=st_canvas(fill_color='rgba(255,255,255,0)',stroke_width=4,stroke_color='#0F172A',background_color='#DDE5E7',height=190,width=420,drawing_mode='freedraw',display_toolbar=False,update_streamlit=True,key=f'tr_csig_v31fix_{aid}_{sl["id"]}_{trainer["id"]}')
                cert=st.checkbox("Je certifie l'exactitude des présences et absences indiquées pour ce créneau.",key=f'tr_cert_{aid}_{sl["id"]}')
                if st.button('CONTRESIGNER CE CRÉNEAU',type='primary',key=f'tr_sign_{aid}_{sl["id"]}',disabled=not eligible):
                    if not cert: st.error('La certification est obligatoire.')
                    elif not signature_trace_is_valid(tr_canvas.image_data): st.error('La signature semble vide ou trop courte. Merci d’apposer une signature manuscrite complète dans le cadre.')
                    else:
                        img=PILImage.fromarray(tr_canvas.image_data.astype('uint8'),'RGBA').convert('RGB');buf=io.BytesIO();img.save(buf,format='PNG')
                        ip,ua=request_technical_context()
                        ok,msg=countersign_slot(ENGINE,sl['id'],trainer['full_name'],trainer.get('email'),actor,"Je certifie l'exactitude des présences et absences indiquées pour ce créneau.",trainer_id=trainer['id'],signature_bytes=buf.getvalue(),ip_address=ip,user_agent=ua)
                        if ok: st.success('Contresignature enregistrée.'); rerun()
                        else: st.error(msg)
    with tab_codes:
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
    with tab_docs:
        docs=list_action_documents(ENGINE,aid)
        if docs:
            for d in docs:
                path=Path(d['storage_path'])
                if path.is_file(): st.download_button(d['display_name'],path.read_bytes(),file_name=d['display_name'],key=f"tr_doc_dl_{d['id']}")
        else: st.info('Aucun document mis à disposition pour cette action.')
        if trainer.get('can_upload_documents'):
            st.markdown('#### Déposer un document pour tous les bénéficiaires de cette action')
            updoc=st.file_uploader('Document',type=['pdf','json','doc','docx','xls','xlsx','ppt','pptx','txt','csv','jpg','jpeg','png','webp','zip'],key=f'tr_course_doc_{aid}')
            if st.button('Déposer dans Documents de cours',key=f'tr_course_doc_btn_{aid}',disabled=updoc is None):
                try:
                    rid,h,dedup=store_document(ENGINE,updoc.getvalue(),updoc.name,'COURS',actor,action_id=aid,audience='ACTION_BENEFICIARIES')
                    st.success('Document déposé. '+('Le contenu existait déjà : aucune seconde copie physique n’a été créée.' if dedup else 'Nouveau fichier physique enregistré.'));rerun()
                except Exception as ex: _ui_incident('operation_interface',ex)
        else: st.caption("Le dépôt de documents n'est pas autorisé pour votre compte. L'administrateur peut activer ce droit.")
    with tab_tools:
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
                    bl=st.selectbox('Bénéficiaire',list(bmap)); tl=st.selectbox('Outil',list(tmap)); due=st.date_input('Échéance indicative',value=None)
                    submit_tool=st.form_submit_button('PRESCRIRE CET OUTIL',type='primary')
                if submit_tool:
                    bx=bmap[bl]; tx=tmap[tl]
                    try:
                        pr=create_tool_prescription(ENGINE,tx['tool_code'],bx['beneficiary_id'],aid,bx['participant_id'],prescriber_type='TRAINER',prescriber_id=tid,prescriber_role='INTERVENANT',due_at=due.isoformat() if due else None,actor=actor)
                        st.success(f"Prescription créée : {pr['prescription_id']}"); rerun()
                    except ValueError as ex: st.error(str(ex))
            hist=[x for x in list_tool_prescriptions(ENGINE,action_id=aid,trainer_id=tid) if x.get('status')!='ANNULE']
            if hist:
                st.dataframe(pd.DataFrame([{'Bénéficiaire':f"{x['beneficiary_last_name']} {x['beneficiary_first_name']}",'Outil':x['tool_name'],'Créateur':'Moi' if (x.get('prescriber_type')=='TRAINER' and str(x.get('prescriber_id'))==str(tid)) else 'Autre utilisateur','Créée':x['created_at'][:16].replace('T',' '),'Échéance':x.get('due_at') or '','Statut':x['status'].replace('_',' ')} for x in hist]),use_container_width=True,hide_index=True)
                hmap={f"{x['beneficiary_last_name']} {x['beneficiary_first_name']} — {x['tool_name']} — {x['prescription_id']}":x for x in hist}
                hh=hmap[st.selectbox('Prescription existante',list(hmap),key=f'tr_tool_existing_{aid}')]
                owns=(hh.get('prescriber_type')=='TRAINER' and str(hh.get('prescriber_id'))==str(tid))
                if st.button('SUPPRIMER MA PRESCRIPTION',key=f'tr_tool_cancel_{hh["id"]}',disabled=not owns):
                    ok,msg=cancel_tool_prescription_owned(ENGINE,hh['prescription_id'],'TRAINER',tid,actor)
                    if ok: st.success('Prescription supprimée de votre liste active et conservée dans la piste d’audit.');rerun()
                    else: st.warning(msg)
                if not owns: st.caption('Cette prescription a été créée par un autre utilisateur : vous ne pouvez pas la supprimer.')

    with tab_quality:
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
            bstats=quality_question_stats(ENGINE,action_id=aid)
            bcamps=q(ENGINE,"SELECT campaign_kind,status FROM quality_campaigns WHERE action_id=:a AND campaign_kind IN ('HOT','COLD')",{'a':aid})
            completed=sum(1 for x in bcamps if x['status']=='COMPLETED')
            if bcamps:
                st.markdown('#### Résultats des bénéficiaires de cette action')
                vals=[x['Moyenne'] for x in bstats if x.get('Moyenne') is not None]
                c1,c2=st.columns(2); c1.metric('Moyenne des réponses',f"{round(sum(vals)/len(vals),2)}/5" if vals else '—'); c2.metric('Questionnaires reçus',f"{completed}/{len(bcamps)}")
                if bstats:
                    st.dataframe(pd.DataFrame([{'Thème':x['Rubrique'],'Question':x['Question'],'Réponses':x['Réponses'],'Moyenne':x['Moyenne'] if x['Moyenne'] is not None else '—'} for x in bstats]),use_container_width=True,hide_index=True)
        else:
            st.info(f"Questionnaire disponible : {camp.get('questionnaire_title') or 'Retour intervenant'}")
            st.link_button('OUVRIR LE QUESTIONNAIRE',quality_token_url(camp['token'],BASE_URL),type='primary')
    with tab_report:
        st.caption("Vous pouvez transmettre une observation, une difficulté, un incident, un problème logistique ou une demande de contact à l'administration.")
        with st.form(f'tr_report_{aid}',clear_on_submit=True):
            rt=st.selectbox('Nature',['Observation','Difficulté','Incident','Problème logistique','Besoin de contact','Autre'])
            subject=st.text_input('Objet *'); desc=st.text_area('Description *',height=150)
            qrel=st.checkbox('Ce signalement doit également alimenter le suivi qualité',value=rt in ('Difficulté','Incident','Problème logistique'))
            up=st.file_uploader('Joindre éventuellement un document (10 Mo max)',type=['pdf','docx','xlsx','png','jpg','jpeg','txt'],key=f'tr_report_file_{aid}')
            submit=st.form_submit_button('TRANSMETTRE À L’ADMINISTRATION',type='primary')
        if submit:
            if not subject.strip() or not desc.strip(): st.error('Objet et description sont obligatoires.')
            elif up is not None and up.size>10*1024*1024: st.error('Le fichier dépasse 10 Mo.')
            else:
                ap=an=None
                if up is not None:
                    safe=re.sub(r'[^A-Za-z0-9._-]+','_',up.name)[:120]; an=up.name; ap=str(TRAINER_REPORT_DIR/f"{aid}_{tid}_{int(datetime.now().timestamp())}_{safe}"); Path(ap).write_bytes(up.getvalue())
                rid=create_trainer_report(ENGINE,aid,tid,rt,subject.strip(),desc.strip(),qrel,ap,an)
                if rid: st.success('Votre message a été transmis à l’administration et journalisé.')
                else: st.error('Transmission impossible : action non autorisée.')
        history=trainer_reports(ENGINE,aid,tid)
        if history:
            st.markdown('#### Mes transmissions récentes')
            st.dataframe(pd.DataFrame([{'Date':x['created_at'][:16].replace('T',' '),'Nature':x['report_type'],'Objet':x['subject'],'Statut':x['status'].replace('_',' '),'Réponse administration':x.get('admin_response') or ''} for x in history]),use_container_width=True,hide_index=True)

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
    top1,top2=st.columns([4,1])
    top1.caption('Tableau de bord sécurisé : seules les actions qui vous sont affectées sont visibles.')
    if top2.button('Se déconnecter',use_container_width=True):
        _logout_persistent('TRAINER',['trainer_portal_id','trainer_portal_name'])
    acts=trainer_actions(ENGINE,tid)
    if not acts:
        st.info('Aucune action ne vous est actuellement affectée.'); footer(); return
    tasks=trainer_countersign_tasks(ENGINE,tid)
    if tasks:
        st.info(f"{len(tasks)} créneau(x) à contresigner ou à finaliser.")
    else:
        st.success('Aucune contresignature en attente actuellement.')
    cards=[]
    for a in acts:
        data=trainer_action_dashboard(ENGINE,tid,a['id'],TZ); nxt=data.get('next_slot') if data else None
        cards.append({'Action':a['action_no'],'Intitulé':a['title'],'Client':a.get('client_name') or '','Début':a.get('start_date') or '','Fin':a.get('end_date') or '','Prochaine séance':_slot_label(nxt) if nxt else '—','Statut':normalize_action_status(a.get('status'))})
    st.dataframe(pd.DataFrame(cards),use_container_width=True,hide_index=True)
    labels={f"{a['action_no']} — {a['title']} — {normalize_action_status(a.get('status'))}":a for a in acts}
    requested_action=st.query_params.get('action_id')
    try: requested_action=int(requested_action) if requested_action is not None else None
    except Exception: requested_action=None
    lab_list=list(labels); default_idx=next((i for i,k in enumerate(lab_list) if labels[k]['id']==requested_action),0)
    lab=st.selectbox('Action à ouvrir',lab_list,index=default_idx,key='trainer_action_choice'); render_trainer_action(labels[lab],tr)
    footer(labels[lab]['id'])


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
    c1,c2=st.columns([4,1]);c1.caption(f"Identifiant interne : {b['public_id']} · Connexion : {acc['email']}")
    if c2.button('Se déconnecter',use_container_width=True): _logout_persistent('BENEFICIARY',['beneficiary_portal_id'])
    acts=beneficiary_participations(ENGINE,bid);docs=list_beneficiary_documents(ENGINE,bid)
    pending=q(ENGINE,"""SELECT qc.*,a.action_no,qt.title FROM quality_campaigns qc JOIN actions a ON a.id=qc.action_id JOIN questionnaire_templates qt ON qt.id=qc.template_id
      WHERE qc.participant_id IN (SELECT id FROM participants WHERE beneficiary_id=:b) AND qc.status<>'COMPLETED' ORDER BY qc.due_at""",{'b':bid})
    completed=q(ENGINE,"""SELECT qc.*,a.action_no,a.title action_title,qt.title FROM quality_campaigns qc JOIN actions a ON a.id=qc.action_id JOIN questionnaire_templates qt ON qt.id=qc.template_id
      WHERE qc.participant_id IN (SELECT id FROM participants WHERE beneficiary_id=:b) AND qc.status='COMPLETED' ORDER BY COALESCE(qc.completed_at,qc.created_at) DESC""",{'b':bid})
    prescriptions=list_tool_prescriptions(ENGINE,beneficiary_id=bid,include_cancelled=False)
    tabs=st.tabs(['🏠 Accueil','🎓 Mes formations / accompagnements','📅 Mon planning','💻 Mes réunions Teams','🧭 Mes outils Clarté360','📄 Mes documents administratifs','📚 Documents de cours','✅ Mes questionnaires / actions','✍️ Mes émargements','📣 Signaler / informer','🗂️ Mes archives / téléchargements'])
    with tabs[0]:
        st.metric('Parcours enregistrés',len(acts));st.metric('Documents disponibles',len(docs));st.metric('Actions à réaliser',len(pending))
        if acts: st.dataframe(pd.DataFrame([{'Action':a['action_no'],'Intitulé':a['title'],'Prestation':a.get('prestation_type') or a.get('nature'),'Début':a.get('start_date') or '','Fin':a.get('end_date') or '','Statut':normalize_action_status(a.get('status'))} for a in acts]),use_container_width=True,hide_index=True)
    with tabs[1]:
        if acts: st.dataframe(pd.DataFrame([{'Action':a['action_no'],'Intitulé':a['title'],'Client':a.get('client_name') or '','Lieu / modalité':a.get('location') or a.get('mode') or '','Période':f"{a.get('start_date') or '—'} → {a.get('end_date') or '—'}"} for a in acts]),use_container_width=True,hide_index=True)
        else: st.info('Aucun parcours.')
    with tabs[2]:
        rows=[]
        for a in acts:
            for sl in q(ENGINE,"SELECT * FROM slots WHERE action_id=:a AND status NOT IN ('ANNULE','REPORTE') ORDER BY slot_date,start_time",{'a':a['id']}): rows.append({'Action':a['action_no'],'Date':sl['slot_date'],'Début':sl['start_time'],'Fin':sl['end_time'],'Type':sl.get('slot_kind') or 'NORMAL'})
        if rows: st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        else: st.info('Aucun créneau disponible.')
        if acts:
            st.markdown('#### Mes calendriers')
            for aa in acts:
                ics=action_calendar_ics(ENGINE,aa['id'],beneficiary_id=bid)
                if ics:
                    st.download_button(f"📅 {aa['action_no']} — ajouter / actualiser dans mon agenda",ics,file_name=f"{aa['action_no']}_planning.ics",mime='text/calendar',key=f'benef_ics_{aa["id"]}')
    def _show_docs(rows,empty):
        if not rows: st.info(empty);return
        for d in rows:
            path=Path(d['storage_path'])
            if path.is_file(): st.download_button(f"{d.get('action_no') or 'Général'} — {d['display_name']}",path.read_bytes(),file_name=d['display_name'],key=f"bdl_{d['id']}")
    with tabs[3]:
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
    with tabs[4]:
        if not prescriptions:
            st.info('Aucun outil Clarté360 ne vous est actuellement prescrit.')
        else:
            for pr in prescriptions:
                st.markdown(f"**{pr['tool_name']}** — {pr['action_no']} · Statut : {pr['status'].replace('_',' ')}")
                if pr.get('due_at'): st.caption(f"Échéance : {pr['due_at']}")
                if pr.get('status')=='TERMINE':
                    st.success('Outil terminé.')
                else:
                    try:
                        tok=create_prescription_launch_token(ENGINE,pr['prescription_id'],actor=f"beneficiary:{bid}")
                        st.link_button('OUVRIR CET OUTIL',f"{BASE_URL.rstrip('/')}?tool_launch={quote(tok)}",type='primary')
                    except ValueError as ex: st.warning(str(ex))
                st.divider()
    with tabs[5]: _show_docs([d for d in docs if d['category']!='COURS'],'Aucun document administratif disponible.')
    with tabs[6]:
        _show_docs([d for d in docs if d['category']=='COURS'],'Aucun document de cours disponible.')
        st.markdown('#### Déposer mes documents / résultats d’applications')
        st.caption('Vous pouvez déposer plusieurs fichiers PDF ou JSON issus des outils Clarté360. Ils restent rattachés à votre espace et à l’action choisie.')
        if acts:
            amap={f"{aa['action_no']} — {aa['title']}":aa for aa in acts}; al=st.selectbox('Action concernée',list(amap),key='benef_upload_action'); aa=amap[al]
            uploads=st.file_uploader('Mes fichiers',type=['pdf','json'],accept_multiple_files=True,key='benef_app_results')
            if st.button('DÉPOSER DANS MON ESPACE',type='primary',disabled=not bool(uploads),key='benef_upload_btn'):
                pp=one(ENGINE,'SELECT id FROM participants WHERE action_id=:a AND beneficiary_id=:b AND active=1',{'a':aa['id'],'b':bid})
                done=0
                for up in uploads or []:
                    try:
                        store_document(ENGINE,up.getvalue(),up.name,'BENEFICIAIRE',f'beneficiary:{bid}',action_id=aa['id'],beneficiary_id=bid,participant_id=(pp or {}).get('id'),audience='BENEFICIARY_ONLY',visible_to_beneficiary=True,allowed_extensions={'.pdf','.json'})
                        done+=1
                    except Exception as ex: st.error(f"{up.name} : {ex}")
                if done: st.success(f'{done} fichier(s) déposé(s) dans votre espace.'); rerun()
    with tabs[7]:
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
    with tabs[8]:
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

    with tabs[9]:
        st.caption("Vous pouvez transmettre une observation, une difficulté, un incident, un problème logistique ou une demande de contact à l'administration. Votre historique reste visible après traitement.")
        if acts:
            amap={f"{aa['action_no']} — {aa['title']}":aa for aa in acts}
            with st.form('beneficiary_report_form',clear_on_submit=True):
                al=st.selectbox('Action concernée',list(amap),key='benef_report_action'); aa=amap[al]
                rt=st.selectbox('Nature',['Observation','Difficulté','Incident','Problème logistique','Besoin de contact','Autre'],key='benef_report_type')
                subject=st.text_input('Objet *',key='benef_report_subject'); desc=st.text_area('Description *',height=150,key='benef_report_desc')
                qrel=st.checkbox('Ce signalement doit également alimenter le suivi qualité',value=rt in ('Difficulté','Incident','Problème logistique'),key='benef_report_quality')
                up=st.file_uploader('Joindre éventuellement un document (10 Mo max)',type=['pdf','docx','xlsx','png','jpg','jpeg','txt','json'],key='benef_report_file')
                submit=st.form_submit_button('TRANSMETTRE À L’ADMINISTRATION',type='primary')
            if submit:
                if not subject.strip() or not desc.strip(): st.error('Objet et description sont obligatoires.')
                elif up is not None and up.size>10*1024*1024: st.error('Le fichier dépasse 10 Mo.')
                else:
                    ap=an=None
                    if up is not None:
                        safe=re.sub(r'[^A-Za-z0-9._-]+','_',up.name)[:120]; an=up.name; ap=str(TRAINER_REPORT_DIR/f"benef_{aa['id']}_{bid}_{int(datetime.now().timestamp())}_{safe}"); Path(ap).write_bytes(up.getvalue())
                    rid=create_beneficiary_report(ENGINE,aa['id'],bid,rt,subject.strip(),desc.strip(),qrel,ap,an)
                    if rid: st.success("Votre signalement a été transmis à l'administration et journalisé."); rerun()
                    else: st.error('Transmission impossible pour cette action.')
        hist=beneficiary_reports(ENGINE,beneficiary_id=bid)
        if hist:
            st.markdown('#### Mes signalements')
            st.dataframe(pd.DataFrame([{'Date':x['created_at'][:16].replace('T',' '),'Action':x['action_no'],'Nature':x['report_type'],'Objet':x['subject'],'Statut':x['status'].replace('_',' '),'Réponse administration':x.get('admin_response') or ''} for x in hist]),use_container_width=True,hide_index=True)
        else: st.info('Aucun signalement transmis.')
    with tabs[10]:
        st.caption('Vous pouvez télécharger à tout moment une copie des documents actuellement mis à disposition dans votre portail.')
        z=beneficiary_portal_zip(ENGINE,bid)
        st.download_button('TÉLÉCHARGER MON ESPACE EN ZIP',z,file_name=f"{b['public_id']}_ESPACE_CLARTE360.zip",mime='application/zip',type='primary')
        _show_docs(docs,'Aucun document disponible.')
    footer()

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
        st.info('Signez dans le cadre gris ci-dessous avec la souris, le doigt ou un stylet.')
        legacy_canvas=st_canvas(fill_color='rgba(255,255,255,0)',stroke_width=4,stroke_color='#0F172A',background_color='#EEF2F3',height=190,width=520,drawing_mode='freedraw',display_toolbar=True,update_streamlit=True,key=f'legacy_csig_{slot["id"]}')
        cert=st.checkbox("Je certifie l'exactitude des présences et absences indiquées pour ce créneau.")
        if st.button('CONTRESIGNER CE CRÉNEAU',type='primary',disabled=(not eligible or (bool(assigned) and legacy_tid is None))):
            if not name.strip() or not cert: st.error('Nom et certification obligatoires.')
            elif not signature_trace_is_valid(legacy_canvas.image_data): st.error('La signature semble vide ou trop courte. Merci d’apposer une signature manuscrite complète dans le cadre.')
            else:
                img=PILImage.fromarray(legacy_canvas.image_data.astype('uint8'),'RGBA').convert('RGB');buf=io.BytesIO();img.save(buf,format='PNG')
                ip,ua=request_technical_context()
                ok,msg=countersign_slot(ENGINE,slot['id'],name.strip(),row.get('trainer_email'),f"trainer:{name.strip()}","Je certifie l'exactitude des présences et absences indiquées pour ce créneau.",trainer_id=legacy_tid,signature_bytes=buf.getvalue(),ip_address=ip,user_agent=ua)
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

def sidebar():
    st.sidebar.image(str(LOGO_PATH),width=70);st.sidebar.markdown(f"**{st.session_state.get('admin_name','Administrateur')}**")
    pages=['Tableau de bord','Nouvelle action','Importer une action','Actions','Relances','Qualité','Études PIP/O*NET','Contacts / Prospects','Paramètres']
    page=st.sidebar.radio('Navigation',pages,key='nav')
    st.sidebar.divider()
    if st.sidebar.button('Se déconnecter',use_container_width=True): _logout_persistent('ADMIN',['admin_email','admin_name','nav'])
    return page

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

    with st.form('new_action', enter_to_submit=False):
        action_no=st.text_input('N° D’ACTION *',value=p.get('action_no','')).strip().upper()
        title=st.text_input('Intitulé *',value=p.get('title',''))
        subtitle=st.text_input('Intitulé complémentaire',value=p.get('subtitle') or '')

        c1,c2=st.columns(2)
        start_date=c1.date_input('Date de début',value=start_default)
        end_date=c2.date_input('Date de fin',value=end_default)

        c1,c2,c3,c4=st.columns(4)
        mode=c1.selectbox('Organisation',mode_options,index=mode_options.index(mode_default))
        planned=c2.number_input('Durée contractuelle prévue (h)',min_value=0.0,step=.5,value=float(p.get('planned_hours') or 0))
        expected=c3.number_input('Nombre prévu de stagiaires',min_value=1,step=1,value=expected_default)
        group=c4.text_input('Code de groupe / session INTER',value=p.get('group_code') or '')

        c1,c2=st.columns(2)
        client=c1.text_input('Client / entreprise (facultatif)',value=p.get('client_name') or '')
        client_type=c2.selectbox('Type client',['Non précisé','Professionnel','Particulier'])

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
        else:
            aid=create_action(ENGINE,{
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
            },st.session_state.admin_email)

            if trainer_opts.get(trainer_label):
                assign_trainer(ENGINE,aid,trainer_opts[trainer_label],st.session_state.admin_email)

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

def dashboard():
    header('Clarté360 — Gestion des actions','Vue globale des actions et du suivi opérationnel')
    acts=q(ENGINE,'SELECT * FROM actions ORDER BY id DESC')
    total=len(acts);open_n=sum(normalize_action_status(a['status'])!='ARCHIVEE' for a in acts);pending=one(ENGINE,"SELECT COUNT(*) n FROM email_events WHERE status='PENDING'")['n'];signed=one(ENGINE,"SELECT COUNT(*) n FROM signatures WHERE status='VALIDE'")['n']
    c1,c2,c3,c4=st.columns(4)
    for c,n,l in [(c1,total,'Actions'),(c2,open_n,'Actives'),(c3,signed,'Signatures'),(c4,pending,'Envois / relances prévus')]: c.markdown(f"<div class='c360-kpi'><div class='n'>{n}</div><div class='l'>{l}</div></div>",unsafe_allow_html=True)
    st.subheader('Actions récentes')
    rows=[]
    for a in acts[:20]:
        pr=action_progress(ENGINE,a['id']);rows.append({'Action':a['action_no'],'Intitulé':a['title'],'Mode':a['mode'],'Participants':pr['participants'],'Créneaux':pr['slots'],'Signatures':f"{pr['signed']}/{pr['expected']}",'Avancement':f"{pr['percent']}%"})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    st.caption("Le pilotage qualité est centralisé dans l’onglet Qualité.")
    footer()

def actions_list():
    header('Clarté360 — Actions','Reprendre, modifier et suivre une action')
    c1,c2=st.columns([3,1]); search=c1.text_input('Rechercher une action, un bénéficiaire, un client ou un email'); include_archived=c2.checkbox('Inclure les archives',value=False); acts=search_actions(ENGINE,search,include_archived=include_archived)
    if not acts: st.info('Aucune action correspondant aux critères.');footer();return
    labels={f"{a['action_no']} — {a['title']} — {normalize_action_status(a['status'])}":a['id'] for a in acts};sel=st.selectbox('Choisir une action',list(labels));aid=labels[sel];st.session_state.selected_action=aid
    action_detail(aid)
    a=one(ENGINE,'SELECT * FROM actions WHERE id=:a',{'a':aid})
    with st.expander('🗑️ Supprimer définitivement cette action'):
        st.error('Suppression irréversible : participants, créneaux, signatures, absences, relances, contresignatures et historique de cette action seront supprimés.')
        confirm=st.text_input(f"Pour confirmer, saisissez le n° d’action : {a['action_no']}",key=f'delactxt{aid}');pw=st.text_input('Votre mot de passe administrateur',type='password',key=f'delacpw{aid}')
        if st.button('🗑️ SUPPRIMER DÉFINITIVEMENT L’ACTION',key=f'delac{aid}'):
            if confirm.strip()!=a['action_no']: st.error('Le numéro d’action saisi ne correspond pas.')
            elif not admin_password_ok(ENGINE,st.session_state.admin_email,pw): st.error('Mot de passe administrateur incorrect.')
            else:
                ok,msg=purge_action(ENGINE,aid,st.session_state.admin_email)
                if ok: st.session_state.pop('selected_action',None);st.success('Action et données associées supprimées.');rerun()
                else: st.error(msg)
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
    tabs=st.tabs(['Paramètres action','Participants','Intervenants','Calendrier','Teams','Outils Clarté360','Contractualisation','Envois & relances','Suivi','Qualité','Documents','Journal'])
    tab_specs=[
        ('action_parametres', action_settings_tab),('action_participants', participants_tab),('action_intervenants', action_trainers_tab),
        ('action_calendrier', calendar_tab),('action_teams', teams_tab),('action_outils', action_tools_tab),
        ('action_contractualisation', contractualization_tab),('action_envois', dispatch_tab),('action_suivi', tracking_tab),
        ('action_qualite', quality_tab),('action_documents', documents_tab),('action_journal', audit_tab)]
    for tab,(ctx,fn) in zip(tabs,tab_specs):
        with tab:
            _run_ui_module(ctx,lambda fn=fn: fn(a),action_id=a['id'])

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
        c1,c2=st.columns(2);start_date=c1.date_input('Date de début',value=date.fromisoformat(a['start_date']) if a.get('start_date') else date.today());end_date=c2.date_input('Date de fin',value=date.fromisoformat(a['end_date']) if a.get('end_date') else date.today())
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
    allowed_tools=action_allowed_tools(ENGINE,a['id'])
    with st.expander('Outils autorisés sur cette action',expanded=not bool(allowed_tools)):
        st.caption("L'administrateur choisit ici les outils que les intervenants autorisés pourront prescrire dans cette action. Le catalogue global reste inchangé.")
        cmap={f"{x['name']} — {x.get('tool_version') or 'version non précisée'}":x for x in compatible_tools}
        current_codes={x['tool_code'] for x in allowed_tools}
        defaults=[label for label,x in cmap.items() if x['tool_code'] in current_codes]
        selected=st.multiselect('Outils disponibles pour cette action',list(cmap),default=defaults,key=f'action_tools_allow_{a["id"]}')
        if st.button('ENREGISTRER LES OUTILS DE L’ACTION',key=f'action_tools_allow_save_{a["id"]}',type='primary'):
            wanted={cmap[x]['tool_code'] for x in selected}
            for tx in compatible_tools:
                set_action_tool_allowed(ENGINE,a['id'],tx['tool_code'],tx['tool_code'] in wanted,st.session_state.admin_email)
            st.success('Liste des outils autorisés enregistrée.'); rerun()
    tools=action_allowed_tools(ENGINE,a['id'])
    c1,c2,c3=st.columns(3);c1.metric('Bénéficiaires rattachés',len(linked));c2.metric('Outils autorisés',len(tools));c3.metric('Prescriptions',len([x for x in list_tool_prescriptions(ENGINE,action_id=a['id']) if x.get('status')!='ANNULE']))
    if linked and tools:
        bmap={f"{x['last_name']} {x['first_name']} — {x['public_id']}":x for x in linked}; tmap={f"{x['name']} — {x.get('tool_version') or 'version non précisée'}":x for x in tools}
        with st.form(f'admin_tool_prescribe_{a["id"]}'):
            bl=st.selectbox('Bénéficiaire',list(bmap)); tl=st.selectbox('Outil Clarté360',list(tmap)); due=st.date_input('Échéance indicative',value=None,key=f'tool_due_{a["id"]}')
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
        st.dataframe(pd.DataFrame([{'Prescription':x['prescription_id'],'Bénéficiaire':f"{x['beneficiary_last_name']} {x['beneficiary_first_name']}",'Outil':x['tool_name'],'Créateur':'Administrateur' if x.get('prescriber_type')=='ADMIN' else 'Intervenant','Statut':x['status'].replace('_',' '),'Créée':x['created_at'][:16].replace('T',' '),'Échéance':x.get('due_at') or ''} for x in rows if x.get('status')!='ANNULE']),use_container_width=True,hide_index=True)
        rmap={f"{x['prescription_id']} — {x['beneficiary_last_name']} {x['beneficiary_first_name']} — {x['tool_name']}":x for x in rows}; rl=st.selectbox('Prescription à gérer',list(rmap),key=f'presc_manage_{a["id"]}'); rr=rmap[rl]
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
            st.dataframe(pd.DataFrame([{'Code':x['tool_code'],'Nom':x['name'],'Catégorie':x['category'],'Version':x.get('tool_version') or '','Actif':'Oui' if x['active'] else 'Non','Prescriptible':'Oui' if x['prescription_allowed'] else 'Non','Connexion':'Sécurisée Clarté360' if x['launch_type']=='EXTERNAL_SIGNED' else ('Redirection Hub' if x['launch_type']=='HUB_REDIRECT' else 'Interne'),'État':'Connecté' if x.get('connector_status')=='CONNECTED' else ('Lancement prêt' if x.get('connector_status')=='LAUNCH_ONLY' else 'Configuration VPS à terminer')} for x in cat]),use_container_width=True,hide_index=True)
        st.caption("Les outils Clarté360 connus sont préchargés automatiquement. Sélectionnez un outil existant pour le consulter ou le mettre à jour.")
        existing_map={'➕ Nouvel outil':None}
        for x in cat:
            existing_map[f"{x['name']} — {x['tool_code']}"]=x
        selected_label=st.selectbox('Outil du catalogue',list(existing_map),key=f'tool_catalog_select_{a["id"]}')
        selected_tool=existing_map[selected_label]
        with st.form(f'tool_catalog_add_{a["id"]}'):
            pip_selected=bool(selected_tool and selected_tool.get('tool_code')=='PIP_RIASEC_ONET')
            c1,c2=st.columns(2)
            code=c1.text_input('Code outil',value=(selected_tool or {}).get('tool_code') or '',disabled=pip_selected)
            name=c2.text_input('Nom outil',value=(selected_tool or {}).get('name') or '',disabled=pip_selected)
            c1,c2,c3=st.columns(3)
            category=c1.text_input('Catégorie',value=(selected_tool or {}).get('category') or 'OUTIL',disabled=pip_selected)
            version=c2.text_input('Version',value=(selected_tool or {}).get('tool_version') or '',disabled=pip_selected)
            base_url=c3.text_input('URL de base vérifiée',value=(selected_tool or {}).get('base_url') or ('https://pip-riasec.clarte360.com' if pip_selected else ''),disabled=pip_selected)
            launch_values=['HUB_REDIRECT','EXTERNAL_SIGNED','INTERNAL']
            current_launch='EXTERNAL_SIGNED' if pip_selected else ((selected_tool or {}).get('launch_type') or 'HUB_REDIRECT')
            launch=st.selectbox('Type de connexion',launch_values,index=launch_values.index(current_launch),disabled=pip_selected,help='Connexion sécurisée signée pour le PIP ; redirection simple pour un outil web sans contrat signé ; interne pour un module de Gestion des Actions.')
            if pip_selected: st.caption('PIP RIASEC / O*NET : connexion sécurisée Clarté360 imposée automatiquement.')
            active=st.checkbox('Actif',value=bool((selected_tool or {}).get('active',1)))
            presc=st.checkbox('Prescription autorisée',value=bool((selected_tool or {}).get('prescription_allowed',1)))
            save_tool=st.form_submit_button('ENREGISTRER LE CATALOGUE')
        if save_tool:
            try:
                effective=selected_tool or {}
                final_code=effective.get('tool_code') or code
                final_name=effective.get('name') or name
                final_category=effective.get('category') or category
                final_version=effective.get('tool_version') or version
                final_url=effective.get('base_url') or base_url
                final_launch='EXTERNAL_SIGNED' if final_code=='PIP_RIASEC_ONET' else launch
                upsert_tool_catalog(ENGINE,{'tool_code':final_code,'name':final_name,'category':final_category,'tool_version':final_version,'base_url':final_url,'launch_type':final_launch,'active':active,'prescription_allowed':presc,'allowed_publics':['BENEFICIAIRE']},st.session_state.admin_email)
                st.success('Catalogue mis à jour.');rerun()
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
        st.dataframe(pd.DataFrame([{'Séance':f"{x['slot_date']} — {x['start_time']}–{x['end_time']}",
            'Statut':'Présence récupérée' if x.get('attendance_report_id') else ('Planifiée' if x.get('status')=='PLANNED' else x.get('status') or '—')} for x in occ]),use_container_width=True,hide_index=True)

    roles=teams_roles(ENGINE,a['id'])
    if roles:
        st.markdown('#### Intervenants Teams')
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
    st.success("Cette action peut comporter plusieurs intervenants. Ajouter un intervenant ne remplace pas les intervenants déjà affectés.")
    st.caption("Le référent coordonne l’action ; les co-intervenants et remplaçants restent rattachés selon leurs droits.")
    trainers=list_trainers(ENGINE,active_only=True)
    current=list_action_trainers(ENGINE,a['id'],active_only=True)
    if current:
        st.dataframe(pd.DataFrame([{
            'Intervenant':x['full_name'],'Email':x.get('email') or '',
            'Rôle action':x.get('role') or 'INTERVENANT','Référent':'Oui' if x.get('is_referent') else 'Non',
            'Gestion planning action':'Oui' if x.get('can_manage_planning') else 'Non',
            'Prescription outils':'Oui' if x.get('can_prescribe_tools') else 'Non'
        } for x in current]),use_container_width=True,hide_index=True)
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

    if trainers:
        opts={f"{t['full_name']} — {t.get('email') or 'sans email'}":t for t in trainers}
        with st.form(f'add_action_trainer_{a["id"]}'):
            c1,c2,c3=st.columns([3,2,1])
            lab=c1.selectbox('Ajouter un intervenant à cette action',list(opts),key=f'at_add_{a["id"]}')
            role=c2.selectbox('Rôle sur l’action',['INTERVENANT','REFERENT'],key=f'at_role_{a["id"]}')
            make_ref=c3.checkbox('Référent',value=role=='REFERENT',key=f'at_ref_{a["id"]}')
            reason=st.text_input('Motif / commentaire éventuel',key=f'at_reason_{a["id"]}')
            submit=st.form_submit_button('Ajouter / mettre à jour cet intervenant',type='primary')
        if submit:
            tr=opts[lab]; ref=make_ref or role=='REFERENT'
            ok,msg=assign_action_trainer(ENGINE,a['id'],tr['id'],st.session_state.admin_email,role='REFERENT' if ref else role,is_referent=ref,reason=reason or None)
            if ref:
                # Compatibility field remains synchronized, but existing co-intervenants are preserved.
                assign_trainer(ENGINE,a['id'],tr['id'],st.session_state.admin_email)
            if ok: st.success('Affectation action enregistrée.');rerun()
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
    if trainers:
        opts={f"{t['full_name']} — {t.get('email') or 'sans email'}":t for t in trainers}
        with st.form(f'slot_assign_{sl["id"]}'):
            c1,c2=st.columns(2)
            tlab=c1.selectbox('Intervenant',list(opts),key=f'st_add_tr_{sl["id"]}')
            srole=c2.selectbox('Rôle sur ce créneau',['PRINCIPAL','CO_INTERVENANT','REMPLACANT'],key=f'st_add_role_{sl["id"]}')
            sreason=st.text_input('Motif / commentaire',key=f'st_add_reason_{sl["id"]}')
            sadd=st.form_submit_button('Affecter à ce créneau',type='primary')
        if sadd:
            tr=opts[tlab];ok,msg=assign_slot_trainer(ENGINE,sl['id'],tr['id'],st.session_state.admin_email,srole,sreason or None)
            if ok: st.success('Affectation créneau enregistrée.');rerun()
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
                'Date':x['created_at'][:19].replace('T',' '),'Intervenant':x.get('full_name') or f"#{x.get('trainer_id')}",
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
            display.append({'Séance':i,'Date':x['slot_date'],'Début':x['start_time'],'Fin':x['end_time'],'Durée':slot_duration_hours(x),'Envoi initial':initial})
        st.dataframe(pd.DataFrame(display),use_container_width=True,hide_index=True)

    st.markdown('### Ajouter une nouvelle séance')
    last_date=date.fromisoformat(slots[-1]['slot_date']) if slots else date.today()
    last_start=dt_time.fromisoformat(slots[-1]['start_time']) if slots else dt_time(9,0)
    last_end=dt_time.fromisoformat(slots[-1]['end_time']) if slots else dt_time(10,30)
    with st.form(f'addslot_{a["id"]}',clear_on_submit=False):
        c1,c2,c3=st.columns(3)
        d=c1.date_input('Date de la nouvelle séance',value=last_date,key=f'd{a["id"]}')
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
    dst=st.date_input('Nouvelle date',value=src_date+__import__('datetime').timedelta(days=7),key=f'dup{a["id"]}')
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
            c1,c2,c3=st.columns(3);ed=c1.date_input('Date',value=date.fromisoformat(es['slot_date']));est=c2.time_input('Début',value=dt_time.fromisoformat(es['start_time']));eet=c3.time_input('Fin',value=dt_time.fromisoformat(es['end_time']))
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
        c1,c2,c3=st.columns(3);rpd=c1.date_input('Nouvelle date',value=date.fromisoformat(rsrc['slot_date']),key=f'rpd{rsrc["id"]}');rps=c2.time_input('Nouveau début',value=dt_time.fromisoformat(rsrc['start_time']),key=f'rps{rsrc["id"]}');rpe=c3.time_input('Nouvelle fin',value=dt_time.fromisoformat(rsrc['end_time']),key=f'rpe{rsrc["id"]}')
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
            evrows.append({'Nom':e['last_name'],'Prénom':e['first_name'],'Email':e.get('email') or '','Date séance':datetime.fromisoformat(e['slot_date']).strftime('%d/%m/%Y'),'Début':e['start_time'],'Fin':e['end_time'],'Type':e['event_type'],'Échéance (heure locale)':due,'Statut':e['status'],'Envoyé le':sent_local,'Dernière anomalie':friendly_mail_error(e.get('last_error'))})
        st.dataframe(pd.DataFrame(evrows),use_container_width=True,hide_index=True)
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
    comm=communication_journal(ENGINE,a['id'])
    if comm:
        status_labels={'A_ENVOYER':'À envoyer','EN_FILE':'En file','ENVOYE':'Envoyé','ECHEC':'Échec','RELANCE':'Relancé','ANNULE':'Annulé'}
        rows=[]
        for e in comm:
            who=(e.get('participant_first_name') or '')+' '+(e.get('participant_last_name') or '') if e.get('participant_id') else (e.get('trainer_name') or '')
            slot_label=(f"{e.get('slot_date')} {e.get('start_time')}–{e.get('end_time')}" if e.get('slot_date') else '')
            rows.append({'Type':e['communication_type'],'Destinataire':who.strip() or e.get('recipient_email') or '','Email':e.get('recipient_email') or '','Créneau':slot_label,'Déclenchement':'Automatique' if e.get('trigger_mode')=='AUTO' else 'Manuel','Statut':status_labels.get(e.get('status'),e.get('status')),'Prévu':e.get('due_at') or '','Envoyé':e.get('sent_at') or '','Anomalie':friendly_mail_error(e.get('last_error'))})
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
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
        absent=q(ENGINE,"""SELECT p.* FROM attendance_status x JOIN participants p ON p.id=x.participant_id WHERE x.slot_id=:s AND x.status='ABSENT'""",{'s':ss['id']});opts={f"{p['last_name']} {p['first_name']}":p['id'] for p in absent};sel=st.multiselect('Absents concernés',list(opts),default=list(opts));c1,c2,c3=st.columns(3);rd=c1.date_input('Date du rattrapage',key=f'rd{a["id"]}');rs=c2.time_input('Début rattrapage',value=dt_time(9,0),key=f'rs{a["id"]}');re=c3.time_input('Fin rattrapage',value=dt_time(12,0),key=f're{a["id"]}')
        if st.button('Créer le créneau de rattrapage',key=f'catch{a["id"]}'):
            if not sel: st.error('Sélectionnez au moins un participant absent.')
            else: ns=create_catchup_slot(ENGINE,ss['id'],rd.isoformat(),rs.strftime('%H:%M'),re.strftime('%H:%M'),[opts[x] for x in sel],st.session_state.admin_email);ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ);st.success(f'Rattrapage créé : créneau #{ns}.');rerun()

def quality_tab(a):
    st.subheader('Évaluations qualité')
    enabled=[]
    if a.get('use_quality_hot'): enabled.append('à chaud')
    if a.get('use_quality_cold'): enabled.append('à froid')
    if a.get('use_trainer_feedback'): enabled.append('retour intervenant')
    if not enabled:
        st.info("Aucun module qualité n'est activé pour cette action. Vous pouvez les activer dans « Paramètres action ».")
        return
    st.caption('Modules activés : '+', '.join(enabled)+'. Les campagnes utilisent les questionnaires standard V2 versionnés et les rubriques analytiques fixes Rxx/Ixx.')
    try:
        end_due=standard_quality_due(ENGINE,a['id'],'HOT')
        ref_end=local_dt(end_due,organization_runtime_config(ENGINE,a['id'])['timezone'])
        end_date=ref_end.date().isoformat()
    except ValueError:
        end_date=None
    if not end_date:
        st.warning("Ajoutez un calendrier ou renseignez une date de fin de l'action avant de préparer les campagnes qualité.")
    else:
        st.write(f"Date de fin de référence : **{datetime.fromisoformat(end_date).strftime('%d/%m/%Y')}** (dernière séance planifiée lorsqu’un calendrier existe)")
        if a.get('use_quality_cold'):
            pt=(a.get('prestation_type') or 'FORMATION').upper();label='M+6' if pt=='BILAN_COMPETENCES' else 'J+90 (ou date spécifique si renseignée)'
            st.caption(f'Échéance standard à froid : {label}.')
        if st.button('Préparer les campagnes qualité standard',type='primary',key=f'prepquality{a["id"]}',disabled=not bool(end_date)):
            try:
                made=prepare_quality_campaigns(ENGINE,a['id'],BASE_URL,st.session_state.admin_email)
                if made: st.success(f'{len(made)} campagne(s) créée(s) et planifiée(s).')
                else: st.info('Toutes les campagnes nécessaires étaient déjà préparées. Les échéances encore en attente ont été réalignées sur le calendrier actuel.')
                rerun()
            except ValueError as ex: st.error(str(ex))
    campaigns=list_quality_campaigns(ENGINE,a['id'])
    if campaigns:
        rows=[]
        tzname=organization_runtime_config(ENGINE,a['id'])['timezone']
        for c in campaigns:
            who=c.get('trainer_full_name') or f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip()
            due=local_dt(c['due_at'],tzname)
            rows.append({'ID':c['id'],'Type':c['campaign_kind'],'Questionnaire':c['questionnaire_title'],'Répondant':who,'Échéance':due.strftime('%d/%m/%Y %H:%M'),'Statut':c['status']})
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        cmap={f"#{c['id']} — {c['campaign_kind']} — {(c.get('trainer_full_name') or ((c.get('first_name') or '')+' '+(c.get('last_name') or '')).strip())}":c for c in campaigns}
        selected=cmap[st.selectbox('Campagne à consulter',list(cmap),key=f'qcamp{a["id"]}')]
        st.code(quality_token_url(selected['token'],BASE_URL))
        c1,c2=st.columns(2)
        if c1.button('Relancer manuellement ce questionnaire',key=f'qsend{selected["id"]}',disabled=selected['status']=='COMPLETED'):
            try:
                queue_quality_manual_reminder(ENGINE,selected['id'],st.session_state.admin_email)
                st.success('Relance manuelle placée dans la file du worker. Le même questionnaire et le même lien sont réutilisés.');rerun()
            except ValueError as ex: st.warning(str(ex))
        if selected['status']=='COMPLETED':
            try:
                qpdf=quality_response_pdf(ENGINE,selected['id'])
                c2.download_button('Télécharger le questionnaire PDF',qpdf,f"{a['action_no']}_questionnaire_{selected['id']}.pdf",'application/pdf',use_container_width=True)
            except Exception as ex: _ui_incident('pdf_qualite',ex,subject='Le PDF qualité')
    issues=list_quality_issues(ENGINE,a['id'])
    st.markdown('#### Difficultés, aléas, réclamations et amélioration')
    with st.expander('Créer une fiche manuellement'):
        with st.form(f'issue_new_{a["id"]}'):
            it=st.selectbox('Type',['DIFFICULTE_ALEA','RECLAMATION','INCIDENT']); title=st.text_input('Titre'); desc=st.text_area('Description'); owner=st.text_input('Responsable'); ok=st.form_submit_button('Créer la fiche')
        if ok and title.strip(): create_quality_issue(ENGINE,a['id'],it,title.strip(),desc,owner,st.session_state.admin_email);rerun()
    if issues:
        imap={f"#{i['id']} — {i['issue_type']} — {i['title']} — {i['status']}":i for i in issues}; il=st.selectbox('Fiche à suivre',list(imap),key=f'issue_sel_{a["id"]}'); ii=imap[il]
        c1,c2=st.columns(2); ns=c1.selectbox('Statut',['OUVERTE','EN_COURS','CLOTUREE'],index=['OUVERTE','EN_COURS','CLOTUREE'].index(ii['status']) if ii['status'] in ['OUVERTE','EN_COURS','CLOTUREE'] else 0,key=f'is_{ii["id"]}'); own=c2.text_input('Responsable',value=ii.get('owner') or '',key=f'io_{ii["id"]}')
        if st.button('Mettre à jour la fiche',key=f'iu_{ii["id"]}'): update_quality_issue(ENGINE,ii['id'],ns,own,st.session_state.admin_email);rerun()
        with st.form(f'imp_new_{ii["id"]}'):
            tt=st.text_input('Action d’amélioration'); dd=st.text_area('Description de l’action'); oo=st.text_input('Responsable action'); due=st.date_input('Échéance',value=None); addi=st.form_submit_button('Ajouter l’action d’amélioration')
        if addi and tt.strip(): create_improvement_action(ENGINE,a['id'],tt.strip(),dd,oo,due.isoformat() if due else None,ii['id'],st.session_state.admin_email);rerun()
    imps=q(ENGINE,'SELECT * FROM improvement_actions WHERE action_id=:a ORDER BY id DESC',{'a':a['id']})
    if imps: st.dataframe(pd.DataFrame(imps)[['id','title','owner','due_at','status','completed_at']],use_container_width=True,hide_index=True)
    if issues:
        st.markdown('### Difficultés / aléas / réclamations détectés')
        st.dataframe(pd.DataFrame(issues),use_container_width=True,hide_index=True)
    tr_reports=q(ENGINE,"""SELECT r.*,t.full_name source_name FROM trainer_reports r JOIN trainers t ON t.id=r.trainer_id WHERE r.action_id=:a ORDER BY r.created_at DESC""",{'a':a['id']})
    br_reports=beneficiary_reports(ENGINE,action_id=a['id'])
    if tr_reports or br_reports:
        st.markdown('### Signalements liés à cette action')
        rr=[]
        for x in tr_reports: rr.append({'Date':x['created_at'][:16].replace('T',' '),'Source':'Intervenant','Personne':x.get('source_name') or '','Objet':x['subject'],'Statut':x['status'],'Réponse administration':x.get('admin_response') or ''})
        for x in br_reports: rr.append({'Date':x['created_at'][:16].replace('T',' '),'Source':'Bénéficiaire','Personne':f"{x.get('beneficiary_first_name') or ''} {x.get('beneficiary_last_name') or ''}".strip(),'Objet':x['subject'],'Statut':x['status'],'Réponse administration':x.get('admin_response') or ''})
        st.dataframe(pd.DataFrame(rr),use_container_width=True,hide_index=True)

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
        st.caption(f"Action sélectionnée : {a['action_no']}. Le document de cours sera visible par tous les bénéficiaires de cette action disposant d’un espace personnel.")
        category=st.selectbox('Catégorie',['COURS','ADMINISTRATIF'],format_func=lambda x:'Documents de cours' if x=='COURS' else 'Document administratif',key=f'doccat_{a["id"]}')
        updoc=st.file_uploader('Fichier (25 Mo maximum)',type=['pdf','json','doc','docx','xls','xlsx','ppt','pptx','txt','csv','jpg','jpeg','png','webp','zip'],key=f'action_doc_{a["id"]}')
        if st.button('DÉPOSER LE DOCUMENT',type='primary',key=f'action_doc_btn_{a["id"]}',disabled=updoc is None):
            try:
                rid,h,dedup=store_document(ENGINE,updoc.getvalue(),updoc.name,category,st.session_state.admin_email,action_id=a['id'],audience='ACTION_BENEFICIARIES')
                st.success('Document enregistré. '+('Déduplication SHA-256 : le fichier physique existait déjà.' if dedup else 'Nouveau contenu physique enregistré.'));rerun()
            except Exception as ex: _ui_incident('operation_interface',ex)
    refs=list_action_documents(ENGINE,a['id'])
    if refs:
        st.dataframe(pd.DataFrame([{'Nom':d['display_name'],'Catégorie':d['category'],'Taille (Ko)':round(d['size_bytes']/1024,1),'SHA-256':d['sha256'][:16]+'…','Déposé par':d.get('uploaded_by') or ''} for d in refs]),use_container_width=True,hide_index=True)
        rmap={f"#{d['id']} — {d['display_name']}":d for d in refs};rl=st.selectbox('Document à gérer',list(rmap),key=f'docref_{a["id"]}');rr=rmap[rl];path=Path(rr['storage_path'])
        cdl,cdel=st.columns(2)
        if path.is_file(): cdl.download_button('Télécharger',path.read_bytes(),file_name=rr['display_name'],key=f'adm_doc_dl_{rr["id"]}',use_container_width=True)
        if cdel.button('Retirer de cette action',key=f'adm_doc_del_{rr["id"]}',use_container_width=True): delete_document_reference(ENGINE,rr['id'],st.session_state.admin_email);st.success('Référence retirée. Le fichier physique n’est supprimé que s’il n’est plus utilisé ailleurs.');rerun()
    else: st.info('Aucun document de bibliothèque pour cette action.')

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
        st.dataframe(pd.DataFrame([{'Action':r['action_no'],'Date':r['slot_date'],'Horaire':f"{r['start_time']}–{r['end_time']}",'Participant':f"{r['last_name']} {r['first_name']}",'Email':r.get('email') or ''} for r in arows]),use_container_width=True,hide_index=True)
        st.caption('La régularisation elle-même reste réalisée dans la fiche de l’action afin de conserver les contrôles de preuve et d’absence existants.')
    footer()

def quality_management_screen():
    header('Clarté360 — Qualité','Pilotage métier des évaluations, signalements, difficultés et améliorations')
    orgs=list_organizations(ENGINE,active_only=True); om={'Tous':None,**{o['name']:o['id'] for o in orgs}}
    c1,c2,c3=st.columns(3)
    ol=c1.selectbox('Organisme',list(om),key='qm_org')
    pt=c2.selectbox('Prestation',['Tous','FORMATION','BILAN_COMPETENCES','VAE','COACHING','MENTORAT','AUTRE'],key='qm_pt')
    aq=q(ENGINE,'SELECT id,action_no,title,organization_id,prestation_type FROM actions ORDER BY action_no')
    if om[ol]: aq=[x for x in aq if x.get('organization_id')==om[ol]]
    if pt!='Tous': aq=[x for x in aq if (x.get('prestation_type') or '').upper()==pt]
    amap={'Toutes les actions':None,**{f"{x['action_no']} — {x['title']}":x['id'] for x in aq}}
    al=c3.selectbox('Action',list(amap),key='qm_action')
    action_id=amap[al]
    filters={'organization_id':om[ol],'prestation_type':None if pt=='Tous' else pt}
    j2=quality_dashboard_v31(ENGINE,organization_id=om[ol],prestation_type=None if pt=='Tous' else pt,action_id=action_id)
    st.markdown('### Tableau de bord Qualité J2')
    k1,k2,k3,k4,k5=st.columns(5)
    k1.metric('Événements ouverts',j2['events_open']);k2.metric('Réclamations',j2['complaints_open']);k3.metric('Non-conformités',j2['nc_open']);k4.metric('Points ≤ 3',j2['review_points']);k5.metric('Actions en retard',j2['overdue_actions'])
    score_cols=st.columns(5)
    for col,(kind,label) in zip(score_cols,[('HOT','À chaud'),('COLD','À froid'),('TRAINER','Intervenant'),('CLIENT','Client / prescripteur'),('OPCO','OPCO')]):
        x=j2['by_kind'][kind]; score='—' if x['score'] is None else f"{x['score']:.2f}/5"
        col.metric(label,score,f"{x['responses']}/{x['invitations']} réponse(s)" if x['invitations'] else 'Aucune invitation')
    qd=quality_management_summary(ENGINE,**filters)
    c1,c2,c3,c4=st.columns(4)
    for c,n,l in [(c1,qd['campaigns'],'Questionnaires prévus'),(c2,f"{qd['response_rate']}%",'Taux de réponse'),(c3,qd['issues_open'],'Difficultés ouvertes'),(c4,qd['improvements_open'],'Améliorations ouvertes')]:
        c.markdown(f"<div class='c360-kpi'><div class='n'>{n}</div><div class='l'>{l}</div></div>",unsafe_allow_html=True)

    st.markdown('### Lecture synthétique par thème')
    stats=quality_question_stats(ENGINE,organization_id=om[ol],prestation_type=None if pt=='Tous' else pt,action_id=action_id)
    rubrics={}
    for r in stats:
        rubrics.setdefault(r['Rubrique'],[]).append(r)
    if not rubrics:
        st.info('Aucune réponse exploitable avec ces filtres.')
    else:
        summary=[]
        for rub,items in rubrics.items():
            vals=[x['Moyenne'] for x in items if x.get('Moyenne') is not None]
            summary.append({'Thème':rub,'Questions':len(items),'Réponses':sum(int(x.get('Réponses') or 0) for x in items),'Moyenne':round(sum(vals)/len(vals),2) if vals else None})
        st.dataframe(pd.DataFrame(summary),use_container_width=True,hide_index=True)
        rub=st.selectbox('Explorer un thème',list(rubrics),key='qm_rubric')
        with st.expander(f'Détail du thème — {rub}',expanded=False):
            st.dataframe(pd.DataFrame(rubrics[rub])[['Question','Réponses','Moyenne']],use_container_width=True,hide_index=True)

    if action_id:
        st.markdown('### Détail de l’action sélectionnée')
        camps=list_quality_campaigns(ENGINE,action_id)
        if camps:
            campaign_rows=[]
            for x in camps:
                hist=quality_campaign_email_history(ENGINE,x['id']); sent=[h for h in hist if h.get('sent_at')]
                campaign_rows.append({'Type':x['campaign_kind'],'Questionnaire':x['questionnaire_title'],'Statut':x['status'],'Disponibilité':quality_campaign_availability(x),'Échéance':x.get('due_at') or '',
                  'Invitation initiale':next((h.get('sent_at') for h in hist if h['event_type']=='INITIAL' and h.get('sent_at')),'—'),'Dernière relance':next((h.get('sent_at') for h in reversed(hist) if h['event_type'].startswith('MANUAL_') and h.get('sent_at')),'—'),
                  'Nb relances':sum(1 for h in hist if h['event_type'].startswith('MANUAL_') and h.get('sent_at')),'Réponse':x.get('completed_at') or '—'})
            st.dataframe(pd.DataFrame(campaign_rows),use_container_width=True,hide_index=True)
        else: st.info('Aucune campagne qualité sur cette action.')

    st.markdown('### Événements qualité et CAPA')
    evs=list_quality_events(ENGINE,action_id=action_id) if action_id else list_quality_events(ENGINE)
    if evs:
        st.dataframe(pd.DataFrame([{'Réf.':e['public_id'],'Action':e.get('action_no') or '—','Intitulé':e.get('action_title') or '—','Personne / origine':e.get('source_name') or e.get('origin') or '—','Type':e['event_type'],'Objet':e['subject'],'Gravité':e['severity'],'Statut':e['status'],'Responsable':e.get('owner_name') or '','Échéance':e.get('due_at') or ''} for e in evs]),use_container_width=True,hide_index=True)
        em={f"{e['public_id']} — {e.get('action_no') or 'sans action'} — {e['subject']}":e for e in evs}
        el=st.selectbox('Ouvrir / traiter une fiche qualité',list(em),key='j2_event_open'); ev=em[el]
        with st.expander(f"Fiche {ev['public_id']} — traitement jusqu’à clôture",expanded=True):
            st.caption(f"Action : {ev.get('action_no') or '—'} — {ev.get('action_title') or '—'} · Origine : {ev.get('source_name') or ev.get('origin') or '—'} · Créée : {ev.get('detected_at') or ev.get('created_at')}")
            st.write(ev.get('description') or 'Aucune description.')
            statuses=['NOUVEAU','A_ANALYSER','EN_TRAITEMENT','EN_ATTENTE','A_VERIFIER','CLOTURE','CLASSE_SANS_SUITE','REFUSE']
            c1,c2,c3=st.columns(3); es=c1.selectbox('Statut',statuses,index=statuses.index(ev['status']) if ev['status'] in statuses else 0,key=f"evs_{ev['id']}"); owner=c2.text_input('Responsable',value=ev.get('owner_name') or '',key=f"evo_{ev['id']}"); due=c3.text_input('Échéance',value=ev.get('due_at') or '',key=f"evd_{ev['id']}")
            qual=st.text_area('Qualification / analyse',value=ev.get('qualification') or '',key=f"evq_{ev['id']}"); imm=st.text_area('Action immédiate',value=ev.get('immediate_action') or '',key=f"evi_{ev['id']}"); cause=st.text_area('Analyse de cause',value=ev.get('cause_analysis') or '',key=f"evc_{ev['id']}")
            ec=st.text_area("Critères de vérification d'efficacité",value=ev.get('effectiveness_criteria') or '',key=f"evec_{ev['id']}"); er=st.text_area("Résultat de la vérification d'efficacité",value=ev.get('effectiveness_result') or '',key=f"ever_{ev['id']}"); close=st.text_area('Conclusion / motif de clôture ou classement',value=ev.get('closure_comment') or '',key=f"evcl_{ev['id']}")
            if st.button('ENREGISTRER LA FICHE',type='primary',key=f"evsave_{ev['id']}"):
                try:
                    update_quality_event(ENGINE,ev['id'],st.session_state.admin_email,status=es,owner_name=owner,severity=ev.get('severity'),urgency=ev.get('urgency'),due_at=due or None,qualification=qual,immediate_action=imm,cause_analysis=cause,effectiveness_criteria=ec,effectiveness_result=er,closure_comment=close)
                    st.success('Fiche qualité enregistrée et historisée.'); rerun()
                except ValueError as ex: st.error(str(ex))
            st.markdown('#### Actions correctives / préventives (CAPA)')
            capas=quality_event_actions(ENGINE,ev['id'])
            if capas:
                st.dataframe(pd.DataFrame([{'ID':x['id'],'Type':x['action_kind'],'Action':x['title'],'Responsable':x.get('owner_name') or '','Échéance':x.get('due_at') or '','Statut':x['status'],'Efficacité':x.get('effectiveness_result') or ''} for x in capas]),use_container_width=True,hide_index=True)
                cm={f"#{x['id']} — {x['title']}":x for x in capas}; cl=st.selectbox('Action CAPA à mettre à jour',list(cm),key=f"capa_sel_{ev['id']}"); ca=cm[cl]
                c1,c2=st.columns(2); cas=c1.selectbox('Statut CAPA',['A_FAIRE','EN_COURS','EN_ATTENTE','TERMINEE'],index=['A_FAIRE','EN_COURS','EN_ATTENTE','TERMINEE'].index(ca['status']) if ca['status'] in ['A_FAIRE','EN_COURS','EN_ATTENTE','TERMINEE'] else 0,key=f"capas_{ca['id']}"); cao=c2.text_input('Responsable CAPA',value=ca.get('owner_name') or '',key=f"capao_{ca['id']}")
                caer=st.text_area("Preuve / résultat d'efficacité CAPA",value=ca.get('effectiveness_result') or '',key=f"capaer_{ca['id']}")
                if st.button('METTRE À JOUR CETTE ACTION',key=f"capau_{ca['id']}"):
                    update_quality_event_action(ENGINE,ca['id'],st.session_state.admin_email,status=cas,owner_name=cao,effectiveness_result=caer); st.success('Action CAPA mise à jour.'); rerun()
            with st.form(f"new_capa_{ev['id']}",clear_on_submit=True):
                ct=st.text_input('Nouvelle action corrective / préventive'); co=st.text_input('Responsable'); cd=st.text_input('Échéance'); csub=st.form_submit_button('AJOUTER AU PLAN D’ACTION')
            if csub and ct.strip(): add_quality_event_action(ENGINE,ev['id'],ct.strip(),st.session_state.admin_email,owner_name=co.strip() or None,due_at=cd.strip() or None); st.success('Action ajoutée au plan général.'); rerun()
    else: st.info('Aucun événement qualité avec ces filtres.')
    with st.expander('Créer un événement qualité',expanded=False):
        if aq:
            emap={f"{x['action_no']} — {x['title']}":x['id'] for x in aq}; ea=st.selectbox('Action concernée',list(emap),key='j2_ev_action')
            fam=st.selectbox('Famille',['EXPRESSION','CONFORMITE','QUESTIONNAIRES','AUDIT','TECHNIQUE','AMELIORATION'],key='j2_ev_family')
            typ=st.selectbox('Type',['INFORMATION','OBSERVATION','SUGGESTION','DIFFICULTE','RECLAMATION','NON_CONFORMITE','INCIDENT','ECART_DOCUMENTAIRE','ECART_ORGANISATIONNEL','OPPORTUNITE'],key='j2_ev_type')
            subj=st.text_input('Objet',key='j2_ev_subject');desc=st.text_area('Description factuelle',key='j2_ev_desc');sev=st.selectbox('Gravité',['MINEURE','MAJEURE','CRITIQUE'],key='j2_ev_sev')
            if st.button('CRÉER LA FICHE QUALITÉ',type='primary',disabled=not subj.strip(),key='j2_ev_create'):
                create_quality_event(ENGINE,fam,typ,subj.strip(),desc.strip(),st.session_state.admin_email,action_id=emap[ea],severity=sev);st.success('Fiche qualité créée et historisée.');rerun()
    pts=quality_review_points(ENGINE,action_id=action_id,open_only=True)
    if pts:
        st.markdown('#### Points à examiner — notes ≤ 3')
        st.dataframe(pd.DataFrame([{'ID':p['id'],'Action':p['action_no'],'Intitulé':p.get('action_title') or '','Type':p['campaign_kind'],'Question':p['question_text'],'Note':p['score'],'Statut':p['status']} for p in pts]),use_container_width=True,hide_index=True)
        pm={f"#{p['id']} — {p['action_no']} — note {p['score']} — {p['question_text'][:60]}":p for p in pts}; pl=st.selectbox('Point à examiner',list(pm),key='review_point_sel'); rp=pm[pl]
        dec=st.selectbox('Décision',['CLASSE','EVENEMENT_CREE','RETOUR_DEMANDE'],key=f"rpd_{rp['id']}"); com=st.text_area('Analyse / motif / retour demandé',key=f"rpc_{rp['id']}")
        if st.button('TRAITER CE POINT',type='primary',key=f"rps_{rp['id']}"):
            qev=None
            if dec=='EVENEMENT_CREE': qev=create_quality_event(ENGINE,'QUESTIONNAIRES','DIFFICULTE',f"Point à examiner — {rp['question_text'][:100]}",f"Note {rp['score']}/5. {com}",st.session_state.admin_email,action_id=rp['action_id'],campaign_id=rp['campaign_id'],origin='QUESTIONNAIRE')
            review_quality_point(ENGINE,rp['id'],dec,com,st.session_state.admin_email,qev); st.success('Point examiné et décision historisée.'); rerun()

    st.markdown('### Signalements à traiter et historique')
    trainer_rows=q(ENGINE,"""SELECT r.*,a.action_no,a.title action_title,t.full_name source_name FROM trainer_reports r
      JOIN actions a ON a.id=r.action_id JOIN trainers t ON t.id=r.trainer_id ORDER BY r.created_at DESC""")
    benef_rows=beneficiary_reports(ENGINE)
    combined=[]
    for r in trainer_rows:
        combined.append({'kind':'TRAINER','id':r['id'],'action_id':r['action_id'],'Action':r['action_no'],'Source':'Intervenant','Personne':r.get('source_name') or '','Nature':r['report_type'],'Objet':r['subject'],'Description':r['description'],'Statut':r['status'],'Réponse':r.get('admin_response') or '','Date':r['created_at']})
    for r in benef_rows:
        combined.append({'kind':'BENEFICIARY','id':r['id'],'action_id':r['action_id'],'Action':r['action_no'],'Source':'Bénéficiaire','Personne':f"{r.get('beneficiary_first_name') or ''} {r.get('beneficiary_last_name') or ''}".strip(),'Nature':r['report_type'],'Objet':r['subject'],'Description':r['description'],'Statut':r['status'],'Réponse':r.get('admin_response') or '','Date':r['created_at']})
    if om[ol]:
        allowed={x['id'] for x in q(ENGINE,'SELECT id FROM actions WHERE organization_id=:o',{'o':om[ol]})}; combined=[x for x in combined if x['action_id'] in allowed]
    if pt!='Tous':
        allowed={x['id'] for x in q(ENGINE,'SELECT id FROM actions WHERE prestation_type=:p',{'p':pt})}; combined=[x for x in combined if x['action_id'] in allowed]
    if action_id: combined=[x for x in combined if x['action_id']==action_id]
    status_filter=st.selectbox('Afficher les signalements',['Tous','NOUVEAU','EN_COURS','TRAITE','CLOTURE'],key='qm_report_status')
    if status_filter!='Tous': combined=[x for x in combined if x['Statut']==status_filter]
    if not combined:
        st.info('Aucun signalement avec ces filtres.')
    else:
        st.dataframe(pd.DataFrame([{'Date':x['Date'][:16].replace('T',' '),'Action':x['Action'],'Source':x['Source'],'Personne':x['Personne'],'Nature':x['Nature'],'Objet':x['Objet'],'Statut':x['Statut']} for x in combined]),use_container_width=True,hide_index=True)
        rmap={f"{x['Action']} — {x['Source']} — {x['Objet']} — #{x['id']}":x for x in combined}; rl=st.selectbox('Fiche à traiter',list(rmap),key='qm_report_select'); rr=rmap[rl]
        st.write(rr['Description'])
        c1,c2=st.columns([1,2]); ns=c1.selectbox('Statut',['NOUVEAU','EN_COURS','TRAITE','CLOTURE'],index=['NOUVEAU','EN_COURS','TRAITE','CLOTURE'].index(rr['Statut']) if rr['Statut'] in ['NOUVEAU','EN_COURS','TRAITE','CLOTURE'] else 0,key=f"qm_rep_status_{rr['kind']}_{rr['id']}")
        response=c2.text_area('Réponse / traitement de l’administration',value=rr.get('Réponse') or '',key=f"qm_rep_resp_{rr['kind']}_{rr['id']}")
        if st.button('ENREGISTRER LE TRAITEMENT',key=f"qm_rep_save_{rr['kind']}_{rr['id']}",type='primary'):
            ok,msg=update_user_report(ENGINE,rr['kind'],rr['id'],ns,response,st.session_state.admin_email)
            if ok: st.success('Fiche mise à jour. Elle reste conservée dans l’historique.');rerun()
            else: st.warning(msg)

    issues=list_quality_issues(ENGINE,action_id) if action_id else list_quality_issues(ENGINE)
    if om[ol] and not action_id:
        aids={x['id'] for x in q(ENGINE,'SELECT id FROM actions WHERE organization_id=:o',{'o':om[ol]})};issues=[x for x in issues if x.get('action_id') in aids]
    if issues:
        with st.expander('Historique qualité ancien format',expanded=False):
            st.dataframe(pd.DataFrame(issues),use_container_width=True,hide_index=True)
    st.markdown("### Suivi du plan d'action général")
    plan=quality_general_action_plan(ENGINE,action_id=action_id)
    if plan:
        st.dataframe(pd.DataFrame([{'N°':x['id'],'Événement':x['event_ref'],'Origine':x.get('origin') or '','Date':x.get('detected_at') or '','Action':x.get('action_no') or '—','Intitulé':x.get('action_title') or '—','Personne':x.get('source_name') or '—','Type':x.get('event_type') or '','Point':x.get('subject') or '','Action décidée':x.get('action_title_capa') or '','Responsable':x.get('owner_name') or '','Échéance':x.get('due_at') or '','Statut':x.get('status') or '','Efficacité':x.get('effectiveness_result') or ''} for x in plan]),use_container_width=True,hide_index=True)
    else: st.info("Aucune action qualité consolidée dans le plan d'action général.")
    footer()

def studies_screen():
    header('Clarté360 — Études PIP/O*NET','Pilotage méthodologique pseudonymisé')
    study_dir=secret('pip_connector','study_dir','')
    if not study_dir:
        st.info("Le répertoire d'études PIP n'est pas encore configuré. Il sera raccordé aux données persistantes PIP lors de la recette VPS.")
        footer(); return
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
    if hist: st.dataframe(pd.DataFrame(hist),use_container_width=True,hide_index=True)
    footer()


def crm_screen():
    header('Clarté360 — Contacts / Prospects','CRM léger séparé des données de recherche')
    st.caption("Le consentement marketing est indépendant du consentement recherche. Une conversion en bénéficiaire contrôle les doublons avant toute création.")
    with st.expander('Ajouter un contact / prospect', expanded=False):
        with st.form('crm_add_contact'):
            c1,c2=st.columns(2); fn=c1.text_input('Prénom *'); ln=c2.text_input('Nom *')
            c1,c2=st.columns(2); em=c1.text_input('E-mail *'); ph=c2.text_input('Téléphone')
            c1,c2=st.columns(2); job=c1.text_input('Fonction'); comp=c2.text_input('Entreprise')
            interests=st.text_input("Centres d'intérêt (séparés par des virgules)")
            marketing=st.checkbox('Consentement marketing explicite recueilli')
            rgpd=st.text_input("Version de l'information RGPD",value='I9-G')
            add=st.form_submit_button('AJOUTER LE CONTACT',type='primary')
        if add:
            try:
                create_crm_contact(ENGINE,fn,ln,em,phone=ph or None,job_title=job or None,company=comp or None,
                                   interests=[x.strip() for x in interests.split(',') if x.strip()],marketing_consent=marketing,
                                   rgpd_notice_version=rgpd or None,actor=st.session_state.admin_email)
                st.success('Contact ajouté.'); rerun()
            except ValueError as ex: st.error(str(ex))
    rows=list_crm_contacts(ENGINE)
    if not rows:
        st.info('Aucun contact / prospect enregistré.'); footer(); return
    st.dataframe(pd.DataFrame([{'ID':x['public_id'],'Nom':f"{x['first_name']} {x['last_name']}",'E-mail':x['email'],
      'Téléphone':x.get('phone') or '','Entreprise':x.get('company') or '','Marketing':'Oui' if x.get('marketing_consent') else 'Non',
      'Statut':x['status'].replace('_',' '),'Bénéficiaire':x.get('beneficiary_public_id') or ''} for x in rows]),use_container_width=True,hide_index=True)
    cmap={f"{x['public_id']} — {x['first_name']} {x['last_name']} — {x['email']}":x for x in rows}
    label=st.selectbox('Contact à gérer',list(cmap)); c=cmap[label]
    c1,c2=st.columns(2)
    statuses=['NOUVEAU','A_CONTACTER','CONTACTE','CONVERTI','SANS_SUITE']
    ns=c1.selectbox('Statut CRM',statuses,index=statuses.index(c['status']) if c['status'] in statuses else 0)
    if c1.button('Enregistrer le statut'):
        update_crm_status(ENGINE,c['id'],ns,st.session_state.admin_email); st.success('Statut mis à jour.'); rerun()
    consent=c2.checkbox('Consentement marketing',value=bool(c.get('marketing_consent')),key=f"crm_consent_{c['id']}")
    if c2.button('Enregistrer le consentement',key=f"crm_consent_save_{c['id']}"):
        set_crm_marketing_consent(ENGINE,c['id'],consent,st.session_state.admin_email,c.get('rgpd_notice_version') or 'I9-G')
        st.success('Consentement mis à jour et tracé.'); rerun()
    if not c.get('beneficiary_id'):
        st.markdown('#### Conversion en bénéficiaire')
        bd=st.date_input('Date de naissance pour contrôle anti-doublon',value=None,key=f"crm_bd_{c['id']}")
        if st.button('CONVERTIR / RATTACHER AU BÉNÉFICIAIRE',disabled=bd is None,key=f"crm_convert_{c['id']}"):
            try:
                b=convert_crm_contact_to_beneficiary(ENGINE,c['id'],bd.isoformat(),st.session_state.admin_email)
                st.success(f"Contact rattaché à {b['public_id']}."); rerun()
            except ValueError as ex: st.error(str(ex))
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
          'JSON':x.get('json_ref') or '','Mis à jour':x['updated_at'][:16].replace('T',' ')} for x in cases]),use_container_width=True,hide_index=True)
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


def settings_screen():
    header('Clarté360 — Paramètres','Administration de l’application')
    tabg,tabo,tabag,tabi,taba,tabt,tabdiag=st.tabs(['Général','Organisme','Agences / établissements','Imports','Administrateurs','Formateurs / accompagnants','Diagnostic I9'])
    with tabg:
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
            c1,c2=st.columns(2); general_email=c1.text_input('Email général',value=org.get('general_email') or ''); tz=c2.text_input('Fuseau horaire IANA',value=org.get('timezone') or 'Europe/Paris')
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
    with tabt:
        st.subheader('Formateurs / accompagnants référencés')
        trainers=list_trainers(ENGINE)
        tf=st.session_state.pop('_trainer_flash',None)
        if tf:
            if tf[0]=='success': st.success(tf[1])
            else: st.warning(tf[1])
        if trainers: st.dataframe(pd.DataFrame(trainers)[['id','full_name','email','phone','active']],use_container_width=True,hide_index=True)
        with st.expander('Ajouter un formateur / accompagnant',expanded=not trainers):
            with st.form('add_trainer'):
                n=st.text_input('Nom et prénom *');e=st.text_input('Email');ph=st.text_input('Téléphone');add=st.form_submit_button('Ajouter au référentiel')
            if add:
                if not n.strip(): st.error('Nom obligatoire.')
                else:
                    try:
                        tid=add_trainer(ENGINE,n,e,ph,st.session_state.admin_email)
                        if e.strip():
                            token=create_trainer_invitation(ENGINE,tid,st.session_state.admin_email)
                            tr=one(ENGINE,'SELECT * FROM trainers WHERE id=:i',{'i':tid})
                            okm,msgm=send_trainer_invitation_email(tr,token) if token else (False,'Invitation non créée.')
                            st.session_state['_trainer_flash']=('success' if okm else 'warning',msgm)
                        else:
                            st.session_state['_trainer_flash']=('warning','Intervenant ajouté sans email : aucun accès personnel ne peut être créé tant qu’une adresse email n’est pas renseignée.')
                        rerun()
                    except ValueError as ex: st.error(str(ex))
                    except Exception as ex: _ui_incident('gestion_intervenant',ex,subject='Cette opération intervenant')
        if trainers:
            tmap={f"{x['full_name']} — {x.get('email') or 'sans email'}":x for x in trainers};tl=st.selectbox('Intervenant à gérer',list(tmap),key='tr_manage');tt=tmap[tl]
            allow_docs=st.checkbox('Autoriser cet intervenant à déposer des documents de cours sur ses actions',value=bool(tt.get('can_upload_documents')),key=f'tr_doc_perm_{tt["id"]}')
            if allow_docs!=bool(tt.get('can_upload_documents')):
                execute(ENGINE,'UPDATE trainers SET can_upload_documents=:v,updated_at=:u WHERE id=:i',{'v':1 if allow_docs else 0,'u':utcnow_iso(),'i':tt['id']});audit(ENGINE,'TRAINER_DOCUMENT_PERMISSION_CHANGED',actor=st.session_state.admin_email,entity_type='trainer',entity_id=tt['id'],details={'allowed':allow_docs});rerun()
            c1,c2,c3=st.columns(3)
            if c1.button('Désactiver' if tt['active'] else 'Réactiver',key='tr_toggle'): set_trainer_active(ENGINE,tt['id'],not bool(tt['active']),st.session_state.admin_email);rerun()
            if c2.button('Envoyer / renouveler l’invitation d’accès',key='tr_invite',disabled=not bool(tt.get('email'))):
                token=create_trainer_invitation(ENGINE,tt['id'],st.session_state.admin_email)
                okm,msgm=send_trainer_invitation_email(tt,token) if token else (False,'Invitation non créée.')
                if okm: st.success(msgm)
                else: st.warning(msgm)
            with c3.expander('🗑️ Supprimer définitivement'):
                pw=st.text_input('Votre mot de passe administrateur',type='password',key='trdelpw');conf=st.text_input('Saisissez SUPPRIMER',key='trdelconf')
                if st.button('Supprimer du référentiel',key='trdel'):
                    if conf!='SUPPRIMER' or not admin_password_ok(ENGINE,st.session_state.admin_email,pw): st.error('Confirmation ou mot de passe incorrect.')
                    else: purge_trainer(ENGINE,tt['id'],st.session_state.admin_email);st.success('Intervenant supprimé.');rerun()
        st.markdown('### Remontées des intervenants')
        reports=q(ENGINE,"""SELECT r.*,t.full_name trainer_name,a.action_no,a.title action_title FROM trainer_reports r
          JOIN trainers t ON t.id=r.trainer_id JOIN actions a ON a.id=r.action_id ORDER BY r.created_at DESC LIMIT 100""")
        if not reports:
            st.info('Aucune remontée intervenant.')
        else:
            st.dataframe(pd.DataFrame([{'Date':r['created_at'][:16].replace('T',' '),'Action':r['action_no'],'Intervenant':r['trainer_name'],'Nature':r['report_type'],'Objet':r['subject'],'Qualité':'Oui' if r['quality_relevant'] else 'Non','Statut':r['status']} for r in reports]),use_container_width=True,hide_index=True)
            rmap={f"#{r['id']} — {r['action_no']} — {r['subject']}":r for r in reports}; rl=st.selectbox('Remontée à traiter',list(rmap),key='trainer_report_admin'); rr=rmap[rl]
            st.write(rr['description'])
            if rr.get('attachment_path') and Path(rr['attachment_path']).is_file():
                st.download_button(f"Télécharger la pièce jointe — {rr.get('attachment_name') or 'document'}",Path(rr['attachment_path']).read_bytes(),file_name=rr.get('attachment_name') or Path(rr['attachment_path']).name,key=f"tr_report_dl_{rr['id']}")
            statuses=['NOUVEAU','EN_COURS','TRAITE']; idx=statuses.index(rr['status']) if rr['status'] in statuses else 0; new_status=st.selectbox('Statut de traitement',statuses,index=idx,key=f"tr_report_status_{rr['id']}")
            if st.button('Enregistrer le statut',key=f"tr_report_save_{rr['id']}"):
                execute(ENGINE,'UPDATE trainer_reports SET status=:s,updated_at=:u WHERE id=:i',{'s':new_status,'u':utcnow_iso(),'i':rr['id']}); audit(ENGINE,'TRAINER_REPORT_STATUS_CHANGED',rr['action_id'],st.session_state.admin_email,'trainer_report',rr['id'],{'status':new_status}); st.success('Statut mis à jour.'); rerun()
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
        try:
            if ctx.get('tool_code')=='PIP_RIASEC_ONET':
                key=secret('pip_connector','launch_signing_key','')
                url=build_pip_prescription_launch(ENGINE,ctx['prescription_id'],key,valid_seconds=900)
                label="OUVRIR LE PIP RIASEC / O*NET"
            else:
                key=secret('hub','hmac_secret','')
                url=build_generic_tool_launch(ENGINE,ctx['prescription_id'],key,valid_seconds=900)
                label=f"OUVRIR {ctx.get('tool_name') or 'L’OUTIL'}"
            st.info("Votre accès sécurisé Clarté360 est prêt. Aucun secret ni identifiant technique n'est affiché.")
            st.link_button(label,url,type='primary')
        except Exception:
            st.warning("Cet outil est temporairement indisponible. Votre prescription reste enregistrée ; réessayez plus tard ou contactez Clarté360.")
    elif ctx.get('base_url'):
        st.link_button("OUVRIR L'OUTIL",ctx['base_url'],type='primary')
    else:
        st.warning("Le contrat de lancement de cet outil n'est pas encore configuré.")
    footer()

# ROUTING PUBLIC SIGNATURE
params=st.query_params
if params.get('tool_launch'):
    _run_ui_module('tool_launch',lambda: tool_launch_page(params.get('tool_launch')));st.stop()
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
    st.session_state['nav'] = st.session_state.pop('_next_nav')
page=sidebar()
if page=='Tableau de bord': _run_ui_module('dashboard',dashboard)
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
elif page=='Paramètres': _run_ui_module('parametres',settings_screen)
