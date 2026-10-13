# ticket-diagrams

A Claude Code skill that turns "draw how this ticket's code works" into a pack of
[Archify](https://github.com/tt-a1i/archify) diagrams. Every arrow is checked against the code at a
named commit (`file:line`, pinned by SHA), and one `index.html` tabs through the diagrams, with
optional Before / After eras. The pack never claims anything about production.

## Requirements

| Tool | Version | Used for |
|---|---|---|
| Archify skill | written against `2.17.0-dev.1` | schemas, rendering, validation, visual check |
| node | ≥ 18 | Archify CLI |
| Python | ≥ 3.7 (stdlib only) | `scripts/*.py` |
| git | ≥ 2.24 | pinning claims to commits (code outside git also works, pinned by file hash) |
| Chrome / Chromium / Edge | any recent | screenshots and Archify's visual check |

Set `ARCHIFY_CHROME=/path/to/browser` when the browser isn't in a standard place. Both Archify and
`screenshot.py` read it. On Linux as root or in a container, also set `ARCHIFY_CHROME_NO_SANDBOX=1`.

## Install

One command — installs Archify (required, MIT) and this skill for Claude Code, user-wide:

```bash
npx skills add tt-a1i/archify -g -a claude-code -y && npx skills add AygerimTan/ticket-diagram-skill -g -a claude-code -y
```

This puts both skills in `~/.claude/skills/`. The command installs the current Archify stable
(3.0.1 at the time of writing), while §3 of `SKILL.md` was validated against `2.17.0-dev.1` —
where they disagree, Archify's own `SKILL.md` wins.

Restart Claude Code, then check:
`cd ~/.claude/skills/ticket-diagrams && python3 scripts/evidence.py --selfcheck &&
python3 scripts/build_index.py --selfcheck && python3 scripts/screenshot.py --selfcheck`.

Then ask Claude something like "draw how PROJ-123's order cancel works across services" or
"before/after diagrams for branch feat/x".

## Config (optional)

`<repo>/.claude/ticket-diagrams.json` or `~/.claude/ticket-diagrams.json`:

```json
{
  "output_dir": "~/diagrams/{slug}",
  "language": "en",
  "code_roots": ["~/src/backend", "~/src/frontend"],
  "worktrees": "{repo}/.claude/worktrees/{ticket}",
  "docs": ["~/notes/architecture"],
  "note_template": "Checked against code {refs}, {date}. Not a statement about production. {not_checked}"
}
```

Without a config, packs go to `<current repo>/diagrams/<slug>`. Each diagram adds about 1.5 MB, so
add `diagrams/` to `.gitignore` or set `output_dir`. The request always beats the config. A global
config's `docs`, `examples` and `note_template` are ignored for projects outside its `code_roots`.

## Scripts

| Script | Does |
|---|---|
| `scripts/evidence.py` | Checks `claims.json` (claim, file, line, needle, optional ref) against the code and writes `evidence.json` with statuses and pinned SHAs. Exits 1 if any claim isn't `ok`. |
| `scripts/build_index.py` | Builds `index.html` from `manifest.json`: light iframe tabs, or one sandboxed, CSP-locked bundle. |
| `scripts/screenshot.py` | Headless-browser screenshot of a page at a given size. |

## Evals

`evals/evals.json` holds two test prompts that run wherever this skill and Archify are installed:
diagram Archify's own `deliver` command (English; the prompt asks whether Archify is a git checkout),
and diagram this skill itself (Russian, checks a non-English pack; a plain copy, so it also tests
pinning by file hashes). `evals/grade.py <iteration-dir>` grades runs laid out the way skill-creator
lays them out (`eval-<id>-<name>/<config>/run-<n>/outputs/`); add your own prompts against your
repositories in a separate file and pass it with `--evals`.

## Archify changes

Section 3 of `SKILL.md` names Archify flags, file names and layout limits as of `2.17.0-dev.1`. If
Archify's CLI or its `SKILL.md` disagrees, Archify wins, and the skill tells the model to report the
drift.

## License

MIT, see `LICENSE`. Archify is a separate MIT project by its authors and is not bundled here.
