# Phase 1 — Mode detection

Pick the right elicitation question bank by reading the *shape* of what
the user brought. Two modes; the distinction is whether the user
arrived with a **solution in mind** (feature) or a **pain in mind**
(problem). The same user can hold both at once, but they almost always
lead with one — that's the lead the skill follows.

## Why this matters

The question banks for the two modes look superficially similar but
have different *first* questions. Asking a feature-shape user "what
hurts?" is awkward and rate-limits the conversation; asking a
problem-shape user "what should it look like?" jumps to a solution
before the problem is understood, which is exactly what intent-aligner
is supposed to prevent.

## Signal table

| Signal in invocation | Suggests |
|---|---|
| Concrete noun for the thing-to-build (a dashboard, an API, a CLI, a page, a job) | `feature` |
| Verb of building / having ("I want to build X", "let's add Y", "we need a Z") | `feature` |
| User persona is implicit and singular ("for our admins", "for our customers") with the solution already imagined | `feature` |
| Verb of suffering ("I'm tired of", "it's painful that", "we keep getting", "Z is slow") | `problem` |
| Mention of a recent incident or workaround ("we paged again", "I had to copy-paste") | `problem` |
| Frustration without a stated solution ("I don't know how to fix this") | `problem` |
| Question form ("how should we…?", "what's the best way to…?") with no fixed answer | `problem` |
| Mixed (the user states both a pain AND a fixed solution they want built for it) | lead with `feature` if the solution is concrete; otherwise `problem` — and surface the pain explicitly as a sanity check during Phase 2 |

## Classification rule

1. Apply the signal table to the invocation utterance + any same-turn
   follow-up text.
2. If 2+ signals point to one mode and 0 point to the other → that
   mode wins.
3. If signals are mixed or absent → ask the user one disambiguating
   question (see "Ambiguity dialog" below) before classifying.
4. Echo the classification + a one-line reason. Wait for `confirm mode`
   (English token, never translated) or a re-classification request.
   Silence is not yes.

## Ambiguity dialog

When signals are mixed or absent, ask exactly one question and stop:

- **Korean**: `한 가지만 짧게 여쭤볼게요 — 머릿속에 이미 만들고 싶은 "것"(기능, 화면, 도구)이 그려져 있나요, 아니면 지금 겪고 있는 "불편함"이 있는데 어떻게 풀지는 아직 정하지 않은 상태인가요?`
- **English**: `One quick clarifier — do you already have a *thing* in mind to build (a feature, screen, tool), or is there a *pain* you're hitting and we haven't yet decided how to solve it?`

Map the user's answer:
- "thing" / "기능" / names a concrete artifact → `feature`
- "pain" / "불편함" / describes a frustration → `problem`
- "both" / "둘 다" → use the lead heuristic ("which is more pressing
  right now?") and pick that one; the other thread becomes a Phase 2
  side-channel

## Mid-flow re-classification

If, partway through Phase 2, the user's answers reveal the mode was
wrong (e.g., a "feature" turns out to be a workaround for a deeper
pain), it's allowed to switch modes mid-run:

1. Stop the current pass.
2. Surface the observation: "It sounds like the real driver here is
   `<X>` — should I switch to problem-mode questioning to dig into
   that?"
3. On user confirmation, set `MODE` to the new value, restart Phase 2
   from pass 1 of the new bank. The intent values captured so far
   carry over (don't discard); just re-direct further questioning.
4. Do NOT silently switch — always echo and confirm.

## What this phase does NOT do

- It does NOT pick a tech stack (that's the planner's job downstream).
- It does NOT validate that the chosen mode is "the right way to think
  about it" — the user owns that framing.
- It does NOT block further phases if the user picks a less-common mode
  for their input — the question bank is a default, not a corset.
