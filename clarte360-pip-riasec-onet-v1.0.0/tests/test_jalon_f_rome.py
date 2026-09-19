import subprocess
import sys
from pathlib import Path

from clarte360_pip.connectors.rome import RomePort, ROME_REFERENCE_VERSION, two_letter_profile
from clarte360_pip.reporting import PIP_REPORT_VERSION, build_pip_report_pdf
from clarte360_pip.pip_data.loader import load_pip_bank

ROOT = Path(__file__).resolve().parents[1]


def sample():
    bank = load_pip_bank()
    answers = {x['item_id']: 3 for x in bank['items']}
    return {
        'pip_state': {'answers': answers, 'bank_version': bank['bank_version']},
        'pip_scoring': {
            'complete': True,
            'indices': {'E': 82, 'C': 74, 'S': 58, 'A': 45, 'I': 40, 'R': 35},
            'order': ['E', 'C', 'S', 'A', 'I', 'R'],
            'holland_code': 'ECS',
            'algorithm_version': 'PIP-SCORE-0.5',
        },
    }


def test_rome_runtime_is_synchronized():
    p = subprocess.run([sys.executable, str(ROOT/'scripts/build_rome_runtime.py'), '--check'], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    assert '1911 fiches' in p.stdout


def test_reference_version_and_exact_profile_counts():
    port = RomePort()
    assert port.reference_version == ROME_REFERENCE_VERSION == 'ROME-RIASEC-2026-06'
    ec = port.matching_profiles('EC')
    assert len(ec) == 170
    assert all(x['riasec_profile'] == 'EC' for x in ec)


def test_exploration_is_limited_deterministic_and_not_scored():
    port = RomePort()
    a = port.explore_equivalent_profiles('EC', limit=6)
    b = port.explore_equivalent_profiles('EC', limit=6)
    assert a == b
    assert len(a) == 6
    assert len({x['rome_code'] for x in a}) == 6
    assert all('score' not in x and 'compat' not in x for x in a)
    # The diversification rule should use several ROME macro-domains when available.
    assert len({x['rome_code'][0] for x in a}) >= 3


def test_two_letter_profile_is_not_forced_on_ties():
    assert two_letter_profile({'E':82,'C':74,'S':58}, ['E','C','S']) == 'EC'
    assert two_letter_profile({'E':82,'C':82,'S':58}, ['E','C','S']) is None
    assert two_letter_profile({'E':82,'C':74,'S':74}, ['E','C','S']) is None


def test_pip_report_f_contains_rome_section_and_version():
    pdf = build_pip_report_pdf(sample())
    assert pdf.startswith(b'%PDF')
    assert len(pdf) > 15000
    assert PIP_REPORT_VERSION == 'PIP-RPT-1.6'
