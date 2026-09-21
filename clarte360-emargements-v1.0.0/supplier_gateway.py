"""J10 - passerelle Fournisseur (Gestion Clients reste maitre de l'entite economique)."""
from __future__ import annotations
import json, time, uuid, hmac, hashlib
from urllib import request as urlrequest

class GestionClientsSupplierGateway:
    def __init__(self, base_url='', secret='', transport=None, timeout=8):
        self.base_url=(base_url or '').rstrip('/'); self.secret=secret or ''; self.transport=transport; self.timeout=timeout
    def _headers(self, method, path, body):
        if not self.secret: return {'Content-Type':'application/json'}
        ts=str(int(time.time())); nonce=uuid.uuid4().hex
        # Convention API Gestion Clients : timestamp + nonce + methode + path + corps.
        canonical='\n'.join([ts,nonce,method.upper(),path]).encode()+b'\n'+body
        sig=hmac.new(self.secret.encode(),canonical,hashlib.sha256).hexdigest()
        return {'Content-Type':'application/json','X-Clarte360-Timestamp':ts,'X-Clarte360-Nonce':nonce,'X-Clarte360-Signature':sig}
    def _call(self, method, path, payload=None):
        body=json.dumps(payload or {},ensure_ascii=False,separators=(',',':')).encode() if payload is not None else b''
        headers=self._headers(method,path,body)
        if self.transport: return self.transport(method,path,payload,headers)
        if not self.base_url: raise RuntimeError('URL Gestion Clients non configurée.')
        req=urlrequest.Request(self.base_url+path,data=body if payload is not None else None,headers=headers,method=method)
        with urlrequest.urlopen(req,timeout=self.timeout) as r: return json.loads(r.read().decode())
    def get_supplier(self, supplier_id): return self._call('GET',f'/api/v1/suppliers/{supplier_id}/360')
    def link_professional(self,supplier_id,professional_person_id,relationship_type='PROFESSIONAL',valid_from=None,valid_to=None,actor_id=None):
        return self._call('POST',f'/api/v1/suppliers/{supplier_id}/professional-links',{'professional_person_id':professional_person_id,'relationship_type':relationship_type,'valid_from':valid_from,'valid_to':valid_to,'source_system':'GESTION_INTERVENANTS','actor_id':actor_id})
