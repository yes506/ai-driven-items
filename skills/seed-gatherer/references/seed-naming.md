# Seed naming

Each resource yields one seed pair:
`ai-artifacts/seeds/seed.<intent-slug>.<resource-slug>.md` and
`ai-artifacts/seeds/seed.<intent-slug>.<resource-slug>.html`.

The `<intent-slug>` part is fixed for the run (chosen at Phase 1, see
[intent-loading.md](intent-loading.md)). The `<resource-slug>` part is
derived from the resource's location, per the rules below.

## Resource slug derivation

| Resource type | Slug source | Example |
|---|---|---|
| `web` | host + last meaningful path segment | `https://nextjs.org/docs/app/building-your-application/caching` → `nextjs-caching` |
| `youtube` | host-style prefix + video id | `https://youtu.be/dQw4w9WgXcQ` → `youtube-dqw4w9wgxcq` |
| `pdf` | filename without extension | `/Users/foo/refs/whitepaper-2024.pdf` → `whitepaper-2024` |
| `image` | filename without extension | `/Users/foo/screens/error-toast.png` → `error-toast` |
| `local-doc` | filename without extension | `/path/to/RFC-9728.md` → `rfc-9728` |
| `local-code` | filename including extension (slug-safe) | `/path/to/cache.config.ts` → `cache-config-ts` |
| `ideation` | `idea-` prefix + short keyword phrase from the crystallized idea | crystallized idea "real-time dashboard sync via SSE" → `idea-realtime-sync-sse` |

**Ordering note**: slug derivation runs on the **canonicalized**
location, not the raw user input. Phase 2 canonicalization (see
[resource-extraction.md#canonicalization-at-intake](resource-extraction.md))
rewrites YouTube variants (`youtu.be/<ID>`, `m.youtube.com/...`,
`music.youtube.com/...`) to the
`https://www.youtube.com/watch?v=<ID>` form before slug derivation
sees them. The slug rules below assume that canonical form for
`youtube` resources.

### Web URL → slug

1. Parse the URL: `host` + `path`.
2. Strip `www.` prefix from host. Lowercase.
3. From the path, take the last non-empty segment (ignoring trailing
   slashes and query strings).
4. If that segment is generic (`index`, `index.html`, `index.htm`,
   `default`, `home`, `main`), take the second-to-last segment instead.
5. Combine: `<host-keyword>-<segment>`. The "host-keyword" is the
   second-level domain (e.g., `nextjs` from `nextjs.org`, `github`
   from `github.com`).
6. Sanitize (see below).

If the URL has no meaningful path (`https://example.com/`), use the
host-keyword alone (`example`).

### YouTube → slug

1. Extract the video ID:
   - `youtu.be/<ID>` form → `<ID>`
   - `youtube.com/watch?v=<ID>` form → `<ID>`
   - `youtube.com/shorts/<ID>` form → `<ID>`
2. Lowercase.
3. Prefix with `youtube-`.

If the URL has no recoverable video ID (e.g., a channel URL), refuse at
Phase 2 classification — channels aren't single-resource extractions.

### Local file → slug

1. Take the basename (drop the directory path).
2. For `local-doc`, `pdf`, `image`: drop the extension. For
   `local-code`: convert the extension's `.` to `-` so it's preserved
   in the slug (`cache.config.ts` → `cache-config-ts`); this prevents
   collisions between `cache.config.ts` and `cache.config.js` in the
   same project.
3. Sanitize (see below).

### Ideation → slug

1. Start from the agent's one-sentence description of the
   crystallized idea (the value of `extracted_content` for ideation
   resources).
2. Extract up to 4 keyword tokens — drop stopwords (`a`, `the`, `for`,
   `via`, `with`, etc.), prefer noun + qualifier pairs.
3. Lowercase, hyphen-join the tokens.
4. Prepend `idea-` so the resource_slug is `idea-<keyword-phrase>`.
5. Sanitize (see below).

Example: idea "Real-time dashboard sync via Server-Sent Events" →
keywords `realtime-sync-sse` → resource_slug `idea-realtime-sync-sse`.

If the keyword extraction yields fewer than 2 tokens (degenerate
ideas like "do it"), fall back to `idea-unnamed-<short-rand>` and
surface a note prompting the user to refine.

## Sanitization

After the per-type derivation, apply:

```bash
slug="$(printf '%s' "${raw_slug}" \
  | tr 'A-Z' 'a-z' \
  | tr -cs 'a-z0-9-' '-' \
  | sed -e 's/^-*//' -e 's/-\{2,\}/-/g' -e 's/-*$//' \
  | cut -c1-40)"
```

This:

1. Lowercases.
2. Replaces every non-`[a-z0-9-]` character with `-`.
3. Strips leading dashes (would confuse shell flag parsing if ever
   passed bare to a tool).
4. Collapses consecutive dashes.
5. Strips trailing dashes.
6. Truncates to 40 characters.

If the result is empty (e.g., a URL like `https://example.com/!!!`
where everything got stripped), fall back to:

- `web`: use the host-keyword alone.
- `youtube`: use `youtube-unknown-<short-rand>` and surface a note.
- local files: use `unnamed-<short-rand>` and surface a note.

The short-rand is 4 hex chars from `$RANDOM` so multiple unnamed
falls back don't all collide.

## Collision policy (3-case disambiguation)

A target file `ai-artifacts/seeds/seed.<intent-slug>.<resource-slug>.md` already
existing on disk can mean three different things — and they require
different handling. The discriminators are git-trackedness (was the
file inherited from `${BASE_BRANCH}` via worktree branching, or did
it appear in this worktree?) AND the `## Source` field inside it:

| Case | git-tracked? | Source-field match? | Meaning | Action |
|---|---|---|---|---|
| **(a) Inherited merged seed** | yes (tracked in HEAD) | n/a | A prior merged seed run already emitted this slug. The current run is the documented iteratively-re-runnable happy path. | Auto-suffix `-N`, notify, update state slug. Preserves both seeds (prior + new). **Escape hatch**: to *replace* rather than preserve a prior merged seed, on `${BASE_BRANCH}` `rm` **both** `ai-artifacts/seeds/seed.<intent-slug>.<resource-slug>.md` **and** `ai-artifacts/seeds/seed.<intent-slug>.<resource-slug>.html` (the pair invariant — removing only the `.md` leaves an orphan `.html` until the next emit overwrites it), **commit the removal**, then re-run the skill — that converts case (a) into a fresh emit. (Skipping the commit step trips Phase 4's dirty-`BASE_BRANCH` guard, which refuses to create the new worktree until the working tree is clean.) |
| **(b) Crash-attempt mine** | no (untracked) | yes | Same run, prior Phase 5 attempt wrote the file but crashed before the state-update landed. | **Overwrite silently** — it's recovery, not a collision. |
| **(c) True intra-run collision** | no (untracked) | no | Two distinct resources in this run derived the same slug (e.g., two `whitepaper.pdf` files in different directories), OR a manually-placed unrelated file is in the way. | Auto-suffix `-N`, notify, update state slug. |

When emitting at Phase 5, for each resource:

1. If the file does NOT exist → write it; done.
2. If the file **does** exist, branch by git-trackedness FIRST:
   - **Tracked in HEAD** (case a) — the file came from
     `${BASE_BRANCH}` via worktree branching:
     ```bash
     if git ls-files --error-unmatch "${target_md}" >/dev/null 2>&1; then
       # case (a): inherited from prior merged seed run
     fi
     ```
     Auto-suffix (see step 3 below); notify; update state slug.
   - **Untracked** — the file appeared in this worktree. Read its
     `## Source` field with the strict awk (see "Reading the
     existing `Source` field" below):
     - Source matches `resources[i].location` (case b) → mine from
       a prior crashed attempt; **overwrite silently** to complete
       the recovery.
     - Source differs (case c) → true collision; auto-suffix.

3. **Auto-suffix algorithm** (cases a + c): find the smallest
   integer `N ≥ 2` such that
   `ai-artifacts/seeds/seed.<intent-slug>.<resource-slug>-N.md` does NOT exist;
   append `-N` to the resource_slug for both `.md` and `.html`;
   update `resources[i].resource_slug` in the state file to the
   suffixed name (so resume re-checks against the resolved slug);
   persist state; notify the user in chat (mandatory — never
   silent for cases a + c). Notification strings:
   - Case (a) — English: *"Re-seeding `<location>` — a prior merged seed already uses `seed.<slug>.<resource-slug>.md`. Adding the new capture as `seed.<slug>.<resource-slug>-N.md` to preserve the prior one. If `-N` is climbing fast across runs, consider whether older captures should be retired (`rm` them on `${BASE_BRANCH}` before re-running) to avoid an over-accumulated `ai-artifacts/seeds/`."*
   - Case (a) — Korean: *"`<location>` 재시드 — 이전 병합된 시드가 이미 `seed.<slug>.<resource-slug>.md`를 사용 중입니다. 이전 것을 보존하기 위해 새 캡처를 `seed.<slug>.<resource-slug>-N.md`로 추가합니다. 여러 번 실행으로 `-N`이 빠르게 증가한다면, 오래된 캡처를 정리하는 것(`${BASE_BRANCH}`에서 재실행 전 `rm`)을 고려하세요."*
   - Case (c) — English: *"Slug collision — `seed.<slug>.<resource-slug>.md` already exists with a different source. Using `seed.<slug>.<resource-slug>-N.md` instead."*
   - Case (c) — Korean: *"슬러그 충돌 — `seed.<slug>.<resource-slug>.md`가 다른 출처로 이미 존재합니다. 대신 `seed.<slug>.<resource-slug>-N.md`를 사용합니다."*

Crash-resume overwrite (case b) is silent — it's recovery completing
a half-finished emit, not a collision the user needs to act on.

### Reading the existing `## Source` field

The seed markdown emits the source on a deterministic line after the
`## Source` heading (see [output-schema.md](output-schema.md)) —
always a URL (`http://` / `https://` prefix) or an absolute path
(starts with `/`). The strict awk matches only those prefixes, so a
future schema drift that introduces sub-labels or indented values
doesn't silently extract the wrong line:

```bash
existing_source="$(awk '/^## Source$/{flag=1; next} flag && /^(\/|https?:\/\/)/{gsub(/[[:space:]]+$/,""); print; exit}' "${target_md}")"
```

The `gsub(/[[:space:]]+$/,"")` strips trailing whitespace inside awk
before printing (the surrounding `$(...)` only strips trailing
newlines, not spaces or tabs). Without it, a Source line that picked
up trailing whitespace via hand-edit or future schema drift would
fail the strict-equality compare against `resources[i].location` and
misfire case (b) → (c).

If the awk extracts nothing (malformed file, non-URL/path Source, or
the file isn't actually a seed at all), `existing_source` will be
empty — which won't match `resources[i].location` (non-empty), so the
logic falls into case (c) and auto-suffixes. Safe behavior under
malformed input.

**Empty-location defensive guard** — before the case-b equality
check, also assert `resources[i].location` is non-empty. The Phase 2
classifier rejects empty location at intake, so this guard is
unreachable on the happy path, but it closes the empty-equals-empty
loop if a corrupted state file ever stages an empty location:

```bash
if [ -n "${NEW_LOCATION}" ] && [ "${existing_source}" = "${NEW_LOCATION}" ]; then
  # case (b): mine from a prior crashed attempt — overwrite silently
else
  # case (c): suffix
fi
```

## What this naming buys

- **Browsability**: a directory of `seed.dashboard.nextjs-caching.md`,
  `seed.dashboard.cloudfront-edge-tos.md`,
  `seed.dashboard.youtube-abc123def.md` is scannable.
- **Stable handoff**: plan-establisher can glob
  `ai-artifacts/seeds/seed.<intent-slug>.*.md` to find everything for one intent.
- **Cross-intent coexistence**: `seed.dashboard.nextjs-caching.md`
  and `seed.payments.nextjs-caching.md` don't collide — same web
  resource, different intent perspective.
- **Suffix marks repeats**: `seed.dashboard.whitepaper-2.md` is a
  visible cue that there's also a `whitepaper.md` for the same
  intent, prompting the user to consider whether they belong
  together.

## What this naming does NOT do

- **Does not encode timestamp**. Multiple captures of the same URL
  across different runs will collide; auto-suffix handles it, but the
  files don't carry "I was captured later" semantics. If the user
  needs that, plan-establisher (or the user manually) can rename.
- **Does not encode language**. A Korean-extracted seed and an
  English-extracted seed for the same URL would collide; auto-suffix
  preserves both. The seed file's `Extracted at` and the dialog
  `language` (in `.seed-state.json`) carry the language signal.
- **Does not deduplicate semantically**. Two URLs pointing to the
  same article via different routes (with/without `?utm=...`, http vs
  https) will produce different slugs. We don't normalize URLs.
