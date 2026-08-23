from __future__ import annotations

import os
import stat
from pathlib import Path

HOME_ENV = "TMCI_HOME"


def home() -> Path:
    override = os.environ.get(HOME_ENV)
    root = Path(override).expanduser() if override else Path.home() / ".tmci"
    root.mkdir(parents=True, exist_ok=True)
    return root


def config_file() -> Path:
    return home() / "config.json"


def downloads_dir() -> Path:
    return _ensure(home() / "downloads")


def cache_dir() -> Path:
    return _ensure(home() / "cache")


def browser_profile_dir() -> Path:
    return _ensure(home() / "browser")


def _ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def restrict(path: Path) -> None:
    """Make a file owner-readable only. On Windows this only clears the read-only
    bit, so config.json is not protected from other accounts on that OS."""
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
