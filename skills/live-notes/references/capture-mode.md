# Phase 1 — Capture mode (the stateful loop)

The core of this skill. Phase 1 is a multi-turn loop where the user's
messages are **note content**, not tasks. The AI must resist its
default instincts (answer questions, refactor code, propose plans) and
instead append the user's words to a buffer until a finish signal
arrives.

## Operating contract during Phase 1

For every user message received during Phase 1 — i.e. after the
Phase 0 ACK (and after any `gitignore yes` / stale-draft prompt
response, both handled in Phase 0 before any chunk is recorded) and
before the finish signal — follow these rules **in order**:

0. **Run the orphan-recovery sweep first**, before dispatching on
   the message type. A prior turn may have crashed between
   `Write(tmp)` and `cat tmp >> draft`, leaving an orphan tmp on
   disk. The sweep merges any leftover `{SESSION_ID}.chunk.*.tmp`
   into the draft (in lex/numeric order) before the next dispatch.
   Critically, this must run *before* the finish-signal check —
   otherwise a user who types `finish` immediately after a crash
   would synthesize a draft that's missing the last captured chunk.
   The same sweep also runs as the first step of Phase 2.

   ```bash
   # null_glob makes the loop body skip cleanly on no-match.
   # Both shell setops use 2>/dev/null so the wrong shell is silent.
   { setopt null_glob 2>/dev/null || shopt -s nullglob 2>/dev/null; } || true
   for f in "${NOTES_DIR}/.live-notes-drafts/${SESSION_ID}.chunk."*.tmp; do
     [ -e "$f" ] || continue   # belt-and-braces against literal-glob expansion
     cat "$f" >> "${NOTES_DIR}/.live-notes-drafts/${SESSION_ID}.draft.md" \
       && rm "$f"
   done
   ```

   The `setopt null_glob 2>/dev/null || shopt -s nullglob 2>/dev/null`
   prelude is non-negotiable: the `Bash` tool runs **zsh** on macOS by
   default. Without `null_glob`, zsh's default `nomatch` option makes
   the loop *fail loudly* on every clean turn (no orphans) with
   `zsh: no matches found: ...chunk.*.tmp`. That would surface to the
   agent as a hard error on every chunk write — empirically reproduced
   during review (zsh 5.9). The `[ -e "$f" ] || continue` line stays
   as belt-and-braces for the edge case where neither setop is
   available (e.g. a constrained POSIX `sh`).

1. **Check the finish signals.** If the message matches any of:
   - English: `finish`, `done`, `/live-notes finish`, `/live-notes done`
   - Korean: `종료`, `끝`, `마치기`, `/live-notes 종료`, `/live-notes 끝`,
     `/live-notes 마치기`
   - Case-insensitive; surrounding whitespace ignored; nothing else on
     the line. A user message like *"finish drafting that paragraph"*
     is **content**, not a finish signal — the signal must be the
     whole line (or whole message), not a substring.

   → Exit Phase 1, proceed to Phase 2 synthesis. Do NOT append the
   finish signal itself to the buffer.

2. **Check meta-commands.** If the message matches (whole-line):

   | Command | Korean alias | Persistence | Effect |
   |---|---|---|---|
   | `status` | `상태` | one-shot | Echo one line: turns captured, draft path, elapsed, language, `QUIET` state, `RESEARCH_OPT_OUT` state. Does **not** append to buffer |
   | `section <name>` | `섹션 <이름>` | one-shot | Append a divider chunk (`<!-- chunk: N at HH:MM:SS section -->\n## <name>\n`). Section name keeps the user's casing |
   | `category <slug>` | `카테고리 <슬러그>` | session-sticky | Stash `CATEGORY_HINT` for Phase 2 (overrides AI heuristic). Validates `^[a-z0-9][a-z0-9_-]*(/[a-z0-9][a-z0-9_-]*)?$` — at most one `/` |
   | `undo` | `되돌리기` | one-shot | Truncate the last content chunk from buffer + draft. Echo what was removed (first 60 chars). Limited to the last 5 chunks per session — beyond that, the user edits the draft manually |
   | `quiet` | `조용` | toggle | Toggle `QUIET`. When set, suppress per-chunk ACKs entirely (no echo on append). Echo once at toggle: `📵 quiet on` / `📢 quiet off`. Persists for the rest of the session unless toggled again |
   | `no research` | `리서치 안함` | one-way for the session | Set `RESEARCH_OPT_OUT=true`. Phase 2 skips all `WebSearch` / `WebFetch` calls; the References section is omitted unless the user pasted explicit URLs. Echo once: `🔌 research off — synthesis will skip web lookups`. No re-enable via meta-command — the user explicitly opted out, and the next session starts fresh anyway |
   | `language <ko\|en>` | `언어 <ko\|en>` | session-sticky | Switch `LANGUAGE`. ACK in the new language. Does not retroactively re-tag prior content (verbatim user input is never translated) — only future organizing prose follows the new setting. The new language persists for the rest of the session until another `language <…>` command |
   | `cancel` | `취소` | one-shot | Begin abort. Echo: `Type "cancel confirm" / "취소 확정" within the next message to abort and delete the buffer-draft. Anything else continues capture.` Does **not** delete anything by itself |
   | `cancel confirm` | `취소 확정` | terminal | Only valid as a follow-up to a prior `cancel`. Delete the buffer-draft file, exit cleanly. Echo the deleted path |

   Meta-commands give the user a tiny control surface without
   polluting the buffer (except `section`, which intentionally
   appends a structural marker to be honored at synthesis).

3. **Otherwise, treat the message as note content.** Append the
   verbatim message to the in-memory buffer **and** to the
   on-disk draft (see below). Echo a minimal ACK or, when the user has
   typed `quiet` (or `조용`) earlier in the session, no echo at all.

   Minimal ACK examples:

   - `LANGUAGE=Korean`: `📝 (124자 추가됨, 누적 1.2k자)`
   - `LANGUAGE=English`: `📝 (added 124 chars, total 1.2k)`

   The ACK is **diagnostic**, not conversational. Never propose
   follow-ups, ask clarifying questions, or interpret content. The
   user is taking notes; their next message is the next note, not a
   reply to you.

## What the AI MUST NOT do during Phase 1

These are the most common failure modes — guard against them:

- **Do not** answer factual questions embedded in the user's notes.
  A user typing *"What's the half-life of caffeine? About 5h I think"*
  is **noting** their own recollection, not asking you. Append, do not
  reply with the actual half-life. If the user genuinely wants a
  lookup mid-session, they'll meta-command or finish the session.
- **Do not** refactor or critique code the user pastes. They're
  capturing it for later reference.
- **Do not** background-summarize aggressively. Light background
  organization is allowed — see "Background organization" below — but
  do not surface the summary unprompted. The summary lives in your
  internal scratchpad until Phase 2.
- **Do not** invoke `WebSearch`, `WebFetch`, `Bash`, `Edit`, or any
  side-effecting tool during Phase 1 (except the draft-write helper
  documented below). Web research is **Phase 2 only**, gated by AI
  judgment after the user has finished. Premature research means
  spending tokens on context the user might still change.
- **Do not** treat silence as a finish signal. If the user pauses for a
  while, that's a normal capture pause. The skill waits.
- **Do not** chain into another skill. No `/code-review`, no
  `/seed-gatherer`, no `/plan-establisher`. The note is the artifact.

## Draft buffer on-disk (crash safety)

The buffer lives primarily in your conversation memory across turns,
but conversation memory can be pruned by context-window compression.
To survive that, also append each captured chunk to a draft file.

### Path

```
{NOTES_DIR}/.live-notes-drafts/{SESSION_ID}.draft.md
```

The `.live-notes-drafts/` directory is **created on the first content
message** in Phase 1 (not in Phase 0), so an aborted session that
never gets past the ACK leaves zero residue.

### Header (first content message)

```
<!-- live-notes language: {Korean|English} -->
<!-- live-notes session: {SESSION_ID} -->
<!-- live-notes started: {ISO_LOCAL} -->
<!-- live-notes root: {ROOT} -->

```

### Per-content-message append

```
<!-- chunk: {N} at {HH:MM:SS} -->
{verbatim user message}

```

The chunk markers exist for `undo` lookup and Phase 2 reconstruction.
Never edit a past chunk — `undo` truncates the file at the chunk
boundary; section dividers are appended as their own chunk.

### Append mechanics — byte-safe two-step recipe

**DO NOT use a bash heredoc to append user content.** A quoted
heredoc terminator (`<<'EOF'`) disables `${VAR}` expansion but does
**not** protect against a user typing a line whose entire content is
the literal terminator string. Real example: a user pastes a shell
snippet that itself contains `EOF` on its own line — the outer
heredoc closes early, the chunk is silently truncated, and following
lines are parsed by `sh` (potentially as commands). This was
empirically reproduced during review; do not regress it.

Use this **two-step recipe** instead — user content travels through
the `Write` tool (which writes file bytes directly without bash
parsing), and `bash` only handles paths:

**Step 1** — first content message only (one-time per session):

```bash
mkdir -p "${NOTES_DIR}/.live-notes-drafts"
```

Then use the `Write` tool to create `{NOTES_DIR}/.live-notes-drafts/{SESSION_ID}.draft.md`
with the header block (see "Header" above). The header is fixed text,
never user content — `Write` here is just the canonical create-with-content
primitive.

**Step 2** — the orphan-recovery sweep already ran at the very top of
this turn (rule 0 in the operating contract above), so by the time we
reach the per-chunk Write below, any leftover tmp from a prior
crash has already been merged. Re-running it here would be redundant
no-op work. The sweep recipe (with the `null_glob` prelude required
for zsh) is documented under
[Operating contract during Phase 1 → rule 0](#operating-contract-during-phase-1).

Glob expansion is lexicographic; the zero-padded chunk number (Step 3
below) makes lex order = numeric order, so recovered orphans append
in the order they were captured.

**Honest limitation — sweep idempotency under partial failure.**
The `cat "$f" && rm "$f"` chain handles the common `cat`-fails case
(disk full / permission mid-cat) by leaving the orphan on disk for a
later retry — that's the design goal. The opposite asymmetric case
— `cat` succeeds but `rm` fails (extremely rare: usually mid-turn
permission change or filesystem quota exhaustion) — would leave the
orphan on disk **after** its content already made it into the draft,
so the next turn's sweep re-cats it, producing a **duplicate chunk**.
The user can edit the duplicate out post-save; Phase 2 synthesis
does not attempt to deduplicate. Mentioned for honesty, not as a
ship-blocker — `rm` failure on a directory the agent itself just
wrote to is genuinely uncommon.

**Step 3** — every content message (including the first), repeated:

1. Use the `Write` tool to create a **per-chunk** temp file at
   `{NOTES_DIR}/.live-notes-drafts/{SESSION_ID}.chunk.{NNNN}.tmp`
   (zero-padded to 4 digits; chunk counter `N` lives in-memory and
   increments after a successful `cat`+`rm`). Content:

   ```
   <!-- chunk: {N} at {HH:MM:SS} -->
   {verbatim user message}

   ```

   The `Write` tool's `content` parameter is a JSON string that the
   harness passes directly to the filesystem — user content never
   enters bash source, so `EOF`/`${...}`/`` `...` `` in user input is
   harmless file bytes. Per-chunk temp filenames (not a single shared
   `.chunk.tmp`) protect orphans from being overwritten by the next
   chunk's Write — the orphan-recovery sweep above can then merge
   them in the next turn.

2. Append the temp file to the draft and remove it:

   ```bash
   cat "${NOTES_DIR}/.live-notes-drafts/${SESSION_ID}.chunk.${NNNN}.tmp" \
       >> "${NOTES_DIR}/.live-notes-drafts/${SESSION_ID}.draft.md" \
     && rm "${NOTES_DIR}/.live-notes-drafts/${SESSION_ID}.chunk.${NNNN}.tmp"
   ```

   `cat` reads bytes from a file and writes bytes to another — no
   shell parsing of content. `rm` only sees the path. The `&&` chain
   means: if `cat` fails (disk full, permission), the per-chunk temp
   stays on disk — the next turn's orphan-recovery sweep will pick
   it up rather than lose it.

**Why per-chunk temp names?** A single shared `.chunk.tmp` is a foot-gun:
if the agent crashes between Step 3's Write and the same step's `cat`,
the orphan tmp sits there carrying chunk N's content. The *next* user
turn would Write chunk N+1 to the same path, silently overwriting the
orphan — chunk N is lost without warning. Per-chunk numbered temps +
the Step 2 sweep eliminates that loss mode.

**Why two phases (Write tool then cat)?** A single-step `Write`
directly to the draft would require re-emitting the entire prior
draft each turn (`Write` overwrites). The Write-then-cat pattern lets
`Write` carry only the new chunk while `cat` accumulates — efficient
and still byte-safe.

### Phase 0 / resume orphan integration

The rule-0 sweep is per-turn. When Phase 0 detects a stale-draft to
resume (per [#resume-from-stale-buffer-draft](#resume-from-stale-buffer-draft)),
the resume bootstrap runs in this explicit order:

1. Phase 0 inspector → resolve `ROOT`, `NOTES_DIR`, etc.
2. Stale-draft detection prompt → user types `resume` / `recover` /
   `discard` / `skip` / `delete`.
3. On `resume`: rehydrate `SESSION_ID` from the chosen draft's basename.
4. **Run the orphan-recovery sweep against the resumed `SESSION_ID`**
   — this is the one-shot equivalent of the per-turn rule-0 sweep
   that fresh sessions get. Any tmp files left from the prior
   session's last incomplete turn now land in the draft.
5. **Skip Step 1 (header Write)** — the existing draft already
   carries the header from the original session. Re-writing it would
   be a no-op (identical fixed content), but the explicit skip avoids
   any ambiguity for a precise reader.
6. Rehydrate the in-memory `BUFFER` by parsing the now-post-sweep
   draft (read chunk markers in order).
7. Set the next chunk counter `N = (max chunk N seen in draft) + 1`.
8. Continue at Phase 1 turn N — and rule 0 of the per-turn loop will
   keep running on every subsequent turn, idempotently.

On `recover` (jump straight to Phase 2 from a stale draft) — the
abridged bootstrap is **5 steps** (not 8), because Phase 1 doesn't
run and no new chunks are added:

1. Phase 0 inspector → resolve `ROOT`, `NOTES_DIR`, etc.
2. Stale-draft detection prompt → user types `recover`.
3. Rehydrate `SESSION_ID` from the chosen draft's basename.
4. **Run the Phase 2 prelude orphan-recovery sweep** against the
   resumed `SESSION_ID` (per
   [synthesis-and-research.md](synthesis-and-research.md#phase-2-prelude--final-orphan-recovery-sweep)) —
   any leftover tmp files from the prior session's last incomplete
   turn now land in the draft.
5. **Rehydrate the in-memory `BUFFER`** by parsing the now-post-sweep
   draft (read chunk markers in order, populate one entry per chunk).
   This step is **load-bearing**: without it, BUFFER stays empty and
   the zero-chunks early-exit at the start of Phase 2 fires spuriously,
   wiping the user's recovered content. Mirrors step 6 of the `resume`
   bootstrap above; the only difference is no Phase 1 follows.

Then enter Phase 2 synthesis (title derivation, etc.) against the
rehydrated BUFFER. The zero-chunks check at the top of Phase 2
([synthesis-and-research.md](synthesis-and-research.md#zero-chunks-early-exit))
fires only when BUFFER is genuinely empty — which on the recover
path means a draft that had only a header (no content chunks) AND
no orphan tmps merged by step 4. That's correctly handled (drop the
header-only draft, surface the early-exit message).

### Allowed Phase 1 file operations

Strictly limited to:

- `Write` tool → `{drafts_dir}/{SESSION_ID}.draft.md` (initial header
  only, once per session — skipped on resume per the 8-step bootstrap
  order above) and `{drafts_dir}/{SESSION_ID}.chunk.{NNNN}.tmp` (one
  per chunk, removed within the same turn by the Step 3 `&&` chain —
  or, if that turn crashed, recovered next turn by rule 0's sweep).
- `Bash` `mkdir -p {drafts_dir}` (once, before the first `Write`).
- `Bash` orphan-recovery sweep at the start of **every Phase 1 turn**
  (before finish/meta/content dispatch — rule 0 of the operating
  contract above), plus the parallel Phase 2 prelude sweep in
  [synthesis-and-research.md](synthesis-and-research.md#phase-2-prelude--final-orphan-recovery-sweep)
  for direct `recover` paths. Canonical recipe with the `null_glob`
  prelude lives at [#operating-contract-during-phase-1](#operating-contract-during-phase-1) — do not paste the
  inner `for f in *.chunk.*.tmp; do ...; done` snippet without it.
- `Bash` `cat tmp >> draft && rm tmp` per chunk.
- `Bash` cleanup on `cancel confirm` — delete the draft and any
  leftover per-chunk temps. Both `rm` calls use `-f` so a cancel
  before any content message ever wrote the draft is silent rather
  than erroring on a missing path:
  ```bash
  rm -f "${NOTES_DIR}/.live-notes-drafts/${SESSION_ID}.draft.md"
  { setopt null_glob 2>/dev/null || shopt -s nullglob 2>/dev/null; } || true
  rm -f "${NOTES_DIR}/.live-notes-drafts/${SESSION_ID}.chunk."*.tmp
  ```
- `Read` + `Write` to truncate the draft on `undo` (read the draft,
  drop the last chunk marker block, write the truncated content
  back). Note that `Write` here is not write-tmp-then-rename atomic —
  a crash between `Read` and `Write` could leave the draft partially
  rewritten. The risk is bounded because the user has just *asked* to
  drop a chunk, so losing it is the intent; only the chunks *before*
  the undone one are at risk, in a window of milliseconds.

All other tool calls — `WebSearch`, `WebFetch`, `Edit` on user files,
`git`, skill invocations — are forbidden during Phase 1.

### Background organization

After every Nth content chunk (N=5 by default, tunable to taste), the
AI **may** do a silent organizing pass: skim the buffer, mentally
group adjacent chunks into topics, decide a tentative category. This
work stays **internal** — no chat echo, no draft mutation, no
tool calls. It exists only to make Phase 2 synthesis faster.

If the user runs `status` mid-session, you may surface the current
tentative category as part of the echo (`tentative category:
meetings/`) — but only when the user asked.

## Resume from stale buffer-draft

On a fresh `/live-notes` invocation, after Phase 0 inspector runs,
glob `${NOTES_DIR}/.live-notes-drafts/*.draft.md`. The `Bash` tool
runs zsh on macOS by default, so the glob loop MUST use the
`null_glob` prelude — otherwise the common case of "drafts dir
exists but is empty" (the default state after every successful
`confirm save`, since the draft is deleted at save time) fails with
`zsh: no matches found`:

```bash
{ setopt null_glob 2>/dev/null || shopt -s nullglob 2>/dev/null; } || true
for f in "${NOTES_DIR}/.live-notes-drafts/"*.draft.md; do
  [ -e "$f" ] || continue
  # ... per-draft prompt logic (see below)
done
```

For each draft found:

- Parse the `started` header.
- If the draft is from **today** and has **any content chunks**, surface:

  ```
  Found an unfinished session from {HH:MM} ({N} chunks).
  Resume (`resume`), discard (`discard`), or start fresh (`fresh`)?
  ```

- If the draft is from **today** but has **zero content chunks**
  (header-only — happens when a crash hit between Step 1 header Write
  and the first content chunk, an extremely narrow window), surface
  the same prompt with `(0 chunks)` as the count. On `resume`, treat
  `BUFFER` as empty and continue at Phase 1 turn 1; on `discard`,
  delete it; on `fresh`, leave it untouched and start a new session
  (rare and mostly harmless either way — no user content is at risk).

- If the draft is from **yesterday or older**, prompt:

  ```
  Found a stale draft from {YYYY-MM-DD HH:MM}. Synthesize-and-save
  now (`recover`), keep the file untouched (`skip`), or delete
  (`delete`)?
  ```

Silence is not yes; re-prompt.

**On `resume`**: rehydrate the buffer from the draft (parse the chunk
markers), set `LANGUAGE` from the draft header, set `SESSION_ID` to
the draft's session, continue at Phase 1 turn N+1.

**On `recover`**: run the [5-step abridged recover
bootstrap](#phase-0--resume-orphan-integration) — including the
**load-bearing** `BUFFER` rehydration at step 5 — then enter Phase 2
synthesis directly (no Phase 1 turns follow). Skipping step 5 lets the
zero-chunks gate fire spuriously and wipes the recovered content; do
not regress to "jump to Phase 2 directly" without the rehydration.

**On `fresh`/`skip`**: leave the old draft alone, start a new session.

**On `discard`/`delete`**: clean the specific draft file and any
leftover per-chunk temps for that session, then start fresh:

```bash
rm -f "${NOTES_DIR}/.live-notes-drafts/${SESSION_ID}.draft.md"
{ setopt null_glob 2>/dev/null || shopt -s nullglob 2>/dev/null; } || true
rm -f "${NOTES_DIR}/.live-notes-drafts/${SESSION_ID}.chunk."*.tmp
```

`rm -f` matches the cleanup-uniformity rule used at all four cleanup
sites in this skill (cancel-confirm, save-success, zero-chunks
early-exit, discard/delete) and is defensive against a TOCTOU race
with a concurrent `/live-notes` in another terminal that already
cleaned up the same stale draft.

Never auto-delete a draft without explicit user choice — the user
might have closed their terminal mid-meeting and needs that content.

**On any other reply (not one of the prompt tokens)**: treat the
input as **not** the user's answer to the stale-draft prompt — do
NOT proceed to Phase 1 with the unparsed message, do NOT silently
default to one of the branches. Re-prompt the same question. This
mirrors the gating discipline used elsewhere ("Silence is not yes"):
the stale-draft prompt is a blocking gate because mishandling drafts
has real consequences (either lost meeting notes or unwanted file
deletion). Free-text replies, mid-input typos, and any non-token
content all fall through to the re-prompt.

## Honest limitations

- The 5-chunk `undo` window is a heuristic; deeper rollback requires
  manually editing the draft file. The skill won't paper over that.
- A draft that hits the FS write limit (extremely unlikely — would
  require many MB of notes in one session) will fail the append. The
  AI should surface that error and offer to truncate at the previous
  chunk and finish-now.
- The "whole-line finish signal" rule means a user who pastes a
  multi-line block containing "finish" on its own line **will** end
  the session. The Phase 0 ACK pre-warns the user about this
  ("한 줄에 단독 입력" / "whole line, alone") so the edge case is at
  least announced before it bites.
- Concurrent invocations in the same `NOTES_DIR` (e.g. user opens two
  terminals) each get their own `SESSION_ID` and draft file — they
  won't collide, but the user must finish each independently.
