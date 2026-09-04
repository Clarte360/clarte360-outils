from __future__ import annotations
import io, os, json, csv, base64, re
from datetime import date, datetime, time
from pathlib import Path
from urllib.parse import quote
import pandas as pd
import qrcode
from PIL import Image as PILImage
import streamlit as st
from streamlit_drawable_canvas import st_canvas

from branding import *
from db import make_engine, init_db, q, one, execute, audit, sha256_bytes, utcnow_iso
from security import hash_password, verify_password
from services import *
from excel_import import read_clarte360_xlsm, read_adca_xlsm, list_action_numbers
from pdf_utils import collective_pdf, individual_pdf, certificate_pdf, quality_response_pdf
from mailer import send_mail, resolve_mail_config, validate_mail_config
from source_store import source_info, set_external_path, save_uploaded_source, refresh_from_external, read_snapshot

st.set_page_config(page_title=APP_NAME,page_icon=str(ICON_PATH),layout='wide',initial_sidebar_state='expanded')
st.markdown(CSS,unsafe_allow_html=True)

def secret(section,key,default=None):
    try:return st.secrets.get(section,{}).get(key,default)
    except:return default
DB_URL=secret('database','url',None); ENGINE=make_engine(DB_URL);init_db(ENGINE)
ensure_default_organization(ENGINE); migrate_legacy_action_statuses(ENGINE)
try:
    _default_org=get_organization(ENGINE)
    seed_standard_questionnaires(ENGINE,_default_org.get('id') if _default_org else None,'system')
except Exception:
    pass
BASE_URL=secret('app','base_url','http://localhost:8501');TZ=secret('app','timezone','Europe/Paris')
_PIN_KEY=secret('security','participant_pin_key',secret('app','setup_key',''))
if _PIN_KEY: os.environ['CLARTE360_PIN_KEY']=str(_PIN_KEY)
TRAINER_REPORT_DIR=Path(__file__).resolve().parent/'data'/'trainer_reports'; TRAINER_REPORT_DIR.mkdir(parents=True,exist_ok=True)

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
    return txt[:120]


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


def send_schedule_confirmations(action_id, actor):
    action=one(ENGINE,'SELECT * FROM actions WHERE id=:a',{'a':action_id})
    parts=q(ENGINE,'SELECT * FROM participants WHERE action_id=:a AND active=1 ORDER BY last_name,first_name',{'a':action_id})
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


def send_participant_code_email(participant, action, pin):
    cfg=mail_cfg()
    if not participant.get('email') or not cfg.get('enabled'): return False, 'Email non envoyé (adresse ou configuration MAIL indisponible).'
    org=org_identity(action.get('id'));org_name=org.get('name') or 'Organisme'; subject=f"{org_name} — votre accès émargement — {action['action_no']}"
    body=f"""<p>Bonjour {participant['first_name']},</p><p>Vous êtes inscrit(e) à <strong>{action['title']}</strong>.</p><p>Votre code personnel pour l'émargement via QR code est : <strong style='font-size:20px'>{pin}</strong>.</p><p>Conservez ce code pendant l'action. Les liens personnels reçus par email permettent également d'émarger sans ressaisir ce code.</p>{privacy_notice_html(action.get('id'))}<p>{org_name}</p>"""
    try: send_mail(cfg,participant['email'],subject,body); return True,'Code envoyé par email.'
    except Exception as ex: return False,f'Envoi du code impossible : {ex}'


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
    body=f"""<p>Bonjour {beneficiary.get('first_name') or ''},</p><p>Votre espace personnel Clarté360 peut maintenant être activé.</p><p><a href='{link}'>ACTIVER MON ESPACE PERSONNEL</a></p><p>Ce lien est temporaire. Votre adresse email sert à la connexion mais ne constitue pas votre identité dans Clarté360.</p>{privacy_notice_html()}"""
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
        rows.append({'Participant':f"{p['last_name']} {p['first_name']}",'Statut':status,'Email':p.get('email') or ''})
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
    c3.metric('Modalité',a.get('mode') or '—')
    c4.metric('Participants',len(parts))
    st.caption(f"Lieu / modalité : {a.get('location') or 'Non renseigné'} · Période : {a.get('start_date') or '—'} → {a.get('end_date') or '—'} · Statut : {normalize_action_status(a.get('status'))}")
    if next_slot:
        st.success(f"Prochaine séance : {_slot_label(next_slot)}")
    elif slots:
        st.info('Aucune séance future : le calendrier affiché ci-dessous reprend les séances enregistrées.')
    else:
        st.warning('Aucun créneau n’est actuellement enregistré pour cette action.')

    tab_plan,tab_em,tab_codes,tab_docs,tab_quality,tab_report=st.tabs(['📅 Planning','✍️ Émargements / QR','🔐 Codes participants','📚 Documents','📋 Qualité','📣 Signaler / informer'])
    with tab_plan:
        if slots:
            cal=[]
            for sl in slots:
                signed=one(ENGINE,"SELECT COUNT(*) n FROM signatures WHERE slot_id=:s AND status='VALIDE'",{'s':sl['id']})['n']
                absent=one(ENGINE,"SELECT COUNT(*) n FROM attendance_status WHERE slot_id=:s AND status='ABSENT'",{'s':sl['id']})['n']
                cs=one(ENGINE,'SELECT id FROM trainer_countersignatures WHERE slot_id=:s',{'s':sl['id']})
                cal.append({'Date':sl['slot_date'],'Début':sl['start_time'],'Fin':sl['end_time'],'Type':sl.get('slot_kind') or 'NORMAL','Signés':signed,'Absents':absent,'Contresigné':'Oui' if cs else 'Non'})
            st.dataframe(pd.DataFrame(cal),use_container_width=True,hide_index=True)
        else: st.info('Aucun créneau.')
    with tab_em:
        if not slots:
            st.info('Aucun créneau à gérer.')
        else:
            smap={_slot_label(x):x for x in slots}; sl=smap[st.selectbox('Créneau à gérer',list(smap),key=f'tr_slot_{aid}') ]
            qr=qrcode.make(public_slot_url(sl,BASE_URL)); buf=io.BytesIO(); qr.save(buf,format='PNG')
            c1,c2=st.columns([1,2]); c1.image(buf.getvalue(),width=220); c2.markdown('**QR d’émargement**'); c2.caption('Vous pouvez présenter ce QR code aux participants. Le code personnel reste nécessaire sur la page QR.')
            parts2,rows=_trainer_slot_status_rows(aid,sl['id']); st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
            if parts2:
                pmap={f"{p['last_name']} {p['first_name']}":p for p in parts2}; pp=pmap[st.selectbox('Participant à gérer',list(pmap),key=f'tr_part_{aid}_{sl["id"]}') ]
                c1,c2,c3=st.columns(3)
                if c1.button('Marquer ABSENT',key=f'tr_abs_{aid}_{sl["id"]}_{pp["id"]}',use_container_width=True):
                    ok,msg=set_attendance_status(ENGINE,pp['id'],sl['id'],'ABSENT','Déclaré par intervenant',actor)
                    if ok: st.success('Absence enregistrée.'); rerun()
                    else: st.error(msg)
                if c2.button('Remettre EN ATTENTE',key=f'tr_wait_{aid}_{sl["id"]}_{pp["id"]}',use_container_width=True):
                    set_attendance_status(ENGINE,pp['id'],sl['id'],'EN_ATTENTE','Correction intervenant',actor); rerun()
                if c3.button('Relancer par email',key=f'tr_rem_{aid}_{sl["id"]}_{pp["id"]}',disabled=not bool(pp.get('email')),use_container_width=True):
                    ensure_tokens_and_events(ENGINE,aid,BASE_URL,TZ); url=token_url(ENGINE,pp['id'],sl['id'],BASE_URL); cfg=mail_cfg(); org=org_identity(aid)
                    body=f"<p>Bonjour {pp['first_name']},</p><p>Merci de régulariser votre émargement pour le {sl['slot_date']} de {sl['start_time']} à {sl['end_time']}.</p><p><a href='{url}'>SIGNER / RÉGULARISER</a></p>{privacy_notice_html(aid)}"
                    try:
                        send_mail(cfg,pp['email'],f"{org.get('name') or 'Organisme'} — émargement — {a['action_no']}",body); audit(ENGINE,'TRAINER_MANUAL_REMINDER',aid,actor,'participant',pp['id'],{'slot_id':sl['id']}); st.success('Relance envoyée.')
                    except Exception as ex: st.error(f'Envoi impossible : {friendly_mail_error(ex)}')
            st.markdown('#### Contresignature du créneau')
            existing=one(ENGINE,'SELECT * FROM trainer_countersignatures WHERE slot_id=:s',{'s':sl['id']})
            if existing: st.success(f"Créneau contresigné par {existing['trainer_name']} le {local_dt(existing['signed_at'],TZ).strftime('%d/%m/%Y à %H:%M')}")
            else:
                cert=st.checkbox("Je certifie l'exactitude des présences et absences indiquées pour ce créneau.",key=f'tr_cert_{aid}_{sl["id"]}')
                if st.button('CONTRESIGNER CE CRÉNEAU',type='primary',key=f'tr_sign_{aid}_{sl["id"]}'):
                    if not cert: st.error('La certification est obligatoire.')
                    else:
                        countersign_slot(ENGINE,sl['id'],trainer['full_name'],trainer.get('email'),actor,"Je certifie l'exactitude des présences et absences indiquées pour ce créneau."); st.success('Contresignature enregistrée.'); rerun()
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
            updoc=st.file_uploader('Document',type=['pdf','doc','docx','xls','xlsx','ppt','pptx','txt','csv','jpg','jpeg','png','webp','zip'],key=f'tr_course_doc_{aid}')
            if st.button('Déposer dans Documents de cours',key=f'tr_course_doc_btn_{aid}',disabled=updoc is None):
                try:
                    rid,h,dedup=store_document(ENGINE,updoc.getvalue(),updoc.name,'COURS',actor,action_id=aid,audience='ACTION_BENEFICIARIES')
                    st.success('Document déposé. '+('Le contenu existait déjà : aucune seconde copie physique n’a été créée.' if dedup else 'Nouveau fichier physique enregistré.'));rerun()
                except Exception as ex: st.error(str(ex))
        else: st.caption("Le dépôt de documents n'est pas autorisé pour votre compte. L'administrateur peut activer ce droit.")
    with tab_quality:
        camp=one(ENGINE,"""SELECT qc.*,qt.title questionnaire_title FROM quality_campaigns qc JOIN questionnaire_templates qt ON qt.id=qc.template_id
          WHERE qc.action_id=:a AND qc.trainer_id=:t AND qc.campaign_kind='TRAINER' ORDER BY qc.id DESC LIMIT 1""",{'a':aid,'t':tid})
        if not a.get('use_trainer_feedback'):
            st.info("Le questionnaire qualité intervenant n'est pas activé pour cette action.")
        elif not camp:
            st.info("Le questionnaire est activé mais n'a pas encore été généré. Il sera créé selon le calendrier qualité de l'action.")
        elif camp.get('status')=='COMPLETED':
            st.success('Votre questionnaire intervenant a été complété.')
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
            st.dataframe(pd.DataFrame([{'Date':x['created_at'][:16].replace('T',' '),'Nature':x['report_type'],'Objet':x['subject'],'Statut':x['status']} for x in history]),use_container_width=True,hide_index=True)

def trainer_portal_page():
    if not st.session_state.get('trainer_portal_id'):
        header('Clarté360 — Espace intervenant','Accès réservé aux formateurs / accompagnants')
        with st.form('trainer_login'):
            email=st.text_input('Email').strip().lower(); pw=st.text_input('Mot de passe',type='password'); ok=st.form_submit_button('Se connecter',type='primary')
        if ok:
            tr=verify_trainer_login(ENGINE,email,pw)
            if tr:
                st.session_state.trainer_portal_id=tr['id']; st.session_state.trainer_portal_name=tr['full_name']; rerun()
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
        st.session_state.pop('trainer_portal_id',None); st.session_state.pop('trainer_portal_name',None); rerun()
    acts=trainer_actions(ENGINE,tid)
    if not acts:
        st.info('Aucune action ne vous est actuellement affectée.'); footer(); return
    cards=[]
    for a in acts:
        data=trainer_action_dashboard(ENGINE,tid,a['id'],TZ); nxt=data.get('next_slot') if data else None
        cards.append({'Action':a['action_no'],'Intitulé':a['title'],'Client':a.get('client_name') or '','Début':a.get('start_date') or '','Fin':a.get('end_date') or '','Prochaine séance':_slot_label(nxt) if nxt else '—','Statut':normalize_action_status(a.get('status'))})
    st.dataframe(pd.DataFrame(cards),use_container_width=True,hide_index=True)
    labels={f"{a['action_no']} — {a['title']} — {normalize_action_status(a.get('status'))}":a for a in acts}
    lab=st.selectbox('Action à ouvrir',list(labels),key='trainer_action_choice'); render_trainer_action(labels[lab],tr)
    footer(labels[lab]['id'])


def beneficiary_invitation_page(token):
    header('Clarté360 — Activation de mon espace','Création de votre accès personnel')
    b=beneficiary_by_invite(ENGINE,token)
    if not b:
        st.error('Invitation invalide ou déjà utilisée.'); footer(); return
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

def beneficiary_portal_page():
    if not st.session_state.get('beneficiary_portal_id'):
        header('Clarté360 — Espace bénéficiaire','Mes formations, mon planning et mes documents')
        with st.form('beneficiary_login'):
            email=st.text_input('Email').strip().lower();pw=st.text_input('Mot de passe',type='password');ok=st.form_submit_button('Se connecter',type='primary')
        if ok:
            acc=verify_beneficiary_login(ENGINE,email,pw)
            if acc:
                st.session_state.beneficiary_portal_id=acc['beneficiary_id'];rerun()
            else: st.error('Identifiants incorrects ou espace non activé.')
        footer();return
    bid=st.session_state.beneficiary_portal_id
    b=one(ENGINE,'SELECT * FROM beneficiaries WHERE id=:b AND active=1',{'b':bid})
    acc=one(ENGINE,'SELECT * FROM beneficiary_portal_accounts WHERE beneficiary_id=:b AND active=1',{'b':bid})
    if not b or not acc:
        st.session_state.pop('beneficiary_portal_id',None);rerun()
    header('Clarté360 — Mon espace',f"Bienvenue {b['first_name']} {b['last_name']}")
    c1,c2=st.columns([4,1]);c1.caption(f"Identifiant interne : {b['public_id']} · Connexion : {acc['email']}")
    if c2.button('Se déconnecter',use_container_width=True): st.session_state.pop('beneficiary_portal_id',None);rerun()
    acts=beneficiary_participations(ENGINE,bid);docs=list_beneficiary_documents(ENGINE,bid)
    pending=q(ENGINE,"""SELECT qc.*,a.action_no,qt.title FROM quality_campaigns qc JOIN actions a ON a.id=qc.action_id JOIN questionnaire_templates qt ON qt.id=qc.template_id
      WHERE qc.participant_id IN (SELECT id FROM participants WHERE beneficiary_id=:b) AND qc.status<>'COMPLETED' ORDER BY qc.due_at""",{'b':bid})
    tabs=st.tabs(['🏠 Accueil','🎓 Mes formations / accompagnements','📅 Mon planning','📄 Mes documents administratifs','📚 Documents de cours','✅ Mes questionnaires / actions','🗂️ Mes archives / téléchargements'])
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
    def _show_docs(rows,empty):
        if not rows: st.info(empty);return
        for d in rows:
            path=Path(d['storage_path'])
            if path.is_file(): st.download_button(f"{d.get('action_no') or 'Général'} — {d['display_name']}",path.read_bytes(),file_name=d['display_name'],key=f"bdl_{d['id']}")
    with tabs[3]: _show_docs([d for d in docs if d['category']!='COURS'],'Aucun document administratif disponible.')
    with tabs[4]: _show_docs([d for d in docs if d['category']=='COURS'],'Aucun document de cours disponible.')
    with tabs[5]:
        if not pending: st.success('Aucune action à réaliser actuellement.')
        for x in pending: st.link_button(f"{x['action_no']} — {x['title']}",quality_token_url(x['token'],BASE_URL))
    with tabs[6]:
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
def get_ip(): return None
def get_ua(): return None

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
    if st.session_state.get('admin_email'): return True
    header(sub='Espace administrateur')
    c1,c2=st.columns([1,1]);
    with c1:
        email=st.text_input('Email').strip().lower();pw=st.text_input('Mot de passe',type='password')
        if st.button('Se connecter',type='primary',use_container_width=True):
            a=one(ENGINE,'SELECT * FROM admins WHERE email=:e AND active=1',{'e':email})
            if a and verify_password(pw,a['password_hash']): st.session_state.admin_email=email;st.session_state.admin_name=a.get('full_name') or email;rerun()
            else: st.error('Identifiants incorrects.')
    with c2:
        st.markdown("<div class='c360-card'><h3>À quoi sert cet espace ?</h3>Créer ou importer une action, définir ses créneaux, gérer les stagiaires, suivre les signatures, relancer et générer les justificatifs.</div>",unsafe_allow_html=True)
    st.link_button('Accès formateur / accompagnant',f"{BASE_URL.rstrip('/')}?trainer_portal=1")
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
        canvas=st_canvas(fill_color='rgba(255,255,255,0)',stroke_width=3,stroke_color='#1F2937',background_color='#FFFFFF',height=180,width=360,drawing_mode='freedraw',display_toolbar=True,update_streamlit=True,key=f"sig_{row['id']}_{row['slot_id']}")
    else:
        typed_name=st.text_input('Saisissez vos nom et prénom',value=f"{row['first_name']} {row['last_name']}")
        st.caption("La validation associe votre identité saisie, votre déclaration et l'horodatage réel à la preuve d'émargement.")
    if st.button('VALIDER MON ÉMARGEMENT',type='primary',use_container_width=True):
        if not consent: st.error('Veuillez confirmer les informations.');return
        if sig_mode=='Signature manuscrite':
            if canvas.image_data is None or (canvas.image_data[:,:,:3] < 250).sum() < 100: st.error('Merci d’apposer votre signature dans le cadre.');return
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
        rows.append({'Participant':f"{p['last_name']} {p['first_name']}",'Statut':status,'Email':p.get('email') or ''})
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
        except Exception as ex: st.error(f'Envoi impossible : {ex}')
    st.markdown('### Contresignature du créneau')
    existing=one(ENGINE,'SELECT * FROM trainer_countersignatures WHERE slot_id=:s',{'s':slot['id']})
    if existing: st.success(f"Créneau contresigné par {existing['trainer_name']} le {local_dt(existing['signed_at'],TZ).strftime('%d/%m/%Y à %H:%M')}")
    name=st.text_input('Nom et prénom de l’intervenant',value=row.get('trainer_name') or '');cert=st.checkbox("Je certifie l'exactitude des présences et absences indiquées pour ce créneau.")
    if st.button('CONTRESIGNER CE CRÉNEAU',type='primary'):
        if not name.strip() or not cert: st.error('Nom et certification obligatoires.')
        else: countersign_slot(ENGINE,slot['id'],name.strip(),row.get('trainer_email'),f"trainer:{name.strip()}","Je certifie l'exactitude des présences et absences indiquées pour ce créneau.");st.success('Contresignature enregistrée.');rerun()
    footer()

def quality_page(token):
    ctx=quality_campaign_context(ENGINE,token)
    if not ctx:
        header('Questionnaire qualité','Lien sécurisé');st.error('Lien de questionnaire invalide ou expiré.');footer();return
    runtime=organization_runtime_config(ENGINE,ctx['action_id']);org=runtime['organization'];org_name=org.get('name') or 'Organisme'
    header(f"{org_name} — Qualité",ctx['questionnaire_title'])
    if ctx.get('status')=='COMPLETED':
        st.success('Votre questionnaire a déjà été enregistré. Merci pour votre retour.');footer();return
    respondent=ctx.get('trainer_full_name') or f"{ctx.get('first_name') or ''} {ctx.get('last_name') or ''}".strip()
    st.markdown(f"<div class='c360-card'><b>{ctx['action_title']}</b><br>N° action : {ctx['action_no']}<br>Répondant : {respondent}<br>Questionnaire : {ctx['questionnaire_title']} — version {ctx['questionnaire_version']}</div>",unsafe_allow_html=True)
    privacy=org.get('privacy_notice') or "Les informations recueillies sont utilisées pour le suivi de l’action et l’amélioration de la qualité des prestations."
    contact=org.get('privacy_contact') or org.get('general_email') or ''
    st.info(f"Données personnelles : {privacy}" + (f" Contact : {contact}" if contact else ''))
    questions=quality_questions(ENGINE,ctx['id']);existing=quality_existing_answers(ENGINE,ctx['id']);answers={}
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
    pages=['Tableau de bord','Nouvelle action','Importer Clarté360 / CSV','Actions','Paramètres']
    page=st.sidebar.radio('Navigation',pages,key='nav')
    st.sidebar.divider()
    if st.sidebar.button('Se déconnecter',use_container_width=True): st.session_state.clear();rerun()
    return page

def create_action_screen(prefill=None,participants_prefill=None):
    # Lors d'un import, le brouillon reste en session jusqu'à création ou annulation.
    # Cela évite la perte des champs lors d'un rerun Streamlit ou d'une frappe sur Entrée.
    if st.session_state.get('import_create_active'):
        prefill = st.session_state.get('import_prefill') or prefill
        participants_prefill = st.session_state.get('import_parts') or participants_prefill

    p=prefill or {}
    imported_parts=participants_prefill or []

    header('Clarté360 — Nouvelle action','Création d’une action et de son dossier d’émargement')

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

    with st.form('new_action', enter_to_submit=False):
        c1,c2=st.columns(2)
        action_no=c1.text_input('N° D’ACTION *',value=p.get('action_no','')).strip().upper()
        prestation_labels={'Formation':'FORMATION','Bilan de compétences':'BILAN_COMPETENCES','VAE':'VAE','Coaching':'COACHING','Mentorat':'MENTORAT','Autre':'AUTRE'}
        prestation_label=c2.selectbox('Type de prestation *',list(prestation_labels))
        prestation_type=prestation_labels[prestation_label]
        nature=prestation_label

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
        org_label=st.selectbox('Organisme',list(org_opts))
        organization_id=org_opts[org_label]
        agencies=list_agencies(ENGINE,organization_id,active_only=True)
        agency_opts={'— Siège / aucune agence —':None,**{g['name']:g['id'] for g in agencies}}
        agency_label=st.selectbox('Agence / établissement',list(agency_opts))
        agency_id=agency_opts[agency_label]

        st.markdown('**Modules activés pour cette action**')
        m1,m2,m3,m4=st.columns(4)
        use_attendance=m1.checkbox('Émargement',value=True)
        use_hot=m2.checkbox('Évaluation à chaud',value=False)
        use_cold=m3.checkbox('Évaluation à froid',value=False)
        use_trainer=m4.checkbox('Retour intervenant',value=False)

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

        c1,c2=st.columns(2)
        trainer_label=c1.selectbox('Intervenant référencé',trainer_labels,index=trainer_index)
        location=c2.text_input('Lieu / modalité',value=p.get('location') or '')

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
                st.success('Action créée. Vous pouvez maintenant ajouter les participants et les créneaux.')
            st.session_state['_next_nav']='Actions'
            rerun()
    footer()

def import_screen():
    header('Clarté360 — Import','Importer une action depuis la base Clarté360 ou un CSV de participants')
    tab1,tabadca,tab2=st.tabs(['Base GESTION OF CLARTE360 (.xlsm)','Base GESTION OF ADCA (.xlsm)','CSV participants'])
    with tab1:
        info=source_info('CLARTE360')
        if info.get('snapshot_path'):
            st.info(f"Base Clarté360 mémorisée sur le VPS : {info.get('original_name') or Path(info['snapshot_path']).name}. Vous pouvez rechercher plusieurs actions sans recharger le fichier.")
        f=st.file_uploader('Charger / actualiser GESTION OF CLARTE360 (.xlsm/.xlsx)',type=['xlsm','xlsx'],key='xlsm')
        mode=st.selectbox('Mode de l’action',['INTRA','INTER','INDIVIDUEL'],key='clar_mode'); n=st.text_input('N° D’ACTION à rechercher',placeholder='CLA0001').strip().upper()
        if st.button('Lire l’action',type='primary') and n:
            try:
                if f:
                    raw=f.getvalue(); save_uploaded_source('CLARTE360',f.name,raw)
                else:
                    raw,_=read_snapshot('CLARTE360')
                if not raw:
                    st.error('Chargez une base Clarté360 une première fois. Elle sera ensuite conservée sur le VPS pour les recherches suivantes.')
                else:
                    data,parts=read_clarte360_xlsm(raw,n,mode)
                    if not data: st.error('Action introuvable dans les onglets CONV ADM et STAGIAIRE.')
                    else:
                        st.session_state.import_prefill=data;st.session_state.import_parts=parts;st.success(f"Action trouvée — {len(parts)} participant(s) détecté(s). Le NIR n’est pas importé.")
            except Exception as e: st.error(f"Lecture impossible : {e}")
        if st.session_state.get('import_prefill'):
            d=st.session_state.import_prefill;st.json({k:v for k,v in d.items() if k not in ['default_start','default_end']});
            if st.button('Créer cette action dans Clarté360 Émargements'):
                st.session_state.import_create_active=True;st.session_state['_next_nav']='Nouvelle action';rerun()
    with tabadca:
        st.info('Import ADCA : permet notamment de reprendre une action historique pour activer uniquement la qualité à froid, sans recréer artificiellement des émargements.')
        ainfo=source_info('ADCA')
        if ainfo.get('snapshot_path'):
            st.info(f"Base ADCA mémorisée sur le VPS : {ainfo.get('original_name') or Path(ainfo['snapshot_path']).name}. Vous pouvez rechercher plusieurs actions sans recharger le fichier.")
        af=st.file_uploader('Charger / actualiser GESTION OF ADCA (.xlsm/.xlsx)',type=['xlsm','xlsx'],key='adca_xlsm')
        amode=st.selectbox('Mode de l’action',['INTRA','INTER','INDIVIDUEL'],key='adca_mode')
        an=st.text_input('N° ADCA à rechercher',placeholder='ADC4736').strip().upper()
        if st.button('Lire l’action ADCA',type='primary') and an:
            try:
                if af:
                    araw=af.getvalue(); save_uploaded_source('ADCA',af.name,araw)
                else:
                    araw,_=read_snapshot('ADCA')
                if not araw:
                    st.error('Chargez une base ADCA une première fois. Elle sera ensuite conservée sur le VPS pour les recherches suivantes.')
                else:
                    data,parts=read_adca_xlsm(araw,an,amode)
                    if not data: st.error('Action ADCA introuvable.')
                    else:
                        st.session_state.import_prefill=data;st.session_state.import_parts=parts;st.success(f"Action trouvée — {len(parts)} participant(s). Source métier utilisée : {data.get('source_sheet')}.")
            except Exception as e: st.error(f'Lecture ADCA impossible : {e}')
        if st.session_state.get('import_prefill',{}).get('source')=='GESTION OF ADCA':
            d=st.session_state.import_prefill;st.json({k:v for k,v in d.items() if k not in ['default_start','default_end']})
            st.caption('Après création, vous pourrez désactiver Émargement et conserver uniquement Évaluation à froid.')
            if st.button('Créer cette action historique ADCA'):
                st.session_state.import_create_active=True;st.session_state['_next_nav']='Nouvelle action';rerun()
    with tab2:
        st.caption('Colonnes reconnues : no_action, nom, nom_naissance, prenom, date_naissance, email, matricule, entreprise, telephone.')
        sample='no_action,nom,nom_naissance,prenom,date_naissance,email,matricule,entreprise,telephone\nCLA0001,DURAND,,Marie,1985-02-14,marie@example.com,M001,SOCIETE EXEMPLE,0600000000\n'
        st.download_button('Télécharger un modèle CSV',sample.encode(),'modele_participants.csv','text/csv')
        cf=st.file_uploader('CSV participants',type=['csv'],key='csvp')
        if cf:
            try:
                df=pd.read_csv(cf,sep=None,engine='python',dtype=str).fillna('');st.dataframe(df,use_container_width=True)
                action_no=st.text_input('N° action auquel rattacher ces participants').strip().upper();a=one(ENGINE,'SELECT * FROM actions WHERE action_no=:n',{'n':action_no}) if action_no else None
                if st.button('Importer les participants dans cette action'):
                    if not a: st.error('Action introuvable.')
                    else:
                        count=0
                        for _,r in df.iterrows():
                            last=(r.get('nom') or r.get('NOM') or '').strip();first=(r.get('prenom') or r.get('PRENOM') or '').strip()
                            if not last or not first: continue
                            add_participant(ENGINE,a['id'],{'individual_action_no':(r.get('no_action') or action_no).strip(),'last_name':last,'birth_name':(r.get('nom_naissance') or '').strip() or None,'first_name':first,'birth_date':(r.get('date_naissance') or '').strip() or None,'email':(r.get('email') or '').strip() or None,'employee_id':(r.get('matricule') or '').strip() or None,'company_name':(r.get('entreprise') or '').strip() or None,'phone':(r.get('telephone') or '').strip() or None},st.session_state.admin_email);count+=1
                        st.success(f'{count} participant(s) importé(s).')
            except Exception as e: st.error(f'CSV illisible : {e}')
    footer()

def dashboard():
    header('Clarté360 — Tableau de bord','Vue globale des actions et émargements')
    acts=q(ENGINE,'SELECT * FROM actions ORDER BY id DESC')
    total=len(acts);open_n=sum(normalize_action_status(a['status'])!='ARCHIVEE' for a in acts);pending=one(ENGINE,"SELECT COUNT(*) n FROM email_events WHERE status='PENDING'")['n'];signed=one(ENGINE,"SELECT COUNT(*) n FROM signatures WHERE status='VALIDE'")['n']
    c1,c2,c3,c4=st.columns(4)
    for c,n,l in [(c1,total,'Actions'),(c2,open_n,'Actives'),(c3,signed,'Signatures'),(c4,pending,'Envois / relances prévus')]: c.markdown(f"<div class='c360-kpi'><div class='n'>{n}</div><div class='l'>{l}</div></div>",unsafe_allow_html=True)
    st.subheader('Actions récentes')
    rows=[]
    for a in acts[:20]:
        pr=action_progress(ENGINE,a['id']);rows.append({'Action':a['action_no'],'Intitulé':a['title'],'Mode':a['mode'],'Participants':pr['participants'],'Créneaux':pr['slots'],'Signatures':f"{pr['signed']}/{pr['expected']}",'Avancement':f"{pr['percent']}%"})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    st.subheader('Pilotage qualité')
    orgs=list_organizations(ENGINE,active_only=True); om={'Tous':None,**{o['name']:o['id'] for o in orgs}}; c1,c2=st.columns(2); ol=c1.selectbox('Organisme',list(om),key='qd_org'); pts=['Tous','FORMATION','BILAN_COMPETENCES','VAE','COACHING','MENTORAT','AUTRE']; pt=c2.selectbox('Prestation',pts,key='qd_pt')
    qd=quality_management_summary(ENGINE,organization_id=om[ol],prestation_type=None if pt=='Tous' else pt)
    c1,c2,c3,c4=st.columns(4)
    for c,n,l in [(c1,qd['campaigns'],'Questionnaires prévus'),(c2,f"{qd['response_rate']}%",'Taux de réponse'),(c3,('—' if qd.get('nps_score') is None else qd['nps_score']),'NPS'),(c4,qd['issues_open'],'Difficultés ouvertes')]: c.markdown(f"<div class='c360-kpi'><div class='n'>{n}</div><div class='l'>{l}</div></div>",unsafe_allow_html=True)
    if qd.get('rubric_averages'):
        st.caption('Lecture direction par rubriques stables : '+ ' · '.join(f"{k}: {v}" for k,v in sorted(qd['rubric_averages'].items())))
    if qd['improvements_open']: st.info(f"{qd['improvements_open']} action(s) d’amélioration encore ouverte(s).")
    stats=quality_question_stats(ENGINE,organization_id=om[ol],prestation_type=None if pt=='Tous' else pt)
    if stats: st.dataframe(pd.DataFrame(stats),use_container_width=True,hide_index=True)
    st.subheader('Dépôt documentaire rapide')
    st.caption('Indiquez simplement le numéro d’action : le document sera disponible pour les bénéficiaires rattachés à cette action.')
    c1,c2=st.columns([1,2]); quick_no=c1.text_input('N° action',key='quick_doc_action').strip().upper(); quick_file=c2.file_uploader('Document',type=['pdf','doc','docx','xls','xlsx','ppt','pptx','txt','csv','jpg','jpeg','png','webp','zip'],key='quick_doc_file')
    quick_cat=st.selectbox('Catégorie',['COURS','ADMINISTRATIF'],format_func=lambda x:'Documents de cours' if x=='COURS' else 'Document administratif',key='quick_doc_cat')
    if st.button('DÉPOSER PAR N° ACTION',key='quick_doc_btn',disabled=not bool(quick_no and quick_file)):
        aa=one(ENGINE,'SELECT * FROM actions WHERE action_no=:n',{'n':quick_no})
        if not aa: st.error('Action introuvable.')
        else:
            try:
                rid,h,dedup=store_document(ENGINE,quick_file.getvalue(),quick_file.name,quick_cat,st.session_state.admin_email,action_id=aa['id'],audience='ACTION_BENEFICIARIES')
                st.success(f"Document rattaché à {quick_no}. "+('Le contenu existait déjà : aucune duplication physique.' if dedup else 'Nouveau contenu enregistré.'))
            except Exception as ex: st.error(str(ex))
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
    st.markdown(f"<div class='c360-card'><h3>{a['action_no']} — {a['title']}</h3>{a.get('subtitle') or ''}<br><b>{a['mode']}</b> — Durée prévue : {a['planned_hours']:g} h — Statut : {a['status']}</div>",unsafe_allow_html=True)
    flash=st.session_state.pop('_action_flash',None)
    if flash and flash[0]==aid:
        if flash[1]=='success': st.success(flash[2])
        elif flash[1]=='warning': st.warning(flash[2])
        else: st.info(flash[2])
    c1,c2,c3,c4=st.columns(4);c1.metric('Participants',pr['participants']);c2.metric('Créneaux',pr['slots']);c3.metric('Signatures',f"{pr['signed']}/{pr['expected']}");c4.metric('Avancement',f"{pr['percent']} %")
    tabs=st.tabs(['Paramètres action','Participants','Calendrier','Envois & relances','Suivi','Qualité','Documents','Journal'])
    with tabs[0]: action_settings_tab(a)
    with tabs[1]: participants_tab(a)
    with tabs[2]: calendar_tab(a)
    with tabs[3]: dispatch_tab(a)
    with tabs[4]: tracking_tab(a)
    with tabs[5]: quality_tab(a)
    with tabs[6]: documents_tab(a)
    with tabs[7]: audit_tab(a)

def action_settings_tab(a):
    st.subheader('Paramètres de l’action')
    prestation_labels={'Formation':'FORMATION','Bilan de compétences':'BILAN_COMPETENCES','VAE':'VAE','Coaching':'COACHING','Mentorat':'MENTORAT','Autre':'AUTRE'}
    reverse_pt={v:k for k,v in prestation_labels.items()}; current_pt=a.get('prestation_type') or 'FORMATION'; current_label=reverse_pt.get(current_pt,'Formation')
    orgs=list_organizations(ENGINE,active_only=True); org_opts={o['name']:o['id'] for o in orgs}; current_org=a.get('organization_id') or (next(iter(org_opts.values())) if org_opts else None); current_org_label=next((k for k,v in org_opts.items() if v==current_org),next(iter(org_opts),'—'))
    agencies=list_agencies(ENGINE,current_org,active_only=True) if current_org else []; agency_opts={'— Siège / aucune agence —':None,**{g['name']:g['id'] for g in agencies}}; current_agency_label=next((k for k,v in agency_opts.items() if v==a.get('agency_id')),'— Siège / aucune agence —')
    with st.form(f'action_settings_{a["id"]}'):
        c1,c2=st.columns(2);title=c1.text_input('Intitulé',value=a['title']);subtitle=c2.text_input('Intitulé complémentaire',value=a.get('subtitle') or '')
        c1,c2=st.columns(2);start_date=c1.date_input('Date de début',value=date.fromisoformat(a['start_date']) if a.get('start_date') else date.today());end_date=c2.date_input('Date de fin',value=date.fromisoformat(a['end_date']) if a.get('end_date') else date.today())
        c1,c2,c3=st.columns(3);pt_label=c1.selectbox('Type de prestation',list(prestation_labels),index=list(prestation_labels).index(current_label));mode=c2.selectbox('Organisation',['INTRA','INTER','INDIVIDUEL'],index=['INTRA','INTER','INDIVIDUEL'].index(a['mode']));current_status=normalize_action_status(a.get('status'));c3.text_input('Statut',value=current_status,disabled=True);status=current_status
        c1,c2,c3=st.columns(3);planned=c1.number_input('Durée prévue (h)',min_value=0.0,step=.5,value=float(a.get('planned_hours') or 0));expected=c2.number_input('Nombre prévu de participants',min_value=1,step=1,value=int(a.get('expected_participants') or 1));group=c3.text_input('Code groupe / session',value=a.get('group_code') or '')
        c1,c2=st.columns(2);client=c1.text_input('Client / entreprise',value=a.get('client_name') or '');client_type=c2.selectbox('Type client',['Non précisé','Professionnel','Particulier'],index=['Non précisé','Professionnel','Particulier'].index(a.get('client_type')) if a.get('client_type') in ['Non précisé','Professionnel','Particulier'] else 0)
        c1,c2=st.columns(2); org_label=c1.selectbox('Organisme',list(org_opts),index=list(org_opts).index(current_org_label) if current_org_label in org_opts else 0); agency_label=c2.selectbox('Agence / établissement',list(agency_opts),index=list(agency_opts).index(current_agency_label) if current_agency_label in agency_opts else 0)
        st.markdown('**Modules activés**');m1,m2,m3,m4=st.columns(4);use_attendance=m1.checkbox('Émargement',value=bool(a.get('use_attendance',1)));use_hot=m2.checkbox('Évaluation à chaud',value=bool(a.get('use_quality_hot',0)));use_cold=m3.checkbox('Évaluation à froid',value=bool(a.get('use_quality_cold',0)));use_trainer=m4.checkbox('Retour intervenant',value=bool(a.get('use_trainer_feedback',0)))
        trainers=list_trainers(ENGINE,active_only=True); trainer_opts={'— Aucun intervenant référencé —':None,**{f"{t['full_name']} — {t.get('email') or 'sans email'}":t['id'] for t in trainers}}; trainer_labels=list(trainer_opts); current_idx=next((i for i,l in enumerate(trainer_labels) if trainer_opts[l]==a.get('trainer_id')),0)
        c1,c2=st.columns(2);trainer_label=c1.selectbox('Intervenant référencé',trainer_labels,index=current_idx);location=c2.text_input('Lieu / modalité',value=a.get('location') or '')
        admins=q(ENGINE,'SELECT email,full_name FROM admins WHERE active=1 ORDER BY full_name,email');admin_opts={f"{x.get('full_name') or x['email']} — {x['email']}":x['email'] for x in admins};cur_email=a.get('admin_email') or st.session_state.admin_email;cur_admin=next((k for k,v in admin_opts.items() if v==cur_email),list(admin_opts)[0] if admin_opts else '');admin_label=st.selectbox('Administrateur référent',list(admin_opts),index=list(admin_opts).index(cur_admin) if cur_admin in admin_opts else 0);admin_email=admin_opts.get(admin_label,cur_email);notes=st.text_area('Observations',value=a.get('notes') or '')
        save=st.form_submit_button('Enregistrer les modifications',type='primary')
    if save:
        try:
            nature=pt_label
            update_action(ENGINE,a['id'],{'title':title,'subtitle':subtitle or None,'nature':nature,'mode':mode,'client_name':client or None,'client_type':client_type,'group_code':group or None,'planned_hours':float(planned),'expected_participants':int(expected),'admin_email':admin_email,'trainer_name':a.get('trainer_name'),'trainer_email':a.get('trainer_email'),'location':location or None,'notes':notes or None,'status':status},st.session_state.admin_email)
            safe_set_action_modules(ENGINE,a['id'],prestation_labels[pt_label],use_attendance,use_hot,use_cold,use_trainer,org_opts.get(org_label),agency_opts.get(agency_label),st.session_state.admin_email)
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
                        if cand:
                            st.warning('Participant ajouté. Une correspondance bénéficiaire existe déjà ou paraît possible : aucun rattachement automatique n’a été effectué. Utilisez la rubrique « Espace bénéficiaire » ci-dessous pour décider.')
                        else:
                            bid=create_beneficiary_from_participant(ENGINE,pid,st.session_state.admin_email)
                            tok=create_beneficiary_portal_invitation(ENGINE,bid,pp['email'],st.session_state.admin_email)
                            bb=one(ENGINE,'SELECT * FROM beneficiaries WHERE id=:b',{'b':bid});okb,msgb=send_beneficiary_invitation_email(bb,tok)
                            if okb: st.success(msgb)
                            else: st.warning(msgb)
                if one(ENGINE,'SELECT COUNT(*) n FROM slots WHERE action_id=:a',{'a':a['id']})['n']:
                    ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ)
                sync_quality_schedule(a['id'],st.session_state.admin_email)
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
                if bdi!='__ERR__': update_participant(ENGINE,ep['id'],{'last_name':ln.strip().upper(),'birth_name':bn.strip().upper() or None,'first_name':fn.strip().title(),'birth_date':bdi,'email':em.strip() or None,'employee_id':emp.strip() or None,'company_name':co.strip() or None,'phone':ph.strip() or None,'individual_action_no':ino.strip() or None,'active':1},st.session_state.admin_email);st.success('Participant modifié.');rerun()
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
            st.caption(f"Email de connexion : {(acc or {}).get('email') or linked.get('current_email') or 'non configuré'}")
            c1,c2=st.columns(2)
            if c1.button('Envoyer / renouveler l’invitation espace',key=f'ben_inv_{pid_sel}',disabled=not bool(pp.get('email'))):
                try:
                    tok=create_beneficiary_portal_invitation(ENGINE,linked['id'],pp.get('email'),st.session_state.admin_email);bb=one(ENGINE,'SELECT * FROM beneficiaries WHERE id=:b',{'b':linked['id']});okb,msgb=send_beneficiary_invitation_email(bb,tok)
                    if okb: st.success(msgb)
                    else: st.warning(msgb)
                except Exception as ex: st.error(str(ex))
            new_email=c2.text_input('Nouvel email de connexion',value=(acc or {}).get('email') or linked.get('current_email') or '',key=f'ben_email_{pid_sel}')
            if st.button('Enregistrer le nouvel email sans recréer la personne',key=f'ben_email_save_{pid_sel}'):
                try:
                    tok=update_beneficiary_email(ENGINE,linked['id'],new_email,st.session_state.admin_email)
                    target=dict(linked);target['current_email']=new_email
                    okb,msgb=send_beneficiary_invitation_email(target,tok)
                    if okb: st.success('Demande de changement enregistrée. La nouvelle adresse deviendra l’identifiant de connexion après vérification par email.')
                    else: st.warning(msgb)
                    rerun()
                except Exception as ex: st.error(str(ex))
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
                    except Exception as ex: st.error(str(ex))
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
            display.append({'Séance':i,'Date':x['slot_date'],'Début':x['start_time'],'Fin':x['end_time'],'Durée':slot_duration_hours(x),'Envoi initial':initial,'Relance 1':x['reminder1_offset_min'],'Relance 2':x['reminder2_offset_min']})
        st.dataframe(pd.DataFrame(display),use_container_width=True,hide_index=True)

    st.markdown('### Ajouter une nouvelle séance')
    last_date=date.fromisoformat(slots[-1]['slot_date']) if slots else date.today()
    last_start=time.fromisoformat(slots[-1]['start_time']) if slots else time(9,0)
    last_end=time.fromisoformat(slots[-1]['end_time']) if slots else time(10,30)
    with st.form(f'addslot_{a["id"]}',clear_on_submit=False):
        c1,c2,c3=st.columns(3)
        d=c1.date_input('Date de la nouvelle séance',value=last_date,key=f'd{a["id"]}')
        stt=c2.time_input('Début',value=last_start,key=f's{a["id"]}')
        ett=c3.time_input('Fin',value=last_end,key=f'e{a["id"]}')
        c1,c2,c3=st.columns(3)
        send_mode=c1.selectbox('Envoi du lien d’émargement',['Au début du créneau','10 min avant la fin','À la fin du créneau','Personnalisé'],key=f'sendmode{a["id"]}')
        custom=c2.number_input('Décalage personnalisé (min / fin)',value=-10,step=5,key=f'customsend{a["id"]}',disabled=send_mode!='Personnalisé')
        close=c3.number_input('Émargement possible après la fin pendant (min)',value=1440,step=60,key=f'add_close_offset_{a["id"]}')
        c1,c2=st.columns(2)
        r1=c1.number_input('Relance 1 après fin (min)',value=20,step=5,key=f'r1{a["id"]}')
        r2=c2.number_input('Relance 2 après fin (min)',value=120,step=15,key=f'r2{a["id"]}')
        add=st.form_submit_button('➕ AJOUTER CETTE NOUVELLE SÉANCE',type='primary')
    if add:
        if send_mode=='Au début du créneau': send=slot_start_offset_minutes(stt.strftime('%H:%M'),ett.strftime('%H:%M'))
        elif send_mode=='10 min avant la fin': send=-10
        elif send_mode=='À la fin du créneau': send=0
        else: send=int(custom)
        add_slot(ENGINE,a['id'],d.isoformat(),stt.strftime('%H:%M'),ett.strftime('%H:%M'),st.session_state.admin_email,int(send),int(r1),int(r2),int(close))
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
            c1,c2,c3=st.columns(3);ed=c1.date_input('Date',value=date.fromisoformat(es['slot_date']));est=c2.time_input('Début',value=time.fromisoformat(es['start_time']));eet=c3.time_input('Fin',value=time.fromisoformat(es['end_time']))
            c1,c2,c3,c4=st.columns(4)
            edit_send_mode=c1.selectbox('Envoi initial',['Au début du créneau','Personnalisé'],index=0 if current_begin else 1)
            esend=c2.number_input('Décalage personnalisé (min / fin)',value=int(es['send_offset_min']),step=5,disabled=edit_send_mode!='Personnalisé')
            er1=c3.number_input('Relance 1',value=int(es['reminder1_offset_min']),step=5);er2=c4.number_input('Relance 2',value=int(es['reminder2_offset_min']),step=15)
            eclose=st.number_input('Émargement possible après la fin pendant (min)',value=int(es['close_offset_min']),step=60)
            reason=st.text_input('Motif de modification (recommandé si l’action a commencé)');save_slot=st.form_submit_button('Enregistrer les modifications de cette séance')
        if save_slot:
            final_send=slot_start_offset_minutes(est.strftime('%H:%M'),eet.strftime('%H:%M')) if edit_send_mode=='Au début du créneau' else int(esend)
            ok,msg=safe_update_slot(ENGINE,es['id'],{'slot_date':ed.isoformat(),'start_time':est.strftime('%H:%M'),'end_time':eet.strftime('%H:%M'),'send_offset_min':final_send,'reminder1_offset_min':int(er1),'reminder2_offset_min':int(er2),'close_offset_min':int(eclose),'reason':reason},st.session_state.admin_email)
            if ok:
                ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ);sync_quality_schedule(a['id'],st.session_state.admin_email);st.success('Séance modifiée et échéances futures recalculées, y compris les campagnes qualité non envoyées.');rerun()
            else: st.error(msg)

    with st.expander('📅 Reporter une séance non encore réalisée',expanded=False):
        rep_choices={f"Séance {i} — {x['slot_date']} {x['start_time']}–{x['end_time']}":x for i,x in enumerate(slots,1)}
        rep_lab=st.selectbox('Séance à reporter',list(rep_choices),key=f'repsel{a["id"]}');rsrc=rep_choices[rep_lab]
        c1,c2,c3=st.columns(3);rpd=c1.date_input('Nouvelle date',value=date.fromisoformat(rsrc['slot_date']),key=f'rpd{rsrc["id"]}');rps=c2.time_input('Nouveau début',value=time.fromisoformat(rsrc['start_time']),key=f'rps{rsrc["id"]}');rpe=c3.time_input('Nouvelle fin',value=time.fromisoformat(rsrc['end_time']),key=f'rpe{rsrc["id"]}')
        rpr=st.text_input('Motif du report',key=f'rpr{rsrc["id"]}')
        if st.button('REPORTER CETTE SÉANCE',key=f'report{rsrc["id"]}'):
            ns=report_slot(ENGINE,rsrc['id'],rpd.isoformat(),rps.strftime('%H:%M'),rpe.strftime('%H:%M'),st.session_state.admin_email,rpr or 'Report')
            if ns: ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ);sync_quality_schedule(a['id'],st.session_state.admin_email);st.success('Séance reportée et échéances futures recalculées.');rerun()
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
        ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ);st.success('Liens personnels et échéances de relance préparés.');rerun()
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
            if st.button('Envoyer maintenant le lien personnel'):
                ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ);url=token_url(ENGINE,pp['id'],ss['id'],BASE_URL)
                cfg=mail_cfg();subject=f"Clarté360 — émargement — {a['action_no']}";body=f"<p>Bonjour {pp['first_name']},</p><p>Merci d'émarger votre présence pour <strong>{a['title']}</strong>, le {ss['slot_date']} de {ss['start_time']} à {ss['end_time']}.</p><p><a href='{url}' style='background:#008080;color:white;padding:12px 18px;text-decoration:none;border-radius:8px'>SIGNER MA PRÉSENCE</a></p><p>Ce lien personnel ne nécessite pas le code QR à 4 chiffres.</p>{privacy_notice_html(a['id'])}"
                try:
                    send_mail(cfg,pp['email'],subject,body);audit(ENGINE,'MANUAL_EMAIL_SENT',a['id'],st.session_state.admin_email,'participant',pp['id'],{'slot_id':ss['id'],'email':pp['email']});st.success('Email envoyé.')
                except Exception as ex: st.error(f"Envoi impossible : {ex}")
    elif not smtp_enabled:
        st.info('L’envoi manuel sera disponible dès que la configuration MAIL sera activée.')
    else:
        st.info('L’envoi manuel est disponible après activation de l’action.')

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
        absent=q(ENGINE,"""SELECT p.* FROM attendance_status x JOIN participants p ON p.id=x.participant_id WHERE x.slot_id=:s AND x.status='ABSENT'""",{'s':ss['id']});opts={f"{p['last_name']} {p['first_name']}":p['id'] for p in absent};sel=st.multiselect('Absents concernés',list(opts),default=list(opts));c1,c2,c3=st.columns(3);rd=c1.date_input('Date du rattrapage',key=f'rd{a["id"]}');rs=c2.time_input('Début rattrapage',value=time(9,0),key=f'rs{a["id"]}');re=c3.time_input('Fin rattrapage',value=time(12,0),key=f're{a["id"]}')
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
        if c1.button('Déclencher / reprogrammer l’envoi initial maintenant',key=f'qsend{selected["id"]}',disabled=selected['status']=='COMPLETED'):
            if force_quality_event_now(ENGINE,selected['id'],'INITIAL'): st.success('Envoi placé dans la file du worker.');rerun()
            else: st.warning('Événement initial introuvable ou déjà traité.')
        if selected['status']=='COMPLETED':
            try:
                qpdf=quality_response_pdf(ENGINE,selected['id'])
                c2.download_button('Télécharger le questionnaire PDF',qpdf,f"{a['action_no']}_questionnaire_{selected['id']}.pdf",'application/pdf',use_container_width=True)
            except Exception as ex: c2.error(f'PDF qualité : {ex}')
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
            set_action_client_contacts(ENGINE,a['id'],ca,cf,cq,cb,co,st.session_state.admin_email);configure_final_transmission(ENGINE,a['id'],transmit,tq,tf,of,ol,oe,st.session_state.admin_email);st.success('Destinataires enregistrés.');rerun()
    if normalize_action_status(a.get('status')) in ('CLOTUREE','ARCHIVEE'):
        try:
            bundle=action_final_bundle(ENGINE,a['id'],False,st.session_state.admin_email)
            st.download_button('Télécharger le dossier final collectif',bundle,f"{a['action_no']}_dossier_final.zip",'application/zip',use_container_width=True)
            st.caption('Destinataires dossier final : '+(', '.join(action_client_recipients(ENGINE,a['id'],'FINAL')) or 'aucun contact configuré')+' · Qualité à froid : '+(', '.join(action_client_recipients(ENGINE,a['id'],'QUALITY')) or 'aucun contact qualité configuré'))
        except Exception as ex: st.warning(f'Dossier final : {ex}')
    transmissions=q(ENGINE,"SELECT transmission_type,recipient_email,document_name,status,sent_at,last_error,created_at FROM client_transmissions WHERE action_id=:a ORDER BY id DESC",{'a':a['id']})
    if transmissions:
        st.markdown('### Journal des transmissions client')
        st.dataframe(pd.DataFrame(transmissions),use_container_width=True,hide_index=True)
    st.markdown('### Bibliothèque documentaire de l’action')
    stats=document_storage_stats(ENGINE);st.caption(f"Stockage physique mutualisé : {stats['files']} fichier(s), {stats['bytes']/1024/1024:.2f} Mo, {stats['references']} référence(s) logique(s).")
    with st.expander('Déposer un document par n° d’action',expanded=False):
        st.caption(f"Action sélectionnée : {a['action_no']}. Le document de cours sera visible par tous les bénéficiaires de cette action disposant d’un espace personnel.")
        category=st.selectbox('Catégorie',['COURS','ADMINISTRATIF'],format_func=lambda x:'Documents de cours' if x=='COURS' else 'Document administratif',key=f'doccat_{a["id"]}')
        updoc=st.file_uploader('Fichier (25 Mo maximum)',type=['pdf','doc','docx','xls','xlsx','ppt','pptx','txt','csv','jpg','jpeg','png','webp','zip'],key=f'action_doc_{a["id"]}')
        if st.button('DÉPOSER LE DOCUMENT',type='primary',key=f'action_doc_btn_{a["id"]}',disabled=updoc is None):
            try:
                rid,h,dedup=store_document(ENGINE,updoc.getvalue(),updoc.name,category,st.session_state.admin_email,action_id=a['id'],audience='ACTION_BENEFICIARIES')
                st.success('Document enregistré. '+('Déduplication SHA-256 : le fichier physique existait déjà.' if dedup else 'Nouveau contenu physique enregistré.'));rerun()
            except Exception as ex: st.error(str(ex))
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
    except Exception as e: st.error(f'PDF collectif : {e}')
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
    except Exception as e: st.error(f'Archive : {e}')

def audit_tab(a):
    st.subheader('Piste d’audit')
    logs=q(ENGINE,'SELECT * FROM audit_log WHERE action_id=:a ORDER BY id DESC',{'a':a['id']})
    if logs: st.dataframe(pd.DataFrame(logs),use_container_width=True,hide_index=True)

def settings_screen():
    header('Clarté360 — Paramètres','Administration de l’application')
    tabg,tabo,tabag,taba,tabt=st.tabs(['Général','Organisme','Agences / établissements','Administrateurs','Formateurs / accompagnants'])
    with tabg:
        st.write(f"URL publique configurée : `{BASE_URL}`")
        smtp_enabled=bool(mail_cfg().get('enabled'));st.write('Email automatique (secret MAIL) :', '✅ activé' if smtp_enabled else '⚠️ non activé')
        st.markdown(privacy_notice_html(),unsafe_allow_html=True)
        st.caption('Les paramètres sensibles sont stockés dans .streamlit/secrets.toml sur le VPS et ne doivent jamais être envoyés sur GitHub.')
        st.markdown('### Bases d’import mémorisées')
        st.caption("Une base chargée depuis votre navigateur est copiée instantanément sur le VPS. Cette copie de travail peut ensuite servir à importer plusieurs actions, même si le classeur d’origine est ouvert ou n’est plus accessible.")
        ci=source_info('CLARTE360'); ai=source_info('ADCA')
        st.write('Clarté360 :',ci.get('snapshot_path') or 'aucune copie mémorisée')
        st.write('ADCA :',ai.get('snapshot_path') or 'aucune copie mémorisée')
        with st.form('source_paths'):
            cp=st.text_input('Chemin source Clarté360 sur le VPS / volume monté (optionnel)',value=ci.get('external_path') or '')
            ap=st.text_input('Chemin source ADCA sur le VPS / volume monté (optionnel)',value=ai.get('external_path') or '')
            sv=st.form_submit_button('Enregistrer les chemins')
        if sv:
            set_external_path('CLARTE360',cp); set_external_path('ADCA',ap); st.success('Chemins enregistrés.')
        st.caption("Un chemin Windows de votre PC (ex. C:\\...) n’est pas directement accessible depuis le VPS. Dans ce cas, utilisez le chargement du fichier : la copie VPS est ensuite conservée.")
        c1,c2=st.columns(2)
        if c1.button('Actualiser la copie Clarté360 depuis le chemin serveur',disabled=not bool(ci.get('external_path'))):
            try: refresh_from_external('CLARTE360'); st.success('Copie Clarté360 actualisée.')
            except Exception as ex: st.error(str(ex))
        if c2.button('Actualiser la copie ADCA depuis le chemin serveur',disabled=not bool(ai.get('external_path'))):
            try: refresh_from_external('ADCA'); st.success('Copie ADCA actualisée.')
            except Exception as ex: st.error(str(ex))
    with tabo:
        st.subheader('Identité de l’organisme')
        org=get_organization(ENGINE); oid=(org or {}).get('id')
        with st.form('organization_settings'):
            c1,c2=st.columns(2); name=c1.text_input('Nom commercial *',value=(org or {}).get('name') or ''); legal=c2.text_input('Raison sociale',value=(org or {}).get('legal_name') or '')
            address=st.text_input('Adresse du siège',value=(org or {}).get('address') or ''); c1,c2,c3=st.columns(3); postal=c1.text_input('Code postal',value=(org or {}).get('postal_code') or ''); city=c2.text_input('Ville',value=(org or {}).get('city') or ''); country=c3.text_input('Pays',value=(org or {}).get('country') or 'France')
            c1,c2,c3,c4=st.columns(4); siret=c1.text_input('SIRET',value=(org or {}).get('siret') or ''); rcs=c2.text_input('RCS',value=(org or {}).get('rcs') or ''); naf=c3.text_input('NAF',value=(org or {}).get('naf') or ''); vat=c4.text_input('TVA / Id CEE',value=(org or {}).get('vat_id') or '')
            c1,c2,c3=st.columns(3); nda=c1.text_input('NDA',value=(org or {}).get('nda') or ''); website=c2.text_input('Site web',value=(org or {}).get('website') or ''); phone=c3.text_input('Téléphone',value=(org or {}).get('phone') or '')
            c1,c2=st.columns(2); general_email=c1.text_input('Email général',value=(org or {}).get('general_email') or ''); tz=c2.text_input('Fuseau horaire IANA',value=(org or {}).get('timezone') or 'Europe/Paris')
            c1,c2=st.columns(2); privacy_contact=c1.text_input('Contact RGPD',value=(org or {}).get('privacy_contact') or ''); retention=c2.number_input('Conservation indicative (mois)',min_value=0,step=1,value=int((org or {}).get('retention_months') or 0))
            privacy_notice=st.text_area('Notice RGPD',value=(org or {}).get('privacy_notice') or '',height=130)
            c1,c2=st.columns(2); from_name=c1.text_input('Nom affiché expéditeur',value=(org or {}).get('email_from_name') or ''); from_address=c2.text_input('Adresse expéditeur (si différente du secret SMTP)',value=(org or {}).get('email_from_address') or '')
            save_org=st.form_submit_button('Enregistrer l’organisme',type='primary')
        if save_org:
            if not name.strip(): st.error('Nom commercial obligatoire.')
            else:
                try:
                    from zoneinfo import ZoneInfo; ZoneInfo(tz.strip())
                    upsert_organization(ENGINE,oid,{'name':name.strip(),'legal_name':legal.strip() or None,'address':address.strip() or None,'postal_code':postal.strip() or None,'city':city.strip() or None,'country':country.strip() or None,'siret':siret.strip() or None,'rcs':rcs.strip() or None,'naf':naf.strip() or None,'vat_id':vat.strip() or None,'nda':nda.strip() or None,'website':website.strip() or None,'general_email':general_email.strip() or None,'phone':phone.strip() or None,'timezone':tz.strip(),'privacy_contact':privacy_contact.strip() or None,'privacy_notice':privacy_notice.strip() or None,'logo_path':(org or {}).get('logo_path'),'favicon_path':(org or {}).get('favicon_path'),'primary_color':(org or {}).get('primary_color'),'secondary_color':(org or {}).get('secondary_color'),'email_from_name':from_name.strip() or None,'email_from_address':from_address.strip() or None,'retention_months':int(retention) or None},st.session_state.admin_email);st.success('Organisme enregistré.');rerun()
                except Exception as ex: st.error(f'Paramètres invalides : {ex}')
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
                    else: add_agency(ENGINE,org['id'],{'name':aname.strip(),'address':aaddress.strip() or None,'postal_code':apostal.strip() or None,'city':acity.strip() or None,'country':acountry.strip() or None,'siret':asiret.strip() or None,'nda':anda.strip() or None,'email':aemail.strip() or None,'phone':aphone.strip() or None},st.session_state.admin_email);rerun()
            if agencies:
                amap={f"{x['name']} — {x.get('city') or ''}":x for x in agencies}; alab=st.selectbox('Agence à gérer',list(amap),key='agency_manage'); ag=amap[alab]
                with st.form('edit_agency_form'):
                    c1,c2=st.columns(2); ename=c1.text_input('Nom',value=ag['name']); eemail=c2.text_input('Email',value=ag.get('email') or ''); eaddress=st.text_input('Adresse',value=ag.get('address') or ''); c1,c2,c3=st.columns(3); epostal=c1.text_input('Code postal',value=ag.get('postal_code') or ''); ecity=c2.text_input('Ville',value=ag.get('city') or ''); ecountry=c3.text_input('Pays',value=ag.get('country') or ''); c1,c2,c3=st.columns(3); esiret=c1.text_input('SIRET',value=ag.get('siret') or ''); enda=c2.text_input('NDA',value=ag.get('nda') or ''); ephone=c3.text_input('Téléphone',value=ag.get('phone') or ''); eactive=st.checkbox('Agence active',value=bool(ag.get('active'))); esave=st.form_submit_button('Enregistrer les modifications')
                if esave: update_agency(ENGINE,ag['id'],{'name':ename.strip(),'address':eaddress.strip() or None,'postal_code':epostal.strip() or None,'city':ecity.strip() or None,'country':ecountry.strip() or None,'siret':esiret.strip() or None,'nda':enda.strip() or None,'email':eemail.strip() or None,'phone':ephone.strip() or None,'active':int(eactive)},st.session_state.admin_email);rerun()
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
                else: execute(ENGINE,'UPDATE admins SET password_hash=:p WHERE email=:e',{'p':hash_password(np1),'e':st.session_state.admin_email});audit(ENGINE,'ADMIN_PASSWORD_CHANGED',actor=st.session_state.admin_email,entity_type='admin',details={});st.success('Mot de passe modifié.')
        with st.expander('Ajouter un administrateur'):
            with st.form('add_admin'):
                n=st.text_input('Nom et prénom');e=st.text_input('Email').strip().lower();p1=st.text_input('Mot de passe initial',type='password');p2=st.text_input('Confirmer',type='password');add=st.form_submit_button('Créer administrateur')
            if add:
                if not e or len(p1)<10 or p1!=p2: st.error('Email requis, mot de passe d’au moins 10 caractères et confirmation identique.')
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
                    except Exception as ex: st.error(f'Impossible : {ex}')
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
    footer()

# ROUTING PUBLIC SIGNATURE
params=st.query_params
if params.get('beneficiary_invite'):
    beneficiary_invitation_page(params.get('beneficiary_invite'));st.stop()
if params.get('beneficiary_portal'):
    beneficiary_portal_page();st.stop()
if params.get('quality_token'):
    quality_page(params.get('quality_token'));st.stop()
if params.get('trainer_invite'):
    trainer_invitation_page(params.get('trainer_invite'));st.stop()
if params.get('trainer_reset_request'):
    trainer_reset_request_page();st.stop()
if params.get('trainer_reset'):
    trainer_reset_page(params.get('trainer_reset'));st.stop()
if params.get('trainer_portal'):
    trainer_portal_page();st.stop()
if params.get('trainer_token'):
    trainer_page(params.get('trainer_token'));st.stop()
if params.get('token'):
    signature_page(token=params.get('token'));st.stop()
if params.get('slot_token'):
    signature_page(slot_token=params.get('slot_token'));st.stop()

if not setup_or_login(): st.stop()
if '_next_nav' in st.session_state:
    st.session_state['nav'] = st.session_state.pop('_next_nav')
page=sidebar()
if page=='Tableau de bord': dashboard()
elif page=='Nouvelle action':
    if st.session_state.get('import_create_active'):
        create_action_screen(st.session_state.get('import_prefill'),st.session_state.get('import_parts'))
    else:
        create_action_screen()
elif page=='Importer Clarté360 / CSV':import_screen()
elif page=='Actions':actions_list()
elif page=='Paramètres':settings_screen()
