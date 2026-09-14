import tempfile
from datetime import date, timedelta

import pytest

from db import make_engine, init_db, one
from input_validation import (
    InputValidationError, validate_person_name, validate_email, validate_phone,
    validate_birth_date, validate_action_no, validate_postal_code, validate_siret,
    validate_nda, validate_naf, validate_vat_id, validate_url, validate_timezone,
    validate_json_text, validate_date_range, validate_slot, validate_action_payload,
    validate_participant_payload, validate_organization_payload, validate_agency_payload,
    validate_crm_payload,
)
from services import (
    create_action, add_participant, add_trainer, create_crm_contact,
    upsert_organization, add_agency, set_action_client_contacts,
    set_trainer_microsoft_email, save_import_profile,
)


def engine_tmp():
    p=tempfile.NamedTemporaryFile(suffix='.db',delete=False); p.close()
    e=make_engine('sqlite:///'+p.name); init_db(e); return e


@pytest.mark.parametrize('value', [
    'DURAND','Durand','Élodie','Jean-Pierre',"D'ARC",'Anne Marie','Őri','Łukasz','Zoë','N’Diaye'
])
def test_person_name_valid(value):
    assert validate_person_name(value)


@pytest.mark.parametrize('value', [
    'DURAND2','123','Jean_Pierre','Jean@Pierre','Jean/Pierre','Jean.Pierre','<script>',
    '-Durand','Durand-',' Durand - ','Jean  Pierre','Jean--Pierre','Jean😊'
])
def test_person_name_rejects_misplaced_values(value):
    with pytest.raises(InputValidationError):
        validate_person_name(value)


@pytest.mark.parametrize('value', [
    'dominique@example.com','prenom.nom+test@sub.example.fr','a@b.co','TEST@EXAMPLE.COM'
])
def test_email_valid(value):
    out=validate_email(value,required=True)
    assert '@' in out and out == out.lower()


@pytest.mark.parametrize('value', [
    'dominique','@example.com','a@','a@@example.com','a b@example.com','a@example',
    'a..b@example.com','.a@example.com','a.@example.com','a@-example.com','a@example-.com',
    'a@example..com','a@example.com\nBCC:x@y.com'
])
def test_email_rejects_invalid(value):
    with pytest.raises(InputValidationError): validate_email(value,required=True)


@pytest.mark.parametrize('value', [
    '+33 6 12 34 56 78','06 12 34 56 78','+36-30-123-4567','(01) 42 00 00 00','0612345678'
])
def test_phone_valid(value):
    assert validate_phone(value)


@pytest.mark.parametrize('value', ['123','abcdef','06AB123456','++33612345678','06#12#34#56','1234567890123456'])
def test_phone_rejects_invalid(value):
    with pytest.raises(InputValidationError): validate_phone(value)


def test_birth_date_boundaries():
    assert validate_birth_date(date.today().isoformat()) == date.today().isoformat()
    with pytest.raises(InputValidationError): validate_birth_date((date.today()+timedelta(days=1)).isoformat())
    with pytest.raises(InputValidationError): validate_birth_date('1900-02-30')
    with pytest.raises(InputValidationError): validate_birth_date('31364')


@pytest.mark.parametrize('value', ['CLA0001','ADCA-2026/001','A_1.2','X'])
def test_action_no_valid(value): assert validate_action_no(value)

@pytest.mark.parametrize('value', ['CLA 001','CLA#001','../CLA001','CLA;DROP','é001',''])
def test_action_no_invalid(value):
    with pytest.raises(InputValidationError): validate_action_no(value)


@pytest.mark.parametrize('value', ['75016','H2X 1Y4','SW1A 1AA','1011'])
def test_postal_valid(value): assert validate_postal_code(value)

@pytest.mark.parametrize('value', ['75@016','<75016>','75016\nX'])
def test_postal_invalid(value):
    with pytest.raises(InputValidationError): validate_postal_code(value)


def test_french_identifiers_formats():
    assert validate_siret('123 456 789 00012') == '12345678900012'
    with pytest.raises(InputValidationError): validate_siret('123456')
    with pytest.raises(InputValidationError): validate_siret('1234567890001A')
    assert validate_nda('11750000075') == '11750000075'
    with pytest.raises(InputValidationError): validate_nda('1175ABC0075')
    assert validate_naf('8559A') == '8559A'
    assert validate_naf('85.59A') == '8559A'
    with pytest.raises(InputValidationError): validate_naf('855A')
    assert validate_vat_id('FR 40 123456789') == 'FR40123456789'
    with pytest.raises(InputValidationError): validate_vat_id('123456789')


def test_url_timezone_json():
    assert validate_url('https://www.clarte360.com')
    with pytest.raises(InputValidationError): validate_url('www.clarte360.com')
    with pytest.raises(InputValidationError): validate_url('javascript:alert(1)')
    assert validate_timezone('Europe/Paris') == 'Europe/Paris'
    with pytest.raises(InputValidationError): validate_timezone('Paris/France')
    assert validate_json_text('{"a":1}')
    with pytest.raises(InputValidationError): validate_json_text('[1,2,3]')
    with pytest.raises(InputValidationError): validate_json_text('{bad}')


def test_date_range_and_slot():
    assert validate_date_range('2026-09-01','2026-09-02') == ('2026-09-01','2026-09-02')
    with pytest.raises(InputValidationError): validate_date_range('2026-09-03','2026-09-02')
    assert validate_slot('2026-09-01','09:00','09:30') == ('2026-09-01','09:00','09:30')
    with pytest.raises(InputValidationError): validate_slot('2026-09-01','09:00','09:00')
    with pytest.raises(InputValidationError): validate_slot('2026-02-30','09:00','10:00')
    with pytest.raises(InputValidationError): validate_slot('2026-09-01','25:00','10:00')


def test_payloads_normalize_and_reject():
    a=validate_action_payload({'action_no':'cla-1','title':'Test','admin_email':'admin@example.com','planned_hours':1,'expected_participants':1})
    assert a['action_no']=='CLA-1'
    with pytest.raises(InputValidationError): validate_action_payload({'action_no':'CLA 1','title':'Test','admin_email':'admin@example.com','planned_hours':1,'expected_participants':1})
    with pytest.raises(InputValidationError): validate_action_payload({'action_no':'CLA1','title':'','admin_email':'admin@example.com','planned_hours':1,'expected_participants':1})
    with pytest.raises(InputValidationError): validate_action_payload({'action_no':'CLA1','title':'Test','admin_email':'bad','planned_hours':1,'expected_participants':1})
    with pytest.raises(InputValidationError): validate_action_payload({'action_no':'CLA1','title':'Test','admin_email':'admin@example.com','planned_hours':-1,'expected_participants':1})

    p=validate_participant_payload({'last_name':'DURAND','first_name':'Élodie','email':'e@example.com','phone':'+33 6 11 22 33 44'})
    assert p['email']=='e@example.com'
    with pytest.raises(InputValidationError): validate_participant_payload({'last_name':'DUR4ND','first_name':'Élodie'})
    with pytest.raises(InputValidationError): validate_participant_payload({'last_name':'DURAND','first_name':'Él0die'})


def test_org_and_agency_payloads():
    org=validate_organization_payload({'name':'Clarté360','siret':'12345678900012','nda':'11750000075','naf':'8559A','website':'https://clarte360.com','general_email':'contact@clarte360.com','phone':'+33 1 23 45 67 89','timezone':'Europe/Paris'})
    assert org['siret']=='12345678900012'
    with pytest.raises(InputValidationError): validate_organization_payload({'name':'Clarté360','siret':'123','timezone':'Europe/Paris'})
    with pytest.raises(InputValidationError): validate_organization_payload({'name':'Clarté360','general_email':'contact@bad','timezone':'Europe/Paris'})
    ag=validate_agency_payload({'name':'Paris','email':'paris@example.com','phone':'01 23 45 67 89','siret':'12345678900012','nda':'11750000075'})
    assert ag['email']=='paris@example.com'


def test_crm_payload_rejects_name_digits():
    assert validate_crm_payload('Farid','Benali','f@example.com','0612345678')['first_name']=='Farid'
    with pytest.raises(InputValidationError): validate_crm_payload('Far1d','Benali','f@example.com')
    with pytest.raises(InputValidationError): validate_crm_payload('Farid','Ben@li','f@example.com')


def _base_action(no='VAL001'):
    return {'action_no':no,'title':'Validation','subtitle':None,'nature':'Formation','mode':'INTRA','delivery_mode':'PRESENTIEL','client_name':None,'client_type':'Non précisé','group_code':None,'planned_hours':1.0,'expected_participants':1,'admin_email':'admin@example.com','trainer_name':None,'trainer_email':None,'location':None,'notes':None,'source':'TEST'}


def test_service_boundaries_reject_bad_structured_data():
    e=engine_tmp()
    aid=create_action(e,_base_action(),'test')
    with pytest.raises(InputValidationError):
        add_participant(e,aid,{'last_name':'DUR4ND','first_name':'Marie','email':'m@example.com'},'test')
    with pytest.raises(InputValidationError):
        add_trainer(e,'Marc Renaud2','marc@example.com','0612345678','test')
    with pytest.raises(InputValidationError):
        create_crm_contact(e,'Far1d','BENALI','f@example.com',actor='test')
    with pytest.raises(InputValidationError):
        set_action_client_contacts(e,aid,admin_email='pas-un-email',actor='test')
    with pytest.raises(InputValidationError):
        set_trainer_microsoft_email(e,999,'pas-un-email','test')


def test_service_organization_and_import_profile_validation():
    e=engine_tmp()
    with pytest.raises(InputValidationError):
        upsert_organization(e,None,{'name':'X','siret':'123','timezone':'Europe/Paris'},'test')
    oid=upsert_organization(e,None,{'name':'X','timezone':'Europe/Paris'},'test')
    with pytest.raises(InputValidationError):
        add_agency(e,oid,{'name':'Agence','email':'bad-email'},'test')
    with pytest.raises(InputValidationError):
        save_import_profile(e,None,oid,{'code':'PRO FIL','name':'Profil','source_type':'EXCEL','action_key':'NO','mapping_json':'{}','config_json':'{}','active':True},'test')
    with pytest.raises(InputValidationError):
        save_import_profile(e,None,oid,{'code':'PROFIL','name':'Profil','source_type':'EXCEL','action_key':'NO','mapping_json':'[1,2]','config_json':'{}','active':True},'test')

def test_structured_fields_resist_injection_and_control_characters():
    bad_names=['Robert; DROP TABLE participants;','<b>Robert</b>','Robert\x00Martin','Robert\tMartin','Robert/../../x','Robert%20Martin','Robert🙂']
    for v in bad_names:
        with pytest.raises(InputValidationError): validate_person_name(v)
    bad_emails=['x@example.com\r\nBCC:evil@example.com','<x>@example.com','x @example.com','x@example.com<script>']
    for v in bad_emails:
        with pytest.raises(InputValidationError): validate_email(v,required=True)
    bad_phones=['0612345678<script>','0612345678\nX','tel:0612345678','06_12_34_56_78']
    for v in bad_phones:
        with pytest.raises(InputValidationError): validate_phone(v)
