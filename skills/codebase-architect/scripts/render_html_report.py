#!/usr/bin/env python3
"""Render a self-contained HTML handoff report from .architect-state.json.

Reads the state file (path arg) plus the bundled HTML template
(assets/html-report-template.html), populates placeholders, and emits HTML
to stdout. The output uses mermaid.js from a CDN for diagram rendering;
all other content is inline so the report works after first load.

Read-only: writes only to stdout. Caller redirects with `> architecture.html`.
"""

import html
import json
import sys
from pathlib import Path


TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "html-report-template.html"


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name) or "node"


def _render_plan(plan: dict) -> str:
    if not plan:
        return "<p><em>(plan not yet captured)</em></p>"
    parts = [f"<p><strong>Goal:</strong> {html.escape(plan.get('goal', '[unspecified]'))}</p>"]
    sections = [("In-scope", "in_scope"), ("Out-of-scope", "out_of_scope"),
                ("Constraints", "constraints"), ("Success criteria", "success_criteria"),
                ("Open questions", "open_questions")]
    for label, key in sections:
        items = plan.get(key) or []
        if items:
            parts.append(f"<h4>{label}</h4><ul>")
            parts.extend(f"<li>{html.escape(str(it))}</li>" for it in items)
            parts.append("</ul>")
    return "\n".join(parts)


def _render_packages(packages: list) -> str:
    if not packages:
        return "<p><em>(no packages planned)</em></p>"
    return "<ul>" + "".join(f"<li><code>{html.escape(str(p))}</code></li>" for p in packages) + "</ul>"


def _render_interfaces(interfaces: list) -> str:
    if not interfaces:
        return "<p><em>(no interfaces yet)</em></p>"
    parts = []
    for iface in interfaces:
        name = html.escape(iface.get("name", "?"))
        pkg = html.escape(iface.get("package", "?"))
        cohesion = html.escape(iface.get("cohesion_source", "?"))
        parts.append(f'<details><summary><strong>{name}</strong> '
                     f'<small>({pkg}, cohesion: {cohesion})</small></summary>')
        parts.append("<ul>")
        for method in iface.get("methods") or []:
            mname = html.escape(method.get("name", "?"))
            fields = ", ".join(method.get("docstring_fields_present", []) or [])
            parts.append(f"<li><code>{mname}</code> — fields: {html.escape(fields)}</li>")
        parts.append("</ul></details>")
    return "\n".join(parts)


def _render_mermaid(interfaces: list) -> str:
    lines = ["graph LR"]
    if not interfaces:
        lines.append('  empty["(no interfaces yet)"]')
        return "\n".join(lines)
    seen: set = set()
    for iface in interfaces:
        name = iface.get("name", "?")
        node_id = _safe(name)
        lines.append(f'  {node_id}["{html.escape(name)}"]')
        for method in iface.get("methods") or []:
            for collab in method.get("collaborators") or []:
                target_id = _safe(collab.split(".", 1)[0])
                edge = (node_id, target_id)
                if edge in seen or target_id == node_id:
                    continue
                seen.add(edge)
                lines.append(f"  {node_id} --> {target_id}")
    return "\n".join(lines)


def _render_rubric(scores: dict) -> str:
    if not scores:
        return "<p><em>(rubric not yet scored)</em></p>"
    rows = "".join(
        f"<tr><td>{html.escape(str(c))}</td><td>{html.escape(str(s))}/4</td></tr>"
        for c, s in scores.items()
    )
    return ("<table><thead><tr><th>Criterion</th><th>Score</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>")


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("usage: render_html_report.py <path-to-.architect-state.json>\n")
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

    out = template
    out = out.replace("{{PROJECT_SLUG}}", html.escape(state.get("project_slug", "(unnamed)")))
    out = out.replace("{{LANGUAGE}}", html.escape(state.get("language_stack", "?")))
    out = out.replace("{{PHASE}}", html.escape(state.get("phase_completed", "?")))
    out = out.replace("{{PLAN}}", _render_plan(state.get("plan") or {}))
    out = out.replace("{{PACKAGES}}", _render_packages(state.get("packages") or []))
    out = out.replace("{{INTERFACES}}", _render_interfaces(state.get("interfaces") or []))
    out = out.replace("{{MERMAID}}", _render_mermaid(state.get("interfaces") or []))
    out = out.replace("{{RUBRIC}}", _render_rubric(state.get("rubric_scores") or {}))

    sys.stdout.write(out)
    if not out.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
