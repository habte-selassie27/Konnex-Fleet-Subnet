# Security Policy

## Reporting a Vulnerability

This project is a research prototype for the Konnex Builder Program. If you discover a security issue, please do **not** open a public issue.

Contact the maintainers privately (email TBD), and include:

- A description of the vulnerability and its impact
- Steps to reproduce
- Affected versions/components

We will acknowledge receipt within 5 business days and coordinate a fix before public disclosure.

## Security Design Notes (MVP)

- All credentials via environment variables (`.env`, never committed). See `.env.example`.
- API authentication via `X-Fleet-API-Key` header (JWT post-MVP).
- Policy execution runs inside sandboxed containers with CPU/memory limits and network isolation (Phase 6).
- Policy tampering protection via SHA-256 hash verification before execution (Phase 6).
- Benchmarks are validated by `validate_benchmark_result` (TESTING_PLAN.md §7) — no fabricated data accepted.

## Out of Scope (MVP)

- On-chain reward distribution (adapter only, Phase 8).
- Multi-validator consensus (post-MVP).
