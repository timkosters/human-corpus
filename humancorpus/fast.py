"""Fast hybrid search: Tantivy BM25 + 1-bit embeddings + register (style) tags.

These are sidecar files derived from corpus.db, so the SQLite schema is unchanged:

    <search dir>/
        manifest.json   sources, counts, model name
        tantivy/        BM25 index (block-max WAND top-k, stops early on common words)
        ids.npy         fragment id per row (uint32, sorted)
        bits.npy        sign bits of the potion embedding, 32 bytes per sentence
        bits.ivf        inverted-file index over bits (corpora of 1M+ rows)
        meta.npy        per row: words, source code, register code (uint8 each)
        mean.npy        embedding mean, subtracted before taking signs

Query: lexical top-k (Tantivy) + dense top-k (Hamming over bits, faiss) -> fetch texts from SQLite
-> re-embed candidates exactly -> blend meaning, style example and keyword rank -> MMR for variety.
If the sidecar is missing, index.search (SQLite FTS5) is used instead.

Build:  humancorpus --db corpus.db build-search  [--out DIR]
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import time
from pathlib import Path

import numpy as np

from .text import EMOTIVE_BIT, REGISTERS, STYLE_BIT, STYLES, register_code, register_name, style_mask, style_names

MODEL = os.environ.get("HUMANCORPUS_EMBED", "minishlab/potion-base-8M")

# Filter names accepted by search(register=...): a set of allowed register codes.
_ALL = range(16)
REGISTER_FILTERS: dict[str, set[int]] = {name: {c for c in _ALL if c & 7 == i} for i, name in enumerate(REGISTERS)}
REGISTER_FILTERS["emotive"] = {c for c in _ALL if c & EMOTIVE_BIT}
# "intimate": first or second person, with feeling words. The love-letter register.
REGISTER_FILTERS["intimate"] = {c for c in _ALL if c & EMOTIVE_BIT and c & 7 in (3, 4)}
REGISTER_FILTERS["conversational"] = {c for c in _ALL if c & 7 in (2, 3, 4)}


def default_dir(db: Path | str) -> Path:
    env = os.environ.get("HUMANCORPUS_SEARCH")
    return Path(env) if env else Path(db).parent / "search"


def _schema():
    import tantivy

    sb = tantivy.SchemaBuilder()
    sb.add_text_field("text", stored=False, tokenizer_name="en_stem", index_option="position")
    sb.add_unsigned_field("id", stored=True, indexed=False, fast=True)
    sb.add_unsigned_field("source", indexed=True, fast=True)
    sb.add_unsigned_field("register", indexed=True, fast=True)
    sb.add_unsigned_field("words", indexed=True, fast=True)
    sb.add_unsigned_field("styles", indexed=True)  # one value per style bit set
    return sb.build()


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def _tag(texts: list[str]) -> list[tuple[int, int]]:
    return [(register_code(t), style_mask(t)) for t in texts]


def build(db: Path | str, out: Path | str | None = None, batch: int = 50_000,
          heap_mb: int = 1500, threads: int | None = None, vectors: bool = True) -> dict:
    """vectors=False keeps existing bits/ids/IVF and rebuilds only tags + Tantivy (after tagger changes)."""
    import multiprocessing as mp

    import tantivy
    from model2vec import StaticModel

    pool = mp.get_context("fork").Pool(threads or (os.cpu_count() or 2))  # fork before any threads start
    db = Path(db)
    out = Path(out) if out else default_dir(db)
    (out / "tantivy").mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    t0 = time.time()
    n, max_id = con.execute("SELECT count(*), coalesce(max(id),0) FROM fragments").fetchone()
    if max_id >= 2**32:
        raise ValueError("fragment ids exceed uint32")
    sources = [r[0] for r in con.execute("SELECT DISTINCT source FROM docs ORDER BY source")]
    src_code = {s: i for i, s in enumerate(sources)}
    doc_src = dict(con.execute("SELECT id, source FROM docs"))
    model = StaticModel.from_pretrained(MODEL) if vectors else None
    if not vectors:
        old = np.load(out / "ids.npy", mmap_mode="r")
        if len(old) != n:
            raise ValueError(f"existing vectors have {len(old):,} rows, corpus has {n:,}: rebuild with vectors")
        prev = json.loads((out / "manifest.json").read_text())

    # Mean of a sample, so sign bits split each dimension near its median.
    if vectors:
        sample = [r[0] for r in con.execute("SELECT text FROM fragments WHERE id % ? = 0 LIMIT 100000",
                                            (max(1, n // 100_000),))]
        mean = model.encode(sample).mean(axis=0).astype(np.float32)
        dim = mean.shape[0]
        np.save(out / "mean.npy", mean)
        ids = np.lib.format.open_memmap(out / "ids.npy", mode="w+", dtype=np.uint32, shape=(n,))
        bits = np.lib.format.open_memmap(out / "bits.npy", mode="w+", dtype=np.uint8, shape=(n, dim // 8))
    else:
        dim = prev["dim"]
    meta = np.lib.format.open_memmap(out / "meta.npy", mode="w+", dtype=np.uint8, shape=(n, 3))
    styles = np.lib.format.open_memmap(out / "styles.npy", mode="w+", dtype=np.uint16, shape=(n,))

    index = tantivy.Index(_schema(), path=str(out / "tantivy"), reuse=False)
    writer = index.writer(heap_size=heap_mb * 1_000_000, num_threads=threads or (os.cpu_count() or 2))
    row = 0
    cur = con.execute("SELECT id, doc_id, words, text FROM fragments ORDER BY id")
    while True:
        chunk = cur.fetchmany(batch)
        if not chunk:
            break
        texts = [c[3] for c in chunk]
        k = len(chunk)
        tagged = pool.map_async(_tag, [texts[i:i + 2000] for i in range(0, k, 2000)])
        if vectors:
            emb = model.encode(texts) - mean
            bits[row:row + k] = np.packbits(emb > 0, axis=1)
            ids[row:row + k] = [c[0] for c in chunk]
        tags = [t for part in tagged.get() for t in part]
        for j, ((fid, doc_id, words, text), (r, st)) in enumerate(zip(chunk, tags)):
            s = src_code[doc_src[doc_id]]
            w = min(words, 255)
            meta[row + j] = (w, s, r)
            styles[row + j] = st
            doc = tantivy.Document()
            doc.add_unsigned("id", fid)
            doc.add_unsigned("source", s)
            doc.add_unsigned("register", r)
            doc.add_unsigned("words", w)
            for b, name in enumerate(STYLES):
                if st >> b & 1:
                    doc.add_unsigned("styles", b)
            doc.add_text("text", text)
            writer.add_document(doc)
        row += k
        rate = row / (time.time() - t0)
        print(f"build-search: {row:,}/{n:,} ({rate:,.0f} rows/s)", file=sys.stderr, flush=True)
    pool.close()
    writer.commit()
    writer.wait_merging_threads()
    for a in (meta, styles) + ((ids, bits) if vectors else ()):
        a.flush()
    docs = {r[0]: [r[1], r[2]] for r in con.execute("SELECT source, max(license), count(*) FROM docs GROUP BY source")}
    manifest = {"rows": row, "sources": sources, "docs": docs, "model": MODEL, "dim": int(dim), "registers": REGISTERS,
                "styles": STYLES, "built_from": db.name, "seconds": round(time.time() - t0, 1)}
    con.close()
    if not vectors and "ivf" in prev:
        manifest["ivf"] = prev["ivf"]
    elif row >= 1_000_000:
        manifest["ivf"] = build_ivf(out)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def build_ivf(out: Path | str, nlist: int | None = None, train_n: int = 500_000) -> dict:
    """Inverted-file index over the 1-bit vectors: scans ~1% of rows per query instead of all."""
    import faiss

    out = Path(out)
    bits = np.load(out / "bits.npy", mmap_mode="r")
    n, nbytes = bits.shape
    nlist = nlist or int(min(16384, max(256, 4 * np.sqrt(n))))
    t0 = time.time()
    quant = faiss.IndexBinaryFlat(nbytes * 8)
    ivf = faiss.IndexBinaryIVF(quant, nbytes * 8, nlist)
    sample = np.sort(np.random.default_rng(0).choice(n, size=min(n, train_n), replace=False))
    ivf.train(np.ascontiguousarray(bits[sample]))
    for s in range(0, n, 2_000_000):
        ivf.add(np.ascontiguousarray(bits[s:s + 2_000_000]))
        print(f"build-ivf: {min(n, s + 2_000_000):,}/{n:,}", file=sys.stderr, flush=True)
    faiss.write_index_binary(ivf, str(out / "bits.ivf"))
    return {"nlist": nlist, "rows": n, "seconds": round(time.time() - t0, 1)}


# --------------------------------------------------------------------------- #
# Query
# --------------------------------------------------------------------------- #
class Engine:
    def __init__(self, path: Path | str):
        import faiss
        import tantivy
        from model2vec import StaticModel

        path = Path(path)
        self.manifest = json.loads((path / "manifest.json").read_text())
        self.sources = self.manifest["sources"]
        self.ids = np.load(path / "ids.npy", mmap_mode="r")
        self.meta = np.load(path / "meta.npy")  # small: 3 bytes per row, kept in RAM
        sp = path / "styles.npy"
        self.styles = np.load(sp) if sp.exists() else np.zeros(len(self.meta), dtype=np.uint16)
        self.has_styles = sp.exists()
        self.mean = np.load(path / "mean.npy")
        self.model = StaticModel.from_pretrained(self.manifest.get("model", MODEL))
        self.schema = _schema()
        self.tindex = tantivy.Index.open(str(path / "tantivy"))
        self.tindex.reload()
        self.lock = threading.Lock()
        bits = np.load(path / "bits.npy", mmap_mode="r")
        dim = bits.shape[1] * 8
        # Main 1-bit index, plus small ones for selective register filters (so a filtered
        # dense search scans only the matching rows).
        if (path / "bits.ivf").exists():
            self.bindex = faiss.read_index_binary(str(path / "bits.ivf"))
            self.bindex.nprobe = int(os.environ.get("HUMANCORPUS_NPROBE", 96))
        else:
            self.bindex = self._binary_index(bits, None, dim)
        self.sub: dict[str, tuple[object, np.ndarray]] = {}
        regs = self.meta[:, 2]
        for name in ("intimate", "personal", "first_person", "dialogue", "emotive", "conversational"):
            rows = np.flatnonzero(np.isin(regs, list(REGISTER_FILTERS[name]))).astype(np.int64)
            if 0 < len(rows) < 0.4 * len(regs):
                self.sub[name] = (self._binary_index(bits, rows, dim), rows)
        for name in STYLES if self.has_styles else ():
            rows = np.flatnonzero(self.styles & STYLE_BIT[name]).astype(np.int64)
            if 0 < len(rows) < 0.4 * len(regs):
                self.sub[name] = (self._binary_index(bits, rows, dim), rows)
        faiss.omp_set_num_threads(int(os.environ.get("HUMANCORPUS_THREADS", os.cpu_count() or 2)))

    @staticmethod
    def _binary_index(bits, rows, dim, chunk=2_000_000):
        import faiss

        idx = faiss.IndexBinaryFlat(dim)
        n = len(rows) if rows is not None else bits.shape[0]
        for s in range(0, n, chunk):
            part = bits[rows[s:s + chunk]] if rows is not None else bits[s:s + chunk]
            idx.add(np.ascontiguousarray(part))
        return idx

    # -- pieces ------------------------------------------------------------- #
    def _embed(self, texts: list[str]) -> np.ndarray:
        v = self.model.encode(texts).astype(np.float32)
        return v

    def _rows_for_ids(self, fids) -> np.ndarray:
        return np.searchsorted(self.ids, np.asarray(fids, dtype=np.uint32))

    def _allowed(self, rows: np.ndarray, source_code, min_words, max_words, reg_codes, smask=0) -> np.ndarray:
        m = self.meta[rows]
        ok = (m[:, 0] >= min_words) & (m[:, 0] <= max_words)
        if source_code is not None:
            ok &= m[:, 1] == source_code
        if reg_codes is not None:
            ok &= np.isin(m[:, 2], list(reg_codes))
        if smask:
            ok &= (self.styles[rows] & smask) == smask
        return ok

    def lexical(self, terms: list[str], mode: str, k: int, source_code, min_words, max_words, reg_codes,
                styles: list[str] = ()):
        import tantivy

        if not terms:
            return []
        q = self.tindex.parse_query(_tantivy_query(terms, mode), ["text"])
        must = [(tantivy.Occur.Must, q),
                (tantivy.Occur.Must, tantivy.Query.range_query(self.schema, "words", tantivy.FieldType.Unsigned,
                                                               min_words, max_words))]
        if source_code is not None:
            must.append((tantivy.Occur.Must, tantivy.Query.term_query(self.schema, "source", source_code)))
        if reg_codes is not None:
            must.append((tantivy.Occur.Must,
                         tantivy.Query.term_set_query(self.schema, "register", sorted(reg_codes))))
        for name in styles:
            must.append((tantivy.Occur.Must, tantivy.Query.term_query(self.schema, "styles", STYLES.index(name))))
        with self.lock:
            searcher = self.tindex.searcher()
            hits = searcher.search(tantivy.Query.boolean_query(must), k, count=False).hits
            return [searcher.doc(addr)["id"][0] for _, addr in hits]

    def dense(self, qvec: np.ndarray, k: int, source_code, min_words, max_words, register: str | None,
              reg_codes, styles: list[str] = ()) -> list[int]:
        qbits = np.packbits((qvec - self.mean) > 0)[None, :]
        smask = sum(STYLE_BIT[n] for n in styles)
        # Scan the smallest matching sub-index; other filters are applied after.
        keys = [n for n in list(styles) + [register] if n in self.sub]
        key = min(keys, key=lambda n: len(self.sub[n][1])) if keys else None
        if key:
            idx, rowmap = self.sub[key]
            _, I = idx.search(qbits, k)
            rows = rowmap[I[0][I[0] >= 0]]
        else:
            _, I = self.bindex.search(qbits, k)
            rows = I[0][I[0] >= 0]
        rows = rows[self._allowed(rows, source_code, min_words, max_words, reg_codes, smask)]
        return [int(x) for x in self.ids[rows]]

    def register_of(self, fids: list[int]) -> list[str]:
        rows = self._rows_for_ids(fids)
        return [register_name(int(c)) for c in self.meta[rows, 2]]

    def styles_of(self, fids: list[int]) -> list[list[str]]:
        rows = self._rows_for_ids(fids)
        return [style_names(int(m)) for m in self.styles[rows]]


def _tantivy_query(terms: list[str], mode: str) -> str:
    clean = [t.replace("'", "") for t in terms]
    clean = [t for t in clean if t]
    if mode == "phrase":
        return '"' + " ".join(clean) + '"'
    return (" AND " if mode == "all" else " OR ").join(clean)


_ENGINE: Engine | None | bool = None
_ENGINE_LOCK = threading.Lock()


def engine(db: Path | str) -> Engine | None:
    """Load the sidecar once. None when it is missing or its libraries aren't installed."""
    global _ENGINE
    if _ENGINE is None:
        with _ENGINE_LOCK:
            if _ENGINE is None:
                path = default_dir(db)
                try:
                    if not (path / "manifest.json").exists():
                        raise FileNotFoundError(path)
                    t = time.time()
                    _ENGINE = Engine(path)
                    print(f"fast search loaded from {path} in {time.time() - t:.1f}s", file=sys.stderr, flush=True)
                except Exception as e:  # missing sidecar or libraries: fall back to FTS5
                    print(f"fast search unavailable ({e!r}); using SQLite FTS5", file=sys.stderr, flush=True)
                    _ENGINE = False
    return _ENGINE or None


def reset() -> None:
    global _ENGINE
    _ENGINE = None
