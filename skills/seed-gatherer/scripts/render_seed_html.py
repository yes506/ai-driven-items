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
        "source_label":      "Source",
        "extracted_label":   "Extracted content (intent-filtered)",
        "rationale_label":   "Relevance rationale",
        "extracted_at_label": "Extracted at:",
        "seed_run_label":    "Seed run:",
        "empty_extract":     "(no content extracted)",
        "empty_rationale":   "(no rationale recorded)",
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
        "source_label":      "출처",
        "extracted_label":   "추출 내용 (의도 기반 필터링)",
        "rationale_label":   "관련성 설명",
        "extracted_at_label": "추출 시각:",
        "seed_run_label":    "시드 런:",
        "empty_extract":     "(추출된 내용 없음)",
        "empty_rationale":   "(설명이 기록되지 않음)",
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


def _type_label(rtype: str, t: dict) -> str:
    return t.get(f"type_{rtype}", rtype or "?")


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
    rtype = (match.get("type") or "").lower()

    replacements = {
        "HTML_LANG":             _esc(t["html_lang"]),
        "T_TITLE_PREFIX":        _esc(t["title_prefix"]),
        "T_TYPE_LABEL":          _esc(_type_label(rtype, t)),
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
        "RATIONALE_BLOCK":       _rationale_block(match, t),
    }
    out = _render_template(template, replacements)

    sys.stdout.write(out)
    if not out.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
