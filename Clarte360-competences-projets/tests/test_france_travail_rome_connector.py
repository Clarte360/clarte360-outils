from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from io import BytesIO

import pytest

from clarte360_cp.connectors.france_travail import (
    FranceTravailConfigurationError,
    FranceTravailHttpError,
    FranceTravailRomeClient,
    FranceTravailSettings,
    FranceTravailTransportError,
)


class FakeResponse:
    def __init__(self, payload, headers=None):
        self._body = json.dumps(payload).encode("utf-8")
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._body


def settings():
    return FranceTravailSettings(
        client_id="synthetic-client-id",
        client_secret="synthetic-client-secret",
        rome_scope="synthetic-rome-scope",
    )


def test_scope_is_required_but_never_read_from_or_confused_with_secret():
    with pytest.raises(FranceTravailConfigurationError, match="scope ROME"):
        FranceTravailSettings.from_mapping({"client_id": "id", "client_secret": "secret"})


def test_all_four_rome_product_scopes_are_loaded_independently():
    configured = FranceTravailSettings.from_mapping({
        "client_id": "synthetic-id", "client_secret": "synthetic-secret",
        "rome_scope": "scope-metiers", "rome_competences_scope": "scope-competences",
        "rome_contextes_scope": "scope-contextes", "rome_fiches_metiers_scope": "scope-fiches",
    })
    assert configured.rome_scope == "scope-metiers"
    assert configured.rome_competences_scope == "scope-competences"
    assert configured.rome_contextes_scope == "scope-contextes"
    assert configured.rome_fiches_scope == "scope-fiches"


def test_fiches_product_can_be_configured_without_the_separate_metiers_scope():
    calls = []

    def opener(request, timeout):
        calls.append(request)
        if request.method == "POST":
            return FakeResponse({"access_token": "synthetic-fiche-token", "expires_in": 3600})
        return FakeResponse({"rome": {"code_rome": "M1203", "intitule": "Comptable"},
                             "competences": {"savoirs": []}})

    configured = FranceTravailSettings.from_mapping({
        "client_id": "synthetic-id", "client_secret": "synthetic-secret",
        "rome_fiches_metiers_scope": "only-fiches-scope",
    })
    client = FranceTravailRomeClient(configured, opener=opener)
    result = client.fetch_fiche_metier("M1203", force_refresh=True)
    assert configured.rome_scope == ""
    assert b"scope=only-fiches-scope" in calls[0].data
    assert result.code == "M1203"

    with pytest.raises(FranceTravailConfigurationError, match="Scope France Travail"):
        client.fetch_metier("M1203")


def test_fetch_metier_uses_oauth_scope_and_returns_provenance_without_extra_token_calls():
    calls = []
    clock_values = iter([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])

    def opener(request, timeout):
        calls.append((request, timeout))
        if request.method == "POST":
            return FakeResponse({"access_token": "synthetic-access-token", "expires_in": 3600})
        return FakeResponse(
            {"code": "M1203", "intitule": "Comptable", "version": "ROME-4.0-test"},
            {"ETag": '"synthetic-etag"'},
        )

    client = FranceTravailRomeClient(
        settings(), opener=opener, monotonic=lambda: next(clock_values),
        clock=lambda: datetime(2026, 10, 23, tzinfo=timezone.utc),
    )
    result = client.fetch_metier("m1203", force_refresh=True)

    assert len(calls) == 2
    token_request, _ = calls[0]
    api_request, _ = calls[1]
    assert token_request.method == "POST"
    assert b"scope=synthetic-rome-scope" in token_request.data
    assert api_request.full_url.endswith("/v1/metiers/metier/M1203")
    assert api_request.get_header("Authorization") == "Bearer synthetic-access-token"
    assert result.code == "M1203"
    assert result.payload["intitule"] == "Comptable"
    assert result.provider == "FRANCE_TRAVAIL"
    assert result.resource_type == "ROME_METIER"
    assert result.source_version == "ROME-4.0-test"
    assert result.source_etag == '"synthetic-etag"'


def test_search_metiers_uses_documented_autocomplete_route_and_query_parameters():
    calls = []

    def opener(request, timeout):
        calls.append(request)
        if request.method == "POST":
            return FakeResponse({"access_token": "synthetic-access-token", "expires_in": 3600})
        if urlparse(request.full_url).path.endswith("/appellation/requete"):
            return FakeResponse({"totalResultats": 1, "requete": "comptable", "resultats": [
                {"code": "12345", "libelle": "Comptable général", "metier": {"code": "M1203", "libelle": "Comptabilité"}},
            ]})
        return FakeResponse({"totalResultats": 2, "requete": "comptable", "resultats": [
            {"code": "M1203", "libelle": "Comptabilité"},
            {"code": "M1204", "libelle": "Contrôle de gestion"},
            {"code": "not-a-code", "libelle": "Valeur invalide"},
        ]})

    client = FranceTravailRomeClient(settings(), opener=opener)
    results = client.search_metiers("comptable", limit=2)
    assert len(calls) == 3
    métier_request, appellation_request = calls[1:]
    parsed = urlparse(métier_request.full_url)
    assert parsed.path.endswith("/v1/metiers/metier/requete")
    assert parse_qs(parsed.query) == {"q": ["comptable"], "champs": ["code,libelle"]}
    parsed_alias = urlparse(appellation_request.full_url)
    assert parsed_alias.path.endswith("/v1/metiers/appellation/requete")
    assert parse_qs(parsed_alias.query) == {"q": ["comptable"], "champs": ["libelle,code,metier(code,libelle)"]}
    assert métier_request.get_header("Authorization") == "Bearer synthetic-access-token"
    assert results == (
        {"code": "M1203", "label": "Comptabilité", "appellation": "Comptable général"},
        {"code": "M1204", "label": "Contrôle de gestion"},
    )


def test_product_get_requests_respect_documented_one_call_per_second_limit(monkeypatch):
    from urllib.request import Request
    from clarte360_cp.connectors import france_travail

    current_time = [10.0]
    sleeps = []
    monkeypatch.setattr(france_travail, "_ROME_API_LAST_REQUEST_AT", 0.0)
    monkeypatch.setattr(france_travail.time, "monotonic", lambda: current_time[0])
    def fake_sleep(seconds):
        sleeps.append(seconds)
        current_time[0] += seconds
    monkeypatch.setattr(france_travail.time, "sleep", fake_sleep)

    client = FranceTravailRomeClient(settings(), opener=lambda *_a, **_k: FakeResponse({"ok": True}),
                                     enforce_rate_limit=True)
    client._json_request(Request("https://api.francetravail.io/rome/test-1", method="GET"))
    client._json_request(Request("https://api.francetravail.io/rome/test-2", method="GET"))

    assert sleeps == [pytest.approx(1.05)]


def test_invalid_code_does_not_make_network_call():
    calls = []
    client = FranceTravailRomeClient(settings(), opener=lambda *args, **kwargs: calls.append(args))
    with pytest.raises(ValueError, match="code ROME"):
        client.fetch_metier("M12")
    assert calls == []


def test_fetch_fiche_metier_uses_its_own_scope_and_documented_route():
    calls = []
    clock_values = iter([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
    def opener(request, timeout):
        calls.append(request)
        if request.method == "POST":
            return FakeResponse({"access_token": "synthetic-fiche-token", "expires_in": 3600})
        return FakeResponse({"rome": {"code_rome": "M1203", "intitule": "Comptable"},
                             "competences": {"savoirs": []}, "version": "ROME-4.0-test"})
    settings = FranceTravailSettings("synthetic-client-id", "synthetic-client-secret", "metiers-scope",
        rome_fiches_scope="fiches-scope")
    client = FranceTravailRomeClient(settings, opener=opener, monotonic=lambda: next(clock_values))
    result = client.fetch_fiche_metier("m1203", force_refresh=True)
    assert b"scope=fiches-scope" in calls[0].data
    assert calls[1].full_url.endswith("/v1/fiches-rome/fiche-metier/M1203")
    assert result.resource_type == "ROME_FICHE_METIER"
    assert result.source_version == "ROME-4.0-test"


def test_fiche_metier_fails_closed_without_its_product_scope():
    client = FranceTravailRomeClient(settings(), opener=lambda *_a, **_k: pytest.fail("network must not be called"))
    with pytest.raises(FranceTravailConfigurationError, match="Scope ROME Fiches métiers"):
        client.fetch_fiche_metier("M1203")


@pytest.mark.parametrize(("method_name", "scope_field", "route", "resource_type"), [
    ("fetch_competence", "rome_competences_scope", "/v1/competences/competence/117781", "ROME_COMPETENCE"),
    ("fetch_contexte", "rome_contextes_scope", "/v1/situations-travail/contexte-travail/300799", "ROME_CONTEXTE"),
])
def test_rome_reference_families_use_independent_scopes_and_routes(method_name, scope_field, route, resource_type):
    calls = []

    def opener(request, timeout):
        calls.append(request)
        if request.method == "POST":
            return FakeResponse({"access_token": "synthetic-reference-token", "expires_in": 3600})
        return FakeResponse({"libelle": "Référence ROME", "version": "ROME-4.0-test"}, {"ETag": '"e1"'})

    settings = FranceTravailSettings(
        "synthetic-id", "synthetic-secret", "metiers-scope",
        rome_competences_scope="competences-scope", rome_contextes_scope="contextes-scope",
    )
    client = FranceTravailRomeClient(settings, opener=opener)
    code = "117781" if method_name == "fetch_competence" else "300799"
    result = getattr(client, method_name)(code, force_refresh=True)

    expected_scope = "competences-scope" if scope_field == "rome_competences_scope" else "contextes-scope"
    assert b"scope=" + expected_scope.encode() in calls[0].data
    assert calls[1].full_url.endswith(route)
    assert result.resource_type == resource_type
    assert result.code == code
    assert result.source_version == "ROME-4.0-test"
    assert result.source_etag == '"e1"'


@pytest.mark.parametrize(("method_name", "settings", "code"), [
    ("fetch_competence", FranceTravailSettings("id", "secret", "rome", rome_competences_scope=""), "117781"),
    ("fetch_contexte", FranceTravailSettings("id", "secret", "rome", rome_contextes_scope=""), "300799"),
])
def test_rome_reference_families_fail_closed_without_own_scope(method_name, settings, code):
    client = FranceTravailRomeClient(settings, opener=lambda *_a, **_k: pytest.fail("network must not be called"))
    with pytest.raises(FranceTravailConfigurationError, match="Scope ROME"):
        getattr(client, method_name)(code)


def test_rome_reference_codes_are_validated_before_network_call():
    client = FranceTravailRomeClient(settings(), opener=lambda *_a, **_k: pytest.fail("network must not be called"))
    with pytest.raises(ValueError, match="identifiant numérique"):
        client.fetch_competence("../117781")


def test_rome_reference_response_code_must_match_requested_code():
    def opener(request, timeout):
        if request.method == "POST":
            return FakeResponse({"access_token": "synthetic-reference-token", "expires_in": 3600})
        return FakeResponse({"competence": {"code_ogr": "999999", "libelle": "Autre"}})

    configured = FranceTravailSettings("id", "secret", "rome", rome_competences_scope="competences")
    client = FranceTravailRomeClient(configured, opener=opener)
    with pytest.raises(FranceTravailTransportError, match="ne correspond pas au code demandé"):
        client.fetch_competence("117781", force_refresh=True)


def test_403_error_never_exposes_response_body_or_client_secret():
    secret = "synthetic-secret-must-not-leak"

    def opener(request, timeout):
        if request.method == "POST":
            return FakeResponse({"access_token": "synthetic-access-token", "expires_in": 3600})
        raise HTTPError(request.full_url, 403, secret, {}, BytesIO(secret.encode()))

    client = FranceTravailRomeClient(
        FranceTravailSettings("synthetic-id", secret, "synthetic-scope"), opener=opener
    )
    with pytest.raises(FranceTravailHttpError) as error:
        client.fetch_metier("M1203", force_refresh=True)
    assert "403" in str(error.value)
    assert secret not in str(error.value)


def test_404_explains_local_rome_fallback_without_inferring_no_jobs():
    error = FranceTravailHttpError(404)
    assert "référentiel local" in str(error)
    assert "ne prouve pas l’absence" in str(error)


def test_timeout_error_is_safe_and_does_not_echo_transport_details():
    def opener(_request, timeout):
        raise TimeoutError("synthetic timeout detail")

    client = FranceTravailRomeClient(settings(), opener=opener)
    with pytest.raises(FranceTravailTransportError) as error:
        client.fetch_metier("M1203", force_refresh=True)
    assert "France Travail ne répond pas" in str(error.value)
    assert "synthetic timeout detail" not in str(error.value)


def test_fiche_response_cache_expires_and_explicit_refresh_bypasses_it():
    from clarte360_cp.connectors import france_travail

    france_travail._ROME_RESPONSE_CACHE.clear()
    calls = []
    fetch_count = 0
    clock = [100.0]

    def opener(request, timeout):
        nonlocal fetch_count
        calls.append(request)
        if request.method == "POST":
            return FakeResponse({"access_token": "synthetic-cache-token", "expires_in": 3600})
        fetch_count += 1
        title = "Comptable" if fetch_count == 1 else "Comptable actualisé"
        return FakeResponse({"rome": {"code_rome": "M1203", "intitule": title}, "version": str(fetch_count)})

    configured = FranceTravailSettings("synthetic-cache-id", "synthetic-cache-secret", "",
        rome_fiches_scope="synthetic-cache-fiches-scope")
    client = FranceTravailRomeClient(configured, opener=opener, monotonic=lambda: clock[0])
    first = client.fetch_fiche_metier("M1203")
    first.payload["rome"]["intitule"] = "corruption locale"
    cached = client.fetch_fiche_metier("M1203")
    assert len(calls) == 2  # OAuth + one fiche request
    assert cached.payload["rome"]["intitule"] == "Comptable"
    assert cached.source_version == "1"

    refreshed = client.fetch_fiche_metier("M1203", force_refresh=True)
    assert len(calls) == 3
    assert refreshed.payload["rome"]["intitule"] == "Comptable actualisé"
    assert refreshed.source_version == "2"

    clock[0] += france_travail.ROME_RESPONSE_CACHE_SECONDS + 1
    expired = client.fetch_fiche_metier("M1203")
    assert len(calls) == 4
    assert expired.payload["rome"]["intitule"] == "Comptable actualisé"
    assert expired.source_version == "3"
    france_travail._ROME_RESPONSE_CACHE.clear()
