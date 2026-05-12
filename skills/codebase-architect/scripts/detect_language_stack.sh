#!/usr/bin/env bash
# detect_language_stack.sh — detect project language(s) from root build files.
# Emits a single JSON line on stdout:
#   {"language":"...","validation_command":"...","detected_build_files":["..."],"project_root":"..."}
# `language` is the *primary* recommendation. When multiple build files are present
# (monorepo / mixed stack), `detected_build_files` lists every match so the caller
# (SKILL.md Phase 0) can ask the user to pick. Read-only — never modifies the FS.

set -euo pipefail

PROJECT_ROOT="${1:-$(pwd)}"

# Reject obviously hostile paths up front (path traversal contains ../).
case "${PROJECT_ROOT}" in
  *..*) printf '{"language":"unknown","validation_command":"","detected_build_files":[],"project_root":null,"error":"path_contains_dotdot"}\n'; exit 0 ;;
esac

cd "${PROJECT_ROOT}" 2>/dev/null || {
  # Use python to safely encode the path into JSON.
  python3 -c 'import json,sys; r=sys.argv[1]; print(json.dumps({"language":"unknown","validation_command":"","detected_build_files":[],"project_root":None,"error":"cd_failed","attempted_path":r}))' "${PROJECT_ROOT}"
  exit 0
}

# Detect every build file present, in priority order (first match → primary).
DETECTED=()
LANG=""
CMD=""
for entry in \
  "pom.xml:java:mvn compile" \
  "build.gradle:java:./gradlew compileJava" \
  "build.gradle.kts:java:./gradlew compileJava" \
  "pyproject.toml:python:mypy --strict <package>" \
  "requirements.txt:python:mypy --strict <package>" \
  "Pipfile:python:mypy --strict <package>" \
  "tsconfig.json:typescript:tsc --noEmit" \
  "package.json:javascript:" \
  "go.mod:go:go build ./..." \
  "Cargo.toml:rust:cargo check"
do
  file="${entry%%:*}"
  rest="${entry#*:}"
  lang_for_file="${rest%%:*}"
  cmd_for_file="${rest#*:}"
  if [ -e "${file}" ]; then
    DETECTED+=("${file}")
    if [ -z "${LANG}" ]; then
      LANG="${lang_for_file}"
      CMD="${cmd_for_file}"
    fi
  fi
done

if [ -z "${LANG}" ]; then
  LANG="unknown"
  CMD=""
fi

# If both `package.json` AND `tsconfig.json` are present, the priority list above
# already promoted `tsconfig.json` (so primary = typescript). If only `package.json`
# is present, primary stays `javascript` (no first-class skeleton — caller handles).

# Emit JSON via Python so paths/build-file names are escaped correctly.
python3 -c '
import json, sys
out = {
  "language": sys.argv[1],
  "validation_command": sys.argv[2],
  "detected_build_files": sys.argv[3].split("\x1f") if sys.argv[3] else [],
  "project_root": sys.argv[4],
}
print(json.dumps(out))
' "${LANG}" "${CMD}" "$(IFS=$'\x1f'; echo "${DETECTED[*]:-}")" "${PROJECT_ROOT}"
