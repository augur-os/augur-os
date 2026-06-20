# Dispatch Escalation Pattern

Reusable architecture pattern for executing AI-assisted tasks from the Augur dashboard. Applies to any feature where the dashboard needs agent processing but must not call LLM APIs directly (Critical Rule 11).

## Core Principle

Dashboard dispatches work to native AI clients via `useActionRunner`. Three dispatch tiers provide a cost/speed/reliability tradeoff. The dashboard always receives results by **polling for file changes**, never through response payloads.

## The Three Tiers

### Tier 1: Oneshot CLI (Default — Fast Path)

**When**: Structured tasks with well-defined prompts (content pipeline, file transforms, code generation).

**Flow**:
```
Dashboard click → spawn native AI-client CLI → fixed prompt → write output file → exit
Dashboard polls for file → validates → done
```

**Characteristics**:
- **Tokens**: ~12,000-15,000 per pipeline (minimal system prompt ~500-2,000 tokens)
- **Latency**: 5-15s per stage, 20-60s full pipeline
- **Overhead**: Bounded agent reasoning, zero MCP round-trips, fixed prompt→response
- **Context window**: ~6% of 200K
- **Cost**: Uses the user's configured AI-client subscription or local model
- **Tradeoff**: No self-recovery, no feedback loop, fixed prompt only

**Implementation**:
```typescript
// Dashboard side — useActionRunner with dispatch: 'oneshot' or custom bash dispatch
const action: ActionDef = {
  id: `pipeline-${slug}-${stage}`,
  label: `Run ${stage}`,
  dispatch: 'oneshot',  // or custom bash executor
  prompt: assembledPrompt,  // pre-built via MCP get-*-prompt tool
  page: currentPage,
};
await runAction(action);
// Poll for output file existence
```

**When to use**:
- Prompts that are pre-assembled (via MCP tools like `get-smb-stage-prompt`)
- Tasks that produce a single, well-structured output file
- Batch processing (can parallelize multiple stages)
- Background automation (no user interaction needed)

### Tier 2: Embedded CLI (Fallback — Chat Bar)

**When**: Tier 1 output fails validation, or task needs light interactivity.

**Flow**:
```
Dashboard click → embedded CLI in chat bar → agent processes → MCP write → file
Dashboard polls for file → validates → done
(User can see progress in chat bar, can provide feedback)
```

**Characteristics**:
- **Tokens**: ~23,000-25,000 per pipeline (system prompt ~4,000-6,000 tokens)
- **Latency**: 15-40s per stage, 1-3 min full pipeline
- **Overhead**: Agent reasoning loop, 3-4 MCP calls per stage
- **Context window**: ~12% of 200K
- **Cost**: ~$0.10-0.12 per pipeline run
- **Tradeoff**: Blocks chat bar, agent overhead, but can self-recover

**Implementation**:
```typescript
const action: ActionDef = {
  id: `fix-${slug}-${stage}`,
  label: `Fix ${stage} output`,
  dispatch: 'ide',  // routes to embedded CLI when 1 IDE connected
  prompt: `/design-content-pipeline ${slug} ${stage} --feedback "Previous output had structural issues: ${validationError}"`,
  page: currentPage,
};
await runAction(action);
```

**When to use**:
- Tier 1 output failed structural validation
- Tasks that may need clarification or context
- User wants visibility into processing
- First-time runs of new prompt templates

### Tier 3: IDE Dispatch (Escalation — Full Agent)

**When**: Tier 2 fails, or task is exploratory/complex.

**Flow**:
```
Dashboard click → connected IDE (Claude Code) → full agent capabilities → MCP write → file
User monitors in IDE, agent can read files, explore, self-recover
```

**Characteristics**:
- **Tokens**: ~32,000-50,000 per pipeline (system prompt ~10,000+ tokens)
- **Latency**: 30-90s per stage, 2-6 min full pipeline
- **Overhead**: Full agentic loop, 4-6 MCP calls per stage, agent reasoning
- **Context window**: ~25% of 200K
- **Cost**: ~$0.15-0.25 per pipeline run
- **Tradeoff**: Slowest, most expensive, blocks IDE — but most capable

**When to use**:
- Tier 2 failed to produce valid output
- Complex or ambiguous tasks requiring exploration
- Debugging prompt quality issues
- First-time setup of new pipeline stages

## Automatic Escalation Logic

```
User clicks "Run"
  → Tier 1: Oneshot (fast, cheap, ~95% success rate)
  → Validate output file
  → If structurally broken:
      → Attempt Augur lib auto-fix (Tier 0 — no LLM)
      → If still broken: Tier 2 with fix prompt
      → Validate again
      → If still broken: Tier 3 for full investigation
```

### Escalation in Code

```typescript
// Pseudocode for escalation controller
async function executeWithEscalation(slug: string, stage: string) {
  // Tier 1: Oneshot
  await dispatchOneshot(slug, stage);
  const result1 = await pollForOutput(slug, stage, { timeout: 60_000 });
  if (result1 && validateOutput(result1)) return result1;

  // Tier 0: Auto-fix (no LLM)
  if (result1) {
    const fixed = autoRepairOutput(result1);
    if (validateOutput(fixed)) { writeOutput(fixed); return fixed; }
  }

  // Tier 2: Embedded CLI with fix prompt
  const error = describeValidationFailure(result1);
  await dispatchEmbeddedCli(slug, stage, error);
  const result2 = await pollForOutput(slug, stage, { timeout: 180_000 });
  if (result2 && validateOutput(result2)) return result2;

  // Tier 3: Full IDE dispatch
  await dispatchIde(slug, stage, `Tier 1 and 2 failed. Investigate: ${error}`);
  return await pollForOutput(slug, stage, { timeout: 300_000 });
}
```

## File-Based Result Delivery

All tiers write results to files. The dashboard NEVER receives LLM output through HTTP response bodies.

**Pattern**:
1. LLM agent writes output to the canonical file location (e.g., `posts/{slug}/tailored.md`)
2. Dashboard polls a lightweight GET endpoint that checks file existence/mtime
3. When file appears or mtime changes, dashboard reads and renders

**Why file-based**:
- Decouples execution from delivery — any surface (MCP, CLI, IDE) can produce results
- Files are the source of truth — no sync issues between surfaces
- Enables offline/async workflows — CLI can run overnight, dashboard picks up results next morning
- Natural audit trail — every intermediate file is preserved

## Output Validation

After any tier writes an output file, validate before accepting:

### Tier 0: Augur Auto-Fix (No LLM)

Structural repairs that don't need AI:

```typescript
function autoRepairOutput(content: string, expectedFormat: OutputFormat): string | null {
  // 1. Strip LLM preamble ("Here is the content:", "Sure, here's...", etc.)
  content = stripPreamble(content);

  // 2. Fix frontmatter structure
  if (expectedFormat === 'markdown-with-frontmatter') {
    content = repairFrontmatter(content, requiredFields);
  }

  // 3. Fix JSON/YAML structure
  if (expectedFormat === 'json') {
    content = repairJson(content);  // strip markdown fences, fix trailing commas
  }

  // 4. Validate result
  return isValid(content, expectedFormat) ? content : null;
}
```

**Common auto-fixable issues**:
| Issue | Fix |
|-------|-----|
| LLM preamble before content | Strip lines before first `---` or `{` |
| Missing frontmatter delimiters | Wrap with `---` if key: value lines detected |
| Markdown code fences around JSON | Strip `` ```json `` and `` ``` `` |
| Trailing comma in JSON | Remove trailing comma before `}` or `]` |
| Unclosed YAML string | Add closing quote |
| Empty body after frontmatter | Fail — escalate to Tier 2 |
| Wrong encoding/BOM | Strip BOM, normalize to UTF-8 |

### Validation Rules by File Type

**Markdown with frontmatter** (tailored.md, translated.md, variants):
- Has `---` delimiters (opening and closing)
- Required fields present: `stage`, `date`, `status`
- Body non-empty and > 50 characters
- No raw JSON or code blocks as body (indicates LLM formatting error)

**Platform variants** (website.md, facebook.md, instagram.md):
- All 3 files exist after split stage
- Each has frontmatter with `platform` field
- Character count within platform rules (e.g., instagram < 2200 chars)

**JSON files** (brand-profile.json, voice-dna.json):
- Valid JSON (parseable)
- Required top-level keys present
- No null/undefined in required fields

## Token Budget Reference

For a typical 800-word blog draft, full pipeline (tailor → translate → split):

| Component | Tier 1 | Tier 2 | Tier 3 |
|-----------|--------|--------|--------|
| System prompt | 500-2,000 | 4,000-6,000 | 10,000+ |
| Agent reasoning (3 stages) | 0-1,000 | 4,800 | 6,600 |
| MCP overhead | 0-600 | 2,700 | 3,600 |
| Pure content (3 stages) | 11,700 | 11,700 | 11,700 |
| **Total** | **~12-15K** | **~23-25K** | **~32-50K** |
| **Cost (Sonnet)** | ~$0.05-0.07 | ~$0.10-0.12 | ~$0.15-0.25 |
| **Time (full pipeline)** | 20-60s | 1-3 min | 2-6 min |

## CLI Oneshot vs SDK API Direct — Why Not Call the API Directly?

A natural question: why route through a CLI process at all instead of calling the Anthropic SDK directly from a Next.js API route? This section documents the tradeoff analysis.

### Per-Stage Token Breakdown (800-word blog post)

| Component | CLI Oneshot | SDK API Direct |
|-----------|------------|----------------|
| System prompt | ~800-1,500 (CLI minimal mode) | ~200-400 (bare task instructions) |
| Tool definitions | ~300-500 (even minimal set) | 0 |
| Agent reasoning | ~100-300 (parse prompt, decide) | 0 |
| Stage instructions | ~300 | ~300 |
| Context data (brand, voice) | ~600 | ~600 |
| Input content (draft body) | ~1,000 | ~1,000 |
| Output tokens | ~1,200 | ~1,200 |
| **Per-stage total** | **~4,300-5,400** | **~3,300-3,500** |

### Full Pipeline Comparison (3 stages)

| Metric | CLI Oneshot | SDK API Direct | Delta |
|--------|-----------|----------------|-------|
| Total tokens | ~13,200-16,200 | ~9,900-10,500 | -25% to -35% |
| Input cost ($3/M) | $0.029-0.038 | $0.019-0.021 | -35% |
| Output cost ($15/M) | $0.054 | $0.054 | same |
| **Cost per pipeline** | **~$0.08-0.09** | **~$0.07-0.08** | **~$0.01-0.02** |
| Monthly (5 posts/day) | ~$13 | ~$11 | ~$2/mo |

Cost delta is **small** (~15-20%) because output tokens dominate and are identical.

### Latency Comparison

| Phase | CLI Oneshot | SDK API Direct | Delta |
|-------|-----------|----------------|-------|
| Process spawn | 1-3s per stage | 0 | -1-3s |
| CLI initialization | 1-2s per stage | 0 | -1-2s |
| SDK client init | 0 | ~100ms (once) | negligible |
| API round-trip (LLM) | 5-15s per stage | 5-15s per stage | same |
| File write + cleanup | ~0.5s | ~0.1s | -0.4s |
| **Per stage** | **8-20s** | **5-15s** | **-3-5s** |
| **Full pipeline** | **24-60s** | **15-45s** | **-25% to -30%** |

Latency delta is **moderate** — most time is LLM thinking. CLI overhead of ~3-5s per stage adds ~9-15s across 3 stages.

### Infrastructure Overhead

| Concern | CLI Oneshot | SDK API Direct |
|---------|-----------|----------------|
| API key management | CLI handles (user's auth) | Must store in env, rotate, secure |
| Provider switching | CLI handles transparently | Hard-coded to one SDK |
| Rate limiting / retries | CLI handles | Must implement |
| Dependencies | None in dashboard | `@anthropic-ai/sdk` added |
| Error handling | CLI exits with code | Must handle 429s, timeouts, errors |
| Model selection | CLI config | Explicit (more control) |

### Where SDK API Wins

**Prompt caching** — cache system prompt + context across stages. Cached tokens cost $0.30/M instead of $3/M (90% discount). Saves ~$0.005/pipeline and reduces TTFT by 1-2s per stage. CLI may or may not support this transparently.

**Structured output** — JSON mode and tool_use guarantee parseable output, reducing need for Tier 0 auto-repair. CLI oneshot has limited control over these API parameters.

**Parameter control** — temperature, max_tokens, stop sequences are explicit. CLI uses its own defaults.

### Why CLI Oneshot Was Chosen

1. **Critical Rule 11 compliance** — dashboard must not call LLM APIs directly. This is a hard architectural constraint, not a preference.
2. **Provider independence** — native AI-client CLIs handle their own provider routing. SDK locks Augur to one provider.
3. **Zero API key exposure** — no secrets in dashboard environment. CLI manages its own authentication.
4. **Maintenance burden** — CLI handles retries, rate limits, error recovery. SDK approach requires reimplementing all of this.
5. **Marginal savings** — ~$2/month and ~10-15s per pipeline don't justify the architectural cost.

### When to Reconsider

- **>50 posts/day**: Prompt caching savings become meaningful (~$5-10/month)
- **Sub-second latency required**: The 3-5s CLI overhead per stage becomes the bottleneck
- **Structured output critical**: If >5% of Tier 1 outputs need auto-repair, JSON mode could eliminate Tier 0 entirely
- **Dedicated API gateway exists**: If Augur adds a shared LLM proxy service that handles auth/retry/routing, the dashboard could call that instead of the raw SDK — satisfying Rule 7 while getting SDK-level control

## Applicability

This pattern applies to any dashboard feature that needs LLM processing:

- **Content pipeline** (current use case): draft → tailor → translate → split
- **Invoice generation**: data → format → review
- **Career content**: job analysis → resume tailoring → cover letter
- **Code generation**: spec → scaffold → test
- **Any skill with a multi-stage LLM workflow**

The dispatch tier and validation rules are configured per-skill, but the escalation controller and file-polling mechanism are shared infrastructure.
