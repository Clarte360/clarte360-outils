"""J9: French-first regional display settings. SQL evidence remains UTC/ISO.

Display conversion is deliberately separated from legal timestamps, the scheduler,
and the user's saved planning wall-clock values. Never localize stored proof data.
"""
from __future__ import annotations
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FORMATS_DATE = {'FR':'%d/%m/%Y', 'ISO':'%Y-%m-%d', 'US':'%m/%d/%Y'}
FORMATS_TIME = {'24H':'%H:%M', '12H':'%I:%M %p'}
DEFAULTS = {'timezone':'Europe/Paris','display_date_format':'FR',
            'display_time_format':'24H','display_language':'fr'}
LANGUAGES = ('fr','en')  # Metadata for future translations; UI texts remain French.

# Historical technical event types H2/H15 remain stable for old queues. Their delays
# are now configurable per organisation, in minutes before a Teams session starts.
REMINDER_DEFAULTS = {'online_reminder_first_minutes': 120,
                     'online_reminder_second_minutes': 15}
REMINDER_MAX_MINUTES = 10080  # seven days; no missing/zero/negative reminder delay


def validate_online_reminders(first_minutes, second_minutes):
    def integer_minutes(value):
        if isinstance(value, bool) or str(value).strip() != str(value):
            raise ValueError('Le délai doit être un nombre entier de minutes.')
        try:
            minute = int(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError('Le délai doit être un nombre entier de minutes.') from exc
        if isinstance(value, float) or minute < 1 or minute > REMINDER_MAX_MINUTES:
            raise ValueError('Chaque rappel doit être compris entre 1 et 10 080 minutes.')
        return minute

    first = integer_minutes(first_minutes)
    second = integer_minutes(second_minutes)
    if first <= second:
        raise ValueError('Le premier rappel doit précéder le deuxième (délai plus long).')
    return {'online_reminder_first_minutes': first,
            'online_reminder_second_minutes': second}


def online_reminders_from_org(org=None):
    org = org or {}
    raw = {k: org.get(k) if org.get(k) is not None else v
           for k, v in REMINDER_DEFAULTS.items()}
    try:
        return validate_online_reminders(raw['online_reminder_first_minutes'],
                                         raw['online_reminder_second_minutes'])
    except ValueError:
        return REMINDER_DEFAULTS.copy()


def format_online_reminder_delay(minutes):
    m = int(minutes)
    if m % 60 == 0:
        hours = m // 60
        return f'{hours} heure' if hours == 1 else f'{hours} heures'
    if m >= 60:
        return f'{m // 60} h {m % 60:02d}'
    return '1 minute' if m == 1 else f'{m} minutes'


def validate_preferences(*, timezone_name='Europe/Paris', date_format='FR', time_format='24H', language='fr'):
    zone = str(timezone_name or '').strip()
    try:
        if not zone or len(zone)>100: raise ValueError('Fuseau horaire invalide.')
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, KeyError, ValueError) as exc:
        raise ValueError('Fuseau horaire IANA inconnu.') from exc
    if date_format not in FORMATS_DATE: raise ValueError('Format de date inconnu.')
    if time_format not in FORMATS_TIME: raise ValueError("Format de l’heure inconnu.")
    if language not in LANGUAGES: raise ValueError('Langue inconnue.')
    return {'timezone':zone,'display_date_format':date_format,
            'display_time_format':time_format,'display_language':language}


def preferences_from_org(org=None):
    """Older databases use safe defaults; invalid legacy values cannot crash screens."""
    org=org or {}
    vals={k:org.get(k) or v for k,v in DEFAULTS.items()}
    try:return validate_preferences(timezone_name=vals['timezone'],date_format=vals['display_date_format'],
                                    time_format=vals['display_time_format'],language=vals['display_language'])
    except ValueError:return DEFAULTS.copy()


def parse_utc_timestamp(value):
    """Timestamp only: stored naive timestamps are UTC; dates without time excluded."""
    if isinstance(value,datetime): result=value
    elif isinstance(value,str):
        raw=value.strip()
        if not raw or ('T' not in raw and ' ' not in raw): raise ValueError('Horodatage attendu.')
        result=datetime.fromisoformat(raw.replace('Z','+00:00'))
    else:raise ValueError('Horodatage non pris en charge.')
    if result.tzinfo is None:result=result.replace(tzinfo=timezone.utc)
    return result


def format_timestamp(value, prefs=None, *, with_seconds=False):
    if value is None or value=='':return '—'
    prefs=preferences_from_org(prefs)
    try:
        dt=parse_utc_timestamp(value).astimezone(ZoneInfo(prefs['timezone']))
        d_fmt=FORMATS_DATE[prefs['display_date_format']]
        t_fmt=FORMATS_TIME[prefs['display_time_format']]
        if with_seconds:
            t_fmt = '%H:%M:%S' if t_fmt=='%H:%M' else '%I:%M:%S %p'
        return dt.strftime(d_fmt+' '+t_fmt)
    except (ValueError,TypeError,OverflowError):return '—'


def format_date(value,prefs=None):
    if value is None or value=='':return '—'
    prefs=preferences_from_org(prefs)
    try:
        if isinstance(value,datetime): d=value.date()
        elif isinstance(value,date):d=value
        else:d=date.fromisoformat(str(value).strip()[:10])
        return d.strftime(FORMATS_DATE[prefs['display_date_format']])
    except (TypeError,ValueError):return '—'


def format_wall_time(value,prefs=None):
    """Local schedule wall time, NOT a timestamp: no UTC conversion."""
    if value is None or value=='':return '—'
    prefs=preferences_from_org(prefs)
    try:
        t=value if isinstance(value,time) else time.fromisoformat(str(value))
        return t.strftime(FORMATS_TIME[prefs['display_time_format']])
    except (ValueError,TypeError):return '—'


def date_input_format(prefs=None):
    fmt=preferences_from_org(prefs)['display_date_format']
    return {'FR':'DD/MM/YYYY','ISO':'YYYY-MM-DD','US':'MM/DD/YYYY'}[fmt]


def safe_cell(value,kind,prefs=None):
    if kind=='timestamp':return format_timestamp(value,prefs)
    if kind=='date':return format_date(value,prefs)
    if kind=='time':return format_wall_time(value,prefs)
    raise ValueError('Type de date inconnu.')
