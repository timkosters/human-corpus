"""Upload the index as a public HF dataset and deploy the MCP server as an HF Space."""
import argparse
import os
import shutil
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent

DATASET_CARD = """---
license: cc-by-sa-3.0
language: [en]
pretty_name: Human Corpus
tags: [human-written, pre-llm, sentences, mcp, wikipedia, gutenberg]
---

# Human Corpus index

SQLite FTS5 index of verifiably human-written English sentences, built by
[human-corpus](https://github.com/timkosters/human-corpus):

- English Wikipedia, 2022-03-01 dump (before ChatGPT). CC BY-SA 3.0.
- Project Gutenberg public-domain books.

Only general-purpose sentences are kept (no digits, few proper nouns), deduplicated.
Every row links to its source document and license.

Use it via the hosted MCP server: https://{user}-human-corpus.hf.space/mcp
or download `corpus.db` and run `humancorpus --db corpus.db serve`.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="timourxyz")
    ap.add_argument("--db", type=Path, default=None)
    ap.add_argument("--name", default="human-corpus")
    ap.add_argument("--space-only", action="store_true")
    ap.add_argument("--search", type=Path, default=None,
                    help="upload a fast-search sidecar dir (from `humancorpus build-search`) as search/")
    ap.add_argument("--search-only", action="store_true", help="only upload --search, skip db and Space")
    ap.add_argument("--hardware", default=None, help="e.g. cpu-upgrade ($0.03/h); default free cpu-basic")
    a = ap.parse_args()
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_TOKEN")
    api = HfApi(token=token)
    repo = f"{a.user}/{a.name}"

    if a.search:
        api.create_repo(repo, repo_type="dataset", exist_ok=True, private=False)
        print(f"uploading fast search sidecar {a.search}")
        api.upload_folder(repo_id=repo, repo_type="dataset", folder_path=str(a.search), path_in_repo="search",
                          delete_patterns=["tantivy/*"],  # drop stale segments from earlier builds
                          commit_message="Fast search sidecar (Tantivy + 1-bit embeddings + register tags)")
        if a.search_only:
            return

    if not a.space_only:
        if a.db is None:
            ap.error("--db is required unless --space-only or --search-only")
        api.create_repo(repo, repo_type="dataset", exist_ok=True, private=False)
        api.upload_file(path_or_fileobj=DATASET_CARD.format(user=a.user).encode(), path_in_repo="README.md",
                        repo_id=repo, repo_type="dataset")
        print(f"uploading {a.db} ({a.db.stat().st_size / 1e9:.1f} GB)")
        api.upload_file(path_or_fileobj=str(a.db), path_in_repo="corpus.db", repo_id=repo, repo_type="dataset")

    api.create_repo(repo, repo_type="space", space_sdk="docker", exist_ok=True, private=False)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for item in ["humancorpus", "pyproject.toml", "LICENSE"]:
            src = ROOT / item
            (shutil.copytree if src.is_dir() else shutil.copy)(src, tmp / item)
        shutil.copy(ROOT / "space" / "Dockerfile", tmp / "Dockerfile")
        readme = (ROOT / "space" / "README.md").read_text().replace("timourxyz", a.user)
        (tmp / "README.md").write_text(readme)
        shutil.copy(ROOT / "README.md", tmp / "PROJECT_README.md")
        dockerfile = (tmp / "Dockerfile").read_text().replace("timourxyz", a.user)
        (tmp / "Dockerfile").write_text(dockerfile)
        api.upload_folder(repo_id=repo, repo_type="space", folder_path=str(tmp),
                          ignore_patterns=["__pycache__/*", "*.pyc"])
    if a.hardware:
        api.request_space_hardware(repo, a.hardware)
    print(f"dataset: https://huggingface.co/datasets/{repo}")
    print(f"space:   https://huggingface.co/spaces/{repo}")
    print(f"mcp:     https://{a.user}-{a.name}.hf.space/mcp")


if __name__ == "__main__":
    main()
