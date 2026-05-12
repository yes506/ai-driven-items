# 9-field docstring schema

Every method on every emitted interface MUST carry these 9 fields. Missing
any field is a Phase 7 rubric failure on the "Docstring quality"
criterion.

## Fields

| # | Field | Purpose |
|---|---|---|
| 1 | **Responsibility** | One sentence describing what this method does, in the active voice |
| 2 | **Pipeline-position** | Predecessor stage(s) → THIS → successor stage(s) |
| 3 | **Inputs** | Each parameter: name, type, semantic constraint (not just type) |
| 4 | **Outputs** | Return type + semantic guarantee on success |
| 5 | **Side-effects** | I/O, mutations, time, randomness, network |
| 6 | **Preconditions** | What callers must ensure BEFORE invocation |
| 7 | **Postconditions** | What is guaranteed AFTER successful return |
| 8 | **Failure-modes** | Enumerated errors + how surfaced (exception/Result/error code) |
| 9 | **Collaborators** | Other interfaces/methods this method calls |

If a field is genuinely empty for a given method (e.g., no side effects),
write `None.` explicitly — do NOT omit the field.

## Per-language format

### Java (Javadoc)

```java
public interface OrderRepository {
    /**
     * Responsibility: Persist a validated Order to the canonical store.
     * Pipeline-position: PaymentCharger.capture -> THIS -> OrderEventPublisher.publish
     * Inputs:
     *   - order: Order — must be validated AND payment-captured (status >= CAPTURED)
     * Outputs: Order — same instance with non-null id and status PERSISTED
     * Side-effects: writes one row to ORDERS table; increments persisted_total metric
     * Preconditions: order.status == CAPTURED; order.id == null
     * Postconditions: order.id != null; row exists in ORDERS with status=PERSISTED
     * Failure-modes:
     *   - PersistenceException — row could not be written (db down, constraint)
     *   - IllegalStateException — preconditions violated
     * Collaborators: None. (terminal persistence step)
     */
    Order save(Order order);
}
```

### Python (PEP 257 with structured sections)

```python
from typing import Protocol

class OrderRepository(Protocol):
    def save(self, order: Order) -> Order:
        """Persist a validated Order to the canonical store.

        Responsibility: Persist a validated Order to the canonical store.
        Pipeline-position: PaymentCharger.capture -> THIS -> OrderEventPublisher.publish
        Inputs:
            order: Order — must be validated AND payment-captured (status >= CAPTURED)
        Outputs: Order — same instance with non-null id and status PERSISTED
        Side-effects: writes one row to ORDERS table; increments persisted_total
        Preconditions: order.status == CAPTURED; order.id is None
        Postconditions: order.id is not None; row exists with status=PERSISTED
        Failure-modes:
            PersistenceError — row could not be written
            ValueError — preconditions violated
        Collaborators: None. (terminal persistence step)
        """
        ...
```

### TypeScript (TSDoc)

```typescript
interface OrderRepository {
  /**
   * Responsibility: Persist a validated Order to the canonical store.
   * Pipeline-position: PaymentCharger.capture -> THIS -> OrderEventPublisher.publish
   * Inputs:
   *   - order: Order — must be validated AND payment-captured (status >= CAPTURED)
   * Outputs: Order — same instance with non-null id and status PERSISTED
   * Side-effects: writes one row to ORDERS table; increments persisted_total
   * Preconditions: order.status === 'CAPTURED'; order.id == null
   * Postconditions: order.id != null; row exists with status='PERSISTED'
   * Failure-modes:
   *   - PersistenceError — thrown when row could not be written
   *   - Error — thrown when preconditions violated
   * Collaborators: None. (terminal persistence step)
   */
  save(order: Order): Promise<Order>;
}
```

### Go (godoc)

```go
// OrderRepository persists validated Orders.
type OrderRepository interface {
    // Save persists a validated Order to the canonical store.
    //
    // Responsibility: Persist a validated Order to the canonical store.
    // Pipeline-position: PaymentCharger.Capture -> THIS -> OrderEventPublisher.Publish
    // Inputs:
    //   - order: *Order — must be validated AND payment-captured (Status >= Captured)
    // Outputs: *Order — same pointer with non-empty ID and Status == Persisted
    // Side-effects: writes one row to orders table; increments persisted_total
    // Preconditions: order.Status == Captured; order.ID == ""
    // Postconditions: order.ID != ""; row exists with Status == Persisted
    // Failure-modes:
    //   - ErrPersistence — row could not be written
    //   - ErrPrecondition — preconditions violated
    // Collaborators: None. (terminal persistence step)
    Save(ctx context.Context, order *Order) (*Order, error)
}
```

### Rust (rustdoc)

```rust
/// Persists validated Orders to the canonical store.
pub trait OrderRepository {
    /// Persist a validated Order to the canonical store.
    ///
    /// **Responsibility:** Persist a validated Order to the canonical store.
    /// **Pipeline-position:** `PaymentCharger::capture` -> THIS -> `OrderEventPublisher::publish`
    /// **Inputs:**
    /// - `order`: `Order` — must be validated AND payment-captured (status >= Captured)
    /// **Outputs:** `Order` — with `Some(id)` and status Persisted
    /// **Side-effects:** writes one row to orders table; increments persisted_total
    /// **Preconditions:** `order.status == Captured`; `order.id.is_none()`
    /// **Postconditions:** `order.id.is_some()`; row exists with status=Persisted
    /// **Failure-modes:**
    /// - `PersistenceError` — row could not be written
    /// - `ValidationError` — preconditions violated
    /// **Collaborators:** None. (terminal persistence step)
    fn save(&self, order: Order) -> Result<Order, OrderRepositoryError>;
}
```

## Quality bar

The docstring must be useful to:
- A human reviewer deciding whether the contract is sound
- A downstream Claude session implementing the body without re-asking
  what it should do

If a downstream agent would need to ask "what does this method do?", the
docstring failed.

## Common defects to flag in self-verification

- **Type-restating Inputs**: "order: Order — an order" — adds zero
  information. Inputs must capture *semantic* constraints.
- **Empty Failure-modes**: any non-trivial method has at least one
  failure mode. If the method genuinely cannot fail, write
  "None. (this method is total over its preconditions)" — but be sure
  that's actually true.
- **Postconditions echoing Inputs**: "Postconditions: returns the
  saved order" — that's the Outputs field. Postconditions describe
  effects on state observable to other code, not the return value.
- **Collaborators listing the receiver class**: collaborators are
  *other* interfaces this method calls. The implementing class itself
  is implicit and should not be listed.
