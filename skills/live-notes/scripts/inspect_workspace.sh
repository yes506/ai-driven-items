#!/usr/bin/env bash
# inspect_workspace.sh — Phase 0 read-only workspace detector for live-notes.
#
# Resolves the project root (git toplevel when available, else cwd),
# the notes directory name, and surfaces a small JSON document the
# skill body parses. Side-effect free: never creates the notes dir,
# never writes state. Creation happens in Phase 3 on `confirm save`.
#
# Output schema (one JSON object on stdout):
#   {
#     "cwd":                "<absolute>",
#     "in_git_repo":        true|false,
#     "git_toplevel":       "<absolute>|null",
#     "root":               "<absolute project root>",
#     "root_basename":      "<basename>",
#     "notes_dir_name":     "<root_basename>-notes",
#     "notes_dir":          "<absolute notes dir path>",
#     "notes_dir_exists":   true|false,
#     "notes_dir_kind":     "absent" | "dir" | "file",
#     "gitignore_has_notes":true|false|null,
#     "session_id":         "YYYYMMDD-HHMMSS-<pid>",
#     "iso_local":          "YYYY-MM-DDTHH:MM:SS+HH:MM",
#     "date":               "YYYY-MM-DD",
#     "time":               "HH:MM"
#   }
#
# Exit codes:
#   0 — JSON emitted (even when `in_git_repo=false`)
#   2 — unrecoverable error (e.g. cwd disappeared between calls)

set -u

CWD="$(pwd -P 2>/dev/null)" || { echo "{\"error\":\"cwd unreadable\"}"; exit 2; }

GIT_TOPLEVEL=""
IN_GIT="false"
if git -C "${CWD}" rev-parse --show-toplevel >/dev/null 2>&1; then
  GIT_TOPLEVEL="$(git -C "${CWD}" rev-parse --show-toplevel)"
  IN_GIT="true"
fi

if [ "${IN_GIT}" = "true" ]; then
  ROOT="${GIT_TOPLEVEL}"
else
  ROOT="${CWD}"
fi

ROOT_BASENAME="$(basename "${ROOT}")"
NOTES_DIR_NAME="${ROOT_BASENAME}-notes"
NOTES_DIR="${ROOT}/${NOTES_DIR_NAME}"

NOTES_DIR_EXISTS="false"
NOTES_DIR_KIND="absent"
if [ -d "${NOTES_DIR}" ]; then
  # Resolves symlink-to-dir as well; that's fine — mkdir -p is a no-op.
  NOTES_DIR_EXISTS="true"
  NOTES_DIR_KIND="dir"
elif [ -e "${NOTES_DIR}" ]; then
  # Regular file / symlink-to-file / device occupying the path — refuse cleanly.
  NOTES_DIR_KIND="file"
elif [ -L "${NOTES_DIR}" ]; then
  # Dangling symlink — [ -e ] follows the link, so this fires only when
  # the link target is missing. mkdir -p would fail with ENOENT here.
  NOTES_DIR_KIND="file"
fi

GITIGNORE_HAS_NOTES="null"
if [ "${IN_GIT}" = "true" ] && [ -f "${ROOT}/.gitignore" ]; then
  if grep -qxF "${NOTES_DIR_NAME}/" "${ROOT}/.gitignore" 2>/dev/null \
     || grep -qxF "/${NOTES_DIR_NAME}/" "${ROOT}/.gitignore" 2>/dev/null \
     || grep -qxF "${NOTES_DIR_NAME}" "${ROOT}/.gitignore" 2>/dev/null; then
    GITIGNORE_HAS_NOTES="true"
  else
    GITIGNORE_HAS_NOTES="false"
  fi
elif [ "${IN_GIT}" = "true" ]; then
  GITIGNORE_HAS_NOTES="false"
fi

ISO_LOCAL="$(date +%Y-%m-%dT%H:%M:%S%z | sed -E 's/([+-][0-9]{2})([0-9]{2})$/\1:\2/')"
DATE="$(date +%Y-%m-%d)"
TIME="$(date +%H:%M)"
SESSION_ID="$(date +%Y%m%d-%H%M%S)-$$"

json_escape() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

cat <<EOF
{
  "cwd":                 "$(json_escape "${CWD}")",
  "in_git_repo":         ${IN_GIT},
  "git_toplevel":        $([ -n "${GIT_TOPLEVEL}" ] && printf '"%s"' "$(json_escape "${GIT_TOPLEVEL}")" || printf 'null'),
  "root":                "$(json_escape "${ROOT}")",
  "root_basename":       "$(json_escape "${ROOT_BASENAME}")",
  "notes_dir_name":      "$(json_escape "${NOTES_DIR_NAME}")",
  "notes_dir":           "$(json_escape "${NOTES_DIR}")",
  "notes_dir_exists":    ${NOTES_DIR_EXISTS},
  "notes_dir_kind":      "$(json_escape "${NOTES_DIR_KIND}")",
  "gitignore_has_notes": ${GITIGNORE_HAS_NOTES},
  "session_id":          "$(json_escape "${SESSION_ID}")",
  "iso_local":           "$(json_escape "${ISO_LOCAL}")",
  "date":                "$(json_escape "${DATE}")",
  "time":                "$(json_escape "${TIME}")"
}
EOF
