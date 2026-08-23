from __future__ import annotations

import argparse
from pathlib import Path

from .. import config as config_module
from ..cache import Cache
from ..client import Client
from ..config import Config
from ..service import LmsService
from ..session import load as load_session


class Context:
    """Per-invocation state: settings, output mode and lazily built LMS access.

    Built lazily so commands that never touch the network (config, help) do not
    require a stored session.
    """

    def __init__(self, args: argparse.Namespace, config: Config | None = None) -> None:
        self.args = args
        self.config = config if config is not None else config_module.load()
        self._client: Client | None = None
        self._service: LmsService | None = None

    @property
    def as_json(self) -> bool:
        return bool(getattr(self.args, "json", False))

    @property
    def use_color(self) -> bool:
        return self.config.color and not getattr(self.args, "no_color", False)

    @property
    def cache(self) -> Cache:
        ttl = 0 if getattr(self.args, "refresh", False) else self.config.cache_ttl_seconds
        return Cache(ttl_seconds=ttl)

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = Client(load_session(), base_url=self.config.base_url)
        return self._client

    @property
    def service(self) -> LmsService:
        if self._service is None:
            self._service = LmsService(self.client, self.cache)
        return self._service

    def download_root(self) -> Path:
        out = getattr(self.args, "out", None)
        if out:
            path = Path(out).expanduser()
            path.mkdir(parents=True, exist_ok=True)
            return path
        return self.config.resolved_download_dir()

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
