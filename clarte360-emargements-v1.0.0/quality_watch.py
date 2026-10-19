"""GO4 official-source watch: explicit configuration, immutable evidence, safe collection.

Nothing is collected at import. Public operations require an existing, active admin
and a single organization through quality_service. HTTP has no credentials, proxies,
cookies or autonomous tools. All network entry points validate and pin a public IP.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
import threading
import time
import uuid
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import xml.etree.ElementTree as ET
from xml.parsers import expat

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


FORMATS = ('RSS', 'ATOM', 'JSON', 'HTML', 'MANUAL')
PRIORITIES = ('LOW', 'NORMAL', 'HIGH', 'CRITICAL')
EXCLUDED_HOSTS = ('centre-inffo.fr', 'centre-inffo.com', 'veilleformation.com')
_CATEGORIES = 'REGLEMENTATION_QUALIOPI, METIERS_COMPETENCES, PEDAGOGIE_TECHNOLOGIE, HANDICAP_ACCESSIBILITE, EXPLOITATION_INFORMATIQUE'


class WatchError(ValueError):
    """A bounded, user-readable watch error; external response bodies are never errors."""


class WatchConflictError(WatchError):
    pass


class WatchBusyError(WatchConflictError):
    def __init__(self, run_id=None):
        super().__init__('Une collecte de cette source est déjà en cours.')
        self.run_id = run_id


class WatchFetchError(WatchError):
    pass


WATCH_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS quality_watch_settings (
      organization_id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0,
      configuration_validated INTEGER NOT NULL DEFAULT 0,
      timezone TEXT NOT NULL DEFAULT 'Europe/Paris', hour INTEGER NOT NULL DEFAULT 9,
      minute INTEGER NOT NULL DEFAULT 0, row_version INTEGER NOT NULL DEFAULT 1,
      updated_at TEXT NOT NULL, updated_by TEXT NOT NULL,
      FOREIGN KEY(organization_id) REFERENCES organizations(id))""",
    """CREATE TABLE IF NOT EXISTS quality_watch_technologies (
      id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER NOT NULL,
      name TEXT NOT NULL, name_key TEXT NOT NULL, family TEXT NOT NULL,
      publisher TEXT NOT NULL DEFAULT '', official_url TEXT NOT NULL DEFAULT '',
      applications_json TEXT NOT NULL DEFAULT '[]', environment TEXT NOT NULL DEFAULT '',
      observed_version TEXT NOT NULL DEFAULT '', observed_at TEXT,
      model TEXT NOT NULL DEFAULT '', technical_owner TEXT NOT NULL DEFAULT '',
      criticality TEXT NOT NULL DEFAULT 'NORMAL', active INTEGER NOT NULL DEFAULT 1,
      row_version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(organization_id,name_key), FOREIGN KEY(organization_id) REFERENCES organizations(id))""",
    """CREATE TABLE IF NOT EXISTS quality_watch_sources (
      id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER NOT NULL,
      name TEXT NOT NULL, category TEXT NOT NULL, url TEXT NOT NULL, scope TEXT NOT NULL DEFAULT '',
      priority TEXT NOT NULL DEFAULT 'NORMAL', format TEXT NOT NULL,
      active INTEGER NOT NULL DEFAULT 0, configuration_validated INTEGER NOT NULL DEFAULT 0,
      allowed_hosts_json TEXT NOT NULL, parser_config_json TEXT NOT NULL DEFAULT '{}',
      overlap_days INTEGER NOT NULL DEFAULT 14, point_zero TEXT,
      last_success_at TEXT, cursor_at TEXT, last_attempt_at TEXT, last_error TEXT,
      last_successful_month TEXT, lease_token TEXT, lease_expires_at TEXT,
      archived_at TEXT, row_version INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, created_by TEXT NOT NULL,
      UNIQUE(organization_id,url), FOREIGN KEY(organization_id) REFERENCES organizations(id))""",
    """CREATE TABLE IF NOT EXISTS quality_watch_source_technologies (
      source_id INTEGER NOT NULL, technology_id INTEGER NOT NULL,
      PRIMARY KEY(source_id,technology_id),
      FOREIGN KEY(source_id) REFERENCES quality_watch_sources(id) ON DELETE CASCADE,
      FOREIGN KEY(technology_id) REFERENCES quality_watch_technologies(id))""",
    """CREATE TABLE IF NOT EXISTS quality_watch_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER NOT NULL,
      organization_id INTEGER NOT NULL, trigger TEXT NOT NULL, status TEXT NOT NULL,
      started_at TEXT NOT NULL, finished_at TEXT, period_start_at TEXT NOT NULL,
      period_end_at TEXT NOT NULL, initial_run INTEGER NOT NULL, lease_token TEXT NOT NULL,
      config_sha256 TEXT NOT NULL, triggered_by TEXT NOT NULL,
      pages INTEGER NOT NULL DEFAULT 0, bytes_read INTEGER NOT NULL DEFAULT 0,
      items_seen INTEGER NOT NULL DEFAULT 0, new_items INTEGER NOT NULL DEFAULT 0,
      new_versions INTEGER NOT NULL DEFAULT 0, unchanged INTEGER NOT NULL DEFAULT 0,
      ignored_before_zero INTEGER NOT NULL DEFAULT 0,
      pages_json TEXT NOT NULL DEFAULT '[]', error TEXT,
      coverage TEXT NOT NULL DEFAULT 'PAGES_PUBLIEES_PAR_LA_SOURCE',
      FOREIGN KEY(source_id) REFERENCES quality_watch_sources(id),
      FOREIGN KEY(organization_id) REFERENCES organizations(id))""",
    """CREATE TABLE IF NOT EXISTS quality_watch_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER NOT NULL,
      organization_id INTEGER NOT NULL, item_key TEXT NOT NULL, version_no INTEGER NOT NULL,
      supersedes_id INTEGER, content_sha256 TEXT NOT NULL, title TEXT NOT NULL,
      summary TEXT NOT NULL DEFAULT '', url TEXT NOT NULL, published_at TEXT, updated_source_at TEXT,
      effective_at TEXT, is_reference INTEGER NOT NULL DEFAULT 0,
      initial_reason TEXT NOT NULL DEFAULT '', discovered_at TEXT NOT NULL,
      run_id INTEGER NOT NULL, payload_json TEXT NOT NULL,
      UNIQUE(source_id,item_key,content_sha256), UNIQUE(source_id,item_key,version_no),
      FOREIGN KEY(source_id) REFERENCES quality_watch_sources(id),
      FOREIGN KEY(supersedes_id) REFERENCES quality_watch_items(id),
      FOREIGN KEY(run_id) REFERENCES quality_watch_runs(id))""",
    """CREATE TABLE IF NOT EXISTS quality_watch_action_links (
      source_id INTEGER NOT NULL, item_key TEXT NOT NULL, action_id INTEGER,
      created_at TEXT NOT NULL, PRIMARY KEY(source_id,item_key),
      FOREIGN KEY(source_id) REFERENCES quality_watch_sources(id),
      FOREIGN KEY(action_id) REFERENCES quality_events(id) ON DELETE SET NULL)""",
    """CREATE TABLE IF NOT EXISTS quality_watch_decisions (
      id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER NOT NULL,
      item_id INTEGER NOT NULL, decision TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',
      action_id INTEGER, prior_decision_id INTEGER, command_id TEXT NOT NULL,
      command_sha256 TEXT NOT NULL, decided_by TEXT NOT NULL, decided_at TEXT NOT NULL,
      UNIQUE(organization_id,command_id),
      FOREIGN KEY(item_id) REFERENCES quality_watch_items(id),
      FOREIGN KEY(action_id) REFERENCES quality_events(id) ON DELETE SET NULL,
      FOREIGN KEY(prior_decision_id) REFERENCES quality_watch_decisions(id))""",
    """CREATE TABLE IF NOT EXISTS quality_watch_decision_heads (
      item_id INTEGER PRIMARY KEY, decision_id INTEGER NOT NULL,
      FOREIGN KEY(item_id) REFERENCES quality_watch_items(id),
      FOREIGN KEY(decision_id) REFERENCES quality_watch_decisions(id))""",
    """CREATE TABLE IF NOT EXISTS quality_watch_audit (
      id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER NOT NULL,
      event_type TEXT NOT NULL, entity_kind TEXT NOT NULL, entity_id TEXT NOT NULL,
      actor TEXT NOT NULL, created_at TEXT NOT NULL, details_json TEXT NOT NULL)""",
    'CREATE INDEX IF NOT EXISTS ix_watch_items_latest ON quality_watch_items(source_id,item_key,version_no)',
    'CREATE INDEX IF NOT EXISTS ix_watch_runs_source ON quality_watch_runs(source_id,started_at,id)',
    """CREATE TRIGGER IF NOT EXISTS quality_watch_items_no_update
      BEFORE UPDATE ON quality_watch_items BEGIN
        SELECT RAISE(ABORT,'Les informations de veille sont immuables.'); END""",
    """CREATE TRIGGER IF NOT EXISTS quality_watch_items_no_delete
      BEFORE DELETE ON quality_watch_items BEGIN
        SELECT RAISE(ABORT,'Les informations de veille sont immuables.'); END""",
]


def init_watch_schema(conn):
    """Additive schema; caller owns the same transaction as db.init_db."""
    for statement in WATCH_SCHEMA:
        conn.execute(text(statement))


def _actor(engine, actor):
    from quality_service import require_admin
    return require_admin(engine, actor)


def _org(actor):
    return int(actor.organization_id)


def _who(actor):
    return actor.key


def _time(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise WatchError('Une date avec fuseau horaire est nécessaire.')
        return value.astimezone(timezone.utc)
    raw = str(value).strip()
    if not raw:
        raise WatchError('Date vide.')
    try:
        dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        try:
            dt = parsedate_to_datetime(raw)
        except (TypeError, ValueError, OverflowError):
            raise WatchError('Date de source invalide.') from None
    if dt.tzinfo is None:
        # Date-only notices are explicitly stored at UTC midnight; no local inference.
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            raise WatchError('Une date avec fuseau horaire est nécessaire.')
    return dt.astimezone(timezone.utc)


def _iso(value=None):
    return _time(value).isoformat()


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _digest(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def _clean(value, label, limit=200, required=False):
    value = str(value or '').strip()
    if required and not value:
        raise WatchError(f'{label} est nécessaire.')
    if len(value) > limit or any(ord(c) < 32 and c not in '\n\t' for c in value):
        raise WatchError(f'{label} est trop long ou contient des caractères non autorisés.')
    if re.search(r'-----BEGIN [A-Z ]*PRIVATE KEY-----|(?i:bearer\s+[a-z0-9_.-]{20,}|(?:password|client_secret|api_key)\s*[:=])', value):
        raise WatchError('Ne pas enregistrer de secret dans le registre de veille.')
    return value


def _integer(value, label, minimum, maximum):
    if isinstance(value, bool):
        raise WatchError(f'{label} doit être un entier.')
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        raise WatchError(f'{label} doit être un entier.') from None
    if str(result) != str(value).strip() or not minimum <= result <= maximum:
        raise WatchError(f'{label} doit être compris entre {minimum} et {maximum}.')
    return result


def _host(raw):
    host = str(raw or '').strip().rstrip('.').lower()
    if not host or '%' in host or any(c in host for c in '/@?#\\'):
        raise WatchFetchError('Hôte invalide.')
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        try:
            host = host.encode('idna').decode('ascii')
        except UnicodeError:
            raise WatchFetchError('Hôte invalide.') from None
        if len(host) > 253 or '.' not in host or not re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)+', host):
            raise WatchFetchError('Un hôte public explicite est nécessaire.')
        if any(not part or len(part) > 63 or part.startswith('-') or part.endswith('-') for part in host.split('.')):
            raise WatchFetchError('Hôte invalide.')
        if host.endswith(('.localhost', '.local', '.internal', '.lan', '.home', '.invalid')):
            raise WatchFetchError('Les hôtes locaux ou réservés sont interdits.')
    else:
        if not addr.is_global or addr.is_multicast or addr.is_unspecified or addr.is_reserved:
            raise WatchFetchError('Les adresses non publiques sont interdites.')
        host = addr.compressed
    if any(host == bad or host.endswith('.' + bad) for bad in EXCLUDED_HOSTS):
        raise WatchFetchError('Cette source est exclue du périmètre de veille validé.')
    return host


def _url(raw, allowed_hosts=None, *, keep_fragment=False):
    raw = _clean(raw, 'URL', 4096, True)
    if any(ord(c) < 33 for c in raw) or '\\' in raw:
        raise WatchFetchError('URL invalide.')
    try:
        p = urlsplit(raw)
        port = p.port
    except ValueError:
        raise WatchFetchError('URL invalide.') from None
    if p.scheme.lower() != 'https' or p.username is not None or p.password is not None or port not in (None, 443):
        raise WatchFetchError('Seules les URL HTTPS sans identifiant, sur le port 443, sont acceptées.')
    host = _host(p.hostname)
    if allowed_hosts is not None and host not in allowed_hosts:
        raise WatchFetchError('Hôte absent de la liste des domaines autorisés.')
    for key, _ in parse_qsl(p.query, keep_blank_values=True):
        if re.search(r'(?i)^(?:access_token|api[-_]?key|key|token|password|secret|client_secret|authorization)$', key):
            raise WatchFetchError('Les URL de collecte ne doivent contenir aucun secret.')
    netloc = '[' + host + ']' if ':' in host else host
    return urlunsplit(('https', netloc, p.path or '/', p.query, p.fragment if keep_fragment else ''))


def _hosts(url, values=None):
    base = _host(urlsplit(url).hostname)
    if isinstance(values, str):
        values = [v.strip() for v in values.split(',') if v.strip()]
    hosts = sorted({_host(v) for v in (values or [base])})
    if base not in hosts or len(hosts) > 20:
        raise WatchError('Le domaine de la source doit figurer dans une liste de 20 hôtes maximum.')
    return hosts


def _priority(value):
    result = str(value or 'NORMAL').upper()
    if result not in PRIORITIES:
        raise WatchError('Priorité invalide.')
    return result


def _audit(conn, actor, kind, entity_kind, entity_id, details):
    conn.execute(text('''INSERT INTO quality_watch_audit
      (organization_id,event_type,entity_kind,entity_id,actor,created_at,details_json)
      VALUES(:org,:kind,:entity,:id,:actor,:at,:details)'''),
      {'org': _org(actor), 'kind': kind, 'entity': entity_kind, 'id': str(entity_id),
       'actor': _who(actor), 'at': _iso(), 'details': _json(details)})


def _one(conn, statement, params=None):
    row = conn.execute(text(statement), params or {}).mappings().first()
    return dict(row) if row else None


def _source(conn, actor, source_id):
    row = _one(conn, 'SELECT * FROM quality_watch_sources WHERE id=:id AND organization_id=:org',
               {'id': int(source_id), 'org': _org(actor)})
    if not row:
        raise PermissionError('Source de veille inaccessible.')
    return row


def _source_dict(conn, row):
    result = dict(row)
    result['allowed_hosts'] = json.loads(result.pop('allowed_hosts_json'))
    result['parser_config'] = json.loads(result.pop('parser_config_json'))
    result['technology_ids'] = [r[0] for r in conn.execute(text(
        'SELECT technology_id FROM quality_watch_source_technologies WHERE source_id=:id ORDER BY technology_id'), {'id': row['id']})]
    for key in ('active', 'configuration_validated'):
        result[key] = bool(result[key])
    result['running'] = bool(result.pop('lease_token') and result.get('lease_expires_at') and _time(result['lease_expires_at']) > _time())
    return result


def _assert_version(row, expected_version):
    if expected_version is None or int(expected_version) != int(row['row_version']):
        raise WatchConflictError('Cette fiche a changé. Actualisez-la avant de l’enregistrer.')


def _assert_idle(conn, row, now=None):
    if row.get('lease_token') and row.get('lease_expires_at') and _time(row['lease_expires_at']) > _time(now):
        running = _one(conn, "SELECT id FROM quality_watch_runs WHERE source_id=:s AND status='RUNNING' ORDER BY id DESC LIMIT 1", {'s': row['id']})
        raise WatchBusyError(running['id'] if running else None)


def list_sources(engine, actor, include_archived=False):
    actor = _actor(engine, actor)
    with engine.connect() as conn:
        rows = conn.execute(text('SELECT * FROM quality_watch_sources WHERE organization_id=:org'
            + ('' if include_archived else ' AND archived_at IS NULL') + ' ORDER BY name,id'), {'org': _org(actor)}).mappings()
        return [_source_dict(conn, r) for r in rows]


def save_source(engine, actor, *, source_id=None, expected_version=None, name, category, url,
                scope='', priority='NORMAL', active=False, configuration_validated=False,
                format='RSS', allowed_hosts=None, parser_config=None, overlap_days=14,
                technology_ids=None, point_zero=None):
    actor = _actor(engine, actor)
    fmt = str(format or '').upper()
    if fmt not in FORMATS:
        raise WatchError('Méthode non prise en charge : utiliser RSS, ATOM, JSON, HTML ou MANUAL.')
    endpoint = _url(url)
    hosts = _hosts(endpoint, allowed_hosts)
    config = _parser_config(fmt, parser_config, validated=bool(configuration_validated))
    vals = {'org': _org(actor), 'name': _clean(name, 'Nom', required=True),
            'category': _clean(category, 'Famille', 100, True), 'url': endpoint,
            'scope': _clean(scope, 'Périmètre', 2000), 'priority': _priority(priority), 'format': fmt,
            'active': int(bool(active) and bool(configuration_validated) and fmt != 'MANUAL'),
            'validated': int(bool(configuration_validated)), 'hosts': _json(hosts), 'config': _json(config),
            'overlap': _integer(overlap_days, 'Recouvrement en jours', 1, 366),
            'point_zero': _iso(point_zero) if point_zero else None, 'now': _iso(), 'by': _who(actor)}
    techs = sorted(set(int(t) for t in (technology_ids or [])))
    try:
        with engine.begin() as conn:
            old = _source(conn, actor, source_id) if source_id is not None else None
            reset_cursor = False
            if old:
                _assert_version(old, expected_version)
                _assert_idle(conn, old)
                if old['archived_at']:
                    raise WatchError('Une source archivée ne peut pas être réactivée silencieusement.')
                if old['last_success_at'] and old['url'] != endpoint:
                    raise WatchError('Une source déjà collectée conserve son URL : créez une nouvelle source pour un autre point d’entrée.')
                if old['last_success_at'] and (old['format'] != fmt or old['parser_config_json'] != vals['config']):
                    # Preserve every previous run/item; a changed extraction rule must
                    # be reviewed explicitly before reactivation and a fresh scan.
                    reset_cursor = True
                    vals['active'] = 0
                    vals['validated'] = 0
                if old['point_zero'] and vals['point_zero'] and old['point_zero'] != vals['point_zero']:
                    raise WatchError('Le point zéro déjà enregistré ne peut pas être remplacé.')
                vals['point_zero'] = old['point_zero'] or vals['point_zero']
            for tid in techs:
                if not _one(conn, 'SELECT id FROM quality_watch_technologies WHERE id=:id AND organization_id=:org', {'id': tid, 'org': _org(actor)}):
                    raise PermissionError('Technologie hors périmètre.')
            if old:
                vals['id'] = int(source_id)
                changed = conn.execute(text('''UPDATE quality_watch_sources SET name=:name,category=:category,
                  url=:url,scope=:scope,priority=:priority,format=:format,active=:active,
                  configuration_validated=:validated,allowed_hosts_json=:hosts,parser_config_json=:config,
                  overlap_days=:overlap,point_zero=:point_zero,updated_at=:now,row_version=row_version+1
                  WHERE id=:id AND organization_id=:org AND row_version=:expected'''),
                  {**vals, 'expected': int(expected_version)}).rowcount
                if not changed:
                    raise WatchConflictError('Cette source a changé pendant l’enregistrement.')
                if reset_cursor:
                    conn.execute(text('''UPDATE quality_watch_sources SET cursor_at=NULL,last_success_at=NULL,
                        last_successful_month=NULL WHERE id=:id'''), {'id': source_id})
            else:
                result = conn.execute(text('''INSERT INTO quality_watch_sources
                  (organization_id,name,category,url,scope,priority,format,active,configuration_validated,
                   allowed_hosts_json,parser_config_json,overlap_days,point_zero,created_at,updated_at,created_by)
                  VALUES(:org,:name,:category,:url,:scope,:priority,:format,:active,:validated,
                   :hosts,:config,:overlap,:point_zero,:now,:now,:by)'''), vals)
                source_id = result.lastrowid
            conn.execute(text('DELETE FROM quality_watch_source_technologies WHERE source_id=:id'), {'id': source_id})
            for tid in techs:
                conn.execute(text('INSERT INTO quality_watch_source_technologies(source_id,technology_id) VALUES(:s,:t)'), {'s': source_id, 't': tid})
            _audit(conn, actor, 'SOURCE_UPDATED' if old else 'SOURCE_CREATED', 'source', source_id,
                   {'active': bool(vals['active']), 'configuration_validated': bool(vals['validated']), 'technology_ids': techs,
                    'url': endpoint, 'format': fmt, 'allowed_hosts': hosts, 'parser_config': config,
                    'scope': vals['scope'], 'category': vals['category'], 'priority': vals['priority'],
                    'overlap_days': vals['overlap'], 'point_zero': vals['point_zero'], 'cursor_reset_for_review': reset_cursor})
    except IntegrityError as ex:
        raise WatchConflictError('Une source de cette URL est déjà enregistrée pour cet organisme.') from ex
    return int(source_id)


def remove_source(engine, actor, source_id, *, expected_version, reason):
    actor = _actor(engine, actor)
    reason = _clean(reason, 'Motif', 2000, True)
    with engine.begin() as conn:
        row = _source(conn, actor, source_id)
        _assert_version(row, expected_version)
        _assert_idle(conn, row)
        used = _one(conn, 'SELECT id FROM quality_watch_runs WHERE source_id=:id LIMIT 1', {'id': source_id})
        if used:
            conn.execute(text('''UPDATE quality_watch_sources SET active=0,archived_at=:now,
                updated_at=:now,row_version=row_version+1 WHERE id=:id'''), {'id': source_id, 'now': _iso()})
        else:
            conn.execute(text('DELETE FROM quality_watch_sources WHERE id=:id'), {'id': source_id})
        _audit(conn, actor, 'SOURCE_ARCHIVED' if used else 'SOURCE_REMOVED', 'source', source_id, {'reason': reason})
    return {'removed': not bool(used), 'archived': bool(used)}


def list_technologies(engine, actor):
    actor = _actor(engine, actor)
    with engine.connect() as conn:
        result = []
        for row in conn.execute(text('SELECT * FROM quality_watch_technologies WHERE organization_id=:o ORDER BY name,id'), {'o': _org(actor)}).mappings():
            item = dict(row)
            item['applications'] = json.loads(item.pop('applications_json'))
            item['active'] = bool(item['active'])
            item['source_ids'] = [r[0] for r in conn.execute(text('SELECT source_id FROM quality_watch_source_technologies WHERE technology_id=:t ORDER BY source_id'), {'t': row['id']})]
            result.append(item)
    return result


def save_technology(engine, actor, *, technology_id=None, expected_version=None, name, family,
                    publisher='', official_url='', applications=None, environment='', observed_version='',
                    observed_at=None, model='', technical_owner='', criticality='NORMAL', active=True):
    actor = _actor(engine, actor)
    title = _clean(name, 'Nom de technologie', 200, True)
    if isinstance(applications, str):
        applications = [v.strip() for v in applications.split(',') if v.strip()]
    apps = sorted({_clean(v, 'Application', 200, True) for v in (applications or [])})
    if len(apps) > 100:
        raise WatchError('100 applications maximum par technologie.')
    version = _clean(observed_version, 'Version observée', 200)
    vals = {'org': _org(actor), 'name': title, 'key': title.casefold(),
            'family': _clean(family, 'Famille', 100, True), 'publisher': _clean(publisher, 'Éditeur'),
            'url': _url(official_url) if official_url else '', 'apps': _json(apps),
            'environment': _clean(environment, 'Environnement', 300), 'version': version,
            'observed': _iso(observed_at) if observed_at else None,
            'model': _clean(model, 'Modèle'), 'owner': _clean(technical_owner, 'Responsable'),
            'criticality': _priority(criticality), 'active': int(bool(active)), 'now': _iso()}
    if vals['observed'] and not version:
        raise WatchError('Une date d’observation nécessite une version renseignée.')
    try:
        with engine.begin() as conn:
            if technology_id is None:
                result = conn.execute(text('''INSERT INTO quality_watch_technologies
                  (organization_id,name,name_key,family,publisher,official_url,applications_json,environment,
                   observed_version,observed_at,model,technical_owner,criticality,active,created_at,updated_at)
                  VALUES(:org,:name,:key,:family,:publisher,:url,:apps,:environment,:version,:observed,
                   :model,:owner,:criticality,:active,:now,:now)'''), vals)
                technology_id = result.lastrowid
            else:
                old = _one(conn, 'SELECT * FROM quality_watch_technologies WHERE id=:id AND organization_id=:org', {'id': technology_id, 'org': _org(actor)})
                if not old:
                    raise PermissionError('Technologie inaccessible.')
                _assert_version(old, expected_version)
                changed = conn.execute(text('''UPDATE quality_watch_technologies SET name=:name,name_key=:key,
                  family=:family,publisher=:publisher,official_url=:url,applications_json=:apps,
                  environment=:environment,observed_version=:version,observed_at=:observed,model=:model,
                  technical_owner=:owner,criticality=:criticality,active=:active,updated_at=:now,row_version=row_version+1
                  WHERE id=:id AND organization_id=:org AND row_version=:expected'''),
                  {**vals, 'id': technology_id, 'expected': expected_version}).rowcount
                if not changed:
                    raise WatchConflictError('Cette technologie a changé pendant l’enregistrement.')
            _audit(conn, actor, 'TECHNOLOGY_SAVED', 'technology', technology_id, {'applications': apps, 'observed_version': version})
    except IntegrityError as ex:
        raise WatchConflictError('Cette technologie existe déjà pour cet organisme.') from ex
    return int(technology_id)


def get_schedule(engine, actor):
    actor = _actor(engine, actor)
    with engine.connect() as conn:
        row = _one(conn, 'SELECT * FROM quality_watch_settings WHERE organization_id=:o', {'o': _org(actor)})
    row = row or {'organization_id': _org(actor), 'enabled': 0, 'configuration_validated': 0,
                 'timezone': 'Europe/Paris', 'hour': 9, 'minute': 0, 'row_version': 0}
    row['enabled'] = bool(row['enabled'])
    row['configuration_validated'] = bool(row['configuration_validated'])
    row['day'] = 1
    return row


def save_schedule(engine, actor, *, enabled=False, configuration_validated=False,
                  timezone='Europe/Paris', hour=9, minute=0, expected_version=None):
    actor = _actor(engine, actor)
    tzname = _clean(timezone, 'Fuseau', 100, True)
    try:
        ZoneInfo(tzname)
    except (ZoneInfoNotFoundError, ValueError):
        raise WatchError('Fuseau horaire inconnu.') from None
    vals = {'o': _org(actor), 'tz': tzname, 'hour': _integer(hour, 'Heure', 0, 23),
            'minute': _integer(minute, 'Minute', 0, 59),
            'enabled': int(bool(enabled) and bool(configuration_validated)),
            'valid': int(bool(configuration_validated)), 'now': _iso(), 'actor': _who(actor)}
    with engine.begin() as conn:
        old = _one(conn, 'SELECT * FROM quality_watch_settings WHERE organization_id=:o', vals)
        if old:
            _assert_version(old, expected_version)
            changed = conn.execute(text('''UPDATE quality_watch_settings SET enabled=:enabled,
              configuration_validated=:valid,timezone=:tz,hour=:hour,minute=:minute,
              row_version=row_version+1,updated_at=:now,updated_by=:actor
              WHERE organization_id=:o AND row_version=:expected'''), {**vals, 'expected': expected_version}).rowcount
            if not changed:
                raise WatchConflictError('Le calendrier a changé pendant l’enregistrement.')
        else:
            if expected_version not in (None, 0):
                raise WatchConflictError('Le calendrier n’existe pas encore.')
            conn.execute(text('''INSERT INTO quality_watch_settings
              (organization_id,enabled,configuration_validated,timezone,hour,minute,updated_at,updated_by)
              VALUES(:o,:enabled,:valid,:tz,:hour,:minute,:now,:actor)'''), vals)
        _audit(conn, actor, 'SCHEDULE_SAVED', 'schedule', _org(actor), {'enabled': bool(vals['enabled']), 'timezone': tzname, 'hour': vals['hour'], 'minute': vals['minute'], 'day': 1})
    return get_schedule(engine, actor)


@dataclass(frozen=True)
class CollectionLimits:
    max_page_bytes: int = 1_048_576
    timeout_seconds: int = 10
    max_pages: int = 20
    max_items: int = 2000
    max_run_seconds: int = 45
    max_run_bytes: int = 10_485_760
    max_redirects: int = 3


_LIMIT_BOUNDS = {
    'max_page_bytes': (1024, 5_242_880), 'timeout_seconds': (1, 30),
    'max_pages': (1, 100), 'max_items': (1, 10000), 'max_run_seconds': (1, 60),
    'max_run_bytes': (1024, 20_971_520), 'max_redirects': (0, 5),
}
_JSON_FIELDS = ('id', 'title', 'summary', 'url', 'published_at', 'updated_at', 'effective_at', 'is_reference')
_HTML_KEYS = ('item_tag', 'item_class', 'id_attribute', 'title_tag', 'summary_tag',
              'link_tag', 'link_attribute', 'published_attribute', 'effective_attribute', 'reference_attribute')


def _path(value, label):
    value = _clean(value, label, 200)
    if value and not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*', value):
        raise WatchError('Les chemins JSON doivent être des clés simples séparées par des points.')
    return value


def _parser_config(fmt, raw, *, validated):
    if raw is None:
        raw = {}
    if not isinstance(raw, dict) or len(_json(raw)) > 12000:
        raise WatchError('Paramètres de lecture invalides ou trop volumineux.')
    allowed = {'limits', 'since_param', 'reference_document'}
    if fmt == 'JSON':
        allowed |= {'items_path', 'next_path', 'next_cursor_path', 'cursor_param', 'fields'}
    if fmt == 'HTML':
        allowed |= set(_HTML_KEYS)
    if set(raw) - allowed:
        raise WatchError('Paramètre de lecture non pris en charge : ' + ', '.join(sorted(set(raw) - allowed)))
    config = dict(raw)
    lim = raw.get('limits') or {}
    if not isinstance(lim, dict) or set(lim) - set(_LIMIT_BOUNDS):
        raise WatchError('Limites de collecte inconnues.')
    defaults = CollectionLimits()
    config['limits'] = {key: _integer(lim.get(key, getattr(defaults, key)), key, low, high)
                        for key, (low, high) in _LIMIT_BOUNDS.items()}
    config['reference_document'] = bool(raw.get('reference_document', False))
    config['since_param'] = _path(raw.get('since_param', ''), 'Paramètre de reprise')
    if config['since_param'] and '.' in config['since_param']:
        raise WatchError('Le paramètre de reprise doit être un nom simple.')
    if fmt == 'JSON':
        config['items_path'] = _path(raw.get('items_path', 'items'), 'Liste JSON')
        config['next_path'] = _path(raw.get('next_path', 'next'), 'Page suivante')
        config['next_cursor_path'] = _path(raw.get('next_cursor_path', ''), 'Curseur JSON')
        config['cursor_param'] = _path(raw.get('cursor_param', 'cursor'), 'Paramètre du curseur')
        if '.' in config['cursor_param'] or not config['cursor_param']:
            raise WatchError('Le paramètre du curseur doit être un nom simple.')
        fields = raw.get('fields') or {}
        if not isinstance(fields, dict) or set(fields) - set(_JSON_FIELDS):
            raise WatchError('Champs JSON inconnus.')
        config['fields'] = {key: _path(fields.get(key, key), 'Champ JSON') for key in _JSON_FIELDS}
    elif fmt == 'HTML':
        defaults_html = {'item_tag': '', 'item_class': '', 'id_attribute': 'id',
                         'title_tag': 'h2', 'summary_tag': 'p', 'link_tag': 'a',
                         'link_attribute': 'href', 'published_attribute': 'data-published',
                         'effective_attribute': 'data-effective', 'reference_attribute': 'data-reference'}
        for key, default in defaults_html.items():
            value = _clean(raw.get(key, default), 'Règle HTML', 80)
            if value and not re.fullmatch(r'[A-Za-z][A-Za-z0-9:_-]*', value):
                raise WatchError('La règle HTML doit nommer une balise, classe ou attribut simple.')
            config[key] = value
        if validated and (not config['item_tag'] or not config['title_tag'] or not config['id_attribute']):
            raise WatchError('La lecture HTML nécessite une balise d’entrée, une balise de titre et un attribut identifiant explicites.')
    return config


@dataclass(frozen=True)
class ResolvedTarget:
    url: str
    hostname: str
    address: str
    port: int
    request_target: str


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict
    body: bytes


def resolve_target(url, allowed_hosts, *, resolver=None, timeout=5):
    """Validate all DNS answers, then pin one numeric address. No second resolution."""
    clean_url = _url(url, allowed_hosts)
    parsed = urlsplit(clean_url)
    hostname = _host(parsed.hostname)
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        response = {}
        ready = threading.Event()

        def resolve():
            try:
                response['answers'] = (resolver or socket.getaddrinfo)(hostname, 443, type=socket.SOCK_STREAM)
            except BaseException as ex:
                response['error'] = type(ex).__name__
            finally:
                ready.set()

        thread = threading.Thread(target=resolve, name='quality-watch-dns', daemon=True)
        thread.start()
        if not ready.wait(max(0.001, min(float(timeout), 5.0))):
            raise WatchFetchError('Délai de résolution DNS dépassé.')
        if response.get('error'):
            raise WatchFetchError('Résolution DNS impossible.')
        answers = response.get('answers', [])
        addresses = []
        for answer in answers:
            try:
                address = ipaddress.ip_address(answer[4][0])
            except (IndexError, TypeError, ValueError):
                raise WatchFetchError('Réponse DNS invalide.') from None
            if not address.is_global or address.is_multicast or address.is_reserved or address.is_unspecified:
                raise WatchFetchError('La résolution DNS contient une adresse non publique.')
            if address.version == 6 and (address.ipv4_mapped or address.sixtofour or address.teredo):
                raise WatchFetchError('Les adresses de transition IPv6 ne sont pas acceptées.')
            addresses.append(address.compressed)
        if not addresses:
            raise WatchFetchError('La source ne possède aucune adresse publique.')
        address = sorted(set(addresses))[0]
    else:
        if literal.version == 6 and (literal.ipv4_mapped or literal.sixtofour or literal.teredo):
            raise WatchFetchError('Les adresses de transition IPv6 ne sont pas acceptées.')
        address = literal.compressed
    path = urlunsplit(('', '', parsed.path or '/', parsed.query, ''))
    return ResolvedTarget(clean_url, hostname, address, 443, path)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """TLS authenticates hostname; TCP connects only to the already approved address."""
    def __init__(self, target, timeout):
        super().__init__(target.hostname, port=443, timeout=timeout, context=ssl.create_default_context())
        self.target = target
        self.deadline = time.monotonic() + timeout

    def connect(self):
        ip = ipaddress.ip_address(self.target.address)
        sock = socket.socket(socket.AF_INET6 if ip.version == 6 else socket.AF_INET, socket.SOCK_STREAM)
        self.sock = sock
        try:
            sock.settimeout(max(0.01, self.deadline - time.monotonic()))
            address = (self.target.address, 443, 0, 0) if ip.version == 6 else (self.target.address, 443)
            sock.connect(address)
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Collecte expirée.')
            sock.settimeout(remaining)
            self.sock = self._context.wrap_socket(sock, server_hostname=self.target.hostname)
        except BaseException:
            sock.close()
            self.sock = None
            raise


def _http_once(target, *, timeout, max_bytes):
    """One GET; no automatic redirects, proxy lookup, authentication or compression."""
    conn = _PinnedHTTPSConnection(target, timeout)
    expired = threading.Event()

    def abort():
        expired.set()
        sock = conn.sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()

    timer = threading.Timer(timeout, abort)
    timer.daemon = True
    timer.start()
    try:
        conn.request('GET', target.request_target, headers={
            'Host': '[' + target.hostname + ']' if ':' in target.hostname else target.hostname,
            'Accept': 'application/rss+xml, application/atom+xml, application/json, application/xml, text/html;q=0.8',
            'Accept-Encoding': 'identity', 'User-Agent': 'Clarte360-QualityWatch/1.0', 'Connection': 'close'})
        response = conn.getresponse()
        headers = {key.lower(): value for key, value in response.getheaders()}
        if headers.get('content-encoding', 'identity').lower() not in ('', 'identity'):
            raise WatchFetchError('La réponse compressée n’est pas acceptée par ce collecteur.')
        length = headers.get('content-length')
        declared = None
        if length is not None:
            try:
                declared = int(length)
            except ValueError:
                raise WatchFetchError('Taille de réponse invalide.') from None
            if declared < 0 or declared > max_bytes:
                raise WatchFetchError('La réponse dépasse la taille autorisée.')
        chunks = []
        count = 0
        while True:
            if expired.is_set():
                raise WatchFetchError('Délai de collecte dépassé.')
            chunk = response.read1(min(65536, max_bytes - count + 1))
            if not chunk:
                break
            count += len(chunk)
            if count > max_bytes:
                raise WatchFetchError('La réponse dépasse la taille autorisée.')
            chunks.append(chunk)
        if declared is not None and count != declared:
            raise WatchFetchError('La réponse HTTPS est tronquée ; collecte incomplète.')
        if expired.is_set():
            raise WatchFetchError('Délai de collecte dépassé.')
        return HttpResponse(response.status, headers, b''.join(chunks))
    except WatchError:
        raise
    except Exception as ex:
        raise WatchFetchError('Lecture HTTPS impossible ou délai dépassé.') from ex
    finally:
        timer.cancel()
        conn.close()


def _safe_fetch(url, source, limits, deadline, transport=None, resolver=None, budget=None):
    budget = budget if budget is not None else {'used': 0}
    hosts = json.loads(source['allowed_hosts_json'])
    visited = set()
    current = _url(url, hosts)
    for redirect in range(limits.max_redirects + 1):
        if current in visited:
            raise WatchFetchError('Boucle de redirection détectée.')
        visited.add(current)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise WatchFetchError('Délai total de collecte dépassé.')
        target = resolve_target(current, hosts, resolver=resolver, timeout=min(5, remaining))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise WatchFetchError('Délai total de collecte dépassé.')
        remaining_bytes = limits.max_run_bytes - budget['used']
        if remaining_bytes <= 0:
            raise WatchFetchError('La collecte dépasse le volume total autorisé.')
        response = (transport or _http_once)(target, timeout=min(limits.timeout_seconds, remaining),
                                            max_bytes=min(limits.max_page_bytes, remaining_bytes))
        if not isinstance(response, HttpResponse) or not isinstance(response.body, bytes):
            raise WatchFetchError('Réponse de transport invalide.')
        budget['used'] += len(response.body)
        if budget['used'] > limits.max_run_bytes:
            raise WatchFetchError('La collecte dépasse le volume total autorisé.')
        headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
        length = headers.get('content-length')
        if length is not None:
            try:
                declared = int(length)
            except ValueError:
                raise WatchFetchError('Taille de réponse invalide.') from None
            if declared < 0 or declared != len(response.body):
                raise WatchFetchError('La réponse HTTPS est tronquée ou sa taille est incohérente.')
        if len(response.body) > limits.max_page_bytes:
            raise WatchFetchError('La réponse dépasse la taille autorisée.')
        if deadline <= time.monotonic():
            raise WatchFetchError('Délai total de collecte dépassé.')
        if response.status in (301, 302, 303, 307, 308):
            if redirect >= limits.max_redirects or not headers.get('location'):
                raise WatchFetchError('Nombre de redirections dépassé ou destination absente.')
            current = _url(urljoin(current, headers['location']), hosts)
            continue
        if response.status != 200:
            raise WatchFetchError(f'Source indisponible : réponse HTTP {int(response.status)}.')
        if headers.get('content-encoding', 'identity').lower() not in ('', 'identity'):
            raise WatchFetchError('La réponse compressée n’est pas acceptée par ce collecteur.')
        return current, HttpResponse(response.status, headers, response.body)
    raise WatchFetchError('Redirection non traitée.')


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ('script', 'style'):
            self.ignored += 1
        elif not self.ignored:
            self.parts.append(' ')

    def handle_endtag(self, tag):
        if tag.lower() in ('script', 'style') and self.ignored:
            self.ignored -= 1
        elif not self.ignored:
            self.parts.append(' ')

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def _plain(value, limit):
    if value is None:
        return ''
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise WatchFetchError('Champ textuel de source invalide.')
    if len(str(value)) > limit * 4:
        raise WatchFetchError('Une information de veille dépasse la taille autorisée.')
    parser = _PlainText()
    parser.feed(str(value))
    result = ' '.join(''.join(parser.parts).split())
    if len(result) > limit:
        raise WatchFetchError('Une information de veille dépasse la taille autorisée.')
    return result


def _field(data, path, default=None):
    current = data
    if not path:
        return current
    for key in path.split('.'):
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _date(value):
    return _iso(value) if value not in (None, '') else None


def _record(raw, page_url, source, config):
    title = _plain(raw.get('title'), 1000)
    if not title:
        raise WatchFetchError('Une information de veille ne possède pas de titre.')
    link = raw.get('url') or page_url
    clean_link = _url(urljoin(page_url, str(link)), json.loads(source['allowed_hosts_json']), keep_fragment=True)
    key = str(raw.get('id') or raw.get('url') or '').strip()
    if not key or len(key) > 1000 or any(ord(c) < 32 for c in key):
        raise WatchFetchError('Un identifiant stable ou un lien direct est nécessaire pour chaque information.')
    reference = raw.get('is_reference', False)
    if isinstance(reference, str):
        reference = reference.strip().lower() in ('true', '1', 'yes', 'oui')
    payload = {'id': key, 'title': title, 'summary': _plain(raw.get('summary'), 32000),
               'url': clean_link, 'published_at': _date(raw.get('published_at')),
               'updated_at': _date(raw.get('updated_at')), 'effective_at': _date(raw.get('effective_at')),
               'is_reference': bool(reference or config.get('reference_document'))}
    return {**payload, 'content_sha256': _digest(payload), 'payload_json': _json(payload)}


def _local(tag):
    return tag.rsplit('}', 1)[-1].lower()


def _child(element, names):
    for child in element:
        if _local(child.tag) in names:
            return ''.join(child.itertext()).strip()
    return ''


def _next_header(headers, current):
    value = headers.get('link', '')
    if len(value) > 16000:
        raise WatchFetchError('En-tête de pagination trop long.')
    matches = re.findall(r'<([^<>]+)>\s*;\s*rel\s*=\s*["\']?next["\']?(?:\s*[,;]|$)', value, re.I)
    if len(matches) > 1:
        raise WatchFetchError('Pagination ambiguë.')
    return urljoin(current, matches[0]) if matches else None


def _parse_xml(body, current, fmt):
    if re.search(br'<!\s*(?:DOCTYPE|ENTITY)', body, re.I):
        raise WatchFetchError('Les déclarations DTD et entités XML sont interdites.')
    def reject_declaration(*args):
        raise WatchFetchError('Les déclarations DTD et entités XML sont interdites.')

    try:
        # Expat reads the XML encoding itself. A UTF-16 declaration cannot evade
        # the byte-level fast check above or cause entity expansion in ElementTree.
        checked = expat.ParserCreate()
        checked.StartDoctypeDeclHandler = reject_declaration
        checked.EntityDeclHandler = reject_declaration
        checked.ExternalEntityRefHandler = reject_declaration
        checked.Parse(body, True)
        root = ET.fromstring(body)
    except (ET.ParseError, expat.ExpatError) as ex:
        raise WatchFetchError('Flux XML invalide.') from ex
    root_name = _local(root.tag)
    if fmt == 'ATOM' and root_name != 'feed':
        raise WatchFetchError('La source ne fournit pas le flux Atom configuré.')
    if fmt == 'RSS' and root_name not in ('rss', 'rdf'):
        raise WatchFetchError('La source ne fournit pas le flux RSS configuré.')
    container = next((c for c in root if _local(c.tag) == 'channel'), root)
    entries = [c for c in (root if root_name in ('feed', 'rdf') else container) if _local(c.tag) in ('entry', 'item')]
    following = []
    for c in list(root) + (list(container) if container is not root else []):
        if _local(c.tag) == 'link' and c.attrib.get('rel', '').lower() == 'next':
            following.append(urljoin(current, c.attrib.get('href', '')))
    if len(set(following)) > 1:
        raise WatchFetchError('Pagination XML ambiguë.')
    items = []
    for entry in entries:
        link = ''
        for child in entry:
            if _local(child.tag) == 'link':
                rel = child.attrib.get('rel', 'alternate').lower()
                if rel in ('alternate', ''):
                    link = child.attrib.get('href') or ''.join(child.itertext()).strip()
                    if link:
                        break
        items.append({'id': _child(entry, ('id', 'guid')) or link,
                      'title': _child(entry, ('title',)), 'url': link,
                      'summary': _child(entry, ('summary', 'description', 'encoded', 'content')),
                      'published_at': _child(entry, ('published', 'pubdate', 'date')),
                      'updated_at': _child(entry, ('updated', 'modified')),
                      'effective_at': _child(entry, ('effective', 'effective_at', 'effectiveat')),
                      'is_reference': _child(entry, ('reference', 'is_reference'))})
    return items, following[0] if following else None


class _ConfiguredHTML(HTMLParser):
    """Small declared extraction grammar. No script, selector language, or evaluation."""
    def __init__(self, config):
        super().__init__(convert_charrefs=True)
        self.config = config
        self.depth = 0
        self.start_depth = None
        self.item = None
        self.capture = []
        self.items = []
        self.next_links = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = dict(attrs)
        void = tag in ('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr')
        if not void:
            self.depth += 1
        if tag in ('script', 'style'):
            self.ignored += 1
            return
        if self.ignored:
            return
        if tag in ('a', 'link') and 'next' in (attrs.get('rel') or '').lower().split() and attrs.get('href'):
            self.next_links.append(attrs['href'])
        match = tag == self.config['item_tag'].lower()
        wanted_class = self.config.get('item_class')
        if match and (not wanted_class or wanted_class in (attrs.get('class') or '').split()):
            if self.item is not None:
                raise WatchFetchError('Règle HTML ambiguë : entrées imbriquées.')
            self.start_depth = self.depth
            self.item = {'id': attrs.get(self.config['id_attribute'], ''), 'title': '', 'summary': '', 'url': '',
                         'published_at': attrs.get(self.config['published_attribute'], ''),
                         'effective_at': attrs.get(self.config['effective_attribute'], ''),
                         'is_reference': attrs.get(self.config['reference_attribute'], '')}
        if self.item is not None:
            if tag == self.config['title_tag'].lower():
                self.capture.append(('title', self.depth))
            if tag == self.config['summary_tag'].lower():
                self.capture.append(('summary', self.depth))
            if tag == self.config['link_tag'].lower() and not self.item['url']:
                self.item['url'] = attrs.get(self.config['link_attribute'], '')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() not in ('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'):
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ('script', 'style') and self.ignored:
            self.ignored -= 1
        if not self.ignored and self.item is not None:
            self.capture = [(kind, depth) for kind, depth in self.capture if depth != self.depth]
            if self.depth == self.start_depth:
                self.items.append(self.item)
                self.item = None
                self.start_depth = None
                self.capture = []
        self.depth = max(0, self.depth - 1)

    def handle_data(self, data):
        if self.item is not None and not self.ignored:
            for key in {key for key, _ in self.capture}:
                self.item[key] += ' ' + data


def _parse_page(current, response, source, config):
    fmt = source['format']
    content_type = response.headers.get('content-type', '').split(';', 1)[0].strip().lower()
    expected = {'RSS': {'application/rss+xml', 'text/xml', 'application/xml'},
                'ATOM': {'application/atom+xml', 'text/xml', 'application/xml'},
                'JSON': {'application/json', 'application/feed+json'},
                'HTML': {'text/html', 'application/xhtml+xml'}}
    if content_type and content_type not in expected.get(fmt, set()):
        raise WatchFetchError('Le format retourné ne correspond pas à la méthode configurée.')
    if fmt in ('RSS', 'ATOM'):
        raw_items, next_url = _parse_xml(response.body, current, fmt)
    elif fmt == 'JSON':
        try:
            payload = json.loads(response.body.decode('utf-8-sig'))
        except (UnicodeError, json.JSONDecodeError) as ex:
            raise WatchFetchError('Réponse JSON invalide.') from ex
        raw_entries = _field(payload, config['items_path'])
        if not isinstance(raw_entries, list):
            raise WatchFetchError('La liste JSON configurée est absente.')
        raw_items = []
        for entry in raw_entries:
            if not isinstance(entry, dict):
                raise WatchFetchError('Une entrée JSON n’est pas un objet.')
            raw_items.append({key: _field(entry, path) for key, path in config['fields'].items()})
        next_value = _field(payload, config['next_path']) if config['next_path'] else None
        if next_value is not None and not isinstance(next_value, str):
            raise WatchFetchError('La prochaine page JSON doit être une URL.')
        next_url = urljoin(current, next_value) if next_value else None
        if config['next_cursor_path']:
            cursor = _field(payload, config['next_cursor_path'])
            if cursor not in (None, ''):
                if next_url:
                    raise WatchFetchError('La source fournit deux paginations concurrentes.')
                cursor = _clean(cursor, 'Curseur de pagination', 1000, True)
                p = urlsplit(current)
                params = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k != config['cursor_param']]
                params.append((config['cursor_param'], cursor))
                next_url = urlunsplit((p.scheme, p.netloc, p.path, urlencode(params), ''))
    elif fmt == 'HTML':
        try:
            body = response.body.decode('utf-8-sig')
        except UnicodeError as ex:
            raise WatchFetchError('La règle HTML exige une page UTF-8.') from ex
        parser = _ConfiguredHTML(config)
        parser.feed(body)
        parser.close()
        if parser.item is not None:
            raise WatchFetchError('Une entrée HTML est incomplète.')
        # Zero items can mean a changed page template or a robot wall, not no change.
        if not parser.items:
            raise WatchFetchError('La règle HTML ne retrouve aucune entrée : contrôle manuel nécessaire.')
        if len(set(parser.next_links)) > 1:
            raise WatchFetchError('Pagination HTML ambiguë.')
        raw_items = parser.items
        next_url = urljoin(current, parser.next_links[0]) if parser.next_links else None
    else:
        raise WatchFetchError('Cette source nécessite un contrôle manuel.')
    header_next = _next_header(response.headers, current)
    if header_next and next_url and header_next != next_url:
        raise WatchFetchError('La page et son en-tête annoncent des suites différentes.')
    following = next_url or header_next
    if following:
        following = _url(following, json.loads(source['allowed_hosts_json']))
    return [_record(item, current, source, config) for item in raw_items], following


def _month(now, settings):
    return now.astimezone(ZoneInfo(settings.get('timezone') or 'Europe/Paris')).strftime('%Y-%m')


def _claim_run(engine, actor, source_id, trigger, now):
    with engine.begin() as conn:
        # Serialize source mutations/claims before reading decision or cursor state.
        conn.execute(text('UPDATE quality_watch_sources SET row_version=row_version WHERE id=:id AND organization_id=:o'),
                     {'id': int(source_id), 'o': _org(actor)})
        source = _source(conn, actor, source_id)
        if source['archived_at'] or not source['active'] or not source['configuration_validated'] or source['format'] == 'MANUAL':
            raise WatchError('Source inactive ou paramètres non validés : aucun appel réseau autorisé.')
        _assert_idle(conn, source, now)
        config = _parser_config(source['format'], json.loads(source['parser_config_json']), validated=True)
        limits = CollectionLimits(**config['limits'])
        settings = _one(conn, 'SELECT * FROM quality_watch_settings WHERE organization_id=:o', {'o': _org(actor)}) or {}
        cycle = _month(now, settings)
        if trigger == 'MONTHLY':
            if not settings.get('enabled') or not settings.get('configuration_validated'):
                raise WatchError('Le calendrier mensuel n’est pas activé et validé.')
            local_now = now.astimezone(ZoneInfo(settings['timezone']))
            due = local_now.replace(day=1, hour=settings['hour'], minute=settings['minute'], second=0, microsecond=0)
            if local_now < due or source['last_successful_month'] == cycle:
                return source, None, config, limits
        if source.get('lease_token'):
            conn.execute(text("""UPDATE quality_watch_runs SET status='INTERRUPTED',finished_at=:n,
                error='Collecte interrompue : réservation expirée, curseur conservé.'
                WHERE source_id=:s AND status='RUNNING'"""), {'s': source_id, 'n': now.isoformat()})
        point_zero = source['point_zero'] or now.isoformat()
        period_start = (_time(source['cursor_at']) - timedelta(days=source['overlap_days'])).isoformat() if source['cursor_at'] else point_zero
        token = uuid.uuid4().hex
        until = (now + timedelta(seconds=limits.max_run_seconds + 15)).isoformat()
        updated = conn.execute(text('''UPDATE quality_watch_sources SET lease_token=:token,lease_expires_at=:until,
            point_zero=:zero,last_attempt_at=:now,updated_at=:now,row_version=row_version+1
            WHERE id=:id AND organization_id=:o AND row_version=:version'''),
            {'token': token, 'until': until, 'zero': point_zero, 'now': now.isoformat(),
             'id': source_id, 'o': _org(actor), 'version': source['row_version']}).rowcount
        if not updated:
            raise WatchConflictError('La source a changé pendant le démarrage de la collecte.')
        fingerprint = _digest({'url': source['url'], 'format': source['format'], 'hosts': source['allowed_hosts_json'],
                               'config': config, 'overlap_days': source['overlap_days'], 'point_zero': point_zero})
        result = conn.execute(text('''INSERT INTO quality_watch_runs
          (source_id,organization_id,trigger,status,started_at,period_start_at,period_end_at,initial_run,
           lease_token,config_sha256,triggered_by)
          VALUES(:s,:o,:trigger,'RUNNING',:now,:start,:now,:initial,:token,:hash,:actor)'''),
          {'s': source_id, 'o': _org(actor), 'trigger': trigger, 'now': now.isoformat(),
           'start': period_start, 'initial': int(source['cursor_at'] is None), 'token': token,
           'hash': fingerprint, 'actor': _who(actor)})
        source['point_zero'] = point_zero
        source['lease_token'] = token
        source['lease_expires_at'] = until
        run = {'id': int(result.lastrowid), 'source_id': int(source_id), 'organization_id': _org(actor),
               'trigger': trigger, 'status': 'RUNNING', 'started_at': now.isoformat(),
               'period_start_at': period_start, 'period_end_at': now.isoformat(),
               'initial_run': source['cursor_at'] is None, 'lease_token': token, 'cycle': cycle}
    return source, run, config, limits


def _merge_record(records, record):
    old = records.get(record['id'])
    if old is None or old['content_sha256'] == record['content_sha256']:
        records[record['id']] = record
        return
    if old['updated_at'] and record['updated_at'] and old['updated_at'] != record['updated_at']:
        if _time(record['updated_at']) > _time(old['updated_at']):
            records[record['id']] = record
        return
    raise WatchFetchError('La source présente deux versions contradictoires du même identifiant dans une seule collecte.')


def _initial_reason(record, point_zero):
    zero = _time(point_zero)
    if record['is_reference']:
        return 'REFERENCE'
    if record['effective_at'] and _time(record['effective_at']) >= zero:
        return 'FUTURE_EFFECT'
    if record['published_at'] and _time(record['published_at']) >= zero:
        return 'SINCE_POINT_ZERO'
    if record['updated_at'] and _time(record['updated_at']) >= zero:
        return 'UPDATED_SINCE_POINT_ZERO'
    if not record['published_at'] and not record['updated_at']:
        return 'DATE_UNKNOWN_TO_REVIEW'
    return ''


def _store_records(conn, actor, source, run, records, discovered_at):
    counts = {'new_items': 0, 'new_versions': 0, 'unchanged': 0, 'ignored_before_zero': 0}
    for record in records.values():
        old = _one(conn, '''SELECT * FROM quality_watch_items WHERE source_id=:s AND item_key=:key
            ORDER BY version_no DESC LIMIT 1''', {'s': source['id'], 'key': record['id']})
        same = _one(conn, '''SELECT id FROM quality_watch_items WHERE source_id=:s AND item_key=:key AND content_sha256=:hash''',
                    {'s': source['id'], 'key': record['id'], 'hash': record['content_sha256']})
        if same:
            counts['unchanged'] += 1
            continue
        reason = _initial_reason(record, source['point_zero'])
        if not old and not reason:
            counts['ignored_before_zero'] += 1
            continue
        conn.execute(text('''INSERT INTO quality_watch_items
          (source_id,organization_id,item_key,version_no,supersedes_id,content_sha256,title,summary,url,
           published_at,updated_source_at,effective_at,is_reference,initial_reason,discovered_at,run_id,payload_json)
          VALUES(:source,:org,:key,:version,:old,:hash,:title,:summary,:url,:published,:updated,:effective,
                 :reference,:reason,:found,:run,:payload)'''),
          {'source': source['id'], 'org': _org(actor), 'key': record['id'], 'version': old['version_no'] + 1 if old else 1,
           'old': old['id'] if old else None, 'hash': record['content_sha256'], 'title': record['title'],
           'summary': record['summary'], 'url': record['url'], 'published': record['published_at'],
           'updated': record['updated_at'], 'effective': record['effective_at'], 'reference': int(record['is_reference']),
           'reason': reason or 'MODIFIED_EXISTING_ITEM', 'found': discovered_at,
           'run': run['id'], 'payload': record['payload_json']})
        counts['new_versions' if old else 'new_items'] += 1
    return counts


def _finish_run(engine, actor, source, run, records, pages, seen, bytes_read, finished_at, error=None):
    if error is None:
        _actor(engine, actor)  # Revocation during a slow fetch must prevent publishing its result.
    with engine.begin() as conn:
        conn.execute(text('UPDATE quality_watch_sources SET row_version=row_version WHERE id=:s AND organization_id=:o'),
                     {'s': source['id'], 'o': _org(actor)})
        current = _source(conn, actor, source['id'])
        if current['lease_token'] != run['lease_token']:
            raise WatchConflictError('Cette collecte a perdu sa réservation ; aucun résultat ni curseur n’a été appliqué.')
        counts = {'new_items': 0, 'new_versions': 0, 'unchanged': 0, 'ignored_before_zero': 0}
        if error is None:
            counts = _store_records(conn, actor, source, run, records, finished_at)
            conn.execute(text('''UPDATE quality_watch_sources SET last_success_at=:cursor,cursor_at=:cursor,
                last_error=NULL,last_successful_month=:month,lease_token=NULL,lease_expires_at=NULL,
                updated_at=:now,row_version=row_version+1 WHERE id=:id AND lease_token=:token'''),
                {'cursor': run['started_at'], 'month': run['cycle'], 'now': finished_at,
                 'id': source['id'], 'token': run['lease_token']})
        else:
            conn.execute(text('''UPDATE quality_watch_sources SET last_error=:error,
                lease_token=NULL,lease_expires_at=NULL,updated_at=:now,row_version=row_version+1
                WHERE id=:id AND lease_token=:token'''),
                {'error': error, 'now': finished_at, 'id': source['id'], 'token': run['lease_token']})
        conn.execute(text('''UPDATE quality_watch_runs SET status=:status,finished_at=:finished,pages=:pages,
            bytes_read=:bytes,items_seen=:seen,new_items=:new_items,new_versions=:new_versions,
            unchanged=:unchanged,ignored_before_zero=:ignored_before_zero,pages_json=:evidence,error=:error
            WHERE id=:id AND status='RUNNING' AND lease_token=:token'''),
            {**counts, 'status': 'ERROR' if error else 'SUCCESS', 'finished': finished_at, 'pages': len(pages),
             'bytes': bytes_read, 'seen': seen, 'evidence': _json(pages), 'error': error,
             'id': run['id'], 'token': run['lease_token']})
        _audit(conn, actor, 'COLLECTION_ERROR' if error else 'COLLECTION_SUCCEEDED', 'run', run['id'],
               {**counts, 'source_id': source['id'], 'pages': len(pages), 'cursor_advanced': error is None})
        result = _one(conn, 'SELECT * FROM quality_watch_runs WHERE id=:id', {'id': run['id']})
    result.pop('lease_token', None)
    result['pages_detail'] = json.loads(result.pop('pages_json'))
    return result


def collect_source(engine, actor, source_id, *, trigger='MANUAL', now=None, transport=None, resolver=None):
    """Collect one configured source. Failures are durable ERROR runs, never false success.

    ``transport`` and ``resolver`` are injectable offline test boundaries, never source
    configuration. Every target is validated/resolved even with a supplied transport.
    """
    actor = _actor(engine, actor)
    trigger = str(trigger).upper()
    if trigger not in ('MANUAL', 'MONTHLY'):
        raise WatchError('Mode de collecte invalide.')
    started = _time(now)
    monotonic_start = time.monotonic()
    source, run, config, limits = _claim_run(engine, actor, source_id, trigger, started)
    if run is None:
        return {'id': None, 'source_id': int(source_id), 'status': 'NOT_DUE', 'new_items': 0, 'new_versions': 0}
    deadline = monotonic_start + limits.max_run_seconds
    pages, records, visited = [], {}, set()
    seen = 0
    budget = {'used': 0}
    try:
        current = source['url']
        # Initial run MUST scan the declared feed, not a date-filtered "since now"
        # endpoint which would omit already published future-effect notices.
        if source['cursor_at'] and config.get('since_param'):
            p = urlsplit(current)
            params = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k != config['since_param']]
            params.append((config['since_param'], run['period_start_at']))
            current = urlunsplit((p.scheme, p.netloc, p.path, urlencode(params), ''))
        while current:
            if len(pages) >= limits.max_pages:
                raise WatchFetchError('Limite de pages atteinte avant la fin de la source : collecte incomplète.')
            if current in visited:
                raise WatchFetchError('Boucle de pagination détectée.')
            visited.add(current)
            final_url, response = _safe_fetch(current, source, limits, deadline, transport, resolver, budget)
            if final_url in visited and final_url != current:
                raise WatchFetchError('La redirection de pagination retourne une page déjà parcourue.')
            visited.add(final_url)
            page_items, following = _parse_page(final_url, response, source, config)
            seen += len(page_items)
            if seen > limits.max_items:
                raise WatchFetchError('La collecte dépasse le nombre d’informations autorisé.')
            pages.append({'url': final_url, 'status': response.status, 'bytes': len(response.body),
                          'sha256': hashlib.sha256(response.body).hexdigest(), 'items': len(page_items)})
            for item in page_items:
                _merge_record(records, item)
            if time.monotonic() >= deadline:
                raise WatchFetchError('Délai total de collecte dépassé.')
            current = following
        finished = (started + timedelta(seconds=time.monotonic() - monotonic_start)).isoformat()
        return _finish_run(engine, actor, source, run, records, pages, seen, budget['used'], finished)
    except WatchConflictError:
        raise
    except Exception as ex:
        message = str(ex) if isinstance(ex, WatchError) else 'Collecte interrompue par une erreur technique ; curseur conservé.'
        finished = (started + timedelta(seconds=time.monotonic() - monotonic_start)).isoformat()
        return _finish_run(engine, actor, source, run, {}, pages, seen, budget['used'], finished, message[:500])


def collect_due_sources(engine, actor, *, now=None, transport=None, resolver=None):
    """First-of-month schedule with catch-up after downtime; one cursor per source.

    The caller chooses an existing admin and organization. There is no process or
    scheduler at import. A failed source does not prevent independent sources running.
    """
    actor = _actor(engine, actor)
    at = _time(now)
    settings = get_schedule(engine, actor)
    if not settings['enabled'] or not settings['configuration_validated']:
        return []
    local = at.astimezone(ZoneInfo(settings['timezone']))
    due = local.replace(day=1, hour=settings['hour'], minute=settings['minute'], second=0, microsecond=0)
    if local < due:
        return []
    sources = list_sources(engine, actor)
    results = []
    for source in sources:
        if not source['active'] or not source['configuration_validated'] or source['last_successful_month'] == local.strftime('%Y-%m'):
            continue
        try:
            results.append(collect_source(engine, actor, source['id'], trigger='MONTHLY', now=at, transport=transport, resolver=resolver))
        except WatchBusyError as ex:
            results.append({'id': ex.run_id, 'source_id': source['id'], 'status': 'ALREADY_RUNNING'})
        except WatchError as ex:
            results.append({'id': None, 'source_id': source['id'], 'status': 'NOT_RUN', 'error': str(ex)})
    return results


def list_runs(engine, actor, source_id=None, limit=100):
    actor = _actor(engine, actor)
    limit = _integer(limit, 'Nombre de résultats', 1, 500)
    with engine.connect() as conn:
        if source_id is not None:
            _source(conn, actor, source_id)
        rows = conn.execute(text('''SELECT r.*,s.name source_name FROM quality_watch_runs r
            JOIN quality_watch_sources s ON s.id=r.source_id WHERE r.organization_id=:o'''
            + (' AND r.source_id=:s' if source_id is not None else '') + ' ORDER BY r.id DESC LIMIT :limit'),
            {'o': _org(actor), 's': source_id, 'limit': limit}).mappings()
        result = []
        for row in rows:
            item = dict(row)
            item.pop('lease_token', None)
            item['pages_detail'] = json.loads(item.pop('pages_json'))
            result.append(item)
        return result


def list_items(engine, actor, source_id=None, decision=None, include_superseded=False, limit=500):
    actor = _actor(engine, actor)
    limit = _integer(limit, 'Nombre de résultats', 1, 2000)
    if decision not in (None, 'ACTION', 'NO_ACTION', 'A_EXAMINER'):
        raise WatchError('Filtre de décision invalide.')
    conditions = ['i.organization_id=:o']
    if source_id is not None:
        conditions.append('i.source_id=:s')
    if not include_superseded:
        conditions.append('NOT EXISTS(SELECT 1 FROM quality_watch_items newer WHERE newer.source_id=i.source_id AND newer.item_key=i.item_key AND newer.version_no>i.version_no)')
    if decision:
        conditions.append("COALESCE(d.decision,'A_EXAMINER')=:decision")
    with engine.connect() as conn:
        if source_id is not None:
            _source(conn, actor, source_id)
        rows = conn.execute(text('''SELECT i.*,s.name source_name,s.category,s.scope,s.priority,
            COALESCE(d.decision,'A_EXAMINER') decision,d.reason decision_reason,d.id decision_id,
            COALESCE(d.action_id,l.action_id) action_id,d.decided_at,d.decided_by
            FROM quality_watch_items i JOIN quality_watch_sources s ON s.id=i.source_id
            LEFT JOIN quality_watch_decision_heads h ON h.item_id=i.id
            LEFT JOIN quality_watch_decisions d ON d.id=h.decision_id
            LEFT JOIN quality_watch_action_links l ON l.source_id=i.source_id AND l.item_key=i.item_key
            WHERE ''' + ' AND '.join(conditions) + ' ORDER BY i.discovered_at DESC,i.id DESC LIMIT :limit'),
            {'o': _org(actor), 's': source_id, 'decision': decision, 'limit': limit}).mappings()
        return [dict(r) for r in rows]


def list_decisions(engine, actor, *, source_id=None, decision=None, include_history=False, limit=500):
    actor = _actor(engine, actor)
    if decision not in (None, 'ACTION', 'NO_ACTION'):
        raise WatchError('Filtre de décision invalide.')
    limit = _integer(limit, 'Nombre de résultats', 1, 2000)
    conditions = ['d.organization_id=:o']
    if source_id is not None:
        conditions.append('i.source_id=:s')
    if decision:
        conditions.append('d.decision=:decision')
    if not include_history:
        conditions.append('h.decision_id=d.id')
    with engine.connect() as conn:
        if source_id is not None:
            _source(conn, actor, source_id)
        rows = conn.execute(text('''SELECT d.*,i.title,i.url,i.source_id,i.item_key,i.version_no,
            i.published_at,i.effective_at,s.name source_name,'CLOSED' status,
            CASE WHEN d.decision='NO_ACTION' THEN 'DECISION_WITHOUT_TASK' ELSE 'ACTION_REQUESTED' END outcome
            FROM quality_watch_decisions d JOIN quality_watch_items i ON i.id=d.item_id
            JOIN quality_watch_sources s ON s.id=i.source_id
            LEFT JOIN quality_watch_decision_heads h ON h.item_id=i.id
            WHERE ''' + ' AND '.join(conditions) + ' ORDER BY d.id DESC LIMIT :limit'),
            {'o': _org(actor), 's': source_id, 'decision': decision, 'limit': limit}).mappings()
        return [dict(r) for r in rows]


def _live_action(conn, action_id):
    event = _one(conn, 'SELECT id,deleted_at FROM quality_events WHERE id=:id', {'id': action_id}) if action_id else None
    if not event or event['deleted_at']:
        raise WatchConflictError('L’action associée a été retirée ; aucune tâche n’est recréée automatiquement.')
    return int(action_id)


def _draft_action(item):
    # The complete publication remains in its immutable source version. The
    # editable action draft respects the canonical service's field lengths.
    title = item['title'] if len(item['title']) <= 250 else item['title'][:249].rstrip() + '…'
    citation = ('\n\nSource : ' + item['url']
                + '\nPublication : ' + (item['published_at'] or 'À confirmer')
                + '\nApplication : ' + (item['effective_at'] or 'À confirmer'))
    budget = 10000 - len(citation)
    summary = item['summary']
    if len(summary) > budget:
        summary = summary[:budget - 1].rstrip() + '…'
    return title, summary + citation


def decide_item(engine, actor, item_id, *, decision, reason='', command_id, title=None,
                description=None, reconsider=False):
    """Atomic human decision; NO_ACTION creates no action and claims no work done."""
    actor = _actor(engine, actor)
    choice = str(decision).upper()
    if choice not in ('ACTION', 'NO_ACTION'):
        raise WatchError('Choisissez Action nécessaire ou Sans action nécessaire.')
    reason = _clean(reason, 'Motif', 4000, required=choice == 'NO_ACTION' or bool(reconsider))
    command_id = _clean(command_id, 'Identifiant de commande', 200, True)
    request = {'item_id': int(item_id), 'decision': choice, 'reason': reason, 'title': title,
               'description': description, 'reconsider': bool(reconsider), 'actor': _who(actor)}
    request_hash = _digest(request)
    with engine.begin() as conn:
        item = _one(conn, 'SELECT * FROM quality_watch_items WHERE id=:id AND organization_id=:o', {'id': int(item_id), 'o': _org(actor)})
        if not item:
            raise PermissionError('Information de veille inaccessible.')
        conn.execute(text('UPDATE quality_watch_sources SET row_version=row_version WHERE id=:s AND organization_id=:o'),
                     {'s': item['source_id'], 'o': _org(actor)})
        existing_command = _one(conn, 'SELECT * FROM quality_watch_decisions WHERE organization_id=:o AND command_id=:c', {'o': _org(actor), 'c': command_id})
        if existing_command:
            if existing_command['command_sha256'] != request_hash:
                raise WatchConflictError('Cet identifiant de commande a déjà servi à une autre décision.')
            if existing_command['decision'] == 'ACTION':
                _live_action(conn, existing_command['action_id'])
            return existing_command
        old = _one(conn, '''SELECT d.* FROM quality_watch_decision_heads h
            JOIN quality_watch_decisions d ON d.id=h.decision_id WHERE h.item_id=:i''', {'i': item_id})
        if old and not reconsider:
            if old['decision'] == choice and old['reason'] == reason:
                if choice == 'ACTION':
                    _live_action(conn, old['action_id'])
                return old
            raise WatchConflictError('Cette information a déjà été décidée ; un réexamen explicite et motivé est nécessaire.')
        link = _one(conn, 'SELECT * FROM quality_watch_action_links WHERE source_id=:s AND item_key=:key', {'s': item['source_id'], 'key': item['item_key']})
        event_id = None
        if choice == 'NO_ACTION' and link:
            raise WatchConflictError('Une action est déjà associée à cette information. Son suivi se traite dans le plan d’actions.')
        if choice == 'ACTION':
            if link:
                event_id = _live_action(conn, link['action_id'])
            else:
                from quality_service import _create_action_tx
                default_title, default_description = _draft_action(item)
                event_title = _clean(title if title is not None else default_title, 'Titre de l’action', 250, True)
                details = description if description is not None else default_description
                event_description = _clean(details, 'Description de l’action', 10000)
                event_id = _create_action_tx(conn, actor, event_title, event_description,
                    origin='VEILLE', nature='PREVENTIVE', action_id=None, classification='REAL',
                    command_id='watch:' + str(item['source_id']) + ':' + hashlib.sha256(item['item_key'].encode()).hexdigest())
                conn.execute(text('''INSERT INTO quality_watch_action_links(source_id,item_key,action_id,created_at)
                    VALUES(:s,:key,:e,:n)'''), {'s': item['source_id'], 'key': item['item_key'], 'e': event_id, 'n': _iso()})
        result = conn.execute(text('''INSERT INTO quality_watch_decisions
            (organization_id,item_id,decision,reason,action_id,prior_decision_id,command_id,command_sha256,decided_by,decided_at)
            VALUES(:o,:i,:decision,:reason,:event,:prior,:command,:hash,:actor,:at)'''),
            {'o': _org(actor), 'i': int(item_id), 'decision': choice, 'reason': reason, 'event': event_id,
             'prior': old['id'] if old else None, 'command': command_id, 'hash': request_hash, 'actor': _who(actor), 'at': _iso()})
        decision_id = int(result.lastrowid)
        conn.execute(text('''INSERT INTO quality_watch_decision_heads(item_id,decision_id) VALUES(:i,:d)
            ON CONFLICT(item_id) DO UPDATE SET decision_id=excluded.decision_id'''), {'i': item_id, 'd': decision_id})
        _audit(conn, actor, 'WATCH_DECISION', 'item', item_id,
               {'decision': choice, 'decision_id': decision_id, 'action_id': event_id, 'prior_decision_id': old['id'] if old else None})
        return _one(conn, 'SELECT * FROM quality_watch_decisions WHERE id=:id', {'id': decision_id})
