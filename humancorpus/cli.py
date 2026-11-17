"""Command line: build the corpus, search it, verify drafts, run the MCP server."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import index


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="humancorpus", description=__doc__)
    p.add_argument("--db", type=Path, default=index.DEFAULT_DB, help="corpus database path")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("ingest", help="download a source and index its sentences")
    i.add_argument("source", choices=["wikipedia", "gutenberg"])
    i.add_argument("--shards", type=int, default=1, help="parquet shards (wikipedia: 41, gutenberg: 52)")
    i.add_argument("--max-docs", type=int, default=None, help="stop after N documents")

    s = sub.add_parser("search", help="search fragments")
    s.add_argument("query")
    s.add_argument("-n", "--limit", type=int, default=10)
    s.add_argument("--mode", default="any", choices=["any", "all", "phrase", "raw"])
    s.add_argument("--source")
    s.add_argument("--phrases", action="store_true")
    s.add_argument("--no-semantic", action="store_true", help="plain BM25, skip embedding rerank")
    s.add_argument("--json", action="store_true")

    v = sub.add_parser("verify", help="check a draft (file or stdin) against the corpus")
    v.add_argument("file", nargs="?")
    v.add_argument("--json", action="store_true")

    sub.add_parser("stats", help="corpus statistics")
    sub.add_parser("serve", help="run the MCP server on stdio")

    a = p.parse_args(argv)

    if a.cmd == "ingest":
        print(json.dumps(index.ingest(a.source, a.db, shards=a.shards, max_docs=a.max_docs), indent=2))
    elif a.cmd == "search":
        rows = index.search(index.connect(a.db, readonly=True), a.query, limit=a.limit, mode=a.mode,
                            source=a.source, phrases=a.phrases, semantic=not a.no_semantic)
        if a.json:
            print(json.dumps(rows, indent=2))
        for r in rows if not a.json else []:
            print(f"[{r['id']}] {r['text']}\n      {r['source']}: {r['title']}")
            for ph in r.get("phrases", []):
                print(f"        > {ph}")
    elif a.cmd == "verify":
        text = Path(a.file).read_text() if a.file else sys.stdin.read()
        res = index.verify(index.connect(a.db, readonly=True), text)
        if a.json:
            print(json.dumps(res, indent=2))
        else:
            for r in res["results"]:
                mark = {"exact": "HUMAN", "contained": "HUMAN~", "not_found": "?????"}[r["status"]]
                src = f"  ({r['source']['title']})" if r["source"] else ""
                print(f"{mark:7} {r['sentence']}{src}")
            print(f"\n{res['human_verified']}/{res['sentences']} sentences verified human ({res['human_ratio']:.0%})")
    elif a.cmd == "stats":
        print(json.dumps(index.stats(index.connect(a.db, readonly=True)), indent=2))
    elif a.cmd == "serve":
        import os
        os.environ["HUMANCORPUS_DB"] = str(a.db)
        from .server import main as serve
        serve()


if __name__ == "__main__":
    main()
