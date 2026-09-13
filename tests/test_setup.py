from __future__ import annotations

import json

import pytest

from tmci import login as login_module
from tmci.cli.main import main
from tmci.errors import LoginFailed


def test_setup_reports_ready_when_the_browser_is_present(tmci_home, monkeypatch, capsys):
    monkeypatch.setattr("tmci.cli.commands.setup.browser_is_installed", lambda: True)

    assert main(["setup", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ready"] is True


def test_setup_check_does_not_download(tmci_home, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr("tmci.cli.commands.setup.browser_is_installed", lambda: False)
    monkeypatch.setattr("tmci.cli.commands.setup.install_chromium", lambda: calls.append(1) or True)

    assert main(["setup", "--check", "--json"]) == 1
    assert calls == []
    assert json.loads(capsys.readouterr().out)["ready"] is False


def test_setup_downloads_when_missing(tmci_home, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr("tmci.cli.commands.setup.browser_is_installed", lambda: False)
    monkeypatch.setattr("tmci.cli.commands.setup.install_chromium", lambda: calls.append(1) or True)

    assert main(["setup", "--json"]) == 0
    assert calls == [1]


def test_setup_reports_a_failed_download(tmci_home, monkeypatch, capsys):
    monkeypatch.setattr("tmci.cli.commands.setup.browser_is_installed", lambda: False)
    monkeypatch.setattr("tmci.cli.commands.setup.install_chromium", lambda: False)

    assert main(["setup", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["ready"] is False


def build(root, name, complete=True):
    directory = root / name
    directory.mkdir(parents=True)
    if complete:
        (directory / "INSTALLATION_COMPLETE").touch()
    return directory


def pin(monkeypatch, root, builds=("chromium-1234", "chromium_headless_shell-1234")):
    monkeypatch.setattr(login_module, "_browsers_root", lambda: root)
    monkeypatch.setattr(login_module, "_pinned_builds", lambda: list(builds))


def test_a_complete_install_of_every_pinned_build_is_installed(tmp_path, monkeypatch):
    pin(monkeypatch, tmp_path)
    build(tmp_path, "chromium-1234")
    build(tmp_path, "chromium_headless_shell-1234")

    assert login_module.browser_is_installed()


def test_a_browser_from_another_project_is_not_this_one(tmp_path, monkeypatch):
    # The bug this guards: any chromium* directory counted, so a build left by
    # some other tool reported ready and then failed to launch.
    pin(monkeypatch, tmp_path)
    build(tmp_path, "chromium-1000")
    build(tmp_path, "chromium_headless_shell-1000")

    assert not login_module.browser_is_installed()


def test_an_interrupted_download_is_not_installed(tmp_path, monkeypatch):
    pin(monkeypatch, tmp_path)
    build(tmp_path, "chromium-1234", complete=False)
    build(tmp_path, "chromium_headless_shell-1234")

    assert not login_module.browser_is_installed()


def test_the_headless_shell_is_required_too(tmp_path, monkeypatch):
    pin(monkeypatch, tmp_path)
    build(tmp_path, "chromium-1234")

    assert not login_module.browser_is_installed()


def test_an_unreadable_manifest_counts_as_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(login_module, "_browsers_root", lambda: tmp_path)
    monkeypatch.setattr(
        login_module, "_pinned_builds", lambda: (_ for _ in ()).throw(OSError("no manifest"))
    )

    assert not login_module.browser_is_installed()


def test_the_pinned_builds_come_from_playwrights_own_manifest():
    builds = login_module._pinned_builds()

    assert builds, "playwright ships a browsers.json listing the builds it pins"
    assert any(name.startswith("chromium-") for name in builds)
    assert any(name.startswith("chromium_headless_shell-") for name in builds)


class FakeChromium:
    """Fails to launch until the browser is fetched, like a real missing build."""

    def __init__(self, failures=1, error="Executable doesn't exist at chrome.exe"):
        self.failures = failures
        self.error = error
        self.attempts = 0

    def launch_persistent_context(self, **_options):
        self.attempts += 1
        if self.attempts <= self.failures:
            raise RuntimeError(self.error)
        return "context"


class FakePlaywright:
    def __init__(self, chromium):
        self.chromium = chromium


def test_login_fetches_the_browser_and_retries_rather_than_giving_up(tmci_home, monkeypatch):
    # The dead end this guards: launch failed telling the user to run a
    # playwright command the tool install does not provide.
    fetched = []
    monkeypatch.setattr(login_module, "install_chromium", lambda: fetched.append(True) or True)
    chromium = FakeChromium(failures=1)

    context = login_module._launch(FakePlaywright(chromium))

    assert context == "context"
    assert fetched == [True]
    assert chromium.attempts == 2


def test_a_failed_download_says_so_rather_than_looping(tmci_home, monkeypatch):
    monkeypatch.setattr(login_module, "install_chromium", lambda: False)

    with pytest.raises(LoginFailed, match="could not be downloaded"):
        login_module._launch(FakePlaywright(FakeChromium(failures=1)))


def test_an_unrelated_launch_failure_is_not_treated_as_a_missing_browser(tmci_home, monkeypatch):
    monkeypatch.setattr(login_module, "install_chromium", lambda: pytest.fail("must not download"))
    chromium = FakeChromium(failures=1, error="Target page crashed")

    with pytest.raises(LoginFailed, match="Could not start the browser"):
        login_module._launch(FakePlaywright(chromium))
