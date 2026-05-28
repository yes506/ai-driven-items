# State and resume — `.seed-state.json`

The state file is the durable representation of an in-flight
seed-gatherer run. It lives at the worktree root, is gitignored
(written to the worktree's `.gitignore` at Phase 4 step 3), and exists
only inside the worktree — never on `MAIN_CHECKOUT` / `${BASE_BRANCH}`.

If the skill crashes between phases, re-invoking it from inside the
worktree (`inside-seed-worktree`) reads this file and resumes from the
next phase after `phase_completed`.

## Schema

```json
{
  "run_mode": "standard | bootstrap | ideation | bootstrap, ideation",
  "language": "Korean | English",
  "intent_slug": "<the chosen intent.<slug>.md slug>",
  "seed_run_id": "<5-digit-epoch>-<pid>-<random>",
  "main_checkout": "<absolute-path>",
  "base_branch": "dev",
  "intent": {
    "mode":              "<bootstrap only — feature | problem>",
    "persona":           "<bootstrap only — single sentence>",
    "goal":              "<single sentence>",
    "in_scope":          ["...", "..."],
    "out_of_scope":      ["...", "..."],
    "constraints":       ["...", "..."],
    "success_criteria":  ["...", "..."],
    "examples":          ["bootstrap only — bullet list"],
    "counter_examples":  ["bootstrap only — bullet list"],
    "root_cause":        ["bootstrap problem-mode only — symptom + why-chain"],
    "open_questions":    ["...", "..."]
  },
  "bootstrap_sources": [
    {"type": "web | pdf | image | local-doc | prompt", "location": "<url/path or '(inline)'>", "content": "<prompt text — present only for type=prompt>", "extracted_at": "<iso>"}
  ],
  "bootstrap_intent_id":   "<bootstrap only — Intent ID for the emitted intent.md>",
  "bootstrap_verified_at": "<bootstrap only — when user typed confirm intent at Phase 1b.4>",
  "resources": [
    {
      "type":          "web | youtube | pdf | image | local-doc | local-code | ideation",
      "location":      "<URL or absolute file path OR 'ideation:<idea-slug>' for ideation type>",
      "resource_slug": "<sanitized slug used in seed.<intent-slug>.<resource-slug>.{md,html}>",
      "status":        "pending | extracted | confirmed | emitted | skipped-no-ytdlp | skipped-fetch-failed",
      "extracted_at":  "<ISO-8601 — written when status transitions to extracted>",
      "output_md":     "<relative path under seeds/, populated at emit time>",
      "output_html":   "<relative path under seeds/, populated at emit time>",
      "extracted_content":   "<intent-filtered excerpts / summary — populated at Phase 3>",
      "relevance_rationale": "<one paragraph linking to specific INTENT fields — populated at Phase 3>",
      "feasibility_check":   "<ideation-only — summary of web/code/file checks the agent ran>"
    }
  ],
  "phase_completed": "synthesis_confirmed | worktree_created | artifacts_emitted | human_confirmed",
  "verified_at": "<ISO-8601 — written at Phase 3 confirm-seeds>",
  "merged_at":   "<ISO-8601 — written at Phase 6 confirm-merge>"
}
```

### Field notes

- **`run_mode`** — discriminator for the three Phase 1 / 2 branches.
  Encoded as a single string; combo runs use a comma:
  - `standard` — existing `intent.<slug>.md` loaded; resources produce
    seeds (no intent emit).
  - `bootstrap` — no existing intent; Phase 1b captures ad-hoc intent
    AND emits `intent.<slug>.{md,html}` alongside seeds. See
    [intent-bootstrap.md](intent-bootstrap.md).
  - `ideation` — Phase 2 chose ideation (zero resources or user typed
    `ideate`); seeds come from AI/user dialogue + feasibility checks.
    See [ideation-mode.md](ideation-mode.md).
  - `bootstrap, ideation` — both branches taken in one run (Phase 1
    bootstrap captured intent, Phase 2 terminated into ideation). This
    is the only combined-mode string encoded; standard+ideation runs
    set `run_mode: "ideation"` (the upstream choice was "existing intent",
    which is the default — no extra discriminator needed beyond the
    presence/absence of `bootstrap_sources` in state).
- **`bootstrap_sources` / `bootstrap_intent_id` /
  `bootstrap_verified_at`** — populated only in bootstrap. Hold the
  user's starting inputs (prompt + URLs + files) and the Phase 1b.4
  confirmation timestamp. Schema and capture rules:
  [intent-bootstrap.md](intent-bootstrap.md).
- **`intent.mode` / `intent.persona` / `intent.examples` /
  `intent.counter_examples` / `intent.root_cause`** — bootstrap-only
  extensions of the parsed-from-file intent (which carries only 6
  rubric fields). Bootstrap captures the full intent-aligner shape so
  the bundled `render_intent_html.py` can produce the HTML the same
  way intent-aligner does.
- **`language`** — written for the first time at Phase 4 (worktree
  creation). Before that, `LANGUAGE` lives only in memory. See
  [language-selection.md](language-selection.md).
- **`intent_slug`** — chosen at Phase 1 (auto-detect if single
  `intent.*.md`, prompt if multiple). Persisted at Phase 4.
- **`intent`** — the parsed 6 rubric fields loaded from
  `intent.<intent-slug>.md`. See [intent-loading.md](intent-loading.md)
  for the parsing contract.
- **`resources`** — ordered list, populated incrementally:
  - Phase 2 (`resources_collected`): each entry has `type`, `location`,
    `resource_slug` (derived per [seed-naming.md](seed-naming.md)),
    `status="pending"`.
  - Phase 3 (`synthesis_confirmed`): `extracted_content`,
    `relevance_rationale`, `extracted_at` populated for each resource;
    `status` flips to `confirmed` (or `skipped-*` for failures).
  - Phase 5 (`artifacts_emitted`): `output_md`, `output_html`
    populated; `status` flips to `emitted`.
- **`phase_completed`** — the most-recently-finished phase. The resume
  map (below) is keyed off this.
- **`verified_at`** / **`merged_at`** — ISO-8601 timestamps with
  timezone offset (e.g. `2026-05-27T15:30:00+09:00`). Use the user's
  local timezone.

## Resume map

| `phase_completed` value | Resume at |
|---|---|
| `synthesis_confirmed` | Phase 5 (emit artifacts). Phase 4 (worktree) already done by construction. |
| `worktree_created` | Phase 3 again — the worktree was created but synthesis hadn't been confirmed; safer to re-elicit confirmation than to assume prior synthesis is still valid. |
| `artifacts_emitted` | Phase 6 (human gate + merge) |
| `human_confirmed` | nothing — the run is complete; offer to remove the worktree if it still exists |

Two values are deliberately absent from this map even though earlier
drafts listed them: `intent_selected` (Phase 1) and `resources_collected`
(Phase 2) are unreachable in practice. Phase 4 is the first state-file
write, so no resume can encounter those values. They were removed from
the schema for that reason; if a future variant ever persists state
earlier, both the schema and this map should be updated together.

If the user is `inside-seed-worktree` but the state file is missing
→ refuse and ask the user to either remove the worktree (`git -C
"${MAIN_CHECKOUT}" worktree remove <path>`, no `--force`) or supply a
state file.

## Persistence rule

Write the state file:

1. **At Phase 4 step 4** (first write): immediately after the worktree
   is created and the gitignore is committed. The file captures
   everything decided so far (language, intent_slug, intent, resources
   with their pending statuses + confirmed synthesis content from Phase
   3) plus `phase_completed: worktree_created` → updated to
   `synthesis_confirmed` in the same write since Phase 3 has already
   completed by the time Phase 4 runs.

   *Important*: Phase 3 happens in-memory before Phase 4 (no disk
   writes); the worktree is created with the synthesis already
   confirmed, so the very first state file write reflects
   `phase_completed: synthesis_confirmed`. The `worktree_created`
   value exists in the resume map only as a defensive checkpoint —
   it's possible if the agent crashes mid-Phase-4 between worktree
   creation and the synthesis-confirmed update, leaving the file
   with the earlier checkpoint.

2. **Inside the Phase 5 per-resource loop** (note: SKILL.md Phase 5
   uses a *single batch commit* at the end of the loop, not per-pair
   commits — earlier wording in this file said "after each seed pair
   is committed" and was wrong):
   - **Before** writing each seed pair to disk: persist the state file
     with the settled `resources[i].resource_slug` (post-collision-
     suffixing, if any). This way a crash mid-write leaves a state
     file pointing at the exact filename we were about to write — the
     subsequent resume re-checks against that exact slug.
   - **After** writing each seed pair (still inside the loop, before
     the final batch commit): update
     `resources[i].status="emitted"`, `output_md`, `output_html`, and
     persist again. This is the per-resource "done" marker.
   - **After the per-resource loop** and the single batch
     `git add seeds/ && git commit` (guarded with `diff --cached
     --quiet`): set `phase_completed: artifacts_emitted` and persist.
3. **At Phase 6** after the merge: update `phase_completed:
   human_confirmed`, write `merged_at`.

If the agent crashes between writes, the state reflects the last
successful checkpoint, which is the right thing to resume from.

## What this state file is NOT

- It is NOT a transcript. The Phase 2 intake dialog and Phase 3
  synthesis preview are in chat history; only the *confirmed* final
  per-resource records live here.
- It is NOT the artifact. Each `seeds/seed.<intent-slug>.<resource-slug>.md`
  is the human-and-AI-readable artifact; this state file is a JSON
  sidecar for resumability.
- It is NOT version-controlled. It's gitignored deliberately — the
  worktree commits + the merged seeds directory are the canonical
  record, the state file is local working state.
- It is NOT shared with downstream skills. They read each
  `seeds/seed.*.md`, not `.seed-state.json`. The handoff contract is
  the markdown files under `seeds/`.

## Honest limitations

- Concurrent runs in the same shell session share `$$` but get
  different `$RANDOM` — so `SEED_RUN_ID` collisions are vanishingly
  unlikely but not impossible. If a collision happens, the worktree
  creation will fail at Phase 4 (path already exists) and Phase 4's
  collision handler asks the user to resume the prior run or pick a
  different intent slug.
- If the user manually deletes `.seed-state.json` mid-run, the
  worktree becomes unresumable. Phase 0 refuses with a message
  telling them to remove the worktree and start over.
- Multiple seed runs in flight for the same intent slug (different
  `SEED_RUN_ID`s) are fully independent — different worktrees,
  different branches, different state files. Phase 0 distinguishes by
  which worktree the user is currently inside. The downstream `seeds/`
  directory accumulates contributions from all merged runs.
