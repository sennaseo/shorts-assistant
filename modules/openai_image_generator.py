from __future__ import annotations

import base64
import json
import mimetypes
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path


# OpenAI Images API — 표준 API 키 사용(ChatGPT 구독 쿼터가 아니라 API 크레딧에서 차감).
# 첨부 없음 → POST /v1/images/generations, 첨부 있음 → POST /v1/images/edits (multipart, image[] 반복)
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "").strip() or "gpt-image-2"
GENERATION_TIMEOUT_SEC = 300
MAX_REFERENCE_IMAGES = 8
_ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth")

# gpt-image-2 실측(2026-08-30): 폭·높이 모두 16의 배수여야 하고, 긴 변 1824까지 그대로 나온다.
# ("1024x1365"는 422 — divisible by 16). 비율별로 짧은 변 1024 기준 16의 배수로 맞춘 값.
SIZE_BY_ASPECT = {
    "1:1": "1024x1024",
    "9:16": "1024x1824",
    "16:9": "1824x1024",
    "4:5": "1024x1280",
    "5:4": "1280x1024",
    "3:4": "1024x1360",
    "4:3": "1360x1024",
    "2:3": "1024x1536",
    "3:2": "1536x1024",
}
IMAGE_ASPECT_RATIOS = tuple(SIZE_BY_ASPECT)
_EXT_BY_FORMAT = {"png": ".png", "webp": ".webp", "jpeg": ".jpg"}


def _api_key() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip()


def is_openai_image_available() -> bool:
    return bool(_api_key())


def _extract_error_message(body: str) -> str:
    """4xx/5xx 응답 바디에서 사람이 읽을 메시지를 뽑는다."""
    try:
        data = json.loads(body)
    except Exception:
        return (body or "").strip()[:400]
    err = data.get("error")
    if isinstance(err, dict):
        return str(err.get("message") or err)[:400]
    return str(err or data)[:400]


def _multipart(fields: list[tuple[str, str]], files: list[tuple[str, Path]]) -> tuple[bytes, str]:
    """multipart/form-data 본문을 만든다. files는 (필드명, 경로) — 같은 필드명을 여러 번 넣을 수 있다."""
    boundary = "----shorts" + uuid.uuid4().hex
    buf = bytearray()
    for name, value in fields:
        buf += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8")
    for name, path in files:
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        buf += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; "
                f"filename=\"{path.name}\"\r\nContent-Type: {mime}\r\n\r\n").encode("utf-8")
        buf += path.read_bytes() + b"\r\n"
    buf += f"--{boundary}--\r\n".encode("utf-8")
    return bytes(buf), f"multipart/form-data; boundary={boundary}"


def generate_openai_image(
    prompt: str,
    output_dir: str | Path,
    aspect_ratio: str = "9:16",
    num_images: int = 1,
    file_prefix: str = "img_",
    reference_images: list[str | Path] | None = None,
    model: str = "",
    output_format: str = "png",
    quality: str = "",
    base_url: str = DEFAULT_BASE_URL,
    timeout_sec: int = GENERATION_TIMEOUT_SEC,
) -> dict[str, object]:
    """텍스트 프롬프트(+선택: 참고 이미지들)로 이미지를 만들어 output_dir에 저장한다. 반환: {paths, success, error}.

    Higgsfield 쪽 generate_higgsfield_image와 반환 형태를 맞춰 두 엔진을 같은 코드로 다룰 수 있게 했다.
    - reference_images 없음 → /images/generations
    - reference_images 있음 → /images/edits (image[]를 순서대로 반복 — 그 순서가 first/second)
    """
    if not is_openai_image_available():
        return {"paths": [], "success": False, "error": "OPENAI_API_KEY가 설정되지 않았습니다."}
    prompt = (prompt or "").strip()
    if not prompt:
        return {"paths": [], "success": False, "error": "프롬프트가 비어 있습니다."}

    refs = [Path(p) for p in (reference_images or [])][:MAX_REFERENCE_IMAGES]
    for ref in refs:
        if not ref.is_file():
            return {"paths": [], "success": False, "error": f"참고 이미지를 찾을 수 없습니다: {ref.name}"}

    size = SIZE_BY_ASPECT.get(aspect_ratio) or SIZE_BY_ASPECT["9:16"]
    num_images = min(4, max(1, int(num_images or 1)))
    model = model or DEFAULT_MODEL
    output_format = output_format if output_format in _EXT_BY_FORMAT else "png"

    # 첨부가 2장 이상이면 프롬프트에서 "first image"/"second image"로 지목할 수 있게 순서를 명시한다.
    # (image[] 전송 순서 = 첨부 순서지만, 모델은 프롬프트에 적힌 순서 라벨을 보고 구분한다)
    if len(refs) > 1:
        labels = ", ".join(f"{_ORDINALS[i]} image = {ref.name}" for i, ref in enumerate(refs))
        prompt = (f"Reference images are given in this order: {labels}. "
                  f"Refer to them as first/second image in that order.\n{prompt}")

    try:
        if refs:
            fields = [("model", model), ("prompt", prompt), ("size", size),
                      ("n", str(num_images)), ("output_format", output_format)]
            if quality:
                fields.append(("quality", quality))
            body, content_type = _multipart(fields, [("image[]", ref) for ref in refs])
            url = f"{base_url}/images/edits"
            headers = {"Authorization": f"Bearer {_api_key()}", "Content-Type": content_type}
        else:
            payload = {"model": model, "prompt": prompt, "size": size,
                       "n": num_images, "output_format": output_format}
            if quality:
                payload["quality"] = quality
            body = json.dumps(payload).encode("utf-8")
            url = f"{base_url}/images/generations"
            headers = {"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"}

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        items = [it for it in (result.get("data") or []) if isinstance(it, dict) and it.get("b64_json")]
        if not items:
            return {"paths": [], "success": False, "error": f"결과 이미지가 없습니다: {result}"}

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        ext = _EXT_BY_FORMAT[output_format]
        paths = []
        for i, item in enumerate(items):
            path = out_dir / f"{file_prefix}{i}{ext}"
            path.write_bytes(base64.b64decode(item["b64_json"]))
            paths.append(path)
        return {"paths": paths, "success": True, "error": ""}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = _extract_error_message(exc.read().decode("utf-8"))
        except Exception:
            pass
        return {"paths": [], "success": False, "error": f"OpenAI 이미지 API 오류({exc.code}): {detail}"}
    except Exception as exc:  # 네트워크/타임아웃
        return {"paths": [], "success": False, "error": f"OpenAI 이미지 생성 실패: {exc}"}
