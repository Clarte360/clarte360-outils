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


GLOBAL_PROMPT_VERSION = 'dossier_professionnel_global_v1_20260921'
GLOBAL_DOSSIER_SCHEMA = {
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
  'languages':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{'language':{'type':'string'},'level':{'type':['string','null']},'source_document_id':{'type':['integer','null']}},'required':['language','level','source_document_id']}},
  'identity_alerts':{'type':'array','items':{'type':'string'}},
  'missing_points':{'type':'array','items':{'type':'string'}},
  'service_candidates':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{
    'service_id':{'type':'integer'},'service_level':{'type':'integer','minimum':0,'maximum':4},'confidence':{'type':'number','minimum':0,'maximum':1},'rationale':{'type':'string'},'source_document_ids':{'type':'array','items':{'type':'integer'}},
    'missing_points':{'type':'array','items':{'type':'string'}},
    'evidence':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{
      'source':{'type':'string'},'fact':{'type':'string'},'supports_level':{'type':'integer','minimum':0,'maximum':4},'document_id':{'type':['integer','null']},'criterion_ids':{'type':'array','items':{'type':'integer'}},'identity_status':{'type':'string','enum':['COHERENT','A_VERIFIER','INCOHERENT']}
    },'required':['source','fact','supports_level','document_id','criterion_ids','identity_status']}},
    'criteria':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{
      'criterion_id':{'type':'integer'},'proposed_level':{'type':'integer','minimum':0,'maximum':4},'confidence':{'type':'number','minimum':0,'maximum':1},'rationale':{'type':'string'},'evidence_indexes':{'type':'array','items':{'type':'integer'}}
    },'required':['criterion_id','proposed_level','confidence','rationale','evidence_indexes']}}
  },'required':['service_id','service_level','confidence','rationale','source_document_ids','missing_points','evidence','criteria']}}
 },
 'required':['profile','experiences','education','certifications','languages','identity_alerts','missing_points','service_candidates']
}
GLOBAL_INSTRUCTIONS = """Tu assistes un administrateur Clarte360 pour analyser GLOBALLEMENT un dossier professionnel.
L'IA propose uniquement : l'humain reste decideur. Utilise exclusivement les faits fournis. N'invente rien.
Repere les incoherences d'identite entre la personne et les documents et place-les dans identity_alerts. Une piece avec une identite incoherente ne doit jamais etre consideree comme preuve valide.
L'analyse du catalogue est EXHAUSTIVE : chaque prestation active transmise doit recevoir un resultat, y compris lorsqu'aucun rapprochement n'est trouve. Une prestation sans element probant reste visible avec service_level=0, evidence=[], des criteres proposes a 0 et une justification explicite "Aucun rapprochement factuel dans le dossier".
Pour chaque prestation, evalue chaque critere fourni exactement une fois. Ne confonds jamais le niveau attendu du critere avec le niveau demontre par le dossier.
Pour chaque prestation, produis le niveau indicatif, la confiance, les criteres proposes, les preuves documentaires et les points a verifier afin qu'ils soient immediatement disponibles dans l'onglet Qualifications/Adequation, sans second declenchement IA par l'utilisateur.
Les pourcentages sont des indices de confiance dans l'analyse, jamais des notes, des certifications ou des validations.
Les dates inconnues restent nulles. Pour chaque element documentaire, conserve source_document_id lorsque la source est identifiable. Reponds en francais clair selon le schema JSON impose."""

GLOBAL_PROFILE_SCHEMA = {
    'type':'object','additionalProperties':False,
    'properties':{k:v for k,v in GLOBAL_DOSSIER_SCHEMA['properties'].items() if k!='service_candidates'},
    'required':[k for k in GLOBAL_DOSSIER_SCHEMA['required'] if k!='service_candidates']
}
GLOBAL_SERVICE_BATCH_SCHEMA = {
    'type':'object','additionalProperties':False,
    'properties':{'service_candidates':GLOBAL_DOSSIER_SCHEMA['properties']['service_candidates']},
    'required':['service_candidates']
}

GLOBAL_PROFILE_INSTRUCTIONS = """Analyse les documents et construis un dossier professionnel factuel aussi complet que possible.
N'evalue aucune prestation dans cette etape. Extrais profil, specialites, experiences, diplomes/formations, certifications/habilitations, langues, alertes d'identite et points factuels manquants.
Conserve source_document_id pour chaque element lorsque la source est identifiable. N'invente jamais une information absente."""

GLOBAL_SERVICE_INSTRUCTIONS = """Evalue EXHAUSTIVEMENT le sous-ensemble de prestations transmis a partir du dossier professionnel structure fourni.
Tu dois retourner exactement une entree service_candidates par service_id fourni, meme si aucun rapprochement n'existe.
Pour une prestation sans preuve : service_level=0, evidence=[], et une justification explicite. Chaque critere fourni doit apparaitre exactement une fois dans criteria, avec proposed_level=0 lorsqu'il n'est pas demontre.
L'IA propose uniquement ; l'humain decide. Utilise uniquement les faits fournis. Ne deduis pas une competence d'un simple intitule lorsqu'aucune experience, formation, certification ou autre preuve ne la soutient.
confidence exprime la confiance dans l'analyse, pas une note de la personne. Les preuves doivent reutiliser les document_id/source_document_id du dossier structure lorsqu'ils sont identifiables."""

class GlobalDossierAIGateway(QualificationAIGateway):
    def __init__(self, api_key:str, model:str, timeout:float=90.0, client=None, batch_size:int=5):
        super().__init__(api_key,model,timeout,client)
        try:self.batch_size=max(1,min(int(batch_size),8))
        except Exception:self.batch_size=5

    def _response_json(self, instructions:str, payload:dict, schema:dict, name:str, max_output_tokens:int=5000, images=None):
        client=self._client_obj()
        content=[{'type':'input_text','text':json.dumps(payload,ensure_ascii=False)}]
        for img in (images or []):
            if img.get('data_url'):
                content.append({'type':'input_image','image_url':img['data_url']})
                content.append({'type':'input_text','text':f"Image document_id={img.get('document_id')} nom={img.get('name')} categorie={img.get('category')}"})
        response=client.responses.create(
            model=self.model,instructions=instructions,input=[{'role':'user','content':content}],store=False,
            max_output_tokens=max_output_tokens,
            text={'format':{'type':'json_schema','name':name,'strict':True,'schema':schema}}
        )
        if getattr(response,'status',None) not in (None,'completed'):
            raise RuntimeError(f"Reponse IA incomplete : {getattr(response,'status',None)}")
        txt=getattr(response,'output_text','')
        if not txt: raise RuntimeError('Reponse IA vide.')
        return json.loads(txt),getattr(response,'usage',None)

    @staticmethod
    def _empty_service_result(service, reason):
        return {
            'service_id':int(service['service_id']),'service_level':0,'confidence':0.0,
            'rationale':reason,'source_document_ids':[],'missing_points':[reason],
            'evidence':[],
            'criteria':[{
                'criterion_id':int(c['criterion_id']),'proposed_level':0,'confidence':0.0,
                'rationale':'Aucun element factuel exploitable ne permet de demontrer ce critere lors de ce passage.',
                'evidence_indexes':[]
            } for c in (service.get('criteria') or [])]
        }

    @staticmethod
    def _normalize_service_result(service, result):
        out=dict(result or {})
        out['service_id']=int(service['service_id'])
        out['service_level']=max(0,min(4,int(out.get('service_level') or 0)))
        try:out['confidence']=max(0.0,min(1.0,float(out.get('confidence') or 0)))
        except Exception:out['confidence']=0.0
        out['rationale']=out.get('rationale') or ('Aucun rapprochement factuel dans le dossier.' if out['service_level']==0 else 'Proposition issue de l analyse globale.')
        out['source_document_ids']=[int(x) for x in (out.get('source_document_ids') or []) if str(x).isdigit()]
        out['missing_points']=list(out.get('missing_points') or [])
        out['evidence']=list(out.get('evidence') or [])
        by_criterion={}
        for cp in (out.get('criteria') or []):
            try:cid=int(cp.get('criterion_id'))
            except Exception:continue
            by_criterion[cid]=cp
        criteria=[]
        for c in (service.get('criteria') or []):
            cid=int(c['criterion_id']); cp=dict(by_criterion.get(cid) or {})
            cp['criterion_id']=cid
            cp['proposed_level']=max(0,min(4,int(cp.get('proposed_level') or 0)))
            try:cp['confidence']=max(0.0,min(1.0,float(cp.get('confidence') or 0)))
            except Exception:cp['confidence']=0.0
            cp['rationale']=cp.get('rationale') or ('Aucun element factuel ne demontre ce critere.' if cp['proposed_level']==0 else 'Proposition IA a verifier.')
            cp['evidence_indexes']=[int(x) for x in (cp.get('evidence_indexes') or []) if str(x).isdigit()]
            criteria.append(cp)
        out['criteria']=criteria
        return out

    def analyze(self, payload:dict):
        request_hash=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()
        clean=dict(payload)
        images=clean.pop('document_images',[]) or []
        catalog=list(clean.pop('service_catalog',[]) or [])

        profile_payload={k:v for k,v in clean.items() if k!='service_catalog'}
        profile_result,profile_usage=self._response_json(
            GLOBAL_PROFILE_INSTRUCTIONS,profile_payload,GLOBAL_PROFILE_SCHEMA,
            'dossier_professionnel_global_profil',5000,images
        )

        results={}
        service_usage=[]
        for pos in range(0,len(catalog),self.batch_size):
            batch=catalog[pos:pos+self.batch_size]
            batch_payload={
                'person':clean.get('person') or {},
                'dossier_professionnel_extrait':profile_result,
                'service_catalog':batch
            }
            batch_result,usage=self._response_json(
                GLOBAL_SERVICE_INSTRUCTIONS,batch_payload,GLOBAL_SERVICE_BATCH_SCHEMA,
                'dossier_professionnel_services_batch',4500,None
            )
            service_usage.append(usage)
            allowed={int(s['service_id']):s for s in batch}
            for sc in (batch_result.get('service_candidates') or []):
                try:sid=int(sc.get('service_id'))
                except Exception:continue
                if sid in allowed and sid not in results:
                    results[sid]=self._normalize_service_result(allowed[sid],sc)

        ordered=[]
        for service in catalog:
            sid=int(service['service_id'])
            if sid in results:
                ordered.append(results[sid])
            else:
                ordered.append(self._empty_service_result(service,'Analyse IA incomplète pour cette prestation : aucun résultat n’a été retourné par le modèle. Une vérification humaine est nécessaire.'))

        final=dict(profile_result)
        final['service_candidates']=ordered
        class Usage:
            input_tokens=sum(int(getattr(x,'input_tokens',0) or 0) for x in [profile_usage,*service_usage] if x is not None)
            output_tokens=sum(int(getattr(x,'output_tokens',0) or 0) for x in [profile_usage,*service_usage] if x is not None)
        return {
            'result':final,'request_hash':request_hash,'usage':Usage(),
            'model':self.model,'prompt_version':GLOBAL_PROMPT_VERSION,'provider':'openai',
            'batch_count':(len(catalog)+self.batch_size-1)//self.batch_size
        }

