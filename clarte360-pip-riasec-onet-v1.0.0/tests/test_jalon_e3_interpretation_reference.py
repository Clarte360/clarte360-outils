import json
import subprocess
import sys
from pathlib import Path

from clarte360_pip.interpretation import INTERPRETATION_VERSION, interpret_pip, load_rules
from clarte360_pip.reporting_e1 import PIP_REPORT_VERSION

ROOT=Path(__file__).resolve().parents[1]


def test_e3_versions():
    assert INTERPRETATION_VERSION == 'PIP-INT-1.0'
    assert PIP_REPORT_VERSION == 'PIP-RPT-1.6'


def test_reference_runtime_is_synchronized():
    p=subprocess.run([sys.executable,str(ROOT/'scripts/build_interpretation_runtime.py'),'--check'],cwd=ROOT,capture_output=True,text=True)
    assert p.returncode == 0, p.stdout + p.stderr


def test_all_reference_examples_match_expected_rules():
    rules=load_rules()
    for row in rules['examples']:
        vals={d:float(row[d]) for d in 'RIASEC'}
        order=[x.strip() for x in str(row['ordre_attendu']).split(',')]
        result=interpret_pip(vals,order)
        assert result['scenario_rule_id'] == row['scenario_attendu'], row['case_id']
        assert result['shape']['relief'] == row['relief_attendu'], row['case_id']


def test_runtime_contains_no_onet_interpretation_rules():
    rules=load_rules()
    assert rules['interpretation_version']=='PIP-INT-1.0'
    assert all('O*NET' not in str(x.get('rule_id','')) for x in rules['bands'])
