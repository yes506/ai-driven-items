#!/usr/bin/env python3
"""Render a self-contained HTML verification doc from an intent state file.

Reads `.intent-state.json` (intent-aligner) OR `.seed-state.json`
(seed-gatherer bootstrap path) plus the bundled HTML template
(assets/intent-html-template.html), populates placeholders, emits HTML
to stdout. The two state schemas differ — intent-aligner stores `mode`
and `project_slug` at the top level; seed-gatherer stores them at
`intent.mode` and `intent_slug` respectively. The renderer reads both
forms (intent-aligner keys first, seed-state fallbacks second) so a
single script handles both invocations without drift. The HTML is
fully self-contained — no CDN, no external JS, no external SVG. Every
user-supplied value is HTML-escaped before substitution.

The HTML is designed as a *first-class visual verification document*:
- A **pipeline breadcrumb SVG** anchoring this Intent in the 5-stage
  chain (Intent → Seed → Plan → Doc Stub → Interface).
- A **stat tape SVG** showing in-scope / out-of-scope / criteria /
  constraint / open-question counts at a glance, replacing prose.
- An **SVG mode badge** (⚙ Feature vs ⚠ Problem) replacing the text pill.
- A **hero card** with the goal.
- A **scope grid** with SVG check / cross glyphs.
- A **success checklist** with SVG checkbox glyphs.
- An **SVG fishbone** for the root-cause chain (problem mode only).
- Paired example / counter-example columns with SVG bullets.
- A loud SVG-iconed open-questions callout when unresolved items remain.

Machine-only fields (intent_id, language knob) are NOT rendered — those
stay in intent.<slug>.md.

The shared visual vocabulary (stage glyphs, colors, status palette) is
documented in references/visual-language.md. The five chain skills'
renderers all emit the same five-stage breadcrumb so a reviewer who
opens any HTML output immediately knows where the artifact sits.

Read-only: writes only to stdout. Caller redirects with
`> ai-artifacts/intents/intent.<slug>.html` per SKILL.md Phase 5.
"""

import html
import json
import re
import sys
from pathlib import Path

# Sibling module — Python adds this script's directory to sys.path[0] when
# the script is invoked directly, so a plain import works without packaging.
from _chain_visuals import (
    pipeline_breadcrumb_svg,
    stat_tape_svg,
)


TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "intent-html-template.html"


# Localized chrome strings. Language is read from state["language"] —
# "Korean" → ko, anything else → en (fallback). Body content already
# follows LANGUAGE; this localizes the section labels and the lang attr.
STRINGS = {
    "en": {
        "html_lang":           "en",
        "title_prefix":        "Intent",
        "mode_feature":        "Feature",
        "mode_problem":        "Problem",
        "what_we_agreed":      "What we agreed to build",
        "for_persona":         "For",
        "in_scope":            "In scope",
        "out_of_scope":        "Not in scope",
        "success_criteria":    "How we'll know it works",
        "constraints":         "Constraints",
        "why_happening":       "Why this is happening",
        "rc_symptom":          "Symptom",
        "rc_root":             "Root cause",
        "rc_why":              "Why",
        "examples_good":       "What it looks like when it works",
        "examples_bad":        "What must NOT happen",
        "examples_incidents":  "Recent incidents (the pain we're solving)",
        "examples_must_not_break": "Adjacent areas that must not break",
        "open_questions":      "Still unresolved",
        "verified_at":         "Verified by user at",
        "not_recorded":        "(not recorded)",
        "unspecified":         "(unspecified)",
        "no_examples":         "(no example captured)",
        "no_counter":          "(no counter-example captured)",
    },
    "ko": {
        "html_lang":           "ko",
        "title_prefix":        "의도 확인서",
        "mode_feature":        "기능 정의",
        "mode_problem":        "문제 정의",
        "what_we_agreed":      "우리가 합의한 결과물",
        "for_persona":         "대상",
        "in_scope":            "범위 안",
        "out_of_scope":        "범위 밖",
        "success_criteria":    "성공의 기준",
        "constraints":         "제약 사항",
        "why_happening":       "원인 분석",
        "rc_symptom":          "증상",
        "rc_root":             "근본 원인",
        "rc_why":              "왜",
        "examples_good":       "이렇게 동작하면 성공",
        "examples_bad":        "이런 일은 절대 발생하면 안 됨",
        "examples_incidents":  "과거에 발생한 사건 (해결하려는 통증)",
        "examples_must_not_break": "절대 깨지면 안 되는 인접 영역",
        "open_questions":      "아직 결정되지 않은 것",
        "verified_at":         "사용자 확인 시각:",
        "not_recorded":        "(기록 없음)",
        "unspecified":         "(미지정)",
        "no_examples":         "(예시가 기록되지 않음)",
        "no_counter":          "(반례가 기록되지 않음)",
    },
}


def _strings_for(language) -> dict:
    """Return the string table for the given LANGUAGE.

    Fallback order, matching SKILL.md Phase L contract ("missing language
    field defaults to Korean — Phase L's own default"):

    - None / empty / whitespace-only → Korean (contract default)
    - "korean" / "ko" / "kr" (case-insensitive) → Korean
    - anything else (e.g. "english", "Spanish") → English fallback
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
    """Replace each {{NAME}} placeholder exactly ONCE in a single pass.

    Avoids the double-substitution bug of chained `str.replace()` where a
    user-provided value containing `{{X}}` could get re-substituted by a
    later replace() call.
    """
    pattern = re.compile(r"\{\{(" + "|".join(re.escape(k) for k in replacements) + r")\}\}")
    return pattern.sub(lambda m: replacements[m.group(1)], template)


# ── intent-aligner-specific visual primitives ─────────────────────────────
# (Pipeline breadcrumb, stat tape, and stage glyphs come from
# _chain_visuals.py — see the imports at the top of this file. The mode
# badge and root-cause fishbone are intent-aligner-only.)


def _mode_badge_svg(mode: str, t: dict, lang: str) -> str:
    """Inline SVG badge for Feature vs Problem mode. Replaces the text pill
    so the visual asymmetry between the two modes is immediately legible.
    """
    is_problem = (mode == "problem")
    color = "#b53737" if is_problem else "#2b5fb5"
    soft = "#fbeaea" if is_problem else "#e8f0fb"
    label = t["mode_problem"] if is_problem else t["mode_feature"]
    tagline_en = "Root-cause analysis" if is_problem else "New capability"
    tagline_ko = "근본 원인 분석" if is_problem else "신규 기능"
    tagline = tagline_ko if lang == "ko" else tagline_en

    if is_problem:
        # ⚠ warning triangle
        glyph = (
            '<polygon points="14,4 26,24 2,24" fill="none" '
            f'stroke="{color}" stroke-width="2.2" stroke-linejoin="round"/>'
            f'<line x1="14" y1="11" x2="14" y2="18" stroke="{color}" stroke-width="2.2" stroke-linecap="round"/>'
            f'<circle cx="14" cy="21.5" r="1.2" fill="{color}"/>'
        )
    else:
        # ⚙ gear (simplified 6-tooth)
        glyph = (
            f'<circle cx="14" cy="14" r="5" fill="none" stroke="{color}" stroke-width="2"/>'
            f'<circle cx="14" cy="14" r="1.7" fill="{color}"/>'
        )
        # 6 little teeth
        for ang_deg in (0, 60, 120, 180, 240, 300):
            import math as _m
            rad = _m.radians(ang_deg)
            x1 = 14 + 7 * _m.cos(rad)
            y1 = 14 + 7 * _m.sin(rad)
            x2 = 14 + 10 * _m.cos(rad)
            y2 = 14 + 10 * _m.sin(rad)
            glyph += (
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
            )

    return (
        f'<span class="mode-badge" style="background:{soft};border-color:{color};color:{color}">'
        f'<svg viewBox="0 0 28 28" width="20" height="20" aria-hidden="true">{glyph}</svg>'
        f'<span class="mode-text"><strong>{_esc(label)}</strong>'
        f'<span class="mode-tagline">{_esc(tagline)}</span></span>'
        f'</span>'
    )


def _fishbone_svg(steps: list, t: dict, lang: str) -> str:
    """Render the 5-Whys chain as an SVG fishbone:

        Symptom ──┬── Why1 ──┬── Why2 ──┬── Root
                  │          │          │
                 (bone)    (bone)     (bone)

    Each step gets a horizontal segment + a slanted "bone" leading to a
    label. This replaces the previous flex-based horizontal cards.

    Caller has already validated len(steps) >= 2 and that steps are
    non-empty strings.
    """
    n = len(steps)
    width = 880
    gap = (width - 40) // max(n - 1, 1)
    height = 230
    spine_y = 130
    parts = [
        f'<svg class="fishbone-svg" viewBox="0 0 {width} {height}" '
        f'preserveAspectRatio="xMidYMid meet" role="img" '
        f'aria-label="Root cause chain">'
    ]
    # spine
    parts.append(
        f'<line x1="20" y1="{spine_y}" x2="{20 + gap*(n-1) + 0}" y2="{spine_y}" '
        f'stroke="#888" stroke-width="2.5"/>'
    )
    # arrowhead at end (pointing right)
    end_x = 20 + gap * (n - 1)
    parts.append(
        f'<polygon points="{end_x},{spine_y} {end_x-10},{spine_y-6} {end_x-10},{spine_y+6}" '
        f'fill="#888"/>'
    )

    # Per-step nodes + bones. Alternate top/bottom so labels don't collide.
    for i, step in enumerate(steps):
        x = 20 + gap * i
        is_top = (i % 2 == 0)
        if i == 0:
            role_en, role_ko, color = "Symptom", "증상", "#b53737"
        elif i == n - 1:
            role_en, role_ko, color = "Root cause", "근본 원인", "#2f7c4f"
        else:
            role_en, role_ko, color = f"Why {i}", f"이유 {i}", "#b87900"
        role = role_ko if lang == "ko" else role_en

        # node dot on spine
        parts.append(
            f'<circle cx="{x}" cy="{spine_y}" r="6" fill="{color}" '
            f'stroke="#fff" stroke-width="2"/>'
        )
        # label box first (so we know where the bone should land — round-3
        # F-F fixed an issue where the last node's bone overran the viewBox
        # by always pointing 30px right of the node; now the bone lands on
        # the actual clamped box position).
        bone_dy = -50 if is_top else 50
        bone_y = spine_y + bone_dy
        box_y = bone_y - 22 if is_top else bone_y - 2
        box_w = min(gap, 220)
        box_h = 56
        # preferred box origin = 30px to the right of the node, but for
        # the rightmost nodes clamp left so the box (and the bone that
        # connects to it) stays inside the viewBox.
        box_x = x + 30
        if box_x + box_w > width - 4:
            box_x = max(0, width - 4 - box_w)
        # bone goes from the spine node to the near corner of the box
        parts.append(
            f'<line x1="{x}" y1="{spine_y}" x2="{box_x}" y2="{bone_y}" '
            f'stroke="{color}" stroke-width="2" stroke-dasharray="3 3"/>'
        )
        parts.append(
            f'<rect x="{box_x}" y="{box_y}" width="{box_w}" height="{box_h}" '
            f'rx="5" fill="#fff" stroke="{color}" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{box_x + 8}" y="{box_y + 16}" font-size="10" font-weight="700" '
            f'fill="{color}" letter-spacing="0.06em" '
            f'font-family="-apple-system, system-ui, sans-serif">'
            f'{_esc(role.upper())}</text>'
        )
        # body text (truncate visually; full text remains in markdown)
        snippet = step if len(step) <= 60 else (step[:57] + "…")
        parts.append(
            f'<text x="{box_x + 8}" y="{box_y + 36}" font-size="12" '
            f'fill="#1a1a1a" '
            f'font-family="-apple-system, system-ui, sans-serif">'
            f'{_esc(snippet)}</text>'
        )

    parts.append('</svg>')
    return "".join(parts)


# ── block renderers ──────────────────────────────────────────────────────


def _hero_block(intent: dict, t: dict) -> str:
    goal = intent.get("goal")
    persona = intent.get("persona")
    if not (goal or persona):
        return ""
    goal_html = (
        f'<p class="goal">{_esc(goal)}</p>'
        if goal else f'<p class="goal placeholder">{_esc(t["unspecified"])}</p>'
    )
    persona_html = (
        f'<p class="persona"><strong>{_esc(t["for_persona"])}:</strong> {_esc(persona)}</p>'
        if persona else ""
    )
    return (
        '<section class="hero">'
        f'<div class="label">{_esc(t["what_we_agreed"])}</div>'
        f'{goal_html}{persona_html}'
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
        if in_scope else f'<p class="placeholder">{_esc(t["not_recorded"])}</p>'
    )
    out_html = (
        f'<ul>{"".join(_li(x) for x in out_scope)}</ul>'
        if out_scope else f'<p class="placeholder">{_esc(t["not_recorded"])}</p>'
    )
    return (
        '<section class="scope-grid">'
        f'<div class="scope-col in"><h2>{_esc(t["in_scope"])}</h2>{in_html}</div>'
        f'<div class="scope-col out"><h2>{_esc(t["out_of_scope"])}</h2>{out_html}</div>'
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


def _root_cause_block(intent: dict, mode: str, t: dict, lang: str) -> str:
    """SVG fishbone of the 5-Whys chain. Problem mode only.

    Suppressed for n<2 chains: a one-element "chain" has no flow. Avoids
    labeling a lone step "Symptom" with no Why to flow into. For n>=2 the
    chain is rendered as an SVG fishbone (see `_fishbone_svg`). The
    full-text version of each step still lives in the markdown intent file
    — the SVG truncates labels for visual fit.
    """
    if mode != "problem":
        return ""
    chain = intent.get("root_cause")
    if not chain:
        return ""
    if isinstance(chain, str):
        chain = [chain]
    steps = [str(x).strip() for x in chain if str(x).strip()]
    if len(steps) < 2:
        return ""
    return (
        '<section class="panel">'
        f'<h2>{_esc(t["why_happening"])}</h2>'
        f'{_fishbone_svg(steps, t, lang)}'
        '</section>'
    )


def _examples_block(intent: dict, mode: str, t: dict) -> str:
    """Paired columns: positive (examples) vs negative (counter_examples).

    Column labels are mode-aware. In feature mode the positive column is
    "happy path" semantics; in problem mode it's "past incidents we want
    to prevent" — both rendered in the same two-column layout but with
    labels that match what was elicited per the mode's question bank.
    """
    good = [str(x).strip() for x in (intent.get("examples") or []) if str(x).strip()]
    bad = [str(x).strip() for x in (intent.get("counter_examples") or []) if str(x).strip()]
    if not (good or bad):
        return ""

    if mode == "problem":
        good_label = t["examples_incidents"]
        bad_label = t["examples_must_not_break"]
    else:
        good_label = t["examples_good"]
        bad_label = t["examples_bad"]

    def _items(items, placeholder):
        if not items:
            return f'<p class="placeholder">{_esc(placeholder)}</p>'
        return "".join(f'<div class="ex-item">{_esc(it)}</div>' for it in items)

    return (
        '<section class="ex-grid">'
        f'<div class="ex-col good"><h2>{_esc(good_label)}</h2>'
        f'{_items(good, t["no_examples"])}</div>'
        f'<div class="ex-col bad"><h2>{_esc(bad_label)}</h2>'
        f'{_items(bad, t["no_counter"])}</div>'
        '</section>'
    )


def _open_questions_block(intent: dict, t: dict) -> str:
    """Render only when there are unresolved items. Hidden when empty."""
    items = [str(x).strip() for x in (intent.get("open_questions") or []) if str(x).strip()]
    if not items:
        return ""
    lis = "".join(f"<li>{_esc(x)}</li>" for x in items)
    return (
        '<section class="open-questions">'
        f'<h2>{_esc(t["open_questions"])}</h2>'
        f'<ul>{lis}</ul>'
        '</section>'
    )


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write(f"usage: {Path(__file__).name} <path-to-state.json>\n")
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

    # Dual-schema read — intent-aligner stores `mode` and `project_slug` at
    # the top level; seed-gatherer bootstrap stores them at `intent.mode`
    # and `intent_slug`. For the confirmation timestamp the seed-state has
    # TWO candidates: `bootstrap_verified_at` (Phase 1b.4 confirm-intent)
    # and `verified_at` (Phase 3 confirm-seeds). The intent HTML must show
    # the intent-confirmation moment, so `bootstrap_verified_at` takes
    # precedence when present; intent-aligner state lacks that key and
    # falls through to its own `verified_at`.
    intent = state.get("intent") or {}
    mode = state.get("mode") or intent.get("mode") or "feature"
    project_slug = state.get("project_slug") or state.get("intent_slug") or "(unnamed)"
    verified_at = state.get("bootstrap_verified_at") or state.get("verified_at")
    t = _strings_for(state.get("language"))
    lang = t["html_lang"]  # "ko" or "en"

    # stat tape: counts per category. Empty categories are still shown
    # (muted) so the reviewer can see what is missing at a glance.
    stat_tuples = [
        (len(intent.get("in_scope")        or []), "In scope",    "범위 안",    "#2f7c4f"),
        (len(intent.get("out_of_scope")    or []), "Out of scope","범위 밖",    "#b53737"),
        (len(intent.get("success_criteria")or []), "Success",     "성공 기준",  "#2b5fb5"),
        (len(intent.get("constraints")     or []), "Constraints", "제약",       "#7a3fb5"),
        (len(intent.get("open_questions")  or []), "Open Q",      "미해결",     "#b87900"),
    ]

    replacements = {
        "HTML_LANG":            _esc(t["html_lang"]),
        "T_TITLE_PREFIX":       _esc(t["title_prefix"]),
        "T_VERIFIED_AT":        _esc(t["verified_at"]),
        "PROJECT_SLUG":         _esc(project_slug),
        "VERIFIED_AT":          _esc(verified_at or t["not_recorded"]),
        "PIPELINE_SVG":         pipeline_breadcrumb_svg("intent", lang),
        "MODE_BADGE":           _mode_badge_svg(mode, t, lang),
        "STAT_TAPE":            stat_tape_svg(stat_tuples, lang),
        "HERO_BLOCK":           _hero_block(intent, t),
        "SCOPE_BLOCK":          _scope_block(intent, t),
        "SUCCESS_BLOCK":        _success_block(intent, t),
        "CONSTRAINTS_BLOCK":    _constraints_block(intent, t),
        "ROOT_CAUSE_BLOCK":     _root_cause_block(intent, mode, t, lang),
        "EXAMPLES_BLOCK":       _examples_block(intent, mode, t),
        "OPEN_QUESTIONS_BLOCK": _open_questions_block(intent, t),
    }
    out = _render_template(template, replacements)

    sys.stdout.write(out)
    if not out.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
