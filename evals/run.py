"""Run the eval suite and print a scorecard, with deltas against a saved baseline.

  python -m evals.run                         # retrieval + service metrics vs the live server
  python -m evals.run --server http://127.0.0.1:7860/mcp   # a local server (humancorpus serve --http)
  python -m evals.run --judge                 # label unseen results with Claude via the API (cached in labels.jsonl)
  python -m evals.grade export                # no API key: export unseen results for an in-session Claude to grade
  python -m evals.run --drafts evals/drafts/baseline       # score saved drafts (verify + judge)
  python -m evals.run --compose               # Claude writes fresh drafts via the MCP tools, then scores them
  python -m evals.run --save-baseline         # make this run the new baseline

Output: evals/results/<timestamp>.json and .md; the scorecard is also printed.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

from . import heuristics as H
from .mcp_client import MCPClient

HERE = Path(__file__).parent
LIVE = "https://timourxyz-human-corpus.hf.space/mcp"
LIMIT = 10


def pct(xs: list[float], p: float) -> float:
    if not xs:
        return float("nan")
    xs = sorted(xs)
    k = min(len(xs) - 1, max(0, round(p / 100 * (len(xs) - 1))))
    return xs[k]


def mean(xs) -> float:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


def retrieval(client: MCPClient, tasks: list[dict], judge: bool) -> dict:
    from . import judge as J

    labels = J.load_labels()
    nonce = " " * (1 + int(time.time()) % 97)  # trailing spaces: same search, new cache key -> a cold call
    per_task, rows, cold, warm, errors = [], [], [], [], []
    for task in tasks:
        tq = []
        for q in task["queries"]:
            args = {k: q.get(k) for k in ("register", "style", "like", "source")}
            try:
                res, dt_cold = client.call("search_fragments", query=q["query"] + nonce, limit=LIMIT, **args)
                _, dt_warm = client.call("search_fragments", query=q["query"] + nonce, limit=LIMIT, **args)
            except Exception as e:
                errors.append(f"{task['id']}: {q['query']}: {e}")
                tq.append({"query": q["query"], "error": str(e)})
                continue
            cold.append(dt_cold)
            warm.append(dt_warm)
            texts = [r["text"] for r in res]
            if judge:
                new = [t for t in dict.fromkeys(texts) if (task["id"], t) not in labels]
                if new:
                    for r in J.judge_results(task, q["query"], new):
                        labels[(r["task"], r["text"])] = r
            tags = H.expected_tags(q)
            allow_archaic = "archaic" in tags
            res_rows = []
            for rank, r in enumerate(res, 1):
                lab = labels.get((task["id"], r["text"]))
                fl = H.flags(r["text"], allow_archaic)
                row = {"task": task["id"], "query": q["query"], "rank": rank, "id": r["id"], "text": r["text"],
                       "source": r["source"], "register": r.get("register"), "styles": r.get("styles", []),
                       "flags": fl, "tag_ok": all(H.has_tag(r, t) for t in tags) if tags else None,
                       "relevance": lab["relevance"] if lab else None, "usable": lab["usable"] if lab else None}
                res_rows.append(row)
            rows += res_rows
            labeled = [x for x in res_rows if x["relevance"] is not None]
            tq.append({
                "query": q["query"], "n": len(res), "cold_s": round(dt_cold, 3), "warm_s": round(dt_warm, 3),
                "tag_precision": mean([x["tag_ok"] for x in res_rows]) if tags else None,
                "clean_rate": mean([not x["flags"] for x in res_rows]),
                "dup_rate": H.near_dup_rate(texts),
                "relevant_at_10": mean([x["relevance"] >= 1 for x in labeled]) if labeled else None,
                "good_at_10": mean([x["relevance"] == 2 and x["usable"] == 1 for x in labeled]) if labeled else None,
                "hit_good_at_5": (any(x["relevance"] == 2 and x["usable"] == 1 for x in labeled if x["rank"] <= 5)
                                  if labeled else None),
                "label_coverage": len(labeled) / len(res_rows) if res_rows else 0,
            })
        per_task.append({"task": task["id"], "queries": tq})

    allq = [q for t in per_task for q in t["queries"] if "error" not in q]
    flag_counts = Counter(f for r in rows for f in r["flags"])
    src = Counter(r["source"] for r in rows)

    def agg(key):
        return mean([q[key] for q in allq if q.get(key) is not None])

    summary = {
        "queries": len(allq), "errors": len(errors), "results": len(rows),
        "empty_queries": sum(q["n"] == 0 for q in allq),
        "latency_cold_p50_s": pct(cold, 50), "latency_cold_p95_s": pct(cold, 95), "latency_cold_max_s": max(cold or [0]),
        "latency_warm_p50_s": pct(warm, 50),
        "tag_precision": agg("tag_precision"), "clean_rate": agg("clean_rate"), "dup_rate": agg("dup_rate"),
        "relevant_at_10": agg("relevant_at_10"), "good_at_10": agg("good_at_10"),
        "hit_good_at_5": agg("hit_good_at_5"), "label_coverage": agg("label_coverage"),
        "gutenberg_share": src.get("gutenberg", 0) / max(1, len(rows)),
        "flag_rates": {k: v / max(1, len(rows)) for k, v in flag_counts.most_common()},
    }
    return {"summary": summary, "per_task": per_task, "rows": rows, "errors": errors}


def drafts(client: MCPClient, tasks: dict, draft_dir: Path, judge: bool) -> dict:
    from . import judge as J

    out = []
    vt = []
    for path in sorted(draft_dir.glob("*__*.md")):
        task_id, mode = path.stem.split("__")
        if task_id not in tasks:
            continue
        text = path.read_text().strip()
        try:
            v, dt = client.call("verify_draft", text=text)
        except Exception as e:
            out.append({"task": task_id, "mode": mode, "error": str(e)})
            continue
        if isinstance(v, list):
            v = v[0]
        vt.append(dt)
        jpath = path.with_suffix(".judge.json")
        scores = json.loads(jpath.read_text()) if jpath.exists() else None
        if scores is None and judge:
            scores = J.judge_draft(tasks[task_id]["brief"], mode, text)
            jpath.write_text(json.dumps(scores, indent=1))
        out.append({"task": task_id, "mode": mode, "words": len(text.split()), "human_ratio": v["human_ratio"],
                    "sentences": v["sentences"], "verify_s": round(dt, 2), "judge": scores})
    summary = {"drafts": len(out), "verify_p50_s": pct(vt, 50), "verify_max_s": max(vt or [0])}
    for mode in ("strict", "seeded"):
        ds = [d for d in out if d.get("mode") == mode and "error" not in d]
        if not ds:
            continue
        summary[f"{mode}_human_ratio"] = mean([d["human_ratio"] for d in ds])
        for k in ("fits_brief", "coherence", "fluency", "voice", "overall"):
            summary[f"{mode}_{k}"] = mean([d["judge"][k] for d in ds if d["judge"]])
    return {"summary": summary, "drafts": out}


# ---------- scorecard ----------

LOWER_IS_BETTER = ("latency", "dup_rate", "errors", "empty", "verify_p50", "verify_max")


def fmt(v) -> str:
    if v is None or (isinstance(v, float) and v != v):
        return "n/a"
    if isinstance(v, float):
        return f"{v:.3f}" if abs(v) < 10 else f"{v:.1f}"
    return str(v)


def delta(k: str, v, b) -> str:
    if not isinstance(v, (int, float)) or not isinstance(b, (int, float)) or v != v or b != b:
        return ""
    d = v - b
    if abs(d) < 1e-9:
        return "="
    better = (d < 0) if any(s in k for s in LOWER_IS_BETTER) else (d > 0)
    return f"{'+' if d > 0 else ''}{d:.3f} ({'better' if better else 'worse'})"


def scorecard(result: dict, base: dict | None) -> str:
    lines = [f"# Human corpus eval  {result['meta']['when']}", "",
             f"Server: {result['meta']['server']}  Tasks: v{result['meta']['tasks_version']}",
             f"Baseline: {base['meta']['when'] if base else 'none'}", ""]
    for section in ("retrieval", "drafts"):
        if section not in result:
            continue
        lines += [f"## {section.title()}", "", "| metric | value | vs baseline |", "|---|---|---|"]
        bsum = (base or {}).get(section, {}).get("summary", {})
        for k, v in result[section]["summary"].items():
            if isinstance(v, dict):
                v = ", ".join(f"{a} {b:.3f}" for a, b in list(v.items())[:8])
                lines.append(f"| {k} | {v} | |")
            else:
                lines.append(f"| {k} | {fmt(v)} | {delta(k, v, bsum.get(k))} |")
        lines.append("")
    if "retrieval" in result:
        lines += ["## Per task (retrieval)", "", "| task | tag precision | clean | relevant@10 | good@10 | cold s |",
                  "|---|---|---|---|---|---|"]
        for t in result["retrieval"]["per_task"]:
            qs = [q for q in t["queries"] if "error" not in q]
            lines.append(f"| {t['task']} | {fmt(mean([q['tag_precision'] for q in qs]))} | "
                         f"{fmt(mean([q['clean_rate'] for q in qs]))} | {fmt(mean([q['relevant_at_10'] for q in qs]))} | "
                         f"{fmt(mean([q['good_at_10'] for q in qs]))} | {fmt(max([q['cold_s'] for q in qs] or [0]))} |")
        lines.append("")
        if result["retrieval"]["errors"]:
            lines += ["Errors:", *[f"- {e}" for e in result["retrieval"]["errors"]], ""]
    if "drafts" in result:
        lines += ["## Drafts", "", "| task | mode | human_ratio | overall | weakness |", "|---|---|---|---|---|"]
        for d in result["drafts"]["drafts"]:
            j = d.get("judge") or {}
            lines.append(f"| {d['task']} | {d['mode']} | {fmt(d.get('human_ratio'))} | {fmt(j.get('overall'))} | "
                         f"{j.get('weakness', d.get('error', ''))} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", default=LIVE)
    ap.add_argument("--tasks", default=str(HERE / "tasks.json"))
    ap.add_argument("--only", help="comma-separated task ids")
    ap.add_argument("--judge", action="store_true", help="LLM-judge unseen results and unscored drafts")
    ap.add_argument("--drafts", help="directory of saved drafts to score")
    ap.add_argument("--compose", action="store_true", help="have Claude write drafts first (implies --drafts)")
    ap.add_argument("--modes", default="strict,seeded")
    ap.add_argument("--no-retrieval", action="store_true")
    ap.add_argument("--baseline", default=str(HERE / "baseline.json"))
    ap.add_argument("--save-baseline", action="store_true")
    ap.add_argument("--timeout", type=float, default=90)
    a = ap.parse_args(argv)

    spec = json.loads(Path(a.tasks).read_text())
    tasks = spec["tasks"]
    if a.only:
        keep = set(a.only.split(","))
        tasks = [t for t in tasks if t["id"] in keep]
    when = time.strftime("%Y-%m-%dT%H-%M-%S")
    t0 = time.perf_counter()
    client = MCPClient(a.server, timeout=a.timeout)
    result: dict = {"meta": {"when": when, "server": a.server, "tasks_version": spec["version"],
                             "first_call_s": round(time.perf_counter() - t0, 2)}}
    if not a.no_retrieval:
        print(f"retrieval: {sum(len(t['queries']) for t in tasks)} queries ...", file=sys.stderr)
        result["retrieval"] = retrieval(client, tasks, a.judge)
    draft_dir = Path(a.drafts) if a.drafts else None
    if a.compose:
        from . import compose
        draft_dir = draft_dir or HERE / "drafts" / when
        compose.run(client, tasks, a.modes.split(","), draft_dir)
    if draft_dir:
        print(f"drafts: scoring {draft_dir} ...", file=sys.stderr)
        result["drafts"] = drafts(client, {t["id"]: t for t in tasks}, draft_dir, a.judge or a.compose)
    result["meta"]["wall_s"] = round(time.perf_counter() - t0, 1)
    if "retrieval" in result and result["retrieval"]["summary"]["label_coverage"] < 1 and not a.judge:
        print("some results are unlabeled: `python -m evals.grade export`, grade, `python -m evals.grade ingest FILE`,"
              " then rerun", file=sys.stderr)

    base_path = Path(a.baseline)
    base = json.loads(base_path.read_text()) if base_path.exists() else None
    if base and base["meta"].get("tasks_version") != spec["version"]:
        print("baseline uses another tasks version; deltas not comparable", file=sys.stderr)
        base = None
    card = scorecard(result, base)
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / f"{when}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    (out / f"{when}.md").write_text(card)
    if a.save_baseline:
        slim = {k: ({"summary": v["summary"]} if isinstance(v, dict) and "summary" in v else v)
                for k, v in result.items()}
        base_path.write_text(json.dumps(slim, indent=1))
        print(f"saved baseline -> {base_path}", file=sys.stderr)
    print(card)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
