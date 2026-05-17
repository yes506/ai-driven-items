# Validation + auto-fix policy

Phase 4 runs the project's compile/type-check/test command after the
implementation loop has emptied the work queue. Failure triggers a
bounded auto-fix loop. Beyond the budget, validation failure is a
blocker.

## Validation command — provenance

The planner's `.planner-state.json` is gitignored and therefore not
portable across runs. The implementer resolves `validation_command`
in **this priority order at Phase 1**:

1. **Auto-detect from the current worktree's build files** — `pom.xml`
   / `build.gradle*` → Java, `pyproject.toml` / `setup.py` → Python,
   `tsconfig.json` → TypeScript, `go.mod` → Go, `Cargo.toml` → Rust.
2. **If still ambiguous** (monorepo with multiple build files,
   `unknown` stack, or non-standard project layout): ask the user
   once, document the answer in the run for resume.

Recorded commands by stack:

| Stack | Validation command |
|---|---|
| Java (Gradle) | `./gradlew build` (compile + test) |
| Java (Maven) | `mvn verify` |
| Python | `pytest -x && mypy --strict <package>` |
| TypeScript | `tsc --noEmit && npm test` |
| Go | `go build ./... && go test ./...` |
| Rust | `cargo build && cargo test` |

The implementer runs the **broader** command (compile + test) than the
planner did (compile-only on empty skeletons). The planner's job was
"do interfaces type-check"; the implementer's job is "do bodies pass
tests".

## Auto-fix loop

```
Run validation_command
  ├─ exit 0 → Phase 4 done, move to Phase 5
  └─ exit != 0 →
       attempt = 1
       while attempt <= MAX_AUTOFIX_ATTEMPTS:
         1. Capture full stderr + stdout (cap at 200 lines tail —
            longer outputs are usually repeats of the same failure)
         2. Diagnose: which queue items' files are implicated by the
            errors? Cross-check each implicated path against
            `work_queue[].files_touched` — if a path is NOT in that
            set, treat it as a blocker (a hostile test could otherwise
            emit a fake error pointing at a sensitive non-queue file
            to bait the loop into editing it). Constrain the fix to
            files that ARE in the union of `files_touched`.
         3. Generate fix(es). Apply via Edit/Write.
         4. Re-run validation.
         5. If exit 0: done. Else: attempt += 1
       end while
       if still failing: BLOCKER — see "Failure escalation" below
```

`MAX_AUTOFIX_ATTEMPTS` default: **3**. Rationale: one attempt to fix
the obvious cause, one to fix what the first fix broke, one
contingency. Beyond that, the loop is thrashing and a human should
look.

**Oscillation detection (within the budget)**: hash the staged diff
after each attempt's fix. If attempt N+1 produces the same hash as
some prior attempt, the loop is cycling between two states; emit the
"VALIDATION BLOCKER" escalation immediately rather than burning the
remaining attempts on the same cycle. This converts a confusing
"exhausted 3 attempts" message into a more actionable "oscillating
between attempts N and N+1".

## Auto-fix scope discipline

The fix loop has the same scope discipline as the main implementation
loop ([implementation-loop.md](implementation-loop.md) — "Scope
discipline"):

- May edit files the loop already wrote.
- May edit imports / type annotations in those files.
- May NOT add new files, rename existing public names, change method
  signatures the planner committed, or "fix" code that the loop didn't
  write (unless the failure is provably caused by it — and even then,
  surface as a blocker first; the planner's contract is meant to be
  authoritative).
- May NOT relax tests. Failing tests are signal, not noise. If a test
  the loop did NOT write is failing, that's a blocker — the
  implementation introduced a regression and a human should decide
  whether to fix the impl or the test.
- May NOT touch the `validation_command` itself (e.g., editing
  `package.json` test scripts to skip failing tests). Refuse.

## Failure escalation — blocker format

When `MAX_AUTOFIX_ATTEMPTS` is exhausted, print:

```
VALIDATION BLOCKER after N auto-fix attempts.

Last command:       <validation_command>
Last exit code:     <N>
Last error summary: <tail 20 lines>

Items implicated:   <list of work-queue item_ids whose files appear in errors>

Attempted fixes:
  attempt 1: <one-line summary of what was tried>
  attempt 2: <...>
  attempt 3: <...>

Suggested next steps:
  - Inspect <files> manually
  - Re-run /codebase-implementer from inside this worktree to resume
    after manual fixes (the resume gate reads .implementer-state.json)
  - OR abort this run and re-plan with the planner if the spec is wrong
```

Then exit cleanly. Do NOT merge. Do NOT clean up the worktree — the
user needs it for inspection.

## Special cases

### Pre-existing failures

If `validation_command` was already failing on `${BASE_BRANCH}` before
the implementer made any change, the loop will see those failures
along with any it caused. To distinguish:

- **Phase 2** (right after worktree creation, BEFORE Phase 3 starts):
  record a baseline run of `validation_command` on the fresh worktree
  HEAD (`${BASE_BRANCH}` content) as `baseline_validation_exit` in
  `.implementer-state.json`.
- If baseline is non-zero, warn the user at Phase 2 BEFORE entering
  Phase 3: "Baseline `${BASE_BRANCH}` validation is failing. The
  implementer can still proceed, but Phase 4 will count fixing those as
  blockers (not part of the planned scope). Continue?" — require
  explicit `proceed` token. Default is refusal.

### Slow validation commands

If the baseline validation run measured in Phase 2 took longer than
10 minutes, the auto-fix budget drops to 1 attempt (long iteration
cycles waste user time and the model has worse signal on big
failures). Surface this at Phase 2: "Baseline validation took
N minutes; auto-fix budget will be 1 attempt per pass." Persist the
adjusted `max_autofix_attempts` in `.implementer-state.json`.

**Late-emerging slowness** (baseline was fast but post-implementation
runs are slow because the generated code added tests / fixtures /
slow integration paths): if Phase 4 attempt 0 itself exceeds 10
minutes — even though the Phase-2-derived budget was 3 — drop the
remaining budget to 1 for this run and onwards. Re-record
`max_autofix_attempts` so subsequent resumes inherit the adjusted
budget. Surface at the time of the first slow run: "Phase 4 attempt 0
took N minutes (vs N_baseline at baseline); auto-fix budget reduced
to 1 for the rest of this run."

### Flaky tests

A test that passes attempt N and fails attempt N+1 with no code change
between is flaky. If the loop observes this (a re-run of an unchanged
build flips outcome), report as a blocker rather than retry — the
implementer is not the right place to debug flakes.
