"""Corpus sources. Each yields Document records of verifiably human, pre-LLM text.

Provenance rules:
- Wikipedia: the 2022-03-01 English dump (8 months before ChatGPT's release on
  2022-11-30). License CC BY-SA 3.0/4.0, attribution required.
- Project Gutenberg: public-domain books (almost all pre-1930 originals).
"""
from __future__ import annotations

import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

CACHE = Path(os.environ.get("HUMANCORPUS_CACHE", Path.home() / ".cache" / "humancorpus"))
HF = "https://huggingface.co/datasets"


@dataclass
class Document:
    source: str
    ext_id: str
    title: str
    author: str
    url: str
    license: str
    date: str  # date the text is known to predate LLMs (snapshot or publication)
    paragraphs: list[str]


@dataclass
class Source:
    name: str
    description: str
    license: str
    shard_urls: list[str]

    def iter_docs(self, shards: int, max_docs: int | None) -> Iterator[Document]:
        raise NotImplementedError


def _download(url: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / url.rsplit("/", 1)[-1]
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    tmp = dest.with_suffix(".part")
    print(f"downloading {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "humancorpus/0.1"})
    with urllib.request.urlopen(req) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.rename(dest)
    return dest


def _iter_parquet(urls: list[str], columns: list[str]) -> Iterator[dict]:
    import pyarrow.parquet as pq

    for url in urls:
        pf = pq.ParquetFile(_download(url))
        for batch in pf.iter_batches(batch_size=256, columns=columns):
            yield from batch.to_pylist()


# --------------------------------------------------------------------------- #
# Wikipedia
# --------------------------------------------------------------------------- #
_WIKI_SKIP_SECTIONS = {
    "references", "external links", "see also", "notes", "further reading",
    "bibliography", "sources", "citations", "footnotes", "works cited",
}


class Wikipedia(Source):
    def __init__(self) -> None:
        base = f"{HF}/legacy-datasets/wikipedia/resolve/main/data/20220301.en"
        super().__init__(
            name="wikipedia",
            description="English Wikipedia, 2022-03-01 snapshot (pre-ChatGPT)",
            license="CC BY-SA 3.0",
            shard_urls=[f"{base}/train-{i:05d}-of-00041.parquet" for i in range(41)],
        )

    def iter_docs(self, shards: int, max_docs: int | None) -> Iterator[Document]:
        n = 0
        for row in _iter_parquet(self.shard_urls[:shards], ["id", "url", "title", "text"]):
            paras: list[str] = []
            for block in row["text"].split("\n"):
                block = block.strip()
                if not block:
                    continue
                if block.lower() in _WIKI_SKIP_SECTIONS:
                    break  # everything after is lists and citations
                paras.append(block)
            yield Document(
                source=self.name, ext_id=row["id"], title=row["title"], author="Wikipedia contributors",
                url=row["url"].replace("%20", "_"), license=self.license, date="2022-03-01", paragraphs=paras,
            )
            n += 1
            if max_docs and n >= max_docs:
                return


# --------------------------------------------------------------------------- #
# Project Gutenberg
# --------------------------------------------------------------------------- #
_PG_START = re.compile(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG[^\n]*", re.I)
_PG_END = re.compile(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG|End of (the )?Project Gutenberg", re.I)
_PG_TITLE = re.compile(r"^Title:\s*(.+)$", re.M)
_PG_AUTHOR = re.compile(r"^Author:\s*(.+)$", re.M)
_PG_NOISE = re.compile(
    r"(produced by|prepared by|transcriber|proofread|gutenberg|e-text|etext|illustrat|"
    r"distributed proofreading|internet archive|\[illustration|\bchapter [ivxlc0-9]+\b)", re.I
)


class Gutenberg(Source):
    def __init__(self) -> None:
        self._listing_url = f"https://huggingface.co/api/datasets/manu/project_gutenberg/tree/main/data"
        super().__init__(
            name="gutenberg",
            description="Project Gutenberg English books (public domain)",
            license="Public domain (US)",
            shard_urls=[],
        )

    def _shards(self) -> list[str]:
        if not self.shard_urls:
            import json

            req = urllib.request.Request(self._listing_url, headers={"User-Agent": "humancorpus/0.1"})
            with urllib.request.urlopen(req) as r:
                files = sorted(x["path"] for x in json.load(r) if x["path"].startswith("data/en-"))
            self.shard_urls = [f"{HF}/manu/project_gutenberg/resolve/main/{p}" for p in files]
        return self.shard_urls

    def iter_docs(self, shards: int, max_docs: int | None) -> Iterator[Document]:
        n = 0
        for row in _iter_parquet(self._shards()[:shards], ["id", "text"]):
            raw = row["text"]
            head = raw[:5000]
            title = (m.group(1).strip() if (m := _PG_TITLE.search(head)) else f"Gutenberg #{row['id']}")
            author = (m.group(1).strip() if (m := _PG_AUTHOR.search(head)) else "Unknown")
            if (m := _PG_START.search(raw)):
                raw = raw[m.end():]
            if (m := _PG_END.search(raw)):
                raw = raw[: m.start()]
            paras = []
            for block in re.split(r"\n\s*\n", raw):
                # Unwrap hard line breaks; drop italics underscores.
                text = re.sub(r"\s*\n\s*", " ", block).replace("_", "").strip()
                if not text or _PG_NOISE.search(text):
                    continue
                paras.append(text)
            book_id = row["id"].split("-")[0]
            yield Document(
                source=self.name, ext_id=row["id"], title=title, author=author,
                url=f"https://www.gutenberg.org/ebooks/{book_id}", license=self.license,
                date="public domain", paragraphs=paras,
            )
            n += 1
            if max_docs and n >= max_docs:
                return


SOURCES: dict[str, type[Source]] = {"wikipedia": Wikipedia, "gutenberg": Gutenberg}
