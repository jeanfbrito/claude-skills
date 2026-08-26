# Jira skill — synthesis workflows, ticket creation, cross-project linking

Read when: the user asks you to synthesize session work into a ticket
comment, open a new ticket for in-flight work, or link/escalate across
support and engineering projects.

## Workflow: synthesize session work into a ticket update

When the user says any variant of _"update <KEY> with what we did"_, _"log
today's work to the ticket"_, _"leave a status note on this issue"_,
_"summarize what we shipped on the JIRA"_, or hands you a ticket key after
a working session — this is the highest-value workflow this skill exists
for. Don't just paste back the user's last message as a comment; the user
already knew what they did. The job is to **synthesize the session's
actual work into a comment future-you would want to read.**

### What "session context" means

You're (typically) running inside Claude Code with full visibility into
the user's working state. Pull from:

- **`git log -n 10 --oneline`** — what commits landed during the session
- **`git diff --stat HEAD~N`** or staged/unstaged diffs — files touched
  and rough size
- **`gh pr view`** if a PR is open in the working directory's repo — link,
  title, status
- **The conversation itself** — decisions discussed, alternatives ruled
  out, things you debugged together
- **Files you edited** — concrete config keys flipped, function
  signatures changed, deps bumped

A comment written from this synthesis is dramatically more useful than
one paraphrased from the user's prompt alone.

### Pattern

1. **Pull session context** before drafting. If you've been working in a
   repo, run `git log` and `git diff --stat` (no need to ask permission
   for read-only git). If a PR exists, grab its URL.
2. **Draft a comment** that's concise, factual, past-tense, and mentions
   concrete artifacts (PR link, commit SHA, file paths, version numbers).
   Aim for 1–3 short paragraphs. No greetings, no sign-offs, no thanks.
3. **Echo the proposed comment AND the exact command** back to the user,
   formatted as a block quote followed by the bash. This is the
   contract — they see the wording before it lands on a ticket their team
   watches.
4. **Wait for explicit confirmation.** "shall I post?" — and stop. Don't
   run the write until they say yes/go/post/ship/do it. Editing the
   wording on request is fine and expected.
5. **Offer adjacent updates as a follow-up** in the same response: _"also
   want me to (a) log a worklog of Xh, (b) move it to Ready for QA, (c)
   link the PR via Smart Commits?"_ — but as a question, not an assumed
   next step.

### Comment style guide

| Do                                                                 | Don't                                      |
| ------------------------------------------------------------------ | ------------------------------------------ |
| Past tense, declarative ("Bumped electron 28→30, patched 7 CVEs.") | Future/aspirational ("Will work on CVEs.") |
| Concrete artifacts (PR #1234, file paths, commit SHAs, versions)   | Vague ("did some work on the deps")        |
| Lead with the outcome, then context if needed                      | Bury the outcome in setup                  |
| Skip greetings/signoffs — Jira knows who you are                   | "Hi team," / "Thanks!" / "— Name"          |
| Mention follow-ups explicitly if any                               | Leave them implied                         |

### Worked example

**User:** _(after a session)_ update PROJ-1755 with what we shipped today

**You (good):**

```bash
git log -n 5 --oneline && git diff --stat origin/main...HEAD
# (pulls SHAs and file scope)
gh pr view --json url,title,state -q .url 2>/dev/null
# (grabs PR URL if open)
```

Then:

> Here's what I'd post on PROJ-1755, synthesized from this session:
>
> > Bumped framework 28.3.3 → 30.4.1 and patched 7 high-severity CVEs (axios, ws, formidable, semver, cookie, ip, tar — see `package.json` lockfile). Updated build matrix; macOS arm64 smoke test green. PR: https://github.com/example/repo/pull/1234
>
> ```bash
> source ~/.claude/skills/jira/jira-env.sh && \
>   jira issue comment add PROJ-1755 "Bumped framework 28.3.3 → 30.4.1 and patched 7 high-severity CVEs (axios, ws, formidable, semver, cookie, ip, tar — see package.json lockfile). Updated build matrix; macOS arm64 smoke test green. PR: https://github.com/example/repo/pull/1234"
> ```
>
> Shall I post it? Also: want me to (a) log a worklog with the time, or (b) move the ticket to "Ready for QA" since the PR is up?

**You (bad — just paraphrasing the prompt):**

> ```bash
> jira issue comment add PROJ-1755 "Shipped the dep update work today"
> ```

The bad version wastes the context Claude Code has. The good version
captures what actually changed and gives the team something to grep for
in three months.

### When the user IS the source of truth

If the user explicitly dictates the comment ("post 'PR coming today' on
PROJ-1755"), don't editorialize — use their wording verbatim. Synthesis is
for when they ask you to capture _what we did_, not when they're handing
you a literal message to send.

## Workflow: open a new ticket for in-flight work

The mirror image of "synthesize → update": the user is mid-work on
something that doesn't have a ticket yet, and asks you to create one.
Triggers: _"open a ticket for this"_, _"create a jira task for what I'm
working on"_, _"there's no ticket yet — can you make one"_, _"file a bug
for what we just hit"_. This is a write — same safety posture as comments.

### Decisions you have to make first

1. **Project.** Infer from working directory, conversation, and
   `defaults.primary_project` in `local-config.yml`. Customer-reported
   issue → support project. Partner integration repo → integration
   project. If unclear, ASK — don't guess at a project that has many
   watchers.

2. **Issue type.** Map the work to one of the project's valid types:
   | Work pattern | Type |
   |---|---|
   | We're fixing broken behavior, regression, crash | `Bug` |
   | We're doing chore / refactor / dep-bump / cleanup / runbook / credential rotation | `Improvement` |
   | Generic engineering work that doesn't fit Bug or Story | `Task` |
   | We're adding a user-visible capability or feature | `Story` (or `New Feature` if the team prefers) |
   | We're researching/spiking/POC | `Task` (with `[spike]` prefix in summary) |
   | We're tracking a multi-issue effort | `Epic` (rare — usually you want a child issue linked to an existing Epic) |
   | We're filing a child of an existing issue | `Sub-task` |

   If genuinely unsure about which type fits, ASK. Default-guessing wrong
   clutters the wrong reports.

3. **Component.** If `defaults.default_component` is set in
   `local-config.yml` AND you're filing in the primary project, pass
   `--component <value>`. To list a project's components, see
   `~/Github/agent-skills/jira/references/project-conventions.md`. Other
   projects often don't use components — don't force one in.

4. **Parent / epic link.** Many projects organize Stories/Improvements/Bugs
   under an Epic. If you've been working in a feature branch named like
   `feat/PROJ-1234-foo`, that issue key is probably the parent epic — use
   `--parent PROJ-1234`. If you can't tell, omit the flag and the user can
   add it after.

### Drafting the summary and description

**Summary** — one line, imperative, ≤ 80 chars, no period. Lead with the
verb. Include enough specifics that someone scanning a backlog gets it
without opening the ticket.

| Good summary                                               | Bad summary           |
| ---------------------------------------------------------- | --------------------- |
| "Audio echoes after Bluetooth headset reconnects mid-call" | "Audio bug"           |
| "Bump framework 28 → 30 and patch 7 transitive CVEs"       | "Update dependencies" |
| "Crash on macOS arm64 when opening Settings while in DND"  | "Settings crash"      |

**Description** — three short sections, no headers needed unless the
description gets long:

1. **Context / what's happening** — the problem in 1-2 sentences, with
   reproduction steps if it's a bug
2. **Approach** — what you're doing about it (link the PR or branch if
   one exists)
3. **Status** — where this stands right now (investigating, PR open,
   blocked on X)

Pull from session context: branch name, PR URL, recent commits, files
touched, decisions made together. Same synthesis discipline as the
comment workflow.

### The command

```bash
jira issue create --project <KEY> \
  --type Bug \
  --component <component-if-applicable> \
  --summary "Audio echoes after Bluetooth headset reconnects mid-call" \
  --body "On macOS 14+, after disconnecting and reconnecting an AirPods Pro mid-voice-call, the local mic input loops back into the speaker stream causing a 200–400ms echo.

Repro: start a voice call, disconnect AirPods, wait 5s, reconnect.
Affected: macOS 14.4+, framework 28.x.

Approach: investigating whether it's the WebRTC audio pipeline reinitializing or a Chromium-side regression. Branch: bugfix/audio-echo-bt-reconnect.

Status: investigating, no PR yet." \
  --no-input
```

`--no-input` is mandatory for non-TTY invocation. `--label`, `--priority`,
`--assignee`, `--parent` are optional — only set when the user specifies
(or per `local-config.yml` defaults).

### Pattern in practice

1. Pull session context (`git status`, `git log`, branch name, optionally
   `gh pr view`).
2. Decide project + type. If ambiguous, **ask before drafting** — a single
   clarifying question is cheaper than a wrong-shaped ticket.
3. Draft summary + description.
4. Echo the proposed `jira issue create` command back to the user
   **including** the rendered summary + description as a block quote so
   they can read what's about to land.
5. Wait for confirmation. Stop.
6. After creation, jira-cli prints the new key. Capture it and offer
   follow-ups: _"Created PROJ-2117. Want me to (a) assign it to you, (b)
   link the PR via Smart Commits, (c) add it to the active sprint?"_

### Common slips to avoid

- **Don't assign on create unless the user said so** (or
  `defaults.default_assignee` is set). Many teams have triage workflows
  that route unassigned bugs differently. Let the user opt in.
- **Don't set priority unless asked.** Priority is usually a triage/PM
  call, not the engineer's.
- **Don't include `[BUG]` / `[TASK]` prefixes in the summary.** Jira
  already shows the type as an icon — the prefix is noise.
- **Don't paste raw stack traces into the summary.** Stack traces go in
  description with triple-backtick fencing; summary should be
  human-readable.
- **Match the project's prevailing tone.** A scan of recent tickets via
  `jira issue list -q "project = <KEY>" --order-by created --reverse
--plain --no-headers --columns key,summary | head -20` will show
  whether the project uses sentence-case, title-case, or terse
  imperative.

## Cross-project workflows (escalations, linking, references)

A common pattern: a customer-reported issue lives in a support project;
the engineering fix lives in a separate ticket linked back to it. The
support ticket is the customer-facing record; the engineering ticket
carries the technical detail.

### When the user mentions a ticket by URL or key

If the user says _"I'm working on SUPP-1025"_ or pastes a Jira URL,
**load the ticket context first** before doing anything else. The user
may assume you already know what's in it; you don't.

```bash
source ~/.claude/skills/jira/jira-env.sh && jira issue view SUPP-1025
```

If the description renders poorly because of ADF nodes jira-cli doesn't
handle (panels, info banners, embedded media), fall back to REST:

```bash
curl -sS -u "$ATLASSIAN_EMAIL:$JIRA_API_TOKEN" \
  "https://$ATLASSIAN_SITE/rest/api/3/issue/SUPP-1025?fields=summary,status,description,issuelinks" | jq .
```

Also scan the **summary text for bare ticket references** like
_"PROJ-595 is Done, worked for a while, but now it doesn't work
anymore."_ — those are informal links the team relies on but Jira doesn't
treat as formal `issuelinks`. When you see them, mention the related
tickets to the user and offer to view them too.

### Comment voice depends on audience

| Project audience                                                          | Voice                                                                                                                                                                      |
| ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Customer-facing (support tickets often visible to the customer who filed) | Plain English, no internal jargon, no PR/SHA gunk, customer-progress-oriented ("Confirmed the regression on Windows 11. Working on a fix; expect it in the next release.") |
| Internal engineering                                                      | Technical, precise, artifact-heavy (PR, commit, file paths, version numbers)                                                                                               |
| Mixed (PM, eng, occasionally exec)                                        | Outcome-oriented; technical detail in collapsibles or links                                                                                                                |

When the user asks you to _"comment on SUPP-1025 with what I'm doing"_,
draft for the customer audience even though they framed it as their own
work — strip jargon, lead with outcome. When they ask you to comment on
the engineering-side fix ticket, use the technical voice.

### Spawning an engineering follow-up linked to a support ticket

The shape:

1. Read the support ticket (above).
2. Create the engineering ticket (use the create workflow above),
   referencing the support key in the description.
3. Link them formally so the relationship shows up on both tickets.

```bash
# After creating PROJ-2117:
jira issue link SUPP-1025 PROJ-2117 "is caused by"
# or, depending on which direction the team prefers:
jira issue link PROJ-2117 SUPP-1025 "blocks"
```

Available link types vary by Jira config. Common ones: `relates to`,
`blocks`, `is blocked by`, `is caused by`, `clones`, `duplicates`. If
`jira issue link` errors with "invalid link type", run:

```bash
curl -sS -u "$ATLASSIAN_EMAIL:$JIRA_API_TOKEN" \
  "https://$ATLASSIAN_SITE/rest/api/3/issueLinkType" | jq '.issueLinkTypes[] | .name'
```

to enumerate what's actually configured, and ask the user which direction
makes sense.
