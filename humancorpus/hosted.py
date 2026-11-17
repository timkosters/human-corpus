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


def main() -> None:
    db = ensure_db()
    os.environ["HUMANCORPUS_DB"] = str(db)
    from .web import serve

    serve(port=int(os.environ.get("PORT", 7860)))


if __name__ == "__main__":
    main()
