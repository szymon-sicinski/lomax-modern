# AGENTS.md — working rules for this repository

Instructions for human and AI contributors alike. Read before changing code or
research.

## What this project is

Research + read-only tooling for **The Adventures of Lomax** (Psygnosis,
1996/97, Windows 95). Current phase: research. The deliverable of this phase is
[`docs/research/`](docs/research/) plus a small, honest CLI.

## Hard rules

1. **No game bytes, ever.** No `LOMAX.EXE`, `*.WLD`, `*.WAV`, sprites, disc
   images, extracted art, or full hashes of copyrighted binaries in the
   repository, tests, issues or CI logs. `.gitignore` covers the common cases;
   do not work around it.
2. **No code from unlicensed projects.** `Lomax+` has no licence (all rights
   reserved). Cite its *facts* with `[S#]`; never copy code, comments or prose.
   See [`docs/architecture.md`](docs/architecture.md) §2.
3. **Do not guess binary layouts.** Until a real file confirms a layout, ship a
   scanner that reports offsets and records the unknown as an open question.
   Callers must be able to tell "verified" from "hypothesis".
4. **Every claim is sourced or marked derived.** Research prose uses `[S#]`
   citations; numbers computed from them are marked `[derived]`.
5. **No DRM/CD-check circumvention shipped.** Describe, do not implement.
6. **Read-only by default.** Tools must not write into the game folder until a
   component explicitly owns that operation, with a backup path and a
   refuse-if-no-round-trip rule.
7. **Tests before claims.** Never report a build or test as passing without the
   command output that shows it. Unit tests use synthetic fixtures only.

## Workflow

- Feature branch per change; never commit to `main` directly from an agent.
- Conventional Commits; one topic per PR.
- Before pushing: `python -m compileall -q src tests`,
  `python -m pytest tests -m "not realgame" -q`, `git diff --stat`, `git status`.
- Update `CHANGELOG.md` (`## [Unreleased]`) for user-visible changes, and the
  relevant `docs/` page when behaviour or a format claim changes.

## Where things live

| Need | File |
|---|---|
| Research findings | `docs/research/` (start at its `README.md`) |
| Format claims and confidence levels | `docs/file-formats.md` |
| Clean-room boundary | `docs/architecture.md` |
| Dev setup, tests, style | `docs/development.md` |
| Ranked work items | `docs/research/04-improvement-backlog.md` |
| Unanswered questions | `docs/research/05-open-questions.md` |

## Definition of done for a research task

- The claim has a citation or a measurement recorded in the repo.
- Contradictions with existing docs are fixed in the same change (no orphaned
  "we think X" elsewhere).
- New unknowns are added to `05-open-questions.md` instead of being silently
  dropped.
