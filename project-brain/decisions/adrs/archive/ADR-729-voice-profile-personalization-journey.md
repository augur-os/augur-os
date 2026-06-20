---
status: Implemented
date: '2026-05-11'
deciders:
- gsannikov
related:
- ADR-722
- ADR-728
hub: command
tags:
- personalization
- profile
- voice-profile
- knowledge
- onboarding
- dashboard
- mcp
superseded_by: null
spec_file: 2026-05-11-voice-profile-personalization-design.md
plan_file: 2026-05-11-voice-profile-personalization.md
---

# ADR-729: Voice Profile — Personalization Journey

## Decision summary

Ship the end-to-end voice-profile personalization journey — onboarding (ADR-722 milestone 3), inline 100-question Almaya interview with per-answer auto-save and pause/resume, dashboard view at `/brain/profile` showing three visual states (not-started / in-progress with progress bar / complete with...

## Status notes

Spec + plan written 2026-05-11 in same session via `/superpowers:brainstorming` + `/superpowers:writing-plans`. Source content: Roey Parel's Almaya 2-step prompt (`vault/prompts/voice-profile-almaya.md`), already saved in the user's vault. Two profiles, two layers (per user decision): - **about-me.md** = user-authored voice profile (Almaya interview output, slow-changing, "who I am") - **HUMAN_API.md** = auto-derived memory profile (existing, unchanged, fast-changing, "what I've been doing") Both render on `/brain/profile`. Coexist. Pause/resume requirement absorbed: language-scoped state files `vault/profile/{en,he}/interview-in-progress.yaml` written via `vault-write` after every answer. Dashboard polls `profile-status` every 30s to surface progress. No daemon scheduling (per ADR-727 / insight_scanner lesson). Maintenance is manual; dashboard surfaces age + amber banner at >180 days. Voice-to-text deliberately out of scope (user's choice — Wispr Flow / macOS dictation). **Amendment 2026-05-11 — bilingual support (Model B).** Spec and plan amended to ship 4 prompts (`shared-vault/skills/knowledge/prompts/voice-profile/{interview,summary}-{en,he}.md` — verbatim from <https://almaya.ai/blog/creating-ai-voice-profile>, attribution in sibling `README.md`); language selection happens at the start of `/profile interview`; profiles are per-language parallel artifacts under `vault/profile/{en,he}/`; all four MCP tools gain a `language` parameter (`profile-status` makes it optional and returns a dict keyed by language when omitted; the other three require it); `<VoiceProfile>` renders 0/1/2 cards keyed by which languages have profiles; ADR-722 milestone 3 probe is satisfied by either language. See spec §0 and plan amendment block for the full delta. Implemented 2026-05-13 via `/adr implement ADR-729`: C1-C5 are complete with bilingual MCP tools, slash command policy, dashboard profile cards, Browse category wiring, onboarding probe integration, and regression coverage.

## Impact Manifest

```yaml
paths_renamed: []
apis_changed:
- 'New MCP tools: profile-status, profile-read, profile-write, profile-get-age'
- 'New slash command: /profile (3 actions: interview, update, view)'
- 'Browse category: new `profile` entry in BROWSE_CATEGORIES (journey_group=knowledge,
  journey_order=4)'
- 'ADR-722 milestone 3 probe + action: strengthened to check vault/profile/{en,he}/about-me.md
  specifically; action triggers /profile interview'
patterns_deprecated: []
files_affected:
- shared-vault/skills/knowledge/scripts/profile_state.py (NEW)
- shared-vault/skills/knowledge/scripts/mcp/tools_voice_profile.py (NEW)
- shared-vault/skills/knowledge/commands/profile.md (NEW)
- apps/dashboard/features/pages/brain/profile/components/VoiceProfile.tsx (NEW)
- apps/dashboard/features/pages/brain/profile/hooks/useVoiceProfile.ts (NEW)
- apps/dashboard/features/pages/brain/profile/page.tsx
- apps/dashboard/lib/browse/types.ts
- apps/dashboard/lib/browse/transforms.ts
- config/system/capability_exposure.yaml
- shared-vault/skills/onboard/config/setup-items.yaml (or follow-on to ADR-722)
- shared-vault/skills/onboard/scripts/setup/probes/foundation.py
- shared-vault/skills/knowledge/augur/tests/test_voice_profile_state.py (NEW)
- shared-vault/skills/knowledge/augur/tests/test_voice_profile_mcp.py (NEW)
- shared-vault/skills/onboard/augur/tests/test_setup_aggregator.py
- tests/dashboard/features/pages/brain/profile/components/VoiceProfile.test.tsx (NEW)
- tests/dashboard/lib/browse/transforms.test.ts
```
