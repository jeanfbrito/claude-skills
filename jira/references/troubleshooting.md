# Jira skill — troubleshooting

Read when: a `jira` command errors, the config looks incomplete, or you need
the full error catalog before improvising a fix.

## `Error: invalid issue types in config`

`jira issue create` requires an `issue.types` block in
`~/.config/.jira/.config.yml` listing the issue types known to the target
project. If the config is missing this block (e.g. fresh install, or
`jira init` was never run), every create call will fail with `Error: invalid
issue types in config` regardless of the `--type` value.

Do **not** hand-write fake IDs — jira-cli will panic at runtime
(`interface conversion: interface {} is nil, not bool`). Bootstrap correctly:

1. Run `jira init` interactively and let it pick the default project. It
   populates the `issue.types` block with real IDs and `subtask` flags
   pulled from the API.
2. Or, if `jira init` is not feasible, fetch real type IDs via REST and
   write them yourself with the exact shape jira-cli expects:
   ```yaml
   issue:
     types:
       - id: "10001"
         name: Bug
         handle: Bug
         subtask: false
   ```
   The `subtask: false` (or `true` for Sub-task) field is mandatory;
   omitting it triggers the panic above.

Until the config is valid, all `jira issue create` invocations are blocked.
Tell the user, do not improvise.

## Config completeness check

Verify the config has an `issue.types` block before any write attempt:

```bash
grep -qE "^[[:space:]]+types:" ~/.config/.jira/.config.yml || echo "CONFIG_INCOMPLETE"
```

If it prints `CONFIG_INCOMPLETE` (or the file only has the four-line stub:
installation/auth_type/server/login), `jira issue create` and `jira issue
move` will fail. Tell the user:

> The jira-cli config doesn't have project metadata yet. Run
> `~/.claude/skills/jira/setup.sh` (idempotent — re-running re-runs `jira
init`), pick your primary project as default, accept the prompts. That
> populates `issue.types`, custom fields, board, epic schema. Then we can
> continue.

## Authentication failures

If `jira me` returns a 401, the most likely cause is a stale or revoked
token. Tell the user to mint a fresh one at
https://id.atlassian.com/manage-profile/security/api-tokens and rerun the
setup script — don't try to "fix" the token yourself.

## Error catalog / pitfalls

- **`jira sprint list` caps at 25 sprints.** Usually fine (you want
  `--current` or `--state active,future`). For historical sprint
  analytics, fall back to `/rest/agile/1.0/board/<id>/sprint?startAt=N`
  directly via curl.
- **Pagination on `issue list`.** `--paginate <page>:<limit>` — `<limit>`
  is capped at 100 (passing larger errors with `Format <from>:<limit>,
where <from> is optional and <limit> must be between 1 and 100`). For
  "all" loop pages: `--paginate 1:100`, `--paginate 2:100`, etc.
- **Custom fields.** Story points, epic link, etc. are `customfield_*`.
  They're not in the default columns; you have to add them via
  `--columns` or use `--raw` and parse JSON.
- **Display names with spaces.** When using `-a` for assignee, prefer the
  email or `$(jira me)`, not the display name — display name matching is
  fuzzy and can match the wrong person.
- **`Error: invalid issue types in config`.** Means the config has no
  `issue.types` block (fresh install or stub). Run `jira init`
  interactively to populate it. Do not hand-write entries — bad IDs panic
  the binary.
- **Issue-type names are case-sensitive.** Pass them as `Bug`, `Task`,
  `Improvement`, `Story`, `New Feature`, `Epic`, `Sub-task` — not
  lowercase, not pluralised. If `jira issue create` returns `Error:
invalid issue type 'X'`, check spelling against the populated config
  (`grep -A 30 "^issue:" ~/.config/.jira/.config.yml`).
- **`ORDER BY` inside `-q` is rejected** (`Expecting ',' but got 'ORDER'`).
  Use `--order-by <field> [--reverse]` flags. See the JQL cookbook
  (`~/Github/agent-skills/jira/references/jql-and-output.md`).
- **REST `/rest/api/3/project/<KEY>` may return 404** (`No project could
be found with key '<KEY>'`) when called with the API token. Browse
  permissions for some projects are not granted to API tokens, only to
  the logged-in UI session. Don't rely on REST for project metadata or
  `createmeta` lookups against those projects — fetch type names
  indirectly via `jira issue list` against existing issues, and let
  `jira init` populate the config.
- **`git push` after `git checkout -b`** still requires `-u origin
<branch>` for the first push of a new branch (no auto-tracking by
  default). If you see `fatal: The current branch ... has no upstream
branch`, retry with `git push -u origin <branch>`.

## When to escape to direct REST

The `jira` CLI covers ~90% of needs. Reach for `curl` against
`https://$ATLASSIAN_SITE/rest/api/3/...` when:

- You need fields jira-cli doesn't surface (custom field schemas, workflow
  definitions, screen configs)
- You need historical sprint data beyond the 25-cap
- You're inspecting raw ADF to debug a rendering issue
- You're doing a bulk operation jira-cli doesn't support

Auth pattern: `curl -u "$ATLASSIAN_EMAIL:$JIRA_API_TOKEN"` — the same
email/token combo, basic auth. Both env vars are populated by
`~/.claude/skills/jira/jira-env.sh` (token from Keychain, email from
`local-config.yml`).

**Permission caveat:** the API token has narrower project access than the
logged-in UI. Endpoints like `/rest/api/3/project/<KEY>`,
`/rest/api/3/issue/createmeta/<KEY>/issuetypes`, and individual issue
fetches against some projects (`/rest/api/3/issue/<KEY>-XXXX`) can return
`404 No project could be found` or `errorMessages: ["You are not
authorized..."]` even when `jira me` works and `jira issue list -q
"project = <KEY>"` returns rows. The CLI uses a different code path that
the token is allowed on; raw REST often is not. If REST 404s, fall back
to: (a) the CLI for that operation, (b) extracting the data from a
CLI-listed sample issue, or (c) asking the user to fetch the resource from
the browser.

## What this skill does NOT cover

- Confluence (use REST or a separate skill)
- Bitbucket / GitHub / GitLab (use their respective CLIs)
- Compass
- Atlassian admin operations (user management, billing)
- Setting up jira-cli from scratch — `setup.sh` handles that
