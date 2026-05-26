# Phase 2 — Question bank for `problem` mode

Use when the user arrived with a pain or frustration in mind, with no
fixed solution yet. The mode classifier in
[mode-detection.md](mode-detection.md) is what picks this bank.

Each pass below lists the topic, a few example opening prompts, and
the **output it should produce** (where it lands in the intent markdown). The
three techniques from [elicitation-techniques.md](elicitation-techniques.md)
(Socratic + 5 Whys + example/counter-example) apply across every
pass — these prompts are just the seed.

Run passes in the order listed unless the user steers otherwise.
**5 Whys is the load-bearing technique in this mode** — Pass 4 makes
it explicit.

Don't batch.

---

## Pass 1 — Persona: whose pain?

**Topic**: The specific human (or team) hurt by this problem.

**Opening prompts** (pick one, then drill):
- "Whose problem is this — you, your team, an internal user, a
  customer? Be specific."
- "Who feels it the most? Who feels it second-most? How are they
  different?"
- "Is this hurting one person daily, or a hundred people occasionally?
  That changes everything downstream."

**Drilling**: Push past "everyone" — there is almost always one
persona who feels it most.

**Produces**: `intent.persona` (single sentence).

---

## Pass 2 — Concrete incident

**Topic**: The most recent specific moment the pain hurt. Names,
times, what they were trying to do.

**Opening prompts**:
- "When did this last bite? Walk me through the most recent specific
  incident."
- "Tell me about a time this hurt — what were you (or the persona)
  trying to do, what happened instead?"
- "What's the freshest example, even if it's small?"

**Why concrete**: Vague pains ("our deploys are flaky") generate vague
plans. A specific incident ("last Tuesday at 4pm, deploy 1247 hung for
22 minutes and I rolled back at 4:30") generates a sharp plan.

**Produces**: `intent.examples[]` (called "examples" but in problem
mode these are *incident reports* — keep them concrete). Renders
in the HTML's problem-mode positive column under the label
"Recent incidents (the pain we're solving)" / "과거에 발생한 사건"
— the renderer picks mode-aware labels per
[output-schema.md](output-schema.md). Pass 8 (Success criteria)
later turns the concrete incident into an observable scenario
(e.g. incident "deploy 1247 hung 22 minutes" → success criterion
"deploys complete in &lt;5 minutes p95"); Pass 2 just flags the
source incident.

---

## Pass 3 — Current workaround

**Topic**: What the persona does *today* to cope with the pain. There
is almost always something.

**Opening prompts**:
- "What do you (or the persona) do today to work around this? Even an
  ugly workaround counts."
- "If I told you we couldn't fix this for six months, what would you
  do in the meantime?"
- "Is there a hero on the team who manually handles this? What do they
  do?"

**Why this matters**: The workaround tells you (a) what the persona
*actually needs* the fix to do (they've already designed half the
solution), and (b) the cost of *not* fixing it (their workaround time
is the floor of the ROI).

**Produces**: A constraint-shaped insight — captured as a constraint
or a success criterion, sometimes both. Often becomes:
- `intent.constraints[]`: "must not break the manual workaround until
  the new solution is verified"
- `intent.success_criteria[]`: "<workaround-time> drops from X to ~0"

---

## Pass 4 — 5 Whys drill (root-cause chain)

**Topic**: From the symptom, drill to the underlying driver.

**Opening prompts**:
- "Let's drill in. You said `<symptom>`. Why does that happen?"
- After the user answers: "Why does *that* happen?"
- Continue 3–5 levels deep.

**Stopping rules**: stop when (a) the user says "I don't know" — that
becomes an open question, (b) the next "why" lands on something out
of scope, or (c) you've hit 5 levels.

**Produces**: `intent.root_cause[]` — the chain of whys, in order,
as an ordered list. The HTML renderer shows it as a horizontal
Symptom → Why 1 → … → Root cause flow.

If the chain reveals the *root cause* is not what the user originally
mentioned, surface it: "the surface symptom was `<X>`, but the chain
suggests the real lever is `<Y>` — should we re-target the intent at
`<Y>`?" Do not silently re-target.

---

## Pass 5 — Goal: what would relief look like?

**Topic**: One sentence on what "fixed" looks like, framed in terms of
what changes for the persona.

**Opening prompts**:
- "If this were no longer a problem, what would the persona's day look
  like instead?"
- "What's the shortest sentence that captures 'this is now solved'?"
- "What changes that you'd actually *notice*?"

**Why now and not earlier**: in problem mode, the goal is hard to
articulate before the root cause is named. Pass 4 gives Pass 5 the
words.

**Produces**: `intent.goal` — one sentence in the **"For `<persona>`,
`<outcome>`" form** (see [output-schema.md](output-schema.md) →
"Fields"). The persona prefix answers "what is this for whom?" in
one read. When persona is generic, drop the prefix and capture the
genericness in Open Questions.

---

## Pass 6 — Solution-space sketch (NOT a design)

**Topic**: Rough shape of what a fix could look like — but explicitly
NOT a detailed design. That's the planner's job.

**Opening prompts**:
- "Without designing it — what shape might a fix take? A new tool, a
  config change, a process change, a refactor?"
- "Are there constraints on *how* we can fix it? (e.g., 'can't
  introduce new services this quarter')"
- "What's an obvious fix that you'd *reject*, and why?"

**Drilling**: For each candidate shape, ask "what would have to be true
for this to be the right shape?" — answers go to constraints or open
questions.

**Produces**: `intent.in_scope[]` (the shapes worth exploring),
`intent.out_of_scope[]` (the rejected shapes + reasons),
`intent.constraints[]` (any new ones surfaced).

---

## Pass 7 — Counter-examples: what should NOT change?

**Topic**: Things that look adjacent or in-scope but are explicitly
not — the boundary, plus any "must not break" constraints from
related systems.

**Opening prompts**:
- "What's something a fix MIGHT inadvertently break that absolutely
  cannot break?"
- "What's another problem in the neighborhood that's tempting to
  bundle in, but we should not? Why?"
- "If the fix accidentally also did `<adjacent thing>`, would that be
  a bonus, neutral, or a problem?"

**Produces**: `intent.counter_examples[]` (at least one entry) —
full form, the user's verbatim phrasing with the reason intact.
Renders in the HTML's negative column under the problem-mode label
"Adjacent areas that must not break" / "절대 깨지면 안 되는 인접
영역" (mode-aware — see [output-schema.md](output-schema.md)). The
matching non-goals (things that look adjacent but shouldn't be in
scope) go in `intent.out_of_scope[]` as plain bullets — keep the
boundary in Out-of-scope and the reasoning in Counter-examples;
downstream skills can pair them when needed.

---

## Pass 8 — Success criteria

**Topic**: How will we know the problem is solved? Measurable wherever
possible.

**Opening prompts**:
- "Three months after a fix lands, what's the leading indicator that
  it worked?"
- "What's the lagging indicator? What number / event / qualitative
  signal moves?"
- "If we could only measure ONE thing to know this is solved, what?"

**Drilling**: Vague criteria ("things feel better") become open
questions. Push for the closest proxy.

**Produces**: `intent.success_criteria[]`.

---

## Pass 9 — Open questions sweep

**Topic**: Surface every "I don't know yet" from passes 1–8 and add
anything the conversation revealed without resolving.

**Opening prompts**:
- "Before I synthesize this, what did we defer or guess at?"
- "Any 'I'd need to check' moments we didn't follow up on?"

**Produces**: `intent.open_questions[]`.

---

## Convergence check

Before moving to Phase 3 synthesis, verify:

- [ ] Persona is one specific sentence
- [ ] At least one concrete incident captured in `examples`
- [ ] Current workaround documented (in constraints or success criteria)
- [ ] Root-cause chain has at least 3 entries (or a clear "we couldn't
      drill further because…" reason)
- [ ] Goal is one sentence framed as relief
- [ ] At least one counter-example captured
- [ ] Success criteria listed (vague ones moved to open questions)
- [ ] Open questions list is the truthful set of unknowns

If any of these aren't true after three full passes, surface the gap
to the user and proceed to synthesis with the gap explicit in
`intent.open_questions`.
