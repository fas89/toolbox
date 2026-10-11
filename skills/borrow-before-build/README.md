# borrow-before-build

AI coding agents write from memory by default. Ask for a retry helper, a config
loader or a YAML validator and you get a fresh implementation, even when your
codebase already has one, a dependency you ship already does it, or a maintained
library has solved it with edge cases you haven't thought of yet.

This skill makes the search a required, visible step. Before the agent builds
anything non-trivial, it:

1. **Looks inside**: your codebase, installed dependencies, the standard library.
2. **Searches outside**: at least 2–3 real web or GitHub queries, then reads the
   actual README or source of the likely candidates.
3. **Shows receipts**: what it checked and what it found, so you can see that it
   actually searched.
4. **Decides**: depend on it, vendor it, adapt the pattern, or diverge on purpose,
   after checking license, maintenance, security advisories and fit.
5. **Cites** the project it borrowed from in the code, commit or docs.

It skips the search only for trivial glue, bug fixes inside existing code, or
when you say so. With no web access it stops and tells you, instead of passing
off memory as research.

## What receipts look like

```
Checked locally:
- src/ + pyproject.toml → no retry helper; httpx is already a dependency

Searched:
- python retry exponential backoff library → tenacity, backoff, stamina
- Fetched: https://github.com/hynek/stamina → retries with production defaults, built on tenacity

Prior art found:
- tenacity @ 9.2.1 — decorator retries, jitter, async support (https://github.com/jd/tenacity)
- stamina @ 26.1.0 — tenacity with safe defaults and instrumentation (https://github.com/hynek/stamina)

Reuse strategy: depend on
Rationale: stamina (MIT) gives an HTTP client sensible defaults in one decorator;
both projects are actively maintained.
```

## Install

See the [repository README](../../README.md#install).

## How it compares

[reuse-before-build](https://github.com/Ai-Eastern/reuse-before-build) covers a
wider loop: reusing code and tests, and resuming work from saved evidence. Its
look-inside-first step is borrowed here, with credit. borrow-before-build stays
narrower: only the build-or-borrow decision, with a mandatory outside search,
visible receipts, and a license and health check before anything is adopted.

## Make it yours

The "Search starting points by domain" table in `SKILL.md` reflects my stack
(data engineering, Python, TypeScript). If you fork the skill, replace that table
with yours; it is the part that gains the most from local knowledge.
