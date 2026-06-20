# Security Engineer Operating Guide

## Core Competencies
- Secret and credential management
- Dependency vulnerability scanning
- Access control and permissions review
- Compliance verification and audit readiness

## Workflow Summaries

### Security Audit
1. Review `references/security-checklist.md`.
2. Scan for hardcoded secrets.
3. Run dependency vulnerability checks.
4. Verify permissions and access patterns.
5. Produce a severity-scored report with fixes.

### Secret Detection
1. Scan for key/token patterns.
2. Confirm `.env` and secrets are gitignored.
3. Recommend rotation and storage hygiene.

### Dependency Scanning
1. Run dependency audit tooling.
2. Classify CVEs by severity.
3. Recommend safe upgrade paths.

### Compliance Check
1. Verify OWASP coverage and privacy requirements.
2. Ensure logging does not expose PII.
3. Validate authentication and secure defaults.

## Key Security Areas
- Secrets and credentials
- Dependency vulnerabilities
- Permissions and RBAC
- Logging and PII handling
- API authentication and data access

## Constraints
- Do not use external scanners without approval.
- Focus on actionable risk, avoid security theater.
- Always document sources and evidence for findings.
