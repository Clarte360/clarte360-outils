from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from clarte360_ipip.framework.validation import ValidationError
from clarte360_ipip.scoring import ScoringResult, DOMAIN_ORDER

@dataclass(frozen=True)
class InterpretationReference:
    version: str
    principles: tuple[str, ...]
    domains: dict[str, dict[str, Any]]
    facets: dict[str, dict[str, Any]]


def load_interpretation(path: Path) -> InterpretationReference:
    raw=json.loads(path.read_text(encoding='utf-8'))
    domains={str(x['code']):x for x in raw.get('domains',[])}
    facets={str(x['code']):x for x in raw.get('facets',[])}
    if set(domains)!=set(DOMAIN_ORDER):
        raise ValidationError('Référentiel d’interprétation invalide : 5 domaines attendus.')
    expected={f'{d}{i}' for d in DOMAIN_ORDER for i in range(1,7)}
    if set(facets)!=expected:
        raise ValidationError('Référentiel d’interprétation invalide : 30 facettes attendues.')
    required_facet={'display_fr','scientific_term','plain_definition','low_tendency','intermediate_tendency','high_tendency','debrief_question','guardrail'}
    for code,row in facets.items():
        missing=required_facet-set(row)
        if missing: raise ValidationError(f'Facette {code} incomplète : {sorted(missing)}')
    return InterpretationReference(str(raw.get('version','')),tuple(raw.get('principles',[])),domains,facets)


def tendency_band(mean: float) -> str:
    # Convention descriptive Clarté360, non normative et non percentile.
    if mean < 2.5: return 'less'
    if mean > 3.5: return 'more'
    return 'intermediate'


def tendency_label(mean: float) -> str:
    return {'less':'Tendance moins marquée','intermediate':'Zone intermédiaire','more':'Tendance plus marquée'}[tendency_band(mean)]


def interpret_scoring(result: ScoringResult, ref: InterpretationReference) -> dict[str, Any]:
    domains=[]
    for code in DOMAIN_ORDER:
        score=result.domains[code]; meta=ref.domains[code]
        domains.append({
            'code':code,'display_fr':meta['display_fr'],'scientific_term':meta['scientific_term'],
            'plain_definition':meta['plain_definition'],'mean':score.mean,'index_0_100':score.index_0_100,
            'tendency_band':tendency_band(score.mean),'tendency_label':tendency_label(score.mean),
        })
    facets=[]
    for d in DOMAIN_ORDER:
        for i in range(1,7):
            code=f'{d}{i}'; score=result.facets[code]; meta=ref.facets[code]; band=tendency_band(score.mean)
            text={'less':meta['low_tendency'],'intermediate':meta['intermediate_tendency'],'more':meta['high_tendency']}[band]
            facets.append({
                'code':code,'domain':d,'display_fr':meta['display_fr'],'scientific_term':meta['scientific_term'],
                'plain_definition':meta['plain_definition'],'mean':score.mean,'index_0_100':score.index_0_100,
                'tendency_band':band,'tendency_label':tendency_label(score.mean),'tendency_text':text,
                'debrief_question':meta['debrief_question'],'guardrail':meta['guardrail'],
            })
    return {
        'schema':'clarte360.ipipneo.interpretation.v1','reference_version':ref.version,
        'scoring_algorithm_version':result.algorithm_version,'principles':list(ref.principles),
        'domains':domains,'facets':facets,
        'non_normative_notice':'Les repères moins marquée / intermédiaire / plus marquée sont descriptifs. Ils ne sont ni des percentiles ni des normes françaises.'
    }
