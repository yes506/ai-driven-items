# Update mode — refining an existing intent from accumulated seeds

Update mode is the second of two flows the skill supports. Use this
reference alongside SKILL.md's compact update-mode section.

| Flow | Invocation | First mutation | Merge marker |
|---|---|---|---|
| **Create** (default) | `/intent-aligner` | Phase 4 worktree creation | `(intent, human-confirmed)` |
| **Update** | `/intent-aligner update <slug>` | Phase 4u worktree creation | `(intent, updated-from-seeds, human-confirmed)` |

Intent is **not immutable**. User intent is often incomplete at the
first capture; as `/seed-gatherer` runs accumulate evidence, the intent
can be refined to reflect what's been learned. Update mode is the
formal feedback path closing the seed→intent loop in the chain.

## When to use update mode

The user has already run `/intent-aligner` once (or `/seed-gatherer`
in bootstrap mode) to produce `intent.<slug>.md`, and since then
`seeds/seed.<slug>.*.md` files have accumulated. Update mode reads
both, proposes targeted refinements per rubric field, and emits a new
revision of the intent.

Skip update mode if:

- No seeds exist yet for this intent → run `/seed-gatherer` first.
- The user wants to **replace** the intent wholesale rather than
  refine it → ask them to delete `intent.<slug>.md` and run
  `/intent-aligner` (create mode) again. Update is for incremental
  refinement, not rewrites.

## Invocation parsing (Phase 0 argument detection)

`/intent-aligner update <slug>` and `/intent-aligner --update <slug>`
both enter update mode. Plain `/intent-aligner` enters create mode.

Parse rules (case-sensitive on `update` / `--update`):

| Invocation | `RUN_MODE` | Notes |
|---|---|---|
| `/intent-aligner` | `create` | Default. |
| `/intent-aligner update <slug>` | `update` | `<slug>` is the existing intent's slug. |
| `/intent-aligner --update <slug>` | `update` | Same as above. |
| `/intent-aligner update` (no slug) | refuse | Ask: *"Update mode needs an intent slug. Existing intents at `${MAIN_CHECKOUT}`: <list>. Re-invoke as `/intent-aligner update <slug>`."* |
| `/intent-aligner <anything-else>` | refuse | Ask: *"Unrecognized argument. Use `/intent-aligner` to create, or `/intent-aligner update <slug>` to refine an existing intent."* |

The slug must match an existing `intent.<slug>.md` at `MAIN_CHECKOUT`.
If not found, refuse and list existing intents.

## Phase map (update mode)

| Phase | Purpose | First mutation? |
|---|---|---|
| **Lu** | Language preamble (same as Phase L) | no |
| **0u** | Repo state + arg parsing + existing-intent discovery | no |
| **1u** | Load existing intent + glob seeds + summarize | no |
| **2u** | Refinement elicitation (per-field dialog) | no |
| **3u** | Synthesis + `confirm refinement` gate | no |
| **4u** | Worktree creation | **yes** (first mutation) |
| **5u** | Emit updated intent.<slug>.md + .html + commit | yes |
| **6u** | Human gate + merge with update marker | yes |

Phases Lu / 0u / 4u / 5u / 6u mirror create mode's Phases L / 0 / 4 /
5 / 6 with the worktree path and merge marker variations called out
below. Phases 1u / 2u / 3u are update-specific.

## Phase 0u — extended repo state checks

Run the standard `inspect_repo_state.sh`. In addition to the create-
mode states, update mode adds:

| State | Action |
|---|---|
| `on-dev` + slug arg given + `intent.<slug>.md` exists | proceed to Phase 1u |
| `on-dev` + slug arg given + no matching intent file | refuse: *"No `intent.<slug>.md` at `${MAIN_CHECKOUT}`. Existing intents: <list>. To create new, run `/intent-aligner` without `update`."* |
| `inside-intent-worktree` whose state file has `run_mode: update` | resume update mode from `.intent-state.json` |
| All other create-mode states | apply as written in create mode |

## Phase 1u — load existing intent + glob seeds

1. Parse `intent.<slug>.md` fully — not just the 6 rubric sections but
   also `## Mode`, `## Persona`, `## Examples`, `## Counter-examples`,
   `## Root-cause`, `## Provenance`. The existing intent is the **base
   revision** that refinements diff against.

2. Extract `revision` from `## Provenance`:
   - Line of the form `- Revision: <N>` → `BASE_REVISION = N`
   - Absent → `BASE_REVISION = 1` (back-compat with pre-update-mode
     intents)
   - Set `TARGET_REVISION = BASE_REVISION + 1`

3. Check `Bootstrapped by: <skill>` in Provenance:
   - Absent → standard intent-aligner-authored
   - `seed-gatherer` → intent was bootstrapped during a seed run. Note
     this in the chat surface ("This intent was bootstrapped by
     seed-gatherer; bootstrap intents tend to be thinner — expect
     more elicitation"). Don't change behavior, just calibrate.

4. Glob seed files for this intent:
   ```bash
   ls -1 "${MAIN_CHECKOUT}"/seeds/seed."${INTENT_SLUG}".*.md 2>/dev/null
   ```
   For each seed file, parse `## Source`, `## Resource type`,
   `## Extracted content (intent-filtered)`, and `## Relevance
   rationale` (the field labels are fixed per seed-gatherer's
   output-schema). If zero seeds → refuse: *"No seeds found at
   `seeds/seed.${INTENT_SLUG}.*.md`. Run `/seed-gatherer` first to
   accumulate evidence, then re-run update mode."*

5. Surface a summary to the user before any elicitation:
   ```
   Existing intent: intent.<slug>.md (revision N)
   Bootstrap source: <skill-name | none>

   Seeds collected since (M seeds):
     1. seed.<slug>.<resource-slug-1>.md
        Source: <URL or path>
        Informs: Goal, Constraints  (from relevance rationale)
     2. seed.<slug>.<resource-slug-2>.md
        Source: <URL or path>
        Informs: Open questions, Success criteria
     ...

   Type `proceed` to start refinement, or `abort` to exit.
   ```

   `proceed` → Phase 2u. Silence is not yes.

## Phase 2u — refinement elicitation loop

Iterate per rubric field (`Goal`, `In-scope features`, `Out-of-scope`,
`Constraints`, `Success criteria`, `Open questions`; mode-specific:
`Persona`, `Examples`, `Counter-examples`, `Root-cause`). For each
field:

1. **Show the current value.** Verbatim from `intent.<slug>.md`.
2. **Propose targeted refinements.** For each refinement, name the
   seed(s) that back it. Format:
   ```
   Field: Constraints
   Current:
     - Must work behind CloudFront
     - p95 latency under 300ms
   Proposed additions (from seeds):
     + Cache-control header must permit edge caching
       [from seed.<slug>.nextjs-caching.md — Quote: "..."]
     + Stale-while-revalidate not supported on CloudFront edges
       [from seed.<slug>.cloudfront-edge-tos.md]
   Proposed edits:
     ~ "Must work behind CloudFront" → "Must work behind CloudFront
       with no path rewrites"
       [from seed.<slug>.nextjs-caching.md — Quote: "..."]
   Proposed removals:
     (none)
   Open questions surfaced:
     ? Does the dashboard need stale-while-revalidate? (raised by
       seed.<slug>.cloudfront-edge-tos.md but unresolved)
   ```
3. **Ask the user**: accept all / edit / reject / skip-field.
   - Accept all → apply the refinements to the in-memory `INTENT`.
   - Edit → user types their preferred wording; replace the proposal.
   - Reject → leave the field unchanged.
   - Skip-field → move to the next field; this field's refinements are
     dropped (record in state under `skipped_fields[]` for audit).

4. **User free-form input.** After the per-field loop, ask once:
   *"Anything else to add or change beyond what the seeds suggested?
   Type `done` to lock the synthesis, or describe additions."*
   If the user adds free-form input, treat it as a mini elicitation —
   short Socratic loop (1–2 rounds) to nail it down, then fold into
   the in-memory `INTENT`.

## Phase 3u — synthesis + confirm refinement

Render the updated `INTENT` in chat as a single fenced block. Use the
same template as create mode's Phase 3 synthesis, but prepend a
**diff summary** so the user sees what changed:

```
INTENT REFINEMENT — synthesis
=============================
Slug: <slug>
Revision: <BASE_REVISION> → <TARGET_REVISION>

Diff summary:
  Constraints: +2 added, 1 edited, 0 removed
  Open questions: +1 added, 2 resolved (now in Constraints)
  Success criteria: +0
  ...

[Full updated intent rendered below]
Mode: <feature | problem>
Persona: <...>
Goal: <...>
...

Seeds that informed this refinement:
  - seed.<slug>.nextjs-caching.md
  - seed.<slug>.cloudfront-edge-tos.md
  - seed.<slug>.youtube-dqw4w9wgxcq.md
```

Then prompt:

```
Type `confirm refinement` to lock revision <TARGET_REVISION> and emit
intent.<slug>.md + intent.<slug>.html (overwriting the prior revision),
or `revise` to iterate further.
```

- `confirm refinement` → record `verified_at`, proceed to Phase 4u.
  Silence is not yes.
- `revise` → return to Phase 2u with the user's specific corrections.
- Anything else → re-ask.

## Phase 4u — worktree creation (first mutation)

Same shape as create mode's Phase 4, with these substitutions:

| Variable | Create mode | Update mode |
|---|---|---|
| Worktree path | `.worktrees/intent-<slug>-<id>/` | `.worktrees/intent-update-<slug>-<id>/` |
| Branch | `intent/<slug>-<id>` | `intent/update-<slug>-<id>` |
| Initial commit subject | `chore(intent): initialize <slug> worktree` | `chore(intent): initialize <slug> update worktree (rev <N>→<N+1>)` |

Path-prefix `intent-update-` keeps `git worktree list` legible — at a
glance the maintainer sees which worktrees are create vs. update runs.

State-file persistence is the same as create mode but the schema
carries `run_mode: update`, `base_revision`, `target_revision`,
`refining_seed_slugs[]` (the seeds whose rationale was actually
used in Phase 2u).

## Phase 5u — emit updated intent.<slug>.md + .html + commit

Overwrite the existing `intent.<slug>.md` and `intent.<slug>.html`
with the refined content. The Provenance section MUST include:

```markdown
## Provenance

- Intent ID: <intent_id-of-this-update-run>
- Revision: <TARGET_REVISION>
- Confirmed at: <ISO-8601 timestamp>
- Language used during elicitation: <Korean | English>
- Refined from seeds: <comma-separated list of slugs>
- Prior revision intent ID: <BASE intent_id from the file being overwritten>
```

`Refined from seeds` captures **only the seeds that materially shaped
this revision** (not the cumulative set across all revisions). The git
history is the cumulative audit trail.

`Prior revision intent ID` preserves the linkage to the previous run's
`INTENT_ID` so reviewers can trace any revision back through git log.

`Bootstrapped by: seed-gatherer` (if present in the base) is **dropped**
on update — once intent-aligner refines a bootstrap intent, it's no
longer a fresh bootstrap. The git history is the audit trail.

Commit message:
```
feat(intent): refine <slug> rev <N>→<N+1>
```

The `intent.<slug>.html` re-renders identically to create mode via the
same `scripts/render_html_report.py`. The HTML doesn't surface the
revision number in body chrome — that's a machine field — but the
footer's `Verified by user at <timestamp>` updates to the new
`verified_at`.

## Phase 6u — human gate + merge with update marker

Same as create mode's Phase 6, with:

- Merge commit message:
  ```
  feat(intent): merge <slug> refinement (intent, updated-from-seeds, human-confirmed)
  ```
- The audit-trail marker `(intent, updated-from-seeds, human-confirmed)`
  is what makes update merges visible-at-a-glance in `git log`.

The dirty-`MAIN_CHECKOUT` guard, `--no-ff` requirement, and worktree-
remove prompt are all unchanged.

## State-file schema (update mode additions)

Update mode persists the same fields as create mode plus:

```json
{
  "run_mode": "update",
  "base_revision": <integer>,
  "target_revision": <integer>,
  "base_intent_id": "<intent_id of the file being refined>",
  "refining_seed_slugs": ["seed.<slug>.<resource-slug-1>", "..."],
  "skipped_fields": ["root_cause", "..."]
}
```

`run_mode` is the discriminator that Phase 0u's resume logic keys off.
A worktree at `.worktrees/intent-update-<slug>-<id>/` with state
`run_mode: create` is a corrupted state — refuse to resume and ask the
user to remove the worktree.

## Resume map (update mode)

| `phase_completed` | Resume at |
|---|---|
| `worktree_created` | Phase 5u (emit updated artifacts) |
| `artifacts_emitted` | Phase 6u (human gate + merge) |
| `human_confirmed` | nothing — run complete |

If `run_mode: update` but `phase_completed` is missing → refuse, ask
the user to remove the worktree.

## Honest limitations

- **No revision rollback.** Once a revision lands on `${BASE_BRANCH}`,
  reverting requires git operations (`git revert <commit>` or manual
  edit of `intent.<slug>.md`). The skill does not offer rollback —
  conflating refinement with rollback would muddle the audit trail.
- **Per-field-only refinements.** Update mode can change values within
  fields, add new bullets, drop bullets, edit bullet wording. It does
  NOT change the intent's `Mode` (feature vs problem) or the
  `PROJECT_SLUG`. Both are identity-load-bearing; changing them is a
  new-intent operation, not a refinement.
- **Seeds without rationale fields are unusable.** The refinement
  loop reads each seed's `Relevance rationale` to attach proposals to
  intent fields. A seed with an empty rationale gets surfaced
  ("seed.<X>.md has no rationale — skipping in refinement; consider
  re-running /seed-gatherer for it") and excluded.
- **No partial seed exclusion at Phase 1u.** All seeds matching the
  glob are surfaced and contribute equally to the per-field proposals.
  To exclude a seed's signal, use the per-field controls in Phase 2u
  (reject / edit / skip-field on any proposal whose only support is
  that seed). There is no `drop <n>` at the Phase 1u confirmation
  gate, and no per-seed weighting.
