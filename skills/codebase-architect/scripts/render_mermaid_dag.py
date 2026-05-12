#!/usr/bin/env python3
"""Render a Mermaid DAG from .architect-state.json.

Reads the state file (path arg) and emits a Mermaid `graph LR` block to stdout.
Edges come from each interface's methods' `collaborators` field if present in
the state; otherwise just nodes are emitted.

Read-only: writes only to stdout. Caller redirects with `> architecture.mmd`.
"""

import json
import sys
from pathlib import Path


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name) or "node"


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("usage: render_mermaid_dag.py <path-to-.architect-state.json>\n")
        return 2

    state_path = Path(sys.argv[1])
    if not state_path.is_file():
        sys.stderr.write(f"state file not found: {state_path}\n")
        return 2

    state = json.loads(state_path.read_text(encoding="utf-8"))
    interfaces = state.get("interfaces") or []

    print("graph LR")
    if not interfaces:
        print('  empty["(no interfaces emitted yet)"]')
        return 0

    seen_edges: set = set()
    for iface in interfaces:
        name = iface.get("name", "?")
        node_id = _safe(name)
        print(f'  {node_id}["{name}"]')
        for method in iface.get("methods") or []:
            for collab in method.get("collaborators") or []:
                target = collab.split(".", 1)[0]
                target_id = _safe(target)
                edge = (node_id, target_id)
                if edge in seen_edges or target_id == node_id:
                    continue
                seen_edges.add(edge)
                print(f"  {node_id} --> {target_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
