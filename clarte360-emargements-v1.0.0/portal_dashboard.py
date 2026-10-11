"""J7: cross-action welcome dashboards, strictly scoped to a logged-in identity.

Data access is computed server-side from authorized participations or Client grants.
A CRM ordering-customer link is NOT a grant and never appears in these predicates.
"""
from __future__ import annotations
from datetime import datetime
from zoneinfo import ZoneInfo
from db import q, one


def beneficiary_dashboard(engine, beneficiary_id, *, today=None):
    from services import beneficiary_participations, list_beneficiary_documents, list_tool_prescriptions, beneficiary_reports
    bid=int(beneficiary_id)
    actions=beneficiary_participations(engine,bid)
    from services import get_regional_preferences
    now=today or datetime.now(ZoneInfo(get_regional_preferences(engine)['timezone']))
    if isinstance(now,str): now=datetime.fromisoformat(now)
    current=now.strftime('%Y-%m-%d');clock=now.strftime('%H:%M')
    sessions=q(engine,"""SELECT DISTINCT s.id,s.action_id,a.action_no,a.title,s.slot_date,s.start_time,s.end_time
        FROM slots s JOIN actions a ON a.id=s.action_id JOIN participants p ON p.action_id=a.id
        WHERE p.beneficiary_id=:b AND p.active=1 AND s.status NOT IN ('ANNULE','REPORTE')
          AND (s.slot_date>:dt OR (s.slot_date=:dt AND s.end_time>=:tm))
        ORDER BY s.slot_date,s.start_time,s.id LIMIT 12""",{'b':bid,'dt':current,'tm':clock})
    pending=q(engine,"""SELECT qc.id,qc.action_id,a.action_no,t.title,qc.due_at
        FROM quality_campaigns qc JOIN participants p ON p.id=qc.participant_id
        JOIN actions a ON a.id=qc.action_id JOIN questionnaire_templates t ON t.id=qc.template_id
        WHERE p.beneficiary_id=:b AND p.active=1 AND qc.status NOT IN ('COMPLETED','CANCELLED','ANNULE')
        ORDER BY qc.due_at,qc.id""",{'b':bid})
    prescriptions=list_tool_prescriptions(engine,beneficiary_id=bid,include_cancelled=False)
    active_tools=[p for p in prescriptions if str(p.get('status') or '') not in ('TERMINE','ANNULE','CONSULTE')]
    signed=one(engine,"""SELECT COUNT(*) AS n FROM slots s JOIN participants p ON p.action_id=s.action_id
        LEFT JOIN signatures sg ON sg.slot_id=s.id AND sg.participant_id=p.id AND sg.status='VALIDE'
        LEFT JOIN attendance_status at ON at.slot_id=s.id AND at.participant_id=p.id
        WHERE p.beneficiary_id=:b AND p.active=1 AND s.status NOT IN ('ANNULE','REPORTE')
          AND (s.slot_date<:dt OR (s.slot_date=:dt AND s.end_time<:tm))
          AND sg.id IS NULL AND COALESCE(at.status,'') NOT IN ('NON_CONCERNE','ABSENT')""",
        {'b':bid,'dt':current,'tm':clock})
    docs=list_beneficiary_documents(engine,bid)
    reports=beneficiary_reports(engine,beneficiary_id=bid)
    return {'actions':actions,'upcoming':sessions,'pending_campaigns':pending,
      'pending_tools':active_tools,'signatures_to_review':int(signed['n'] or 0),
      'documents':docs,'reports':reports}


def client_dashboard(engine, account_id):
    """Only public organizational summaries, never beneficiaries, scores or free text."""
    from client_portal import list_client_actions, client_action_summary, client_public_schedule, list_client_documents
    aid=int(account_id)
    actions=list_client_actions(engine,aid)
    summaries=[];documents=0;next_sessions=[]
    for a in actions:
        summary=client_action_summary(engine,aid,a['id'])
        summaries.append(summary)
        if summary.get('can_download'):
            documents+=len(list_client_documents(engine,aid,a['id']))
        if summary.get('collective_training'):
            for slot in client_public_schedule(engine,aid,a['id']):
                next_sessions.append({'action_no':a['action_no'],'slot_date':slot['slot_date'],
                    'start_time':slot['start_time'],'end_time':slot['end_time']})
    next_sessions.sort(key=lambda row:(row['slot_date'],row['start_time']))
    return {'actions':actions,'summaries':summaries,'shared_documents':documents,
      'collective_sessions':next_sessions[:10],
      'active_actions':sum(str(x.get('status') or '').upper() in
        ('EN_COURS','ACTIVE','ACTIF','PLANIFIEE','PLANIFIE') for x in actions)}
