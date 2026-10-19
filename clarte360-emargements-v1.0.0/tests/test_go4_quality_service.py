"""CDC GO4 R01-R08, R12-R19/R23: isolated fictitious SQLite, no SMTP."""
import json
import socket
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from db import make_engine, init_db, execute, one, q, utcnow_iso
import quality_service as qs
import quality_notifications as qn


@pytest.fixture
def env(tmp_path, monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('Réseau interdit dans les tests métier GO4')
    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket, 'create_connection', blocked)
    e = make_engine('sqlite:///' + str(tmp_path / 'fictif.sqlite'))
    init_db(e)
    now = utcnow_iso()
    orgs = [execute(e, 'INSERT INTO organizations(name,created_at,updated_at) VALUES(:name,:n,:n)', {'name': f'Fictif {i}', 'n': now}) for i in (1, 2)]
    for name in ('admin', 'second'):
        execute(e, 'INSERT INTO admins(email,password_hash,created_at) VALUES(:e,\'fictif\',:n)', {'e': name+'@example.invalid', 'n': now})
    admin = qs.QualityActor('ADMIN', 'admin@example.invalid', orgs[0])
    admin2 = qs.QualityActor('ADMIN', 'second@example.invalid', orgs[0])
    tids = [execute(e, 'INSERT INTO trainers(full_name,email,created_at,updated_at) VALUES(:name,:email,:n,:n)',
                    {'name': f'Trainer {i}', 'email': f'trainer{i}@example.invalid', 'n': now}) for i in range(3)]
    aids = [execute(e, '''INSERT INTO actions(action_no,title,nature,mode,organization_id,trainer_id,created_at,updated_at,prestation_type)
      VALUES(:ref,'Formation fictive','FORMATION','INDIVIDUEL',:org,:tid,:n,:n,'FORMATION')''',
      {'ref': f'TEST-GO4-{i}', 'org': orgs[1] if i == 2 else orgs[0], 'tid': tids[i], 'n': now}) for i in range(3)]
    bids, cids = [], []
    for i in range(3):
        b = execute(e, '''INSERT INTO beneficiaries(public_id,first_name,last_name,birth_date,created_at,updated_at)
          VALUES(:pid,'Fictive','Personne','2000-01-01',:n,:n)''', {'pid': f'BEN-GO4-{i}', 'n': now})
        execute(e, 'INSERT INTO beneficiary_portal_accounts(beneficiary_id,email,password_hash,created_at,updated_at) VALUES(:b,:email,\'fictif\',:n,:n)',
                {'b': b, 'email': f'ben{i}@example.invalid', 'n': now})
        execute(e, 'INSERT INTO participants(action_id,last_name,first_name,beneficiary_id,created_at) VALUES(:a,\'Fictive\',\'Personne\',:b,:n)',
                {'a': aids[0] if i < 2 else aids[2], 'b': b, 'n': now})
        bids.append(b)
        contact = execute(e, '''INSERT INTO crm_contacts(public_id,first_name,last_name,email,company,created_at,updated_at)
          VALUES(:pid,'Contact','Fictif',:email,'Même entreprise',:n,:n)''', {'pid': f'C-GO4-{i}', 'email': f'client{i}@example.invalid', 'n': now})
        cid = execute(e, 'INSERT INTO client_portal_accounts(crm_contact_id,email,password_hash,created_at,updated_at) VALUES(:c,:email,\'fictif\',:n,:n)',
                      {'c': contact, 'email': f'client{i}@example.invalid', 'n': now})
        execute(e, '''INSERT INTO client_action_grants(account_id,action_id,role,granted_by,granted_at)
          VALUES(:c,:a,'CLIENT_ADMIN','admin@example.invalid',:n)''', {'c': cid, 'a': aids[0] if i < 2 else aids[2], 'n': now})
        cids.append(cid)
    data = dict(e=e, admin=admin, admin2=admin2, orgs=orgs, aids=aids, tids=tids, bids=bids, cids=cids,
                trainer=qs.QualityActor('TRAINER', tids[0], orgs[0]),
                ben=qs.QualityActor('BENEFICIARY', bids[0], orgs[0]),
                client=qs.QualityActor('CLIENT', cids[0], orgs[0]))
    yield data
    e.dispose()


def create(env, **kwargs):
    return qs.create_action(env['e'], env['admin'], 'Prévention fictive', command_id='new-'+str(one(env['e'],'SELECT COUNT(*) n FROM quality_events')['n']), **kwargs)


def version(env, event):
    return one(env['e'], 'SELECT row_version FROM quality_events WHERE id=:e', {'e': event})['row_version']


def test_r01_prevention_without_incident_or_training_and_duplicate(env):
    e,a=env['e'],env['admin']
    first=qs.create_action(e,a,'Prévenir un problème',command_id='repeat')
    assert qs.create_action(e,a,'Prévenir un problème',command_id='repeat')==first
    assert one(e,'SELECT COUNT(*) n FROM quality_events')['n']==1
    assert one(e,'SELECT COUNT(*) n FROM quality_event_actions')['n']==0
    row=qs.get_action(e,a,first)['event']
    assert row['action_id'] is None and row['action_nature']=='PREVENTIVE'
    with pytest.raises(ValueError):qs.create_action(e,a,'Autre action',command_id='repeat')


def test_r02_q003_single_transaction_closes_step_and_one_row(env):
    e,a=env['e'],env['admin']; event=create(env)
    execute(e,"UPDATE quality_events SET public_id='Q-003' WHERE id=:e",{'e':event})
    step=qs.add_step(e,a,event,'Tester la nouvelle consigne',expected_version=1)
    args=dict(expected_version=2,summary='Consigne testée : saisie correcte constatée',step_outcomes={step:{'outcome':'VERIFIED'}},command_id='close')
    assert qs.close_action(e,a,event,**args)
    assert qs.close_action(e,a,event,**args)
    assert one(e,'SELECT COUNT(*) n FROM quality_events')['n']==1
    assert one(e,'SELECT status FROM quality_event_actions WHERE id=:s',{'s':step})['status']=='TERMINEE'
    assert len([h for h in qs.get_action(e,a,event)['history'] if h['change_kind']=='CLOTURE'])==1
    assert qs.get_action(e,a,event)['event']['public_id']=='Q-003'


@pytest.mark.parametrize('outcome',[None,'REMAINING','ABANDONED'])
def test_r03_unfinished_or_unmotivated_abandonment_changes_nothing(env,outcome):
    e,a=env['e'],env['admin']; event=create(env)
    s1=qs.add_step(e,a,event,'Première étape',expected_version=1)
    s2=qs.add_step(e,a,event,'Deuxième étape',expected_version=2)
    before={tab:q(e,f'SELECT * FROM {tab}') for tab in ('quality_events','quality_event_actions','quality_event_history','quality_notification_outbox')}
    with pytest.raises(ValueError):qs.close_action(e,a,event,expected_version=3,summary='Bilan',step_outcomes={s1:{'outcome':'VERIFIED'},s2:{'outcome':outcome}},command_id='bad')
    for tab,rows in before.items():assert q(e,f'SELECT * FROM {tab}')==rows


def test_r03_database_failure_rolls_back_steps_and_notifications(env,monkeypatch):
    e,a=env['e'],env['admin']; event=create(env)
    sid=qs.add_step(e,a,event,'Vérification',expected_version=1)
    old=one(e,'SELECT COUNT(*) n FROM quality_event_history')['n']
    def fail(*args,**kwargs):raise RuntimeError('échec fictif de stockage')
    monkeypatch.setattr(qn,'enqueue_event_tx',fail)
    with pytest.raises(RuntimeError):qs.close_action(e,a,event,expected_version=2,summary='Réalisé',step_outcomes={sid:{'outcome':'VERIFIED'}},command_id='failure')
    assert version(env,event)==2
    assert one(e,'SELECT status FROM quality_event_actions WHERE id=:i',{'i':sid})['status']=='A_FAIRE'
    assert one(e,'SELECT COUNT(*) n FROM quality_event_history')['n']==old


def test_r04_unchanged_save_no_event_comment_only_one_advancement(env):
    e,a=env['e'],env['admin']; event=create(env)
    count=one(e,'SELECT COUNT(*) n FROM quality_event_history')['n']
    assert not qs.update_action(e,a,event,expected_version=1,status='NOUVEAU',title='Prévention fictive')
    assert version(env,event)==1 and one(e,'SELECT COUNT(*) n FROM quality_event_history')['n']==count
    assert qs.update_action(e,a,event,expected_version=1,comment='Premier essai réalisé')
    history=qs.get_action(e,a,event)['history']
    assert history[-1]['change_kind']=='AVANCEE'
    assert 'NOUVEAU' not in history[-1]['after_json']


def test_r04_concurrent_stale_form_cannot_overwrite(env):
    event=create(env); e,a=env['e'],env['admin']
    qs.update_action(e,a,event,expected_version=1,comment='Version actualisée')
    with pytest.raises(qs.ConflictError):qs.update_action(e,a,event,expected_version=1,title='Écrasement')
    assert qs.get_action(e,a,event)['event']['subject']=='Prévention fictive'


def test_r05_full_delegation_cycle_minimal_rights(env):
    e,a,t=env['e'],env['admin'],env['trainer']; event=create(env,action_id=env['aids'][0])
    qs.assign_action(e,a,event,expected_version=1,delegate_role='TRAINER',delegate_id=t.subject_id,expected_result='Tester un moyen',command_id='assign')
    assert qs.get_action(e,t,event)['permissions']['close'] is False
    qs.respond_assignment(e,t,event,expected_version=2,decision='REFUSE',comment='Indisponible',command_id='refuse')
    with pytest.raises(PermissionError):qs.get_action(e,t,event)
    qs.assign_action(e,a,event,expected_version=3,delegate_role='TRAINER',delegate_id=t.subject_id,expected_result='Nouveau créneau pour le test',command_id='reassign')
    qs.respond_assignment(e,t,event,expected_version=4,decision='ACCEPT',command_id='accept')
    qs.respond_assignment(e,t,event,expected_version=5,decision='SUBMIT',comment='Essai terminé, résultat à valider',command_id='submit')
    assert qs.get_action(e,a,event)['event']['status']=='A_VERIFIER'
    with pytest.raises(PermissionError):qs.close_action(e,t,event,expected_version=6,summary='Fait',command_id='forbidden')
    qs.close_action(e,a,event,expected_version=6,summary='Résultat vérifié',command_id='valid')
    assert qs.plan_counts(e,a)['resolved']==1


def test_r05_inactive_or_unassigned_delegate_rejected(env):
    event=create(env,action_id=env['aids'][0]);e,a=env['e'],env['admin']
    for tid in env['tids'][1:]:
        with pytest.raises(PermissionError):qs.assign_action(e,a,event,expected_version=1,delegate_role='TRAINER',delegate_id=tid,expected_result='Essai',command_id=f'bad-{tid}')
    execute(e,'UPDATE trainers SET active=0 WHERE id=:i',{'i':env['tids'][0]})
    assert not any(x['role']=='TRAINER' for x in qs.eligible_delegates(e,a,event))


def test_r06_reopen_preserves_reference_old_date_and_summary(env):
    event=create(env);e,a=env['e'],env['admin'];ref=qs.get_action(e,a,event)['event']['public_id']
    qs.close_action(e,a,event,expected_version=1,summary='Premier bilan vérifié',command_id='close')
    closed=qs.get_action(e,a,event)['event']['closed_at']
    qs.reopen_action(e,a,event,expected_version=2,reason='Un besoin nouveau',command_id='reopen')
    case=qs.get_action(e,a,event)
    assert case['event']['public_id']==ref and case['event']['closed_at'] is None
    assert any('Premier bilan vérifié' in str(h) and closed in str(h) for h in case['history'])
    assert one(e,'SELECT COUNT(*) n FROM quality_events')['n']==1


def test_r08_cancelled_does_not_count_as_overdue_or_resolved(env):
    event=create(env,due_at='2000-01-01');e,a=env['e'],env['admin']
    qs.close_action(e,a,event,expected_version=1,summary='Le besoin a disparu',outcome='CANCELLED',command_id='cancel')
    assert qs.plan_counts(e,a)['overdue']==0
    assert qs.plan_counts(e,a)['resolved']==0
    assert qs.plan_counts(e,a)['cancelled']==1


def test_r12_filtered_export_same_rows_safe_cells(env):
    e,a=env['e'],env['admin']
    first=qs.create_action(e,a,'=FORMULE()',classification='TEST',command_id='one')
    second=create(env)
    filtered=qs.list_actions(e,a,classification='REAL')
    data=qs.export_plan_csv(e,a,classification='REAL').decode('utf-8-sig')
    assert len(filtered)==1 and filtered[0]['id']==second
    assert '=FORMULE()' not in data
    assert 'Méthode' in data and 'Exclus' in data
    assert "'=FORMULE()" in qs.export_plan_csv(e,a,classification='TEST').decode('utf-8-sig')
    assert qs.export_plan_pdf(e,a,classification='REAL').startswith(b'%PDF-')


def test_r13_client_contacts_same_company_never_share_requests(env):
    e,c=env['e'],env['client']
    event=qs.create_action(e,c,'Ma demande',action_id=env['aids'][0],command_id='client')
    other=qs.QualityActor('CLIENT',env['cids'][1],env['orgs'][0])
    assert qs.list_actions(e,other)==[]
    with pytest.raises(PermissionError):qs.get_action(e,other,event)
    with pytest.raises(PermissionError):qs.update_action(e,other,event,expected_version=1,comment='Intrusion')
    assert 'Ma demande' not in qs.export_plan_csv(e,other).decode('utf-8-sig')


@pytest.mark.parametrize('role,identifier',[('BENEFICIARY','bids'),('TRAINER','tids'),('CLIENT','cids')])
def test_r14_other_organization_rejects_guessed_ids(env,role,identifier):
    event=create(env);bad=qs.QualityActor(role,env[identifier][2],env['orgs'][0])
    with pytest.raises(PermissionError):qs.get_action(env['e'],bad,event)
    with pytest.raises(PermissionError):qs.list_actions(env['e'],bad)
    with pytest.raises(PermissionError):qs.export_plan_csv(env['e'],bad)


def test_r14_same_organization_non_requester_beneficiary_rejected(env):
    event=qs.create_action(env['e'],env['ben'],'Besoin',command_id='ben')
    other=qs.QualityActor('BENEFICIARY',env['bids'][1],env['orgs'][0])
    with pytest.raises(PermissionError):qs.get_action(env['e'],other,event)
    assert not qs.list_actions(env['e'],other)


def test_r15_internal_notes_attachments_search_and_mail_hidden(env):
    e,a,c=env['e'],env['admin'],env['client'];event=qs.create_action(e,c,'Organisation',command_id='client')
    qs.update_action(e,a,event,expected_version=1,comment='CONFIDENTIEL HANDICAP BC',audience='INTERNAL')
    aid=qs.add_attachment(e,a,event,expected_version=2,data=b'CONFIDENTIEL HANDICAP BC',filename='note.txt',audience='INTERNAL',command_id='attach')
    assert 'CONFIDENTIEL' not in str(qs.get_action(e,c,event))
    assert not qs.list_actions(e,c,search='CONFIDENTIEL')
    with pytest.raises(PermissionError):qs.read_attachment(e,c,event,aid)
    assert 'CONFIDENTIEL' not in qs.export_plan_csv(e,c).decode('utf-8-sig')
    assert 'CONFIDENTIEL' not in str(q(e,'SELECT * FROM workspace_notifications'))
    assert 'CONFIDENTIEL' not in str(q(e,'SELECT * FROM quality_notification_outbox'))


def test_r15_sensitive_case_not_visible_to_all_admins(env):
    event=create(env,sensitivity='RESTRICTED')
    with pytest.raises(PermissionError):qs.get_action(env['e'],env['admin2'],event)
    assert qs.plan_counts(env['e'],env['admin2'])['total']==0


def test_r17_revoked_client_grant_and_inactive_account_deny_old_link(env):
    e,c=env['e'],env['client'];event=qs.create_action(e,c,'Demande',action_id=env['aids'][0],command_id='c')
    execute(e,'UPDATE client_action_grants SET revoked_at=:n WHERE account_id=:i',{'n':utcnow_iso(),'i':c.subject_id})
    with pytest.raises(PermissionError):qs.get_action(e,c,event)
    execute(e,'UPDATE client_action_grants SET revoked_at=NULL WHERE account_id=:i',{'i':c.subject_id})
    execute(e,'UPDATE client_portal_accounts SET active=0 WHERE id=:i',{'i':c.subject_id})
    with pytest.raises(PermissionError):qs.get_action(e,c,event)


def test_r17_reassignment_removes_old_mission_access(env):
    e,a,t=env['e'],env['admin'],env['trainer'];event=create(env)
    qs.assign_action(e,a,event,expected_version=1,delegate_role='TRAINER',delegate_id=t.subject_id,expected_result='Essai',command_id='first')
    qs.assign_action(e,a,event,expected_version=2,delegate_role='ADMIN',delegate_id=env['admin2'].subject_id,expected_result='Reprise',command_id='second')
    with pytest.raises(PermissionError):qs.get_action(e,t,event)


def test_r18_default_outbox_no_send_and_idempotent_enqueue(env):
    event=create(env);e=env['e'];seen=[]
    initial=one(e,'SELECT COUNT(*) n FROM quality_notification_outbox')['n']
    assert qn.process_outbox(e,lambda *a,**kw:seen.append(a))['pending']==initial
    assert seen==[]
    with e.begin() as conn:
        hid=conn.execute(text('SELECT MAX(id) FROM quality_event_history')).scalar()
        qn.enqueue_event_tx(conn,event,hid,'CREATION','PUBLIC')
    assert one(e,'SELECT COUNT(*) n FROM quality_notification_outbox')['n']==initial


def test_r18_smtp_failure_retries_without_repeating_accepted(env):
    e,a=env['e'],env['admin'];event=create(env)
    qs.configure_organization(e,a,email_enabled=True)
    attempted=[];accepted=[]
    def failed(to,subject,body,**kwargs):
        attempted.append(to);raise qn.RetryableDeliveryError('Échec fictif avant acceptation')
    assert qn.process_outbox(e,failed,base_url='https://example.invalid',dry_run=False)['retry']==2
    assert qs.get_action(e,a,event)['event']['status']=='NOUVEAU'
    def success(to,subject,body,**kwargs):
        accepted.append((to,subject,body,kwargs));return {'accepted':True,'receipt':'simulation'}
    assert qn.process_outbox(e,success,base_url='https://example.invalid',dry_run=False)['accepted']==2
    assert qn.process_outbox(e,success,base_url='https://example.invalid',dry_run=False)['accepted']==0
    assert len(accepted)==2
    assert 'Prévention fictive' not in str(accepted)
    assert all(x['status']=='ACCEPTED' for x in q(e,'SELECT * FROM quality_notification_outbox'))


def test_r18_ambiguous_delivery_is_held_without_duplicate(env):
    e,a=env['e'],env['admin'];create(env);qs.configure_organization(e,a,email_enabled=True)
    def uncertain(*args,**kwargs):raise TimeoutError('Réponse perdue après acceptation possible')
    assert qn.process_outbox(e,uncertain,base_url='https://example.invalid',dry_run=False)['unknown']==2
    assert qn.process_outbox(e,uncertain,base_url='https://example.invalid',dry_run=False)['unknown']==0


def test_r19_deadline_change_and_close_cancel_stale_reminders(env):
    e,a=env['e'],env['admin'];event=create(env,due_at='2000-01-01');qs.configure_organization(e,a,reminder_days=2)
    assert qn.schedule_reminders(e)==2
    assert qn.schedule_reminders(e)==0
    qs.update_action(e,a,event,expected_version=1,due_at='2100-01-01')
    assert all(x['status']=='CANCELLED' for x in q(e,"SELECT status FROM quality_notification_outbox WHERE event_kind='REMINDER'"))
    assert qn.schedule_reminders(e)==0
    qs.close_action(e,a,event,expected_version=2,summary='Traitement vérifié',command_id='done')
    assert qn.schedule_reminders(e)==0


def test_r23_deletion_requires_policy_then_preserves_training(env):
    e,a=env['e'],env['admin'];event=create(env,action_id=env['aids'][0])
    assert not qs.deletion_preview(e,a,event)['can_delete']
    with pytest.raises(ValueError):qs.delete_action(e,a,event,1,'Essai fictif','delete')
    qs.configure_organization(e,a,deletion_enabled=True,retention_days=0)
    result=qs.delete_action(e,a,event,1,'Essai fictif','delete')
    assert result['deleted'] and one(e,'SELECT id FROM actions WHERE id=:i',{'i':env['aids'][0]})
    assert not one(e,'SELECT id FROM quality_events WHERE id=:i',{'i':event})
    assert qs.delete_action(e,a,event,1,'Essai fictif','delete')==result
    assert 'Prévention fictive' not in str(q(e,'SELECT * FROM quality_deletion_receipts'))


def test_r23_retention_and_non_admin_deletion_blocked(env):
    e,a=env['e'],env['admin'];event=qs.create_action(e,env['ben'],'Besoin',command_id='ben')
    qs.configure_organization(e,a,deletion_enabled=True,retention_days=365)
    with pytest.raises(ValueError):qs.delete_action(e,a,event,1,'Trop tôt','bad')
    with pytest.raises(PermissionError):qs.deletion_preview(e,env['ben'],event)


@pytest.mark.parametrize('filename,data',[('../evil.html',b'<script>evil</script>'),('fake.pdf',b'not a pdf'),('evil.docx',b'not an office file')])
def test_attachment_type_validation_without_mutation(env,filename,data):
    event=create(env)
    with pytest.raises(ValueError):qs.add_attachment(env['e'],env['admin'],event,expected_version=1,data=data,filename=filename,command_id='bad')
    assert version(env,event)==1


def test_public_attachment_read_requires_current_requester(env):
    e,a,c=env['e'],env['admin'],env['client'];event=qs.create_action(e,c,'Demande',command_id='request')
    attachment=qs.add_attachment(e,a,event,expected_version=1,data=b'Reponse utile',filename='../preuve.txt',audience='PUBLIC',command_id='attachment')
    assert qs.read_attachment(e,c,event,attachment)['filename']=='preuve.txt'
    wrong=qs.QualityActor('CLIENT',env['cids'][1],env['orgs'][0])
    with pytest.raises(PermissionError):qs.read_attachment(e,wrong,event,attachment)


def test_r08_legacy_report_keeps_author_last_reply_and_idempotence(env):
    e,a=env['e'],env['admin'];n=utcnow_iso()
    rid=execute(e,'''INSERT INTO beneficiary_reports(action_id,beneficiary_id,report_type,subject,description,status,admin_response,created_at,updated_at)
      VALUES(:aid,:b,'OBSERVATION','Ancienne demande','Contexte ancien','EN_COURS','Réponse ancienne',:n,:n)''',
      {'aid':env['aids'][0],'b':env['bids'][0],'n':n})
    first=qs.migrate_legacy(e,a);second=qs.migrate_legacy(e,a)
    assert first['sources_created']==1 and second['sources_created']==0
    case=qs.get_action(e,env['ben'],first['mappings'][0]['event_id'])
    assert case['event']['description']=='Contexte ancien'
    assert any(m['message']=='Réponse ancienne' for m in case['messages'])
    full=qs.get_action(e,a,first['mappings'][0]['event_id'])['event']
    assert full['created_by']=='BENEFICIARY:'+str(env['bids'][0])
    assert one(e,'SELECT admin_response FROM beneficiary_reports WHERE id=:i',{'i':rid})['admin_response']=='Réponse ancienne'


def test_r08_legacy_improvement_maps_as_one_action_or_optional_step(env):
    e,a=env['e'],env['admin'];n=utcnow_iso()
    issue=execute(e,"INSERT INTO quality_issues(action_id,title,issue_type,created_at) VALUES(:a,'Affaire ancienne','OBSERVATION',:n)",{'a':env['aids'][0],'n':n})
    execute(e,"INSERT INTO improvement_actions(action_id,issue_id,title,status,created_at) VALUES(:a,:i,'Mesure liée','A_FAIRE',:n)",{'a':env['aids'][0],'i':issue,'n':n})
    general=execute(e,"INSERT INTO improvement_actions(title,status,created_at) VALUES('Prévention générale','ANNULEE',:n)",{'n':n})
    report=qs.migrate_legacy(e,a,general_source_ids=[('IMPROVEMENT_ACTION',general)])
    assert report['sources_created']==2 and report['steps_created']==1
    assert qs.plan_counts(e,a)['total']==2 and qs.plan_counts(e,a)['cancelled']==1
    again=qs.migrate_legacy(e,a,general_source_ids=[('IMPROVEMENT_ACTION',general)])
    assert again['sources_created']==0 and again['steps_created']==0


def test_r08_ambiguous_titles_are_reported_not_merged(env):
    e,a=env['e'],env['admin'];n=utcnow_iso()
    qs.create_action(e,a,'Même titre','Même contenu',action_id=env['aids'][0],command_id='existing')
    execute(e,"INSERT INTO quality_issues(action_id,title,description,issue_type,created_at) VALUES(:a,'Même titre','Même contenu','OBSERVATION',:n)",{'a':env['aids'][0],'n':n})
    report=qs.migrate_legacy(e,a)
    assert report['sources_created']==0 and len(report['unresolved'])==1
    assert one(e,'SELECT outcome FROM quality_migration_decisions')['outcome']=='REVIEW'


def test_r17_restricted_admin_mission_expires_on_refusal_and_reassignment(env):
    e,a,b=env['e'],env['admin'],env['admin2']; event=create(env,sensitivity='RESTRICTED')
    qs.assign_action(e,a,event,expected_version=1,delegate_role='ADMIN',delegate_id=b.subject_id,expected_result='Vérifier le dossier',command_id='mission')
    assert qs.get_action(e,b,event)
    qs.respond_assignment(e,b,event,expected_version=2,decision='REFUSE',comment='Indisponible',command_id='refusal')
    with pytest.raises(PermissionError):qs.get_action(e,b,event)
    assert qs.access_grants(e,a,event)[0]['revoked_at']
    qs.assign_action(e,a,event,expected_version=3,delegate_role='ADMIN',delegate_id=b.subject_id,expected_result='Nouveau créneau',command_id='again')
    qs.assign_action(e,a,event,expected_version=4,delegate_role='ADMIN',delegate_id=a.subject_id,expected_result='Reprise',command_id='owner')
    with pytest.raises(PermissionError):qs.get_action(e,b,event)


def test_r17_inactive_referent_can_be_revoked_and_not_restored_by_reactivation(env):
    e,a,b=env['e'],env['admin'],env['admin2']; event=create(env,sensitivity='RESTRICTED')
    qs.set_access_grant(e,a,event,expected_version=1,role='ADMIN',subject_id=b.subject_id,can_internal=True)
    execute(e,'UPDATE admins SET active=0 WHERE email=:m',{'m':b.subject_id})
    assert qs.set_access_grant(e,a,event,expected_version=2,role='ADMIN',subject_id=b.subject_id,revoke=True)
    assert not qs.set_access_grant(e,a,event,expected_version=3,role='ADMIN',subject_id=b.subject_id,revoke=True)
    execute(e,'UPDATE admins SET active=1 WHERE email=:m',{'m':b.subject_id})
    with pytest.raises(PermissionError):qs.get_action(e,b,event)
    qs.assign_action(e,a,event,expected_version=3,delegate_role='ADMIN',delegate_id=b.subject_id,expected_result='Mission temporaire',command_id='temporary')
    assert qs.access_grants(e,a,event)[0]['grant_origin']=='ASSIGNMENT'
    qs.respond_assignment(e,b,event,expected_version=4,decision='REFUSE',comment='Mission refusée',command_id='refusal')
    with pytest.raises(PermissionError):qs.get_action(e,b,event)


def test_r17_independent_explicit_grant_survives_end_of_mission(env):
    e,a,b=env['e'],env['admin'],env['admin2']; event=create(env,sensitivity='RESTRICTED')
    qs.set_access_grant(e,a,event,expected_version=1,role='ADMIN',subject_id=b.subject_id)
    qs.assign_action(e,a,event,expected_version=2,delegate_role='ADMIN',delegate_id=b.subject_id,expected_result='Mission',command_id='mission')
    qs.respond_assignment(e,b,event,expected_version=3,decision='REFUSE',comment='Pas pour cette mission',command_id='refusal')
    assert qs.get_action(e,b,event)
    assert qs.access_grants(e,a,event)[0]['grant_origin']=='EXPLICIT'


def test_r18_disabling_delivery_during_first_provider_call_stops_remaining_batch(env):
    e,a=env['e'],env['admin']; event=create(env); qs.configure_organization(e,a,email_enabled=True)
    calls=[]
    def provider(*args,**kwargs):
        calls.append(args)
        qs.configure_organization(e,a,email_enabled=False)
        return {'accepted':True,'receipt':'simulé'}
    result=qn.process_outbox(e,provider,base_url='https://example.invalid',dry_run=False)
    assert result['accepted']==1 and len(calls)==1
    assert [r['status'] for r in qs.delivery_status(e,a,event)]==['ACCEPTED','PENDING']


def test_r18_deleting_case_during_delivery_does_not_send_or_crash_remaining_batch(env):
    e,a=env['e'],env['admin']; event=create(env)
    qs.configure_organization(e,a,email_enabled=True,deletion_enabled=True,retention_days=0)
    calls=[]
    def provider(*args,**kwargs):
        calls.append(args)
        qs.delete_action(e,a,event,expected_version=1,reason='Base fictive',command_id='delete')
        return {'accepted':True,'receipt':'simulé'}
    result=qn.process_outbox(e,provider,base_url='https://example.invalid',dry_run=False)
    assert result['accepted']==1 and len(calls)==1
    assert q(e,'SELECT * FROM quality_notification_outbox')==[]


@pytest.mark.parametrize('classification',['TEST','A_EXAMINER'])
def test_r18_test_and_unclassified_records_never_call_email_provider(env,classification):
    e,a=env['e'],env['admin']; create(env,classification=classification)
    qs.configure_organization(e,a,email_enabled=True)
    def forbidden(*args,**kwargs):pytest.fail('Aucun envoi pour une donnée d’essai ou non qualifiée')
    assert qn.process_outbox(e,forbidden,base_url='https://example.invalid',dry_run=False)['cancelled']==2


def test_r19_in_app_reminders_are_unique_and_removed_when_deadline_changes(env):
    e,a=env['e'],env['admin']; event=create(env,due_at='2000-01-01')
    qs.configure_organization(e,a,reminder_days=1)
    qn.schedule_reminders(e);qn.schedule_reminders(e)
    sql="SELECT COUNT(*) n FROM workspace_notifications WHERE source_event_id LIKE 'go4:reminder:%'"
    assert one(e,sql)['n']==2
    qs.update_action(e,a,event,expected_version=1,due_at='2100-01-01')
    assert one(e,sql)['n']==0


def test_r15_delegate_never_receives_earlier_public_requester_exchange(env):
    e,a,b,t=env['e'],env['admin'],env['ben'],env['trainer']
    event=qs.create_action(e,b,'Demande confidentielle','Contexte bénéficiaire',action_id=env['aids'][0],command_id='beneficiary')
    qs.update_action(e,a,event,expected_version=1,comment='Réponse au bénéficiaire contenant un détail privé')
    piece=qs.add_attachment(e,a,event,expected_version=2,data=b'Detail personnel',filename='reponse.txt',audience='PUBLIC',command_id='private_reply')
    qs.assign_action(e,a,event,expected_version=3,delegate_role='TRAINER',delegate_id=t.subject_id,expected_result='Tester une procédure générique',command_id='mission')
    delegated=qs.get_action(e,t,event)
    assert not delegated['messages'] and not delegated['attachments']
    assert 'Contexte bénéficiaire' not in str(delegated)
    with pytest.raises(PermissionError):qs.read_attachment(e,t,event,piece)
    assert qs.read_attachment(e,b,event,piece)['data']==b'Detail personnel'


def test_r23_concurrent_distinct_delete_commands_produce_one_receipt(env,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy.exc import OperationalError
    e,a=env['e'],env['admin']; event=create(env)
    qs.configure_organization(e,a,deletion_enabled=True,retention_days=0)
    barrier=Barrier(2); original=qs._deletion_preview_tx
    def simultaneous(*args,**kwargs):
        preview=original(*args,**kwargs)
        barrier.wait(timeout=5)
        return preview
    monkeypatch.setattr(qs,'_deletion_preview_tx',simultaneous)
    def delete(index):
        try:return qs.delete_action(e,a,event,1,'Suppression fictive concurrente',f'delete-{index}')
        except (qs.ConflictError,PermissionError,OperationalError) as error:return error
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(delete,[1,2]))
    assert sum(isinstance(result,dict) and result['deleted'] for result in results)==1
    assert one(e,'SELECT COUNT(*) n FROM quality_deletion_receipts')['n']==1
    assert not one(e,'SELECT id FROM quality_events WHERE id=:e',{'e':event})
    assert q(e,'SELECT * FROM quality_notification_outbox')==[]


def test_r08_general_existing_quality_event_requires_explicit_tenant_choice(env):
    e,a=env['e'],env['admin']; event=create(env)
    execute(e,'UPDATE quality_events SET organization_id=NULL,go4_managed=0 WHERE id=:e',{'e':event})
    first=qs.migrate_legacy(e,a)
    assert first['events_adopted']==0
    assert first['unresolved'][0]['kind']=='QUALITY_EVENT'
    second=qs.migrate_legacy(e,a,general_source_ids=[('QUALITY_EVENT',event)])
    assert second['events_adopted']==1
    assert qs.get_action(e,a,event)['event']['organization_id']==a.organization_id
    assert qs.migrate_legacy(e,a)['events_adopted']==0


def test_r08_exact_reconciliation_preserves_request_author_reply_and_single_row(env):
    e,a,b=env['e'],env['admin'],env['ben']; now=utcnow_iso()
    event=qs.create_action(e,b,'Objet historique','Texte historique',action_id=env['aids'][0],command_id='legacy_event')
    source=execute(e,'''INSERT INTO beneficiary_reports(action_id,beneficiary_id,report_type,subject,description,status,admin_response,created_at,updated_at)
      VALUES(:a,:b,'OBSERVATION','Objet historique','Texte historique','EN_COURS','Réponse originelle',:n,:n)''',
      {'a':env['aids'][0],'b':env['bids'][0],'n':now})
    result=qs.migrate_legacy(e,a)
    assert result['sources_created']==0 and result['unresolved'][0]['candidate_ids']==[event]
    assert qs.reconcile_legacy_source(e,a,event,'BENEFICIARY_REPORT',source,expected_version=1)
    assert not qs.reconcile_legacy_source(e,a,event,'BENEFICIARY_REPORT',source,expected_version=2)
    qs.migrate_legacy(e,a)
    case=qs.get_action(e,b,event)
    assert one(e,'SELECT COUNT(*) n FROM quality_events')['n']==1
    assert [m['message'] for m in case['messages']]==['Réponse originelle']
    assert qs.get_action(e,a,event)['event']['created_by']==b.label
    assert f'BENEFICIARY_REPORT:{source}' in qs.list_actions(e,a)[0]['legacy_aliases']


def test_r08_reconciliation_refuses_same_text_from_different_author(env):
    e,a,b=env['e'],env['admin'],env['ben']; now=utcnow_iso()
    event=qs.create_action(e,b,'Objet','Texte',action_id=env['aids'][0],command_id='event')
    source=execute(e,'''INSERT INTO beneficiary_reports(action_id,beneficiary_id,report_type,subject,description,status,created_at,updated_at)
      VALUES(:a,:b,'OBSERVATION','Objet','Texte','EN_COURS',:n,:n)''',{'a':env['aids'][0],'b':env['bids'][1],'n':now})
    with pytest.raises(ValueError):qs.reconcile_legacy_source(e,a,event,'BENEFICIARY_REPORT',source,expected_version=1)
    assert version(env,event)==1 and q(e,'SELECT * FROM quality_source_links')==[]


def test_r08_managed_legacy_mutation_cannot_bypass_atomic_closure(env):
    from services import update_quality_event
    e,a=env['e'],env['admin']; event=create(env)
    with pytest.raises(ValueError):update_quality_event(e,event,actor=a.label,status='CLOTURE')
    assert qs.get_action(e,a,event)['event']['status']=='NOUVEAU'
    assert version(env,event)==1


def test_r23_shared_document_and_second_case_link_survive_unitary_deletion(env,tmp_path,monkeypatch):
    import hashlib
    import services
    e,a=env['e'],env['admin']
    monkeypatch.setattr(services,'BENEFICIARY_DOC_DIR',tmp_path/'shared_documents')
    services.BENEFICIARY_DOC_DIR.mkdir()
    data=b'Cours partage fictif'
    reference,_,_=services.store_document(e,data,'cours.txt','COURS',a.key,action_id=env['aids'][0])
    stored=one(e,'''SELECT sf.* FROM stored_files sf JOIN document_references dr ON dr.stored_file_id=sf.id WHERE dr.id=:r''',{'r':reference})
    events=[create(env,action_id=env['aids'][0]),create(env,action_id=env['aids'][0])]
    attachments=[]
    for event in events:
        attachments.append(execute(e,'''INSERT INTO quality_attachments(event_id,filename,mime_type,byte_size,sha256,document_reference_id,audience,author,created_at)
          VALUES(:e,'cours.txt','text/plain',:size,:sha,:ref,'PUBLIC',:a,:n)''',
          {'e':event,'size':len(data),'sha':hashlib.sha256(data).hexdigest(),'ref':reference,'a':a.label,'n':utcnow_iso()}))
    assert qs.read_attachment(e,a,events[0],attachments[0])['data']==data
    qs.configure_organization(e,a,deletion_enabled=True,retention_days=0)
    qs.delete_action(e,a,events[0],expected_version=1,reason='Suppression fictive unitaire',command_id='delete')
    assert one(e,'SELECT * FROM stored_files WHERE id=:i',{'i':stored['id']})==stored
    assert one(e,'SELECT id FROM document_references WHERE id=:r',{'r':reference})
    assert qs.read_attachment(e,a,events[1],attachments[1])['data']==data
    assert services.read_document_for_actor(e,reference,'BENEFICIARY',env['bids'][0],env['aids'][0])==data


def test_r08_original_report_attachment_keeps_bytes_and_authorized_access(env,tmp_path,monkeypatch):
    e,a,b=env['e'],env['admin'],env['ben']; now=utcnow_iso()
    root=tmp_path/'legacy_reports';root.mkdir();path=root/'original.txt';path.write_bytes(b'Piece historique fictive')
    monkeypatch.setattr(qs,'LEGACY_ATTACHMENT_ROOT',root)
    source=execute(e,'''INSERT INTO beneficiary_reports(action_id,beneficiary_id,report_type,subject,description,attachment_name,attachment_path,created_at,updated_at)
      VALUES(:a,:b,'OBSERVATION','Demande avec piece','Contexte','ancienne.txt',:path,:n,:n)''',
      {'a':env['aids'][0],'b':env['bids'][0],'path':str(path),'n':now})
    first=qs.migrate_legacy(e,a);qs.migrate_legacy(e,a)
    event=first['mappings'][0]['event_id'];case=qs.get_action(e,b,event)
    assert len(case['attachments'])==1
    att=case['attachments'][0]
    assert att['id']==f'legacy:BENEFICIARY_REPORT:{source}'
    assert str(path) not in str(case)
    assert qs.read_attachment(e,b,event,att['id'])['data']==path.read_bytes()
    assert qs.read_attachment(e,a,event,att['id'])['filename']=='ancienne.txt'
    other=qs.QualityActor('BENEFICIARY',env['bids'][1],env['orgs'][0])
    with pytest.raises(PermissionError):qs.read_attachment(e,other,event,att['id'])
    assert one(e,'SELECT attachment_path FROM beneficiary_reports WHERE id=:s',{'s':source})['attachment_path']==str(path)


def test_r15_original_attachment_cannot_escape_approved_report_directory(env,tmp_path,monkeypatch):
    e,a=env['e'],env['admin'];now=utcnow_iso()
    root=tmp_path/'reports';root.mkdir();outside=tmp_path/'not_a_report.txt';outside.write_text('Jamais exposer')
    monkeypatch.setattr(qs,'LEGACY_ATTACHMENT_ROOT',root)
    source=execute(e,'''INSERT INTO trainer_reports(action_id,trainer_id,report_type,subject,description,attachment_name,attachment_path,created_at,updated_at)
      VALUES(:a,:t,'OBSERVATION','Ancien signalement','Texte','piece.txt',:path,:n,:n)''',
      {'a':env['aids'][0],'t':env['tids'][0],'path':str(outside),'n':now})
    event=qs.migrate_legacy(e,a)['mappings'][0]['event_id']
    with pytest.raises(ValueError):qs.read_attachment(e,a,event,f'legacy:TRAINER_REPORT:{source}')
    assert outside.read_text()=='Jamais exposer'
