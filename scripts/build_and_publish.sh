#!/usr/bin/env bash
# Build the full hosted index and publish it to Hugging Face.
#   HF_TOKEN=... scripts/build_and_publish.sh
# Env: HF_USER (default timourxyz), WORKERS (default nproc), GUTENBERG_SHARDS (default 4),
#      DB (default ./build/corpus.db), SKIP_BUILD=1 to only publish.
set -euo pipefail
cd "$(dirname "$0")/.."
HF_USER=${HF_USER:-timourxyz}
WORKERS=${WORKERS:-$(nproc)}
GUTENBERG_SHARDS=${GUTENBERG_SHARDS:-4}
DB=${DB:-$PWD/build/corpus.db}
export HUMANCORPUS_DELETE_DOWNLOADS=1   # keep disk use low: drop each parquet after indexing
mkdir -p "$(dirname "$DB")"

if [ -z "${SKIP_BUILD:-}" ]; then
  # Resumable: rerunning skips documents already indexed. No FTS optimize / VACUUM:
  # both need temporary space the size of the index and gain little here.
  humancorpus --db "$DB" ingest wikipedia --shards 41 --profile reusable --workers "$WORKERS" --no-optimize
  humancorpus --db "$DB" ingest gutenberg --shards "$GUTENBERG_SHARDS" --profile reusable --workers "$WORKERS" --no-optimize
  python3 -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); c.execute('PRAGMA journal_mode=DELETE')" "$DB"
fi
humancorpus --db "$DB" stats

python3 scripts/publish_hf.py --user "$HF_USER" --db "$DB"
