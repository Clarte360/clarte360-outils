from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from clarte360_pip.framework.config import OnetSettings


class OnetApiError(RuntimeError):
    pass


ONET_INSTRUMENT = "O*NET Interest Profiler Short Form"
ONET_QUESTION_COUNT = 60
ONET_API_VERSION = "2.0"
ONET_LANGUAGE = "en"


def normalize_onet_results(results: list[dict]) -> list[dict]:
    """Return the six O*NET RIASEC results sorted by descending official raw score."""
    return sorted([dict(r) for r in (results or [])], key=lambda r: (-int(r.get("score", 0)), str(r.get("code", ""))))


@dataclass(frozen=True)
class OnetPort:
    settings: OnetSettings

    @property
    def available_for_future_increment(self) -> bool:
        return self.settings.configured

    @property
    def configured(self) -> bool:
        return self.settings.configured

    def _get(self, path: str, params: dict | None = None) -> dict:
        if not self.settings.configured:
            raise OnetApiError("Le service O*NET n'est pas configuré sur le serveur.")
        url = self.settings.base_url.rstrip("/") + path
        if params:
            url += "?" + urlencode(params)
        req = Request(url, headers={"X-API-Key": str(self.settings.api_key), "User-Agent": "Clarte360-PIP-RIASEC"}, method="GET")
        try:
            with urlopen(req, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise OnetApiError(f"Service O*NET temporairement indisponible : {exc}") from exc

    def fetch_interest_profiler(self) -> dict:
        """Fetch the official English 60-item O*NET Interest Profiler."""
        return self._get("/mnm/interestprofiler/questions", {"start": 1, "end": 60})

    def score_interest_profiler(self, answers: dict[int | str, int]) -> dict:
        values = []
        for idx in range(1, ONET_QUESTION_COUNT + 1):
            value = int(answers.get(idx, answers.get(str(idx), 0)))
            if value not in (1, 2, 3, 4, 5):
                raise ValueError(f"Réponse O*NET manquante ou invalide à la question {idx}.")
            values.append(str(value))
        return self._get("/mnm/interestprofiler/results", {"answers": "".join(values)})
