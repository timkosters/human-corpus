from humancorpus import index
from humancorpus.sources import Document
from humancorpus.text import is_good_fragment, split_sentences


def test_split_handles_abbreviations():
    s = split_sentences('Dr. Smith met J. R. R. Tolkien in 1950. "Was it fun?" she asked. Yes, e.g. very.')
    assert s == ["Dr. Smith met J. R. R. Tolkien in 1950.", '"Was it fun?" she asked.', "Yes, e.g. very."]


def test_fragment_filter():
    assert is_good_fragment("The river rose quickly after the storm.")
    assert not is_good_fragment("Early life")  # heading
    assert not is_good_fragment("See https://example.com for more.")


def _db(tmp_path):
    con = index.connect(tmp_path / "t.db")
    doc = Document("test", "1", "Rivers", "Someone", "https://x", "CC BY-SA 3.0", "2022-03-01",
                   ["The river flooded the valley every spring. Farmers welcomed the rich silt it left behind.",
                    "In summer the water ran low and clear."])
    index._add_doc(con, *index.prepare_doc(doc))
    con.commit()
    return con


def test_search_context_verify(tmp_path):
    con = _db(tmp_path)
    hits = index.search(con, "valley flood", semantic=False)
    assert hits and "flooded the valley" in hits[0]["text"]
    ctx = index.context(con, hits[0]["id"], window=1)
    assert len(ctx["fragments"]) == 2
    v = index.verify(con, "The river flooded the valley every spring. Synergy drives value. Farmers welcomed the rich silt.")
    assert [r["status"] for r in v["results"]] == ["exact", "not_found", "contained"]
    assert "CC BY-SA" in index.attribution(con, [hits[0]["id"]])


def test_register_tags():
    from humancorpus.text import register_code, register_name

    assert register_name(register_code("I miss you more than words can say.")) == "personal+emotive"
    assert register_name(register_code("I walked to the station.")) == "first_person"
    assert register_name(register_code("He crossed the bridge at dawn.")) == "narrative"
    assert register_name(register_code("The bridge spans the river.")) == "expository"


def test_fast_hybrid_search(tmp_path, monkeypatch):
    import pytest

    pytest.importorskip("tantivy")
    pytest.importorskip("faiss")
    from humancorpus import fast

    con = _db(tmp_path)
    doc = Document("letters", "2", "Letters", "Someone", "https://y", "Public domain (US)", "1890",
                   ["My darling, I miss you every morning. You are always in my heart.",
                    "The committee approved the annual budget."])
    index._add_doc(con, *index.prepare_doc(doc))
    con.commit()
    monkeypatch.delenv("HUMANCORPUS_SEARCH", raising=False)
    fast.build(tmp_path / "t.db")
    fast.reset()
    db = tmp_path / "t.db"
    try:
        hits = index.search(con, "valley flood", db=db)
        assert hits and "flooded the valley" in hits[0]["text"] and hits[0]["register"]
        warm = index.search(con, "heart", register="intimate", db=db)
        assert warm and all("emotive" in h["register"] for h in warm)
        assert index.search(con, "heart", source="letters", db=db)[0]["source"] == "letters"
        assert index.search(con, "valley", source="nope", db=db) == []
    finally:
        fast.reset()
