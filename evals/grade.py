"""Grade without an API key: export what needs grading, let any Claude session (or a person) grade it, ingest.

  python -m evals.grade export            # unlabeled results from the latest run -> evals/grading/pending.txt
  python -m evals.grade ingest FILE       # read the graded file back into labels.jsonl
  python -m evals.grade drafts DIR        # list drafts in DIR with no .judge.json, with the rubric

pending.txt is plain text so a grader can answer inline. Each item is one line:
  <n> | <task> | <sentence>
The grader writes the answers as lines "<n>: <relevance>,<usable>" (anywhere, e.g. at the end of the file or in
a separate file). Drafts are graded by writing <draft>.judge.json with the keys in judge.DRAFT_PROMPT.
Then rerun `python -m evals.run` (results are scored from the label cache, so no new search is needed for
labels to count; rerun to refresh the scorecard).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from . import judge as J

HERE = Path(__file__).parent
GRADING = HERE / "grading"


def latest_result() -> Path:
    files = sorted((HERE / "results").glob("*.json"))
    if not files:
        raise SystemExit("no results yet; run python -m evals.run first")
    return files[-1]


def export(result: Path | None = None, grader: str = "") -> Path:
    tasks = {t["id"]: t for t in json.loads((HERE / "tasks.json").read_text())["tasks"]}
    labels = J.load_labels()
    rows = json.loads((result or latest_result()).read_text())["retrieval"]["rows"]
    todo, seen = [], set()
    for r in rows:
        k = (r["task"], r["text"])
        if k not in labels and k not in seen:
            seen.add(k)
            todo.append(r)
    GRADING.mkdir(exist_ok=True)
    out = GRADING / "pending.txt"
    lines = ["# Grade each sentence for its task's brief.",
             "# relevance: 2 = would use it as is for this brief; 1 = on topic or right tone, not quite; 0 = off.",
             "# usable: 1 = stands alone in a modern personal piece (no unexplained names, dangling he/this,",
             "#          dialogue tags, quote debris, jarring archaism unless wanted); else 0.",
             "# Answer with lines  n: relevance,usable", "#", "# Briefs:"]
    lines += [f"#   {t}: {tasks[t]['brief']}" for t in sorted({r['task'] for r in todo})]
    lines.append("")
    items = []
    for n, r in enumerate(todo):
        lines.append(f"{n} | {r['task']} | {r['query']} | {r['text']}")
        items.append({"n": n, "task": r["task"], "text": r["text"]})
    out.write_text("\n".join(lines) + "\n")
    (GRADING / "pending.json").write_text(json.dumps(items, ensure_ascii=False))
    print(f"{len(todo)} sentences to grade -> {out}")
    return out


def ingest(path: Path, by: str = "claude-in-session") -> int:
    items = {i["n"]: i for i in json.loads((GRADING / "pending.json").read_text())}
    labels = J.load_labels()
    rows = []
    for m in re.finditer(r"^\s*(\d+)\s*:\s*([0-2])\s*,\s*([01])\s*$", path.read_text(), re.M):
        it = items.get(int(m.group(1)))
        if it and (it["task"], it["text"]) not in labels:
            rows.append({"task": it["task"], "text": it["text"], "relevance": int(m.group(2)),
                         "usable": int(m.group(3)), "by": by})
            labels[(it["task"], it["text"])] = rows[-1]
    J.save_labels(rows)
    missing = len(items) - sum((i["task"], i["text"]) in labels for i in items.values())
    print(f"ingested {len(rows)} labels; {missing} still unlabeled")
    return len(rows)


def drafts(d: Path) -> None:
    tasks = {t["id"]: t for t in json.loads((HERE / "tasks.json").read_text())["tasks"]}
    print(J.DRAFT_PROMPT.split("Draft:")[0].replace("{brief}", "<brief>").replace("{mode}", "<mode>"))
    for p in sorted(d.glob("*__*.md")):
        if not p.with_suffix(".judge.json").exists():
            task, mode = p.stem.split("__")
            print(f"--- {p.name}  brief: {tasks[task]['brief']}  mode: {mode}\n{p.read_text().strip()}\n")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] not in {"export", "ingest", "drafts"}:
        print(__doc__)
        return 1
    if argv[0] == "export":
        export(Path(argv[1]) if len(argv) > 1 else None)
    elif argv[0] == "ingest":
        ingest(Path(argv[1]), *(argv[2:3]))
    else:
        drafts(Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
