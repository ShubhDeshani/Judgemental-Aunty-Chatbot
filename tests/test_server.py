"""
Tests for server.py - no real LLM calls. The AuntyBot is replaced with a fake.
Covers: /health, / serves HTML, normal chat, empty/oversized message (400),
per-visitor daily limit (429), per-minute limit (429), site-wide limit (429),
two visitors keep separate used-fact sets, session_id length cap,
no message text in logs.
"""

import pytest
from fastapi.testclient import TestClient

import server


class FakeBot:
    """Stand-in for AuntyBot: records messages and simulates fact consumption."""
    def __init__(self, debug=False):
        self.used_ids = set()
        self.last_message = None

    def reply(self, message):
        self.last_message = message
        # simulate find_fact injecting + marking one fact as used
        self.used_ids.add("fact_shubh_1")
        return f"Fake aunty: {message}"


@pytest.fixture
def client(monkeypatch):
    """Fresh TestClient with a fake bot and reset in-memory counters."""
    server._visitor_state.clear()
    server._site_day = None
    server._site_count = 0
    server._bot = None
    server._bot_ready = False
    monkeypatch.setattr(server, "AuntyBot", FakeBot)
    # Per-minute limit stays at default (6) unless a test overrides it.
    with TestClient(server.app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "ready": True}


def test_index_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "Judgemental Padosi Aunty" in r.text


def test_normal_chat(client):
    r = client.post("/chat", json={"session_id": "visitor_a", "message": "how much did shubh score"})
    assert r.status_code == 200
    data = r.json()
    assert data["reply"]
    assert data["reply"] != "(Aunty is sleeping...)"
    assert not data["reply"].startswith("User Safety")
    assert data["remaining"] == server.PER_VISITOR_DAILY - 1


def test_empty_message_400(client):
    r = client.post("/chat", json={"session_id": "visitor_a", "message": ""})
    assert r.status_code == 400


def test_whitespace_message_400(client):
    r = client.post("/chat", json={"session_id": "visitor_a", "message": "   \n  "})
    assert r.status_code == 400


def test_too_long_message_400(client):
    long_msg = "x" * (server.MAX_MESSAGE_CHARS + 1)
    r = client.post("/chat", json={"session_id": "visitor_a", "message": long_msg})
    assert r.status_code == 400


def test_per_visitor_daily_limit_429(client, monkeypatch):
    monkeypatch.setattr(server, "PER_VISITOR_PER_MINUTE", 1000)
    for i in range(server.PER_VISITOR_DAILY):
        r = client.post("/chat", json={"session_id": "v_lim", "message": f"msg {i}"})
        assert r.status_code == 200, f"message {i} failed: {r.status_code} {r.text}"
    r = client.post("/chat", json={"session_id": "v_lim", "message": "one more"})
    assert r.status_code == 429
    data = r.json()
    assert data["reply"]


def test_per_minute_limit_429(client):
    for i in range(server.PER_VISITOR_PER_MINUTE):
        r = client.post("/chat", json={"session_id": "v_min", "message": f"rapid {i}"})
        assert r.status_code == 200, f"rapid {i}: {r.status_code} {r.text}"
    r = client.post("/chat", json={"session_id": "v_min", "message": "too fast"})
    assert r.status_code == 429


def test_site_wide_limit_429(client, monkeypatch):
    monkeypatch.setattr(server, "SITE_DAILY", 2)
    server._site_count = 0
    r1 = client.post("/chat", json={"session_id": "v_site_1", "message": "first"})
    assert r1.status_code == 200
    r2 = client.post("/chat", json={"session_id": "v_site_2", "message": "second"})
    assert r2.status_code == 200
    r3 = client.post("/chat", json={"session_id": "v_site_3", "message": "third"})
    assert r3.status_code == 429


def test_two_visitors_separate_used_fact_sets(client):
    client.post("/chat", json={"session_id": "visitor_a", "message": "tell me about shubh"})
    client.post("/chat", json={"session_id": "visitor_b", "message": "tell me about shubh"})
    keys = list(server._visitor_state.keys())
    assert len(keys) == 2
    set_a = server._visitor_state[keys[0]]["used_ids"]
    set_b = server._visitor_state[keys[1]]["used_ids"]
    assert set_a is not set_b


def test_session_id_length_cap(client):
    huge_id = "x" * 10000
    r = client.post("/chat", json={"session_id": huge_id, "message": "hi"})
    assert r.status_code == 200, f"huge session_id failed: {r.status_code} {r.text}"


def test_no_message_text_in_logs(client, caplog):
    secret_msg = "MY_UNIQUE_SECRET_MESSAGE_12345"
    with caplog.at_level("INFO"):
        client.post("/chat", json={"session_id": "v_log", "message": secret_msg})
    for rec in caplog.records:
        assert secret_msg not in rec.getMessage()
