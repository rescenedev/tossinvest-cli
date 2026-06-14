"""API 에러 모델.

토스 Open API 의 표준 에러 envelope:
    {"error": {"requestId": "...", "code": "...", "message": "...", "data": {...}}}
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TossApiError(Exception):
    """API 가 반환한 구조화된 에러."""

    status_code: int
    code: str
    message: str
    request_id: str | None = None
    data: object | None = None

    def __str__(self) -> str:
        # status_code 0 = 네트워크/로컬 오류 → 무의미한 '0' 대신 코드만 표시.
        head = f"{self.status_code} {self.code}" if self.status_code else self.code
        base = f"[{head}] {self.message}"
        if self.request_id:
            base += f" (requestId={self.request_id})"
        return base

    @classmethod
    def from_response(cls, status_code: int, body: object) -> "TossApiError":
        """응답 본문에서 에러를 파싱. 형식이 다르면 안전하게 폴백."""
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict):
                return cls(
                    status_code=status_code,
                    code=str(err.get("code", "unknown")),
                    message=str(err.get("message", "알 수 없는 오류")),
                    request_id=err.get("requestId"),
                    data=err.get("data"),
                )
        text = str(body)
        if text.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
            # CDN/WAF 차단 페이지 등 HTML 응답 — 원문 대신 요약만 노출.
            return cls(
                status_code=status_code,
                code="blocked",
                message=(
                    "요청이 서버(CDN/WAF)에서 차단되었습니다. "
                    "짧은 시간에 요청이 많았다면 잠시 후 다시 시도하세요."
                ),
            )
        return cls(
            status_code=status_code,
            code="unknown",
            message=text[:500] or "알 수 없는 오류",
        )
