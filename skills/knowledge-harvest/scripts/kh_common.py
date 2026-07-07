#!/usr/bin/env python3
"""Shared primitives for knowledge-harvest deterministic scripts.

Owns the security- and correctness-critical logic the LLM must NOT hand-roll:
config, path safety, deterministic slugging, fail-closed redaction, the ledger
state machine, and concept-id -> path resolution. See references/vault-schema.md
and references/matching-and-update.md for the contracts these implement.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # py<3.11 — fall back to the tomli backport
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CONFIG_NAME = "config.toml"
KNOWLEDGE_SUBDIR = "Knowledge"
CATEGORIES = ["Patterns", "Pitfalls", "Decisions", "Tools", "Domain", "Reference"]
NEEDS_REVIEW = "_needs-review"
RESERVED_SLUGS = {NEEDS_REVIEW, ".state", ".ledger", "backups", "evidence", "plans"}


def die(msg: str, code: int = 2) -> "NoReturn":  # type: ignore[valid-type]
    print(f"knowledge-harvest: {msg}", file=sys.stderr)
    sys.exit(code)


def load_config(skill_dir: Path) -> dict:
    """Load config.toml next to the skill. No filesystem guessing for the vault."""
    cfg_path = skill_dir / CONFIG_NAME
    if not cfg_path.exists():
        die(f"missing {cfg_path}. Copy config.example.toml and set vault.path "
            "(see references/vault-schema.md).")
    if tomllib is None:
        die("tomllib unavailable; Python 3.11+ required.")
    try:
        with cfg_path.open("rb") as fh:
            cfg = tomllib.load(fh)
    except tomllib.TOMLDecodeError as e:
        die(f"config.toml is not valid TOML: {e}")
    vault = cfg.get("vault", {}).get("path")
    if not vault:
        die("config.toml has no vault.path")
    vault_root = os.path.expanduser(vault)
    # A missing vault root almost always means a typo — refuse rather than
    # silently materialize a phantom vault at the wrong path.
    if not os.path.isdir(vault_root):
        die(f"vault.path does not exist or is not a directory: {vault_root}")
    cfg["_vault_root"] = vault_root
    cfg.setdefault("limits", {})
    cfg["limits"].setdefault("max_units_per_run", 12)
    cfg["limits"].setdefault("max_index_entries_per_category", 2000)
    cfg["limits"].setdefault("consolidation_delta_threshold", 8)
    return cfg


def knowledge_root(cfg: dict) -> Path:
    return Path(cfg["_vault_root"]) / KNOWLEDGE_SUBDIR


def state_dir(cfg: dict) -> Path:
    return knowledge_root(cfg) / ".state"


def ledger_dir(cfg: dict) -> Path:
    return knowledge_root(cfg) / ".ledger"


# ---------------------------------------------------------------------------
# Path safety (A9) — vault and existing notes are treated as hostile input.
# ---------------------------------------------------------------------------
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_DATE_LIKE = re.compile(r"^\d{4}(-\d{2}){0,2}$")


def is_safe_slug(slug) -> bool:
    if not isinstance(slug, str):   # YAML may hand us an int/None concept-id
        return False
    if not slug or len(slug) > 80:
        return False
    if slug in RESERVED_SLUGS or slug.startswith(".") or slug.startswith("_"):
        return False
    if _DATE_LIKE.match(slug):
        return False
    return bool(_SLUG_RE.match(slug))


def slugify(text: str, salt: str = "") -> str:
    """Deterministic slug (A11): NFKD -> ASCII fold -> lowercase -> kebab.

    No lemmatizer. If nothing ASCII survives (e.g. pure Hangul), fall back to a
    short stable hash so the concept-id is still deterministic and matchable via
    aliases. Callers store the human phrase in `title`/`aliases`.
    """
    norm = unicodedata.normalize("NFKD", text)
    ascii_only = norm.encode("ascii", "ignore").decode("ascii")
    ascii_only = ascii_only.lower()
    ascii_only = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    ascii_only = re.sub(r"-{2,}", "-", ascii_only)[:80].strip("-")
    if not ascii_only or _DATE_LIKE.match(ascii_only):
        h = hashlib.sha256((text + salt).encode("utf-8")).hexdigest()[:10]
        return f"concept-{h}"
    return ascii_only


def resolve_target(cfg: dict, category: str, concept_id: str) -> Path:
    """Deterministic concept-id -> path (A5). The LLM never supplies a path.

    Refuses path escape, symlinks, and non-regular existing targets (A9).
    """
    if category not in CATEGORIES:
        die(f"illegal category {category!r}; must be one of {CATEGORIES}")
    if not is_safe_slug(concept_id):
        die(f"unsafe concept-id slug {concept_id!r}")
    root = knowledge_root(cfg).resolve()
    target = (root / category / f"{concept_id}.md").resolve()
    try:
        target.relative_to(root)
    except ValueError:
        die(f"path escape: {target} not under {root}")
    if target.exists():
        if target.is_symlink() or not target.is_file():
            die(f"refusing to write through non-regular/symlink target {target}")
    return target


# ---------------------------------------------------------------------------
# Frontmatter parsing + note validation — one source of truth so apply_plan,
# validate_note, and build_index agree on the schema (A5/A12).
# ---------------------------------------------------------------------------
VALID_STATUS = ("active", "needs-review", "deprecated", "superseded")
REQUIRED_KEYS = ("schema-version", "concept-id", "title", "category", "status")


def parse_frontmatter(text: str) -> dict | None:
    """Return the YAML frontmatter dict, or None if absent/unparseable.

    yaml is imported lazily so scripts that never parse notes (prepare_source)
    don't take a hard PyYAML dependency just by importing this module.
    """
    import yaml
    text = text.lstrip("﻿")   # tolerate a UTF-8 BOM
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    try:
        data = yaml.safe_load(text[3:end])
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def validate_note_fields(fm: dict, expect_concept: str | None = None,
                         expect_category: str | None = None) -> list[str]:
    errs: list[str] = []
    for k in REQUIRED_KEYS:
        if k not in fm:
            errs.append(f"missing required key: {k}")
    cid = fm.get("concept-id")
    if cid is not None and not is_safe_slug(cid):
        errs.append(f"unsafe concept-id: {cid!r}")
    cat = fm.get("category")
    if cat and cat not in CATEGORIES:
        errs.append(f"illegal category: {cat!r}")
    status = fm.get("status")
    if status and status not in VALID_STATUS:
        errs.append(f"illegal status: {status!r}")
    if status == "superseded" and not fm.get("superseded-by"):
        errs.append("status=superseded requires superseded-by")
    aliases = fm.get("aliases", [])
    if aliases and not isinstance(aliases, list):
        errs.append(f"aliases must be a list, got {type(aliases).__name__}")
    if expect_concept and cid and cid != expect_concept:
        errs.append(f"concept-id {cid!r} != target {expect_concept!r}")
    if expect_category and cat and cat != expect_category:
        errs.append(f"category {cat!r} != target {expect_category!r}")
    return errs


# ---------------------------------------------------------------------------
# Fail-closed redaction (A3) — entropy + context, not pattern-only, so the KB
# can still document secret *formats* without being permanently quarantined.
# ---------------------------------------------------------------------------
# High-signal literal patterns: a hit here is a hard block regardless of entropy.
_HARD_PATTERNS = [
    # PEM private-key blocks: base64 body is low-entropy + contains +// so the
    # entropy sweep misses it entirely — this literal block is the only defense.
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"(?i)authorization:\s*basic\s+[A-Za-z0-9+/]{16,}={0,2}"),  # HTTP Basic
    re.compile(r"[a-z][a-z0-9+.\-]{0,15}://[^/\s:@]{1,64}:[^/\s:@]{1,64}@"),  # url creds user:pass@
    re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),         # OpenAI (sk-, sk-proj-) + Anthropic sk-ant-
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),    # GitHub token
    re.compile(r"AKIA[0-9A-Z]{16}"),              # AWS access key id
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),        # Google API key
    re.compile(r"ya29\.[0-9A-Za-z_-]{20,}"),      # Google OAuth2 access token
    re.compile(r"1//0[0-9A-Za-z_-]{30,}"),        # Google OAuth2 refresh token
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),  # Slack token
]
# Personal-path / private-identifier patterns (repo leak-warning list).
_PII_PATTERNS = [
    # Bounded quantifiers only — an unbounded `+` before a required literal (the
    # `@`, the closing `/`) backtracks O(n^2) on a long run that lacks it.
    re.compile(r"/Users/[A-Za-z0-9._-]{1,64}/"),
    re.compile(r"/home/[A-Za-z0-9._-]{1,64}/"),
    re.compile(r"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,255}\.[A-Za-z]{2,24}"),
]


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)          # single pass — avoids O(n * alphabet) from s.count()
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _looks_like_live_secret(token: str) -> bool:
    """A random-looking >=24-char token with high entropy is treated as live."""
    if len(token) < 24:
        return False
    # Pure-hex tokens are overwhelmingly git SHAs / hashes / hex UUIDs, not
    # credentials — dev knowledge cites them constantly. Don't quarantine them
    # (structured hex secrets are still caught by the literal patterns).
    if re.fullmatch(r"[0-9a-fA-F]+", token):
        return False
    return _shannon_entropy(token) >= 3.5 and bool(re.search(r"[A-Za-z]", token)) \
        and bool(re.search(r"[0-9]", token))


def scan_secrets(text: str) -> list[dict]:
    """Return a list of findings. Empty list == clean.

    Each finding: {kind, pattern, span_hash}. Never returns the raw secret so
    the caller can log findings without persisting the payload (A2).
    """
    findings: list[dict] = []
    for pat in _HARD_PATTERNS:
        for m in pat.finditer(text):
            findings.append(_finding("credential", pat.pattern, m.group(0)))
    for pat in _PII_PATTERNS:
        for m in pat.finditer(text):
            findings.append(_finding("pii", pat.pattern, m.group(0)))
    # Entropy sweep over bare tokens not already covered by a literal pattern.
    for m in re.finditer(r"[A-Za-z0-9_\-]{24,}", text):
        tok = m.group(0)
        if _looks_like_live_secret(tok):
            findings.append(_finding("high-entropy", "entropy>=3.5", tok))
    return findings


def _finding(kind: str, pattern: str, raw: str) -> dict:
    return {
        "kind": kind,
        "pattern": pattern,
        "span_hash": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16],
        "length": len(raw),
    }


def mask_secrets(text: str) -> str:
    """Replace every finding with a typed placeholder. Used for note bodies AND
    for plan-controlled metadata (concept_id/evidence_id) so a hostile plan can't
    smuggle a raw secret into a synced review stub or the ledger."""
    out = str(text)
    for pat in _HARD_PATTERNS:
        out = pat.sub("«REDACTED:credential»", out)
    for pat in _PII_PATTERNS:
        out = pat.sub("«REDACTED:pii»", out)
    out = re.sub(r"[A-Za-z0-9_\-]{24,}",
                 lambda m: "«REDACTED:high-entropy»"
                 if _looks_like_live_secret(m.group(0)) else m.group(0), out)
    return out


def mask_meta(obj):
    """Recursively mask every string in a dict/list/str. Used on ledger rows and
    review-stub metadata so NO plan-controlled field (reason, target_path, …) —
    not just the payload — can smuggle a raw secret into the synced vault."""
    if isinstance(obj, str):
        return mask_secrets(obj)
    if isinstance(obj, dict):
        return {k: mask_meta(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [mask_meta(v) for v in obj]
    return obj


def redaction_summary(findings: list[dict]) -> dict:
    kinds: dict[str, int] = {}
    for f in findings:
        kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
    return {"total": len(findings), "by_kind": kinds,
            "span_hashes": [f["span_hash"] for f in findings]}


# ---------------------------------------------------------------------------
# Hashing / evidence identity (A14) — volatile fields excluded so evidence_id
# is stable across reruns.
# ---------------------------------------------------------------------------
_VOLATILE_KEYS = {"harvested", "ts", "generated_at", "_wall_clock"}


def _canonical(obj):
    if isinstance(obj, dict):
        return {k: _canonical(v) for k, v in sorted(obj.items())
                if k not in _VOLATILE_KEYS}
    if isinstance(obj, list):
        return [_canonical(v) for v in obj]
    return obj


def unit_key(unit_id) -> str:
    """Deterministic non-secret identity for a unit. Ledger idempotency keys on
    THIS (never the raw or masked unit_id) so a secret-shaped unit_id neither
    leaks nor breaks replay lookup."""
    return hashlib.sha256(str(unit_id).encode()).hexdigest()[:16]


def stable_hash(obj) -> str:
    payload = json.dumps(_canonical(obj), ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Ledger state machine (A1) — two-phase, append-only JSONL, single authority.
# ---------------------------------------------------------------------------
def ledger_path(cfg: dict) -> Path:
    return ledger_dir(cfg) / "runs.jsonl"


def ledger_append(cfg: dict, row: dict) -> None:
    p = ledger_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    raw_uid = row.get("unit_id")
    row = mask_meta(dict(row))   # mask EVERY plan-derived string (display only)
    if raw_uid is not None:      # non-secret hash key for idempotency lookups
        row["unit_key"] = unit_key(raw_uid)
    row.setdefault("ts", now_iso())
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def ledger_read(cfg: dict) -> list[dict]:
    p = ledger_path(cfg)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def committed_units(cfg: dict) -> set[str]:
    """unit_keys whose latest ledger status is `committed` (A1/A6)."""
    latest: dict[str, str] = {}
    for row in ledger_read(cfg):
        uk = row.get("unit_key")
        if uk:
            latest[uk] = row.get("status", latest.get(uk, ""))
    return {uk for uk, st in latest.items() if st == "committed"}


def latest_unit_row(cfg: dict, unit_id: str) -> dict | None:
    """Most recent ledger row for a unit, keyed on the non-secret unit_key so a
    secret-shaped (hence masked) unit_id still resolves on replay."""
    uk = unit_key(unit_id)
    found = None
    for row in ledger_read(cfg):
        if row.get("unit_key") == uk:
            found = row
    return found


def needs_review_path(cfg: dict, concept_id, evidence_id, kind: str,
                      unit_id: str = "") -> Path:
    """Path-safe filename under _needs-review/ from plan-controlled values.

    `write_review_stub`/`quarantine` build stub names from LLM-supplied values;
    those must NOT introduce `/` or `..` and escape the review folder (the same
    guarantee resolve_target gives active notes). Sanitize each component, then
    assert the result stays under the dir. `unit_id` disambiguates distinct units
    that share a concept within one evidence run (so candidates aren't clobbered)
    while keeping the name deterministic for idempotent re-runs of the SAME unit.
    """
    nr = (knowledge_root(cfg) / NEEDS_REVIEW)
    # A secret can be a syntactically-valid slug (e.g. sk-ant-api03-…) — never let
    # it become a filename/target_path. Use a neutral deterministic surrogate.
    if is_safe_slug(concept_id) and not scan_secrets(str(concept_id)):
        cid = concept_id
    elif isinstance(concept_id, str) and concept_id and not scan_secrets(concept_id):
        cid = slugify(concept_id)
    else:
        cid = "concept-" + hashlib.sha256(str(concept_id).encode()).hexdigest()[:10]
    # Hash evidence_id + unit_id for filename components: distinct raw values
    # can't collide via stripping/truncation, a secret-shaped value leaves no
    # recognizable prefix, and it stays deterministic for idempotent reruns.
    ev = hashlib.sha256(str(evidence_id).encode()).hexdigest()[:12]
    uid = hashlib.sha256(str(unit_id).encode()).hexdigest()[:12] if unit_id else ""
    k = re.sub(r"[^a-z0-9-]", "", str(kind).lower()) or "candidate"
    name = f"{cid}.{ev}.{uid}.{k}.md" if uid else f"{cid}.{ev}.{k}.md"
    target = (nr / name).resolve()
    try:
        target.relative_to(nr.resolve())
    except ValueError:
        die(f"review-stub path escape blocked for {concept_id!r}")
    return target


def find_existing_concept(cfg: dict, concept_id: str) -> Path | None:
    """Locate a note with this concept-id in ANY category (global-flat identity).

    concept-id is category-independent, so a create must refuse when the id
    already lives under a different category — otherwise re-classification would
    spawn a duplicate the fuzzy matcher can't reconcile.
    """
    root = knowledge_root(cfg)
    for cat in CATEGORIES:
        p = root / cat / f"{concept_id}.md"
        if p.exists():
            return p
    return None


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


# ---------------------------------------------------------------------------
# Lock (A7) — mkdir atomic lock scoped to the write-commit phase, with stale
# reclaim so a crashed run doesn't wedge the vault forever.
# ---------------------------------------------------------------------------
class Lock:
    def __init__(self, cfg: dict, stale_secs: int = 900):
        self.dir = state_dir(cfg) / "harvest.lock"
        self.stale = stale_secs
        self.held = False

    def acquire(self) -> bool:
        self.dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.dir.mkdir()
        except FileExistsError:
            if not self._reclaim_if_stale():
                return False
            try:
                self.dir.mkdir()
            except FileExistsError:
                return False
        (self.dir / "pid").write_text(f"{os.getpid()}\n{time.time()}\n")
        self.held = True
        return True

    def _reclaim_if_stale(self) -> bool:
        # LOW/known-limitation: reclaim (unlink+rmdir then re-mkdir) is not atomic,
        # so two processes racing to reclaim the SAME crashed lock have a narrow
        # double-hold window. Normal contention is safe (mkdir is atomic); this
        # only affects stale-crash recovery under concurrent harvests, which are
        # rare for a single local vault. Deferred; rename-based reclaim would close it.
        meta = self.dir / "pid"
        try:
            pid_s, ts_s = meta.read_text().split("\n")[:2]
            pid, ts = int(pid_s), float(ts_s)
        except (OSError, ValueError):
            return False
        alive = _pid_alive(pid)
        if alive and (time.time() - ts) < self.stale:
            return False
        # Stale: crashed pid or exceeded stale window.
        try:
            meta.unlink(missing_ok=True)
            self.dir.rmdir()
        except OSError:
            return False
        return True

    def release(self) -> None:
        if not self.held:
            return
        try:
            (self.dir / "pid").unlink(missing_ok=True)
            self.dir.rmdir()
        except OSError:
            pass
        self.held = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
