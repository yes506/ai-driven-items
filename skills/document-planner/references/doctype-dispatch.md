# DOCTYPE dispatch — Phase 0.5 classification flow

`DOCTYPE` is a first-class state variable. Phase 0.5 classifies the
target document into one of the v1 roster values **before** picking
the scale lane, so per-doctype reference files load in time to inform
the rest of the workflow.

v1 roster: `api-spec | tech-spec | runbook | ppt`.

## Why DOCTYPE matters

Three downstream decisions key off it:

1. **Stub primitive in Phase 3** — per-endpoint (api-spec),
   per-section (tech-spec), per-step (runbook), per-slide (ppt).
2. **OUTPUT_STACK derivation** — `text` for api-spec/tech-spec/runbook;
   `structured` for ppt. Routes the downstream
   `document-implementer` toolchain.
3. **Per-doctype reference file loading** — `references/<doctype>.md`
   carries doctype-specific stub guidance, length-budget interpretation,
   and validation hints.

## Classification flow

Run in this order. Stop at the first definitive answer.

### Step 1 — Infer from plan-establisher `Goal` field

If a `plan.<intent-slug>.v<N>.md` was accepted at Phase 0.5 discovery,
attempt keyword inference against the `Goal:` section. Match
case-insensitively, first hit wins:

| Keyword pattern | DOCTYPE |
|---|---|
| `api`, `endpoint`, `rest`, `openapi`, `swagger`, `graphql` | `api-spec` |
| `spec`, `design`, `architecture` (when standalone — not in `api-spec` context), `rfc`, `proposal` | `tech-spec` |
| `runbook`, `incident`, `playbook`, `on-call`, `oncall`, `procedure`, `sop` | `runbook` |
| `deck`, `slides`, `presentation`, `pitch`, `keynote`, `pptx` | `ppt` |

If no keyword matches, skip to Step 2 without inferring.

### Step 2 — Confirm with user (single-question prompt)

If Step 1 produced an inference, echo it as a yes/no:

- **Korean**: `문서 종류를 <DOCTYPE>로 추정했습니다. 맞으면 "확인", 아니면 다른 종류를 알려주세요.`
- **English**: `I inferred DOCTYPE = <DOCTYPE>. Reply "confirm" to accept, or name a different type.`

If the user confirms, lock `DOCTYPE` and proceed.

If the user rejects or Step 1 had no inference, go to Step 3.

### Step 3 — Select-from-list

Present the v1 roster as a numbered list:

```
1. api-spec      — API endpoint reference (per-endpoint stubs)
2. tech-spec     — technical specification / design doc (per-section)
3. runbook       — operational procedure (per-step)
4. ppt           — slide deck (per-slide; structured output)
```

Accept either the number or the lowercase token. Reject anything else
and re-ask once. On second reject, go to Step 4.

### Step 4 — Unknown DOCTYPE (friendly refusal)

If the user names a doctype outside the v1 roster (e.g. `adr`,
`bilingual-doc`, `marketing-one-pager`):

```
I don't have a `references/<their-token>.md` yet, so I can't plan
a <their-token> at the right resolution. Options:
  (a) pick one of the v1 roster types and we proceed,
  (b) we add `references/<their-token>.md` as a follow-up ticket
      and re-invoke later.
Which would you like?
```

Do NOT proceed by mapping their token to the nearest roster value
silently — that hides a real gap.

## Interaction with OUTPUT_LANGUAGE

`OUTPUT_LANGUAGE` is captured immediately after DOCTYPE + AUDIENCE
in Phase 0.5. The default is to inherit dialog `LANGUAGE`, but
DOCTYPE + AUDIENCE often imply a different output language:

| DOCTYPE | AUDIENCE pattern | Recommended OUTPUT_LANGUAGE default |
|---|---|---|
| api-spec | external partners, customer integrators, public docs | English |
| api-spec | internal client teams (Korean shop) | Inherit dialog LANGUAGE |
| tech-spec | reviewing engineers (single-language team) | Inherit dialog LANGUAGE |
| tech-spec | cross-team / cross-region | English (lingua franca default) |
| runbook | on-call SREs (single-language team) | Inherit dialog LANGUAGE |
| ppt | mixed-audience deck | Ask explicitly — no good default |

If the inferred default would differ from dialog `LANGUAGE`, ask the
user explicitly. If they match, confirm with a single-line prompt
("Output language: <X>. Type `proceed` to continue or name another.").

OUTPUT_LANGUAGE is mandatory in all 4 lanes (frontmatter for
feature/system, chat-handoff block for micro/local) — the downstream
`document-implementer` depends on it for prose generation.

## Persistence

`DOCTYPE` is written to `.document-planner-state.json` at Phase 4
(feature/system) and into the chat-handoff block at end-of-flow
(micro/local). It is never inferred again on resume — the persisted
value is canonical.

## Multi-doctype projects

`document-planner` is **single-DOCTYPE per invocation**. If the user
wants to plan both an api-spec AND a deck for the same intent,
re-invoke with the same `INTENT_SLUG` and a distinct DOCTYPE — each
run gets its own worktree path
(`.worktrees/docplanner-<slug>-<id>`, distinct `DOCPLANNER_ID`).

Don't try to plan two doctypes in one run. The stub primitive,
OUTPUT_STACK, validators, and downstream implementer all assume a
single DOCTYPE at a time.

## Honest limitations

- Keyword inference is shallow; ambiguous goals will always require
  Step 2 confirmation.
- The v1 roster is intentionally narrow. Adding a doctype is a
  follow-up ticket, not a runtime decision — it requires authoring a
  new `references/<doctype>.md` with the stub primitive and
  length-budget interpretation defined.
