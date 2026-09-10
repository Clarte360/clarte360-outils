from clarte360_pip.framework.config import load_onet_settings, load_smtp_settings


def test_onet_missing_secret_is_safe():
    cfg = load_onet_settings({})
    assert cfg.configured is False
    assert cfg.api_key is None
    assert cfg.base_url == "https://api-v2.onetcenter.org"


def test_onet_reads_only_expected_section():
    cfg = load_onet_settings({"ONET": {"ONET_API_KEY": "test-placeholder", "ONET_API_BASE_URL": "https://example.invalid"}})
    assert cfg.configured is True
    assert cfg.api_key == "test-placeholder"
    assert cfg.base_url == "https://example.invalid"


def test_smtp_missing_secret_is_safe():
    assert load_smtp_settings({}).configured is False
