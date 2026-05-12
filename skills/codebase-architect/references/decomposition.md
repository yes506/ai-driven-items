# Pipeline-node decomposition

## The rule

**One method = one pipeline stage = one node.**

An "interface" (or language-equivalent abstraction — Protocol / trait / etc.)
**aggregates** related methods that share a responsibility, lifecycle, or
collaboration boundary. It is NOT one-method-per-interface in the
single-responsibility extreme; it is one-method-per-stage with cohesive
clustering at the interface level.

## Cohesion test (use this to decide what goes in one interface)

Methods belong on the same interface when they share at least two of:

- **State** — they read/write the same private state of the implementing
  type
- **Lifecycle** — they're called in a known sequence on the same instance
  (open → use → close; init → step → finalize)
- **Collaboration boundary** — they're invoked by the same upstream
  caller(s) and call the same downstream collaborators
- **Failure domain** — when one fails, the others typically can't proceed
  without coordination

Methods that share only the package or only the input type usually do not
belong on the same interface — that's coincidence, not cohesion.

## Concrete example — order processing pipeline

E2E flow: receive request → validate → reserve inventory → charge payment
→ persist order → notify customer → publish event.

**Naive ("god interface")** — DO NOT generate:

```java
interface OrderService {
  Order receive(Request r);
  Validation validate(Order o);
  Reservation reserve(Order o);
  Charge charge(Order o);
  void persist(Order o);
  void notify(Order o);
  void publish(Order o);
}
```

**Decomposed (cohesive clustering)** — what this skill generates:

| Interface | Methods | Cohesion source |
|---|---|---|
| `OrderIntake` | `receive`, `validate` | `lifecycle` — both methods operate on a single Order as it advances through the intake stage (raw → validated); `validate` is meaningful only on the output of `receive` |
| `InventoryReservation` | `reserve`, `release` | `lifecycle` — paired methods on a Reservation aggregate |
| `PaymentCharger` | `authorize`, `capture`, `refund` | `state` — all three read/write the same payment-state machine |
| `OrderRepository` | `save`, `findById`, `markStatus` | `collaboration` — invoked by the same upstream pipeline stage to mediate persistence |
| `CustomerNotifier` | `notify` | single responsibility; may grow if more notification channels appear |
| `OrderEventPublisher` | `publish` | `failure_domain` — event-bus failures must not block the synchronous Order path |

Each method is one node. Each interface is a cohesive group.

## How to enumerate stages from Phase 1's plan

Walk the dominant control flow described in the project plan. For each
observable transition (input → transform → output), name it as one stage.
Capture in a table:

| Node # | Stage | Inputs | Outputs | Side effects |
|---|---|---|---|---|
| 1 | receive request | HTTP body | parsed Order | none |
| 2 | validate | parsed Order | validated Order | none |
| 3 | reserve inventory | validated Order | Reservation | inventory mutation |
| ... | ... | ... | ... | ... |

Then group stages into interfaces by the cohesion test above.

## When a stage doesn't fit a single method

If a stage requires a stateful sub-pipeline (e.g., a streaming join), it
becomes its own *interface* with multiple methods, each representing a
sub-stage. Don't force a multi-step process into one method — that
violates the "one method = one node" rule by hiding nodes inside
implementation that doesn't exist yet.

## Anti-patterns to flag in self-verification

- **God-interface**: an interface with 7+ methods spanning multiple
  cohesion sources. Split it.
- **Method-shaped class**: a wrapper class with one `execute()` method
  whose docstring describes a multi-stage pipeline. Decompose `execute`
  into named stages on cohesive interfaces.
- **Flow-of-control hidden in method body**: a method whose Postconditions
  field implies orchestration of other interfaces. That's not a node;
  that's a workflow. Promote it to a separate `*Workflow` interface OR
  refactor into discrete method nodes.
