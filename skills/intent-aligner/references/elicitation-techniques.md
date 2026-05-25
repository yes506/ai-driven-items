# Elicitation techniques — Phase 2 backbone

Three techniques carry Phase 2. They are not alternatives — they are
**layers** applied across every pass of the question bank. The
mode-specific question banks
([feature-mode-questions.md](feature-mode-questions.md),
[problem-mode-questions.md](problem-mode-questions.md)) supply the
*topics*; this file supplies the *interrogation style*.

## Technique 1 — Socratic question loops

**What**: Open-ended questions that surface assumptions the user is
holding silently. Never yes/no, never leading.

**Why**: The user often knows more than they've said, but their first
articulation skips the parts they assume are obvious. Socratic
questions pull those assumptions into the open where they can be
verified or corrected.

**How to apply**:

- Prefer "what", "how", "when", "for whom" over "is it" / "do you".
- Echo the user's words back in your follow-up so they can hear them
  and notice anything off ("you said `<X>` — when you say `<X>`, what
  exactly counts? what would be `<X>`-adjacent but NOT `<X>`?").
- After each user answer, ask one clarifying follow-up before moving
  on. Stop when the user says "yes, exactly that" without adding
  anything new.

**Example pattern**:
- User: "I want a dashboard."
- Bad: "What charts do you want on it?" (jumps to implementation)
- Good: "What would a person *do* on this dashboard that they can't do
  today? Walk me through one specific moment."

## Technique 2 — 5 Whys / root-cause drilling

**What**: When the user states a *what* or a *symptom*, drill toward
the *why* underneath it. The "5" is a heuristic, not a quota — stop
when the chain stops yielding new information.

**Why**: Solving the surface symptom often misses the actual driver,
which means the planner downstream will plan the wrong thing. Loadbearing
in `problem` mode; usefully orthogonal in `feature` mode (it
turns "I want X" into "I want X *because* Y", which tells the planner
how to weigh trade-offs).

**How to apply**:

- After the user states a pain or a desired feature, ask "why?" (or
  "what's that in service of?", which is gentler).
- After their answer, ask "why?" again about *that* answer.
- Continue 3–5 levels deep, or until the user says "I don't know" or
  "that's just how it is" — those are also data and they go into
  Open Questions.
- Stop drilling when the next "why" would land on something out of
  scope (e.g., "because the company exists" — too high).

**Example pattern**:
- User: "Our local builds are slow."
- "Why is that hurting today?" → "I can't iterate."
- "Why does the iteration speed matter most?" → "We're shipping a
  payments rewrite under a deadline."
- "Why does build speed bottleneck the rewrite specifically?" → "Every
  change needs to be tested against the legacy contract, and I can
  only see if it works after a full build."
- (Now Phase 2 has a much sharper target than "speed up builds".)

**In `feature` mode**, drilling looks slightly different:
- User: "I want a dashboard."
- "What decision does the dashboard help someone make?"
- "Who makes that decision today, and what do they use instead?"
- "What goes wrong without the dashboard?"
- (The dashboard "want" is now grounded in a decision, a person, and a
  failure mode — which the planner can use to scope the feature.)

## Technique 3 — Example & counter-example

**What**: Ask for one concrete *happy path* example (a specific
moment, with names and times), and one or more *counter-examples*
(things that should explicitly NOT happen, even if they seem like
they'd fit). Both are required by Phase 2's convergence rule.

**Why**: This is the strongest disambiguator in the toolkit.
Abstractions are slippery; concrete examples force the user to commit
to a real shape. Counter-examples surface the *implicit* boundary —
the user knows what they don't want even when they can't articulate
what they do want.

**How to apply**:

- After a topic has been discussed in the abstract, ask: "Can you
  describe one specific moment / case / scenario where this would
  happen?" Push for concreteness — names, times, numbers, file paths,
  whatever's relevant.
- Then ask: "What's something that would feel adjacent to this — like
  it almost fits — but shouldn't be in scope? Why not?"
- Capture both verbatim in the intent. They become `examples[]` and
  `counter_examples[]` in the intent markdown.

**Example pattern**:
- User: "We need an audit log."
- Happy path: "Walk me through one moment when the audit log saves the
  day — what does someone search for, what do they see?"
- User: "When a customer disputes a charge, the support agent searches
  by their email and sees every action on their account in the last 30
  days, with timestamps and the actor."
- Counter-example: "What's something that LOOKS like it should be in
  the audit log but shouldn't be? Why?"
- User: "Internal-only state transitions like cache warm-ups —
  agents don't need to see them and they'd drown out the signal."
- (Now scope is much clearer than "we need an audit log".)

## How the three techniques mix per pass

For every pass of the question bank:

1. Open with a **Socratic** question on the pass topic.
2. After the user answers, apply **5 Whys** (1–3 levels) to ground the
   answer in its underlying purpose.
3. Before closing the pass, run one round of **example +
   counter-example** to verify scope.

Then echo the reflection ("here's what I'm hearing: …") and ask for
correction before moving to the next pass.

## Convergence rule

Stop iterating when (a) the user has confirmed each pass's reflection
without further correction, AND (b) at least one concrete happy-path
example AND one counter-example have been captured.

If after **three full passes** the intent is still ambiguous (the
user keeps revising the synthesis, or contradictions surface), stop
and surface the residual ambiguity as `Open questions` in the intent
rather than guessing. It is correct and useful to say "we converged
to a sharp intent with these three unknowns left open" — the planner
downstream can handle that.

## Anti-patterns to avoid

- **Don't batch all questions up front.** The user's earlier answers
  shape later questions; batching produces a survey, not an
  elicitation.
- **Don't propose a solution.** Phase 2 is for understanding intent,
  not designing the system. If the user asks "how should we build
  it?", defer: "let's lock the intent first, then `/codebase-planner`
  will design the build."
- **Don't accept the first answer as final.** The first answer is the
  one the user had pre-loaded. The real intent often surfaces in the
  3rd or 4th exchange.
- **Don't translate the user's own words into your own.** When you
  capture intent values into the intent markdown, use their phrasing, not a
  cleaner paraphrase — paraphrases lose specificity and the user
  can't recognize them in the verification HTML.
- **Don't skip the counter-example pass.** It's the load-bearing
  scope-defining technique. Skipping it is in the Forbidden Actions
  list in SKILL.md.
