"""Shared interface-graph primitives for codebase-planner renderers.

`render_html_report.py` (inline SVG + embedded Mermaid) and
`render_mermaid_dag.py` (standalone .mmd escape hatch) both need the
exact same id-assignment and edge-collection logic. Keeping them in
sync by copy-paste failed in round 3 — the F-D collision fix landed
in render_html_report.py but the sibling .mmd renderer kept the old
counter-based scheme and continued to emit duplicate ids for
`["Foo", "Foo", "Foo_2"]`. Round-4 R4-1 extracts the helpers here so
both call sites share one source of truth.

The module is local to codebase-planner — interface graphs are this
skill's concern, not a chain-wide vocabulary (those live in
`_chain_visuals.py`).
"""


def safe_id(name: str) -> str:
    """Conservative ASCII identifier from arbitrary text."""
    cleaned = "".join(c if c.isalnum() else "_" for c in str(name))
    return cleaned or "node"


def mermaid_label(name) -> str:
    """Escape a string for safe use as a Mermaid quoted label.

    Mermaid renders `id["LABEL"]` blocks; the label is HTML-decoded by
    the renderer, so we use #-prefixed entity codes (Mermaid's preferred
    form) plus standard HTML entities to neutralize quotes, brackets,
    click directives, newlines, and backticks (Mermaid v10+ alternate
    label delimiter).
    """
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


def build_id_map(interfaces: list) -> dict:
    """Map each unique interface name → a Mermaid-safe unique id.

    Same-name interfaces merge to one node (collaborator references are
    name-based, so two interfaces named `Foo` can't be distinguished as
    edge targets anyway). Returns a dict in iteration order so callers
    can use `.items()` to enumerate the unique node list.

    Collision-resolution: start with `safe_id(name)`, then append `_2`,
    `_3`, … until the candidate is not already taken AND not the base
    form of any *other* literal interface name. Pre-seeding the
    reserved set with every name's `safe_id()` form fixes the F-D edge
    case: `["Foo", "Foo", "Foo_2"]` used to assign id `Foo_2` to both
    the second `Foo` (via collision suffix) AND the literal `Foo_2`.
    """
    unique_names: list = []
    seen_names: set = set()
    for iface in interfaces:
        name = str(iface.get("name", "?"))
        if name not in seen_names:
            seen_names.add(name)
            unique_names.append(name)

    reserved = {safe_id(n) for n in unique_names}

    assigned: dict = {}
    used_ids: set = set()
    for name in unique_names:
        base = safe_id(name)
        if base not in used_ids:
            candidate = base
        else:
            suffix = 2
            candidate = f"{base}_{suffix}"
            while candidate in used_ids or candidate in reserved:
                suffix += 1
                candidate = f"{base}_{suffix}"
        assigned[name] = candidate
        used_ids.add(candidate)
    return assigned


def collect_edges(interfaces: list, name_to_id: dict) -> list:
    """Return the ordered list of (src_id, dst_id) edges that should be
    drawn. Skips: self-loops, edges whose target is not a declared
    interface, and duplicates.

    Single source of truth for `render_mermaid` (.html embed),
    `_render_interface_dag_svg` (inline SVG), the stat-tape edge count
    in render_html_report.py, AND the standalone .mmd output in
    render_mermaid_dag.py.
    """
    edges: list = []
    seen: set = set()
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
                edges.append(edge)
    return edges
