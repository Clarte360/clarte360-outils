from db import make_engine, init_db, one
from services import (
    create_action, add_participant, add_slot, activate_action,
    set_generic_action_module, action_module, q, create_beneficiary,
    find_beneficiary_candidates,
)


def make_action(expected=1, planned=1.0):
    e=make_engine('sqlite:///:memory:'); init_db(e)
    aid=create_action(e,{
        'action_no':'I8-TEST','title':'I8 test','subtitle':None,'nature':'FORMATION','mode':'INTRA',
        'client_name':'Client','client_type':'Professionnel','group_code':None,'planned_hours':planned,
        'expected_participants':expected,'admin_email':'admin@example.org','trainer_name':None,'trainer_email':None,
        'location':'Teams ONLINE','notes':None,'source':'TEST'
    },'test')
    return e,aid


def test_i8_teams_can_be_selected_before_any_slot_exists():
    e,aid=make_action()
    eff=set_generic_action_module(e,aid,'TEAMS',True,'admin')
    assert eff is None
    mod=action_module(e,aid,'TEAMS')
    assert mod['enabled']==1
    assert mod['effective_from'] is None


def test_i8_first_future_slot_sets_teams_effective_date_and_queues_sync():
    e,aid=make_action()
    set_generic_action_module(e,aid,'TEAMS',True,'admin')
    sid=add_slot(e,aid,'2099-10-15','09:00','10:00','admin')
    mod=action_module(e,aid,'TEAMS')
    assert mod['effective_from'].startswith('2099-10-15T09:00:00')
    events=q(e,"SELECT * FROM teams_sync_events WHERE action_id=:a AND status='PENDING'",{'a':aid})
    assert any(x['slot_id']==sid and x['event_type']=='SLOT_ADDED' for x in events)


def test_i8_activation_requires_real_participant_count_to_match_expected_count():
    e,aid=make_action(expected=2,planned=1.0)
    add_participant(e,aid,{'last_name':'DUPONT','first_name':'Anne','email':'anne@example.org'},'test')
    add_slot(e,aid,'2099-10-15','09:00','10:00','test')
    ok,issues=activate_action(e,aid,'admin')
    assert not ok
    assert any('1 inscrit(s) pour 2 prévu(s)' in x for x in issues)


def test_i8_exact_beneficiary_match_is_distinguishable_from_approximate_match():
    e,aid=make_action()
    bid=create_beneficiary(e,'BRIET','Dominique','1966-02-23','d@example.org',actor='test')
    matches=find_beneficiary_candidates(e,'briet','dominique','1966-02-23')
    assert len(matches)==1
    assert matches[0]['id']==bid
    assert matches[0]['exact_match'] is True
    assert matches[0]['match_score']==100
