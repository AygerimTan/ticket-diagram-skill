---
name: ticket-diagrams
description: >-
  Build a code-verified diagram pack for a ticket, feature or change — several Archify diagrams
  (sequence, architecture, data-flow, lifecycle, workflow) of how the code really works across services, every
  claim pinned to file:line at a git SHA, joined in one tabbed index.html with an honest "checked
  against <ref>, not production" note, published as a private artifact when the session can. Use whenever someone asks to draw, visualize, map or explain a
  ticket's flow (JIRA-123, #456), a cross-service request path, "how does X work now / after this
  change", before-vs-after of a branch, the services/DBs/tables behind a feature, or asks for
  "схемы"/"диаграммы" of a task — even if they name only one flow or never say "pack". Also use it,
  instead of hand-drawn SVG, when a diagram of code goes into an artifact, page or doc ("include the
  diagram into the artifact", "add a diagram to the page"). For one generic diagram with no code to
  verify, use archify directly.
license: MIT
metadata:
  version: "1.3.2"
  archify: "3.1.0"
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
the shell cwd does not persist between calls. Each script's interface is given where it is used —
don't read their source (run one with `--help` if unsure).

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
| `deliver` | `artifact` when the session can publish a private artifact and nobody said not to, else `folder` | How the pack reaches the user — see §4 Delivery |

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
written against archify `3.1.0` (`<archify-dir>/skill-release.json`). Where archify's CLI or
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
  `lifecycle`; pipelines/tables → `dataflow`; processes, CI/CD, runbooks → `workflow`. Also: tables,
  columns and keys a change touches → `erd`; interfaces and their implementations → `class`; module
  or repo layout → `tree`; release or incident order across repos → `timeline`; where a request
  spends its time → `waterfall`, only with real timings (traces, logs) — otherwise don't draw it.
- **Files.** `<slug>.<type>.json` → `<slug>.html`, with `meta.output: "<slug>.html"` (required; a
  relative path, resolved against the pack — see `ARCHIFY` above); before/after:
  `<slug>-before.*`, `<slug>-after.*`.
- **Language.** Configured/request language; code identifiers, routes and tables stay as in code.
  Built-in viewer languages are in `<archify-dir>/locales/` (en, zh-CN, zh-TW, es, ko in 3.1.0).
  For another language set `meta.locale` (e.g. `ru`) **and** copy
  `<archify-dir>/examples/locales/<lang>.json` into `meta.translations` — never a non-built-in
  locale without translations. `finalize` warns `i18n/translation-coverage` with the coverage (ru
  in 3.1.0: 461/486) — say in the index note that the rest of the viewer UI is English (short: "UI
  частично англ."). No catalog for the language → omit `locale` and say the viewer UI is English.
- **Quality.** `meta.quality_profile: "showcase"`. If `finalize` returns
  `layoutReviewRecommendation`, do its one bounded retry.
- **Sources.** `path:line` relative to the repo (or project root). Sequence: also in each message's `note` — archify 3.1.0 shows notes at the default
  zoom, and each one adds height, so keep a note to one line — its `path:line` — and budget it (§3 Size); key
  sources (entry point, deciding branch, the write) also go on cards. Architecture/dataflow connections have no `note` — put their sources in cards. Every card
  item cites its own `path:line` (a basename is fine when unique in the pack); "see evidence.json"
  is not a source. For a single committed repo whose `origin` is an HTTPS URL on GitHub, Gitee or GitLab
  (self-managed too, with `provider: "gitlab"`), also set `meta.repository` (credential-free URL, 40-hex
  revision, `link_mode: "web"`), node `sources`, and pass `--repo-root`: archify then verifies
  those lines itself and turns them into links to `file:line` at that commit — the code links a
  reader expects. A private host needs the reader logged in; say so in the report. An SSH origin
  or another host → `link_mode: "local-only"` (keep the origin as is — never rewrite SSH as HTTPS). It covers nodes only, not edges, and it does not replace
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
  - Sequence: omit `viewBox` and `column_fit` — the canvas grows and columns spread by default.
    With an explicit `viewBox`, message `y` stays in `[160, height − 83]` and height ≥ last
    message `y` + 104 (+ 120 with a `note`); archify names the exact minimum. Notes cost
    44/55/66 px for 1/2/3 lines: nine messages with 2–3-line notes overflowed the first screen in a
    test run; with one-line notes keep to ~6–7 messages, without notes ~8–9.
  - Lifecycle: `schema_version: 3` with `mainPath` (the happy-path state ids, in order); layout is
    automatic — no lanes, columns or `viewBox` (a 3.0 v2 file fails validation). Write state
    labels in the pack's language.
  - Dataflow: ≤4 stages per diagram with short labels; omit `viewBox` and node widths so archify
    fits the canvas and keeps text readable (showcase growth applies only then). Flows need
    labels (archify suggests `labelAt`/`labelDy` on overlaps). More than 2–3 labelled flows into
    or out of one node rarely cleared archify's label checks — merge sources or split the diagram.

Finalize every diagram in **one** shell call, one after another — archify holds one lock per
output directory, so a parallel run fails with `delivery/concurrent-attempt`:

```bash
cd <pack> && mkdir -p checks && for s in <slug>:<type> <slug2>:<type2>; do slug=${s%%:*}; type=${s##*:}
  node <archify-dir>/bin/archify.mjs finalize "$type" "$slug.$type.json" "$slug.html" \
    --quality showcase --out-dir "checks/$slug.review-<n>" --json > "checks/$slug.finalize.out" \
    && echo "PASS $slug" || echo "FAIL $slug"; done
```

`finalize` validates, delivers, checks and browser-checks, stopping at the first failing gate.
`FAIL` means the HTML is not accepted even if `deliver` already replaced it: read that slug's
`checks/<slug>.finalize.out`, fix the JSON and rerun only that slug, into a **new** `review-<n>`
dir (reusing one after the HTML changed fails with `viewer/evidence-path-conflict`). Don't
pre-run `validate`; standalone commands are for diagnosis. A deliver-stage failure can also leave
`*.delivery-pending.json`, which blocks every checker until a later delivery passes. Never move
`<slug>.delivery.json`: it must stay next to the HTML for provenance checks.

When all pass, take every diagram's images in **one** shell call:
`ARCHIFY visual-check <slug>.html --summary --require-provenance --out-dir checks/<slug>.review-<n>`
(review evidence, not a gate; its PNGs are the only image export you can produce from the shell) and
`python3 SKILL_DIR/scripts/screenshot.py <pack>/<slug>.html <pack>/checks/<slug>.page.1440x830.png 1440x830`.
Look at each page shot yourself — the receipts don't judge readability: diagram and legend on
the first screen, legend labels not running into each other. Open the visual-check PNGs only when
a diagnostic points at layout. `viewer/viewport-overflow` (or `viewer/diagram-clipped`) means split
or compact the diagram. Report unresolved diagnostics truthfully.

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

**Delivery.** Told not to publish, or asked for files → `deliver: folder`, mode by page count
(above); only a request that itself asks for an artifact or page still gets the bundle you would
have published. Otherwise `deliver: artifact` (the default when the session has a tool that publishes a
private artifact or page — e.g. Claude Code's Artifact tool; never a file host or a browser
automation): build with `--mode bundle` and, once §6 passes, publish that one `index.html` privately — it is a
finished page, so publish the file as is, no template. A tabs index loads sibling files, which a
single published page doesn't have, so its tabs would come up empty. The local pack stays: it holds
the evidence and receipts. To update, republish the same file if the tool keeps the URL that way.
Archify's **Copy link** (focused node, relation, route, lens) inside a bundle points at the index:
`<index>#tab=<i>[&era=<id>]&reader=<state>`, and opening that address restores the tab, era and
focus. The address is the manifest's `"url"` if set, else wherever the index was opened from. After
the first publish, put the artifact link in `"url"`, rebuild and republish the same file — without
it a published copy hands out the host's internal frame address. claude.ai passes neither `#…` nor
`?…` into an artifact, so for a claude.ai `url` the copy is the artifact link plus where to go
(`<url> — tab «X», era «Y», node «Z»`, in the manifest's `lang`, ru or en); a copy built with a local or
self-hosted `url` keeps the full deep link. Say so in the report.
Publishing distributes the pack: it must carry no secrets or personal data (§2). No such tool, no
private visibility, or the upload is refused (too large) → `deliver: folder` (keep the bundle you
built), and say why. Repeat the §6 click-check on the published copy where you can open
it.

If the request names an existing artifact or page, the pack still goes out as its own artifact (a
CSP-locked bundle, not a fragment to splice in); once it has a URL, reference it from the existing
one (a link where the host allows links, otherwise the title). A doc that can't host HTML gets the
dark 1440×900 PNGs from the latest `checks/<slug>.review-<n>/`, the note text under them and a
pointer to the pack (URL or path) — a diagram without the note reads as production truth. Don't
redraw the diagrams by hand — that drops the code checks. Where the host sandboxes the page without
downloads (claude.ai artifacts do), Archify's PNG/SVG download exports won't work; say so in the
report.

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

Report briefly: the artifact URL and its visibility (or the index path), mode, tabs, per-diagram archify status, any skipped step (e.g.
archify's update check), evidence counts (ok/moved/missing/dirty/untracked), the UNVERIFIED list,
which screenshots you looked at. Beyond the delivery above, don't link the pack from
docs, wikis or notes as a side effect — offer it.
