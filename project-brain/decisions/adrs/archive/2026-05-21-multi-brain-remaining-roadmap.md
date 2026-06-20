# Multi-Brain Remaining Roadmap Plan

This is a documentation/coordination plan. It creates the formal ADR surfaces
that future sessions will implement phase by phase.

## Tasks

1. Create the roadmap ADR pointing at the roadmap design.
2. Create the implemented phase-2 ADR pointing at the existing project-brain
   foundation spec and plan.
3. Create ADR-770 for the physical `shared-vault/` to `project-brain/`
   migration.
4. Create ADR-771 for AI-client projection and write-routing migration.
5. Create ADR-772 for UI discovery/federation and memory review.
6. Regenerate ADR indexes and generated agent instructions.
7. Run lightweight validation that every new ADR references existing spec/plan
   files and appears in `docs/adrs/adrs-index.json`.

## Handoff Order

Future implementation sessions should run:

```text
/adr implement ADR-770
/adr implement ADR-771
/adr implement ADR-772
```

ADR-769 is a post-facto implemented ADR and should be gap-checked/archived,
not reimplemented.
