# Risks and Dependencies

| Area | State | Risk | Required evidence / mitigation |
|---|---|---|---|
| Teams/Entra | Gate closed | Tab package is schema-valid but has no real hostname/app registration; bot and NAA are not enabled | Public HTTPS hostname, tenant ID, registrations, redirect domains, bot registration, permissions, test users |
| GPT test | Gate closed | No API key/model approval is stored in the repository | User-supplied secret environment variable, approved model and data policy |
| Company LLM | Gate partly defined | Endpoint is OpenAI-compatible, but base URL, auth, model and capability mode are not yet supplied | Contract test against the shared adapter, credentials delivery, limits and data policy |
| Vercel/Supabase | Gate closed | Project references, pooler URLs and hosting-plan suitability are not supplied | Accounts/projects, secret environment configuration, migration URL, public hostname |
| AWS scale-up | Deferred | Account/network/IAM details are intentionally outside MVP | Revisit only when scale/reliability requires it |
| On-prem | Optional fallback | Server access may be delayed | Keep Docker Compose portable and document prerequisites |
| Product template | Provisional | Real team weekly template may differ | Version templates and replace configuration, not core logic |
| Sensitive data | Active risk | Reports may contain confidential content | Redaction, least privilege, approved LLM data policy, anonymized seed |
| MVP QA | In progress | No Playwright/real-Teams/accessibility audit yet | Add browser E2E and audit before production claim |

Mock modes must be visible in health/configuration output and must never be reported
as successful real integration tests.
