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
            'source':{'type':'string'},'fact':{'type':'string'},'supports_level':{'type':'integer','minimum':0,'maximum':4},
            'document_id':{'type':['integer','null']},'criterion_ids':{'type':'array','items':{'type':'integer'}},
            'identity_status':{'type':'string','enum':['COHERENT','A_VERIFIER','INCOHERENT']}
        },'required':['source','fact','supports_level','document_id','criterion_ids','identity_status']}},
        'missing_points':{'type':'array','items':{'type':'string'}},
        'criteria':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{
            'criterion_id':{'type':'integer'},'proposed_level':{'type':'integer','minimum':0,'maximum':4},
            'confidence':{'type':'number','minimum':0,'maximum':1},'rationale':{'type':'string'},
            'evidence_indexes':{'type':'array','items':{'type':'integer'}}
        },'required':['criterion_id','proposed_level','confidence','rationale','evidence_indexes']}}
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
- Pour chaque preuve repérée, indique document_id lorsqu'il est identifiable, les criterion_ids concernés et identity_status. Une identité incohérente ne constitue jamais une preuve recevable.
- Pour chaque critère, evidence_indexes référence les positions (0,1,2...) des preuves de evidence qui soutiennent la proposition.
- Réponds strictement selon le schéma JSON demandé, en français clair et sans jargon inutile.
"""

class QualificationAIGateway:
    def __init__(self, api_key:str, model:str, timeout:float=120.0, client=None):
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
        return OpenAI(api_key=self.api_key, timeout=self.timeout, max_retries=1)
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


GLOBAL_PROMPT_VERSION = 'dossier_professionnel_global_v2_1_20260930'

DOSSIER_FACTS_SCHEMA = {
 'type':'object','additionalProperties':False,
 'properties':{
  'profile':{'type':'object','additionalProperties':False,'properties':{
    'title':{'type':['string','null']},'summary':{'type':['string','null']},'specialties':{'type':'array','items':{'type':'string'}}},
    'required':['title','summary','specialties']},
  'experiences':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{
    'role_title':{'type':'string'},'organization':{'type':['string','null']},'description':{'type':['string','null']},'start_date':{'type':['string','null']},'end_date':{'type':['string','null']},'source_document_id':{'type':['integer','null']}},
    'required':['role_title','organization','description','start_date','end_date','source_document_id']}},
  'education':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{
    'diploma_title':{'type':'string'},'institution':{'type':['string','null']},'field':{'type':['string','null']},'obtained_date':{'type':['string','null']},'source_document_id':{'type':['integer','null']}},
    'required':['diploma_title','institution','field','obtained_date','source_document_id']}},
  'certifications':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{
    'certification_type':{'type':'string','enum':['CERTIFICATION','HABILITATION','ATTESTATION']},'name':{'type':'string'},'issuer':{'type':['string','null']},'reference':{'type':['string','null']},'obtained_date':{'type':['string','null']},'valid_until':{'type':['string','null']},'source_document_id':{'type':['integer','null']}},
    'required':['certification_type','name','issuer','reference','obtained_date','valid_until','source_document_id']}},
  'languages':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{
    'language':{'type':'string'},'level':{'type':['string','null']},'source_document_id':{'type':['integer','null']}},
    'required':['language','level','source_document_id']}},
  'identity_alerts':{'type':'array','items':{'type':'string'}},
  'missing_points':{'type':'array','items':{'type':'string'}}
 },
 'required':['profile','experiences','education','certifications','languages','identity_alerts','missing_points']
}

SERVICE_CANDIDATE_SCHEMA = {
 'type':'object','additionalProperties':False,'properties':{
  'service_id':{'type':'integer'},
  'service_level':{'type':'integer','minimum':0,'maximum':4},
  'confidence':{'type':'number','minimum':0,'maximum':1},
  'rationale':{'type':'string'},
  'source_document_ids':{'type':'array','items':{'type':'integer'}},
  'missing_points':{'type':'array','items':{'type':'string'}},
  'evidence':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{
    'source':{'type':'string'},'fact':{'type':'string'},'supports_level':{'type':'integer','minimum':0,'maximum':4},
    'document_id':{'type':['integer','null']},'criterion_ids':{'type':'array','items':{'type':'integer'}},
    'identity_status':{'type':'string','enum':['COHERENT','A_VERIFIER','INCOHERENT']}
  },'required':['source','fact','supports_level','document_id','criterion_ids','identity_status']}},
  'criteria':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{
    'criterion_id':{'type':'integer'},'proposed_level':{'type':'integer','minimum':0,'maximum':4},
    'confidence':{'type':'number','minimum':0,'maximum':1},'rationale':{'type':'string'},
    'evidence_indexes':{'type':'array','items':{'type':'integer'}}
  },'required':['criterion_id','proposed_level','confidence','rationale','evidence_indexes']}}
 },
 'required':['service_id','service_level','confidence','rationale','source_document_ids','missing_points','evidence','criteria']
}

SERVICE_BATCH_SCHEMA = {
 'type':'object','additionalProperties':False,
 'properties':{'service_candidates':{'type':'array','items':SERVICE_CANDIDATE_SCHEMA}},
 'required':['service_candidates']
}

GLOBAL_INSTRUCTIONS_FACTS = """Tu assistes un administrateur Clarté360 pour constituer une base factuelle UNIQUE à partir de l'ensemble du dossier professionnel transmis.
Règles impératives :
- L'IA propose uniquement ; l'humain décide.
- Utilise exclusivement les faits présents dans les pièces. N'invente rien et ne déduis pas un diplôme, une compétence, une date, une habilitation ou une mission non démontrée.
- Analyse aussi les images transmises (JPG/JPEG/PNG/WEBP) lorsqu'elles sont lisibles.
- Conserve source_document_id dès qu'un fait provient d'une pièce identifiable.
- Repère les incohérences d'identité entre la personne et les documents dans identity_alerts.
- Une pièce à identité incohérente ne doit jamais devenir une preuve recevable.
- Les dates inconnues restent nulles.
- Réponds strictement selon le schéma JSON demandé, en français clair.
"""

GLOBAL_INSTRUCTIONS_SERVICES = """Tu confrontes une base factuelle de dossier professionnel à un LOT de prestations Clarté360 et à leurs critères.
Règles impératives :
- Tu DOIS retourner EXACTEMENT UNE entrée service_candidates pour CHAQUE prestation fournie dans service_catalog, y compris lorsqu'il n'existe AUCUN rapprochement.
- N'omets jamais une prestation. Une absence totale de preuve se traduit par service_level=0, evidence=[], source_document_ids=[] et une rationale explicite du type « Aucun élément du dossier ne démontre actuellement cette prestation ».
- Pour CHAQUE prestation, tu DOIS aussi retourner une proposition pour CHAQUE critère fourni. Un critère non démontré reste à proposed_level=0 avec une justification factuelle.
- L'échelle est : 0 non démontré ; 1 sensibilisé/connaissances de base ; 2 capable avec accompagnement/expérience partielle ; 3 autonome ; 4 référent/expert capable d'accompagner d'autres intervenants.
- Le niveau global reste prudent et cohérent avec les critères obligatoires et les preuves.
- Utilise uniquement dossier_facts. N'invente aucun fait.
- Pour chaque preuve, indique document_id si identifiable, criterion_ids concernés et identity_status.
- Les pourcentages sont des indices de confiance dans la proposition, jamais une validation ni une note de valeur.
- L'IA instruit et préremplit ; l'humain accepte, corrige ou rejette.
- Réponds strictement selon le schéma JSON demandé.
"""

class GlobalDossierAIGateway(QualificationAIGateway):
    """Analyse unique côté utilisateur, exécutée techniquement en 1 extraction factuelle
    puis plusieurs lots de prestations pour éviter les timeouts et garantir 100 % du catalogue.
    """
    def _call_schema(self, instructions, content, schema_name, schema, max_output_tokens):
        client=self._client_obj()
        response=client.responses.create(
            model=self.model,
            instructions=instructions,
            input=[{'role':'user','content':content}],
            store=False,
            max_output_tokens=max_output_tokens,
            text={'format':{'type':'json_schema','name':schema_name,'strict':True,'schema':schema}}
        )
        if getattr(response,'status',None) not in (None,'completed'):
            raise RuntimeError(f"Réponse IA incomplète : {getattr(response,'status',None)}")
        txt=getattr(response,'output_text','')
        if not txt:
            raise RuntimeError('Réponse IA vide.')
        return json.loads(txt), getattr(response,'usage',None)

    @staticmethod
    def _usage_add(total, usage):
        if usage is None:
            return total
        if total is None:
            return {'input_tokens':int(getattr(usage,'input_tokens',0) or 0),'output_tokens':int(getattr(usage,'output_tokens',0) or 0)}
        total['input_tokens']+=int(getattr(usage,'input_tokens',0) or 0)
        total['output_tokens']+=int(getattr(usage,'output_tokens',0) or 0)
        return total

    @staticmethod
    def _usage_obj(total):
        if total is None:
            return None
        class Usage: pass
        u=Usage(); u.input_tokens=total['input_tokens']; u.output_tokens=total['output_tokens']; return u

    @staticmethod
    def _normalize_candidate(candidate, service):
        out=dict(candidate)
        expected=[int(c['criterion_id']) for c in (service.get('criteria') or [])]
        present={int(c.get('criterion_id') or 0):c for c in (out.get('criteria') or [])}
        missing=[]
        normalized=[]
        for criterion in service.get('criteria') or []:
            cid=int(criterion['criterion_id'])
            if cid in present:
                normalized.append(present[cid])
            else:
                missing.append(cid)
                normalized.append({
                    'criterion_id':cid,'proposed_level':0,'confidence':0.0,
                    'rationale':"Critère non retourné par l'IA : contrôle humain requis.",
                    'evidence_indexes':[]
                })
        if missing:
            mp=list(out.get('missing_points') or [])
            mp.append("Certains critères n'ont pas été retournés par l'IA et ont été positionnés à 0 par sécurité : "+", ".join(str(x) for x in missing))
            out['missing_points']=mp
        out['criteria']=normalized
        out['service_id']=int(service['service_id'])
        return out

    def analyze(self, payload:dict):
        request_hash=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()
        clean_payload=dict(payload)
        images=clean_payload.pop('document_images',[]) or []
        services=list(clean_payload.pop('service_catalog',[]) or [])
        if not services:
            raise RuntimeError("Le catalogue des prestations est vide : l'analyse exhaustive ne peut pas être lancée.")

        facts_payload=dict(clean_payload)
        facts_content=[{'type':'input_text','text':json.dumps(facts_payload,ensure_ascii=False)}]
        for img in images:
            if img.get('data_url'):
                facts_content.append({'type':'input_image','image_url':img['data_url']})
                facts_content.append({'type':'input_text','text':f"Image document_id={img.get('document_id')} nom={img.get('name')} categorie={img.get('category')}"})
        facts,usage=self._call_schema(GLOBAL_INSTRUCTIONS_FACTS,facts_content,'dossier_professionnel_faits',DOSSIER_FACTS_SCHEMA,6000)
        usage_total=self._usage_add(None,usage)

        service_candidates=[]
        batch_size=5
        for start in range(0,len(services),batch_size):
            batch=services[start:start+batch_size]
            batch_payload={'dossier_facts':facts,'service_catalog':batch}
            batch_content=[{'type':'input_text','text':json.dumps(batch_payload,ensure_ascii=False)}]
            batch_result,busage=self._call_schema(GLOBAL_INSTRUCTIONS_SERVICES,batch_content,'dossier_prestations_lot',SERVICE_BATCH_SCHEMA,6500)
            usage_total=self._usage_add(usage_total,busage)
            returned={int(x.get('service_id') or 0):x for x in (batch_result.get('service_candidates') or [])}
            expected={int(x['service_id']) for x in batch}
            if set(returned)!=expected:
                missing=sorted(expected-set(returned)); extra=sorted(set(returned)-expected)
                raise RuntimeError(f"Analyse IA incomplète du catalogue (prestations manquantes={missing}, inattendues={extra}). Aucun résultat partiel n'a été enregistré.")
            for service in batch:
                service_candidates.append(self._normalize_candidate(returned[int(service['service_id'])],service))

        result=dict(facts)
        result['service_candidates']=service_candidates
        if len(service_candidates)!=len(services):
            raise RuntimeError("Analyse IA incomplète : toutes les prestations actives n'ont pas été étudiées.")
        return {
            'result':result,'request_hash':request_hash,'usage':self._usage_obj(usage_total),
            'model':self.model,'prompt_version':GLOBAL_PROMPT_VERSION,'provider':'openai'
        }
