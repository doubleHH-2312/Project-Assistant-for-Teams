## Summary

<!-- What changed, why, and which user or operational outcome it supports. -->

## Change surface

- [ ] Backend behavior
- [ ] API/OpenAPI contract
- [ ] Database model or migration
- [ ] Web behavior
- [ ] Date, timezone, or schedule logic
- [ ] `.env.example`, Docker, Makefile, or CI workflow
- [ ] Teams package or integration adapter
- [ ] Documentation only

## CI safety checklist

- [ ] I read and followed [the CI safety rules](../docs/engineering/ci-rules.md).
- [ ] I ran a fresh `make verify` after the final code change, or this PR is
      documentation-only and I ran `git diff --check`.
- [ ] I added behavior-focused RED/GREEN evidence for changed behavior, or explained
      why tests do not apply.
- [ ] API changes include inspected `make openapi` output and pass `make openapi-check`,
      or the API contract is unchanged.
- [ ] Database changes use a new migration and pass an empty-database upgrade, or the
      schema is unchanged.
- [ ] Date/time changes use the configured Team timezone for calendar values and include
      a UTC/Team boundary test, or date/time behavior is unchanged.
- [ ] CI-sensitive changes pass clean `make demo`, `make e2e`, `make build-images`, and
      `make smoke`, or those surfaces are unchanged.
- [ ] `.env.example` remains credential-free and usable by CI; no `.env`, secret, token,
      private key, or confidential data is included.
- [ ] I inspected `git status --short`, `git diff --check`, and the complete diff for
      generated drift, accidental files, unrelated edits, and security regressions.
- [ ] I updated `context-memory/progress.md` and `current-handoff.md` when the change
      affects implementation state or future work.

## Verification evidence

<!-- Paste commands and concise pass/fail totals. Mark non-applicable gates with a reason. -->

```text

```

## API, schema, deployment, and follow-ups

<!-- State each as changed/unchanged. List genuine follow-ups and external gates. -->

