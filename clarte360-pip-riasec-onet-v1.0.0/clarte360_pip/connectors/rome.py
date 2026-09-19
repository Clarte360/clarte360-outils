from __future__ import annotations

from dataclasses import dataclass
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROME_REFERENCE_VERSION = 'ROME-RIASEC-2026-06'
DEFAULT_RUNTIME_PATH = ROOT / 'resources/runtime/rome_riasec_ROME-RIASEC-2026-06.json'


def _normalise_profile(value: str) -> str:
    raw = ''.join(ch for ch in str(value or '').upper() if ch in 'RIASEC')
    out = ''
    for ch in raw:
        if ch not in out:
            out += ch
    return out


@lru_cache(maxsize=4)
def _load_runtime(path_str: str) -> dict:
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f'Référentiel ROME/RIASEC runtime absent: {path}')
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('reference_version') != ROME_REFERENCE_VERSION:
        raise ValueError('Version du référentiel ROME/RIASEC inattendue.')
    return data


def two_letter_profile(indices: dict[str, float], order: list[str]) -> str | None:
    """Return a stable two-letter profile only when ranks 1 and 2 are unambiguous.

    Exact ties at the first rank or at the second/third boundary make a two-letter
    profile unjustified, so no automatic ROME exploration is produced.
    """
    if len(order) < 3:
        return None
    first, second, third = order[:3]
    try:
        s1, s2, s3 = float(indices[first]), float(indices[second]), float(indices[third])
    except (KeyError, TypeError, ValueError):
        return None
    if s1 == s2 or s2 == s3:
        return None
    return first + second


@dataclass(frozen=True)
class RomePort:
    source_path: Path | None = None

    @property
    def runtime_path(self) -> Path:
        return self.source_path or DEFAULT_RUNTIME_PATH

    @property
    def reference_version(self) -> str:
        return str(_load_runtime(str(self.runtime_path)).get('reference_version'))

    @property
    def source_date(self) -> str:
        return str(_load_runtime(str(self.runtime_path)).get('source_date') or '')

    def matching_profiles(self, riasec_profile: str) -> list[dict]:
        profile = _normalise_profile(riasec_profile)
        if len(profile) != 2:
            return []
        rows = _load_runtime(str(self.runtime_path)).get('records') or []
        return [dict(r) for r in rows if _normalise_profile(r.get('riasec_profile', '')) == profile]

    def explore_equivalent_profiles(self, riasec_profile: str, limit: int = 6) -> list[dict]:
        """Return a small, deterministic, diversified sample of exact 2-letter matches.

        This is an exploration list, never a compatibility ranking. To avoid returning
        six near-identical occupations from one ROME macro-domain, the sample first
        takes one fiche from distinct leading ROME letters, then fills any remaining
        slots by ROME code order. No score or recommendation is calculated.
        """
        if limit <= 0:
            return []
        candidates = sorted(self.matching_profiles(riasec_profile), key=lambda r: (r['rome_code'], r['title']))
        if not candidates:
            return []

        selected: list[dict] = []
        seen_codes: set[str] = set()
        seen_macro: set[str] = set()
        for row in candidates:
            macro = str(row.get('rome_code', ''))[:1]
            if macro and macro not in seen_macro:
                selected.append(row)
                seen_codes.add(row['rome_code'])
                seen_macro.add(macro)
                if len(selected) >= limit:
                    return selected
        for row in candidates:
            if row['rome_code'] in seen_codes:
                continue
            selected.append(row)
            if len(selected) >= limit:
                break
        return selected
