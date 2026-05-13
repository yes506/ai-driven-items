# Classify a Google search record into an Obsidian category folder

You are given a single Google Search activity record (JSON). Decide which Obsidian
category folder under `<Vault>/Search/` it should live in.

## Rules

1. List the existing folders under `<Vault>/Search/` (excluding `_inbox`). These are
   your candidate categories.
2. If one clearly fits, reuse it. Otherwise, propose a new TitleCase single-word
   category (e.g. `Tech`, `Cooking`, `Travel`, `Finance`, `Health`, `Korean`,
   `Personal`).
3. Do NOT create a category for a one-off search — prefer to reuse a broader
   existing one.
4. Output exactly: `category: <Name>` on a single line. Nothing else.

## Input

A JSON object emitted by Stage 1 with exactly these fields: `title` (the
search query prefixed by "Searched for "), `titleUrl` (the visit URL), `time`
(ISO timestamp), `query` (the bare query text), `page_title`, `source` (one
of `keyword_search_terms` or `urls_google_search`), and `products`
(`["Search"]`). No other fields are present.

## Examples

Input: `{"title": "Searched for rust async runtime tokio vs async-std", ...}`
Output: `category: Tech`

Input: `{"title": "Searched for 강남 점심 맛집", ...}`
Output: `category: Food`

Input: `{"title": "Searched for symptoms of vitamin D deficiency", ...}`
Output: `category: Health`

(The second example is categorized by *topic* — food / restaurants — not by
the *language* of the query. The query happens to be in Korean, but the
classification rule is about subject matter.)
