from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from . import BASE_URL, store
from .errors import TmciError
from .paths import downloads_dir


@dataclass
class Config:
    base_url: str = BASE_URL
    download_dir: str = ""
    cache_ttl_seconds: int = 600
    color: bool = True

    def resolved_download_dir(self) -> Path:
        if self.download_dir:
            path = Path(self.download_dir).expanduser()
            path.mkdir(parents=True, exist_ok=True)
            return path
        return downloads_dir()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _known() -> set[str]:
    return {f.name for f in fields(Config)}


def load() -> Config:
    data = store.read()
    known = _known()
    return Config(**{k: v for k, v in data.items() if k in known})


def save(config: Config) -> None:
    store.update(**config.to_dict())


def set_value(config: Config, key: str, raw: str) -> Config:
    known = _known()
    if key not in known:
        options = ", ".join(sorted(known))
        raise TmciError(f"Unknown setting '{key}'. Valid settings: {options}")

    current = getattr(config, key)
    if isinstance(current, bool):
        value: Any = raw.strip().lower() in ("1", "true", "yes", "on")
    elif isinstance(current, int):
        try:
            value = int(raw)
        except ValueError:
            raise TmciError(f"'{key}' expects a whole number, got {raw!r}") from None
    else:
        value = raw

    setattr(config, key, value)
    store.update(**{key: value})
    return config
