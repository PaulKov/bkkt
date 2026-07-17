from __future__ import annotations

import re

from typing import Iterable, List, Sequence

from ..exceptions import ConfigError


_RESERVED_AFTER_CDC = {"dbt"}


# Source modes: built-ins are `cdc` and `init`.
# Aliases are supported for convenience:
#   - initial -> init
#   - stream  -> cdc
_MODE_ALIASES = {"initial": "init", "stream": "cdc"}
_MODE_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def normalize_source_mode_token(token: str) -> str:
    """Normalize a source mode token from CLI/name.

    Rules:
      - lower-case
      - apply aliases (initial/stream)
      - validate allowed characters (dot-separated token in connector name)
    """

    t = str(token or "").strip().lower()
    if not t:
        raise ConfigError(
            "Пустой mode token (ожидается строка, например: cdc, init, backfill)"
        )
    t = _MODE_ALIASES.get(t, t)
    if not _MODE_TOKEN_RE.match(t):
        raise ConfigError(
            "Некорректный mode token: "
            f"{t!r}. Допустимо: латиница/цифры/`_`/`-` (например: cdc, init, backfill, replay_v2)"
        )
    return t


def split_csv(values: Sequence[str] | None) -> List[str]:
    """Split an argparse-style repeated CSV list into a flat list.

    Example:
      ["init,cdc", "cdc"] -> ["init", "cdc", "cdc"]
    """
    out: List[str] = []
    for raw in values or []:
        for part in str(raw).split(","):
            p = part.strip()
            if p:
                out.append(p)
    return out


def uniq_preserve(seq: Iterable[str]) -> List[str]:
    """De-duplicate while preserving order."""
    seen: set[str] = set()
    out: List[str] = []
    for x in seq:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def source_name_with_mode(name: str, mode_tok: str) -> str:
    """Build a dot-style source connector name variant with a given mode token.

    Rules:
    - Works only for names that look like:
        <env>.<domain>.<dataset>.source.<system>.<...>.<index>
    - If one of mode tokens (cdc/stream/init/initial) is present in the tail,
      replace the first occurrence.
    - Otherwise insert the mode token right after <system>.
    """
    parts = [p for p in (name or "").split(".") if p]
    if len(parts) < 6 or parts[3].lower() != "source":
        raise ConfigError(
            f"Cannot generate source mode variant: unsupported name: {name}"
        )

    idx = parts[-1]
    tail = parts[5:-1]
    mode_tokens = {"cdc", "stream", "init", "initial"}

    replaced = False
    for i, t in enumerate(tail):
        if t.lower() in mode_tokens:
            tail[i] = mode_tok
            replaced = True
            break

    if not replaced:
        tail = [mode_tok] + tail

    return ".".join([parts[0], parts[1], parts[2], parts[3], parts[4], *tail, idx])


def sink_name_with_kind(name: str, kind_tok: str) -> str:
    """Build a dot-style sink connector name variant with a given kind token.

    Rules (best-effort):
    - Find the `sink` segment.
    - CDC kinds live right after `cdc` token: ... .cdc.<kind>. ...
      - If token after cdc already looks like a kind (not reserved), replace it.
      - Otherwise insert.
    - If there is no `cdc` marker, insert `cdc.<kind>` at the beginning of tail.
    """

    parts = [p for p in (name or "").split(".") if p]
    if len(parts) < 7 or "sink" not in [p.lower() for p in parts]:
        raise ConfigError(
            f"Cannot generate sink kind variant: unsupported name: {name}"
        )

    # Find 'sink' segment (should be at index 3 in our conventions, but be defensive).
    i = next((j for j, p in enumerate(parts) if p.lower() == "sink"), -1)
    if i == -1 or len(parts) < i + 3:
        raise ConfigError(
            f"Cannot generate sink kind variant: unsupported name: {name}"
        )

    idx = parts[-1]
    prefix = parts[: i + 3]  # includes env.domain.dataset.sink.<layer>.<system>
    tail = parts[i + 3 : -1]

    lower_tail = [t.lower() for t in tail]
    if "cdc" in lower_tail:
        j = lower_tail.index("cdc")
        # If token after cdc is already a kind (not reserved), replace it; otherwise insert.
        if (
            j + 1 < len(tail)
            and tail[j + 1].lower() not in _RESERVED_AFTER_CDC
            and not tail[j + 1].isdigit()
        ):
            tail[j + 1] = kind_tok
        else:
            tail.insert(j + 1, kind_tok)
    else:
        tail = ["cdc", kind_tok] + tail

    return ".".join([*prefix, *tail, idx])
