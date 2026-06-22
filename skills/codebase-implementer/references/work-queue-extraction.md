# Work-queue extraction — per scale

Phase 1 normalizes the planner handoff into a flat **work queue**: a
linear list of items the autonomous loop will iterate through. The
extraction rule differs per scale.

## System lane — from interface skeletons + 9-field docstrings

The planner emitted interface files (`.java` / `.py` / `.ts` / `.go` /
`.rs`) with method signatures and full 9-field docstrings but no
implementation bodies. Each **method** becomes one queue item.

Extraction:

1. **Walk the merged branch's source tree directly** — find all files
   matching the language-stack's source extension that contain
   docstrings with the 9-field tags (`Responsibility:`,
   `Pipeline-position:`, ..., `Collaborators:`) and either an `abstract`
   marker (Python / TypeScript) or an interface-style declaration
   (Java `interface`, Go `type ... interface`, Rust `trait`). Do NOT
   parse paths out of `architecture.html` — the HTML is a human-facing
   report, not a stable machine-parseable index. Cross-check the
   discovered set against `"$RUN_DIR/architecture.mmd"` (the Mermaid
   DAG of nodes; `RUN_DIR` = the trailer-resolved `planner_artifact_dir`)
   for sanity: if a node in the DAG has no matching skeleton file,
   surface as a discovery blocker.
2. Parse each interface file. For every method on every interface,
   produce a queue item:

```json
{
  "item_id": "iface.MethodName",
  "kind": "method-body",
  "scale": "system",
  "file_path": "src/.../OrderRepository.java",
  "interface_name": "OrderRepository",
  "method_signature": "Order save(Order order)",
  "docstring_fields": {
    "responsibility": "...",
    "pipeline_position": "...",
    "inputs": "...",
    "outputs": "...",
    "side_effects": "...",
    "preconditions": "...",
    "postconditions": "...",
    "failure_modes": "...",
    "collaborators": ["OrderEventPublisher.publish", "..."]
  }
}
```

3. **Order the queue by `pipeline_position`**: terminal-stage methods
   (no successors) come first only if they have no collaborators that
   are themselves unimplemented. Otherwise leaf-first topological sort
   on the `collaborators` graph. This minimizes the chance of writing a
   body that calls a not-yet-existing helper.

4. **If parsing fails on any method** (docstring missing a field, file
   doesn't compile to a recognizable AST): mark the queue item as
   `blocked` and capture the reason. The autonomous loop will surface
   blocked items as a batched question at end-of-discovery — do NOT
   skip them silently.

## Feature lane — from `"$RUN_DIR/plan.md"` (+ optional skeletons)

The planner emitted `"$RUN_DIR/plan.md"` (prose plan, 5-15
implementation steps) and `"$RUN_DIR/plan.mmd"` (Mermaid DAG), where
`RUN_DIR` = the trailer-resolved `planner_artifact_dir`. Skeletons are
optional at this lane.

Extraction:

1. Parse `"$RUN_DIR/plan.md"`. Each numbered step under a heading like
   "Implementation steps" or equivalent becomes one queue item. If the
   plan structure is ambiguous, fall back to: each `##`-level heading
   that contains imperative-mood prose ("Add", "Implement", "Refactor",
   "Wire", "Replace") is one item.

2. Queue item shape:

```json
{
  "item_id": "step-3",
  "kind": "plan-step",
  "scale": "feature",
  "step_title": "Wire up the rate-limiter to the request handler",
  "step_detail": "...verbatim prose from plan.md...",
  "files_hinted": ["src/handler.ts", "src/middleware/rate-limit.ts"],
  "collaborators_hinted": ["RateLimiter.acquire"]
}
```

3. **If `"$RUN_DIR/plan.mmd"` is present**, use it for ordering:
   topo-sort on the DAG, root-first. If absent, preserve
   `"$RUN_DIR/plan.md"` source order.

4. **If skeletons were also emitted** (feature lane with explicit
   `emit skeletons`): merge — each skeleton-method item is added in
   addition to the prose-step items, ordered by their pipeline position
   relative to nearest prose-step's `files_hinted`. Don't dedupe; a
   prose step that says "implement `RateLimiter.acquire`" and a
   skeleton method `RateLimiter.acquire` together signal the same work
   item, which the loop will detect at execution time.

## Micro / local lane — from chat plan

The planner emitted a 3-7 bullet plan in chat, then a
`scale: <lane>   marker: (plan-<lane>, human-confirmed)` line.

Extraction:

1. Read the most recent chat block that contains the marker. The
   bullets immediately preceding it are the plan.
2. Each bullet becomes one queue item:

```json
{
  "item_id": "bullet-1",
  "kind": "plan-bullet",
  "scale": "micro",
  "bullet_text": "...verbatim bullet...",
  "files_hinted": ["src/...", "..."]
}
```

3. Preserve bullet order — the planner prompted the user to confirm
   them in execution order. Topo-sorting tiny plans adds zero value.

## Universal queue invariants

- **Append-only during execution**: the autonomous loop may NOT add or
  reorder items mid-run. If a body-generation pass surfaces an
  unplanned helper that's needed, that's a blocker (see
  [implementation-loop.md](implementation-loop.md) — "Blocker
  triggers"), not a queue mutation.
- **Persist after extraction**: write the queue to
  `.implementer-state.json` under `work_queue` (see
  [state-and-resume.md](state-and-resume.md)) before Phase 3 starts so
  resume works after a mid-run crash.
- **Hash the source**: also record `source_hash` (sha256 of the
  artifact files for system/feature, or the chat block for micro/local)
  so resume can detect "user re-ran the planner and the plan
  changed" — surface that as a blocker rather than silently using the
  stale queue.

## Empty queue is a refusal

If extraction yields zero items, refuse with: "Planner marker is
present but no implementable items were extracted from the handoff.
Re-run the planner — the plan is empty." Don't silently merge nothing.
