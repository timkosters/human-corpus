"""How an AI model should use the corpus. Served as MCP instructions, a prompt, and a resource."""

SHORT = (
    "human-corpus: search millions of verifiably human-written sentences (English Wikipedia "
    "2022-03-01, before ChatGPT; Project Gutenberg public-domain books) and assemble drafts from "
    "them. Workflow: outline beats, call search_fragments per beat with short idea-level queries, "
    "pick sentences that stand alone, check them with get_context when unsure, assemble, then run "
    "verify_draft and end with cite_sources. Never edit a sentence and still call it verified. "
    "Read the resource guide://compose for the full method."
)

GUIDE = """\
# Composing with human fragments

You are drafting with sentences that real people wrote before LLM text existed.
Every result from this server is a verbatim human sentence with its source.

## Modes
1. Strict (cento): every sentence of the output is a verbatim corpus sentence.
   Only choose, order and paragraph them. Target verify_draft human_ratio = 1.0.
2. Seeded (default): write the piece yourself, but take wording, clauses, rhythm and concrete
   detail from fragments. Report the human_ratio honestly.
3. Check: run verify_draft on text the user supplies and report per sentence.

## Method
1. Outline the piece as beats, one idea per sentence.
2. For each beat, call search_fragments with a SHORT query of the idea's key words
   ("grief after long illness", "storm arriving over the harbour"). Run 2 or 3 variants with
   synonyms and concrete nouns. Ask for limit 15 to 25 and pick the best, not the first.
3. Prefer sentences that stand alone: few proper names, no dates, no dangling "he" or "this".
   Use phrases=true when you need clause-sized pieces. Use get_context when unsure.
4. Mix sources for texture: gutenberg for narrative and emotion, wikipedia for plain
   explanation. Use source= to target one.
5. Assemble. Fix flow by reordering and choosing other sentences, never by editing (strict mode).
6. Call verify_draft on the final text. Replace anything not_found (strict mode).
7. Call cite_sources with the fragment ids you used and append its output.

## Matching tone, not just topic
- Personal writing (love letters, apologies, thank-you notes, toasts): pass register="intimate"
  so results are first or second person with feeling, instead of encyclopedia lines that
  merely mention the topic. register="personal" (speaks to "you"), "dialogue" and "narrative"
  also work. Each result carries its register.
- style= narrows further, comma-separated, all must match: grateful (thank-you notes), apologetic,
  grieving (condolences), celebratory (toasts, congratulations), sensory (vivid description),
  reflective (looking back on life), advice (instructions, encouragement), casual (spoken voice,
  contractions), aphorism (short general truths), archaic (thee/thou), question, exclamation.
  Examples: a toast -> style="celebratory"; a condolence card -> style="grieving";
  a wedding speech -> style="aphorism" for the closing line.
- Pass like="<a sentence in the voice you want>" to rank by closeness to that example as well.
- Query by feeling and situation ("miss you mornings", "proud of you"), not by genre labels
  ("love letter").

## Query tips
- mode="phrase" finds an exact word sequence. mode="raw" accepts FTS5 syntax:
  NEAR(dark harbour, 5), lone*, rain NOT forecast.
- min_words / max_words shape rhythm: 6 to 14 for punchy lines, 20 to 40 for long ones.
- random_fragments(topic=...) is good for finding a voice before drafting.

## Licensing
Wikipedia text is CC BY-SA 3.0: output that reuses it must credit the sources and carry the
same license. Gutenberg text is public domain in the US. Always include the cite_sources block.
"""
