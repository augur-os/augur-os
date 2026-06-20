# Security Audit Checklist

## Overview

Comprehensive security checklist for auditing Augur skills and codebase.

---

## 🔴 Critical Security Checks

### 1. Secret & Credential Management

**Hardcoded Secrets Detection**:
```bash
# Patterns to search for
grep -r "API_KEY\s*=\s*['\"]" .
grep -r "password\s*=\s*['\"]" .
grep -r "token\s*=\s*['\"]" .
grep -r "secret\s*=\s*['\"]" .
grep -r "Bearer [A-Za-z0-9]" .
```

**Checklist**:
- [ ] No hardcoded API keys in code
- [ ] No passwords in configuration files
- [ ] No tokens in git history
- [ ] All secrets use environment variables
- [ ] `.env` files in `.gitignore`
- [ ] Example `.env.example` without real values
- [ ] API keys rotated regularly

### 2. Dependency Vulnerabilities

**Scan Commands**:
```bash
# Python
pip audit
pip list --outdated

# JavaScript (if applicable)
npm audit
npm outdated
```

**Checklist**:
- [ ] No critical CVEs in dependencies
- [ ] No high-severity vulnerabilities
- [ ] Dependencies updated within 6 months
- [ ] Transitive dependencies reviewed
- [ ] Security advisories monitored

### 3. File Permissions

**Check Commands**:
```bash
# Find world-readable sensitive files
find data/ -type f -perm -004

# Find world-writable files
find data/ -type f -perm -002
```

**Checklist**:
- [ ] User data directory has restrictive permissions (700 or 755)
- [ ] Secret files are user-only readable (600)
- [ ] No world-writable files
- [ ] Git repository permissions correct (644/755)

---

## 🟠 High Priority Checks

### 4. Authentication & Authorization

**API Endpoints**:
- [ ] All API endpoints require authentication
- [ ] API keys validated on every request
- [ ] No default/demo credentials in code
- [ ] Session tokens use secure random generation
- [ ] Token expiration implemented

**Data Access**:
- [ ] User data isolated per user
- [ ] No cross-user data leakage
- [ ] Principle of least privilege applied
- [ ] File access validated before reading

### 5. Input Validation

**Code Injection Risks**:
```python
# BAD: Command injection
os.system(f"curl {user_url}")

# GOOD: Safe alternative
subprocess.run(["curl", user_url], check=True)
```

**Checklist**:
- [ ] User input sanitized before shell commands
- [ ] No SQL queries with string concatenation
- [ ] File paths validated (no `../` traversal)
- [ ] URL schemes validated (http/https only)
- [ ] YAML/JSON parsing from trusted sources only

### 6. Data Privacy

**PII Handling**:
- [ ] No PII in log files
- [ ] No credentials in error messages
- [ ] User data encrypted at rest (if applicable)
- [ ] GDPR compliance for EU users
- [ ] Data retention policies documented

**Logging Best Practices**:
```python
# BAD: Logs password
logger.info(f"User login: {username} / {password}")

# GOOD: Logs only username
logger.info(f"User login: {username}")
```

---

## 🟡 Medium Priority Checks

### 7. Network Security

**HTTPS Enforcement**:
- [ ] All external API calls use HTTPS
- [ ] No HTTP fallback allowed
- [ ] Certificate validation enabled
- [ ] TLS 1.2+ required

**API Key Storage**:
- [ ] API keys in environment variables
- [ ] No API keys in URLs (use headers)
- [ ] Rate limiting on API endpoints
- [ ] API key rotation mechanism

### 8. Code Quality & Security

**Static Analysis**:
```bash
# Python security linters
bandit -r plugins/
semgrep --config=auto .

# General code quality
ruff check plugins/
mypy plugins/
```

**Checklist**:
- [ ] No use of `eval()` or `exec()`
- [ ] No `pickle` for untrusted data
- [ ] No `yaml.load()` (use `yaml.safe_load()`)
- [ ] No `shell=True` in subprocess calls
- [ ] Input validation on all user-provided data

### 9. Third-Party Integrations

**External Services**:
- [ ] API keys for external services secured
- [ ] OAuth tokens stored securely
- [ ] Webhook signatures validated
- [ ] Third-party library versions pinned
- [ ] License compliance verified

---

## 🟢 Low Priority / Nice-to-Have

### 10. Monitoring & Alerting

**Security Monitoring**:
- [ ] Failed authentication attempts logged
- [ ] Unusual access patterns detected
- [ ] Dependency vulnerability alerts enabled
- [ ] Security audit trail maintained

### 11. Documentation

**Security Documentation**:
- [ ] Security practices documented
- [ ] Incident response plan exists
- [ ] Secret rotation procedures documented
- [ ] Dependency update process defined

---

## OWASP Top 10 Coverage

### A01:2021 – Broken Access Control
- [ ] All endpoints require authentication
- [ ] User data access validated
- [ ] No insecure direct object references

### A02:2021 – Cryptographic Failures
- [ ] Secrets stored in environment variables
- [ ] Sensitive data not hardcoded
- [ ] HTTPS used for all external calls

### A03:2021 – Injection
- [ ] Input validation on all user data
- [ ] No command injection vulnerabilities
- [ ] Parameterized queries (if SQL used)

### A04:2021 – Insecure Design
- [ ] Threat modeling performed
- [ ] Security requirements documented
- [ ] Secure defaults enforced

### A05:2021 – Security Misconfiguration
- [ ] Dependencies up to date
- [ ] No default credentials
- [ ] Error messages don't leak info

### A06:2021 – Vulnerable and Outdated Components
- [ ] All dependencies scanned
- [ ] Critical CVEs addressed
- [ ] Regular dependency updates

### A07:2021 – Identification and Authentication Failures
- [ ] Strong authentication required
- [ ] Session management secure
- [ ] No credential stuffing vulnerabilities

### A08:2021 – Software and Data Integrity Failures
- [ ] Code signing (if applicable)
- [ ] Dependencies from trusted sources
- [ ] CI/CD pipeline secured

### A09:2021 – Security Logging and Monitoring Failures
- [ ] Security events logged
- [ ] No PII in logs
- [ ] Audit trail maintained

### A10:2021 – Server-Side Request Forgery
- [ ] URL validation on user inputs
- [ ] No arbitrary URL fetching
- [ ] Whitelist for allowed domains

---

## Severity Ratings

### Critical (Fix Immediately)
- Hardcoded secrets or credentials
- High/Critical CVEs with exploits
- Authentication bypass vulnerabilities
- Data exposure to unauthorized users

### High (Fix Within 1 Week)
- Medium-severity CVEs
- Missing input validation
- Insecure file permissions
- PII in logs

### Medium (Fix Within 1 Month)
- Outdated dependencies (no CVEs)
- Missing security documentation
- Suboptimal crypto usage
- Warning-level linter issues

### Low (Fix When Convenient)
- Code quality improvements
- Documentation gaps
- Non-security linter warnings
- Performance optimizations

---

## Audit Report Template

```markdown
# Security Audit Report

**Date**: YYYY-MM-DD
**Auditor**: security agent
**Scope**: [skill-name / full codebase]

## Executive Summary
[High-level overview of findings]

## Critical Issues (Fix Immediately)
1. [Issue description]
   - **Severity**: Critical
   - **Location**: file.py:line
   - **Remediation**: [How to fix]

## High Priority Issues
[Similar format]

## Medium Priority Issues
[Similar format]

## Recommendations
- [General security improvements]

## Compliance Status
- OWASP Top 10: [% covered]
- Dependency Vulnerabilities: [count]
- Secret Management: [Pass/Fail]

## Next Steps
1. [Action item 1]
2. [Action item 2]
```

---

## Automated Scanning Tools

### Python Security
```bash
# Install tools
pip install bandit semgrep safety

# Run scans
bandit -r plugins/ -f json -o security-report.json
semgrep --config=auto plugins/
safety check
```

### Dependency Auditing
```bash
# Python
pip-audit

# JavaScript
npm audit --json
```

### Secret Scanning
```bash
# Install gitleaks (if available)
brew install gitleaks

# Scan for secrets
gitleaks detect --source . --verbose
```

---

## Post-Audit Actions

1. **Triage Issues**: Categorize by severity
2. **Create Tasks**: File issues for each finding
3. **Prioritize**: Critical → High → Medium → Low
4. **Track Progress**: Update regularly
5. **Re-Audit**: After fixes, verify resolution
6. **Document**: Update security docs with learnings

---

## Security Best Practices

### Development
- Never commit secrets
- Use environment variables
- Validate all inputs
- Principle of least privilege
- Secure by default

### Deployment
- Rotate secrets regularly
- Monitor dependencies
- Enable security logging
- Audit access regularly
- Keep software updated

### Incident Response
- Log security events
- Have rollback plan
- Document procedures
- Test recovery
- Learn from incidents
