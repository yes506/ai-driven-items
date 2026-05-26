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
| [`intent-aligner`](skills/intent-aligner/) | Upstream of the planning chain. Extracts what's actually in the user's head before any planning starts: an interactive elicitation dialog (Socratic loops + 5 Whys + example/counter-example disambiguation) auto-detects whether the user brings a **feature/product idea** or a **problem/pain**, then iterates until intent converges. Emits a dual-format artifact — `intent.<slug>.md` (structured AI-parseable seed) and `intent.<slug>.html` (static, self-contained, human-verifiable). Stack-, planner-, and lane-agnostic: the file's 6 rubric-aligned fields (Goal, In-scope features, Out-of-scope, Constraints, Success criteria, Open questions) are directly readable by `codebase-planner`. A future `plan-establisher` skill will sit between `intent-aligner` and `codebase-planner` to add planner-specific rubric folds; until that skill ships, `intent.<slug>.md` can be handed directly to `/codebase-planner`. Runs inside a git worktree and merges to `dev` only after `confirm merge`; marker `(intent, human-confirmed)` makes the chain visible in `git log`. Manual invocation only — `/intent-aligner`. |
| [`codebase-planner`](skills/codebase-planner/) | Decides how much planning a code change needs, then runs only the phases that lane requires. Four scale lanes: **micro** (one-function, 3–7 bullet chat plan, no worktree), **local** (≤3 files / 1 module, chat plan), **feature** (worktree + `plan.md` + Mermaid DAG, optional skeletons), **system** (full interface-skeleton workflow inherited verbatim from the prior codebase-architect skill — worktree + 9-field docstrings + Mermaid DAG + HTML report + human-confirmation merge gate). Lane is picked by a scored tuple (scope, risk, ambiguity) before any mutation; ambiguous requests block-and-ask rather than silently over-engineer. Downstream implementer agents read a scale-tagged marker family (see `codebase-implementer` below). Manual invocation only — `/codebase-planner`. |
| [`codebase-implementer`](skills/codebase-implementer/) | Downstream half of the planner→implementer chain. Reads the planner's scale-tagged, human-confirmed marker from chat (micro/local) or merge commit (feature/system), creates its own git worktree, then runs an **autonomous** implementation loop across all phases (no per-step prompts; only pause is a genuine blocker like a missing collaborator). Generates method bodies from 9-field docstrings (system) or plan steps (feature) or bullets (micro/local), runs the project's compile+test command with bounded auto-fix (default 3 attempts, oscillation-detected), emits an `implementation-report.md` for review, and merges to the base branch (default `dev`) only after the user types `confirm merge`. Language-agnostic. Body-generation only — refuses to re-architect, refactor, or rename committed signatures. Manual invocation only — `/codebase-implementer`. |
| [`collect-searches`](skills/collect-searches/) | Two-stage Chrome-search-history → Obsidian pipeline. Stage 1 is a deterministic Python collector (`scripts/collect.py`) that reads Chrome's local SQLite history, owns the cursor and lock, and stages new Google searches as JSON in a vault inbox. Stage 2 is a prompt-orchestrated workflow that classifies each query into an Obsidian category folder, enriches it with 1–3 WebSearch sources, and writes one Markdown note per search. Designed for periodic runs (e.g. `/loop 6h /collect-searches`). Has side effects (writes notes, deletes inbox files on success); manual invocation only — `/collect-searches`. |

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
│   ├── codebase-planner/
│   ├── codebase-implementer/
│   └── collect-searches/
├── agents/             (planned) Custom Claude Code subagents
├── mcp-servers/        (planned) Model Context Protocol servers
├── playbooks/          (planned) Reusable, AI-consumable implementation guides
└── README.md
```

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
| [`intent-aligner`](skills/intent-aligner/) | 계획 체인의 **상류** 단계 — 계획에 들어가기 전에 사용자의 머릿속에 있는 의도를 끄집어내 명확히 합니다. 대화형 elicitation(소크라테스식 질문 루프 + 5 Whys + 예시/반례 분별)을 통해 사용자가 **만들고 싶은 기능/제품**을 가져왔는지 **겪고 있는 문제/불편함**을 가져왔는지 자동 판별하고, 의도가 수렴할 때까지 반복합니다. 결과물은 두 형식으로 산출됩니다 — `intent.<slug>.md`(구조화된 AI 파싱용 시드) 및 `intent.<slug>.html`(외부 의존성 없는 단일 파일 사람 검증용 문서). 스택·플래너·레인 무관(stack-/planner-/lane-agnostic): 시드의 6개 루브릭 필드(Goal, In-scope features, Out-of-scope, Constraints, Success criteria, Open questions)는 `codebase-planner`가 그대로 읽을 수 있습니다. 향후 `intent-aligner`와 `codebase-planner` 사이에 `plan-establisher` 스킬이 추가되어 플래너 전용 fold(루브릭 정합 변환)를 담당할 예정이며, 그 전까지는 `intent.<slug>.md`를 `/codebase-planner`에 바로 전달할 수 있습니다. 모든 mutation은 git worktree 안에서만 일어나며, `confirm merge` 후에만 `dev`로 머지됩니다. 머지 커밋의 `(intent, human-confirmed)` 마커로 `git log`에서 체인이 가시화됩니다. 수동 호출 전용 — `/intent-aligner`. |
| [`codebase-planner`](skills/codebase-planner/) | 코드 변경에 필요한 **계획 규모**를 먼저 판정한 뒤, 해당 레인에 필요한 단계만 실행합니다. 네 단계 스케일: **micro**(단일 함수 수준, 3–7 항목 채팅 플랜, worktree 없음), **local**(≤3 파일·단일 모듈, 채팅 플랜), **feature**(worktree + `plan.md` + Mermaid DAG, 스켈레톤 선택적), **system**(이전 codebase-architect 스킬의 전체 인터페이스-스켈레톤 워크플로 — worktree + 9-필드 docstring + Mermaid DAG + HTML 리포트 + 사람 확인 머지 게이트). 레인은 mutation 직전에 (scope, risk, ambiguity) 점수 튜플로 결정되며, 요청이 모호하면 silently 과설계하지 않고 명확화 질문으로 차단합니다. 다운스트림 구현 에이전트는 scale-tagged marker family를 읽습니다(아래 `codebase-implementer` 참조). 수동 호출 전용 — `/codebase-planner`. |
| [`codebase-implementer`](skills/codebase-implementer/) | planner→implementer 체인의 다운스트림 절반. 사용자가 확인한 planner의 scale-tagged marker를 chat(micro/local) 또는 머지 커밋(feature/system)에서 읽어, 자체 git worktree를 만든 뒤 모든 phase를 **자율적으로** 실행합니다(per-step 확인 없음, 진짜 blocker(예: 미정의 collaborator)만 정지 신호). 구현 본문을 9-필드 docstring(system) 또는 plan 단계(feature) 또는 bullet(micro/local)에서 생성하고, 프로젝트의 compile+test 명령을 bounded auto-fix(기본 3회, oscillation 감지)로 돌린 뒤, 리뷰용 `implementation-report.md`를 생성하고, 사용자가 `confirm merge`라고 입력해야만 base branch(기본 `dev`)로 머지합니다. 언어 무관. 본문 생성 전용 — re-architecting, refactoring, 커밋된 시그니처 변경은 거부합니다. 수동 호출 전용 — `/codebase-implementer`. |
| [`collect-searches`](skills/collect-searches/) | 두 단계로 동작하는 Chrome 검색 기록 → Obsidian 파이프라인. 1단계는 결정론적 Python 컬렉터(`scripts/collect.py`)로 Chrome 로컬 SQLite 기록을 읽고, cursor와 lock을 소유하며, 새 Google 검색을 JSON 파일로 vault 인박스에 적재합니다. 2단계는 프롬프트 기반 워크플로로 각 검색을 Obsidian 카테고리 폴더로 분류하고, WebSearch로 1–3개 신뢰 가능한 출처를 보강해 검색별 Markdown 노트를 한 개씩 작성합니다. 주기 실행용으로 설계됨(예: `/loop 6h /collect-searches`). 부수효과 있음(노트 작성, 성공 시 인박스 파일 삭제). 수동 호출 전용 — `/collect-searches`. |

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
│   ├── codebase-planner/
│   ├── codebase-implementer/
│   └── collect-searches/
├── agents/             (예정) Claude Code 커스텀 서브에이전트
├── mcp-servers/        (예정) Model Context Protocol 서버
├── playbooks/          (예정) 재사용 가능한 AI 친화적 구현 가이드
└── README.md
```

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
