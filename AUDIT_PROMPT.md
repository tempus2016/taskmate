# Reusable Codebase Audit Prompt

Use this prompt to run a full, autonomous, read-only audit of a codebase. Paste it as-is (adjust the project name/path if needed).

---

Conduct a complete, autonomous audit of this entire codebase. Work through it fully without stopping, asking questions, or requesting confirmation at any point. This is a strictly read-only analysis: do not edit, create, delete, move, or rename any files, do not modify the database, do not run migrations, and do not execute any code that writes data or changes state. You may read files, grep, and inspect configs freely.

Analyse every area below, examining all source files, templates, configs, Dockerfiles, and dependencies:

1. **Security** — SQL injection, XSS, CSRF, authentication/session weaknesses, hardcoded secrets or credentials, insecure headers, debug mode in production, unsafe deserialisation, path traversal, exposed endpoints, dependency vulnerabilities (check versions against known CVEs), file upload risks, insufficient input validation.
2. **Errors & faulty code** — bugs, unhandled exceptions, race conditions, broken logic, incorrect error handling, resource leaks, off-by-one errors, faulty conditionals, broken routes or templates.
3. **Dead & unused code** — unreachable functions, unused imports/variables/routes/templates/static files, commented-out blocks, orphaned files, duplicate logic.
4. **Code quality & improvements** — refactoring opportunities, DRY violations, overly complex functions, missing type hints, inconsistent naming, poor separation of concerns, missing docstrings on key functions.
5. **Performance** — N+1 queries, missing database indexes, inefficient loops, unbounded queries, missing caching opportunities, large payloads, blocking operations.
6. **Architecture & maintainability** — structural issues, tight coupling, config handling, logging gaps, missing tests, error monitoring gaps.
7. **New feature suggestions** — features that would naturally complement the existing functionality, based on what the app does.
8. **Anything else** — accessibility issues, outdated dependencies, Docker/deployment hardening, backup considerations, documentation gaps.

Then produce a single comprehensive report saved as `AUDIT_REPORT.md` (this is the only file you may create) containing: an executive summary; findings grouped by category, each with severity (Critical/High/Medium/Low), the file and line reference, what the issue is, why it matters, and a recommended fix (described, not applied); a prioritised action list; and a list of suggested new features with rationale. Do not apply any fixes — report only. The production database must not be opened in write mode at any point.

---

## Notes for future runs

- **Verify before reporting.** Subagents / fan-out searches occasionally hallucinate line numbers or overstate severity (e.g. claiming data is "unbounded" when it is in fact pruned). Spot-check every Critical/High finding against the actual source before writing it up.
- **Resolve conflicts.** When two passes disagree (e.g. "all handlers are admin-gated" vs "these handlers are not"), open the file and settle it definitively.
- **Fan out for scale.** For large codebases, dispatch parallel read-only agents partitioned by independent domain (backend core / business logic / frontend group A / frontend group B / config-deps-CI), then synthesise and verify.
