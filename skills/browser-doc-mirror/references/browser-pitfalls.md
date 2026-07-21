# claude-in-chrome navigation gotchas

Hard-won traps when driving Confluence / wiki UIs through the claude-in-chrome
extension. Read before a mirroring session; they explain most "it didn't move"
and "the table is half empty" failures.

## Navigation

- **Sidebar link click shows only a hover preview.** Clicking a link by its
  `ref` sometimes triggers the hover card instead of navigating. If the page
  does not change, click the link's on-screen `coordinate` directly with
  `computer`.
- **Collapsed subtrees.** A child page's sidebar link may not exist in the DOM
  until its parent is expanded. `navigate` to the parent page first — that
  auto-expands the subtree — then `find` the child link.
- **Enumeration completeness.** Deep trees expand lazily and long sidebars
  virtualize (only on-screen rows are in the DOM). Expand every collapsed node
  and scroll the sidebar to the end before treating the `pending` list as
  complete — otherwise whole branches are silently missed from coverage.
- **Sequence dependent browser actions.** Do NOT put several dependent
  `find`/`navigate` calls in one message. They race and fail intermittently.
  Run them one at a time, checking the result of each before the next.

## Content extraction

- **Lazy-loaded tables truncate.** Long tables and macros render as you scroll.
  If `get_page_text` returns a cut-off table, `computer` scroll down to that
  section and call `get_page_text` again — repeat until the tail renders. Verify
  you reached the end before writing the mirror.
- **Updated date not in body text.** The "Updated/Published" date often lives in
  page chrome (top-right byline), not the body text. If it is absent from
  `get_page_text`, take a `screenshot` (zoom in if needed) and read it visually.
- **Images and diagrams are not text.** Embedded images, Gliffy/draw.io
  diagrams, and attachments do not come through `get_page_text`. Record their
  existence and a filename in a `note` inside the mirror file; never fabricate
  their content.

## Session stability

- **Confirm the session each run.** Call `tabs_context_mcp` at least once per
  session before other browser actions.
- **Flaky extension.** If the extension drops mid-run, re-check with
  `tabs_context_mcp` and resume from the last `synced` manifest row.
- **Never trigger modal dialogs.** JS `alert`/`confirm`/`prompt` dialogs freeze
  the extension and block all further commands. Avoid buttons (Delete, Publish,
  Move) that pop confirmations — this skill is read-only anyway.
