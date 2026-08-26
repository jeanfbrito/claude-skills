---
name: update-skill
description: Creates a new skill or updates an existing one in THIS repository (~/Github/agent-skills), writing/editing its SKILL.md frontmatter and body, wiring the README bullet + Install symlink, and installing the symlink into ~/.claude/skills/. Triggered by "/update-skill", "create a skill", "new skill", "update the X skill", "fix the description of skill Y", "add a skill for Z". Not for editing skills that live in other repos.
---

# Update Skill

Author or revise a skill directory in this repo so it matches every
convention the existing skills already follow — frontmatter shape, symlink
install, absolute cross-file paths, draft-first behavior, gitignored
per-user state.

## Purpose

Skills here are symlink-installed (`~/Github/agent-skills/<name>` ->
`~/.claude/skills/<name>`), so a skill that looks fine standing alone can
still break at install time (relative paths, missing README wiring, an
untracked local-config leaking into git). This skill exists to make new/
updated skills conform on the first try instead of drifting from the
pattern set by `proposal/`, `weekly-digest/`, `jira/`, etc.

## Frontmatter rules

Every `SKILL.md` starts with YAML frontmatter:

- `name`: kebab-case, MUST match the directory name exactly (the harness
  resolves skills by directory, not by the frontmatter alone).
- `description`: action verb, third person, one sentence covering **what**
  the skill does, **when** to use it, and the **trigger phrases** a user
  would say — pack in key terms since this is what discovery search
  actually matches against. No vague descriptions ("helps with X",
  "does development tasks").

Good: `"Drafts a one-page technical initiative proposal backed by real
evidence mined from the project. Triggered by '/proposal', 'draft a
proposal', 'propose an initiative'."`

Bad: `"Helps write proposals for the team."` — no what/when specificity, no
trigger phrases, first person framing risk.

## Repo-specific conventions (read before writing anything)

- **Location**: the skill lives at `<name>/SKILL.md` at the repo root —
  NOT under a `skills/` subdirectory. Helper scripts live alongside it in
  the same directory.
- **Absolute paths only for cross-file references.** Skills are
  symlink-installed into `~/.claude/skills/<name>`, so any reference to
  another file in this repo (`shared/tone.md`, a helper script) MUST use
  the absolute path `~/Github/agent-skills/...`. A relative path resolves
  against the symlink target's apparent location and breaks silently.
- **Tone rules for outward-facing text.** Any skill that drafts text
  another person reads (posts, tickets, replies, digests, proposals) must
  `Read` `~/Github/agent-skills/shared/tone.md` and call out its key rules
  inline in the SKILL.md body (real numbers only, frame gaps as scope not
  failure, no defensive lead, anonymize) — don't just link to it silently.
- **Draft-first, always.** Anything that posts, files, or sends externally
  (Confluence, Jira, chat channels, PRs) must present the exact final text
  to the user and get explicit approval before any send/file action. No
  "posting now unless you object."
- **Per-user state or secrets → `local-config.yml`.** Lives next to the
  skill's `SKILL.md`, is gitignored (add the path to the repo root
  `.gitignore`, e.g. `weekly-digest/local-config.yml`), and is created
  either by a `setup.sh` or lazily on first run — never shipped with real
  values. The skill itself ships only the generic, config-free playbook.
- **Helper scripts** (`setup.sh`, `*-nudge.sh`, etc.) live inside the
  skill's own directory and must be executable (`chmod +x`).
- **Length**: keep `SKILL.md` at or under ~200 lines. If it grows past
  that, move detailed reference material into a `references/` subdirectory
  and link to it — most skills in this repo don't need one.

## Creating a NEW skill

1. Write `<name>/SKILL.md` following the conventions above.
2. Add a bullet to README's `## Skills` section, matching the existing
   format: **name** — what it does, "Triggered by `/x`, 'trigger phrase'"
   list, and a note if it loads `shared/tone.md` or has a
   `local-config.yml`.
3. Add `ln -s ~/Github/agent-skills/<name> ~/.claude/skills/<name>` to
   README's `## Install` code block, in the same style/order as the
   existing lines.
4. Run that symlink command locally so the skill is actually installed.
5. If the skill has per-user state, add its `local-config.yml` (and any
   `.bak.*` pattern) to the repo `.gitignore`.
6. Remind the user: skills load on the next session start (restart Claude
   Code or start a new session) — this session won't see it yet.
7. Do not commit unless the user explicitly asks.

## Updating an EXISTING skill

1. Read the current `SKILL.md` in full first — don't guess at existing
   structure or overwrite sections you haven't seen.
2. Keep `name:` (and the directory name) stable. Renaming breaks the
   `~/.claude/skills/<name>` symlink and the README bullet/Install line
   that reference the old name — if a rename is genuinely required, update
   all three together.
3. If trigger phrases in the description change, update the matching
   README `## Skills` bullet in the same edit so they don't drift apart.
4. If any path in the body changes, verify it's still absolute
   (`~/Github/agent-skills/...`) — a copy-paste from elsewhere often
   introduces a relative path that breaks post-install.

## Validation

- `head -n 5 <name>/SKILL.md` — frontmatter parses and `name:` matches the
  directory name.
- `ls -la ~/.claude/skills/<name>` — symlink resolves into this repo
  (`~/Github/agent-skills/<name>`).
- Optional: `skills-ref validate ./<name>` if the
  [skills-ref](https://github.com/agentskills/agentskills/tree/main/skills-ref)
  tool is installed — not required, skip silently if it isn't.

## Quality checklist

Before presenting a new or updated skill as done, verify:

- [ ] `name:` matches the directory name exactly
- [ ] `description:` is action-verb-first, third person, states what +
      when, and lists trigger phrases
- [ ] Every cross-repo reference uses an absolute `~/Github/agent-skills/...`
      path, never relative
- [ ] Outward-facing skills load `shared/tone.md` and call out its rules
      inline
- [ ] Anything that posts/files/sends externally is draft-first with
      explicit approval before action
- [ ] Per-user state/secrets live in a gitignored `local-config.yml`, not
      hardcoded in `SKILL.md`
- [ ] Helper scripts are inside the skill directory and executable
- [ ] `SKILL.md` is ≤ ~200 lines (or reference material moved to
      `references/`)
- [ ] README `## Skills` bullet and `## Install` symlink line both added
      (new skill) or kept in sync (renamed trigger phrases)
- [ ] Nothing committed unless the user explicitly asked
