#!/usr/bin/env python3
"""render_doc_structure.py — render document-structure visual artifacts.

Reads the stub list + dependencies from `.document-planner-state.json`
and emits either:
  - a Mermaid DAG (`--format mmd`), or
  - a self-contained HTML preview (`--format html`)

The HTML output has no CDN dependencies and HTML-escapes every node
label to prevent `click ... href="javascript:..."` injection or
mid-label `<script>` injection.

Usage:
  render_doc_structure.py <state.json> --format mmd > document-structure.mmd
  render_doc_structure.py <state.json> --format html > document-structure.html

Expected state.json shape (minimum):
  {
    "intent_slug": "...",
    "doctype": "api-spec|tech-spec|runbook|ppt",
    "stubs": [
      {"id": "<stub-id>", "title": "<short title>",
       "dependencies": ["<other-id>", ...]},
      ...
    ]
  }

Exits 0 on success, 2 on usage error.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

# Sibling module — chain visual primitives. The pipeline breadcrumb /
# stat tape are shared by all five chain skills' HTML outputs.
from _chain_visuals import pipeline_breadcrumb_svg, stat_tape_svg, _esc


def render_mmd(state: dict) -> str:
    """Render the Mermaid DAG. Raises ValueError on undeclared dependencies
    via the shared `_assert_declared_deps` so the .mmd and HTML paths
    share one validation contract."""
    stubs = state.get("stubs", [])
    _assert_declared_deps(stubs)
    declared_ids = {s["id"] for s in stubs}
    lines = ["graph TD"]
    for stub in stubs:
        sid = stub["id"]
        title = stub.get("title") or sid
        safe_title = str(title).replace('"', "'")
        lines.append(f'  {sid}["{safe_title}"]')
    for stub in stubs:
        sid = stub["id"]
        for dep in (stub.get("dependencies") or []):
            if dep in declared_ids:
                lines.append(f"  {dep} --> {sid}")
    return "\n".join(lines) + "\n"


# ── doc-type tile SVG ─────────────────────────────────────────────────────


# Per-doctype glyph + color. Coordinates are renderer-controlled; the
# doctype string is matched against this whitelist before the lookup, so
# arbitrary state values cannot leak into SVG attribute positions.
_DOCTYPE_GLYPHS = {
    "api-spec":  ("#0f7a83", "API",
        '<polyline points="6,10 2,16 6,22" fill="none" stroke="#0f7a83" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
        '<polyline points="26,10 30,16 26,22" fill="none" stroke="#0f7a83" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="19" y1="8" x2="13" y2="24" stroke="#0f7a83" stroke-width="2.2" stroke-linecap="round"/>'),
    "tech-spec": ("#2b5fb5", "TECH",
        '<rect x="5" y="4" width="22" height="24" rx="2.5" fill="none" stroke="#2b5fb5" stroke-width="2"/>'
        '<line x1="9" y1="11" x2="22" y2="11" stroke="#2b5fb5" stroke-width="1.6"/>'
        '<line x1="9" y1="15" x2="22" y2="15" stroke="#2b5fb5" stroke-width="1.6"/>'
        '<line x1="9" y1="19" x2="22" y2="19" stroke="#2b5fb5" stroke-width="1.6"/>'
        '<line x1="9" y1="23" x2="17" y2="23" stroke="#2b5fb5" stroke-width="1.6"/>'),
    "runbook":   ("#b53737", "RUN",
        '<circle cx="16" cy="16" r="11" fill="none" stroke="#b53737" stroke-width="2"/>'
        '<polyline points="16,9 16,16 21,19" fill="none" stroke="#b53737" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'),
    "ppt":       ("#b87900", "PPT",
        '<rect x="4" y="6" width="24" height="16" rx="2" fill="none" stroke="#b87900" stroke-width="2"/>'
        '<line x1="14" y1="22" x2="14" y2="26" stroke="#b87900" stroke-width="1.8"/>'
        '<line x1="18" y1="22" x2="18" y2="26" stroke="#b87900" stroke-width="1.8"/>'
        '<line x1="10" y1="26" x2="22" y2="26" stroke="#b87900" stroke-width="1.8" stroke-linecap="round"/>'
        '<polygon points="10,11 10,18 18,14.5" fill="#b87900"/>'),
}


def _doctype_tile_svg(doctype: str) -> str:
    """Render the doc-type tile: an icon + the doctype name + a single-line
    description. Falls back to a neutral block tile for unknown doctypes.
    """
    if doctype in _DOCTYPE_GLYPHS:
        color, abbr, glyph = _DOCTYPE_GLYPHS[doctype]
    else:
        color, abbr, glyph = ("#5a5a5a", "DOC",
            '<rect x="6" y="6" width="20" height="20" rx="2" fill="none" stroke="#5a5a5a" stroke-width="1.8"/>')
    soft_map = {
        "#0f7a83": "#dff3f5", "#2b5fb5": "#e8f0fb",
        "#b53737": "#fbeaea", "#b87900": "#fff4d6",
        "#5a5a5a": "#f0f0ec",
    }
    soft = soft_map.get(color, "#f0f0ec")
    return (
        f'<span class="doctype-tile" style="background:{soft};border-color:{color};color:{color}">'
        f'<svg viewBox="0 0 32 32" width="28" height="28" aria-hidden="true">{glyph}</svg>'
        f'<span class="doctype-text">'
        f'<strong>{_esc(doctype or "(unspecified)")}</strong>'
        f'<span class="doctype-abbr">{abbr}</span>'
        f'</span>'
        f'</span>'
    )


# ── stub-graph SVG (visual DAG) ───────────────────────────────────────────


def _topo_levels(stubs: list) -> dict:
    """Assign each stub a 0-based level = longest path from a root (a stub
    with no dependencies). Bellman-Ford-style relaxation; runs at most
    `len(stubs) + 1` passes and breaks early when stable.

    Does **not** detect cycles — the caller is expected to validate
    declared-id consistency separately (see `_assert_declared_deps`).
    A cyclic graph here will simply hit the iteration cap with inflated
    levels and produce an oversized SVG; callers that care should
    pre-validate before calling this.
    """
    by_id = {s["id"]: s for s in stubs}
    level = {sid: 0 for sid in by_id}
    for _ in range(len(by_id) + 1):
        changed = False
        for sid, stub in by_id.items():
            for dep in (stub.get("dependencies") or []):
                if dep in by_id:
                    new_level = level[dep] + 1
                    if new_level > level[sid]:
                        level[sid] = new_level
                        changed = True
        if not changed:
            break
    return level


def _assert_declared_deps(stubs: list) -> None:
    """Raise ValueError if any stub depends on an id that is not declared.
    Mirrors the validation `render_mmd` performs inline — extracted so the
    HTML path can call it too (fixes round-3 F-B: the HTML preview used to
    silently drop undeclared edges that the .mmd path failed loudly on).
    """
    declared_ids = {s["id"] for s in stubs}
    unresolved: list = []
    for stub in stubs:
        sid = stub["id"]
        for dep in (stub.get("dependencies") or []):
            if dep not in declared_ids:
                unresolved.append((sid, dep))
    if unresolved:
        details = "; ".join(
            f"stub `{s}` -> undeclared `{d}`" for s, d in unresolved
        )
        raise ValueError(f"undeclared dependencies in state: {details}")


def _stub_dag_svg(stubs: list) -> str:
    """Render a layered SVG DAG of the doc stubs. Nodes are placed by
    longest-path-from-root level; within each level they spread
    horizontally. Edges are drawn as cubic Bezier curves for legibility
    when they cross levels. Inline only — no JS, no external assets.
    """
    if not stubs:
        return ('<div class="empty-dag">(no stubs declared)</div>')

    levels = _topo_levels(stubs)
    by_level: dict = {}
    for sid, lvl in levels.items():
        by_level.setdefault(lvl, []).append(sid)
    for lvl in by_level:
        by_level[lvl].sort()

    max_per_level = max(len(v) for v in by_level.values())
    n_levels = max(levels.values()) + 1

    width = 880
    node_w = 168
    node_h = 44
    level_y_gap = 90
    height = max(200, level_y_gap * n_levels + 60)
    top_margin = 30

    # x position per node: spread evenly within level
    pos: dict = {}
    for lvl, ids in by_level.items():
        n = len(ids)
        # spread n nodes across `width`. Centered.
        if n == 1:
            xs = [(width - node_w) / 2]
        else:
            avail = width - node_w
            step = avail / (n - 1)
            xs = [i * step for i in range(n)]
        y = top_margin + lvl * level_y_gap
        for sid, x in zip(ids, xs):
            pos[sid] = (x, y)

    # `s.get("title", s["id"])` returns None when title is *present but null*;
    # `or s["id"]` covers that case (fixes round-3 F-G title:null crash).
    id_to_title = {s["id"]: (s.get("title") or s["id"]) for s in stubs}

    parts = [
        f'<svg class="stub-dag" viewBox="0 0 {width} {int(height)}" '
        f'preserveAspectRatio="xMidYMid meet" role="img" '
        f'aria-label="Document stub dependency graph">'
    ]
    # arrowhead marker (one per svg)
    parts.append(
        '<defs>'
        '<marker id="dag-arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        '<path d="M0,0 L10,5 L0,10 Z" fill="#888"/>'
        '</marker>'
        '</defs>'
    )

    # edges first (so nodes overdraw their endpoints cleanly)
    for stub in stubs:
        sid = stub["id"]
        for dep in (stub.get("dependencies") or []):
            if dep not in pos:
                continue
            sx, sy = pos[dep]
            tx, ty = pos[sid]
            # source bottom-center → target top-center; cubic bezier
            sx0 = sx + node_w / 2
            sy0 = sy + node_h
            tx0 = tx + node_w / 2
            ty0 = ty
            cy_off = max(20, (ty0 - sy0) / 2)
            d = (
                f"M {sx0:.1f},{sy0:.1f} "
                f"C {sx0:.1f},{sy0 + cy_off:.1f} "
                f"{tx0:.1f},{ty0 - cy_off:.1f} "
                f"{tx0:.1f},{ty0:.1f}"
            )
            parts.append(
                f'<path d="{d}" fill="none" stroke="#888" stroke-width="1.5" '
                f'marker-end="url(#dag-arrow)" opacity="0.75"/>'
            )

    # nodes
    for sid, (x, y) in pos.items():
        title = id_to_title.get(sid, sid)
        # color = level color from a small palette (cycled)
        palette = ["#2b5fb5", "#0f7a83", "#7a3fb5", "#b87900", "#b53737", "#2f7c4f"]
        lvl = levels[sid]
        color = palette[lvl % len(palette)]
        soft_map = {
            "#2b5fb5": "#e8f0fb", "#0f7a83": "#dff3f5", "#7a3fb5": "#f1e8fb",
            "#b87900": "#fff4d6", "#b53737": "#fbeaea", "#2f7c4f": "#e6f4ec",
        }
        soft = soft_map[color]
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{node_w}" height="{node_h}" '
            f'rx="6" fill="{soft}" stroke="{color}" stroke-width="1.6"/>'
        )
        # stub id (smaller, top)
        parts.append(
            f'<text x="{x + 10:.1f}" y="{y + 14:.1f}" font-size="10" '
            f'font-weight="600" fill="{color}" letter-spacing="0.04em" '
            f'font-family="ui-monospace, SFMono-Regular, monospace">'
            f'{_esc(sid)[:24]}</text>'
        )
        # title (larger, wrapped to one line, truncated)
        short_title = title if len(title) <= 24 else (title[:22] + "…")
        parts.append(
            f'<text x="{x + 10:.1f}" y="{y + 32:.1f}" font-size="12.5" '
            f'fill="#1a1a1a" '
            f'font-family="-apple-system, system-ui, sans-serif">'
            f'{_esc(short_title)}</text>'
        )

    parts.append('</svg>')
    return "".join(parts)


def _lang_for(language) -> str:
    """Fallback chain matches the other 4 chain renderers: None / empty /
    'korean' / 'ko' / 'kr' → 'ko'; anything else → 'en'. Fixes round-3 F-C
    where document-planner ignored state['language'] entirely and emitted
    English chrome even when other chain artifacts were Korean.
    """
    raw = str(language or "").strip().lower()
    if raw == "" or raw in ("korean", "ko", "kr"):
        return "ko"
    return "en"


def render_html(state: dict) -> str:
    slug = state.get("intent_slug", "")
    doctype = state.get("doctype", "")
    stubs = state.get("stubs", []) or []
    safe_slug = _esc(slug)
    safe_doctype = _esc(doctype)
    lang = _lang_for(state.get("language"))

    # Fail loudly on undeclared dependencies — same contract render_mmd
    # uses, so the HTML preview can't hide the very error the .mmd path
    # would surface (fixes round-3 F-B).
    _assert_declared_deps(stubs)

    # stat tape: counts. Empty categories render muted.
    n_stubs = len(stubs)
    n_edges = sum(len(s.get("dependencies", []) or []) for s in stubs)
    declared_ids = {s["id"] for s in stubs}
    n_orphan = sum(1 for s in stubs if not (s.get("dependencies") or []))
    referenced_ids: set = set()
    for s in stubs:
        for d in s.get("dependencies", []) or []:
            referenced_ids.add(d)
    n_leaf = sum(1 for s in stubs if s["id"] not in referenced_ids)
    stat_tuples = [
        (n_stubs,  "Stubs",       "스텁",       "#2b5fb5"),
        (n_edges,  "Edges",       "의존성",     "#0f7a83"),
        (n_orphan, "Roots",       "루트",       "#2f7c4f"),
        (n_leaf,   "Leaves",      "리프",       "#b87900"),
    ]

    # textual stub table (kept as a low-bandwidth fallback below the SVG DAG)
    rows = []
    for stub in stubs:
        sid = _esc(stub.get("id", ""))
        title = _esc(stub.get("title", ""))
        deps = ", ".join(_esc(d) for d in stub.get("dependencies", []) or [])
        rows.append(f"<tr><td><code>{sid}</code></td><td>{title}</td><td>{deps}</td></tr>")
    table_body = "\n".join(rows) if rows else (
        "<tr><td colspan='3'><em>(no stubs declared)</em></td></tr>"
    )

    style = """
body { font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", Roboto, sans-serif; max-width: 920px; margin: 0 auto; padding: 36px 32px 60px; color: #1a1a1a; background: #f7f7f5; }
h1 { font-size: 22px; font-weight: 600; border-bottom: 1px solid #e0e0dc; padding-bottom: 14px; margin: 0 0 24px; }
h1 .slug { color: #2b5fb5; }
h2 { font-size: 14px; font-weight: 700; letter-spacing: 0.03em; text-transform: uppercase; color: #888; margin: 28px 0 12px; }
.card { background: #fff; border: 1px solid #e0e0dc; border-radius: 8px; padding: 18px 22px; margin-bottom: 22px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
.pipeline-wrap { margin: 0 0 18px; }
.pipeline-svg { width: 100%; height: auto; max-height: 76px; display: block; }
.stat-tape-wrap { background: #fff; border: 1px solid #e0e0dc; border-radius: 8px; padding: 8px 6px; margin-bottom: 22px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
.stat-tape { width: 100%; height: auto; max-height: 64px; display: block; }
.doctype-row { display: flex; align-items: center; gap: 12px; margin-bottom: 22px; flex-wrap: wrap; }
.doctype-tile { display: inline-flex; align-items: center; gap: 10px; padding: 8px 14px 8px 10px; border: 1px solid; border-radius: 8px; font-size: 13px; }
.doctype-tile svg { flex: 0 0 28px; }
.doctype-tile .doctype-text { display: flex; flex-direction: column; line-height: 1.15; }
.doctype-tile .doctype-text strong { font-size: 14px; font-weight: 700; letter-spacing: 0.02em; }
.doctype-tile .doctype-abbr { font-size: 10px; opacity: 0.65; letter-spacing: 0.1em; font-weight: 600; text-transform: uppercase; }
.stub-dag { width: 100%; height: auto; display: block; }
.empty-dag { color: #888; font-style: italic; padding: 32px; text-align: center; }
table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
th, td { border-bottom: 1px solid #ececec; padding: 8px 10px; text-align: left; vertical-align: top; }
th { background: #f9f9f7; font-size: 11px; letter-spacing: 0.04em; text-transform: uppercase; color: #666; }
code { background: #f0f0ec; padding: 1px 5px; border-radius: 3px; font: 13px ui-monospace, SFMono-Regular, monospace; }
@media print { body { background: #fff; } .card { box-shadow: none; page-break-inside: avoid; } }
"""

    # Localized section/footer labels mirroring the other 4 renderers.
    L = {
        "title":      ("Document structure" if lang == "en" else "문서 구조"),
        "graph_h":    ("Stub dependency graph" if lang == "en" else "스텁 의존성 그래프"),
        "table_h":    ("Stub table" if lang == "en" else "스텁 표"),
        "col_id":     ("id" if lang == "en" else "ID"),
        "col_title":  ("title" if lang == "en" else "제목"),
        "col_deps":   ("dependencies" if lang == "en" else "의존성"),
        "no_stubs":   ("(no stubs declared)" if lang == "en" else "(선언된 스텁이 없음)"),
    }
    # rebuild table header / empty-row text with localized labels
    table_body = "\n".join(rows) if rows else (
        f"<tr><td colspan='3'><em>{_esc(L['no_stubs'])}</em></td></tr>"
    )
    return (
        "<!DOCTYPE html>\n"
        f"<html lang='{lang}'><head><meta charset='utf-8'>\n"
        f"<title>{_esc(L['title'])} — {safe_slug}</title>\n"
        f"<style>{style}</style>\n"
        "</head><body>\n"
        f'<div class="pipeline-wrap">{pipeline_breadcrumb_svg("docstub", lang)}</div>\n'
        f'<h1>{_esc(L["title"])} — <span class="slug">{safe_slug or "(unnamed)"}</span></h1>\n'
        f'<div class="doctype-row">{_doctype_tile_svg(doctype)}</div>\n'
        f'<div class="stat-tape-wrap">{stat_tape_svg(stat_tuples, lang)}</div>\n'
        f'<h2>{_esc(L["graph_h"])}</h2>\n'
        f'<section class="card">{_stub_dag_svg(stubs)}</section>\n'
        f'<h2>{_esc(L["table_h"])}</h2>\n'
        '<section class="card">\n'
        f'<table><thead><tr><th>{_esc(L["col_id"])}</th><th>{_esc(L["col_title"])}</th><th>{_esc(L["col_deps"])}</th></tr></thead>\n'
        f"<tbody>\n{table_body}\n</tbody></table>\n"
        '</section>\n'
        "</body></html>\n"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("state_file", help="path to .document-planner-state.json")
    parser.add_argument(
        "--format",
        choices=("mmd", "html"),
        required=True,
        help="output format",
    )
    args = parser.parse_args(argv[1:])

    state_path = Path(args.state_file)
    if not state_path.is_file():
        sys.stderr.write(f"not a file: {state_path}\n")
        return 2

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"cannot parse {state_path}: {e}\n")
        return 2

    try:
        if args.format == "mmd":
            sys.stdout.write(render_mmd(state))
        else:
            sys.stdout.write(render_html(state))
    except ValueError as e:
        sys.stderr.write(f"render_doc_structure: FAIL — {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
