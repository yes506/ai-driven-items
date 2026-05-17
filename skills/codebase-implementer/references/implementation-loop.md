# Autonomous implementation loop — body-generation rules

The implementer's defining property: **no per-step human confirmation**.
The loop iterates the work queue and generates code without pausing.
This file defines what the loop is allowed to do, what it must not do,
and what triggers the only allowed pause (a genuine blocker).

## Per-item loop

For each queue item, in order:

1. **Load context** — read the target file(s), neighboring files in the
   same package, and any collaborators referenced in the
   docstring/plan. Read tests for the file if they exist.
2. **Generate** the body / change per the item's spec. The
   constraint set depends on the item's `kind`:
   - **`method-body`** (system lane only): signature + 9 docstring
     fields → implementation body. The body MUST satisfy every
     postcondition and handle every failure-mode listed in the
     docstring. The `Collaborators` field (#9) is **authoritative for
     system lane** — methods named there are the ONLY external calls
     allowed in the body. Inventing a new collaborator = blocker.
   - **`plan-step`** (feature lane): prose step → minimal code change
     that satisfies the step. Stay within `files_hinted` plus their
     direct dependencies. Touching a file outside the hint set =
     blocker. **`collaborators_hinted` is a hint, NOT a hard
     constraint** — it was extracted from prose and is not schema-bound
     like system lane's field #9. Treat it as a starting point for
     reading context.
   - **`plan-bullet`** (micro / local lane): bullet → minimal change.
     Same `files_hinted` discipline as feature; same hint-not-constraint
     treatment of any `collaborators_hinted`.
3. **Apply** the change via `Edit` / `Write` (never shell `sed`).
4. **Mark the item done** in `.implementer-state.json` (`work_queue[i].status:
   completed`). This is what makes resume work mid-queue.

The loop does NOT run the validation command per-item — that's Phase 4,
batched across all items. Per-item compile would balloon runtime
without surfacing different signal than the end-of-queue pass.

## Scope discipline (load-bearing)

The implementer is **body-generation only**. It must NOT:

- Re-architect: don't introduce new interfaces, don't split an existing
  interface, don't move methods between interfaces.
- Refactor: don't rename existing public names (params, methods,
  classes), don't change visibility, don't change method signatures
  that the planner committed.
- Change package structure: don't move files, don't add new packages,
  don't reorganize imports beyond what's needed for the new body.
- Re-classify scale: if a "micro" item turns out to be 200 lines of
  work spanning four files, that's a blocker — surface it, don't
  silently expand.
- Add unrequested features, error handling for cases the docstring
  doesn't list, or "polish" to neighboring code.

If a body genuinely cannot be implemented without one of the above
(e.g., the docstring postcondition is impossible without splitting the
interface), that's a blocker. See "Blocker triggers" below.

## Allowed within-body decisions

These are AI judgment calls — no human prompt needed:

- Choice of local variable names, intermediate data structures, control
  flow style (early-return vs nested if, comprehension vs loop).
- Choice of standard-library helpers where the language has multiple
  reasonable options.
- Inline helper functions WITHIN the same file (not the same package —
  cross-file helpers are a refactor).
- Test additions that target the implemented method only and live
  under the project's existing test root. Adding a new test file in a
  new directory is a refactor — blocker.

## Blocker triggers (the ONLY allowed pause)

The user authorized: "OK to pause and ask if something is genuinely
blocking." A blocker is one of:

1. **Missing collaborator**: the docstring lists `Foo.bar` in field #9,
   but no interface/class named `Foo` exists in the codebase OR no
   method `bar` exists on the found `Foo`.
2. **Postcondition impossible under the listed inputs**: e.g.,
   postcondition says "returns sorted by `created_at`" but the input
   type has no `created_at` field.
3. **Failure-mode contradicts language idiom**: e.g., docstring says
   "returns `Result<T, E>` with `NotFound`" but the project uses
   exceptions exclusively (no `Result` type imported anywhere).
4. **Plan step refers to a file that doesn't exist** AND can't be
   reasonably inferred (e.g., `src/handler.ts` but the project's
   handlers live in `app/api/`).
5. **Validation auto-fix budget exhausted** (see
   [validation-and-autofix.md](validation-and-autofix.md)).
6. **Source-hash mismatch on resume**: the planner artifacts changed
   between the original queue extraction and now.
7. **Scope-expansion required**: the item can't be done without
   refactoring / re-architecting per the prohibitions above.
8. **Conflicting concurrent edits**: a file the loop is about to edit
   has uncommitted changes that the implementer didn't make
   (`git status --porcelain` shows it modified).

When a blocker fires:

- Stop the loop. Mark the current item as `blocked` with reason.
- Print: the blocker reason, the item, the relevant docstring/plan text,
  the file(s) involved, and 2 suggested resolutions (e.g., "re-run the
  planner with the missing collaborator added" / "manually edit the
  docstring and resume").
- Wait for explicit user instruction. Resume requires re-invoking
  `/codebase-implementer` from inside the worktree.

## Anti-thrash rules

- **Don't retry the same body twice in one pass.** If a generated body
  fails validation, the auto-fix loop (Phase 4) gets a bounded number
  of attempts to fix it — that's the only retry channel.
- **Don't read the same file more than ~3 times per item.** If you
  need it more, the item is under-specified — that's a blocker, not a
  reason to grep harder.
- **Don't generate speculative tests** beyond what the docstring's
  preconditions/postconditions implies. Test thrash is a real risk
  when generation is autonomous.

## What "autonomous" does NOT mean

- It does NOT mean "fast" — quality > throughput. A 30-method system
  lane may take an hour; that's fine.
- It does NOT mean "silent" — print a one-line "implemented item N of
  M: <item_id>" after each completion so the user can watch progress.
  Save the verbose reasoning (which the model is doing internally) by
  not printing the full diff per item; only on blocker or final summary.
- It does NOT mean "skip the human merge gate" — Phase 6 still
  prompts `confirm merge`. The autonomy is bounded to Phases 3-5.
