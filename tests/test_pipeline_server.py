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
