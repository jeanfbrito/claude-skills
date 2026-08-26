# claude-skills

Personal collection of [Claude Code](https://docs.claude.com/en/docs/claude-code) skills.

## Skills

- **learn** — Capture knowledge from coding sessions into project + global `lessons.md` files. Triggered by `/learn`.
- **commit** — Smart git committing that groups related changes into separate, well-described commits. Triggered by `/commit`.
- **jira** — Drive an Atlassian Cloud Jira workspace via [ankitpokhrel/jira-cli](https://github.com/ankitpokhrel/jira-cli) from Claude Code. Triggered by any Jira-related question. Personal defaults (site, email, primary project, default component, workflow status names) live in a gitignored `local-config.yml` populated by `setup.sh` — the skill itself ships only the generic playbook. A Linux-adapted variant for Hermes lives in `jira/hermes/`.
- **grok-build** — Delegate coding tasks to xAI's Grok CLI (`grok`) running headless: implement, review, or diagnose code with verification patterns, session resume, and worktree isolation. Triggered by "use grok", "ask grok", "grok this". Requires the `grok` binary installed and authenticated (`grok login`).
- **postmortem** — Write a post-mortem after a challenging task: full timeline including failed attempts, root causes, durable lesson extraction into AGENTS.md/memory/mastermind, and draft-first distribution (Confluence write-up, team-channel summary, optional blog handoff). Triggered by `/postmortem`, "write a post-mortem", "document what we learned". Loads the shared tone rules from `shared/tone.md`.
- **weekly-digest** — Draft a short weekly work digest translated from commit/ticket language into impact language, from real sources only (ledger, merged PRs, git history, optional Jira). Triggered by `/weekly-digest`, "weekly digest", "draft my weekly update", "what did I ship this week", "status update for the team". Draft-first, never posts without approval. Loads the shared tone rules from `shared/tone.md`; window state lives in a gitignored `local-config.yml` created on first run.
- **proposal** — Draft a one-page technical initiative proposal backed by real evidence mined from the project (known issues, git history, ledger, CI patterns). Triggered by `/proposal`, "draft a proposal", "propose an initiative", "write an improvement proposal", "make the case for X". Draft-first, never files or posts without approval. Loads the shared tone rules from `shared/tone.md`. Intended cadence: roughly quarterly.
- **update-skill** — Create or update a skill in this repo (`~/Github/agent-skills`), keeping SKILL.md frontmatter, README wiring, and symlink install in sync. Triggered by `/update-skill`, "create a skill", "new skill", "update the X skill", "fix the description of skill Y", "add a skill for Z".

Shared references live in `shared/` — currently `tone.md`, the tone/framing rules for any outward-facing text (post-mortems, PR descriptions, channel posts, replies to bug reports). Skills reference it by absolute path so it works through the symlink install.

## Commands

- **ticket** — Ticket/task workflow. Triggered by `/ticket`.

## Install

Clone once, then symlink each skill into `~/.claude/skills/` and each command into `~/.claude/commands/` — symlinks mean a `git pull` updates everything, but only if every machine points at the SAME clone:

```bash
git clone https://github.com/jeanfbrito/agent-skills.git ~/Github/agent-skills
mkdir -p ~/.claude/skills ~/.claude/commands
ln -s ~/Github/agent-skills/learn ~/.claude/skills/learn
ln -s ~/Github/agent-skills/commit ~/.claude/skills/commit
ln -s ~/Github/agent-skills/jira ~/.claude/skills/jira
ln -s ~/Github/agent-skills/grok-build ~/.claude/skills/grok-build
ln -s ~/Github/agent-skills/postmortem ~/.claude/skills/postmortem
ln -s ~/Github/agent-skills/weekly-digest ~/.claude/skills/weekly-digest
ln -s ~/Github/agent-skills/proposal ~/.claude/skills/proposal
ln -s ~/Github/agent-skills/update-skill ~/.claude/skills/update-skill
ln -s ~/Github/agent-skills/commands/ticket.md ~/.claude/commands/ticket.md
```

For the **jira** skill, also run the one-time setup to install jira-cli, store your API token in macOS Keychain, and capture per-user defaults into `local-config.yml` (gitignored):

```bash
~/.claude/skills/jira/setup.sh
```

Restart Claude Code or start a new session — skills load on startup.

## Layout

Each subdirectory is a self-contained skill with a `SKILL.md` manifest. See [Claude Code skills docs](https://docs.claude.com/en/docs/claude-code/skills).
