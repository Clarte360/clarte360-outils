from __future__ import annotations
import argparse, shutil, sqlite3, tempfile, zipfile
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
DB=DATA/'clarte360_emargements.db'

def validate_archive(path: Path):
    with zipfile.ZipFile(path) as z:
        names=set(z.namelist())
        if 'data/clarte360_emargements.db' not in names:
            raise ValueError('Archive invalide : base SQLite absente.')
        with tempfile.TemporaryDirectory() as td:
            z.extract('data/clarte360_emargements.db',td)
            test=sqlite3.connect(Path(td)/'data'/'clarte360_emargements.db')
            row=test.execute('PRAGMA integrity_check').fetchone(); test.close()
            if not row or row[0] != 'ok': raise ValueError('Archive invalide : integrity_check SQLite en échec.')
    return True

def restore(path: Path, keep_current=True):
    validate_archive(path)
    DATA.mkdir(parents=True,exist_ok=True)
    if keep_current and DB.exists():
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        safety=ROOT/'backups'/f'pre_restore_{stamp}.sqlite'
        safety.parent.mkdir(exist_ok=True)
        src=sqlite3.connect(DB); dst=sqlite3.connect(safety); src.backup(dst); dst.close(); src.close()
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(path) as z: z.extractall(td)
        extracted=Path(td)/'data'
        for folder in ('signatures','documents'):
            target=DATA/folder
            if target.exists(): shutil.rmtree(target)
            if (extracted/folder).exists(): shutil.copytree(extracted/folder,target)
        shutil.copy2(extracted/'clarte360_emargements.db',DB)
    con=sqlite3.connect(DB); ok=con.execute('PRAGMA integrity_check').fetchone()[0]; con.close()
    if ok!='ok': raise RuntimeError('Restauration effectuée mais base incohérente.')
    return DB

def main():
    ap=argparse.ArgumentParser(description='Restaure une sauvegarde Clarté360 Émargements après validation.')
    ap.add_argument('archive',type=Path)
    ap.add_argument('--no-safety-copy',action='store_true')
    ap.add_argument('--yes',action='store_true',help='Confirme explicitement la restauration destructive.')
    args=ap.parse_args()
    if not args.yes: raise SystemExit('Ajoutez --yes après avoir arrêté les services Streamlit et worker.')
    print(restore(args.archive,keep_current=not args.no_safety_copy))
if __name__=='__main__': main()
