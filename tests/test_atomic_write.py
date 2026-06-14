"""원자적 파일 쓰기 유틸 테스트."""


from toss_cli.config import atomic_write


def test_writes_content_and_creates_parent(tmp_path):
    target = tmp_path / "sub" / "f.json"
    atomic_write(target, '{"a": 1}')
    assert target.read_text(encoding="utf-8") == '{"a": 1}'


def test_overwrites_existing(tmp_path):
    target = tmp_path / "f.txt"
    target.write_text("old", encoding="utf-8")
    atomic_write(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_applies_mode_600(tmp_path):
    target = tmp_path / "token.json"
    atomic_write(target, "secret", mode=0o600)
    assert (target.stat().st_mode & 0o777) == 0o600


def test_no_leftover_temp_files(tmp_path):
    target = tmp_path / "f.json"
    atomic_write(target, "x")
    atomic_write(target, "y")
    # 임시 파일(.f.json.*.tmp)이 남지 않아야 한다
    leftovers = [p for p in tmp_path.iterdir() if p.name != "f.json"]
    assert leftovers == []


def test_cleans_temp_on_write_error(tmp_path, monkeypatch):
    import toss_cli.config as cfg

    def boom(*a, **k):
        raise OSError("disk full")

    target = tmp_path / "f.json"
    monkeypatch.setattr(cfg.os, "replace", boom)
    try:
        atomic_write(target, "x")
    except OSError:
        pass
    assert list(tmp_path.iterdir()) == []  # 임시 파일 정리됨
