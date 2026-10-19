"""External pytest plugin for offline RC2 acceptance. Not included in application code."""
import json
import os
from pathlib import Path
import socket

attempts = []
reports = []
active_node = None


def _blocked(operation):
    def denied(*args, **kwargs):
        attempts.append({'operation': operation, 'test': active_node})
        raise RuntimeError('GO4_OFFLINE_GUARD: réseau interdit pendant la recette fictive')
    return denied


def pytest_configure(config):
    socket.socket.connect = _blocked('socket.connect')
    socket.socket.connect_ex = _blocked('socket.connect_ex')
    socket.create_connection = _blocked('socket.create_connection')
    socket.getaddrinfo = _blocked('socket.getaddrinfo')
    socket.gethostbyname = _blocked('socket.gethostbyname')
    socket.gethostbyname_ex = _blocked('socket.gethostbyname_ex')


def pytest_runtest_setup(item):
    global active_node
    active_node = item.nodeid


def pytest_runtest_logreport(report):
    reports.append({'nodeid': report.nodeid, 'when': report.when, 'outcome': report.outcome,
                    'duration': round(report.duration, 6), 'wasxfail': bool(getattr(report, 'wasxfail', False))})


def pytest_sessionfinish(session, exitstatus):
    output = os.environ.get('GO4_NETWORK_GUARD_LOG')
    if output:
        Path(output).write_text(json.dumps({'exitstatus': int(exitstatus), 'network_attempts_blocked': attempts,
                                           'reports': reports}, ensure_ascii=False, indent=2), encoding='utf-8')
