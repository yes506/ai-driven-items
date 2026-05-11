# ai-driven-items

A collection of AI-driven developer utilities for the [Claude Code](https://docs.claude.com/en/docs/claude-code) ecosystem — skills, agents, MCP servers, and related building blocks. Each utility is self-contained, validated against the official Claude Skills standard, and installable without bringing in the rest of the repo.

## Repository layout

```
ai-driven-items/
├── skills/             Claude Code skills (procedural workflows + bundled resources)
│   └── project-scaffolder/
├── agents/             (planned) Custom Claude Code subagents
├── mcp-servers/        (planned) Model Context Protocol servers
├── playbooks/          (planned) Reusable, AI-consumable implementation guides
└── README.md
```

Top-level directories represent *categories* of utilities. New categories
are added when there's a real utility to put in them, not preemptively.

## Available utilities

### Skills

| Skill | What it does |
|---|---|
| [`project-scaffolder`](skills/project-scaffolder/) | Language-agnostic project bootstrapping. Walks intent → 2-4 tech-stack options → scaffolded baseline (lint, test, logging, config, CI stub, health endpoint). Runs entirely inside an isolated git worktree and merges back to `dev` only after explicit user confirmation. Tier-1 stacks: Next.js, Spring Boot, FastAPI, Go, Node/Express. |

## Installing a skill

Pick the install mode that matches how you want the skill scoped.

### Global install (available in every Claude Code session)

```bash
# Symlink (recommended — updates with a git pull)
ln -s "$(pwd)/skills/project-scaffolder" ~/.claude/skills/project-scaffolder

# Or copy if you prefer a frozen snapshot
cp -r skills/project-scaffolder ~/.claude/skills/
```

### Project-local install (only in one project)

```bash
# From inside your target project:
mkdir -p .claude/skills
ln -s /path/to/ai-driven-items/skills/project-scaffolder .claude/skills/project-scaffolder
```

### Verifying

After installing, run `/skill-creator` and confirm the new skill is listed,
or invoke it directly (e.g. `/project-scaffolder` — note that
`disable-model-invocation: true` is set on side-effect skills, so they
only fire on explicit invocation).

## Validating a skill before contributing

Each skill is expected to pass the official Claude Code validators:

```bash
python3 ~/.claude/skills/skill-creator/scripts/quick_validate.py skills/<name>
python3 ~/.claude/skills/skill-creator/scripts/package_skill.py skills/<name> /tmp/out
```

The validator enforces the YAML frontmatter contract, the 500-line `SKILL.md`
soft cap, the directory layout, and `${CLAUDE_SKILL_DIR}/...` reference
resolution on disk.

## Contributing

1. Each utility lives in its own subdirectory under the appropriate
   top-level category (`skills/`, `agents/`, etc.).
2. Run the validator for the category before opening a PR.
3. Keep machine-local state out of git — `.claude/settings.local.json`
   is already gitignored; add new patterns to `.gitignore` if you find
   leakage.

## License

To be added.
