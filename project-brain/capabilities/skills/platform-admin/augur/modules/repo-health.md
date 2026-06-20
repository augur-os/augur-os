# Repository Health Audit

**Module for**: `platform-admin` skill

## Purpose
Audit repository against GitHub best practices for high-quality open source projects.

## Health Score Criteria

### Documentation (30 points)
| Item | Points | Check |
|------|--------|-------|
| README with badges | 5 | Has shields.io badges |
| Installation instructions | 5 | Clear setup steps |
| Usage examples | 5 | Code examples included |
| API documentation | 5 | Documented public APIs |
| Architecture diagram | 5 | Visual system overview |
| Contributing guide | 5 | CONTRIBUTING.md exists |

### Community Files (20 points)
| Item | Points | Check |
|------|--------|-------|
| LICENSE file | 5 | OSI-approved license |
| CODE_OF_CONDUCT.md | 5 | Community guidelines |
| SECURITY.md | 5 | Vulnerability policy |
| FUNDING.yml | 5 | Sponsor support |

### Project Health (30 points)
| Item | Points | Check |
|------|--------|-------|
| CI/CD configured | 10 | GitHub Actions or similar |
| Tests exist | 10 | Test coverage > 0% |
| No stale issues (>30d) | 5 | Active maintenance |
| README has live demo | 5 | Demo link or GIF |

### Discoverability (20 points)
| Item | Points | Check |
|------|--------|-------|
| Topics/tags set | 5 | Repository topics |
| Description filled | 5 | Repo description |
| Social preview image | 5 | Custom og:image |
| Website link | 5 | Homepage URL set |

## Audit Script Output Format
```yaml
# repo_health.yaml
audit_date: 2026-01-07
repository: augur
score: 85/100

documentation:
  readme_badges: pass
  installation: pass
  usage_examples: pass
  api_docs: warn  # Needs improvement
  architecture: pass
  contributing: pass

community:
  license: pass  # MIT
  code_of_conduct: pass
  security: fail  # Missing
  funding: warn  # Optional

project_health:
  ci_cd: pass
  tests: pass
  stale_issues: pass
  demo: warn

discoverability:
  topics: pass
  description: pass
  social_preview: fail  # Missing
  website: pass

recommendations:
  - Create SECURITY.md with vulnerability reporting process
  - Add social preview image (1280x640px)
  - Improve API documentation
```

## Remediation Priority
1. **Critical** (score impact >10): License, README
2. **High** (score impact 5-10): CI/CD, Tests
3. **Medium** (score impact <5): SECURITY.md, Social preview
