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

# Sibling modules — chain visual primitives + interface-graph helpers.
# `_iface_graph` is local to codebase-planner because interface graphs are
# this skill's concern (the chain primitives in `_chain_visuals` are
# vocabulary used by all 5 chain skills).
from _chain_visuals import pipeline_breadcrumb_svg, stat_tape_svg
from _iface_graph import build_id_map, collect_edges, mermaid_label


TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "html-report-template.html"


# ---------- helpers --------------------------------------------------------

def _esc(value) -> str:
    """html.escape that tolerates non-string input (None, ints, etc.)."""
    if value is None:
        return ""
    return html.escape(str(value))


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
    """Inline Mermaid source as plain text — caller renders externally if
    desired. Uses the shared `_iface_graph` helpers so the in-html embed,
    the inline SVG, AND the standalone .mmd file (rendered by
    render_mermaid_dag.py) all agree on id assignment + edge selection.
    """
    lines = ["graph LR"]
    if not interfaces:
        lines.append('  empty["(no interfaces yet)"]')
        return "\n".join(lines)
    name_to_id = build_id_map(interfaces)
    for original, node_id in name_to_id.items():
        lines.append(f'  {node_id}["{mermaid_label(original)}"]')
    for src_id, dst_id in collect_edges(interfaces, name_to_id):
        lines.append(f"  {src_id} --> {dst_id}")
    return "\n".join(lines)


def _render_interface_dag_svg(interfaces: list) -> str:
    """Render the interface dependency DAG as inline SVG. Replaces the
    previous Mermaid-source-in-<pre> block for the HTML view. The sibling
    `render_mermaid_dag.py` still emits the .mmd source file separately
    for reviewers who want to paste into mermaid.live.

    Layout: layered by longest-path-from-source. Within each layer, nodes
    spread horizontally and evenly. Edges are cubic Bezier curves with an
    arrowhead. Inline only — no JS, no external assets.
    """
    if not interfaces:
        return '<div class="empty-dag">(no interfaces yet)</div>'

    # Shared helpers — same id-map and edge set the Mermaid path uses,
    # so the inline SVG, the .mmd source, and the stat-tape edge count
    # never disagree.
    name_to_id = build_id_map(interfaces)
    id_to_name = {v: k for k, v in name_to_id.items()}
    id_to_iface = {name_to_id[str(i.get("name", "?"))]: i for i in interfaces}
    edges = collect_edges(interfaces, name_to_id)

    # Compute longest-path layer for each node (Bellman-Ford-style).
    level = {nid: 0 for nid in id_to_name}
    for _ in range(len(id_to_name) + 1):
        changed = False
        for src, dst in edges:
            new = level[src] + 1
            if new > level[dst]:
                level[dst] = new
                changed = True
        if not changed:
            break
    if level:
        n_levels = max(level.values()) + 1
    else:
        n_levels = 1
    by_level: dict = {}
    for nid, lvl in level.items():
        by_level.setdefault(lvl, []).append(nid)
    for lvl in by_level:
        by_level[lvl].sort()

    # Layout sizing.
    width = 880
    node_w = 168
    node_h = 50
    level_y_gap = 110
    height = max(220, level_y_gap * n_levels + 60)
    top_margin = 30

    pos: dict = {}
    for lvl, ids in by_level.items():
        n = len(ids)
        if n == 1:
            xs = [(width - node_w) / 2]
        else:
            avail = width - node_w
            step = avail / (n - 1)
            xs = [i * step for i in range(n)]
        y = top_margin + lvl * level_y_gap
        for nid, x in zip(ids, xs):
            pos[nid] = (x, y)

    parts = [
        f'<svg class="iface-dag" viewBox="0 0 {width} {int(height)}" '
        f'preserveAspectRatio="xMidYMid meet" role="img" '
        f'aria-label="Interface dependency graph">'
        '<defs>'
        '<marker id="iface-arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        '<path d="M0,0 L10,5 L0,10 Z" fill="#888"/>'
        '</marker>'
        '</defs>'
    ]

    # edges
    for src, dst in edges:
        if src not in pos or dst not in pos:
            continue
        sx, sy = pos[src]
        tx, ty = pos[dst]
        sx0 = sx + node_w / 2
        sy0 = sy + node_h
        tx0 = tx + node_w / 2
        ty0 = ty
        cy_off = max(24, (ty0 - sy0) / 2)
        d = (
            f"M {sx0:.1f},{sy0:.1f} "
            f"C {sx0:.1f},{sy0 + cy_off:.1f} "
            f"{tx0:.1f},{ty0 - cy_off:.1f} "
            f"{tx0:.1f},{ty0:.1f}"
        )
        parts.append(
            f'<path d="{d}" fill="none" stroke="#888" stroke-width="1.5" '
            f'marker-end="url(#iface-arrow)" opacity="0.75"/>'
        )

    # nodes
    palette = ["#0f7a83", "#2b5fb5", "#7a3fb5", "#b87900", "#b53737", "#2f7c4f"]
    soft_map = {
        "#0f7a83": "#dff3f5", "#2b5fb5": "#e8f0fb", "#7a3fb5": "#f1e8fb",
        "#b87900": "#fff4d6", "#b53737": "#fbeaea", "#2f7c4f": "#e6f4ec",
    }
    for nid, (x, y) in pos.items():
        iface = id_to_iface.get(nid, {})
        original = str(iface.get("name") or id_to_name.get(nid, nid))
        pkg = str(iface.get("package") or "")
        n_methods = len(iface.get("methods") or [])
        color = palette[level[nid] % len(palette)]
        soft = soft_map[color]
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{node_w}" height="{node_h}" '
            f'rx="6" fill="{soft}" stroke="{color}" stroke-width="1.8"/>'
        )
        short_name = original if len(original) <= 22 else (original[:20] + "…")
        parts.append(
            f'<text x="{x + 10:.1f}" y="{y + 18:.1f}" font-size="13" '
            f'font-weight="700" fill="{color}" '
            f'font-family="-apple-system, system-ui, sans-serif">'
            f'{_esc(short_name)}</text>'
        )
        short_pkg = pkg if len(pkg) <= 26 else ("…" + pkg[-25:])
        parts.append(
            f'<text x="{x + 10:.1f}" y="{y + 33:.1f}" font-size="10" '
            f'fill="#5a5a5a" '
            f'font-family="ui-monospace, SFMono-Regular, monospace">'
            f'{_esc(short_pkg)}</text>'
        )
        # method-count badge in the top-right corner of the node
        parts.append(
            f'<text x="{x + node_w - 10:.1f}" y="{y + 18:.1f}" font-size="10.5" '
            f'text-anchor="end" font-weight="600" fill="{color}" '
            f'font-family="-apple-system, system-ui, sans-serif">'
            f'{n_methods}m</text>'
        )

    parts.append('</svg>')
    return "".join(parts)


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

    # codebase-planner has no per-state language knob — the report is in
    # English (technical content). Pass "en" to the chain primitives.
    lang = "en"

    interfaces = state.get("interfaces") or []
    packages = state.get("packages") or []
    n_methods = sum(len(i.get("methods") or []) for i in interfaces)
    # Use the same edge set the SVG DAG and Mermaid source emit, so the
    # stat tape can't disagree with the canonical visual (fixes round-3
    # finding F-A — see _collect_edges).
    _name_to_id_for_stats = build_id_map(interfaces)
    n_edges = len(collect_edges(interfaces, _name_to_id_for_stats))
    stat_tuples = [
        (len(packages),   "Packages",   "패키지",   "#2b5fb5"),
        (len(interfaces), "Interfaces", "인터페이스","#0f7a83"),
        (n_methods,       "Methods",    "메서드",   "#7a3fb5"),
        (n_edges,         "Edges",      "의존성",   "#b87900"),
    ]

    replacements = {
        "PROJECT_SLUG":      _esc(state.get("project_slug", "(unnamed)")),
        "LANGUAGE":          _esc(state.get("language_stack", "?")),
        "PHASE":             _esc(state.get("phase_completed", "?")),
        "PIPELINE_SVG":      pipeline_breadcrumb_svg("interface", lang),
        "STAT_TAPE":         stat_tape_svg(stat_tuples, lang),
        "PLAN":              _render_plan(state.get("plan") or {}),
        "PACKAGES":          _render_packages(packages),
        "INTERFACES":        _render_interfaces(interfaces),
        "INTERFACE_DAG_SVG": _render_interface_dag_svg(interfaces),
        "MERMAID":           _render_mermaid(interfaces),
        "RUBRIC":            _render_rubric(state.get("rubric_scores") or {}),
        "CHECKLIST":         _CHECKLIST_HTML,
    }
    out = _render_template(template, replacements)

    sys.stdout.write(out)
    if not out.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
