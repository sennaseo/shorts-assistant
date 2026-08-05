from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Mapping

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")


def llm_available(api_key: str = "") -> bool:
    return bool(api_key or os.getenv("ANTHROPIC_API_KEY", "").strip())


def _build_prompt(info: Mapping[str, Any]) -> str:
    def v(key: str, default: str = "미입력") -> str:
        return str(info.get(key) or default).strip()

    category = v("category", "제품")
    cta_target = f"프로필 링크의 {category}" if info.get("category") else "프로필 링크"
    return f"""당신은 제품 추천 쇼츠(유튜브 쇼츠/틱톡) 대본 작가입니다. 아래 제품 정보로 한국어 나레이션 대본을 작성하세요.

제품 정보:
- 제품명: {v("product_name")}
- 카테고리: {category}
- 가격대: {v("price_range")}
- 타겟 사용자: {v("target_user")}
- 장점 1: {v("advantage_1")}
- 장점 2: {v("advantage_2")}
- 장점 3: {v("advantage_3")}
- 단점/주의점: {v("caution")}
- 톤: {v("tone", "친구 추천형")}
- 목표 길이: 약 {v("target_length", "40")}초 (TTS 낭독 기준)

작성 규칙:
1. 첫 문장은 시청자가 2초 안에 멈추게 하는 훅으로 시작한다.
2. 장점 3개를 자연스럽게 녹이되, 과장 광고 표현(최고, 무조건, 인생템 남발)은 피한다.
3. 단점/주의점을 솔직하게 한 문장 포함한다.
4. 마지막 문장은 "{cta_target}에서 확인" 형태의 CTA로 끝낸다.
5. 문장은 짧게, TTS로 읽기 좋게 쓴다. 이모지, 해시태그, 장면 지시문 금지.
6. 출력은 대본 문장만, 한 줄에 한 문장씩. 다른 설명이나 머리말을 붙이지 않는다.
"""


def generate_script_llm(
    product_info: Mapping[str, Any],
    api_key: str = "",
    model: str = "",
    timeout: int = 60,
) -> dict[str, str]:
    """Claude API로 대본 생성. 실패 시 예외를 던지므로 호출부에서 템플릿으로 폴백한다."""
    key = (api_key or os.getenv("ANTHROPIC_API_KEY", "")).strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    payload = {
        "model": model or DEFAULT_MODEL,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": _build_prompt(product_info)}],
    }
    request = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Claude API 오류(HTTP {exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Claude API 접속 실패: {exc.reason}") from exc

    parts = [block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"]
    script = "\n".join(line.strip() for line in "\n".join(parts).splitlines() if line.strip())
    if not script:
        raise RuntimeError("Claude API 응답에서 대본을 찾지 못했습니다.")
    return {"script": script, "source": "llm"}
