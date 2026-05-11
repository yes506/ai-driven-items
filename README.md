# ai-driven-items

**[English](#english)** · **[한국어](#한국어)**

---

## English

A collection of AI-driven developer utilities for the [Claude Code](https://docs.claude.com/en/docs/claude-code) ecosystem — skills, agents, MCP servers, and related building blocks. Each utility is self-contained, validated against the official Claude Skills standard, and **portable to other AI coding tools** (Codex CLI, Gemini CLI, GitHub Copilot, Cursor) with light adaptation.

### Repository layout

```
ai-driven-items/
├── skills/             Claude Code skills (procedural workflows + bundled resources)
│   └── project-scaffolder/
├── agents/             (planned) Custom Claude Code subagents
├── mcp-servers/        (planned) Model Context Protocol servers
├── playbooks/          (planned) Reusable, AI-consumable implementation guides
└── README.md
```

### Available utilities

| Skill | What it does |
|---|---|
| [`project-scaffolder`](skills/project-scaffolder/) | Language-agnostic project bootstrapping. Walks intent → 2-4 tech-stack options → scaffolded baseline (lint, test, logging, config, CI stub, health endpoint). Runs entirely inside an isolated git worktree and merges back to `dev` only after explicit user confirmation. Tier-1 stacks: Next.js, Spring Boot, FastAPI, Go, Node/Express. |

### Installing for Claude Code (native)

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

Invoke with `/project-scaffolder`. `disable-model-invocation: true` is set, so it only fires on explicit invocation.

### Using with other AI coding tools

The SKILL.md body is plain Markdown describing a workflow — any AI tool that can accept custom instructions can use it. What differs per tool is **where the file goes** and **how the tool loads it**. The bundled `scripts/inspect_repo_state.sh` is a portable bash script and works unchanged.

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

Note about the `gh copilot` CLI: it's scoped to single-command suggestions (`gh copilot suggest`) and command-explanation (`gh copilot explain`), not multi-step interactive workflows. Piping a procedural workflow into `gh copilot suggest` returns one shell-command suggestion, not the documented Phase-gated execution. For workflow-style use, stay with the `.github/copilot-instructions.md` route above and drive the scaffold via Copilot Chat in your IDE.

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

In Cursor, attach the rule explicitly when starting a scaffold task (or set `alwaysApply: true` if you want it on every chat).

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

**AI-tool instruction files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`) are intentionally gitignored.** This is a deliberate convention break from the typical "commit `CLAUDE.md` so the whole team shares context" pattern. Each contributor authors their own version locally based on this README, because tool stacks and instruction styles differ per maintainer. If your AI tool runs `claude /init` (or equivalent) and writes a `CLAUDE.md`, you'll see it silently ignored — that's expected. This README is the canonical contributor doc; the rest is yours to tailor.

### License

Released into the public domain via [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/). To the extent possible under law, the author(s) have waived all copyright and related or neighboring rights to this work. You may copy, modify, distribute, and use the work, even for commercial purposes, all without asking permission. See [`LICENSE`](LICENSE) for the full text.

---

## 한국어

[Claude Code](https://docs.claude.com/en/docs/claude-code) 생태계용 AI 기반 개발 유틸리티 모음 — 스킬, 에이전트, MCP 서버 등 빌딩 블록을 제공합니다. 각 유틸리티는 독립적이고, 공식 Claude Skills 표준을 통과하며, **약간의 수정만으로 다른 AI 코딩 도구**(Codex CLI, Gemini CLI, GitHub Copilot, Cursor)에서도 사용할 수 있습니다.

### 저장소 구조

```
ai-driven-items/
├── skills/             Claude Code 스킬 (절차적 워크플로 + 번들 리소스)
│   └── project-scaffolder/
├── agents/             (예정) Claude Code 커스텀 서브에이전트
├── mcp-servers/        (예정) Model Context Protocol 서버
├── playbooks/          (예정) 재사용 가능한 AI 친화적 구현 가이드
└── README.md
```

### 제공 유틸리티

| 스킬 | 설명 |
|---|---|
| [`project-scaffolder`](skills/project-scaffolder/) | 언어 무관 프로젝트 부트스트래퍼. 의도 파악 → 2-4개 스택 옵션 추천 → 베이스라인 스캐폴딩 (린트, 테스트, 로깅, 설정, CI 스텁, 헬스 엔드포인트) 흐름으로 진행합니다. 모든 작업은 격리된 git worktree 안에서만 일어나며, 사용자가 명시적으로 확인해야만 `dev` 브랜치로 머지됩니다. Tier-1 스택: Next.js, Spring Boot, FastAPI, Go, Node/Express. |

### Claude Code에서 설치 (네이티브)

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

`/project-scaffolder` 로 실행합니다. `disable-model-invocation: true` 가 설정되어 있어, 명시적으로 호출할 때만 동작합니다.

### 다른 AI 코딩 도구에서 사용

SKILL.md 본문은 워크플로를 기술한 일반 Markdown 문서입니다. 커스텀 지침을 받을 수 있는 AI 도구라면 어디서든 사용할 수 있습니다. 도구마다 다른 것은 **파일을 어디에 두느냐**와 **도구가 어떻게 로드하느냐** 뿐입니다. 번들 스크립트 `scripts/inspect_repo_state.sh` 는 휴대성 있는 bash 스크립트라 그대로 동작합니다.

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

`gh copilot` CLI 관련 참고: 이 CLI는 단일 셸 명령 제안(`gh copilot suggest`)과 명령 설명(`gh copilot explain`) 용도이지, 다단계 인터랙티브 워크플로용이 아닙니다. 절차적 워크플로를 `gh copilot suggest` 에 파이프로 넘기면 한 줄짜리 명령 제안만 돌려주며, 문서화된 Phase-게이트 흐름은 실행되지 않습니다. 워크플로 스타일로 쓰려면 위의 `.github/copilot-instructions.md` 경로를 사용하고, 실제 스캐폴딩은 IDE 안의 Copilot Chat에서 진행하세요.

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

Cursor 안에서 스캐폴딩 작업을 시작할 때 명시적으로 룰을 첨부하세요(모든 대화에서 자동 적용을 원하면 `alwaysApply: true` 로 설정).

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

**AI 도구 지침 파일 (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`) 은 의도적으로 gitignore에 포함됩니다.** 이는 일반적인 "팀 전체가 컨텍스트를 공유하도록 `CLAUDE.md` 를 커밋한다" 패턴을 의도적으로 거스르는 결정입니다. 메인테이너마다 도구 스택과 지침 스타일이 달라, 각 기여자가 이 README를 바탕으로 자신만의 로컬 버전을 작성합니다. AI 도구가 `claude /init` (또는 동등한 명령) 으로 `CLAUDE.md` 를 생성해도 조용히 무시되는 것은 정상입니다. 이 README가 정식 기여자 문서이고, 나머지는 각자 맞춤 설정하시면 됩니다.

### 라이선스

[CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/)에 따라 퍼블릭 도메인에 헌정합니다. 법이 허용하는 범위 내에서 저작자는 이 저작물에 대한 모든 저작권 및 인접 권리를 포기합니다. 별도의 허가 없이 상업적 목적을 포함한 모든 용도로 복제, 수정, 배포, 사용할 수 있습니다. 전체 원문은 [`LICENSE`](LICENSE) 파일을 참조하세요.
