from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from clarte360_ipip.framework.validation import ValidationError, validate_score

@dataclass(frozen=True)
class QuestionnaireItem:
    item_no: int
    text_fr: str
    domain_code: str
    facet_code: str
    reverse_scored: bool

@dataclass(frozen=True)
class Questionnaire:
    version: str
    response_scale: dict[int, str]
    disclaimer: str
    items: tuple[QuestionnaireItem, ...]


def load_questionnaire(path: Path) -> Questionnaire:
    raw=json.loads(path.read_text(encoding='utf-8'))
    items=tuple(QuestionnaireItem(
        item_no=int(x['item_no']), text_fr=str(x['adaptation_fr']).strip(),
        domain_code=str(x['domain_code']), facet_code=str(x['facet_code']),
        reverse_scored=bool(x['reverse_scored'])) for x in raw['items'])
    nums=[x.item_no for x in items]
    if len(items)!=120 or nums!=list(range(1,121)) or len(set(nums))!=120:
        raise ValidationError('Le référentiel actif doit contenir exactement les items 1 à 120, dans cet ordre.')
    if any(not x.text_fr for x in items):
        raise ValidationError('Un item du questionnaire est vide.')
    scale={int(k):str(v) for k,v in raw['response_scale'].items()}
    if set(scale)!={1,2,3,4,5}: raise ValidationError('Échelle de réponse invalide.')
    return Questionnaire(str(raw['version']),scale,str(raw['mandatory_disclaimer']),items)


def validate_answers(answers: dict[int, Any], allowed_items: set[int] | None=None) -> dict[int,int]:
    out={}
    for k,v in answers.items():
        n=int(k)
        if not 1<=n<=120 or (allowed_items is not None and n not in allowed_items):
            raise ValidationError('Numéro d’item invalide.')
        out[n]=validate_score(v,f'Réponse {n}')
    return out


def block_items(q: Questionnaire, block_index: int, block_size: int=10):
    if block_size not in (10,12): raise ValidationError('Taille de bloc invalide.')
    count=(len(q.items)+block_size-1)//block_size
    if not 0<=block_index<count: raise ValidationError('Bloc invalide.')
    start=block_index*block_size
    return q.items[start:start+block_size]
