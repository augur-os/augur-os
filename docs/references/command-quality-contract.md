# Command Quality Contract

Augur's primary AI-client command surface is intentionally small:

- `/ask`
- `/keep`
- `/discover`
- `/adr`
- `/dev`
- `/routines`
- `/sweep`

These are the only command docs exported to the primary Codex, Claude, and Gemini surfaces. Internal, deprecated, daemon, and specialist commands may still exist, but they are not primary slash commands.

## Command Layers

Policy lives in `project-brain/capabilities/skills/*/commands/*.md`. Command docs define the user-facing contract, export eligibility, routing expectations, and help text.

Deterministic engines own parsing, routing, validation, timing, and structured output. They should make command behavior repeatable enough to inspect and compare across clients.

Human evals review actual private-data command runs stored outside the shared repo. The shared repo can define the eval shape, but real transcripts and judgments belong in private storage. For the automated demo gate, deterministic scenario assertions produce `reviewer: auto` scorecards so the loop can run without human scoring.

The current deterministic `/ask` quality gate checks source availability, context volume, and freshness. It does not prove semantic relevance to the question; human scorecards must still judge `source_grounding` for demo runs until a relevance-aware gate is added.

## Failure Priority

Failure priority is:

1. Content correctness.
2. UX and observability.
3. Routing correctness.

Speed is measured by phase and cannot hide weak answers, weak captures, or wrong routes.

## Private Data Boundary

The shared repo may contain schemas, synthetic fixtures, and aggregate reports.

Private vaults and documents contain real command transcripts, actual source files, human scorecards, and any copied or private content.

## Demo Readiness Bar

Every demo command needs an actual-data scenario, run envelope timing, an automatic scorecard, an aggregate report, and a known-gap note for weak cases.

## Automatic KPI Gate

The demo gate is automatic: scenario assertions, deterministic route checks,
source refs, expected facts, duration limits, and private artifact checks
produce `reviewer: auto` scorecards. Human scorecards remain useful for
post-demo review, but they are not required to run the KPI loop.
