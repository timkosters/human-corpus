"""MCP server exposing the human-text corpus. Runs over stdio (local) or HTTP (hosted)."""
from __future__ import annotations

import os
import threading
from pathlib import Path

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP

from . import guide, index

DB = Path(os.environ.get("HUMANCORPUS_DB", index.DEFAULT_DB))
MAX_VERIFY_CHARS = 20_000

mcp = FastMCP("human-corpus", instructions=guide.SHORT)
_local = threading.local()


def con():
    """One read-only connection per thread (HTTP tools run in a thread pool)."""
    c = getattr(_local, "con", None)
    if c is None:
        c = _local.con = index.connect(DB, readonly=True)
    return c


@mcp.tool()
def search_fragments(query: str, limit: int = 10, mode: str = "any", source: str | None = None,
                     min_words: int = 4, max_words: int = 40, phrases: bool = False,
                     semantic: bool = True) -> list[dict]:
    """Find human-written sentences matching a query (BM25, plus semantic rerank if installed).

    query: keywords or a short idea, e.g. "river flooded the valley in spring".
    mode: "any" (default, ranked OR), "all" (every keyword), "phrase" (exact word sequence),
          or "raw" (FTS5 syntax: NEAR, prefix*, AND/OR/NOT).
    source: "wikipedia" or "gutenberg" to restrict; omit for all.
    min_words/max_words: fragment length bounds.
    phrases: also return clause-sized pieces of each sentence, best match first.
    semantic: rerank keyword hits by meaning.
    Returns id, text, source, title, author, url, license for each fragment.
    """
    return index.search(con(), query[:500], limit=max(1, min(limit, 50)), mode=mode, source=source,
                        min_words=min_words, max_words=max_words, phrases=phrases,
                        semantic=semantic)


@mcp.tool()
def get_context(fragment_id: int, window: int = 2) -> dict:
    """Show the sentences around a fragment in its original document."""
    return index.context(con(), fragment_id, window=max(0, min(window, 10)))


@mcp.tool()
def random_fragments(n: int = 5, topic: str | None = None, source: str | None = None) -> list[dict]:
    """Random human sentences, optionally on a topic. Useful for inspiration or voice."""
    return index.random_fragments(con(), n=max(1, min(n, 25)), query=topic, source=source)


@mcp.tool()
def verify_draft(text: str) -> dict:
    """Check every sentence of a draft against the corpus.

    Each sentence gets status "exact" (verbatim human sentence), "contained" (verbatim inside a
    human sentence) or "not_found". human_ratio is the share of sentences that are human-sourced.
    """
    return index.verify(con(), text[:MAX_VERIFY_CHARS])


@mcp.tool()
def cite_sources(fragment_ids: list[int]) -> str:
    """Attribution block for the fragments used. Required when reusing Wikipedia (CC BY-SA) text."""
    return index.attribution(con(), fragment_ids[:500])


@mcp.tool()
def corpus_stats() -> dict:
    """Sources, licenses and fragment counts in the corpus."""
    return index.stats(con())


@mcp.resource("guide://compose")
def compose_guide() -> str:
    """Full method for composing text from human fragments."""
    return guide.GUIDE


@mcp.prompt()
def compose_from_fragments(brief: str, mode: str = "seeded") -> str:
    """Draft a piece from verifiably human sentences."""
    return f"{guide.GUIDE}\n\n## Task\nMode: {mode}\nBrief: {brief}\n"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
