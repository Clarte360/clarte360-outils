from __future__ import annotations

from pathlib import Path
from typing import Any

from db import one


def _check(name: str, ok: bool, message: str, *, blocking: bool = False) -> dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "status": "OK" if ok else ("BLOQUANT" if blocking else "A_VERIFIER"),
        "message": message,
        "blocking": bool(blocking and not ok),
    }


def runtime_readiness(engine, *, base_url: str, mail_config: dict | None = None,
                      secrets: dict | None = None, project_root: str | Path | None = None) -> dict[str, Any]:
    """Retourne un diagnostic métier sans jamais exposer les valeurs des secrets.

    Cette fonction est volontairement tolérante : un connecteur optionnel absent ne doit
    pas rendre l'application indisponible. Les contrôles bloquants concernent uniquement
    le socle de fonctionnement du Hub.
    """
    mail_config = mail_config or {}
    secrets = secrets or {}
    root = Path(project_root or Path(__file__).resolve().parent)
    checks: list[dict[str, Any]] = []

    try:
        db_ok = bool(one(engine, "SELECT 1 AS ok").get("ok"))
    except Exception:
        db_ok = False
    checks.append(_check("Base de données", db_ok, "Base accessible." if db_ok else "Base indisponible.", blocking=True))

    url_ok = str(base_url or "").startswith(("http://", "https://"))
    checks.append(_check("URL publique", url_ok, "URL publique configurée." if url_ok else "URL publique à configurer.", blocking=True))

    checks.append(_check("Emails", bool(mail_config.get("enabled")),
                         "Envoi automatique configuré." if mail_config.get("enabled") else "Envoi automatique non activé."))

    ms = secrets.get("microsoft_graph") if isinstance(secrets, dict) else None
    ms = ms if isinstance(ms, dict) else {}
    ms_ready = all(bool(ms.get(k)) for k in ("tenant_id", "client_id", "certificate_path"))
    checks.append(_check("Microsoft 365 / Teams", ms_ready,
                         "Configuration Microsoft présente." if ms_ready else "Configuration Microsoft à vérifier avant recette Teams."))

    pip = secrets.get("pip_connector") if isinstance(secrets, dict) else None
    pip = pip if isinstance(pip, dict) else {}
    pip_ready = bool(pip.get("launch_signing_key")) and bool(pip.get("outbox_path"))
    checks.append(_check("Connecteur PIP", pip_ready,
                         "Connecteur PIP configuré." if pip_ready else "Clé de lancement et/ou outbox PIP à renseigner avant recette PIP."))

    required = ["app.py", "db.py", "services.py", "worker.py", "security.py", "pdf_utils.py"]
    files_ok = all((root / name).is_file() for name in required)
    checks.append(_check("Structure applicative", files_ok,
                         "Fichiers principaux présents." if files_ok else "Un fichier applicatif principal manque.", blocking=True))

    tests_dir = root / "tests"
    tests_ok = tests_dir.is_dir() and any(tests_dir.glob("test_*.py"))
    checks.append(_check("Tests embarqués", tests_ok,
                         "Suite de tests présente." if tests_ok else "Suite de tests absente.", blocking=True))

    return {
        "ready": not any(c["blocking"] for c in checks),
        "checks": checks,
        "ok_count": sum(1 for c in checks if c["ok"]),
        "total_count": len(checks),
    }
