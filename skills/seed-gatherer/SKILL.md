---
name: seed-gatherer
description: |
  Bidirectional with `intent-aligner` in the chain (intent-aligner ⇄
  seed-gatherer → plan-establisher → codebase-planner →
  codebase-implementer). Default path reads an existing
  `intent.<slug>.md` and extracts intent-filtered content from user-
  supplied web/youtube URLs and local file paths (PDF, image, doc,
  code), emitting one md+html seed pair per resource under
  `ai-artifacts/seeds/`.
  When no intent exists, the **bootstrap path** captures intent ad-hoc
  (prompt / URL / file) and emits `ai-artifacts/intents/intent.<slug>.{md,html}` alongside
  seeds in the same commit. When the user has no external resources,
  **ideation mode** crystallizes ideas through AI/user dialogue plus
  feasibility checks — each idea becomes its own seed. Iteratively
  re-runnable; each invocation appends seeds across its own
  worktree+merge cycle. Manual invocation only — `/seed-gatherer`.
disable-model-invocation: true
---

# Seed Gatherer

## Overview

Take the intent captured by `/intent-aligner` (or bootstrap it ad-hoc
within this run) and grow a corpus of intent-filtered evidence. The
user pastes URLs and/or absolute local file paths, OR provides no
external material and lets ideation+feasibility-checks crystallize
ideas. The skill filters content through the intent's rubric (Goal,
In-scope features, Out-of-scope, Constraints, Success criteria, Open
questions) and emits two artifacts per resource:

| Output | Audience | Purpose |
|---|---|---|
| `ai-artifacts/seeds/seed.<intent-slug>.<resource-slug>.md` | AI (next-hop is `plan-establisher`) | Structured seed — source provenance, intent-filtered extract, relevance rationale |
| `ai-artifacts/seeds/seed.<intent-slug>.<resource-slug>.html` | Human (browser-openable) | Self-contained verification doc, no CDN, HTML-escaped |

The skill is **iteratively re-runnable**: each invocation runs in its
own worktree+merge cycle and seeds accumulate in `ai-artifacts/seeds/`.
`plan-establisher` globs `ai-artifacts/seeds/seed.<intent-slug>.*.md` for one intent.

Three Phase 1 / 2 branches encode bidirectionality with intent-aligner:

- **`standard`** — existing `ai-artifacts/intents/intent.<slug>.md`; user provides
  URLs/files; seeds only.
- **`bootstrap`** — no intent file; user supplies prompt/URL/file ad-hoc;
  emits `ai-artifacts/intents/intent.<slug>.{md,html}` (rev 1) **plus** seeds in one merge.
  Spec: [references/intent-bootstrap.md](references/intent-bootstrap.md).
- **`ideation`** — Phase 2 ends with 0 resources (or user types `ideate`);
  AI/user dialogue + feasibility checks crystallize one seed per idea.
  Spec: [references/ideation-mode.md](references/ideation-mode.md).

`bootstrap` + `ideation` compose — bootstrap captures intent, Phase 2
ideation produces seeds, all in one merge.

`disable-model-invocation: true` — the skill has side effects. Never auto-trigger.

## Workflow Decision Tree

```
Phase L: Dialog language — references/language-selection.md
Phase 0: Detect repo state (on-dev | on-default-needs-dev |
         on-nonbase-main-checkout | inside-seed-worktree [resume] |
         inside-other-worktree | unrelated)
Phase 1: Intent selection ──┬─ ≥1 ai-artifacts/intents/intent.<slug>.md exists ─── auto-pick / menu → RUN_MODE=standard
                            ├─ 0 found, user opts bootstrap ── Phase 1b (intent-bootstrap.md) → RUN_MODE=bootstrap
                            └─ 0 found, user opts abort ────── exit cleanly
Phase 2: Resource intake loop ──┬─ user pastes URL/path ─── classify + append
                                ├─ user types `done` w/ 0 resources ── offer ideation (ideation-mode.md)
                                ├─ user types `ideate` mid-intake ──── enter Phase 2i
                                └─ user types `done` w/ ≥1 resource ── proceed to Phase 3
Phase 2i: Ideation dialogue + feasibility checks (one seed per idea) — references/ideation-mode.md
Phase 3: Per-resource extraction + synthesis preview + `confirm seeds` gate
Phase 4: Worktree creation (FIRST mutation) — .worktrees/seed-<intent-slug>-<id>/
Phase 5: Emit seeds (+intent in bootstrap) + commit
Phase 6: Human gate + merge — markers per RUN_MODE; see references/git-worktree-flow.md
```

## State variables

Captured during Phases L–4, threaded through later phases, all
persisted per [references/state-and-resume.md](references/state-and-resume.md):

- `LANGUAGE` — dialog language (`Korean` default | `English`); see
  [references/language-selection.md](references/language-selection.md).
- `MAIN_CHECKOUT`, `BASE_BRANCH` (default `dev`).
- `RUN_MODE` — `standard` | `bootstrap` | `ideation` | combos like
  `bootstrap, ideation`. Set during Phase 1 / Phase 2 branching.
- `INTENT_SLUG` — at Phase 1 from existing intent OR Phase 1b.4 (bootstrap).
- `INTENT` — parsed 6 rubric fields (standard) or freshly-synthesized
  intent object (bootstrap) per [references/intent-loading.md](references/intent-loading.md).
- `SEED_RUN_ID` — stable run handle; end of Phase 1; reused as worktree suffix.
- `RESOURCES` — in-memory list (extracted_content, rationale, plus
  `feasibility_check` for ideation entries); populated at Phases 2–3,
  persisted at Phase 4.
- `BOOTSTRAP_SOURCES` — bootstrap-only; ad-hoc inputs (prompt/URL/file)
  from Phase 1b.1.

---

## Phase L — Dialog language (preamble, runs before Phase 0)

Detect `LANGUAGE` from the invocation utterance (Korean default,
English fallback), echo + confirm with the user, capture. Persist to
`.seed-state.json` at Phase 4; hold in memory until then. Mid-flow
switches supported. Full rules — echo strings, override behavior, what
is / isn't translated (notably: seed-markdown field NAMES stay English
for the plan-establisher parser; field VALUES follow `LANGUAGE`;
verbatim source quotes stay in the source's own language; merge marker
`(seeds, human-confirmed)` stays English):
[references/language-selection.md](references/language-selection.md).

---

## Phase 0 — Repo state detection

Run the read-only inspector via the skill-directory variable (the
bundled script is **not** at the user's project root):

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/inspect_repo_state.sh"
```

Parse the JSON. The `state` field classifies into:

| State | Meaning | Action |
|---|---|---|
| `on-dev` | on `dev` branch in `MAIN_CHECKOUT` | proceed to Phase 1 |
| `on-default-needs-dev` | on `main`/`master`, no local `dev` | run the "create dev from `<default_branch>`?" dialog from [references/git-worktree-flow.md](references/git-worktree-flow.md) |
| `on-nonbase-main-checkout` | on a non-`dev` non-default branch in the main checkout | refuse and ask user to switch to `dev` |
| `inside-seed-worktree` | cwd is inside a `*/.worktrees/seed-*` worktree | resume from `.seed-state.json` if present, else refuse |
| `inside-other-worktree` | inside a non-seed linked worktree (intent / planner / implementer / scaffold / unknown) | refuse, instruct user to run from `MAIN_CHECKOUT` |
| `unrelated` | not in a git repo, detached HEAD, repo with no commits, or otherwise unclassifiable | refuse, surface the `reason` field from the JSON |

Capture from JSON: `MAIN_CHECKOUT`, `default_branch`. Set
`BASE_BRANCH=dev` by default (configurable via dialog if the user
objects).

**Gate**: capture `MAIN_CHECKOUT` + `BASE_BRANCH` before Phase 1.

---

## Phase 1 — Intent selection (or bootstrap)

Discover intents: `ls -1 "${MAIN_CHECKOUT}"/ai-artifacts/intents/intent.*.md 2>/dev/null`.

| Match count | Action |
|---|---|
| 0 | Offer bootstrap or abort — see Phase 1b below |
| 1 | auto-pick; echo slug + Goal; wait for `confirm intent` (or `revise` / `bootstrap` to override — bootstrap creates a sibling intent) |
| ≥2 | numbered menu of slugs + Goal; prompt: *"Type the number, `bootstrap`, or `abort`."* |

**Standard branch** — parse the chosen intent per
[references/intent-loading.md](references/intent-loading.md) into the
6-rubric `INTENT` representation. Surface parse defects; never
silently fill in. Set `RUN_MODE=standard`.

**Phase 1b — Bootstrap branch**: capture intent ad-hoc from
prompt/URL/file, run focused gap-filling, capture `PROJECT_SLUG`,
gate on `confirm intent`. Full flow:
[references/intent-bootstrap.md](references/intent-bootstrap.md). Set
`RUN_MODE=bootstrap`.

Compute `SEED_RUN_ID="$(date +%s | tail -c 6)-$$-${RANDOM}"` at end of
phase (reused as worktree suffix). In bootstrap, also derive
`bootstrap_intent_id` from `SEED_RUN_ID` for the intent's Intent ID.

---

## Phase 2 — Resource intake loop

Iterate. Each round:

```
Paste a resource (URL or absolute file path), or `done` to finish.
Supported: web URL, YouTube URL, PDF, image, local doc (md/txt/rst),
local code. Relative paths not accepted — please use absolute.
```

For each input:

1. Classify per the table in
   [references/resource-extraction.md#resource-type-classification-phase-2](references/resource-extraction.md).
2. If unrecognized → refuse, ask the user to provide a URL or absolute
   path with a recognized extension.
3. Derive `resource_slug` per [references/seed-naming.md](references/seed-naming.md).
4. Echo: *"Recognized as `<type>`: `<location>` → slug `<resource_slug>`. Add another, or type `done` when finished."*
5. Append `{type, location, resource_slug, status: "pending"}` to
   `RESOURCES`.

**Mid-intake `ideate`** — user can type `ideate` (or `ideation`) at any
round to switch into Phase 2i (ideation dialogue + feasibility checks).
Full flow: [references/ideation-mode.md](references/ideation-mode.md).

**Termination on `done`**:

| State | Action |
|---|---|
| `RESOURCES` non-empty | proceed to Phase 3 |
| `RESOURCES` empty | offer ideation: *"No external resources. Enter ideation mode (`1`/`ideate`) or exit (`2`/`exit`)?"* Silence is not yes. |

Phase 2i sets `RUN_MODE` to `ideation` (or appends `, ideation` if
upstream Phase 1 chose `bootstrap`).

No mutations in this phase. Everything lives in memory.

---

## Phase 3 — Per-resource extraction + synthesis

**Pre-fetch confirmation gate** — show the classified resource list
and require explicit `proceed` before any external fetch (catches
mistyped or accidentally-pasted URLs before any `WebFetch` runs):

> Ready to fetch \<N> resources:
>   1. \<type>: \<location>
>   2. \<type>: \<location>
> Type `proceed` (advance to extraction), `revise <n>` (bounce that
> slot back to Phase 2), `drop <n>` (remove that slot — if list
> becomes empty, exit cleanly), or `abort`. Silence is not yes.

Then for each `RESOURCES[i]` (in order):

1. Fetch the content per the tool table in
   [references/resource-extraction.md#extraction-strategy-per-type](references/resource-extraction.md):
   - `web` → `WebFetch`
   - `youtube` → `yt-dlp` (soft dep — if missing, set
     `status="skipped-no-ytdlp"`, surface actionable error, continue)
   - `pdf` → `Read` with `pages`
   - `image` → `Read` (vision)
   - `local-doc` / `local-code` → `Read`
2. Filter the extracted content through `INTENT` — drop content
   irrelevant to Goal / In-scope / Constraints / Success-criteria;
   prefer verbatim quotes (markdown blockquotes) for facts and
   compact paraphrase for context. Full rules:
   [references/resource-extraction.md#what-intent-filtered-means](references/resource-extraction.md).
3. Compose `relevance_rationale` — one paragraph naming which INTENT
   rubric fields the extract informs.
4. Render a preview block in chat (template + examples:
   [references/resource-extraction.md#per-resource-synthesis-preview-phase-3-in-chat](references/resource-extraction.md)).

After all resources are previewed, prompt:

```
Type `confirm seeds` to lock all <N> seeds and proceed to worktree creation,
or `redo <n>` to re-extract resource N, or `drop <n>` to remove resource N.
```

Behavior per response:

- `confirm seeds` → record `verified_at` (ISO-8601 local time) in
  memory, proceed to Phase 4. Silence is not yes.
- `redo <n>` → re-run step 1 for resource N (refetch + refilter).
- `drop <n>` → remove resource N from `RESOURCES`.
- Anything else → re-ask.

Failure handling (fetch failed, file not found, encrypted PDF, etc.):
see [references/resource-extraction.md#failure-handling-webfetch-error-file-not-found-etc](references/resource-extraction.md).
Failed resources are marked `skipped-*` and excluded from emit; they
remain in the state file for audit but produce no seed files.

No mutations in this phase.

---

## Phase 4 — Worktree creation (first mutation)

Order matters — only after Phase 3 `confirm seeds`. Full command
sequence, sanitization, and edge cases:
[references/git-worktree-flow.md](references/git-worktree-flow.md).
Summary:

```bash
# Step 0 — local exclude so .worktrees/ doesn't dirty status.
COMMON_DIR="$(git -C "${MAIN_CHECKOUT}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null \
              || git -C "${MAIN_CHECKOUT}" rev-parse --git-common-dir)"
case "${COMMON_DIR}" in /*) ;; *) COMMON_DIR="${MAIN_CHECKOUT}/${COMMON_DIR}" ;; esac
grep -qxF '.worktrees/' "${COMMON_DIR}/info/exclude" \
  || echo '.worktrees/' >> "${COMMON_DIR}/info/exclude"

# Step 1 — INTENT_SLUG defensively whitelisted to [a-z0-9-]+.
# In bootstrap RUN_MODE, INTENT_SLUG was sanitized at Phase 1b.4 from
# the user-supplied PROJECT_SLUG (same rule as intent-aligner Phase 4).
case "${INTENT_SLUG}" in
  ""|*[!a-z0-9-]*|-*) echo "BLOCKER: intent slug failed [a-z0-9-]+ whitelist: '${INTENT_SLUG}'"; exit 1 ;;
esac
git -C "${MAIN_CHECKOUT}" worktree add \
  ".worktrees/seed-${INTENT_SLUG}-${SEED_RUN_ID}" \
  -b "seed/${INTENT_SLUG}-${SEED_RUN_ID}" "${BASE_BRANCH}"

# Step 2 — cd into the new worktree.
cd "${MAIN_CHECKOUT}/.worktrees/seed-${INTENT_SLUG}-${SEED_RUN_ID}"

# Step 3 — committed gitignore so worktree state stays hidden post-merge.
for entry in '.worktrees/' '.seed-state.json'; do
  grep -qxF "${entry}" .gitignore 2>/dev/null || echo "${entry}" >> .gitignore
done

# Step 4 — initial commit; diff-cached guard handles re-invocation
# after prior merge (gitignore entries already committed).
git add .gitignore
if ! git diff --cached --quiet; then
  git commit -m "chore(seeds): initialize ${INTENT_SLUG} ${RUN_MODE} worktree"
fi
```

Then **write the initial `.seed-state.json`** at the worktree root
with `phase_completed: synthesis_confirmed` (Phase 3 already
finished in memory before Phase 4 began), plus `language`,
`intent_slug`, `intent`, `resources` (including the `extracted_content`,
`relevance_rationale`, `extracted_at` confirmed in Phase 3),
`seed_run_id`, `main_checkout`, `base_branch`, `verified_at`. Schema:
[references/state-and-resume.md](references/state-and-resume.md).

Edge cases (path collision, dirty `BASE_BRANCH`, nested invocation,
untracked files on resume, merge conflicts at the gate) are
documented in [references/git-worktree-flow.md](references/git-worktree-flow.md).
Stop and ask the user — never auto-resolve.

---

## Phase 5 — Emit seeds (+ intent in bootstrap) + commit

**Bootstrap prelude** (only when `RUN_MODE` is `bootstrap` or
`bootstrap, ideation`): `mkdir -p ai-artifacts/intents`, then write
`ai-artifacts/intents/intent.${INTENT_SLUG}.md` at the worktree root per
[references/intent-bootstrap.md](references/intent-bootstrap.md)
(Provenance must include `Revision: 1` and `Bootstrapped by: seed-gatherer`).
Then render the HTML via the bundled renderer:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/render_intent_html.py" \
  .seed-state.json > "ai-artifacts/intents/intent.${INTENT_SLUG}.html"
```

Then `mkdir -p ai-artifacts/seeds`. For each `RESOURCES[i]`, in order:

0. **Skip non-emit cases** — `skipped-*` or already `emitted` (resume).
   Process only `confirmed` and `extracted` (ideation arrives at Phase 3
   already extracted).
1. **Collision check + 3-case disambiguation** — see
   [references/seed-naming.md](references/seed-naming.md) for full
   algorithm. Auto-suffix `-N` for cases (a)+(c); silent overwrite for case (b).
2. **Persist state with the settled slug** before the write (crash-safe).
3. **Write `.md`** per [references/output-schema.md](references/output-schema.md).
   For `ideation` type, include the `## Feasibility check` section.
4. **Render `.html`** via `${CLAUDE_SKILL_DIR}/scripts/render_seed_html.py`.
5. **Persist state** with `status="emitted"`, `output_md`, `output_html`.

After the loop, batch-commit with a `RUN_MODE`-conditional subject:

```bash
[ "${RUN_MODE%,*}" = "bootstrap" ] \
  && git add "ai-artifacts/intents/intent.${INTENT_SLUG}.md" "ai-artifacts/intents/intent.${INTENT_SLUG}.html"
git add ai-artifacts/seeds/
if ! git diff --cached --quiet; then
  case "${RUN_MODE}" in
    bootstrap)            SUBJECT="feat(seeds+intent): bootstrap ${INTENT_SLUG} (rev 1 + ${SEED_COUNT} seeds)" ;;
    bootstrap,*ideation*) SUBJECT="feat(seeds+intent): bootstrap ${INTENT_SLUG} ideation (rev 1 + ${SEED_COUNT} ideas)" ;;
    *ideation*)           SUBJECT="feat(seeds): emit ${INTENT_SLUG} ideation batch ${SEED_RUN_ID}" ;;
    *)                    SUBJECT="feat(seeds): emit ${INTENT_SLUG} batch ${SEED_RUN_ID}" ;;
  esac
  git commit -m "${SUBJECT}"
fi
```

Set `phase_completed: artifacts_emitted`.

---

## Phase 6 — Human gate + merge

The agent's cwd may be inside the worktree. Use `git -C
"${MAIN_CHECKOUT}"` so subsequent commands are cwd-independent.

Print:

1. The list of emitted artifacts — absolute paths to each
   `ai-artifacts/seeds/seed.${INTENT_SLUG}.${RESOURCE_SLUG}.{md,html}` so the user
   can open the HTMLs in a browser. Also list any `skipped-*`
   resources with the reason — these contributed nothing to the
   emit but the user should know they were attempted.

2. Next-step pointer (transition-safe):
   ```
   Next: `/plan-establisher` (reads ai-artifacts/seeds/seed.${INTENT_SLUG}.*.md +
   ai-artifacts/intents/intent.${INTENT_SLUG}.md) — or run `/seed-gatherer` again to grow
   the corpus, or `/intent-aligner update ${INTENT_SLUG}` to refine
   intent from the seeds just landed.
   ```

3. The exact prompt:

```
Type `confirm merge` to merge into <BASE_BRANCH> (marker varies by
RUN_MODE — see references/git-worktree-flow.md), or `keep`, or `revise`.
```

Behavior per response:

- `confirm merge` → run the dirty-MAIN_CHECKOUT guard, checkout
  `${BASE_BRANCH}`, and `git merge --no-ff` with a `RUN_MODE`-keyed
  subject + marker (full table:
  [references/git-worktree-flow.md#merge-command-sequence-phase-6](references/git-worktree-flow.md)).
  After the merge, ask *"Remove the worktree?"* — on yes, `cd
  "${MAIN_CHECKOUT}"` FIRST (Phase 4 left cwd inside the worktree),
  then `git -C "${MAIN_CHECKOUT}" worktree remove <path>` (no `--force`).

- `keep` → leave worktree intact, no merge, exit cleanly.
- `revise` → leave worktree intact, ask which phase to re-enter
  (Phase 2 / 2i / 3 / 5). Do not guess.
- Anything else → re-ask. Silence is not yes.

Update state: `phase_completed: human_confirmed`, record `merged_at`.

---

## Downstream contract

The merge commit message + marker varies by `RUN_MODE` (see
[references/git-worktree-flow.md](references/git-worktree-flow.md)):
`(seeds, human-confirmed)`, `(seeds, ideation, human-confirmed)`,
`(intent+seeds, bootstrap, human-confirmed)`, or the bootstrap+ideation
combo. Each variant makes the chain step visible in `git log`. The
markers are social contracts, not cryptographic; they catch accidental
misuse and make deliberate bypass visible in history.

The skill does NOT auto-launch any downstream skill. The user runs
`/plan-establisher` (or repeats `/seed-gatherer` to grow the
corpus) explicitly when ready. This skill's job ends at the merged
`ai-artifacts/seeds/seed.<intent-slug>.*.md` files — shaping for the planner's
rubric is `plan-establisher`'s concern.

The cross-intent coexistence property is the same as intent-aligner's:
running this skill for `dashboard` and `payments` produces
`ai-artifacts/seeds/seed.dashboard.*.md` and `ai-artifacts/seeds/seed.payments.*.md` without
overwriting each other. The downstream planner globs by intent slug.

---

## Forbidden actions

Refuse even on mid-flow request (surface + ask for explicit override; default refusal):

- `git push`, `git push --force`
- `git merge` without `--no-ff`; `git merge`/`git commit` without `-m`
- `git reset --hard`, `git clean -f`, `git worktree remove --force`,
  `git commit --amend` once a commit landed, `--no-verify`
- Treating user silence as confirmation at any gate (intent select,
  Phase 2 done, `confirm seeds`, `confirm merge`, "remove worktree?")
- Fetching a resource before Phase 3's pre-fetch `proceed` gate
  (resources stay pending; no `WebFetch`/`yt-dlp`/`Read` runs until
  `proceed`). Same rule applies to Phase 1b.1's pre-fetch gate in
  bootstrap mode.
- Auto-resolving slug collisions silently — see [references/seed-naming.md](references/seed-naming.md)
- Auto-retrying failed fetches (mark `skipped-*`, surface reason)
- Persisting raw verbatim third-party content beyond what's
  intent-relevant — extracts must be filtered, not whole-page dumps
  (quasi-quoting / copyright + context-pollution concern)
- Auto-launching `/plan-establisher`, `/codebase-planner`, or
  `/intent-aligner` from Phase 6
- Loading or modifying `ai-artifacts/intents/intent.<slug>.md` in `standard` mode — repair
  is `/intent-aligner`'s job. **Exception**: bootstrap mode authors a
  fresh intent (Phase 1b); that's the only seed-gatherer path that
  writes intent.md.
- Crystallizing an ideation seed without a feasibility check (the
  feasibility-checked promise is what makes ideation seeds valuable —
  see [references/ideation-mode.md](references/ideation-mode.md))
- Running >2 feasibility tool calls per ideated idea (latency budget)
- Setting `Revision` to anything other than `1` in bootstrap output
  (updates are `/intent-aligner update`'s job)
- Creating `README.md` / `INSTALLATION_GUIDE.md` inside this skill folder

---

## Resumability

If re-invoked from inside an existing seed worktree
(`inside-seed-worktree`), read `.seed-state.json` and resume from the
next phase after `phase_completed`. See
[references/state-and-resume.md#resume-map](references/state-and-resume.md)
for the full mapping.

If `inside-seed-worktree` but no state file → refuse and ask the user
to either delete the worktree or supply a state file.

If the state file's `language` field is missing (defensive guard —
should never happen since Phase 4 always writes it): default
`LANGUAGE` to Korean (matching Phase L's default) and continue without
prompting.
