#!/usr/bin/env python3
"""Collect local Claude Code sessions and skills for scoring.

Scans Claude Code project history (`~/.claude/projects/**/*.jsonl`),
discovers installed skills, detects which sessions actually invoked which
skills (vs. merely mentioning them), and emits:

  <out>/inventory.json        - skills, per-session stats, sampling decisions
  <out>/transcripts/<id>.md   - condensed transcripts for sampled sessions

Everything runs locally; nothing is uploaded. Python 3.9+, stdlib only.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_MSG_CHARS = 1500
MAX_TOOL_CHARS = 500
MAX_TRANSCRIPT_ENTRIES = 160
TRANSCRIPT_HEAD = 100
TRANSCRIPT_TAIL = 40

CODE_EDIT_HINTS = ("apply_patch", "*** Begin Patch", "edit_file", "create_file", "str_replace", "write_file")
CLAUDE_CODE_EDIT_TOOLS = {"Edit", "MultiEdit", "NotebookEdit", "Write"}

DEFAULT_SKILLS_DIR = "~/Github/agent-skills"


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--claude-home",
        default=os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude"),
        help="Claude Code config directory (default: CLAUDE_CONFIG_DIR or ~/.claude)",
    )
    p.add_argument(
        "--repo",
        default=None,
        help="explicit repo path to scope sessions to; also disables --all-repos",
    )
    p.add_argument(
        "--all-repos",
        dest="all_repos",
        action="store_true",
        default=True,
        help="consider sessions from every repo under ~/.claude/projects/, not just one "
        "(default: on, since these skills are installed globally)",
    )
    p.add_argument(
        "--no-all-repos",
        dest="all_repos",
        action="store_false",
        help="scope to a single repo (cwd's git root, or --repo)",
    )
    p.add_argument("--days", type=int, default=45, help="only consider sessions modified in the last N days")
    p.add_argument("--max-sessions", type=int, default=12, help="max sessions to sample for scoring")
    p.add_argument("--per-skill", type=int, default=3, help="max sampled sessions per skill")
    p.add_argument("--no-skill", type=int, default=4, help="max sampled sessions that used no skill")
    p.add_argument(
        "--skills-dir",
        action="append",
        default=[],
        help=f"skills directory to scan for SKILL.md files (repeatable; default: {DEFAULT_SKILLS_DIR})",
    )
    p.add_argument(
        "--include-subagents",
        dest="include_subagents",
        action="store_true",
        default=True,
        help="include subagent/sidechain sessions (default: on — orchestrator setups delegate "
        "edits to subagents, so code-quality evidence often lives there)",
    )
    p.add_argument(
        "--no-subagents",
        dest="include_subagents",
        action="store_false",
        help="exclude subagent/sidechain sessions",
    )
    p.add_argument("--out", default="./skill-checkup-report")
    return p.parse_args()


def resolve_repo(repo_arg) -> Path:
    if repo_arg:
        return Path(repo_arg).expanduser().resolve()
    import subprocess

    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10
        )
        if res.returncode == 0 and res.stdout.strip():
            return Path(res.stdout.strip()).resolve()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return Path.cwd().resolve()


def discover_skills(skills_dirs):
    """Skills live directly at `<skills-dir>/<name>/SKILL.md`."""
    skills = {}
    for root in skills_dirs:
        root = Path(root).expanduser()
        if not root.is_dir():
            continue
        for skill_md in sorted(root.glob("*/SKILL.md")):
            name = skill_md.parent.name
            if name in skills:
                continue
            try:
                text = skill_md.read_text(errors="replace")
            except OSError:
                continue
            desc = ""
            m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
            if m:
                desc = m.group(1).strip().strip("\"'")[:300]
            skills[name] = {
                "name": name,
                "path": str(skill_md),
                "description": desc,
                "bytes": skill_md.stat().st_size,
                "modified_at": datetime.fromtimestamp(skill_md.stat().st_mtime, tz=timezone.utc).isoformat(),
            }
    return skills


def find_claude_session_files(claude_home: Path, cutoff: datetime, include_subagents: bool):
    """Find recent Claude Code parent sessions and, optionally, sidechains."""
    projects = claude_home / "projects"
    if not projects.is_dir():
        return []

    candidates = list(projects.glob("*/*.jsonl"))
    if include_subagents:
        candidates.extend(projects.glob("*/*/subagents/*.jsonl"))

    files = []
    for path in candidates:
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if mtime >= cutoff:
            files.append((mtime, path))
    files.sort(key=lambda item: item[0], reverse=True)
    return files


def truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + f" …[truncated {len(text) - limit} chars]"


def extract_text(content) -> str:
    if isinstance(content, str):
        return content
    parts = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                t = block.get("text") or block.get("content") or ""
                if isinstance(t, str) and t:
                    parts.append(t)
            elif isinstance(block, str):
                parts.append(block)
    return "\n".join(parts)


def looks_injected(text: str) -> bool:
    head = text.lstrip()[:80]
    return head.startswith("<") and any(
        tag in head
        for tag in (
            "environment_context", "user_instructions", "ENVIRONMENT", "system-reminder",
            "permissions", "collaboration_mode", "recommended_plugins", "turn_context",
        )
    )


def parse_claude_session(path: Path, skill_names, include_subagents: bool):
    """Normalize one Claude Code JSONL session to the shared transcript shape.

    Returns (meta, stats, entries, skills_invoked, skills_mentioned) or None.

    - skills_invoked: real invocations only — an assistant `Skill` tool_use
      block naming this skill, or a user message that starts with `/<name>`.
    - skills_mentioned: the skill's name appears anywhere in the session's
      text or tool traffic (a much weaker signal — do not use this for
      coverage or "never triggered" findings).
    """
    try:
        raw = path.read_text(errors="replace")
    except OSError:
        return None
    if len(raw) > MAX_FILE_BYTES:
        raw = raw[:MAX_FILE_BYTES]

    meta = {}
    stats = {
        "user_turns": 0,
        "assistant_turns": 0,
        "tool_calls": 0,
        "repeated_tool_calls": 0,
        "error_outputs": 0,
    }
    entries = []
    seen_calls = {}
    seen_assistant_messages = set()
    call_args_text = []
    used_tool_names = set()
    skills_invoked = set()
    first_ts = last_ts = None
    is_sidechain = False

    for line in raw.splitlines():
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        ts = obj.get("timestamp")
        if ts:
            first_ts = first_ts or ts
            last_ts = ts

        if obj.get("isSidechain"):
            is_sidechain = True
            if not include_subagents:
                return None

        if not meta and obj.get("sessionId"):
            session_id = obj.get("sessionId")
            agent_id = obj.get("agentId")
            meta = {
                "id": f"{session_id}-{agent_id}" if agent_id else session_id,
                "cwd": obj.get("cwd"),
                "started_at": ts,
                "originator": "claude-code",
                "thread_source": "subagent" if obj.get("isSidechain") else None,
                "cli_version": obj.get("version"),
                "entrypoint": obj.get("entrypoint"),
            }
        elif meta:
            meta["cwd"] = meta.get("cwd") or obj.get("cwd")
            meta["started_at"] = meta.get("started_at") or ts
            meta["cli_version"] = meta.get("cli_version") or obj.get("version")
            meta["entrypoint"] = meta.get("entrypoint") or obj.get("entrypoint")
            agent_id = obj.get("agentId")
            if agent_id and not meta["id"].endswith(f"-{agent_id}"):
                meta["id"] = f"{obj.get('sessionId') or meta['id']}-{agent_id}"

        record_type = obj.get("type")
        message = obj.get("message")
        if record_type not in ("user", "assistant") or not isinstance(message, dict):
            continue

        role = message.get("role") or record_type
        content = message.get("content")
        blocks = content if isinstance(content, list) else [{"type": "text", "text": content}]
        has_user_text = False

        if role == "assistant":
            message_id = message.get("id") or obj.get("uuid")
            if message_id and message_id not in seen_assistant_messages:
                seen_assistant_messages.add(message_id)
                stats["assistant_turns"] += 1

        for block in blocks:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text")
                if not isinstance(text, str) or not text or looks_injected(text):
                    continue
                if role == "user":
                    has_user_text = True
                    entries.append(("user", truncate(text, MAX_MSG_CHARS)))
                    stripped = text.lstrip()
                    for name in skill_names:
                        if stripped.startswith(f"/{name}"):
                            skills_invoked.add(name)
                elif role == "assistant":
                    entries.append(("assistant", truncate(text, MAX_MSG_CHARS)))
            elif block_type == "tool_use":
                stats["tool_calls"] += 1
                name = str(block.get("name") or "unknown")
                args = block.get("input") or {}
                args_text = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
                key = hashlib.sha1((name + args_text).encode()).hexdigest()
                seen_calls[key] = seen_calls.get(key, 0) + 1
                if seen_calls[key] > 1:
                    stats["repeated_tool_calls"] += 1
                call_args_text.append(args_text)
                used_tool_names.add(name)
                if name == "Skill" and isinstance(args, dict):
                    skill_name = args.get("skill")
                    if skill_name in skill_names:
                        skills_invoked.add(skill_name)
                entries.append((f"tool:{name}", truncate(args_text, MAX_TOOL_CHARS)))
            elif block_type == "tool_result":
                result = extract_text(block.get("content"))
                low = result[:2000].lower()
                if block.get("is_error") or "error" in low or "failed" in low or "traceback" in low:
                    stats["error_outputs"] += 1
                entries.append(("output", truncate(result, MAX_TOOL_CHARS)))

        if role == "user" and has_user_text:
            stats["user_turns"] += 1

    if not meta:
        meta = {
            "id": path.stem,
            "cwd": None,
            "started_at": first_ts,
            "originator": "claude-code",
            "thread_source": "subagent" if is_sidechain else None,
        }
    elif is_sidechain:
        meta["thread_source"] = "subagent"

    # "Mentioned" is a much weaker signal than "invoked": the skill's name
    # shows up somewhere in the conversation text or tool traffic (a Read of
    # its SKILL.md, a passing reference), but no Skill tool call fired.
    text_blob = "\n".join(text for _role, text in entries)
    skills_mentioned = {name for name in skill_names if name in text_blob}
    skills_mentioned.update(skills_invoked)

    stats["first_ts"] = first_ts
    stats["last_ts"] = last_ts
    args_blob = "\n".join(call_args_text)
    stats["has_code_edits"] = (
        bool(used_tool_names & CLAUDE_CODE_EDIT_TOOLS)
        or any(hint in args_blob for hint in CODE_EDIT_HINTS)
    )
    return meta, stats, entries, sorted(skills_invoked), sorted(skills_mentioned)


def render_transcript(meta, stats, skills_invoked, skills_mentioned, entries) -> str:
    lines = [
        f"# Session {meta.get('id')}",
        f"- cwd: {meta.get('cwd')}",
        f"- started: {meta.get('started_at') or stats.get('first_ts')}",
        f"- skills invoked: {', '.join(skills_invoked) or '(none)'}",
        f"- skills mentioned only: {', '.join(sorted(set(skills_mentioned) - set(skills_invoked))) or '(none)'}",
        f"- stats: {stats['user_turns']} user turns, {stats['assistant_turns']} assistant turns, "
        f"{stats['tool_calls']} tool calls ({stats['repeated_tool_calls']} repeated), "
        f"{stats['error_outputs']} error-ish outputs, code edits: {stats['has_code_edits']}",
        "",
        "## Condensed transcript",
        "",
    ]
    shown = entries
    if len(entries) > MAX_TRANSCRIPT_ENTRIES:
        omitted = len(entries) - TRANSCRIPT_HEAD - TRANSCRIPT_TAIL
        shown = entries[:TRANSCRIPT_HEAD] + [("note", f"[... {omitted} entries omitted ...]")] + entries[-TRANSCRIPT_TAIL:]
    for role, text in shown:
        lines.append(f"[{role}] {text}")
        lines.append("")
    return "\n".join(lines)


def session_matches_repo(cwd, repo: Path) -> bool:
    """True when a session's recorded cwd belongs to this repo.

    Two ways to match:
    1. cwd is inside the repo root (same-machine sessions).
    2. cwd's trailing directory name equals the repo's name (worktrees,
       or sessions imported from another machine where the checkout
       path differs).
    Basename matching can over-match if two different projects share a
    directory name; acceptable for a report, and prefix matching alone
    misses every worktree session.
    """
    if not cwd:
        return False
    p = Path(cwd)
    try:
        if p.resolve().is_relative_to(repo):
            return True
    except OSError:
        pass  # cwd from another machine may not exist locally
    return p.name == repo.name or repo.name in p.parts


def main():
    args = parse_args()
    if args.repo:
        args.all_repos = False
    claude_home = Path(args.claude_home).expanduser()
    out_dir = Path(args.out).expanduser()
    transcripts_dir = out_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    repo = resolve_repo(args.repo)
    skills_dirs = args.skills_dir or [DEFAULT_SKILLS_DIR]
    skills = discover_skills(skills_dirs)
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    if not (claude_home / "projects").is_dir():
        print(f"error: Claude Code project history not found at {claude_home / 'projects'}", file=sys.stderr)
        sys.exit(1)

    claude_files = find_claude_session_files(claude_home, cutoff, args.include_subagents)
    scanned_count = len(claude_files)

    sessions = []
    in_repo_count = 0
    for mtime, path in claude_files:
        parsed = parse_claude_session(path, skills.keys(), args.include_subagents)
        if parsed is None:
            continue
        meta, stats, entries, skills_invoked, skills_mentioned = parsed
        if not args.all_repos and not session_matches_repo(meta.get("cwd"), repo):
            continue
        in_repo_count += 1
        if stats["assistant_turns"] < 1 or stats["tool_calls"] < 1:
            continue
        sessions.append({
            "harness": "claude",
            "meta": meta,
            "stats": stats,
            "skills_invoked": skills_invoked,
            "skills_mentioned": skills_mentioned,
            "file": str(path),
            "modified_at": mtime.isoformat(),
            "_entries": entries,
        })

    sessions.sort(key=lambda session: session["modified_at"], reverse=True)
    for session in sessions:
        session["_key"] = f"{session['harness']}:{session['meta']['id']}"

    # Sample: newest-first, prefer sessions with a real invocation, up to
    # --per-skill sessions per skill, then fill with no-invocation sessions.
    sampled_keys = set()
    per_skill_count = {name: 0 for name in skills}
    for s in sessions:
        if len(sampled_keys) >= args.max_sessions:
            break
        for name in s["skills_invoked"]:
            if per_skill_count.get(name, 0) < args.per_skill:
                per_skill_count[name] = per_skill_count.get(name, 0) + 1
                sampled_keys.add(s["_key"])
                break
    no_skill_taken = 0
    for s in sessions:
        if len(sampled_keys) >= args.max_sessions or no_skill_taken >= args.no_skill:
            break
        if not s["skills_invoked"] and s["_key"] not in sampled_keys:
            sampled_keys.add(s["_key"])
            no_skill_taken += 1

    for s in sessions:
        sid = s["meta"]["id"]
        s["sampled"] = s["_key"] in sampled_keys
        if s["sampled"]:
            tpath = transcripts_dir / f"{s['harness']}-{sid}.md"
            tpath.write_text(
                render_transcript(s["meta"], s["stats"], s["skills_invoked"], s["skills_mentioned"], s["_entries"])
            )
            s["transcript_path"] = str(tpath)
        del s["_entries"]
        del s["_key"]

    skill_usage = {name: {"invoked": 0, "mentioned": 0} for name in skills}
    for s in sessions:
        for name in s["skills_invoked"]:
            skill_usage[name]["invoked"] += 1
        for name in s["skills_mentioned"]:
            skill_usage[name]["mentioned"] += 1

    total_invoked = sum(len(s["skills_invoked"]) for s in sessions)
    total_mentioned_only = sum(
        len(set(s["skills_mentioned"]) - set(s["skills_invoked"])) for s in sessions
    )

    inventory = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "harness": "claude",
        "claude_home": str(claude_home),
        "repo": str(repo),
        "repo_name": repo.name,
        "all_repos": args.all_repos,
        "window_days": args.days,
        "skills_dirs": [str(Path(d).expanduser()) for d in skills_dirs],
        "skills": sorted(skills.values(), key=lambda x: x["name"]),
        "skill_usage": skill_usage,
        "stats": {
            "session_files_in_window": scanned_count,
            "session_records_in_window": scanned_count,
            "sessions_in_repo": in_repo_count,
            "sessions_considered": len(sessions),
            "sessions_sampled": len(sampled_keys),
            "skills_found": len(skills),
            "skills_used": sum(1 for v in skill_usage.values() if v["invoked"] > 0),
            "skills_invoked_total": total_invoked,
            "skills_mentioned_only_total": total_mentioned_only,
        },
        "sessions": sessions,
    }
    (out_dir / "inventory.json").write_text(json.dumps(inventory, indent=2))

    st = inventory["stats"]
    print(f"repo scope:        {'all repos' if args.all_repos else repo}")
    print(f"skills found:      {st['skills_found']} ({st['skills_used']} invoked in window)")
    print(f"sessions in window: {st['session_records_in_window']} records, {st['sessions_considered']} scoreable")
    print(f"sessions sampled:  {st['sessions_sampled']} -> {transcripts_dir}")
    print(f"skills invoked in window: {st['skills_invoked_total']}; mentioned only: {st['skills_mentioned_only_total']}")
    print(f"inventory:         {out_dir / 'inventory.json'}")


if __name__ == "__main__":
    main()
