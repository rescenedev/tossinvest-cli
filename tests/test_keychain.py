"""macOS Keychain 자격증명 백엔드 테스트 (security CLI 모킹)."""


from toss_cli import config as cfg


def test_keychain_priority_between_dotenv_and_toml(monkeypatch, tmp_path):
    # env·.env 없음 → keychain 값이 toml 보다 우선
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.toml")
    (tmp_path / "config.toml").write_text(
        'client_id = "from-toml"\nclient_secret = "toml-secret"\n', encoding="utf-8"
    )
    monkeypatch.delenv("TOSS_CLIENT_ID", raising=False)
    monkeypatch.delenv("TOSS_CLIENT_SECRET", raising=False)
    kc = {"client_id": "from-keychain", "client_secret": "kc-secret"}
    monkeypatch.setattr(cfg, "keychain_get", lambda account: kc.get(account))

    config = cfg.load_config(dotenv_path=tmp_path / "nonexistent.env")
    assert config.client_id == "from-keychain"
    assert config.client_secret == "kc-secret"


def test_env_overrides_keychain(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.setenv("TOSS_CLIENT_ID", "from-env")
    monkeypatch.setenv("TOSS_CLIENT_SECRET", "env-secret")
    monkeypatch.setattr(cfg, "keychain_get", lambda account: "from-keychain")
    config = cfg.load_config(dotenv_path=tmp_path / "none.env")
    assert config.client_id == "from-env"


def test_keychain_get_returns_none_off_macos(monkeypatch):
    monkeypatch.setattr(cfg.sys, "platform", "linux")
    assert cfg.keychain_get("client_id") is None
    assert cfg.keychain_available() is False


def test_keychain_get_parses_security_output(monkeypatch):
    monkeypatch.setattr(cfg, "keychain_available", lambda: True)

    class R:
        returncode = 0
        stdout = "secret-value\n"
    monkeypatch.setattr(cfg.subprocess, "run", lambda *a, **k: R())
    assert cfg.keychain_get("client_id") == "secret-value"

    class RFail:
        returncode = 44
        stdout = ""
    monkeypatch.setattr(cfg.subprocess, "run", lambda *a, **k: RFail())
    assert cfg.keychain_get("client_id") is None
