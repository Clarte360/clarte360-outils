from pathlib import Path
from clarte360_pip.version import APP_VERSION, BUILD_INCREMENT, FRAMEWORK_VPS_VERSION
from clarte360_pip.data.loader import load_pip_bank, RUNTIME_FILE
from clarte360_pip.data.validation import assert_valid_bank
from clarte360_pip.journey import results_allowed
from clarte360_pip.framework.config import BASE_DIR, PERSISTENT_DATA_DIR, RESOURCES_DIR, TEMP_DIR

ROOT = Path(__file__).resolve().parents[1]


def test_final_version():
    assert APP_VERSION == "1.0.1-l1-vps"
    assert BUILD_INCREMENT == "L1-D"
    assert FRAMEWORK_VPS_VERSION == "1.0"


def test_runtime_bank_final_integrity():
    bank = load_pip_bank()
    assert_valid_bank(bank)
    assert len(bank["items"]) == 120
    assert len({x["item_id"] for x in bank["items"]}) == 120
    assert RUNTIME_FILE.is_relative_to(RESOURCES_DIR)


def test_onet_anti_influence_gate():
    assert not results_allowed("PIP_PUIS_ONET60", True, False)
    assert results_allowed("PIP_PUIS_ONET60", True, True)


def test_no_real_secret_material_in_repository():
    forbidden = ("sk-" + "proj-", "BEGIN " + "PRIVATE KEY")
    for p in ROOT.rglob("*"):
        if p.is_file() and p != Path(__file__) and p.suffix.lower() in {".py", ".md", ".toml", ".txt", ".json"}:
            text = p.read_text(errors="ignore")
            assert not any(x in text for x in forbidden), p


def test_vps_paths_are_code_independent():
    assert BASE_DIR == ROOT
    assert PERSISTENT_DATA_DIR == ROOT / "data"
    assert str(TEMP_DIR).startswith("/tmp/")
    assert RESOURCES_DIR == ROOT / "resources"


def test_user_recipe_present():
    assert (ROOT / "docs" / "RECETTE_UTILISATEUR_LIVRABLE_1.md").exists()


def test_vps_deployment_documentation_present():
    assert (ROOT / "docs/deployment/VPS_DEPLOYMENT.md").exists()
    assert (ROOT / "docs/deployment/clarte360-pip-riasec-onet.service.example").exists()
