# TMCI CLI

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Platforms](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#install)

Command line client for the TMC Institute LMS at `lms.tmci.uz`.

Installs as the package `tmci-cli` and gives you a `tmci` command.

Lists your courses, the themes in each one, and the materials attached to each theme,
and downloads the files. Every command takes `--json`, so you can pipe it into other
tools.

```console
$ tmci list courses
2025-2026 Spring
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Slug     ┃ Course               ┃ Lecturer         ┃ Tutor       ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ 31-21-en │ Data Structures      │ Prof. A. Karimov │ M. Yusupova │
│ 32-21-en │ Operating Systems    │ Prof. D. Rasulov │ -           │
│ 33-21-en │ Discrete Mathematics │ Prof. S. Umarova │ N. Tosheva  │
└──────────┴──────────────────────┴──────────────────┴─────────────┘

$ tmci list contents 31-21-en
Data Structures (31-21-en)
┏━━━━━┳━━━┳━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Ref ┃ # ┃ Kind  ┃ Section  ┃ Title                    ┃
┡━━━━━╇━━━╇━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 1.1 │ 1 │ file  │ lecture  │ Week 1 slides            │
│ 1.2 │ 2 │ link  │ lecture  │ Reading: Sedgewick ch. 3 │
│ 2.1 │ 3 │ file  │ lecture  │ Week 2 slides            │
│ 3.1 │ 4 │ file  │ tutorial │ Lab handout              │
│ 3.2 │ 5 │ video │ tutorial │ Walkthrough              │
└─────┴───┴───────┴──────────┴──────────────────────────┘

$ tmci download 31-21-en --theme 1
saved    1.1  /home/ali/.tmci/downloads/31-21-en/lecture/01 Arrays and lists/01 Week 1 slides.pdf
link     1.2  Reading: Sedgewick ch. 3  https://example.org/reading
```

## Install

You do not need Python or anything else installed first.

**Windows** (PowerShell):

```powershell
irm https://raw.githubusercontent.com/Just-Bax/tmci-cli/master/install.ps1 | iex
```

**macOS / Linux**:

```bash
curl -fsSL https://raw.githubusercontent.com/Just-Bax/tmci-cli/master/install.sh | sh
```

Then open a **new** terminal and run `tmci login`.

The installer fetches [uv](https://docs.astral.sh/uv/), which supplies its own Python, then
installs `tmci` into an isolated environment and downloads the browser used for signing in
(about 150MB, once).

<details>
<summary>Already have Python tooling?</summary>

```bash
uv tool install "tmci-cli @ https://github.com/Just-Bax/tmci-cli/archive/refs/heads/master.zip"
tmci setup
```

Or from a clone, for development:

```bash
pip install -e .
tmci setup
```
</details>

### Updating

Re-run the same install command. It replaces the existing copy.

### Uninstalling

```bash
uv tool uninstall tmci-cli
```

Your downloads and settings in `~/.tmci` are left alone; delete that folder to remove them.

## Sign in

```bash
tmci login
```

A browser window opens on the real LMS login page. Sign in there, and it closes on its
own once you reach the dashboard.

Your password is typed into the LMS page itself. This tool never reads it, never asks for
it, and never writes it anywhere. Only the resulting session cookie is saved, into
`~/.tmci/config.json` alongside your settings.

The browser step is not optional. The login form is protected by reCAPTCHA v3 and the
server rejects any request without a valid token, so a plain HTTP POST cannot sign in.

To skip the browser, copy the `tmci_session` cookie from your own browser's devtools:

```bash
tmci login --cookie "tmci_session=eyJpdiI6..."
```

Sessions last **2 hours from your last request** and slide forward each time you use the
CLI. After a longer gap, run `tmci login` again.

```bash
tmci whoami     # who is signed in
tmci logout     # end the session, delete the cookie and cache
tmci setup      # re-download the sign-in browser if it goes missing
```

## Browse

```bash
tmci list courses
tmci list themes 31-21-en
tmci list themes 31-21-en --section lecture
tmci list contents 31-21-en
tmci list contents 31-21-en --theme 2 --kind file
```

```bash
tmci describe course 31-21-en
tmci describe course "data structures"     # match by name instead of slug
tmci describe theme 31-21-en 3
tmci describe content 31-21-en 3.2
```

## Download

```bash
tmci download 31-21-en 3.2          # one item
tmci download 31-21-en --theme 3    # everything in a theme
tmci download 31-21-en --section lecture --kind file
tmci download 31-21-en "week 3"     # everything whose title matches
tmci download 31-21-en --all
tmci download 31-21-en --all --out ./notes
```

Files are laid out to mirror the LMS:

```
~/.tmci/downloads/31-21-en/lecture/01 Arrays and lists/01 Week 1 slides.pdf
```

Items that are links rather than files are printed, not downloaded. To follow one:

```bash
tmci open 31-21-en 1.2
```

## How to refer to things

| Ref | Means |
|---|---|
| `31-21-en` | a course, by slug |
| `data structures` | a course, by any unique part of its name |
| `3` | theme 3 (with `describe theme`), or content 3 (with `download`) |
| `lecture:2` | the 2nd theme within the lecture section |
| `3.2` | the 2nd item of theme 3 |
| `203` | a content item by its LMS id |
| `week 1` | anything whose title contains that text |

`tmci list contents` prints the `Ref` column, so `3.2` is always visible before you use it.

## Settings

```bash
tmci config                                  # show effective settings and paths
tmci config set cache_ttl_seconds 60
tmci config set download_dir ~/uni
tmci config clear-cache
```

| Setting | Default | Purpose |
|---|---|---|
| `base_url` | `https://lms.tmci.uz` | which LMS to talk to |
| `download_dir` | `~/.tmci/downloads` | where files land |
| `cache_ttl_seconds` | `600` | how long LMS responses are reused |
| `color` | `true` | coloured output |

Responses are cached because resolving a course slug costs a request of its own. Pass
`--refresh` to any command to ignore the cache for that run.

## Files on disk

Everything lives in `~/.tmci` (`tmci --home` prints the path, `TMCI_HOME` overrides it):

```
~/.tmci/
  config.json      settings and the session cookie, owner-readable only
  browser/         Playwright profile, so login remembers you
  cache/           cached LMS responses
  downloads/       downloaded course materials
```

`config.json` holds your live session cookie, so it is treated as credentials: it is
written owner-readable only, and `tmci config show` never echoes the session. Signing out
removes the session and leaves your settings alone.

On Windows that owner-only permission is not enforced the way it is on Linux and macOS.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | general error |
| 2 | bad command line |
| 3 | not logged in, or session expired |
| 4 | no such course, theme or content |
| 5 | the LMS page could not be parsed |

## When the LMS changes

There is no public API. Course lists and the profile page are scraped from HTML, so a
redesign will break them and you will see exit code 5. Course materials come from a JSON
endpoint and are more stable.

To see exactly what the LMS returned for a course:

```bash
tmci raw 31-21-en
```

Attach that output to a bug report; it is the fastest way to get a parser fixed.

## Use from an AI agent

Every command speaks `--json` and maps failures onto distinct exit codes, so `tmci` works
as a tool for an AI agent. [`SKILL.md`](SKILL.md) is the brief: data model, ref syntax,
JSON shapes, exit codes, and the operations the agent should leave to you. It is plain
markdown with a small YAML header, so paste it into a system prompt, point the agent at
the file, or drop it wherever your tool loads skills from.

You can then ask in plain language ("what is new in Data Structures this week", "grab the
lab handouts for weeks 1 to 3") and the agent resolves the refs and runs the downloads.

It is told not to run `tmci login`, which waits on a browser window, and not to read
`~/.tmci/config.json`, which holds the session cookie.

## Contributing

Issues and pull requests are welcome.

```bash
git clone https://github.com/Just-Bax/tmci-cli
cd tmci-cli
pip install -e ".[dev]"

pytest tests -q
ruff check src tests
```

The layout follows the request path: `client.py` speaks HTTP, `parsers.py` turns LMS
responses into the dataclasses in `models.py`, `refs.py` resolves what you typed to one of
them, `service.py` is the only LMS access the commands get, and `cli/commands/` holds one
module per command group.

Tests use recorded LMS payloads and never touch the network, so `pytest` works offline.
If the LMS markup changes, add the new shape to `tests/conftest.py` alongside the existing
one rather than replacing it.

## License

[MIT](LICENSE) - Copyright (c) 2026 Isfandiyor Baxtiyorov.

This is an unofficial client. It is not affiliated with, endorsed by, or supported by TMC
Institute. It reads only what your own account can already see, using your own session.
