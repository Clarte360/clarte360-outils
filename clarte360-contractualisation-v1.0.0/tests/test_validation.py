from datetime import date,time,timedelta
import pytest
from validation import *

def test_names_accept_real_world():
    for x in ["O'Connor", 'Jean-Pierre', 'Élodie', 'Dvořák', 'Anne Marie']:
        assert clean_name(x, field='Nom')

def test_names_reject_bad_inputs():
    for x in ['Jean123','<script>','🙂','   ']:
        with pytest.raises(ValidationError): clean_name(x, field='Nom')

def test_email_validation():
    assert clean_email('a.b+tag@example.fr') == 'a.b+tag@example.fr'
    for x in ['abc','a@b','a@b.com\nBcc:x@y.com','a@b.com;c@d.com']:
        with pytest.raises(ValidationError): clean_email(x)

def test_phone_validation():
    assert clean_phone('+33 (0)1 89 48 08 25')
    with pytest.raises(ValidationError): clean_phone('hello')

def test_no_clar():
    assert clean_no_clar('cla0002') == 'CLA0002'
    for x in ['../CLA0002','CLA2','CLA0002/xx']:
        with pytest.raises(ValidationError): clean_no_clar(x)

def test_birth_date_plausibility():
    assert validate_birth_date(date.today()-timedelta(days=365*30))
    with pytest.raises(ValidationError): validate_birth_date(date.today()+timedelta(days=1))

def test_period_and_times():
    today=date.today(); future=today+timedelta(days=1)
    assert validate_period(future,future,today)
    with pytest.raises(ValidationError): validate_period(future,today,today)
    with pytest.raises(ValidationError): validate_times(time(18),time(17))

def test_numbers_finite_and_bounded():
    assert clean_amount('10.5',field='Montant') == 10.5
    for x in ['nan','inf',-1,1000001]:
        with pytest.raises(ValidationError): clean_amount(x,field='Montant')

def test_excel_formula_injection_neutralised():
    assert excel_safe_text('=HYPERLINK("x")',field='Obs').startswith("'=")
    assert excel_safe_text('normal',field='Obs') == 'normal'

def test_financements_balance_and_types():
    rows=[{'TYPE_FINANCEUR':'BENEFICIAIRE','MONTANT_TTC':120,'TAUX_TVA':20,'NOM_FINANCEUR':'X'}]
    assert validate_financements(rows,120)[0]['MONTANT_TTC']==120
    with pytest.raises(ValidationError): validate_financements(rows,100)
    with pytest.raises(ValidationError): validate_financements([{'TYPE_FINANCEUR':'XXX','MONTANT_TTC':100}],100)

def test_aps_structure_and_fields():
    good={'meta':{'document_type':'APS'},'beneficiaire':{'prenom':'Jean','nom':'Dupont','email':'j@exemple.fr','date_naissance':'1980-01-01'}}
    assert validate_aps_document(good) is good
    with pytest.raises(ValidationError): validate_aps_document({'meta':{'document_type':'OTHER'}})

def test_filename():
    validate_filename('base.xlsm',('.xlsm',))
    with pytest.raises(ValidationError): validate_filename('../base.xlsm',('.xlsm',))
