"""Check the shipped source files against RELEASE_MANIFEST.json, read-only."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root/'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
    errors = []
    for name, expected in manifest['files_sha256'].items():
        path = root/name
        if not path.resolve().is_relative_to(root) or path.is_symlink() or not path.is_file():
            errors.append(name + ': fichier manquant ou chemin inattendu')
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(name + ': contenu different du ZIP candidat')
    for error in errors: print('ECHEC', error)
    print('VERSION :', manifest['release'])
    print('FICHIERS CONTROLES :', len(manifest['files_sha256']))
    print('INTEGRITE :', 'OK' if not errors else 'ECHEC')
    return 1 if errors else 0

if __name__ == '__main__':
    raise SystemExit(main())
