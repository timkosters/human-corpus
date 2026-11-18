# Round 1 fixes (2026-11-18): before and after

Same index as the live Space (downloaded locally), same 36 queries, every result graded by Claude in the
project thread (no API key). 308 extra sentences were graded for the new results.

| Metric | Before | After |
|---|---|---|
| Usable@10 (stands alone, graded) | 0.38 | 0.67 |
| Relevant@10 | 0.33 | 0.44 |
| Good@10 (use as is) | 0.07 | 0.14 |
| Queries with a use-as-is sentence in the top 5 | 0.47 | 0.58 |
| Clean rate (heuristic) | 0.46 | 0.90 |
| verify_draft per draft, local (max) | 2.8 s | 0.04 s |
| Search, uncached, local (p50) | 0.09 s | 0.13 s (reranker) |
| Strict drafts, overall quality (4 briefs) | 2.0 / 5 | 3.5 / 5 |

What changed, with each step's effect on graded results:

1. **verify_draft via Tantivy** instead of an FTS5 phrase scan: 10x to 70x faster, identical verdicts on all 8 drafts.
2. **Strip quote debris** from returned text (`original` keeps the stored sentence; verify still matches):
   usable 0.38 to 0.52, hit@5 0.47 to 0.53.
3. **Standalone ranking**: penalty for names, dangling he/this, dialogue tags; personal briefs prefer
   first/second-person sentences over narration (`standalone=false` turns it off): usable 0.52 to 0.61,
   relevant 0.33 to 0.38.
4. **MiniLM reranker** (int8 ONNX, 23 MB) on the top 40 candidates, so word order counts
   ("love is patient" no longer returns hospital patients): relevant 0.38 to 0.44, good 0.12 to 0.14,
   hit@5 0.50 to 0.58. Cost: about 90 ms per uncached search locally, likely 150 to 250 ms on the Space.
5. **Guide**: tells models to put the brief's concrete details in queries. The better strict drafts owe
   part of their gain to this: "taking good care of my dog" was findable before too (rank 3 on the live server).

Per task (relevant@10 / good@10, before to after):

| Task | Relevant before | after | Good before | after |
|---|---|---|---|---|
| love_letter | 0.53 | 0.57 | 0.17 | 0.30 |
| thank_you_note | 0.50 | 0.57 | 0.03 | 0.27 |
| condolence | 0.23 | 0.30 | 0.07 | 0.13 |
| birthday_toast | 0.37 | 0.57 | 0.00 | 0.10 |
| wedding_speech | 0.23 | 0.47 | 0.07 | 0.10 |
| apology | 0.47 | 0.63 | 0.10 | 0.17 |
| cover_letter | 0.10 | 0.27 | 0.03 | 0.03 |
| retirement_card | 0.13 | 0.37 | 0.00 | 0.07 |
| eulogy | 0.33 | 0.33 | 0.00 | 0.00 |
| congratulations_baby | 0.20 | 0.10 | 0.03 | 0.03 |
| nature_description | 0.57 | 0.77 | 0.27 | 0.33 |
| encouragement | 0.23 | 0.30 | 0.07 | 0.13 |

Still weak: eulogy, new-baby card and cover letter. Their hard style filters (reflective, aphorism,
celebratory) leave a pool with nothing on topic. Next step: treat style as a soft boost when the filtered
pool scores low, and fix sentence-initial names ("Michelle films her boyfriend...") that the name check misses.

Grading caveat: one grader (Claude in this thread) labeled both runs; labels are in `labels.jsonl` with `by`.

---

# Baseline findings (round 0) (2026-11-17, live HF Space, tasks v1)

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
