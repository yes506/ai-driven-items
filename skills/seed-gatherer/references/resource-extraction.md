# Resource extraction

Phase 3 takes the in-memory `RESOURCES` list (built up at Phase 2) and,
for each entry, fetches the underlying content and produces an
intent-filtered summary that becomes the body of the seed.

## Resource type classification (Phase 2)

When the user pastes a resource in Phase 2, classify it before
echoing back:

| Signal in user's input | `type` |
|---|---|
| Host portion matches `(www\|m\|music)?\.?youtube\.com` or `youtu\.be` over either `http://` or `https://` | `youtube` |
| Starts with `http://` or `https://` (and not YouTube) | `web` |
| Absolute path ending in `.pdf` (case-insensitive) | `pdf` |
| Absolute path ending in `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp` (case-insensitive) | `image` |
| Absolute path ending in `.md`, `.txt`, `.rst`, `.adoc`, `.org` | `local-doc` |
| Absolute path ending in a recognized source-code extension (`.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.java`, `.kt`, `.go`, `.rs`, `.rb`, `.cs`, `.cpp`, `.c`, `.h`, `.swift`, `.scala`, `.sh`, etc.) | `local-code` |
| Anything else | refuse with "I'm not sure how to handle `<input>` — please provide a URL or absolute file path with a recognized extension. Supported types: web URL, YouTube URL, PDF, image, local doc (md/txt/rst), local code." |

Relative paths are explicitly refused — they're ambiguous depending
on the agent's cwd. Ask the user to provide an absolute path.

### Canonicalization at intake

Before echoing, canonicalize the value so that the slug derivation
and the rendered `Source` field both see the same string downstream:

- `youtube`: rewrite to the canonical
  `https://www.youtube.com/watch?v=<ID>` form (even if the user
  pasted `youtu.be/<ID>` or `m.youtube.com/watch?v=<ID>`). Extract
  the video ID per [seed-naming.md#youtube--slug](seed-naming.md).
- `web`: leave verbatim (no normalization — different paths /
  query-strings legitimately represent different pages).
- Local paths: leave verbatim (already absolute by Phase 2's refusal
  rule for relative paths).

Then echo: *"Recognized as `<type>`: `<canonical-location>`. Add
another, or type `done` when finished."*

## Extraction strategy per type

| Type | Tool | Notes |
|---|---|---|
| `web` | `WebFetch` | Pass the URL + a prompt like "Extract content relevant to the following intent: <Goal>. Focus on: <In-scope>. Exclude: <Out-of-scope>." Honor the tool's content limits — if the page is huge, accept truncation; do NOT loop additional fetches. |
| `youtube` | `yt-dlp` (soft dep) | Run `yt-dlp --skip-download --write-auto-sub --sub-lang en --sub-format vtt -o '%(id)s.%(ext)s' <url>` into a temp dir under `/tmp` (use `mktemp -d` and `trap 'rm -rf "$TMP"' EXIT` so the dir is cleaned up regardless of success or failure). Parse the resulting `.vtt` to plain text in memory, then discard the temp dir. **These temp files are the only on-disk artifacts Phase 3 produces; they live outside `MAIN_CHECKOUT` so the "Phase 4 is the first repo/git mutation" rule still holds.** If `yt-dlp` is not on `$PATH`, set `status="skipped-no-ytdlp"` and surface a message (see below). |
| `pdf` | `Read` with `pages` | Read the PDF in batches (≤20 pages per call per the Read tool contract). If the PDF is >20 pages, ask the user which page range matters most for this intent, or accept reading the first 20 with a note in the rationale. |
| `image` | `Read` (vision) | Read the image and describe what's in it through the lens of the intent. Treat it as a fact source (e.g., a screenshot of an error message, a hand-drawn diagram, a UI mockup). The "extracted content" is the agent's vision-based description, not the binary itself. |
| `local-doc` | `Read` | Standard text read. For large files, accept the default 2000-line cap unless the user specified an offset/range in Phase 2. |
| `local-code` | `Read` | Same as `local-doc`. The "extracted content" should be a structural summary + the few specific snippets that bear on the intent, not the whole file. |

## Soft-dependency handling (`yt-dlp` missing)

When `yt-dlp` is not on `$PATH`:

1. Set `resources[i].status="skipped-no-ytdlp"`.
2. Surface a message in chat (language follows `LANGUAGE`):
   - English: *"Couldn't extract YouTube content from `<url>` — `yt-dlp` is not installed. Install it with `pip install yt-dlp` or `brew install yt-dlp`, then re-run `/seed-gatherer` to include this resource. Continuing with the remaining resources."*
   - Korean: *"`<url>`의 YouTube 콘텐츠를 추출할 수 없습니다 — `yt-dlp`가 설치되어 있지 않습니다. `pip install yt-dlp` 또는 `brew install yt-dlp`로 설치한 후 `/seed-gatherer`을 다시 실행하면 이 리소스를 포함할 수 있습니다. 남은 리소스로 계속 진행합니다."*
3. Continue with the other resources. The skipped resource is recorded
   in the state file but no `seed.*.md` is emitted for it.

The same shape applies to any other soft-dep that may exist in the
future (e.g. a hypothetical `pdftotext` fallback). The principle:
never fail the whole run on a single missing optional tool.

## Failure handling (WebFetch error, file-not-found, etc.)

| Failure | Status | Behavior |
|---|---|---|
| `WebFetch` returns 404 / 410 / DNS failure | `skipped-fetch-failed` | Surface the error + URL; continue with remaining resources |
| `WebFetch` returns paywall / login-required content (detected by very-short content + auth-related keywords) | `skipped-fetch-failed` | Surface "looks gated — `WebFetch` saw `<excerpt>`; the source likely requires login. Skipping; you can paste the relevant excerpt directly if you have access." |
| Local file doesn't exist or unreadable | `skipped-fetch-failed` | Surface "file not found at `<path>` — check the path and re-add if needed. Continuing." |
| `yt-dlp` runs but produces empty transcript (no auto-captions, no manual subs) | `skipped-fetch-failed` | Surface "no transcript available for `<url>`. YouTube auto-captions may be disabled. Skipping." |
| PDF is encrypted / password-protected | `skipped-fetch-failed` | Surface "PDF is encrypted — decrypt it first, then re-add." |

In **every** failure case: surface the issue immediately, mark the
resource as skipped, continue with the rest. Never auto-retry —
retries hide root causes and inflate context usage.

## What "intent-filtered" means

The extracted content is NOT a summary of the resource — it is an
**intent-filtered extract**: the subset of the resource that bears on
the user's `intent` (Goal, In-scope features, Out-of-scope,
Constraints, Success criteria, Open questions).

Concretely:

- **Drop content unrelated to the intent.** A 5,000-word web article
  about "Next.js performance" should yield maybe 200–500 words of
  extract if the intent is narrowly about caching headers; everything
  about images / fonts / bundle splitting goes in the trash.
- **Prefer quotes over paraphrase for facts.** When the resource
  states a concrete fact, claim, version number, API signature, or
  cited number, quote it verbatim — paraphrasing introduces drift.
  Use markdown blockquote (`> `) so the seed file makes the boundary
  visible.
- **Paraphrase contextual prose.** When the source is wordy prose
  *about* a fact, paraphrase compactly. Don't blockquote a paragraph
  to say "the article generally agrees with X."
- **Drop content that contradicts Out-of-scope.** If a resource
  advocates for a feature the user explicitly said is out of scope,
  the relevant detail belongs in `relevance_rationale` as a flag
  ("this resource pushes feature Y which the intent excludes — likely
  not directly useful, but the underlying argument about Z might
  inform Constraint C"), not in `extracted_content`.
- **Promote contradictions of Constraints to open-question signal.**
  If a resource contradicts a stated constraint, the rationale should
  flag it loudly so plan-establisher knows to resolve.

The judgement call is: *would the downstream planner be glad this
content was preserved when reading this seed, or would they wish I'd
been more selective?* Lean selective.

## Per-resource synthesis preview (Phase 3 in-chat)

For each resource (in order), render a preview block in chat. Example
(English; mirror for Korean):

```
Resource 2 of 4 — web
URL: https://nextjs.org/docs/app/building-your-application/caching
Resource slug: nextjs-caching-docs

Extracted content (intent-filtered):
  > "The Next.js cache is a persistent HTTP cache that can be shared across regions."
  Key claim: opt-out via `cache: 'no-store'` on individual fetches.
  Pricing/billing implications: none mentioned.
  Sections dropped: ISR detail (out-of-scope per intent), Image caching (out-of-scope).

Relevance rationale:
  Directly informs Goal ("predictable dashboard latency") and Constraint
  ("must work behind our CloudFront layer"). The opt-out mechanism is the
  immediate plan signal — without it the user's "stale-data risk" success
  criterion can't be satisfied.

Type `next` to preview the next resource, `redo <n>` to re-extract resource N,
`drop <n>` to remove resource N, or `confirm seeds` to lock all 4 and emit.
```

The user iterates through the previews. `confirm seeds` is the gate —
silence is not yes. The state file is NOT yet written; everything is
in memory.

## Portability (non-Claude AI tools)

This skill is shipped for Claude Code. When porting to Codex CLI,
Gemini CLI, or another tool, the following Claude-native references
need substitution:

| Reference in this skill | Substitute with the host tool's equivalent |
|---|---|
| `WebFetch` tool | The tool's URL-fetcher (Codex `web_fetch`, Gemini's web tool, etc.) |
| `Read` tool with `pages:` for PDF | The tool's PDF reader or a `pdftotext` shell-out |
| `Read` tool for image (vision) | The tool's vision-capable file reader; if none, refuse `image` resources |
| `Read` tool for text/code | Any text reader (`cat`, the tool's `read_file`, etc.) |
| `Write` tool | The tool's file writer or a `cat > path << 'EOF'` heredoc |
| `${CLAUDE_SKILL_DIR}` | Absolute path to the installed skill directory |
| The skill's classifier expects vision for `image` | If unavailable, treat `image` as unsupported |

The rest of the skill (worktree flow, gate tokens, state file,
HTML renderer) is shell + Python and works unchanged across tools.

## Phase 3 work is lost if Phase 4 fails (known asymmetry)

Phase 3 finishes in memory; the first state-file write is Phase 4
step 4. If Phase 4 fails (dirty `BASE_BRANCH`, path collision, etc.),
the user's confirmed extraction work is lost — they have to re-paste
resources and let Phase 3 re-run, which may repeat slow `WebFetch`
calls.

This is a design choice (not a bug): the worktree's `.seed-state.json`
is the *only* state-file location, and the worktree doesn't exist
until Phase 4. Writing a transient pending-state at `MAIN_CHECKOUT`
would introduce a second state-file location to clean up. The asymmetry
is documented for visibility; in practice Phase 4 failures are rare
(BASE_BRANCH is usually clean since the user just confirmed seeds and
hasn't touched anything).

## Honest limitations

- `WebFetch` has its own content size limits; the extract reflects
  what it returned, not the full page. Long resources may be
  silently truncated by the tool.
- YouTube transcripts via auto-captions are noisy and lack
  punctuation. The extraction should account for this — quoting raw
  caption text is usually a mistake; paraphrase the *meaning* and
  cite the timestamp range.
- PDFs with scanned (image-only) pages can't be extracted without
  OCR; the Read tool surfaces this. Treat as `skipped-fetch-failed`.
- Image extraction relies on Claude's vision capability and works
  best for diagrams, screenshots, and text-heavy images. Photographs
  of physical objects may yield a description but rarely useful
  intent-bearing content.
- The "intent-filtered" judgement is the agent's; a human reviewer
  may legitimately disagree. The Phase 3 preview-and-confirm step is
  the safety net.
