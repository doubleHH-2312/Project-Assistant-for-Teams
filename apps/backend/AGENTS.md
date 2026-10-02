# Backend Instructions

- Keep HTTP concerns in `api/` and domain behavior in module services.
- Services receive an `AsyncSession`; routes do not issue SQL directly.
- Every protected query must constrain team/ownership in addition to checking role.
- Use typed Pydantic request/response models and the shared error envelope.
- External Teams and LLM calls must go through integration protocols.
- Add or update tests for validation, permission, state transitions, and failures.

