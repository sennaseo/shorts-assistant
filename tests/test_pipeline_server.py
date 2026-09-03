import json
import os
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import pipeline_server as ps


@pytest.fixture
def server(tmp_path, monkeypatch):
    """임시 산출물 폴더를 보는 서버를 빈 포트에 띄우고 base_url을 돌려준다."""
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setattr(ps, "RUNS_DIR", runs)
    monkeypatch.setattr(ps, "UPLOADS_DIR", runs / "_uploads")
    monkeypatch.setattr(ps, "APP_PASSWORD", "")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ps.Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def post(url, data: bytes, headers=None):
    req = urllib.request.Request(url, data=data, method="POST", headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def test_health_has_local_flag(server):
    code, _, body = get(server + "/api/health")
    assert code == 200
    j = json.loads(body)
    assert j["ok"] is True
    assert j["local"] == hasattr(os, "startfile")


def test_host_env_default():
    assert ps.HOST == os.environ.get("PIPELINE_HOST", "127.0.0.1")


def test_no_password_means_open(server):
    code, _, _ = get(server + "/")
    assert code == 200


def test_password_gate_redirects_html_and_401_api(server, monkeypatch):
    monkeypatch.setattr(ps, "APP_PASSWORD", "secret1")
    # HTML은 /login 으로
    req = urllib.request.Request(server + "/")
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        r = opener.open(req, timeout=5)
        code, loc = r.status, r.headers.get("Location")
    except urllib.error.HTTPError as e:
        code, loc = e.code, e.headers.get("Location")
    assert code == 302 and loc == "/login"
    # API는 401 JSON
    code, _, body = get(server + "/api/health")
    assert code == 401 and json.loads(body)["error"]
    code, _, body = get(server + "/files/whatever/x.mp3")
    assert code == 401 and json.loads(body)["error"]
    # 로그인 페이지 자체는 열림
    code, _, body = get(server + "/login")
    assert code == 200 and b"password" in body


def test_login_sets_cookie_and_passes(server, monkeypatch):
    monkeypatch.setattr(ps, "APP_PASSWORD", "secret1")
    # 틀린 비번
    code, _, body = post(server + "/login", b"password=wrong",
                         {"Content-Type": "application/x-www-form-urlencoded"})
    assert code == 200 and "틀렸".encode("utf-8") in body
    # 맞는 비번 → 302 + Set-Cookie
    req = urllib.request.Request(server + "/login", data=b"password=secret1", method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        r = opener.open(req, timeout=5); code, hdrs = r.status, r.headers
    except urllib.error.HTTPError as e:
        code, hdrs = e.code, e.headers
    assert code == 302 and hdrs.get("Location") == "/"
    cookie = hdrs.get("Set-Cookie")
    assert cookie and cookie.startswith("auth=") and "HttpOnly" in cookie
    token = cookie.split(";")[0]
    code, _, _ = get(server + "/api/health", {"Cookie": token})
    assert code == 200


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def _make_run(runs_dir: Path, run_id: str, name: str):
    d = runs_dir / run_id
    (d / "item_0").mkdir(parents=True)
    (d / "summary.json").write_text(json.dumps({
        "run_id": run_id, "finished": "2026-09-03T10:00:00", "elapsed_sec": 3.2,
        "input": 1, "passed": 1, "failed": 0}), encoding="utf-8")
    (d / "state.json").write_text(json.dumps({"options": {"tts": True}, "items": [{
        "_item": 0, "product_name": name, "category": "생활", "features": "가벼움",
        "script": "한 줄\n두 줄", "script_source": "gpt", "tts_engine": "Edge TTS",
        "audio_sec": 4.5, "quality": "ok", "upload_text": "[유튜브 쇼츠 제목 후보]\n1. 제목\n\n[해시태그]\n#a #b"}]}),
        encoding="utf-8")
    (d / "item_0" / "voice.mp3").write_bytes(b"\x00" * 10)
    (d / "item_0" / "subtitles.srt").write_text("1\n", encoding="utf-8")
    (d / "item_0" / "upload_text.txt").write_text("x", encoding="utf-8")
    return d


def test_runs_list_newest_first_and_skips_uploads(server):
    runs = ps.RUNS_DIR
    _make_run(runs, "20260901_000000_aaaaaa", "구형")
    _make_run(runs, "20260903_000000_bbbbbb", "신형")
    (runs / "_uploads").mkdir()
    (runs / "20260902_broken").mkdir()   # summary.json 없음 → 제외
    code, _, body = get(server + "/api/runs")
    j = json.loads(body)
    assert code == 200
    assert [r["run_id"] for r in j["runs"]] == ["20260903_000000_bbbbbb", "20260901_000000_aaaaaa"]
    assert j["runs"][0]["product_name"] == "신형" and j["runs"][0]["passed"] == 1


def test_run_detail_files_and_kinds(server):
    _make_run(ps.RUNS_DIR, "20260903_000000_bbbbbb", "신형")
    code, _, body = get(server + "/api/runs/20260903_000000_bbbbbb")
    j = json.loads(body)
    assert code == 200 and j["run_id"] == "20260903_000000_bbbbbb"
    it = j["items"][0]
    assert it["product_name"] == "신형" and it["script"].startswith("한 줄")
    kinds = {f["name"]: f["kind"] for f in it["files"]}
    assert kinds == {"voice.mp3": "audio", "subtitles.srt": "subtitle", "upload_text.txt": "text"}
    assert all(f["url"].startswith("/files/20260903_000000_bbbbbb/item_0/") for f in it["files"])
    code, _, _ = get(server + "/api/runs/nope")
    assert code == 404
    code, _, _ = get(server + "/api/runs/..")
    assert code == 404


def test_zip_download(server):
    import io, zipfile
    _make_run(ps.RUNS_DIR, "20260903_000000_bbbbbb", "신형")
    code, hdrs, body = get(server + "/files/20260903_000000_bbbbbb.zip")
    assert code == 200 and hdrs["Content-Type"] == "application/zip"
    assert "attachment" in hdrs["Content-Disposition"]
    names = zipfile.ZipFile(io.BytesIO(body)).namelist()
    assert "item_0/voice.mp3" in names and "state.json" in names
    code, _, _ = get(server + "/files/nope.zip")
    assert code == 404
