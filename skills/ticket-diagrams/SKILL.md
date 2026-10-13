---
name: ticket-diagrams
description: >-
  Build a code-verified diagram pack for a ticket, feature or change — several Archify diagrams
  (sequence, architecture, data-flow, lifecycle, workflow) of how the code really works across services, every
  claim pinned to file:line at a git SHA, joined in one tabbed index.html with an honest "checked
  against <ref>, not production" note. Use whenever someone asks to draw, visualize, map or explain a
  ticket's flow (JIRA-123, #456), a cross-service request path, "how does X work now / after this
  change", before-vs-after of a branch, the services/DBs/tables behind a feature, or asks for
  "схемы"/"диаграммы" of a task — even if they name only one flow or never say "pack". For one
  generic diagram with no code to verify, use archify directly.
license: MIT
metadata:
  version: "1.1.0"
  archify: "3.0.1"
---

# Ticket diagrams

A pack answers one question for a teammate: *what does this change's code actually do, across
services?* It is a folder of Archify diagrams plus an `index.html` that tabs between them, with
optional Before / After eras.

The value of a pack is that it is **true to the code at a named commit**. A pretty diagram that
guesses is worse than none — the reader trusts it. Most of the work is reading code; drawing is the
short part. Docs, tickets and wikis are *hints* about where to look, never proof.

Scripts live next to this file. Below, `SKILL_DIR` means this skill's directory and
`ARCHIFY` means `cd <pack> && node <archify-dir>/bin/archify.mjs` — archify resolves `meta.output`
against the working directory, so it runs from the pack. Use absolute paths in every other command:
the shell cwd does not persist between calls.

## 0. Setup — config and tools

**Config.** Read the first that exists: `<repo>/.claude/ticket-diagrams.json`, then
`~/.claude/ticket-diagrams.json`. Every field is optional; missing ones fall back to the default.
What the user says in the request (language, output dir, refs) beats the config — and the language
the request is written in counts as saying it: config `language` applies only when the request
gives no cue (a bare ticket id, a link). A global config
describes the user's usual work: when it names `code_roots` and the target project is outside them,
ignore its `docs`, `examples` and `note_template` (they belong to other code) and say so.

| Field | Default | Meaning |
|---|---|---|
| `output_dir` | `<current repo>/diagrams/{slug}`; outside a repo, ask | Where packs go. `{slug}` = ticket id lowercased, or a short topic slug |
| `language` | language of the request | Labels, notes, cards, index note |
| `code_roots` | current repo | Where the services' checkouts live (for cross-repo flows) |
| `worktrees` | none | Pattern for ticket checkouts, e.g. `{repo}/.claude/worktrees/{ticket}` |
| `docs` | none | Paths or URLs of design docs/notes to skim for context |
| `examples` | none | Earlier packs the user likes — follow their tone and depth, not their geometry (§3 sizes win) |
| `note_template` | see §4 | Honesty line; placeholders `{refs}` (heads as `repo@ref sha`), `{date}`, `{not_checked}` |

A pack inside a repo is untracked noise in `git status` (~2 MB per diagram: page ~0.8 MB, checks
~1 MB or more) — mention it, and suggest a `.gitignore` entry or an `output_dir` outside the repo.

Ask only what you can't default: the code location (and the before/after refs, if they want a
comparison) when neither the request nor config gives it, and where to save when the current
directory is not a repo (never drop a pack into a random cwd). Everything else uses the defaults —
say which you used in the report. If you asked, offer to save the answers to
`~/.claude/ticket-diagrams.json` so next time is silent. Never invent a convention the user didn't
state.

**Archify.** Find it at the first existing of: an `archify` skill dir the session already lists,
`~/.claude/skills/archify`, `~/.agents/skills/archify`, `<repo>/.claude/skills/archify`. Then load
its `SKILL.md` — it owns schemas, layout, validation and delivery. Not installed → stop and tell the
user: it is MIT, from https://github.com/tt-a1i/archify; don't hand-draw a substitute. This skill was
written against archify `3.0.1` (`<archify-dir>/skill-release.json`). Where archify's CLI or
`SKILL.md` contradicts §3, archify wins — follow it and report the drift. Archify's own default
folder (`.archify/…`) does not apply: the pack's `output_dir` is the location the user named.
`deliver`/`finalize` run archify's update check inside their receipt; when the run must not touch
the network or write outside the pack, set `ARCHIFY_UPDATE_CHECK_DISABLED=1` and say so. Otherwise,
if a receipt says `update.noticeRequired`, relay it once per pack.

**Tools.** git ≥ 2.24 (when the code is in a repo), Python ≥ 3.7, node ≥ 18, Chrome/Chromium/Edge.
Point both archify and `screenshot.py` at a browser with `ARCHIFY_CHROME`; on Linux as root or in a
container add `ARCHIFY_CHROME_NO_SANDBOX=1`. On Windows use `python` and spell out the home path
instead of `~`. Code outside git works — it just can't be pinned to a commit, only to file hashes.
Each script has a `--selfcheck`.

## 1. Pin scope

From the request, config, or one batch of questions:

- **Flows** — which user-visible flows or topologies become tabs.
- **Code per repo** — which checkout and ref. A before/after pack needs two refs per changed repo.
  "After" is the change branch. "Before" is where that branch left its base:
  `git merge-base <branch> <base>`, not the base's current tip, which may have moved on. Pick the
  base in this order: the target branch the user, MR or ticket names → the repo default
  (`git symbolic-ref refs/remotes/origin/HEAD`, else `git remote show origin` → "HEAD branch") →
  ask. Don't assume `origin/main`. Say in the note which base the merge-base was taken against.
  If they have no ticket checkout, the branch ref is enough. No ticket and no comparison → one
  state: the working tree, pinned at HEAD, no eras. "How it works now" for a ticket branch → draw
  the branch HEAD, say so in the note, and if the base differs materially, say that on a card and
  offer a before/after pack.
- **Hops outside the named repos** — a gateway config, a shared library, an infra repo. Read and
  cite them like any other repo and list them in the note. If their source isn't available (an
  uninstalled `vendor/` package), name the package and locked version and mark the hop UNVERIFIED;
  if a vendored package is its own git checkout, check its HEAD matches the lock file. A hop repo
  with its own branch for the same ticket: draw what was asked, mention that branch on a card.
- **Context** — skim configured `docs`, the ticket text if pasted, the repo's README/CLAUDE.md/ADRs.
  Use them to find entry points faster; don't repeat their claims unless the code confirms them.
  Configured `docs` can hold private notes — nothing from them goes into the pack.

If the request's premise doesn't match the code ("how the reply reaches the customer" when nothing
sends one), draw what the code does and state the mismatch on a card and in the report.

Never overwrite an existing pack silently; add files or ask.

## 2. Trace the code, collect claims

Read without changing checkouts. For a ref that isn't checked out, read with `git show <ref>:<path>`.

Trace each flow end to end — entry route → handlers → services → DB/queues → external calls →
what comes back. Every arrow you intend to draw is a claim. Write them to `<pack>/claims.json`:

```json
[{"claim": "gateway drops pickup_days", "file": "/abs/path/gateway/orders/handler.go", "line": 88,
  "needle": "PickupDays"},
 {"claim": "before: unknown locale fell back to en", "file": "/abs/path/api/src/locale.rs", "line": 12,
  "needle": "\"en\"", "ref": "origin/main"}]
```

`ref` makes the script read and pin that commit; without it the working tree is read and HEAD
pinned. Code outside git gets head `no-git` and is pinned only by each file's sha256 — the note then
says so instead of SHAs (en: "not a git repo; pinned by file hashes in evidence.json" / ru: "не
git-репозиторий; закреплено хешами файлов в evidence.json"). Then:

```bash
python3 SKILL_DIR/scripts/evidence.py <pack>/claims.json <pack>/evidence.json --scope "origin/main + branch; no production access"
```

One claims/evidence file per pack, before and after together. `heads` in the output
(`api@origin/main`, `api:TICKET-1`, …) is what the index note cites.

| Status | Do |
|---|---|
| `moved` | Fix the line number (`found_line` is the nearest hit; check `also_at` for the right one), rerun |
| `missing` | See `reason`: malformed claim, wrong needle, file absent, ref not a commit — re-read the code |
| `dirty` | Uncommitted edits: say so in the note, or cite a committed ref |
| `untracked` | Gitignored or never committed (e.g. `vendor/`): HEAD says nothing about it — cite the file's real source (its own repo, a lock-file version), or mark the claim UNVERIFIED |

A needle that also matches other lines is listed in `also_at`. When it is a fragment that also
matches *different* code in another function or block, tighten it — there it could be pinning the
wrong code. When the whole line is identical elsewhere (repeated fields, config entries, the same
call in two functions, or no longer substring is unique), keep it: the line number is what
disambiguates. `evidence.py` exits 1 if any claim is not `ok`.

Never copy secrets or personal data into the pack: tokens and keys turn up in configs, lock files
and `.env` examples; names, phones and messages in data files, logs, fixtures — and sometimes in code
(name lists in regexes, sample tickets in string literals). Claims and needles land verbatim in
`claims.json` and `evidence.json`, so never take a needle from such a line; cite data files, logs,
reports and those code lines by path. Describe the hop ("auth via token from env"), not the value.

A negative ("nothing calls X") has no line to pin: say on a card how you checked (the grep) and mark
it UNVERIFIED.

Card sources are claims too: add them to `claims.json` and rerun `evidence.py` once the cards are
final.

Anything not visible in code — clients you don't have, real servers, env values, DB contents —
goes into the diagram marked **UNVERIFIED**, never drawn as fact. Parallel read-only agents are
fine for several repos at once; you still pin their `file:line` with the script.

## 3. Draw each diagram with Archify

Follow archify's fast authoring path. Pack-specific choices on top of it:

- **Type.** Request chains → `sequence`; services/DBs → `architecture`; status machines →
  `lifecycle`; pipelines/tables → `dataflow`; processes, CI/CD, runbooks → `workflow`.
- **Files.** `<slug>.<type>.json` → `<slug>.html`, with `meta.output: "<slug>.html"` (required; a
  relative path, resolved against the pack — see `ARCHIFY` above); before/after:
  `<slug>-before.*`, `<slug>-after.*`.
- **Language.** Configured/request language; code identifiers, routes and tables stay as in code.
  For a language other than `en`/`zh-CN`, set `meta.locale` (e.g. `ru`) **and** copy
  `<archify-dir>/examples/locales/<lang>.json` into `meta.translations` — never a non-built-in
  locale without translations. `finalize` records the coverage in its receipt
  (`checks/<slug>.review-<n>/<slug>.finalize.json`; ru in 3.0.1: 423/438 keys) — say in the index
  note that the rest of the viewer UI is English (short: "UI частично англ."). No catalog for the
  language → omit `locale` and say the viewer UI is English.
- **Quality.** `meta.quality_profile: "showcase"`. A sequence with ≥5 participants →
  `meta.column_fit: "spread"` and a viewBox width around 1000–1100: wider failed
  `composition/desktop-readability` in test runs. If `finalize` returns
  `layoutReviewRecommendation`, do its one bounded retry.
- **Sources.** `path:line` relative to the repo (or project root). Sequence: also in each message's
  `note` — but archify hides notes at the default zoom (sequence and lifecycle alike; shown at ≥175%
  zoom, on focus or hover) — so key sources (entry point, deciding branch, the write) go on cards
  too. Architecture/dataflow connections have no `note` — put their sources in cards. Every card
  item cites its own `path:line` (a basename is fine when unique in the pack); "see evidence.json"
  is not a source. For a single committed repo with an `origin`, also set `meta.repository`
  (credential-free URL, 40-hex revision, and `link_mode: "local-only"` unless the origin is a
  canonical GitHub/Gitee HTTPS URL — otherwise `repository-evidence/links-unsupported`) and node
  `sources` and pass `--repo-root`: archify then
  verifies those lines itself. It covers nodes only, not edges, and it does not replace
  `evidence.py`. Outside git it is unavailable.
- **Cards.** 2–3: what is drawn; what is code fact vs UNVERIFIED. Keep each to ~3 items of ~60
  chars; archify's overflow diagnostics name the exact px to trim.
- **Title.** `meta.title` on one line, ~30 chars: longer titles wrapped at 1440 wide.
- **Variants.** Arrow variants carry fixed legend meanings. `dashed` = async; `security` (policy,
  PII checks) and sequence `return` also render dashed. Use `dashed` only for real async/queued
  work. `meta.legend.entries` may reword or hide an entry but must keep its meaning (archify: labels
  never change semantics); with `meta.translations` the default labels are already localized, but
  longer ones can run into the next legend swatch while every gate passes — check the legend in your
  page shot and shorten via `meta.legend.entries`. Node/state types are legend entries too: pick
  them by legend meaning (files on disk are not a `database`; a checker is not `security`). No
  variant means "unverified" or "fails": put "?" or "✗" in the label and explain on a card.
- **Labels.** In archify's label font (JetBrains Mono) Cyrillic `п`/`л` read as `n` at label size —
  `поле` looks like `none` in screenshots while the HTML text is intact. In short labels prefer
  words without them; don't "fix" the JSON for it.
- **Proxies.** Draw a transparent proxy (e.g. an API gateway) on the way in; draw the response
  straight back to the caller, skipping its return hop — it costs height and says nothing.
- **Size.** The viewer scales a diagram to the page width, so at 1440×830 its panel is about
  1355 × (height / width) px. Aim for the diagram and its legend on the first screen; cards then
  start just below it — that is expected in archify 3, don't chase it with wider viewBoxes (they
  fail readability). A diagram that doesn't fit becomes numbered tabs ("1 · OTP",
  "2 · Account"); a full-length tab is optional and labelled as scrolling.
  - Sequence: message `y` in `[160, height − 83]`, and the canvas needs room for the legend:
    height ≥ last message `y` + 104, or + 120 when it has a `note` (activations and segments can
    push it further; archify names the exact minimum), or omit `viewBox` and let it grow. Roughly
    ≤8–9 messages at a 34–40px step.
  - Lifecycle: `schema_version: 2`, omit `viewBox` (the canvas sizes itself). One row per lane —
    `main` first (required), `terminal` last — titled from `lanes[].label`, so write labels in the
    pack's language. `col` 0–4 is a shared grid; put an interruption or exit in the column of the
    state it leaves. In test runs a v2 lifecycle was the one type that kept its cards on the first
    screen.
  - Dataflow: ≤4 stages per diagram with short labels; rows sit at y 128/242/356/…, so two rows
    need a viewBox height of ~380+, three ~490+. Keep the `viewBox`: in a test run the default canvas
    shrank text. Flows need labels (archify suggests `labelAt`/`labelDy` on overlaps). More than 2–3
    labelled flows into or out of one node rarely cleared archify's label checks — merge sources or
    split the diagram.

Per diagram, one diagram at a time (archify locks the output dir):

```bash
ARCHIFY finalize <type> <slug>.<type>.json <slug>.html \
  --quality showcase --out-dir checks/<slug>.review-<n> --json
```

`finalize` validates, delivers, checks and browser-checks, stopping at the first failing gate; a
non-zero exit is failure — fix the JSON and rerun it whole, into a **new** `review-<n>` dir (reusing
one after the HTML changed fails with `viewer/evidence-path-conflict`). Don't pre-run `validate`;
standalone commands are for diagnosis. A non-zero exit means the HTML is not accepted even
if `deliver` already replaced it; a deliver-stage failure can also leave `*.delivery-pending.json`,
which blocks every checker until a later delivery passes. Never move `<slug>.delivery.json`: it
must stay next to the HTML for provenance checks.

If `finalize` reports `internal/unclassified` "Renderer failed before emitting a structured
diagnostic" on a pack with `meta.translations`, archify misread its own coverage line (3.0.1). See
the real error by running the renderer directly —
`ARCHIFY_QUALITY_PROFILE=showcase node <archify-dir>/renderers/<type>/render-<type>.mjs <json>
<pack>/checks/probe.html` — or by validating a copy without `locale`/`translations`.

After it passes, get images to look at (archify calls this review evidence, not a gate):
`ARCHIFY visual-check <slug>.html --summary --require-provenance --out-dir checks/<slug>.review-<n>`.
Look at `<slug>.visual-check.1440x900.dark.png` there yourself — the receipt does not judge
readability — and shoot the page at the index viewport:
`screenshot.py <html> <pack>/checks/<slug>.page.1440x830.png 1440x830`. `viewer/viewport-overflow`
(or `viewer/diagram-clipped`) means split or compact the diagram. A pass with an auto-sized canvas
may still scroll vertically — archify accepts that, so your 1440×830 shot is what tells you whether
the diagram is on the first screen. Report unresolved diagnostics truthfully.

Every helper or temporary file tied to the pack (claim generators, receipts, page shots, probes) goes
in `<pack>/checks/` — never in a shared scratchpad, where a parallel run can overwrite it, and never
in the repos. Delete superseded `review-<n>` dirs at the end.

## 4. Build the index

`<pack>/manifest.json`:

```json
{
  "title": "Order cancel · PROJ-123",
  "lang": "en",
  "note": "Checked against code: api@<sha> (merge-base with origin/main), api:PROJ-123 <sha>, <date>. Not a statement about production. Not checked: mobile client.",
  "eras": [{"id": "before", "label": "Before"}, {"id": "after", "label": "After"}],
  "tabs": [
    {"label": "1 · Cancel", "files": {"before": "cancel-before.html", "after": "cancel-after.html"}},
    {"label": "Tables", "file": "tables.html"}
  ]
}
```

Omit `eras` for a single-state pack. A `file` tab is the same in every era; a `files` tab switches.

```bash
python3 SKILL_DIR/scripts/build_index.py <pack>/manifest.json   # --mode tabs|bundle overrides
```

- **tabs** (≤4 pages, no eras) — tiny `index.html`, iframes load sibling files. Share the folder.
- **bundle** (eras, or >4 pages) — every page inlined into one sandboxed, CSP-locked file
  (~0.8 MB per diagram). Share one file.

The **note** (plain text) is the honesty line: refs and SHAs from `heads`, date, what was *not*
checked. The index shows it on one line and cuts the rest behind "…", so keep it under ~200 chars,
refs and "not checked" first; details go on cards. Over budget: shorten "not checked" to keywords,
then drop the date (it is in `evidence.json`) — never the refs or the disclaimer. Default
wording — en: "Checked against code: … Not a statement about production." / ru: "Сверено с кодом: … Не подтверждение прода." For a project
with no production — en: "Not a statement about any deployment or run." / ru: "Не утверждение о
запуске или проде." Use `note_template` if configured. The note never says or implies production
state.

## 5. Extra pages — only on request

Risks ("closed in code / still open"), country or data tables and other non-diagram tabs are
hand-written HTML in the pack: dark background, cards, a small source line under each claim. Same
evidence rule — each claim gets a source or UNVERIFIED. Make them only when asked.

## 6. Check, then report

```bash
python3 SKILL_DIR/scripts/screenshot.py <pack>/index.html <pack>/checks/index.check.png 1440x900
```

Look at it — the first tab's diagram must be visible, unclipped, under the index chrome; the other
pages were shot at 1440×830 in §3. For eras, also check the other era: rebuild with `--default-era <other-id>`,
shoot, then rebuild without the flag (the manifest's `default_era`, or the last era, applies again).
For a bundle, click every tab and era with `agent-browser`/playwright if available — srcdoc pages
can fail silently. Fix what you see.

Report briefly: index path and mode, tabs, per-diagram archify status, any skipped step (e.g.
archify's update check), evidence counts (ok/moved/missing/dirty/untracked), the UNVERIFIED list,
which screenshots you looked at. Don't link the pack from docs, wikis or notes as a side effect —
offer it.
