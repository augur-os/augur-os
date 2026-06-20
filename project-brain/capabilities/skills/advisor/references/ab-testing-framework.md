# A/B Testing Framework

## Experiment Design
- Define hypothesis and success metric.
- Select primary and guardrail metrics.
- Determine sample size and duration.

## Metrics
- Primary: success rate, task completion, quality score.
- Guardrails: latency, token usage, error rate.

## Sample Size Guidance
- Minimum: 100 interactions per variant.
- Confidence: 95% (alpha 0.05).
- Detectable delta: >= 5%.

## Workflow
1. Define experiment name and variants.
2. Split traffic between variants.
3. Collect metrics with timestamps.
4. Run significance tests.
5. Decide winner and document results.

## Result Template
```yaml
experiment_id: exp_001
variants:
  - name: A
  - name: B
metrics:
  success_rate:
  latency:
  token_cost:
winner: A
notes: |
  Summary of findings.
```
