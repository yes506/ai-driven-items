# Hook automation adapter (EXPERIMENTAL — opt-in, draft-only by default)

The skill is **manual-first**: `/knowledge-harvest` works fully without any hook.
This adapter is an optional trigger that runs the same skill headless at the end
of a work cycle. It is off unless `hook.enabled = true` in config, and even then
it is **draft-only** (writes to `_needs-review/` only) until you deliberately
enable active updates. Do not ship it enabled.

Table of contents:
- [Why a hook can't do the work itself](#why-a-hook-cant-do-the-work-itself)
- [The loop hazard and the three-layer guard](#the-loop-hazard-and-the-three-layer-guard)
- [Trigger choice: SessionEnd, not Stop](#trigger-choice-sessionend-not-stop)
- [Per-CLI recipes](#per-cli-recipes)
- [Mandatory pre-enable test](#mandatory-pre-enable-test)

## Why a hook can't do the work itself

A hook is a shell command; it cannot do the LLM reasoning (distill, fuzzy match).
So the hook's only job is to **spawn a headless agent** that runs
`/knowledge-harvest`. That spawn is what creates the loop hazard below.

## The loop hazard and the three-layer guard

If a `SessionEnd`/`Stop` hook spawns a fresh `claude -p`, that child is a NEW
session that starts with `stop_hook_active=false` and reloads the same global
hook config — so its own termination fires the hook again → fork-bomb.
`stop_hook_active` guards the *self-continue* loop, NOT this *spawn-new-session*
loop. Defense is three independent layers:

1. **Structural (best):** launch the child with hooks disabled. On Claude Code,
   `claude --bare` skips hook auto-discovery **and still resolves `/skill-name`**
   (verified on 2.1.x). `--settings '{"disableAllHooks":true}'` also works but does
   NOT suppress managed/enterprise-layer hooks. `--settings <file>` alone is a
   MERGE, so a "no-hooks settings file" does NOT remove existing hooks — do not
   rely on it.
2. **Sentinel:** set `AI_KNOWLEDGE_HARVEST_ORIGIN=hook` on the child; the hook
   script exits early if it sees it. Note some tools sanitize hook env (Gemini) —
   so back it with a file marker under `.state/`, never rely on env alone.
3. **Lock:** `apply_plan.py`'s `mkdir` lock (with stale reclaim) prevents a manual
   run and a hook-spawned run from racing on writes.

Because `--bare` also disables CLAUDE.md/MCP/auto-memory discovery, inject context
explicitly: `--mcp-config` (Obsidian MCP), `--add-dir` (target), skill body carries
the vault contract.

## Trigger choice: SessionEnd, not Stop

`Stop` fires **every turn** (whenever the assistant finishes responding), not once
per work cycle — harvesting there means a distill session per message: cost/noise
blowup. Use `SessionEnd` (closer to "cycle done", and it **cannot block**, so the
self-continue loop is structurally gone). SessionEnd runs at teardown with a
timeout, and a distill run can take minutes → **detach** the child
(`setsid`/`nohup … & disown`) so a timeout SIGKILL can't interrupt a note write
mid-flight. Notes are still written atomically (`ln`/`mv`), so a killed child
leaves no half-written file. If you must use `Stop`, add a debounce (only harvest
when the diff since the last harvest exceeds a threshold).

## Per-CLI recipes

All four CLIs now have hooks with a cycle-end event. Sketch (draft-only child):

```bash
# Claude Code — SessionEnd hook
[ "$AI_KNOWLEDGE_HARVEST_ORIGIN" = hook ] && exit 0        # sentinel guard
AI_KNOWLEDGE_HARVEST_ORIGIN=hook setsid claude --bare -p "/knowledge-harvest --source-hook" \
  --add-dir "$PWD" >/dev/null 2>&1 &                        # detached, hooks off
```

- **Codex CLI** (`Stop`): hooks merge across config layers, so a hook-free profile
  is not enough. Use `codex exec --ignore-user-config -c 'features.hooks=false'`.
- **Gemini CLI** (`AfterAgent`): env is sanitized → the file-marker sentinel is
  mandatory; `AfterAgent` firing has known reliability bugs → treat as best-effort.
- **Copilot CLI** (`agentStop`/`sessionEnd`): policy-layer hooks cannot be disabled
  by `disableAllHooks`; verify the child does not re-trigger.

## Mandatory pre-enable test

Before enabling the hook on any CLI, prove it does not recurse: in a throwaway
repo, install the hook with a **counter + hard cap** and confirm the child spawns
at most once. Only after that test passes should you set `hook.enabled = true`,
and keep `hook_allow_active_updates = false` until manual mode has proven stable.
