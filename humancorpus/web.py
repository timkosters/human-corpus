"""Hosted mode: MCP over streamable HTTP at /mcp, with per-IP rate limits and a landing page.

Run:  humancorpus serve --http --port 7860
"""
from __future__ import annotations

import inspect
import ipaddress
import os
import time
from collections import defaultdict

from . import guide
from .server import mcp

RATE = int(os.environ.get("HUMANCORPUS_RATE_PER_MIN", "60"))  # requests per IP per minute
BURST = int(os.environ.get("HUMANCORPUS_BURST", "30"))

LANDING = """<!doctype html><html><head><meta charset="utf-8"><title>Human Corpus</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font:16px/1.55 system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;color:#222}}
code,pre{{background:#f3f3f1;padding:2px 5px;border-radius:4px}}pre{{padding:12px;overflow:auto}}</style></head>
<body><h1>Human Corpus</h1>
<p>A free public MCP server of verifiably human-written sentences: English Wikipedia as of
2022-03-01 (before ChatGPT) and Project Gutenberg public-domain books. AI models search it,
assemble drafts from real sentences, and verify them sentence by sentence.</p>
<h3>Connect</h3>
<pre>claude mcp add --transport http human-corpus {url}</pre>
<p>Or add <code>{url}</code> as a custom connector in Claude, ChatGPT or any MCP client.</p>
<h3>Tools</h3><p>search_fragments, get_context, random_fragments, verify_draft, cite_sources, corpus_stats</p>
<h3>How models should use it</h3><pre>{guide}</pre>
<p>Wikipedia text is CC BY-SA 3.0. Code: <a href="https://github.com/timkosters/human-corpus">GitHub</a>.</p>
</body></html>"""


class RateLimit:
    """Token bucket per client IP. Pure ASGI so it works with any Starlette version."""

    def __init__(self, app):
        self.app = app
        self.buckets: dict[str, list[float]] = defaultdict(lambda: [float(BURST), time.monotonic()])

    def _ip(self, scope) -> str:
        """The client address as our own proxy saw it.

        Proxies append to X-Forwarded-For, so everything left of the last hop is whatever the
        client sent and can be forged to dodge the limit. Take the rightmost public address.
        """
        xff = ",".join(v.decode("latin-1") for k, v in scope.get("headers", []) if k == b"x-forwarded-for")
        for part in reversed(xff.split(",")):
            try:
                if ipaddress.ip_address(part.strip()).is_global:
                    return part.strip()
            except ValueError:
                continue
        return (scope.get("client") or ("?",))[0]

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/mcp") and scope["method"] == "POST":
            b = self.buckets[self._ip(scope)]
            now = time.monotonic()
            b[0] = min(BURST, b[0] + (now - b[1]) * RATE / 60)
            b[1] = now
            if b[0] < 1:
                await send({"type": "http.response.start", "status": 429,
                            "headers": [(b"content-type", b"application/json"), (b"retry-after", b"5")]})
                await send({"type": "http.response.body",
                            "body": b'{"error":"rate limited, retry in a few seconds"}'})
                return
            b[0] -= 1
            if len(self.buckets) > 50_000:  # forget idle clients, not everyone (a full clear resets abusers too)
                cutoff = now - 120
                for ip in [ip for ip, (_, t) in self.buckets.items() if t < cutoff]:
                    del self.buckets[ip]
        await self.app(scope, receive, send)


def build_app():
    from starlette.responses import HTMLResponse, JSONResponse
    from starlette.routing import Route

    params = inspect.signature(mcp.streamable_http_app).parameters
    if "stateless_http" in params:  # mcp 2.x
        from mcp.server.transport_security import TransportSecuritySettings

        app = mcp.streamable_http_app(
            stateless_http=True, json_response=True, host="0.0.0.0",
            transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        )
    else:  # mcp 1.x
        mcp.settings.stateless_http = True
        mcp.settings.json_response = True
        try:
            from mcp.server.transport_security import TransportSecuritySettings

            mcp.settings.transport_security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
        except ImportError:
            pass
        app = mcp.streamable_http_app()

    public_url = os.environ.get("HUMANCORPUS_PUBLIC_URL", "https://YOUR-HOST/mcp")

    async def landing(request):
        import html
        return HTMLResponse(LANDING.format(url=public_url, guide=html.escape(guide.GUIDE)))

    async def health(request):
        return JSONResponse({"ok": True})

    app.router.routes.insert(0, Route("/", landing))
    app.router.routes.insert(0, Route("/health", health))
    return RateLimit(app)


def serve(host: str = "0.0.0.0", port: int = 7860) -> None:
    import uvicorn

    uvicorn.run(build_app(), host=host, port=port, proxy_headers=True, forwarded_allow_ips="*")
