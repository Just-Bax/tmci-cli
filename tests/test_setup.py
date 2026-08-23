from __future__ import annotations

import json

from tmci.cli.main import main


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


def test_browser_probe_reads_the_playwright_cache(tmp_path, monkeypatch):
    from tmci.login import browser_is_installed

    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
    assert browser_is_installed() is False

    (tmp_path / "chromium-1234").mkdir()
    assert browser_is_installed() is True
