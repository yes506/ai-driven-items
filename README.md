# ai-driven-items

**[English](#english)** · **[한국어](#한국어)**

---

## English

A collection of AI-driven developer utilities for the [Claude Code](https://docs.claude.com/en/docs/claude-code) ecosystem — skills, agents, MCP servers, and playbooks. Each utility is self-contained, validated against the official Claude Skills standard, and **portable to other AI coding tools** (Codex CLI, Gemini CLI, GitHub Copilot, Cursor) with light adaptation.

This README is the **item index** for the repo. Items are grouped by type below; per-tool install instructions follow.

### Item index

#### Skills

| Skill | What it does |
|---|---|
| [`project-scaffolder`](skills/project-scaffolder/) | Language-agnostic project bootstrapping. Walks intent → 2-4 tech-stack options → scaffolded baseline (lint, test, logging, config, CI stub, health endpoint). Runs entirely inside an isolated git worktree and merges back to `dev` only after explicit user confirmation. Tier-1 stacks: Next.js, Spring Boot, FastAPI, Go, Node/Express. |
| [`intent-aligner`](skills/intent-aligner/) | Head of the planning chain — and now **bidirectional** with `seed-gatherer`. Extracts what's actually in the user's head before any planning starts: an interactive elicitation dialog (Socratic loops + 5 Whys + example/counter-example disambiguation) auto-detects whether the user brings a **feature/product idea** or a **problem/pain**, then iterates until intent converges. Emits a dual-format artifact — `intent.<slug>.md` (structured AI-parseable seed) and `intent.<slug>.html` (static, self-contained, human-verifiable). Stack-, planner-, and lane-agnostic: the file's 6 rubric-aligned fields (Goal, In-scope features, Out-of-scope, Constraints, Success criteria, Open questions) are directly readable by `codebase-planner`. **Two invocations**: `/intent-aligner` for first capture (create mode, revision 1), and `/intent-aligner update <slug>` for refinement from accumulated seeds — the seed→intent feedback loop that lets intent grow more solid before planning. Update mode loads existing intent + globs `seeds/seed.<slug>.*.md`, proposes per-field refinements with seed-backed citations, bumps the revision (`Revision: N`), and merges with marker `(intent, updated-from-seeds, human-confirmed)`. Downstream `seed-gatherer` collects evidence, `plan-establisher` folds intent + seeds into `plan.<intent-slug>.v<N>.md`. Create-mode marker: `(intent, human-confirmed)`. Manual invocation only — `/intent-aligner` or `/intent-aligner update <slug>`. |
| [`seed-gatherer`](skills/seed-gatherer/) | Bidirectional with `intent-aligner` in the planning chain. **Standard path**: reads existing `intent.<slug>.md` and grows an evidence corpus from user-supplied URLs / YouTube / PDFs / images / local docs/code; each resource is intent-filtered into an md+html seed pair under `seeds/seed.<intent-slug>.<resource-slug>.{md,html}` with source provenance + relevance rationale. **Bootstrap path**: when no intent.md exists, the user supplies a starting prompt / URL / file and the skill captures intent ad-hoc (revision 1, marked `Bootstrapped by: seed-gatherer`), emitting intent.md + intent.html alongside seeds in a single merge — marker `(intent+seeds, bootstrap, human-confirmed)`. **Ideation path**: when the user has no external material, AI/user back-and-forth dialogue plus feasibility checks (WebSearch, local code grep, reference doc lookup) crystallize one seed per accepted idea — marker `(seeds, ideation, human-confirmed)`. Bootstrap and ideation compose. Pre-fetch `proceed` gates protect against accidentally-pasted URLs in both bootstrap and standard intake. Iteratively re-runnable across worktree+merge cycles with 3-case collision disambiguation. Feeds `plan-establisher`; refinement of the bootstrapped intent flows back to `/intent-aligner update <slug>`. Manual invocation only — `/seed-gatherer`. |
| [`plan-establisher`](skills/plan-establisher/) | Sits between `seed-gatherer` and the downstream planners — **`codebase-planner`** (for code) and **`document-planner`** (for documents). Reads `intent.<slug>.md` (required) and `seeds/seed.<intent-slug>.*.md` (optional), runs **4 verification dimensions** (intent self-consistency, seeds-vs-intent, seeds-vs-seeds, planner-rubric completeness), resolves ambiguities via interactive Socratic dialog (per-finding `(d) Defer` or batch `accept remaining`), then emits a folded planner-ready `plan.<intent-slug>.v<N>.md` + `.html` at the repo root. The downstream planner reads ONLY the plan; `intent.md` + `seeds/` become raw source material the planner doesn't re-read. Includes a proposed scale lane (`micro` / `local` / `feature` / `system`) with reasoning + an Evidence inventory mapping rubric fields → contributing seeds. Iteratively re-runnable — each invocation emits the next monotonic version (`v1`, `v2`, ...) with prior versions preserved as audit trail; Phase 5 race-guard re-scans for parallel runs. Runs inside a git worktree and merges to `dev` only after `confirm merge`; marker `(plan, human-confirmed)` keeps the chain visible in `git log`. Manual invocation only — `/plan-establisher`. |
| [`codebase-planner`](skills/codebase-planner/) | Decides how much planning a code change needs, then runs only the phases that lane requires. Four scale lanes: **micro** (one-function, 3–7 bullet chat plan, no worktree), **local** (≤3 files / 1 module, chat plan), **feature** (worktree + `plan.md` + Mermaid DAG, optional skeletons), **system** (full interface-skeleton workflow inherited verbatim from the prior codebase-architect skill — worktree + 9-field docstrings + Mermaid DAG + HTML report + human-confirmation merge gate). Lane is picked by a scored tuple (scope, risk, ambiguity) before any mutation; ambiguous requests block-and-ask rather than silently over-engineer. Downstream implementer agents read a scale-tagged marker family (see `codebase-implementer` below). Manual invocation only — `/codebase-planner`. |
| [`codebase-implementer`](skills/codebase-implementer/) | Downstream half of the planner→implementer chain. Reads the planner's scale-tagged, human-confirmed marker from chat (micro/local) or merge commit (feature/system), creates its own git worktree, then runs an **autonomous** implementation loop across all phases (no per-step prompts; only pause is a genuine blocker like a missing collaborator). Generates method bodies from 9-field docstrings (system) or plan steps (feature) or bullets (micro/local), runs the project's compile+test command with bounded auto-fix (default 3 attempts, oscillation-detected), emits an `implementation-report.md` for review, and merges to the base branch (default `dev`) only after the user types `confirm merge`. Language-agnostic. Body-generation only — refuses to re-architect, refactor, or rename committed signatures. Manual invocation only — `/codebase-implementer`. |
| [`document-planner`](skills/document-planner/) | The document-shaped sibling of `codebase-planner`. Decides how much planning a document needs, then runs only the phases that lane requires — same four scale lanes (**micro** / **local** / **feature** / **system**) and same `(scope, risk, ambiguity)` triage, but axes are re-grounded in document semantics (scope = content volume, risk = accuracy / compliance, ambiguity = unresolved claims/evidence/audience). First-class **DOCTYPE** classification picks one of `api-spec` / `tech-spec` / `runbook` / `ppt` and drives the stub primitive (per-endpoint / per-section / per-step / per-slide) and the eventual output stack (`text` for markdown doctypes; `structured` for pptx). Heavy lanes emit a **9-field stub schema** (`## stub: <id>` + YAML body — id, purpose, audience, key claims, evidence sources, dependencies, acceptance criteria, length budget, open questions) plus a Mermaid dependency DAG and self-contained HTML preview. Bundled validators check structure (DFS cycle detection), internal-ref resolution (`[[stub-id]]`), and undeclared-dependency catches at the render step. Marker family `(document-plan-<scale>, human-confirmed)` is a fresh choice — does NOT inherit codebase-planner's legacy `(interfaces only, …)` system marker. Manual invocation only — `/document-planner`. |
| [`document-implementer`](skills/document-implementer/) | Downstream half of the `document-planner` → `document-implementer` pair. Reads the planner's `(document-plan-<scale>, human-confirmed)` handoff (frontmatter at the top of `document-plan.md` for feature/system; chat-handoff block for micro/local with explicit chronological pairing rules for `revise` cycles), creates its own git worktree, then runs an **autonomous** generation loop in source order — text doctypes (api-spec / tech-spec / runbook) write markdown directly to `TARGET_PATH` with explicit `<a id="<stub-id>"></a>` anchors before each section heading; structured (ppt) accumulates per-slide content in state and renders via bundled `render_pptx.py` (with stub-id provenance injected into each slide's speaker notes). Bounded auto-fix at Phase 4 (text=3 attempts; structured=0 — pptx failures are rarely LLM-fixable). Phase 5 self-verification report includes an **explicit per-stub acceptance-criteria checklist** the human reviewer ticks before `confirm merge` lands the merge with marker `(document-impl-<scale>, human-confirmed)`. Mirror discipline with planner-side `parse_frontmatter.py` (planner is canonical). Manual invocation only — `/document-implementer`. |
| [`collect-searches`](skills/collect-searches/) | Two-stage Chrome-search-history → Obsidian pipeline. Stage 1 is a deterministic Python collector (`scripts/collect.py`) that reads Chrome's local SQLite history, owns the cursor and lock, and stages new Google searches as JSON in a vault inbox. Stage 2 is a prompt-orchestrated workflow that classifies each query into an Obsidian category folder, enriches it with 1–3 WebSearch sources, and writes one Markdown note per search. Designed for periodic runs (e.g. `/loop 6h /collect-searches`). Has side effects (writes notes, deletes inbox files on success); manual invocation only — `/collect-searches`. |
| [`live-notes`](skills/live-notes/) | Keep-on note-taking companion for meetings, study sessions, or any free-form capture. `/live-notes` enters capture mode immediately — every subsequent user message is appended **verbatim** to a buffered note until a finish signal arrives (`finish` / `done` / `종료` / `끝` / `마치기` as a whole line). On finish the skill synthesizes the buffer into a TL;DR-up-top, detail-below markdown file with Obsidian-compatible YAML frontmatter (English keys, `source: live-notes`, ASCII tag slugs), and optionally invokes **light AI-discretionary web research** (≤ 3 `WebSearch` + ≤ 3 `WebFetch`, ≤ 120s wall-clock) to verify factual claims the user flagged as uncertain or to define named entities the user referenced — strictly within a citation-required References section. Output lands at `{project-root}/{root-basename}-notes/{category}/{YYYY-MM-DD}-{HHmm}-{title-slug}.md`; the AI proposes a category from content heuristics (`meetings/`, `study/`, `projects/<slug>/`, `tech/<topic>/`, `research/<topic>/`, `journal/`, `inbox/`) which the user can override via `revise category <slug>`. Meta-commands during capture: `section <name>` / `category <slug>` / `status` / `undo` / `quiet` / `no research` / `language <ko\|en>` / `cancel` / `cancel confirm` (+ Korean aliases — `상태` / `섹션` / `카테고리` / `되돌리기` / `조용` / `리서치 안함` / `언어` / `취소` / `취소 확정`). A buffer-draft file under `.live-notes-drafts/` provides crash safety with per-chunk temp names + a per-turn orphan-recovery sweep so a mid-write crash never loses a captured chunk; stale drafts trigger a `resume` / `recover` / `discard` prompt on the next invocation. Korean default with English fallback per `references/language-selection.md`; verbatim user content is **never** translated, only the organizing voice (TL;DR, section intros, research synopses) follows `LANGUAGE`. Manual invocation only — `/live-notes`. |

#### Agents

_(planned — none shipped yet)_

#### MCP servers

_(planned — none shipped yet)_

#### Playbooks

_(planned — none shipped yet)_

### Repository layout

```
ai-driven-items/
├── skills/             Claude Code skills (procedural workflows + bundled resources)
│   ├── project-scaffolder/
│   ├── intent-aligner/
│   ├── seed-gatherer/
│   ├── plan-establisher/
│   ├── codebase-planner/
│   ├── codebase-implementer/
│   ├── document-planner/
│   ├── document-implementer/
│   ├── collect-searches/
│   └── live-notes/
├── agents/             (planned) Custom Claude Code subagents
├── mcp-servers/        (planned) Model Context Protocol servers
├── playbooks/          (planned) Reusable, AI-consumable implementation guides
└── README.md
```

**Where skills write their deliverables.** Side-effect skills never scatter
artifacts across your project root — they all write under a single committed
`ai-artifacts/` directory (created on first use), so multiple skill runs in one
project never collide:

```
ai-artifacts/
├── intents/   intent.<slug>.{md,html}             # intent-aligner / seed-gatherer
├── seeds/     seed.<slug>.<resource>.{md,html}    # seed-gatherer
├── plans/     plan.<slug>.v<N>.{md,html}          # plan-establisher (versioned)
└── runs/
    ├── code/<slug>-<planner-id>/                  # codebase-planner → codebase-implementer
    │     plan.md  plan.mmd | architecture.{html,mmd}   report.<impl-id>.md
    └── doc/<slug>-<docplanner-id>/                # document-planner → document-implementer
          document-plan.md  document-structure.{mmd,html}   report.<impl-id>.md
```

Durable artifacts (intents/seeds/plans) are slug- and version-named; per-run
planner→implementer handoffs keep stable filenames inside a run-id-keyed
directory whose path is passed downstream via an `AI-Artifacts-Run-Dir:` git
trailer on the merge commit. Exempt from `ai-artifacts/`: `document-implementer`
writes the finished document to your chosen `TARGET_PATH`; `collect-searches`
and `live-notes` write to their own note targets.

### Installing

The install instructions below use `project-scaffolder` as the running example. **Substitute `<name>`** with the directory name of any other utility from the index above (e.g. `codebase-planner`).

#### Claude Code (native)

Run from the repo root:

```bash
# Global — available in every Claude Code session
mkdir -p ~/.claude/skills
ln -s "$(pwd)/skills/project-scaffolder" ~/.claude/skills/project-scaffolder

# Or project-local — only in one project
mkdir -p /path/to/your-project/.claude/skills
ln -s "$(pwd)/skills/project-scaffolder" /path/to/your-project/.claude/skills/project-scaffolder
```

Windows note: `ln -s` requires Developer Mode or admin. Use `mklink /J` (cmd) or `New-Item -ItemType SymbolicLink` (PowerShell) instead, or use WSL.

Invoke with `/project-scaffolder` (or `/<name>` for any other utility). Skills that ship with `disable-model-invocation: true` only fire on explicit invocation.

### Using with other AI coding tools

The SKILL.md body is plain Markdown describing a workflow — any AI tool that can accept custom instructions can use it. What differs per tool is **where the file goes** and **how the tool loads it**. Bundled scripts under `skills/<name>/scripts/` are portable and work unchanged.

When porting, two Claude-specific bits to adapt:

- **Frontmatter**: `name`, `description`, `disable-model-invocation` are Claude Code fields. Other tools either ignore them or use a different schema (see per-tool notes below).
- **`${CLAUDE_SKILL_DIR}`**: Claude resolves this at load time. For other tools, replace with the actual absolute path to the skill directory.

#### Codex CLI

Codex CLI has a near-identical skill convention. Run from the repo root:

```bash
mkdir -p ~/.codex/skills
ln -s "$(pwd)/skills/project-scaffolder" ~/.codex/skills/project-scaffolder
```

Then invoke `/project-scaffolder` from inside Codex. The frontmatter is broadly compatible; if Codex rejects an unknown field, remove `disable-model-invocation` and tell the agent the workflow is manual-only in the body.

#### Gemini CLI

Gemini CLI doesn't have a skill system, but it loads `GEMINI.md` for context. Two adoption patterns:

```bash
# Option A — wire as a custom command (recommended for repeat use)
mkdir -p ~/.gemini/commands
cat > ~/.gemini/commands/project-scaffolder.toml <<'EOF'
description = "Bootstrap a new project's common, non-domain baseline inside an isolated git worktree."
prompt = """
Follow the workflow in: /absolute/path/to/skills/project-scaffolder/SKILL.md
References live next to it under references/.
"""
EOF

# Option B — drop the SKILL.md body into the project's GEMINI.md
# (strips the YAML frontmatter automatically, preserves body --- separators)
awk 'fm < 2 { if (/^---$/) fm++; next } { print }' \
  skills/project-scaffolder/SKILL.md > ./GEMINI.md
```

Invoke option A with `/project-scaffolder` inside Gemini; option B is automatic context once `GEMINI.md` is present.

#### GitHub Copilot (Copilot Chat in IDE, or `gh copilot`)

Copilot has no skill system; the closest equivalent is the project-level instructions file.

```bash
# Project-scoped: tell Copilot Chat to follow the workflow
mkdir -p .github
cat > .github/copilot-instructions.md <<'EOF'
When the user asks to scaffold a project, follow the workflow in
/absolute/path/to/skills/project-scaffolder/SKILL.md. Honor every phase
gate (no mutations before stack confirmation; no merge without user
typing `confirm merge`). References live under references/ next to it.
EOF
```

Note about the `gh copilot` CLI: it's scoped to single-command suggestions (`gh copilot suggest`) and command-explanation (`gh copilot explain`), not multi-step interactive workflows. Piping a procedural workflow into `gh copilot suggest` returns one shell-command suggestion, not the documented Phase-gated execution. For workflow-style use, stay with the `.github/copilot-instructions.md` route above and drive the workflow via Copilot Chat in your IDE.

#### Cursor AI

Cursor uses `.cursor/rules/*.mdc` with its own frontmatter format.

```bash
# Project-scoped: convert SKILL.md frontmatter to MDC frontmatter
mkdir -p .cursor/rules
cat > .cursor/rules/project-scaffolder.mdc <<'EOF'
---
description: Bootstrap a new project's common, non-domain baseline inside an isolated git worktree.
globs: []
alwaysApply: false
---
EOF
# Append the SKILL.md body (everything after the YAML frontmatter).
# Uses awk, not sed: SKILL.md uses --- horizontal-rule separators in the
# body too, and a naive sed range would silently drop most Phase sections.
awk 'fm < 2 { if (/^---$/) fm++; next } { print }' \
  skills/project-scaffolder/SKILL.md >> .cursor/rules/project-scaffolder.mdc
```

In Cursor, attach the rule explicitly when starting a task (or set `alwaysApply: true` if you want it on every chat).

### Validating a skill

Each Claude Code skill is expected to pass the official validators:

```bash
python3 ~/.claude/skills/skill-creator/scripts/quick_validate.py skills/<name>
python3 ~/.claude/skills/skill-creator/scripts/package_skill.py skills/<name> /tmp/out
```

These check the YAML frontmatter, the 500-line `SKILL.md` soft cap, the directory layout, and `${CLAUDE_SKILL_DIR}/...` reference resolution.

### Contributing

1. Each utility lives in its own subdirectory under the appropriate top-level category (`skills/`, `agents/`, …).
2. Run the validator for the category before opening a PR.
3. Keep machine-local state out of git — `.claude/settings.local.json` is already gitignored; add new patterns to `.gitignore` if you find leakage.
4. If the utility is portable to non-Claude AI tools, add a note to the per-tool table in this README.
5. Add a row for the new utility in the **Item index** above so it's discoverable.

**AI-tool instruction files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`) are intentionally gitignored.** This is a deliberate convention break from the typical "commit `CLAUDE.md` so the whole team shares context" pattern. Each contributor authors their own version locally based on this README, because tool stacks and instruction styles differ per maintainer. If your AI tool runs `claude /init` (or equivalent) and writes a `CLAUDE.md`, you'll see it silently ignored — that's expected. This README is the canonical contributor doc; the rest is yours to tailor.

### License

Released into the public domain via [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/). To the extent possible under law, the author(s) have waived all copyright and related or neighboring rights to this work. You may copy, modify, distribute, and use the work, even for commercial purposes, all without asking permission. See [`LICENSE`](LICENSE) for the full text.

---

## 한국어

[Claude Code](https://docs.claude.com/en/docs/claude-code) 생태계용 AI 기반 개발 유틸리티 모음 — 스킬, 에이전트, MCP 서버, 플레이북 등 빌딩 블록을 제공합니다. 각 유틸리티는 독립적이고, 공식 Claude Skills 표준을 통과하며, **약간의 수정만으로 다른 AI 코딩 도구**(Codex CLI, Gemini CLI, GitHub Copilot, Cursor)에서도 사용할 수 있습니다.

이 README는 저장소의 **아이템 인덱스** 역할을 합니다. 아이템은 아래에 유형별로 그룹화되어 있으며, 도구별 설치 방법은 그 뒤에 이어집니다.

### 아이템 인덱스

#### 스킬

| 스킬 | 설명 |
|---|---|
| [`project-scaffolder`](skills/project-scaffolder/) | 언어 무관 프로젝트 부트스트래퍼. 의도 파악 → 2-4개 스택 옵션 추천 → 베이스라인 스캐폴딩 (린트, 테스트, 로깅, 설정, CI 스텁, 헬스 엔드포인트) 흐름으로 진행합니다. 모든 작업은 격리된 git worktree 안에서만 일어나며, 사용자가 명시적으로 확인해야만 `dev` 브랜치로 머지됩니다. Tier-1 스택: Next.js, Spring Boot, FastAPI, Go, Node/Express. |
| [`intent-aligner`](skills/intent-aligner/) | 계획 체인의 **상류** 단계 — 이제 `seed-gatherer`와 **양방향**으로 연결됩니다. 계획에 들어가기 전에 사용자의 머릿속에 있는 의도를 끄집어내 명확히 합니다. 대화형 elicitation(소크라테스식 질문 루프 + 5 Whys + 예시/반례 분별)을 통해 **만들고 싶은 기능/제품**인지 **겪고 있는 문제/불편함**인지 자동 판별하고, 의도가 수렴할 때까지 반복합니다. 결과물은 두 형식 — `intent.<slug>.md`(구조화된 AI 파싱용 시드) 및 `intent.<slug>.html`(외부 의존성 없는 사람 검증용 문서). 스택·플래너·레인 무관: 6개 루브릭 필드(Goal, In-scope features, Out-of-scope, Constraints, Success criteria, Open questions)는 `codebase-planner`가 그대로 읽을 수 있습니다. **두 가지 호출**: `/intent-aligner`로 최초 캡처(create mode, revision 1) 또는 `/intent-aligner update <slug>`로 누적된 시드로부터 의도를 정제(update mode). update mode는 기존 intent + `seeds/seed.<slug>.*.md` 글롭을 로드해 시드 근거가 붙은 필드별 정제안을 제안하고, revision을 1씩 증가(`Revision: N`)시키며 `(intent, updated-from-seeds, human-confirmed)` 마커로 머지합니다 — 시드→의도 피드백 루프를 통해 계획을 시작하기 전에 의도를 더욱 단단하게 만듭니다. 다운스트림 `seed-gatherer`가 evidence를 모으고, `plan-establisher`가 intent + 시드를 `plan.<intent-slug>.v<N>.md`로 folding합니다. Create-mode 마커: `(intent, human-confirmed)`. 수동 호출 전용 — `/intent-aligner` 또는 `/intent-aligner update <slug>`. |
| [`seed-gatherer`](skills/seed-gatherer/) | 계획 체인에서 `intent-aligner`와 **양방향**으로 연결. **Standard path**: 기존 `intent.<slug>.md`를 읽어 사용자가 제공한 외부 자료(웹 URL, YouTube, PDF, 이미지, 로컬 문서/코드)에서 evidence corpus를 키워, 출처 provenance·의도-필터링된 추출·intent 필드별 관련성 설명을 담은 md+html 시드 쌍(`seeds/seed.<intent-slug>.<resource-slug>.{md,html}`)을 리소스당 하나씩 산출합니다. **Bootstrap path**: intent.md가 없을 때 사용자가 prompt/URL/파일을 제공하면 스킬이 즉석에서 intent를 캡처(revision 1, `Bootstrapped by: seed-gatherer` 표식)해 intent.md + intent.html을 시드와 함께 한 번의 머지에 산출 — 마커 `(intent+seeds, bootstrap, human-confirmed)`. **Ideation path**: 외부 자료가 전혀 없을 때 AI/사용자 간 tiki-taka 대화 + feasibility 검증(WebSearch, 로컬 코드 grep, 레퍼런스 문서 조회)을 통해 채택된 아이디어 하나당 하나의 시드로 결정화 — 마커 `(seeds, ideation, human-confirmed)`. Bootstrap과 ideation은 결합 가능합니다. 외부 fetch 직전의 `proceed` 게이트로 잘못 붙여넣은 URL을 차단(bootstrap과 standard 인테이크 양쪽 적용). 반복 실행 가능, 3-case 충돌 해소 보존. `plan-establisher`에 입력되고, 부트스트랩된 intent의 정제는 `/intent-aligner update <slug>`로 흘러갑니다. 수동 호출 전용 — `/seed-gatherer`. |
| [`plan-establisher`](skills/plan-establisher/) | `seed-gatherer`와 다운스트림 플래너들 — **`codebase-planner`**(코드용)와 **`document-planner`**(문서용) — 사이에 위치합니다. `intent.<slug>.md`(필수)와 `seeds/seed.<intent-slug>.*.md`(선택) 를 읽어 **4가지 검증 차원**(intent 자체 일관성, seeds-vs-intent, seeds-vs-seeds, planner-루브릭 완전성)을 실행하고, 대화형 소크라테스 다이얼로그(개별 `(d) Defer` 또는 일괄 `accept remaining`)로 모호성을 해결한 뒤, 플래너 친화적으로 folding된 `plan.<intent-slug>.v<N>.md` + `.html`을 저장소 루트에 산출합니다. 다운스트림 플래너는 이 plan **만** 활성 입력으로 읽고, `intent.md`와 `seeds/`는 원본 소스 자료가 됩니다. 제안 scale lane(`micro`/`local`/`feature`/`system`) + 근거와, 루브릭 필드 → 기여 시드 매핑인 Evidence inventory를 포함합니다. 반복 실행 가능 — 각 호출은 다음 단조 증가 버전(`v1`, `v2`, ...)을 산출하며 이전 버전을 audit trail로 보존하고, Phase 5에서 병렬 실행을 위한 race-guard 재스캔을 수행합니다. 모든 mutation은 git worktree 안에서만 일어나며 `confirm merge` 후에만 `dev`로 머지됩니다. 머지 마커 `(plan, human-confirmed)`로 `git log`에서 체인이 가시화됩니다. 수동 호출 전용 — `/plan-establisher`. |
| [`codebase-planner`](skills/codebase-planner/) | 코드 변경에 필요한 **계획 규모**를 먼저 판정한 뒤, 해당 레인에 필요한 단계만 실행합니다. 네 단계 스케일: **micro**(단일 함수 수준, 3–7 항목 채팅 플랜, worktree 없음), **local**(≤3 파일·단일 모듈, 채팅 플랜), **feature**(worktree + `plan.md` + Mermaid DAG, 스켈레톤 선택적), **system**(이전 codebase-architect 스킬의 전체 인터페이스-스켈레톤 워크플로 — worktree + 9-필드 docstring + Mermaid DAG + HTML 리포트 + 사람 확인 머지 게이트). 레인은 mutation 직전에 (scope, risk, ambiguity) 점수 튜플로 결정되며, 요청이 모호하면 silently 과설계하지 않고 명확화 질문으로 차단합니다. 다운스트림 구현 에이전트는 scale-tagged marker family를 읽습니다(아래 `codebase-implementer` 참조). 수동 호출 전용 — `/codebase-planner`. |
| [`codebase-implementer`](skills/codebase-implementer/) | planner→implementer 체인의 다운스트림 절반. 사용자가 확인한 planner의 scale-tagged marker를 chat(micro/local) 또는 머지 커밋(feature/system)에서 읽어, 자체 git worktree를 만든 뒤 모든 phase를 **자율적으로** 실행합니다(per-step 확인 없음, 진짜 blocker(예: 미정의 collaborator)만 정지 신호). 구현 본문을 9-필드 docstring(system) 또는 plan 단계(feature) 또는 bullet(micro/local)에서 생성하고, 프로젝트의 compile+test 명령을 bounded auto-fix(기본 3회, oscillation 감지)로 돌린 뒤, 리뷰용 `implementation-report.md`를 생성하고, 사용자가 `confirm merge`라고 입력해야만 base branch(기본 `dev`)로 머지합니다. 언어 무관. 본문 생성 전용 — re-architecting, refactoring, 커밋된 시그니처 변경은 거부합니다. 수동 호출 전용 — `/codebase-implementer`. |
| [`document-planner`](skills/document-planner/) | `codebase-planner`의 문서 버전 자매 스킬. 문서에 필요한 **계획 규모**를 먼저 판정한 뒤, 해당 레인에 필요한 단계만 실행 — 네 단계 스케일(**micro** / **local** / **feature** / **system**)과 `(scope, risk, ambiguity)` triage는 동일하나, 축은 문서 의미로 재정의됩니다(scope = 콘텐츠 분량, risk = 정확성/컴플라이언스, ambiguity = 미해결 주장/근거/대상). 1급 시민인 **DOCTYPE** 분류가 `api-spec` / `tech-spec` / `runbook` / `ppt` 중 하나를 선택해 stub primitive(엔드포인트별 / 섹션별 / 단계별 / 슬라이드별)와 다운스트림 출력 스택(`text`는 markdown 계열, `structured`는 pptx)을 결정합니다. 무거운 레인은 **9-필드 stub 스키마**(`## stub: <id>` + YAML 본문 — id, purpose, audience, key claims, evidence sources, dependencies, acceptance criteria, length budget, open questions) + Mermaid 의존성 DAG + 자체 완결형 HTML 미리보기를 산출합니다. 번들 검증기는 구조(DFS 사이클 감지), 내부 참조 해결(`[[stub-id]]`), 그리고 렌더 단계에서의 미선언 의존성을 모두 잡습니다. 마커 패밀리 `(document-plan-<scale>, human-confirmed)`는 새로 정의된 것으로, codebase-planner의 레거시 `(interfaces only, …)` system 마커를 상속하지 **않습니다**. 수동 호출 전용 — `/document-planner`. |
| [`document-implementer`](skills/document-implementer/) | `document-planner` → `document-implementer` 쌍의 다운스트림 절반. planner의 `(document-plan-<scale>, human-confirmed)` 핸드오프를 읽고(feature/system은 `document-plan.md` 최상단 frontmatter, micro/local은 채팅 핸드오프 블록 + `revise` 사이클에 대한 명시적 시간순 페어링 규칙), 자체 git worktree를 만든 뒤 **자율적으로** 소스 순서대로 생성 루프를 실행합니다 — text 도큐타입(api-spec / tech-spec / runbook)은 `TARGET_PATH`에 markdown을 직접 작성하며 각 섹션 헤딩 앞에 명시적 `<a id="<stub-id>"></a>` 앵커를 emit하고, structured(ppt)는 슬라이드별 콘텐츠를 state에 누적한 뒤 번들 `render_pptx.py`로 렌더(각 슬라이드 speaker notes 첫 줄에 stub-id provenance 주입)합니다. Phase 4 bounded auto-fix(text=3회, structured=0회 — pptx 실패는 LLM으로 잘 안 고쳐짐). Phase 5 self-verification 리포트는 **stub별 명시적 acceptance-criteria 체크리스트**를 포함하여 사람 리뷰어가 `confirm merge` 전에 항목별로 확인한 뒤 `(document-impl-<scale>, human-confirmed)` 마커로 머지합니다. planner 측 `parse_frontmatter.py`와의 mirror discipline(planner가 canonical). 수동 호출 전용 — `/document-implementer`. |
| [`collect-searches`](skills/collect-searches/) | 두 단계로 동작하는 Chrome 검색 기록 → Obsidian 파이프라인. 1단계는 결정론적 Python 컬렉터(`scripts/collect.py`)로 Chrome 로컬 SQLite 기록을 읽고, cursor와 lock을 소유하며, 새 Google 검색을 JSON 파일로 vault 인박스에 적재합니다. 2단계는 프롬프트 기반 워크플로로 각 검색을 Obsidian 카테고리 폴더로 분류하고, WebSearch로 1–3개 신뢰 가능한 출처를 보강해 검색별 Markdown 노트를 한 개씩 작성합니다. 주기 실행용으로 설계됨(예: `/loop 6h /collect-searches`). 부수효과 있음(노트 작성, 성공 시 인박스 파일 삭제). 수동 호출 전용 — `/collect-searches`. |
| [`live-notes`](skills/live-notes/) | 회의·학습·자유 메모 캡처용 keep-on 노트 도우미. `/live-notes` 호출 즉시 캡처 모드에 진입하며, 이후 사용자의 모든 메시지는 종료 시그널(`finish` / `done` / `종료` / `끝` / `마치기` — 한 줄 단독 입력) 전까지 **verbatim**으로 버퍼에 누적됩니다. 종료 시 스킬이 버퍼를 정리해 **앞쪽 TL;DR + 뒤쪽 상세** 구조의 옵시디언 호환 markdown 파일로 합성하며, YAML frontmatter는 영문 키 + `source: live-notes` + ASCII 태그 슬러그로 통일됩니다. 필요 시 사용자가 불확실하다 표시한 사실이나 정의가 필요한 고유명사에 대해 **AI 판단으로** 가벼운 웹 리서치(`WebSearch` ≤ 3회 + `WebFetch` ≤ 3회, 총 ≤ 120초)를 수행하고 결과는 인용을 필수로 하는 References 섹션에만 추가합니다. 결과물은 `{프로젝트 루트}/{루트 디렉토리명}-notes/{카테고리}/{YYYY-MM-DD}-{HHmm}-{title-slug}.md` 경로에 저장되며, AI는 콘텐츠 휴리스틱으로 카테고리(`meetings/`, `study/`, `projects/<slug>/`, `tech/<topic>/`, `research/<topic>/`, `journal/`, `inbox/`)를 제안하고 `revise category <slug>`로 덮어쓸 수 있습니다. 캡처 중 메타 명령: `section <name>` / `category <slug>` / `status` / `undo` / `quiet` / `no research` / `language <ko\|en>` / `cancel` / `cancel confirm` (한국어 별칭 — `상태` / `섹션` / `카테고리` / `되돌리기` / `조용` / `리서치 안함` / `언어` / `취소` / `취소 확정`). `.live-notes-drafts/` 의 버퍼 드래프트는 청크별 임시 파일 + 매 턴 시작 시 orphan-recovery 스윕으로 mid-write 크래시에도 캡처된 청크가 손실되지 않도록 보호하며, 다음 호출에서 stale 드래프트 발견 시 `resume` / `recover` / `discard` 프롬프트를 띄웁니다. 한국어 기본·영어 폴백(`references/language-selection.md` 규칙). 사용자가 입력한 본문은 **절대 번역되지 않으며**, 정리하는 voice(TL;DR, 섹션 도입부, 리서치 요약)만 `LANGUAGE`를 따릅니다. 수동 호출 전용 — `/live-notes`. |

#### 에이전트

_(예정 — 아직 제공되는 항목 없음)_

#### MCP 서버

_(예정 — 아직 제공되는 항목 없음)_

#### 플레이북

_(예정 — 아직 제공되는 항목 없음)_

### 저장소 구조

```
ai-driven-items/
├── skills/             Claude Code 스킬 (절차적 워크플로 + 번들 리소스)
│   ├── project-scaffolder/
│   ├── intent-aligner/
│   ├── seed-gatherer/
│   ├── plan-establisher/
│   ├── codebase-planner/
│   ├── codebase-implementer/
│   ├── document-planner/
│   ├── document-implementer/
│   ├── collect-searches/
│   └── live-notes/
├── agents/             (예정) Claude Code 커스텀 서브에이전트
├── mcp-servers/        (예정) Model Context Protocol 서버
├── playbooks/          (예정) 재사용 가능한 AI 친화적 구현 가이드
└── README.md
```

**스킬 산출물이 저장되는 위치.** 부작용(side-effect)이 있는 스킬은 산출물을
프로젝트 루트에 흩뿌리지 않습니다 — 모두 커밋되는 단일 `ai-artifacts/`
디렉터리 아래에 기록하므로(최초 실행 시 생성), 한 프로젝트에서 여러 스킬을
여러 번 실행해도 서로 충돌하지 않습니다:

```
ai-artifacts/
├── intents/   intent.<slug>.{md,html}             # intent-aligner / seed-gatherer
├── seeds/     seed.<slug>.<resource>.{md,html}    # seed-gatherer
├── plans/     plan.<slug>.v<N>.{md,html}          # plan-establisher (버전 관리)
└── runs/
    ├── code/<slug>-<planner-id>/                  # codebase-planner → codebase-implementer
    │     plan.md  plan.mmd | architecture.{html,mmd}   report.<impl-id>.md
    └── doc/<slug>-<docplanner-id>/                # document-planner → document-implementer
          document-plan.md  document-structure.{mmd,html}   report.<impl-id>.md
```

지속(durable) 산출물(intents/seeds/plans)은 slug·버전으로 이름이 붙고, 실행별
planner→implementer 핸드오프는 run-id 기반 디렉터리 안에서 고정 파일명을
유지하며, 그 경로는 머지 커밋의 `AI-Artifacts-Run-Dir:` git trailer 로
다운스트림에 전달됩니다. `ai-artifacts/` 예외: `document-implementer` 는 완성
문서를 사용자가 지정한 `TARGET_PATH` 에 기록하고, `collect-searches` 와
`live-notes` 는 각자의 노트 대상에 기록합니다.

### 설치

아래 설치 방법은 `project-scaffolder` 를 예시로 사용합니다. 위 인덱스의 다른 유틸리티를 설치하려면 **`<name>` 부분을 해당 디렉터리 이름으로 치환**하세요(예: `codebase-planner`).

#### Claude Code (네이티브)

저장소 루트에서 실행하세요:

```bash
# 전역 설치 — 모든 Claude Code 세션에서 사용 가능
mkdir -p ~/.claude/skills
ln -s "$(pwd)/skills/project-scaffolder" ~/.claude/skills/project-scaffolder

# 또는 프로젝트별 설치 — 특정 프로젝트에서만
mkdir -p /path/to/your-project/.claude/skills
ln -s "$(pwd)/skills/project-scaffolder" /path/to/your-project/.claude/skills/project-scaffolder
```

Windows 참고: `ln -s` 는 Developer Mode 또는 관리자 권한이 필요합니다. 대신 `mklink /J` (cmd) 또는 `New-Item -ItemType SymbolicLink` (PowerShell) 를 사용하거나 WSL을 사용하세요.

`/project-scaffolder` 로 실행합니다(다른 유틸리티는 `/<name>`). `disable-model-invocation: true` 가 설정된 스킬은 명시적으로 호출할 때만 동작합니다.

### 다른 AI 코딩 도구에서 사용

SKILL.md 본문은 워크플로를 기술한 일반 Markdown 문서입니다. 커스텀 지침을 받을 수 있는 AI 도구라면 어디서든 사용할 수 있습니다. 도구마다 다른 것은 **파일을 어디에 두느냐**와 **도구가 어떻게 로드하느냐** 뿐입니다. `skills/<name>/scripts/` 의 번들 스크립트는 휴대성 있는 코드라 그대로 동작합니다.

이식 시 두 가지 Claude 전용 요소를 조정해야 합니다:

- **Frontmatter**: `name`, `description`, `disable-model-invocation` 은 Claude Code 필드입니다. 다른 도구는 무시하거나 다른 스키마를 사용합니다 (각 도구별 노트 참조).
- **`${CLAUDE_SKILL_DIR}`**: Claude가 로드 시점에 해석하는 변수입니다. 다른 도구에서는 실제 스킬 디렉터리의 절대 경로로 치환하세요.

#### Codex CLI

Codex CLI는 거의 동일한 스킬 규약을 따릅니다. 저장소 루트에서 실행하세요:

```bash
mkdir -p ~/.codex/skills
ln -s "$(pwd)/skills/project-scaffolder" ~/.codex/skills/project-scaffolder
```

Codex 안에서 `/project-scaffolder` 로 실행합니다. Frontmatter는 대체로 호환되며, Codex가 알 수 없는 필드를 거부한다면 `disable-model-invocation` 를 제거하고 본문에 "수동 호출 전용" 임을 명시하세요.

#### Gemini CLI

Gemini CLI에는 스킬 시스템이 없지만 `GEMINI.md` 를 컨텍스트로 로드합니다. 두 가지 도입 패턴이 있습니다:

```bash
# 옵션 A — 커스텀 커맨드로 연결 (반복 사용에 권장)
mkdir -p ~/.gemini/commands
cat > ~/.gemini/commands/project-scaffolder.toml <<'EOF'
description = "격리된 git worktree 안에서 새 프로젝트의 공통(비도메인) 베이스라인을 부트스트랩합니다."
prompt = """
다음 워크플로를 따르세요: /absolute/path/to/skills/project-scaffolder/SKILL.md
참조 문서는 같은 디렉터리의 references/ 아래에 있습니다.
"""
EOF

# 옵션 B — SKILL.md 본문을 프로젝트의 GEMINI.md 에 자동 변환하여 작성
# (YAML frontmatter를 자동 제거하고, 본문의 --- 구분자는 그대로 보존)
awk 'fm < 2 { if (/^---$/) fm++; next } { print }' \
  skills/project-scaffolder/SKILL.md > ./GEMINI.md
```

옵션 A는 Gemini 내부에서 `/project-scaffolder` 로 호출합니다. 옵션 B는 `GEMINI.md` 가 있으면 자동으로 컨텍스트에 포함됩니다.

#### GitHub Copilot (IDE의 Copilot Chat 또는 `gh copilot`)

Copilot에는 스킬 시스템이 없습니다. 가장 가까운 대응은 프로젝트 수준 지침 파일입니다.

```bash
# 프로젝트 범위 — Copilot Chat에 워크플로를 따르도록 지시
mkdir -p .github
cat > .github/copilot-instructions.md <<'EOF'
사용자가 프로젝트 스캐폴딩을 요청하면 다음 워크플로를 따르세요:
/absolute/path/to/skills/project-scaffolder/SKILL.md
모든 단계 게이트를 준수하세요(스택 확정 전 파일 변경 금지,
사용자가 `confirm merge` 라고 입력하기 전엔 머지 금지). 참조 문서는
같은 디렉터리의 references/ 아래에 있습니다.
EOF
```

`gh copilot` CLI 관련 참고: 이 CLI는 단일 셸 명령 제안(`gh copilot suggest`)과 명령 설명(`gh copilot explain`) 용도이지, 다단계 인터랙티브 워크플로용이 아닙니다. 절차적 워크플로를 `gh copilot suggest` 에 파이프로 넘기면 한 줄짜리 명령 제안만 돌려주며, 문서화된 Phase-게이트 흐름은 실행되지 않습니다. 워크플로 스타일로 쓰려면 위의 `.github/copilot-instructions.md` 경로를 사용하고, 실제 작업은 IDE 안의 Copilot Chat에서 진행하세요.

#### Cursor AI

Cursor는 `.cursor/rules/*.mdc` 파일을 사용하며, 자체 frontmatter 포맷을 가집니다.

```bash
# 프로젝트 범위 — SKILL.md frontmatter를 MDC frontmatter로 변환
mkdir -p .cursor/rules
cat > .cursor/rules/project-scaffolder.mdc <<'EOF'
---
description: 격리된 git worktree 안에서 새 프로젝트의 공통(비도메인) 베이스라인을 부트스트랩합니다.
globs: []
alwaysApply: false
---
EOF
# SKILL.md 본문(YAML frontmatter 이후) 을 룰 파일에 이어붙입니다.
# sed가 아닌 awk를 사용합니다: SKILL.md 본문에도 --- 수평선 구분자가
# 여러 번 등장하므로, 단순한 sed 범위 패턴은 Phase 섹션을 누락시킵니다.
awk 'fm < 2 { if (/^---$/) fm++; next } { print }' \
  skills/project-scaffolder/SKILL.md >> .cursor/rules/project-scaffolder.mdc
```

Cursor 안에서 작업을 시작할 때 명시적으로 룰을 첨부하세요(모든 대화에서 자동 적용을 원하면 `alwaysApply: true` 로 설정).

### 스킬 검증

각 Claude Code 스킬은 공식 검증 도구를 통과해야 합니다:

```bash
python3 ~/.claude/skills/skill-creator/scripts/quick_validate.py skills/<name>
python3 ~/.claude/skills/skill-creator/scripts/package_skill.py skills/<name> /tmp/out
```

검증 도구는 YAML frontmatter, `SKILL.md` 500줄 권장 한도, 디렉터리 레이아웃, `${CLAUDE_SKILL_DIR}/...` 참조 해결 가능 여부를 확인합니다.

### 기여 가이드

1. 각 유틸리티는 알맞은 최상위 카테고리(`skills/`, `agents/`, …) 아래에 자신의 서브디렉터리를 가집니다.
2. PR을 열기 전에 해당 카테고리의 검증 도구를 실행하세요.
3. 머신별 로컬 상태는 git에 올리지 마세요 — `.claude/settings.local.json` 은 이미 gitignore에 포함되어 있습니다. 새로운 누출 패턴을 발견하면 `.gitignore` 에 추가하세요.
4. 유틸리티가 비-Claude AI 도구에도 이식 가능하다면 README의 도구별 표에 노트를 추가해 주세요.
5. 새 유틸리티를 추가했다면 위의 **아이템 인덱스**에 행을 추가해 발견 가능하도록 하세요.

**AI 도구 지침 파일 (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`) 은 의도적으로 gitignore에 포함됩니다.** 이는 일반적인 "팀 전체가 컨텍스트를 공유하도록 `CLAUDE.md` 를 커밋한다" 패턴을 의도적으로 거스르는 결정입니다. 메인테이너마다 도구 스택과 지침 스타일이 달라, 각 기여자가 이 README를 바탕으로 자신만의 로컬 버전을 작성합니다. AI 도구가 `claude /init` (또는 동등한 명령) 으로 `CLAUDE.md` 를 생성해도 조용히 무시되는 것은 정상입니다. 이 README가 정식 기여자 문서이고, 나머지는 각자 맞춤 설정하시면 됩니다.

### 라이선스

[CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/)에 따라 퍼블릭 도메인에 헌정합니다. 법이 허용하는 범위 내에서 저작자는 이 저작물에 대한 모든 저작권 및 인접 권리를 포기합니다. 별도의 허가 없이 상업적 목적을 포함한 모든 용도로 복제, 수정, 배포, 사용할 수 있습니다. 전체 원문은 [`LICENSE`](LICENSE) 파일을 참조하세요.
