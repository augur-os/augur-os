# UX Research Module

## Purpose
User interviews, usability studies, persona development, and user insight synthesis.

## Research Methods

### Method Selection Guide
| Method | Best For | Time | Participants |
|--------|----------|------|--------------|
| User Interview | Deep insights, motivations | 45-60 min | 5-8 |
| Usability Test | Task completion, pain points | 30-45 min | 5-7 |
| Survey | Quantitative data, scale | 5-10 min | 100+ |
| Card Sort | Information architecture | 20-30 min | 15-20 |
| A/B Test | Comparing options | Varies | 1000+ |
| Diary Study | Long-term behavior | Days-weeks | 10-15 |

## User Interviews

### Interview Guide Template
```markdown
## Interview Guide: [Feature/Topic]

### Intro (5 min)
- Thank participant
- Explain purpose (no wrong answers)
- Get consent for recording

### Warm-up (5 min)
- Tell me about your role
- How do you typically [relevant activity]?

### Core Questions (30-40 min)

**Current Behavior**
1. Walk me through how you currently [task]
2. What tools do you use for [activity]?
3. What's the hardest part about [task]?

**Pain Points**
4. Tell me about a time when [task] was frustrating
5. What would make [activity] easier?

**Feature-Specific** (if testing concept)
6. [Show prototype] What's your first impression?
7. What would you expect to happen if you clicked [X]?
8. How would this fit into your workflow?

### Wrap-up (5 min)
- Anything else you'd like to share?
- Questions for us?
- Thank and explain next steps
```

### Note-Taking Template
```yaml
interview:
  participant: "P03"
  date: "2026-01-06"
  duration: "52 min"
  
  key_quotes:
    - "I spend 30 minutes every morning just organizing tasks"
    - "I never trust the automatic categorization"
  
  observations:
    - Hesitated when looking for settings
    - Used keyboard shortcuts extensively
    - Kept browser tabs open for reference
  
  pain_points:
    - Manual data entry is tedious
    - Hard to find historical information
    - Notifications are overwhelming
  
  opportunities:
    - Auto-import from email
    - Better search/filter
    - Notification preferences
  
  surprise_insights:
    - Uses spreadsheet alongside our tool
    - Shares screenshots, not links
```

## Usability Testing

### Test Plan Template
```markdown
## Usability Test Plan

### Objective
Evaluate the new checkout flow for task completion and ease of use.

### Participants
- 6 participants
- Mix of new and existing users
- Age range: 25-55

### Tasks
1. Add an item to cart (baseline)
2. Apply a discount code (new feature)
3. Complete checkout with saved payment
4. Find order confirmation email

### Success Metrics
| Task | Success Rate | Time | Errors |
|------|--------------|------|--------|
| Task 1 | >95% | <30s | 0 |
| Task 2 | >80% | <60s | <2 |
| Task 3 | >90% | <90s | <1 |
| Task 4 | >85% | <45s | <1 |

### Equipment
- Screen recording (Loom)
- Think-aloud protocol
- Post-task questionnaire (SUS)
```

### SUS (System Usability Scale)
```markdown
## Post-Test Questionnaire

Rate 1 (Strongly Disagree) to 5 (Strongly Agree):

1. I would use this system frequently
2. The system was unnecessarily complex
3. The system was easy to use
4. I would need support to use this
5. Functions were well integrated
6. Too much inconsistency
7. Most people would learn quickly
8. Very cumbersome to use
9. I felt confident using it
10. Needed to learn a lot before starting

**SUS Score Calculation:**
- Odd questions: (score - 1)
- Even questions: (5 - score)
- Sum × 2.5 = SUS score (0-100)

**Interpretation:**
- 68+ = Above average
- 80+ = Good
- 90+ = Excellent
```

## Personas

### Persona Template
```markdown
## Persona: Efficient Emily

### Demographics
- Age: 32
- Role: Project Manager
- Company: Mid-size tech startup (50-200 people)
- Tech savviness: High

### Photo
[Representative stock photo]

### Quote
"I don't have time to fiddle with tools—they need to just work."

### Goals
- Keep projects on track
- Minimize meetings
- Clear visibility for stakeholders

### Frustrations
- Too many tools to juggle
- Manual status updates
- Finding information across systems

### Behaviors
- Checks dashboard first thing
- Prefers keyboard shortcuts
- Uses mobile app for quick updates
- Batch processes at end of day

### Scenarios
**Morning ritual**: Opens laptop, checks overnight updates, triages inbox, updates standup notes.

**Weekly planning**: Reviews burndown, adjusts priorities, prepares stakeholder report.

### Design Implications
- Fast-loading dashboard
- Keyboard navigation support
- Mobile-optimized views
- One-click status updates
```

## Research Synthesis

### Affinity Mapping
```
┌─────────────────────────────────────────────────┐
│                PAIN POINTS                      │
├─────────────┬─────────────┬─────────────────────┤
│ Onboarding  │ Daily Use   │ Advanced Features   │
│             │             │                     │
│ • Confusing │ • Slow      │ • Hard to find      │
│   setup     │   search    │ • Too many steps    │
│ • No        │ • Manual    │ • Missing           │
│   guidance  │   entry     │   documentation     │
└─────────────┴─────────────┴─────────────────────┘
```

### Insight Template
```yaml
insight:
  id: "INS-001"
  statement: "Users abandon complex forms because they can't save progress"
  
  evidence:
    - "5/6 participants mentioned losing work" (interviews)
    - "Form abandonment rate: 67%" (analytics)
    - "Support tickets about lost data: 23/month" (support)
  
  impact: "High - directly affects conversion"
  
  recommendation: "Implement auto-save with visual indicator"
  
  confidence: "High (multiple data sources)"
```

### Research Report Structure
```markdown
# UX Research Report: [Feature/Topic]

## Executive Summary
[2-3 sentences on key findings and recommendations]

## Methodology
- Method used
- Participants (n=X)
- Timeline

## Key Findings
### Finding 1: [Headline]
**Evidence**: [Data points]
**Impact**: [Business/user impact]
**Recommendation**: [Action to take]

### Finding 2: [Headline]
...

## Detailed Observations
[Supporting details, quotes, clips]

## Recommendations Summary
| Priority | Recommendation | Effort | Impact |
|----------|---------------|--------|--------|
| P1 | Auto-save forms | Medium | High |
| P2 | Improve search | High | High |
| P3 | Add tooltips | Low | Medium |

## Next Steps
1. Share with product team
2. Prioritize in backlog
3. Schedule follow-up testing
```

## Output

Research reports: `skills/frontend/augur/research/`
Personas: `skills/frontend/augur/personas/`
Interview notes: `skills/frontend/augur/interviews/`
