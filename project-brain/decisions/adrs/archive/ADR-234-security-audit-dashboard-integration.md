---
status: Implemented
date: '2026-03-05'
deciders:
- Project team
related:
- ADR-229 (Settings Hardening)
- ADR-130 (Action Button Dispatch Modes)
hub: null
tags:
- security
- audit
- dashboard
- integration
superseded_by: null
---

# ADR-234: Security Audit Dashboard Integration

## Context

The `/settings/security` page currently shows AI guardrails (consent toggles, PII warnings, secret blocking) and a remote audit log table (user actions like logins). However, there is no way to trigger or view a **codebase security audit** from the dashboard.

Two audit capabilities exist but are disconnected from the UI:

### 1. Claude Code `/security-review` (AI-powered)
Claude's built-in `/security-review` slash command performs deep AI-powered analysis covering injection attacks (SQL, command, XSS), authentication/authorization flaws, cryptographic weaknesses, data exposure, business logic issues (race conditions, TOCTOU), insecure config, supply chain risks, and RCE vectors. It outputs structured JSON:

```json
{
  "findings": [{
    "file": "path/to/file.py",
    "line": 42,
    "severity": "HIGH",
    "category": "sql_injection",
    "description": "User input passed directly to SQL query",
    "exploit_scenario": "Attacker can extract database contents via...",
    "recommendation": "Use parameterized queries",
    "confidence": 0.95
  }],
  "analysis_summary": {
    "files_reviewed": 8,
    "high_severity": 1,
    "medium_severity": 0,
    "low_severity": 0,
    "review_completed": true
  }
}
```

Severity: HIGH (directly exploitable RCE/data breach), MEDIUM (requires preconditions), LOW (defense-in-depth). Confidence threshold: >0.8. Excludes DoS, rate limiting, resource exhaustion.

### 2. `security_audit.py` (fast pattern scan)
The existing script does 3 narrow checks: regex-based secret detection (`API_KEY=`, `sk-`, `ghp_`), `pip audit`/`npm audit` wrappers, and `.env` file validation. Output is markdown-only with a limited schema (`{file, line, pattern, severity}`). No category, description, exploit scenario, recommendation, or confidence fields.

**Gap**: The dashboard should surface Claude's comprehensive security review as the primary audit, with `security_audit.py` as a supplementary fast scan. The results table must align to Claude's richer finding format.

**User requirements**:
1. A prominent "Run Security Audit" button on the security page
2. A results table presenting findings aligned to Claude's `/security-review` output format (severity, category, file, line, description, confidence)

## Decision

### 1. Add "Codebase Security Audit" section to SecurityTab

Add a new section between "AI Guardrails" and "Audit Log" in `SecurityTab.tsx` with:
- A large, prominent "Run Security Audit" button (full-width, uses `ShieldAlert` icon)
- Status indicator showing last audit timestamp and summary counts
- The button dispatches via `useActionRunner` with `dispatch: 'ide'` to invoke Claude's `/security-review` in the IDE/CLI agent (per Rule #8 — no direct LLM/script calls from dashboard)
- A secondary smaller "Quick Scan" button that runs `security_audit.py` via the existing `run-security-scan` MCP tool for fast pattern checks

### 2. Canonical Finding Schema

All audit results — whether from Claude's `/security-review` or `security_audit.py` — are normalized to a single schema before display:

```typescript
interface SecurityFinding {
  file: string;           // relative path
  line: number;           // line number
  severity: "HIGH" | "MEDIUM" | "LOW";  // color-coded
  category: string;       // e.g. "sql_injection", "secret_detection", "dependency"
  description: string;    // human-readable explanation
  confidence: number;     // 0-1 (Claude findings have real scores; script findings default to 1.0)
  recommendation?: string;       // fix guidance
  exploit_scenario?: string;     // how it could be exploited
  source: "claude" | "scanner";  // which tool produced this finding
}

interface AuditReport {
  timestamp: string;
  source: "claude" | "scanner" | "combined";
  analysis_summary: {
    files_reviewed: number;
    high_severity: number;
    medium_severity: number;
    low_severity: number;
  };
  findings: SecurityFinding[];
}
```

### 3. API route to store and fetch audit reports

Create `/api/dev/security/report` that:
- **GET**: Reads the most recent audit report JSON from `runtime/factory/security/`
- **POST**: Accepts an `AuditReport` JSON body and persists it to `runtime/factory/security/audit_{timestamp}.json`. This is called by the IDE dispatch completion handler to store Claude's `/security-review` output.

### 4. Adapt `security_audit.py` to output normalized JSON

Add `--json` flag to `security_audit.py` that outputs findings in the canonical schema above. Mapping:
- Secret findings: `category: "secret_detection"`, `confidence: 1.0`, `description` built from pattern match
- Dependency findings: `category: "dependency_vulnerability"`, parsed from `pip audit`/`npm audit` JSON
- Env findings: `category: "environment_config"`, `severity` mapped from existing INFO→LOW, MEDIUM→MEDIUM

### 5. Results Table

A dedicated table below the button, aligned to Claude's output:

| Column | Source Field | Notes |
|--------|-------------|-------|
| Severity | `finding.severity` | Badge: HIGH=red, MEDIUM=amber, LOW=blue |
| Confidence | `finding.confidence` | Percentage bar or value (e.g. "95%") |
| Category | `finding.category` | Formatted label (e.g. "SQL Injection", "Secret Detection") |
| File | `finding.file` | Monospace code font with path |
| Line | `finding.line` | Numeric |
| Description | `finding.description` | Truncated with expand-on-click |
| Source | `finding.source` | Small badge: "Claude" (purple) or "Scanner" (gray) |

Expandable row detail shows `exploit_scenario` and `recommendation` when available.

### 6. Summary Cards

Above the table, 3 summary cards:
- **High Severity**: count, red accent
- **Medium Severity**: count, amber accent
- **Low Severity**: count, blue accent

Plus a "Files Reviewed" stat and "Last Audit" timestamp.

## Consequences

### Positive

- Dashboard surfaces Claude's comprehensive AI security analysis — not just regex pattern matching
- Single canonical schema normalizes findings from both sources
- Confidence scores help users prioritize real vulnerabilities over noise
- Expandable exploit scenarios and recommendations provide actionable guidance
- `dispatch: 'ide'` pattern — no Rule #8 violations

### Negative

- Claude's `/security-review` takes longer than `security_audit.py` (AI analysis vs regex)
- IDE dispatch means the audit runs in the user's CLI session, not server-side
- `security_audit.py` needs schema adaptation to match the canonical format

### Neutral

- The existing remote audit log section remains unchanged — this adds a new section, not replacing
- `security_audit.py` continues to work standalone for CI/quick checks
- Claude's `/security-review` continues to work standalone in the terminal

## Alternatives Considered

### Alternative 1: Use only `security_audit.py` output

Build the table around the script's limited `{file, line, pattern, severity}` format. Rejected because it misses the vast majority of vulnerability categories (injection, auth, crypto, XSS, business logic) and lacks descriptions, exploit scenarios, recommendations, and confidence scoring. The dashboard would show a severely impoverished view.

### Alternative 2: Call Claude API directly from the dashboard

Run `/security-review` via an API route that calls Claude. Rejected — violates Rule #8 (no direct LLM calls from dashboard). All AI execution must happen in IDE/CLI agents via `dispatch: 'ide'`.

### Alternative 3: Separate /settings/security/audit page

Create a dedicated sub-page. Rejected as over-engineering — the security page already has a natural section flow and the audit results fit as another section.

## Implementation Order

### Phase 1: Backend — Schema and Storage (PIPELINE)
1. Add `--json` flag to `security_audit.py` — normalize output to the canonical `AuditReport` schema with proper `category`, `description`, `confidence` fields
2. Create `/api/dev/security/report` route — GET reads latest report, POST persists new reports
3. Add a `security-audit` action entry in the validator plugin's `augur.yaml` with `dispatch: 'ide'` targeting Claude's `/security-review`

### Phase 2: Frontend — Dashboard UI (PIPELINE, depends on Phase 1)
1. Add "Codebase Security Audit" section to `SecurityTab.tsx` with:
   - Primary "Run Security Audit" button (IDE dispatch → Claude `/security-review`)
   - Secondary "Quick Scan" button (fire dispatch → `run-security-scan` MCP tool)
   - Summary cards (HIGH/MEDIUM/LOW counts + files reviewed + timestamp)
   - Results table with all 7 columns, expandable row detail
2. Wire IDE dispatch completion to POST results to `/api/dev/security/report`, then refresh table
3. Wire Quick Scan to GET `/api/dev/security/report` after MCP tool completes

## References

- [Claude Code `/security-review`](https://support.claude.com/en/articles/11932705-automated-security-reviews-in-claude-code) — AI-powered security analysis
- [anthropics/claude-code-security-review](https://github.com/anthropics/claude-code-security-review) — GitHub Action + finding schema
- `plugins/dev/skills/validator/scripts/security/security_audit.py` — fast pattern scan script
- `plugins/dev/skills/validator/augur.yaml` — MCP tool and action definitions
- `src/dashboard/app/settings/tabs/SecurityTab.tsx` — current security tab
- `src/dashboard/app/api/dev/security/route.ts` — existing MCP-backed API route
- ADR-229: Settings Hardening (composite score 93/100)
- ADR-130: Action Button Dispatch Modes

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-234-security-audit-dashboard`

### Phase 1: Backend — Schema normalization and API route
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | backend-dev | medium | Add `--json` flag to `security_audit.py`. When set, write a `.json` file alongside the `.md` report using the canonical `AuditReport` schema: `{ timestamp, source: "scanner", analysis_summary: { files_reviewed, high_severity, medium_severity, low_severity }, findings: [{ file, line, severity, category, description, confidence, recommendation, source: "scanner" }] }`. Map secrets to `category: "secret_detection"` with `confidence: 1.0` and build `description` from pattern+file context. Map dep vulns to `category: "dependency_vulnerability"`. Map env issues to `category: "environment_config"` with severity INFO→LOW. Keep backward compat — `--json` is opt-in. | `plugins/dev/skills/validator/scripts/security/security_audit.py` |
| 1.2 | backend-dev | medium | Create API route at `src/dashboard/app/api/dev/security/report/route.ts`. GET: read the most recent `audit_*.json` from `runtime/factory/security/`, return as-is. If no report, return `{ status: "no_report" }`. POST: accept `AuditReport` JSON body, validate it has `findings` array, write to `runtime/factory/security/audit_{timestamp}.json`, return `{ ok: true }`. Follow error handling pattern from existing `/api/dev/security/route.ts`. | `src/dashboard/app/api/dev/security/report/route.ts` |
| 1.3 | backend-dev | low | Update MCP tool handler for `run-security-scan` to always pass `--json` so structured output is produced. Add a `security-review` action in validator's `augur.yaml` actions list with `dispatch: ide`, `label: "AI Security Review"`, `description: "Run Claude /security-review for deep vulnerability analysis"`. | `plugins/dev/skills/validator/augur.yaml`, MCP tool config |

### Phase 2: Frontend — Dashboard UI
**Strategy**: PIPELINE (depends on Phase 1)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend-dev | high | Add "Codebase Security Audit" section to `SecurityTab.tsx` between AI Guardrails and Audit Log. Components: (a) Primary full-width "Run Security Audit" button with `ShieldAlert` icon — dispatches `security-review` action via `useActionRunner` (dispatch: 'ide'). Secondary "Quick Scan" outline button — calls `GET /api/dev/security` (existing MCP route). Both show loading spinners. (b) Summary cards row: 3 severity count cards (HIGH=red, MEDIUM=amber, LOW=blue) + files reviewed + "Last audit: {timestamp}". (c) Results table: 7 columns — Severity (color badge), Confidence (percentage), Category (formatted label), File (monospace `<code>`), Line, Description (truncated), Source ("Claude"/"Scanner" badge). Expandable row shows `exploit_scenario` + `recommendation`. (d) On IDE dispatch complete, POST Claude's JSON output to `/api/dev/security/report`, then re-fetch GET to refresh table. On Quick Scan complete, re-fetch GET. (e) On mount, fetch GET `/api/dev/security/report` to show last results. | `src/dashboard/app/settings/tabs/SecurityTab.tsx` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `python security_audit.py --full --json` and verify JSON output matches canonical schema. Run `npm run build` — no type errors. |
| V.2 | validator | low | Browser-validate `/settings/security` — both buttons render, Quick Scan triggers MCP tool and shows results in table, summary cards populate. Verify table columns match spec (Severity, Confidence, Category, File, Line, Description, Source). |

### Completion Criteria
- [ ] `security_audit.py --json` produces valid `AuditReport` JSON with canonical schema
- [ ] `GET /api/dev/security/report` returns latest audit data
- [ ] `POST /api/dev/security/report` persists Claude review results
- [ ] "Run Security Audit" button dispatches to IDE (Claude `/security-review`)
- [ ] "Quick Scan" button triggers `run-security-scan` MCP tool
- [ ] Results table renders all 7 columns with expandable row detail
- [ ] Summary cards show severity counts, files reviewed, timestamp
- [ ] Source badge distinguishes "Claude" vs "Scanner" findings
- [ ] `npm run build` passes with no type errors
- [ ] No Rule #8 or Rule #9 violations
- [ ] ADR status updated to Implemented
