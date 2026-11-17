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

## Use it from Claude

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
