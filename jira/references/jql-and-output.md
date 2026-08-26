# Jira skill — JQL cookbook & output flags

Read when: writing a custom JQL query beyond the canonical examples in
SKILL.md, or picking output flags for scripting/piping.

## JQL cookbook

Pass any of these to `jira issue list -q '...'`:

```jql
# My open work, freshest first
# (use --order-by updated --reverse on the command line, not ORDER BY in JQL)
assignee = currentUser() AND resolution = Unresolved

# What I'm doing in the active sprint
assignee = currentUser() AND sprint in openSprints()

# Things I reported that are still open
reporter = currentUser() AND resolution = Unresolved

# Stale stuff — open >30 days, not updated in 14
resolution = Unresolved AND created < -30d AND updated < -14d AND assignee = currentUser()

# Bugs ready to pick up in your primary project
project = <KEY> AND status = "Ready for Dev" AND assignee is EMPTY AND issuetype = Bug

# Customer-driven escalations in a support project
project = <SUPP> AND assignee = currentUser() AND resolution = Unresolved

# Touched by me this week (any project)
assignee was currentUser() AFTER -7d
```

JQL gotchas: use `currentUser()` not your account ID (more portable), use
double-quoted strings for status names with spaces (`"Ready for Dev"`), and
`was` for historical assignee changes.

**`ORDER BY` in jira-cli:** the JQL `ORDER BY` clause is rejected when
passed via `-q` (`Error in the JQL Query: Expecting ',' but got 'ORDER'`).
Use the dedicated flags instead:

```bash
jira issue list -q "project = <KEY>" --order-by created --reverse
```

Drop `ORDER BY ...` from the JQL string entirely; pass it as `--order-by
<field> [--reverse]` next to the query.

## Output discipline

| Goal                                | Flags                                                        |
| ----------------------------------- | ------------------------------------------------------------ |
| Show the user a readable list       | (defaults — TUI table)                                       |
| Pipe to `head`, `awk`, etc.         | `--plain --no-headers`                                       |
| Pick specific columns               | `--plain --no-headers --columns key,summary,status,assignee` |
| Get raw JSON for further processing | `--raw`                                                      |
| CSV for spreadsheet export          | `--csv`                                                      |
| Fixed pagination                    | `--paginate 1:N` (page:size)                                 |

## "What am I working on" — the full display rules

The default view is a **cross-project, priority-sorted** list excluding
terminal statuses (Done, Mitigated, Parking Lot, Cancelled). This is what
the user expects when they ask "what's open for me":

```bash
# Step 1: fetch all open tickets across all projects
jira issue list -q "assignee = currentUser() AND resolution = Unresolved AND status NOT IN ('Done', 'Mitigated', 'Parking Lot', 'Cancelled')" \
  --order-by priority --reverse --plain --columns key,summary,status,priority

# Step 2: present as a single table sorted by priority (Highest → Unprioritized), grouped visually
```

Display rules:

- **Exclude** tickets with status: Done, Mitigated, Parking Lot, Cancelled
- **Sort by priority**: Highest → High → Medium → Low → Lowest → Unprioritized
- **Include project column** (infer from key prefix) so cross-project view is clear
- **Show status column** — the user wants to see To Do vs Ready for Dev vs Specifying etc.
- Present as a markdown table with columns: Priority, Key, Project, Summary, Status

## Viewing a single issue

```bash
jira issue view <KEY>
```

Note: jira-cli's ADF renderer is incomplete — some Atlassian Document
Format nodes (panels, status lozenges, custom emoji) render imperfectly.
If the user wants the raw description for inspection, use `--raw` to dump
JSON instead.

## Default sprint context

If your primary project uses Scrum, the active sprint changes regularly.
Re-discover at runtime:

```bash
jira sprint list --project <KEY> --current --plain --no-headers
```

Don't hard-code sprint IDs in commands you write for the user. Always look
them up at runtime if needed. Kanban-only projects won't return sprints —
that's expected, not an error.

## Boards / sprints (Scrum projects only)

```bash
jira board list --project <KEY>
jira sprint list --project <KEY> --current
jira sprint list --project <KEY> --state future,active
```
