#!/usr/bin/env python3
"""Render a self-contained HTML verification doc from .intent-state.json.

Reads the state file (path arg) plus the bundled HTML template
(assets/intent-html-template.html), populates placeholders, emits HTML
to stdout. The HTML is fully self-contained — no CDN, no external JS.
Every user-supplied value is HTML-escaped before substitution.

The HTML is designed as a *first-class human verification document*, not
an MD→HTML conversion: a hero card with the goal, a side-by-side scope
grid, a success checklist, a root-cause flow (problem mode only), paired
example/counter-example columns, and a loud open-questions callout when
unresolved items remain. Machine-only fields (intent_id, language knob)
are NOT rendered — those stay in intent.<slug>.md.

Read-only: writes only to stdout. Caller redirects with
`> intent.<slug>.html` per SKILL.md Phase 5.
"""

import html
import json
import re
import sys
from pathlib import Path


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


def _root_cause_block(intent: dict, mode: str, t: dict) -> str:
    """Visual horizontal flow of the 5-Whys chain. Problem mode only.

    Suppressed for n<2 chains: a one-element "chain" has no flow.
    Avoids labeling a lone step "Symptom" with no `Why` to flow into.
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

    parts = []
    n = len(steps)
    for i, step in enumerate(steps):
        if i == 0:
            cls, label = "rc-step symptom", t["rc_symptom"]
        elif i == n - 1 and n > 1:
            cls, label = "rc-step root", t["rc_root"]
        else:
            cls, label = "rc-step", f'{t["rc_why"]} {i}'
        parts.append(
            f'<div class="{cls}">'
            f'<span class="rc-label">{_esc(label)}</span>'
            f'{_esc(step)}'
            '</div>'
        )
        if i != n - 1:
            parts.append('<div class="rc-arrow" aria-hidden="true">→</div>')

    return (
        '<section class="panel">'
        f'<h2>{_esc(t["why_happening"])}</h2>'
        f'<div class="root-cause-flow">{"".join(parts)}</div>'
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


def _mode_label(mode: str, t: dict) -> str:
    if mode == "problem":
        return t["mode_problem"]
    return t["mode_feature"]


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("usage: render_html_report.py <path-to-.intent-state.json>\n")
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
    mode = state.get("mode") or "feature"
    t = _strings_for(state.get("language"))

    replacements = {
        "HTML_LANG":            _esc(t["html_lang"]),
        "T_TITLE_PREFIX":       _esc(t["title_prefix"]),
        "T_MODE_LABEL":         _esc(_mode_label(mode, t)),
        "T_VERIFIED_AT":        _esc(t["verified_at"]),
        "PROJECT_SLUG":         _esc(state.get("project_slug") or "(unnamed)"),
        "VERIFIED_AT":          _esc(state.get("verified_at", t["not_recorded"])),
        "HERO_BLOCK":           _hero_block(intent, t),
        "SCOPE_BLOCK":          _scope_block(intent, t),
        "SUCCESS_BLOCK":        _success_block(intent, t),
        "CONSTRAINTS_BLOCK":    _constraints_block(intent, t),
        "ROOT_CAUSE_BLOCK":     _root_cause_block(intent, mode, t),
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
