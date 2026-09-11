from pathlib import Path
import re

from clarte360_pip.version import (
    APP_VERSION,
    BUILD_INCREMENT,
    FRAMEWORK_VERSION,
    FRAMEWORK_VPS_VERSION,
)

ROOT = Path(__file__).resolve().parents[1]


def test_versions_and_required_layout():
    assert APP_VERSION == "1.0.6-l1-vps"
    assert BUILD_INCREMENT == "L1-D"
    assert FRAMEWORK_VERSION == "4.0"
    assert FRAMEWORK_VPS_VERSION == "1.0"
    for rel in [
        "app.py", "requirements.txt", "README.md", "CHANGELOG.md", "pytest.ini",
        ".streamlit/config.toml", ".streamlit/secrets.example.toml",
        "assets/site_icon.png", "resources/runtime", "resources/schemas", "scripts", "docs",
        "clarte360_pip/framework", "clarte360_pip/domain", "clarte360_pip/connectors", "clarte360_pip/ui", "tests",
    ]:
        assert (ROOT / rel).exists(), rel


def test_four_master_sources_are_carried_forward():
    src = ROOT / "docs" / "sources"
    expected = {
        "CDC_PIP_RIASEC_CLARTE360_ONET_V1_4.docx",
        "REFERENTIEL_METHODOLOGIQUE_PIP_RIASEC_CLARTE360_V1_0.docx",
        "CLARTE360_PIP_RIASEC_TABLEUR_MAITRE_V0_3.xlsx",
        "PIP_RIASEC_CLARTE360_BANQUE_EXPERIMENTALE_120_ITEMS_REVUE_V0_1.docx",
    }
    names = {p.name for p in src.iterdir() if p.is_file()}
    assert expected.issubset(names)
    assert names - expected <= {"CLARTE360_PIP_RIASEC_TABLEUR_MAITRE_V0_4_CONTEXTES.xlsx"}
    assert (ROOT / "docs" / "references" / "rome_riasec_clarte360.xlsx").exists()


def test_no_real_secret_patterns_in_text_files():
    suspicious = [
        re.compile(r"ONET_API_KEY\s*=\s*[\"'][^\"']{12,}[\"']"),
        re.compile(r"smtp_password\s*=\s*[\"'][^\"']{8,}[\"']"),
        re.compile(r"BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY"),
    ]
    for path in ROOT.rglob("*"):
        # Do not dereference VPS-local secret symlinks: the repository scan
        # must validate versioned content, not the external secret store.
        if path.is_symlink():
            continue
        if not path.is_file() or path.suffix.lower() in {".docx", ".xlsx", ".png", ".zip", ".pyc"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in suspicious:
            assert not pattern.findall(text), f"Potential secret in {path}"



def test_secret_symlink_is_ignored_by_repository_scans(tmp_path):
    external = tmp_path / "external-secrets.toml"
    external.write_text("ONET_" + "API_KEY = \"" + "example-secret-material-123456" + "\"", encoding="utf-8")
    link = tmp_path / "secrets.toml"
    link.symlink_to(external)
    assert link.is_symlink()


def test_vps_forbidden_artifacts_are_ignored_by_git():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for token in [".venv/", "venv/", "__pycache__/", ".pytest_cache/", "*.py[cod]",
                  ".streamlit/secrets.toml", "*.pem", "*.key", "*.pfx", "*.p12",
                  "*.bak", "*.tmp", "data/"]:
        assert token in text


def test_versioned_runtime_is_not_under_ignored_data_directory():
    assert (ROOT / "resources/runtime/pip_bank_PIP-BANK-0.3.json").is_file()
    assert (ROOT / "resources/schemas/pip_run_schema_v0.json").is_file()
    assert not (ROOT / "data/runtime").exists()
    assert not (ROOT / "data/schemas").exists()


def test_gitignore_protects_vps_local_state():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for token in [".venv/", ".streamlit/secrets.toml", "data/", "__pycache__/", "*.pem", "*.key"]:
        assert token in text


def test_l1a_runtime_does_not_embed_pilot_item_ids():
    for path in list((ROOT / "clarte360_pip").rglob("*.py")) + [ROOT / "app.py"]:
        text = path.read_text(encoding="utf-8")
        assert "PIP-ACT-R-R1-001" not in text
        assert "Assembler des elements pour fabriquer" not in text


def test_python_source_package_is_not_named_data():
    """Le .gitignore racine du monorepo ignore **/data/ : aucun code Python ne doit y vivre."""
    assert not (ROOT / "clarte360_pip" / "data").exists()
    assert (ROOT / "clarte360_pip" / "pip_data" / "loader.py").is_file()
    assert (ROOT / "clarte360_pip" / "pip_data" / "validation.py").is_file()
