"""GO4: versioned survey measures and deliberately bounded Client publications.

The RC2 tables remain the source of invitations and answers. One campaign is one
invitation, not one question. V1 never substitutes an item average for an absent
global question. Historical campaigns without a frozen contract are explicitly
A_EXAMINER and are excluded from the default REAL report.

Public administration entry points validate QualityActor on every call. The
underscore snapshot helpers are integration hooks for the existing survey
creation transaction, not alternate authentication entry points.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import text

from db import audit, execute, one, q, utcnow_iso

METHOD_VERSION = 'CLARTE360_QUALITE_V1.0'
KINDS = ('HOT', 'COLD', 'TRAINER', 'CLIENT', 'PRESCRIBER', 'OPCO')
CLASSIFICATIONS = ('REAL', 'TEST', 'A_EXAMINER')
TERMINAL_CANCELLED = frozenset(('CANCELLED', 'ANNULE', 'ANNULEE'))
RUBRICS = {
    'R01': 'Information et objectifs', 'R02': 'Organisation',
    'R03': 'Moyens et environnement', 'R04': 'Supports et ressources',
    'R05': 'Intervenant / animation', 'R06': 'Adaptation et accompagnement',
    'R07': 'Accessibilité', 'R08': 'Atteinte des objectifs',
    'R09': 'Utilité / transfert', 'R10': 'Satisfaction globale',
    'R11': 'Recommandation', 'R12': 'Difficultés / réclamations',
    'I01': 'Information, préparation et coordination',
    'I02': 'Locaux, accès et moyens techniques',
    'I03': 'Ressources, supports et traçabilité',
    'I04': 'Organisation et conditions de réalisation',
    'I05': 'Adaptation et accessibilité', 'I06': 'Difficultés / aléas',
    'I07': 'Améliorations proposées',
}


def init_metrics_schema(conn):
    """Additive, repeatable initialization; never classifies historical data."""
    statements = [
        """CREATE TABLE IF NOT EXISTS quality_campaign_contracts (
            campaign_id INTEGER PRIMARY KEY,
            data_classification TEXT NOT NULL CHECK(data_classification IN ('REAL','TEST','A_EXAMINER')),
            method_version TEXT NOT NULL,
            template_id INTEGER NOT NULL, template_code TEXT NOT NULL,
            template_version TEXT NOT NULL, template_fingerprint TEXT NOT NULL,
            snapshot_json TEXT NOT NULL, snapshot_origin TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(campaign_id) REFERENCES quality_campaigns(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS quality_template_metric_rules (
            template_id INTEGER PRIMARY KEY, global_question_id INTEGER NOT NULL,
            created_at TEXT NOT NULL, created_by TEXT NOT NULL,
            FOREIGN KEY(template_id) REFERENCES questionnaire_templates(id) ON DELETE CASCADE,
            FOREIGN KEY(global_question_id) REFERENCES questionnaire_questions(id)
        )""",
        """CREATE TABLE IF NOT EXISTS quality_metric_policies (
            organization_id INTEGER PRIMARY KEY, method_version TEXT NOT NULL,
            positive_min INTEGER NOT NULL CHECK(positive_min BETWEEN 1 AND 5),
            min_distinct INTEGER NOT NULL CHECK(min_distinct>=5),
            client_enabled INTEGER NOT NULL DEFAULT 0,
            approved_at TEXT, approved_by TEXT, updated_at TEXT NOT NULL,
            FOREIGN KEY(organization_id) REFERENCES organizations(id)
        )""",
        """CREATE TABLE IF NOT EXISTS quality_client_publications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER NOT NULL,
            action_id INTEGER NOT NULL, campaign_kind TEXT NOT NULL CHECK(campaign_kind IN ('HOT','COLD')),
            payload_json TEXT NOT NULL, source_digest TEXT NOT NULL,
            policy_digest TEXT NOT NULL, published_at TEXT NOT NULL,
            published_by TEXT NOT NULL, revoked_at TEXT,
            UNIQUE(action_id,campaign_kind),
            FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE,
            FOREIGN KEY(organization_id) REFERENCES organizations(id)
        )""",
        """CREATE TRIGGER IF NOT EXISTS quality_contract_snapshot_immutable
            BEFORE UPDATE OF method_version,template_id,template_code,template_version,
                template_fingerprint,snapshot_json,snapshot_origin,created_at
            ON quality_campaign_contracts
            BEGIN SELECT RAISE(ABORT,'Questionnaire snapshot is immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS quality_publication_content_immutable
            BEFORE UPDATE OF organization_id,action_id,campaign_kind,payload_json,
                source_digest,policy_digest,published_at,published_by
            ON quality_client_publications
            BEGIN SELECT RAISE(ABORT,'Client publication is immutable'); END""",
    ]
    for statement in statements:
        conn.exec_driver_sql(statement)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _digest(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def _rows(conn, sql, params=None):
    return [dict(row) for row in conn.execute(text(sql), params or {}).mappings()]


def _actor_admin(engine, actor):
    from quality_service import require_admin
    return require_admin(engine, actor)


def _snapshot_campaign_tx(conn, campaign_id, classification='REAL'):
    if classification not in CLASSIFICATIONS:
        raise ValueError('Classification de campagne inconnue.')
    existing = _rows(conn, 'SELECT * FROM quality_campaign_contracts WHERE campaign_id=:c', {'c': campaign_id})
    if existing:
        return existing[0]
    rows = _rows(conn, """SELECT c.*,t.code template_code,t.version template_version,t.title template_title,a.organization_id
        FROM quality_campaigns c JOIN questionnaire_templates t ON t.id=c.template_id
        JOIN actions a ON a.id=c.action_id
        WHERE c.id=:c""", {'c': campaign_id})
    if not rows:
        raise ValueError('Campagne introuvable.')
    campaign = rows[0]
    questions = _rows(conn, """SELECT id,template_id,question_code,rubric_code,response_type,
        question_text,position,required,active FROM questionnaire_questions
        WHERE template_id=:t AND active=1 ORDER BY position,id""", {'t': campaign['template_id']})
    answers = _rows(conn, """SELECT question_id,rubric_code,response_type,question_text_snapshot
        FROM quality_responses WHERE campaign_id=:c""", {'c': campaign_id})
    origin = 'AT_CREATION'
    if answers:
        # A pre-existing answer has its own historical semantics. Its original
        # question code was not stored by RC2: do not invent it from a live model.
        origin = 'LEGACY_RESPONSE_SNAPSHOTS'
        saved = {a['question_id']: a for a in answers}
        known = {x['id'] for x in questions}
        for question in questions:
            previous = saved.get(question['id'])
            if previous:
                question.update(rubric_code=previous['rubric_code'],
                                response_type=previous['response_type'],
                                question_text=previous['question_text_snapshot'],
                                question_code=f"LEGACY-Q{question['id']}")
        for question_id, previous in saved.items():
            if question_id not in known:
                questions.append({'id': question_id, 'template_id': campaign['template_id'],
                    'question_code': f'LEGACY-Q{question_id}', 'rubric_code': previous['rubric_code'],
                    'response_type': previous['response_type'], 'question_text': previous['question_text_snapshot'],
                    'position': len(questions) + 1, 'required': 0, 'active': 1})
    rule = _rows(conn, 'SELECT global_question_id FROM quality_template_metric_rules WHERE template_id=:t',
                 {'t': campaign['template_id']})
    if rule and origin == 'AT_CREATION':
        global_ids = [x['id'] for x in questions if x['id'] == rule[0]['global_question_id'] and x['response_type'] == 'SCALE_1_5']
    else:
        global_ids = [x['id'] for x in questions if x['rubric_code'] == 'R10' and x['response_type'] == 'SCALE_1_5']
    # More than one global candidate is ambiguous, never an item average.
    snapshot = {'questions': questions, 'global_question_ids': global_ids,
                'template_title': campaign['template_title'] if origin == 'AT_CREATION' else 'Questionnaire historique — titre d’origine non attesté',
                'current_template_version_at_snapshot': campaign['template_version'],
                'action_id': campaign['action_id'], 'campaign_kind': campaign['campaign_kind'],
                'organization_id': campaign['organization_id'],
                'global_identification': 'EXPLICIT_RULE' if rule and origin == 'AT_CREATION' else 'UNIQUE_R10_SCALE_1_5'}
    fingerprint = _digest([{k: x.get(k) for k in ('question_code', 'rubric_code', 'response_type', 'question_text', 'required')}
                           for x in questions])
    params = {'c': campaign_id, 'cl': classification, 'm': METHOD_VERSION,
              't': campaign['template_id'], 'code': campaign['template_code'],
              'v': campaign['template_version'] if origin == 'AT_CREATION' else 'HISTORIQUE_NON_ATTESTEE',
              'f': fingerprint, 's': _json(snapshot),
              'origin': origin, 'now': utcnow_iso()}
    conn.execute(text("""INSERT OR IGNORE INTO quality_campaign_contracts(campaign_id,data_classification,
        method_version,template_id,template_code,template_version,template_fingerprint,snapshot_json,snapshot_origin,created_at)
        VALUES(:c,:cl,:m,:t,:code,:v,:f,:s,:origin,:now)"""), params)
    return _rows(conn, 'SELECT * FROM quality_campaign_contracts WHERE campaign_id=:c', {'c': campaign_id})[0]


def _snapshot_campaign(engine, campaign_id, classification='REAL'):
    """Creation hook; use the transaction variant when the caller owns one."""
    with engine.begin() as conn:
        return _snapshot_campaign_tx(conn, campaign_id, classification)


def campaign_questions(engine, campaign_id):
    """Frozen questions for the already-authorized survey/token entry point.

    Legacy rendering remains available and is not silently adopted into V1.
    The caller must validate its bound survey token before presenting answers.
    """
    contract = one(engine, 'SELECT snapshot_json FROM quality_campaign_contracts WHERE campaign_id=:c', {'c': campaign_id})
    if contract:
        return json.loads(contract['snapshot_json'])['questions']
    return q(engine, """SELECT qq.* FROM questionnaire_questions qq JOIN quality_campaigns c ON c.template_id=qq.template_id
        WHERE c.id=:c AND qq.active=1 ORDER BY qq.position,qq.id""", {'c': campaign_id})


def campaign_question(engine, campaign_id, question_id):
    for question in campaign_questions(engine, campaign_id):
        if question['id'] == question_id:
            return question
    raise ValueError('Question absente du questionnaire de cette campagne.')


def configure_template_measure(engine, actor, template_id, global_question_id):
    """Set an explicit global item only before any invitation uses the model."""
    actor = _actor_admin(engine, actor)
    row = one(engine, """SELECT t.organization_id,q.response_type FROM questionnaire_templates t
        JOIN questionnaire_questions q ON q.template_id=t.id WHERE t.id=:t AND q.id=:q""",
        {'t': template_id, 'q': global_question_id})
    if not row or row['organization_id'] != actor.organization_id:
        raise PermissionError('Modèle non autorisé dans cet organisme.')
    if row['response_type'] != 'SCALE_1_5':
        raise ValueError('La satisfaction globale nécessite une question sur cinq.')
    if one(engine, 'SELECT id FROM quality_campaigns WHERE template_id=:t LIMIT 1', {'t': template_id}):
        raise ValueError('Ce modèle est déjà utilisé : créer une nouvelle version avant de changer la mesure.')
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO quality_template_metric_rules(template_id,global_question_id,created_at,created_by)
            VALUES(:t,:q,:n,:a) ON CONFLICT(template_id) DO UPDATE SET global_question_id=excluded.global_question_id,
            created_at=excluded.created_at,created_by=excluded.created_by"""),
            {'t': template_id, 'q': global_question_id, 'n': utcnow_iso(), 'a': str(actor.subject_id)})
    audit(engine, 'QUALITY_GLOBAL_MEASURE_CONFIGURED', actor=str(actor.subject_id), entity_type='questionnaire_template', entity_id=template_id)


def classify_campaign(engine, actor, campaign_id, classification):
    """Explicit adoption/classification, with historical answer snapshots retained."""
    actor = _actor_admin(engine, actor)
    if classification not in CLASSIFICATIONS:
        raise ValueError('Classification de campagne inconnue.')
    campaign = one(engine, """SELECT c.id,a.organization_id FROM quality_campaigns c
        JOIN actions a ON a.id=c.action_id WHERE c.id=:c""", {'c': campaign_id})
    if not campaign or campaign['organization_id'] != actor.organization_id:
        raise PermissionError('Campagne non autorisée dans cet organisme.')
    with engine.begin() as conn:
        _snapshot_campaign_tx(conn, campaign_id, classification)
        conn.execute(text('UPDATE quality_campaign_contracts SET data_classification=:cl WHERE campaign_id=:c'),
                     {'cl': classification, 'c': campaign_id})
    audit(engine, 'QUALITY_CAMPAIGN_CLASSIFIED', actor=str(actor.subject_id), entity_type='quality_campaign',
          entity_id=campaign_id, details={'classification': classification})


def _policy(engine, organization_id):
    return one(engine, 'SELECT * FROM quality_metric_policies WHERE organization_id=:o', {'o': organization_id}) or {
        'organization_id': organization_id, 'method_version': METHOD_VERSION,
        'positive_min': 4, 'min_distinct': 5, 'client_enabled': 0,
        'approved_at': None, 'approved_by': None,
    }


def metric_policy(engine, actor):
    actor = _actor_admin(engine, actor)
    return _policy(engine, actor.organization_id)


def configure_metric_policy(engine, actor, *, positive_min=4, min_distinct=5, client_enabled=False, confirmed=False):
    actor = _actor_admin(engine, actor)
    if isinstance(positive_min, bool) or not isinstance(positive_min, int) or not 1 <= positive_min <= 5:
        raise ValueError('Le seuil positif doit être un entier de un à cinq.')
    if isinstance(min_distinct, bool) or not isinstance(min_distinct, int) or min_distinct < 5:
        raise ValueError('La publication Client GO4 conserve un minimum de cinq personnes distinctes.')
    if client_enabled and confirmed is not True:
        raise ValueError('Confirmer la méthode et le seuil avant d’activer une publication Client.')
    now = utcnow_iso()
    execute(engine, """INSERT INTO quality_metric_policies(organization_id,method_version,positive_min,min_distinct,
        client_enabled,approved_at,approved_by,updated_at) VALUES(:o,:m,:p,:d,:e,:at,:by,:n)
        ON CONFLICT(organization_id) DO UPDATE SET method_version=excluded.method_version,positive_min=excluded.positive_min,
        min_distinct=excluded.min_distinct,client_enabled=excluded.client_enabled,approved_at=excluded.approved_at,
        approved_by=excluded.approved_by,updated_at=excluded.updated_at""",
        {'o': actor.organization_id, 'm': METHOD_VERSION, 'p': positive_min, 'd': min_distinct,
         'e': int(bool(client_enabled)), 'at': now if confirmed is True else None,
         'by': str(actor.subject_id) if confirmed is True else None, 'n': now})
    audit(engine, 'QUALITY_METRIC_POLICY_SAVED', actor=str(actor.subject_id), entity_type='organization',
          entity_id=actor.organization_id, details={'positive_min': positive_min, 'min_distinct': min_distinct,
                                                  'client_enabled': bool(client_enabled), 'confirmed': confirmed is True})
    return _policy(engine, actor.organization_id)


def _method(policy):
    state = 'confirmés' if policy.get('approved_at') else 'proposés, à confirmer avant utilisation réelle'
    return (f"{METHOD_VERSION} — Questionnaires finalisés uniquement ; une question globale explicite sur cinq par questionnaire. "
            f"Satisfaction : globale ≥ {policy['positive_min']}/5 / globales valides. Retour : questionnaires finalisés parmi les "
            "invitations effectivement envoyées et ouvertes du même périmètre / ces invitations envoyées. "
            "Les invitations futures et annulées sont exclues de ce taux. REAL est la classification retenue par défaut ; "
            "tout périmètre d’essai ou d’examen demandé est explicitement affiché dans les filtres. Les thèmes font la moyenne des moyennes "
            "individuelles sur un jeu d’items comparable, sans arrondi intermédiaire. NPS distinct : %9–10 moins %0–6. "
            f"Seuils {state}. Le seuil Client est un choix interne de {policy['min_distinct']} personnes distinctes, pas une exigence Qualiopi.")


def _date(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _numeric(raw, response_type):
    """Return (valid number, anomaly); N/A/empty is an absence, never zero."""
    try:
        answer = json.loads(raw) if raw is not None else None
    except (ValueError, TypeError):
        return None, 'INVALID_JSON'
    if answer is None or answer == '' or answer == 'N/A':
        return None, None
    if response_type not in ('SCALE_1_5', 'NPS_0_10'):
        return None, None
    if isinstance(answer, bool) or not isinstance(answer, (int, float)):
        return None, 'INVALID_NUMERIC_ANSWER'
    value = float(answer)
    lower, upper = (1, 5) if response_type == 'SCALE_1_5' else (0, 10)
    if not math.isfinite(value) or not value.is_integer() or not lower <= value <= upper:
        return None, 'OUT_OF_RANGE_ANSWER'
    return value, None


def _identity(row):
    # Reuse the stable person reference, including across several formations.
    # A participation id or an email alias is not proof of a distinct person.
    # Missing identity means unknown, never an additional publishable person.
    for field, prefix in (('beneficiary_id', 'beneficiary'), ('trainer_id', 'trainer'), ('external_contact_id', 'contact')):
        if row.get(field) is not None:
            return f'{prefix}:{row[field]}'
    # A participant id belongs to one action, not to a reliably distinct person.
    return None


def _normalize_filters(organization_id, *, agency_id=None, prestation_type=None, action_id=None,
                       date_from=None, date_to=None, campaign_kinds=None, classification='REAL'):
    if classification is not None and classification not in CLASSIFICATIONS:
        raise ValueError('Classification de campagne inconnue.')
    if isinstance(campaign_kinds, str):
        campaign_kinds = (campaign_kinds,)
    kinds = tuple(dict.fromkeys(campaign_kinds or KINDS))
    if any(kind not in KINDS for kind in kinds):
        raise ValueError('Type de campagne Qualité inconnu.')
    for value in (date_from, date_to):
        if value is not None:
            try:
                datetime.strptime(str(value), '%Y-%m-%d')
            except (ValueError, TypeError):
                raise ValueError('La période attend des dates AAAA-MM-JJ.') from None
    if date_from and date_to and date_from > date_to:
        raise ValueError('La fin de période précède le début.')
    return {'organization_id': organization_id, 'agency_id': agency_id,
            'prestation_type': prestation_type, 'action_id': action_id,
            'date_from': date_from, 'date_to': date_to, 'campaign_kinds': list(kinds),
            'classification': classification,
            'period_basis': 'Date d’ouverture prévue du questionnaire (due_at), même cohorte pour les retours et les envois.',
            'population_basis': 'Invitations existantes : aucun effectif théorique de personnes éligibles n’est déduit du nombre de campagnes.'}


def _survey_data(engine, organization_id, **filters):
    now_arg = filters.pop('now', None)
    now = _date(now_arg) if now_arg else datetime.now(timezone.utc)
    if now is None:
        raise ValueError('Horloge de mesure invalide.')
    scope = _normalize_filters(organization_id, **filters)
    conditions = ['a.organization_id=:o']
    params = {'o': organization_id}
    for key, column in (('agency_id', 'a.agency_id'), ('prestation_type', 'a.prestation_type'), ('action_id', 'a.id')):
        if scope[key] is not None:
            conditions.append(f'{column}=:{key}'); params[key] = scope[key]
    if scope['date_from']:
        conditions.append('substr(c.due_at,1,10)>=:df'); params['df'] = scope['date_from']
    if scope['date_to']:
        conditions.append('substr(c.due_at,1,10)<=:dt'); params['dt'] = scope['date_to']
    if scope['classification'] is not None:
        conditions.append("COALESCE(ct.data_classification,'A_EXAMINER')=:cl"); params['cl'] = scope['classification']
    holders = ','.join(f':k{i}' for i, _ in enumerate(scope['campaign_kinds']))
    conditions.append(f'c.campaign_kind IN ({holders})')
    params.update({f'k{i}': kind for i, kind in enumerate(scope['campaign_kinds'])})
    campaigns = q(engine, """SELECT c.*,a.action_no,a.start_date action_start,a.end_date action_end,
        COALESCE(ct.data_classification,'A_EXAMINER') data_classification,ct.snapshot_json,
        ct.template_fingerprint,ct.template_version,ct.snapshot_origin,
        p.email participant_email,p.beneficiary_id,b.current_email beneficiary_email,
        tr.email trainer_email,cc.email contact_email
        FROM quality_campaigns c JOIN actions a ON a.id=c.action_id
        LEFT JOIN quality_campaign_contracts ct ON ct.campaign_id=c.id
        LEFT JOIN participants p ON p.id=c.participant_id
        LEFT JOIN beneficiaries b ON b.id=p.beneficiary_id
        LEFT JOIN trainers tr ON tr.id=c.trainer_id
        LEFT JOIN external_quality_contacts cc ON cc.id=c.external_contact_id
        WHERE """ + ' AND '.join(conditions) + ' ORDER BY c.id', params)
    ids = [x['id'] for x in campaigns]
    responses, sends = defaultdict(list), defaultdict(list)
    if ids:
        # Chunking avoids SQLite parameter limits for multi-year inventories.
        for offset in range(0, len(ids), 400):
            chunk = ids[offset:offset + 400]
            marks = ','.join(f':c{i}' for i, _ in enumerate(chunk))
            values = {f'c{i}': cid for i, cid in enumerate(chunk)}
            for row in q(engine, f'SELECT * FROM quality_responses WHERE campaign_id IN ({marks}) ORDER BY id', values):
                responses[row['campaign_id']].append(row)
            for row in q(engine, f"""SELECT campaign_id,sent_at FROM quality_email_events
                WHERE campaign_id IN ({marks}) AND event_type='INITIAL' AND status='SENT' AND sent_at IS NOT NULL""", values):
                sends[row['campaign_id']].append(row['sent_at'])
    policy = _policy(engine, organization_id)
    by_kind = {kind: {'score': None, 'satisfaction_rate': None, 'return_rate': None, 'n_global': 0,
        'completed': 0, 'completed_sent': 0, 'sent': 0, 'invitations': 0, 'planned': 0,
        'opened': 0, 'eligible_people': None, 'cancelled': 0, 'drafts': 0, 'distinct_respondents': 0,
        'unknown_respondents': 0, 'nps': None, 'n_nps': 0, 'anomalies': []} for kind in KINDS}
    values_by_kind, nps_by_kind = defaultdict(list), defaultdict(list)
    identities_by_kind, all_identities, nps_identities = defaultdict(set), defaultdict(set), defaultdict(set)
    unknown_all, unknown_nps, warnings = defaultdict(int), defaultdict(int), defaultdict(lambda: defaultdict(int))
    themes, questions = {}, {}
    campaign_rows = []
    answer_digest = []
    for campaign in campaigns:
        cid, kind = campaign['id'], campaign['campaign_kind']
        target = by_kind[kind]
        target['invitations'] += 1
        cancelled = str(campaign['status']).upper() in TERMINAL_CANCELLED
        due = _date(campaign.get('due_at'))
        future = due is not None and due > now
        eligible = due is not None and not future and not cancelled
        if due is None:
            warnings[kind]['INVALID_OPENING_DATE'] += 1
        evidence = sends[cid] + ([campaign['sent_at']] if campaign.get('sent_at') else [])
        sent = any(_date(value) is not None and _date(value) <= now for value in evidence) and eligible
        complete_time = _date(campaign.get('completed_at'))
        completed = campaign['status'] == 'COMPLETED' and eligible and (complete_time is None or complete_time <= now)
        if campaign['status'] == 'COMPLETED' and not completed:
            warnings[kind]['COMPLETED_OUTSIDE_OPEN_COHORT'] += 1
        if completed and not sent:
            warnings[kind]['COMPLETED_WITHOUT_SENT_EVIDENCE'] += 1
        target['planned'] += int(future and not cancelled)
        target['opened'] += int(eligible)
        target['cancelled'] += int(cancelled)
        target['sent'] += int(sent)
        target['completed'] += int(completed)
        target['completed_sent'] += int(completed and sent)
        target['drafts'] += int(bool(responses[cid]) and eligible and not completed)
        identity = _identity(campaign)
        if not cancelled:
            if identity:
                all_identities[kind].add(identity)
            else:
                unknown_all[kind] += 1
        stage = ('Annulée' if cancelled else 'Terminée' if completed else 'Prévue' if future
                 else 'En cours' if responses[cid] else 'Envoyée / ouverte' if sent else 'Ouverte, envoi non attesté')
        campaign_rows.append({'id': cid, 'action_id': campaign['action_id'], 'action_no': campaign['action_no'],
            'kind': kind, 'classification': campaign['data_classification'], 'status': stage,
            'due_at': campaign['due_at'], 'sent': sent, 'completed': completed,
            'template_version': campaign.get('template_version'), 'method_version': METHOD_VERSION})
        if not completed:
            continue
        if not campaign.get('snapshot_json'):
            warnings[kind]['UNVERIFIED_LEGACY_TEMPLATE'] += 1
            continue
        snapshot = json.loads(campaign['snapshot_json'])
        if campaign['snapshot_origin'] == 'LEGACY_RESPONSE_SNAPSHOTS':
            warnings[kind]['LEGACY_TEMPLATE_VERSION_UNVERIFIED'] += 1
        if (snapshot.get('action_id', campaign['action_id']) != campaign['action_id'] or
                snapshot.get('campaign_kind', kind) != kind or
                snapshot.get('organization_id', organization_id) != organization_id):
            warnings[kind]['CAMPAIGN_SCOPE_CHANGED'] += 1
            continue
        question_map = {item['id']: item for item in snapshot['questions']}
        global_ids = snapshot.get('global_question_ids', [])
        valid = {}
        for response in responses[cid]:
            question = question_map.get(response['question_id'])
            if question is None:
                warnings[kind]['QUESTION_OUTSIDE_SNAPSHOT'] += 1
                continue
            # The campaign contract is authoritative for new campaigns. An old
            # mismatch is an anomaly, not an invitation to reinterpret the row.
            if response['response_type'] != question['response_type'] or response['rubric_code'] != question['rubric_code'] or response['question_text_snapshot'] != question['question_text']:
                warnings[kind]['ANSWER_SNAPSHOT_MISMATCH'] += 1
                continue
            value, anomaly = _numeric(response['answer_json'], question['response_type'])
            if anomaly:
                warnings[kind][anomaly] += 1
            if value is not None:
                valid[question['id']] = value
            key = (kind, question['question_code'], question['rubric_code'], question['response_type'], question['question_text'])
            item = questions.setdefault(key, {'kind': kind, 'rubric_code': question['rubric_code'],
                'question_code': question['question_code'], 'question': question['question_text'],
                'response_type': question['response_type'], 'template_versions': set(), 'responses': 0,
                'valid_scores': 0, 'sum': 0.0, 'mean': None})
            item['template_versions'].add(campaign['template_version'])
            try:
                raw = json.loads(response['answer_json'])
            except (ValueError, TypeError):
                raw = None
            if raw is not None and raw != '' and raw != 'N/A' and raw != []:
                item['responses'] += 1
            if value is not None and question['response_type'] == 'SCALE_1_5':
                item['valid_scores'] += 1; item['sum'] += value
        if len(global_ids) != 1:
            warnings[kind]['MISSING_GLOBAL_QUESTION' if not global_ids else 'AMBIGUOUS_GLOBAL_QUESTION'] += 1
        elif global_ids[0] in valid:
            values_by_kind[kind].append(valid[global_ids[0]])
            if identity:
                identities_by_kind[kind].add(identity)
            else:
                target['unknown_respondents'] += 1
        nps_ids = [item['id'] for item in snapshot['questions'] if item['response_type'] == 'NPS_0_10']
        if len(nps_ids) == 1 and nps_ids[0] in valid:
            nps_by_kind[kind].append(valid[nps_ids[0]])
            if identity:
                nps_identities[kind].add(identity)
            else:
                unknown_nps[kind] += 1
        elif len(nps_ids) > 1:
            warnings[kind]['AMBIGUOUS_NPS_QUESTION'] += 1
        rubric_questions = defaultdict(list)
        for question in snapshot['questions']:
            if question['response_type'] == 'SCALE_1_5' and question['id'] not in global_ids:
                rubric_questions[question['rubric_code']].append(question)
        for rubric, items in rubric_questions.items():
            scores = [valid[item['id']] for item in items if item['id'] in valid]
            if not scores:
                continue
            signature = _digest(sorted((item['question_code'], item['response_type'], item['question_text']) for item in items))
            key = (kind, rubric, signature)
            item = themes.setdefault(key, {'kind': kind, 'rubric_code': rubric, 'label': RUBRICS.get(rubric, rubric),
                'item_set': signature[:12], 'template_versions': set(), 'questionnaires': 0,
                'items': 0, 'expected_items_per_questionnaire': len(items), '_individual_sum': 0.0, 'mean': None})
            item['template_versions'].add(campaign['template_version'])
            item['questionnaires'] += 1; item['items'] += len(scores)
            item['_individual_sum'] += sum(scores) / len(scores)
        answer_digest.append((cid, campaign['template_fingerprint'], sorted(valid.items())))
    for kind, bucket in by_kind.items():
        scores, nps = values_by_kind[kind], nps_by_kind[kind]
        bucket['n_global'] = len(scores)
        bucket['score'] = round(sum(scores) / len(scores), 2) if scores else None
        bucket['satisfaction_rate'] = round(100 * sum(x >= policy['positive_min'] for x in scores) / len(scores), 2) if scores else None
        bucket['return_rate'] = round(100 * bucket['completed_sent'] / bucket['sent'], 2) if bucket['sent'] else None
        bucket['distinct_respondents'] = len(identities_by_kind[kind])
        bucket['n_nps'] = len(nps)
        bucket['nps'] = round(100 * (sum(x >= 9 for x in nps) - sum(x <= 6 for x in nps)) / len(nps), 2) if nps else None
        bucket['anomalies'] = [f'{code} : {count}' for code, count in sorted(warnings[kind].items())]
    theme_rows = []
    for item in themes.values():
        item['mean'] = round(item.pop('_individual_sum') / item['questionnaires'], 2)
        item['template_versions'] = sorted(item['template_versions'])
        item['template_version'] = ', '.join(item['template_versions'])
        theme_rows.append(item)
    question_rows = []
    for item in questions.values():
        item['mean'] = round(item['sum'] / item['valid_scores'], 2) if item['valid_scores'] else None
        item['template_versions'] = sorted(item['template_versions'])
        question_rows.append(item)
    return {'method_version': METHOD_VERSION, 'method': _method(policy),
        'method_confirmed': bool(policy.get('approved_at')), 'scope': scope, 'by_kind': by_kind,
        'themes': sorted(theme_rows, key=lambda row: (row['kind'], row['rubric_code'], row['item_set'])),
        'questions': sorted(question_rows, key=lambda row: (row['kind'], row['rubric_code'], row['question_code'], row['question'])),
        'campaigns': campaign_rows,
        'anomalies': [f'{kind} — {message}' for kind in KINDS for message in by_kind[kind]['anomalies']],
        'generated_at': now.isoformat(), 'distinct_respondents': len(set().union(*identities_by_kind.values())) if identities_by_kind else 0,
        '_private': {'respondents': identities_by_kind, 'cohort': all_identities, 'unknown_cohort': unknown_all,
                     'nps_respondents': nps_identities, 'unknown_nps': unknown_nps,
                     'source_digest': _digest(answer_digest), 'policy': policy}}


def survey_dashboard(engine, actor, *, agency_id=None, prestation_type=None, action_id=None,
                     date_from=None, date_to=None, campaign_kinds=None, classification='REAL'):
    actor = _actor_admin(engine, actor)
    if action_id is not None:
        action = one(engine, 'SELECT organization_id FROM actions WHERE id=:a', {'a': action_id})
        if not action or action['organization_id'] != actor.organization_id:
            raise PermissionError('Action non autorisée dans cet organisme.')
    result = _survey_data(engine, actor.organization_id, agency_id=agency_id, prestation_type=prestation_type,
                          action_id=action_id, date_from=date_from, date_to=date_to,
                          campaign_kinds=campaign_kinds, classification=classification)
    result.pop('_private')
    return result


def export_survey_csv(engine, actor, **filters):
    """Exactly the authorized dashboard scope; no respondent identities/comments."""
    view = survey_dashboard(engine, actor, **filters)
    output = io.StringIO(newline='')
    writer = csv.writer(output, delimiter=';')
    def write(cells):
        writer.writerow([_safe_csv_cell(value) for value in cells])
    write(['Date du calcul', view['generated_at']])
    write(['Méthode', view['method']])
    write(['Filtres', _json(view['scope'])])
    write(['Famille', 'Moyenne globale /5', 'Satisfaction %', 'Globales valides', 'Personnes distinctes',
                     'Finalisés', 'Envoyés', 'Finalisés parmi envoyés', 'Retour %', 'Prévus futurs', 'NPS', 'Effectif NPS'])
    for kind in view['scope']['campaign_kinds']:
        row = view['by_kind'][kind]
        write([kind, row['score'], row['satisfaction_rate'], row['n_global'], row['distinct_respondents'],
                         row['completed'], row['sent'], row['completed_sent'], row['return_rate'], row['planned'], row['nps'], row['n_nps']])
    write([])
    write(['Famille', 'Thème', 'Versions', 'Jeu d’items', 'Questionnaires', 'Items valides', 'Moyenne individuelle du thème /5'])
    for row in view['themes']:
        write([row['kind'], row['label'], row['template_version'], row['item_set'], row['questionnaires'], row['items'], row['mean']])
    write([])
    write(['Anomalies'])
    for warning in view['anomalies']:
        write([warning])
    return ('\ufeff' + output.getvalue()).encode('utf-8')


def _safe_csv_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def _policy_digest(policy):
    return _digest({key: policy[key] for key in ('method_version', 'positive_min', 'min_distinct')})


def publish_client_satisfaction(engine, actor, action_id, campaign_kind='HOT', *, confirmed=False):
    """Publish one immutable, fixed action/family aggregate after administration review.

    No arbitrary subset is accepted. Completed actions only, known identities,
    minimum distinct responders, and small complementary groups are checked.
    A changed second publication is rejected to prevent differencing attacks.
    Nothing is emailed; an existing explicit Client grant is still required.
    """
    actor = _actor_admin(engine, actor)
    if confirmed is not True:
        raise ValueError('Confirmer la publication de cet agrégat fixe.')
    if campaign_kind not in ('HOT', 'COLD'):
        raise ValueError('Seules les satisfactions bénéficiaires HOT/COLD peuvent être publiées au Client.')
    from client_portal import _is_individual_action
    action = one(engine, 'SELECT * FROM actions WHERE id=:a', {'a': action_id})
    if not action or action['organization_id'] != actor.organization_id:
        raise PermissionError('Action non autorisée dans cet organisme.')
    if _is_individual_action(action) or str(action.get('prestation_type') or '').upper() != 'FORMATION':
        raise PermissionError('Agrégat non communicable pour cette prestation.')
    if action['status'] not in ('CLOTUREE', 'ARCHIVEE', 'TERMINEE'):
        raise ValueError('Clôturer la formation avant de publier son agrégat fixe.')
    data = _survey_data(engine, actor.organization_id, action_id=action_id, campaign_kinds=(campaign_kind,))
    private, bucket = data['_private'], data['by_kind'][campaign_kind]
    policy = private['policy']
    if not policy.get('approved_at') or not policy.get('client_enabled'):
        raise ValueError('La méthode et la politique de publication Client doivent être confirmées et activées.')
    respondents = private['respondents'][campaign_kind]
    cohort = set(private['cohort'][campaign_kind])
    unknown = private['unknown_cohort'][campaign_kind]
    # The formation roster can reveal a complementary group even when a
    # questionnaire was never generated for its members.
    for participant in q(engine, """SELECT p.email participant_email,p.beneficiary_id,b.current_email beneficiary_email
            FROM participants p LEFT JOIN beneficiaries b ON b.id=p.beneficiary_id
            WHERE p.action_id=:a AND p.active=1""", {'a': action_id}):
        person = _identity(participant)
        if person:
            cohort.add(person)
        else:
            unknown += 1
    minimum = policy['min_distinct']
    complement = len(cohort - respondents)
    if len(respondents) < minimum or unknown or (0 < complement < minimum):
        raise ValueError('Agrégat protégé : effectif distinct ou groupe complémentaire insuffisant, ou identités non fiabilisées.')
    if bucket['planned'] or bucket['drafts'] or bucket['unknown_respondents'] or bucket['anomalies']:
        raise ValueError('Terminer et vérifier la cohorte avant sa publication Client.')
    now = utcnow_iso()
    payload = {key: bucket[key] for key in ('score', 'satisfaction_rate', 'n_global', 'distinct_respondents',
               'sent', 'completed', 'completed_sent', 'return_rate', 'nps', 'n_nps')}
    # NPS has its own respondents: five global answers do not anonymize a
    # single NPS answer. Withheld NPS does not reveal its small exact effectif.
    nps_people = private['nps_respondents'][campaign_kind]
    nps_complement = len(cohort - nps_people)
    if len(nps_people) < minimum or private['unknown_nps'][campaign_kind] or 0 < nps_complement < minimum:
        payload.update(nps=None, n_nps=None, nps_status='PROTECTED')
    else:
        payload['nps_status'] = 'AVAILABLE'
    payload.update(status='AVAILABLE', message='Agrégat fixe publié pour cette formation et cette famille.',
                   action_id=action_id, campaign_kind=campaign_kind,
                   period={'date_from': action.get('start_date'), 'date_to': action.get('end_date'),
                           'basis': 'Formation complète ; publication fixe, aucun filtre de sous-groupe.'},
                   method=data['method'], method_version=METHOD_VERSION, published_at=now)
    existing = one(engine, 'SELECT * FROM quality_client_publications WHERE action_id=:a AND campaign_kind=:k',
                   {'a': action_id, 'k': campaign_kind})
    if existing:
        if existing['source_digest'] == private['source_digest'] and existing['policy_digest'] == _policy_digest(policy) and not existing['revoked_at']:
            return json.loads(existing['payload_json'])
        raise ValueError('Ce périmètre possède déjà une publication fixe : une mise à jour pourrait permettre de déduire une réponse individuelle.')
    execute(engine, """INSERT INTO quality_client_publications(organization_id,action_id,campaign_kind,payload_json,
        source_digest,policy_digest,published_at,published_by) VALUES(:o,:a,:k,:p,:s,:d,:n,:by)""",
        {'o': actor.organization_id, 'a': action_id, 'k': campaign_kind, 'p': _json(payload),
         's': private['source_digest'], 'd': _policy_digest(policy), 'n': now, 'by': str(actor.subject_id)})
    audit(engine, 'QUALITY_CLIENT_AGGREGATE_PUBLISHED', action_id, str(actor.subject_id), 'action', action_id,
          {'kind': campaign_kind, 'method_version': METHOD_VERSION})
    return payload


def revoke_client_satisfaction(engine, actor, action_id, campaign_kind='HOT'):
    actor = _actor_admin(engine, actor)
    row = one(engine, 'SELECT organization_id FROM actions WHERE id=:a', {'a': action_id})
    if not row or row['organization_id'] != actor.organization_id:
        raise PermissionError('Action non autorisée dans cet organisme.')
    execute(engine, """UPDATE quality_client_publications SET revoked_at=COALESCE(revoked_at,:n)
        WHERE action_id=:a AND campaign_kind=:k""", {'a': action_id, 'k': campaign_kind, 'n': utcnow_iso()})
    audit(engine, 'QUALITY_CLIENT_AGGREGATE_REVOKED', action_id, str(actor.subject_id), 'action', action_id, {'kind': campaign_kind})


def _client_publication(engine, account_id, action_id, campaign_kind='HOT'):
    from client_portal import client_action_permission, _is_individual_action
    action, _ = client_action_permission(engine, account_id, action_id)
    if not one(engine, 'SELECT id FROM organizations WHERE id=:o AND active=1', {'o': action.get('organization_id')}):
        return {'status': 'PROTECTED', 'message': 'Satisfaction non communicable pour ce périmètre.'}
    if campaign_kind not in ('HOT', 'COLD') or _is_individual_action(action) or str(action.get('prestation_type') or '').upper() != 'FORMATION':
        return {'status': 'PROTECTED', 'message': 'Satisfaction non communicable pour ce périmètre.'}
    policy = _policy(engine, action.get('organization_id'))
    if not policy.get('approved_at') or not policy.get('client_enabled'):
        return {'status': 'DISABLED', 'message': 'La publication des agrégats de satisfaction n’est pas activée.'}
    row = one(engine, """SELECT payload_json,policy_digest,revoked_at FROM quality_client_publications
        WHERE action_id=:a AND campaign_kind=:k""", {'a': action_id, 'k': campaign_kind})
    if not row or row['revoked_at'] or row['policy_digest'] != _policy_digest(policy):
        return {'status': 'NOT_PUBLISHED', 'message': 'Aucun agrégat communicable n’a été publié pour cette formation et cette famille.'}
    return json.loads(row['payload_json'])
