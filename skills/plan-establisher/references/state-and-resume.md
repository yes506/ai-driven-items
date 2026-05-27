# State and resume — `.plan-state.json`

The state file is the durable representation of an in-flight
plan-establisher run. It lives at the worktree root, is gitignored
(written to the worktree's `.gitignore` at Phase 4 step 3), and exists
only inside the worktree — never on `MAIN_CHECKOUT` / `${BASE_BRANCH}`.

If the skill crashes between phases, re-invoking it from inside the
worktree (`inside-plan-worktree`) reads this file and resumes from
the next phase after `phase_completed`.

## Schema

```json
{
  "language": "Korean | English",
  "intent_slug": "<the chosen intent.<slug>.md slug>",
  "plan_run_id": "<5-digit-epoch>-<pid>-<random>",
  "plan_version": 1,
  "main_checkout": "<absolute-path>",
  "base_branch": "dev",
  "intent": {
    "goal":              "<single sentence — possibly refined via Dim 1 resolution>",
    "in_scope":          ["...", "..."],
    "out_of_scope":      ["...", "..."],
    "constraints":       ["...", "..."],
    "success_criteria":  ["...", "..."],
    "open_questions":    ["...", "..."]
  },
  "seeds": [
    {
      "resource_slug":       "<from seeds/seed.<intent-slug>.<resource-slug>.md>",
      "source":              "<URL or absolute path>",
      "type":                "web | youtube | pdf | image | local-doc | local-code",
      "extracted_content":   "<from seed's ## Extracted content (intent-filtered)>",
      "relevance_rationale": "<from seed's ## Relevance rationale>"
    }
  ],
  "findings": [
    {
      "dimension":       1,
      "severity":        "blocker | major | minor",
      "locus":           "intent.constraints[2]",
      "description":     "<one sentence>",
      "resolution_mode": "auto | needs-user",
      "resolution":      {
        "mode": "selected-candidate | user-typed | deferred | auto",
        "text": "<verbatim resolution chosen / typed / explanation>"
      }
    }
  ],
  "proposed_scale_lane": "micro | local | feature | system",
  "lane_reasoning": "<paragraph>",
  "evidence_inventory": {
    "Goal":                   [{"seed_slug": "seed_slug_1", "relevance": "one-line relevance note"}, {"seed_slug": "seed_slug_2", "relevance": "..."}],
    "in_scope[0]":            [{"seed_slug": "seed_slug_3", "relevance": "..."}],
    "constraints[1]":         [],
    "success_criteria[0]":    [{"seed_slug": "seed_slug_2", "relevance": "..."}]
  },
  "phase_completed": "synthesis_confirmed | worktree_created | artifacts_emitted | human_confirmed",
  "verified_at": "<ISO-8601 — written at Phase 3 confirm-plan>",
  "merged_at":   "<ISO-8601 — written at Phase 6 confirm-merge>"
}
```

### Field notes

- **`language`** — written for the first time at Phase 4 (worktree
  creation). Before that, `LANGUAGE` lives only in memory. See
  [language-selection.md](language-selection.md).
- **`intent_slug`** — chosen at Phase 1 (auto-detect if single
  `intent.*.md`, prompt if multiple). Persisted at Phase 4.
- **`plan_version`** — the tentative `N` from Phase 1's scan,
  possibly bumped at Phase 5's race-guard re-scan. See
  [plan-naming-and-versioning.md](plan-naming-and-versioning.md).
- **`intent`** — the parsed 6 rubric fields loaded from
  `intent.<intent-slug>.md`. Values may be refined via Dim 1
  resolutions (Phase 3) before persisting. See
  [intent-loading.md](intent-loading.md).
- **`seeds`** — loaded from `seeds/seed.<intent-slug>.*.md` at Phase
  1. If `len(seeds) > 32` OR total content > 200KB, replace each
  entry's `extracted_content` and `relevance_rationale` with the
  string `"(see seeds/seed.<intent-slug>.<resource-slug>.md)"` to
  keep the state file lean — the renderer doesn't need them, only
  Phase 2 verification does, and Phase 2 has already run by the time
  the state file is written. See [seed-loading.md](seed-loading.md).
- **`findings`** — populated at Phase 2; resolutions added at Phase
  3. See [verification-dimensions.md](verification-dimensions.md)
  and [ambiguity-resolution.md](ambiguity-resolution.md).
- **`proposed_scale_lane`** + **`lane_reasoning`** — computed at
  Phase 3 synthesis. See `ambiguity-resolution.md`'s "Picking the
  proposed scale lane" section.
- **`evidence_inventory`** — mapping of plan rubric fields (using
  field paths like `Goal`, `in_scope[0]`, `constraints[1]`) to lists
  of contributing-seed entries. Each entry is `{seed_slug,
  relevance}` where `relevance` is the one-line note explaining how
  this seed informs the rubric field (same text that appears in the
  plan markdown's Evidence inventory bullet and in the HTML
  Evidence-inventory table). Empty list means "intent-only — no
  seeds contributed". Defensive resilience: the HTML renderer also
  accepts the legacy shape `["seed_slug_only", ...]` and renders
  slugs with an `(no relevance recorded)` placeholder — but new
  state files MUST emit the structured form so the contract in
  `output-schema.md` is satisfied.
- **`phase_completed`** — the most-recently-finished phase. The
  resume map (below) is keyed off this.
- **`verified_at`** / **`merged_at`** — ISO-8601 timestamps with
  timezone offset (e.g. `2026-05-27T15:30:00+09:00`). Use the user's
  local timezone.

## Resume map

| `phase_completed` value | Resume at |
|---|---|
| `synthesis_confirmed` | Phase 5 (emit plan artifacts). Phase 4 (worktree) already done by construction. |
| `worktree_created` | Phase 3 again — the worktree was created but synthesis hadn't been confirmed; safer to re-elicit confirmation than to assume prior synthesis is still valid. |
| `artifacts_emitted` | Phase 6 (human gate + merge) |
| `human_confirmed` | nothing — the run is complete; offer to remove the worktree if it still exists |

Earlier phase values (`intent_selected`, `verification_complete`,
`resolutions_complete`) are deliberately absent from this map.
Phase 4 is the first state-file write, so no resume can encounter
those values. If a future variant ever persists state earlier, both
the schema and this map should be updated together.

If the user is `inside-plan-worktree` but the state file is missing
→ refuse and ask the user to either remove the worktree (`git -C
"${MAIN_CHECKOUT}" worktree remove <path>`, no `--force`) or supply a
state file.

## Persistence rule

Write the state file:

1. **At Phase 4 step 4** (first write): immediately after the worktree
   is created and the gitignore is committed. The file captures
   everything decided so far (language, intent_slug, plan_version,
   intent, seeds, findings with resolutions, proposed_scale_lane,
   lane_reasoning, evidence_inventory) plus
   `phase_completed: worktree_created` → updated to
   `synthesis_confirmed` in the same write since Phase 3 has already
   completed by the time Phase 4 runs.

   *Important*: Phase 3 happens in-memory before Phase 4 (no disk
   writes); the worktree is created with the synthesis already
   confirmed, so the very first state-file write reflects
   `phase_completed: synthesis_confirmed`. The `worktree_created`
   value exists in the resume map only as a defensive checkpoint —
   it's possible if the agent crashes mid-Phase-4 between worktree
   creation and the synthesis-confirmed update, leaving the file
   with the earlier checkpoint.

2. **At Phase 5**:
   - **Before** writing the `.md` + `.html`: if Phase 5's race-guard
     bumps `plan_version`, persist the new version first so a crash
     mid-write leaves state pointing at the actually-used N.
   - **After** the batch commit (`git add plan.*.{md,html} && git
     commit` guarded with `diff --cached --quiet`): set
     `phase_completed: artifacts_emitted` and persist.

3. **At Phase 6** after the merge: update `phase_completed:
   human_confirmed`, write `merged_at`.

If the agent crashes between writes, the state reflects the last
successful checkpoint, which is the right thing to resume from.

## What this state file is NOT

- It is NOT a transcript. The Phase 2 verification dialog and Phase
  3 resolution Q&A are in chat history; only the *confirmed* final
  records live here.
- It is NOT the artifact. `plan.<intent-slug>.v<N>.md` is the
  human-and-AI-readable artifact; this state file is a JSON sidecar
  for resumability and for the HTML renderer.
- It is NOT version-controlled. It's gitignored deliberately — the
  worktree commits + the merged plan files are the canonical record,
  the state file is local working state.
- It is NOT shared with downstream skills. `codebase-planner` reads
  `plan.<intent-slug>.v<N>.md`, not `.plan-state.json`. The handoff
  contract is the markdown file.

## Honest limitations

- Concurrent runs in the same shell session share `$$` but get
  different `$RANDOM` — so `PLAN_RUN_ID` collisions are vanishingly
  unlikely but not impossible. If a collision happens, the worktree
  creation will fail at Phase 4 (path already exists) and the
  collision handler asks the user to resume the prior run.
- If the user manually deletes `.plan-state.json` mid-run, the
  worktree becomes unresumable. Phase 0 refuses with a message
  telling them to remove the worktree and start over.
- Multiple plan runs in flight for the same intent slug (different
  `PLAN_RUN_ID`s) are fully independent at the worktree level —
  different worktrees, different branches, different state files.
  They DO compete for the same version-number namespace at emit
  time; the Phase 5 race-guard catches that.
- Large `seeds` arrays (>32 seeds or >200KB content) are partially
  redacted in the state file to keep it lean — `extracted_content`
  and `relevance_rationale` become a path-reference placeholder.
  Resume can still proceed (Phase 5 emit doesn't re-read seeds; only
  Phase 2 did, and Phase 2 won't re-run from `synthesis_confirmed`).
  If a resume DOES need to re-run Phase 2 (`worktree_created`
  resume target), the seeds get re-loaded fresh from the seed
  files.
