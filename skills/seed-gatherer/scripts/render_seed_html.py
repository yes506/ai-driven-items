#!/usr/bin/env python3
"""Render a self-contained HTML verification doc for one seed.

Reads `.seed-state.json` (path arg #1) plus a resource_slug (arg #2),
finds the matching entry in state["resources"], populates the bundled
HTML template (assets/seed-html-template.html), emits HTML to stdout.

The HTML is fully self-contained — no CDN, no external JS. Every
user-supplied value is HTML-escaped before substitution; the template
uses single-pass placeholder substitution to defuse the chained-replace
re-substitution class.

Read-only: writes only to stdout. Caller redirects with
`> seeds/seed.<intent-slug>.<resource-slug>.html` per SKILL.md Phase 5.

Usage:
    render_seed_html.py <path-to-.seed-state.json> <resource_slug>
"""

import html
import json
import re
import sys
from pathlib import Path

# Sibling module — chain visual primitives (pipeline breadcrumb, etc.)
from _chain_visuals import pipeline_breadcrumb_svg


TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "seed-html-template.html"


# Localized chrome strings. Language is read from state["language"] —
# "Korean" / "ko" / "kr" → ko, anything else → en. Body content (extracted
# excerpts, rationale prose) already follows LANGUAGE; this localizes the
# section labels and the lang attr.
STRINGS = {
    "en": {
        "html_lang":         "en",
        "title_prefix":      "Seed",
        "type_web":          "Web",
        "type_youtube":      "YouTube",
        "type_pdf":          "PDF",
        "type_image":        "Image",
        "type_local-doc":    "Local doc",
        "type_local-code":   "Local code",
        "type_ideation":     "Ideation",
        "source_label":      "Source",
        "extracted_label":   "Extracted content (intent-filtered)",
        "feasibility_label": "Feasibility check",
        "rationale_label":   "Relevance rationale",
        "extracted_at_label": "Extracted at:",
        "seed_run_label":    "Seed run:",
        "empty_extract":     "(no content extracted)",
        "empty_rationale":   "(no rationale recorded)",
        "empty_feasibility": "(no feasibility check recorded)",
        "not_recorded":      "(not recorded)",
    },
    "ko": {
        "html_lang":         "ko",
        "title_prefix":      "시드",
        "type_web":          "웹",
        "type_youtube":      "유튜브",
        "type_pdf":          "PDF",
        "type_image":        "이미지",
        "type_local-doc":    "로컬 문서",
        "type_local-code":   "로컬 코드",
        "type_ideation":     "아이디에이션",
        "source_label":      "출처",
        "extracted_label":   "추출 내용 (의도 기반 필터링)",
        "feasibility_label": "타당성 검증",
        "rationale_label":   "관련성 설명",
        "extracted_at_label": "추출 시각:",
        "seed_run_label":    "시드 런:",
        "empty_extract":     "(추출된 내용 없음)",
        "empty_rationale":   "(설명이 기록되지 않음)",
        "empty_feasibility": "(타당성 검증 기록 없음)",
        "not_recorded":      "(기록 없음)",
    },
}


WEB_TYPES = {"web", "youtube"}


def _strings_for(language) -> dict:
    """Return the string table for the given LANGUAGE.

    Fallback chain matches SKILL.md Phase L contract: None / empty / "ko"
    / "kr" / "korean" → Korean (default); anything else → English.
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


# ── markdown-ish to HTML (small, deliberate subset) ──────────────────────


_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_BOLD_RE        = re.compile(r"\*\*([^*\n]+)\*\*")
_ITALIC_RE      = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")


def _inline(text: str) -> str:
    """Escape, then re-introduce inline <code>, <strong>, <em>.

    Order matters: escape first, then apply markdown over the escaped
    text. The markdown delimiters are ASCII (`*`, `` ` ``) which are not
    affected by html.escape, so the regexes still match. The body
    captured by each regex is already HTML-safe because escaping ran
    first.
    """
    out = html.escape(text)
    out = _INLINE_CODE_RE.sub(lambda m: f"<code>{m.group(1)}</code>", out)
    out = _BOLD_RE.sub(lambda m: f"<strong>{m.group(1)}</strong>", out)
    out = _ITALIC_RE.sub(lambda m: f"<em>{m.group(1)}</em>", out)
    return out


def _md_to_html(text: str) -> str:
    """Small markdown subset → HTML for the extracted-content panel.

    Supported:
      - Blockquotes (lines starting with `> `) → <blockquote>
      - Unordered lists (lines starting with `- ` or `* `) → <ul><li>
      - Ordered lists (lines starting with `1. `, `2. `, …) → <ol><li>
      - Paragraph breaks on blank lines
      - Inline: `code`, **bold**, *italic*

    Not supported (intentional — keeps the surface XSS-free and the
    visual hierarchy predictable):
      - Headings (the section is a body, not a doc)
      - Tables, images, raw HTML (XSS surface)
      - Nested lists (rare in seed content; surface as flat)
    """
    if text is None or str(text).strip() == "":
        return ""

    lines = str(text).splitlines()
    blocks = []
    i = 0

    def flush_paragraph(buf):
        if buf:
            joined = " ".join(s.strip() for s in buf if s.strip())
            if joined:
                blocks.append(f"<p>{_inline(joined)}</p>")

    para_buf = []

    while i < len(lines):
        line = lines[i]

        # blank → flush paragraph
        if line.strip() == "":
            flush_paragraph(para_buf)
            para_buf = []
            i += 1
            continue

        # blockquote — gather contiguous `> ` lines
        if line.startswith("> ") or line.rstrip() == ">":
            flush_paragraph(para_buf); para_buf = []
            quote_lines = []
            while i < len(lines) and (lines[i].startswith("> ") or lines[i].rstrip() == ">"):
                quote_lines.append(lines[i][2:] if lines[i].startswith("> ") else "")
                i += 1
            quote_text = " ".join(s.strip() for s in quote_lines if s.strip())
            blocks.append(f"<blockquote><p>{_inline(quote_text)}</p></blockquote>")
            continue

        # unordered list — gather contiguous `- ` / `* ` lines
        if re.match(r"^[-*]\s+", line):
            flush_paragraph(para_buf); para_buf = []
            items = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i]):
                items.append(re.sub(r"^[-*]\s+", "", lines[i]))
                i += 1
            lis = "".join(f"<li>{_inline(it.strip())}</li>" for it in items if it.strip())
            blocks.append(f"<ul>{lis}</ul>")
            continue

        # ordered list — gather contiguous `N. ` lines
        if re.match(r"^\d+\.\s+", line):
            flush_paragraph(para_buf); para_buf = []
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\d+\.\s+", "", lines[i]))
                i += 1
            lis = "".join(f"<li>{_inline(it.strip())}</li>" for it in items if it.strip())
            blocks.append(f"<ol>{lis}</ol>")
            continue

        # plain paragraph line
        para_buf.append(line)
        i += 1

    flush_paragraph(para_buf)
    return "".join(blocks)


# ── block renderers ──────────────────────────────────────────────────────


def _source_block(resource: dict) -> str:
    location = resource.get("location") or ""
    rtype = (resource.get("type") or "").lower()
    safe = _esc(location)
    if not safe:
        return '<div class="source-value placeholder">(no source recorded)</div>'
    # Defense-in-depth: only emit <a href="..."> when the value parses as a
    # safe scheme (http/https, lowercase). A `javascript:`/`data:` URL
    # written into an `href` is a clickable XSS surface — `html.escape`
    # does not touch the colon or the payload. Phase 2 classification
    # (references/resource-extraction.md) is also case-sensitive on
    # `http://` / `https://`; this renderer matches that exactly so the
    # contract is consistent. If the classifier ever widens to accept
    # `HTTPS://` etc., update this check together — the coupling is
    # deliberate, not accidental.
    loc_str = str(location)
    if rtype in WEB_TYPES and (loc_str.startswith("http://") or loc_str.startswith("https://")):
        return f'<a class="source-value" href="{safe}" rel="noopener noreferrer">{safe}</a>'
    return f'<div class="source-value">{safe}</div>'


def _extracted_block(resource: dict, t: dict) -> str:
    body = resource.get("extracted_content")
    rendered = _md_to_html(body)
    if not rendered:
        return f'<p class="placeholder">{_esc(t["empty_extract"])}</p>'
    return rendered


def _rationale_block(resource: dict, t: dict) -> str:
    body = resource.get("relevance_rationale")
    rendered = _md_to_html(body)
    if not rendered:
        return f'<p class="placeholder">{_esc(t["empty_rationale"])}</p>'
    return rendered


def _feasibility_section(resource: dict, t: dict) -> str:
    """Emit the Feasibility check panel for ideation resources only.

    Resource-derived seeds (web/pdf/etc) omit the section entirely —
    returning an empty string collapses the placeholder slot to a no-op.
    Per references/output-schema.md the markdown schema gates the section
    on `type == "ideation"`; the HTML mirrors that gate.
    """
    rtype = (resource.get("type") or "").lower()
    if rtype != "ideation":
        return ""
    body = resource.get("feasibility_check")
    rendered = _md_to_html(body)
    if not rendered:
        rendered = f'<p class="placeholder">{_esc(t["empty_feasibility"])}</p>'
    return (
        '<section class="panel feasibility">'
        f'<h2>{_esc(t["feasibility_label"])}</h2>'
        f'<div class="body">{rendered}</div>'
        '</section>'
    )


def _type_label(rtype: str, t: dict) -> str:
    return t.get(f"type_{rtype}", rtype or "?")


# ── SVG type badge — replaces the text-only type pill ─────────────────────


# Per-resource-type glyph drawn as inline SVG, plus the badge color used for
# the surrounding pill. Glyphs are renderer-defined (no user input flows in
# as coordinates) and the labels pass through _esc(). XSS-safe.
_TYPE_GLYPHS = {
    # web — globe (circle with two intersecting arcs)
    "web": ("#2b5fb5",
        '<circle cx="14" cy="14" r="9.5" fill="none" stroke="#2b5fb5" stroke-width="1.8"/>'
        '<ellipse cx="14" cy="14" rx="4" ry="9.5" fill="none" stroke="#2b5fb5" stroke-width="1.5"/>'
        '<line x1="4.5" y1="14" x2="23.5" y2="14" stroke="#2b5fb5" stroke-width="1.5"/>'),
    # youtube — rounded rect + play triangle
    "youtube": ("#b53737",
        '<rect x="4" y="6.5" width="20" height="15" rx="3" fill="#b53737"/>'
        '<polygon points="12,11 12,17 18,14" fill="#fff"/>'),
    # pdf — page with corner fold + "PDF" lines
    "pdf": ("#b53737",
        '<path d="M6.5 4.5 H17 L21.5 9 V23.5 H6.5 Z" fill="none" stroke="#b53737" stroke-width="1.8" stroke-linejoin="round"/>'
        '<path d="M17 4.5 V9 H21.5" fill="none" stroke="#b53737" stroke-width="1.5" stroke-linejoin="round"/>'
        '<line x1="9.5" y1="14" x2="18" y2="14" stroke="#b53737" stroke-width="1.4"/>'
        '<line x1="9.5" y1="17.5" x2="18" y2="17.5" stroke="#b53737" stroke-width="1.4"/>'
        '<line x1="9.5" y1="21" x2="14.5" y2="21" stroke="#b53737" stroke-width="1.4"/>'),
    # image — frame + sun + mountains
    "image": ("#7a3fb5",
        '<rect x="3.5" y="6" width="21" height="16" rx="2" fill="none" stroke="#7a3fb5" stroke-width="1.8"/>'
        '<circle cx="9" cy="11" r="1.6" fill="#7a3fb5"/>'
        '<polyline points="3.5,20 10,14 14,17 18,12 24.5,20" fill="none" stroke="#7a3fb5" stroke-width="1.5" stroke-linejoin="round"/>'),
    # local-doc — folder with horizontal lines
    "local-doc": ("#b87900",
        '<path d="M3.5 8 V21.5 H24.5 V10 H13 L11 8 Z" fill="none" stroke="#b87900" stroke-width="1.8" stroke-linejoin="round"/>'
        '<line x1="7" y1="14" x2="20" y2="14" stroke="#b87900" stroke-width="1.4"/>'
        '<line x1="7" y1="17.5" x2="17" y2="17.5" stroke="#b87900" stroke-width="1.4"/>'),
    # local-code — angle brackets
    "local-code": ("#0f7a83",
        '<polyline points="9,8 4,14 9,20" fill="none" stroke="#0f7a83" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<polyline points="19,8 24,14 19,20" fill="none" stroke="#0f7a83" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="16" y1="6" x2="12" y2="22" stroke="#0f7a83" stroke-width="1.8" stroke-linecap="round"/>'),
    # ideation — lightbulb
    "ideation": ("#b87900",
        '<path d="M14 4.5 a7 7 0 0 1 4 12.5 V19 H10 V17 a7 7 0 0 1 4 -12.5 Z" fill="none" stroke="#b87900" stroke-width="1.8" stroke-linejoin="round"/>'
        '<line x1="11" y1="21" x2="17" y2="21" stroke="#b87900" stroke-width="1.6" stroke-linecap="round"/>'
        '<line x1="12" y1="23.5" x2="16" y2="23.5" stroke="#b87900" stroke-width="1.6" stroke-linecap="round"/>'),
}


def _type_badge_svg(rtype: str, t: dict) -> str:
    """Render an SVG type badge for one resource. Falls back to a neutral
    block glyph when `rtype` is unknown so the layout never collapses.
    """
    color, glyph = _TYPE_GLYPHS.get(rtype, ("#5a5a5a",
        '<rect x="4" y="4" width="20" height="20" rx="3" fill="none" stroke="#5a5a5a" stroke-width="1.6"/>'))
    soft_map = {
        "#2b5fb5": "#e8f0fb", "#b53737": "#fbeaea", "#7a3fb5": "#f1e8fb",
        "#b87900": "#fff4d6", "#0f7a83": "#dff3f5", "#5a5a5a": "#f0f0ec",
    }
    soft = soft_map.get(color, "#f0f0ec")
    label = _type_label(rtype, t)
    return (
        f'<span class="type-badge" style="background:{soft};border-color:{color};color:{color}">'
        f'<svg viewBox="0 0 28 28" width="22" height="22" aria-hidden="true">{glyph}</svg>'
        f'<strong>{_esc(label)}</strong>'
        f'</span>'
    )


def main() -> int:
    if len(sys.argv) != 3:
        sys.stderr.write("usage: render_seed_html.py <path-to-.seed-state.json> <resource_slug>\n")
        return 2

    state_path = Path(sys.argv[1])
    target_slug = sys.argv[2]

    if not state_path.is_file():
        sys.stderr.write(f"state file not found: {state_path}\n")
        return 2
    if not TEMPLATE_PATH.is_file():
        sys.stderr.write(f"template not found at {TEMPLATE_PATH}\n")
        return 2

    state = json.loads(state_path.read_text(encoding="utf-8"))
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    resources = state.get("resources") or []
    match = next((r for r in resources if r.get("resource_slug") == target_slug), None)
    if match is None:
        sys.stderr.write(f"no resource with resource_slug={target_slug!r} in state file\n")
        return 2

    t = _strings_for(state.get("language"))
    lang = t["html_lang"]  # "ko" or "en"
    rtype = (match.get("type") or "").lower()

    replacements = {
        "HTML_LANG":             _esc(t["html_lang"]),
        "T_TITLE_PREFIX":        _esc(t["title_prefix"]),
        "PIPELINE_SVG":          pipeline_breadcrumb_svg("seed", lang),
        "TYPE_BADGE":            _type_badge_svg(rtype, t),
        "T_SOURCE_LABEL":        _esc(t["source_label"]),
        "T_EXTRACTED_LABEL":     _esc(t["extracted_label"]),
        "T_RATIONALE_LABEL":     _esc(t["rationale_label"]),
        "T_EXTRACTED_AT_LABEL":  _esc(t["extracted_at_label"]),
        "T_SEED_RUN_LABEL":      _esc(t["seed_run_label"]),
        "INTENT_SLUG":           _esc(state.get("intent_slug") or "(unnamed)"),
        "RESOURCE_SLUG":         _esc(match.get("resource_slug") or "(unnamed)"),
        "EXTRACTED_AT":          _esc(match.get("extracted_at") or t["not_recorded"]),
        "SEED_RUN_ID":           _esc(state.get("seed_run_id") or t["not_recorded"]),
        "SOURCE_BLOCK":          _source_block(match),
        "EXTRACTED_BLOCK":       _extracted_block(match, t),
        "FEASIBILITY_SECTION":   _feasibility_section(match, t),
        "RATIONALE_BLOCK":       _rationale_block(match, t),
    }
    out = _render_template(template, replacements)

    sys.stdout.write(out)
    if not out.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
