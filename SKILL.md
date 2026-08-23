---
name: tmci
description: Read and download TMC Institute LMS course material through the `tmci` command line client. Use when the user asks about their courses, themes, weeks, lectures, tutorials, slides, labs, handouts, readings or recordings, or asks to find, list or download university course files. Triggers on "my courses", "lecture slides", "download the lab handout", "what is in week 3", "TMCI", "lms.tmci.uz".
---

# tmci

Command line client for the TMC Institute LMS at `lms.tmci.uz`. It scrapes the site with
the user's own session and sees only what they can already see.

## Parse `--json`, and put the flag last

```bash
tmci list courses --json      # works
tmci --json list courses      # exit 2, unrecognized argument
tmci config --json show       # exit 0, but prints a table
```

Errors are JSON on stdout too: `{"error": "...", "exit_code": 3}`.

## Data model

```
course   31-21-en          a subject, identified by a slug
  theme  1, 2, 3 ...       one lecture or lab, numbered course-wide
    content  1.1, 1.2 ...  a file, link or video inside that theme
```

Every theme belongs to a `section` (`lecture` or `tutorial`). Every content item has a
`kind`: `file`, `link` or `video`. Links are external URLs, reported but never downloaded.

Course refs are global. Theme and content refs only mean anything relative to a course, so
resolve the course first.

## Refs

| Ref | Means |
|---|---|
| `31-21-en` | a course, by exact slug |
| `data structures` | a course, by any unique part of its name |
| `3.2` | the 2nd content item of theme 3 |
| `lecture:2` | the 2nd theme in the lecture section |
| `3` | theme 3 for `describe theme`; content #3 for `download` and `describe content` |
| `203` | a content item by its LMS id |
| `week 1` | anything whose title contains that text |

Two traps:

- A bare number is never matched against titles. `download X 5` looks for content index 5
  or LMS id 5, then errors out rather than matching "Week 5 recap". Quote a non-numeric
  string to match titles: `download X "week 5"`.
- `X 3` and `X --theme 3` are different. `3` is the single item whose course-wide index is
  3; `--theme 3` is everything in theme 3. Use `--theme` when the user says "week 3".

A title ref can match several items. `download` takes all of them; `describe content`
refuses and lists the candidates.

## Session

`tmci config show --json` reports `logged_in` without a network call. If that is false, or
any command exits 3, ask the user to run `tmci login`. Do not run it yourself: it opens a
browser window and blocks for up to five minutes waiting for a password. There is no
headless path; the form is behind reCAPTCHA v3.

Sessions last two hours from the last request and slide forward with use.

## Reading

```bash
tmci list courses --json
tmci list themes 31-21-en --json
tmci list contents 31-21-en --json
tmci list contents 31-21-en --theme 2 --kind file --json
tmci describe course 31-21-en --json
tmci describe theme 31-21-en 3 --json
tmci describe content 31-21-en 3.2 --json
```

| Command | Returns |
|---|---|
| `list courses` | `[{name, slug, url, lecture_teacher, tutorial_teacher, semester}]` |
| `list themes` | `[{index, position, section, number, date, title, label, content_count}]` |
| `list contents` | `[{ref, index, position, theme_index, theme_title, section, kind, title, description, url, file_name, lms_id}]` |
| `describe course` | `{course, sections, themes}` |
| `whoami` | `{full_name, student_number, group_name, specialization, study_language, degree, email}` |

`list contents` carries every field the `describe` commands do. Fetch it once and filter
locally rather than calling `describe content` per item.

Responses are cached for 10 minutes. Add `--refresh` if the user says something was just
uploaded.

## Downloading

```bash
tmci download 31-21-en 3.2 --json
tmci download 31-21-en --theme 3 --json
tmci download 31-21-en --section lecture --kind file --json
tmci download 31-21-en "week 3" --json
tmci download 31-21-en --all --out ./notes --json
```

With no ref, no filter and no `--all`, the command refuses rather than taking the whole
course.

The output is one array, one entry per selected item, carrying exactly one of `path`,
`link` or `error`:

```json
[
  {"ref": "1.1", "title": "Week 1 slides", "path": "/home/ali/.tmci/downloads/..."},
  {"ref": "1.2", "title": "Reading", "link": "https://example.org/reading"},
  {"ref": "2.1", "title": "Week 2 slides", "error": "..."}
]
```

Scan for `error` keys. The exit code stays 0 whenever at least one file saved, so it tells
you nothing about partial failure.

Files land in `~/.tmci/downloads/<slug>/<section>/<NN theme>/<NN title.ext>` unless `--out`
is set. Size a course with `list contents` before running `--all`; it can be hundreds of
megabytes.

Hand `link` URLs back to the user. `tmci open` launches their default browser.

## Exit codes

| Code | Meaning | Do |
|---|---|---|
| 0 | success | |
| 1 | general error | Read the `error` string. |
| 2 | bad command line | Fix the invocation. |
| 3 | not logged in, or session expired | Ask the user to run `tmci login`. |
| 4 | no such course, theme or content | Re-run the matching `list` and pick a real ref. |
| 5 | LMS page could not be parsed | The site changed. Report it, do not retry. |

Exit 4 messages list near-misses. Correct your own ref before asking the user.

## Never

- Run `tmci login`. It blocks on a human in a browser window.
- Read, print or copy `~/.tmci/config.json`. It holds the live session cookie.
  `tmci config show --json` omits it deliberately.
- Read `tmci raw` output directly. It is the entire unparsed calendar payload for a
  course. Use it only to diagnose a broken parser, and filter it first.
- Run `tmci logout`, `tmci config set` or `tmci setup` unasked. All three change state
  that outlives the conversation.
