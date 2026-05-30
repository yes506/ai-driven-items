"""Shared visual primitives for the 5-stage chain HTML outputs.

Used by:
    intent-aligner / seed-gatherer / plan-establisher / document-planner /
    codebase-planner

This file is **duplicated identically** into each of the five skills'
scripts/ directories. The duplication is intentional — per the repo's
"skills are self-contained" rule (see ai-driven-items/CLAUDE.md), skills
do not import from sibling skills. If you change this file in one skill,
sync the change into the other four.

Defines the ubiquitous-language vocabulary documented in each skill's
references/visual-language.md:
- 5 stages: intent / seed / plan / docstub / interface
- Per-stage glyph (diamond / circle / triangle / page / block)
- Per-stage primary color + soft bg
- Pipeline breadcrumb SVG (current stage highlighted)
- Stat-tape SVG (at-a-glance counts)

XSS-safety: every user-supplied value passes through _esc() before being
interpolated into SVG `<text>` content. Renderer-controlled values
(coordinates, colors from the stage palette) are not escaped — they are
not user-supplied.
"""

import html


# (stage_key, label_en, label_ko, primary_color, soft_bg)
STAGES = [
    ("intent",    "Intent",    "의도",       "#2b5fb5", "#e8f0fb"),
    ("seed",      "Seed",      "씨앗",       "#2f7c4f", "#e6f4ec"),
    ("plan",      "Plan",      "계획",       "#7a3fb5", "#f1e8fb"),
    ("docstub",   "Doc Stub",  "문서 골격",  "#b87900", "#fff4d6"),
    ("interface", "Interface", "인터페이스", "#0f7a83", "#dff3f5"),
]


def _esc(value) -> str:
    """html.escape that tolerates non-string input (None, ints, etc.)."""
    if value is None:
        return ""
    return html.escape(str(value))


def stage_glyph_svg(stage_key: str, color: str, active: bool, cx: int, cy: int, r: int = 14) -> str:
    """Inline SVG glyph for one stage. Shape varies per stage; fill follows
    `active` (filled when current, outline when other). Coordinates are
    renderer-controlled — no user input flows in as numbers.
    """
    fill = color if active else "#fff"
    stroke = color
    sw = 2 if active else 1.5
    if stage_key == "intent":   # ◆ diamond
        pts = f"{cx},{cy-r} {cx+r},{cy} {cx},{cy+r} {cx-r},{cy}"
        return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
    if stage_key == "seed":     # ● circle
        return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
    if stage_key == "plan":     # ▲ triangle
        pts = f"{cx},{cy-r} {cx+r},{cy+r-2} {cx-r},{cy+r-2}"
        return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
    if stage_key == "docstub":  # ▤ page (rect with two horizontal lines)
        inner = "#fff" if active else color
        return (
            f'<rect x="{cx-r}" y="{cy-r+1}" width="{2*r}" height="{2*r-2}" rx="2" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
            f'<line x1="{cx-r+4}" y1="{cy-3}" x2="{cx+r-4}" y2="{cy-3}" '
            f'stroke="{inner}" stroke-width="1.4"/>'
            f'<line x1="{cx-r+4}" y1="{cy+3}" x2="{cx+r-4}" y2="{cy+3}" '
            f'stroke="{inner}" stroke-width="1.4"/>'
        )
    # interface — ◫ block (rect with vertical divider)
    inner = "#fff" if active else color
    return (
        f'<rect x="{cx-r}" y="{cy-r+1}" width="{2*r}" height="{2*r-2}" rx="2" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        f'<line x1="{cx}" y1="{cy-r+3}" x2="{cx}" y2="{cy+r-3}" '
        f'stroke="{inner}" stroke-width="1.4"/>'
    )


def pipeline_breadcrumb_svg(active_key: str, lang: str = "en") -> str:
    """Render the 5-stage pipeline breadcrumb. `active_key` highlights one
    stage (must be one of "intent" / "seed" / "plan" / "docstub" /
    "interface"); the other four render as outline + muted label. Single
    inline `<svg>`, no JS, no external assets.

    `lang` controls label localization: "ko" → Korean, anything else → English.
    """
    width = 880
    height = 76
    n = len(STAGES)
    slot = width // n  # 176
    parts = [
        f'<svg class="pipeline-svg" viewBox="0 0 {width} {height}" '
        f'preserveAspectRatio="xMidYMid meet" role="img" '
        f'aria-label="Pipeline position: {_esc(active_key)}">'
    ]
    # connecting line under all glyphs
    parts.append(
        f'<line x1="{slot//2}" y1="32" x2="{width - slot//2}" y2="32" '
        f'stroke="#d4d4cf" stroke-width="2" stroke-dasharray="4 3"/>'
    )
    for i, (key, lbl_en, lbl_ko, color, _soft) in enumerate(STAGES):
        cx = slot * i + slot // 2
        active = (key == active_key)
        parts.append(stage_glyph_svg(key, color, active, cx, 32))
        label = lbl_ko if lang == "ko" else lbl_en
        text_color = color if active else "#888"
        weight = "600" if active else "400"
        parts.append(
            f'<text x="{cx}" y="62" text-anchor="middle" font-size="12" '
            f'font-weight="{weight}" fill="{text_color}" '
            f'font-family="-apple-system, system-ui, sans-serif">'
            f'{_esc(label)}</text>'
        )
    parts.append('</svg>')
    return "".join(parts)


def stat_tape_svg(stats: list, lang: str = "en") -> str:
    """Render an at-a-glance "stat tape" of count tiles. `stats` is a list
    of (count:int, label_en:str, label_ko:str, color:str). Empty tiles
    (count == 0) render muted so the reviewer sees what is missing.

    Returns "" if `stats` is empty so the caller can omit the wrapper.
    """
    if not stats:
        return ""
    width = 880
    n = len(stats)
    tile_w = width // n
    height = 64
    parts = [
        f'<svg class="stat-tape" viewBox="0 0 {width} {height}" '
        f'preserveAspectRatio="xMidYMid meet" role="img" aria-label="At a glance">'
    ]
    for i, (count, lbl_en, lbl_ko, color) in enumerate(stats):
        x = tile_w * i
        muted = (count == 0)
        num_color = "#bbb" if muted else color
        lbl_color = "#999" if muted else "#5a5a5a"
        if i > 0:
            parts.append(
                f'<line x1="{x}" y1="12" x2="{x}" y2="{height-12}" '
                f'stroke="#e0e0dc" stroke-width="1"/>'
            )
        cx = x + tile_w // 2
        parts.append(
            f'<text x="{cx}" y="32" text-anchor="middle" '
            f'font-size="22" font-weight="700" fill="{num_color}" '
            f'font-family="-apple-system, system-ui, sans-serif">{int(count)}</text>'
        )
        label = lbl_ko if lang == "ko" else lbl_en
        parts.append(
            f'<text x="{cx}" y="52" text-anchor="middle" '
            f'font-size="10.5" letter-spacing="0.05em" '
            f'font-weight="600" fill="{lbl_color}" '
            f'font-family="-apple-system, system-ui, sans-serif">'
            f'{_esc(label.upper())}</text>'
        )
    parts.append('</svg>')
    return "".join(parts)
