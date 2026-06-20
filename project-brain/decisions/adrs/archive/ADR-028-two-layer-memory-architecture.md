---
status: Implemented
date: '2026-01-29'
deciders:
- Core team
related: []
hub: null
tags:
- two
- layer
- memory
- architecture
- human
superseded_by: null
---

# ADR-028: Two-Layer Memory Architecture with Human API Profile

**Supersedes**: This ADR consolidates the original ADR-028, ADR-029, and ADR-030

## Context

Augur currently uses ripgrep for full-text search (ADR-004) which works well for document retrieval but lacks:

1. **Session continuity**: No way to answer "what did we decide last week about X?"
2. **Deterministic lookups**: Grep returns matches, not ranked results
3. **Cross-session learning**: Patterns and decisions aren't persisted
4. **Structured metadata**: Can't filter by category, date range, or confidence
5. **User context**: AI doesn't know who the user is, their expertise, or preferences

The Clawdbot memory architecture demonstrates a pattern for local-first agents. The "Human API" concept from hybrid intelligence research frames user context as: **the quality of your AI interface depends on how well you communicate context**.

This pattern aligns with Augur's local-first principles (ADR-006) and extends ADR-004's Markdown RAG pattern to session memory.

## Decision

Implement a **comprehensive memory system** with three integrated components:

1. **Two-Layer Memory**: Daily logs → curated MEMORY.md
2. **Adaptive Rules**: Memory patterns → agent-rules.md evolution
3. **Human API Profile**: Auto-generated user interface for AI interactions

### Architecture Overview

```
data/core/memory/
├── MEMORY.md              # Layer 2: Curated, persistent knowledge
├── HUMAN_API.md           # Auto-generated user profile
├── LEARNED_RULES.md       # Proposed rules (staging area)
├── index.yaml             # YAML index for structured queries
├── daily/                 # Layer 1: Ephemeral session logs
│   ├── 2026-01-29.md
│   └── ...
└── archive/               # Archived daily logs (optional)
```

---

## Part 1: Two-Layer Memory

### Layer 1: Daily Logs (Ephemeral)

**Purpose**: Capture raw session events for later distillation

**Contents**:
```markdown
# Session Log: 2026-01-29

## 09:15 - Context Switch
- From: /career
- To: /health
- Tools loaded: [health-tracker, medication-reminder]

## 09:18 - Decision Made
**Topic**: Medication schedule
**Decision**: Take vitamin D in morning, not evening
**Reasoning**: Better absorption with breakfast
**Confidence**: High (doctor recommendation)
```

**Lifecycle**:
- Auto-created on first session event each day
- Rotated after 14 days (configurable)
- Parsed and distilled into MEMORY.md via curation

### Layer 2: Curated MEMORY.md (Persistent)

**Purpose**: Distilled decisions, patterns, and preferences

**Structure**:
```markdown
# Augur Memory

*Last curated: 2026-01-29*

## Decisions

### Health
- **Vitamin D timing**: Morning with breakfast (2026-01-29)
  - Source: Doctor recommendation
  - Confidence: High

## Learned Patterns

### Workflow Patterns
- User switches to /health most often on Monday mornings
- Career-related tasks cluster on Tuesday/Wednesday

## User Preferences

### Communication
- Prefers concise responses
- Dislikes excessive emojis
- Wants tables over prose
```

### Hybrid Search (Ripgrep + YAML Index)

Following ADR-004's pattern, we use ripgrep for fast full-text search combined with a YAML index for structured metadata queries:

**YAML Index** (index.yaml):
```yaml
version: "1.0"
updated: "2026-01-29T10:00:00"
entries:
  - key: "Vitamin D timing"
    category: decision
    date: "2026-01-29"
    file_path: "/data/core/memory/MEMORY.md"
    line_number: 12
    tags: [health, medication]
```

**Search modes**:
| Mode | Use Case | Implementation |
|------|----------|----------------|
| `keyword` | Fast text search | ripgrep |
| `metadata` | Structured queries | YAML index |
| `hybrid` | Combined search | ripgrep + YAML |

---

## Part 2: Adaptive Agent Rules

### Memory-to-Rules Pipeline

```
┌─────────────────┐
│  Daily Logs     │  Session events
└────────┬────────┘
         ↓ curate
┌─────────────────┐
│   MEMORY.md     │  Curated patterns with confidence scores
└────────┬────────┘
         ↓ analyze
┌─────────────────┐
│ LEARNED_RULES.md│  Proposed rules (staging area)
└────────┬────────┘
         ↓ review (human approval)
┌─────────────────┐
│ agent-rules.md  │  "Learned Rules" section
└────────┬────────┘
         ↓ generate
┌─────────────────┐
│   CLAUDE.md     │  Final agent instructions
└─────────────────┘
```

### Confidence Scoring & Decay

Each learned pattern has:
- **confidence**: 0.0 - 1.0 (based on occurrence frequency and consistency)
- **occurrences**: number of times observed
- **last_seen**: date of most recent observation
- **contradictions**: count of opposing patterns

**Promotion threshold**: confidence ≥ 0.8 AND occurrences ≥ 5

**Decay rules**:
- confidence -= 0.1 per month of inactivity
- confidence -= 0.2 per contradiction
- Rule removed when confidence < 0.5

### Learned Rules Section

Added to `docs/agent-rules.md`:
```markdown
## 🧠 Learned Rules (Auto-Generated)

*These rules were derived from session memory. Last synced: 2026-01-29*
*Review and edit as needed. Remove rules that no longer apply.*

### Code Style (confidence: 0.92)
- Prefer 2-space indentation for TypeScript files
- Use named exports over default exports

### Preferences (confidence: 0.88)
- Avoid adding console.log statements
- Prefer functional components over class components
```

---

## Part 3: Human API Profile

### HUMAN_API.md - Auto-Generated User Interface

**Purpose**: Structured profile that helps AI understand how to work with the user effectively

**Location**: `data/core/memory/HUMAN_API.md`

**Structure**:
```markdown
# Human API Profile

*Auto-generated from session memory. Last updated: 2026-01-29*
*This profile helps AI understand how to work with you effectively.*

## Identity

### Role & Authority
- **Primary Role**: Founder & Lead Developer
- **Authority Level**: Vision holder, final decision maker
- **Responsibilities**: Architecture, product direction, technical implementation

### Expertise (What I Know That AI Doesn't)
- Project history and why decisions were made
- Business context and strategic priorities
- User needs and product vision
- Codebase patterns and conventions

### Domain Knowledge
- TypeScript, Next.js, Python, system architecture
- Personal knowledge management systems
- AI/LLM integration patterns

## Communication Preferences

### How I Prefer Information
- **Format**: Concise, tables over prose, code examples
- **Length**: Brief explanations, expand on request
- **Tone**: Direct, technical, no fluff
- **Structure**: Options with trade-offs, then I choose

### Decision Style
- Present options with pros/cons
- I make final calls on architecture
- Prefer working code over perfect code

## Work Patterns

### Common Tasks
- Building dashboard features
- Writing Python automation scripts
- Creating ADRs for architecture decisions
- Plugin development

### Success Criteria
- Follows existing patterns in codebase
- Respects plugin architecture (ADR-018)
- No hardcoded paths (critical rule)
- Working > perfect

## Context Gaps (What to Ask About)
- Current business priorities
- Timeline/urgency of tasks
- Integration with other plugins
```

### Profile Generation Pipeline

```
MEMORY.md (patterns)
       ↓
Profile Synthesizer (memory_sync.py --profile)
       ↓
HUMAN_API.md (structured profile)
       ↓
Loaded at session start via /load-context
```

### 10-Second Protocol (Automatic)

The Human API profile answers the "10-second protocol" questions automatically:

| Question | Answered By |
|----------|-------------|
| What do I know that AI doesn't? | Identity.Expertise + Context Gaps |
| What does AI need to give useful output? | Communication Preferences |
| If answer misses, what to check? | Context Gaps section |

### Initial Profile Interview

During onboarding (`/onboarding` workflow), a structured interview seeds the initial profile:

1. **Role Discovery**: "What's your primary role? (Developer, Manager, Founder, etc.)"
2. **Expertise Mapping**: "What domains do you have deep expertise in?"
3. **Communication Style**: "How do you prefer to receive information?"
4. **Success Criteria**: "What makes a response 'good' for you?"

This interview runs once and can be re-triggered via dashboard settings.

---

## Single Command: `/memory-sync`

```bash
# Full pipeline
/memory-sync

# Or via Python script
python3 .github/scripts/memory_sync.py [--review] [--apply] [--profile] [--ci]
```

**Modes**:
- `--review`: Generate LEARNED_RULES.md proposals only (default)
- `--apply`: Apply approved rules to agent-rules.md
- `--profile`: Regenerate HUMAN_API.md profile
- `--ci`: Run in CI mode (cleanup + review + profile, no apply)

---

## Integration Points

### MCP Tools

| Tool | Description |
|------|-------------|
| `memory-search` | Search decisions, patterns, preferences |
| `memory-log-decision` | Log a decision to daily log |
| `memory-log-preference` | Log a user preference |
| `memory-curate` | Distill daily logs to MEMORY.md |
| `memory-stats` | Get memory system statistics |
| `get-context` | Returns context including HUMAN_API.md profile |

### Context Injector Integration

```python
# In context_injector.py
@dataclass
class HumanApiProfile:
    exists: bool = False
    role: str = ""
    expertise: list[str] = field(default_factory=list)
    communication_style: str = ""
    success_criteria: list[str] = field(default_factory=list)
    context_gaps: list[str] = field(default_factory=list)

def build_context(self, skill_hint=None, include_memory=True):
    context = self._build_base_context(skill_hint)
    context.human_api_profile = self._load_human_api_profile()

    if include_memory:
        memory_results = memory_search(query=skill_hint, top_k=3)
        context.memory_insights = memory_results

    return context
```

### Dashboard Integration

| Feature | Location | Purpose |
|---------|----------|---------|
| Profile Viewer/Editor | `/settings` → Memory section | View and edit HUMAN_API.md |
| Memory Search | `/brain/memory` | Search memories with filters |
| Daily Log Calendar | `/brain/memory` | Browse daily logs by date |
| Memory Stats | `/brain/memory` | View memory system health |

### CI Integration (Nightly Job)

```python
# In nightly_maintainer.py
def main():
    # ... existing steps ...

    # Memory sync (ADR-028: curate daily logs, propose rules, update profile)
    run_memory_sync(project_root)
```

---

## Consequences

### Positive

- **Deterministic answers**: "What did we decide about X?" becomes a lookup
- **Session continuity**: Decisions persist across conversations
- **Local-first**: Plain files, no external service or binary dependencies
- **Human-readable**: All files are markdown, git-trackable
- **Consistent with ADR-004**: Uses ripgrep pattern already established
- **Personalized AI**: Human API profile provides automatic context
- **Evolving rules**: Agent behavior improves based on actual usage
- **Founder context**: Vision and business context properly captured

### Negative

- **No semantic search**: Must use exact keywords or synonyms
- **Curation overhead**: MEMORY.md needs periodic distillation
- **Profile maintenance**: HUMAN_API.md needs periodic updates
- **Review discipline**: LEARNED_RULES.md proposals need human review
- **Initial setup**: Profile interview needed during onboarding

### Risks

- Over-reliance on profile vs asking clarifying questions
  - Mitigation: Profile includes "Context Gaps" section
- Over-aggressive rule promotion cluttering agent-rules.md
  - Mitigation: Conservative thresholds (0.8 confidence, 5 occurrences)
- Profile may drift if patterns change
  - Mitigation: Nightly profile regeneration

---

## Implementation

### Location

Memory is implemented as part of the **Knowledge plugin** (`plugins/ai/skills/knowledge/`):

| Component | File | Purpose |
|-----------|------|---------|
| DailyLogger | `mcp/memory/daily_logger.py` | Log session events |
| MemoryStore | `mcp/memory/memory_store.py` | Manage MEMORY.md |
| MemorySearcher | `mcp/memory/search.py` | Ripgrep + YAML search |
| MemoryCurator | `mcp/memory/curator.py` | Distill daily logs |
| ProfileGenerator | `mcp/memory/profile.py` | Generate HUMAN_API.md |

### Management Script

`/.github/scripts/memory_sync.py` handles:
1. Cleanup temp files (with memory preservation)
2. Curate daily logs → MEMORY.md
3. Analyze memory → LEARNED_RULES.md proposals
4. Generate/update HUMAN_API.md profile

### Dashboard UI Components

| Component | File | Purpose |
|-----------|------|---------|
| MemorySection | `components/MemorySection.tsx` | Settings page integration |
| ProfileEditor | `brain/memory/ProfileEditor.tsx` | Edit HUMAN_API.md |
| MemorySearch | `brain/memory/MemorySearch.tsx` | Search interface |
| DailyLogCalendar | `brain/memory/Calendar.tsx` | Browse daily logs |

---

## Alternatives Considered

### Alternative 1: SQLite FTS5 + sqlite-vec
Rejected: Adds binary dependency, violates ADR-004's "no vector DB" principle

### Alternative 2: Full Vector Database (ChromaDB)
Rejected: Violates local-first, overkill for memory use case

### Alternative 3: Manual Profile Maintenance
Rejected: Users won't maintain profiles; auto-generation from patterns is more reliable

### Alternative 4: Static Agent Rules Only
Rejected: Misses opportunity for system to learn and improve from actual usage

---

## References

- [ADR-004](./ADR-004-markdown-rag.md) - Markdown RAG decision
- [ADR-006](./ADR-006-local-first.md) - Local-first architecture
- [ADR-012](./ADR-012-plugin-extraction-guide.md) - Plugin extraction guide
- [Clawdbot Memory Architecture](https://github.com/activus-d/clawdbot) - Inspiration
- "Human API" concept from hybrid intelligence research
- `plugins/ai/skills/knowledge/augur/memory/` - Implementation
- `.github/scripts/memory_sync.py` - Management script
