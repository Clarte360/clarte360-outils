from pathlib import Path
import re


def test_datetime_time_not_shadowed_by_services_star_import():
    app = Path(__file__).resolve().parents[1] / 'app.py'
    src = app.read_text(encoding='utf-8')
    assert 'from datetime import date, datetime, time as dt_time' in src
    assert not re.search(r'(?<![A-Za-z0-9_])time\.fromisoformat\(', src)
    assert 'dt_time.fromisoformat(' in src
