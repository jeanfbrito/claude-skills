---
name: jira
description: Drive your Atlassian Jira workspace from a terminal session via the `jira` CLI (ankitpokhrel/jira-cli). Use this skill ANY time the user asks about Jira tickets, issues, sprints, JQL, boards, story points, worklogs, or names a project key from your org — even if they don't say the word "Jira". Also use it for vague work-status questions like "what's on my plate", "what am I working on", "what's blocked", "show me my open tickets", "current sprint", "ready for dev queue", because that work usually lives in Jira. Skip this skill only when the user is clearly asking about something else (Confluence pages, GitHub PRs, Slack messages) — for those, use the appropriate other tool. Personal defaults (primary project key, default component, default assignee, workflow status names) live in `local-config.yml` next to this file (gitignored), populated by `setup.sh`.
---

# Atlassian Jira workflow (jira-cli)

This skill captures a working setup against any Atlassian Cloud Jira so you
can answer Jira questions and execute Jira workflows directly in the
terminal instead of nudging the user to "go check Jira."

User-specific config — Atlassian site, email, primary project, default
component, default assignee — lives in `local-config.yml` next to this
file. That file is gitignored; run `setup.sh` once to populate it. Read
defaults from `local-config.yml` whenever this document references "your
primary project" / "your default component" etc.

**Setup gate.** If `jira-env.sh` warns that `local-config.yml` is missing,
stop before any project/issue-type probing: run
`~/.claude/skills/jira/setup.sh` (or ask the user for the primary project
key once and write `defaults.primary_project` to `local-config.yml`
yourself). Do not re-derive project keys, boards, or issue types ad hoc
with `jira project list` / grep chains — that costs 5–10 tool calls per
session and was the top waste in three of the last twelve sessions.

## Preconditions — verify before running commands

Before the first `jira` invocation in a session, verify the binary exists:

```bash
command -v jira >/dev/null 2>&1 || echo "MISSING"
```

If it prints `MISSING`, tell the user to run
`~/.claude/skills/jira/setup.sh` and stop.

Also verify the config has an `issue.types` block before any write attempt
(`CONFIG_INCOMPLETE` → tell the user to run `setup.sh`, don't hand-write
the block — full recovery steps in
`~/Github/agent-skills/jira/references/troubleshooting.md`):

```bash
grep -qE "^[[:space:]]+types:" ~/.config/.jira/.config.yml || echo "CONFIG_INCOMPLETE"
```

## Loading the CLI and auth

`jira-cli` reads the API token from the `JIRA_API_TOKEN` env var. The
token lives in macOS Keychain (service `jira-cli`, account = your
Atlassian email). Source the skill-local helper before any `jira`
invocation so the env var is always fresh:

```bash
source ~/.claude/skills/jira/jira-env.sh && jira me
```

If the user has already added `source jira-env.sh` to their shell rc, the
explicit `source` is redundant — but it's cheap and harmless, and
guarantees the command works even in a one-off shell.

401 on `jira me` → stale/revoked token; tell the user to mint a fresh one
and rerun `setup.sh` (details:
`~/Github/agent-skills/jira/references/troubleshooting.md`).

## Defaults from `local-config.yml`

- `defaults.primary_project` — the project to assume when the user says
  "ticket / issue / bug" without a key.
- `defaults.default_component` — pass `--component <value>` when creating
  in the primary project.
- `defaults.default_assignee` — assign on creation only when set (or the
  user says so); never assume otherwise.
- `workflow_statuses` — pinned status names so you don't have to
  rediscover the workflow chain every session.
- `defaults.priority_projects` — comma-separated project keys whose
  tickets are customer-facing escalations. **They always rank above
  everything else** when answering "what's on my plate" / "what should I
  do first", regardless of the Jira priority field: list them in their own
  block at the top, then the rest by priority. `jira-mine` already does
  this split. Never bury one of these under an internal Highest ticket.

Full issue-type table, status-chain conventions, project discovery, and
component listing: read when creating/moving tickets and you need the
complete reference —
`~/Github/agent-skills/jira/references/project-conventions.md`

## Core command patterns

**List** (assignee/status/project filters via JQL, plain output for
scripting):

```bash
jira issue list -q "assignee = currentUser() AND resolution = Unresolved" --plain --no-headers --columns key,summary,status,priority
```

**Project scope trap.** `jira issue list` silently ANDs `project = <primary
project>` into every query unless the `-q` string itself mentions `project`.
For "what's on my plate" / "my open tickets" / anything cross-project, add
`project is not EMPTY` (always true) to the JQL so nothing gets hidden —
support escalations assigned to the user (e.g. SUP tickets) otherwise never
show up. Sorting: use `--order-by <field>` (`--reverse` flips it); an
`ORDER BY` inside `-q` returns a 400. The skill ships this as a script:

```bash
~/.claude/skills/jira/jira-mine                        # all my open issues, all projects, Highest first
~/.claude/skills/jira/jira-mine "status = 'In Progress'"   # extra JQL AND-ed in
~/.claude/skills/jira/jira-mine --count
```

Output comes in two blocks: `defaults.priority_projects` first (always the
top of the answer), then everything else ordered by priority.

**View** a single issue:

```bash
jira issue view <KEY>
```

**Create** (draft-first — see below):

```bash
jira issue create --project <KEY> --type Task --summary "Brief actionable summary" --body "Detailed description (markdown ok)" --no-input
```

**Move** (transition status — target name must exactly match a valid
transition):

```bash
jira issue move <KEY> "In Progress"
```

**Comment** (draft-first — see below):

```bash
jira issue comment add <KEY> "Shipped the dep bumps in PR #1234"
```

**Worklog:**

```bash
jira issue worklog add <KEY> "2h 30m" --comment "Reviewing CVE patches"
```

**Assign** (`$(jira me)` / an email / `default` / `x` to unassign):

```bash
jira issue assign <KEY> $(jira me)
```

**Edit fields** (description, summary, labels, custom fields):

```bash
jira issue edit <KEY> --summary "New summary" --label needs-review
```

**JQL search** — one canonical form; the full cookbook (stale tickets,
sprint filters, cross-project escalations, `ORDER BY` gotcha) is in
`~/Github/agent-skills/jira/references/jql-and-output.md`:

```bash
jira issue list -q "project = <KEY> AND status = 'Ready for Dev'" --plain --no-headers --columns key,summary | head
```

Full output-flag table (`--raw`, `--csv`, `--paginate`) and board/sprint
commands: `~/Github/agent-skills/jira/references/jql-and-output.md`

## Draft-first — required for every write

Mutations are cheap to perform but expensive to undo (especially in
projects with many watchers). Before `jira issue create`, `comment add`,
`edit`, `move`, `assign`, `worklog add`, or `link`: **show the user the
exact fields (summary, body/comment text, target status, command) and ask
"shall I run this?"** — unless the user explicitly said "go ahead and X"
with the specifics already given. Wait for explicit confirmation before
running the write.

For the two highest-value write workflows — synthesizing a session into a
ticket comment, and opening a new ticket for in-flight work (plus
cross-project linking/escalation) — the full patterns, worked examples,
and common slips are in
`~/Github/agent-skills/jira/references/workflows.md`

## Tone for ticket text

Before drafting any comment, description, or worklog note a human will
read, load `~/Github/agent-skills/shared/tone.md` and apply it. Key rules
to keep front of mind while drafting:

- **Real numbers only** — never invent metrics, counts, or time estimates.
- **Don't name third parties** — no blaming individuals or other teams by
  name in ticket text.
- **Don't guess the source channel** — if you don't know whether a report
  came from a customer, a teammate, or monitoring, say so or omit it
  rather than assume.
- No defensive lead when replying to a raised issue — investigate first,
  explain after.

## Reference index

- `~/Github/agent-skills/jira/references/project-conventions.md` — read
  when discovering project keys, or you need the full issue-type/status/
  component reference before creating or moving a ticket.
- `~/Github/agent-skills/jira/references/jql-and-output.md` — read when
  writing a JQL query beyond the canonical example above, or picking
  output flags for scripting/piping, boards/sprints.
- `~/Github/agent-skills/jira/references/workflows.md` — read when
  synthesizing session work into a ticket comment, opening a new ticket
  for in-flight work, or linking/escalating across support and
  engineering projects.
- `~/Github/agent-skills/jira/references/troubleshooting.md` — read when
  any `jira` command errors, the config looks incomplete, or you need the
  full error catalog / REST escape-hatch details.
