from __future__ import annotations

import json
from typing import Any

from .paths import config_file, restrict

SESSION_KEY = "session"


def read() -> dict[str, Any]:
    path = config_file()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def update(**changes: Any) -> dict[str, Any]:
    """Merge keys into config.json, leaving every other key alone.

    Settings and the session cookie share one file, so a blind overwrite from
    either side would drop the other.
    """
    data = read()
    for key, value in changes.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value

    path = config_file()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # The file holds a live session cookie, so it is credentials, not just settings.
    restrict(path)
    return data
