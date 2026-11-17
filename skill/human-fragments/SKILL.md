---
name: human-fragments
description: Draft text assembled from verifiably human-written sentences (Wikipedia 2022 snapshot, Project Gutenberg) using the human-corpus MCP tools, then verify and cite. Use when the user wants writing that is provably human-sourced, a cento or collage of real sentences, or to check how much of a draft is human text.
---

# Human fragments

Write with sentences that real people wrote before LLMs existed. The `human-corpus` MCP server
indexes sentence fragments from pre-LLM sources and can prove, sentence by sentence, that a
draft is made of them.

## Tools (MCP server `human-corpus`)

- `search_fragments(query, limit, mode, source, min_words, max_words, phrases, register, like, style)`: find sentences.
  For personal writing use `register="intimate"`; `like="<example sentence>"` ranks by tone.
  `style=` (comma-separated): grateful, apologetic, grieving, celebratory, sensory, reflective,
  advice, casual, aphorism, archaic, question, exclamation.
  Use short idea-level queries ("grief after a long illness"), not full prose.
  `mode="phrase"` for exact wording, `mode="raw"` for FTS5 syntax (`NEAR(a b, 5)`, `pref*`).
  `phrases=true` also returns clause-sized pieces you can splice.
- `get_context(fragment_id)`: read the surrounding sentences before relying on one.
- `random_fragments(n, topic)`: for voice or inspiration.
- `verify_draft(text)`: per-sentence status `exact` / `contained` / `not_found`, plus `human_ratio`.
- `cite_sources(fragment_ids)`: attribution block.

If the MCP server is not connected, use the CLI the same way: `humancorpus search "..." --json`,
`humancorpus verify draft.txt`.

## Modes

Ask which mode the user wants if it is unclear. Default to **seeded**.

1. **Strict (cento)**: every sentence in the final text is a verbatim corpus sentence.
   - Outline the piece as a list of beats (one idea per sentence).
   - For each beat run 1 to 3 searches, read 10+ candidates, pick the one that fits voice and flow.
     Vary queries (synonyms, concrete nouns) rather than settling for a weak match.
   - Never edit a chosen sentence. Only reorder, choose, and break paragraphs.
   - Run `verify_draft` on the result. Target `human_ratio` = 1.0. Replace any `not_found` line.
2. **Seeded**: write normally, but source phrasing from the corpus.
   - Pull fragments for each section first, then draft using their wording, rhythm and
     concrete details. Prefer reusing whole clauses over paraphrasing them.
   - Run `verify_draft` and report the human ratio honestly.
3. **Check only**: run `verify_draft` on text the user provides and report which sentences
   have a human source.

## Rules

- Do not alter a sentence and still call it verified. Only `verify_draft` decides that.
- Avoid fragments that only make sense in their source (dangling "he", "this species", dates
  tied to a specific article) unless the draft supplies that context. Use `get_context` to check.
- Keep names and facts from Wikipedia sentences accurate to the new context, or skip them.
- Licensing: Wikipedia text is CC BY-SA 3.0. Any output that reuses it needs attribution and
  the same license, so always end with the `cite_sources` block when Wikipedia fragments are used.
  Gutenberg text is public domain in the US.
- Deliver: the text, then a one-line verification summary (e.g. "14/14 sentences verified
  human"), then sources.
