# AGENTS.md

Single source of truth for every coding agent in this repo.
Claude Code reads it via the `@AGENTS.md` import in CLAUDE.md.

## What this project is

`fas89/toolbox` is a public collection of skills (and, later, other tools) for AI
coding agents. One layout serves three ways to install:

- **Agent Skills**: `skills/<name>/SKILL.md` in the open format at
  https://agentskills.io. `npx skills add fas89/toolbox` reads it.
- **Claude Code plugin marketplace**: `.claude-plugin/marketplace.json` lists one
  plugin per skill.
- **Copying by hand**: each skill folder is self-contained, license included.

## Build / test / run

```bash
./scripts/check.sh    # everything CI runs; must exit 0 before you push
```

It needs `uv`, `python3`, and the `claude` CLI. To try a skill in Claude Code
without installing it: `claude --plugin-dir skills/<name>`.

## Conventions

- **Adding a skill**: create `skills/<name>/` with `SKILL.md`, a short `README.md`
  for people browsing GitHub, and `LICENSE.txt` (a byte-identical copy of the root
  `LICENSE`). Add a marketplace entry with `"source": "./skills/<name>"` and
  `"skills": ["./"]`. Add a row to the table in the root `README.md`.
- The frontmatter `name`, the folder name, and the marketplace entry `name` are
  the same string.
- Write `description` as a YAML block scalar (`description: >-`). A plain scalar
  breaks at the first colon-space inside the text.
- No `version` in marketplace entries, so installs track commits. `check.sh`
  enforces this.
- Nothing private ships: no internal project names, hostnames, file paths,
  credentials, or customer data. Grep before you commit.
- Credit borrowed ideas in a **Credits** section at the end of `SKILL.md`.
- A skill that ships a script gets tests in `tests/` (stdlib `unittest`, run by
  `check.sh`). Tests live outside the skill folder so installs stay small. Write
  each test so it fails against the code before the fix.

## Traps

- Each plugin's root is its skill folder, not the repo root. Pointing `source` at
  `./` would copy the whole repo into every install, and `claude plugin validate`
  warns about the root `CLAUDE.md`.
- `skills-ref`, the spec validator, installs an executable named `agentskills`.
- Hidden Unicode in a skill is prompt injection, and `check.sh` fails on it. Some
  tools turn an escape sequence into the real invisible character when they write
  a file, so in code, write code points as hex numbers (`0x200B`), never as
  string escapes.
- Reserved marketplace and plugin names include `agent-skills` and anything that
  starts with `claude-` or `anthropic-`.
