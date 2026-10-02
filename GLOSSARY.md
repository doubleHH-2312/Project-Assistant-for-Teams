# Project Assistant Domain

Canonical product language shared by the application, documentation, and agents.

## Language

**Daily Report**:
A member's structured evidence for one work item on one reporting date.
_Avoid_: Check-in, timesheet

**Expected Reporter**:
An active team member who is required to submit at least one valid Daily Report for
a reporting date.
_Avoid_: Assignee, missing user

**Effective Blocker**:
The blocker text shown to consumers: the explicit blocker when present, otherwise the
work summary for a Daily Report whose status is `BLOCKED`.
_Avoid_: Inferred blocker, AI blocker

**Member Weekly Report**:
A human-reviewable weekly draft for one member, generated only from that member's
Daily Reports.
_Avoid_: Personal summary

**Team Weekly Report**:
A human-reviewable weekly draft generated only from confirmed Member Weekly Reports.
_Avoid_: Automatic team summary

**Confirmation**:
The irreversible approval that makes a Weekly Report authoritative and immutable.
_Avoid_: Submit, publish

**Revision**:
A new editable Weekly Report that explicitly supersedes a confirmed report without
modifying the confirmed evidence.
_Avoid_: Reopen, overwrite

**Integration Gate**:
External evidence required before a Teams, Entra, internal-LLM, or AWS adapter can be
reported as verified against the real provider.
_Avoid_: Feature flag

**Team Membership**:
The active relationship assigning one User a role within one Team. A User may have
different roles in different Teams.
_Avoid_: Global user role

**Action**:
A named, user-triggered product workflow such as `daily` or `weekly-team`, independent
of whether it is invoked from Teams or the web application.
_Avoid_: Command handler business logic

**Action Invocation**:
The append-only audit record of one attempt to trigger an Action, including actor,
scope, server timestamp, correlation, idempotency and outcome.
_Avoid_: Chat history, application log

**Work Item Status Event**:
An append-only, server-timestamped observation of a Work Item status submitted through
a Daily Report. Earlier events remain authoritative history after later updates.
_Avoid_: Current status snapshot

**Multi-team Weekly Report**:
A human-reviewable weekly draft generated only from confirmed Team Weekly Reports for
Teams where the actor has the required membership.
_Avoid_: Organization report

**Publication**:
An audited delivery of a confirmed report to a Teams conversation. Publication does
not modify or confirm the report.
_Avoid_: Confirmation
