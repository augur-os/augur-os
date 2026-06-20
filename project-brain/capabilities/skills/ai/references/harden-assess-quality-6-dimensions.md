## Step S2: Assess Quality (6 Dimensions)

Score each dimension 0–100 based on what actually exists and works. Be brutally
honest. Directory existence does not equal functionality.

### Dimension 1: Problem Alignment (weight 25%)

Check whether the skill has a clear problem statement and the code addresses it.

- Read `SKILL.md` — does it define clear problems/use cases?
- Check actions/pages — do they map to the stated problem?
- Score `0` if the skill has no clear problem statement
- Score `50` if the problem is stated but the workflows are mostly stubbed

### Dimension 2: Action Coverage (weight 20%)

Check whether actions actually work end to end.

- Review action definitions and dispatch mode
- For fire actions, verify backend handlers exist
- For oneshot/ide actions, verify the agent or prompt exists
- Score `0` if there are no working actions

### Dimension 3: Data Support (weight 20%)

Check whether the owned data is real and used.

- Inspect `augur/data/` or equivalent skill-owned data
- Sample files to distinguish real content from placeholders
- Verify the data is actually consumed by pages or actions

### Dimension 4: UI Access (weight 15%)

Check whether dashboard pages render meaningful content.

- List the owned dashboard pages
- Confirm whether they fetch real data or show hardcoded placeholders
- Verify page registrations still match live files

### Dimension 5: Capability Completeness (weight 10%)

Compare promised capabilities against real implementation.

- Count implemented versus promised surfaces
- Score low when the skill promises workflows that do not exist

### Dimension 6: User Journey Fit (weight 10%)

Trace one complete user flow.

- open page
- trigger action
- see real result

Score `0` when no complete flow exists. Score high only when the flow completes
without workarounds.

### Present Results

Show a before/after score table when hardening changes are made:

```text
Skill: {name}
Overall: {score}/100

| Dimension             | Score | Status     | Key Finding |
|-----------------------|-------|------------|-------------|
| Problem Alignment     | 40    | needs-work | ...         |
| Action Coverage       | 15    | critical   | ...         |
| Data Support          | 60    | needs-work | ...         |
| UI Access             | 35    | critical   | ...         |
| Capability Complete   | 20    | critical   | ...         |
| User Journey Fit      | 10    | critical   | ...         |
```

