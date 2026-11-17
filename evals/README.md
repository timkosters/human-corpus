# Eval suite

One command scores the MCP server on real drafting tasks and diffs against a saved baseline.

```bash
python -m evals.run                                  # live server, retrieval + service metrics (~1 min, no API key)
python -m evals.run --drafts evals/drafts/baseline   # also score saved drafts (verify_draft + cached judge scores)
python -m evals.run --server http://127.0.0.1:7860/mcp   # a local `humancorpus serve --http`
python -m evals.run --judge                          # Claude labels results it has not seen (pip install -e ".[eval]")
python -m evals.run --compose --only love_letter     # Claude drafts via the MCP tools, then judge scores it
python -m evals.run --save-baseline                  # accept this run as the new baseline
```

Each run writes `evals/results/<time>.json` (every result row with flags and labels) and a `.md` scorecard,
and prints the scorecard with `vs baseline` deltas marked better or worse.

## What it measures

| Area | Metric | How |
|---|---|---|
| Service | latency cold p50/p95/max, warm p50, errors | each query twice; trailing-space nonce forces a cache miss |
| Service | verify_p50_s / verify_max_s | `verify_draft` on every saved draft |
| Retrieval | tag_precision | results carry the register/style asked for (filter compliance, not tag accuracy) |
| Retrieval | clean_rate, flag_rates | model-free checks in `heuristics.py`: quote debris, names, dangling "he/this", dialogue tags, archaic, markup. 81% precision, 99% recall against hand labels |
| Retrieval | relevant_at_10, good_at_10, hit_good_at_5 | labels in `labels.jsonl` (relevance 0-2, usable 0/1 per task + sentence). good = relevance 2 and usable |
| Retrieval | dup_rate, gutenberg_share | near duplicates (token Jaccard >= 0.8), source mix |
| Drafts | human_ratio per mode | `verify_draft` |
| Drafts | fits_brief, coherence, fluency, voice, overall (1-5) | judge rubric in `judge.py`, cached next to each draft as `.judge.json` |

## Files

- `tasks.json`: 12 briefs (love letter, thank-you, condolence, toast, wedding speech, apology, cover letter,
  retirement, eulogy, new baby, nature description, encouragement), 3 queries each, written the way
  `guide://compose` tells a model to query. Bump `version` when you change queries; baselines from another
  version are not compared.
- `labels.jsonl`: 360 hand labels from the baseline run. New results are unlabeled until you run `--judge`
  (Claude, default `claude-opus-5-5`, override with `HC_EVAL_JUDGE_MODEL`), or add rows by hand.
  `label_coverage` shows how much of a run the labels cover; relevance metrics are over labeled rows only.
- `drafts/baseline/`: 8 drafts (4 briefs x strict/seeded) written by hand in a thread with the live MCP, plus judge scores.
- `baseline.json`: summary metrics the next run is compared against.

## Iterating

1. Change ranking, filters or tagging; run the server locally.
2. `python -m evals.run --server http://127.0.0.1:7860/mcp --judge` (labels only the new sentences).
3. Read the scorecard deltas, and `results/<time>.json` rows for the failures behind them.
4. `--save-baseline` when it is better.
