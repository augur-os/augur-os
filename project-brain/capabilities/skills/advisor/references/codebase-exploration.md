# Four-Phase Codebase Exploration Framework

Use this framework when exploring a codebase to understand how a feature or
subsystem works. Output of each phase feeds `/advisor-architecture`; the
blueprint output contract lives in `references/blueprint-template.md`.

(Adapted from the staged r3 architecture-analyzer module. The original
"Repository Adaptation Analysis" half was excluded at adoption — external
repo adaptation belongs to `skillify` and the port-release contract.)

## Phase 1: Discovery

Identify the key entry points and boundaries.

| Element | How to Identify |
|---------|-----------------|
| **Entry Points** | API routes, CLI commands, UI components, event handlers |
| **Core Implementation** | Main business logic files (not boilerplate) |
| **Feature Boundaries** | Where this feature starts and ends |
| **Configuration** | Environment vars, config files, feature flags |

**Output Example:**
```markdown
### Discovery Results

**Entry Points:**
- API: `src/api/users/route.ts:15` - GET /api/users
- UI: `src/app/users/page.tsx:1` - User list page

**Core Files:**
- `src/services/UserService.ts` - Main user logic (450 LOC)
- `src/repositories/UserRepository.ts` - Data access (200 LOC)

**Boundaries:**
- Depends on: AuthService, EmailService
- Depended on by: OrderService, NotificationService
```

## Phase 2: Tracing

Follow execution paths from entry to completion.

| Element | What to Document |
|---------|------------------|
| **Execution Chain** | Function call sequence from entry to exit |
| **Data Transformations** | How data changes at each step |
| **Dependencies** | External services, databases, APIs called |
| **State Changes** | What gets mutated along the way |

**Output Example:**
```markdown
### Execution Trace: Create User

1. `POST /api/users` → `UserController.create()` (route.ts:25)
   - Input: `{ email, name, role }`
   - Validation: Zod schema (schema.ts:10)

2. → `UserService.createUser()` (UserService.ts:45)
   - Checks email uniqueness (DB query)
   - Hashes password (bcrypt)

3. → `UserRepository.insert()` (UserRepository.ts:30)
   - Prisma insert to `users` table

4. Response: 201 with user object
```

## Phase 3: Architecture Mapping

Map the system layers and patterns.

| Layer | What to Identify |
|-------|------------------|
| **Presentation** | UI components, API routes, CLI handlers |
| **Business Logic** | Services, use cases, domain models |
| **Data Access** | Repositories, ORMs, database queries |
| **Infrastructure** | External services, caching, messaging |

**Patterns to Identify:**
- Design patterns used (Repository, Factory, Strategy, etc.)
- Architectural style (MVC, Clean Architecture, Hexagonal)
- Cross-cutting concerns (logging, auth, validation)

## Phase 4: Implementation Analysis

Deep-dive into algorithms, edge cases, and technical debt.

| Element | What to Look For |
|---------|------------------|
| **Algorithms** | Core logic, time/space complexity |
| **Error Handling** | Exception paths, recovery strategies |
| **Edge Cases** | Boundary conditions, race conditions |
| **Tech Debt** | TODOs, workarounds, deprecated code |

## Augur-specific anchors

When exploring this repository, additionally check:

- **Governing ADRs** — `docs/generated/adr-index.md` and `get_adr_dir()`
  before concluding a pattern is accidental (CLAUDE.md rules 12, 22).
- **Directory README files** — local ownership and placement rules (rule 6).
- **Path helpers** — `src/config/paths.py` is the source of truth for data
  locations; hardcoded paths in traced code are findings, not patterns.
- **Import architecture** — dashboard `@/` (framework) must not import
  `@/features/` (ADR-490); violations are findings.
