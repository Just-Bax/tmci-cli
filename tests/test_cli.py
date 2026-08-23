from __future__ import annotations

import json

import pytest

from tmci.cli.main import build_parser, main
from tmci.errors import EXIT_AUTH, EXIT_NOT_FOUND, EXIT_OK, EXIT_PARSE, EXIT_USAGE

PARSES = [
    ["login"],
    ["login", "--cookie", "x"],
    ["logout"],
    ["whoami"],
    ["list", "courses"],
    ["list", "themes", "31-21-en"],
    ["list", "themes", "31-21-en", "--section", "lecture"],
    ["list", "contents", "31-21-en"],
    ["list", "contents", "31-21-en", "--theme", "2", "--kind", "file"],
    ["describe", "course", "31-21-en"],
    ["describe", "theme", "31-21-en", "2"],
    ["describe", "content", "31-21-en", "3.1"],
    ["download", "31-21-en", "3.1"],
    ["download", "31-21-en", "--all"],
    ["download", "31-21-en", "--all", "--out", "somewhere"],
    ["open", "31-21-en", "1.2"],
    ["config"],
    ["config", "show"],
    ["config", "set", "cache_ttl_seconds", "30"],
    ["config", "clear-cache"],
    ["raw", "31-21-en"],
]


@pytest.mark.parametrize("argv", PARSES, ids=lambda a: " ".join(a))
def test_every_command_parses_and_binds_a_handler(argv):
    args = build_parser().parse_args(argv)
    assert callable(getattr(args, "func", None))


@pytest.mark.parametrize("argv", PARSES, ids=lambda a: " ".join(a))
def test_json_flag_is_accepted_everywhere(argv):
    args = build_parser().parse_args([*argv, "--json"])
    assert args.json is True


def test_refresh_flag_is_accepted(argv=None):
    assert build_parser().parse_args(["list", "courses", "--refresh"]).refresh is True


def test_unknown_command_is_a_usage_error():
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["nonsense"])
    assert exc.value.code == EXIT_USAGE


def test_list_without_a_resource_is_a_usage_error():
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["list"])
    assert exc.value.code == EXIT_USAGE


def test_bare_invocation_prints_help(tmci_home, capsys):
    assert main([]) == EXIT_USAGE
    assert "usage: tmci" in capsys.readouterr().out


def test_home_flag(tmci_home, capsys):
    assert main(["--home"]) == EXIT_OK
    assert str(tmci_home) in capsys.readouterr().out


def test_not_logged_in_exits_with_the_auth_code(tmci_home):
    assert main(["list", "courses"]) == EXIT_AUTH


def test_not_logged_in_json_carries_the_exit_code(tmci_home, capsys):
    main(["list", "courses", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert payload["exit_code"] == EXIT_AUTH
    assert "Not logged in" in payload["error"]


def test_download_validates_its_arguments_before_needing_a_session(tmci_home, capsys):
    assert main(["download", "31-21-en", "--json"]) == 1
    assert "--all" in json.loads(capsys.readouterr().out)["error"]


def test_config_show_works_without_a_session(tmci_home, capsys):
    assert main(["config", "show", "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)

    assert payload["cache_ttl_seconds"] == 600
    assert payload["paths"]["home"] == str(tmci_home)


def test_config_set_persists(tmci_home, capsys):
    assert main(["config", "set", "cache_ttl_seconds", "30", "--json"]) == EXIT_OK
    capsys.readouterr()

    main(["config", "show", "--json"])
    assert json.loads(capsys.readouterr().out)["cache_ttl_seconds"] == 30


def test_config_set_rejects_an_unknown_key(tmci_home, capsys):
    assert main(["config", "set", "nope", "1", "--json"]) != EXIT_OK
    assert "Unknown setting" in json.loads(capsys.readouterr().out)["error"]


def test_config_set_rejects_a_non_numeric_ttl(tmci_home, capsys):
    assert main(["config", "set", "cache_ttl_seconds", "soon", "--json"]) != EXIT_OK
    assert "whole number" in json.loads(capsys.readouterr().out)["error"]


def test_config_set_parses_booleans(tmci_home, capsys):
    main(["config", "set", "color", "false", "--json"])
    capsys.readouterr()
    main(["config", "show", "--json"])

    assert json.loads(capsys.readouterr().out)["color"] is False


def test_error_classes_map_to_distinct_exit_codes():
    from tmci.errors import Ambiguous, NotFound, NotLoggedIn, ParseError, TmciError

    assert NotLoggedIn().exit_code == EXIT_AUTH
    assert NotFound("x").exit_code == EXIT_NOT_FOUND
    assert Ambiguous("x").exit_code == EXIT_NOT_FOUND
    assert ParseError("x").exit_code == EXIT_PARSE
    assert TmciError("x").exit_code == 1


def test_non_ascii_output_survives_a_legacy_codepage_stdout(tmci_home, monkeypatch):
    import io
    import sys

    from tmci.cli.main import force_utf8_output

    # Reproduces a Windows cp1252 console, where any Cyrillic or Uzbek title
    # used to abort the command with UnicodeEncodeError.
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(raw, encoding="cp1252"))
    force_utf8_output()
    print("Маъруза 1 — кириш")
    sys.stdout.flush()

    assert "Маъруза" in raw.getvalue().decode("utf-8")


def test_force_utf8_output_tolerates_a_stream_without_reconfigure(monkeypatch):
    import io
    import sys

    from tmci.cli.main import force_utf8_output

    monkeypatch.setattr(sys, "stdout", io.StringIO())
    force_utf8_output()
