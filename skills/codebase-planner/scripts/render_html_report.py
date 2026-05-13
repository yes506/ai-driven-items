#!/usr/bin/env python3
"""Render a self-contained HTML handoff report from .planner-state.json.

Reads the state file (path arg) plus the bundled HTML template
(assets/html-report-template.html), populates placeholders, and emits HTML
to stdout. The HTML is fully self-contained — no CDN, no external scripts.
The Mermaid diagram is included as plain `<pre>` text so a reviewer can copy
it into a Mermaid renderer; this avoids running third-party JS in the
reviewer's browser, which would also be an XSS surface.

Read-only: writes only to stdout. Caller redirects with `> architecture.html`.
"""

import html
import json
import re
import sys
from pathlib import Path


TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "html-report-template.html"


# ---------- helpers --------------------------------------------------------

def _esc(value) -> str:
    """html.escape that tolerates non-string input (None, ints, etc.)."""
    if value is None:
        return ""
    return html.escape(str(value))


def _safe(name: str) -> str:
    cleaned = "".join(c if c.isalnum() else "_" for c in str(name))
    return cleaned or "node"


def _mermaid_label(name) -> str:
    """Match render_mermaid_dag.py's label escape so the embedded diagram is consistent."""
    return (
        str(name)
        .replace("&", "&amp;")
        .replace('"', "#quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("|", "&#124;")
        .replace("[", "&#91;")
        .replace("]", "&#93;")
        .replace("`", "&#96;")  # Mermaid v10+ supports backtick label syntax
    )


def _render_template(template: str, replacements: dict) -> str:
    """Replace each {{NAME}} placeholder exactly ONCE in a single pass.

    Avoids the double-substitution bug of chained `str.replace()` calls
    where, e.g., a user-provided plan goal containing the literal text
    `{{MERMAID}}` would get re-substituted by a later replace() call.
    """
    pattern = re.compile(r"\{\{(" + "|".join(re.escape(k) for k in replacements) + r")\}\}")
    return pattern.sub(lambda m: replacements[m.group(1)], template)


# ---------- section renderers ---------------------------------------------

def _render_plan(plan: dict) -> str:
    if not plan:
        return "<p><em>(plan not yet captured)</em></p>"
    parts = [f"<p><strong>Goal:</strong> {_esc(plan.get('goal', '[unspecified]'))}</p>"]
    sections = [("In-scope", "in_scope"), ("Out-of-scope", "out_of_scope"),
                ("Constraints", "constraints"), ("Success criteria", "success_criteria"),
                ("Open questions", "open_questions")]
    for label, key in sections:
        items = plan.get(key) or []
        if items:
            parts.append(f"<h4>{_esc(label)}</h4><ul>")
            parts.extend(f"<li>{_esc(it)}</li>" for it in items)
            parts.append("</ul>")
    return "\n".join(parts)


def _render_packages(packages: list) -> str:
    if not packages:
        return "<p><em>(no packages planned)</em></p>"
    return "<ul>" + "".join(f"<li><code>{_esc(p)}</code></li>" for p in packages) + "</ul>"


def _render_interfaces(interfaces: list) -> str:
    if not interfaces:
        return "<p><em>(no interfaces yet)</em></p>"
    parts = []
    for iface in interfaces:
        name = _esc(iface.get("name", "?"))
        pkg = _esc(iface.get("package", "?"))
        cohesion = _esc(iface.get("cohesion_source", "?"))
        parts.append(f'<details open><summary><strong>{name}</strong> '
                     f'<small>({pkg}, cohesion: {cohesion})</small></summary>')
        parts.append("<ul>")
        for method in iface.get("methods") or []:
            mname = _esc(method.get("name", "?"))
            fields = ", ".join(_esc(f) for f in (method.get("docstring_fields_present") or []))
            docstring = method.get("docstring", "")
            parts.append(f"<li><code>{mname}</code>")
            if fields:
                parts.append(f' <small class="meta">fields: {fields}</small>')
            if docstring:
                parts.append(f"<pre class=\"doc\">{_esc(docstring)}</pre>")
            parts.append("</li>")
        parts.append("</ul></details>")
    return "\n".join(parts)


def _render_mermaid(interfaces: list) -> str:
    """Inline Mermaid source as plain text — caller renders externally if desired."""
    lines = ["graph LR"]
    if not interfaces:
        lines.append('  empty["(no interfaces yet)"]')
        return "\n".join(lines)
    name_to_id, taken = {}, {}
    for iface in interfaces:
        original = str(iface.get("name", "?"))
        base = _safe(original)
        if base in taken:
            taken[base] += 1
            node_id = f"{base}_{taken[base]}"
        else:
            taken[base] = 1
            node_id = base
        name_to_id[original] = node_id
        lines.append(f'  {node_id}["{_mermaid_label(original)}"]')
    seen = set()
    for iface in interfaces:
        src_name = str(iface.get("name", "?"))
        src_id = name_to_id.get(src_name)
        if src_id is None:
            continue
        for m in iface.get("methods") or []:
            for c in m.get("collaborators") or []:
                target_name = str(c).split(".", 1)[0]
                target_id = name_to_id.get(target_name)
                if target_id is None or target_id == src_id:
                    continue
                edge = (src_id, target_id)
                if edge in seen:
                    continue
                seen.add(edge)
                lines.append(f"  {src_id} --> {target_id}")
    return "\n".join(lines)


def _render_rubric(scores: dict) -> str:
    if not scores:
        return "<p><em>(rubric not yet scored)</em></p>"
    rows = "".join(
        f"<tr><td>{_esc(c)}</td><td>{_esc(s)}/4</td></tr>"
        for c, s in scores.items()
    )
    return ("<table><thead><tr><th>Criterion</th><th>Score</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>")


# Static checklist (kept in lockstep with references/self-verification.md).
_CHECKLIST_HTML = """
<ul class="checklist">
  <li>The decomposition table in Phase 3 matches the interfaces actually emitted in Phase 5</li>
  <li>Every method has all 9 docstring fields (skim 3 random methods to spot-check)</li>
  <li>No interface looks like a grab-bag of unrelated methods</li>
  <li>The Mermaid DAG (architecture.mmd) is acyclic</li>
  <li>No method body has been written (interface-only)</li>
  <li>The validation command (Phase 6) passed — see <code>.planner-state.json</code>: <code>validation_status</code></li>
</ul>
""".strip()


# ---------- main -----------------------------------------------------------

def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("usage: render_html_report.py <path-to-.planner-state.json>\n")
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

    replacements = {
        "PROJECT_SLUG": _esc(state.get("project_slug", "(unnamed)")),
        "LANGUAGE":     _esc(state.get("language_stack", "?")),
        "PHASE":        _esc(state.get("phase_completed", "?")),
        "PLAN":         _render_plan(state.get("plan") or {}),
        "PACKAGES":     _render_packages(state.get("packages") or []),
        "INTERFACES":   _render_interfaces(state.get("interfaces") or []),
        "MERMAID":      _render_mermaid(state.get("interfaces") or []),
        "RUBRIC":       _render_rubric(state.get("rubric_scores") or {}),
        "CHECKLIST":    _CHECKLIST_HTML,
    }
    out = _render_template(template, replacements)

    sys.stdout.write(out)
    if not out.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
