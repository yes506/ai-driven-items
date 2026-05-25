#!/usr/bin/env python3
"""Render a self-contained HTML verification doc from .intent-state.json.

Reads the state file (path arg) plus the bundled HTML template
(assets/intent-html-template.html), populates placeholders, emits HTML
to stdout. The HTML is fully self-contained — no CDN, no external JS.
Every user-supplied value is HTML-escaped before substitution.

Read-only: writes only to stdout. Caller redirects with
`> intent.<slug>.html` per SKILL.md Phase 5.
"""

import html
import json
import re
import sys
from pathlib import Path


TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "intent-html-template.html"


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


def _render_paragraph(value, placeholder="(unspecified)") -> str:
    """Render a single-string field as a <p>. Falls back to a placeholder."""
    if not value or not str(value).strip():
        return f'<p class="placeholder">{_esc(placeholder)}</p>'
    return f"<p>{_esc(value)}</p>"


def _render_list(items, placeholder="(none recorded)") -> str:
    """Render a list of strings as a <ul>. Falls back to a placeholder."""
    if not items:
        return f'<p class="placeholder">{_esc(placeholder)}</p>'
    lis = "".join(f"<li>{_esc(it)}</li>" for it in items if str(it).strip())
    if not lis:
        return f'<p class="placeholder">{_esc(placeholder)}</p>'
    return f"<ul>{lis}</ul>"


def _render_examples(items, kind="example") -> str:
    """Render examples / counter-examples with a subtle backdrop."""
    placeholder = (
        "(no happy-path example captured — Phase 2 must include at least one)"
        if kind == "example"
        else "(no counter-example captured — Phase 2 must include at least one)"
    )
    if not items:
        return f'<p class="placeholder">{_esc(placeholder)}</p>'
    cls = "good" if kind == "example" else "warn"
    return "".join(f'<div class="{cls}">{_esc(it)}</div>' for it in items if str(it).strip()) \
        or f'<p class="placeholder">{_esc(placeholder)}</p>'


def _render_root_cause(intent: dict, mode: str) -> str:
    """Only meaningful in problem mode; in feature mode render an explicit
    'not-applicable' note so the section's purpose is clear to the reader."""
    if mode != "problem":
        return '<p class="placeholder">(not applicable — feature mode)</p>'
    chain = intent.get("root_cause") or []
    if not chain:
        return '<p class="placeholder">(5 Whys chain not recorded)</p>'
    if isinstance(chain, str):
        return f"<p>{_esc(chain)}</p>"
    return "<ol>" + "".join(f"<li>{_esc(step)}</li>" for step in chain) + "</ol>"


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

    replacements = {
        "PROJECT_SLUG":     _esc(state.get("project_slug") or "(unnamed)"),
        "MODE":             _esc(mode),
        "LANGUAGE":         _esc(state.get("language", "?")),
        "INTENT_ID":        _esc(state.get("intent_id", "?")),
        "VERIFIED_AT":      _esc(state.get("verified_at", "(not yet confirmed)")),
        "GOAL":             _render_paragraph(intent.get("goal")),
        "PERSONA":          _render_paragraph(intent.get("persona")),
        "IN_SCOPE":         _render_list(intent.get("in_scope")),
        "OUT_OF_SCOPE":     _render_list(intent.get("out_of_scope")),
        "CONSTRAINTS":      _render_list(intent.get("constraints")),
        "SUCCESS_CRITERIA": _render_list(intent.get("success_criteria")),
        "EXAMPLES":         _render_examples(intent.get("examples"), kind="example"),
        "COUNTER_EXAMPLES": _render_examples(intent.get("counter_examples"), kind="counter"),
        "ROOT_CAUSE":       _render_root_cause(intent, mode),
        "OPEN_QUESTIONS":   _render_list(intent.get("open_questions"), placeholder="(none)"),
    }
    out = _render_template(template, replacements)

    sys.stdout.write(out)
    if not out.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
