from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Mapping

from clarte360_ipip.framework.validation import ValidationError
from clarte360_ipip.questionnaire.model import Questionnaire, validate_answers

DOMAIN_ORDER = ('N','E','O','A','C')

@dataclass(frozen=True)
class FacetScore:
    code: str
    domain_code: str
    corrected_sum: int
    mean: float
    index_0_100: float
    item_numbers: tuple[int, ...]

@dataclass(frozen=True)
class DomainScore:
    code: str
    corrected_sum: int
    mean: float
    index_0_100: float
    facet_codes: tuple[str, ...]

@dataclass(frozen=True)
class ScoringResult:
    algorithm_version: str
    reference_version: str
    corrected_items: dict[int, int]
    facets: dict[str, FacetScore]
    domains: dict[str, DomainScore]

    def to_dict(self) -> dict:
        return {
            'algorithm_version': self.algorithm_version,
            'reference_version': self.reference_version,
            'corrected_items': {str(k): v for k,v in self.corrected_items.items()},
            'facets': {k: asdict(v) for k,v in self.facets.items()},
            'domains': {k: asdict(v) for k,v in self.domains.items()},
        }

ALGORITHM_VERSION = 'ipip-scoring-v1'

def _index(mean: float) -> float:
    return round((mean - 1.0) / 4.0 * 100.0, 6)

def score_questionnaire(q: Questionnaire, answers: Mapping[int, int]) -> ScoringResult:
    clean = validate_answers(dict(answers), allowed_items={x.item_no for x in q.items})
    if set(clean) != set(range(1,121)):
        missing = sorted(set(range(1,121)) - set(clean))
        raise ValidationError(f'Le scoring exige exactement 120 réponses. Manquantes: {missing[:10]}')

    by_no={x.item_no:x for x in q.items}
    corrected={n:(6-v if by_no[n].reverse_scored else v) for n,v in clean.items()}

    facet_items: dict[str,list[int]]={}
    facet_domain: dict[str,str]={}
    for item in q.items:
        facet_items.setdefault(item.facet_code,[]).append(item.item_no)
        facet_domain[item.facet_code]=item.domain_code
    if len(facet_items)!=30 or any(len(v)!=4 for v in facet_items.values()):
        raise ValidationError('Structure invalide: 30 facettes de 4 items sont requises.')

    facets={}
    for code, nums in facet_items.items():
        total=sum(corrected[n] for n in nums); mean=total/4.0
        facets[code]=FacetScore(code,facet_domain[code],total,mean,_index(mean),tuple(nums))

    domains={}
    for domain in DOMAIN_ORDER:
        nums=[x.item_no for x in q.items if x.domain_code==domain]
        fcodes=tuple(f'{domain}{i}' for i in range(1,7))
        if len(nums)!=24 or any(c not in facets for c in fcodes):
            raise ValidationError(f'Structure invalide pour le domaine {domain}.')
        total=sum(corrected[n] for n in nums); mean=total/24.0
        facet_mean=sum(facets[c].mean for c in fcodes)/6.0
        if abs(mean-facet_mean)>1e-12:
            raise ValidationError(f'Incohérence de calcul du domaine {domain}.')
        domains[domain]=DomainScore(domain,total,mean,_index(mean),fcodes)

    return ScoringResult(ALGORITHM_VERSION,q.version,corrected,facets,domains)
