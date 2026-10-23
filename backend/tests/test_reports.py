"""Report a problem -> a line in data/reports.jsonl and (with GITHUB_TOKEN) a GitHub issue."""
import io
import json
import urllib.error
from pathlib import Path

import pytest

from app import config, create_app
from app.api import report

REAL_PATH = Path(__file__).resolve().parents[2] / "data" / "build" / "campus.merged.json"


class FakeGitHub:
    def __init__(self, fail=None):
        self.requests = []
        self.fail = fail

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        if self.fail:
            raise self.fail
        return io.BytesIO(json.dumps({"html_url": "https://github.com/x/y/issues/1"}).encode())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REPORTS_PATH", tmp_path / "reports.jsonl")
    monkeypatch.setattr(report, "_dispatch", lambda job: job())      # run the GitHub call at once
    monkeypatch.setitem(report._day, "date", None)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    return create_app(REAL_PATH).test_client()


def post(c, **kw):
    body = {"start": "gate_main", "destination": "library", "reason": "The path was blocked"}
    body.update(kw)
    return c.post("/api/report", json=body)


def test_without_a_token_only_the_file(client, monkeypatch, tmp_path):
    gh = FakeGitHub()
    monkeypatch.setattr(report.urllib.request, "urlopen", gh)
    assert post(client).status_code == 201
    assert gh.requests == []
    assert "The path was blocked" in (tmp_path / "reports.jsonl").read_text()


def test_opens_a_readable_issue(client, monkeypatch):
    gh = FakeGitHub()
    monkeypatch.setattr(report.urllib.request, "urlopen", gh)
    monkeypatch.setenv("GITHUB_TOKEN", "t0k3n")
    r = post(client, step="Turn right at Lobby and walk 13 m", step_free=True,
             details="Gate 2 is shut after 6 pm @someone see #12 ~~~")
    assert r.status_code == 201
    (req,) = gh.requests
    assert req.full_url == f"https://api.github.com/repos/{config.REPORTS_REPO}/issues"
    assert req.get_header("Authorization") == "Bearer t0k3n"
    issue = json.loads(req.data)
    assert issue["labels"] == ["report"]
    assert issue["title"].startswith("Report: The path was blocked (Main Gate")
    assert "Library" in issue["title"]
    body = issue["body"]
    assert "At the step: Turn right at Lobby and walk 13 m" in body
    assert "Step-free route" in body
    assert "api/route?from=gate_main&to=library&accessible=1" in body
    # What people type is shown as text: no mentions, issue links, or a way out of the block.
    assert "~~~text\nGate 2 is shut after 6 pm @someone see #12 ~ ~ ~\n~~~" in body


def test_mentions_in_the_reason_are_quiet(client, monkeypatch):
    gh = FakeGitHub()
    monkeypatch.setattr(report.urllib.request, "urlopen", gh)
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    post(client, reason="ping @admin #3")
    issue = json.loads(gh.requests[0].data)
    assert "@admin" not in issue["title"] and "#3" not in issue["title"]


def test_github_failing_still_keeps_the_report(client, monkeypatch, tmp_path):
    gh = FakeGitHub(fail=urllib.error.URLError("down"))
    monkeypatch.setattr(report.urllib.request, "urlopen", gh)
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    assert post(client).status_code == 201
    assert len(gh.requests) == 1
    assert "The path was blocked" in (tmp_path / "reports.jsonl").read_text()


def test_daily_cap(client, monkeypatch):
    gh = FakeGitHub()
    monkeypatch.setattr(report.urllib.request, "urlopen", gh)
    monkeypatch.setattr(config, "REPORTS_ISSUES_PER_DAY", 2)
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    for _ in range(4):
        assert post(client).status_code == 201
    assert len(gh.requests) == 2
