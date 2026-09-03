from __future__ import annotations

import io
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


# Higgsfield 개발자 API — API 키/시크릿은 higgsfield.ai 대시보드에서 발급
# 스펙 출처: 공식 SDK 소스 + 공식 문서 (platform.higgsfield.ai)
DEFAULT_BASE_URL = "https://platform.higgsfield.ai"
DEFAULT_MODEL = os.getenv("HIGGSFIELD_MODEL", "").strip() or "higgsfield-ai/dop/standard"
GENERATION_TIMEOUT_SEC = 600
POLL_INTERVAL_SEC = 5.0

# platform.higgsfield.ai는 Cloudflare 뒤에 있어 User-Agent가 없으면 403(error code 1010)으로 차단된다.
# 공식 SDK와 동일한 UA를 보내야 통과한다.
USER_AGENT = "higgsfield-client-py/1.0"

# Cloudflare 봇 스코어링이 간헐적으로 SDK UA도 1010으로 차단한다(2026-07-20 실측 — 같은 요청이
# 몇 분 뒤 재시도에서 통과). 1010이면 잠시 대기 후 브라우저 UA로 한 번 더 시도한다.
FALLBACK_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
CLOUDFLARE_RETRY_DELAY_SEC = 3.0

_MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def _api_key() -> str:
    return os.getenv("HIGGSFIELD_API_KEY", "").strip()


def _api_secret() -> str:
    return os.getenv("HIGGSFIELD_API_SECRET", "").strip()


def is_higgsfield_available() -> bool:
    return bool(_api_key())


def _auth_header() -> str:
    return f"Key {_api_key()}:{_api_secret()}"


def _guess_mime(image: Path) -> str:
    return _MIME_BY_EXT.get(image.suffix.lower(), "image/png")


def _extract_error_message(body: str) -> str:
    """4xx/5xx 응답 바디에서 에러 메시지를 추출한다. detail → details → message → error → 원문 순."""
    try:
        data = json.loads(body)
    except Exception:
        return body[:200]
    if isinstance(data, dict):
        for key in ("detail", "details", "message", "error"):
            value = data.get(key)
            if value:
                return str(value)[:200]
    return body[:200]


def _is_cloudflare_block(exc: urllib.error.HTTPError) -> tuple[bool, str]:
    """403이 Cloudflare 1010 차단인지 판별하고 (차단 여부, 읽은 바디)를 반환한다."""
    if exc.code != 403:
        return False, ""
    try:
        body = exc.read().decode("utf-8")
    except Exception:
        return False, ""
    return "1010" in body, body


def _request_json(method: str, url: str, payload: dict | None = None, timeout: float = 30) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    for attempt, user_agent in enumerate((USER_AGENT, FALLBACK_USER_AGENT)):
        headers = {
            "Content-Type": "application/json",
            "Authorization": _auth_header(),
            "User-Agent": user_agent,
        }
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            blocked, body = _is_cloudflare_block(exc)
            if blocked and attempt == 0:
                time.sleep(CLOUDFLARE_RETRY_DELAY_SEC)
                continue
            # exc.read()를 이미 소모했으므로 상위에서 다시 읽지 못한다 — 바디를 담아 재구성한다.
            if body:
                raise urllib.error.HTTPError(url, exc.code, exc.reason, exc.headers, io.BytesIO(body.encode("utf-8")))
            raise
    raise RuntimeError("unreachable")


def _upload_image(base_url: str, image: Path, image_bytes: bytes, timeout: float = 60) -> tuple[str | None, str | None]:
    """이미지를 업로드하고 (public_url, error) 튜플을 반환한다."""
    mime = _guess_mime(image)

    upload_info = _request_json(
        "POST",
        f"{base_url}/files/generate-upload-url",
        {"content_type": mime},
        timeout=30,
    )
    upload_url = upload_info.get("upload_url")
    public_url = upload_info.get("public_url")
    if not upload_url or not public_url:
        return None, "Higgsfield 업로드 URL 발급 실패"

    # presigned URL이므로 Authorization 헤더를 붙이지 않는다.
    # 서명에 포함된 헤더(x-amz-tagging 등)는 응답의 upload_headers로 내려온다 —
    # 이걸 그대로 보내지 않으면 SignatureDoesNotMatch(403)가 난다 (2026-08-05 실측).
    put_headers = upload_info.get("upload_headers") or {"Content-Type": mime}
    put_req = urllib.request.Request(
        upload_url,
        data=image_bytes,
        method="PUT",
        headers=put_headers,
    )
    with urllib.request.urlopen(put_req, timeout=timeout):
        pass

    return public_url, None


def _wait_for_completion(base_url: str, status_url: str | None, request_id: str, timeout_sec: float) -> dict:
    url = status_url or f"{base_url}/requests/{request_id}/status"
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        result = _request_json("GET", url, timeout=30)
        status = result.get("status")
        if status in ("completed", "failed", "nsfw", "canceled"):
            return result
        time.sleep(POLL_INTERVAL_SEC)
    return {"status": "timeout"}


def _extract_video_url(result: dict) -> str | None:
    video_url = result.get("video", {}).get("url")
    if video_url:
        return video_url
    images = result.get("images") or []
    if images and isinstance(images, list):
        return images[0].get("url")
    return None


def generate_higgsfield_video(
    image_path: str | Path,
    prompt: str,
    output_dir: str | Path,
    aspect_ratio: str = "9:16",
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    timeout_sec: int = GENERATION_TIMEOUT_SEC,
) -> dict[str, object]:
    """제품 이미지 한 장 + 프롬프트로 짧은 영상 클립을 생성한다.

    HIGGSFIELD_API_KEY(.env)가 없으면 즉시 건너뛴다 — 나머지 파이프라인은 계속 진행되고
    project_manager.py는 이미지 슬라이드쇼(video_renderer.py)로 자동 대체한다.

    aspect_ratio는 시그니처 호환을 위해서만 받고 실제 요청에는 보내지 않는다
    (image-to-video 생성 요청 예제에 이 필드가 없고, 알 수 없는 필드는 422를 유발할 수 있음).
    """
    if not is_higgsfield_available():
        return {"path": None, "success": False, "error": "HIGGSFIELD_API_KEY가 설정되지 않아 건너뜁니다."}

    image = Path(image_path)
    if not image.exists():
        return {"path": None, "success": False, "error": f"이미지 파일을 찾을 수 없습니다: {image}"}

    try:
        # 1) 이미지 업로드 → public_url 발급
        image_bytes = image.read_bytes()
        public_url, upload_error = _upload_image(base_url, image, image_bytes)
        if upload_error:
            return {"path": None, "success": False, "error": upload_error}

        # 2) 영상 생성 요청 (model이 URL 경로, 바디는 wrapper 없이 top-level)
        job = _request_json(
            "POST",
            f"{base_url}/{model}",
            {"image_url": public_url, "prompt": prompt},
            timeout=30,
        )
        request_id = job.get("request_id")
        if not request_id:
            return {"path": None, "success": False, "error": f"Higgsfield 생성 요청 실패: {job}"}

        result = _wait_for_completion(base_url, job.get("status_url"), request_id, timeout_sec)
        status = result.get("status", "timeout")

        if status == "timeout":
            return {"path": None, "success": False, "error": f"Higgsfield 생성 시간 초과({timeout_sec}초)."}
        if status in ("failed", "nsfw", "canceled"):
            return {
                "path": None,
                "success": False,
                "error": f"Higgsfield 생성 실패(status={status}): {result.get('error') or result}. "
                "failed/nsfw인 경우 크레딧은 자동 환불됩니다.",
            }

        video_url = _extract_video_url(result)
        if not video_url:
            return {"path": None, "success": False, "error": "완료됐지만 결과 영상 URL이 없습니다."}

        video_req = urllib.request.Request(video_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(video_req, timeout=120) as resp:
            video_bytes = resp.read()

        output_path = Path(output_dir) / "higgsfield_clip.mp4"
        output_path.write_bytes(video_bytes)
        return {"path": output_path, "success": True, "error": ""}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = _extract_error_message(exc.read().decode("utf-8"))
        except Exception:
            pass
        return {"path": None, "success": False, "error": f"Higgsfield API 오류({exc.code}): {detail}"}
    except Exception as exc:
        return {"path": None, "success": False, "error": f"Higgsfield 영상 생성 실패: {exc}"}


# ─────────────────────────── 이미지 생성 (Soul text-to-image) ───────────────────────────
DEFAULT_IMAGE_MODEL = os.getenv("HIGGSFIELD_IMAGE_MODEL", "").strip() or "higgsfield-ai/soul/standard"
# 첨부 이미지가 있을 때(참고·수정·합성) 쓰는 모델 — popcorn/auto는 image_urls 최대 8장.
# nano-banana·flux-kontext는 이 계정에서 404 model_not_found, reve/*는 423 model_blocked (2026-08-19 실측).
DEFAULT_EDIT_MODEL = os.getenv("HIGGSFIELD_EDIT_MODEL", "").strip() or "higgsfield-ai/popcorn/auto"
IMAGE_ASPECT_RATIOS = ("1:1", "4:3", "3:4", "3:2", "2:3", "5:4", "4:5", "16:9", "9:16", "21:9")
MAX_REFERENCE_IMAGES = 8
_ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth")
_EXT_BY_MIME = {v: k for k, v in _MIME_BY_EXT.items() if k != ".jpeg"}


def generate_higgsfield_image(
    prompt: str,
    output_dir: str | Path,
    aspect_ratio: str = "9:16",
    num_images: int = 1,
    resolution: str = "",
    file_prefix: str = "img_",
    reference_images: list[str | Path] | None = None,
    base_url: str = DEFAULT_BASE_URL,
    model: str = "",
    timeout_sec: int = GENERATION_TIMEOUT_SEC,
) -> dict[str, object]:
    """텍스트 프롬프트(+선택: 참고 이미지들)로 사진/그림을 생성해 output_dir에 저장한다. 반환: {paths, success, error}.

    - reference_images 없음 → DEFAULT_IMAGE_MODEL(Soul) 텍스트→이미지
    - reference_images 있음 → DEFAULT_EDIT_MODEL(popcorn/auto) — 첨부 사진을 참고/수정/합성
    영상 생성과 같은 요청/폴링 프로토콜 — POST /{model} → status_url 폴링 → images[].url 다운로드.
    """
    if not is_higgsfield_available():
        return {"paths": [], "success": False, "error": "HIGGSFIELD_API_KEY가 설정되지 않았습니다."}
    prompt = (prompt or "").strip()
    if not prompt:
        return {"paths": [], "success": False, "error": "프롬프트가 비어 있습니다."}
    refs = [Path(p) for p in (reference_images or [])][:MAX_REFERENCE_IMAGES]
    for ref in refs:
        if not ref.is_file():
            return {"paths": [], "success": False, "error": f"참고 이미지를 찾을 수 없습니다: {ref.name}"}
    if not model:
        model = DEFAULT_EDIT_MODEL if refs else DEFAULT_IMAGE_MODEL
    if aspect_ratio not in IMAGE_ASPECT_RATIOS:
        aspect_ratio = "9:16"
    num_images = min(4, max(1, int(num_images or 1)))
    # 첨부가 2장 이상이면 프롬프트에서 "first image"/"second image"로 지목할 수 있게 순서를 명시한다.
    # (image_urls 순서 = 첨부 순서지만, 모델은 프롬프트에 적힌 순서 라벨을 보고 구분한다)
    if len(refs) > 1:
        labels = ", ".join(f"{_ORDINALS[i]} image = {ref.name}" for i, ref in enumerate(refs))
        prompt = (f"Reference images are given in this order: {labels}. "
                  f"Refer to them as first/second image in that order.\n{prompt}")

    try:
        payload = {"prompt": prompt, "aspect_ratio": aspect_ratio, "num_images": num_images}
        if resolution:   # soul/standard는 '720p'|'1080p'만 받는다(2026-08-19 실측 422). 비우면 서버 기본값.
            payload["resolution"] = resolution
        if refs:
            urls = []
            for ref in refs:
                public_url, err = _upload_image(base_url, ref, ref.read_bytes())
                if err:
                    return {"paths": [], "success": False, "error": err}
                urls.append(public_url)
            payload["image_urls"] = urls
        job = _request_json("POST", f"{base_url}/{model}", payload, timeout=30)
        request_id = job.get("request_id")
        if not request_id:
            return {"paths": [], "success": False, "error": f"Higgsfield 생성 요청 실패: {job}"}

        result = _wait_for_completion(base_url, job.get("status_url"), request_id, timeout_sec)
        status = result.get("status", "timeout")
        if status == "timeout":
            return {"paths": [], "success": False, "error": f"Higgsfield 생성 시간 초과({timeout_sec}초)."}
        if status != "completed":
            return {"paths": [], "success": False,
                    "error": f"Higgsfield 생성 실패(status={status}): {result.get('error') or result}"}

        urls = [im.get("url") for im in (result.get("images") or []) if isinstance(im, dict) and im.get("url")]
        if not urls:
            return {"paths": [], "success": False, "error": "완료됐지만 결과 이미지 URL이 없습니다."}

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for i, url in enumerate(urls):
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as resp:
                mime = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
                data = resp.read()
            ext = _EXT_BY_MIME.get(mime) or Path(url.split("?")[0]).suffix.lower() or ".png"
            if ext not in _MIME_BY_EXT:
                ext = ".png"
            path = out_dir / f"{file_prefix}{i}{ext}"
            path.write_bytes(data)
            paths.append(path)
        return {"paths": paths, "success": True, "error": ""}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = _extract_error_message(exc.read().decode("utf-8"))
        except Exception:
            pass
        return {"paths": [], "success": False, "error": f"Higgsfield API 오류({exc.code}): {detail}"}
    except Exception as exc:
        return {"paths": [], "success": False, "error": f"Higgsfield 이미지 생성 실패: {exc}"}
