"""J1 / P5-RC2: controlled, auditable purge of explicitly certified *fictional* actions.

No automatic inference from action number/title. Never run against live production
without a separate release authorization. Physical files are quarantined until the
SQL transaction commits, with a journal that can recover after a process crash.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path

from sqlalchemy import inspect, text
from db import utcnow_iso

ROOT = Path(__file__).resolve().parent
DATA_ROOT = ROOT / 'data'

PURGE_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS action_purge_certifications (
      action_id INTEGER PRIMARY KEY, action_no TEXT NOT NULL, actor TEXT NOT NULL,
      evidence TEXT NOT NULL, certified_at TEXT NOT NULL, snapshot_fingerprint TEXT NOT NULL DEFAULT '',
      FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE)""",
    """CREATE TABLE IF NOT EXISTS action_purge_journal (
      id TEXT PRIMARY KEY, action_id INTEGER NOT NULL, action_no TEXT NOT NULL,
      actor TEXT NOT NULL, status TEXT NOT NULL, manifest_json TEXT NOT NULL,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT)""",
)


def ensure_purge_schema(engine):
    with engine.begin() as conn:
        for statement in PURGE_SCHEMA:
            conn.execute(text(statement))


def _fetch(conn, sql, params=None):
    return [dict(r._mapping) for r in conn.execute(text(sql), params or {}).fetchall()]


def _one(conn, sql, params=None):
    found = _fetch(conn, sql, params)
    return found[0] if found else None


def _ids(conn, table, predicate='action_id=:aid', args=None):
    return [int(row['id']) for row in _fetch(conn, f'SELECT id FROM {table} WHERE {predicate}', args or {})]


def _sql_in(column, values, params, prefix):
    if not values:
        return '1=0'
    keys=[]
    for i, value in enumerate(values):
        key=f'{prefix}_{i}'
        params[key]=value
        keys.append(':'+key)
    return f"{column} IN ({','.join(keys)})"


def _path_in_root(raw, root):
    """Reject symlinks and any path outside the configured data directory."""
    if not raw or not str(raw).strip():
        return None
    path=Path(str(raw))
    if not path.is_absolute():
        # Historical relative paths are anchored in the application root.
        path=ROOT/path
    real=path.resolve(strict=False)
    data_root=Path(root).resolve()
    if not real.is_relative_to(data_root):
        raise ValueError('Chemin de fichier hors repertoire de donnees autorise.')
    if path.is_symlink():
        raise ValueError('Lien symbolique interdit dans une purge.')
    if path.exists() and not path.is_file():
        raise ValueError('Un document pointe vers un dossier, purge interrompue.')
    return real


def _related_snapshot(conn, action_id, data_root):
    action=_one(conn, 'SELECT * FROM actions WHERE id=:aid', {'aid':action_id})
    if action is None:
        return None
    tables=inspect(conn).get_table_names()
    columns={t: {c['name'] for c in inspect(conn).get_columns(t)} for t in tables}
    ids={}
    for name in tables:
        if name in ('actions','action_purge_journal','action_purge_certifications'):
            continue
        if 'action_id' in columns[name] and 'id' in columns[name]:
            ids[name]=_ids(conn,name,args={'aid':action_id})
    participants=ids.get('participants',[])
    slots=ids.get('slots',[])
    campaigns=ids.get('quality_campaigns',[])

    predicates={}
    if 'quality_issues' in tables:
        params={'aid':action_id}
        wh=_sql_in('campaign_id', campaigns, params, 'ci')
        ids['quality_issues']=_ids(conn,'quality_issues',f'action_id=:aid OR {wh}',params)
    issues=ids.get('quality_issues',[])
    if issues:
        p={};w=_sql_in('id',issues,p,'iown')
        other=_fetch(conn,f'SELECT id,action_id FROM quality_issues WHERE {w} AND action_id IS NOT NULL AND action_id<>:aid',{**p,'aid':action_id})
        if other:
            raise ValueError('Fiche Qualite liee a une autre action : suppression refusee.')
        p={};included=_sql_in('campaign_id',campaigns,p,'campaign_owner_issue')
        selected=_sql_in('id',issues,p,'issue_selected')
        other=_fetch(conn,f'SELECT id,campaign_id FROM quality_issues WHERE {selected} AND campaign_id IS NOT NULL AND NOT ({included})',p)
        if other:
            raise ValueError('Fiche Qualite associant une campagne exterieure : suppression refusee.')
    if 'improvement_actions' in tables:
        params={'aid':action_id}
        wh=_sql_in('issue_id', issues, params, 'qi')
        ids['improvement_actions']=_ids(conn,'improvement_actions',f'action_id=:aid OR {wh}',params)
    if 'quality_events' in tables:
        params={'aid':action_id}
        wh=_sql_in('campaign_id',campaigns,params,'ce')
        ids['quality_events']=_ids(conn,'quality_events',f'action_id=:aid OR {wh}',params)
    events=ids.get('quality_events',[])
    if events:
        p={};w=_sql_in('id',events,p,'eown')
        other=_fetch(conn,f'SELECT id,action_id FROM quality_events WHERE {w} AND action_id IS NOT NULL AND action_id<>:aid',{**p,'aid':action_id})
        if other:
            raise ValueError('Evenement Qualite lie a une autre action : suppression refusee.')
        p={};incl=_sql_in('campaign_id',campaigns,p,'campaign_owner_evt')
        selected=_sql_in('id',events,p,'event_selected')
        other=_fetch(conn,f'SELECT id,campaign_id FROM quality_events WHERE {selected} AND campaign_id IS NOT NULL AND NOT ({incl})',p)
        if other:
            raise ValueError('Evenement Qualite lie a une campagne exterieure : suppression refusee.')
    if 'quality_event_actions' in tables:
        p={}; wh=_sql_in('quality_event_id',events,p,'eac')
        ids['quality_event_actions']=_ids(conn,'quality_event_actions',wh,p)
    if 'quality_event_messages' in tables:
        p={}; wh=_sql_in('quality_event_id',events,p,'em')
        ids['quality_event_messages']=_ids(conn,'quality_event_messages',wh,p)
    # J2: include all new Quality link and revision rows in the pre-purge inventory.
    for child,parent,parents,prefix in (
        ('quality_source_links','quality_event_id',events,'source'),
        ('quality_event_history','quality_event_id',events,'history'),
        ('quality_capa_source_links','quality_event_action_id',ids.get('quality_event_actions',[]),'capa_source')):
        if child in tables:
            p={}; clause=_sql_in(parent,parents,p,prefix)
            ids[child]=_ids(conn,child,clause,p)
    # A source attached to a retained action must never be removed with a fictitious one.
    if ids.get('quality_source_links'):
        p={};clause=_sql_in('id',ids['quality_source_links'],p,'selected_quality_link')
        links=_fetch(conn,f'SELECT source_kind,source_id FROM quality_source_links WHERE {clause}',p)
        source_tables={'TRAINER_REPORT':'trainer_reports','BENEFICIARY_REPORT':'beneficiary_reports','QUALITY_ISSUE':'quality_issues'}
        for link in links:
            table=source_tables.get(link['source_kind'])
            if table in tables:
                row=_one(conn,f'SELECT action_id FROM {table} WHERE id=:i',{'i':link['source_id']})
                if row and row.get('action_id') is not None and row['action_id']!=action_id:
                    raise ValueError('Source Qualite partagee avec une autre action : purge refusee.')
    if 'quality_responses' in tables:
        p={}; wh=_sql_in('campaign_id',campaigns,p,'cr')
        ids['quality_responses']=_ids(conn,'quality_responses',wh,p)
    if 'document_references' in tables:
        p={'aid':action_id}
        wh=_sql_in('participant_id', participants, p, 'drp')
        ids['document_references']=_ids(conn,'document_references',f'action_id=:aid OR {wh}',p)
        if ids['document_references']:
            p={};w=_sql_in('id',ids['document_references'],p,'docown')
            other=_fetch(conn,f'SELECT id,action_id FROM document_references WHERE {w} AND action_id IS NOT NULL AND action_id<>:aid',{**p,'aid':action_id})
            if other:
                raise ValueError('Document rattache a une autre action : suppression refusee.')
    ref_ids=ids.get('document_references',[])
    if 'document_notifications' in tables:
        p={'aid':action_id};wh=_sql_in('document_reference_id',ref_ids,p,'dn')
        ids['document_notifications']=_ids(conn,'document_notifications',f'action_id=:aid OR {wh}',p)
    if 'quality_review_points' in tables:
        p={'aid':action_id};wh=_sql_in('campaign_id',campaigns,p,'qr')
        we=_sql_in('quality_event_id',events,p,'evrp')
        ids['quality_review_points']=_ids(conn,'quality_review_points',f'action_id=:aid OR {wh} OR {we}',p)
        if ids['quality_review_points']:
            p={};w=_sql_in('id',ids['quality_review_points'],p,'rvown')
            other=_fetch(conn,f'SELECT id,action_id,campaign_id FROM quality_review_points WHERE {w} AND action_id IS NOT NULL AND action_id<>:aid',{**p,'aid':action_id})
            if other:
                raise ValueError('Point de revue Qualite partage avec une autre action.')
            p={};wh=_sql_in('id',ids['quality_review_points'],p,'review_selected')
            in_campaign=_sql_in('campaign_id',campaigns,p,'review_campaign')
            other=_fetch(conn,f'SELECT id,campaign_id FROM quality_review_points WHERE {wh} AND campaign_id IS NOT NULL AND NOT ({in_campaign})',p)
            if other:
                raise ValueError('Revue Qualite liee a une campagne exterieure.')
    if 'audit_log' in tables:
        ids['audit_log']=[int(x['id']) for x in _fetch(conn,'''SELECT id FROM audit_log WHERE action_id=:a
          OR (entity_type='action' AND entity_id=:s)''',{'a':action_id,'s':str(action_id)})]

    # A cross-action quality link must never be silently broken.
    if events and 'quality_review_points' in tables:
        p={};wh=_sql_in('quality_event_id',events,p,'eq')
        outsiders=_fetch(conn,f'''SELECT id,action_id FROM quality_review_points
          WHERE {wh} AND action_id IS NOT NULL AND action_id<>:aid''',{**p,'aid':action_id})
        if outsiders:
            raise ValueError('Evenement Qualite partage avec une autre action : analyse manuelle obligatoire.')
    if issues and 'improvement_actions' in tables:
        p={};wh=_sql_in('issue_id',issues,p,'iox')
        outsiders=_fetch(conn,f'''SELECT id,action_id FROM improvement_actions
          WHERE {wh} AND action_id IS NOT NULL AND action_id<>:aid''',{**p,'aid':action_id})
        if outsiders:
            raise ValueError('Action corrective liee a un autre dossier : analyse manuelle obligatoire.')

    # A content-addressed blob is only deleted if no other reference needs it.
    referenced_files=[]
    if ref_ids and 'stored_files' in tables:
        p={};wh=_sql_in('dr.id',ref_ids,p,'refer')
        referenced_files=_fetch(conn,f'''SELECT DISTINCT sf.id,sf.storage_path,sf.sha256
            FROM document_references dr JOIN stored_files sf ON sf.id=dr.stored_file_id
            WHERE {wh}''',p)
    shared_blobs=[];orphan_blobs=[]
    for file in referenced_files:
        p={'sid':file['id']};wh=_sql_in('id',ref_ids,p,'xref')
        outside=_one(conn,f'''SELECT COUNT(*) n FROM document_references
          WHERE stored_file_id=:sid AND NOT ({wh})''',p)['n']
        prof_docs=_one(conn,'SELECT COUNT(*) n FROM professional_documents WHERE stored_file_id=:sid',{'sid':file['id']})['n'] if 'professional_documents' in tables else 0
        prof_photos=_one(conn,'SELECT COUNT(*) n FROM professional_profiles WHERE photo_stored_file_id=:sid',{'sid':file['id']})['n'] if 'professional_profiles' in tables else 0
        if outside or prof_docs or prof_photos:
            shared_blobs.append(int(file['id']))
        else:
            orphan_blobs.append(file)

    file_entries=[]
    for file in orphan_blobs:
        file_entries.append(('stored_files',int(file['id']),file['storage_path']))
    if participants and 'signatures' in tables:
        p={};wh=_sql_in('p.id',participants,p,'ps')
        file_entries.extend(('signatures',row['id'],row['signature_path']) for row in _fetch(conn,f'''SELECT s.id,s.signature_path FROM signatures s
          JOIN participants p ON p.id=s.participant_id WHERE {wh}''',p))
    if slots:
        p={};wh=_sql_in('slot_id',slots,p,'tc')
        for name in ('trainer_countersignatures','trainer_countersignatures_v3'):
            if name in tables:
                file_entries.extend((name,row['id'],row['signature_path']) for row in _fetch(conn,f'SELECT id,signature_path FROM {name} WHERE {wh}',p))
    for table in ('trainer_reports','beneficiary_reports'):
        if table in tables:
            file_entries.extend((table,row['id'],row['attachment_path']) for row in _fetch(conn,f'SELECT id,attachment_path FROM {table} WHERE action_id=:aid',{'aid':action_id}))
    if action.get('final_bundle_path'):
        file_entries.append(('actions',int(action_id),action['final_bundle_path']))

    files_by_path={}
    for source,row_id,raw in file_entries:
        path=_path_in_root(raw,data_root)
        if path is None:
            continue
        key=str(path)
        if key not in files_by_path:
            exists=path.exists()
            files_by_path[key]={
                'path':key,'exists':exists,'bytes':path.stat().st_size if exists else 0,
                'sha256':_file_hash(path) if exists else None,'references':[],
            }
        files_by_path[key]['references'].append(f'{source}:{row_id}')

    # A physical path may also be reused through another action's signature,
    # report or generated final bundle. Keep neighboring files untouched.
    selected_source_refs={(source,int(row_id)) for source,row_id,_ in file_entries}
    path_columns=(('stored_files','storage_path'),('signatures','signature_path'),
       ('trainer_countersignatures','signature_path'),('trainer_countersignatures_v3','signature_path'),
       ('trainer_reports','attachment_path'),('beneficiary_reports','attachment_path'))
    for table,column in path_columns:
        if table not in tables or not files_by_path:
            continue
        for row in _fetch(conn,f"SELECT id,{column} AS path FROM {table} WHERE {column} IS NOT NULL AND {column} <> ''"):
            raw=str(row['path'])
            path=Path(raw)
            real=(path if path.is_absolute() else ROOT/path).resolve(strict=False)
            if str(real) in files_by_path and (table,int(row['id'])) not in selected_source_refs:
                raise ValueError('Fichier partage avec une autre piece ou action : purge refusee.')
    if 'actions' in tables:
        for row in _fetch(conn,'SELECT id,final_bundle_path AS path FROM actions WHERE id<>:a AND final_bundle_path IS NOT NULL',{'a':action_id}):
            raw=Path(str(row['path']))
            real=(raw if raw.is_absolute() else ROOT/raw).resolve(strict=False)
            if str(real) in files_by_path:
                raise ValueError('Dossier final reutilise par une autre action : purge refusee.')

    # Never move a blob whose physical path is reused by a retained row.
    for path in files_by_path:
        if 'stored_files' in tables:
            p={'p':path};wh=_sql_in('id',[int(x['id']) for x in orphan_blobs],p,'sf')
            retained=_one(conn,f'SELECT COUNT(*) n FROM stored_files WHERE storage_path=:p AND NOT ({wh})',p)['n']
            if retained:
                raise ValueError('Chemin de document partage avec un fichier conserve : suppression refusee.')

    counts={t:len(rows) for t,rows in ids.items() if rows}
    counts['stored_files_to_remove']=len(orphan_blobs)
    counts['stored_files_shared_to_keep']=len(shared_blobs)
    files=sorted(files_by_path.values(),key=lambda row:row['path'])
    snapshot={'action_id':action_id,'action_no':action['action_no'],'status':action.get('status'),
              'source':action.get('source'),'title':action.get('title'),
              'updated_at':action.get('updated_at'),'created_at':action['created_at'],
              'counts':counts,'ids':{key:sorted(value) for key,value in ids.items() if value},
              'orphan_file_ids':sorted(int(x['id']) for x in orphan_blobs),
              'shared_file_ids':sorted(shared_blobs),'files':files}
    # Detect changed statuses/notes even when a dependent row's primary key is unchanged.
    row_hash=hashlib.sha256()
    for table in sorted(ids):
        if not ids[table]:
            continue
        params={}; wh=_sql_in('id',sorted(set(ids[table])),params,'snapshot')
        rows=_fetch(conn,f'SELECT * FROM {table} WHERE {wh} ORDER BY id',params)
        row_hash.update(json.dumps([table,rows],sort_keys=True,default=str,ensure_ascii=False).encode('utf-8'))
    # J8 rows use string PKs: the generic id-based inventory above cannot see them.
    # All J8 tables are FK-cascaded, but include contents in the preflight digest so
    # an intervening mission/document change invalidates the purge certification.
    j8_counts={}
    for table in ('action_mission_policy','action_mission_engagements','action_mission_events','action_mission_outbox'):
        if table not in tables:continue
        rows=_fetch(conn,f'SELECT * FROM {table} WHERE action_id=:aid ORDER BY rowid',{'aid':action_id})
        j8_counts[table]=len(rows)
        row_hash.update(json.dumps([table,rows],sort_keys=True,default=str,ensure_ascii=False).encode('utf-8'))
    snapshot['j8_counts']=j8_counts
    counts.update({name:count for name,count in j8_counts.items() if count})
    snapshot['dependent_row_sha256']=row_hash.hexdigest()
    digest=hashlib.sha256(json.dumps(snapshot,ensure_ascii=False,sort_keys=True,default=str).encode('utf-8')).hexdigest()
    return {'action':action,'ids':ids,'files':files,'orphan_file_ids':snapshot['orphan_file_ids'],
            'shared_file_ids':snapshot['shared_file_ids'],'counts':counts,'fingerprint':digest}


def _file_hash(path):
    d=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            d.update(block)
    return d.hexdigest()


def preview_action_purge(engine,action_id,*,data_root=None):
    """Read-only inventory; never marks a file or SQL record for deletion."""
    with engine.connect() as conn:
        snap=_related_snapshot(conn,int(action_id),data_root or DATA_ROOT)
        if snap is None:
            return None
        return {'action_id':int(action_id),'action_no':snap['action']['action_no'],
                'title':snap['action']['title'],'status':snap['action'].get('status'),
                'source':snap['action'].get('source'),'prestation_type':snap['action'].get('prestation_type'),
                'counts':snap['counts'],'files':snap['files'],
                'shared_files_kept':len(snap['shared_file_ids']),
                'fingerprint':snap['fingerprint']}


def certify_test_action(engine,action_id,actor,*,evidence,confirmation,password,data_root=None):
    """Must be performed by a *real authenticated administrator*; fail closed."""
    from security import verify_password
    actor=str(actor or '').strip().lower()
    evidence=str(evidence or '').strip()
    ensure_purge_schema(engine)
    with engine.begin() as conn:
        admin=_one(conn,'SELECT password_hash FROM admins WHERE LOWER(email)=:a AND active=1',{'a':actor})
        if not admin or not verify_password(password or '',admin['password_hash']):
            return False,'Identite administrateur non validee.'
        row=_one(conn,'SELECT * FROM actions WHERE id=:a',{'a':int(action_id)})
        if not row:
            return False,'Action introuvable.'
        if confirmation != f"JE CERTIFIE ESSAI {row['action_no']}":
            return False,'Attestation ecrite incorrecte.'
        if len(evidence)<24:
            return False,'Justifier precisement pourquoi aucune donnee reelle ni obligation de conservation ne concerne cette action.'
        conn.execute(text('''INSERT INTO action_purge_certifications(action_id,action_no,actor,evidence,certified_at)
          VALUES(:a,:n,:actor,:ev,:now)
          ON CONFLICT(action_id) DO UPDATE SET actor=excluded.actor,evidence=excluded.evidence,
             certified_at=excluded.certified_at,action_no=excluded.action_no'''),
          {'a':action_id,'n':row['action_no'],'actor':actor,'ev':evidence,'now':utcnow_iso()})
        conn.execute(text('''INSERT INTO audit_log(action_id,actor,event_type,entity_type,entity_id,details_json,created_at)
          VALUES(:a,:actor,'ACTION_TEST_CERTIFIED','action',:id,:details,:now)'''),
          {'a':action_id,'actor':actor,'id':str(action_id),
           'details':json.dumps({'attestation':True},ensure_ascii=False),'now':utcnow_iso()})
        snapshot=_related_snapshot(conn,int(action_id),data_root or DATA_ROOT)
        conn.execute(text('UPDATE action_purge_certifications SET snapshot_fingerprint=:hash WHERE action_id=:aid'),
                     {'hash':snapshot['fingerprint'],'aid':action_id})
        return True,'Qualification explicite comme dossier fictif enregistree.'


def _update_journal(engine,operation_id,status,error=None):
    with engine.begin() as conn:
        conn.execute(text('UPDATE action_purge_journal SET status=:s,error=:err,updated_at=:n WHERE id=:id'),
                     {'s':status,'err':(str(error)[:1000] if error else None),'n':utcnow_iso(),'id':operation_id})


def _manifest_paths(row,data_root):
    manifest=json.loads(row['manifest_json'])
    root=Path(data_root).resolve()
    qdir=root/'purge_quarantine'/row['id']
    result=[]
    for i,x in enumerate(manifest['files']):
        src=_path_in_root(x['path'],root)
        dst=qdir/(f'{i:04d}_'+hashlib.sha256(str(src).encode()).hexdigest()[:16])
        result.append((src,dst,x))
    return result


def _restore_staged(entries):
    errors=[]
    for src,dst,_ in reversed(entries):
        if dst.exists():
            if src.exists():
                errors.append('Original et quarantaine coexistent : '+src.name)
                continue
            try:
                src.parent.mkdir(parents=True,exist_ok=True)
                os.replace(dst,src)
            except Exception as exc:
                errors.append(src.name+': '+str(exc))
    return errors


def recover_action_purges(engine,*,data_root=None):
    """Idempotent recovery after interruption, limited to one local data root."""
    root=data_root or DATA_ROOT
    ensure_purge_schema(engine)
    with engine.connect() as conn:
        rows=_fetch(conn,"SELECT * FROM action_purge_journal WHERE status IN ('PREPARED','RECOVERY_REQUIRED','COMMITTED','CLEANUP_REQUIRED') ORDER BY created_at")
    results=[]
    for row in rows:
        try:
            entries=_manifest_paths(row,root)
            if row['status'] in ('PREPARED','RECOVERY_REQUIRED'):
                with engine.connect() as c:
                    still_exists=_one(c,'SELECT id FROM actions WHERE id=:aid',{'aid':row['action_id']}) is not None
                if not still_exists:
                    # If the SQL commit made it, the journal must be COMMITTED too.
                    raise RuntimeError('Etat SQL et journal incoherents ; reprise manuelle.')
                errors=_restore_staged(entries)
                if errors:
                    raise RuntimeError('; '.join(errors))
                _update_journal(engine,row['id'],'ROLLED_BACK')
                results.append({'operation':row['id'],'status':'ROLLED_BACK'})
            else:
                with engine.connect() as c:
                    still_exists=_one(c,'SELECT id FROM actions WHERE id=:aid',{'aid':row['action_id']}) is not None
                if still_exists:
                    raise RuntimeError('Action encore presente malgre COMMITTED ; controle manuel.')
                for _,dest,_ in entries:
                    if dest.exists():
                        dest.unlink()
                _update_journal(engine,row['id'],'COMPLETE')
                results.append({'operation':row['id'],'status':'COMPLETE'})
        except Exception as exc:
            _update_journal(engine,row['id'],'RECOVERY_REQUIRED' if row['status'] in ('PREPARED','RECOVERY_REQUIRED') else 'CLEANUP_REQUIRED',exc)
            results.append({'operation':row['id'],'status':'ERROR','error':str(exc)})
    return results


def purge_certified_action(engine,action_id,actor,*,confirmation,preview_fingerprint,data_root=None):
    """Purge only after separate authenticated test certification + fresh fingerprint.

    Returns (success, message). File quarantine and SQL journal allow crash recovery.
    """
    root=Path(data_root or DATA_ROOT).resolve()
    ensure_purge_schema(engine)
    operation_id=uuid.uuid4().hex
    with engine.connect() as conn:
        action=_one(conn,'SELECT * FROM actions WHERE id=:a',{'a':int(action_id)})
        if not action:
            return False,'Action introuvable.'
        if confirmation != f"SUPPRIMER ESSAI {action['action_no']}":
            return False,'Confirmation de suppression non conforme.'
        pending=_one(conn,"SELECT id FROM action_purge_journal WHERE action_id=:a AND status IN ('PREPARED','COMMITTED','RECOVERY_REQUIRED','CLEANUP_REQUIRED')",{'a':action_id})
        if pending:
            return False,'Ancienne purge a reprendre avant une nouvelle tentative.'
        certification=_one(conn,'SELECT * FROM action_purge_certifications WHERE action_id=:a',{'a':action_id})
        if not certification:
            return False,'Suppression refusee : aucun certificat de dossier fictif.'
        if str(certification['action_no'])!=str(action['action_no']):
            return False,'Action modifiee depuis son attestation : recommencer.'
        if not actor or str(certification['actor']).lower()!=str(actor).strip().lower():
            return False,'Administrateur different du certificateur : renouveler attestation.'
        snap=_related_snapshot(conn,int(action_id),root)
        if snap['fingerprint']!=preview_fingerprint:
            return False,'Le dossier a change : actualiser la previsualisation avant suppression.'
        if certification['snapshot_fingerprint']!=snap['fingerprint']:
            return False,'Le dossier a change depuis son attestation : renouveler la certification.'
        manifest={'files':snap['files'],'fingerprint':snap['fingerprint']}
    # Durable journal before the first external filesystem move.
    try:
        with engine.begin() as conn:
            conn.execute(text('''INSERT INTO action_purge_journal(id,action_id,action_no,actor,status,manifest_json,created_at,updated_at)
              VALUES(:id,:a,:n,:actor,'PREPARED',:m,:now,:now)'''),
              {'id':operation_id,'a':action_id,'n':action['action_no'],'actor':actor,
               'm':json.dumps(manifest,ensure_ascii=False),'now':utcnow_iso()})
    except Exception as exc:
        return False,'Journal de purge indisponible : '+str(exc)[:220]
    record={'id':operation_id,'manifest_json':json.dumps(manifest)}
    entries=_manifest_paths(record,root)
    try:
        with engine.connect() as conn:
            # SQLite write lock spans the staging and all deletions: concurrent writers blocked.
            conn.exec_driver_sql('PRAGMA foreign_keys=ON')
            checked=conn.exec_driver_sql('PRAGMA foreign_keys').scalar()
            if checked!=1:
                raise RuntimeError('SQLite foreign_keys n est pas actif : purge bloquee.')
            conn.exec_driver_sql('BEGIN IMMEDIATE')
            try:
                if _one(conn,'SELECT id FROM actions WHERE id=:a',{'a':action_id}) is None:
                    raise RuntimeError('Action deja supprimee.')
                cert=_one(conn,'SELECT actor,action_no FROM action_purge_certifications WHERE action_id=:a',{'a':action_id})
                if not cert or cert['actor'].lower()!=str(actor).strip().lower():
                    raise RuntimeError('Attestation revoquee ou differente.')
                current=_related_snapshot(conn,int(action_id),root)
                if current['fingerprint']!=manifest['fingerprint']:
                    raise RuntimeError('Dossier modifie pendant la preparation ; recommencer.')
                certified=_one(conn,'SELECT snapshot_fingerprint FROM action_purge_certifications WHERE action_id=:a',{'a':action_id})
                if not certified or certified['snapshot_fingerprint']!=current['fingerprint']:
                    raise RuntimeError('Attestation perimee pendant preparation ; recommencer.')
                for src,dst,detail in entries:
                    if not detail['exists']:
                        if src.exists():
                            raise RuntimeError('Fichier apparu apres apercu : '+src.name)
                        continue
                    if not src.is_file() or _file_hash(src)!=detail['sha256']:
                        raise RuntimeError('Fichier modifie apres apercu : '+src.name)
                    dst.parent.mkdir(parents=True,exist_ok=True)
                    os.replace(src,dst)
                # Delete SET NULL objects explicitly *before* cascading action deletion.
                for t in ('quality_review_points','quality_event_history','quality_source_links',
                          'quality_capa_source_links','quality_event_messages','quality_event_actions',
                          'quality_events','improvement_actions','quality_issues','document_notifications','audit_log'):
                    values=current['ids'].get(t,[])
                    if values:
                        params={}; clause=_sql_in('id',values,params,t)
                        conn.execute(text(f'DELETE FROM {t} WHERE {clause}'),params)
                conn.execute(text('DELETE FROM actions WHERE id=:a'),{'a':action_id})
                for sid in current['orphan_file_ids']:
                    conn.execute(text('DELETE FROM stored_files WHERE id=:i'),{'i':sid})
                # Invariant: the target action must not leave dangling quality records or
                # non-FK document notifications, and no FK violation may be introduced.
                for t in ('quality_events','quality_issues','improvement_actions','document_notifications'):
                    if _one(conn,f'SELECT COUNT(*) n FROM {t} WHERE action_id=:a',{'a':action_id})['n']:
                        raise RuntimeError('Dependance residuelle : '+t)
                if _fetch(conn,'PRAGMA foreign_key_check'):
                    raise RuntimeError('Integrite des cles etrangeres invalide.')
                conn.execute(text('''INSERT INTO audit_log(action_id,actor,event_type,entity_type,entity_id,details_json,created_at)
                  VALUES(NULL,:actor,'ACTION_TEST_PURGED','action',:id,:d,:now)'''),
                  {'actor':actor,'id':str(action_id),'now':utcnow_iso(),
                   'd':json.dumps({'action_no':action['action_no'],'purge_operation':operation_id,'fictional':True})})
                conn.execute(text("UPDATE action_purge_journal SET status='COMMITTED',updated_at=:n WHERE id=:id"),
                             {'n':utcnow_iso(),'id':operation_id})
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    except Exception as exc:
        problems=_restore_staged(entries)
        _update_journal(engine,operation_id,'RECOVERY_REQUIRED' if problems else 'ROLLED_BACK',
                        f'{str(exc)}'+('; restauration incomplete : '+'; '.join(problems) if problems else ''))
        return False,'Suppression non validee : '+str(exc)[:290]+(' ; restauration a verifier.' if problems else ' ; restauration effectuee.')

    cleanup_errors=[]
    for src,dst,_ in entries:
        if dst.is_file():
            try: dst.unlink()
            except Exception as exc: cleanup_errors.append(f'{src.name}: {exc}')
    if cleanup_errors:
        _update_journal(engine,operation_id,'CLEANUP_REQUIRED','; '.join(cleanup_errors))
        return False,'Base supprimee, mais des fichiers restent en quarantaine. Reprise de nettoyage obligatoire.'
    _update_journal(engine,operation_id,'COMPLETE')
    return True,'Action fictive et dependances supprimees, journal de purge complete.'


def legacy_quality_orphans(engine):
    """No historical reattribution by guessing; only report rows already unlinked."""
    with engine.connect() as conn:
        return {
            'quality_events_without_action':_one(conn,'SELECT COUNT(*) n FROM quality_events WHERE action_id IS NULL')['n'],
            'quality_issues_without_action':_one(conn,'SELECT COUNT(*) n FROM quality_issues WHERE action_id IS NULL')['n'],
            'improvement_actions_without_action':_one(conn,'SELECT COUNT(*) n FROM improvement_actions WHERE action_id IS NULL')['n'],
        }
