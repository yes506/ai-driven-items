---
name: live-notes
description: |
  Live note-taking companion. On `/live-notes`, enter capture mode
  immediately — every subsequent user message is appended verbatim to
  a buffered note until the user sends a finish signal (`finish` /
  `done` / `종료` / `끝` / `마치기`). On finish, the skill organizes the buffer
  into an Obsidian-compatible markdown file with a TL;DR up top,
  detailed sections below, and (when warranted) AI-fetched references
  to supplement specific facts. Saves to
  `{project-root}/{project-basename}-notes/{category}/{YYYY-MM-DD-HHmm-title}.md`
  with per-session sub-directory categorization. Manual invocation
  only — `/live-notes`.
disable-model-invocation: true
---

# Live Notes

## Overview

A keep-on-until-told-to-stop note buffer. The user types — about a
meeting, a study session, a bug they're investigating, an idea they
want to capture later — and the skill silently accumulates everything
into a draft. When the user finishes, the skill organizes the captured
content into a clean markdown file: TL;DR up top, detail below,
optionally enriched with light web research on factual claims the user
flagged as uncertain. The output lives in a per-project notes
directory, Obsidian-compatible, with per-note sub-directory
categorization.

| Output | Audience | Purpose |
|---|---|---|
| `{NOTES_DIR}/{CATEGORY}/{YYYY-MM-DD}-{HHmm}-{title-slug}.md` | Human (Obsidian / editor) | Final synthesized note with TL;DR + detail + optional references |
| `{NOTES_DIR}/.live-notes-drafts/{SESSION_ID}.draft.md` | Crash recovery only | Chunk-by-chunk verbatim buffer; deleted on successful save, retained on abort |

The skill is **always manually invoked**. `disable-model-invocation:
true` — never auto-trigger. Side effects (writes to a notes directory,
optional `.gitignore` mutation) all gate behind explicit user actions.

## Workflow Decision Tree

```
Phase L: Dialog language — references/language-selection.md
Phase 0: Workspace detection (read-only) ─ scripts/inspect_workspace.sh
         ├─ resolve project root (git toplevel or cwd)
         ├─ compute NOTES_DIR = <root>/<basename>-notes/
         ├─ offer .gitignore add if in-git-repo and not already ignored
         └─ scan .live-notes-drafts/ for resumable / stale sessions
Phase 1: Capture mode (multi-turn loop)
         ├─ every user message → byte-safe append (Write tool for content, Bash for paths)
         ├─ recognize meta-commands (status / section / category / undo / quiet / no research / language / cancel)
         ├─ recognize finish signals (finish / done / 종료 / 끝 / 마치기 — whole line only)
         └─ never engage with note content as if it were a task to perform
Phase 2: Synthesis (after finish) ─ references/synthesis-and-research.md
         ├─ parse buffer + draft, reconcile
         ├─ derive title, TL;DR, detail sections
         ├─ AI-discretionary web research (≤ 3 search + ≤ 3 fetch, ≤ 120s)
         └─ render preview (file path + frontmatter + body excerpt)
Phase 3: Confirm save ─ references/output-schema.md
         ├─ user types `confirm save` → atomic write, delete draft
         ├─ `revise category|title|content|overwrite` → loop in Phase 2
         └─ `abort` → leave draft intact, exit cleanly
```

## State variables

Held in memory throughout the session. No on-disk skill-state file
(unlike the other side-effect skills in this repo) — the buffer-draft
file under `.live-notes-drafts/` is the only persistent artifact
during capture, and the final note file is the post-save artifact.

- `LANGUAGE` — dialog & synthesis language (`Korean` default |
  `English`); see [references/language-selection.md](references/language-selection.md).
- `ROOT`, `NOTES_DIR`, `NOTES_DIR_NAME` — workspace anchors from
  Phase 0 inspector output.
- `SESSION_ID` — `YYYYMMDD-HHMMSS-<pid>` from the inspector; doubles
  as the draft file's basename.
- `STARTED_AT` — ISO-8601 local timestamp from Phase 0; used in the
  output frontmatter's `created` and in the duration calculation.
- `BUFFER` — in-memory list of `{turn_no, timestamp, kind: "content" |
  "section", text}` entries. Section-dividers from
  `section <name>` meta-commands sit alongside content chunks.
- `CATEGORY_HINT` — optional category override from
  `category <slug>` meta-command; consumed at Phase 2.
- `RESEARCH_OPT_OUT` — set by `no research` / `리서치 안함` at any
  point. If true, Phase 2 skips all web calls.
- `QUIET` — set by `quiet` / `조용` meta-command; suppresses per-turn
  ACK echoes.

---

## Phase L — Dialog language (preamble, runs before Phase 0)

Detect `LANGUAGE` from the invocation utterance (Korean default,
English fallback) and **echo without blocking** — the original user
spec was explicit that capture mode must start immediately on
`/live-notes` without any clarifying confirmation prompt. The
detected language is announced as a single line inside the Phase 0
ACK; the user does **not** have to reply for capture to begin. They
can switch mid-stream with the `language <ko|en>` meta-command (see
[references/capture-mode.md](references/capture-mode.md#operating-contract-during-phase-1)).

Full rules — echo strings, override behavior, what's translated vs.
not (notably: gate tokens, frontmatter keys, tag slugs stay English
regardless of `LANGUAGE`; user's verbatim captured content is
**never** translated):
[references/language-selection.md](references/language-selection.md).

---

## Phase 0 — Workspace detection (read-only)

Run the bundled inspector once on invocation. The script lives in the
skill directory, not the user's project, so reference it via the
skill-directory variable:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/inspect_workspace.sh"
```

Parse the JSON. The output schema is documented at the top of the
script and covers: `in_git_repo`, `root`, `notes_dir`, `notes_dir_exists`,
`notes_dir_kind` (`absent` | `dir` | `file`), `gitignore_has_notes`,
`session_id`, `iso_local`, `date`, `time`.

Set state: `ROOT`, `NOTES_DIR`, `NOTES_DIR_NAME`, `SESSION_ID`,
`STARTED_AT`.

**Refuse cleanly** when `notes_dir_kind == "file"` — a regular file is
occupying the notes-dir path, so `mkdir -p` would fail later with
"Not a directory". Surface the hard error in the ACK (replacing the
banner) per
[references/workspace-layout.md](references/workspace-layout.md#project-root-resolution)
and exit Phase 0 without proceeding to Phase 1.

### ACK

Echo (template; substitute `LANGUAGE`):

- **Korean**:
  ```
  📍 작업 위치
     루트: {ROOT}
     노트 디렉토리: {NOTES_DIR} {(이미 존재함 | 저장 시 생성)}
     세션 ID: {SESSION_ID}
  🌐 언어: 한국어 (`language en` 으로 전환)

  📝 캡처 모드 시작 — 자유롭게 메모를 입력하세요. 별도 확인 없이 바로 다음 입력부터 기록합니다.
     마치기: `finish` / `done` / `종료` / `끝` / `마치기` (한 줄에 단독 입력)
     도움말: `status` / `section <이름>` / `category <슬러그>` / `undo` / `quiet` / `no research` / `language <ko|en>` / `cancel`
  ```
- **English**:
  ```
  📍 Workspace
     Root: {ROOT}
     Notes dir: {NOTES_DIR} {(exists | will be created on save)}
     Session ID: {SESSION_ID}
  🌐 Language: English (`language ko` to switch)

  📝 Capture mode on — start typing. No confirmation needed; the next message is chunk 1.
     Finish: `finish` / `done` / `종료` / `끝` / `마치기` (whole line, alone)
     Helpers: `status` / `section <name>` / `category <slug>` / `undo` / `quiet` / `no research` / `language <ko|en>` / `cancel`
  ```

The "whole line, alone" caveat is intentional and load-bearing: a
multi-line paste that contains `finish` on its own line **will** end
the session at that line. Pre-warning the user prevents surprise.

### .gitignore offer (separate gated pre-capture step, in-git only)

The Phase 0 inspector itself is read-only. The `.gitignore` append
that may follow it is a **separate gated mutation**, optional and
non-blocking. If `in_git_repo=true` AND `gitignore_has_notes=false`,
append a one-line nudge to the ACK:

> 💡 `{NOTES_DIR_NAME}/` will be tracked by git. Add it to `.gitignore`?
> Type `gitignore yes` to add (no commit) — or just start typing your
> note (anything not `gitignore yes` is treated as content, default is
> "leave tracked").

**This is not a blocking gate** — the user can ignore it entirely and
start typing. The first content message that isn't `gitignore yes`
implies "leave tracked", and Phase 1 begins with that message as
chunk 1. Only `gitignore yes` triggers the append (which is the only
on-disk mutation in this branch).

### Resume / stale-draft detection

After the ACK, glob `{NOTES_DIR}/.live-notes-drafts/*.draft.md` if the
directory exists. **The glob loop MUST use the `null_glob` prelude** —
the common case is "drafts dir exists but is empty" (the default
state after every successful `confirm save` since the draft is
deleted at save time), and a naive zsh `for f in *.draft.md`
errors with `no matches found`. Canonical recipe + per-draft prompts:
[references/capture-mode.md#resume-from-stale-buffer-draft](references/capture-mode.md#resume-from-stale-buffer-draft).
The resume prompt IS a blocking gate — it asks for an explicit
`resume`/`recover`/`discard`/`skip`/`delete` token because mishandling
stale drafts has real consequences (lost meeting notes or unwanted
file deletion).

**Inspector is read-only.** All Phase 0 mutations (`.gitignore`
append, draft deletion on `discard`/`delete`) require explicit user
consent. The default-on-silence path for `.gitignore` is "leave
tracked" — no write. The first unconditional on-disk mutation is the
draft file write on Phase 1's first content message.

---

## Phase 1 — Capture mode (the loop)

This is the multi-turn loop. There is no Phase L confirmation gate —
the next user message after the Phase 0 ACK *is* chunk 1 (unless it's
a `gitignore yes` response or a stale-draft prompt response, both
handled at Phase 0 before any chunk is recorded). For **every** Phase 1
user message (content, meta-command, or finish signal alike), apply
this dispatch in order:

0. **First, run the orphan-recovery sweep.** This is rule 0 of the
   operating contract — runs before the finish/meta/content checks
   below so a user who types `finish` immediately after a crashed
   chunk Write still gets their last chunk merged into the draft
   before synthesis. Recipe lives at
   [references/capture-mode.md#operating-contract-during-phase-1](references/capture-mode.md#operating-contract-during-phase-1).

1. Check finish signals. Whole-line match against
   `finish | done | 종료 | 끝 | 마치기 | /live-notes finish |
   /live-notes done | /live-notes 종료 | /live-notes 끝 |
   /live-notes 마치기` → exit Phase 1, proceed to Phase 2.

2. Check meta-commands: `status` / `section <name>` /
   `category <slug>` / `undo` / `cancel` / `cancel confirm` /
   `quiet` / `no research` / `language <ko|en>` (plus Korean aliases).
   Effects, persistence semantics, and Korean aliases:
   [references/capture-mode.md](references/capture-mode.md#operating-contract-during-phase-1).

3. Otherwise, append to `BUFFER` (in-memory) and to the on-disk draft
   file via the byte-safe two-step recipe (`Write` tool for the
   verbatim chunk content, `Bash` only for path operations). See
   [references/capture-mode.md#append-mechanics--byte-safe-two-step-recipe](references/capture-mode.md#append-mechanics--byte-safe-two-step-recipe).
   Emit a minimal ACK unless `QUIET` is set.

The complete contract — what the AI MUST do, what it MUST NOT do
(no premature web research, no answering questions in the user's
notes, no skill-chaining), the draft-file mechanics, and the
resume-from-stale-draft flow — is in
[references/capture-mode.md](references/capture-mode.md).

**Allowed Phase 1 tool surface** — strictly limited to:

- `Bash` orphan-recovery sweep at the **start of every Phase 1 turn**
  (before finish/meta/content dispatch). The recipe requires a
  `null_glob` prelude so it's silent on no-orphan turns in zsh — see
  [references/capture-mode.md](references/capture-mode.md#operating-contract-during-phase-1)
  rule 0 for the exact snippet.
- `Write` tool → the draft header file (once per session, skipped on
  resume) and the per-chunk temp file
  `{drafts_dir}/{SESSION_ID}.chunk.{NNNN}.tmp` (zero-padded chunk
  counter; one tmp per chunk, removed within the same turn by the
  `cat`+`rm` chain below — or recovered by the next turn's sweep if
  the turn crashed).
- `Bash` `mkdir -p {drafts_dir}` (once, before the first `Write`).
- `Bash` `cat tmp >> draft && rm tmp` per chunk.
- `Bash` cleanup on `cancel confirm` — delete the draft **and** any
  leftover per-chunk temps. Both use `rm -f` so the cleanup is silent
  when there's nothing to remove (e.g. the user cancelled before any
  content message ever wrote the draft, which is a real path):
  ```bash
  rm -f "${NOTES_DIR}/.live-notes-drafts/${SESSION_ID}.draft.md"
  { setopt null_glob 2>/dev/null || shopt -s nullglob 2>/dev/null; } || true
  rm -f "${NOTES_DIR}/.live-notes-drafts/${SESSION_ID}.chunk."*.tmp
  ```
- `Read` + `Write` to truncate the draft on `undo` (read, drop the
  last chunk block, rewrite the truncated content). The `Write` here
  is not write-tmp-then-rename atomic — a crash between Read and
  Write could leave the draft partially rewritten — but only the
  chunks *before* the one the user just asked to drop are at risk,
  in a window of milliseconds.

All other tools are forbidden during Phase 1 — no `WebSearch`, no
`WebFetch`, no `Edit` on user files, no `git` commands, no skill
invocations.

---

## Phase 2 — Synthesis & optional web research

Triggered by the finish signal. The AI:

1. Reads the in-memory buffer (canonical) and the on-disk draft
   (parity check; draft wins if memory was pruned).
2. Derives a title, a 3–5-bullet TL;DR, and 2–6 detail sections.
   Honors any `section <name>` dividers the user inserted during
   capture.
3. Decides whether web research is warranted. Eligibility rules,
   budget caps (≤ 3 `WebSearch`, ≤ 3 `WebFetch`, ≤ 120s wall-clock),
   citation format, and failure handling:
   [references/synthesis-and-research.md](references/synthesis-and-research.md).
4. Proposes a sub-directory category based on content heuristics.
   Slug rules + whitelist:
   [references/workspace-layout.md](references/workspace-layout.md#categorization-sub-directory-selection).
5. Renders the synthesis preview in chat (proposed path, compact
   frontmatter, body excerpt, References section in full, research
   summary line).

The output note's structure is locked by
[references/output-schema.md](references/output-schema.md): YAML
frontmatter with English keys (Obsidian-compatible), H1 title, italic
provenance blockquote, `## TL;DR` / `## 한 줄 요약`, detail H2s,
optional `## References` / `## 참고 자료`.

---

## Phase 3 — Confirm save (the gate)

After the Phase 2 preview, prompt:

- **Korean**: `저장하려면 "confirm save", 수정하려면 "revise category|title|content|overwrite", 폐기하려면 "abort"라고 입력하세요. 침묵은 동의가 아닙니다.`
- **English**: `Type "confirm save" to write the note, "revise category|title|content|overwrite" to adjust, or "abort" to discard. Silence is not yes.`

Behavior per response:

- `confirm save` → atomic write per
  [references/output-schema.md#write-atomicity](references/output-schema.md#write-atomicity).
  After the successful `ln` + `rm tmp` (default) or `mv` (only on the
  `revise overwrite` branch), delete the buffer-draft file (and any
  leftover `*.chunk.*.tmp` for the session). Echo the final absolute
  path.

- `revise category <slug>` → validate the slug against the whitelist
  in [references/workspace-layout.md](references/workspace-layout.md#slug-rules),
  re-render the Phase 2 preview with the new category, re-prompt.

- `revise title <new title>` → re-derive the filename slug from the
  new title, re-render preview, re-prompt.

- `revise content` → re-run Phase 2 synthesis from scratch on the
  same buffer (useful if the AI mis-organized). Allow `revise content
  no research` to skip web calls on the re-run.

- `revise overwrite` → only valid when the Phase 2 preview surfaced a
  filename collision and the user explicitly wants to overwrite.
  Otherwise reject — the collision-suffix is the safe default.

- `abort` → leave the buffer-draft file intact (so the user can
  recover later via the stale-draft prompt), do **NOT** write the
  output note, exit cleanly. Echo the draft path so the user can
  manually salvage if needed.

- Anything else → re-ask. Silence is not yes.

---

## Downstream contract

There is no downstream skill. The note file is the artifact; the
user's editor (Obsidian, VS Code, vim) is the consumer. The
`source: live-notes` frontmatter field is a stable greppable marker
across all files written by this skill — useful for vault-wide queries
("show me all my live-notes from 2026") without false positives from
hand-written notes.

The skill does NOT auto-launch any follow-up tool. The post-save echo
points the user to their editor, not to another skill.

---

## Forbidden actions

Refuse even on mid-flow request (surface + ask for explicit override;
default refusal):

- Treating user silence as confirmation at the **blocking** gates:
  stale-draft `resume`/`recover`/`discard`/`skip`/`delete`,
  `confirm save`, and `cancel confirm`. (Phase L has no
  confirmation gate; the `.gitignore` offer is intentionally
  non-blocking with "leave tracked" as the silent default.)
- Invoking any side-effecting tool during Phase 1 other than the
  allowed draft-file operations listed in
  [Phase 1 — Capture mode (the loop)](#phase-1--capture-mode-the-loop)
  above (`Write` to draft header / chunk tmp, `Bash` for path
  operations, `Read` + `Write` for `undo` truncate, `Bash rm` for
  `cancel confirm`). No `WebSearch`, no `WebFetch`, no `Edit` on
  user files, no `git` commands, no skill-chaining.
- Using a bash heredoc (`<<EOF` / `<<'EOF'`) to embed user content
  in any shell command. A user note containing a line that matches
  the heredoc terminator silently truncates the chunk. The
  byte-safe recipe (Write tool for content, Bash for paths only)
  is documented in
  [references/capture-mode.md](references/capture-mode.md#append-mechanics--byte-safe-two-step-recipe)
  and [references/output-schema.md](references/output-schema.md#write-atomicity)
  — never regress to a heredoc.
- Answering factual questions embedded in the user's note content as
  if the user were asking the AI. The user is capturing notes — those
  embedded questions are notes-to-self, not prompts to the AI. See
  [references/capture-mode.md](references/capture-mode.md#what-the-ai-must-not-do-during-phase-1).
- Translating the user's captured content. Verbatim is the contract.
  Only the surrounding organizing prose (TL;DR, section headings,
  research synopses) follows `LANGUAGE`.
- Auto-resolving filename collisions silently. Surface in the Phase 3
  preview; require explicit `revise overwrite` to overwrite.
- Auto-deleting buffer-draft files. Drafts only get deleted on
  successful `confirm save` (cleanup), explicit `discard`/`delete`
  during the stale-draft prompt, or explicit `cancel confirm`
  during capture.
- Web research that exceeds the budget caps in
  [references/synthesis-and-research.md](references/synthesis-and-research.md).
  Prefer 0 research over partial.
- Fabricating Obsidian wikilinks to non-existent notes. See
  [references/output-schema.md](references/output-schema.md#obsidian-wikilinks).
- Loading or modifying any file outside `{NOTES_DIR}/` and the
  user-confirmed `.gitignore` append. The skill is a notes utility,
  not a project mutator.
- Creating `README.md` / `INSTALLATION_GUIDE.md` inside this skill
  folder (per the repo's skill-creator validator).

---

## Resumability

Resume is keyed off the buffer-draft files under
`{NOTES_DIR}/.live-notes-drafts/`. On a fresh invocation, Phase 0
detects existing drafts and prompts the user:

- Today's draft → `resume` / `discard` / `fresh`.
- Stale (yesterday+) draft → `recover` (jump to Phase 2) / `skip` / `delete`.

Full flow + edge cases:
[references/capture-mode.md](references/capture-mode.md#resume-from-stale-buffer-draft).

If a draft has no chunk content (only the header) and is being
resumed, treat the buffer as empty and continue at Phase 1 turn 1.

If a draft's `language` header line is missing (defensive guard —
should never happen since Phase 1 always writes it), default
`LANGUAGE` to Korean (matching Phase L's default) and continue
without re-prompting.
