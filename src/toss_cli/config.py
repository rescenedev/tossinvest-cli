"""설정 로딩: 환경변수, .env, ~/.toss-cli/config.toml 순서로 병합.

자격증명과 같은 민감 정보는 환경변수 또는 .env 파일을 통해 주입하며,
이 모듈은 불변(frozen) 설정 객체를 반환합니다.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path


def atomic_write(path: Path, content: str, *, mode: int | None = None) -> None:
    """임시 파일에 쓴 뒤 os.replace 로 원자적 교체.

    부분 쓰기(인터럽트·디스크풀)와 동시 쓰기로 인한 파일 손상을 방지한다.
    mode 가 주어지면 교체 전에 권한을 설정해, 민감 파일이 잠깐도 느슨한
    권한으로 노출되지 않게 한다 (토큰 캐시 0o600 등).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise

DEFAULT_BASE_URL = "https://openapi.tossinvest.com"
CONFIG_DIR = Path(os.path.expanduser("~")) / ".toss-cli"
CONFIG_FILE = CONFIG_DIR / "config.toml"
TOKEN_CACHE_FILE = CONFIG_DIR / "token.json"

# macOS Keychain (security CLI) 항목 식별자
KEYCHAIN_SERVICE = "tossinvest-cli"
KEYCHAIN_KEYS = {"TOSS_CLIENT_ID": "client_id", "TOSS_CLIENT_SECRET": "client_secret"}


def keychain_available() -> bool:
    """macOS 이고 security CLI 가 있으면 Keychain 사용 가능."""
    return sys.platform == "darwin" and shutil.which("security") is not None


def keychain_get(account: str) -> str | None:
    """Keychain 에서 generic password 조회 (없거나 비-macOS 면 None)."""
    if not keychain_available():
        return None
    try:
        result = subprocess.run(
            ["security", "find-generic-password",
             "-s", KEYCHAIN_SERVICE, "-a", account, "-w"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def keychain_set(account: str, secret: str) -> None:
    """Keychain 에 generic password 저장 (있으면 갱신). 실패 시 ConfigError."""
    if not keychain_available():
        raise ConfigError("Keychain 은 macOS 에서만 사용할 수 있습니다.")
    try:
        result = subprocess.run(
            ["security", "add-generic-password",
             "-s", KEYCHAIN_SERVICE, "-a", account, "-w", secret, "-U"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigError(f"Keychain 저장 실패: {exc}") from exc
    if result.returncode != 0:
        raise ConfigError(f"Keychain 저장 실패: {result.stderr.strip()}")


def keychain_delete(account: str) -> bool:
    """Keychain 항목 삭제. 삭제했으면 True."""
    if not keychain_available():
        return False
    try:
        result = subprocess.run(
            ["security", "delete-generic-password",
             "-s", KEYCHAIN_SERVICE, "-a", account],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


class ConfigError(Exception):
    """설정이 누락되었거나 잘못된 경우."""


@dataclass(frozen=True)
class Config:
    client_id: str
    client_secret: str
    base_url: str = DEFAULT_BASE_URL
    account_seq: int | None = None

    def with_account(self, account_seq: int | None) -> "Config":
        """계좌를 덮어쓴 새 Config 사본을 반환 (불변 패턴)."""
        if account_seq is None:
            return self
        return Config(
            client_id=self.client_id,
            client_secret=self.client_secret,
            base_url=self.base_url,
            account_seq=account_seq,
        )

    def require_account(self) -> int:
        if self.account_seq is None:
            raise ConfigError(
                "계좌가 지정되지 않았습니다. --account 옵션을 사용하거나 "
                "TOSS_ACCOUNT_SEQ 환경변수를 설정하세요. "
                "(`toss account list` 로 accountSeq 확인)"
            )
        return self.account_seq


def _load_dotenv(path: Path) -> dict[str, str]:
    """간단한 .env 파서 (의존성 없이). KEY=VALUE 형식만 지원."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _load_config_file(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _coerce_account(raw: object) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"account_seq 값이 정수가 아닙니다: {raw!r}") from exc


def flag_enabled(name: str, dotenv_path: Path | None = None) -> bool:
    """불리언 플래그 조회. 우선순위: 환경변수 > .env(cwd)."""
    raw = os.environ.get(name) or _load_dotenv(dotenv_path or Path.cwd() / ".env").get(name, "")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_config(dotenv_path: Path | None = None) -> Config:
    """우선순위: 환경변수 > .env(cwd) > macOS Keychain > ~/.toss-cli/config.toml.

    누락된 필수 자격증명이 있으면 ConfigError 를 발생시킵니다.
    """
    file_cfg = _load_config_file(CONFIG_FILE)
    dotenv = _load_dotenv(dotenv_path or Path.cwd() / ".env")

    def pick(env_key: str, file_key: str) -> str | None:
        if os.environ.get(env_key):
            return os.environ[env_key]
        if dotenv.get(env_key):
            return dotenv[env_key]
        if env_key in KEYCHAIN_KEYS and (kc := keychain_get(KEYCHAIN_KEYS[env_key])):
            return kc
        value = file_cfg.get(file_key)
        return str(value) if value is not None else None

    client_id = pick("TOSS_CLIENT_ID", "client_id")
    client_secret = pick("TOSS_CLIENT_SECRET", "client_secret")
    base_url = pick("TOSS_BASE_URL", "base_url") or DEFAULT_BASE_URL
    account_raw = pick("TOSS_ACCOUNT_SEQ", "account_seq")

    missing = [
        name
        for name, value in (("TOSS_CLIENT_ID", client_id), ("TOSS_CLIENT_SECRET", client_secret))
        if not value
    ]
    if missing:
        raise ConfigError(
            "자격증명이 없습니다: "
            + ", ".join(missing)
            + ". .env 파일(.env.example 참고) 또는 환경변수로 설정하세요."
        )

    return Config(
        client_id=client_id,  # type: ignore[arg-type]
        client_secret=client_secret,  # type: ignore[arg-type]
        base_url=base_url.rstrip("/"),
        account_seq=_coerce_account(account_raw),
    )
