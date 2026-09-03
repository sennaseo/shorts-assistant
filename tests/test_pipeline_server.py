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
