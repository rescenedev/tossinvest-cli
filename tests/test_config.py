"""설정 로딩 테스트."""

import pytest

from toss_cli import config as config_mod
from toss_cli.config import Config, ConfigError, load_config


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch, tmp_path):
    # 실제 환경/홈 설정의 영향을 제거.
    for key in ("TOSS_CLIENT_ID", "TOSS_CLIENT_SECRET", "TOSS_ACCOUNT_SEQ", "TOSS_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.toml")
    # 실제 macOS Keychain 영향 제거 (개발 머신에 키가 저장돼 있을 수 있음)
    monkeypatch.setattr(config_mod, "keychain_get", lambda account: None)
    yield


def test_load_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TOSS_CLIENT_ID", "cid")
    monkeypatch.setenv("TOSS_CLIENT_SECRET", "secret")
    monkeypatch.setenv("TOSS_ACCOUNT_SEQ", "7")
    cfg = load_config(dotenv_path=tmp_path / "missing.env")
    assert cfg.client_id == "cid"
    assert cfg.account_seq == 7
    assert cfg.base_url == config_mod.DEFAULT_BASE_URL


def test_missing_credentials_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(dotenv_path=tmp_path / "missing.env")


def test_dotenv_used_when_env_absent(tmp_path):
    env = tmp_path / ".env"
    env.write_text('TOSS_CLIENT_ID="fid"\nTOSS_CLIENT_SECRET=fsec\n', encoding="utf-8")
    cfg = load_config(dotenv_path=env)
    assert cfg.client_id == "fid"
    assert cfg.client_secret == "fsec"
    assert cfg.account_seq is None


def test_with_account_is_immutable():
    cfg = Config(client_id="a", client_secret="b", account_seq=1)
    updated = cfg.with_account(2)
    assert cfg.account_seq == 1  # 원본 불변
    assert updated.account_seq == 2


def test_require_account_raises_when_missing():
    cfg = Config(client_id="a", client_secret="b")
    with pytest.raises(ConfigError):
        cfg.require_account()
