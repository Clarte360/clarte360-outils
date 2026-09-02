from __future__ import annotations
import io, os, json, csv, base64
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
from excel_import import read_clarte360_xlsm
from pdf_utils import collective_pdf, individual_pdf, certificate_pdf
from mailer import send_mail

st.set_page_config(page_title=APP_NAME,page_icon=str(ICON_PATH),layout='wide',initial_sidebar_state='expanded')
st.markdown(CSS,unsafe_allow_html=True)

def secret(section,key,default=None):
    try:return st.secrets.get(section,{}).get(key,default)
    except:return default
DB_URL=secret('database','url',None); ENGINE=make_engine(DB_URL);init_db(ENGINE)
BASE_URL=secret('app','base_url','http://localhost:8501');TZ=secret('app','timezone','Europe/Paris')

def footer(): st.markdown(f"<div class='c360-footer'>{LEGAL_LINE_1}<br>{LEGAL_LINE_2}</div>",unsafe_allow_html=True)
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
    consent=st.checkbox('Je confirme l’exactitude de ces informations.')
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
            audit(ENGINE,'SIGNATURE_RECORDED',row['action_id'],f"participant:{row['id']}",'signature',f"{row['id']}/{row['slot_id']}",{'method':method,'sha256':digest})
            st.success(f"Votre présence a bien été enregistrée à {datetime.now(ZoneInfo(TZ)).strftime('%H:%M')}. Merci.");st.balloons()
        except Exception: st.info('Cet émargement a déjà été enregistré.')

def trainer_page(token):
    row=one(ENGINE,"""SELECT t.action_id,a.* FROM trainer_access_tokens t JOIN actions a ON a.id=t.action_id WHERE t.token=:t AND t.active=1""",{'t':token})
    if not row: header('Clarté360 — Intervenant');st.error('Accès intervenant invalide.');footer();return
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
    if c1.button('Marquer ABSENT',use_container_width=True): set_attendance_status(ENGINE,pp['id'],slot['id'],'ABSENT','Déclaré par intervenant',f"trainer:{row.get('trainer_email') or row.get('trainer_name')}");st.success('Absence enregistrée.');rerun()
    if c2.button('Remettre EN ATTENTE',use_container_width=True): set_attendance_status(ENGINE,pp['id'],slot['id'],'EN_ATTENTE','Correction intervenant',f"trainer:{row.get('trainer_email') or row.get('trainer_name')}");rerun()
    if pp.get('email') and st.button('Relancer ce participant par email'):
        ensure_tokens_and_events(ENGINE,row['action_id'],BASE_URL,TZ);url=token_url(ENGINE,pp['id'],slot['id'],BASE_URL);cfg=dict(st.secrets.get('smtp',{}));subject=f"Clarté360 — émargement — {row['action_no']}";body=f"<p>Bonjour {pp['first_name']},</p><p>Merci de régulariser votre émargement pour le {slot['slot_date']} de {slot['start_time']} à {slot['end_time']}.</p><p><a href='{url}'>SIGNER / RÉGULARISER</a></p>"
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

def sidebar():
    st.sidebar.image(str(LOGO_PATH),width=70);st.sidebar.markdown(f"**{st.session_state.get('admin_name','Administrateur')}**")
    pages=['Tableau de bord','Nouvelle action','Importer Clarté360 / CSV','Actions','Paramètres']
    page=st.sidebar.radio('Navigation',pages,key='nav')
    st.sidebar.divider()
    if st.sidebar.button('Se déconnecter',use_container_width=True): st.session_state.clear();rerun()
    return page

def create_action_screen(prefill=None,participants_prefill=None):
    header('Clarté360 — Nouvelle action','Création d’une action et de son dossier d’émargement')
    p=prefill or {}
    with st.form('new_action'):
        c1,c2=st.columns(2);action_no=c1.text_input('N° D’ACTION *',value=p.get('action_no','')).strip().upper();nature=c2.selectbox('Nature de l’action',['Formation','Bilan de compétences','Coaching / accompagnement','Autre'],index=0)
        title=st.text_input('Intitulé *',value=p.get('title',''));subtitle=st.text_input('Intitulé complémentaire',value=p.get('subtitle') or '')
        c1,c2,c3,c4=st.columns(4);mode=c1.selectbox('Organisation',['INTRA','INTER','INDIVIDUEL']);planned=c2.number_input('Durée contractuelle prévue (h)',min_value=0.0,step=.5,value=float(p.get('planned_hours') or 0));expected=c3.number_input('Nombre prévu de stagiaires',min_value=1,step=1,value=int(p.get('expected_participants') or (1 if mode=='INDIVIDUEL' else 1)));group=c4.text_input('Code de groupe / session INTER',value='')
        c1,c2=st.columns(2);client=c1.text_input('Client / entreprise (facultatif)',value=p.get('client_name') or '');client_type=c2.selectbox('Type client',['Non précisé','Professionnel','Particulier'])
        c1,c2=st.columns(2);trainer=c1.text_input('Intervenant',value=p.get('trainer_name') or '');location=c2.text_input('Lieu / modalité',value=p.get('location') or '')
        admin_email=st.text_input('Email administrateur destinataire',value=st.session_state.get('admin_email',''));notes=st.text_area('Observations')
        ok=st.form_submit_button('Créer l’action',type='primary')
    if ok:
        if not action_no or not title: st.error('Le n° d’action et l’intitulé sont obligatoires.')
        elif one(ENGINE,'SELECT id FROM actions WHERE action_no=:n',{'n':action_no}): st.error('Ce numéro d’action existe déjà.')
        else:
            aid=create_action(ENGINE,{'action_no':action_no,'title':title,'subtitle':subtitle or None,'nature':nature,'mode':mode,'client_name':client or None,'client_type':client_type,'group_code':group or None,'planned_hours':planned,'expected_participants':int(expected),'admin_email':admin_email,'trainer_name':trainer or None,'trainer_email':None,'location':location or None,'notes':notes or None,'source':p.get('source') or 'SAISIE MANUELLE'},st.session_state.admin_email)
            pins=[]
            for pd in participants_prefill or []:
                pid,pin=add_participant(ENGINE,aid,pd.copy(),st.session_state.admin_email);pins.append((pid,pin))
            st.session_state.selected_action=aid;st.success('Action créée. Vous pouvez maintenant ajouter les participants et les créneaux.');st.session_state['_next_nav']='Actions';rerun()
    footer()

def import_screen():
    header('Clarté360 — Import','Importer une action depuis la base Clarté360 ou un CSV de participants')
    tab1,tab2=st.tabs(['Base GESTION OF CLARTE360 (.xlsm)','CSV participants'])
    with tab1:
        f=st.file_uploader('Sélectionnez GESTION OF CLARTE360 EN COURS.xlsm',type=['xlsm','xlsx'],key='xlsm')
        n=st.text_input('N° D’ACTION à rechercher',placeholder='CLA0001').strip().upper()
        if st.button('Lire l’action',type='primary') and f and n:
            try:
                data,parts=read_clarte360_xlsm(f.getvalue(),n)
                if not data: st.error('Action introuvable dans les onglets CONV ADM et STAGIAIRE.')
                else:
                    st.session_state.import_prefill=data;st.session_state.import_parts=parts;st.success(f"Action trouvée — {len(parts)} participant(s) détecté(s). Le NIR n’est pas importé.")
            except Exception as e: st.error(f"Lecture impossible : {e}")
        if st.session_state.get('import_prefill'):
            d=st.session_state.import_prefill;st.json({k:v for k,v in d.items() if k not in ['default_start','default_end']});
            if st.button('Créer cette action dans Clarté360 Émargements'):
                st.session_state.prefill_create=True;st.session_state['_next_nav']='Nouvelle action';rerun()
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
    total=len(acts);open_n=sum(a['status']!='ARCHIVE' for a in acts);pending=one(ENGINE,"SELECT COUNT(*) n FROM email_events WHERE status='PENDING'")['n'];signed=one(ENGINE,"SELECT COUNT(*) n FROM signatures WHERE status='VALIDE'")['n']
    c1,c2,c3,c4=st.columns(4)
    for c,n,l in [(c1,total,'Actions'),(c2,open_n,'Actives'),(c3,signed,'Signatures'),(c4,pending,'Envois / relances prévus')]: c.markdown(f"<div class='c360-kpi'><div class='n'>{n}</div><div class='l'>{l}</div></div>",unsafe_allow_html=True)
    st.subheader('Actions récentes')
    rows=[]
    for a in acts[:20]:
        pr=action_progress(ENGINE,a['id']);rows.append({'Action':a['action_no'],'Intitulé':a['title'],'Mode':a['mode'],'Participants':pr['participants'],'Créneaux':pr['slots'],'Signatures':f"{pr['signed']}/{pr['expected']}",'Avancement':f"{pr['percent']}%"})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    footer()

def actions_list():
    header('Clarté360 — Actions','Reprendre, modifier et suivre une action')
    acts=q(ENGINE,'SELECT * FROM actions ORDER BY id DESC')
    if not acts: st.info('Aucune action pour le moment.');footer();return
    labels={f"{a['action_no']} — {a['title']}":a['id'] for a in acts};sel=st.selectbox('Choisir une action',list(labels));aid=labels[sel];st.session_state.selected_action=aid
    action_detail(aid);footer()

def action_detail(aid):
    a=one(ENGINE,'SELECT * FROM actions WHERE id=:a',{'a':aid});pr=action_progress(ENGINE,aid)
    st.markdown(f"<div class='c360-card'><h3>{a['action_no']} — {a['title']}</h3>{a.get('subtitle') or ''}<br><b>{a['mode']}</b> — Durée prévue : {a['planned_hours']:g} h — Statut : {a['status']}</div>",unsafe_allow_html=True)
    c1,c2,c3,c4=st.columns(4);c1.metric('Participants',pr['participants']);c2.metric('Créneaux',pr['slots']);c3.metric('Signatures',f"{pr['signed']}/{pr['expected']}");c4.metric('Avancement',f"{pr['percent']} %")
    tabs=st.tabs(['Paramètres action','Participants','Calendrier','Envois & relances','Suivi','Documents','Journal'])
    with tabs[0]: action_settings_tab(a)
    with tabs[1]: participants_tab(a)
    with tabs[2]: calendar_tab(a)
    with tabs[3]: dispatch_tab(a)
    with tabs[4]: tracking_tab(a)
    with tabs[5]: documents_tab(a)
    with tabs[6]: audit_tab(a)

def action_settings_tab(a):
    st.subheader('Paramètres de l’action')
    with st.form(f'action_settings_{a["id"]}'):
        c1,c2=st.columns(2);title=c1.text_input('Intitulé',value=a['title']);subtitle=c2.text_input('Intitulé complémentaire',value=a.get('subtitle') or '')
        c1,c2,c3=st.columns(3);nature=c1.selectbox('Nature',['Formation','Bilan de compétences','Coaching / accompagnement','Autre'],index=['Formation','Bilan de compétences','Coaching / accompagnement','Autre'].index(a['nature']) if a['nature'] in ['Formation','Bilan de compétences','Coaching / accompagnement','Autre'] else 0);mode=c2.selectbox('Organisation',['INTRA','INTER','INDIVIDUEL'],index=['INTRA','INTER','INDIVIDUEL'].index(a['mode']));status=c3.selectbox('Statut',['BROUILLON','ACTIVE','TERMINEE','ARCHIVE'],index=['BROUILLON','ACTIVE','TERMINEE','ARCHIVE'].index(a['status']) if a['status'] in ['BROUILLON','ACTIVE','TERMINEE','ARCHIVE'] else 0)
        c1,c2,c3=st.columns(3);planned=c1.number_input('Durée prévue (h)',min_value=0.0,step=.5,value=float(a.get('planned_hours') or 0));expected=c2.number_input('Nombre prévu de stagiaires',min_value=1,step=1,value=int(a.get('expected_participants') or 1));group=c3.text_input('Code groupe / session',value=a.get('group_code') or '')
        c1,c2=st.columns(2);client=c1.text_input('Client / entreprise',value=a.get('client_name') or '');client_type=c2.selectbox('Type client',['Non précisé','Professionnel','Particulier'],index=['Non précisé','Professionnel','Particulier'].index(a.get('client_type')) if a.get('client_type') in ['Non précisé','Professionnel','Particulier'] else 0)
        c1,c2=st.columns(2);trainer=c1.text_input('Intervenant',value=a.get('trainer_name') or '');location=c2.text_input('Lieu / modalité',value=a.get('location') or '')
        admin_email=st.text_input('Email administrateur destinataire',value=a.get('admin_email') or st.session_state.admin_email);notes=st.text_area('Observations',value=a.get('notes') or '')
        save=st.form_submit_button('Enregistrer les modifications',type='primary')
    if save:
        update_action(ENGINE,a['id'],{'title':title,'subtitle':subtitle or None,'nature':nature,'mode':mode,'client_name':client or None,'client_type':client_type,'group_code':group or None,'planned_hours':float(planned),'expected_participants':int(expected),'admin_email':admin_email,'trainer_name':trainer or None,'trainer_email':a.get('trainer_email'),'location':location or None,'notes':notes or None,'status':status},st.session_state.admin_email);st.success('Action mise à jour.');rerun()

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
            submit=st.form_submit_button('Ajouter',type='primary')
        if submit:
            if not last.strip() or not first.strip(): st.error('Nom et prénom obligatoires.')
            else:
                
                try: birth_iso=datetime.strptime(bdate.strip(),'%d/%m/%Y').date().isoformat() if bdate.strip() else None
                except ValueError: st.error('Date de naissance invalide : utilisez JJ/MM/AAAA.');return
                dup=participant_duplicate(ENGINE,a['id'],last,first,birth_iso,email)
                if dup: st.error(f"Participant potentiellement déjà présent : {dup['last_name']} {dup['first_name']}.");return
                pid,pin=add_participant(ENGINE,a['id'],{'individual_action_no':indno.strip() or None,'last_name':last.strip().upper(),'birth_name':birth.strip().upper() or None,'first_name':first.strip().title(),'birth_date':birth_iso,'email':email.strip() or None,'employee_id':emp.strip() or None,'company_name':company.strip() or None,'phone':phone.strip() or None},st.session_state.admin_email)
                st.success(f"Participant ajouté. Code QR personnel : {pin} — notez-le maintenant.");st.code(pin);st.info('Pour des raisons de sécurité, ce code ne pourra pas être réaffiché en clair.');
                if one(ENGINE,'SELECT COUNT(*) n FROM slots WHERE action_id=:a',{'a':a['id']})['n']:
                    ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ)
    if parts:
        ids={f"{p['last_name']} {p['first_name']}":p['id'] for p in parts};lab=st.selectbox('Supprimer un participant', ['—']+list(ids),key=f'delp{a["id"]}')
        if lab!='—' and st.button('Supprimer le participant sélectionné'):
            if one(ENGINE,'SELECT id FROM signatures WHERE participant_id=:p',{'p':ids[lab]}): st.error('Impossible : ce participant possède déjà une signature. Désactivez-le plutôt dans une version ultérieure.')
            else: delete_participant(ENGINE,ids[lab],st.session_state.admin_email);rerun()
        st.markdown('**Réinitialiser un code personnel QR**')
        rlab=st.selectbox('Participant concerné',list(ids),key=f'pinreset{a["id"]}')
        if st.button('Générer un nouveau code à 4 chiffres',key=f'pinbtn{a["id"]}'):
            newpin=reset_participant_pin(ENGINE,ids[rlab],st.session_state.admin_email);st.success('Nouveau code généré. Communiquez-le au participant :');st.code(newpin)

def calendar_tab(a):
    st.subheader('Calendrier et créneaux')
    slots=q(ENGINE,'SELECT * FROM slots WHERE action_id=:a ORDER BY slot_date,start_time',{'a':a['id']})
    total=sum(slot_duration_hours(s) for s in slots);delta=round(total-float(a['planned_hours'] or 0),2)
    if abs(delta)<0.01: st.markdown(f"<div class='c360-ok'>✅ Calendrier cohérent : <b>{total:g} h / {a['planned_hours']:g} h</b></div>",unsafe_allow_html=True)
    else: st.markdown(f"<div class='c360-warn'>⚠️ Total des créneaux : <b>{total:g} h</b> — durée prévue : <b>{a['planned_hours']:g} h</b> — écart : <b>{delta:+g} h</b></div>",unsafe_allow_html=True)
    if slots:
        st.dataframe(pd.DataFrame([{'ID':s['id'],'Date':s['slot_date'],'Début':s['start_time'],'Fin':s['end_time'],'Durée':slot_duration_hours(s),'Envoi (min/fin)':s['send_offset_min'],'Relance 1':s['reminder1_offset_min'],'Relance 2':s['reminder2_offset_min']} for s in slots]),use_container_width=True,hide_index=True)
        st.markdown('**Modifier un créneau**')
        edit_choices={f"#{x['id']} — {x['slot_date']} {x['start_time']}–{x['end_time']}":x for x in slots}; edit_lab=st.selectbox('Créneau à modifier',list(edit_choices),key=f'editsel{a["id"]}'); es=edit_choices[edit_lab]
        with st.form(f'editslot{es["id"]}'):
            c1,c2,c3=st.columns(3);ed=c1.date_input('Date',value=date.fromisoformat(es['slot_date']));est=c2.time_input('Début',value=time.fromisoformat(es['start_time']));eet=c3.time_input('Fin',value=time.fromisoformat(es['end_time']))
            c1,c2,c3,c4=st.columns(4);esend=c1.number_input('Envoi vs fin (min)',value=int(es['send_offset_min']),step=5);er1=c2.number_input('Relance 1',value=int(es['reminder1_offset_min']),step=5);er2=c3.number_input('Relance 2',value=int(es['reminder2_offset_min']),step=15);eclose=c4.number_input('Clôture',value=int(es['close_offset_min']),step=60)
            reason=st.text_input('Motif de modification (recommandé si l’action a commencé)');save_slot=st.form_submit_button('Enregistrer le créneau')
        if save_slot:
            ok,msg=safe_update_slot(ENGINE,es['id'],{'slot_date':ed.isoformat(),'start_time':est.strftime('%H:%M'),'end_time':eet.strftime('%H:%M'),'send_offset_min':int(esend),'reminder1_offset_min':int(er1),'reminder2_offset_min':int(er2),'close_offset_min':int(eclose),'reason':reason},st.session_state.admin_email)
            if ok: ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ);st.success('Créneau modifié et journalisé.');rerun()
            else: st.error(msg)
        st.markdown('**Reporter un créneau non encore réalisé**')
        c1,c2,c3=st.columns(3);rpd=c1.date_input('Nouvelle date',key=f'rpd{es["id"]}');rps=c2.time_input('Nouveau début',value=time.fromisoformat(es['start_time']),key=f'rps{es["id"]}');rpe=c3.time_input('Nouvelle fin',value=time.fromisoformat(es['end_time']),key=f'rpe{es["id"]}')
        rpr=st.text_input('Motif du report',key=f'rpr{es["id"]}')
        if st.button('REPORTER CE CRÉNEAU',key=f'report{es["id"]}'):
            ns=report_slot(ENGINE,es['id'],rpd.isoformat(),rps.strftime('%H:%M'),rpe.strftime('%H:%M'),st.session_state.admin_email,rpr or 'Report')
            if ns: ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ);st.success(f'Créneau reporté. Nouveau créneau #{ns}.');rerun()
            else: st.error('Ce créneau contient déjà une preuve ou ne peut plus être reporté. Utilisez absence/rattrapage si la séance a déjà eu lieu.')
    with st.expander('Ajouter un créneau',expanded=not slots):
        c1,c2,c3=st.columns(3);d=c1.date_input('Date',key=f'd{a["id"]}');s=c2.time_input('Début',value=time(9,0),key=f's{a["id"]}');e=c3.time_input('Fin',value=time(12,30),key=f'e{a["id"]}')
        c1,c2,c3,c4=st.columns(4);send=c1.number_input('Envoi vs fin (min)',value=-10,step=5);r1=c2.number_input('Relance 1 après fin',value=20,step=5);r2=c3.number_input('Relance 2 après fin',value=120,step=15);close=c4.number_input('Clôture après fin',value=1440,step=60)
        if st.button('Ajouter ce créneau',type='primary'):
            add_slot(ENGINE,a['id'],d.isoformat(),s.strftime('%H:%M'),e.strftime('%H:%M'),st.session_state.admin_email,int(send),int(r1),int(r2),int(close))
            if one(ENGINE,'SELECT COUNT(*) n FROM participants WHERE action_id=:a AND active=1',{'a':a['id']})['n']:
                ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ)
            rerun()
    if slots:
        st.markdown('**Dupliquer les créneaux d’une date vers une autre date**')
        dates=sorted(set(s['slot_date'] for s in slots));c1,c2=st.columns(2);src=c1.selectbox('Date source',dates);dst=c2.date_input('Nouvelle date',key=f'dup{a["id"]}')
        if st.button('Dupliquer cette journée'):
            for s in [x for x in slots if x['slot_date']==src]: add_slot(ENGINE,a['id'],dst.isoformat(),s['start_time'],s['end_time'],st.session_state.admin_email,s['send_offset_min'],s['reminder1_offset_min'],s['reminder2_offset_min'],s['close_offset_min'])
            ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ);rerun()
        st.markdown('**Supprimer un créneau (possible uniquement s’il n’est pas signé)**')
        choices={f"#{s['id']} — {s['slot_date']} {s['start_time']}–{s['end_time']}":s['id'] for s in slots};ch=st.selectbox('Créneau',list(choices),key=f'dels{a["id"]}')
        if st.button('Supprimer ce créneau'):
            ok,msg=delete_slot(ENGINE,choices[ch],st.session_state.admin_email);st.success('Créneau supprimé.') if ok else st.error(msg);rerun() if ok else None

def dispatch_tab(a):
    st.subheader('Envois automatiques et relances')
    parts=q(ENGINE,'SELECT * FROM participants WHERE action_id=:a AND active=1',{'a':a['id']});slots=q(ENGINE,'SELECT * FROM slots WHERE action_id=:a ORDER BY slot_date,start_time',{'a':a['id']})
    if not parts or not slots: st.info('Ajoutez d’abord au moins un participant et un créneau.');return
    if st.button('Préparer / actualiser toutes les demandes de signature',type='primary'):
        ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ);st.success('Liens personnels et échéances de relance préparés.');rerun()
    events=q(ENGINE,"""SELECT e.*,p.last_name,p.first_name,p.email,s.slot_date,s.start_time,s.end_time FROM email_events e JOIN participants p ON p.id=e.participant_id JOIN slots s ON s.id=e.slot_id WHERE p.action_id=:a ORDER BY e.due_at""",{'a':a['id']})
    if events: st.dataframe(pd.DataFrame(events)[['last_name','first_name','email','slot_date','start_time','end_time','event_type','due_at','status','sent_at','last_error']],use_container_width=True,hide_index=True)
    st.markdown('### Envoi / relance manuelle')
    smtp_enabled=bool(secret('smtp','enabled',False))
    if smtp_enabled:
        email_parts=[p for p in parts if p.get('email')]
        if email_parts:
            pc={f"{p['last_name']} {p['first_name']} — {p['email']}":p for p in email_parts};pl=st.selectbox('Participant à relancer',list(pc),key=f'mailp{a["id"]}');pp=pc[pl]
            sc={f"{x['slot_date']} {x['start_time']}–{x['end_time']}":x for x in slots};sl=st.selectbox('Créneau à relancer',list(sc),key=f'mails{a["id"]}');ss=sc[sl]
            if st.button('Envoyer maintenant le lien personnel'):
                ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ);url=token_url(ENGINE,pp['id'],ss['id'],BASE_URL)
                cfg=dict(st.secrets.get('smtp',{}));subject=f"Clarté360 — émargement — {a['action_no']}";body=f"<p>Bonjour {pp['first_name']},</p><p>Merci d'émarger votre présence pour <strong>{a['title']}</strong>, le {ss['slot_date']} de {ss['start_time']} à {ss['end_time']}.</p><p><a href='{url}' style='background:#008080;color:white;padding:12px 18px;text-decoration:none;border-radius:8px'>SIGNER MA PRÉSENCE</a></p>"
                try:
                    send_mail(cfg,pp['email'],subject,body);audit(ENGINE,'MANUAL_EMAIL_SENT',a['id'],st.session_state.admin_email,'participant',pp['id'],{'slot_id':ss['id'],'email':pp['email']});st.success('Email envoyé.')
                except Exception as ex: st.error(f"Envoi impossible : {ex}")
    else:
        st.info('L’envoi manuel sera disponible dès que la configuration SMTP du VPS sera activée.')

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
        if c1.button('Marquer ABSENT',key=f'abs{a["id"]}'): set_attendance_status(ENGINE,pp['id'],ss['id'],'ABSENT',reason,st.session_state.admin_email);rerun()
        if c2.button('Remettre EN ATTENTE',key=f'wait{a["id"]}'): set_attendance_status(ENGINE,pp['id'],ss['id'],'EN_ATTENTE',reason,st.session_state.admin_email);rerun()
        st.markdown('### Créer une séance de rattrapage')
        absent=q(ENGINE,"""SELECT p.* FROM attendance_status x JOIN participants p ON p.id=x.participant_id WHERE x.slot_id=:s AND x.status='ABSENT'""",{'s':ss['id']});opts={f"{p['last_name']} {p['first_name']}":p['id'] for p in absent};sel=st.multiselect('Absents concernés',list(opts),default=list(opts));c1,c2,c3=st.columns(3);rd=c1.date_input('Date du rattrapage',key=f'rd{a["id"]}');rs=c2.time_input('Début rattrapage',value=time(9,0),key=f'rs{a["id"]}');re=c3.time_input('Fin rattrapage',value=time(12,0),key=f're{a["id"]}')
        if st.button('Créer le créneau de rattrapage',key=f'catch{a["id"]}'):
            if not sel: st.error('Sélectionnez au moins un participant absent.')
            else: ns=create_catchup_slot(ENGINE,ss['id'],rd.isoformat(),rs.strftime('%H:%M'),re.strftime('%H:%M'),[opts[x] for x in sel],st.session_state.admin_email);ensure_tokens_and_events(ENGINE,a['id'],BASE_URL,TZ);st.success(f'Rattrapage créé : créneau #{ns}.');rerun()

def documents_tab(a):
    st.subheader('Documents et archivage')
    try:
        cpdf=collective_pdf(ENGINE,a['id']);st.download_button('Télécharger la feuille collective PDF',cpdf,f"{a['action_no']}_emargement_collectif.pdf",'application/pdf')
    except Exception as e: st.error(f'PDF collectif : {e}')
    parts=q(ENGINE,'SELECT * FROM participants WHERE action_id=:a ORDER BY last_name,first_name',{'a':a['id']})
    if parts:
        labels={f"{p['last_name']} {p['first_name']}":p for p in parts};lab=st.selectbox('Participant',list(labels),key=f'docp{a["id"]}');p=labels[lab]
        c1,c2=st.columns(2)
        ipdf=individual_pdf(ENGINE,p['id']);c1.download_button('Feuille individuelle PDF',ipdf,f"{a['action_no']}_{p['last_name']}_{p['first_name']}_emargement.pdf",'application/pdf',use_container_width=True)
        ok_cert,issues=can_issue_certificate(ENGINE,p['id'])
        if ok_cert:
            cert=certificate_pdf(ENGINE,p['id']);c2.download_button('Certificat de réalisation PDF',cert,f"{a['action_no']}_{p['last_name']}_{p['first_name']}_certificat_realisation.pdf",'application/pdf',use_container_width=True)
        else: c2.warning('Certificat définitif indisponible : '+ ' ; '.join(issues[:4]))
    js=export_action_json(ENGINE,a['id']);st.download_button('Exporter le dossier JSON portable',js,f"{a['action_no']}_dossier.json",'application/json')
    try:
        pdfs={'emargement_collectif.pdf':collective_pdf(ENGINE,a['id'])};z=export_action_zip(ENGINE,a['id'],pdfs);st.download_button('Exporter l’archive complète ZIP',z,f"{a['action_no']}_archive_complete.zip",'application/zip')
    except Exception as e: st.error(f'Archive : {e}')

def audit_tab(a):
    st.subheader('Piste d’audit')
    logs=q(ENGINE,'SELECT * FROM audit_log WHERE action_id=:a ORDER BY id DESC',{'a':a['id']})
    if logs: st.dataframe(pd.DataFrame(logs),use_container_width=True,hide_index=True)

def settings_screen():
    header('Clarté360 — Paramètres','État de la configuration du serveur')
    st.write(f"URL publique configurée : `{BASE_URL}`")
    smtp_enabled=bool(secret('smtp','enabled',False));st.write('Email automatique :', '✅ activé' if smtp_enabled else '⚠️ non activé')
    st.caption('Les paramètres sensibles sont stockés dans .streamlit/secrets.toml sur le VPS et ne doivent jamais être envoyés sur GitHub.')
    footer()

# ROUTING PUBLIC SIGNATURE
params=st.query_params
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
    if st.session_state.pop('prefill_create',False): create_action_screen(st.session_state.get('import_prefill'),st.session_state.get('import_parts'))
    else:create_action_screen()
elif page=='Importer Clarté360 / CSV':import_screen()
elif page=='Actions':actions_list()
elif page=='Paramètres':settings_screen()
