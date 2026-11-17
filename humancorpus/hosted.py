"""Entry point for hosted deployments: fetch the index from Hugging Face, then serve HTTP."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def ensure_db() -> Path:
    db = Path(os.environ.get("HUMANCORPUS_DB", "/home/user/data/corpus.db"))
    if db.exists():
        return db
    from huggingface_hub import hf_hub_download

    repo = os.environ.get("HUMANCORPUS_DATASET", "timourxyz/human-corpus")
    print(f"downloading index from {repo} ...", file=sys.stderr, flush=True)
    path = hf_hub_download(repo, "corpus.db", repo_type="dataset", local_dir=db.parent)
    return Path(path)


def ensure_search(db: Path) -> None:
    """Fetch the fast-search sidecar (search/) if the dataset has one. Optional: FTS5 is the fallback."""

    if os.environ.get("HUMANCORPUS_NO_FAST"):
        return
    # Always sync: snapshot_download only fetches files that changed since the last download.
    try:
        from huggingface_hub import snapshot_download

        repo = os.environ.get("HUMANCORPUS_DATASET", "timourxyz/human-corpus")
        print(f"downloading fast search index from {repo} ...", file=sys.stderr, flush=True)
        snapshot_download(repo, repo_type="dataset", allow_patterns=["search/*", "search/**"],
                          local_dir=db.parent)
    except Exception as e:
        print(f"no fast search index ({e!r}); using SQLite FTS5", file=sys.stderr, flush=True)


def main() -> None:
    db = ensure_db()
    ensure_search(db)
    os.environ["HUMANCORPUS_DB"] = str(db)
    import threading

    from . import fast

    threading.Thread(target=fast.engine, args=(db,), daemon=True).start()  # warm before first query
    from .web import serve

    serve(port=int(os.environ.get("PORT", 7860)))


if __name__ == "__main__":
    main()
