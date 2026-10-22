"""Regression tests for the API hardening in api/security.py, api/main.py and
api/repository.py. These need no models, GPU or network."""

import io
import os
import zipfile

import pytest
from fastapi.testclient import TestClient

import api.main as main_mod
import api.repository as repo_mod
from api.main import app

KEY = "test-key-not-a-real-secret"


@pytest.fixture
def keyed(monkeypatch):
    monkeypatch.setenv("DOCRAG_API_KEY", KEY)
    return TestClient(app)


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    root = tmp_path / "data"
    (root / "papers").mkdir(parents=True)
    monkeypatch.setenv("DOCRAG_DATA_ROOTS", str(root))
    monkeypatch.setattr(repo_mod, "background_ingest_repository", lambda *a, **k: None)
    return root


PROTECTED = [
    ("get", "/repository/"),
    ("post", "/repository/"),
    ("get", "/repository/abc"),
    ("delete", "/repository/abc"),
    ("post", "/repository/abc/reindex"),
    ("post", "/query"),
    ("post", "/cache/clear"),
    ("get", "/indexing/status/abc"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_missing_key_is_rejected(keyed, method, path):
    r = getattr(keyed, method)(path, **({"json": {"name": "x", "question": "q"}} if method == "post" else {}))
    assert r.status_code == 401


@pytest.mark.parametrize("method,path", PROTECTED[:3])
def test_wrong_key_is_rejected(keyed, method, path):
    r = getattr(keyed, method)(path, headers={"X-API-Key": "wrong"}, **({"json": {"name": "x"}} if method == "post" else {}))
    assert r.status_code == 401


def test_correct_key_is_accepted(keyed):
    assert keyed.get("/repository/", headers={"X-API-Key": KEY}).status_code == 200


def test_remote_client_denied_when_no_key_configured(monkeypatch):
    monkeypatch.delenv("DOCRAG_API_KEY", raising=False)
    remote = TestClient(app, client=("203.0.113.9", 4444))
    assert remote.get("/repository/").status_code == 403
    assert remote.post("/cache/clear").status_code == 403


def test_loopback_allowed_when_no_key_configured(monkeypatch):
    monkeypatch.delenv("DOCRAG_API_KEY", raising=False)
    local = TestClient(app, client=("127.0.0.1", 4444))
    assert local.get("/repository/").status_code == 200


def test_health_hides_details_from_unauthenticated(keyed):
    body = keyed.get("/health").json()
    assert body == {"status": "ok", "system": "DocumentRAG"}


def test_source_path_outside_roots_is_forbidden(keyed, data_root, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    for evil in [str(outside), str(data_root / ".." / "outside"), "/etc", r"C:\Windows"]:
        r = keyed.post("/repository/", headers={"X-API-Key": KEY}, json={"name": "n", "source_path": evil})
        assert r.status_code in (400, 403), evil
        assert r.status_code != 200


def test_source_path_inside_root_is_accepted(keyed, data_root):
    r = keyed.post(
        "/repository/",
        headers={"X-API-Key": KEY},
        json={"name": "ok", "source_path": str(data_root / "papers")},
    )
    assert r.status_code == 200, r.text


def test_nonexistent_source_path_is_rejected(keyed, data_root):
    r = keyed.post(
        "/repository/",
        headers={"X-API-Key": KEY},
        json={"name": "n", "source_path": str(data_root / "nope")},
    )
    assert r.status_code == 400


def test_update_cannot_repoint_to_outside_path(keyed, data_root, tmp_path):
    h = {"X-API-Key": KEY}
    rid = keyed.post("/repository/", headers=h, json={"name": "n"}).json()["repo_id"]
    outside = tmp_path / "secret_dir"
    outside.mkdir()
    r = keyed.put(f"/repository/{rid}", headers=h, json={"source_path": str(outside)})
    assert r.status_code == 403


def test_symlink_escape_is_blocked(keyed, data_root, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = data_root / "papers" / "link"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted on this platform")
    r = keyed.post("/repository/", headers={"X-API-Key": KEY}, json={"name": "n", "source_path": str(link)})
    assert r.status_code == 403


def test_cors_rejects_unknown_origin(keyed):
    r = keyed.options(
        "/query",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in r.headers
    r = keyed.get("/health", headers={"Origin": "https://evil.example"})
    assert r.headers.get("access-control-allow-origin") != "*"
    assert "access-control-allow-origin" not in r.headers


def test_cors_allows_local_ui_without_credentials(keyed):
    r = keyed.get("/health", headers={"Origin": "http://localhost:8501"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:8501"
    assert "access-control-allow-credentials" not in r.headers


def test_query_errors_do_not_leak_internals(keyed, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("SECRET_INTERNAL /srv/app/config.py token=abc")

    monkeypatch.setattr(main_mod.orchestrator, "answer", boom)
    r = keyed.post("/query", headers={"X-API-Key": KEY}, json={"question": "hi"})
    assert r.status_code == 500
    assert "SECRET_INTERNAL" not in r.text and "/srv/app" not in r.text


def test_query_input_limits(keyed):
    h = {"X-API-Key": KEY}
    assert keyed.post("/query", headers=h, json={"question": "x" * 4001}).status_code == 422
    assert keyed.post("/query", headers=h, json={"question": "q", "request_id": "../../x"}).status_code == 422


def test_unknown_indexing_status_does_not_allocate_tracker(keyed):
    from storage.progress import ProgressRegistry

    r = keyed.get("/indexing/status/does-not-exist", headers={"X-API-Key": KEY})
    assert r.status_code == 404
    assert "does-not-exist" not in ProgressRegistry._progress


def test_zip_slip_is_blocked(tmp_path):
    from ingestion.worker import _safe_extractall

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil.txt", "x")
    buf.seek(0)
    dest = tmp_path / "out"
    dest.mkdir()
    with zipfile.ZipFile(buf) as zf, pytest.raises(ValueError):
        _safe_extractall(zf, str(dest))
    assert not (tmp_path / "evil.txt").exists()


def test_zip_normal_extracts(tmp_path):
    from ingestion.worker import _safe_extractall

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a/b.txt", "ok")
    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        _safe_extractall(zf, str(tmp_path / "out"))
    assert (tmp_path / "out" / "a" / "b.txt").read_text() == "ok"
