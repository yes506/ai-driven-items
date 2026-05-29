# DOCTYPE: tech-spec

Technical specification / design document. Stub primitive:
**per-section**. `OUTPUT_STACK = text`.

## When to pick this DOCTYPE

- The intent is to specify a system, feature, or architectural
  decision in prose form for engineering review.
- The audience is engineers (internal team, partner engineering,
  reviewer SMEs).
- The eventual deliverable is markdown or another text-stack format.
- Includes RFCs, design proposals, architecture overviews,
  cross-team alignment docs.

## Stub primitive: per-section

One stub = one section of the eventual document. Sections roughly
correspond to top-level (`##`) headings in the final markdown.

Typical tech-spec section pattern:
1. Context / problem statement
2. Goals + non-goals
3. Proposed approach
4. Alternatives considered
5. Implementation plan / phases
6. Risks + mitigations
7. Open questions

Not every tech-spec uses all of these — let the Phase 2 outline grow
from `In scope` and `Goals` captured at Phase 1, not from a template.

## Field interpretations

| Field | tech-spec interpretation |
|---|---|
| `id` | kebab-case section identifier (e.g. `context`, `proposed-approach`, `alternative-1-event-sourcing`) |
| `purpose` | The argumentative role this section plays in the doc (e.g. "establishes the constraint that forces approach X") |
| `audience` | `[reviewing engineers]` / `[implementation team]` / `[both]`; if the section is for an SME like security or compliance, name it |
| `key claims` | The load-bearing assertions the section will make. Tech-spec sections are argumentative — each claim should be defensible |
| `evidence sources` | Existing code paths, prior tech-specs, benchmarks, dashboards, prior incidents — anything that backs a claim |
| `dependencies` | Other sections this one references. E.g. `risks` typically depends on `proposed-approach` |
| `acceptance criteria` | What makes the section "complete" for review — e.g. "covers all 3 failure modes from the incident log", "includes 1 worked example" |
| `length budget` | Word-count target — `~200 words` for a short context section, `~1500 words` for the proposed-approach core |
| `open questions` | Decisions deferred to reviewer feedback; assumptions that need a yes/no from a specific person |

## Phase 2 (outline) shape

Numbered section list with a one-line summary per section:

```
1. Context — Why we need a new caching layer (audience: implementation team)
2. Goals — p95 latency under 50ms; cache hit rate above 90% (audience: reviewers)
3. Non-goals — Multi-region replication is out of scope (audience: all)
4. Proposed approach — Read-through cache with TTL + cache-aside writes
5. Alternatives considered — Write-through cache; CDN-only
6. Risks + mitigations — Cache stampede; stale reads during failover
7. Open questions — Should we co-locate cache with DB or in front of API?
```

## Validation hints (Phase 6)

For tech-spec, the Phase 7 "Evidence coverage" criterion is
particularly load-bearing — argumentative documents that fail to
cite evidence become "vibes-driven design" that can't survive
review. Encourage every claim in `key claims` to have at least one
`evidence sources` entry.

## Implementer handoff notes

`document-implementer` for tech-spec generates markdown with one
`##` heading per stub. Per-section prose synthesis follows the
claims and evidence in the stub.

`[[stub-id]]` transformation: markdown heading anchor `#<stub-id>`.

## Honest limitations

- v1 stub primitive is one-section-one-stub. A long section (e.g. a
  proposed-approach with 3 sub-mechanisms) can be split into 3 stubs
  during Phase 3 if the sub-mechanisms have meaningfully different
  audiences/evidence. Otherwise keep it as one stub with multiple
  bullets in `key claims`.
- Mermaid diagrams **inside** the tech-spec body are an implementer
  concern, not a planner concern — the planner-level
  `document-structure.mmd` is the stub-dependency graph, not
  body-content diagrams.
