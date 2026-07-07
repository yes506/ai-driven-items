#!/usr/bin/env python3
"""Stage 1c — the write engine. Consumes a PERSISTED plan and applies it.

Owns every irreversible effect: lock, write-gate redaction, CAS, the ln/mv
write primitives, and the two-phase ledger. The LLM never calls this with a
path — it supplies concept-id + category and this script resolves the path
deterministically (A5). Recovery re-runs this against the persisted plan; it
never re-distills (A6).

Plan schema (one JSON file, produced by the match step and persisted BEFORE
apply — see references/matching-and-update.md):
  { "evidence_id": str,
    "mode": "manual"|"hook",
    "units": [ { "unit_id", "proposed_action": create|update|propose|skip,
                 "target_concept_id", "category", "knowledge_confidence",
                 "match_confidence", "reason",
                 "note_body"?,            # full markdown for create
                 "delta"?,                # append-delta section for update
                 "expected_current_sha256"? } ] }

Usage: apply_plan.py --skill-dir DIR --plan PLAN.json [--allow-finding HASH ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import kh_common as kh


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def write_create(target: Path, content: str) -> None:
    """CREATE via link(2): fails if target exists (collision refusal)."""
    target.parent.mkdir(parents=True, exist_ok=True)   # first run: category dir may not exist
    tmp = target.with_name(f".tmp.{os.getpid()}.{target.name}")
    tmp.write_text(content, encoding="utf-8")
    try:
        os.link(tmp, target)   # EEXIST if present -> refuse
    finally:
        tmp.unlink(missing_ok=True)


def write_update(target: Path, content: str) -> None:
    """UPDATE via rename(2): intentional atomic replace of an existing note."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".tmp.{os.getpid()}.{target.name}")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, target)    # atomic mv, replaces existing


def _atomic_write(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".tmp.{os.getpid()}.{target.name}")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, target)   # atomic even for the review folder (claude2 LOW)


def write_review_stub(cfg: dict, kind: str, concept_id: str, evidence_id: str,
                      payload: str, extra: dict, unit_id: str = "") -> Path:
    """Park a proposal/conflict/hook-draft in _needs-review (masked, typed).

    Everything the automated path declines to write to an active note lands here
    for `/knowledge-harvest --review` to drain. Payload AND plan-controlled
    metadata are masked so a stub never persists a raw secret (A2); every value is
    JSON-encoded so a newline/colon in a hostile value can't inject YAML; the path
    is sanitized so a hostile concept_id can't escape the review folder; unit_id
    keeps distinct same-concept candidates from clobbering each other."""
    stub = kh.needs_review_path(cfg, concept_id, evidence_id, kind, unit_id)
    fm = ["---", f"kind: {json.dumps(kind)}",
          f"concept-id: {json.dumps(mask(str(concept_id)), ensure_ascii=False)}",
          f"evidence_id: {json.dumps(mask(str(evidence_id)), ensure_ascii=False)}"]
    for k, v in extra.items():   # mask EVERY plan-controlled extra (reason, …)
        fm.append(f"{k}: {json.dumps(kh.mask_meta(v), ensure_ascii=False)}")
    fm.append("---\n")
    _atomic_write(stub, "\n".join(fm) + "\n" + mask(payload or ""))
    return stub


def quarantine(cfg: dict, concept_id: str, evidence_id: str, kind: str,
               masked_body: str, summary: dict, unit_id: str = "") -> Path:
    """Route a blocked write OUT of the active vault (A2). Raw is never kept;
    only a masked stub + redaction summary land in _needs-review."""
    stub = kh.needs_review_path(cfg, concept_id, evidence_id, kind, unit_id)
    fm = ("---\n"
          f"kind: {json.dumps(kind)}\n"
          f"concept-id: {json.dumps(mask(str(concept_id)), ensure_ascii=False)}\n"
          f"evidence_id: {json.dumps(mask(str(evidence_id)), ensure_ascii=False)}\n"
          f"redaction: {json.dumps(summary, ensure_ascii=False)}\n"
          "---\n\n")
    _atomic_write(stub, fm + masked_body)
    return stub


def mask(text: str) -> str:
    return kh.mask_secrets(text)


def gate_findings(content: str, allow: set[str]) -> list[dict]:
    return [f for f in kh.scan_secrets(content) if f["span_hash"] not in allow]


def apply_unit(cfg: dict, evidence_id: str, mode: str, unit: dict,
               allow: set[str]) -> dict:
    if not isinstance(unit, dict):
        return {"unit_id": None, "result": "failed", "reason": "unit-not-object"}
    uid = unit.get("unit_id")
    action = unit.get("proposed_action")
    concept_id = unit.get("target_concept_id")
    category = unit.get("category")
    if not uid or action not in ("create", "update", "propose", "skip"):
        return {"unit_id": uid, "result": "failed",
                "reason": f"malformed-unit:action={action!r}"}

    # Idempotency BEFORE any side effect (stub write or ledger row): a rerun of an
    # already-committed unit — of ANY action — is a no-op. (The active create/update
    # path additionally reconciles planned-without-committed below.)
    prior = kh.latest_unit_row(cfg, uid)
    if prior and prior.get("status") == "committed":
        return {"unit_id": uid, "result": "already-committed"}

    if action == "skip":
        kh.ledger_append(cfg, {"evidence_id": evidence_id, "unit_id": uid,
                               "concept_id": concept_id, "action": "skip",
                               "status": "committed", "reason": unit.get("reason", "")})
        return {"unit_id": uid, "result": "skip"}

    if action == "propose":
        stub = write_review_stub(cfg, "candidate", concept_id, evidence_id,
                                 unit.get("note_body") or unit.get("delta") or "",
                                 {"category": category, "reason": unit.get("reason", ""),
                                  "knowledge_confidence": unit.get("knowledge_confidence"),
                                  "match_confidence": unit.get("match_confidence")}, unit_id=uid)
        kh.ledger_append(cfg, {"evidence_id": evidence_id, "unit_id": uid,
                               "concept_id": concept_id, "action": "propose",
                               "status": "committed", "target_path": str(stub)})
        return {"unit_id": uid, "result": "propose", "path": str(stub)}

    # Hook-mode draft-only policy enforced HERE, not left to the LLM (the trust
    # boundary owns this). Unless config opts in, hook create/update never touches
    # an active note — it becomes a review candidate.
    hook_updates_ok = bool(cfg.get("hook", {}).get("hook_allow_active_updates", False))
    if mode == "hook" and not hook_updates_ok:
        stub = write_review_stub(cfg, "candidate", concept_id, evidence_id,
                                 unit.get("note_body") or unit.get("delta") or "",
                                 {"category": category, "downgraded_from": action,
                                  "reason": "hook draft-only (hook_allow_active_updates=false)"},
                                 unit_id=uid)
        kh.ledger_append(cfg, {"evidence_id": evidence_id, "unit_id": uid,
                               "concept_id": concept_id, "action": action,
                               "status": "committed", "target_path": str(stub),
                               "reason": "hook-downgraded-to-review"})
        return {"unit_id": uid, "result": "hook-downgraded", "path": str(stub)}

    # Confidence gate enforced at the boundary, not just in the match prompt: a
    # low/medium-knowledge unit, or a weak-match update, can never auto-write an
    # active note even if a malformed/adversarial plan says create/update.
    # Full gate table owned at the boundary (references/matching-and-update.md):
    # create only for a genuinely-new concept (no/low match); update only for a
    # strong match. Anything else -> review, never an active write.
    kc = unit.get("knowledge_confidence")
    mc = unit.get("match_confidence")
    gate_ok = kc == "high" and (
        (action == "create" and mc in ("none", "low", None))
        or (action == "update" and mc in ("exact", "high")))
    if not gate_ok:
        stub = write_review_stub(cfg, "candidate", concept_id, evidence_id,
                                 unit.get("note_body") or unit.get("delta") or "",
                                 {"category": category, "downgraded_from": action,
                                  "reason": f"confidence-gate: knowledge={kc} match={mc}"},
                                 unit_id=uid)
        kh.ledger_append(cfg, {"evidence_id": evidence_id, "unit_id": uid,
                               "concept_id": concept_id, "action": action,
                               "status": "committed", "target_path": str(stub),
                               "reason": "confidence-gate-downgraded"})
        return {"unit_id": uid, "result": "gate-downgraded", "path": str(stub)}

    # Per-unit field validation BEFORE resolve_target, which would otherwise
    # die() on a bad category/slug and abort every later unit in the batch.
    if category not in kh.CATEGORIES or not kh.is_safe_slug(concept_id) \
            or kh.scan_secrets(concept_id):   # never let a secret become a note filename
        return _fail(cfg, evidence_id, uid, concept_id,
                     f"malformed-unit: category={category!r} concept={concept_id!r}")
    target = kh.resolve_target(cfg, category, concept_id)  # A5/A9 (validates slug/cat)
    exists = target.exists()

    # Ledger is the authority (A7). Reconcile crash between planned and committed:
    last = kh.latest_unit_row(cfg, uid)
    if last:
        if last.get("status") == "committed":
            return {"unit_id": uid, "result": "already-committed"}
        # planned-without-committed: if the target already holds the intended
        # bytes, the write landed and only the commit row was lost -> reconcile,
        # never re-apply (which would double-append a delta).
        if last.get("status") == "planned" and exists \
                and sha256_file(target) == last.get("after_sha256"):
            kh.ledger_append(cfg, {"evidence_id": evidence_id, "unit_id": uid,
                                   "concept_id": concept_id, "action": action,
                                   "status": "committed", "target_path": str(target),
                                   "after_sha256": last.get("after_sha256")})
            return {"unit_id": uid, "result": "reconciled-committed"}

    if action == "create":
        # Global-flat identity: refuse if the concept already lives anywhere.
        other = kh.find_existing_concept(cfg, concept_id)
        if other is not None:
            return _fail(cfg, evidence_id, uid, concept_id,
                         f"concept-exists:{other.parent.name}")
        content = unit.get("note_body")
        if not content:
            return _fail(cfg, evidence_id, uid, concept_id, "create-missing-note_body")
        # The body is LLM output — the trust boundary validates it, never trusts
        # the workflow to have run validate_note. Frontmatter must agree with the
        # deterministically resolved concept-id + category (C).
        fm = kh.parse_frontmatter(content)
        if fm is None:
            return _fail(cfg, evidence_id, uid, concept_id, "create-no-frontmatter")
        body_errs = kh.validate_note_fields(fm, expect_concept=concept_id,
                                            expect_category=category)
        if body_errs:
            return _fail(cfg, evidence_id, uid, concept_id,
                         "invalid-note-body:" + "; ".join(body_errs))
        gate_content = content   # everything is new
    elif action == "update":
        if not exists:
            return _fail(cfg, evidence_id, uid, concept_id, "update-target-missing")
        delta = unit.get("delta")
        if not delta:
            return _fail(cfg, evidence_id, uid, concept_id, "update-missing-delta")
        current = target.read_text(encoding="utf-8")
        exp = unit.get("expected_current_sha256")
        # CAS is REQUIRED for update (A8): a missing/mismatched sha means the plan
        # was built against a different note state -> conflict, never a blind write.
        # Compare file BYTES so it matches build_index's content_sha256 (the
        # deterministic source the match step copies into the plan).
        if not exp or sha256_file(target) != exp:
            reason = "cas-missing" if not exp else "cas-mismatch"
            stub = write_review_stub(cfg, "conflict", concept_id, evidence_id, delta,
                                     {"category": category,
                                      "reason": f"{reason}: note state differs from match"},
                                     unit_id=uid)
            kh.ledger_append(cfg, {"evidence_id": evidence_id, "unit_id": uid,
                                   "concept_id": concept_id, "action": "update",
                                   "status": "failed", "reason": reason,
                                   "target_path": str(stub)})
            return {"unit_id": uid, "result": "conflict", "path": str(stub)}
        content = current.rstrip() + "\n\n" + delta.strip() + "\n"
        gate_content = delta     # only the NEW text — a pre-existing secret in the
                                 # note isn't re-introduced by us and mustn't brick updates (F4)
    else:  # unreachable (validated above) — defensive
        return _fail(cfg, evidence_id, uid, concept_id, f"unknown-action:{action}")

    # Write-gate redaction (A2/A3): fail closed, raw never enters an active note.
    findings = gate_findings(gate_content, allow)
    if findings:
        summary = kh.redaction_summary(findings)
        stub = quarantine(cfg, concept_id, evidence_id, "security-redaction",
                          mask(content), summary, unit_id=uid)
        kh.ledger_append(cfg, {"evidence_id": evidence_id, "unit_id": uid,
                               "concept_id": concept_id, "action": action,
                               "status": "failed", "reason": "security-redaction",
                               "redaction": summary, "target_path": str(stub)})
        return {"unit_id": uid, "result": "quarantined", "path": str(stub)}

    before = sha256_file(target) if exists else None
    after = sha256_text(content)
    kh.ledger_append(cfg, {"evidence_id": evidence_id, "unit_id": uid,
                           "concept_id": concept_id, "action": action,
                           "status": "planned", "target_path": str(target),
                           "before_sha256": before, "after_sha256": after})
    try:
        if action == "create":
            write_create(target, content)
        else:
            write_update(target, content)
    except FileExistsError:
        return _fail(cfg, evidence_id, uid, concept_id, "create-collision")
    if sha256_file(target) != after:
        return _fail(cfg, evidence_id, uid, concept_id, "post-write-sha-mismatch")
    kh.ledger_append(cfg, {"evidence_id": evidence_id, "unit_id": uid,
                           "concept_id": concept_id, "action": action,
                           "status": "committed", "target_path": str(target),
                           "after_sha256": after})
    return {"unit_id": uid, "result": action, "path": str(target)}


def _fail(cfg, evidence_id, uid, concept_id, reason) -> dict:
    kh.ledger_append(cfg, {"evidence_id": evidence_id, "unit_id": uid,
                           "concept_id": concept_id, "status": "failed",
                           "reason": reason})
    return {"unit_id": uid, "result": "failed", "reason": reason}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-dir", required=True, type=Path)
    ap.add_argument("--plan", required=True, type=Path)
    ap.add_argument("--allow-finding", action="append", default=[])
    args = ap.parse_args()
    cfg = kh.load_config(args.skill_dir)
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        kh.die(f"cannot read plan {args.plan}: {e}")
    if not isinstance(plan, dict) or not plan.get("evidence_id"):
        kh.die("plan must be a JSON object with an evidence_id")
    evidence_id = plan["evidence_id"]
    mode = plan.get("mode", "manual")
    allow = set(args.allow_finding)
    units = plan.get("units", [])
    if not isinstance(units, list):
        kh.die("plan.units must be a list")

    results = []
    with kh.Lock(cfg) as lock:            # lock scoped to write-commit only (A7)
        if not lock.acquire():
            print(json.dumps({"status": "locked",
                              "detail": "another harvest is committing"}))
            return 0
        for unit in units:
            results.append(apply_unit(cfg, evidence_id, mode, unit, allow))

    print(json.dumps({"status": "ok", "evidence_id": evidence_id,
                      "results": results}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
