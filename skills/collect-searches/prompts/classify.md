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

A JSON object that includes `title` (the search query, prefixed by "Searched for "),
`titleUrl`, `time` (ISO timestamp), and possibly `subtitles` and `details`.

## Examples

Input: `{"title": "Searched for rust async runtime tokio vs async-std", ...}`
Output: `category: Tech`

Input: `{"title": "Searched for 강남 점심 맛집", ...}`
Output: `category: Korean`

Input: `{"title": "Searched for symptoms of vitamin D deficiency", ...}`
Output: `category: Health`
