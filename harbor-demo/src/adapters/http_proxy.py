from __future__ import annotations

import urllib.request
from typing import Any


def proxy_environment(proxy_url: str) -> dict[str, str]:
    """Env so HTTP clients send traffic through the proxy."""
    proxy = proxy_url.strip()
    if not proxy:
        return {}
    return {
        "HTTP_PROXY": proxy,
        "HTTPS_PROXY": proxy,
        "ALL_PROXY": proxy,
        "http_proxy": proxy,
        "https_proxy": proxy,
        "all_proxy": proxy,
        "NO_PROXY": "",
        "no_proxy": "",
    }


class ForcedProxyHandler(urllib.request.ProxyHandler):
    """ProxyHandler that does not bypass loopback hosts."""

    def proxy_open(self, req: urllib.request.Request, proxy: str, type: str) -> Any:
        original = urllib.request.proxy_bypass
        urllib.request.proxy_bypass = lambda host: False  # type: ignore[assignment]
        try:
            return super().proxy_open(req, proxy, type)
        finally:
            urllib.request.proxy_bypass = original


def build_forced_proxy_opener(proxy_url: str) -> urllib.request.OpenerDirector:
    proxy = proxy_url.strip()
    if not proxy:
        return urllib.request.build_opener()
    handler = ForcedProxyHandler({"http": proxy, "https": proxy})
    return urllib.request.build_opener(handler)
