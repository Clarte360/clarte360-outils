from __future__ import annotations
import random
from dataclasses import dataclass

BLOCKS=("ACT","SIT","ENV")

def build_order(bank: dict, seed: str) -> list[str]:
    rng=random.Random(seed); out=[]
    for block in BLOCKS:
        by_dim={d:[x for x in bank["items"] if x["bloc"]==block and x["dimension"]==d] for d in "RIASEC"}
        for values in by_dim.values(): rng.shuffle(values)
        previous=None
        while any(by_dim.values()):
            available=[d for d,v in by_dim.items() if v and d!=previous]
            if not available: available=[d for d,v in by_dim.items() if v]
            # Prefer dimensions with most remaining items; randomize ties.
            maxn=max(len(by_dim[d]) for d in available)
            candidates=[d for d in available if len(by_dim[d])==maxn]
            d=rng.choice(candidates); out.append(by_dim[d].pop()["item_id"]); previous=d
    return out


@dataclass
class QuestionnaireEngine:
    bank: dict
    order: list[str]
    answers: dict[str,int]
    index: int=0
    def __post_init__(self):
        self._items={x["item_id"]:x for x in self.bank["items"]}
    @property
    def total(self): return len(self.order)
    @property
    def current_id(self): return self.order[self.index]
    @property
    def current(self): return self._items[self.current_id]
    def answer(self, value:int):
        if value not in (1,2,3,4,5): raise ValueError("Réponse PIP hors échelle 1-5.")
        self.answers[self.current_id]=value
    def next(self):
        if self.current_id not in self.answers: raise ValueError("Une réponse est requise avant de continuer.")
        if self.index < self.total-1: self.index += 1
    def previous(self):
        if self.index>0: self.index-=1
    def completed(self): return len(self.answers)==self.total
