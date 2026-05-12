# Enrich a Google search record into an Obsidian-compatible note

You are given a Google Search activity record. Produce a Markdown note that
preserves the original search and appends complementary research.

## Rules

1. Preserve the **original search** verbatim — query text and timestamp are
   load-bearing.
2. Use the WebSearch tool to gather 1–3 reliable sources for complementary
   research. Skip sources that look unreliable (content farms, AI-generated SEO
   spam, expired domains).
3. The complementary research must add value beyond what's in the query:
   definitions, key concepts, common pitfalls, or a one-paragraph synthesis.
   Do NOT just restate the query.
4. If the search is too vague to enrich confidently (e.g. a navigation query
   like "facebook"), produce a short note with the original search only and
   skip enrichment. Mark `enrichment: skipped` in frontmatter.
5. Use Obsidian-friendly formatting: YAML frontmatter, headings, `[[wikilinks]]`
   only when you're sure the linked note exists in this vault.
6. **YAML escaping** — the `query:` field can contain arbitrary user text
   including double quotes, single quotes, colons, and `#`. Use YAML
   single-quoted scalars and double any inner single quotes
   (`query: 'she said ''hi'''`). If the query contains a newline, use the
   literal block form (`query: |` followed by an indented next line).
   Never paste the raw query into a double-quoted scalar without escaping.

## Output template

```markdown
---
date: <ISO datetime of the search>
source: google-search
category: <Category from classify step>
query: '<original query text — single-quoted, inner single quotes doubled>'
tags: [search, <category-lower>, <1-3 topical tags>]
enrichment: <complete | skipped>
---

## Original search
- **Query**: <query>
- **Time**: <ISO datetime>
- **Result clicked**: <titleUrl if present, otherwise "n/a">

## Complementary research
<Claude's enriched explanation. Aim for 100–300 words. Avoid filler.>

## Sources
- [<title>](<url>)
- [<title>](<url>)
```

## Filename

`<YYYY-MM-DD>-<slug>.md` where `<slug>` is the query text lowercased,
non-alphanumerics replaced by `-`, truncated to 60 chars. If a file with that
name already exists, append `-2`, `-3`, etc.
