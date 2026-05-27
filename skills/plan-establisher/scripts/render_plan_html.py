#!/usr/bin/env python3
"""Render a self-contained HTML verification doc for one plan.

Reads `.plan-state.json` (path arg) and the bundled HTML template
(assets/plan-html-template.html), populates placeholders, emits HTML
to stdout. The HTML is fully self-contained — no CDN, no external JS.
Every user-supplied value is HTML-escaped before substitution; the
template uses single-pass placeholder substitution to defuse the
chained-replace re-substitution class.

Read-only: writes only to stdout. Caller redirects with
`> plan.<intent-slug>.v<N>.html` per SKILL.md Phase 5.

Usage:
    render_plan_html.py <path-to-.plan-state.json>
"""

import html
import json
import re
import sys
from pathlib import Path


TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "plan-html-template.html"


# Localized chrome strings. Language is read from state["language"] —
# "Korean" / "ko" / "kr" → ko, anything else → en. Body content
# (refined goal, resolutions, lane reasoning prose) already follows
# LANGUAGE; this localizes the section labels and the lang attr.
STRINGS = {
    "en": {
        "html_lang":          "en",
        "title_prefix":       "Plan",
        "lane_micro":         "Micro",
        "lane_local":         "Local",
        "lane_feature":       "Feature",
        "lane_system":        "System",
        "lane_unknown":       "?",
        "hero_label":         "Goal",
        "in_scope":           "In scope",
        "out_of_scope":       "Not in scope",
        "constraints":        "Constraints",
        "success_criteria":   "Success criteria",
        "lane_reasoning":     "Why this scale lane",
        "evidence_inventory": "Evidence inventory",
        "evidence_field":     "Plan field",
        "evidence_seeds":     "Contributing seeds",
        "evidence_intent_only_row": "(intent-only)",
        "evidence_all_intent_only": "(intent-only plan — no seeds informed any rubric field)",
        "resolved_ambiguities": "Resolved ambiguities",
        "open_questions":     "Remaining open questions",
        "intent_label":       "Intent slug:",
        "version_label":      "Plan version:",
        "run_id_label":       "Plan run ID:",
        "confirmed_label":    "Confirmed at:",
        "format_label":       "Format version:",
        "not_recorded":       "(not recorded)",
        "unspecified":        "(unspecified)",
        "none_recorded":      "(none recorded)",
        "no_unresolved":      "(none — all ambiguities resolved)",
        "no_relevance":       "(no relevance recorded)",
    },
    "ko": {
        "html_lang":          "ko",
        "title_prefix":       "플랜",
        "lane_micro":         "마이크로",
        "lane_local":         "로컬",
        "lane_feature":       "피처",
        "lane_system":        "시스템",
        "lane_unknown":       "?",
        "hero_label":         "목표",
        "in_scope":           "범위 안",
        "out_of_scope":       "범위 밖",
        "constraints":        "제약 사항",
        "success_criteria":   "성공의 기준",
        "lane_reasoning":     "이 스케일 레인을 선택한 이유",
        "evidence_inventory": "근거 인벤토리",
        "evidence_field":     "플랜 필드",
        "evidence_seeds":     "기여 시드",
        "evidence_intent_only_row": "(의도만)",
        "evidence_all_intent_only": "(의도-단독 플랜 — 어떤 시드도 루브릭 필드에 기여하지 않음)",
        "resolved_ambiguities": "해결된 모호성",
        "open_questions":     "남은 미해결 질문",
        "intent_label":       "의도 슬러그:",
        "version_label":      "플랜 버전:",
        "run_id_label":       "플랜 런 ID:",
        "confirmed_label":    "확정 시각:",
        "format_label":       "포맷 버전:",
        "not_recorded":       "(기록 없음)",
        "unspecified":        "(미지정)",
        "none_recorded":      "(기록 없음)",
        "no_unresolved":      "(없음 — 모든 모호성이 해결됨)",
        "no_relevance":       "(관련성 설명 없음)",
    },
}


def _strings_for(language) -> dict:
    """Return the string table for the given LANGUAGE.

    Fallback chain matches SKILL.md Phase L contract: None / empty / "ko"
    / "kr" / "korean" → Korean (default); anything else → English.
    """
    raw = str(language or "").strip().lower()
    if raw == "" or raw in ("korean", "ko", "kr"):
        return STRINGS["ko"]
    return STRINGS["en"]


def _esc(value) -> str:
    """html.escape that tolerates non-string input (None, ints, etc.)."""
    if value is None:
        return ""
    return html.escape(str(value))


def _render_template(template: str, replacements: dict) -> str:
    """Replace each {{NAME}} placeholder exactly ONCE in a single pass."""
    pattern = re.compile(r"\{\{(" + "|".join(re.escape(k) for k in replacements) + r")\}\}")
    return pattern.sub(lambda m: replacements[m.group(1)], template)


def _lane_label(lane: str, t: dict) -> str:
    return t.get(f"lane_{(lane or '').lower()}", t["lane_unknown"])


# ── block renderers ──────────────────────────────────────────────────────


def _hero_block(intent: dict, t: dict) -> str:
    goal = intent.get("goal")
    if not goal:
        body = f'<p class="goal placeholder">{_esc(t["unspecified"])}</p>'
    else:
        body = f'<p class="goal">{_esc(goal)}</p>'
    return (
        '<section class="hero">'
        f'<div class="label">{_esc(t["hero_label"])}</div>'
        f'{body}'
        '</section>'
    )


def _scope_block(intent: dict, t: dict) -> str:
    in_scope = [str(x).strip() for x in (intent.get("in_scope") or []) if str(x).strip()]
    out_scope = [str(x).strip() for x in (intent.get("out_of_scope") or []) if str(x).strip()]
    if not (in_scope or out_scope):
        return ""

    def _li(item):
        return f"<li>{_esc(item)}</li>"

    in_html = (
        f'<ul>{"".join(_li(x) for x in in_scope)}</ul>'
        if in_scope else f'<p class="placeholder">{_esc(t["none_recorded"])}</p>'
    )
    out_html = (
        f'<ul>{"".join(_li(x) for x in out_scope)}</ul>'
        if out_scope else f'<p class="placeholder">{_esc(t["none_recorded"])}</p>'
    )
    return (
        '<section class="scope-grid">'
        f'<div class="scope-col in"><h2>{_esc(t["in_scope"])}</h2>{in_html}</div>'
        f'<div class="scope-col out"><h2>{_esc(t["out_of_scope"])}</h2>{out_html}</div>'
        '</section>'
    )


def _constraints_block(intent: dict, t: dict) -> str:
    items = [str(x).strip() for x in (intent.get("constraints") or []) if str(x).strip()]
    if not items:
        return ""
    lis = "".join(f"<li>{_esc(x)}</li>" for x in items)
    return (
        '<section class="panel">'
        f'<h2>{_esc(t["constraints"])}</h2>'
        f'<ul class="constraint-list">{lis}</ul>'
        '</section>'
    )


def _success_block(intent: dict, t: dict) -> str:
    items = [str(x).strip() for x in (intent.get("success_criteria") or []) if str(x).strip()]
    if not items:
        return ""
    lis = "".join(f"<li>{_esc(x)}</li>" for x in items)
    return (
        '<section class="panel">'
        f'<h2>{_esc(t["success_criteria"])}</h2>'
        f'<ul class="checklist">{lis}</ul>'
        '</section>'
    )


def _lane_reasoning_block(state: dict, t: dict) -> str:
    reasoning = state.get("lane_reasoning")
    if not reasoning or not str(reasoning).strip():
        return ""
    return (
        '<section class="lane-callout">'
        f'<h2>{_esc(t["lane_reasoning"])}</h2>'
        f'<p>{_esc(reasoning)}</p>'
        '</section>'
    )


def _evidence_block(state: dict, intent: dict, t: dict) -> str:
    """Render the evidence inventory as a two-column table.

    The state's evidence_inventory maps field-paths ("Goal", "in_scope[0]",
    "constraints[1]", etc.) to lists of contributing seed_slugs. We resolve
    each field-path to a human-friendly row label using the intent fields.
    """
    inventory = state.get("evidence_inventory") or {}
    if not isinstance(inventory, dict) or not inventory:
        return ""

    rows = []
    any_with_seeds = False
    for field_path, entries in inventory.items():
        label = _resolve_field_label(field_path, intent)
        # Normalize entries: support both structured form
        # [{"seed_slug": "...", "relevance": "..."}] and the legacy
        # string-only form ["slug", ...] (the latter renders with a
        # missing-relevance placeholder; new state files MUST use the
        # structured form per state-and-resume.md).
        normalized = []
        for entry in (entries or []):
            if isinstance(entry, dict):
                slug = str(entry.get("seed_slug") or "").strip()
                relevance = str(entry.get("relevance") or "").strip()
            else:
                slug = str(entry or "").strip()
                relevance = ""
            if slug:
                normalized.append((slug, relevance))
        if normalized:
            any_with_seeds = True
            parts = []
            for slug, relevance in normalized:
                if relevance:
                    parts.append(
                        f'<div class="seed-row">'
                        f'<code>{_esc(slug)}</code>'
                        f'<span class="relevance"> — {_esc(relevance)}</span>'
                        f'</div>'
                    )
                else:
                    parts.append(
                        f'<div class="seed-row">'
                        f'<code>{_esc(slug)}</code>'
                        f'<span class="relevance placeholder"> — {_esc(t["no_relevance"])}</span>'
                        f'</div>'
                    )
            cell = f'<td class="seeds">{"".join(parts)}</td>'
        else:
            cell = f'<td class="seeds intent-only">{_esc(t["evidence_intent_only_row"])}</td>'
        rows.append(f'<tr><td class="field">{_esc(label)}</td>{cell}</tr>')

    if not any_with_seeds:
        return (
            '<section class="panel">'
            f'<h2>{_esc(t["evidence_inventory"])}</h2>'
            f'<div class="evidence-empty">{_esc(t["evidence_all_intent_only"])}</div>'
            '</section>'
        )

    return (
        '<section class="panel">'
        f'<h2>{_esc(t["evidence_inventory"])}</h2>'
        '<table class="evidence-table">'
        '<thead><tr>'
        f'<th>{_esc(t["evidence_field"])}</th>'
        f'<th>{_esc(t["evidence_seeds"])}</th>'
        '</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table>'
        '</section>'
    )


_FIELD_PATH_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)(?:\[(\d+)\])?$")

# Whitelist of the 6 known intent rubric fields → singular display label.
# Using an explicit map (rather than `.rstrip("s")`) avoids surprise
# singularizations if a future variant adds a field like `address` or
# `progress` whose trailing `s` is not pluralization.
_SINGULAR_LABELS = {
    "goal":             "Goal",
    "in_scope":         "In scope",
    "out_of_scope":     "Out of scope",
    "constraints":      "Constraint",
    "success_criteria": "Success criterion",
    "open_questions":   "Open question",
}


def _resolve_field_label(field_path: str, intent: dict) -> str:
    """Turn a field-path like `constraints[1]` into 'Constraint #2: <text>'.

    Pure prose labels (e.g., `Goal`) pass through unchanged. Bracketed
    indices resolve against the intent dict to surface the actual bullet
    text, but capped at ~80 chars to keep table rows readable.

    Field-name singularization uses a whitelist (`_SINGULAR_LABELS`) of
    the 6 known intent rubric fields. Unknown fields pass through with
    their underscore-replaced, capitalized form (no `.rstrip("s")`
    guesswork that would mis-singularize `address` → `Acres`).
    """
    if not field_path:
        return ""
    m = _FIELD_PATH_RE.match(str(field_path))
    if not m:
        return str(field_path)
    field, idx = m.group(1), m.group(2)
    if idx is None:
        # Bare field name (e.g., "Goal"): use the whitelist's plural-stripped
        # form if known, otherwise the underscore-replaced capitalize form.
        pretty = _SINGULAR_LABELS.get(field) or field.replace("_", " ").capitalize()
        return pretty
    # Indexed field (e.g., "constraints[1]"): singularize via whitelist.
    pretty_field = _SINGULAR_LABELS.get(field) or field.replace("_", " ").capitalize()
    idx_i = int(idx)
    items = intent.get(field) if isinstance(intent, dict) else None
    if isinstance(items, list) and 0 <= idx_i < len(items):
        snippet = str(items[idx_i]).strip()
        if len(snippet) > 80:
            snippet = snippet[:77].rstrip() + "..."
        return f"{pretty_field} #{idx_i + 1}: {snippet}"
    return f"{pretty_field} #{idx_i + 1}"


def _resolved_block(state: dict, t: dict) -> str:
    findings = state.get("findings") or []
    resolved = [f for f in findings if isinstance(f, dict) and (f.get("resolution") or {}).get("mode") not in (None, "deferred")]
    if not resolved:
        return ""
    items = []
    for f in resolved:
        res = f.get("resolution") or {}
        mode_class = " auto" if res.get("mode") == "auto" else ""
        desc = _esc(f.get("description") or "")
        text = _esc(res.get("text") or "")
        items.append(
            f'<li class="resolved{mode_class}">'
            f'<span class="finding">{desc}</span>'
            f'<span class="resolution">{text}</span>'
            '</li>'
        )
    return (
        '<section class="panel">'
        f'<h2>{_esc(t["resolved_ambiguities"])}</h2>'
        f'<ul class="resolved-list">{"".join(items)}</ul>'
        '</section>'
    )


def _open_questions_block(state: dict, t: dict) -> str:
    findings = state.get("findings") or []
    deferred = [f for f in findings if isinstance(f, dict) and (f.get("resolution") or {}).get("mode") == "deferred"]
    if not deferred:
        return ""
    items = "".join(f'<li>{_esc(f.get("description") or "")}</li>' for f in deferred)
    return (
        '<section class="open-questions">'
        f'<h2>{_esc(t["open_questions"])}</h2>'
        f'<ul>{items}</ul>'
        '</section>'
    )


# ── main ─────────────────────────────────────────────────────────────────


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("usage: render_plan_html.py <path-to-.plan-state.json>\n")
        return 2

    state_path = Path(sys.argv[1])
    if not state_path.is_file():
        sys.stderr.write(f"state file not found: {state_path}\n")
        return 2
    if not TEMPLATE_PATH.is_file():
        sys.stderr.write(f"template not found at {TEMPLATE_PATH}\n")
        return 2

    state = json.loads(state_path.read_text(encoding="utf-8"))
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    intent = state.get("intent") or {}
    lane = state.get("proposed_scale_lane") or ""
    t = _strings_for(state.get("language"))

    replacements = {
        "HTML_LANG":            _esc(t["html_lang"]),
        "T_TITLE_PREFIX":       _esc(t["title_prefix"]),
        "T_LANE_LABEL":         _esc(_lane_label(lane, t)),
        "T_INTENT_LABEL":       _esc(t["intent_label"]),
        "T_VERSION_LABEL":      _esc(t["version_label"]),
        "T_RUN_ID_LABEL":       _esc(t["run_id_label"]),
        "T_CONFIRMED_LABEL":    _esc(t["confirmed_label"]),
        "T_FORMAT_LABEL":       _esc(t["format_label"]),
        "INTENT_SLUG":          _esc(state.get("intent_slug") or "(unnamed)"),
        "PLAN_VERSION":         _esc(state.get("plan_version") or "?"),
        "PLAN_RUN_ID":          _esc(state.get("plan_run_id") or t["not_recorded"]),
        "VERIFIED_AT":          _esc(state.get("verified_at") or t["not_recorded"]),
        "FORMAT_VERSION":       _esc("1.0"),
        "HERO_BLOCK":           _hero_block(intent, t),
        "SCOPE_BLOCK":          _scope_block(intent, t),
        "CONSTRAINTS_BLOCK":    _constraints_block(intent, t),
        "SUCCESS_BLOCK":        _success_block(intent, t),
        "LANE_REASONING_BLOCK": _lane_reasoning_block(state, t),
        "EVIDENCE_BLOCK":       _evidence_block(state, intent, t),
        "RESOLVED_BLOCK":       _resolved_block(state, t),
        "OPEN_QUESTIONS_BLOCK": _open_questions_block(state, t),
    }
    out = _render_template(template, replacements)

    sys.stdout.write(out)
    if not out.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
