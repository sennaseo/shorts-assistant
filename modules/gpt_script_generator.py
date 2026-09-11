from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Mapping

from .llm_script_generator import _build_prompt
from .script_generator import DISCLOSURE

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "").strip() or "gpt-4o-mini"


def gpt_available(api_key: str = "") -> bool:
    return bool(api_key or os.getenv("OPENAI_API_KEY", "").strip())


def generate_script_gpt(
    product_info: Mapping[str, Any],
    api_key: str = "",
    model: str = "",
    timeout: int = 60,
) -> dict[str, str]:
    """OpenAI Chat Completions로 대본 생성. 실패 시 예외를 던지므로 호출부에서 템플릿으로 폴백한다."""
    key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")

    payload = {
        "model": model or DEFAULT_MODEL,
        "max_completion_tokens": 1024,
        "messages": [{"role": "user", "content": _build_prompt(product_info)}],
    }
    request = urllib.request.Request(
        OPENAI_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"OpenAI API 오류(HTTP {exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI API 접속 실패: {exc.reason}") from exc

    choices = data.get("choices") or []
    raw = (choices[0].get("message", {}).get("content") if choices else "") or ""
    script = "\n".join(line.strip() for line in raw.splitlines() if line.strip())
    if not script:
        raise RuntimeError("OpenAI API 응답에서 대본을 찾지 못했습니다.")
    return {"script": script, "disclosure": DISCLOSURE, "source": "gpt"}
