from __future__ import annotations
import json, hashlib, os
from pathlib import Path

PROMPT_VERSION = 'qualification_intervenant_v1_20260920'

QUALIFICATION_SCHEMA = {
    'type':'object','additionalProperties':False,
    'properties':{
        'service_level':{'type':'integer','minimum':0,'maximum':4},
        'confidence':{'type':'number','minimum':0,'maximum':1},
        'rationale':{'type':'string'},
        'evidence':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{
            'source':{'type':'string'},'fact':{'type':'string'},'supports_level':{'type':'integer','minimum':0,'maximum':4}
        },'required':['source','fact','supports_level']}},
        'missing_points':{'type':'array','items':{'type':'string'}},
        'criteria':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{
            'criterion_id':{'type':'integer'},'proposed_level':{'type':'integer','minimum':0,'maximum':4},
            'confidence':{'type':'number','minimum':0,'maximum':1},'rationale':{'type':'string'}
        },'required':['criterion_id','proposed_level','confidence','rationale']}}
    },
    'required':['service_level','confidence','rationale','evidence','missing_points','criteria']
}

INSTRUCTIONS = """Tu assistes un administrateur Clarté360 dans l'analyse de l'adéquation entre le dossier factuel d'une personne professionnelle et UNE prestation Clarté360.
Règles impératives :
- L'IA propose, l'humain décide. Ne jamais présenter ta sortie comme une validation ou une certification.
- Utilise uniquement les faits, documents et critères fournis. N'invente jamais diplôme, expérience, compétence, date, habilitation ou mission.
- En cas d'information insuffisante, baisse la confiance et indique clairement les éléments manquants.
- Échelle : 0 non démontré ; 1 sensibilisé/connaissances de base ; 2 capable avec accompagnement/expérience partielle ; 3 autonome ; 4 référent/expert capable d'accompagner d'autres intervenants.
- Une certification Qualiopi, un NDA ou une qualification Clarté360 sont des notions distinctes.
- Le niveau global doit être prudent et cohérent avec les critères obligatoires et les preuves disponibles.
- Réponds strictement selon le schéma JSON demandé, en français clair et sans jargon inutile.
"""

class QualificationAIGateway:
    def __init__(self, api_key:str, model:str, timeout:float=45.0, client=None):
        self.api_key=(api_key or '').strip(); self.model=(model or '').strip() or 'gpt-5-mini'; self.timeout=timeout; self._client=client
    @property
    def ready(self): return bool(self.api_key or self._client)
    def _client_obj(self):
        if self._client is not None: return self._client
        if not self.api_key: raise RuntimeError("La clé API OpenAI n'est pas configurée.")
        try:
            from openai import OpenAI
        except Exception as exc:
            raise RuntimeError("Le client OpenAI n'est pas installé.") from exc
        return OpenAI(api_key=self.api_key, timeout=self.timeout, max_retries=0)
    def analyze(self, payload:dict):
        request_hash=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()
        client=self._client_obj()
        response=client.responses.create(model=self.model,instructions=INSTRUCTIONS,input=json.dumps(payload,ensure_ascii=False),store=False,max_output_tokens=1800,
            text={'format':{'type':'json_schema','name':'qualification_intervenant','strict':True,'schema':QUALIFICATION_SCHEMA}})
        if getattr(response,'status',None) not in (None,'completed'):
            raise RuntimeError(f"Réponse IA incomplète : {getattr(response,'status',None)}")
        txt=getattr(response,'output_text','')
        if not txt: raise RuntimeError('Réponse IA vide.')
        data=json.loads(txt)
        return {'result':data,'request_hash':request_hash,'usage':getattr(response,'usage',None),'model':self.model,'prompt_version':PROMPT_VERSION,'provider':'openai'}


def extract_document_text(path:str, extension:str='', max_chars:int=18000)->str:
    p=Path(path); ext=(extension or p.suffix).lower().lstrip('.')
    if not p.exists(): return ''
    try:
        if ext=='pdf':
            from pypdf import PdfReader
            parts=[]
            for page in PdfReader(str(p)).pages:
                parts.append(page.extract_text() or '')
                if sum(len(x) for x in parts)>=max_chars: break
            return '\n'.join(parts)[:max_chars]
        if ext=='docx':
            from docx import Document
            doc=Document(str(p)); return '\n'.join(x.text for x in doc.paragraphs if x.text)[:max_chars]
        if ext in ('txt','md','csv'):
            return p.read_text(encoding='utf-8',errors='ignore')[:max_chars]
    except Exception:
        return ''
    return ''
