from collections import Counter
from clarte360_pip.pip_data.loader import load_pip_bank
from clarte360_pip.pip_data.validation import validate_bank

def test_bank72_contract():
    b=load_pip_bank(); assert b["bank_version"]=="PIP-BANK-0.5"; assert len(b["items"])==72; assert validate_bank(b)==[]
    assert Counter(x["dimension"] for x in b["items"])==Counter({d:12 for d in "RIASEC"})

def test_all_30_facets_covered_at_least_twice():
    b=load_pip_bank(); c=Counter(x["facette"] for x in b["items"]); assert len(c)==30; assert min(c.values())>=2

def test_no_separate_examples_and_concrete_texts():
    b=load_pip_bank(); assert all("exemple_concret" not in x for x in b["items"]); assert all(len(x["texte_fr"].strip())>=25 for x in b["items"])

def test_item_versions_are_v05():
    b=load_pip_bank(); assert {x["item_version"] for x in b["items"]}=={"0.6"}
