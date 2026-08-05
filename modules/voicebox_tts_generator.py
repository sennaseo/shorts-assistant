from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path


# Voicebox 데스크톱 앱이 REST+MCP를 함께 서빙하는 고정 포트 (8000은 별도 단독 서버용)
DEFAULT_BASE_URL = "http://127.0.0.1:17493"
DEFAULT_ENGINE = "qwen_custom_voice"
DEFAULT_MODEL_SIZE = "0.6B"
GENERATION_TIMEOUT_SEC = 900


def _request_json(method: str, url: str, payload: dict | None = None, timeout: float = 15) -> dict | list:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download_bytes(url: str, timeout: float = 60) -> tuple[bytes, str]:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(), resp.headers.get("Content-Type", "")


def _wait_for_completion(base_url: str, generation_id: str, timeout_sec: float) -> dict:
    # status 엔드포인트는 JSON이 아니라 SSE 스트림(data: {...} 라인)으로 응답한다
    deadline = time.monotonic() + timeout_sec
    req = urllib.request.Request(f"{base_url}/generate/{generation_id}/status")
    with urllib.request.urlopen(req, timeout=60) as resp:
        for raw_line in resp:
            if time.monotonic() > deadline:
                return {"status": "timeout"}
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            try:
                event = json.loads(line[5:].strip())
            except Exception:
                continue
            if event.get("status") in ("completed", "failed"):
                return event
    return {"status": "timeout"}


def is_voicebox_available(base_url: str = DEFAULT_BASE_URL) -> bool:
    try:
        health = _request_json("GET", f"{base_url}/health", timeout=3)
        return isinstance(health, dict) and health.get("status") == "healthy"
    except Exception:
        return False


def _resolve_profile(base_url: str, profile: str = "", language: str = "ko") -> dict | None:
    profiles = _request_json("GET", f"{base_url}/profiles", timeout=10)
    if not isinstance(profiles, list) or not profiles:
        return None
    if profile:
        for item in profiles:
            if profile in (item.get("id"), item.get("name")):
                return item
    for item in profiles:
        if item.get("language") == language:
            return item
    return profiles[0]


def generate_voicebox_tts(
    text: str,
    output_dir: str | Path,
    profile: str = "",
    language: str = "ko",
    base_url: str = DEFAULT_BASE_URL,
    engine: str = DEFAULT_ENGINE,
    model_size: str = DEFAULT_MODEL_SIZE,
    timeout_sec: int = GENERATION_TIMEOUT_SEC,
) -> dict[str, object]:
    clean_text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not clean_text:
        return {"path": None, "success": False, "error": "TTS로 변환할 문장이 없습니다."}

    if not is_voicebox_available(base_url):
        return {"path": None, "success": False, "error": f"Voicebox 서버({base_url})에 연결할 수 없습니다."}

    try:
        resolved = _resolve_profile(base_url, profile, language)
        if not resolved:
            return {
                "path": None,
                "success": False,
                "error": "Voicebox에 음성 프로필이 없습니다. Voicebox 앱에서 프로필을 먼저 만들어 주세요.",
            }

        generation = _request_json(
            "POST",
            f"{base_url}/generate",
            {
                "profile_id": resolved["id"],
                "text": clean_text,
                "language": language,
                "engine": resolved.get("default_engine") or engine,
                "model_size": model_size,
            },
            timeout=60,
        )
        generation_id = generation["id"]

        status = str(generation.get("status") or "pending")
        if status not in ("completed", "failed"):
            generation = _wait_for_completion(base_url, generation_id, timeout_sec)
            status = str(generation.get("status") or "pending")

        if status == "failed":
            return {"path": None, "success": False, "error": f"Voicebox 생성 실패: {generation.get('error')}"}
        if status != "completed":
            return {"path": None, "success": False, "error": f"Voicebox 생성 시간 초과({timeout_sec}초)."}

        audio_bytes, content_type = _download_bytes(f"{base_url}/audio/{generation_id}", timeout=120)
        suffix = ".mp3" if "mpeg" in content_type or "mp3" in content_type else ".wav"
        # 파일명은 CapCut 패키지/히스토리 탭이 찾는 edge_tts_test.* 이름을 그대로 유지
        output_path = Path(output_dir) / f"edge_tts_test{suffix}"
        output_path.write_bytes(audio_bytes)
        return {
            "path": output_path,
            "success": True,
            "error": "",
            "profile": resolved.get("name"),
            "duration": generation.get("duration"),
        }
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:200]
        except Exception:
            pass
        return {"path": None, "success": False, "error": f"Voicebox API 오류({exc.code}): {detail}"}
    except Exception as exc:
        return {"path": None, "success": False, "error": f"Voicebox TTS 생성 실패: {exc}"}
