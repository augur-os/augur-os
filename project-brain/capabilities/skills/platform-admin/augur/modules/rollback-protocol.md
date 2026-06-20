# Rollback Protocol

All infrastructure changes must follow this protocol:

| Step | Action |
|------|--------|
| **1. Snapshot** | Capture current state before change |
| **2. Change** | Apply modification |
| **3. Verify** | Health check within 5 minutes |
| **4. Rollback trigger** | Auto-revert if health check fails |

## Example: Safe Deployment

```bash
./scripts/snapshot.sh
./scripts/deploy.sh --env staging
./scripts/health_check.sh || ./scripts/rollback.sh
```

## Key Rules

- Every change must be reversible or have documented rollback steps
- Health check timeout: 5 minutes max
- On failure: auto-revert to snapshot
- Production deployments require explicit approval before and after
