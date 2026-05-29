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


def render_mmd(state: dict) -> str:
    """Render the Mermaid DAG. Raise ValueError on undeclared dependencies
    so bad state is caught at render time, not silently dropped."""
    lines = ["graph TD"]
    stubs = state.get("stubs", [])
    declared_ids = {s["id"] for s in stubs}

    for stub in stubs:
        sid = stub["id"]
        title = stub.get("title", sid)
        safe_title = title.replace('"', "'")
        lines.append(f'  {sid}["{safe_title}"]')

    unresolved: list[tuple[str, str]] = []
    for stub in stubs:
        sid = stub["id"]
        for dep in stub.get("dependencies", []):
            if dep not in declared_ids:
                unresolved.append((sid, dep))
            else:
                lines.append(f"  {dep} --> {sid}")

    if unresolved:
        details = "; ".join(
            f"stub `{s}` -> undeclared `{d}`" for s, d in unresolved
        )
        raise ValueError(f"undeclared dependencies in state: {details}")

    return "\n".join(lines) + "\n"


def render_html(state: dict) -> str:
    slug = html.escape(str(state.get("intent_slug", "")))
    doctype = html.escape(str(state.get("doctype", "")))
    stubs = state.get("stubs", [])

    rows: list[str] = []
    for stub in stubs:
        sid = html.escape(str(stub.get("id", "")))
        title = html.escape(str(stub.get("title", "")))
        deps = ", ".join(html.escape(str(d)) for d in stub.get("dependencies", []))
        rows.append(
            f"<tr><td><code>{sid}</code></td><td>{title}</td><td>{deps}</td></tr>"
        )
    table_body = "\n".join(rows) if rows else (
        "<tr><td colspan='3'><em>(no stubs declared)</em></td></tr>"
    )

    style = (
        "body{font-family:system-ui,sans-serif;max-width:900px;margin:2em auto;"
        "padding:0 1em;color:#222}"
        "h1{border-bottom:1px solid #ccc;padding-bottom:0.3em}"
        "table{border-collapse:collapse;width:100%;margin-top:1em}"
        "th,td{border:1px solid #ddd;padding:0.5em;text-align:left;vertical-align:top}"
        "th{background:#f4f4f4}"
        "code{background:#f4f4f4;padding:0.1em 0.3em;border-radius:3px}"
    )

    return (
        "<!DOCTYPE html>\n"
        "<html lang='en'><head><meta charset='utf-8'>\n"
        f"<title>document-structure — {slug}</title>\n"
        f"<style>{style}</style>\n"
        "</head><body>\n"
        f"<h1>document-structure: {slug}</h1>\n"
        f"<p><strong>DOCTYPE:</strong> <code>{doctype}</code></p>\n"
        "<h2>Stubs</h2>\n"
        "<table><thead><tr><th>id</th><th>title</th><th>dependencies</th></tr></thead>\n"
        f"<tbody>\n{table_body}\n</tbody></table>\n"
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
