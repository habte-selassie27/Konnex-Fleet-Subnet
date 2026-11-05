# Contributing

Thank you for contributing to the **Konnex Fleet Intelligence Subnet**.

## Ground Rules

1. **Never fabricate results.** A benchmark number that did not come from an actual run is `NOT RUN`. An unfinished component is `STUB`. (AGENTS.md §0.3, Law 1)
2. **Respect layer separation.** The robotics core never imports from `protocol/konnex/`; the validator never modifies robot state. (AGENTS.md §0.3, Law 2)
3. **One command.** The demo must launch with `make demo`. (AGENTS.md §0.3, Law 3)

## Before You Start

- Read `AGENTS.md` (especially §0 Global Rules), `PLAN.md`, `BUILD.md`, `SYSTEM_PROMPT.md`, and `TESTING_PLAN.md`.
- State which Phase (0–10) your task belongs to and its acceptance criterion (TESTING_PLAN.md §10).

## Commit Gate (AGENTS.md §0.4)

Only commit when **all** of the following hold:

1. All tests for the modified component pass
2. `make lint` passes with zero errors
3. You have executed the component and observed correct behavior
4. Documentation for the component is updated
5. No fabricated data exists anywhere in the changed files

## Workflow

1. One component at a time: implement → test → lint → commit (AGENTS.md §7-style incremental development).
2. Update the relevant `docs/*.md` file alongside code.
3. Keep pull requests small and focused on a single phase.

## Dependency Policy

- Never add a dependency without verifying it is in the approved list (BUILD.md §2.2 / SYSTEM_PROMPT.md §6.2).
- Pin exact versions; research before pinning (no versions from memory).
- No Konnex SDK calls until the SDK is verified against real docs — mark as `STUB` with `# TODO: verify SDK`.
