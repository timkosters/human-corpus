"""SQLite FTS5 index of human-written sentence fragments."""
from __future__ import annotations

import os
import re
import sqlite3
import sys
import time
from pathlib import Path

from .sources import SOURCES, Document
from .text import clauses, fingerprint, is_good_fragment, normalize, split_sentences, word_count

DEFAULT_DB = Path(os.environ.get("HUMANCORPUS_DB", Path.home() / ".cache" / "humancorpus" / "corpus.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    ext_id TEXT NOT NULL,
    title TEXT, author TEXT, url TEXT, license TEXT, date TEXT,
    UNIQUE(source, ext_id)
);
CREATE TABLE IF NOT EXISTS fragments (
    id INTEGER PRIMARY KEY,
    doc_id INTEGER NOT NULL REFERENCES docs(id),
    pos INTEGER NOT NULL,
    words INTEGER NOT NULL,
    hash TEXT NOT NULL UNIQUE,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS fragments_doc_pos ON fragments(doc_id, pos);
CREATE VIRTUAL TABLE IF NOT EXISTS fragments_fts USING fts5(
    text, content='fragments', content_rowid='id',
    tokenize='porter unicode61 remove_diacritics 2'
);
"""

STOPWORDS = set(
    "a an and are as at be but by for from has have he her his i if in into is it its of on or "
    "she so than that the their them then there these they this to was were which who will with "
    "would you your we our not no can could should do does did about over".split()
)


def connect(db: Path | str = DEFAULT_DB, readonly: bool = False) -> sqlite3.Connection:
    db = Path(db)
    if readonly:
        if not db.exists():
            raise FileNotFoundError(f"No corpus at {db}. Build one with: humancorpus ingest wikipedia")
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, check_same_thread=False)
    else:
        db.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(db)
        con.executescript(SCHEMA)
    con.row_factory = sqlite3.Row
    return con


# --------------------------------------------------------------------------- #
# Ingest
# --------------------------------------------------------------------------- #
def ingest(source: str, db: Path | str = DEFAULT_DB, shards: int = 1, max_docs: int | None = None,
           min_words: int = 4, max_words: int = 80) -> dict:
    con = connect(db)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=OFF")
    src = SOURCES[source]()
    t0 = time.time()
    n_docs = n_frag = n_dup = 0
    for doc in src.iter_docs(shards=shards, max_docs=max_docs):
        n, d = _add_doc(con, doc, min_words, max_words)
        n_frag += n
        n_dup += d
        n_docs += 1
        if n_docs % 2000 == 0:
            con.commit()
            rate = n_docs / (time.time() - t0)
            print(f"{source}: {n_docs:,} docs, {n_frag:,} fragments ({rate:.0f} docs/s)", file=sys.stderr)
    con.commit()
    con.execute("INSERT INTO fragments_fts(fragments_fts) VALUES('optimize')")
    con.commit()
    con.close()
    return {"source": source, "docs": n_docs, "fragments": n_frag, "duplicates_skipped": n_dup,
            "seconds": round(time.time() - t0, 1)}


def _add_doc(con: sqlite3.Connection, doc: Document, min_words: int, max_words: int) -> tuple[int, int]:
    cur = con.execute(
        "INSERT OR IGNORE INTO docs(source, ext_id, title, author, url, license, date) VALUES (?,?,?,?,?,?,?)",
        (doc.source, doc.ext_id, doc.title, doc.author, doc.url, doc.license, doc.date),
    )
    if cur.rowcount == 0:
        return 0, 0  # already ingested
    doc_id = cur.lastrowid
    pos = added = dups = 0
    for para in doc.paragraphs:
        for sent in split_sentences(para):
            pos += 1
            if not is_good_fragment(sent, min_words, max_words):
                continue
            c = con.execute(
                "INSERT OR IGNORE INTO fragments(doc_id, pos, words, hash, text) VALUES (?,?,?,?,?)",
                (doc_id, pos, word_count(sent), fingerprint(sent), sent),
            )
            if c.rowcount:
                con.execute("INSERT INTO fragments_fts(rowid, text) VALUES (?, ?)", (c.lastrowid, sent))
                added += 1
            else:
                dups += 1
        pos += 1  # paragraph gap, so context windows respect paragraph breaks
    return added, dups


# --------------------------------------------------------------------------- #
# Query
# --------------------------------------------------------------------------- #
_TOKEN = re.compile(r"[A-Za-z0-9À-ɏ']+")


def build_match(query: str, mode: str = "any") -> str:
    """Turn natural language into a safe FTS5 MATCH expression."""
    if mode == "raw":
        return query
    if mode == "phrase":
        return '"' + " ".join(_TOKEN.findall(query)) + '"'
    terms = [t for t in _TOKEN.findall(query.lower()) if t not in STOPWORDS and len(t) > 1]
    if not terms:
        terms = _TOKEN.findall(query.lower())
    terms = [f'"{t}"' for t in dict.fromkeys(terms)]
    return (" AND " if mode == "all" else " OR ").join(terms)


_FRAG_COLS = """f.id, f.text, f.words, d.source, d.title, d.author, d.url, d.license, d.date"""


def _row(r: sqlite3.Row) -> dict:
    return {k: r[k] for k in r.keys()}


_MODEL = None


def _embedder():
    """Optional tiny static embedding model (pip install model2vec). None if unavailable."""
    global _MODEL
    if _MODEL is None:
        try:
            from model2vec import StaticModel

            _MODEL = StaticModel.from_pretrained(os.environ.get("HUMANCORPUS_EMBED", "minishlab/potion-base-8M"))
        except Exception:  # not installed or offline
            _MODEL = False
    return _MODEL or None


def _rerank(query: str, rows: list[dict], limit: int) -> list[dict]:
    model = _embedder()
    if not model or not rows:
        return rows[:limit]
    import numpy as np

    vecs = model.encode([query] + [r["text"] for r in rows])
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9
    sims = vecs[1:] @ vecs[0]
    # Blend semantic similarity with the BM25 rank.
    n = len(rows)
    for i, (r, s) in enumerate(zip(rows, sims)):
        r["similarity"] = round(float(s), 3)
        r["_blend"] = 0.7 * float(s) + 0.3 * (1 - i / n)
    rows.sort(key=lambda r: -r.pop("_blend"))
    return rows[:limit]


def search(con: sqlite3.Connection, query: str, limit: int = 10, mode: str = "any",
           source: str | None = None, min_words: int = 4, max_words: int = 60,
           phrases: bool = False, semantic: bool = True) -> list[dict]:
    """BM25 search, then (if model2vec is installed) semantic rerank of the top candidates."""
    match = build_match(query, mode)
    if not match:
        return []
    sql = f"""
        SELECT {_FRAG_COLS}, bm25(fragments_fts) AS score
        FROM fragments_fts JOIN fragments f ON f.id = fragments_fts.rowid
        JOIN docs d ON d.id = f.doc_id
        WHERE fragments_fts MATCH ? AND f.words BETWEEN ? AND ?
        {"AND d.source = ?" if source else ""}
        ORDER BY score LIMIT ?
    """
    args: list = [match, min_words, max_words]
    if source:
        args.append(source)
    use_sem = semantic and mode in ("any", "all") and _embedder() is not None
    args.append(max(limit * 15, 150) if use_sem else limit)
    rows = [_row(r) for r in con.execute(sql, args)]
    if use_sem:
        rows = _rerank(query, rows, limit)
    if phrases:
        terms = {t for t in _TOKEN.findall(query.lower()) if t not in STOPWORDS}
        for r in rows:
            cl = clauses(r["text"])
            r["phrases"] = sorted(cl, key=lambda c: -len(terms & set(_TOKEN.findall(c.lower()))))[:3]
    return rows


def random_fragments(con: sqlite3.Connection, n: int = 5, query: str | None = None,
                     source: str | None = None, min_words: int = 6, max_words: int = 40) -> list[dict]:
    if query:
        rows = search(con, query, limit=200, source=source, min_words=min_words, max_words=max_words,
                      semantic=False)
        import random
        random.shuffle(rows)
        return rows[:n]
    max_id = con.execute("SELECT max(id) FROM fragments").fetchone()[0] or 0
    import random
    out: list[dict] = []
    tries = 0
    while len(out) < n and tries < n * 50:
        tries += 1
        r = con.execute(
            f"SELECT {_FRAG_COLS} FROM fragments f JOIN docs d ON d.id=f.doc_id WHERE f.id >= ? "
            f"AND f.words BETWEEN ? AND ? {'AND d.source = ?' if source else ''} LIMIT 1",
            [random.randint(1, max_id), min_words, max_words] + ([source] if source else []),
        ).fetchone()
        if r and r["id"] not in {o["id"] for o in out}:
            out.append(_row(r))
    return out


def context(con: sqlite3.Connection, fragment_id: int, window: int = 2) -> dict:
    f = con.execute("SELECT doc_id, pos FROM fragments WHERE id = ?", (fragment_id,)).fetchone()
    if not f:
        raise KeyError(f"fragment {fragment_id} not found")
    rows = con.execute(
        f"SELECT {_FRAG_COLS}, f.pos FROM fragments f JOIN docs d ON d.id=f.doc_id "
        "WHERE f.doc_id = ? AND f.pos BETWEEN ? AND ? ORDER BY f.pos",
        (f["doc_id"], f["pos"] - window * 2, f["pos"] + window * 2),
    ).fetchall()
    rows = [_row(r) for r in rows]
    i = next(i for i, r in enumerate(rows) if r["id"] == fragment_id)
    rows = rows[max(0, i - window): i + window + 1]
    meta = {k: rows[0][k] for k in ("source", "title", "author", "url", "license", "date")}
    return {**meta, "fragments": [{"id": r["id"], "text": r["text"], "focus": r["id"] == fragment_id} for r in rows]}


def verify(con: sqlite3.Connection, text: str) -> dict:
    """Check each sentence of a draft against the corpus.

    exact:     the sentence exists verbatim as a human-written sentence.
    contained: the sentence appears verbatim inside a longer human sentence.
    not_found: no verbatim human source (this sentence may be machine-written).
    """
    results = []
    for para in re.split(r"\n\s*\n", text):
        for sent in split_sentences(para):
            row = con.execute(
                f"SELECT {_FRAG_COLS} FROM fragments f JOIN docs d ON d.id=f.doc_id WHERE f.hash = ?",
                (fingerprint(sent),),
            ).fetchone()
            status, match = "not_found", None
            if row:
                status, match = "exact", _row(row)
            else:
                toks = _TOKEN.findall(sent)
                if len(toks) >= 3:
                    norm = normalize(sent).rstrip(".!?")
                    for r in con.execute(
                        f"SELECT {_FRAG_COLS} FROM fragments_fts JOIN fragments f ON f.id=fragments_fts.rowid "
                        "JOIN docs d ON d.id=f.doc_id WHERE fragments_fts MATCH ? LIMIT 50",
                        ('"' + " ".join(toks) + '"',),
                    ):
                        if norm in normalize(r["text"]):
                            status, match = "contained", _row(r)
                            break
            results.append({"sentence": sent, "status": status, "source": match})
    total = len(results)
    human = sum(r["status"] != "not_found" for r in results)
    return {"sentences": total, "human_verified": human,
            "human_ratio": round(human / total, 3) if total else 0.0, "results": results}


def stats(con: sqlite3.Connection) -> dict:
    by_source = con.execute(
        "SELECT d.source, d.license, count(DISTINCT d.id) docs, count(f.id) fragments "
        "FROM docs d LEFT JOIN fragments f ON f.doc_id=d.id GROUP BY d.source, d.license"
    ).fetchall()
    return {"sources": [_row(r) for r in by_source]}


def attribution(con: sqlite3.Connection, fragment_ids: list[int]) -> str:
    """Attribution block for fragments used in a draft (needed for CC BY-SA text)."""
    qs = ",".join("?" * len(fragment_ids))
    rows = con.execute(
        f"SELECT DISTINCT d.title, d.author, d.url, d.license, d.date FROM fragments f "
        f"JOIN docs d ON d.id=f.doc_id WHERE f.id IN ({qs}) ORDER BY d.source, d.title",
        fragment_ids,
    ).fetchall()
    lines = ["Sources:"]
    for r in rows:
        lines.append(f"- \"{r['title']}\", {r['author']} ({r['date']}), {r['license']}. {r['url']}")
    if any("BY-SA" in r["license"] for r in rows):
        lines.append("Text from Wikipedia is reused under CC BY-SA; derivative text must carry the same license.")
    return "\n".join(lines)
