#!/usr/bin/env python3
"""Contract tests for the knowledge-harvest deterministic scripts.

Covers the review-mandated matrix: CREATE collision refusal, UPDATE CAS
conflict, ledger planned/committed resume, denylist security quarantine WITHOUT
raw vault persistence, path-traversal rejection, low-confidence no-create,
malformed frontmatter, and the redaction self-domain false-positive guard.

Run: python3 tests/test_contracts.py   (exit 0 = all pass)
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import kh_common as kh  # noqa: E402

PASS, FAIL = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


def make_vault(tmp: Path) -> Path:
    skill = tmp / "skill"
    skill.mkdir()
    vault = tmp / "vault"
    (skill / "config.toml").write_text(f'[vault]\npath = "{vault}"\n')
    for cat in kh.CATEGORIES:
        (vault / "Knowledge" / cat).mkdir(parents=True)
    return skill


def note(concept_id: str, title: str, body: str = "current answer.") -> str:
    return (f"---\nschema-version: 1\nconcept-id: {concept_id}\n"
            f'title: "{title}"\ncategory: Tools\nstatus: active\n'
            f"created: \"2026-07-07\"\nupdated: \"2026-07-07\"\n---\n\n"
            f"## Current conclusion\n\n{body}\n")


def run_apply(skill: Path, plan: dict, tmp: Path) -> dict:
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    r = subprocess.run([sys.executable, str(SCRIPTS / "apply_plan.py"),
                        "--skill-dir", str(skill), "--plan", str(p)],
                       capture_output=True, text=True)
    return json.loads(r.stdout)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        skill = make_vault(tmp)
        cfg = kh.load_config(skill)

        # 1. CREATE writes a new note.
        out = run_apply(skill, {"evidence_id": "ev1", "mode": "manual", "units": [
            {"unit_id": "u1", "proposed_action": "create",
             "target_concept_id": "jwt-format", "category": "Tools",
             "knowledge_confidence": "high", "match_confidence": "none",
             "note_body": note("jwt-format", "JWT format")}]}, tmp)
        target = kh.knowledge_root(cfg) / "Tools" / "jwt-format.md"
        check("create writes note", out["results"][0]["result"] == "create" and target.exists())

        # 2. CREATE collision refusal: same concept-id again, different evidence.
        out = run_apply(skill, {"evidence_id": "ev2", "mode": "manual", "units": [
            {"unit_id": "u2", "proposed_action": "create",
             "target_concept_id": "jwt-format", "category": "Tools",
             "knowledge_confidence": "high", "match_confidence": "none",
             "note_body": note("jwt-format", "DUP")}]}, tmp)
        check("create collision refused", out["results"][0]["result"] == "failed"
              and out["results"][0]["reason"] in ("create-collision", "concept-exists:Tools"),
              str(out["results"][0]))
        check("collision left original intact", "DUP" not in target.read_text())

        # 3. UPDATE append-delta with correct CAS.
        cur_sha = kh.hashlib.sha256(target.read_bytes()).hexdigest()
        out = run_apply(skill, {"evidence_id": "ev3", "mode": "manual", "units": [
            {"unit_id": "u3", "proposed_action": "update",
             "target_concept_id": "jwt-format", "category": "Tools",
             "knowledge_confidence": "high", "match_confidence": "exact",
             "expected_current_sha256": cur_sha,
             "delta": "## Update 2026-07-08\n\nNew detail."}]}, tmp)
        check("update appended", out["results"][0]["result"] == "update"
              and "Update 2026-07-08" in target.read_text())

        # 4. UPDATE CAS conflict: stale expected sha.
        out = run_apply(skill, {"evidence_id": "ev4", "mode": "manual", "units": [
            {"unit_id": "u4", "proposed_action": "update",
             "target_concept_id": "jwt-format", "category": "Tools",
             "knowledge_confidence": "high", "match_confidence": "exact",
             "expected_current_sha256": "deadbeef",
             "delta": "## Update 2026-07-09\n\nShould not land."}]}, tmp)
        check("CAS conflict rejected", out["results"][0]["result"] == "conflict"
              and "2026-07-09" not in target.read_text(), str(out["results"][0]))

        # 5. Ledger records committed unit -> resume skips it.
        committed = kh.committed_units(cfg)
        check("ledger tracks committed",
              kh.unit_key("u1") in committed and kh.unit_key("u3") in committed)
        out = run_apply(skill, {"evidence_id": "ev3", "mode": "manual", "units": [
            {"unit_id": "u3", "proposed_action": "update",
             "target_concept_id": "jwt-format", "category": "Tools",
             "knowledge_confidence": "high", "match_confidence": "exact",
             "delta": "## Update DUP\n\ndup"}]}, tmp)
        check("resume skips committed unit",
              out["results"][0]["result"] == "already-committed"
              and "Update DUP" not in target.read_text())

        # 6. Denylist security quarantine: real credential never enters vault.
        secret = "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcd"
        out = run_apply(skill, {"evidence_id": "ev5", "mode": "manual", "units": [
            {"unit_id": "u5", "proposed_action": "create",
             "target_concept_id": "leaky-note", "category": "Tools",
             "knowledge_confidence": "high", "match_confidence": "none",
             "note_body": note("leaky-note", "leak", body=f"key is {secret}")}]}, tmp)
        leaky = kh.knowledge_root(cfg) / "Tools" / "leaky-note.md"
        check("secret quarantined not written",
              out["results"][0]["result"] == "quarantined" and not leaky.exists())
        # raw secret must not appear anywhere under the vault (stub is masked).
        leaked = any(secret in p.read_text(errors="ignore")
                     for p in kh.knowledge_root(cfg).rglob("*.md"))
        check("raw secret absent from vault", not leaked)
        ledger_txt = kh.ledger_path(cfg).read_text()
        check("raw secret absent from ledger", secret not in ledger_txt)

        # 7. Redaction self-domain false-positive guard: documenting formats is OK.
        doc = ("A JWT starts with `eyJ` and API keys look like `sk-...`. "
               "Never hardcode a home path.")
        findings = kh.scan_secrets(doc)
        check("format-documentation not flagged", findings == [], str(findings))

        # 8. Path traversal rejected by resolver.
        try:
            kh.resolve_target(cfg, "Tools", "../../etc/passwd")
            traversal_blocked = False
        except SystemExit:
            traversal_blocked = True
        check("path traversal rejected", traversal_blocked)

        # 9. Low-confidence propose never creates an active note.
        out = run_apply(skill, {"evidence_id": "ev6", "mode": "manual", "units": [
            {"unit_id": "u6", "proposed_action": "propose",
             "target_concept_id": "maybe-thing", "category": "Domain",
             "knowledge_confidence": "low", "match_confidence": "none",
             "reason": "uncertain"}]}, tmp)
        maybe = kh.knowledge_root(cfg) / "Domain" / "maybe-thing.md"
        check("low-confidence does not create", not maybe.exists()
              and out["results"][0]["result"] == "propose")

        # 10. build_index ignores operational dirs + flags malformed notes.
        (kh.knowledge_root(cfg) / "Tools" / "bad.md").write_text("no frontmatter here")
        r = subprocess.run([sys.executable, str(SCRIPTS / "build_index.py"),
                            "--skill-dir", str(skill)], capture_output=True, text=True)
        idx = json.loads(r.stdout)
        check("index built, malformed flagged", idx["count"] >= 1
              and any("bad.md" in e["path"] for e in idx["errors"]), str(idx))
        index_text = kh.state_dir(cfg).joinpath("index.jsonl").read_text()
        check("quarantine stub not indexed", "leaky-note" not in index_text)

        # 11. slugify determinism + Hangul fallback.
        check("slug deterministic", kh.slugify("Stop Hook Loop") == "stop-hook-loop")
        check("hangul falls back to hash", kh.slugify("한글개념").startswith("concept-"))

        # 12. Global-flat concept-id: same id in another category is refused.
        run_apply(skill, {"evidence_id": "ev7", "mode": "manual", "units": [
            {"unit_id": "u7", "proposed_action": "create",
             "target_concept_id": "cross-cat", "category": "Tools",
             "knowledge_confidence": "high", "match_confidence": "none",
             "note_body": note("cross-cat", "Tools one")}]}, tmp)
        out = run_apply(skill, {"evidence_id": "ev8", "mode": "manual", "units": [
            {"unit_id": "u8", "proposed_action": "create",
             "target_concept_id": "cross-cat", "category": "Pitfalls",
             "knowledge_confidence": "high", "match_confidence": "none",
             "note_body": note("cross-cat", "Pitfalls dup")}]}, tmp)
        pit = kh.knowledge_root(cfg) / "Pitfalls" / "cross-cat.md"
        check("cross-category concept-id refused",
              out["results"][0]["result"] == "failed"
              and out["results"][0]["reason"].startswith("concept-exists")
              and not pit.exists(), str(out["results"][0]))

        # 13. Redaction now catches PEM / ya29 / sk-proj (security round-3).
        check("PEM key flagged", bool(kh.scan_secrets(
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEabc+/def\n-----END RSA PRIVATE KEY-----")))
        check("ya29 token flagged", bool(kh.scan_secrets("ya29." + "Q" * 40)))
        check("sk-proj flagged", bool(kh.scan_secrets("sk-proj-" + "A" * 40)))

        # 14. Crash reconciliation: a planned-without-committed row whose target
        # already holds the intended bytes must NOT double-apply.
        tgt = kh.knowledge_root(cfg) / "Tools" / "jwt-format.md"
        after = kh.hashlib.sha256(tgt.read_bytes()).hexdigest()
        kh.ledger_append(cfg, {"evidence_id": "ev9", "unit_id": "u9",
                               "concept_id": "jwt-format", "action": "update",
                               "status": "planned", "target_path": str(tgt),
                               "after_sha256": after})
        before_len = len(tgt.read_text())
        out = run_apply(skill, {"evidence_id": "ev9", "mode": "manual", "units": [
            {"unit_id": "u9", "proposed_action": "update",
             "target_concept_id": "jwt-format", "category": "Tools",
             "knowledge_confidence": "high", "match_confidence": "exact",
             "delta": "## Update SHOULD-NOT-DOUBLE\n\nx"}]}, tmp)
        check("crash reconcile: no double-apply",
              out["results"][0]["result"] == "reconciled-committed"
              and len(tgt.read_text()) == before_len
              and "SHOULD-NOT-DOUBLE" not in tgt.read_text(), str(out["results"][0]))

        # 15. Robustness: malformed inputs reject cleanly, never crash.
        r = subprocess.run([sys.executable, str(SCRIPTS / "apply_plan.py"),
                            "--skill-dir", str(skill), "--plan", str(tmp / "nope.json")],
                           capture_output=True, text=True)
        check("missing plan file: clean error", r.returncode != 0
              and "Traceback" not in r.stderr, r.stderr[-200:])
        bad = tmp / "bad.json"; bad.write_text("{not json")
        r = subprocess.run([sys.executable, str(SCRIPTS / "apply_plan.py"),
                            "--skill-dir", str(skill), "--plan", str(bad)],
                           capture_output=True, text=True)
        check("malformed plan JSON: clean error", "Traceback" not in r.stderr)
        out = run_apply(skill, {"evidence_id": "ev10", "mode": "manual", "units": [
            {"unit_id": "u10", "proposed_action": "create",
             "target_concept_id": "no-body", "category": "Tools",
             "knowledge_confidence": "high", "match_confidence": "none"}]}, tmp)
        check("create without note_body: graceful fail",
              out["results"][0]["result"] == "failed", str(out["results"][0]))

        # 16. build_index survives hostile notes (tab-YAML, int concept-id, dir.md).
        badyaml = kh.knowledge_root(cfg) / "Tools" / "tabyaml.md"
        badyaml.write_text("---\nconcept-id:\tvalue: x\n---\nbody")
        intid = kh.knowledge_root(cfg) / "Tools" / "intid.md"
        intid.write_text("---\nconcept-id: 12345\ntitle: T\ncategory: Tools\n---\nb")
        (kh.knowledge_root(cfg) / "Tools" / "adir.md").mkdir()
        r = subprocess.run([sys.executable, str(SCRIPTS / "build_index.py"),
                            "--skill-dir", str(skill)], capture_output=True, text=True)
        check("build_index no crash on hostile notes",
              r.returncode == 0 and "Traceback" not in r.stderr, r.stderr[-200:])
        idx = json.loads(r.stdout)
        check("int concept-id flagged not indexed",
              any("intid.md" in e["path"] for e in idx["errors"]))

        # 17. prepare_source: binary stdin never crashes.
        r = subprocess.run([sys.executable, str(SCRIPTS / "prepare_source.py"),
                            "--skill-dir", str(skill), "--mode", "stdin"],
                           input=b"\xff\xfe\x00rubbish", capture_output=True)
        check("binary stdin: no crash", r.returncode == 0
              and b"Traceback" not in r.stderr, r.stderr[-120:])

        # 18. Redaction scan has no catastrophic-backtracking cliff (200KB < 2s).
        import time as _t
        blob = "a1b2c3d4" * 25600
        _start = _t.time()
        kh.scan_secrets(blob)
        check("200KB redaction scan is fast", (_t.time() - _start) < 2.0)

        # 19. Hook-mode draft-only: create/update never touch an active note
        # unless config opts in (round-4 trust-boundary fix).
        run_apply(skill, {"evidence_id": "ev11", "mode": "manual", "units": [
            {"unit_id": "u11", "proposed_action": "create",
             "target_concept_id": "hooktgt", "category": "Tools",
             "knowledge_confidence": "high", "match_confidence": "none",
             "note_body": note("hooktgt", "seed")}]}, tmp)
        htgt = kh.knowledge_root(cfg) / "Tools" / "hooktgt.md"
        seed_sha = kh.hashlib.sha256(htgt.read_bytes()).hexdigest()
        out = run_apply(skill, {"evidence_id": "ev12", "mode": "hook", "units": [
            {"unit_id": "u12", "proposed_action": "update",
             "target_concept_id": "hooktgt", "category": "Tools",
             "knowledge_confidence": "high", "match_confidence": "exact",
             "delta": "## Update\nHOOK-SHOULD-NOT-WRITE"}]}, tmp)
        nr = kh.knowledge_root(cfg) / "_needs-review"
        check("hook update downgraded to review",
              out["results"][0]["result"] == "hook-downgraded"
              and kh.hashlib.sha256(htgt.read_bytes()).hexdigest() == seed_sha
              and "HOOK-SHOULD-NOT-WRITE" not in htgt.read_text(), str(out["results"][0]))
        check("hook downgrade wrote a review stub", nr.exists()
              and any("candidate" in p.name for p in nr.glob("*.md")))

        # 20. propose writes a typed _needs-review candidate (not silent skip).
        out = run_apply(skill, {"evidence_id": "ev13", "mode": "manual", "units": [
            {"unit_id": "u13", "proposed_action": "propose",
             "target_concept_id": "maybe-x", "category": "Domain",
             "knowledge_confidence": "medium", "match_confidence": "medium",
             "reason": "uncertain", "note_body": "candidate detail"}]}, tmp)
        check("propose writes review candidate",
              out["results"][0]["result"] == "propose"
              and Path(out["results"][0]["path"]).exists()
              and "maybe-x" in out["results"][0]["path"], str(out["results"][0]))

        # 21. CAS mismatch writes a conflict stub (not a silent fail).
        out = run_apply(skill, {"evidence_id": "ev14", "mode": "manual", "units": [
            {"unit_id": "u14", "proposed_action": "update",
             "target_concept_id": "jwt-format", "category": "Tools",
             "knowledge_confidence": "high", "match_confidence": "exact",
             "expected_current_sha256": "stale", "delta": "## Update\nx"}]}, tmp)
        check("cas mismatch writes conflict stub",
              out["results"][0]["result"] == "conflict"
              and "conflict" in out["results"][0]["path"], str(out["results"][0]))

        # 22. Create-body frontmatter must agree with the resolved target.
        out = run_apply(skill, {"evidence_id": "ev15", "mode": "manual", "units": [
            {"unit_id": "u15", "proposed_action": "create",
             "target_concept_id": "good-slug", "category": "Tools",
             "knowledge_confidence": "high", "match_confidence": "none",
             "note_body": note("WRONG-SLUG", "mismatch")}]}, tmp)
        gs = kh.knowledge_root(cfg) / "Tools" / "good-slug.md"
        check("mismatched create body rejected",
              out["results"][0]["result"] == "failed"
              and "invalid-note-body" in out["results"][0]["reason"]
              and not gs.exists(), str(out["results"][0]))

        # 23. First create into an EMPTY vault (no category dirs) works.
        skill2 = tmp / "skill2"; skill2.mkdir()
        vault2 = tmp / "vault2"; (vault2 / "Knowledge").mkdir(parents=True)  # no category dirs
        (skill2 / "config.toml").write_text(f'[vault]\npath = "{vault2}"\n')
        out = run_apply(skill2, {"evidence_id": "ev16", "mode": "manual", "units": [
            {"unit_id": "u16", "proposed_action": "create",
             "target_concept_id": "first-note", "category": "Patterns",
             "knowledge_confidence": "high", "match_confidence": "none",
             "note_body": note("first-note", "first").replace("category: Tools",
                                                              "category: Patterns")}]}, tmp)
        check("empty-vault first create succeeds",
              out["results"][0]["result"] == "create"
              and (vault2 / "Knowledge" / "Patterns" / "first-note.md").exists(),
              str(out["results"][0]))

        # 24. Superseded note redirects instead of winning an exact match.
        kr = kh.knowledge_root(cfg)
        (kr / "Tools" / "old-way.md").write_text(
            "---\nschema-version: 1\nconcept-id: old-way\ntitle: Old\ncategory: Tools\n"
            "status: superseded\nsuperseded-by: new-way\naliases: [\"legacy way\"]\n---\nx")
        (kr / "Tools" / "new-way.md").write_text(
            "---\nschema-version: 1\nconcept-id: new-way\ntitle: New\ncategory: Tools\n"
            "status: active\n---\nx")
        subprocess.run([sys.executable, str(SCRIPTS / "build_index.py"),
                        "--skill-dir", str(skill)], capture_output=True, text=True)
        r = subprocess.run([sys.executable, str(SCRIPTS / "match_candidates.py"),
                            "--skill-dir", str(skill), "--title", "legacy way"],
                           capture_output=True, text=True)
        mc = json.loads(r.stdout)
        check("superseded redirects to successor",
              mc["exact"] and mc["exact"]["concept_id"] == "new-way"
              and mc["exact"].get("redirected_from") == "old-way", str(mc["exact"]))

        # 25. Self-domain friction: full git SHA is no longer quarantined; a real
        # URL credential still is.
        check("full git SHA not flagged",
              not kh.scan_secrets("fixed in " + "a1" * 20))
        check("url credential flagged",
              bool(kh.scan_secrets("db at postgres://admin:s3cretpw@host/db")))

        # 26. Review-stub path safety: a hostile target_concept_id can't escape
        # _needs-review into an active category folder (round-4 regression fix).
        before = set((kh.knowledge_root(cfg) / "Patterns").glob("*.md"))
        out = run_apply(skill, {"evidence_id": "evX", "mode": "manual", "units": [
            {"unit_id": "ux", "proposed_action": "propose",
             "target_concept_id": "../Patterns/escaped", "category": "Tools",
             "knowledge_confidence": "medium", "match_confidence": "medium",
             "note_body": "payload"}]}, tmp)
        after_p = set((kh.knowledge_root(cfg) / "Patterns").glob("*.md"))
        stub_path = Path(out["results"][0]["path"]).resolve()
        nrdir = (kh.knowledge_root(cfg) / "_needs-review").resolve()
        check("review stub cannot escape _needs-review",
              after_p == before and str(stub_path).startswith(str(nrdir)),
              str(out["results"][0]))

        # 27. Confidence gate at the boundary: low knowledge can't auto-create.
        out = run_apply(skill, {"evidence_id": "evY", "mode": "manual", "units": [
            {"unit_id": "uy", "proposed_action": "create",
             "target_concept_id": "low-create", "category": "Tools",
             "knowledge_confidence": "low", "match_confidence": "none",
             "note_body": note("low-create", "low")}]}, tmp)
        check("low-confidence create downgraded to review",
              out["results"][0]["result"] == "gate-downgraded"
              and not (kh.knowledge_root(cfg) / "Tools" / "low-create.md").exists(),
              str(out["results"][0]))

        # 28. Weak-match update can't auto-write an active note.
        jf = kh.knowledge_root(cfg) / "Tools" / "jwt-format.md"
        jf_sha = kh.hashlib.sha256(jf.read_bytes()).hexdigest()
        out = run_apply(skill, {"evidence_id": "evZ", "mode": "manual", "units": [
            {"unit_id": "uz", "proposed_action": "update",
             "target_concept_id": "jwt-format", "category": "Tools",
             "knowledge_confidence": "high", "match_confidence": "medium",
             "delta": "## Update\nweak-match-should-not-write"}]}, tmp)
        check("weak-match update downgraded",
              out["results"][0]["result"] == "gate-downgraded"
              and kh.hashlib.sha256(jf.read_bytes()).hexdigest() == jf_sha,
              str(out["results"][0]))

        # 29. Two same-concept propose units in one run -> two distinct stubs,
        # both payloads survive (no silent clobber).
        out = run_apply(skill, {"evidence_id": "evDup", "mode": "manual", "units": [
            {"unit_id": "d1", "proposed_action": "propose", "target_concept_id": "dupc",
             "category": "Tools", "knowledge_confidence": "medium",
             "match_confidence": "medium", "note_body": "FIRST-PAYLOAD"},
            {"unit_id": "d2", "proposed_action": "propose", "target_concept_id": "dupc",
             "category": "Tools", "knowledge_confidence": "medium",
             "match_confidence": "medium", "note_body": "SECOND-PAYLOAD"}]}, tmp)
        paths = {r["path"] for r in out["results"]}
        blob = "".join(Path(p).read_text() for p in paths)
        check("same-concept candidates don't clobber",
              len(paths) == 2 and "FIRST-PAYLOAD" in blob and "SECOND-PAYLOAD" in blob,
              str(out["results"]))

        # 30. Full gate table: exact-match create is downgraded, not created.
        out = run_apply(skill, {"evidence_id": "evXm", "mode": "manual", "units": [
            {"unit_id": "xm", "proposed_action": "create", "target_concept_id": "exactcreate",
             "category": "Tools", "knowledge_confidence": "high",
             "match_confidence": "exact", "note_body": note("exactcreate", "x")}]}, tmp)
        check("exact-match create downgraded",
              out["results"][0]["result"] == "gate-downgraded"
              and not (kh.knowledge_root(cfg) / "Tools" / "exactcreate.md").exists(),
              str(out["results"][0]))

        # 31. Update without expected_current_sha256 -> conflict (CAS required).
        (kh.knowledge_root(cfg) / "Tools" / "casreq.md").write_text(
            note("casreq", "orig"))
        out = run_apply(skill, {"evidence_id": "evCas", "mode": "manual", "units": [
            {"unit_id": "cr", "proposed_action": "update", "target_concept_id": "casreq",
             "category": "Tools", "knowledge_confidence": "high",
             "match_confidence": "exact", "delta": "## U\nNO-CAS"}]}, tmp)
        check("update without CAS becomes conflict",
              out["results"][0]["result"] == "conflict"
              and "NO-CAS" not in (kh.knowledge_root(cfg) / "Tools" / "casreq.md").read_text(),
              str(out["results"][0]))

        # 32. Secret-shaped concept-id never persists raw in a stub or the ledger.
        sec = "sk-ant-api03-ZYXWVUTSRQPONMLKJIHGFEDCBA9876543210zyxw"
        run_apply(skill, {"evidence_id": "evSec", "mode": "manual", "units": [
            {"unit_id": "sc", "proposed_action": "propose", "target_concept_id": sec,
             "category": "Tools", "knowledge_confidence": "medium",
             "match_confidence": "medium", "note_body": "x"}]}, tmp)
        vault_txt = "".join(p.read_text(errors="ignore")
                            for p in kh.knowledge_root(cfg).rglob("*")
                            if p.is_file())
        check("secret concept-id masked everywhere", sec not in vault_txt)

        # 33. A malformed unit fails alone; later units still process (no die()).
        out = run_apply(skill, {"evidence_id": "evBatch", "mode": "manual", "units": [
            {"unit_id": "b1", "proposed_action": "create", "knowledge_confidence": "high",
             "match_confidence": "none", "note_body": "x"},   # missing concept/category
            {"unit_id": "b2", "proposed_action": "propose", "target_concept_id": "okunit",
             "category": "Domain", "knowledge_confidence": "medium",
             "match_confidence": "medium", "note_body": "y"}]}, tmp)
        check("malformed unit doesn't abort batch",
              len(out["results"]) == 2 and out["results"][0]["result"] == "failed"
              and out["results"][1]["result"] == "propose", str(out["results"]))

        # 34. D1: build_index provides content_sha256 and match_candidates returns
        # it, so an update using that (deterministic) sha actually applies.
        (kh.knowledge_root(cfg) / "Tools" / "casnote.md").write_text(note("casnote", "orig"))
        subprocess.run([sys.executable, str(SCRIPTS / "build_index.py"),
                        "--skill-dir", str(skill)], capture_output=True, text=True)
        r = subprocess.run([sys.executable, str(SCRIPTS / "match_candidates.py"),
                            "--skill-dir", str(skill), "--title", "casnote"],
                           capture_output=True, text=True)
        exact = json.loads(r.stdout)["exact"]
        check("match_candidates supplies content_sha256",
              exact and exact.get("content_sha256"), str(exact))
        out = run_apply(skill, {"evidence_id": "evCasOk", "mode": "manual", "units": [
            {"unit_id": "cok", "proposed_action": "update", "target_concept_id": "casnote",
             "category": "Tools", "knowledge_confidence": "high", "match_confidence": "exact",
             "expected_current_sha256": exact["content_sha256"],
             "delta": "## Update\nCAS-APPLIED"}]}, tmp)
        check("update with index-supplied sha applies",
              out["results"][0]["result"] == "update"
              and "CAS-APPLIED" in (kh.knowledge_root(cfg) / "Tools" / "casnote.md").read_text(),
              str(out["results"][0]))

        # 35. Secret in `reason` (propose) never persists in vault or ledger.
        sr = "sk-ant-api03-REASONLEAKABCDEFGHIJKLMNOPQRSTUV0123456789"
        run_apply(skill, {"evidence_id": "evR", "mode": "manual", "units": [
            {"unit_id": "rr", "proposed_action": "propose", "target_concept_id": "safe-r",
             "category": "Tools", "knowledge_confidence": "medium",
             "match_confidence": "medium", "reason": f"see {sr}", "note_body": "x"}]}, tmp)
        allfiles = "".join(p.read_text(errors="ignore")
                           for p in kh.knowledge_root(cfg).rglob("*") if p.is_file())
        check("secret in reason masked everywhere", sr not in allfiles)

        # 36. Secret in skip.reason never persists in the ledger.
        sk = "sk-ant-api03-SKIPLEAKABCDEFGHIJKLMNOPQRSTUVWX0123456789"
        run_apply(skill, {"evidence_id": "evS", "mode": "manual", "units": [
            {"unit_id": "ss", "proposed_action": "skip", "target_concept_id": "s",
             "reason": f"skip {sk}"}]}, tmp)
        check("secret in skip.reason masked in ledger",
              sk not in kh.ledger_path(cfg).read_text())

        # 37. Secret-shaped but slug-safe concept-id: no secret in filename/path,
        # and an active create with it is rejected.
        sc2 = "sk-ant-api03-fnameleakabcdefghijklmnopqrstuvwx0123456789"
        out = run_apply(skill, {"evidence_id": "evF", "mode": "manual", "units": [
            {"unit_id": "ff", "proposed_action": "propose", "target_concept_id": sc2,
             "category": "Tools", "knowledge_confidence": "medium",
             "match_confidence": "medium", "note_body": "x"}]}, tmp)
        check("secret concept-id yields clean filename",
              sc2 not in out["results"][0]["path"]
              and "concept-" in Path(out["results"][0]["path"]).name)
        out = run_apply(skill, {"evidence_id": "evF2", "mode": "manual", "units": [
            {"unit_id": "ff2", "proposed_action": "create", "target_concept_id": sc2,
             "category": "Tools", "knowledge_confidence": "high",
             "match_confidence": "none", "note_body": note(sc2, "x")}]}, tmp)
        check("secret concept-id create rejected",
              out["results"][0]["result"] == "failed")

        # 38. Collision-resistant stub names: punctuation-only + same-16-prefix
        # unit ids no longer collide.
        out = run_apply(skill, {"evidence_id": "evC", "mode": "manual", "units": [
            {"unit_id": "!!!", "proposed_action": "propose", "target_concept_id": "cc",
             "category": "Tools", "knowledge_confidence": "medium",
             "match_confidence": "medium", "note_body": "P1"},
            {"unit_id": "???", "proposed_action": "propose", "target_concept_id": "cc",
             "category": "Tools", "knowledge_confidence": "medium",
             "match_confidence": "medium", "note_body": "P2"}]}, tmp)
        paths2 = {r["path"] for r in out["results"]}
        blob2 = "".join(Path(p).read_text() for p in paths2)
        check("punctuation-only unit ids don't collide",
              len(paths2) == 2 and "P1" in blob2 and "P2" in blob2, str(out["results"]))

        # 39. Review-only idempotency: rerunning a committed propose is a no-op.
        plan39 = {"evidence_id": "evI", "mode": "manual", "units": [
            {"unit_id": "idem", "proposed_action": "propose", "target_concept_id": "idemc",
             "category": "Tools", "knowledge_confidence": "medium",
             "match_confidence": "medium", "note_body": "ONCE"}]}
        run_apply(skill, plan39, tmp)
        out = run_apply(skill, plan39, tmp)
        rows = kh.ledger_path(cfg).read_text().count('"unit_id": "idem"')
        check("rerun of committed propose is no-op",
              out["results"][0]["result"] == "already-committed" and rows == 1,
              f"result={out['results'][0]['result']} rows={rows}")

        # 40. Secret-shaped unit_id: idempotency still holds (state keyed on the
        # non-secret unit_key, not the masked display value) and never leaks.
        secuid = "sk-ant-api03-UNITIDLEAKabcdefghijklmnop0123456789xy"
        plan40 = {"evidence_id": "evU", "mode": "manual", "units": [
            {"unit_id": secuid, "proposed_action": "propose", "target_concept_id": "su",
             "category": "Tools", "knowledge_confidence": "medium",
             "match_confidence": "medium", "note_body": "P"}]}
        run_apply(skill, plan40, tmp)
        out = run_apply(skill, plan40, tmp)
        ledger_txt = kh.ledger_path(cfg).read_text()
        check("secret unit_id: replay is no-op + no leak",
              out["results"][0]["result"] == "already-committed"
              and secuid not in ledger_txt, str(out["results"][0]))

        # 41. Secret-shaped evidence_id leaves no recognizable prefix in the path.
        out = run_apply(skill, {"evidence_id": secuid, "mode": "manual", "units": [
            {"unit_id": "ev-uid", "proposed_action": "propose", "target_concept_id": "se",
             "category": "Tools", "knowledge_confidence": "medium",
             "match_confidence": "medium", "note_body": "P"}]}, tmp)
        name = Path(out["results"][0]["path"]).name
        check("secret evidence_id yields clean filename",
              "skant" not in name.lower() and "api03" not in name.lower(), name)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
