from __future__ import annotations
from dataclasses import dataclass

RIASEC = "RIASEC"
SCORING_VERSION = "PIP-SCORE-0.5"

@dataclass(frozen=True)
class ScoreResult:
    means: dict[str,float]
    indices: dict[str,float]
    order: list[str]
    exact_ties: list[list[str]]
    holland_code: str | None
    code_extended: list[list[str]]
    complete: bool
    answered: int
    expected: int
    algorithm_version: str = SCORING_VERSION

def score_pip(bank:dict, answers:dict[str,int]) -> ScoreResult:
    items=bank["items"]; expected=len(items)
    active={x["item_id"]:x for x in items}
    valid={k:v for k,v in answers.items() if k in active and v in (1,2,3,4,5)}
    complete=len(valid)==expected
    vals={d:[] for d in RIASEC}
    for iid,v in valid.items(): vals[active[iid]["dimension"]].append(v)
    means={d:(sum(vals[d])/len(vals[d]) if vals[d] else 0.0) for d in RIASEC}
    indices={d:(25*(means[d]-1) if vals[d] else 0.0) for d in RIASEC}
    order=sorted(RIASEC,key=lambda d:(-indices[d], RIASEC.index(d)))
    groups=[]
    for d in order:
        if groups and indices[groups[-1][0]]==indices[d]: groups[-1].append(d)
        else: groups.append([d])
    ties=[g for g in groups if len(g)>1]
    top=[]
    for g in groups:
        if len(top)>=3: break
        top.append(g)
    # A 3-letter code is only emitted when the first three ranks are unambiguous.
    first3=order[:3]
    unambiguous=complete and len(set(indices[d] for d in first3))==3 and (len(order)==3 or indices[first3[-1]]!=indices[order[3]])
    code="".join(first3) if unambiguous else None
    return ScoreResult(means,indices,order,ties,code,top,complete,len(valid),expected)
