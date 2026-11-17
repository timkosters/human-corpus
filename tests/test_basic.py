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
