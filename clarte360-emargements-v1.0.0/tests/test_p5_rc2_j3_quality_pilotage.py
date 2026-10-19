"""J3 Quality steering and review: fictitious local data; no mail/VPS/GitHub."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from db import make_engine, init_db, execute, one, q, utcnow_iso
from services import (
    ensure_default_organization, create_action, create_questionnaire_template,
    create_quality_campaign, save_quality_response, quality_dashboard,
    quality_management_summary, quality_question_stats, quality_dashboard_v31,
    quality_campaign_pilotage, quality_campaign_pilotage_summary,
    queue_quality_manual_reminder, schedule_quality_email_events,
    quality_review_points, quality_short_treatment, quality_case,
    quality_campaign_email_history, complete_quality_campaign, quality_questions,
    create_quality_event,create_quality_issue, link_quality_source
)

ADMIN='admin@example.invalid'

@pytest.fixture
def ctx(tmp_path):
    engine=make_engine('sqlite:///'+str(tmp_path/'j3.sqlite'))
    init_db(engine);oid=ensure_default_organization(engine)
    actions=[]
    for no in ('TEST-J3','VOISINE-J3'):
        aid=create_action(engine,{
          'action_no':no,'title':'Formation fictive','subtitle':None,'nature':'FORMATION',
          'mode':'INDIVIDUEL','client_name':'Fictif','client_type':'ENTREPRISE',
          'group_code':None,'planned_hours':2,'expected_participants':1,
          'admin_email':ADMIN,'trainer_name':None,'trainer_email':None,
          'location':None,'notes':None,'source':'TEST'},ADMIN)
        execute(engine,'UPDATE actions SET organization_id=:o,prestation_type=\'FORMATION\' WHERE id=:i',{'o':oid,'i':aid})
        actions.append(aid)
    return engine,oid,*actions


def form(ctx,action_idx=2,kind='HOT',scores=(5,5),nps=10,text='RAS',due='past',status='COMPLETED'):
    engine,oid,*_=ctx
    aid=ctx[action_idx]
    question_def=[
        {'question_code':'R01','rubric_code':'R01','response_type':'SCALE_1_5','question_text':'Information','required':1},
        {'question_code':'R02','rubric_code':'R01','response_type':'SCALE_1_5','question_text':'Préparation','required':1},
        {'question_code':'R11','rubric_code':'R11','response_type':'NPS_0_10','question_text':'Recommandation','required':1},
        {'question_code':'R12','rubric_code':'R12','response_type':'TEXT_LONG','question_text':'Avis libre','required':0}]
    template=create_questionnaire_template(engine,oid,f'TEST-{kind}-{action_idx}-{one(engine,"SELECT COUNT(*) n FROM questionnaire_templates")["n"]}',
                                           '1.0','FORMATION',kind,'Questionnaire fictif',question_def,ADMIN)
    due_at=(datetime.now(timezone.utc)+(timedelta(days=3) if due=='future' else -timedelta(days=2))).isoformat()
    cid,_=create_quality_campaign(engine,aid,template,kind,due_at,actor=ADMIN)
    qs=quality_questions(engine,cid)
    for qu,answer in zip(qs,[*scores,nps,text]):
        save_quality_response(engine,cid,qu['id'],answer,ADMIN)
    execute(engine,'UPDATE quality_campaigns SET status=:s,completed_at=:n WHERE id=:i',{
        's':status,'n':utcnow_iso() if status=='COMPLETED' else None,'i':cid})
    return cid,qs


def test_nps_ten_never_yields_satisfaction_above_five(ctx):
    form(ctx,nps=10)
    e,_,a,_=ctx
    dashboard=quality_dashboard(e,action_id=a)
    assert dashboard['scores']==[5.0,5.0]
    assert dashboard['nps']==[10.0]
    assert quality_dashboard_v31(e,action_id=a)['by_kind']['HOT']['score']==5.0


def test_text_rarely_numeric_is_excluded_from_average(ctx):
    form(ctx,scores=(2,4),nps=9,text='10')
    e,_,a,_=ctx
    stats=quality_question_stats(e,action_id=a)
    assert [x['Moyenne'] for x in stats if x['Échelle']=='1-5']==[2.0,4.0]
    assert all(x['Moyenne'] is None for x in stats if x['Échelle']!='1-5')


def test_na_excluded_without_becoming_zero(ctx):
    form(ctx,scores=('N/A',5),nps=0)
    e,_,a,_=ctx
    summary=quality_management_summary(e,action_id=a)
    assert summary['rubric_averages']['Information et objectifs']==5.0
    assert len(summary['scores'])==1 and summary['scores'][0]==5.0


def test_weighted_rubric_average_not_mean_of_question_means(ctx):
    form(ctx,scores=(1,5))
    form(ctx,scores=(1,5))
    e,_,a,_=ctx
    rows=quality_question_stats(e,action_id=a)
    assert len([x for x in rows if x['Échelle']=='1-5'])==2
    assert quality_management_summary(e,action_id=a)['rubric_averages']['Information et objectifs']==3.0


def test_validate_scale_rejects_out_of_range(ctx):
    e,_,a,_=ctx
    cid,qs=form(ctx)
    for ans in (6,0,True,1.5,'5',float('nan')):
        with pytest.raises(ValueError,match='sur 5'):
            save_quality_response(e,cid,qs[0]['id'],ans,ADMIN)
    assert one(e,'SELECT answer_json FROM quality_responses WHERE campaign_id=:c AND question_id=:q',
               {'c':cid,'q':qs[0]['id']})['answer_json']=='5'


def test_validate_nps_rejects_invalid(ctx):
    e,_,a,_=ctx
    cid,qs=form(ctx)
    for ans in (11,-1,True,5.6,'9'):
        with pytest.raises(ValueError,match='NPS'):
            save_quality_response(e,cid,qs[2]['id'],ans,ADMIN)
    assert one(e,'SELECT answer_json FROM quality_responses WHERE campaign_id=:c AND question_id=:q',
               {'c':cid,'q':qs[2]['id']})['answer_json']=='10'


def test_legacy_invalid_old_values_are_ignored_not_clamped(ctx):
    e,_,a,_=ctx;cid,qs=form(ctx)
    execute(e,"UPDATE quality_responses SET answer_json='8' WHERE campaign_id=:c AND question_id=:q",{'c':cid,'q':qs[0]['id']})
    assert quality_dashboard_v31(e,action_id=a)['by_kind']['HOT']['score']==5.0
    execute(e,"UPDATE quality_responses SET answer_json='-1' WHERE campaign_id=:c AND question_id=:q",{'c':cid,'q':qs[2]['id']})
    assert quality_management_summary(e,action_id=a)['nps_score'] is None


def test_client_and_prescriber_weighted_together(ctx):
    form(ctx,kind='CLIENT',scores=(1,1))
    form(ctx,kind='PRESCRIBER',scores=(5,5))
    e,_,a,_=ctx
    combined=quality_campaign_pilotage_summary(e,action_id=a)
    assert combined['invitations']==2 and combined['completed']==2
    assert combined['valid_scores']==4 and combined['score']==3.0


def test_opco_trainer_stay_separate(ctx):
    form(ctx,kind='TRAINER',scores=(3,3))
    form(ctx,kind='OPCO',scores=(5,5))
    e,_,a,_=ctx
    scores=quality_dashboard_v31(e,action_id=a)['by_kind']
    assert scores['TRAINER']['score']==3.0 and scores['OPCO']['score']==5.0


def test_campaign_overview_counts_status_and_notifies_nobody(ctx):
    e,_,a,_=ctx
    cid,_=form(ctx,kind='HOT',status='PENDING',due='future')
    overview=quality_campaign_pilotage(e,action_id=a)
    assert overview['total']==1 and overview['by_kind']['HOT']['pending']==1
    assert overview['rows'][0]['availability']=='À venir'
    assert not quality_campaign_email_history(e,cid)


def test_campaign_email_receipts_and_reminders_are_not_confused(ctx):
    e,_,a,_=ctx
    cid,_=form(ctx,kind='COLD',status='PENDING')
    schedule_quality_email_events(e,cid,utcnow_iso(),'COLD')
    queue_quality_manual_reminder(e,cid,ADMIN)
    before=quality_campaign_pilotage(e,action_id=a)['rows'][0]
    assert before['sent_reminders']==0 and before['pending_reminders']==1
    execute(e,"UPDATE quality_email_events SET status='SENT',sent_at=:t WHERE campaign_id=:c AND event_type='INITIAL'",{'c':cid,'t':utcnow_iso()})
    execute(e,"UPDATE quality_email_events SET status='SENT',sent_at=:t WHERE campaign_id=:c AND event_type='MANUAL_1'",{'c':cid,'t':utcnow_iso()})
    after=quality_campaign_pilotage(e,action_id=a)['rows'][0]
    assert after['initial_sent'] and after['sent_reminders']==1 and after['pending_reminders']==0


def test_campaign_scope_cannot_show_other_action(ctx):
    form(ctx,action_idx=2)
    form(ctx,action_idx=3)
    e,_,a,other=ctx
    assert [x['action_id'] for x in quality_campaign_pilotage(e,action_id=a)['rows']]==[a]
    assert [x['action_id'] for x in quality_campaign_pilotage(e,action_id=other)['rows']]==[other]


def _low_campaign(ctx,with_text='RAS',decision=None):
    e,oid,a,_=ctx
    # Build campaign in future? use past, then complete with low score.
    cid,qs=form(ctx,scores=(2,5),text=with_text,status='PENDING')
    execute(e,'DELETE FROM quality_responses WHERE campaign_id=:c',{'c':cid})
    answers={q['id']:(2 if q['question_code']=='R01' else 5 if q['question_code']=='R02' else 9 if q['question_code']=='R11' else with_text) for q in qs}
    complete_quality_campaign(e,cid,answers,'beneficiary')
    pts=quality_review_points(e,action_id=a,open_only=True)
    return cid,qs,pts


def test_short_review_creates_single_case_and_immutable_trace(ctx):
    e,_,a,_=ctx;cid,qs,pts=_low_campaign(ctx)
    assert len(pts)==1
    ev_id=quality_short_treatment(e,ADMIN,'PRISE_EN_COMPTE','Suivi par responsable',point_id=pts[0]['id'])
    case=quality_case(e,ev_id)
    assert case['event']['status']=='EN_TRAITEMENT'
    assert case['messages'][0]['message']=='Suivi par responsable'
    assert any(h['change_kind']=='TRAITEMENT_COURT' for h in case['history'])
    assert quality_review_points(e,a,True)==[]
    with pytest.raises(ValueError,match='déjà été examiné'):
        quality_short_treatment(e,ADMIN,'PRISE_EN_COMPTE','En double',point_id=pts[0]['id'])


def test_short_review_classification_requires_comment_and_closes(ctx):
    e,_,a,_=ctx;_,_,pts=_low_campaign(ctx)
    with pytest.raises(ValueError,match='motif'):
        quality_short_treatment(e,ADMIN,'CLASSE',' ',point_id=pts[0]['id'])
    assert quality_review_points(e,a,True)
    eid=quality_short_treatment(e,ADMIN,'CLASSE','Sans conséquence avérée',point_id=pts[0]['id'])
    result=quality_case(e,eid)['event']
    assert result['status']=='CLASSE_SANS_SUITE' and result['closure_comment']=='Sans conséquence avérée'
    assert result['closed_at']


def test_short_review_capa_creates_single_action_and_history(ctx):
    e,_,a,_=ctx;_,_,pts=_low_campaign(ctx)
    eid=quality_short_treatment(e,ADMIN,'PLAN_ACTION','Contrôler les documents',point_id=pts[0]['id'])
    case=quality_case(e,eid)
    assert len(case['actions'])==1 and case['actions'][0]['status']=='A_FAIRE'
    assert one(e,'SELECT status FROM quality_review_points WHERE id=:id',{'id':pts[0]['id']})['status']=='REPRIS_PLAN_ACTION'


def test_short_review_asks_for_clarification_without_external_notification(ctx):
    e,_,a,_=ctx;_,_,pts=_low_campaign(ctx)
    eid=quality_short_treatment(e,ADMIN,'RETOUR_DEMANDE','Précisez le besoin',point_id=pts[0]['id'])
    case=quality_case(e,eid)
    assert case['event']['status']=='EN_ATTENTE'
    assert case['messages'][0]['direction']=='INTERNE'


def test_r12_comment_short_treatment_preserves_source_sync(ctx):
    e,_,a,_=ctx
    cid,qs,pts=_low_campaign(ctx,with_text='Difficulté à accéder aux documents')
    issue=one(e,'SELECT * FROM quality_issues WHERE action_id=:a',{'a':a})
    event=one(e,"SELECT * FROM quality_events WHERE origin='QUESTIONNAIRE_R12_I06' AND action_id=:a",{'a':a})
    assert issue and event
    quality_short_treatment(e,ADMIN,'CLASSE','Explication communiquée et résolue',event_id=event['id'])
    assert one(e,'SELECT status FROM quality_issues WHERE id=:i',{'i':issue['id']})['status']=='CLOTUREE'
    assert quality_case(e,event['id'])['messages']


def test_unrelated_quality_event_refuses_short_treatment(ctx):
    e,_,a,_=ctx
    ev=create_quality_event(e,'AUDIT','OBSERVATION','Observation test','',ADMIN,action_id=a)
    with pytest.raises(ValueError,match='réservé'):
        quality_short_treatment(e,ADMIN,'CLASSE','Examen terminé',event_id=ev)
    assert one(e,'SELECT status FROM quality_events WHERE id=:e',{'e':ev})['status']=='NOUVEAU'


def test_finished_comment_short_treatment_does_not_overwrite(ctx):
    e,_,a,_=ctx;cid,qs,pts=_low_campaign(ctx,with_text='Difficulté')
    ev=one(e,"SELECT * FROM quality_events WHERE origin='QUESTIONNAIRE_R12_I06' AND action_id=:a",{'a':a})
    quality_short_treatment(e,ADMIN,'CLASSE','Motif clair',event_id=ev['id'])
    with pytest.raises(ValueError,match='déjà clôturée'):
        quality_short_treatment(e,ADMIN,'PLAN_ACTION','Ne pas modifier',event_id=ev['id'])
    assert len(quality_case(e,ev['id'])['messages'])==1


def test_review_rejects_missing_reference(ctx):
    e,_,a,_=ctx
    with pytest.raises(ValueError,match='exactement une'):
        quality_short_treatment(e,ADMIN,'CLASSE','Motif')
    with pytest.raises(ValueError,match='introuvable'):
        quality_short_treatment(e,ADMIN,'CLASSE','Motif',point_id=999)


def test_invalid_campaign_submission_rejects_before_any_write(ctx):
    e,oid,a,_=ctx
    cid,qs=form(ctx,status='PENDING',due='past')
    execute(e,'DELETE FROM quality_responses WHERE campaign_id=:c',{'c':cid})
    answers={qs[0]['id']:3,qs[1]['id']:5,qs[2]['id']:12,qs[3]['id']:'RAS'}
    with pytest.raises(ValueError,match='NPS'):
        complete_quality_campaign(e,cid,answers,'beneficiary')
    assert one(e,'SELECT COUNT(*) n FROM quality_responses WHERE campaign_id=:c',{'c':cid})['n']==0


def test_histories_remain_after_short_decision(ctx):
    e,_,a,_=ctx;_,_,pts=_low_campaign(ctx)
    eid=quality_short_treatment(e,ADMIN,'PLAN_ACTION','Suivi',point_id=pts[0]['id'])
    case=quality_case(e,eid)
    assert len(case['history'])>=3
    assert case['messages'][0]['message']=='Suivi'


def test_ui_global_and_action_share_plan_surveys_history_without_legacy_edits():
    # CDC V1.0 / maquette V1.1: the visible permanent plan replaces the old
    # "À traiter" entry; it is no longer hidden inside History. Same controls.
    s=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf8')
    assert s.count('def render_quality_case_workbench(')==1
    action=s[s.index('def quality_tab(a):'):s.index('def documents_tab(a):')]
    general=s[s.index('def quality_management_screen():'):s.index('def studies_screen():')]
    for view in ('Plan d’actions unique','Enquêtes et indicateurs','Historique'):
        assert view in action and view in general
    assert 'update_quality_issue(' not in action and 'update_user_report(' not in action
    assert 'render_quality_case_workbench(action_id=a[\'id\']' in action
    assert 'render_quality_case_workbench(action_id=action_id,' in general


def test_j4_preserves_quality_views_and_exposes_central_notifications():
    # J3 intentionally deferred notifications. Once J4 is implemented, the
    # regression gate must validate the new capability rather than an old note.
    app=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf8')
    assert 'def _j4_notification_drawer(role,actor_id):' in app
    for marker in ("_j4_notification_drawer('ADMIN'", "_j4_notification_drawer('TRAINER'",
                   "_j4_notification_drawer('BENEFICIARY'", "_j4_notification_drawer('CLIENT'"):
        assert marker in app
    assert 'def render_quality_case_workbench(' in app


def test_beneficiary_scores_do_not_mix_intervenant_questionnaires(ctx):
    form(ctx,kind='HOT',scores=(1,1))
    form(ctx,kind='TRAINER',scores=(5,5))
    e,_,a,_=ctx
    beneficiary_stats=quality_question_stats(e,action_id=a,campaign_kinds=('HOT','COLD'))
    n=sum(x['Notes valides 1-5'] for x in beneficiary_stats)
    assert round(sum(x['_sum_1_5'] for x in beneficiary_stats)/n,2)==1.0
    assert quality_dashboard_v31(e,action_id=a)['by_kind']['TRAINER']['score']==5.0


def test_general_quality_actions_and_legacy_review_remain_visible_in_org(ctx):
    # GO4 uses an explicit authorized organization instead of an unscoped
    # display filter. General requests stay visible without guessing a training.
    import quality_service as go4
    engine,oid,*_=ctx
    execute(engine,"INSERT INTO admins(email,password_hash,active,role,created_at) VALUES(:e,'fictive',1,'ADMIN',:n)",
            {'e':ADMIN,'n':utcnow_iso()})
    actor=go4.QualityActor('ADMIN',ADMIN,oid)
    event_id=go4.create_action(engine,actor,'Prévention générale fictive',command_id='j3-general-go4')
    general=go4.list_actions(engine,actor)
    assert event_id in {row['id'] for row in general}
    assert next(row for row in general if row['id']==event_id)['action_id'] is None
    s=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf8')
    assert "quality_v1.available_organizations(ENGINE,'ADMIN',st.session_state.admin_email)" in s
    assert 'Toutes, y compris les actions générales' in s
    assert "render_quality_legacy(ENGINE,actor,key='quality_global_legacy')" in s
    assert 'Aucun rattachement automatique' in s


def test_invalid_campaign_filter_is_rejected(ctx):
    e,_,a,_=ctx
    with pytest.raises(ValueError,match='inconnu'):
        quality_question_stats(e,action_id=a,campaign_kinds=('ADMIN_SECRET',))
