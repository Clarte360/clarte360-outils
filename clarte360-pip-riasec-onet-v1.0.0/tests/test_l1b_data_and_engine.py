from collections import Counter
from clarte360_pip.pip_data.loader import load_pip_bank
from clarte360_pip.pip_data.validation import validate_bank
from clarte360_pip.questionnaire import QuestionnaireEngine, build_order

def test_runtime_bank_valid():
 b=load_pip_bank(); assert validate_bank(b)==[]; assert b["bank_version"]=="PIP-BANK-0.5"

def test_exact_distribution():
 b=load_pip_bank(); assert Counter(x["dimension"] for x in b["items"])==Counter({d:12 for d in "RIASEC"}); assert len(set(x["facette"] for x in b["items"]))==30

def test_closed_scale_exact_text():
 b=load_pip_bank(); assert b["response_scale"]=={"1":"Je n’aimerais pas du tout faire cela","2":"J’aimerais peu faire cela","3":"Je suis partagé(e) / sans préférence marquée","4":"J’aimerais assez faire cela","5":"J’aimerais beaucoup faire cela"}

def test_order_is_complete_unique_deterministic_and_blocked():
 b=load_pip_bank(); a=build_order(b,"abc"); c=build_order(b,"abc"); assert a==c; assert len(a)==72==len(set(a)); idx={x["item_id"]:x for x in b["items"]}; blocks=[idx[i]["bloc"] for i in a]; assert blocks==sorted(blocks,key={"ACT":0,"SIT":1,"ENV":2}.get)

def test_dimensions_are_mixed_inside_blocks():
 b=load_pip_bank(); order=build_order(b,"xyz"); idx={x["item_id"]:x for x in b["items"]}; assert all(idx[a]["dimension"]!=idx[c]["dimension"] for a,c in zip(order,order[1:]) if idx[a]["bloc"]==idx[c]["bloc"])

def test_engine_rejects_invalid_answer_and_requires_answer():
 b=load_pip_bank(); e=QuestionnaireEngine(b,build_order(b,"x"),{});
 try: e.answer(6); assert False
 except ValueError: pass
 try: e.next(); assert False
 except ValueError: pass

def test_engine_completes_all_72():
 b=load_pip_bank(); e=QuestionnaireEngine(b,build_order(b,"done"),{});
 for n in range(72):
  e.answer((n%5)+1)
  if n<71: e.next()
 assert e.completed(); assert len(e.answers)==72
