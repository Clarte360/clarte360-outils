from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from build_rome_catalog import build
except ImportError:
    from tools.build_rome_catalog import build


def _read_catalog(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError(f"Catalogue inexploitable : {path}")
    codes = [str(row.get("code", "")) for row in data["items"]]
    if not codes or len(codes) != len(set(codes)):
        raise ValueError(f"Le catalogue source contient des codes absents ou en doublon : {path}")
    return data


def _fingerprint(row: dict) -> str:
    raw = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def compare(old: dict, new: dict) -> dict:
    old_by_code = {row["code"]: row for row in old["items"]}
    new_by_code = {row["code"]: row for row in new["items"]}
    old_codes, new_codes = set(old_by_code), set(new_by_code)
    common = old_codes & new_codes
    changed = sorted(code for code in common
                     if _fingerprint(old_by_code[code]) != _fingerprint(new_by_code[code]))
    return {
        "old_version": old.get("version"),
        "new_version": new.get("version"),
        "old_date": old.get("publication_date"),
        "new_date": new.get("publication_date"),
        "old_count": len(old_codes),
        "new_count": len(new_codes),
        "added_codes": sorted(new_codes - old_codes),
        "removed_codes": sorted(old_codes - new_codes),
        "changed_codes": changed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare a new official ROME export with the packaged index; never overwrites the packaged index."
    )
    parser.add_argument("source_zip", type=Path, help="New official RefRomeXml.zip")
    parser.add_argument("--current", type=Path, default=Path("clarte360_cp/data/rome_catalog.json"))
    parser.add_argument("--version", required=True, help="Version officielle affichée dans le nouvel export.")
    parser.add_argument("--publication-date", required=True, help="Date de publication officielle (AAAA-MM-JJ).")
    parser.add_argument("--candidate-output", type=Path,
                        help="Write the rebuilt candidate here; this must not point at --current.")
    args = parser.parse_args()
    old = _read_catalog(args.current)
    new = build(args.source_zip, version=args.version, publication_date=args.publication_date)
    report = compare(old, new)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.candidate_output:
        if args.candidate_output.resolve() == args.current.resolve():
            raise SystemExit("Refus : le nouvel index doit être enregistré dans un fichier candidat séparé.")
        args.candidate_output.parent.mkdir(parents=True, exist_ok=True)
        args.candidate_output.write_text(
            json.dumps(new, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        print(f"Index candidat écrit : {args.candidate_output}")


if __name__ == "__main__":
    main()

