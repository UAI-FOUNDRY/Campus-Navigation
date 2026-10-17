"""Security headers, request limits, rate limiting, ETag/304 and gzip (app/web.py)."""
import gzip
import json
from pathlib import Path

from app import config, create_app

REAL_PATH = Path(__file__).resolve().parents[2] / "data" / "build" / "campus.merged.json"


def client():
    return create_app(REAL_PATH).test_client()


def test_security_headers_on_every_answer():
    for path in ("/api/health", "/api/rooms?q=lib", "/api/nope"):
        h = client().get(path).headers
        assert h["X-Content-Type-Options"] == "nosniff" and h["X-Frame-Options"] == "DENY"
        assert "default-src 'none'" in h["Content-Security-Policy"] and h["Referrer-Policy"] == "no-referrer"


def test_route_has_etag_and_answers_304():
    c = client()
    r = c.get("/api/route?from=gate_main&to=library")
    tag = r.headers["ETag"]
    assert r.status_code == 200 and "max-age" in r.headers["Cache-Control"]
    assert c.get("/api/route?from=gate_main&to=library", headers={"If-None-Match": tag}).status_code == 304
    assert c.get("/api/route?from=gate_main&to=mess", headers={"If-None-Match": tag}).status_code == 200


def test_gzip_when_asked():
    c = client()
    r = c.get("/api/graph", headers={"Accept-Encoding": "gzip, br"})
    assert r.headers["Content-Encoding"] == "gzip" and "Accept-Encoding" in r.headers["Vary"]
    body = json.loads(gzip.decompress(r.data))
    assert body["version"] and body["nodes"]
    plain = c.get("/api/graph")
    assert "Content-Encoding" not in plain.headers and len(plain.data) > len(r.data) * 3


def test_public_graph_hides_mapping_data():
    g = client().get("/api/graph").json
    indoor = [n for n in g["nodes"] if n["space"] == "indoor"]
    assert indoor and all("pos" not in n and "verify" not in n and "note" not in n and "plan" not in n for n in indoor)
    assert all("via" not in e and "source" not in e and "corridor" not in e for e in g["edges"])
    assert all("note" not in r for r in g["rooms"])


def test_limits_on_input():
    c = client()
    assert c.get("/api/rooms?q=" + "a" * 500).status_code == 400
    big = {"start": "gate_main", "destinations": ["x" * 100] * 400}
    assert c.post("/api/estimates", json=big).status_code == 413
    assert c.delete("/api/route?from=gate_main&to=library").status_code == 405


def test_rate_limit_answers_429(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMITS_ON", True)
    monkeypatch.setattr(config, "REPORTS_PATH", tmp_path / "reports.jsonl")
    c = client()
    codes = [c.post("/api/report", json={"reason": "test"}).status_code for _ in range(6)]
    assert 429 in codes
    r = c.post("/api/report", json={"reason": "test"})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1


def test_report_inbox_has_a_size_cap(tmp_path, monkeypatch):
    inbox = tmp_path / "reports.jsonl"
    inbox.write_text("x" * 50)
    monkeypatch.setattr(config, "REPORTS_PATH", inbox)
    monkeypatch.setattr(config, "REPORTS_MAX_BYTES", 10)
    assert client().post("/api/report", json={"reason": "full?"}).status_code == 503
