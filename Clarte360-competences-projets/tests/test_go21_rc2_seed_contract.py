from __future__ import annotations

from pathlib import Path


def test_demo_seed_contains_published_enriched_journey_artifact():
    text = Path("tools/go21_demo_seed.py").read_text(encoding="utf-8")
    assert 'artifact_type="PARCOURS_PRO_ENRICHI"' in text
    assert 'state="PUBLIE_POUR_RELECTURE"' in text
    assert '"assistance_ia":true' in text
