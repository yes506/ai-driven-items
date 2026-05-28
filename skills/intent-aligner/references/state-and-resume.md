# State and resume — `.intent-state.json`

The state file is the durable representation of an in-flight
intent-aligner run. It lives at the worktree root, is gitignored
(written to the worktree's `.gitignore` at Phase 4 step 3), and
exists only inside the worktree — never on `MAIN_CHECKOUT` /
`${BASE_BRANCH}`.

If the skill crashes between phases, re-invoking it from inside the
worktree (`inside-intent-worktree`) reads this file and resumes from
the next phase after `phase_completed`.

## Schema

```json
{
  "run_mode": "create | update",
  "language": "Korean | English",
  "mode": "feature | problem",
  "project_slug": "<sanitized-ascii-slug>",
  "main_checkout": "<absolute-path>",
  "base_branch": "dev",
  "intent_id": "<5-digit-epoch>-<pid>-<random>",
  "revision": <integer; 1 for create, base+1 for update>,
  "base_revision": <integer; update mode only — the revision being refined>,
  "base_intent_id": "<update mode only — Intent ID of the file being refined>",
  "refining_seed_slugs": ["update mode only — seeds that informed Phase 2u"],
  "skipped_fields": ["update mode only — fields the user skipped during Phase 2u"],
  "bootstrapped_by": "<optional — set when authored by seed-gatherer; dropped on first update>",
  "phase_completed": "worktree_created | artifacts_emitted | human_confirmed",
  "intent": {
    "goal": "<single sentence>",
    "persona": "<single sentence>",
    "in_scope": ["...", "..."],
    "out_of_scope": ["...", "..."],
    "constraints": ["...", "..."],
    "success_criteria": ["...", "..."],
    "examples": ["...", "..."],
    "counter_examples": ["...", "..."],
    "root_cause": ["symptom", "why1", "why2", "..."],
    "open_questions": ["...", "..."]
  },
  "verified_at": "<ISO-8601 — written at Phase 3 / 3u confirm gate>",
  "merged_at": "<ISO-8601 — written at Phase 6 / 6u confirm-merge>"
}
```

### Field notes

- **`run_mode`** — `create` (plain `/intent-aligner`) or `update`
  (`/intent-aligner update <slug>` or `--update <slug>`). Set at
  Phase 0 from the invocation arg. Discriminator for the resume map
  below — a worktree at `.worktrees/intent-update-<slug>-<id>/` whose
  state says `run_mode: create` is corrupted (refuse to resume). See
  [update-mode.md](update-mode.md) for the full update-mode flow.
- **`revision`** / **`base_revision`** / **`base_intent_id`** /
  **`refining_seed_slugs`** / **`skipped_fields`** — populated only
  when `run_mode == "update"`. The base fields capture what the
  current refinement diffs against. See
  [update-mode.md](update-mode.md).
- **`bootstrapped_by`** — populated only when the state was
  initialized by `/seed-gatherer`'s no-intent bootstrap path
  (intent-aligner's create mode never sets this). Dropped on first
  update-mode refinement.
- **`language`** — written for the first time at Phase 4 (worktree
  creation). Before that, `LANGUAGE` lives only in memory. See
  [language-selection.md](language-selection.md).
- **`mode`** — captured at Phase 1; persisted at Phase 4. If the user
  triggers a mid-flow re-classification (per
  [mode-detection.md](mode-detection.md)), update both the in-memory
  value and the state file's `mode` field. **Update mode does not
  change `mode`** — changing feature ↔ problem is a new-intent
  operation, not a refinement.
- **`intent`** — the normalized representation built up during Phase 2.
  Each field is a single string or list of strings. Use the user's
  verbatim phrasing; do not paraphrase.
- **`intent.root_cause`** — ordered list. Step 0 is the symptom; each
  subsequent step is the next "why" deeper. In feature mode this is
  usually `null` or `[]` (omitted from `intent.<slug>.md`).
- **`phase_completed`** — the most-recently-finished phase. The resume
  map (below) is keyed off this.
- **`verified_at`** / **`merged_at`** — ISO-8601 timestamps with
  timezone offset (e.g. `2026-05-24T15:30:00+09:00`). Use the user's
  local timezone.

## Resume map

Keyed off `phase_completed` AND `run_mode`:

| `run_mode` | `phase_completed` value | Resume at |
|---|---|---|
| `create` | `worktree_created` | Phase 5 (emit intent.<slug>.md + intent.<slug>.html + commit) |
| `create` | `artifacts_emitted` | Phase 6 (human gate + merge) |
| `create` | `human_confirmed` | nothing — run complete; offer to remove worktree if it still exists |
| `update` | `worktree_created` | Phase 5u (emit refined artifacts) |
| `update` | `artifacts_emitted` | Phase 6u (human gate + merge with update marker) |
| `update` | `human_confirmed` | nothing — run complete; offer to remove worktree if it still exists |

If the user is `inside-intent-worktree` but the state file is missing
→ refuse and ask the user to either remove the worktree (`git -C
"${MAIN_CHECKOUT}" worktree remove <path>`, no `--force`) or supply a
state file.

## Persistence rule

Write the state file:

1. **At Phase 4 step 4** (first write): immediately after the worktree
   is created and the gitignore is committed. The file captures
   everything decided so far (language, mode, intent, slug, ids,
   paths) plus `phase_completed: worktree_created`.
2. **At Phase 5** after artifacts are committed: update
   `phase_completed: artifacts_emitted`.
3. **At Phase 6** after the merge: update `phase_completed:
   human_confirmed`, write `merged_at`.

If the agent crashes between writes, the state reflects the last
successful checkpoint, which is the right thing to resume from.

## What this state file is NOT

- It is NOT a transcript. The Phase 2 elicitation dialog is in chat
  history; only the *final* normalized intent lives here.
- It is NOT the artifact. `intent.<slug>.md` is the human-and-AI-readable
  artifact; this state file is a JSON sidecar for resumability.
- It is NOT version-controlled. It's gitignored deliberately — the
  worktree commit is the canonical record, the state file is local
  working state.
- It is NOT shared with downstream skills. They read
  `intent.<slug>.md`, not `.intent-state.json`. The handoff contract
  is the markdown file.

## Honest limitations

- Concurrent runs in the same shell session share `$$` but get
  different `$RANDOM` — so `INTENT_ID` collisions are vanishingly
  unlikely but not impossible. If a collision happens, the worktree
  creation will fail at Phase 4 (path already exists) and Phase 4's
  collision handler asks the user to pick a different slug or resume.
- If the user manually deletes `.intent-state.json` mid-run, the
  worktree becomes unresumable. Phase 0 refuses with a message
  telling them to remove the worktree and start over.
- If two intent runs are in flight for different slugs (intentional),
  they're fully independent — different worktrees, different branches,
  different state files. Phase 0 distinguishes by which worktree the
  user is currently inside.
