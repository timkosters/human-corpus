"""Hosted-mode safety: the rate limit can't be dodged with a forged header, slow queries are cut off,
and bad arguments come back as readable errors."""
import json

import pytest

from humancorpus import index
from humancorpus.sources import Document

starlette = pytest.importorskip("starlette.testclient")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    con = index.connect(db)
    doc = Document("test", "1", "Rivers", "Someone", "https://x", "CC BY-SA 3.0", "2022-03-01",
                   ["The river flooded the valley every spring. Farmers welcomed the rich silt it left behind."])
    index._add_doc(con, *index.prepare_doc(doc))
    con.commit()
    con.close()
    monkeypatch.setenv("HUMANCORPUS_NO_FAST", "1")
    from humancorpus import server, web

    monkeypatch.setattr(server, "DB", db)
    monkeypatch.setattr(server, "_local", type(server._local)())
    server._cached_search.cache_clear()
    monkeypatch.setattr(index, "DEFAULT_DB", db)
    monkeypatch.setattr(web, "BURST", 5)
    monkeypatch.setattr(web, "RATE", 1)
    monkeypatch.setattr(server, "PROGRESS_STEPS", 1)
    with starlette.TestClient(web.build_app()) as c:
        yield c, server


H = {"content-type": "application/json", "accept": "application/json, text/event-stream"}


def call(c, name, args, headers=None):
    r = c.post("/mcp", headers={**H, **(headers or {})},
               json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})
    return r.status_code, (r.json() if r.status_code == 200 else None)


def test_forged_forwarded_for_does_not_reset_limit(client):
    c, _ = client
    codes = [call(c, "corpus_stats", {}, {"x-forwarded-for": f"9.9.9.{i}, 203.0.113.7, 8.8.8.8"})[0]
             for i in range(8)]
    assert codes.count(429) == 3  # same real client (8.8.8.8) each time, burst of 5


def test_errors_are_readable(client):
    c, _ = client
    _, body = call(c, "search_fragments", {"query": "x", "register": "bogus"})
    assert body["result"]["isError"] and "need the fast search index" in body["result"]["content"][0]["text"]
    _, body = call(c, "get_context", {"fragment_id": -1})
    assert "not found" in body["result"]["content"][0]["text"]


def test_slow_query_is_cut_off(client, monkeypatch):
    c, server = client
    monkeypatch.setattr(server, "QUERY_SECONDS", -1.0)  # every query is already over budget
    _, body = call(c, "search_fragments", {"query": "river*", "mode": "raw", "semantic": False})
    assert body["result"]["isError"] and "took longer" in body["result"]["content"][0]["text"]
    monkeypatch.setattr(server, "QUERY_SECONDS", 10.0)
    _, body = call(c, "search_fragments", {"query": "river*", "mode": "raw", "semantic": False})
    assert not body["result"]["isError"], body
