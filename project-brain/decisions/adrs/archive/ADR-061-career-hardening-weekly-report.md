---
status: Implemented
date: '2026-02-10'
deciders:
- Gur Sannikov
- Claude
related:
- ADR-057 (Memory System Alignment)
- ADR-028 (Two-Layer Memory)
- ADR-046 (Crew Orchestration Bridge)
- ADR-060 (External Execution Mode)
hub: null
tags:
- career
- hardening
- cross
- session
- weekly
superseded_by: null
---

# ADR-061: Career Hardening — Cross-Session Weekly Report & Knowledge Retention

## Context

Users of the Augur system work across multiple AI interfaces daily — Claude Code, Cursor, Windsurf, Kimi, ChatGPT, Antigravity, Copilot, and others. Each session generates memory traces (daily logs, commit messages, session transcripts), but there is no mechanism to **aggregate this cross-tool activity into a coherent career narrative** and, critically, no way to **harden the user's own retention** of what they learned.

### The Problem

Today's knowledge workers operate through AI as their primary interface — whether coding, writing marketing copy, doing financial analysis, or managing projects. This creates a paradox:

| Symptom | Root Cause |
|---------|-----------|
| "What did I even do last week?" | Work is scattered across 5+ AI tools with no unified view |
| "I did this before but can't remember how" | AI did the heavy lifting; user memory didn't encode it |
| "My resume is 3 months stale" | No feedback loop from daily work to career artifacts |
| "I'm preparing for an interview but forgot half my projects" | No spaced repetition or active recall practice on own work |

### Existing Infrastructure

The building blocks already exist:

1. **Daily memory logs** (`data/core/memory/daily/*.md`) — every session writes decisions, patterns, and insights via post-commit hooks and `/learn`
2. **Memory sync pipeline** (`memory_sync.py`) — curates daily logs into MEMORY.md, distributes to all agents
3. **AI Bridge session tracking** (`usage_tracker.py`) — logs LLM API calls, tokens, costs per provider per day
4. **Career skill** (`plugins/career/skills/career/`) — 11 tabs covering job pipeline, interview prep, STAR stories, learning, knowledge, resume, habits
5. **Ripgrep-based search** (ADR-004) — fast content search across markdown files, the project's chosen RAG approach
6. **Chain executor** (`chain_executor.py`) — multi-step workflow orchestration with offload support

What's missing: a **synthesis layer** that reads across all these sources and produces (a) a weekly activity report, and (b) an interactive hardening experience that transfers knowledge from AI-mediated work back into the user's brain.

### User Story

A user working as a software engineer uses Claude Code for coding, Cursor for frontend, ChatGPT for design brainstorming, and Kimi for documentation. On Friday afternoon, they navigate to the Career Hub → Hardening tab and click "Generate Report." The system:

1. Scans daily logs, commit history, and session data for the past 7 days
2. Produces a structured report: topics worked on, technologies used, problems solved, patterns learned
3. Offers action buttons: **Harden Knowledge**, **Update CV**, **Update Learning Targets**, **Suggest Roles & Companies**

Clicking "Harden Knowledge" generates a quiz based on what the user actually did — starting easy, progressing to hard, in groups of 10. Getting all 10 right unlocks the next difficulty tier. The goal: transfer AI-mediated knowledge into long-term human memory.

## Decision

### 1. New Career Tab: "Hardening"

Add a `hardening/` tab to the career dashboard with three views:

| View | Route | Purpose |
|------|-------|---------|
| **Report** | `/career/hardening` (default) | Weekly activity report with date range selector |
| **Quiz** | `/career/hardening/quiz` | Interactive knowledge retention questionnaire |
| **History** | `/career/hardening/history` | Past reports and quiz scores over time |

### 2. Cross-Session Activity Aggregator

A Python script (`career_hardening.py`) that aggregates activity from all available sources:

**Data Sources (Priority Order)**:

| Source | What It Provides | Collection Method |
|--------|-----------------|-------------------|
| Daily memory logs (`data/core/memory/daily/*.md`) | Decisions, patterns, insights per session | ripgrep scan for entries in date range |
| Git commit history | Code changes, features built, bugs fixed | `git log --after={start} --before={end} --format` |
| LLM usage tracker (`data/factory/devops/llm_usage.json`) | Provider usage, session frequency, token volume | JSON read + date filter |
| MEMORY.md curated entries | Persistent knowledge, architectural decisions | ripgrep for date-tagged entries |
| Career data (`data/career/`) | Job applications, interview prep, learning progress | YAML scan |
| User-attached external files | PDFs, notes, screenshots, docs from outside the system | Manual upload via dashboard or CLI |

**External File Ingestion**:

Users work in tools beyond Augur's tracking — Google Docs, Notion, Confluence, Slack threads, meeting notes, exported ChatGPT conversations, design tool exports, etc. The system must accept these as supplementary context:

```
# Via CLI
python3 career_hardening.py --action attach \
    --file ~/Downloads/meeting-notes-2026-02-07.md \
    --tag "architecture,planning" \
    --period 2026-W06

# Via dashboard
Upload button on the Report page → drag & drop or file picker
Supported: .md, .txt, .pdf, .yaml, .json, .png, .jpg (images stored, text extracted)
```

Attached files are stored in `data/career/hardening/attachments/` with metadata:

```yaml
# data/career/hardening/attachments/index.yaml
- file: "meeting-notes-2026-02-07.md"
  attached: "2026-02-10T14:30:00"
  tags: ["architecture", "planning"]
  period: "2026-W06"
  source: "manual"  # manual | cli | api
  summary: null      # AI-generated on first report inclusion
```

When generating a report, the aggregator scans `attachments/index.yaml` for files matching the date range, reads their content (text extraction for PDFs via Python `pdfplumber` or similar — plugin-local dependency), and includes them as an additional source category. The AI summarizes each attachment on first inclusion and caches the summary.

**Aggregation Pipeline**:

```
1. Collect: ripgrep + git log + JSON reads across all sources
2. Deduplicate: Same decision appearing in daily log + MEMORY.md → merge
3. Categorize: Tag each entry (coding, architecture, debugging, learning, career, ops)
4. Summarize: Group by category, extract key topics and technologies
5. Output: Structured JSON → rendered as report in dashboard
```

**Date Range Support**:

```
--range day      # Last 24 hours
--range week     # Last 7 days (default)
--range month    # Last 30 days
--range custom   # User specifies start/end dates
```

### 3. Report Structure

The generated report follows this schema:

```yaml
report:
  period:
    start: "2026-02-03"
    end: "2026-02-10"
    range: "week"

  summary:
    total_sessions: 14
    total_commits: 23
    total_decisions: 31
    primary_focus: "orchestration, memory system, MCP tools"
    technologies: ["Python", "TypeScript", "Next.js", "MCP", "YAML"]

  categories:
    - name: "Architecture & Design"
      entries:
        - "ADR-057: Memory System Alignment — simplified pipeline, multi-agent sync"
        - "ADR-060: External Execution Mode — cross-CLI orchestration"
      weight: 0.35  # 35% of week's effort

    - name: "Implementation"
      entries:
        - "CLIBridge integration with 10 CLI tools, 120 tests"
        - "Plugin template standard (ADR-040)"
      weight: 0.40

    - name: "DevOps & Hardening"
      entries:
        - "Nightly lint fixes, test repairs, CI pipeline"
        - "Plugin health sweep"
      weight: 0.20

    - name: "Career & Learning"
      entries:
        - "Updated 4 CV variants"
      weight: 0.05

  external_files:
    - file: "meeting-notes-2026-02-07.md"
      tags: ["architecture", "planning"]
      summary: "Sprint planning for orchestration layer — discussed external execution..."

  hardening_candidates:
    # Topics suitable for quiz generation
    - topic: "MCP Protocol"
      depth: "deep"
      source_count: 8
    - topic: "Memory Architecture"
      depth: "medium"
      source_count: 5
    - topic: "Plugin Self-Containment"
      depth: "shallow"
      source_count: 2

  recommended_reading:
    # AI-curated resources to deepen understanding of worked topics
    - topic: "MCP Protocol"
      resources:
        - type: "article"
          title: "Model Context Protocol Specification"
          url: "https://modelcontextprotocol.io/specification"
          reason: "You implemented 3 MCP tools this week — reading the spec will solidify your understanding of the protocol lifecycle"
          estimated_time: "20 min"
        - type: "documentation"
          title: "MCP Python SDK — Tool Registration Patterns"
          url: "https://github.com/modelcontextprotocol/python-sdk"
          reason: "Directly relevant to the orchestration tools you built in ADR-060"
          estimated_time: "15 min"
    - topic: "Memory Architecture"
      resources:
        - type: "paper"
          title: "Ebbinghaus Forgetting Curve and Spaced Repetition"
          reason: "Foundational to the hardening quiz system you're building"
          estimated_time: "30 min"
        - type: "article"
          title: "Two-Layer Memory Systems in Personal Knowledge Management"
          reason: "Parallels to ADR-057's daily logs + curated MEMORY.md architecture"
          estimated_time: "10 min"
```

### 4. Knowledge Hardening Quiz System

The quiz system transforms the report into active recall exercises:

**Quiz Generation Flow**:

```
Report → Extract hardening_candidates → AI generates questions → User answers → Score → Next tier
```

**Question Types**:

| Type | Format | Example |
|------|--------|---------|
| Multiple Choice | 4 options, 1 correct | "Which ADR introduced external execution mode? A) ADR-057 B) ADR-060 C) ADR-046 D) ADR-054" |
| Free Answer | Text input, AI-graded | "Explain the difference between `--external` and `--mode remote` in chain_executor.py" |
| Code Recall | Code snippet with blanks | "Fill in the missing flag: `python3 swarm_executor.py --preset _____ --input 'task'`" |
| Architecture | Diagram/flow question | "What is the fallback order when preferred_cli is set to 'auto'?" |

**Difficulty Tiers**:

| Tier | Question Style | Unlock Criteria |
|------|---------------|-----------------|
| 1: Recognition | "Which of these did you work on?" | Default (always available) |
| 2: Recall | "What was the purpose of X?" | ≥8/10 on Tier 1 |
| 3: Application | "How would you apply X to solve Y?" | ≥8/10 on Tier 2 |
| 4: Analysis | "Compare approaches A and B — which is better for Z and why?" | ≥8/10 on Tier 3 |
| 5: Synthesis | "Design a solution using concepts from this week" | ≥8/10 on Tier 4 |

Based on Bloom's Taxonomy: Remember → Understand → Apply → Analyze → Create.

**Session Format**:
- 10 questions per round
- Mixed types within a round
- ≥8/10 correct → option to generate next 10 at higher tier
- <8/10 → review incorrect answers with explanations, retry same tier
- Progress saved to `data/career/hardening/sessions/`

### 5. External File Ingestion

Users produce and consume knowledge artifacts outside of Augur-tracked tools — meeting notes, design docs, Slack exports, ChatGPT conversation exports, Confluence pages, PDF whitepapers, handwritten notes (photos). The hardening system must accept these to build a complete picture.

**Input Methods**:

| Method | UX | When |
|--------|-----|------|
| **Dashboard upload** | Drag & drop zone on Report page, or file picker button | During report review — "I also did this meeting" |
| **CLI attach** | `career_hardening.py --action attach --file <path> --tag <tags>` | From any terminal session |
| **MCP tool** | `career-hardening-attach` tool with `file_path` and `tags` args | From any AI IDE |
| **Watched folder** | Auto-scan `data/career/hardening/inbox/` on report generation | Drop files anytime, they get picked up on next report |

**Processing Pipeline**:

```
File dropped / attached
    ↓
Detect format: .md/.txt → read directly
               .pdf → extract text (pdfplumber, plugin-local dep)
               .json/.yaml → parse and summarize
               .png/.jpg → store as-is, flag for future OCR (Phase 2)
               .html → extract text (strip tags)
    ↓
Store in data/career/hardening/attachments/{period}/
    ↓
Update attachments/index.yaml with metadata
    ↓
On report generation → AI summarizes content → cached in index.yaml
    ↓
Summary included in report under external_files section
    ↓
Hardening candidates enriched with external file context
```

**Tag Taxonomy** (suggested, user can add custom):

| Tag | For |
|-----|-----|
| `architecture` | Design decisions, system diagrams |
| `meeting` | Meeting notes, standup summaries |
| `learning` | Course notes, tutorial takeaways |
| `research` | Papers, articles, competitive analysis |
| `communication` | Emails, Slack threads, presentations |
| `debugging` | Bug reports, postmortems, incident notes |
| `planning` | Roadmaps, sprint plans, OKRs |

### 6. AI-Curated Reading & Resource Suggestions

After generating a report, the AI analyzes the user's worked topics and recommends external resources to develop a **deeper, more holistic understanding** — not just recall what was done, but understand the underlying principles.

**Why This Matters**:

Working through AI creates a "knowledge iceberg" problem — the user touches the surface of many topics but may not understand the foundations. A user who implemented MCP tools all week benefits from reading the protocol spec. A user who wrote database migrations benefits from reading about schema evolution patterns. The AI bridges the gap between *doing* and *understanding*.

**Resource Types**:

| Type | Description | Example |
|------|-------------|---------|
| `article` | Blog posts, technical articles | "Understanding the Actor Model" after working on agent orchestration |
| `documentation` | Official docs for tools/frameworks used | Next.js App Router docs after dashboard work |
| `paper` | Academic or industry papers | "Spaced Repetition" paper after building the quiz system |
| `video` | Conference talks, tutorials | "MCP Deep Dive" talk after implementing MCP tools |
| `book_chapter` | Specific chapters, not full books | "Designing Data-Intensive Applications, Ch. 5" after working on data pipelines |
| `course` | Online courses or modules | "TypeScript Advanced Patterns" after heavy TS work |

**Generation Flow**:

```
Report categories + technologies + hardening_candidates
    ↓
AI prompt: "Given this user worked on {topics} using {technologies},
           suggest 2-3 resources per major topic that would deepen
           their understanding. Prioritize:
           1. Foundational knowledge they likely applied implicitly
           2. Best practices they might have missed
           3. Adjacent concepts that would make their work more robust
           Include estimated reading time and a 1-sentence reason
           specific to what they did this week."
    ↓
Output: recommended_reading section in report YAML
    ↓
Dashboard renders as "Recommended Reading" panel on report page
    ↓
User can:
  - Click to open resource (external link)
  - Mark as "read" → included in next hardening quiz
  - Dismiss → AI learns preference, suggests less of that type
  - Save to reading list → data/career/learning/reading-list.yaml
```

**Integration with Quiz System**:

Resources marked as "read" get folded into the next hardening quiz at Tier 3+ (Application/Analysis). This creates a powerful learning loop:

```
Do the work → Report what you did → Read the theory behind it → Quiz on both practice AND theory
```

**Personalization Signals**:

| Signal | Effect on Suggestions |
|--------|----------------------|
| User's career profile (`data/career/profile/candidate.md`) | Weight suggestions toward career goals (e.g., "moving to architecture role" → more design pattern articles) |
| Previous quiz scores by topic | Low scores → suggest more foundational resources; high scores → suggest advanced/adjacent material |
| Reading history (read/dismissed) | Learn preference for format (prefers articles over videos), depth (prefers quick reads), and topics (skip marketing, love systems design) |
| Current learning targets (`data/career/learning/`) | Align suggestions with active learning goals |

**Data Storage**:

```yaml
# data/career/hardening/reading/preferences.yaml
preferred_formats: ["article", "documentation", "paper"]
dismissed_topics: ["marketing", "sales"]
max_suggestions_per_topic: 3
preferred_language: "en"
max_estimated_time: "30 min"  # per resource

# data/career/hardening/reading/history.yaml
- url: "https://modelcontextprotocol.io/specification"
  topic: "MCP Protocol"
  status: "read"           # read | dismissed | saved | in-progress
  read_date: "2026-02-10"
  included_in_quiz: "2026-02-14T10-00"  # quiz session that tested this
  user_rating: 4           # 1-5, optional
```

### 7. Future: Multi-Modal Hardening (Phase 2+)

Flagged for future implementation — not in scope for Phase 1 but architecturally planned:

| Modality | Mechanism | Brain Impact |
|----------|-----------|-------------|
| **Visual** | Generate diagrams/flowcharts from report data, quiz with visual questions | Dual-coding theory — visual + verbal = stronger encoding |
| **Voice** | Text-to-speech for questions, speech-to-text for answers | Auditory encoding, production effect (saying it aloud improves recall) |
| **Spaced Repetition** | Re-quiz on topics from 1, 3, 7, 14 days ago | Ebbinghaus forgetting curve — optimal re-testing intervals |
| **Interleaving** | Mix topics from different weeks in later quizzes | Interleaved practice > blocked practice for long-term retention |

Data model includes `next_review_date` and `ease_factor` fields on each quiz entry to support spaced repetition when implemented.

### 8. Career Impact Buttons

After viewing the report, the user can trigger downstream career actions:

| Button | Action | Flow | Target |
|--------|--------|------|--------|
| **Harden Knowledge** | Generate quiz from report | Navigate to `/career/hardening/quiz` | Quiz system (Section 4) |
| **Update CV** | AI suggests CV additions based on week's work | `flow: llm` → IDE chat with report context | `/career/resume` tab |
| **Update Learning Targets** | AI identifies skill gaps from work patterns | `flow: llm` → IDE chat with report + current targets | `/career/learning` tab |
| **Suggest Companies & Roles** | AI matches week's demonstrated skills to job market | `flow: llm` → IDE chat with report + career profile | `/career/companies` tab |

These follow the existing central action button pattern (dashboard.yaml actions with `flow: llm`).

### 9. Data Storage

```
data/career/hardening/
├── reports/
│   ├── 2026-W06.yaml          # Weekly report (ISO week)
│   ├── 2026-02-10.yaml        # Daily report (if generated)
│   └── 2026-01.yaml           # Monthly report
├── sessions/
│   ├── 2026-02-10T14-30.yaml  # Quiz session with scores
│   └── ...
├── questions/
│   └── bank.yaml              # Generated question bank for reuse
├── attachments/
│   ├── index.yaml             # Metadata for all attached files
│   ├── 2026-W06/              # Files grouped by period
│   │   ├── meeting-notes.md
│   │   └── design-review.pdf
│   └── inbox/                 # Watched folder — auto-picked up on report gen
├── reading/
│   ├── preferences.yaml       # Format/topic preferences for suggestions
│   └── history.yaml           # Read/dismissed/saved tracking per resource
└── config.yaml                # Hardening preferences (difficulty, question count)
```

### 10. MCP Tools

Register three new MCP tools for cross-IDE access:

| Tool | Args | Description |
|------|------|-------------|
| `career-hardening-report` | `range: day\|week\|month\|custom`, `start?`, `end?` | Generate activity report. Returns structured YAML. |
| `career-hardening-attach` | `file_path`, `tags?`, `period?` | Attach an external file to the hardening system. Copies file, updates index. |
| `career-hardening-reading` | `action: list\|mark-read\|dismiss\|save`, `url?` | Manage reading suggestions — list current, mark as read, dismiss, or save to reading list. |

The quiz generation and grading use `flow: llm` (IDE chat) rather than MCP — the AI needs conversational context to generate good questions and evaluate free-form answers.

### 11. Implementation Architecture

```
User clicks "Generate Report"
    ↓
Dashboard calls API route → /api/career/hardening/report
    ↓
API route invokes: python3 plugins/career/skills/career/scripts/career_hardening.py \
    --action report --range week
    ↓
career_hardening.py:
    1. ripgrep data/core/memory/daily/ for date range
    2. git log --after --before
    3. Read data/factory/devops/llm_usage.json
    4. Read data/core/memory/MEMORY.md for curated entries
    5. Scan data/career/ for recent changes
    6. Scan data/career/hardening/attachments/index.yaml for external files in range
    7. Read & summarize attached files (cache summaries)
    8. Aggregate → Categorize → Weight
    9. Write report to data/career/hardening/reports/
   10. Return JSON to dashboard
    ↓
Dashboard renders report with action buttons + "Recommended Reading" panel
    ↓
AI generates reading suggestions based on report topics + user profile
    ↓
User can: open links, mark read, dismiss, save to reading list
    ↓
Dashboard renders report with action buttons
    ↓
User clicks "Harden Knowledge"
    ↓
Dashboard navigates to /career/hardening/quiz
    ↓
Quiz page sends report + config to IDE via flow: llm
    ↓
AI generates 10 questions at Tier 1 → User answers → Score → Next tier
```

## Consequences

### Positive

- **Cross-tool visibility**: First unified view of work across all AI interfaces
- **Knowledge retention**: Active recall transfers AI-mediated work into human memory
- **Career artifact freshness**: Automatic prompt to update CV, learning targets from actual work
- **Bloom's Taxonomy progression**: Structured depth (recognition → synthesis) prevents shallow skimming
- **Leverages existing infrastructure**: Daily logs, memory pipeline, ripgrep search, career skill, action button pattern — no new frameworks needed
- **Universal access**: MCP tools mean any CLI can generate reports, attach files, and manage reading — not just the dashboard
- **External file ingestion**: Users can plug in knowledge from any source (meeting notes, Notion exports, ChatGPT conversations) — the system adapts to how people actually work
- **Reading suggestions close the theory gap**: Users don't just recall what they did — they understand the principles behind it, creating deeper competence
- **Learning loop**: Do → Report → Read theory → Quiz on both practice AND theory — a complete knowledge retention cycle

### Negative

- **AI dependency for quiz generation and reading suggestions**: Both require LLM calls — adds cost per hardening session
- **Report quality depends on log quality**: Sparse daily logs → sparse reports. External files mitigate this but require manual effort
- **Multi-modal features deferred**: Voice and visual hardening require additional infrastructure (TTS/STT, diagram generation) — not in Phase 1
- **Quiz grading for free-form answers is imprecise**: AI grading isn't perfect, especially for nuanced technical answers

### Neutral

- Daily log format unchanged — the aggregator reads whatever exists
- Memory pipeline (ADR-057) unchanged — report reads from it, doesn't write to it
- Career skill's existing 11 tabs unaffected — hardening is additive
- Action button pattern (dashboard.yaml) unchanged — new buttons follow existing conventions

## Alternatives Considered

### Alternative 1: Standalone Weekly Digest Email

Generate and send a weekly email summary instead of an in-app experience. Rejected because:
- Passive consumption (reading an email) doesn't create memory traces
- No interactive hardening component possible via email
- Doesn't leverage the existing dashboard infrastructure
- Can't trigger downstream career actions (CV update, etc.)

### Alternative 2: Automatic Daily Quizzes

Generate quiz questions after every session automatically. Rejected because:
- Too frequent — quiz fatigue reduces engagement
- Individual sessions lack enough context for meaningful questions
- Weekly aggregation provides better topic diversity and deeper questions
- Users should control when they harden (Friday afternoon ritual, not constant interruption)

### Alternative 3: Integration with External Spaced Repetition Tools (Anki, etc.)

Export questions to Anki or similar SRS apps. Rejected for Phase 1 because:
- Adds external dependency (breaks local-first, ADR-006)
- Loses the tight integration with career actions (CV update, role matching)
- Can be added as a Phase 2 export option without architectural changes

## References

- `data/core/memory/daily/` — daily session logs (primary data source)
- `.github/scripts/memory_sync.py` — memory curation pipeline
- `plugins/career/skills/career/` — career skill (host for new tab)
- `plugins/career/skills/career/augur.yaml` — dashboard tab/action configuration
- `plugins/ai/skills/ai_bridge/scripts/usage_tracker.py` — LLM session tracking
- `data/career/learning/` — existing learning targets (consumed by reading suggestions)
- `data/career/profile/candidate.md` — career profile (personalizes reading suggestions)
- ADR-004: Markdown RAG (ripgrep-based search pattern)
- ADR-006: Local-first architecture (reading suggestions stay local, links are external)
- ADR-018: Plugin self-containment (pdfplumber goes in career skill's requirements.txt)
- ADR-057: Memory System Alignment (canonical memory source)
- Bloom's Taxonomy: Anderson & Krathwohl (2001) — cognitive domain framework for quiz tiers
- Ebbinghaus, H. (1885) — forgetting curve (spaced repetition foundation)
- Dual-coding theory: Paivio (1986) — visual + verbal encoding for Phase 2 multi-modal

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-061: Career Hardening — Cross-Session Weekly Report & Knowledge Retention**.

Read the full ADR: `docs/decisions/ADR-061-career-hardening-weekly-report.md`

**Team name**: `adr-061-career-hardening`

### Phase 1: Backend — Activity Aggregator Script
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create `career_hardening.py` in career scripts. Implement `collect_daily_logs(start, end)` — ripgrep scan of `data/core/memory/daily/*.md` for entries in date range. Implement `collect_git_history(start, end)` — parse `git log` output. Implement `collect_llm_usage(start, end)` — read usage tracker JSON. Implement `collect_external_files(start, end)` — scan `attachments/index.yaml` for files matching period, read content, generate/cache summaries. | `plugins/career/skills/career/scripts/career_hardening.py` |
| 1.2 | developer | medium | Add `aggregate_report(sources)` — deduplicate, categorize entries (architecture, implementation, devops, career, learning), compute weights, extract technologies and topics. Add `identify_hardening_candidates(categorized)` — rank topics by depth (source_count) for quiz generation. Include external file summaries in categorization. | `plugins/career/skills/career/scripts/career_hardening.py` |
| 1.3 | developer | medium | Add `attach_file(file_path, tags, period)` — copy file to `attachments/{period}/`, update `index.yaml`, detect format and extract text for `.md/.txt/.html/.json/.yaml` (PDF support via optional `pdfplumber` in plugin requirements.txt). Add `scan_inbox()` — process files from `attachments/inbox/`, move to period folder. | `plugins/career/skills/career/scripts/career_hardening.py` |
| 1.4 | developer | medium | Add CLI interface: `--action report\|attach\|list-reports\|scan-inbox`, `--range day\|week\|month\|custom`, `--start`, `--end`, `--file`, `--tag`, `--period`, `--output json\|yaml`. Write report to `data/career/hardening/reports/`. | `plugins/career/skills/career/scripts/career_hardening.py` |
| 1.5 | developer | low | Create `data/career/hardening/` directory structure: `reports/`, `sessions/`, `questions/`, `attachments/inbox/`, `reading/`, `config.yaml` with default preferences including reading suggestion prefs. Create `attachments/index.yaml` (empty). Create `reading/preferences.yaml` and `reading/history.yaml`. | `data/career/hardening/config.yaml`, `data/career/hardening/attachments/index.yaml`, `data/career/hardening/reading/preferences.yaml` |

### Phase 2: Dashboard — Hardening Tab
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend | medium | Create `hardening/page.tsx` — report view with date range selector (day/week/month/custom), generate button, file upload drop zone (for external files), and report display. Use existing StatusCard pattern for summary stats. Categories rendered as collapsible sections with weight bars. Include "Recommended Reading" panel below categories with resource cards (title, type badge, estimated time, reason, open/read/dismiss/save buttons). Include "External Files" section showing attached files with tags. | `plugins/career/skills/career/augur/hardening/page.tsx` |
| 2.2 | frontend | medium | Create `hardening/quiz/page.tsx` — quiz interface with question display, answer input (radio for MC, textarea for free-form, code block for code recall), submit button, score display. Tier indicator and progress bar (question N/10). | `plugins/career/skills/career/augur/hardening/quiz/page.tsx` |
| 2.3 | frontend | low | Create `hardening/history/page.tsx` — table of past reports and quiz sessions with dates, scores, tier reached. Link to view past reports. | `plugins/career/skills/career/augur/hardening/history/page.tsx` |
| 2.4 | frontend | low | Add API route `/api/career/hardening/report` — invokes `career_hardening.py --action report --range {range} --output json` via subprocess, returns JSON. | `plugins/career/skills/career/augur/hardening/actions.ts` |

### Phase 3: Dashboard Configuration & Actions
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Update `dashboard.yaml` — add "Hardening" tab group with tabs: Report (`/career/hardening`), Quiz (`/career/hardening/quiz`), History (`/career/hardening/history`). Add actions: "Generate Report" (flow: fast, invokes API route), "Harden Knowledge" (flow: llm, sends report + tier config to IDE), "Suggest CV Updates" (flow: llm), "Update Learning Targets" (flow: llm), "Suggest Roles & Companies" (flow: llm), "Get Reading Suggestions" (flow: llm, sends report topics + user profile to IDE for personalized resource curation). | `plugins/career/skills/career/augur.yaml` |
| 3.2 | developer | low | Register 3 MCP tools in career MCP tools: `career-hardening-report` (subprocess → `--action report`), `career-hardening-attach` (subprocess → `--action attach --file {path} --tag {tags}`), `career-hardening-reading` (subprocess → `--action reading --reading-action {list\|mark-read\|dismiss\|save}`). | `plugins/career/skills/career/mcp/tools.py` |

### Phase 4: Quiz Data Model
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Create quiz session schema in `career_hardening.py`: `QuizSession` (date, report_ref, tier, questions, score, duration). `QuizQuestion` (type: mc\|free\|code\|architecture, prompt, options?, correct_answer, user_answer, is_correct, explanation). Save/load to `data/career/hardening/sessions/`. | `plugins/career/skills/career/scripts/career_hardening.py` |
| 4.2 | developer | low | Add `--action list-sessions` and `--action get-session --id {id}` to CLI for quiz session retrieval. | `plugins/career/skills/career/scripts/career_hardening.py` |

### Phase 5: Reading Suggestion & External File Management
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | medium | Add `generate_reading_suggestions(report, user_profile)` to `career_hardening.py` — takes report's hardening_candidates + technologies, reads `reading/preferences.yaml` for user prefs, reads `data/career/profile/candidate.md` for career goals, outputs structured `recommended_reading` section. AI prompt template stored in `data/career/hardening/config.yaml`. | `plugins/career/skills/career/scripts/career_hardening.py` |
| 5.2 | developer | medium | Add `manage_reading(action, url)` to `career_hardening.py` — `list` returns current suggestions from latest report, `mark-read` moves resource to history with read_date, `dismiss` records dismissal (AI learns preference), `save` appends to `data/career/learning/reading-list.yaml`. | `plugins/career/skills/career/scripts/career_hardening.py` |
| 5.3 | developer | low | Add `--action reading` CLI with `--reading-action list\|mark-read\|dismiss\|save` and `--url` flag. Add `--action attach` integration with inbox scanning: `--action scan-inbox` processes `attachments/inbox/` automatically. | `plugins/career/skills/career/scripts/career_hardening.py` |
| 5.4 | frontend | medium | Add ReadingPanel component to `hardening/page.tsx` — resource cards with type badge (article/docs/paper/video/course), estimated time pill, 1-sentence reason, and action buttons (Open, Mark Read, Dismiss, Save). Dismissed resources fade out. Read resources show checkmark. | `plugins/career/skills/career/augur/hardening/page.tsx` |

### Final Phase: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `python3 plugins/career/skills/career/scripts/career_hardening.py --action report --range week --output json` — verify report generation |
| V.2 | validator | low | Run `npm run build` in `src/dashboard/` — verify hardening tab compiles |
| V.3 | validator | low | Verify `data/career/hardening/` directory structure exists with config.yaml |
| V.4 | validator | low | Run `npm run test` in `src/dashboard/` — no regressions |
| V.5 | validator | low | Run `pytest tests/src/` — no Python regressions |
| V.6 | architect | low | Verify ADR intent: report aggregates cross-session data, quiz follows Bloom's tiers, action buttons connect to existing career tabs |

### Completion Criteria
- [ ] `career_hardening.py` generates report from daily logs + git history + usage tracker + external files
- [ ] Report written to `data/career/hardening/reports/` in YAML format with `external_files` and `recommended_reading` sections
- [ ] External file attach works via CLI (`--action attach --file <path> --tag <tags>`)
- [ ] Inbox folder auto-scanned on report generation (`--action scan-inbox`)
- [ ] Dashboard hardening tab renders report with date range selector and file upload drop zone
- [ ] Recommended Reading panel displays AI-curated resources with open/read/dismiss/save actions
- [ ] Reading preferences and history persist to `data/career/hardening/reading/`
- [ ] Quiz page accepts answers, scores, and tracks tier progression
- [ ] Resources marked as "read" are included in Tier 3+ quiz questions
- [ ] History page shows past reports and quiz sessions
- [ ] `dashboard.yaml` updated with Hardening tab group and 6 action buttons
- [ ] 3 MCP tools registered and functional (`career-hardening-report`, `career-hardening-attach`, `career-hardening-reading`)
- [ ] Quiz session data persists to `data/career/hardening/sessions/`
- [ ] All existing tests pass
- [ ] Dashboard builds without errors
