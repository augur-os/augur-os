---
title: "Voice Profile — Personalization Journey (Onboarding → Process → View → Maintenance)"
type: spec
status: draft
created: 2026-05-11
amended: 2026-05-11
authors:
  - gsannikov
related:
  - ADR-722 — Setup Completeness Widget (shares onboarding milestone 3)
  - ADR-728 — Browse Page Lifecycle Ordering (places new `profile` Browse category)
  - shared-vault/skills/knowledge — owner skill
  - apps/dashboard/features/pages/brain/profile/page.tsx — existing page being extended
  - shared-vault/skills/knowledge/prompts/voice-profile/ — 4 shipped prompts (EN+HE × interview+summary)
inspired_by: "https://almaya.ai/blog/creating-ai-voice-profile — Roey Parel, Almaya"
governance:
  next_step: ADR (via /adr write) → implementation plan (writing-plans) → /adr implement
tags:
  - personalization
  - profile
  - voice-profile
  - knowledge
  - onboarding
  - dashboard
  - mcp
  - bilingual
---

# Voice Profile — Personalization Journey

## 0. Amendment 2026-05-11 — Bilingual support + shipped prompts (Model B)

This amendment block supersedes the affected sections below. Read this section first; the original sections remain as context for unchanged behavior. Where this section conflicts with an original section, this section wins.

### 0.1 What changed

The original spec described a single-language flow with one Almaya prompt the user had saved in their personal vault (`vault/prompts/voice-profile-almaya.md`). It produced one `about-me.md`. The amended design:

1. **Ships 4 prompts with the system** under `shared-vault/skills/knowledge/prompts/voice-profile/`:
   - `interview-en.md` — Almaya Prompt 1, English (verbatim from source)
   - `summary-en.md` — Almaya Prompt 2, English (verbatim from source)
   - `interview-he.md` — Almaya Prompt 1, Hebrew (verbatim from source)
   - `summary-he.md` — Almaya Prompt 2, Hebrew (verbatim from source)
   - `README.md` — attribution + usage notes
2. **Adds language selection** at the start of `/profile interview`. The agent asks "English or Hebrew?" and loads the corresponding prompt files.
3. **Per-language parallel profiles (Model B).** A bilingual user keeps an English voice profile and a Hebrew voice profile as separate artifacts. Running the interview in HE does not touch the EN profile, and vice versa. Voice is language-bound; the system reflects that.

### 0.2 Path & data-model changes

Storage moves from a single profile to per-language subdirectories under the user vault:

```
vault/profile/
├── en/
│   ├── about-me.md
│   ├── interview-in-progress.yaml
│   └── archive/
│       └── interview-2026-05-11.yaml
└── he/
    ├── about-me.md
    ├── interview-in-progress.yaml
    └── archive/
        └── interview-2026-05-11.yaml
```

Either subdirectory may be empty if the user has not yet built that language's profile. The system treats languages independently throughout.

The in-progress YAML schema gains one field:

```yaml
# vault/profile/<lang>/interview-in-progress.yaml
version: 1
language: en          # NEW — "en" | "he"; set once at interview start, never mutated
total: 100
answered: 23
# ... rest unchanged
```

### 0.3 MCP tool signatures (amendments to §5)

All 4 tools gain an optional `language` parameter. When omitted, tools return aggregate or "first found" semantics as noted.

- **`profile-status(language: 'en' | 'he' | null)`** — when `language` is given, returns the status for that language only. When `null` or omitted, returns a dict keyed by language: `{ "en": { ... }, "he": { ... } }`. Each language's payload preserves the original shape (in_progress, answered, total, about_me sub-object).
- **`profile-read(language: 'en' | 'he')`** — language is required. Returns the about-me.md content for that language. If the file doesn't exist for the requested language: `{"success": false, "error": "profile_not_found", "language": "<lang>"}`.
- **`profile-write(content, mode, language: 'en' | 'he')`** — language is required. Writes `vault/profile/<lang>/about-me.md`. Archives that language's in-progress yaml only.
- **`profile-get-age(language: 'en' | 'he')`** — language is required. Returns the age of that language's `about-me.md` only.

Capability-exposure entries in `config/system/capability_exposure.yaml` get the matching parameter docs in their descriptions; no other config changes.

### 0.4 Slash command body changes (amendments to §6)

`/profile interview` no longer embeds the prompts verbatim. Instead, the command body instructs the agent:

1. **Ask the user for language.** "Run the interview in English (en) or Hebrew (he)?" Wait for the answer. If the user types anything else, re-ask once; on second invalid input, default to `en` and proceed.
2. **State check** — call `vault-read` on `vault/profile/<lang>/interview-in-progress.yaml` (substitute the chosen language). Branches as in the original §6, but the path is language-scoped.
3. **Load the interview prompt** — read `shared-vault/skills/knowledge/prompts/voice-profile/interview-<lang>.md` using whatever file-read mechanism the AI client provides (Claude Code `Read`, equivalent in others). Follow the loaded prompt's instructions verbatim. The file content IS the prompt; nothing in `profile.md` overrides it except the auto-save behavior.
4. **Per-question loop** — same as original §6.1, but writes go to `vault/profile/<lang>/interview-in-progress.yaml`.
5. **After question 100** — read `shared-vault/skills/knowledge/prompts/voice-profile/summary-<lang>.md` and apply it as the compression step. Call `profile-write(content, mode="full", language="<lang>")` to save the result.
6. **Notify user** — "Voice profile saved at `vault/profile/<lang>/about-me.md`."

`/profile update` similarly:
- Asks the user which language profile to update (only languages with an existing `about-me.md` are valid choices; abort with "no profile to update" if neither exists).
- Loads `summary-<lang>.md` for the re-compression step.
- The delta-question template is shared across languages — agent translates dynamically if interviewing in HE (acceptable because delta questions are short and the dynamic translation is bounded).

`/profile view` takes an optional `<language>` argument. With no argument, prints the about-me for the only language present (or asks if both exist).

### 0.5 Dashboard changes (amendments to §7)

`<VoiceProfile>` renders **0, 1, or 2 cards** based on `profile-status()` (the no-arg variant):

- **0 cards** — neither language has a profile or in-progress interview. Render the existing State C call-to-action card once, with a language hint in the body: "Run `/profile interview` in your AI client to create one (English or Hebrew supported)."
- **1 card** — one language has an active or completed profile. Render that card with a language badge (e.g., "EN" or "HE" in the corner).
- **2 cards** — both languages have profiles. Render two cards stacked, each with its own state (A/B), each with the same action buttons (Re-run, Update, Edit) but each scoped to its language.

Polling shape unchanged (every 30s); the hook now diffs both language slots.

`<VoiceProfile>` no longer assumes a single source of truth. The Browse `profile` card shows a small badge with the count of completed profiles (0/1/2) and lists which languages.

### 0.6 ADR-722 integration (amendments to §8)

The probe is satisfied if EITHER `vault/profile/en/about-me.md` OR `vault/profile/he/about-me.md` exists and is >256 bytes. Milestone 3 is binary done/not-done; building a second language is optional, not required for milestone completion.

```yaml
- id: human-profile
  label: Build human profile
  probe: foundation.voice_profile     # checks: any language's about-me.md exists AND size > 256b
  action: { type: command, command: "/profile interview", label: "Run /profile interview" }
```

### 0.7 Implementation order (amendments to §10)

Insert a new C0 at the top of the checkpoint list. The other checkpoints remain in order but each now handles bilingual paths and the `language` parameter.

| # | Checkpoint | Verifiable by |
|---|---|---|
| **C0** | **4 prompt files + README shipped at `shared-vault/skills/knowledge/prompts/voice-profile/`** | **`ls` shows 5 files; manual diff against source URL confirms verbatim content** |
| C1 | New MCP tools (now with `language` parameter) + capability_exposure entries | pytest unit tests covering en/he/null code paths |
| C2 | `/profile` slash command — interview asks for language; loads `interview-<lang>.md` and `summary-<lang>.md` from the skill's prompts directory; state file is language-scoped | manual: `/profile interview` in Claude Code asks language then proceeds in chosen tongue |
| C3 | `<VoiceProfile>` renders 0/1/2 cards keyed by language; polls language-agnostic `profile-status()` | rule-28 browser verification of 0-card, 1-card-en, 1-card-he, 2-card states |
| C4 | Browse category `profile` shows completed-profile count badge | Browse > knowledge group shows profile card with "1/2 languages" or similar |
| C5 | ADR-722 milestone 3 probe accepts EITHER language's about-me.md | unit test covers both happy paths and the "neither exists" failure path |

**Status of C0 as of this amendment**: shipped this session — the 4 prompts + README are committed to the repo. C0 verification is complete; C1–C5 are the work that remains for `/adr implement`.

### 0.8 Out of scope additions

| Item | Why deferred |
|---|---|
| **Auto-translation between EN profile and HE profile** | Voice is language-bound; auto-translation loses fidelity. If a user wants both, they run the interview twice — once per language — and the answers may differ meaningfully. That is the feature, not a bug. |
| **A third language** | If/when needed, the same per-language pattern scales. No code changes pre-required; just add the prompt files and the language enum gains a new value. |
| **Dashboard language switcher in the card UI** | The cards always render side-by-side when both profiles exist. No tabs, no toggle — both visible simultaneously per Model B's "both are first-class" stance. |

### 0.9 Note on the original spec body below

§1–§14 below remain authoritative for the **journey, state-file schema basics, MCP tool return shapes, slash command structure, dashboard visual states, ADR-722/ADR-728 coordination, and alternatives considered**. Where this §0 amends a specific path, parameter, or behavior, §0 wins. The verbatim Almaya prompts referenced by §6 are now external files (per §0.4), not embedded in the slash command body.

---

## 1. Problem

Augur's existing user-profile artifact is `HUMAN_API.md` — auto-derived from agent interaction logs. It captures "what the user has been doing" (observed patterns). What it does NOT capture is "who the user is" — voice, convictions, writing style, aesthetic offenses, personality. That richer **identity layer** is the input that turns generic AI into a personalized agent.

The user has already saved Roey Parel's Almaya voice-profile prompt (`vault/prompts/voice-profile-almaya.md`) — a 2-step workflow: a 100-question self-interview followed by a compression step that produces `about-me.md`. Today nothing in Augur orchestrates running it. The prompt sits in the user's vault but is invoked manually, ad-hoc, with no progress tracking, no automatic save, no dashboard surface, no integration with the onboarding journey.

This spec defines the **end-to-end personalization journey** — onboarding, process (interview + compress), view, and maintenance — using existing Augur capabilities (slash commands, MCP tools, vault, dashboard, Browse, Setup Completeness Widget). Output: a `about-me.md` voice profile that AI clients can load alongside `HUMAN_API.md`, persisted across pause/resume sessions, with first-class dashboard visibility and a soft maintenance prompt at 6 months.

## 2. Goals and non-goals

### Goals

1. **End-to-end journey** — onboarding (Setup Completeness Widget milestone 3), process (interview + compress), view (dashboard), maintenance (manual + visible age).
2. **Inline interview, no clipboard** — the `/profile interview` slash command IS the interview; the agent reads the command body and conducts it directly in the AI-client session.
3. **Pause/resume with progress** — the interview is stateful. After every answer, state auto-saves to `vault/profile/interview-in-progress.yaml`. The user can `/exit` anytime and resume in a later session at the next unanswered question.
4. **Dashboard progress visibility** — `/brain/profile` page shows "23 of 100 questions answered" during the interview phase; switches to the rendered `about-me.md` view when complete.
5. **Two-layer profile** — `about-me.md` (user-authored voice, slow-changing) coexists with `HUMAN_API.md` (auto-derived memory, fast-changing). Both render on `/brain/profile`.
6. **Manual maintenance + visible age** — `/brain/profile` shows "Last updated: N days/months ago"; >6 months → soft amber banner. No daemon scheduling (lesson from insight_scanner).

### Non-goals

- Voice-to-text integration (user's choice — Wispr Flow / macOS dictation / etc.)
- Daemon-driven auto-refresh (rejected per insight_scanner lesson)
- Multi-version profile history (one canonical about-me.md; archived state files are append-only)
- Cross-machine profile sync (vault-level concern, separate)
- LLM-based delta-question generation for `/profile update` (use a fixed delta-question template for v1)
- Sharing/exporting about-me.md to other AI assistants (future work)
- A separate `profile` skill (the user picked: extend the `knowledge` skill)

## 3. Decision summary

**Pipeline (end-to-end):**

```
ONBOARDING:
  Setup Completeness Widget milestone 3 ("Build human profile")
  Action: "Run /profile interview in your AI client"
  Probe strengthened: vault/profile/about-me.md exists with size >256 bytes
                      (was: any *profile* file >256 bytes)

PROCESS (inline, no clipboard, with pause/resume):
  User in Claude Code: /profile interview
  ↓
  Agent reads command body (Almaya Prompt 1 embedded + state-management instructions)
  ↓
  Agent calls vault-read on vault/profile/interview-in-progress.yaml:
    - absent → create fresh state via vault-write (total=100, answered=0)
    - present, answered<100 → load prior Q&A pairs, resume at next question
    - present, answered=100 → prompt: "Interview complete. /profile compress or /profile interview --restart?"
  ↓
  Agent asks one question at a time (per Almaya prompt category quotas)
  User answers (typed or dictated via user's tool of choice)
  Agent calls vault-write to append the new qa_pair + bump `answered`
  Agent confirms: "✓ Saved. 24 of 100 done. (Type /exit anytime.)"
  ↓
  After question 100:
    Agent transitions to Prompt 2 compression (same session)
    Agent calls profile-write to save vault/profile/about-me.md
    Agent optionally archives interview-in-progress.yaml → interview-2026-05-11.yaml

VIEW:
  /brain/profile page (extended existing page):
    [Voice Profile section] - new
    [Memory Profile section] - existing HumanApiProfile component, unchanged
  Browse category `profile` in knowledge journey_group (coordinates with ADR-728)

MAINTENANCE:
  /brain/profile shows "Last updated: N days/months ago"
  If >6 months: amber banner "Consider running /profile update in your AI client"
  /profile update: delta-question template (10-20 questions), regenerates about-me.md
  Manual only — no daemon scheduling.
```

## 4. State + storage

### 4.1 `vault/profile/interview-in-progress.yaml`

The single source of truth for in-progress interview state. Written after every answer via `vault-write`.

```yaml
# vault/profile/interview-in-progress.yaml
version: 1
total: 100
answered: 23
started_at: 2026-05-11T14:00:00Z
last_answered_at: 2026-05-11T14:42:00Z
mode: full            # full | update
qa_pairs:
  - n: 1
    category: "BELIEFS & UNCONVENTIONAL VIEWS"
    q: "What's a conviction you hold that differs from the majority in your profession?"
    a: "<user's answer text>"
    asked_at: 2026-05-11T14:00:30Z
  - n: 2
    category: "BELIEFS & UNCONVENTIONAL VIEWS"
    q: "..."
    a: "..."
    asked_at: 2026-05-11T14:01:15Z
  # ... 23 entries total
```

### 4.2 `vault/profile/about-me.md`

The final voice profile, written via `profile-write` after the compression step.

```markdown
---
title: "Voice Profile — <User Name>"
generated_at: 2026-05-11T16:30:00Z
source: "Almaya 100-question interview, compressed via Prompt 2"
question_count: 100
mode: full
---

# Voice Profile

<Identity synthesis: 3-4 paragraphs capturing the user's voice, written
as if Claude itself is summarizing "who this user is" for another
instance of Claude to replicate their style.>

## Beliefs
...

## Writing
...

## Aesthetics
...

## Personality
...
```

Mirrors the Almaya prompt structure. Self-contained markdown the user can read or hand-edit.

### 4.3 `vault/profile/archive/interview-<YYYY-MM-DD>.yaml`

After successful compression, the in-progress yaml is moved to the archive subdirectory with the run date as filename. Provides a permanent record of the answers behind each `about-me.md` version.

## 5. MCP tools

### 5.1 Reused (no changes)

- **`vault-read(path)`** — agent reads interview state file
- **`vault-write(path, content)`** — agent writes interview state file after each answer AND writes final about-me.md (alternative to `profile-write`)

### 5.2 New

- **`profile-status()`** — dashboard polls for interview progress.

  Returns:
  ```json
  {
    "success": true,
    "in_progress": true,                              // false if no interview-in-progress.yaml
    "answered": 23,
    "total": 100,
    "percentage": 23,
    "started_at": "2026-05-11T14:00:00Z",
    "last_answered_at": "2026-05-11T14:42:00Z",
    "complete": false,                                // true if answered=100 AND about-me.md exists
    "about_me": {
      "exists": false,                                // about-me.md present?
      "last_updated_at": null,                        // mtime of about-me.md
      "age_days": null
    }
  }
  ```

- **`profile-read()`** — return rendered about-me.md content for the dashboard.

  Returns:
  ```json
  {
    "success": true,
    "content": "<full markdown of about-me.md>",
    "metadata": {
      "generated_at": "2026-05-11T16:30:00Z",
      "question_count": 100,
      "mode": "full",
      "last_updated_at": "2026-05-11T16:30:00Z",
      "age_days": 0
    }
  }
  ```

  If the file doesn't exist: `{"success": false, "error": "profile_not_found", "hint": "Run /profile interview to create your voice profile"}`.

- **`profile-write(content, mode)`** — write `vault/profile/about-me.md`.

  Args:
  - `content` — full markdown body
  - `mode` — `"full"` (after `/profile interview` completes 100 questions) | `"update"` (after `/profile update` delta questions)

  On success, also archives the in-progress yaml to `vault/profile/archive/interview-<YYYY-MM-DD>.yaml` and removes the live in-progress file.

- **`profile-get-age()`** — lightweight helper for the age banner (`profile-status` already returns this, but keep `profile-get-age` for explicit callers).

  Returns `{"success": true, "age_days": 5}` or `{"success": true, "exists": false}`.

### 5.3 Capability exposure entries

Add to `config/system/capability_exposure.yaml`:

```yaml
mcp-tool:profile-status:
  type: mcp-tool
  owner_kind: skill
  skill: knowledge
  management: read-only
  scope: vault
  primary_surface: mcp via dashboard
  preferred_client: dashboard
  export_to: [mcp]
  description: "Status of the voice-profile interview (progress + about-me.md metadata)."
mcp-tool:profile-read:
  ...
mcp-tool:profile-write:
  ...
mcp-tool:profile-get-age:
  ...
```

## 6. Slash command — `/profile`

New file: `shared-vault/skills/knowledge/commands/profile.md`.

Three actions:

- **`/profile interview`** — full 100-question interview with auto-save + resume.
- **`/profile update`** — delta-question re-interview (10-20 questions targeting "what's changed").
- **`/profile view`** — print the current about-me.md to chat (for quick inline reference).

### 6.1 Command body — `/profile interview`

```markdown
# /profile interview

Conduct the Almaya 100-question voice-profile interview inline in this AI-client session. Auto-saves after every answer. Resumable across sessions.

## Behavior

1. **State check** — call vault-read on `vault/profile/interview-in-progress.yaml`.
   - If absent: create fresh state via vault-write.
   - If present and `answered < total`: load prior Q&A pairs and resume at the next unanswered question.
   - If present and `answered == total`: prompt the user: "Interview complete (100 of 100). Run `/profile compress` to compress into about-me.md, or `/profile interview --restart` to wipe and redo."

2. **Conduct the interview** following the Almaya 8-category structure with quotas:
   - BELIEFS & UNCONVENTIONAL VIEWS (15)
   - WRITING PRACTICES (20)
   - AESTHETIC OFFENSES (15)
   - PERSONALITY & UNIQUENESS (15)
   - … (other Almaya categories totaling 100)

3. **Per-question loop**:
   - Ask one question, framed in the Almaya interviewer voice.
   - Wait for the user's answer.
   - Append the qa_pair to interview-in-progress.yaml via vault-write (with the schema in §4.1 of the spec).
   - Bump `answered` and update `last_answered_at`.
   - Confirm to the user: "✓ Saved. {answered} of {total} done."
   - Continue to the next question.

4. **After question 100**: transition into the compression step (Almaya Prompt 2). Use the embedded compression prompt template (see §6.3 below). Call `profile-write(content, mode="full")` to save the result, which also archives the in-progress yaml.

5. **Notify user**: "Voice profile saved at vault/profile/about-me.md. View at http://localhost:3000/brain/profile."

## Embedded Prompt 1 — Interviewer voice (from Almaya)

<embed the verbatim text from vault/prompts/voice-profile-almaya.md Prompt 1>

## Embedded Prompt 2 — Compression (from Almaya)

<embed the verbatim text from vault/prompts/voice-profile-almaya.md Prompt 2>

## Failure / Resume / Edge cases

- If vault-write fails: report the error to the user; do not proceed with the next question (answers must persist).
- If the user types something that isn't a clear answer (e.g., "skip" or "I don't know"): record the answer as the literal text and continue. Do not skip the question slot.
- If the user types `/exit` or closes the session: state is already persisted. Resume on next `/profile interview`.
- If `vault/profile/interview-in-progress.yaml` has malformed YAML: report the error; do not overwrite. User can manually fix or delete the file.
```

### 6.2 Command body — `/profile update`

```markdown
# /profile update

Delta-question re-interview for an existing voice profile. Asks 10-20 questions focused on "what's changed since last interview," then re-compresses the existing about-me.md + new answers into an updated about-me.md.

## Behavior

1. **Precondition check** — call profile-status. If `about_me.exists == false`, abort with: "No existing voice profile found. Run `/profile interview` for the full interview."

2. **Read existing about-me.md** — call profile-read to load the current profile.

3. **Ask delta questions** (10-20 questions targeting categories where life or thinking changes:
   - "What have you started believing in the last 6 months that you didn't before?"
   - "What style of writing now grates on you that didn't used to?"
   - "What new patterns are you noticing in how you work?"
   - … (full delta template embedded below)

4. **Per-question loop**: same auto-save pattern as `/profile interview`, but `mode: "update"` in interview-in-progress.yaml.

5. **Compression**: re-run Prompt 2 with prior about-me.md + new answers as combined input. Output replaces about-me.md (the old version is preserved via the archive yaml).

6. **Notify user** with the new profile path + diff summary if available.

## Embedded delta-question template

<10-20 question template, derived from the Almaya category structure>
```

### 6.3 Command body — `/profile view`

```markdown
# /profile view

Print the current voice profile to chat for inline reference (e.g., when starting an AI session that needs personalization context).

## Behavior

1. Call profile-read.
2. Print the markdown body to chat.
3. If profile doesn't exist: prompt the user to run `/profile interview`.

This is a convenience command — most users will view the profile in `/brain/profile` instead.
```

## 7. Dashboard surfaces

### 7.1 Extended `/brain/profile` page

`apps/dashboard/features/pages/brain/profile/page.tsx` adds a `<VoiceProfile>` section ABOVE the existing `<HumanApiProfile>` component. Two cards stacked.

### 7.2 `<VoiceProfile>` component (NEW)

`apps/dashboard/features/pages/brain/profile/components/VoiceProfile.tsx`

Two visual states, switched by `profile-status`:

**State A — interview in progress (about_me.exists == false AND in_progress == true):**

```
┌─ Voice Profile (interview in progress) ──────────────────────┐
│  23 of 100 questions answered   ▓▓▓░░░░░░░  23%              │
│                                                              │
│  Started: 2 hours ago · Last answered: 5 minutes ago         │
│                                                              │
│  Continue by running /profile interview in your AI client.   │
│  Your progress saves automatically after every answer.       │
│                                                              │
│  [View partial answers]    [Discard and restart]             │
└──────────────────────────────────────────────────────────────┘
```

- Progress bar (CSS bar with percentage)
- Timestamps formatted via `formatRelativeTime` from ADR-728
- "View partial answers" opens a modal listing the qa_pairs so far
- "Discard and restart" prompts confirmation, then deletes interview-in-progress.yaml

**State B — complete (about_me.exists == true):**

```
┌─ Voice Profile (about-me.md) ────────────────────────────────┐
│  <markdown render of about-me.md content>                    │
│                                                              │
│  Last updated: 2 days ago · Built from 100 questions         │
│                                                              │
│  [Re-run interview]   [Update (delta questions)]   [Edit]    │
└──────────────────────────────────────────────────────────────┘
```

- Markdown rendered with the project's existing markdown renderer
- "Last updated" uses `formatRelativeTime`
- If `age_days > 180` → amber banner above the card: "Profile is N months old. Consider running `/profile update`."
- "Re-run interview" / "Update" buttons → copy the relevant slash command to clipboard with a toast: "Paste in your AI client"
- "Edit" → switches to a textarea for hand-edit, with Save/Cancel buttons. Save calls `vault-write` directly (or `profile-write` with `mode="manual"`)

**State C — neither (no in-progress, no about-me.md):**

```
┌─ Voice Profile ──────────────────────────────────────────────┐
│  Your voice profile captures how you think, write, and speak │
│  so AI clients can personalize their responses to you.       │
│                                                              │
│  Run /profile interview in your AI client to create one.     │
│  (About 90 minutes with voice-to-text; pause/resume anytime.)│
│                                                              │
│  [Copy /profile interview to clipboard]                      │
└──────────────────────────────────────────────────────────────┘
```

Polling: dashboard hook polls `profile-status` every 30s while the page is open. On state transitions, the card swaps without a full page reload.

### 7.3 Browse category `profile` (coordinates with ADR-728)

Add to `BROWSE_CATEGORIES`:

```typescript
{
  id: "profile",
  label: "Profile",
  singularLabel: "Voice Profile",
  icon: "User",
  devOnly: false,
  group: "content",
  journey_group: "knowledge",
  journey_order: 4,      // after notes=1, wiki=2, pages=3 (per ADR-728 reservation for ADR-723)
  viewLayout: "card",
}
```

Click on the profile card in Browse → navigates to `/brain/profile`.

If the user has no profile (no about-me.md, no in-progress): the Browse card shows "Not yet started — click to begin".

If interview in progress: card shows "23 of 100 questions answered" badge.

If complete: card shows the first 1-2 lines of about-me.md as a preview.

## 8. Integration with ADR-722 (Setup Completeness Widget)

ADR-722 milestone 3 currently has:

```yaml
- id: human-profile
  label: Build human profile
  probe: foundation.human_profile     # checks: profile file exists AND size > 256b
  action: { type: mcp, mcp_tool: "memory-profile-regenerate", label: "Generate profile" }
```

This spec strengthens the probe and changes the action:

```yaml
- id: human-profile
  label: Build human profile
  probe: foundation.voice_profile     # NEW: checks vault/profile/about-me.md exists AND size > 256b
  action: { type: command, command: "/profile interview", label: "Run /profile interview" }
```

When ADR-722 implementation lands (or has already landed), its probe + action for milestone 3 update to match. This is a small follow-on edit to the onboard skill's `setup-items.yaml`.

## 9. Integration with ADR-728 (Browse Lifecycle Ordering)

ADR-728 reserves placement for ADR-723's `pages` category at `journey_group: knowledge, journey_order: 3`. This spec adds a `profile` category at `journey_order: 4` in the same journey_group.

The knowledge group's final order:

| journey_order | category | source |
|---|---|---|
| 1 | notes | ADR-728 |
| 2 | wiki | ADR-728 |
| 3 | pages | ADR-723 (reserved by ADR-728) |
| 4 | **profile** | **THIS SPEC** |

Coordination: ADR-728's spec §10 should be amended to note this fourth reservation. The amendment is a one-line addition to ADR-728's reservation table.

## 10. Implementation order

Five checkpoints, one PR:

| # | Checkpoint | Verifiable by |
|---|---|---|
| C1 | New MCP tools (`profile-status`, `profile-read`, `profile-write`, `profile-get-age`) + capability_exposure entries | pytest unit tests for each tool; manual: `aug profile-status` returns valid JSON |
| C2 | New `/profile` slash command at `shared-vault/skills/knowledge/commands/profile.md` with three actions (interview, update, view); Almaya prompts embedded in command body | manual: in Claude Code, `/profile interview` opens the interview flow; agent reads embedded prompts and conducts the interview |
| C3 | New `<VoiceProfile>` React component + integration into `/brain/profile` page; three visual states (in-progress, complete, not-yet-started); polling via `profile-status` | rule-28 browser verification of all three states |
| C4 | Browse category `profile` added to `BROWSE_CATEGORIES`; coordinates with ADR-728 (journey_group=knowledge, journey_order=4) | Browse > knowledge group shows profile card |
| C5 | ADR-722 milestone 3 probe + action updated in `setup-items.yaml` (or follow-on to ADR-722 implementation if ADR-722 hasn't shipped yet); strengthened probe checks vault/profile/about-me.md specifically | unit test for the probe |

## 11. Out of scope

| Item | Why deferred |
|---|---|
| Voice-to-text built into Augur | Users have established tools (Wispr Flow, macOS dictation); not Augur's job |
| Daemon-driven auto-refresh | insight_scanner lesson — don't auto-burn tokens |
| LLM-driven delta-question generation in `/profile update` | Static delta template is fine for v1; LLM customization is a follow-on |
| Multi-profile (e.g., "professional me" vs "casual me") | One profile per user for v1; expand if multiple users ask |
| Profile sharing / export to other AI assistants | Future work; about-me.md is a markdown file, copy-paste already works |
| Multi-machine sync | Vault-level concern (vault repo already syncs) |
| Profile diff view (compare versions) | Archive yamls preserve history; UI diff is future polish |
| Editing in dashboard (rich editor) | Textarea hand-edit is sufficient for v1 |

## 12. Alternatives considered

| Alternative | Why rejected |
|---|---|
| Replace HUMAN_API.md with about-me.md | User picked "two profiles, two layers" |
| New `profile` skill | User picked knowledge skill (lower scope creep) |
| Clipboard-based interview flow | User correctly pointed out: agent is already in Claude, no paste needed |
| Stateless interview (no auto-save) | User requested pause/resume + progress visibility; stateless can't support this |
| Daemon-scheduled refresh | insight_scanner lesson |
| Standalone /profile dashboard route | User asked for /brain hub specifically |
| Single slash command with no subactions | Three distinct user tasks (full interview, delta update, quick view) warrant three explicit actions |
| Pre-populate vault/profile/ on install | Premature; the directory is created on first use |

## 13. References

- ADR-722 — Setup Completeness Widget (shares onboarding milestone 3 — probe + action updates land here)
- ADR-728 — Browse Page Lifecycle Ordering (places the new `profile` Browse category)
- ADR-727 — Background Routines (informs the "no daemon scheduling" decision)
- `vault/prompts/voice-profile-almaya.md` — the user's saved Almaya prompt (source content embedded in slash command)
- `apps/dashboard/features/pages/brain/profile/page.tsx` — existing page being extended
- `shared-vault/skills/knowledge/scripts/mcp/tools_memory_core.py` — where `memory-profile-regenerate` lives (the auto-derived HUMAN_API.md flow that remains unchanged)
- CLAUDE.md rule 1 — User-visible correctness; this spec's pause/resume contract honors that
- CLAUDE.md rule 11 — Dashboard uses MCP, not direct local execution

## 14. Governance

This brainstorming spec is the design record. After approval:

1. `/superpowers:writing-plans` produces the multi-task implementation plan.
2. `/adr write` adopts this design as ADR-729 (thin index) pointing at both spec and plan.
3. `/adr implement ADR-729` drives the plan through worktree + subagent-driven flow.

The brainstorming spec is not the architectural commitment — the ADR is.

## Self-review

- **Placeholder scan:** No TBDs. The "embedded Prompt 1 / Prompt 2 / delta template" sections in §6 are intentional placeholders pointing at concrete source files (the existing voice-profile-almaya.md and a delta template to be authored in the plan).
- **Internal consistency:** §3 pipeline ↔ §4 state file ↔ §5 MCP tools ↔ §6 slash command ↔ §7 dashboard ↔ §10 implementation order — all reference the same field names (`answered`, `total`, `qa_pairs`, `about_me.exists`) and same tool names (`profile-status`, `profile-read`, etc.).
- **Scope check:** Wiki-only-like scope (knowledge skill only); one PR sized for 5 checkpoints. ✓
- **Ambiguity check:** Three slash-command actions clearly delimited; three dashboard visual states clearly delimited; all four MCP tools have JSON return shapes specified.
