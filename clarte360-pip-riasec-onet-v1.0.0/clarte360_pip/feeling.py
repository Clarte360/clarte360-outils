from __future__ import annotations
from datetime import datetime
QUESTIONS_VERSION="PIP-FEELING-1.0"
QUESTIONS={
 "global":{"text":"Dans quelle mesure le profil présenté vous ressemble-t-il ?","kind":"scale5"},
 "dominants":{"text":"Les dimensions qui ressortent le plus correspondent-elles à ce qui vous attire professionnellement ?","kind":"scale5"},
 "nuances":{"text":"Le rapport rend-il suffisamment compte des différentes façons dont vos intérêts peuvent s’exprimer ?","kind":"scale5"},
 "over":{"text":"Une dimension vous paraît-elle trop élevée par rapport à votre ressenti ?","kind":"delta"},
 "under":{"text":"Une dimension vous paraît-elle trop faible par rapport à votre ressenti ?","kind":"delta"},
 "useful":{"text":"Ce résultat vous aide-t-il à mieux comprendre ce qui vous attire dans le travail ?","kind":"scale5"},
 "dialogue":{"text":"Souhaitez-vous approfondir certains éléments avec votre accompagnateur ?","kind":"yesno"},
}
def build_feeling_record(answers:dict, context:str, report_version:str|None=None)->dict:
 return {"version":QUESTIONS_VERSION,"questions":QUESTIONS,"answers":answers,"context":context,"report_version":report_version,"recorded_at":datetime.now().isoformat(timespec="seconds")}
