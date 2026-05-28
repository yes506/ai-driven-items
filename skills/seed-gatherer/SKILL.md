---
name: seed-gatherer
description: |
  Downstream of `intent-aligner` in the chain (intent-aligner →
  seed-gatherer → plan-establisher → codebase-planner →
  codebase-implementer). Reads `intent.<slug>.md` and extracts
  intent-filtered content from user-supplied web/youtube URLs and
  local file paths (PDF, image, doc, code), emitting one md+html
  seed pair per resource under `seeds/`. Iteratively re-runnable —
  each invocation appends seeds across its own worktree+merge cycle.
  Manual invocation only — `/seed-gatherer`.
disable-model-invocation: true
---

# Seed Gatherer

## Overview

Take the intent captured by `/intent-aligner` and grow a corpus of
intent-filtered evidence from the user's external research material.
The user pastes URLs and/or absolute local file paths; the skill
fetches each resource, filters the content through the intent's
rubric (Goal, In-scope features, Out-of-scope, Constraints, Success
criteria, Open questions), and emits two artifacts per resource:

| Output | Audience | Purpose |
|---|---|---|
| `seeds/seed.<intent-slug>.<resource-slug>.md` | AI (next-hop is `plan-establisher`) | Structured seed — source provenance, intent-filtered extract, relevance rationale |
| `seeds/seed.<intent-slug>.<resource-slug>.html` | Human (browser-openable) | Self-contained verification doc, no CDN, HTML-escaped |

The skill is **iteratively re-runnable**: each invocation runs in its
own worktree+merge cycle but the seeds it emits accumulate alongside
seeds from prior runs in `seeds/`. The downstream `plan-establisher`
will glob `seeds/seed.<intent-slug>.*.md` to find everything for one
intent.

`disable-model-invocation: true` — the skill has side effects (writes
files, creates a git worktree, merges branches). Never auto-trigger.

## Workflow Decision Tree

```
Phase L: Dialog language (preamble) — see references/language-selection.md
Phase 0: Detect repo state ──┬─ on-dev ──────────────────── proceed
                             ├─ on-default-needs-dev ────── create-dev dialog
                             ├─ on-nonbase-main-checkout ── refuse, ask user to switch to dev
                             ├─ inside-seed-worktree ────── resume from .seed-state.json
                             ├─ inside-other-worktree ───── refuse, run from MAIN_CHECKOUT
                             └─ unrelated ────────────────── refuse, surface reason
Phase 1: Intent selection (auto-pick if single intent.<slug>.md, else prompt) + load 6 rubric fields
Phase 2: Resource intake loop (paste URL or absolute path; echo + classify; `done` to finish)
Phase 3: Per-resource extraction + synthesis preview + `confirm seeds` gate (no mutations yet)
Phase 4: Worktree creation (FIRST mutation) — .worktrees/seed-<intent-slug>-<id>/
Phase 5: Emit seeds/seed.<intent-slug>.<resource-slug>.{md,html} (mkdir seeds/ on first emit) + commit
Phase 6: Human gate + merge (`confirm merge` → marker `(seeds, human-confirmed)`)
```

## State variables

Captured during Phases L–4 and threaded through later phases:

- `LANGUAGE` — dialog language (`Korean` default | `English`); captured
  at Phase L per [references/language-selection.md](references/language-selection.md);
  held in memory through Phases 0–3, persisted at Phase 4.
- `MAIN_CHECKOUT` — absolute path to the parent main worktree.
- `BASE_BRANCH` — branch the seed worktree branches from (default `dev`).
- `INTENT_SLUG` — chosen at Phase 1 (auto if single `intent.*.md`,
  prompt if multiple).
- `INTENT` — parsed 6 rubric fields from `intent.<INTENT_SLUG>.md`
  per [references/intent-loading.md](references/intent-loading.md).
- `SEED_RUN_ID` — stable run handle; computed at end of Phase 1,
  reused as worktree/branch suffix in Phase 4.
- `RESOURCES` — in-memory list of `{type, location, resource_slug,
  status, extracted_content, relevance_rationale, extracted_at}`
  entries; populated at Phases 2–3, persisted at Phase 4.

All persisted per [references/state-and-resume.md](references/state-and-resume.md).

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

## Phase 1 — Intent selection

Discover available intents at the repo root:

```bash
ls -1 "${MAIN_CHECKOUT}"/intent.*.md 2>/dev/null
```

| Match count | Action |
|---|---|
| 0 | refuse: *"No `intent.<slug>.md` found at `${MAIN_CHECKOUT}`. Run `/intent-aligner` first to capture your intent."* exit cleanly |
| 1 | auto-pick; echo slug + goal line; wait for `confirm intent` (or `revise` to abort) |
| ≥2 | list all slugs with their `Goal:` lines as a numbered menu; prompt: *"Which intent should these seeds serve? Type the number, or `abort`."* |

Parse the chosen `intent.<INTENT_SLUG>.md` per
[references/intent-loading.md](references/intent-loading.md) — load
the 6 rubric fields (`goal`, `in_scope`, `out_of_scope`, `constraints`,
`success_criteria`, `open_questions`) into the in-memory `INTENT`
representation. Surface any parse defects (missing required section,
empty Goal, etc.) and ask the user before proceeding — do NOT silently
fill in.

Compute `SEED_RUN_ID="$(date +%s | tail -c 6)-$$-${RANDOM}"` at the
end of this phase (stable for the rest of the run, reused in worktree
path/branch at Phase 4).

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

Termination: user types `done`. If `RESOURCES` is empty when the user
types `done`, ask: *"No resources gathered — exit without doing
anything?"* Silence is not yes.

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
# Step 0 — local exclude so .worktrees/ doesn't dirty status. CRITICAL:
# --git-common-dir returns a RELATIVE path on older git; use
# --path-format=absolute (git >= 2.31) with fallback, otherwise the
# exclude lands at "<cwd>/.git/info/exclude" not MAIN_CHECKOUT's.
COMMON_DIR="$(git -C "${MAIN_CHECKOUT}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null \
              || git -C "${MAIN_CHECKOUT}" rev-parse --git-common-dir)"
case "${COMMON_DIR}" in /*) ;; *) COMMON_DIR="${MAIN_CHECKOUT}/${COMMON_DIR}" ;; esac
grep -qxF '.worktrees/' "${COMMON_DIR}/info/exclude" \
  || echo '.worktrees/' >> "${COMMON_DIR}/info/exclude"

# Step 1 — INTENT_SLUG already sanitized by intent-aligner; defensive
# positive whitelist (intent-aligner's output is [a-z0-9-]+, so accepting
# only that closes the loop in case intent-aligner ever loosens its rule)
case "${INTENT_SLUG}" in
  ""|*[!a-z0-9-]*|-*) echo "BLOCKER: intent slug failed [a-z0-9-]+ whitelist: '${INTENT_SLUG}'"; exit 1 ;;
esac

git -C "${MAIN_CHECKOUT}" worktree add \
  ".worktrees/seed-${INTENT_SLUG}-${SEED_RUN_ID}" \
  -b "seed/${INTENT_SLUG}-${SEED_RUN_ID}" "${BASE_BRANCH}"

# Step 2 — cd into the new worktree
cd "${MAIN_CHECKOUT}/.worktrees/seed-${INTENT_SLUG}-${SEED_RUN_ID}"

# Step 3 — committed gitignore so .worktrees/ + .seed-state.json
# stay hidden after the merge to ${BASE_BRANCH}
for entry in '.worktrees/' '.seed-state.json'; do
  grep -qxF "${entry}" .gitignore 2>/dev/null \
    || echo "${entry}" >> .gitignore
done

# Step 4 — initial commit on the seed branch. Guard with diff-cached
# because on re-invocation after a prior seed merge, `.worktrees/` and
# `.seed-state.json` are already in the committed `.gitignore`. Step 3
# correctly no-ops in that case, so `git add` stages nothing and a bare
# `git commit` would fail with "nothing to commit" and abort the run.
# Phase 5's `feat(seeds): emit ...` commit becomes the first commit on
# the branch in that resumed-after-merge case; `git merge --no-ff` still
# proceeds normally.
git add .gitignore
if ! git diff --cached --quiet; then
  git commit -m "chore(seeds): initialize ${INTENT_SLUG} worktree"
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

## Phase 5 — Emit seeds + commit

`mkdir -p seeds`. For each `RESOURCES[i]`, in order:

0. **Skip non-emit cases** — `skipped-no-ytdlp` / `skipped-fetch-failed`
   (failure path), or already `emitted` (the latter handles resume
   where the resource finished in a prior attempt). Process only
   `confirmed`.
1. **Collision check + 3-case disambiguation** — if the target file
   exists, classify by git-trackedness AND Source field:
   (a) **tracked in HEAD** = inherited from a prior merged seed run
   (the iteratively-re-runnable happy path) → auto-suffix `-N`,
   notify, update state slug;
   (b) **untracked + `## Source` matches `RESOURCES[i].location`** =
   mine from a prior crashed attempt → overwrite silently (recovery);
   (c) **untracked + Source differs** = true intra-run collision →
   auto-suffix, notify, update state slug.
   Full algorithm, awk snippets, and notification strings:
   [references/seed-naming.md#collision-policy-3-case-disambiguation](references/seed-naming.md).
2. **Persist state with the settled slug** *before* the file write — a
   crash mid-write leaves state pointing at the exact filename to
   re-check on resume.
3. **Write `.md`** via `Write` per [references/output-schema.md](references/output-schema.md).
   Field NAMES English; VALUES follow `LANGUAGE`; verbatim source
   quotes stay in the source's own language.
4. **Render `.html`**:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/render_seed_html.py" \
     .seed-state.json "${RESOURCE_SLUG}" > "seeds/seed.${INTENT_SLUG}.${RESOURCE_SLUG}.html"
   ```

   Renderer is self-contained (no CDN, HTML-escapes all user content,
   only emits `<a href="...">` for `http(s)://` URLs). Template at
   `${CLAUDE_SKILL_DIR}/assets/seed-html-template.html`.
5. **Persist state** with `status="emitted"`, `output_md`,
   `output_html`. A crash after this means resume skips at step 0.

After the per-resource loop, commit with a single batch commit. The
`diff --cached --quiet` guard handles resume — re-rendered identical
artifacts stage nothing; the skip prevents a "nothing to commit"
abort:

```bash
git add seeds/
if ! git diff --cached --quiet; then
  git commit -m "feat(seeds): emit ${INTENT_SLUG} batch ${SEED_RUN_ID}"
fi
```

State file is gitignored (Phase 4 step 3) so it doesn't appear in the
commit. Finally set `phase_completed: artifacts_emitted` and persist —
a crash after this leaves the resume target as Phase 6.

---

## Phase 6 — Human gate + merge

The agent's cwd may be inside the worktree. Use `git -C
"${MAIN_CHECKOUT}"` so subsequent commands are cwd-independent.

Print:

1. The list of emitted artifacts — absolute paths to each
   `seeds/seed.${INTENT_SLUG}.${RESOURCE_SLUG}.{md,html}` so the user
   can open the HTMLs in a browser. Also list any `skipped-*`
   resources with the reason — these contributed nothing to the
   emit but the user should know they were attempted.

2. Next-step pointer (transition-safe — `plan-establisher` is the
   intended next hop but may not be installed yet):

   ```
   Next step: run `/plan-establisher` when ready. It reads
   ${MAIN_CHECKOUT}/seeds/seed.${INTENT_SLUG}.*.md alongside
   intent.${INTENT_SLUG}.md to shape a planner-ready handoff. If
   `/plan-establisher` isn't installed yet, you can run
   `/seed-gatherer` again to add more seeds, or pass the
   seeds directory directly to `/codebase-planner` as supporting
   material.
   ```

3. The exact prompt:

```
Type `confirm merge` to merge seed/<intent-slug>-<id> into <BASE_BRANCH>
with marker (seeds, human-confirmed),
or `keep` to leave the worktree intact for further iteration,
or `revise` to address something before merging.
```

Behavior per response:

- `confirm merge` → run the dirty-MAIN_CHECKOUT guard + `git checkout
  "${BASE_BRANCH}"` + `git merge --no-ff -m "feat(seeds): merge
  ${INTENT_SLUG} batch ${SEED_RUN_ID} (seeds, human-confirmed)"` per
  the exact sequence in [references/git-worktree-flow.md#merge-command-sequence-phase-6](references/git-worktree-flow.md).
  After the merge, ask: *"Remove the worktree at
  `.worktrees/seed-${INTENT_SLUG}-${SEED_RUN_ID}`?"* On yes: **first
  `cd "${MAIN_CHECKOUT}"`** (the agent's cwd may still be inside the
  worktree from Phase 4 step 2; removing it without `cd` out leaves
  the shell with a deleted cwd). Then `git -C "${MAIN_CHECKOUT}"
  worktree remove <path>` (no `--force`). On no: leave it.

- `keep` → leave worktree intact, no merge, exit cleanly.
- `revise` → leave worktree intact, ask the user **which** phase to
  re-enter (Phase 2 to add/remove resources, Phase 3 to re-extract,
  Phase 5 to re-render). Do not guess.
- Anything else → re-ask. Silence is not yes.

Update state: `phase_completed: human_confirmed`, record `merged_at`.

---

## Downstream contract

The merge commit message `feat(seeds): merge <intent-slug> batch
<seed-run-id> (seeds, human-confirmed)` makes the seed landing
visible in `git log` — the same pattern the intent / planner /
implementer chain uses. The marker is a social contract, not
cryptographic; the goal is catching accidental misuse and making
deliberate bypass visible in git history.

The skill does NOT auto-launch any downstream skill. The user runs
`/plan-establisher` (or repeats `/seed-gatherer` to grow the
corpus) explicitly when ready. This skill's job ends at the merged
`seeds/seed.<intent-slug>.*.md` files — shaping for the planner's
rubric is `plan-establisher`'s concern.

The cross-intent coexistence property is the same as intent-aligner's:
running this skill for `dashboard` and `payments` produces
`seeds/seed.dashboard.*.md` and `seeds/seed.payments.*.md` without
overwriting each other. The downstream planner globs by intent slug.

---

## Forbidden actions

The skill must refuse to execute any of these even if the user
requests them mid-flow (politely surface the forbidden item and ask
for confirmation to deviate, but default to refusal):

- `git push`, `git push --force`
- `git merge` without the `--no-ff` flag for the seed branch
- `git merge` or `git commit` without the `-m` flag (would hang on
  `$EDITOR`)
- `git reset --hard`, `git clean -f`, `git worktree remove --force`
- `git commit --amend` once a commit has landed on the seed branch
  (create a new commit instead — amend rewrites history that
  `--no-ff` was meant to preserve)
- `--no-verify` on commits (pre-commit hooks must run)
- Treating user silence as confirmation at any gate (intent
  selection, resource intake termination, `confirm seeds`, `confirm
  merge`, "remove worktree?")
- Fetching a resource before Phase 3's pre-fetch `proceed` gate
  (resources accepted into `RESOURCES` at Phase 2 are pending only;
  no `WebFetch` / `yt-dlp` / `Read` may run until the user explicitly
  types `proceed` at the start of Phase 3 — protects against
  accidentally-pasted sensitive or private URLs)
- Auto-resolving slug collisions silently — the chat notification
  is mandatory per [references/seed-naming.md](references/seed-naming.md)
- Auto-retrying failed fetches (mark `skipped-*` and surface the
  reason; the user decides whether to re-add)
- Persisting raw verbatim third-party content beyond what's
  intent-relevant — extracts must be filtered, not whole-page dumps.
  Quoting a paragraph that informs the intent is fine; quoting an
  entire article because it was "easier" is not (this is a
  quasi-quoting / copyright concern as well as a context-pollution
  one)
- Auto-launching `/plan-establisher`, `/codebase-planner`, or any
  downstream skill from Phase 6 (the user runs the next-hop
  explicitly when ready)
- Loading or modifying `intent.<slug>.md` in any way other than
  reading at Phase 1 — repairing a malformed intent is the
  `intent-aligner`'s job
- Creating `README.md`, `INSTALLATION_GUIDE.md`, or similar docs
  inside this skill folder

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
