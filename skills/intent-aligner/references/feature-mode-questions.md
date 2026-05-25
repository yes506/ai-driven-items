# Phase 2 — Question bank for `feature` mode

Use when the user arrived with a concrete thing-to-build in mind
(a feature, app, screen, endpoint, tool). The mode classifier in
[mode-detection.md](mode-detection.md) is what picks this bank.

Each pass below lists the topic, a few example opening prompts, and
the **output it should produce** (where it lands in the intent markdown). The
three techniques from [elicitation-techniques.md](elicitation-techniques.md)
(Socratic + 5 Whys + example/counter-example) apply across every
pass — these prompts are just the seed.

Run passes in the order listed unless the user steers otherwise. Don't
batch.

---

## Pass 1 — Persona: who is this for?

**Topic**: The human who will use this thing, in enough specificity
that the rest of the conversation can refer to them.

**Opening prompts** (pick one, then drill):
- "Who's the *single specific person* (or small team) who'd use this?
  Job title, what they do day-to-day, what tools they live in."
- "Is this for you, your teammates, your customers, an internal
  audience? Walk me through who first."
- "If only one type of person ever used this, who'd you pick? Why?"

**5 Whys** (gently): "Why does *this* persona need it more than
others?"

**Produces**: `intent.persona` (single sentence).

---

## Pass 2 — Goal: what does it do for them?

**Topic**: One sentence on what the thing *is*, framed in terms of
what changes for the persona.

**Opening prompts**:
- "In one sentence — what does the persona *do* with this that they
  can't do today?"
- "What's the headline outcome? Not the feature list — the outcome."
- "If you had to put this on a sticker, what does it say?"

**5 Whys**: "What's that outcome in service of? What happens if they
can't do it?"

**Produces**: `intent.goal` — one sentence in the **"For `<persona>`,
`<outcome>`" form** (see [output-schema.md](output-schema.md) → "Why
some content appears in two places"). The persona prefix is what
makes the goal survive the planner's rubric, which asks "what does
this project do *for whom*?" — if persona is generic, drop the
prefix and capture the genericness in Open Questions.

---

## Pass 3 — Concrete happy path

**Topic**: A walk-through of one specific moment where the thing earns
its keep.

**Opening prompts**:
- "Walk me through one specific use of this, end to end. The persona
  opens it / triggers it / receives it — then what?"
- "Pick the most common scenario and tell it like a story. Names,
  numbers, screens, whatever's relevant."
- "What's the first thing they see, and what's the last thing they do
  before they're done?"

**Drilling**: If the user stays abstract, ask "what would that look
like *specifically*?" or "give me a real example from last week."

**Produces**:
- `intent.examples[]` (at least one entry; usually 1–3) — full
  narrative form, the user's verbatim scenario. Survives in the HTML
  for human verification.
- `intent.success_criteria[]` gains a parallel entry rendering the
  most-concrete example as an **observable scenario** form (e.g. "A
  support agent searches by customer email and sees 30 days of
  timestamped actions"). Fold is mandatory because the planner's
  rubric drops the standalone `## Examples` section from its
  synthesis — without the fold, the concrete scenario signal is lost
  at planner normalization (see [output-schema.md](output-schema.md)
  "Why some content appears in two places"). Skip ONLY if the
  example is already verbatim a success criterion (rare in practice).

---

## Pass 4 — Counter-examples: what should NOT happen?

**Topic**: Things that look adjacent or in-scope but are explicitly
not — the boundary.

**Opening prompts**:
- "What's something that LOOKS like it should be part of this, but
  shouldn't? Why not?"
- "If you saw a draft of this and it had `<feature X>` in it, would
  that feel right, wrong, or scope-creep? Why?"
- "Where would you draw the line between this thing and the next
  thing?"

**Why this matters**: This is the strongest disambiguator. Without
it, the planner downstream will likely overshoot scope.

**Produces**:
- `intent.counter_examples[]` (at least one entry) — full form, the
  user's verbatim phrasing with the reason intact. Survives in the
  HTML for human verification.
- `intent.out_of_scope[]` — same entries reshaped as `<non-goal>
  (counter-example: <reason>)` so the planner's `Out-of-scope`
  rubric field captures both the boundary AND the reasoning. The
  fold is mandatory because the planner's normalization drops the
  standalone `## Counter-examples` section from its synthesis (see
  [output-schema.md](output-schema.md) "Why some content appears in
  two places").

---

## Pass 5 — Constraints

**Topic**: The fixed-in-stone facts the planner has to work around.

**Opening prompts**:
- "What's NOT up for debate? Tech stack, deployment target, deadline,
  compliance, team familiarity?"
- "Anything we have to *avoid*? (incompatible vendors, legacy systems
  to not touch, regulatory limits)"
- "What's the budget — time, money, people — for getting this in
  front of the persona?"

**Drilling**: For each constraint, ask "why this constraint?" — some
will turn out to be assumptions in disguise, others are real.

**Produces**: `intent.constraints[]`.

---

## Pass 6 — Success criteria

**Topic**: How will we know it worked? Measurable wherever possible.

**Opening prompts**:
- "Three months after this ships, how would you know it was worth
  building? What changed for the persona?"
- "What's the leading indicator the persona is using this well?"
- "What's the lagging indicator that, if it doesn't move, means we
  built the wrong thing?"
- "If you can't measure it directly, what's the closest proxy?"

**Drilling**: Push on whether each criterion is observable. Vague
criteria ("they like it") become open questions.

**Produces**: `intent.success_criteria[]`.

---

## Pass 7 — Open questions sweep

**Topic**: Surface every "I don't know yet" that came up during
passes 1–6 and add anything the conversation revealed without
resolving.

**Opening prompts**:
- "Before I synthesize this, are there decisions we deferred or
  things we're guessing about?"
- "Anything that came up that we didn't dig into?"

**Produces**: `intent.open_questions[]`.

---

## Convergence check

Before moving to Phase 3 synthesis, verify:

- [ ] Persona is one specific sentence
- [ ] Goal is one sentence framed as the persona's outcome
- [ ] At least one concrete happy-path example captured
- [ ] At least one counter-example captured
- [ ] Constraints listed (or explicitly noted as "none yet")
- [ ] Success criteria listed (vague ones moved to open questions)
- [ ] Open questions list is the truthful set of unknowns

If any of these aren't true after three full passes, surface the gap
to the user and proceed to synthesis with the gap explicit in
`intent.open_questions`.
