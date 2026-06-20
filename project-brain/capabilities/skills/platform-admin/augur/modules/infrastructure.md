<!--
Copyright 2026 Augur Contributors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

This document incorporates and modifies content from the Company-in-a-Box project,
licensed under the Apache License 2.0.
-->

# Infrastructure Maintenance Module


## Overview

Provides structured patterns for CI/CD pipeline management, deployment automation, and infrastructure monitoring.

## CI/CD Pipeline Patterns

### GitHub Actions Workflow Template
```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v3
      - name: Set up Python
        run: uv python install 3.12
      - name: Install dependencies
        run: uv sync
      - name: Run tests
        run: uv run pytest --cov --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v3
      - name: Set up Python
        run: uv python install 3.12
      - name: Lint
        run: |
          uv sync
          uv run ruff check .
          uv run mypy .

  deploy:
    needs: [test, lint]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        run: ./deploy.sh
```

### Pipeline Stages

| Stage | Purpose | Quality Gate |
|-------|---------|--------------|
| Build | Compile, install deps | Exit 0 |
| Test | Unit, integration | 80% coverage |
| Lint | Code quality | No errors |
| Security | Vulnerability scan | No critical |
| Deploy | Push to environment | Health check pass |

## Deployment Strategies

### Blue-Green Deployment
```
┌─────────────────────────────────────┐
│           Load Balancer             │
└──────────────┬──────────────────────┘
               │
    ┌──────────┴──────────┐
    ▼                     ▼
┌─────────┐          ┌─────────┐
│  Blue   │          │  Green  │
│ (Live)  │          │ (Idle)  │
└─────────┘          └─────────┘

Deploy to Green → Test → Switch traffic → Blue becomes idle
```

### Canary Deployment
```
Traffic split:
├── 95% → Stable version
└── 5%  → Canary version (new release)

Monitor error rates → If OK, gradually increase canary %
```

### Rolling Deployment
```
Instances: [A] [B] [C] [D]
Step 1: Update A, B → 50% new
Step 2: Update C, D → 100% new
Rollback: Reverse the process
```

## Environment Configuration

### Environment Hierarchy
```
base.yaml (src/lib defaults)
├── development.yaml
├── staging.yaml
└── production.yaml
```

### Secrets Management
```python
# Never commit secrets! Use environment variables
DATABASE_URL = os.environ["DATABASE_URL"]
API_KEY = os.environ["API_KEY"]

# Or use secret managers
from aws_secrets import get_secret
secrets = get_secret("prod/app/credentials")
```

## Monitoring & Alerting

### Health Check Endpoint
```python
@app.get("/health")
async def health_check():
    checks = {
        "database": await check_database(),
        "cache": await check_cache(),
        "dependencies": await check_dependencies()
    }
    status = "healthy" if all(checks.values()) else "unhealthy"
    return {"status": status, "checks": checks}
```

### Alert Thresholds

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| CPU | >70% | >90% | Scale up |
| Memory | >75% | >95% | Scale up |
| Error rate | >1% | >5% | Investigate |
| Response time | >500ms | >2s | Optimize |
| Disk | >80% | >95% | Cleanup |

### Log Aggregation Pattern
```python
import structlog

logger = structlog.get_logger()

logger.info(
    "request_processed",
    user_id=user.id,
    endpoint="/api/users",
    duration_ms=45,
    status=200
)
```

## Infrastructure as Code

### Terraform Pattern
```hcl
# main.tf
resource "aws_instance" "app" {
  ami           = var.ami_id
  instance_type = var.instance_type
  
  tags = {
    Name        = "${var.environment}-app"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Variables in tfvars per environment
# prod.tfvars, staging.tfvars
```

### Docker Compose for Local Dev
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgres://db:5432/app
    depends_on:
      - db
      - redis
  
  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
```

## Runbook Templates

### Incident Response
```markdown
## Incident: [Title]

### Detection
- Time: [timestamp]
- Alert: [alert name]
- Severity: [P1/P2/P3]

### Impact
- Users affected: [count]
- Services impacted: [list]

### Timeline
- HH:MM - Issue detected
- HH:MM - Investigation started
- HH:MM - Root cause identified
- HH:MM - Fix deployed
- HH:MM - Resolved

### Root Cause
[Description]

### Action Items
- [ ] [Preventive measure 1]
- [ ] [Preventive measure 2]
```

### Deployment Runbook
```markdown
## Deploy: [Service] v[Version]

### Pre-Deploy
- [ ] All tests passing
- [ ] Changelog updated
- [ ] Database migrations ready
- [ ] Stakeholders notified

### Deploy Steps
1. [ ] Create deployment branch
2. [ ] Run migrations (if any)
3. [ ] Deploy to staging
4. [ ] Smoke test staging
5. [ ] Deploy to production
6. [ ] Verify health checks
7. [ ] Monitor for 15 minutes

### Rollback Plan
- Command: `./rollback.sh v[previous-version]`
- Estimated time: 5 minutes
```

## Commands

| Command | Action |
|---------|--------|
| `pipeline status` | Check CI/CD pipeline health |
| `deploy: [env]` | Deploy to environment |
| `rollback: [version]` | Rollback to previous version |
| `health check` | Run infrastructure health checks |
| `runbook: [incident]` | Generate incident runbook |
