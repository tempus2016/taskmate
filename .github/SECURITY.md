# Security Policy

TaskMate is a Home Assistant custom integration. It stores all of its data —
children, chores, points, reward claims and completion history — locally inside
your Home Assistant instance using HA's native storage helpers. Nothing is sent
to any external service.

Because TaskMate runs inside Home Assistant, the most relevant security
boundaries are the ones Home Assistant itself enforces (authenticated users,
the HTTP/WebSocket API, and Lovelace). The most likely classes of issue in
TaskMate specifically are:

- A service or WebSocket command that performs an action without correctly
  checking the caller, or that accepts unvalidated input.
- A Lovelace card that renders attacker-controlled text without escaping it
  (potential XSS in the dashboard).
- Information disclosure through a sensor attribute or photo endpoint.

## Supported versions

Only the **latest released version** of TaskMate receives security fixes.
Before reporting, please update to the newest release and confirm the issue
still reproduces.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately using GitHub's
[private vulnerability reporting](https://github.com/tempus2016/taskmate/security/advisories/new)
(the **Report a vulnerability** button under the repository's **Security** tab).
This keeps the details private until a fix is available.

When reporting, please include:

- The TaskMate version and Home Assistant version.
- A description of the issue and its impact.
- Steps to reproduce, including any relevant card YAML, service calls, or
  sensor state.

## What to expect

This is a community project maintained in spare time, so timelines are
best-effort:

- **Acknowledgement** of your report as soon as is practical.
- An assessment of the issue and, if confirmed, a fix in a subsequent release.
- Credit in the release notes for the fix, unless you'd prefer to stay
  anonymous.

Thank you for helping keep TaskMate and its users safe.
