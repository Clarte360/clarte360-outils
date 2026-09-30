from pathlib import Path

from db import make_engine, init_db, execute, one
from services import (
    upsert_organization, add_agency, save_import_profile,
    delete_organization_if_unused, delete_agency_if_unused, delete_import_profile,
    organization_delete_dependencies, agency_delete_dependencies,
    create_improvement_action, update_improvement_action, delete_improvement_action
)


def eng(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'tables.db'))
    init_db(e)
    return e


def org_payload(name='Org Test'):
    return {
        'name':name,'legal_name':None,'address':None,'postal_code':None,'city':'Paris','country':'France',
        'siret':None,'rcs':None,'naf':None,'vat_id':None,'nda':None,'website':None,'general_email':None,
        'phone':None,'timezone':'Europe/Paris','privacy_contact':None,'privacy_notice':None,'logo_path':None,
        'favicon_path':None,'primary_color':None,'secondary_color':None,'email_from_name':None,
        'email_from_address':None,'retention_months':None
    }


def test_master_data_tables_support_safe_delete(tmp_path):
    e=eng(tmp_path)
    oid=upsert_organization(e,None,org_payload(),'admin')
    aid=add_agency(e,oid,{'name':'Agence test','country':'France'},'admin')
    pid=save_import_profile(e,None,oid,{'code':'TEST','name':'Profil test','source_type':'EXCEL','action_key':'NO_CLAR','action_sheet':'A','participant_sheet':'P','mapping_json':'{}','config_json':'{}','active':True},'admin')
    assert agency_delete_dependencies(e,aid)==[]
    assert delete_agency_if_unused(e,aid,'admin') is True
    assert delete_import_profile(e,pid,'admin') is True
    assert organization_delete_dependencies(e,oid)==[]
    assert delete_organization_if_unused(e,oid,'admin') is True


def test_organization_and_agency_delete_are_blocked_when_used(tmp_path):
    e=eng(tmp_path)
    oid=upsert_organization(e,None,org_payload('Org utilisée'),'admin')
    aid=add_agency(e,oid,{'name':'Agence utilisée','country':'France'},'admin')
    action_id=execute(e,"""INSERT INTO actions(action_no,title,nature,mode,planned_hours,status,organization_id,agency_id,created_at,updated_at)
        VALUES('A1','Action','FORMATION','INTRA',1,'BROUILLON',:o,:g,'2026-09-30','2026-09-30')""",{'o':oid,'g':aid})
    assert organization_delete_dependencies(e,oid)
    assert agency_delete_dependencies(e,aid)
    try:
        delete_agency_if_unused(e,aid,'admin')
        assert False
    except ValueError:
        pass
    try:
        delete_organization_if_unused(e,oid,'admin')
        assert False
    except ValueError:
        pass


def test_improvement_action_is_editable_and_deletable(tmp_path):
    e=eng(tmp_path)
    oid=upsert_organization(e,None,org_payload(),'admin')
    action_id=execute(e,"""INSERT INTO actions(action_no,title,nature,mode,planned_hours,status,organization_id,created_at,updated_at)
        VALUES('A2','Action','FORMATION','INTRA',1,'BROUILLON',:o,'2026-09-30','2026-09-30')""",{'o':oid})
    iid=create_improvement_action(e,action_id,'Action initiale','Desc','Moi','2026-10-15',None,'admin')
    update_improvement_action(e,iid,'EN_COURS','admin','Action corrigée','Nouvelle desc','Responsable','2026-10-20')
    row=one(e,'SELECT * FROM improvement_actions WHERE id=:i',{'i':iid})
    assert row['title']=='Action corrigée' and row['status']=='EN_COURS' and row['owner']=='Responsable'
    assert delete_improvement_action(e,iid,'admin') is True
    assert one(e,'SELECT * FROM improvement_actions WHERE id=:i',{'i':iid}) is None


def test_all_application_tables_are_actionable_or_explicitly_read_only():
    src=Path('app.py').read_text(encoding='utf-8').splitlines()
    failures=[]
    read_only_markers=(
        'lecture seule','historique','traçabilité','restitution','preuve','se modifient dans',
        'journal','consolidée','régularisation elle-même','vue dérivée','vue de restitution'
    )
    interactive_tokens=(
        'st.selectbox(','st.button(','st.form(','st.checkbox(','st.multiselect(','st.radio(',
        'st.text_input(','st.date_input(','st.data_editor(','st.download_button(','st.link_button('
    )
    for i,line in enumerate(src):
        if 'st.dataframe(' not in line and 'st.data_editor(' not in line and 'st.table(' not in line:
            continue
        window='\n'.join(src[max(0,i-8):min(len(src),i+32)]).lower()
        if any(tok in window for tok in interactive_tokens):
            continue
        if any(mark in window for mark in read_only_markers):
            continue
        failures.append((i+1,line.strip()))
    assert not failures, f"Tableaux sans action métier ni justification lecture seule : {failures}"


def test_transversal_management_ui_is_present():
    src=Path('app.py').read_text(encoding='utf-8')
    for text in [
        'OUVRIR / GÉRER CETTE ACTION',
        "Action d'amélioration à gérer",
        "Supprimer cette action d'amélioration",
        'Signalement à traiter',
        "Supprimer définitivement l'organisme",
        "Supprimer définitivement l'agence",
        "Supprimer définitivement ce profil d'import",
        'Supprimer définitivement cet outil'
    ]:
        assert text in src
