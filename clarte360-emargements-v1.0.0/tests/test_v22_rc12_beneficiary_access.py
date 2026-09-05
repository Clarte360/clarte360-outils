from db import make_engine, init_db, execute, one, utcnow_iso
from security import hash_password
from services import create_beneficiary_password_reset, beneficiary_by_reset_token, complete_beneficiary_password_reset, verify_beneficiary_login

def setup_beneficiary(tmp_path):
    e=make_engine(f"sqlite:///{tmp_path/'b.db'}"); init_db(e); now=utcnow_iso()
    bid=execute(e,"INSERT INTO beneficiaries(public_id,last_name,first_name,birth_date,current_email,created_at,updated_at) VALUES('BEN-X','PAQUETTE','Quentin','1990-01-01','q@example.org',:n,:n)",{'n':now})
    execute(e,"INSERT INTO beneficiary_portal_accounts(beneficiary_id,email,password_hash,active,created_at,updated_at) VALUES(:b,'q@example.org',:p,1,:n,:n)",{'b':bid,'p':hash_password('AncienMotDePasse1!'),'n':now})
    return e,bid

def test_beneficiary_password_reset_is_single_use(tmp_path):
    e,bid=setup_beneficiary(tmp_path)
    acc,token=create_beneficiary_password_reset(e,'q@example.org')
    assert acc and token and acc['beneficiary_id']==bid
    assert beneficiary_by_reset_token(e,token)
    ok,msg=complete_beneficiary_password_reset(e,token,'NouveauMotDePasse2!')
    assert ok
    assert verify_beneficiary_login(e,'q@example.org','NouveauMotDePasse2!')
    assert beneficiary_by_reset_token(e,token) is None
    ok2,_=complete_beneficiary_password_reset(e,token,'EncoreUnMotDePasse3!')
    assert not ok2

def test_unknown_beneficiary_reset_does_not_create_token(tmp_path):
    e,_=setup_beneficiary(tmp_path)
    acc,token=create_beneficiary_password_reset(e,'inconnu@example.org')
    assert acc is None and token is None
