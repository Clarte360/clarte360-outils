"""France Travail ROME 4.0 connector.

The secret pair is supplied by the central Streamlit secret store. The product
scope is deliberately a separate, required runtime setting: it is an access
parameter, not a credential, and must come from the subscribed application.
The client keeps the four independently subscribed ROME product families
separate. API routes are limited to operations documented by France Travail.
"""
from __future__ import annotations

import json
from copy import deepcopy
import re
from threading import RLock
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
DEFAULT_ROME_BASE_URL = "https://api.francetravail.io/partenaire/rome-metiers"
ROME_METIER_PATH = "/v1/metiers/metier/{code}"
ROME_METIER_SEARCH_PATH = "/v1/metiers/metier/requete"
ROME_APPELLATION_SEARCH_PATH = "/v1/metiers/appellation/requete"
DEFAULT_ROME_COMPETENCES_BASE_URL = "https://api.francetravail.io/partenaire/rome-competences"
ROME_COMPETENCE_PATH = "/v1/competences/competence/{code}"
DEFAULT_ROME_CONTEXTS_BASE_URL = "https://api.francetravail.io/partenaire/rome-contextes-travail"
ROME_CONTEXT_PATH = "/v1/situations-travail/contexte-travail/{code}"
DEFAULT_ROME_FICHES_BASE_URL = "https://api.francetravail.io/partenaire/rome-fiches-metiers"
ROME_FICHE_METIER_PATH = "/v1/fiches-rome/fiche-metier/{code}"
ROME_RESPONSE_CACHE_SECONDS = 300
ROME_RESPONSE_CACHE_MAX_ITEMS = 256
_ROME_RESPONSE_CACHE: dict[tuple[str, str, str], tuple[float, "RomeMetierSnapshot"]] = {}
_ROME_RESPONSE_CACHE_LOCK = RLock()
_ROME_API_RATE_LIMIT_SECONDS = 1.05
_ROME_API_RATE_LIMIT_LOCK = RLock()
_ROME_API_LAST_REQUEST_AT = 0.0


class FranceTravailError(RuntimeError):
    """Base error that never includes credentials, tokens, or response bodies."""


class FranceTravailConfigurationError(FranceTravailError):
    pass


class FranceTravailTransportError(FranceTravailError):
    pass


class FranceTravailHttpError(FranceTravailError):
    def __init__(self, status_code: int):
        self.status_code = int(status_code)
        if status_code == 401:
            message = "France Travail a refusé l'authentification (HTTP 401)."
        elif status_code == 403:
            message = "France Travail a refusé l'accès au produit demandé (HTTP 403)."
        elif status_code == 429:
            message = "Le quota France Travail est atteint (HTTP 429)."
        elif status_code == 404:
            message = "La ressource ROME demandée n’a pas été trouvée (HTTP 404). Vérifiez le code dans le référentiel local; ce retour ne prouve pas l’absence d’un métier ou de débouchés."
        else:
            message = f"France Travail a répondu avec le statut HTTP {status_code}."
        super().__init__(message)


@dataclass(frozen=True)
class FranceTravailSettings:
    client_id: str
    client_secret: str
    rome_scope: str = ""
    token_url: str = DEFAULT_TOKEN_URL
    rome_base_url: str = DEFAULT_ROME_BASE_URL
    timeout_seconds: float = 12.0
    rome_fiches_scope: str = ""
    rome_fiches_base_url: str = DEFAULT_ROME_FICHES_BASE_URL
    rome_competences_scope: str = ""
    rome_competences_base_url: str = DEFAULT_ROME_COMPETENCES_BASE_URL
    rome_contextes_scope: str = ""
    rome_contextes_base_url: str = DEFAULT_ROME_CONTEXTS_BASE_URL

    @classmethod
    def from_mapping(cls, section: Mapping[str, Any]) -> "FranceTravailSettings":
        """Read the canonical secret pair plus the separately supplied scope.

        This method accepts the `[france_travail]` section from `st.secrets`;
        it does not read a file or print configuration values.
        """
        client_id = str(section.get("client_id", "")).strip()
        secret_value = str(section.get("client_secret", "")).strip()
        scope = str(section.get("rome_scope", section.get("scope_rome_metiers", ""))).strip()
        fiche_scope = str(section.get("rome_fiches_metiers_scope", section.get("scope_rome_fiches_metiers", ""))).strip()
        skills_scope = str(section.get("rome_competences_scope", section.get("scope_rome_competences", ""))).strip()
        contexts_scope = str(section.get("rome_contextes_scope", section.get("scope_rome_contextes_travail", ""))).strip()
        token_url = str(section.get("token_url", DEFAULT_TOKEN_URL)).strip()
        base_url = str(section.get("rome_base_url", DEFAULT_ROME_BASE_URL)).strip().rstrip("/")
        fiche_base_url = str(section.get("rome_fiches_metiers_base_url", DEFAULT_ROME_FICHES_BASE_URL)).strip().rstrip("/")
        skills_base_url = str(section.get("rome_competences_base_url", DEFAULT_ROME_COMPETENCES_BASE_URL)).strip().rstrip("/")
        contexts_base_url = str(section.get("rome_contextes_base_url", DEFAULT_ROME_CONTEXTS_BASE_URL)).strip().rstrip("/")
        if not client_id or not secret_value:
            raise FranceTravailConfigurationError("Identifiants France Travail absents de la configuration centrale.")
        scopes = (scope, fiche_scope, skills_scope, contexts_scope)
        if not any(scopes):
            raise FranceTravailConfigurationError("Aucun scope ROME configuré pour les produits souscrits.")
        for scope_value, label in zip(scopes, ("ROME Métiers", "ROME Fiches métiers", "ROME Compétences", "ROME Contextes de travail")):
            if scope_value and any(ch.isspace() for ch in scope_value):
                raise FranceTravailConfigurationError(f"Le scope {label} doit être une valeur de scope unique.")
        for url in (token_url, base_url, fiche_base_url, skills_base_url, contexts_base_url):
            if not url.startswith("https://"):
                raise FranceTravailConfigurationError("Les URL France Travail doivent utiliser HTTPS.")
        return cls(client_id, secret_value, scope, token_url, base_url, 12.0, fiche_scope, fiche_base_url,
                   skills_scope, skills_base_url, contexts_scope, contexts_base_url)


@dataclass(frozen=True)
class RomeMetierSnapshot:
    code: str
    payload: Mapping[str, Any]
    provider: str
    resource_type: str
    fetched_at: datetime
    source_version: str | None
    source_etag: str | None


class FranceTravailRomeClient:
    """Small synchronous OAuth client with an in-memory token cache."""

    def __init__(
        self,
        settings: FranceTravailSettings,
        *,
        opener: Callable[..., Any] = urlopen,
        monotonic: Callable[[], float] = time.monotonic,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        enforce_rate_limit: bool | None = None,
    ):
        self.settings = settings
        self._opener = opener
        self._monotonic = monotonic
        self._clock = clock
        self._enforce_rate_limit = opener is urlopen if enforce_rate_limit is None else enforce_rate_limit
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._scoped_tokens: dict[str, tuple[str, float]] = {}

    def fetch_metier(self, code: str, *, force_refresh: bool = False) -> RomeMetierSnapshot:
        normalized = str(code or "").strip().upper()
        if not re.fullmatch(r"[A-Z]\d{4}", normalized):
            raise ValueError("Le code ROME doit contenir une lettre suivie de quatre chiffres.")
        url = self.settings.rome_base_url + ROME_METIER_PATH.format(code=normalized)
        cached = self._cached_response(url, self.settings.rome_scope, normalized, force_refresh)
        if cached is not None:
            return cached
        token = self._get_token(self.settings.rome_scope)
        request = Request(url, headers={"Accept": "application/json", "Authorization": f"Bearer {token}"}, method="GET")
        payload, headers = self._json_request(request)
        if not isinstance(payload, dict):
            raise FranceTravailTransportError("La réponse ROME n'est pas un objet JSON exploitable.")
        returned_code = payload.get("code") or payload.get("codeRome") or payload.get("code_rome")
        if returned_code is not None and str(returned_code).upper() != normalized:
            raise FranceTravailTransportError("La réponse France Travail ne correspond pas au code ROME demandé.")
        version = payload.get("version") or payload.get("versionReferentiel") or payload.get("version_referentiel")
        snapshot = RomeMetierSnapshot(
            code=normalized,
            payload=payload,
            provider="FRANCE_TRAVAIL",
            resource_type="ROME_METIER",
            fetched_at=self._clock(),
            source_version=str(version) if version is not None else None,
            source_etag=headers.get("ETag") or headers.get("Etag"),
        )
        self._remember_response(url, self.settings.rome_scope, normalized, snapshot)
        return snapshot

    def search_metiers(self, query: str, *, limit: int = 60) -> tuple[dict[str, str], ...]:
        """Search métier codes and labels using the documented autocomplete operation."""
        term = str(query or "").strip()
        if not term:
            return ()
        if len(term) > 120:
            raise ValueError("La recherche ROME est limitée à 120 caractères.")
        scope = self.settings.rome_scope
        if not scope:
            raise FranceTravailConfigurationError("Scope ROME Métiers non configuré pour le produit souscrit.")
        token = self._get_token(scope)
        limit = max(1, min(int(limit), 200))
        matches: dict[str, dict[str, str]] = {}
        for path, fields in (
            (ROME_METIER_SEARCH_PATH, "code,libelle"),
            (ROME_APPELLATION_SEARCH_PATH, "libelle,code,metier(code,libelle)"),
        ):
            params = urlencode({"q": term, "champs": fields})
            url = f"{self.settings.rome_base_url}{path}?{params}"
            request = Request(url, headers={"Accept": "application/json", "Authorization": f"Bearer {token}"}, method="GET")
            payload, _headers = self._json_request(request)
            rows = payload.get("resultats") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise FranceTravailTransportError("La recherche ROME n'a pas renvoyé de liste exploitable.")
            for row in rows:
                if not isinstance(row, dict):
                    continue
                nested = row.get("metier") if path == ROME_APPELLATION_SEARCH_PATH else None
                nested = nested if isinstance(nested, dict) else {}
                code = str(nested.get("code") or row.get("code") or "").strip().upper()
                label = str(nested.get("libelle") or row.get("libelle") or "").strip()
                if not re.fullmatch(r"[A-Z]\d{4}", code) or not label:
                    continue
                if len(matches) >= limit and code not in matches:
                    continue
                match = matches.setdefault(code, {"code": code, "label": label[:240]})
                alias = str(row.get("libelle") or "").strip() if nested else ""
                if alias and alias.casefold() != match["label"].casefold():
                    match["appellation"] = alias[:240]
                if len(matches) >= limit:
                    break
        return tuple(matches.values())

    def fetch_fiche_metier(self, code: str, *, force_refresh: bool = False) -> RomeMetierSnapshot:
        """Fetch the structured ROME fiche used to populate activity/skill snapshots."""
        normalized = str(code or "").strip().upper()
        if not re.fullmatch(r"[A-Z]\d{4}", normalized):
            raise ValueError("Le code ROME doit contenir une lettre suivie de quatre chiffres.")
        scope = self.settings.rome_fiches_scope
        if not scope:
            raise FranceTravailConfigurationError("Scope ROME Fiches métiers non configuré pour l'application souscrite.")
        url = self.settings.rome_fiches_base_url + ROME_FICHE_METIER_PATH.format(code=normalized)
        cached = self._cached_response(url, scope, normalized, force_refresh)
        if cached is not None:
            return cached
        token = self._get_token(scope)
        request = Request(url, headers={"Accept": "application/json", "Authorization": f"Bearer {token}"}, method="GET")
        payload, headers = self._json_request(request)
        if not isinstance(payload, dict):
            raise FranceTravailTransportError("La fiche ROME n'est pas un objet JSON exploitable.")
        returned_code = payload.get("code") or payload.get("codeRome") or payload.get("code_rome")
        rome = payload.get("rome")
        if returned_code is None and isinstance(rome, dict):
            returned_code = rome.get("code_rome") or rome.get("codeRome") or rome.get("code")
        if returned_code is not None and str(returned_code).upper() != normalized:
            raise FranceTravailTransportError("La fiche France Travail ne correspond pas au code ROME demandé.")
        version = payload.get("version") or payload.get("versionReferentiel") or payload.get("version_referentiel")
        snapshot = RomeMetierSnapshot(
            code=normalized, payload=payload, provider="FRANCE_TRAVAIL", resource_type="ROME_FICHE_METIER",
            fetched_at=self._clock(), source_version=str(version) if version is not None else None,
            source_etag=headers.get("ETag") or headers.get("Etag"),
        )
        self._remember_response(url, scope, normalized, snapshot)
        return snapshot

    def fetch_competence(self, code: str, *, force_refresh: bool = False) -> RomeMetierSnapshot:
        return self._fetch_reference_code(
            code, scope=self.settings.rome_competences_scope,
            base_url=self.settings.rome_competences_base_url, path=ROME_COMPETENCE_PATH,
            resource_type="ROME_COMPETENCE", label="ROME Compétences",
            force_refresh=force_refresh,
        )

    def fetch_contexte(self, code: str, *, force_refresh: bool = False) -> RomeMetierSnapshot:
        return self._fetch_reference_code(
            code, scope=self.settings.rome_contextes_scope,
            base_url=self.settings.rome_contextes_base_url, path=ROME_CONTEXT_PATH,
            resource_type="ROME_CONTEXTE", label="ROME Contextes de travail",
            force_refresh=force_refresh,
        )

    def _fetch_reference_code(self, code: str, *, scope: str, base_url: str, path: str,
                              resource_type: str, label: str,
                              force_refresh: bool) -> RomeMetierSnapshot:
        normalized = str(code or "").strip()
        if not re.fullmatch(r"\d{1,12}", normalized):
            raise ValueError("Le code de référence ROME doit être un identifiant numérique valide.")
        if not scope:
            raise FranceTravailConfigurationError(f"Scope {label} non configuré pour le produit souscrit.")
        url = base_url + path.format(code=normalized)
        cached = self._cached_response(url, scope, normalized, force_refresh)
        if cached is not None:
            return cached
        token = self._get_token(scope)
        request = Request(url, headers={"Accept": "application/json", "Authorization": f"Bearer {token}"}, method="GET")
        payload, headers = self._json_request(request)
        if not isinstance(payload, dict):
            raise FranceTravailTransportError(f"La réponse {label} n'est pas un objet JSON exploitable.")
        returned_code = _reference_code(payload)
        if returned_code is not None and returned_code != normalized:
            raise FranceTravailTransportError(f"La réponse {label} ne correspond pas au code demandé.")
        version = payload.get("version") or payload.get("versionReferentiel") or payload.get("version_referentiel")
        snapshot = RomeMetierSnapshot(
            code=normalized, payload=payload, provider="FRANCE_TRAVAIL", resource_type=resource_type,
            fetched_at=self._clock(), source_version=str(version) if version is not None else None,
            source_etag=headers.get("ETag") or headers.get("Etag"),
        )
        self._remember_response(url, scope, normalized, snapshot)
        return snapshot

    def _cached_response(self, url: str, scope: str, code: str,
                         force_refresh: bool) -> RomeMetierSnapshot | None:
        if force_refresh:
            return None
        key = (url, scope, code)
        now = self._monotonic()
        with _ROME_RESPONSE_CACHE_LOCK:
            entry = _ROME_RESPONSE_CACHE.get(key)
            if entry is None:
                return None
            expires_at, snapshot = entry
            if now >= expires_at:
                _ROME_RESPONSE_CACHE.pop(key, None)
                return None
            return RomeMetierSnapshot(
                code=snapshot.code, payload=deepcopy(snapshot.payload), provider=snapshot.provider,
                resource_type=snapshot.resource_type, fetched_at=snapshot.fetched_at,
                source_version=snapshot.source_version, source_etag=snapshot.source_etag,
            )

    def _remember_response(self, url: str, scope: str, code: str,
                           snapshot: RomeMetierSnapshot) -> None:
        if ROME_RESPONSE_CACHE_SECONDS <= 0:
            return
        key = (url, scope, code)
        copied = RomeMetierSnapshot(
            code=snapshot.code, payload=deepcopy(snapshot.payload), provider=snapshot.provider,
            resource_type=snapshot.resource_type, fetched_at=snapshot.fetched_at,
            source_version=snapshot.source_version, source_etag=snapshot.source_etag,
        )
        with _ROME_RESPONSE_CACHE_LOCK:
            expired = [item for item, (expires, _value) in _ROME_RESPONSE_CACHE.items()
                       if self._monotonic() >= expires]
            for item in expired:
                _ROME_RESPONSE_CACHE.pop(item, None)
            while len(_ROME_RESPONSE_CACHE) >= ROME_RESPONSE_CACHE_MAX_ITEMS:
                _ROME_RESPONSE_CACHE.pop(next(iter(_ROME_RESPONSE_CACHE)))
            _ROME_RESPONSE_CACHE[key] = (self._monotonic() + ROME_RESPONSE_CACHE_SECONDS, copied)

    def _get_token(self, scope: str | None = None) -> str:
        scope = str(scope or self.settings.rome_scope).strip()
        if not scope:
            raise FranceTravailConfigurationError("Scope France Travail absent pour le produit demandé.")
        cached = self._scoped_tokens.get(scope)
        if cached and self._monotonic() < cached[1]:
            return cached[0]
        if self._token and self._monotonic() < self._token_expires_at:
            if scope == self.settings.rome_scope:
                return self._token
        body = urlencode({
            "grant_type": "client_credentials",
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret,
            "scope": scope,
        }).encode("ascii")
        request = Request(
            self.settings.token_url,
            data=body,
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        payload, _headers = self._json_request(request)
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise FranceTravailTransportError("La réponse OAuth France Travail ne contient pas de jeton exploitable.")
        try:
            expires_in = max(0, int(payload.get("expires_in", 0)))
        except (TypeError, ValueError):
            expires_in = 0
        if expires_in <= 30:
            raise FranceTravailTransportError("La durée du jeton OAuth France Travail est absente ou trop courte.")
        self._token_expires_at = self._monotonic() + expires_in - 30
        self._scoped_tokens[scope] = (token, self._token_expires_at)
        if scope == self.settings.rome_scope:
            self._token = token
        return token

    def _json_request(self, request: Request) -> tuple[Any, Mapping[str, str]]:
        if request.method == "GET" and self._enforce_rate_limit:
            _wait_for_rome_api_slot()
        try:
            response = self._opener(request, timeout=self.settings.timeout_seconds)
            with response:
                raw = response.read()
                headers = dict(response.headers.items())
        except HTTPError as exc:
            # Never include the body: OAuth errors may echo submitted parameters.
            raise FranceTravailHttpError(exc.code) from None
        except (TimeoutError, URLError, OSError) as exc:
            raise FranceTravailTransportError("France Travail ne répond pas ou n'est pas joignable.") from None
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise FranceTravailTransportError("France Travail a renvoyé une réponse JSON illisible.") from None
        if isinstance(decoded, dict) and decoded.get("error"):
            # Do not reflect provider text; it can contain request details.
            raise FranceTravailTransportError("France Travail a renvoyé une erreur applicative.")
        return decoded, headers


def _wait_for_rome_api_slot() -> None:
    """Keep product API GETs below the documented one-request-per-second limit."""
    global _ROME_API_LAST_REQUEST_AT
    with _ROME_API_RATE_LIMIT_LOCK:
        now = time.monotonic()
        if _ROME_API_LAST_REQUEST_AT:
            remaining = _ROME_API_RATE_LIMIT_SECONDS - (now - _ROME_API_LAST_REQUEST_AT)
            if remaining > 0:
                time.sleep(remaining)
                now = time.monotonic()
        _ROME_API_LAST_REQUEST_AT = now


def _reference_code(payload: Mapping[str, Any]) -> str | None:
    """Read a ROME competence/context code without trusting arbitrary labels."""
    for key in ("code_ogr", "codeOgr", "code_competence", "codeCompetence", "code_contexte", "codeContexte", "code"):
        value = payload.get(key)
        if isinstance(value, (str, int)) and str(value).isdigit():
            return str(value)
    for key in ("competence", "contexte", "reference", "item"):
        child = payload.get(key)
        if isinstance(child, dict):
            code = _reference_code(child)
            if code:
                return code
    return None
