"""End-to-end drafting: Claude writes each brief using the MCP tools, the way a real client would.

Drafts are saved to evals/drafts/<run>/<task>__<mode>.md so they can be read, diffed and re-scored.
Needs `pip install anthropic` and an API key.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .mcp_client import MCPClient

COMPOSER_MODEL = os.environ.get("HC_EVAL_COMPOSER_MODEL", "claude-opus-5-5")
MAX_TOOL_CALLS = 30
TOOLS_USED = {"search_fragments", "get_context", "random_fragments", "verify_draft"}

INSTRUCTIONS = {
    "strict": "Mode: strict. Every sentence of the final draft must be a verbatim corpus sentence. "
              "Choose and order only. Aim for verify_draft human_ratio 1.0.",
    "seeded": "Mode: seeded. Write the piece yourself, borrowing wording and detail from fragments where it helps.",
}


def compose(client: MCPClient, task: dict, mode: str, guide: str) -> tuple[str, dict]:
    import anthropic

    api = anthropic.Anthropic()
    tools = [{"name": t["name"], "description": t.get("description", "")[:1500],
              "input_schema": t["inputSchema"]} for t in client.list_tools() if t["name"] in TOOLS_USED]
    system = (guide + "\n\n" + INSTRUCTIONS[mode] +
              "\nWhen done, reply with the final draft only, inside <draft></draft> tags. Keep it under 200 words.")
    messages = [{"role": "user", "content": f"Brief: {task['brief']}"}]
    calls = 0
    while True:
        resp = api.messages.create(model=COMPOSER_MODEL, max_tokens=16000, system=system, tools=tools,
                                   output_config={"effort": "medium"}, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text")
            m = re.search(r"<draft>(.*?)</draft>", text, re.S)
            return (m.group(1) if m else text).strip(), {"tool_calls": calls, "stop": resp.stop_reason}
        results = []
        for b in resp.content:
            if b.type != "tool_use":
                continue
            calls += 1
            try:
                if calls > MAX_TOOL_CALLS:
                    raise RuntimeError("tool budget exhausted; finish the draft now")
                out, _ = client.call(b.name, **b.input)
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": json.dumps(out, ensure_ascii=False)[:20000]})
            except Exception as e:  # report to the model, keep going
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": str(e), "is_error": True})
        messages.append({"role": "user", "content": results})


def run(client: MCPClient, tasks: list[dict], modes: list[str], out_dir: Path) -> None:
    from humancorpus import guide

    out_dir.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        for mode in modes:
            path = out_dir / f"{task['id']}__{mode}.md"
            if path.exists():
                continue
            draft, meta = compose(client, task, mode, guide.GUIDE)
            path.write_text(draft + "\n")
            (out_dir / f"{task['id']}__{mode}.meta.json").write_text(json.dumps(meta))
            print(f"  composed {path.name} ({meta['tool_calls']} tool calls)")
