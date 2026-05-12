#!/usr/bin/env bash
# detect_language_stack.sh — detect project language from root build files.
# Emits a single JSON line on stdout: {"language":"...","validation_command":"...","project_root":"..."}
# Read-only — never modifies the filesystem.

set -euo pipefail

PROJECT_ROOT="${1:-$(pwd)}"
cd "${PROJECT_ROOT}"

LANG=""
CMD=""

if [ -f "pom.xml" ]; then
  LANG="java"
  CMD="mvn compile"
elif [ -f "build.gradle" ] || [ -f "build.gradle.kts" ]; then
  LANG="java"
  CMD="./gradlew compileJava"
elif [ -f "pyproject.toml" ] || [ -f "requirements.txt" ] || [ -f "Pipfile" ]; then
  LANG="python"
  # Caller substitutes the actual package path before running.
  CMD="mypy --strict ."
elif [ -f "tsconfig.json" ]; then
  LANG="typescript"
  CMD="tsc --noEmit"
elif [ -f "package.json" ]; then
  LANG="javascript"
  CMD=""
elif [ -f "go.mod" ]; then
  LANG="go"
  CMD="go build ./..."
elif [ -f "Cargo.toml" ]; then
  LANG="rust"
  CMD="cargo check"
else
  LANG="unknown"
  CMD=""
fi

# JSON-escape any double quotes that might appear in PROJECT_ROOT.
PR_ESC="${PROJECT_ROOT//\"/\\\"}"
printf '{"language":"%s","validation_command":"%s","project_root":"%s"}\n' \
  "${LANG}" "${CMD}" "${PR_ESC}"
