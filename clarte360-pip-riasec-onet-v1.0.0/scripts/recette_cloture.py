"""Run the PIP regression suite on a temporary copy, never on live run data.
Usage: python scripts/recette_cloture.py
Uses the calling Python environment; installs nothing; changes no Git ref/service.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone


def main() -> int:
    app = Path(__file__).resolve().parents[1]
    report_dir = Path(tempfile.mkdtemp(prefix='clarte360_pip_rc3_tests_'))
    def ignore(folder, names):
        excluded = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache', 'data', 'secrets.toml'}
        return [name for name in names if name in excluded or name.startswith('data.backup') or (Path(folder)/name).is_symlink()]
    with tempfile.TemporaryDirectory(prefix='clarte360_pip_rc3_source_') as td:
        source = Path(td)/app.name
        shutil.copytree(app, source, ignore=ignore)
        env = dict(os.environ)
        env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(source),
                   CLARTE360_PIP_DATA_DIR=str(source/'data'),
                   CLARTE360_PIP_TEMP_DIR=str(Path(td)/'test_temp'))
        log = report_dir/'tests.log'
        command = [sys.executable, '-m', 'pytest', '-q', 'tests', '--tb=short',
                   '-p', 'no:cacheprovider', '--junitxml='+str(report_dir/'tests.xml')]
        with log.open('w', encoding='utf-8') as handle:
            completed = subprocess.run(command, cwd=source, env=env, stdout=handle, stderr=subprocess.STDOUT)
        text = log.read_text(encoding='utf-8')
        print(text)
    result = {'release': 'H3.3-D-RC3', 'date_utc': datetime.now(timezone.utc).isoformat(),
              'returncode': completed.returncode, 'python': sys.version,
              'production_mutated': False, 'gda_mutated': False,
              'scope': 'PIP tests on temporary synthetic data; no real SMTP, O*NET API or browser check'}
    (report_dir/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('RAPPORT :', report_dir)
    print('RECETTE LOCALE REUSSIE' if completed.returncode == 0 else 'RECETTE EN ECHEC - consulter tests.log')
    return completed.returncode

if __name__ == '__main__':
    raise SystemExit(main())
