from __future__ import annotations

import json

import pytest

from tmci import config as config_module
from tmci import session as session_module
from tmci import store
from tmci.errors import NotLoggedIn
from tmci.paths import config_file
from tmci.session import Session

pytestmark = pytest.mark.usefixtures("tmci_home")


def read_raw() -> dict:
    return json.loads(config_file().read_text(encoding="utf-8"))


def test_settings_and_session_share_one_file():
    config_module.set_value(config_module.load(), "cache_ttl_seconds", "42")
    session_module.save(Session(cookies={"tmci_session": "abc"}))

    raw = read_raw()
    assert raw["cache_ttl_seconds"] == 42
    assert raw["session"]["cookies"]["tmci_session"] == "abc"


def test_saving_a_session_keeps_existing_settings():
    config_module.set_value(config_module.load(), "cache_ttl_seconds", "42")
    session_module.save(Session(cookies={"tmci_session": "abc"}))

    assert config_module.load().cache_ttl_seconds == 42


def test_saving_settings_keeps_an_existing_session():
    session_module.save(Session(cookies={"tmci_session": "abc"}))
    config_module.set_value(config_module.load(), "color", "false")

    assert session_module.load().cookies == {"tmci_session": "abc"}


def test_config_save_does_not_drop_the_session():
    session_module.save(Session(cookies={"tmci_session": "abc"}))
    config_module.save(config_module.load())

    assert session_module.exists()


def test_clearing_the_session_keeps_settings():
    config_module.set_value(config_module.load(), "cache_ttl_seconds", "42")
    session_module.save(Session(cookies={"tmci_session": "abc"}))

    assert session_module.clear() is True

    assert "session" not in read_raw()
    assert config_module.load().cache_ttl_seconds == 42


def test_clearing_without_a_session_reports_nothing_removed():
    assert session_module.clear() is False


def test_session_round_trips():
    session_module.save(Session(cookies={"tmci_session": "abc", "XSRF-TOKEN": "x"}))
    loaded = session_module.load()

    assert loaded.cookies == {"tmci_session": "abc", "XSRF-TOKEN": "x"}


def test_missing_file_means_not_logged_in():
    with pytest.raises(NotLoggedIn):
        session_module.load()


def test_settings_only_file_means_not_logged_in():
    config_module.set_value(config_module.load(), "color", "false")

    with pytest.raises(NotLoggedIn):
        session_module.load()


def test_session_without_the_lms_cookie_is_rejected():
    store.update(session={"cookies": {"XSRF-TOKEN": "only-csrf"}})

    with pytest.raises(NotLoggedIn):
        session_module.load()


def test_corrupt_config_falls_back_to_defaults():
    config_file().write_text("{not json", encoding="utf-8")

    assert config_module.load().cache_ttl_seconds == 600
    assert session_module.exists() is False


def test_unknown_keys_in_the_file_are_ignored_not_dropped():
    store.update(some_future_setting="keep me")
    config_module.set_value(config_module.load(), "color", "false")

    assert read_raw()["some_future_setting"] == "keep me"


def test_touch_advances_the_saved_timestamp():
    session = Session(cookies={"tmci_session": "abc"}, saved_at=0)
    session_module.save(session)
    session_module.touch(session)

    assert session_module.load().saved_at > 0
