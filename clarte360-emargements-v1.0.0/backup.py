from pathlib import Path
from datetime import datetime, timezone
import shutil, sqlite3, zipfile
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'; BACKUPS=ROOT/'backups'; BACKUPS.mkdir(exist_ok=True)
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
db=DATA/'clarte360_emargements.db'; out=BACKUPS/f'clarte360_emargements_{stamp}.zip'
if not db.exists(): raise SystemExit('Base SQLite introuvable')
tmp=BACKUPS/f'.db_{stamp}.sqlite'
src=sqlite3.connect(db); dst=sqlite3.connect(tmp); src.backup(dst); dst.close(); src.close()
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    z.write(tmp,'data/clarte360_emargements.db')
    for folder in ('signatures','documents'):
        p=DATA/folder
        if p.exists():
            for f in p.rglob('*'):
                if f.is_file(): z.write(f,f'data/{folder}/{f.relative_to(p)}')
tmp.unlink(missing_ok=True)
# retention 30 archives
for old in sorted(BACKUPS.glob('clarte360_emargements_*.zip'))[:-30]: old.unlink(missing_ok=True)
print(out)
