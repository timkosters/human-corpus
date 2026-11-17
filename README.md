# human-corpus

A local, searchable corpus of **verifiably human-written sentences**, exposed to Claude as an
MCP server and a skill. Claude can pull real sentences and phrases while drafting, then prove
which sentences of the result are verbatim human text.

## Why these sources

| Source | Snapshot | Why it is human | License |
|---|---|---|---|
| English Wikipedia | 2022-03-01 dump | Frozen 8 months before ChatGPT (2022-11-30) | CC BY-SA 3.0, attribution required |
| Project Gutenberg | English books | Public-domain works, almost all pre-1930 | Public domain (US) |

Both are pulled as Parquet from Hugging Face (`legacy-datasets/wikipedia`, `manu/project_gutenberg`).
Adding a source is one class in `humancorpus/sources.py`.

## How it works

- **Fragments**: each document is split into sentences. Headings, lists, tables, citations and
  markup debris are filtered out. Exact duplicates are removed by a normalized hash.
- **Index**: SQLite FTS5 with BM25 ranking and Porter stemming. One file, no server, fast.
- **Semantic rerank (optional)**: with `model2vec` installed, the top BM25 hits are reranked by
  meaning using a 8M-parameter static embedding model. It adds a few ms per query and needs no
  stored vectors.
- **Phrases**: search can also return clause-sized pieces of each hit for splicing.
- **Verify**: any draft can be checked sentence by sentence: `exact` (a human sentence),
  `contained` (verbatim inside a human sentence) or `not_found`.
- **Fast hybrid search (optional sidecar)**: `humancorpus build-search` derives a `search/` folder
  next to `corpus.db`: a Tantivy BM25 index, 1-bit embeddings (32 bytes per sentence) and a
  register tag per sentence. Queries then combine keyword and meaning candidates, re-embed them
  exactly, and diversify with MMR. Tantivy stops early on common words, so keyword search stays
  in milliseconds at 100M sentences where SQLite FTS5 slows to seconds. Install with
  `pip install -e ".[fast]"`. Without the sidecar, SQLite FTS5 is used.
- **Style**: `register="intimate"` (first or second person, with feeling) finds sentences that
  fit a love letter rather than encyclopedia lines about love; `like="<example>"` ranks by tone.

## Quick start

```bash
pip install -e ".[semantic]"     # or: pip install -e .  (BM25 only)

humancorpus ingest wikipedia --shards 1     # ~157k articles, see sizes below
humancorpus ingest gutenberg --shards 1     # ~1.2k books

humancorpus search "the river flooded the valley in spring"
humancorpus search "loneliness" --source gutenberg --phrases
echo "Your draft here. Another sentence." | humancorpus verify
```

The database lives at `~/.cache/humancorpus/corpus.db` (override with `--db` or `HUMANCORPUS_DB`).

## Hosted public MCP (Hugging Face)

The public server runs as a Hugging Face Space and serves MCP over HTTP:

```bash
claude mcp add --transport http human-corpus https://timourxyz-human-corpus.hf.space/mcp
```

- The index is a public HF dataset (`timourxyz/human-corpus`), downloaded by the Space at boot.
- The server only runs searches. It never calls an AI model, so callers' drafting uses their own
  model, and hosting cost is flat (free CPU tier, or $0.03/h CPU upgrade to avoid sleeping).
- Per-IP rate limit (default 60 req/min, burst 30) via `HUMANCORPUS_RATE_PER_MIN` / `HUMANCORPUS_BURST`.
- The hosted index uses `--profile reusable`: general-purpose sentences only (no digits, few
  proper nouns). That keeps about 40% of sentences, the ones useful for drafting.

Rebuild and redeploy: `HF_TOKEN=... scripts/build_and_publish.sh` (about 3 hours on 4 cores).
Run your own: `humancorpus serve --http --port 7860`.

## Use it from Claude (local)

**MCP server** (Claude Code):

```bash
claude mcp add human-corpus -- humancorpus serve
```

Claude Desktop (`claude_desktop_config.json`):

```json
{ "mcpServers": { "human-corpus": { "command": "humancorpus", "args": ["serve"] } } }
```

Tools: `search_fragments`, `get_context`, `random_fragments`, `verify_draft`, `cite_sources`,
`corpus_stats`.

**Skill**: copy `skill/human-fragments/` into `~/.claude/skills/` (or upload it in claude.ai).
It teaches Claude three modes:

- **Strict (cento)**: every sentence is a verbatim corpus sentence, verified at 100%.
- **Seeded**: normal drafting that borrows wording and clauses from fragments, with the human
  ratio reported.
- **Check only**: verify someone else's text.

## Sizes and scaling

Measured on one cloud CPU core:

| Corpus | Docs | Sentences | DB size | Ingest time |
|---|---|---|---|---|
| Wikipedia shard 1 of 41 | 150k articles | 11.1M | 3.4 GB | ~12 min |
| All of English Wikipedia (estimate) | 6.5M articles | ~150M | ~45 GB | ~8 h single core |

Queries over the 11M-sentence index return in well under a second.

Scaling path:

- **More shards**: `--shards 41` indexes all of English Wikipedia (expect tens of GB and hours
  of CPU). Ingest is resumable: documents already in the DB are skipped.
- **Parallel ingest**: run one process per shard into separate DBs, then attach and merge.
- **More sources**: other pre-2022, permissively licensed text, e.g. Wikisource, Wikinews and
  Wikibooks dumps before 2022, the Gutenberg-derived PG-19 set, public-domain government
  documents. Avoid web crawls after 2022, which contain LLM text.
- **Stored vectors**: for pure semantic search over everything, add `sqlite-vec` with int8
  embeddings. The rerank-only approach here covers most drafting needs without the storage cost.

## Caveats

- "Human-written" means "existed before LLM text was common". Wikipedia 2022 still contains
  older machine-assisted edits (bots, templates), but no LLM prose.
- Reusing Wikipedia sentences creates a CC BY-SA derivative. Keep the `cite_sources` block.
- Sentence splitting is regex based, so a small share of fragments are cut oddly.

## License

Code: MIT. Corpus text keeps its source license (see above).
