from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class NormalizedEndpoint:
    raw: str
    host: str
    port: str | None = None

    @property
    def host_port(self) -> str:
        return f"{self.host}:{self.port}" if self.port else self.host


def normalize_endpoint(value: str) -> NormalizedEndpoint:
    """Normalize URL, host:port, IP:port or plain host for matching."""

    raw = str(value).strip()
    parsed = urlparse(raw if "://" in raw else f"//{raw}")
    host = (parsed.hostname or raw).strip("[]").lower()
    port = str(parsed.port) if parsed.port is not None else None
    if not port and "://" not in raw and raw.count(":") == 1:
        maybe_host, maybe_port = raw.rsplit(":", 1)
        if maybe_port.isdigit():
            host = maybe_host.strip("[]").lower()
            port = maybe_port
    return NormalizedEndpoint(raw=raw, host=host, port=port)


def endpoint_matches(query: str, candidates: list[str] | tuple[str, ...]) -> bool:
    """Return true if a query endpoint matches any candidate by host or host:port."""

    needle = normalize_endpoint(query)
    for candidate in candidates:
        current = normalize_endpoint(candidate)
        if needle.port:
            if needle.host_port == current.host_port:
                return True
        elif needle.host == current.host:
            return True
    return False
