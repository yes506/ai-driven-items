#!/usr/bin/env bash
# publish_thought.sh — publish a document-planner thinking-checkpoint to
# canvas-terminal shared collab-memory so peer agents can read along and feed back.
#
# Usage:
#   publish_thought.sh <docplanner_id> <phase> <topic> [< body-on-stdin]
#
# Silent no-op (exit 0) if no collab-memory dir is found — keeps the skill
# usable when invoked outside canvas-terminal.

set -euo pipefail

if [ "$#" -lt 3 ]; then
  printf 'usage: %s <docplanner_id> <phase> <topic> [< body]\n' "$0" >&2
  exit 2
fi

DOCPLANNER_ID="$1"
PHASE="$2"
TOPIC="$3"

SESSION_DIR=""
if [ -n "${CANVAS_TERMINAL_COLLAB_DIR+set}" ]; then
  if [ -d "${CANVAS_TERMINAL_COLLAB_DIR}" ]; then
    SESSION_DIR="${CANVAS_TERMINAL_COLLAB_DIR}"
  else
    exit 0
  fi
elif [ -n "${HOME:-}" ]; then
  ROOT="${HOME}/.cache/canvas-terminal/collab-memory"
  if [ -d "${ROOT}" ]; then
    if command -v gstat >/dev/null 2>&1; then
      STAT_CMD="gstat -c %Y"
    elif stat -c %Y / >/dev/null 2>&1; then
      STAT_CMD="stat -c %Y"
    else
      STAT_CMD="stat -f %m"
    fi
    SESSION_DIR="$(
      for d in "${ROOT}"/session-*/; do
        [ -d "${d}" ] || continue
        printf '%s %s\n' "$(${STAT_CMD} "${d}")" "${d%/}"
      done | sort -n | tail -n 1 | awk '{print $2}'
    )"
  fi
fi

if [ -z "${SESSION_DIR}" ] || [ ! -d "${SESSION_DIR}" ]; then
  exit 0
fi

sanitize() {
  printf '%s' "$1" | tr 'A-Z' 'a-z' | tr -cs 'a-z0-9._-' '-' \
    | sed -e 's/^-*//' -e 's/-*$//' -e 's/-\{2,\}/-/g' | cut -c1-60
}

ID_SAFE="$(sanitize "${DOCPLANNER_ID}")"
PHASE_SAFE="$(sanitize "${PHASE}")"
TOPIC_SAFE="$(sanitize "${TOPIC}")"

if [ -z "${ID_SAFE}" ] || [ -z "${PHASE_SAFE}" ] || [ -z "${TOPIC_SAFE}" ]; then
  printf 'publish_thought: empty id/phase/topic after sanitize — refusing\n' >&2
  exit 2
fi

OUT="${SESSION_DIR}/docplanner-${ID_SAFE}-phase-${PHASE_SAFE}-${TOPIC_SAFE}.md"
TMP="${OUT}.tmp.$$"

NOW_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

{
  printf -- '---\n'
  printf -- 'docplanner_id: %s\n' "${ID_SAFE}"
  printf -- 'phase: %s\n' "${PHASE_SAFE}"
  printf -- 'topic: %s\n' "${TOPIC_SAFE}"
  printf -- 'ts: %s\n' "${NOW_ISO}"
  printf -- 'author: document-planner\n'
  printf -- '---\n\n'
  printf -- '# Phase %s — %s\n\n' "${PHASE_SAFE}" "${TOPIC_SAFE}"
  if [ -t 0 ]; then
    printf -- '_(no body piped on stdin — placeholder)_\n'
  else
    cat
  fi
  printf -- '\n\n---\n'
  printf -- '_Peer feedback welcome. Drop a markdown file alongside this one named_\n'
  printf -- '`docplanner-%s-feedback-<your-handle>-<topic>.md`_._\n' "${ID_SAFE}"
} > "${TMP}"

mv -f "${TMP}" "${OUT}"
printf '%s\n' "${OUT}"
