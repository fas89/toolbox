# toolbox

Skills and other tools I've built for AI coding agents and use every day, shared so
you don't have to build them yourself.

[![Validate](https://github.com/fas89/toolbox/actions/workflows/validate.yml/badge.svg)](https://github.com/fas89/toolbox/actions/workflows/validate.yml)

## What's inside

| Skill | What it does |
|---|---|
| [**borrow-before-build**](skills/borrow-before-build/) | Before your agent builds anything non-trivial from scratch, it checks your codebase and dependencies, searches for open-source prior art, and shows you receipts. Then it decides whether to depend on it, vendor it, adapt the pattern, or diverge on purpose. |
| [**clean-invisible-unicode**](skills/clean-invisible-unicode/) | Finds and removes characters you can't see: zero-width spaces, Trojan Source bidi controls, hidden tag-character instructions, variation-selector payloads, invisible Hangul-filler variables. Emoji and complex scripts keep working. Ships a stdlib-only Python scanner that doubles as a CI gate. |

Every skill uses the open [Agent Skills](https://agentskills.io) format: a folder
with a `SKILL.md`. It works in Claude Code and in other agents that read
`SKILL.md`, such as Codex, Cursor, Gemini CLI, GitHub Copilot and OpenCode.

## Install

**Claude Code.** This repo is a plugin marketplace:

```
/plugin marketplace add fas89/toolbox
/plugin install borrow-before-build@fas89
/plugin install clean-invisible-unicode@fas89
```

Each skill is its own plugin, so install only the ones you want. Skills fire on their own
when a task calls for them. To run one by hand, type `/<skill>:<skill>`, for example
`/borrow-before-build:borrow-before-build`.

Claude Code doesn't auto-update third-party marketplaces until you turn it on:
`/plugin` → **Marketplaces** → `fas89` → **Enable auto-update**. Or pull changes
yourself with `/plugin marketplace update fas89`.

**Any other agent.** Use the [`skills` CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add fas89/toolbox --skill clean-invisible-unicode
```

Leave out `--skill` to choose interactively.

Add `-g` to install it for all your projects, or `-a <agent>` to pick the agent.

**By hand.** Copy a skill folder into your agent's skills directory, for example
`~/.claude/skills/` for Claude Code.

## Layout

```
skills/<name>/                     one folder per skill
  SKILL.md                         the skill: frontmatter + instructions
  README.md                        for people browsing GitHub
  LICENSE.txt                      copy of the repo license, so every install carries it
  scripts/, references/            optional: code and docs the skill loads on demand
.claude-plugin/marketplace.json    Claude Code catalog: one plugin per skill
tests/                             tests for skill scripts (not shipped with installs)
scripts/check.sh                   every check CI runs
```

## Contributing

Issues and pull requests are welcome. Reports of a skill firing when it
shouldn't, or not firing when it should, are especially useful. Run
`./scripts/check.sh` before you push; it is exactly what CI runs. Conventions are
in [AGENTS.md](AGENTS.md), which your coding agent will read too.

## License

[MIT](LICENSE)
