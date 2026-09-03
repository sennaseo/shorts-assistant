#!/usr/bin/env python3
"""
pipeline_server.py — Shorts 자동화 파이프라인 실행 서버 (n8n 스타일)
─────────────────────────────────────────────────────────────
실행:  python pipeline_server.py          (또는 run_pipeline_server.bat)
접속:  http://localhost:8787

브라우저 폼(웹훅 트리거 역할)으로 제품 정보를 입력하면
shorts-assistant의 실제 모듈들이 노드 순서대로 실행되고,
진행 상황이 SSE로 캔버스에 실시간 표시됩니다.

의존성: shorts-assistant requirements.txt 그대로 (표준라이브러리 서버, 추가 설치 없음)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import queue
import re
import sys
import threading
import time
import traceback
import uuid
from datetime import datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv                                            # noqa: E402
load_dotenv(ROOT / ".env")

from modules.script_generator import generate_script                      # noqa: E402
from modules.llm_script_generator import generate_script_llm, llm_available  # noqa: E402
from modules.gpt_script_generator import generate_script_gpt, gpt_available  # noqa: E402
from modules.higgsfield_video_generator import (                          # noqa: E402
    generate_higgsfield_video, generate_higgsfield_image, is_higgsfield_available)
from modules.openai_image_generator import (                              # noqa: E402
    generate_openai_image, is_openai_image_available)
from modules.edge_tts_generator import generate_edge_tts                  # noqa: E402
from modules.voicebox_tts_generator import generate_voicebox_tts, is_voicebox_available  # noqa: E402
from modules.typecast_formatter import format_for_typecast                # noqa: E402
from modules.subtitle_generator import save_capcut_subtitles              # noqa: E402
from modules.srt_generator import save_srt, get_audio_duration_seconds    # noqa: E402
from modules.upload_text_generator import generate_upload_text            # noqa: E402

PORT = int(os.environ.get("PIPELINE_PORT", "8787"))
HOST = os.environ.get("PIPELINE_HOST", "127.0.0.1")   # 도커에서만 0.0.0.0
APP_PASSWORD = os.environ.get("APP_PASSWORD", "").strip()  # 비어 있으면 게이트 없음 (Task 2에서 사용)
RUNS_DIR = ROOT / "outputs" / "pipeline_runs"
UPLOADS_DIR = RUNS_DIR / "_uploads"
UPLOAD_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
UI_FILE = ROOT / "pipeline_ui.html"
IMAGE_UI_FILE = ROOT / "image_ui.html"

RUNS: dict[str, dict] = {}   # run_id -> {"q": Queue, "history": [], "done": bool}
RUNS_LOCK = threading.Lock()

LOGIN_HTML = """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>쇼츠 만들기 — 로그인</title>
<style>
body{font-family:'Segoe UI','Malgun Gothic','Apple SD Gothic Neo',sans-serif;background:#f2f4ef;color:#111413;
 margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;letter-spacing:-.02em}
form{background:#fff;border-radius:28px;padding:32px 24px;width:min(92vw,380px);box-shadow:0 10px 26px rgba(17,20,19,.06)}
h1{font-size:22px;font-weight:900;margin:0 0 6px}p{color:#5d645f;font-size:14px;margin:0 0 20px}
input{width:100%;box-sizing:border-box;font-size:17px;padding:16px;border:none;border-radius:16px;background:#f3f5f1;margin-bottom:12px}
button{width:100%;font-size:17px;font-weight:800;padding:16px;border:none;border-radius:16px;background:#00d55e;color:#0b3d20}
button:active{transform:scale(.97)}.err{color:#e5484d;font-weight:700}
</style></head><body><form method="post" action="/login">
<h1>쇼츠 만들기</h1><p>비밀번호를 입력하세요</p>{error}
<input type="password" name="password" autofocus autocomplete="current-password" placeholder="비밀번호">
<button type="submit">들어가기</button></form></body></html>"""


# ─────────────────────────── 이벤트 버스 ───────────────────────────
def emit(run_id: str, event: dict) -> None:
    event["ts"] = time.time()
    with RUNS_LOCK:
        run = RUNS.get(run_id)
        if not run:
            return
        run["history"].append(event)
        run["q"].put(event)


def node_event(run_id, node, status, items=None, files=None, note=""):
    emit(run_id, {"type": "node", "node": node, "status": status,
                  "items": items or [], "files": files or [], "note": note})


def log_event(run_id, level, msg):
    emit(run_id, {"type": "log", "level": level, "msg": msg})


# ─────────────────────────── 파이프라인 ───────────────────────────
def file_ref(run_id: str, path: Path) -> dict:
    rel = path.relative_to(RUNS_DIR / run_id)
    return {"name": path.name, "url": f"/files/{run_id}/{rel.as_posix()}",
            "size": f"{path.stat().st_size / 1024:.1f} KB"}


def quality_check(item: dict) -> tuple[bool, str]:
    """IF 노드: 대본 품질 규칙 (자동 분할된 TTS 줄 기준)."""
    lines = item.get("tts_lines") or [l for l in item.get("script", "").splitlines() if l.strip()]
    if not item.get("product_name"):
        return False, "제품명 누락"
    if len(lines) < 4:
        return False, f"대본 분량 부족 ({len(lines)}줄 < 4)"
    if len(lines) > 28:
        return False, f"대본 분량 과다 ({len(lines)}줄 > 28, 60초 초과 위험)"
    still_long = [l for l in lines if len(l) > 80]
    if still_long:
        return False, f"자동 분할 후에도 장문 {len(still_long)}개 (80자 초과)"
    return True, f"통과 ({len(lines)}줄)"


ENGINE_LABEL = {"gpt": "GPT API", "claude": "Claude API", "template": "템플릿"}


def resolve_engine(options: dict) -> str:
    """대본 엔진: gpt | claude | template (기본은 GPT 사용 가능하면 gpt)."""
    engine = (options.get("engine") or ("gpt" if gpt_available() else "template")).lower()
    if engine == "gpt" and not gpt_available():
        engine = "template"
    if engine == "claude" and not llm_available():
        engine = "template"
    return engine


def save_state(run_dir: Path, items: list[dict], options: dict) -> None:
    """단계 재실행의 기반 — items 전체를 문자열 직렬화해 state.json에 저장."""
    def enc(v):
        return str(v) if isinstance(v, Path) else v
    payload = {"options": options,
               "items": [{k: enc(v) for k, v in it.items()} for it in items]}
    (run_dir / "state.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def load_state(run_dir: Path) -> dict | None:
    f = run_dir / "state.json"
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None


# ── 단계 함수: items를 제자리에서 갱신하고 노드 이벤트를 기존과 동일한 순서로 발행 ──
def step_script(run_id, run_dir, items, options):
    """② AI 대본 생성 + 품질 체크(IF). returns (passed, failed)."""
    engine = resolve_engine(options)
    node_event(run_id, "script", "running")
    for it in items:
        src = engine
        if engine in ("gpt", "claude"):
            try:
                result = (generate_script_gpt if engine == "gpt" else generate_script_llm)(it)
            except Exception as exc:
                log_event(run_id, "warn", f"  ↳ {ENGINE_LABEL[engine]} 실패, 템플릿 폴백: {exc}")
                result = generate_script(it)
                src = "template"
        else:
            result = generate_script(it)
        it["script_source"] = src
        it["disclosure"] = result.get("disclosure", "")
        # 긴 문장은 TTS 낭독용 20~35자 줄로 자동 분할 (품질 탈락 방지)
        raw_count = len([l for l in result["script"].splitlines() if l.strip()])
        lines, _numbered = format_for_typecast(result["script"])
        it["tts_lines"] = lines
        it["script"] = "\n".join(lines)
        log_event(run_id, "info",
                  f"  ↳ item[{it['_item']}] '{it.get('product_name','?')}' 대본 "
                  f"{raw_count}문장 → {len(lines)}줄 자동 분할 ({ENGINE_LABEL[src]})")
    node_event(run_id, "script", "success",
               items=[{"json": {k: v for k, v in it.items() if k != "_item"}} for it in items],
               note=f"엔진: {ENGINE_LABEL[engine]} (실패 시 템플릿 자동 폴백)")
    log_event(run_id, "ok", f"✓ [AI 대본 생성] {len(items)} items 출력")

    # ── ③ 품질 체크 (IF) ───────────────────────────────────
    node_event(run_id, "quality", "running")
    passed, failed = [], []
    for it in items:
        ok, reason = quality_check(it)
        it["quality"] = reason
        (passed if ok else failed).append(it)
        log_event(run_id, "info" if ok else "warn",
                  f"  ↳ item[{it['_item']}] {'true' if ok else 'false'}: {reason}")
    time.sleep(0.2)
    node_event(run_id, "quality", "success",
               items=[{"json": {"product_name": it.get("product_name"), "pass": it in passed,
                                "quality": it["quality"]}} for it in items],
               note=f"true {len(passed)} / false {len(failed)} 분기")
    log_event(run_id, "ok", f"✓ [품질 체크 IF] true {len(passed)} / false {len(failed)}")
    if not passed:
        log_event(run_id, "warn",
                  "⚠ 통과 아이템이 0건 — 이후 노드는 건너뜁니다. 폐기 로그의 탈락 사유를 확인하세요.")
    return passed, failed


def step_tts(run_id, run_dir, passed, options):
    """④ TTS 음성 + ⑤ 자막·SRT (자막 타이밍이 오디오에 동기 → 항상 같이 재생성)."""
    do_tts = bool(options.get("tts", True))
    voice = options.get("voice") or "ko-KR-SunHiNeural"
    rate = options.get("rate") or "+0%"

    node_event(run_id, "tts", "running")
    tts_files = []
    for it in passed:
        item_dir = run_dir / f"item_{it['_item']}"
        item_dir.mkdir(exist_ok=True)
        if do_tts:
            r = {"path": None, "success": False, "error": ""}
            it["tts_engine"] = None
            if is_voicebox_available():
                r = generate_voicebox_tts(it["script"], item_dir)
                if r["success"]:
                    it["tts_engine"] = f"Voicebox ({r.get('profile') or '기본 프로필'})"
                else:
                    log_event(run_id, "warn", f"  ↳ item[{it['_item']}] Voicebox 실패, Edge TTS 폴백: {r['error']}")
            else:
                log_event(run_id, "warn",
                          f"  ↳ item[{it['_item']}] Voicebox 미실행(127.0.0.1:17493) — Edge TTS 폴백")
            if not r["success"]:
                r = generate_edge_tts(it["script"], item_dir, voice=voice, rate=rate)
                if r["success"]:
                    it["tts_engine"] = f"Edge TTS ({voice})"
            if r["success"]:
                mp3 = Path(r["path"])
                it["audio_path"] = str(mp3)
                it["audio_sec"] = get_audio_duration_seconds(mp3)
                tts_files.append(file_ref(run_dir.name, mp3))
                log_event(run_id, "info",
                          f"  ↳ item[{it['_item']}] {mp3.name} 생성 ({(it['audio_sec'] or 0):.1f}s · {it['tts_engine']})")
            else:
                it["audio_path"] = None
                it["tts_error"] = r["error"]
                log_event(run_id, "warn", f"  ↳ item[{it['_item']}] TTS 실패: {r['error']} — 자막 타이밍은 추정치 사용")
        else:
            it["audio_path"] = None
            log_event(run_id, "info", f"  ↳ item[{it['_item']}] TTS 건너뜀 (옵션 꺼짐)")
    used_engines = sorted({it.get("tts_engine") for it in passed if it.get("tts_engine")})
    tts_status = "skipped"
    if passed and do_tts:
        tts_status = "success" if tts_files else "error"
    if tts_status == "error":
        fail_reasons = sorted({it.get("tts_error") for it in passed if it.get("tts_error")})
        tts_note = "TTS 전부 실패: " + ("; ".join(fail_reasons) if fail_reasons else "원인 미상")
    else:
        tts_note = (" · ".join(used_engines) if used_engines
                    else "Voicebox 우선 → Edge TTS 폴백 (둘 다 미사용)")
    node_event(run_id, "tts", tts_status,
               items=[{"json": {"product_name": it.get("product_name"),
                                "engine": it.get("tts_engine"),
                                "audio_sec": it.get("audio_sec")},
                       "binary": ({"audio": {"mimeType": "audio/mpeg",
                                             "fileName": Path(it["audio_path"]).name}}
                                  if it.get("audio_path") else None)} for it in passed],
               files=tts_files,
               note=tts_note)
    log_event(run_id, "ok" if passed else "warn",
              f"{'✓' if passed else '⏸'} [TTS 음성 생성] {len(passed)} items")

    # ⑤ 자막·SRT·CapCut
    node_event(run_id, "subtitle", "running")
    sub_files = []
    for it in passed:
        item_dir = run_dir / f"item_{it['_item']}"
        lines = it.get("tts_lines") or format_for_typecast(it["script"])[0]
        it["tts_lines"] = lines
        cap = save_capcut_subtitles(lines, item_dir)
        srt = save_srt(lines, item_dir, audio_path=it.get("audio_path"))
        it["keywords"] = cap["keywords"]
        sub_files += [file_ref(run_dir.name, Path(cap["capcut_subtitles"])), file_ref(run_dir.name, srt)]
        log_event(run_id, "info", f"  ↳ item[{it['_item']}] SRT {len(lines)}줄 · 키워드 {', '.join(cap['keywords'][:4])}")
    node_event(run_id, "subtitle", "success" if passed else "skipped",
               items=[{"json": {"product_name": it.get("product_name"), "lines": len(it["tts_lines"]),
                                "keywords": it["keywords"][:6]}} for it in passed],
               files=sub_files, note="CapCut 자막 + 타이밍 동기 SRT")
    log_event(run_id, "ok" if passed else "warn",
              f"{'✓' if passed else '⏸'} [자막·SRT 생성] {len(passed)} items")


def step_uptext(run_id, run_dir, passed, options):
    """⑥ 업로드 문구·해시태그."""
    node_event(run_id, "uptext", "running")
    up_files = []
    for it in passed:
        item_dir = run_dir / f"item_{it['_item']}"
        item_dir.mkdir(exist_ok=True)
        text = generate_upload_text(it)
        p = item_dir / "upload_text.txt"
        p.write_text(text, encoding="utf-8")
        it["upload_text"] = text
        up_files.append(file_ref(run_dir.name, p))
    time.sleep(0.2)
    node_event(run_id, "uptext", "success" if passed else "skipped",
               items=[{"json": {"product_name": it.get("product_name"),
                                "upload_text_preview": it["upload_text"][:120] + "…"}} for it in passed],
               files=up_files, note="제목 후보 + 설명 + 해시태그")
    log_event(run_id, "ok" if passed else "warn",
              f"{'✓' if passed else '⏸'} [업로드 문구] {len(passed)} items")


def step_higgsfield(run_id, run_dir, passed, options):
    """⑥-b Higgsfield 영상 클립 (옵션 · 실비 소모)."""
    do_higgs = bool(options.get("higgsfield", False))
    image_id = (options.get("image_id") or "").strip()
    # image_id는 파일명만 허용 (경로 탈출 방지)
    upload_img = (UPLOADS_DIR / Path(image_id).name) if image_id else None
    if not do_higgs:
        node_event(run_id, "higgsfield", "skipped", note="옵션 꺼짐")
    elif not (upload_img and upload_img.is_file()):
        node_event(run_id, "higgsfield", "skipped", note="업로드 이미지 없음 (image_id 미지정/파일 없음)")
        log_event(run_id, "warn", "⏸ [Higgsfield] 건너뜀 — 제품 이미지를 먼저 업로드하세요")
    elif not is_higgsfield_available():
        node_event(run_id, "higgsfield", "skipped", note="HIGGSFIELD_API_KEY 미설정")
        log_event(run_id, "warn", "⏸ [Higgsfield] 건너뜀 — HIGGSFIELD_API_KEY 미설정")
    elif not passed:
        node_event(run_id, "higgsfield", "skipped", note="통과 아이템 없음 (품질 체크 false)")
    else:
        node_event(run_id, "higgsfield", "running")
        hf_files = []
        log_event(run_id, "warn",
                  f"⚠ [Higgsfield] 실제 API 호출 — 클립 1개당 약 9크레딧 소모 (예상 {len(passed) * 9}크레딧)")
        for it in passed:
            item_dir = run_dir / f"item_{it['_item']}"
            item_dir.mkdir(exist_ok=True)
            hook = (it.get("tts_lines") or [""])[0]
            prompt = (f"Cinematic vertical product video of {it.get('product_name', 'the product')}. "
                      f"{hook} Slow camera push-in, soft studio lighting, shallow depth of field.")
            # 이미지는 반드시 Path 객체로 — 문자열 전달 시 확장자 유실 버그가 있었다.
            r = generate_higgsfield_video(Path(upload_img), prompt, item_dir)
            if r.get("success") and r.get("path"):
                clip = Path(r["path"])
                it["higgsfield_path"] = str(clip)
                hf_files.append(file_ref(run_dir.name, clip))
                log_event(run_id, "info", f"  ↳ item[{it['_item']}] {clip.name} 생성")
            else:
                log_event(run_id, "warn", f"  ↳ item[{it['_item']}] Higgsfield 실패: {r.get('error')}")
        node_event(run_id, "higgsfield", "success" if hf_files else "error",
                   items=[{"json": {"product_name": it.get("product_name"),
                                    "clip": Path(it["higgsfield_path"]).name},
                           "binary": {"video": {"mimeType": "video/mp4",
                                                "fileName": "higgsfield_clip.mp4"}}}
                          for it in passed if it.get("higgsfield_path")],
                   files=hf_files,
                   note=(f"image-to-video 클립 {len(hf_files)}건" if hf_files
                         else "모든 아이템 생성 실패 — 로그 확인 (failed/nsfw는 크레딧 자동 환불)"))
        log_event(run_id, "ok" if hf_files else "err",
                  f"{'✓' if hf_files else '✕'} [Higgsfield 클립] {len(hf_files)}/{len(passed)} 성공")


def step_render(run_id, run_dir, passed, options):
    """⑦ 초안 렌더링 (옵션)."""
    do_render = bool(options.get("render", False))
    if do_render and passed:
        node_event(run_id, "render", "running")
        ren_files = []
        from modules.video_renderer import render_draft_video
        for it in passed:
            item_dir = run_dir / f"item_{it['_item']}"
            item_dir.mkdir(exist_ok=True)
            out = item_dir / "draft.mp4"
            log_event(run_id, "info", f"  ↳ item[{it['_item']}] moviepy 렌더링 중… (수십 초 소요)")
            r = render_draft_video(it["tts_lines"], out, audio_path=it.get("audio_path"),
                                   product_name=it.get("product_name", ""), root_dir=ROOT)
            if r.get("success"):
                it["video_path"] = str(out)
                ren_files.append(file_ref(run_dir.name, out))
                log_event(run_id, "info", f"  ↳ item[{it['_item']}] draft.mp4 완료")
            else:
                log_event(run_id, "warn", f"  ↳ item[{it['_item']}] 렌더링 실패: {r.get('error')}")
        node_event(run_id, "render", "success" if ren_files else "error",
                   items=[{"json": {"product_name": it.get("product_name"), "resolution": "1080x1920"},
                           "binary": {"video": {"mimeType": "video/mp4", "fileName": "draft.mp4"}}}
                          for it in passed if it.get("video_path")],
                   files=ren_files,
                   note="9:16 초안 mp4 (moviepy)" if ren_files else "모든 아이템 렌더링 실패 — 로그 확인")
        if ren_files:
            log_event(run_id, "ok", f"✓ [초안 렌더링] {len(ren_files)}/{len(passed)} 성공")
        else:
            log_event(run_id, "err", f"✕ [초안 렌더링] 0/{len(passed)} 성공 — moviepy 오류 로그를 확인하세요")
    elif do_render:
        node_event(run_id, "render", "skipped", note="통과 아이템 없음 (품질 체크 false)")
        log_event(run_id, "warn", "⏸ [초안 렌더링] 건너뜀 — 통과 아이템 없음")
    else:
        node_event(run_id, "render", "skipped", note="옵션 꺼짐 — CapCut 수동 편집 플로우")
        log_event(run_id, "warn", "⏸ [초안 렌더링] 건너뜀 (렌더링 옵션 꺼짐)")


STEP_FUNCS = {"script": step_script, "tts": step_tts, "higgsfield": step_higgsfield,
              "render": step_render, "uptext": step_uptext}


def run_pipeline(run_id: str, products: list[dict], options: dict) -> None:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    engine = resolve_engine(options)
    do_tts = bool(options.get("tts", True))
    do_render = bool(options.get("render", False))
    do_higgs = bool(options.get("higgsfield", False))

    try:
        # ── ① 트리거: 폼/웹훅 입력 수신 ─────────────────────────
        node_event(run_id, "trigger", "running")
        items = [dict(p) for p in products]
        for i, it in enumerate(items):
            it["_item"] = i
        time.sleep(0.3)
        node_event(run_id, "trigger", "success",
                   items=[{"json": p} for p in items],
                   note=f"제품 {len(items)}건 수신 (Webhook 트리거에 해당)")
        log_event(run_id, "ok", f"✓ [입력 수신] {len(items)} items — 아이템 1개 = 영상 1편")

        passed, failed = step_script(run_id, run_dir, items, options)
        save_state(run_dir, items, options)

        # ── true 브랜치 (위쪽 우선 — n8n v1.0+ 실행 순서) ─────────
        for fn in (step_tts, step_uptext, step_higgsfield, step_render):
            fn(run_id, run_dir, passed, options)
            save_state(run_dir, items, options)

        # ⑧⑨ 업로드 (시뮬레이션 — API 미연동, 병렬 브랜치)
        for node, platform in (("yt", "YouTube Shorts"), ("tiktok", "TikTok")):
            if not passed:
                node_event(run_id, node, "skipped", note="통과 아이템 없음")
                continue
            node_event(run_id, node, "running")
            time.sleep(0.5)
            node_event(run_id, node, "simulated",
                       items=[{"json": {"product_name": it.get("product_name"), "platform": platform,
                                        "status": "ready_to_upload",
                                        "note": "업로드 API 미연동 — 산출물 수동 업로드"}} for it in passed],
                       note="시뮬레이션 (계정 API 연동 시 실제 업로드)")
            log_event(run_id, "warn", f"◌ [{platform} 업로드] 시뮬레이션 — 산출물 준비 완료 상태로 표기")

        # ⑩ Merge + ⑪ 결과 요약
        node_event(run_id, "merge", "running"); time.sleep(0.3)
        node_event(run_id, "merge", "success" if passed else "skipped",
                   items=[{"json": {"product_name": it.get("product_name"), "platform": p}}
                          for p in ("YouTube Shorts", "TikTok") for it in passed],
                   note=f"Append 병합: {len(passed)}+{len(passed)} items")

        # false 브랜치: 폐기 로그
        node_event(run_id, "discard", "running"); time.sleep(0.2)
        if failed:
            dis = run_dir / "discarded.json"
            dis.write_text(json.dumps([{"product_name": it.get("product_name"), "reason": it["quality"]}
                                       for it in failed], ensure_ascii=False, indent=2), encoding="utf-8")
            node_event(run_id, "discard", "success",
                       items=[{"json": {"product_name": it.get("product_name"), "reason": it["quality"],
                                        "action": "재생성 대기열"}} for it in failed],
                       files=[file_ref(run_dir.name, dis)], note="품질 미달 기록")
            log_event(run_id, "warn", f"✓ [폐기 로그] {len(failed)}건 기록 → discarded.json")
        else:
            node_event(run_id, "discard", "skipped", note="탈락 아이템 없음")

        node_event(run_id, "notify", "running")
        summary = {
            "run_id": run_id, "finished": datetime.now().isoformat(timespec="seconds"),
            "elapsed_sec": round(time.time() - t0, 1),
            "input": len(items), "passed": len(passed), "failed": len(failed),
            "engine": engine, "tts": do_tts, "render": do_render, "higgsfield": do_higgs,
            "output_dir": str(run_dir),
        }
        (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        save_state(run_dir, items, options)
        node_event(run_id, "notify", "success",
                   items=[{"json": summary}], files=[file_ref(run_dir.name, run_dir / "summary.json")],
                   note="Execute Once — 요약 1건")
        log_event(run_id, "ok",
                  f"━━ 실행 완료 ━━ {summary['elapsed_sec']}s · 통과 {len(passed)} / 탈락 {len(failed)} · 산출물: outputs/pipeline_runs/{run_id}/")
        emit(run_id, {"type": "done", "ok": True, "summary": summary})

    except Exception as exc:
        tb = traceback.format_exc(limit=3)
        log_event(run_id, "err", f"✕ 파이프라인 오류: {exc}")
        log_event(run_id, "err", f"   {tb.splitlines()[-1]}")
        log_event(run_id, "warn", "⚡ Error Trigger 발동 → 오류 워크플로우: 실패 정보 기록")
        emit(run_id, {"type": "done", "ok": False, "error": str(exc)})
    finally:
        with RUNS_LOCK:
            RUNS[run_id]["done"] = True


def run_single_step(run_id: str, base_run_id: str, step: str, options: dict) -> None:
    """단계 개별 재실행 — base run_dir의 state.json을 기반으로 해당 번들만 다시 돌린다.
    산출물은 같은 run_dir에 덮어쓴다."""
    run_dir = RUNS_DIR / base_run_id
    t0 = time.time()
    try:
        state = load_state(run_dir)
        items = [dict(it) for it in state["items"]]
        # 산출물 URL은 base run_dir 기준(step 함수가 run_dir.name 사용), 이벤트는 새 run_id 채널로.
        if step == "script":
            step_script(run_id, run_dir, items, options)
        else:
            passed = [it for it in items if quality_check(it)[0]]
            STEP_FUNCS[step](run_id, run_dir, passed, options)
        save_state(run_dir, items, options)
        summary = {"run_id": base_run_id, "step": step,
                   "finished": datetime.now().isoformat(timespec="seconds"),
                   "elapsed_sec": round(time.time() - t0, 1),
                   "output_dir": str(run_dir)}
        log_event(run_id, "ok", f"━━ [{step}] 단계 재실행 완료 ━━ {summary['elapsed_sec']}s")
        emit(run_id, {"type": "done", "ok": True, "summary": summary})
    except Exception as exc:
        tb = traceback.format_exc(limit=3)
        log_event(run_id, "err", f"✕ [{step}] 단계 재실행 오류: {exc}")
        log_event(run_id, "err", f"   {tb.splitlines()[-1]}")
        emit(run_id, {"type": "done", "ok": False, "error": str(exc)})
    finally:
        with RUNS_LOCK:
            RUNS[run_id]["done"] = True


# ─────────────────────────── HTTP 서버 ───────────────────────────
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # 조용한 콘솔
        pass

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _serve_file(self, target: Path, ctype: str):
        """/files/ 전용 전송: Range 지원 + 캐시 허용 (산출물은 불변). _send는 no-store를 박아넣으므로 우회."""
        total = target.stat().st_size
        range_header = self.headers.get("Range")
        start, end = 0, total - 1
        status = 200
        if range_header:
            m = re.match(r"bytes=(\d*)-(\d*)", range_header)
            if not m or (not m.group(1) and not m.group(2)):
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{total}")
                self.end_headers()
                return
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else total - 1
            else:  # suffix range: bytes=-N
                suffix = int(m.group(2))
                start = max(total - suffix, 0)
                end = total - 1
            if start > end or start >= total:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{total}")
                self.end_headers()
                return
            end = min(end, total - 1)
            status = 206

        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "private, max-age=3600")
        self.send_header("Content-Disposition", f'inline; filename="{target.name}"')
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
        self.end_headers()
        with open(target, "rb") as f:
            f.seek(start)
            remaining = length
            chunk = 1024 * 1024
            while remaining > 0:
                data = f.read(min(chunk, remaining))
                if not data:
                    break
                self.wfile.write(data)
                remaining -= len(data)

    # ── 인증 (APP_PASSWORD) ──
    def _auth_token(self) -> str:
        return hashlib.sha256(APP_PASSWORD.encode("utf-8")).hexdigest()

    def _authed(self) -> bool:
        if not APP_PASSWORD:
            return True
        c = SimpleCookie(self.headers.get("Cookie", ""))
        got = c["auth"].value if "auth" in c else ""
        return hmac.compare_digest(got, self._auth_token())

    def _deny(self, path: str) -> None:
        if path.startswith("/api/") or path.startswith("/files/"):
            self._json(401, {"error": "로그인이 필요합니다."})
        else:
            self._send(302, b"", "text/plain", {"Location": "/login"})

    def _login_page(self, error: str = "") -> None:
        html = LOGIN_HTML.replace("{error}", f'<p class="err">{error}</p>' if error else "")
        self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")

    # ── GET ──
    def do_GET(self):
        path = unquote(urlparse(self.path).path)

        if path == "/login":
            self._login_page()
            return
        if not self._authed():
            self._deny(path)
            return

        if path in ("/", "/index.html"):
            if UI_FILE.exists():
                self._send(200, UI_FILE.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, "pipeline_ui.html not found".encode(), "text/plain")
            return

        if path == "/image":
            if IMAGE_UI_FILE.exists():
                self._send(200, IMAGE_UI_FILE.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, "image_ui.html not found".encode(), "text/plain")
            return

        if path == "/api/health":
            self._json(200, {"ok": True, "llm_available": llm_available(),
                             "gpt_available": gpt_available(),
                             "higgsfield_available": is_higgsfield_available(),
                             "openai_image_available": is_openai_image_available(),
                             "voicebox_available": is_voicebox_available(),
                             "local": hasattr(os, "startfile"),
                             "server": "shorts-pipeline", "port": PORT})
            return

        if path.startswith("/api/events/"):
            run_id = path.rsplit("/", 1)[-1]
            with RUNS_LOCK:
                run = RUNS.get(run_id)
            if not run:
                self._json(404, {"error": "unknown run_id"})
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            sent = 0
            last_write = time.time()
            try:
                while True:
                    with RUNS_LOCK:
                        history = list(run["history"])
                        done = run["done"]
                    while sent < len(history):
                        ev = history[sent]; sent += 1
                        payload = f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                        self.wfile.write(payload.encode("utf-8"))
                        self.wfile.flush()
                        last_write = time.time()
                        if ev.get("type") == "done":
                            return
                    if done and sent >= len(history):
                        return
                    if time.time() - last_write > 15:   # 프록시(nginx) 유휴 끊김 방지
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                        last_write = time.time()
                    time.sleep(0.15)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return

        if path.startswith("/files/"):
            rel = path[len("/files/"):]
            target = (RUNS_DIR / rel).resolve()
            if not str(target).startswith(str(RUNS_DIR.resolve())) or not target.is_file():
                self._json(404, {"error": "file not found"})
                return
            ctype = {"mp3": "audio/mpeg", "wav": "audio/wav", "mp4": "video/mp4", "srt": "text/plain; charset=utf-8",
                     "txt": "text/plain; charset=utf-8", "json": "application/json; charset=utf-8",
                     "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp",
                     }.get(target.suffix.lstrip("."), "application/octet-stream")
            self._serve_file(target, ctype)
            return

        self._json(404, {"error": "not found"})

    # ── POST ──
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/login":
            length = int(self.headers.get("Content-Length", "0"))
            form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
            pw = (form.get("password") or [""])[0]
            if APP_PASSWORD and hmac.compare_digest(pw, APP_PASSWORD):
                secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
                cookie = f"auth={self._auth_token()}; Path=/; Max-Age=2592000; HttpOnly; SameSite=Lax{secure}"
                self._send(302, b"", "text/plain", {"Location": "/", "Set-Cookie": cookie})
            else:
                self._login_page("비밀번호가 틀렸어요")
            return
        if not self._authed():
            self._deny(path)
            return

        if path == "/api/upload-image":
            try:
                params = parse_qs(parsed.query)
                name = unquote((params.get("name") or [""])[0])
                # 경로 탈출 방지: 파일명만 취하고 확장자를 화이트리스트로 검사
                ext = Path(name).suffix.lower()
                if ext not in UPLOAD_EXTS:
                    self._json(400, {"error": f"허용되지 않는 확장자: {ext or '(없음)'} — png/jpg/jpeg/webp만 가능"})
                    return
                length = int(self.headers.get("Content-Length", "0"))
                data = self.rfile.read(length) if length else b""
                if not data:
                    self._json(400, {"error": "이미지 본문이 비어 있습니다."})
                    return
                UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
                image_id = uuid.uuid4().hex[:8] + ext
                (UPLOADS_DIR / image_id).write_bytes(data)
                self._json(200, {"image_id": image_id})
            except Exception as exc:
                self._json(500, {"error": str(exc)})
            return

        if path == "/api/image":
            # 사진/그림 생성 (Higgsfield Soul, 실비 소모). 생성물은 _uploads에 저장해
            # 그대로 쇼츠 파이프라인의 제품 이미지(image_id)로 쓸 수 있게 한다.
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length) or b"{}")
                prompt = (body.get("prompt") or "").strip()
                if not prompt:
                    self._json(400, {"error": "프롬프트를 입력하세요."})
                    return
                # 엔진 선택: gpt(OpenAI Images) · higgsfield. 둘 다 고르면 나란히 돌려 결과를 합친다.
                engines = [e for e in (body.get("engines") or ["higgsfield"]) if e in ("gpt", "higgsfield")]
                if not engines:
                    self._json(400, {"error": "엔진을 하나 이상 고르세요 (gpt · higgsfield)."})
                    return
                missing = [name for name, ok in
                           (("gpt", is_openai_image_available()), ("higgsfield", is_higgsfield_available()))
                           if name in engines and not ok]
                if missing:
                    key = "OPENAI_API_KEY" if missing[0] == "gpt" else "HIGGSFIELD_API_KEY"
                    self._json(400, {"error": f"{key} 미설정 — .env에 키를 넣고 서버를 다시 켜세요."})
                    return
                UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
                # 첨부 이미지: /api/upload-image로 먼저 올린 image_id 목록 (경로 탈출 방지: 파일명만)
                refs = []
                for img in (body.get("image_ids") or [])[:8]:
                    f = UPLOADS_DIR / Path(str(img)).name
                    if f.suffix.lower() in UPLOAD_EXTS and f.is_file():
                        refs.append(f)
                aspect = body.get("aspect_ratio") or "9:16"
                count = body.get("num_images") or 1
                results: dict[str, dict] = {}

                def run(engine: str) -> None:
                    fn = generate_openai_image if engine == "gpt" else generate_higgsfield_image
                    prefix = f"gen_{engine}_" + uuid.uuid4().hex[:8] + "_"
                    try:
                        results[engine] = fn(prompt, UPLOADS_DIR, aspect_ratio=aspect,
                                             num_images=count, file_prefix=prefix,
                                             reference_images=refs)
                    except Exception as exc:
                        results[engine] = {"paths": [], "success": False, "error": str(exc)}

                threads = [threading.Thread(target=run, args=(e,), daemon=True) for e in engines]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                images, errors = [], []
                for engine in engines:
                    r = results.get(engine) or {}
                    if r.get("success"):
                        images.extend({"image_id": p.name, "url": f"/files/_uploads/{p.name}",
                                       "engine": engine} for p in r["paths"])
                    else:
                        errors.append(f"{'GPT' if engine == 'gpt' else 'Higgsfield'}: "
                                      f"{r.get('error') or '생성 실패'}")
                if not images:
                    self._json(502, {"error": "\n".join(errors) or "생성 실패"})
                    return
                # 일부만 성공하면 성공분은 돌려주고 실패 사유도 함께 알린다.
                self._json(200, {"images": images, "error": "\n".join(errors)})
            except Exception as exc:
                self._json(500, {"error": str(exc)})
            return

        if path == "/api/open-folder":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length) or b"{}")
                run_id = body.get("run_id") or ""
                # 경로 탈출 방지: run_id는 파일명만 취함 (upload-image와 동일 수준)
                target = (RUNS_DIR / Path(run_id).name).resolve()
                if not str(target).startswith(str(RUNS_DIR.resolve())) or not target.is_dir():
                    self._json(404, {"error": "run 폴더 없음"})
                    return
                os.startfile(target)
                self._json(200, {"ok": True})
            except Exception as exc:
                self._json(500, {"error": str(exc)})
            return

        if path == "/api/run-step":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length) or b"{}")
                step = (body.get("step") or "").strip()
                if step not in STEP_FUNCS:
                    self._json(400, {"error": f"알 수 없는 step: {step}"})
                    return
                # 경로 탈출 방지: base_run_id는 파일명만 취함 (upload-image와 동일 수준)
                base_run_id = Path(body.get("base_run_id") or "").name
                run_dir = (RUNS_DIR / base_run_id).resolve() if base_run_id else None
                if (not run_dir or not str(run_dir).startswith(str(RUNS_DIR.resolve()))
                        or not run_dir.is_dir()):
                    self._json(404, {"error": "이전 실행 폴더를 찾을 수 없습니다."})
                    return
                state = load_state(run_dir)
                if not state:
                    self._json(404, {"error": "이전 실행 상태(state.json)가 없습니다. 전체 실행을 먼저 하세요."})
                    return
                items = state.get("items") or []
                if step != "script" and not any(it.get("script") for it in items):
                    self._json(400, {"error": "이전 실행에 대본이 없습니다. 전체 실행 또는 ② 대본 단계를 먼저 실행하세요."})
                    return
                options = dict(state.get("options") or {})
                options.update(body.get("options") or {})
                if step == "higgsfield":
                    img = (options.get("image_id") or "").strip()
                    if not (img and (UPLOADS_DIR / Path(img).name).is_file()):
                        self._json(400, {"error": "제품 이미지가 없습니다. 이미지를 먼저 업로드하세요."})
                        return
                run_id = base_run_id + "_s" + uuid.uuid4().hex[:4]
                with RUNS_LOCK:
                    RUNS[run_id] = {"q": queue.Queue(), "history": [], "done": False}
                threading.Thread(target=run_single_step,
                                 args=(run_id, base_run_id, step, options), daemon=True).start()
                self._json(200, {"run_id": run_id, "base_run_id": base_run_id, "step": step})
            except Exception as exc:
                self._json(500, {"error": str(exc)})
            return

        if path != "/api/run":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            products = body.get("products") or []
            options = body.get("options") or {}
            if not products:
                self._json(400, {"error": "products가 비어 있습니다."})
                return
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
            with RUNS_LOCK:
                RUNS[run_id] = {"q": queue.Queue(), "history": [], "done": False}
            threading.Thread(target=run_pipeline, args=(run_id, products, options), daemon=True).start()
            self._json(200, {"run_id": run_id})
        except Exception as exc:
            self._json(500, {"error": str(exc)})


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("─" * 52)
    print("  🎬 Shorts 파이프라인 서버 시작")
    print(f"  브라우저에서 열기 →  http://localhost:{PORT}")
    print(f"  이미지 생성(사진/그림) →  http://localhost:{PORT}/image")
    print(f"  바인딩: {HOST}:{PORT} · 비밀번호 잠금: {'켜짐' if APP_PASSWORD else '꺼짐 (APP_PASSWORD 미설정)'}")
    print(f"  대본 엔진: GPT {'O' if gpt_available() else 'X'} · Claude {'O' if llm_available() else 'X'}"
          f" (둘 다 미설정 시 템플릿)")
    print(f"  이미지 엔진: GPT {'O' if is_openai_image_available() else 'X'}"
          f" · Higgsfield {'O' if is_higgsfield_available() else 'X'}")
    print(f"  산출물 폴더: {RUNS_DIR}")
    print("  종료: Ctrl+C")
    print("─" * 52)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버 종료")


if __name__ == "__main__":
    main()
