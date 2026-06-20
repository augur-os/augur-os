# Prompt Optimization

## Goals
- Improve task success rate.
- Reduce token usage and latency.
- Preserve tool-trigger accuracy.

## Workflow
1. Select target prompt or skill.
2. Define baseline metrics (success rate, latency, tokens).
3. Draft variant prompts (concise vs detailed).
4. Run A/B test with fixed sample window.
5. Analyze results and adopt best variant.
6. Document changes and update registry.

## Heuristics
- Prefer concise instructions with explicit triggers.
- Avoid redundant context already present in skill files.
- Keep tool names and usage patterns explicit.
- Use examples only when needed for disambiguation.

## Evaluation Checklist
- Success rate improved?
- Tool selection accuracy improved?
- Token usage reduced?
- Regression risks documented?
