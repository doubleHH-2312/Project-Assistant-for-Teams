# Implementation Plan

The active task-by-task TDD plan is
`docs/superpowers/plans/2026-10-02-teams-bot-action-platform.md`. This file only keeps
the milestone index used for handoff.

## Definition of Done

A work item is complete when its acceptance behavior is implemented, relevant tests
pass, lint/type checks pass where tooling is available, contracts and documentation
are current, no secret is committed, and demo seed data remains usable.

## Milestones

| ID | Milestone | Primary outcome | Dependencies |
|---|---|---|---|
| CTX | Context bootstrap | Agent memory and governing rules exist | None |
| FND | Foundation | Monorepo, config, database, migrations, seed, health | CTX |
| DLY | Daily reporting | Create/edit/history and standalone form | FND |
| MON | Monitoring | Coverage, blockers, missing users, reminders | DLY |
| WKL | Weekly reporting | Member and team draft/edit/confirm/revision | DLY, MON |
| ACT | Action platform | Team RBAC, audit timeline, typed action registry | FND |
| BOT | Teams bot | Personal/group/team commands, cards, binding, publication | ACT, WKL |
| INT | Integrations | Teams SDK and OpenAI-compatible LLM adapters | ACT, WKL |
| WEB | Role-aware web | Team selector, history, dashboards and all weekly scopes | ACT, WKL |
| OPS | Delivery | Vercel/Supabase profile, containers, CI, E2E, runbooks | All |

## Delivery order

1. Create context memory and root/scoped agent rules.
2. Bootstrap Python backend, React frontend, PostgreSQL and tooling.
3. Implement schema, migrations and deterministic seed data.
4. Deliver daily-report vertical slice.
5. Deliver monitoring and notifications.
6. Deliver member and team weekly-report workflows.
7. Replace global roles with Team Membership, append-only audit/status events, and the
   Action Registry.
8. Add GPT-first OpenAI-compatible generation, multi-team reporting, and publication.
9. Mount Teams SDK v2 into FastAPI and expose the same use cases in the role-aware web.
10. Validate, containerize, document, and prepare the Vercel/Supabase demo profile.
