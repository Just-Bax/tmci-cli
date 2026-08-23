from . import auth, describe, download, listing, raw, settings, setup

GROUPS = (auth, listing, describe, download, settings, setup, raw)

__all__ = ["GROUPS"]
