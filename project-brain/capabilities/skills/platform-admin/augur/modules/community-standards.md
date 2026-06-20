# Community Standards

**Module for**: `platform-admin` skill

## Purpose
Ensure repository meets GitHub's Community Standards for open source projects.

## Required Files Checklist

### Essential (Must Have)
- [ ] `README.md` - Project overview, installation, usage
- [ ] `LICENSE` - MIT, Apache 2.0, or similar
- [ ] `CONTRIBUTING.md` - How to contribute
- [ ] `CODE_OF_CONDUCT.md` - Behavioral expectations

### Recommended (Should Have)
- [ ] `SECURITY.md` - Security policy, vulnerability reporting
- [ ] `.github/ISSUE_TEMPLATE/` - Bug report, feature request templates
- [ ] `.github/PULL_REQUEST_TEMPLATE.md` - PR template
- [ ] `CHANGELOG.md` - Version history

### Nice to Have
- [ ] `.github/FUNDING.yml` - Sponsor button configuration
- [ ] `GOVERNANCE.md` - Decision-making process
- [ ] `SUPPORT.md` - How to get help

## File Templates

### CONTRIBUTING.md
```markdown
# Contributing to Augur

Thank you for your interest in contributing!

## How to Contribute
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Code Style
- Use meaningful commit messages
- Follow existing code patterns
- Add tests for new features

## Reporting Bugs
Use the bug report template in Issues.

## Feature Requests
Use the feature request template in Issues.
```

### CODE_OF_CONDUCT.md
```markdown
# Code of Conduct

## Our Pledge
We pledge to make participation in our project a harassment-free experience for everyone.

## Our Standards
- Be respectful and inclusive
- Give and gracefully accept constructive feedback
- Focus on what's best for the community

## Enforcement
Report violations to [email]. All complaints will be reviewed.

Adopted from the Contributor Covenant, version 2.1.
```

### SECURITY.md
```markdown
# Security Policy

## Reporting a Vulnerability
Please report security vulnerabilities to [security@email.com].

Do NOT open public issues for security vulnerabilities.

## Supported Versions
| Version | Supported |
|---------|-----------|
| 1.x.x   | ✅        |
| < 1.0   | ❌        |
```

## Validation Command
```bash
# Check which community files exist
ls -la README.md LICENSE* CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md CHANGELOG.md .github/
```
