"""LLM judge (Claude) for retrieval relevance and draft quality, with a persistent label cache.

Labels live in evals/labels.jsonl, keyed by (task, text), so each sentence is judged once and
later runs are free and deterministic. Hand labels can be added to the same file.
Needs `pip install anthropic` and an API key (ANTHROPIC_API_KEY or `ant auth login`).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

HERE = Path(__file__).parent
LABELS = HERE / "labels.jsonl"
JUDGE_MODEL = os.environ.get("HC_EVAL_JUDGE_MODEL", "claude-opus-5-5")

RETRIEVAL_PROMPT = """You are grading search results for a writer who drafts ONLY by reusing verbatim human sentences.
Brief: {brief}
Search query: {query}

For each numbered sentence give:
- relevance: 2 = a writer would happily use it for this brief as is; 1 = on topic or in the right tone but needs another choice nearby; 0 = off topic or wrong tone.
- usable: 1 if the sentence stands alone in a modern personal piece (no unexplained names, no dangling "he"/"this", no dialogue tags or quote debris, not jarringly archaic unless the brief wants it), else 0.

Sentences:
{items}

Reply with only a JSON array: [{{"i": 1, "relevance": 0, "usable": 0}}, ...]"""

DRAFT_PROMPT = """You are judging a short piece of writing assembled from (or seeded by) human sentences found in old books and Wikipedia.
Brief: {brief}
Mode: {mode} (strict = every sentence is verbatim from the corpus; seeded = the writer could write freely)

Draft:
<<<
{draft}
>>>

Score 1-5 (5 best):
- fits_brief: does it do what the brief asks, for that recipient and occasion?
- coherence: do the sentences follow from each other as one piece?
- fluency: grammar, rhythm, no stitched seams or non sequiturs.
- voice: one consistent, natural modern voice (no stray period diction, names, or encyclopedia tone).
- overall: would the person actually send or say this?
Then one sentence naming the biggest weakness.

Reply with only JSON: {{"fits_brief": n, "coherence": n, "fluency": n, "voice": n, "overall": n, "weakness": "..."}}"""


def load_labels() -> dict[tuple[str, str], dict]:
    out = {}
    if LABELS.exists():
        for line in LABELS.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                out[(r["task"], r["text"])] = r
    return out


def save_labels(rows: list[dict]) -> None:
    with LABELS.open("a") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _client():
    try:
        import anthropic
    except ImportError as e:
        raise SystemExit("LLM judging needs `pip install anthropic`.") from e
    return anthropic.Anthropic()


def _ask(client, prompt: str, max_tokens: int = 4000) -> str:
    resp = client.messages.create(
        model=JUDGE_MODEL, max_tokens=max_tokens, output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("judge refused")
    return "".join(b.text for b in resp.content if b.type == "text")


def _json(text: str):
    m = re.search(r"(\[.*\]|\{.*\})", text, re.S)
    return json.loads(m.group(1) if m else text)


def judge_results(task: dict, query: str, texts: list[str]) -> list[dict]:
    """Label unseen (task, text) pairs; returns new label rows (already saved)."""
    client = _client()
    items = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
    data = _json(_ask(client, RETRIEVAL_PROMPT.format(brief=task["brief"], query=query, items=items)))
    rows = []
    for d in data:
        i = int(d["i"]) - 1
        if 0 <= i < len(texts):
            rows.append({"task": task["id"], "text": texts[i], "relevance": int(d["relevance"]),
                         "usable": int(d["usable"]), "by": JUDGE_MODEL})
    save_labels(rows)
    return rows


def judge_draft(brief: str, mode: str, draft: str) -> dict:
    client = _client()
    out = _json(_ask(client, DRAFT_PROMPT.format(brief=brief, mode=mode, draft=draft), 1000))
    out["by"] = JUDGE_MODEL
    return out
