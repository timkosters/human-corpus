"""MCP server exposing the human-text corpus to Claude (stdio transport)."""
from __future__ import annotations

import os
from pathlib import Path

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP

from . import index

DB = Path(os.environ.get("HUMANCORPUS_DB", index.DEFAULT_DB))

mcp = FastMCP(
    "human-corpus",
    instructions=(
        "Search a corpus of verifiably human-written sentences (Wikipedia 2022-03 snapshot, "
        "Project Gutenberg). Use search_fragments to find real sentences or phrases to build "
        "a draft from, get_context to see surrounding text, verify_draft to check which "
        "sentences of a draft are verbatim human text, and cite_sources for attribution."
    ),
)
_con = None


def con():
    global _con
    if _con is None:
        _con = index.connect(DB, readonly=True)
    return _con


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
    semantic: rerank keyword hits by meaning (needs the optional model2vec install).
    Returns id, text, source, title, author, url, license for each fragment.
    """
    return index.search(con(), query, limit=min(limit, 50), mode=mode, source=source,
                        min_words=min_words, max_words=max_words, phrases=phrases,
                        semantic=semantic)


@mcp.tool()
def get_context(fragment_id: int, window: int = 2) -> dict:
    """Show the sentences around a fragment in its original document."""
    return index.context(con(), fragment_id, window=min(window, 10))


@mcp.tool()
def random_fragments(n: int = 5, topic: str | None = None, source: str | None = None) -> list[dict]:
    """Random human sentences, optionally on a topic. Useful for inspiration or voice."""
    return index.random_fragments(con(), n=min(n, 25), query=topic, source=source)


@mcp.tool()
def verify_draft(text: str) -> dict:
    """Check every sentence of a draft against the corpus.

    Each sentence gets status "exact" (verbatim human sentence), "contained" (verbatim inside a
    human sentence) or "not_found". human_ratio is the share of sentences that are human-sourced.
    """
    return index.verify(con(), text)


@mcp.tool()
def cite_sources(fragment_ids: list[int]) -> str:
    """Attribution block for the fragments used. Required when reusing Wikipedia (CC BY-SA) text."""
    return index.attribution(con(), fragment_ids)


@mcp.tool()
def corpus_stats() -> dict:
    """Sources, licenses and fragment counts in the local corpus."""
    return index.stats(con())


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
