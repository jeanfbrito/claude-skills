---
name: skill-checkup
description: "Grades the skills in ~/Github/agent-skills against recent local Claude Code sessions — scoring efficiency and code quality, measuring which skills actually fire — then drafts concrete SKILL.md edits and a shareable local report. Triggered by '/skill-checkup', 'skill checkup', 'grade my skills', 'how are my skills doing', 'which skills never trigger', 'audit my skills'."
---

# Skill Checkup

Grade the user's Claude Code skill setup by scoring recent local session
history, then propose concrete skill edits and render one shareable report
page. Adapted from [warpdotdev/common-skills](https://github.com/warpdotdev/common-skills)
`skill-doctor` (MIT License), reworked for Claude Code only and this repo's
conventions.

Everything runs locally. Transcripts and session data never leave this
machine — the only shareable artifact is the report the user chooses to
post, and even that contains no raw transcript text, only scores and
proposed diffs.

Let `SKILL_ROOT` = `~/Github/agent-skills/skill-checkup` (absolute — this
skill is symlink-installed into `~/.claude/skills/skill-checkup`).

Never write artifacts into this repo. Create one fresh scratch directory
per run and use it as `REPORT_DIR`:

```bash
REPORT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/skill-checkup-XXXXXXXX")"
```

## Step 1: Collect

```bash
python3 "$SKILL_ROOT/scripts/collect_sessions.py" --out "$REPORT_DIR"
```

Our defaults (no flags needed for the common case):

- `--skills-dir ~/Github/agent-skills` — skills discovered as `<name>/SKILL.md`
  at the repo root (this repo's layout).
- `--days 45`, `--max-sessions 12`.
- `--all-repos` is ON by default: every Claude Code session under
  `~/.claude/projects/` in the window counts, not just sessions whose cwd is
  inside one repo — these skills are installed globally and used everywhere.
  Pass `--repo PATH` to scope to one repo instead (this turns `--all-repos`
  off).
- `--include-subagents` is ON by default: this user's orchestrator setup
  delegates edits to builder subagents, so the code-quality evidence often
  lives in sidechain transcripts, not the parent session. Pass
  `--no-subagents` to exclude them.

Read `$REPORT_DIR/inventory.json`. If `stats.sessions_sampled` is 0, tell the
user there's nothing recent to score (suggest raising `--days`) and stop.

## Step 2: Score each sampled transcript

Pass both rubrics as context:

- `$SKILL_ROOT/scorers/efficiency.md`
- `$SKILL_ROOT/scorers/code-quality.md`

For each transcript in `$REPORT_DIR/transcripts/`, read it and judge it
against both rubrics. Record: label, numeric score (from the rubric's label
table), and a 1–3 sentence reason citing specifics from the transcript.
Apply the code-quality scorer only where the transcript shows code changes;
otherwise record `insufficient_evidence` and exclude that session from the
code-quality average.

## Step 3: Aggregate

- `efficiency` = mean of efficiency scores across all scored sessions.
- `code_quality` = mean of code-quality scores, excluding
  `insufficient_evidence`. If none had enough evidence, set it to 0.5 and
  say so in the findings.
- **`skill_coverage` = fraction of sampled sessions with at least one real
  skill invocation.** `inventory.json`'s `skill_usage` and each session
  record distinguish `invoked` (an actual `Skill` tool call, or a user
  message starting with `/<name>`) from `mentioned` (the skill's name
  merely appears in text or tool output). Coverage, and any "this skill
  never triggers" finding, MUST use `invoked` counts only — a skill whose
  name shows up in conversation but was never actually called is exactly
  the failure this report exists to catch, and `mentioned` would mask it.
- `overall = 0.5 * efficiency + 0.35 * code_quality + 0.15 * skill_coverage`.

Then derive the substance:

- `top_findings`: the 3 most impactful, specific patterns across sessions,
  in STE-100 style — concrete and concise.
- `suggestions`: concrete skill changes tracing back to observed waste or
  defects, not generic best practices — cite the session and the moment
  that motivated each one. A skill with `invoked: 0` across every sampled
  session (but `mentioned > 0`) is almost always a description/trigger-phrase
  problem, and deserves its own suggestion.

## Step 4: Draft skill edits

Follow `$SKILL_ROOT/references/skill-improvements.md` — strict bar, and "no
change is a success" when nothing clears it.

1. Read the skill's current file (path is in `inventory.json`).
2. Write the full improved version to `$REPORT_DIR/proposed/<skill-name>/SKILL.md`.
3. Produce `diff -u <current> <proposed>` and put it in the suggestion's
   `diff` field.

Do not modify the user's real skill files in this step — draft only.
**Applying a suggestion means invoking the `update-skill` skill** on the
approved diff; it owns README bullet sync, absolute-path checks, and the
≤200-line rule. Show each proposed diff to the user and get approval before
invoking `update-skill`. Never commit.

## Step 5: Write report.json and render

```json
{
  "title": "Skill Checkup Report",
  "generated_at": "<ISO timestamp>",
  "harness": "claude",
  "handle": "agent-skills",
  "stats": {
    "sessions_analyzed": 0, "sessions_scanned": 0,
    "skills_found": 0, "skills_used": 0, "window_days": 45
  },
  "scores": {"efficiency": 0.0, "code_quality": 0.0, "skill_coverage": 0.0, "overall": 0.0},
  "top_findings": ["", "", ""],
  "suggestions": [
    {
      "skill": "",
      "change": "<one-sentence summary of the edit>",
      "evidence": "<which session(s) and what happened that motivates this>",
      "proposed_path": "<path under proposed/, if an edit was drafted>",
      "diff": "<unified diff, or full content for a new skill>"
    }
  ]
}
```

```bash
python3 "$SKILL_ROOT/scripts/render_report.py" "$REPORT_DIR/report.json"
```

Writes a single self-contained `$REPORT_DIR/report.html`.

## Step 6: Output

Tell the user the grade and the three findings, in text. Then:

- Your quality report: `file://$REPORT_DIR/report.html`

Ask whether they want the suggestions applied (per-suggestion approval,
via `update-skill`).

## Relationship to `/learn`

`/learn` captures a single skill lesson in-session, right when it happens.
`skill-checkup` is the periodic cross-session sweep across everything —
run it monthly, or before a big skill refactor, to catch patterns no single
session would surface (a skill that's never once fired in a month of real
use, a rubric-level code-quality regression across several sessions).

## Quality checklist

Before presenting the report as done, verify:

- [ ] Nothing outside `$REPORT_DIR` was written
- [ ] `skill_coverage` and every "never triggered" finding used `invoked`
      counts, not `mentioned`
- [ ] Every proposed edit traces to a specific session and moment, per
      `skill-improvements.md`'s bar — no generic best-practice suggestions
- [ ] Proposed edits were drafted to `$REPORT_DIR/proposed/`, not applied
      to the real skill files
- [ ] The user was shown diffs and asked before any `update-skill`
      invocation
- [ ] Nothing was committed
