"""Explicitly ignore HTTP(S) environment proxies for local test requests.

Using the default urllib opener can silently send loopback HTTP requests via
proxy settings, invalidating runtime checks and disclosing synthetic requests.
"""

from __future__ import annotations

from urllib.request import ProxyHandler, build_opener


def loopback_opener(*handlers):
    """Build a standard urllib opener with a zero-proxy policy."""
    return build_opener(ProxyHandler({}), *handlers)
