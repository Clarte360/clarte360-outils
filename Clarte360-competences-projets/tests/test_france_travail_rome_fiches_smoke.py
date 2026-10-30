from __future__ import annotations

import sys
from datetime import datetime, timezone

from clarte360_cp.connectors.france_travail import RomeMetierSnapshot
from tools import test_france_travail_rome_fiches as smoke


def test_fiches_smoke_uses_its_own_scope_and_never_prints_credentials(tmp_path, monkeypatch, capsys):
    secret_file = tmp_path / "secrets.toml"
    secret_file.write_text(
        '[france_travail]\nclient_id="synthetic-id"\nclient_secret="synthetic-secret"\n'
        'rome_scope="rome-metiers-scope"\nrome_fiches_metiers_scope="fiches-scope"\n',
        encoding="utf-8",
    )
    received = {}

    def fake_fetch(self, code, *, force_refresh=False):
        received["scope"] = self.settings.rome_fiches_scope
        received["code"] = code
        received["force_refresh"] = force_refresh
        return RomeMetierSnapshot(
            code="M1203", payload={"fiche_metier": {"rome": {"intitule": "Comptable"}}},
            provider="FRANCE_TRAVAIL", resource_type="ROME_FICHE_METIER",
            fetched_at=datetime.now(timezone.utc), source_version="synthetic-v1", source_etag="synthetic-etag",
        )

    monkeypatch.setattr(smoke.FranceTravailRomeClient, "fetch_fiche_metier", fake_fetch)
    monkeypatch.setattr(sys, "argv", ["test_france_travail_rome_fiches.py", "--secrets", str(secret_file)])

    assert smoke.main() == 0
    output = capsys.readouterr().out
    assert "ROME Fiches métiers: OK" in output
    assert "Comptable" in output and "M1203" in output
    assert "synthetic-id" not in output and "synthetic-secret" not in output
    assert received == {"scope": "fiches-scope", "code": "M1203", "force_refresh": True}
