from __future__ import annotations
import time, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from db import make_engine,init_db,q,execute,audit,one
from services import token_url, organization_runtime_config, quality_token_url, email_event_due_utc, generate_due_final_bundles, portal_retention_candidates, mark_portal_retention_warning, due_portal_purges, purge_beneficiary_portal_documents, action_module_enabled, create_or_sync_teams_room, teams_room, teams_roles, mark_teams_guest_invitation, store_teams_attendance_report, refresh_countersign_communications, delivery_mode_label, trainer_microsoft_identity, mark_trainer_entra_identity, mark_trainer_entra_not_found, consume_pip_outbox, refresh_pip_connector_runtime_status
from mailer import send_mail, resolve_mail_config
from graph_client import GraphClient, graph_config_from_mapping, graph_config_missing

try:
 import tomllib
except ImportError:
 import tomli as tomllib
ROOT=Path(__file__).resolve().parent

def load_cfg():
    p=ROOT/'.streamlit'/'secrets.toml'
    return tomllib.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def _claim_communication(eng,event_id):
    token=uuid.uuid4().hex; now=datetime.now(timezone.utc).isoformat()
    with eng.begin() as c:
        r=c.exec_driver_sql("UPDATE communication_events SET status='EN_FILE',claimed_at=?,claim_token=?,attempts=attempts+1,updated_at=? WHERE id=? AND status='A_ENVOYER'",(now,token,now,event_id))
        if r.rowcount!=1:return None
    return token

def _run_communication_events(eng,smtp,base,limit=100):
    now=datetime.now(timezone.utc).isoformat()
    events=q(eng,"""SELECT ce.*,a.action_no,a.title,a.location,a.delivery_mode,p.first_name,p.last_name,
      t.full_name trainer_name,s.slot_date,s.start_time,s.end_time
      FROM communication_events ce JOIN actions a ON a.id=ce.action_id
      LEFT JOIN participants p ON p.id=ce.participant_id LEFT JOIN trainers t ON t.id=ce.trainer_id LEFT JOIN slots s ON s.id=ce.slot_id
      WHERE ce.status='A_ENVOYER' AND (ce.due_at IS NULL OR ce.due_at<=:n) ORDER BY COALESCE(ce.due_at,ce.created_at),ce.id LIMIT :lim""",{'n':now,'lim':limit})
    sent=0
    for e in events:
        recipient=(e.get('recipient_email') or '').strip()
        if not recipient:
            execute(eng,"UPDATE communication_events SET status='ECHEC',last_error='Adresse email absente',updated_at=:u WHERE id=:i",{'u':now,'i':e['id']});continue
        claim=_claim_communication(eng,e['id'])
        if not claim:continue
        runtime=organization_runtime_config(eng,e['action_id']);org=runtime['organization'];cfg=dict(smtp)
        if org.get('email_from_name'):cfg['from_name']=org['email_from_name']
        if org.get('email_from_address'):cfg['from_email']=org['email_from_address']
        org_name=org.get('name') or 'Organisme'
        try:
            if e['communication_type']=='PLANNING_CONFIRMATION':
                slots=q(eng,"SELECT slot_date,start_time,end_time FROM slots WHERE action_id=:a AND COALESCE(status,'PREVU') NOT IN ('ANNULE') ORDER BY slot_date,start_time",{'a':e['action_id']})
                rows=''.join(f"<li>{x['slot_date']} — {x['start_time']}–{x['end_time']}</li>" for x in slots) or '<li>Planning en cours de finalisation</li>'
                modality=delivery_mode_label(e.get('delivery_mode'))
                subject=f"{org_name} — Confirmation de votre planning — {e['action_no']}"
                body=f"<p>Bonjour {e.get('first_name') or ''},</p><p>Votre inscription à <strong>{e['title']}</strong> est enregistrée.</p><p><strong>Modalité :</strong> {modality}<br><strong>Lieu / précision :</strong> {e.get('location') or 'À confirmer'}</p><ul>{rows}</ul><p><strong>Si vous êtes inscrit(e) à une formation en ligne, vous accéderez à la réunion depuis votre espace Clarté360, onglet Teams.</strong></p>"
            elif e['communication_type'] in ('TEAMS_REMINDER_H2','TEAMS_REMINDER_H15'):
                is_trainer=bool(e.get('trainer_id'))
                who=e.get('trainer_name') if is_trainer else ((e.get('first_name') or '')+' '+(e.get('last_name') or '')).strip()
                delay='2 heures' if e['communication_type']=='TEAMS_REMINDER_H2' else '15 minutes'
                portal=(f"{base.rstrip('/')}?trainer_portal=1&action_id={e['action_id']}" if is_trainer else f"{base.rstrip('/')}?beneficiary_portal=1")
                portal_label='MON ESPACE INTERVENANT' if is_trainer else 'MON ESPACE BÉNÉFICIAIRE'
                subject=f"{org_name} — Rappel séance dans {delay} — action {e['action_no']}"
                body=f"<p>Bonjour {who or ''},</p><p>Votre séance <strong>{e['title']}</strong> débute dans <strong>{delay}</strong>.</p><p><strong>N° d’action : {e['action_no']}</strong><br><strong>Date :</strong> {e.get('slot_date') or ''}<br><strong>Horaire :</strong> {e.get('start_time') or ''}–{e.get('end_time') or ''}</p><p>Connectez-vous à votre espace Clarté360, ouvrez l’action <strong>{e['action_no']}</strong>, puis rendez-vous dans l’onglet <strong>Teams</strong> pour rejoindre la séance.</p><p><a href='{portal}'>{portal_label}</a></p>"
            elif e['communication_type']=='COUNTERSIGN_REQUEST':
                direct=f"{base.rstrip('/')}?trainer_portal=1&action_id={e['action_id']}&slot_id={e['slot_id']}"
                subject=f"{org_name} — Contresignature requise — {e['action_no']}"
                body=f"<p>Bonjour {e.get('trainer_name') or ''},</p><p>Merci de vérifier les présences/absences et de contresigner le créneau du <strong>{e.get('slot_date')} de {e.get('start_time')} à {e.get('end_time')}</strong>.</p><p><a href='{direct}'>OUVRIR LA CONTRESIGNATURE</a></p><p>La page est utilisable sur ordinateur, tablette et smartphone.</p>"
            else:
                execute(eng,"UPDATE communication_events SET status='ANNULE',claim_token=NULL,last_error='Type de communication non géré par le worker',updated_at=:u WHERE id=:i AND claim_token=:c",{'u':now,'i':e['id'],'c':claim});continue
            send_mail(cfg,recipient,subject,body)
            at=datetime.now(timezone.utc).isoformat()
            execute(eng,"UPDATE communication_events SET status='ENVOYE',sent_at=:at,claim_token=NULL,claimed_at=NULL,last_error=NULL,updated_at=:at WHERE id=:i AND claim_token=:c",{'at':at,'i':e['id'],'c':claim})
            audit(eng,'COMMUNICATION_SENT',e['action_id'],'worker','communication_event',e['id'],{'type':e['communication_type'],'recipient':recipient});sent+=1
        except Exception as ex:
            execute(eng,"UPDATE communication_events SET status='ECHEC',claim_token=NULL,claimed_at=NULL,last_error=:er,updated_at=:u WHERE id=:i AND claim_token=:c",{'er':str(ex)[:500],'u':datetime.now(timezone.utc).isoformat(),'i':e['id'],'c':claim})
            audit(eng,'COMMUNICATION_FAILED',e['action_id'],'worker','communication_event',e['id'],{'type':e['communication_type'],'recipient':recipient,'error':str(ex)[:300]})
    return sent

def _claim_event(eng, event_id):
    token=uuid.uuid4().hex; now=datetime.now(timezone.utc).isoformat()
    with eng.begin() as c:
        r=c.exec_driver_sql("UPDATE email_events SET status='SENDING',claimed_at=?,claim_token=?,attempts=attempts+1 WHERE id=? AND status='PENDING'",(now,token,event_id))
        if r.rowcount!=1:return None
    return token

def _quarantine_stale_sending(eng, minutes=15):
    """Never auto-resend an ambiguous SMTP delivery after a crash.

    An event left SENDING may have reached SMTP before the process stopped. It is moved
    to UNKNOWN_DELIVERY for administrator review instead of being resent automatically.
    This deliberately favours duplicate prevention over blind retry.
    """
    cutoff=(datetime.now(timezone.utc)-timedelta(minutes=minutes)).isoformat()
    rows=q(eng,"SELECT id,participant_id,slot_id FROM email_events WHERE status='SENDING' AND claimed_at<:c",{'c':cutoff})
    for r in rows:
        execute(eng,"UPDATE email_events SET status='UNKNOWN_DELIVERY',last_error='Worker interrupted during SMTP delivery; manual review required to avoid duplicate send.' WHERE id=:i AND status='SENDING'",{'i':r['id']})
    return len(rows)

def _claim_quality_event(eng, event_id):
    token=uuid.uuid4().hex; now=datetime.now(timezone.utc).isoformat()
    with eng.begin() as c:
        r=c.exec_driver_sql("UPDATE quality_email_events SET status='SENDING',claimed_at=?,claim_token=?,attempts=attempts+1 WHERE id=? AND status='PENDING'",(now,token,event_id))
        if r.rowcount!=1:return None
    return token

def _quarantine_stale_quality(eng, minutes=15):
    cutoff=(datetime.now(timezone.utc)-timedelta(minutes=minutes)).isoformat()
    rows=q(eng,"SELECT id FROM quality_email_events WHERE status='SENDING' AND claimed_at<:c",{'c':cutoff})
    for r in rows:
        execute(eng,"UPDATE quality_email_events SET status='UNKNOWN_DELIVERY',last_error='Worker interrupted during SMTP delivery; manual review required to avoid duplicate send.' WHERE id=:i AND status='SENDING'",{'i':r['id']})
    return len(rows)

def _quality_mail_content(e, org_name, link, privacy, privacy_contact):
    first=e.get('first_name') or e.get('trainer_full_name') or 'Madame, Monsieur'
    kind=e['campaign_kind']; et=e['event_type']; title=e['action_title']
    if kind=='HOT':
        subject=f"{org_name} — Votre avis sur « {title} » — quelques minutes"
        intro=f"Votre prestation <strong>{title}</strong> vient de se terminer. Votre retour nous aide à mesurer la qualité de l’accompagnement et à améliorer concrètement nos prestations."
    elif kind=='COLD' and e.get('prestation_type')=='BILAN_COMPETENCES':
        subject=f"{org_name} — Six mois après votre bilan de compétences — votre retour"
        intro=f"Six mois après la fin de votre bilan de compétences <strong>{title}</strong>, nous vous proposons de faire le point sur son utilité et les évolutions intervenues depuis sa clôture."
    elif kind=='COLD':
        subject=f"{org_name} — Quelques mois après « {title} » — votre retour"
        intro=f"Quelques mois se sont écoulés depuis <strong>{title}</strong>. Nous vous proposons un court questionnaire afin d’identifier ce qui a perduré, ce qui vous a été utile et ce qui pourrait encore être amélioré."
    else:
        subject=f"{org_name} — Retour qualité intervenant — {title}"
        intro=f"L’action <strong>{title}</strong> est terminée. Nous vous invitons à renseigner votre retour sur les conditions de réalisation : organisation, logistique, moyens, supports, environnement et éventuels aléas. Ce questionnaire ne porte pas sur l’évaluation des participants."
    if et!='INITIAL': subject='Relance — '+subject
    body=f"""<p>Bonjour {first},</p><p>{intro}</p><p><a href='{link}'>OUVRIR LE QUESTIONNAIRE</a></p><p>Il peut être complété depuis un ordinateur, une tablette ou un téléphone.</p><hr><p style='font-size:12px;color:#555'><strong>Information données personnelles :</strong> {privacy} {'Contact : '+privacy_contact if privacy_contact else ''}</p>"""
    return subject,body

def _run_quality_events(eng,smtp,base,limit=50):
    now=datetime.now(timezone.utc).isoformat()
    events=q(eng,"""SELECT qe.*,c.token,c.campaign_kind,c.status campaign_status,c.action_id,qt.prestation_type,
      a.title action_title,a.action_no,p.first_name,p.last_name,p.email participant_email,t.full_name trainer_full_name,t.email trainer_email,c.external_recipient_email,c.external_recipient_name
      FROM quality_email_events qe JOIN quality_campaigns c ON c.id=qe.campaign_id
      JOIN questionnaire_templates qt ON qt.id=c.template_id JOIN actions a ON a.id=c.action_id
      LEFT JOIN participants p ON p.id=c.participant_id LEFT JOIN trainers t ON t.id=c.trainer_id
      WHERE qe.status='PENDING' AND qe.due_at<=:n AND c.status<>'COMPLETED' AND a.status NOT IN ('BROUILLON','PLANIFIEE') AND (qe.event_type='INITIAL' OR qe.event_type LIKE 'MANUAL_%') ORDER BY qe.due_at LIMIT :lim""",{'n':now,'lim':limit})
    sent=0
    for e in events:
        recipient=e.get('participant_email') or e.get('trainer_email') or e.get('external_recipient_email')
        if not recipient:
            execute(eng,"UPDATE quality_email_events SET status='SKIPPED',last_error='No recipient email' WHERE id=:i",{'i':e['id']});continue
        claim=_claim_quality_event(eng,e['id'])
        if not claim:continue
        runtime=organization_runtime_config(eng,e['action_id']);org=runtime['organization'];local_smtp=dict(smtp)
        org_name=org.get('name') or 'Organisme'; privacy=org.get('privacy_notice') or "Les informations recueillies sont utilisées pour le suivi de l’action et l’amélioration de la qualité des prestations.";privacy_contact=org.get('privacy_contact') or org.get('general_email') or ''
        if org.get('email_from_name'):local_smtp['from_name']=org['email_from_name']
        if org.get('email_from_address'):local_smtp['from_email']=org['email_from_address']
        subject,body=_quality_mail_content(e,org_name,quality_token_url(e['token'],base),privacy,privacy_contact)
        try:
            send_mail(local_smtp,recipient,subject,body)
            sent_at=datetime.now(timezone.utc).isoformat()
            execute(eng,"UPDATE quality_email_events SET status='SENT',sent_at=:s,claim_token=NULL,last_error=NULL WHERE id=:i AND claim_token=:c",{'s':sent_at,'i':e['id'],'c':claim})
            if e['event_type']=='INITIAL': execute(eng,"UPDATE quality_campaigns SET status='SENT',sent_at=COALESCE(sent_at,:s) WHERE id=:c",{'s':sent_at,'c':e['campaign_id']})
            audit(eng,'QUALITY_EMAIL_SENT',e['action_id'],'worker','quality_email_event',e['id'],{'event_type':e['event_type'],'campaign_kind':e['campaign_kind']});sent+=1
        except Exception as ex:
            execute(eng,"UPDATE quality_email_events SET status='PENDING',claim_token=NULL,claimed_at=NULL,last_error=:er WHERE id=:i AND claim_token=:c",{'er':str(ex)[:500],'i':e['id'],'c':claim})
    return sent

def _claim_client_transmission(eng, transmission_id):
    token=uuid.uuid4().hex; now=datetime.now(timezone.utc).isoformat()
    with eng.begin() as c:
        r=c.exec_driver_sql("UPDATE client_transmissions SET status='SENDING',claimed_at=?,claim_token=?,attempts=attempts+1 WHERE id=? AND status='PENDING'",(now,token,transmission_id))
        if r.rowcount!=1:return None
    return token

def _quarantine_stale_client_transmissions(eng, minutes=15):
    cutoff=(datetime.now(timezone.utc)-timedelta(minutes=minutes)).isoformat()
    rows=q(eng,"SELECT id FROM client_transmissions WHERE status='SENDING' AND claimed_at<:c",{'c':cutoff})
    for r in rows:
        execute(eng,"UPDATE client_transmissions SET status='UNKNOWN_DELIVERY',last_error='Worker interrupted during SMTP delivery; manual review required to avoid duplicate send.' WHERE id=:i AND status='SENDING'",{'i':r['id']})
    return len(rows)

def _client_transmission_content(eng, row):
    a=one(eng,'SELECT * FROM actions WHERE id=:a',{'a':row['action_id']}) or {}
    runtime=organization_runtime_config(eng,row['action_id']); org=runtime['organization']; org_name=org.get('name') or 'Organisme'
    dates=''
    if a.get('start_date') or a.get('end_date'):
        dates=f"{a.get('start_date') or ''} au {a.get('end_date') or a.get('start_date') or ''}".strip()
    contact=org.get('general_email') or org.get('privacy_contact') or ''
    if row['transmission_type']=='FINAL':
        path=Path(a.get('final_bundle_path') or '')
        if not path.is_file(): raise FileNotFoundError('Dossier final introuvable sur le serveur.')
        subject=f"{org_name} — Dossier de fin d’action — {a.get('action_no') or ''} — {a.get('title') or ''}"
        docs='feuille(s) d’émargement définitive(s), certificat(s) de réalisation et évaluation(s) à chaud disponible(s)'
        body=f"""<p>Bonjour,</p><p>Veuillez trouver en pièce jointe le dossier de fin d’action.</p><p><strong>Organisme :</strong> {org_name}<br><strong>Action :</strong> {a.get('action_no') or ''} — {a.get('title') or ''}<br><strong>Prestation :</strong> {a.get('prestation_type') or a.get('nature') or ''}<br><strong>Dates :</strong> {dates}<br><strong>Client :</strong> {a.get('client_name') or ''}<br><strong>Documents transmis :</strong> {docs}</p><p>Contact organisme : {contact}</p>"""
        return subject,body,{'filename':path.name,'data':path.read_bytes(),'maintype':'application','subtype':'zip'}
    if row['transmission_type']=='COLD':
        cid=row.get('campaign_id')
        if not cid: raise ValueError('Campagne qualité à froid absente de la transmission.')
        from pdf_utils import quality_response_pdf
        data=quality_response_pdf(eng,cid)
        camp=one(eng,"""SELECT c.*,p.first_name,p.last_name FROM quality_campaigns c LEFT JOIN participants p ON p.id=c.participant_id WHERE c.id=:c""",{'c':cid}) or {}
        who=(f"{camp.get('first_name') or ''} {camp.get('last_name') or ''}").strip()
        filename=row.get('document_name') or f'evaluation_a_froid_{cid}.pdf'
        subject=f"{org_name} — Évaluation à froid — {a.get('action_no') or ''} — {a.get('title') or ''}"
        body=f"""<p>Bonjour,</p><p>L’évaluation à froid suivante vient d’être complétée. Elle est transmise indépendamment du dossier initial de fin d’action.</p><p><strong>Organisme :</strong> {org_name}<br><strong>Action :</strong> {a.get('action_no') or ''} — {a.get('title') or ''}<br><strong>Prestation :</strong> {a.get('prestation_type') or a.get('nature') or ''}<br><strong>Dates :</strong> {dates}<br><strong>Client :</strong> {a.get('client_name') or ''}<br><strong>Participant :</strong> {who}<br><strong>Document transmis :</strong> évaluation à froid</p><p>Contact organisme : {contact}</p>"""
        return subject,body,{'filename':filename,'data':data,'maintype':'application','subtype':'pdf'}
    raise ValueError('Type de transmission client inconnu.')

def _run_client_transmissions(eng,smtp,limit=30):
    rows=q(eng,"SELECT * FROM client_transmissions WHERE status='PENDING' ORDER BY created_at,id LIMIT :lim",{'lim':limit});sent=0
    for row in rows:
        claim=_claim_client_transmission(eng,row['id'])
        if not claim: continue
        try:
            subject,body,attachment=_client_transmission_content(eng,row)
            runtime=organization_runtime_config(eng,row['action_id']);org=runtime['organization'];local_smtp=dict(smtp)
            if org.get('email_from_name'):local_smtp['from_name']=org['email_from_name']
            if org.get('email_from_address'):local_smtp['from_email']=org['email_from_address']
            send_mail(local_smtp,row['recipient_email'],subject,body,[attachment])
            sent_at=datetime.now(timezone.utc).isoformat()
            execute(eng,"UPDATE client_transmissions SET status='SENT',sent_at=:s,claim_token=NULL,claimed_at=NULL,last_error=NULL WHERE id=:i AND claim_token=:c",{'s':sent_at,'i':row['id'],'c':claim})
            audit(eng,'CLIENT_TRANSMISSION_SENT',row['action_id'],'worker','client_transmission',row['id'],{'type':row['transmission_type'],'recipient':row['recipient_email']});sent+=1
        except Exception as ex:
            execute(eng,"UPDATE client_transmissions SET status='PENDING',claim_token=NULL,claimed_at=NULL,last_error=:e WHERE id=:i AND claim_token=:c",{'e':str(ex)[:500],'i':row['id'],'c':claim})
    return sent

def _process_portal_retention(eng,smtp,base,warning_days=30):
    changed=0
    # Never purge before a warning has actually been sent.
    for b in portal_retention_candidates(eng,12,warning_days):
        if b.get('portal_warning_sent_at'): continue
        email=(b.get('portal_email') or b.get('current_email') or '').strip()
        if not email: continue
        subject='Clarté360 — Votre espace personnel arrive à échéance'
        link=f"{base.rstrip('/')}?beneficiary_portal=1"
        body=f"""<p>Bonjour {b.get('first_name') or ''},</p><p>Votre dernière action remonte maintenant à plus de 12 mois. Votre espace documentaire personnel sera purgé dans {warning_days} jours si aucune nouvelle action n’est créée.</p><p>Vous pouvez dès maintenant vous connecter et télécharger l’intégralité de votre espace au format ZIP :</p><p><a href='{link}'>ACCÉDER À MON ESPACE</a></p><p>Cette purge concerne uniquement les documents mis à disposition dans votre portail et ne supprime pas les archives réglementaires internes de l’organisme.</p>"""
        try:
            send_mail(smtp,email,subject,body)
            mark_portal_retention_warning(eng,b['id'],warning_days,'worker');changed+=1
        except Exception as ex:
            audit(eng,'BENEFICIARY_PORTAL_RETENTION_WARNING_FAILED',actor='worker',entity_type='beneficiary',entity_id=b['id'],details={'error':str(ex)[:500]})
    for b in due_portal_purges(eng):
        purge_beneficiary_portal_documents(eng,b['id'],'worker');changed+=1
    return changed


def _sync_teams_trainer_identities(eng, client, action_id, base_url):
    """Resolve existing Entra identities first; never create a Guest silently.

    A Guest invitation is only emitted after an explicit administrator request stored on
    the permanent trainer record. Before that invitation the worker searches Entra again,
    which prevents duplicate Microsoft identities.
    """
    roles=teams_roles(eng,action_id)
    seen_trainers=set()
    for role in roles:
        tid=role.get('trainer_id')
        if not tid or tid in seen_trainers:
            continue
        seen_trainers.add(tid)
        t=trainer_microsoft_identity(eng,tid) or {}
        email=(t.get('microsoft_email') or t.get('email') or role.get('email') or '').strip().lower()
        if not email:
            continue
        try:
            # Always search before any creation attempt.
            user=client.find_user_by_email(email)
            if user:
                mark_trainer_entra_identity(eng,tid,user,'worker')
                continue
            mark_trainer_entra_not_found(eng,tid,'worker')
            requested=bool(t.get('entra_creation_requested_at')) or str(t.get('entra_status') or '').upper()=='CREATION_REQUESTED'
            if not requested:
                continue
            if not client.cfg.get('guest_invites_enabled'):
                execute(eng,"UPDATE trainers SET entra_status='CREATION_BLOCKED' WHERE id=:i",{'i':tid})
                audit(eng,'TRAINER_ENTRA_CREATION_BLOCKED',action_id,'worker','trainer',tid,{'reason':'guest_invites_disabled'})
                continue
            # Search once more immediately before the write operation.
            user=client.find_user_by_email(email)
            if user:
                mark_trainer_entra_identity(eng,tid,user,'worker')
                continue
            inv=client.invite_guest(email,base_url,True,t.get('full_name') or role.get('display_name'))
            invited=(inv or {}).get('invitedUser') or {}
            if invited.get('id'):
                mark_trainer_entra_identity(eng,tid,invited,'worker')
                execute(eng,"UPDATE trainers SET entra_status='INVITED' WHERE id=:i",{'i':tid})
                audit(eng,'TRAINER_ENTRA_GUEST_INVITED',action_id,'worker','trainer',tid,{'email':email})
        except Exception as ex:
            execute(eng,"UPDATE trainers SET entra_status='ERROR',entra_last_verified_at=:n WHERE id=:i",{'n':datetime.now(timezone.utc).isoformat(),'i':tid})
            audit(eng,'TEAMS_IDENTITY_SYNC_FAILED',action_id,'worker','trainer',tid,{'error':str(ex)[:500]})


def _apply_teams_advanced_roles(eng, client, action_id):
    room=teams_room(eng,action_id)
    if not room or not room.get('online_meeting_id'):
        return 0
    attendees=[]
    seen=set()
    for r in teams_roles(eng,action_id):
        uid=r.get('entra_user_id'); email=(r.get('email') or '').strip()
        if not uid or uid in seen:
            continue
        seen.add(uid)
        role='coorganizer' if (r.get('role') or '').upper()=='COORGANIZER' else 'presenter'
        attendees.append({'upn':email,'role':role,'identity':{'user':{'id':uid}}})
    if attendees:
        client.update_online_meeting(room['online_meeting_id'],{'participants':{'attendees':attendees}})
        audit(eng,'TEAMS_ROLES_SYNCED',action_id,'worker','teams_action_room',room['id'],{'attendees':len(attendees)})
    return len(attendees)


def _sync_teams_attendance(eng, client, action_id):
    room=teams_room(eng,action_id)
    if not room or not room.get('online_meeting_id'):
        return 0
    imported=0
    reports=client.list_attendance_reports(room['online_meeting_id'])
    for report in reports:
        if one(eng,'SELECT id FROM teams_attendance_reports WHERE report_id=:r',{'r':str(report.get('id') or '')}):
            continue
        records=client.list_attendance_records(room['online_meeting_id'],report.get('id'))
        if store_teams_attendance_report(eng,action_id,room['id'],report,records,'worker'):
            imported+=1
    return imported


def _process_teams(eng, cfg, base_url):
    gcfg=graph_config_from_mapping(cfg)
    if not gcfg.get('enabled'):
        return 0
    missing=graph_config_missing(gcfg)
    if missing:
        audit(eng,'TEAMS_GRAPH_CONFIG_INVALID',actor='worker',entity_type='microsoft_graph',details={'missing':missing})
        return 0
    client=GraphClient(gcfg); changed=0
    actions=q(eng,"""SELECT DISTINCT a.id FROM actions a JOIN action_modules m ON m.action_id=a.id
      WHERE m.module_code='TEAMS' AND m.enabled=1 AND a.status IN ('PLANIFIEE','ACTIVE','A_CLOTURER','CLOTUREE') ORDER BY a.id""")
    for a in actions:
        aid=a['id']
        try:
            create_or_sync_teams_room(eng,aid,client,'worker')
            _sync_teams_trainer_identities(eng,client,aid,base_url)
            _apply_teams_advanced_roles(eng,client,aid)
            changed += _sync_teams_attendance(eng,client,aid)
            execute(eng,"UPDATE teams_sync_events SET status='DONE',processed_at=:n,last_error=NULL WHERE action_id=:a AND status='PENDING'",{'n':datetime.now(timezone.utc).isoformat(),'a':aid})
            execute(eng,"UPDATE planning_change_events SET teams_status='SYNCED' WHERE action_id=:a AND teams_required=1 AND teams_status IN ('PENDING_I7','PENDING')",{'a':aid})
        except Exception as ex:
            execute(eng,"UPDATE teams_sync_events SET attempts=attempts+1,last_error=:e WHERE action_id=:a AND status='PENDING'",{'e':str(ex)[:500],'a':aid})
            execute(eng,"UPDATE planning_change_events SET teams_status='ERROR' WHERE action_id=:a AND teams_required=1 AND teams_status IN ('PENDING_I7','PENDING')",{'a':aid})
            audit(eng,'TEAMS_SYNC_FAILED',aid,'worker','action',aid,{'error':str(ex)[:500]})
    return changed

def run_once():
    cfg=load_cfg(); dburl=(cfg.get('database') or {}).get('url'); eng=make_engine(dburl);init_db(eng)
    smtp=resolve_mail_config(cfg); app=cfg.get('app') or {}; base=app.get('base_url','http://localhost:8501')
    _quarantine_stale_sending(eng)
    _quarantine_stale_quality(eng)
    _quarantine_stale_client_transmissions(eng)
    generate_due_final_bundles(eng,'worker')
    teams_changed=_process_teams(eng,cfg,base)
    pip_cfg=cfg.get('pip_connector') or {}
    refresh_pip_connector_runtime_status(eng,pip_cfg.get('launch_signing_key'),pip_cfg.get('outbox_path'),'worker')
    pip_changed=0
    outbox_path=(pip_cfg.get('outbox_path') or '').strip()
    if outbox_path:
        try:
            pip_changed=consume_pip_outbox(eng,outbox_path,actor='worker').get('processed',0)
        except Exception as ex:
            audit(eng,'PIP_CONNECTOR_FAILED',actor='worker',entity_type='connector',details={'error':str(ex)[:500]})
    # I9-H2.4: keep countersignature requests alive until the trainer signs.
    # Refresh before SMTP processing so end-of-slot requests are actually queued.
    refresh_countersign_communications(eng)
    if not smtp.get('enabled'): return teams_changed + pip_changed
    _process_portal_retention(eng,smtp,base)
    now=datetime.now(timezone.utc).isoformat()
    # Ne pas filtrer les candidats sur due_at avant le garde-fou métier :
    # une ancienne échéance erronée (notamment décalage horaire) peut être stockée dans le futur
    # et empêcherait alors le worker de la réparer. On relit les événements PENDING des actions
    # actives, on recalcule leur vraie échéance à partir du créneau et du fuseau de l'organisme,
    # puis on n'envoie que si cette échéance recalculée est réellement atteinte.
    events=q(eng,"""SELECT e.*,p.email,p.first_name,p.last_name,a.title,a.action_no,a.id action_id,s.slot_date,s.start_time,s.end_time,
              s.send_offset_min,s.reminder1_offset_min,s.reminder2_offset_min,s.close_offset_min
       FROM email_events e JOIN participants p ON p.id=e.participant_id JOIN slots s ON s.id=e.slot_id JOIN actions a ON a.id=p.action_id
       WHERE e.status='PENDING' AND p.email IS NOT NULL AND TRIM(p.email)<>'' AND a.status IN ('ACTIVE','A_CLOTURER')
       ORDER BY e.due_at LIMIT 500""")
    sent=0
    for e in events:
        runtime=organization_runtime_config(eng,e['action_id'])
        tz_name=runtime.get('timezone') or 'Europe/Paris'
        expected_due=email_event_due_utc(e,e['event_type'],tz_name)
        now_dt=datetime.now(timezone.utc)
        stored_due=datetime.fromisoformat(e['due_at'])
        if stored_due.tzinfo is None:
            stored_due=stored_due.replace(tzinfo=timezone.utc)
        # Garde-fou : une échéance incohérente est réparée avant tout envoi.
        if abs((stored_due.astimezone(timezone.utc)-expected_due).total_seconds())>1:
            execute(eng,"UPDATE email_events SET due_at=:d,last_error=NULL WHERE id=:i AND status='PENDING'",{'d':expected_due.isoformat(),'i':e['id']})
        if now_dt < expected_due:
            continue
        claim=_claim_event(eng,e['id'])
        if not claim: continue
        if one(eng,'SELECT id FROM signatures WHERE participant_id=:p AND slot_id=:s AND status="VALIDE"',{'p':e['participant_id'],'s':e['slot_id']}):
            execute(eng,"UPDATE email_events SET status='SKIPPED',claim_token=NULL WHERE id=:id AND claim_token=:c",{'id':e['id'],'c':claim});continue
        org=runtime['organization']
        org_name=org.get('name') or 'Organisme'; privacy=org.get('privacy_notice') or "Les informations nécessaires à l'organisation de l'action et à la justification de sa réalisation sont traitées pour la gestion et la preuve de l'action."
        privacy_contact=org.get('privacy_contact') or org.get('general_email') or ''
        if org.get('email_from_name'): smtp['from_name']=org['email_from_name']
        if org.get('email_from_address'): smtp['from_email']=org['email_from_address']
        url=token_url(eng,e['participant_id'],e['slot_id'],base)
        label={'INITIAL':'demande d’émargement','RELANCE_1':'rappel d’émargement','RELANCE_2':'dernier rappel d’émargement'}.get(e['event_type'],'émargement')
        subject=f"{org_name} — {label} — {e['action_no']}"
        body=f"""<p>Bonjour {e['first_name']},</p><p>Merci d'émarger votre présence pour <strong>{e['title']}</strong>, le {e['slot_date']} de {e['start_time']} à {e['end_time']}.</p><p><a href='{url}'>SIGNER MA PRÉSENCE</a></p><p><strong>Accès :</strong> ce lien est personnel.</p><hr><p style='font-size:12px;color:#555'><strong>Information données personnelles :</strong> {privacy} {'Contact : '+privacy_contact if privacy_contact else ''}</p>"""
        try:
            send_mail(smtp,e['email'],subject,body)
            execute(eng,"UPDATE email_events SET status='SENT',sent_at=:s,claim_token=NULL,last_error=NULL WHERE id=:id AND claim_token=:c",{'s':datetime.now(timezone.utc).isoformat(),'id':e['id'],'c':claim});sent+=1
            audit(eng,'EMAIL_SENT',e['action_id'],'worker','email_event',e['id'],{'event_type':e['event_type']})
        except Exception as ex:
            # Known SMTP failure: safe to retry because send_mail raised before success was acknowledged.
            execute(eng,"UPDATE email_events SET status='PENDING',claim_token=NULL,claimed_at=NULL,last_error=:er WHERE id=:id AND claim_token=:c",{'er':str(ex)[:500],'id':e['id'],'c':claim})
    sent += _run_quality_events(eng,smtp,base)
    sent += _run_client_transmissions(eng,smtp)
    sent += _run_communication_events(eng,smtp,base)
    return sent + teams_changed + pip_changed

if __name__=='__main__':
    print('Clarté360 worker démarré')
    while True:
        try: run_once()
        except Exception as e: print('worker error',e)
        time.sleep(60)
