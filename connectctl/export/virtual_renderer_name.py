from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


def infer_name_from_filename(env_file: Path) -> Optional[str]:
    if env_file.suffix.lower() != ".json":
        return None
    if re.match(r"^(dev|stage|prod)\.", env_file.name, re.IGNORECASE):
        return env_file.stem
    return None
