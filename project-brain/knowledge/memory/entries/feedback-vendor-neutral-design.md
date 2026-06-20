---
title: feedback-vendor-neutral-design
name: feedback-vendor-neutral-design
description: Never name a specific AI model/vendor in designs or code — every AI-using
  feature must route through the multi-vendor LLM abstraction
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_vendor_neutral_design.md
source_hash: 383be4ca636cee0f
_entity_tier: 2
---



All AI-using design decisions in Augur MUST be vendor-neutral. Never reference a specific model name (e.g., "Claude Haiku 4.5", "GPT-5", "Gemini Pro") in designs, specs, code, or config. Route every AI call through the existing multi-vendor LLM abstraction.

**Why:** Augur supports multiple AI vendors and CLIs by design — Claude, Codex (OpenAI), Gemini, Ollama (local), Glama gateway, etc. The active profile changes with airplane mode, cost constraints, and user preference. Hardcoding a vendor breaks portability, breaks airplane mode, and locks the user into a single provider. The user has standing policy: every AI decision is multi-vendor capable.

**How to apply:**
- Read `config/system/llm.yaml` for available `profiles` and `tasks` routing
- Add a task entry (e.g., `vault_hygiene_classify: local`) instead of naming a model
- Reference the model abstractly: "the classifier model" or "the configured LLM profile" — never the brand
- In specs/ADRs, describe behavior in terms of capability tier ("a small fast classification model") not vendor
- Airplane mode forces `local` profile — design must work with local models, not require cloud
- The shared LLM client (probably in `src/lib/ai/`) is the only place that knows vendor specifics
