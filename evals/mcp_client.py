"""Minimal MCP-over-HTTP client (stdlib only) with timing, timeouts and retries."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

PROTOCOL = "2025-06-18"


class MCPError(RuntimeError):
    pass


class MCPClient:
    def __init__(self, url: str, timeout: float = 60.0, retries: int = 2):
        self.url, self.timeout, self.retries = url, timeout, retries
        self.session: str | None = None
        self._id = 0
        self.initialize()

    def _post(self, payload: dict, timeout: float | None = None) -> dict | None:
        headers = {"content-type": "application/json", "accept": "application/json, text/event-stream",
                   "mcp-protocol-version": PROTOCOL, "user-agent": "humancorpus-eval/0.1"}
        if self.session:
            headers["mcp-session-id"] = self.session
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
            self.session = r.headers.get("mcp-session-id") or self.session
            body = r.read().decode()
            if not body.strip():
                return None
            if "text/event-stream" in (r.headers.get("content-type") or ""):
                data = [ln[5:].strip() for ln in body.splitlines() if ln.startswith("data:")]
                msgs = [json.loads(d) for d in data if d]
                return next((m for m in msgs if "id" in m), msgs[-1] if msgs else None)
            return json.loads(body)

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                resp = self._post(payload)
                if resp is None:
                    raise MCPError("empty response")
                if "error" in resp:
                    raise MCPError(str(resp["error"]))
                return resp["result"]
            except urllib.error.HTTPError as e:  # 429 / 5xx retry, else fail
                last = e
                if e.code not in (429, 500, 502, 503, 504):
                    raise
                time.sleep(2 ** attempt * (5 if e.code == 429 else 1))
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last = e
                time.sleep(2 ** attempt)
        raise MCPError(f"{method} failed after retries: {last!r}")

    def initialize(self) -> dict:
        res = self._rpc("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                       "clientInfo": {"name": "humancorpus-eval", "version": "0.1"}})
        try:
            self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        except Exception:
            pass
        return res

    def list_tools(self) -> list[dict]:
        return self._rpc("tools/list")["tools"]

    def call(self, name: str, **arguments) -> tuple[object, float]:
        """Call a tool. Returns (structured result, elapsed seconds)."""
        args = {k: v for k, v in arguments.items() if v is not None}
        t = time.perf_counter()
        res = self._rpc("tools/call", {"name": name, "arguments": args})
        dt = time.perf_counter() - t
        if res.get("isError"):
            raise MCPError(" ".join(c.get("text", "") for c in res.get("content", [])))
        sc = res.get("structuredContent")
        if sc is not None:
            return (sc["result"] if set(sc) == {"result"} else sc), dt
        texts = [c.get("text", "") for c in res.get("content", []) if c.get("type") == "text"]
        try:
            parsed = [json.loads(t) for t in texts]
            return (parsed[0] if len(parsed) == 1 else parsed), dt
        except json.JSONDecodeError:
            return "\n".join(texts), dt
