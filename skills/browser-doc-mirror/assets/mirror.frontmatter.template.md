---
title: "<원문 제목 / source page title>"
confluence_id: <숫자 페이지 ID / numeric page ID>
confluence_url: <정규 permalink — 인증코드·세션·추적 파라미터·#fragment 제거
                 / canonical permalink, ephemeral/tracking params stripped>
confluence_version: <원문 버전/리비전 id, 있으면 / source revision id, if any>
author: <작성자 / author, or - if unavailable>
confluence_updated: <YYYY-MM-DD>   # 원문 Updated/Published 날짜 / source date, or -
synced_at: <YYYY-MM-DD>            # 이 파일을 받아온 날짜 / date this body was fetched
status: <WIP|정본|->
parent: <상위 미러 파일 슬러그 / parent mirror slug, if any>
---

<!-- Frontmatter MUST be the first bytes of the file (the --- above is line 1).
     Confluence source → use the confluence_* keys (REQUIRED for Confluence).
     Any other source → replace confluence_id/url/version/updated with
       source_id / source_url / source_revision / source_updated.
     Do NOT mix the two families. Quote free-form values (title, author).
     Freshness lives in the MANIFEST (checked_at column), not here — an unchanged
     page's file is not rewritten, so a per-file checked_at would go stale.
     Prefer the revision id over the date for staleness; if there is no comparable
     revision (a bare date can't prove unchanged), the page is `unknown` → fully
     re-mirror by default. -->


# <원문 제목 / source page title>

<원문 본문을 마크다운으로 충실히 옮긴다: 표, 목록, 코드 블록 유지.
Faithful markdown transcription of the source body: preserve tables, lists,
code blocks.>

<!-- 이미지/다이어그램은 텍스트로 안 잡힘 → 존재 사실과 파일명을 note로 기록:
     Images/diagrams don't come through as text → record existence + filename:
     > note: [diagram] system-topology.png (Gliffy) — 원문에서 확인 -->

---

> 도메인 메모(@handle): <담당 도메인 관점 요약. 원문 미러와 시각적으로 구분되는
> 파생 분석. 재동기화 시 이 블록은 보존한다. / domain note: summary from the
> owning domain's perspective — derived analysis, kept visually distinct from
> the mirrored source. PRESERVE this block across re-syncs.>
