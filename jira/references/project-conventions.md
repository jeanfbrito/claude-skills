# Jira skill — project conventions, issue types, statuses

Read when: you need the full issue-type / status / component reference, or
you're discovering project keys and don't yet have them in
`local-config.yml`.

## Discovering projects

Most orgs have a few core projects you'll see often. Discover them on
first use:

```bash
jira project list --plain --no-headers --columns key,name | head -20
```

Save the keys you actually care about into `local-config.yml` (or just
remember the conversational mapping). When the user says "the desktop
one" / "the customer issue" / "the platform bug" without a key, infer the
project from context (working directory, recent conversation, branch
name). If you can't tell, ASK — guessing wrong on a write is worse than a
one-line clarifying question.

## Your primary project

`defaults.primary_project` in `local-config.yml` is the project you spend
most time in. Whenever the user mentions "ticket / issue / bug" without a
project key, default to that project.

## Valid issue types

Vary per project. Run `jira init` once to populate them in
`~/.config/.jira/.config.yml`. Common ones across most projects:

- `Bug` — broken behavior, regression, crash
- `Task` — generic engineering work that doesn't fit Bug/Story
- `Improvement` — chore / refactor / ops / cleanup / runbook / dep bump /
  credential rotation
- `Story` — new capability tracked as user-facing work
- `New Feature` — user-visible feature (some teams use Story instead)
- `Epic` — multi-issue effort
- `Sub-task` — child of another issue

Some orgs add `Debt`, `sub-bug`, `Spike`, etc. — ask the user which ones
their team actually files before defaulting.

For chore/credential/runbook work pick `Improvement`. For investigation
tickets that ship code, `Task`. Don't second-guess if the work matches one
of these — file it.

## Statuses

Vary per project workflow. The classic chain is `To Do` → `In Progress` →
`Done`. Many engineering orgs add `Ready for Dev` (after triage) and
`Ready for QA` (after PR opens). When transitioning via `jira issue move`,
pass the target status name **exactly** as the workflow expects (case-
and space-sensitive). To enumerate available transitions for a specific
issue:

```bash
jira issue view <KEY> --raw | jq '.fields.status'
# or
jira issue move <KEY>   # interactive — shows available transitions
```

Pin known statuses in `local-config.yml` under `workflow_statuses:` so the
skill doesn't have to rediscover them every session.

## Default component

Read from `defaults.default_component` in `local-config.yml`. If set,
pass `--component <value>` whenever creating in the primary project.
Other projects keep their own defaults — apply this rule only to the
primary project unless the user says otherwise.

## Defaults for primary-project tickets

When creating a ticket in the primary project, always pass:

- `-a $(jira me)` — assign on creation if `defaults.default_assignee` is
  empty (or matches the current user). Standing preference; do not ask.
- `--component <defaults.default_component>` — when set; required so the
  ticket reaches the right swimlane.

Other projects keep their own defaults — these rules are scoped to the
primary project. Confirm with the user before applying assignee/component
to a non-primary project.

## Listing a project's components

```bash
curl -sS -u "$ATLASSIAN_EMAIL:$JIRA_API_TOKEN" \
  "https://$ATLASSIAN_SITE/rest/api/3/project/<KEY>/components" | jq '.[].name'
```

Other projects often don't use components — don't force one in.

## More `assign` / `edit` variants

```bash
jira issue assign <KEY> $(jira me)
jira issue assign <KEY> someone@example.com
jira issue assign <KEY> default        # default assignee
jira issue assign <KEY> x              # unassign

jira issue edit <KEY> --summary "New summary" --label needs-review
jira issue edit <KEY> --custom story-points=3
```
