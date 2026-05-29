# Forbidden actions

The skill refuses these even if the user requests them mid-flow.
Surface the forbidden item, ask for confirmation to deviate, **default
to refusal**. The fact that "the user asked" is not a sufficient
override — these are load-bearing safety + scope rules.

## Git operations

- `git push` / `git push --force` — out of scope (user's call only).
- `git push --force` to `main` / `master` — refuse even if user
  explicitly asks; surface the request with a warning.
- `git reset --hard` — discards uncommitted work irrecoverably.
- `git clean -f` — same risk.
- `git worktree remove --force` — bypasses uncommitted-change check.
- `git merge` without `--no-ff` for the implementer branch — fast-
  forward erases the merge commit that carries the
  `(document-impl-<scale>, human-confirmed)` marker.
- `git merge` or `git commit` without `-m` flag — drops into
  `$EDITOR` and hangs in non-interactive runs.
- `git commit --amend` after a commit has landed on the implementer
  branch — rewrites history that the `--no-ff` merge was meant to
  preserve. Create a NEW commit instead.
- `--no-verify` on any commit — bypasses pre-commit hooks.

## Planner artifacts (read-only)

The planner produced these and the implementer reads them but never
modifies them. Refuse to edit:

- `document-plan.md` (including its frontmatter)
- `document-structure.mmd`
- `document-structure.html` (system only)

If a stub's spec is wrong, the fix is to re-run the planner with
`/document-planner`, not to edit the artifact.

## Scope discipline

- Re-classify SCALE mid-run — SCALE is read from the marker at
  Phase 0 and never re-derived.
- Add stubs the planner didn't emit, merge stubs, split stubs, or
  re-order stubs.
- "Polish" prose the loop didn't write (e.g., reformatting an
  unrelated existing section in TARGET_PATH).
- Edit files outside the per-item `files_touched` set during
  auto-fix attempts.
- Generate prose without a planner marker (or chat-gate for
  micro/local).
- Auto-bump a missing-marker situation by re-running the planner.
- Treat user silence as confirmation at any gate.

## Mirror discipline

The `scripts/parse_frontmatter.py` in this skill is a COPY of
`skills/document-planner/scripts/parse_frontmatter.py`. **Refuse to
edit it.** Any change must land on the planner-side first; this
skill is bumped to track. Same rule for
`references/marker-detection.md` mirroring
`document-planner/references/implementer-contract.md`.

## Dependency installation

- Auto-install python-pptx (or any other Python dep). Phase 1 dep
  check refuses with the install instruction; user runs `pip install`
  manually and re-invokes.
- Add PyYAML to any script. The bundled `parse_frontmatter.py`
  uses stdlib only.

## Content shipping

- Ship literal `[[stub-id]]` references to the user-facing document.
  `validate_anchors.py` catches these in Phase 4; the auto-fix loop
  must transform them. If auto-fix exhausts, surface as a blocker.
- Ship secrets in any commit. Phase 3's commit cadence runs a
  secrets sniff before every commit (see "Secrets sniff" below).

## Versioning

- Hardcode language/framework/library major versions in any
  generated content. Use placeholders or current-LTS phrasing per
  CLAUDE.md.

## OUTPUT_LANGUAGE handling

- Prompt the user for OUTPUT_LANGUAGE mid-flow. It is mandatory in
  the planner contract; absence at Phase 0 is a refusal blocker.
  Phase L captures `LANGUAGE` (dialog); never `OUTPUT_LANGUAGE`
  (autonomy boundary applies).

## Secrets sniff (Phase 3 commit gate)

Run before every implementer commit on the staged diff:

```bash
SECRETS_PATTERN='(api[_-]?keys?[[:space:]]*[=:][[:space:]]*['"'"'"][A-Za-z0-9._/+-]{16,}|api[_-]?keys?[[:space:]]*=[[:space:]]*[A-Za-z0-9/_+-]{20,}|secret[_-]?(key|token)[[:space:]]*[=:][[:space:]]*['"'"'"][A-Za-z0-9._/+-]{16,}|secret[_-]?(key|token)[[:space:]]*=[[:space:]]*[A-Za-z0-9/_+-]{20,}|password[[:space:]]*[=:][[:space:]]*['"'"'"][^'"'"'"[:space:]]{6,}|password[[:space:]]*=[[:space:]]*[A-Za-z0-9/_+-]{8,}|client_secret[[:space:]]*[=:][[:space:]]*['"'"'"]?[A-Za-z0-9._/+-]{16,}|bearer[[:space:]]+[A-Za-z0-9._-]{20,}|aws_(access_key_id|secret_access_key|session_token)|AKIA[A-Z0-9]{16}|ghp_[A-Za-z0-9]{36}|sk_(live|test)_[A-Za-z0-9]{16,}|xox[abprs]-[A-Za-z0-9-]+|hooks\.slack\.com/services/[A-Z0-9]{8,}/[A-Z0-9]{8,}/[A-Za-z0-9]{20,}|-----BEGIN[[:space:]]+(RSA[[:space:]]+|EC[[:space:]]+|OPENSSH[[:space:]]+|PGP[[:space:]]+)?PRIVATE[[:space:]]+KEY|"private_key"[[:space:]]*:[[:space:]]*"-----BEGIN|AIza[0-9A-Za-z_-]{35}|eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}|(postgres|mysql|mongodb(\+srv)?|redis)://[^:/@[:space:]]+:[^@[:space:]]+@)'

if git diff --cached -U0 | grep -E -i "${SECRETS_PATTERN}" >/dev/null; then
  echo "BLOCKER: candidate secret in staged diff — refusing to commit. Inspect manually."
  git diff --cached -U0 | grep -E -i -n "${SECRETS_PATTERN}" | head -10
  exit 1
fi
```

Same pattern as codebase-implementer. **Fails closed** —
false-positive rate ~10% on auth-code-touching prose; false-negative
bounded (this is a floor, not a ceiling). Layer
trufflehog / detect-secrets / gitleaks at the org level if needed.

## What's NOT forbidden

- Writing speaker notes in pptx slides (provenance contract relies
  on it).
- Re-generating an in-progress stub at Phase 3 (mark as
  in_progress, retry).
- Asking the user for INTENT_SLUG at Phase 1 (bootstrap-time, not
  autonomy-loop prompt).
- Asking the user for clarification on a true blocker (the
  blocker-format protocol is the right way to surface).

## Honest limitations

The forbidden list is a documented social contract, not enforced
by the runtime. A determined user can bypass any check (e.g., by
editing the SKILL.md or running git commands outside the skill).
The list exists to catch accidental violations and make deliberate
bypasses visible at review time.
