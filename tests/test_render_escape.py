"""print_* 가 메시지의 대괄호를 rich 마크업으로 오인하지 않는지 검증."""

from toss_cli import render


def _cap(fn, msg):
    with render.console.capture() as cap:
        fn(msg)
    return cap.get()


def test_error_preserves_brackets(monkeypatch):
    # err_console 을 일반 console 로 바꿔 캡처
    monkeypatch.setattr(render, "err_console", render.console)
    out = _cap(render.print_error, "[400 invalid-request] 잘못된 요청")
    assert "[400 invalid-request]" in out


def test_warning_and_success_preserve_brackets():
    assert "[network-error]" in _cap(render.print_warning, "[network-error] 실패")
    assert "[SIM]" in _cap(render.print_success, "[SIM] 접수됨")
