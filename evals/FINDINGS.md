# Baseline findings (2026-11-17, live HF Space, tasks v1)

## Scorecard

| Metric | Baseline |
|---|---|
| Search latency, first ever call (p50 / p95) | 0.73 s / 1.0 s |
| Search latency, uncached query on warm disk (p50 / p95) | 0.16 s / 0.20 s |
| Search latency, cached (p50) | 0.12 s |
| verify_draft, strict drafts (all sentences found) | 0.2 to 1.7 s |
| verify_draft, seeded drafts (mostly new sentences) | 3 to 21 s, about 5 s per new sentence |
| Errors / empty results | 0 / 0 of 36 queries |
| Tag precision (filter compliance) | 1.00 |
| Clean rate (sentence needs no edits) | 0.46 |
| Relevant@10 (on topic or right tone) | 0.33 |
| Good@10 (use as is) | 0.07 |
| Queries with a use-as-is sentence in the top 5 | 0.47 |
| Strict drafts: human_ratio / overall quality | 1.00 / 2.0 of 5 |
| Seeded drafts: human_ratio / overall quality | 0.16 / 4.5 of 5 |

Best tasks: nature description (good@10 0.27), love letter (0.17). Worst: birthday toast, retirement card,
eulogy (0.00), cover letter (relevant@10 0.10).

## Weaknesses, most costly first

1. **verify_draft is slow on new sentences.** A miss on the exact hash falls back to an FTS5 phrase query over
   41.8M rows on a disk-bound host: about 5 s per sentence, 21 s for a 4-sentence seeded toast. This is the likely
   cause of the interrupted call. Strict drafts verify in under 2 s.
2. **Quote debris on 31% of results.** Wikipedia quotes end in `."` and Gutenberg dialogue keeps open or close
   marks (`And I will miss you every day."`). Another 6% are whole quotations. All need editing before reuse.
3. **Keyword echo beats meaning.** Short idea queries match on one surface word: "love is patient" returns
   hospital patients, "her kitchen was always full" returns sentences about "always", "I am writing to apply for
   the position" returns "I am writing a letter now", "the years have been kind" returns "you have been kind".
4. **Wikipedia plot summaries pass the personal filters.** Lines like "Cameron tells her that she is sorry for her
   loss" or "Simmons was deeply disappointed by his loss" are tagged personal/grieving. Proper names appear in 16%
   of results, dangling he/she/this starts in 7%.
5. **Style tags are noisy.** grieving matches "his loss was due to redistricting"; celebratory matches album
   reviews ("Well done Steven..."); aphorism matches "There is no single point of failure". Tag precision is 1.0
   only because it measures that the filter was applied.
6. **Modern, specific situations have little to draw on.** The dog, the hospital, the bar exam, a museum job,
   "your side of the bed is empty" return nothing usable. Strict mode can only say generic things.
7. **Strict vs seeded gap.** Strict drafts are 100% human but score 2.0/5 (period diction, no specifics, seams).
   Seeded drafts score 4.5/5 but are only 16% human by sentence count.

## Suggested improvements, in order

1. Verify via the Tantivy sidecar: exact hash first, then a Tantivy phrase query (milliseconds) instead of FTS5.
   Target: verify_max_s under 1 s.
2. Clean text at query time: strip unbalanced and wrapping quote marks, and return `text` cleaned plus
   `raw_text`. verify_draft already matches cleaned text as `contained`, so provenance is kept.
   Expected: clean_rate +0.3.
3. A `standalone=true` default for personal registers: down-rank or drop sentences with proper names, dangling
   pronoun starts, and dialogue tags (`evals/heuristics.py` already finds them with 99% recall).
4. Weight the dense score higher for short idea queries, and drop results whose only BM25 overlap is one
   high-frequency word. Watch relevant_at_10 on wedding_speech, eulogy, cover_letter.
5. Tighten the register tagger: ignore pronouns inside reported speech in Wikipedia, and require a pronoun of
   address (you/your) or first person outside quotes for intimate/personal.
6. Report a word-level human ratio (share of words inside verified spans) alongside the sentence ratio, so
   seeded drafts that splice clauses get credit, and add phrase-level splicing to the guide.
7. Add sources of plain modern personal prose from before 2022 with clear licenses (for example public-domain
   letter collections on Wikisource) to cover toasts, cards and cover letters.
