# Autonomous implementation loop — generation rules

The implementer's defining property: **no per-step human confirmation**.
The loop iterates the work queue in source order and generates prose
or slide content without pausing. This file defines per-item context
loading, the 8K-token cap, the `[[stub-id]]` transformation invariant,
scope discipline, and the blocker enumeration.

## Per-item loop

For each queue item, in source order:

1. **Mark** `status: in_progress`, write `started_at`.
2. **Load context** — see "Context loading" below.
3. **Generate** prose (text) or slide content (structured) per the
   stub's `purpose / audience / key_claims / acceptance_criteria /
   length_budget`. Output in `OUTPUT_LANGUAGE`.
4. **Transform** every `[[stub-id]]` reference per
   [output-formats.md](output-formats.md).
5. **Apply** via `Edit` / `Write`:
   - **text** → append to TARGET_PATH. Emit an explicit
     `<a id="<stub-id>"></a>` anchor immediately BEFORE the
     section's human-readable heading so `#<stub-id>` resolves
     regardless of the heading's slug (see output-formats.md).
   - **structured** → update state `work_queue[i].generated_content`
     (and `spec_payload.title` if missing) for later `render_pptx.py`
     invocation. `work_queue[]` is the canonical state shape; there
     is no top-level `stubs[]` array.
   Never shell `sed`.
6. **Mark** `status: completed`, write `files_touched` + `completed_at`.
7. Print: `implemented item <i>/<N>: <stub_id>`.

The loop does NOT run validators per-item — that's Phase 4, batched.

## Context loading — dep stubs + 8K cap

For the stub `S` being implemented:

1. **Always**: `S.spec_payload` (9 fields).
2. **For each dep in `S.spec_payload.dependencies`**:
   - **Backward dep** (already generated this run): load
     `state.work_queue[i].generated_content` (the actual prose).
   - **Forward dep** (not yet generated this run): load only
     `state.work_queue[i].spec_payload.purpose +
     spec_payload.key_claims` (the summary).

3. **8K-token cap on accumulated dep context**. Compute token
   estimate per dep prose chunk (or summary) and degrade older deps
   to summary first when the cap would be exceeded.

   ### Token estimate algorithm (v1)

   ```
   total_chars             = count(non-whitespace Unicode scalars in chunk)
   hangul_syllable_count   = count(U+AC00..U+D7A3 in chunk)

   if total_chars == 0:
       tokens ≈ 0                                # whitespace-only chunk
   elif (hangul_syllable_count / total_chars) > 0.30:
       tokens ≈ max(word_count × 1.3,
                    hangul_syllable_count × 1.1)  # Hangul-heavy path
   else:
       tokens ≈ word_count × 1.3                  # English path
   ```

   - `word_count` is whitespace-delimited tokens.
   - The `max(...)` form for Hangul-heavy chunks conservatively
     **over-estimates** Korean tokens (the safe direction). Korean
     BPE tokenizers produce ~1 token per syllable, so a single
     5-syllable word like "안녕하세요" really is ~5 tokens, not 1.3.
   - English path approximation `word_count × 1.3` is the
     standard BPE-tokenizer rule-of-thumb.
   - **Exact tokenizer measurement is v1.5**. This estimate is
     deliberately conservative — error direction is over-degrading
     (summarizing more deps), not under-degrading (overstuffing).

4. **Track degraded deps** in state for Phase 5 surfacing:
   `state.work_queue[i].dep_context_degraded = ["<dep-id>", ...]`.
   The Phase 5 self-verification report shows this so the human
   reviewer can decide whether full-prose context would have helped.

## Generation rules per OUTPUT_STACK

### text (api-spec / tech-spec / runbook)

- Append to TARGET_PATH directly (markdown).
- Each stub becomes a section. **MANDATORY**: emit an explicit
  `<a id="<stub-id>"></a>` anchor immediately before the human
  heading. The human heading itself follows the per-DOCTYPE
  convention in [output-formats.md](output-formats.md) (e.g. api-spec
  `## <METHOD> <path>`, tech-spec `## <stub-title>`, runbook
  `### Step N — <action>`). Without the explicit anchor,
  `validate_doc_completeness.py` fails because the heading slug
  rarely matches the stub-id (`context` stub ↔ `## System Overview`
  heading slug `system-overview` — no match).
- Write the prose in `OUTPUT_LANGUAGE`.
- `[[stub-id]]` → markdown link `[link-text](#<stub-id>)`.

### structured (ppt)

- Do NOT write to TARGET_PATH per-item; that's a binary file
  produced by `render_pptx.py` at end-of-queue.
- Update `state.work_queue[i].generated_content` with the per-slide
  body content. If `spec_payload.title` is missing, populate it
  from `purpose` or the bullet text — `render_pptx.py` reads
  `spec_payload.title` for the slide title. The state shape is
  `work_queue[]` (canonical per state-and-resume.md); there is no
  top-level `stubs[]` array.
- `[[stub-id]]` → text reference like `(see slide N)` for inline
  cross-refs (python-pptx `hyperlink.slide` action injected at
  render time per `render_pptx.py` provenance contract).
- The render script injects each stub_id as the FIRST LINE of the
  slide's speaker notes (provenance contract — verified by
  `validate_anchors.py --pptx` when a plan is supplied).

## `[[stub-id]]` transformation contract (load-bearing)

Every `[[stub-id]]` in a stub's `key_claims` /
`acceptance_criteria` / `open_questions` MUST be transformed to
target-format anchor syntax when generating the prose:

| OUTPUT_STACK | DOCTYPE | Transformation |
|---|---|---|
| text | api-spec | markdown `[<title>](#<stub-id>)` — `<stub-id>` matches the explicit `<a id="<stub-id>"></a>` anchor at the endpoint section |
| text | tech-spec | markdown `[<title>](#<stub-id>)` — anchor before section heading |
| text | runbook | markdown `[step N](#<stub-id>)` — preserve "step N" in link text; `<stub-id>` matches the anchor |
| structured | ppt | python-pptx slide-jump action; inline text `(see slide <N>)` |

**Never ship literal `[[stub-id]]` to the user-facing document.**
Phase 4's `validate_anchors.py` would catch this with a precise
error pointing at the line.

## Scope discipline (load-bearing)

The implementer is **prose/slide-generation only**. It MUST NOT:

- Re-plan: don't add stubs the planner didn't emit; don't merge or
  split stubs; don't re-order; don't re-classify SCALE.
- Edit planner artifacts: `document-plan.md`,
  `document-structure.mmd`, `document-structure.html` are
  **read-only**. Touching them is a forbidden action.
- Edit `parse_frontmatter.py` (mirror discipline; planner-side is
  canonical).
- Ship prose without a planner marker (or chat-gate for micro/local).

See [forbidden-actions.md](forbidden-actions.md) for the full list.

## Blocker triggers

The ONLY allowed pauses in Phases 0–5. On blocker, mark item
`status: blocked` with `blocker_reason`, set
`phase_completed: impl_in_progress`, exit cleanly:

- **Missing dependency stub** — `stub.dependencies` references an
  id not in the queue.
- **Impossible acceptance criterion** — criterion requires data /
  evidence not available from the stub spec or generated context.
- **Target file unwritable** — TARGET_PATH cannot be created (parent
  dir doesn't exist) or path exists with content (Q7 refusal already
  in Phase 1).
- **Validation auto-fix exhausted** — Phase 4 budget hit (3 for
  text; 0 for structured).
- **Source-hash mismatch on resume** — planner artifacts changed
  since extraction.
- **Conflicting concurrent edit** — `git status` shows unexpected
  changes inside the worktree.

Surface to user: last action, blocker reason, suggested next steps,
how to resume (`/document-implementer` from within the worktree).

## Commit cadence

- **text**: commit every N=5 completed items OR end-of-queue,
  whichever first. Stage only `files_touched` paths (bash array,
  not space-joined string). Secrets sniff per
  [forbidden-actions.md](forbidden-actions.md) before commit.
- **structured**: single commit at end-of-queue after
  `render_pptx.py` produces TARGET_PATH. pptx is binary; per-N-slide
  commits aren't diff-reviewable. Note: pptx files are NOT
  git-LFS-tracked by default in this repo.

## Honest limitations

- v1 generation quality depends on the LLM's prose ability in
  `OUTPUT_LANGUAGE`. The skill enforces structure but not stylistic
  excellence.
- v1 token estimate is approximate. Exact tokenizer-based
  measurement is v1.5.
- v1 does NOT verify that generated prose actually MEETS each
  acceptance criterion — that's the human reviewer's job at Phase 6
  via the explicit checklist (Q8).
