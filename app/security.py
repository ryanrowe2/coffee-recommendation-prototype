"""Validate signatures and restrictive CORS configuration at trust boundaries."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import re
from urllib.parse import urlsplit

DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def verify_typeform_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if (
        not secret
        or not isinstance(signature, str)
        or not signature.startswith("sha256=")
        or len(signature) > 150
    ):
        return False
    try:
        given = base64.b64decode(signature.removeprefix("sha256="), validate=True)
    except (ValueError, base64.binascii.Error):
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return hmac.compare_digest(expected, given)


def validate_origin(origin: str) -> str:
    """Return a canonical HTTPS origin for both configuration and request comparison."""
    if (
        not isinstance(origin, str)
        or not origin
        or "?" in origin
        or "#" in origin
        or origin != origin.strip()
        or any(ord(char) <= 32 or char == "\\" for char in origin)
    ):
        raise ValueError("Invalid CORS origin.")
    try:
        parts = urlsplit(origin)
        port = parts.port
        host = parts.hostname
    except ValueError as exc:
        raise ValueError("Invalid CORS origin.") from exc
    if (
        parts.scheme.lower() != "https"
        or not host
        or parts.username is not None
        or parts.password is not None
        or parts.netloc.endswith(":")  # Explicitly empty port, e.g. example.com:
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
        or port not in (None, 443)
    ):
        raise ValueError("CORS origins must be HTTPS origins without paths or credentials.")
    host = host.lower()
    try:
        parsed_ip = ipaddress.ip_address(host)
    except ValueError:
        try:
            ascii_host = host.encode("idna").decode("ascii")
        except (UnicodeError, ValueError) as exc:
            raise ValueError("Invalid CORS host.") from exc
        if (
            len(ascii_host) > 253
            or ascii_host.endswith(".")
            or not all(DNS_LABEL.fullmatch(part) for part in ascii_host.split("."))
        ):
            raise ValueError("Invalid CORS host.") from None
        host = ascii_host
    else:
        host = f"[{parsed_ip.compressed}]" if parsed_ip.version == 6 else parsed_ip.compressed
    return f"https://{host}"
