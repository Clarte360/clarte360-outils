from study_analytics import (
    pip_order, onet_order, record_is_termine, population_summary,
    individual_concordance, concordance_summary, feeling_summary,
)


def rec(study_id, pip, onet=None, feeling=None, status=None, completed_at=None):
    r={
      'study_id':study_id,'study_consent':True,
      'pip_scoring':{'complete':True,'order':list(pip),'indices':{}},
      'onet_state':onet or {},'feeling':feeling or {},
    }
    if status is not None:r['status']=status
    if completed_at is not None:r['completed_at']=completed_at
    return r


def onet(order):
    names={'R':'realistic','I':'investigative','A':'artistic','S':'social','E':'enterprising','C':'conventional'}
    return {'completed':True,'results':[{'code':names[c],'score':60-i} for i,c in enumerate(order)]}


def feel(global_=4,dominants=5,nuances=3,useful=4,over='Aucune',under='S'):
    questions={
      'global':{'text':'Global','kind':'scale5'},'dominants':{'text':'Dominants','kind':'scale5'},
      'nuances':{'text':'Nuances','kind':'scale5'},'useful':{'text':'Utile','kind':'scale5'},
      'over':{'text':'Trop haut','kind':'delta'},'under':{'text':'Trop bas','kind':'delta'},
    }
    return {'questions':questions,'answers':{'global':global_,'dominants':dominants,'nuances':nuances,'useful':useful,'over':over,'under':under}}


def test_order_extraction_and_strict_pair():
    r=rec('a','RIASEC',onet('RIASEC'))
    assert pip_order(r)==list('RIASEC')
    assert onet_order(r)==list('RIASEC')
    x=individual_concordance(r)
    assert x['same_positions']==6


def test_concordance_distribution_and_position_rates():
    rows=[
      rec('a','RIASEC',onet('RIASEC')),
      rec('b','RIASEC',onet('IRASEC')),
      rec('c','RIASEC',onet('CESAIR')),
    ]
    s=concordance_summary(rows)
    assert s['N']==3
    assert [x['same_positions'] for x in map(individual_concordance,rows)]==[6,4,0]
    hist={x['positions_identiques']:x['n'] for x in s['distribution']}
    assert hist[6]==1 and hist[4]==1 and hist[0]==1
    assert s['mean_same_positions']==round(10/3,2)
    assert s['positions'][0]['n']==1  # only first record has R at position 1
    assert s['positions'][2]['n']==2  # A at position 3 in first two


def test_population_separates_pip_only_and_pip_onet():
    rows=[rec('a','RIASEC',onet('RIASEC'),feel()),rec('b','SIAERC',None,feel()),rec('c','CESAIR',onet('CESAIR'))]
    p=population_summary(rows)
    assert p['n_pip']==3
    assert p['n_pip_onet']==2
    assert p['n_pip_only']==1
    assert p['n_feeling']==2


def test_legacy_completed_at_without_feeling_is_not_termine():
    legacy=rec('a','RIASEC',onet('RIASEC'),{},completed_at='2026-09-19T10:00:00+00:00')
    assert record_is_termine(legacy) is False
    completed=rec('b','RIASEC',onet('RIASEC'),feel(),completed_at='2026-09-24T10:00:00+00:00')
    assert record_is_termine(completed) is True
    explicit=rec('c','RIASEC',onet('RIASEC'),feel(),status='EN_COURS',completed_at='2026-09-24T10:00:00+00:00')
    assert record_is_termine(explicit) is False


def test_feeling_summary_uses_only_questions_really_recorded():
    rows=[rec('a','RIASEC',None,feel(4,5,3,4,'R','Aucune')),rec('b','RIASEC',None,feel(5,5,4,5,'Aucune','S'))]
    s=feeling_summary(rows)
    global_row=next(x for x in s['scale'] if x['key']=='global')
    assert global_row['n']==2 and global_row['n_4']==1 and global_row['n_5']==1
    over=next(x for x in s['delta'] if x['key']=='over')
    counts={x['modalite']:x['n'] for x in over['modalites']}
    assert counts['R']==1 and counts['Aucune']==1

def test_h33c_ui_exposes_required_collective_indicators_only():
    from pathlib import Path
    src=Path('app.py').read_text(encoding='utf-8')
    assert 'N ayant réalisé PIP' in src
    assert 'N PIP + O*NET' in src
    assert 'N PIP seul' in src
    assert 'N avec ressenti exploitable' in src
    assert 'Concordance individuelle PIP ↔ O*NET' in src
    assert 'Concordance par position' in src
    assert 'Moyenne des positions identiques' in src
    assert 'Indicateurs techniques sur les items PIP' in src


def test_h33c_services_legacy_completion_uses_real_feeling_gate():
    from pathlib import Path
    src=Path('services.py').read_text(encoding='utf-8')
    assert 'return record_is_termine(r)' in src
    assert "(r.get('pip_scoring') or {}).get('complete')" in src
