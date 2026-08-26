#!/usr/bin/env python3
"""Render a skill-checkup report.json into one shareable HTML report.

Output (next to report.json):
  report.html - scorecard, findings, and suggested skill edits in a single
                self-contained page. Diffs render as plain <pre> blocks with
                a "show more" toggle for long ones — no external JS bundle.

Python 3.9+, stdlib only.
"""

import html
import json
import sys
from pathlib import Path

GRADES = [
    (0.97, "A+"), (0.93, "A"), (0.90, "A-"),
    (0.87, "B+"), (0.83, "B"), (0.80, "B-"),
    (0.77, "C+"), (0.73, "C"), (0.70, "C-"),
    (0.60, "D"), (0.0, "F"),
]

# Collapsed height of a diff before the "show more" toggle takes over.
DIFF_CLAMP_PX = 320


def grade_for(score: float) -> str:
    for threshold, letter in GRADES:
        if score >= threshold:
            return letter
    return "F"


def pct(score) -> int:
    return round(float(score) * 100)


def esc(v) -> str:
    value = v if v is not None else ""
    return html.escape(str(value))


def render_diff(diff_text: str, proposed_path: str = "") -> str:
    if not diff_text:
        return ""
    filename = Path(proposed_path).name if proposed_path else "SKILL.md"
    return (
        '<div class="diff-wrap" data-collapsed="true">'
        f'<div class="diff-view"><pre class="diff-fallback" title="{esc(filename)}">{esc(diff_text)}</pre></div>'
        '<button class="diff-toggle" type="button" hidden>show more</button>'
        "</div>"
    )


# Design tokens: white ground with a dot grid, monospace, square corners,
# lowercase labels, uppercase wide-tracked meta bars.
PAGE_CSS = """
* { box-sizing: border-box; }
body {
  --fg: #1a1522; --muted: #5d5966; --muted-2: #918d9a; --accent: #2a1eff;
  --line: rgba(13, 10, 61, 0.16); --line-soft: rgba(13, 10, 61, 0.07);
  --bg-panel: #f6f5fb;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: radial-gradient(circle at 1px 1px, var(--line-soft) 1px, transparent 0) 0 0 / 22px 22px, #fff;
  color: var(--fg); max-width: 900px; margin: 0 auto; padding: 48px 24px;
  line-height: 1.65; font-size: 13px;
}
::selection { background: var(--accent); color: #fff; }
h1 { font-weight: 500; letter-spacing: -2px; font-size: 34px; margin: 4px 0 0; }
h2 { font-weight: 500; letter-spacing: -1px; font-size: 20px; margin: 40px 0 8px; }
p { color: var(--muted); font-weight: 500; }
a { color: var(--accent); }
code { background: var(--bg-panel); border: 1px solid var(--line-soft); padding: 1px 5px; }
li { margin-bottom: 10px; }
.tag { font-size: 11px; color: var(--accent); text-transform: lowercase; }
.tag::before { content: "# "; }
.muted { color: var(--muted-2); font-size: 12px; }
.row { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.title-row { margin-top: 4px; }
.title-row h1 { margin: 0; }
.scorecard { display: flex; align-items: center; gap: 48px; border: 1px solid var(--line);
  background: #fff; padding: 26px 28px; margin-top: 20px; }
.grade-col { text-align: center; flex: none; width: 170px; }
.grade { font-size: 96px; font-weight: 600; line-height: 1; letter-spacing: -5px; color: var(--accent); }
.grade-label { font-size: 11px; color: var(--muted-2); margin-top: 8px; text-transform: uppercase; letter-spacing: 0.14em; }
.bars { flex: 1; display: flex; flex-direction: column; gap: 20px; min-width: 0; }
.bar-head { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 7px; font-weight: 500; }
.bar-name { text-transform: lowercase; }
.bar-val { font-weight: 600; font-variant-numeric: tabular-nums; }
.bar-track { height: 8px; background: var(--line-soft); box-shadow: inset 0 0 0 1px var(--line); }
.bar-fill { height: 100%; background: var(--accent); }
.stats { display: grid; grid-template-columns: repeat(3, 1fr); border: 1px solid var(--line);
  border-top: none; background: var(--bg-panel); }
.stat { padding: 16px 24px 14px; border-left: 1px solid var(--line); }
.stat:first-child { border-left: none; }
.stat .num { font-size: 34px; font-weight: 600; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
.stat .lbl { font-size: 12px; color: var(--muted); margin-top: 2px; text-transform: lowercase; }
.diff-wrap { margin: 10px 0 4px; }
.diff-view { display: grid; gap: 10px; max-width: 100%; }
.diff-view > * { min-width: 0; }
.diff-fallback { background: var(--bg-panel); border: 1px solid var(--line); padding: 13px 16px;
  color: var(--muted); font-size: 12px; line-height: 1.7; overflow-x: auto; margin: 0; white-space: pre; }
.diff-wrap[data-overflowing="true"][data-collapsed="true"] .diff-view {
  max-height: __CLAMP__px; overflow: hidden;
  -webkit-mask-image: linear-gradient(#000 calc(100% - 72px), transparent);
  mask-image: linear-gradient(#000 calc(100% - 72px), transparent);
}
.diff-toggle { font-family: inherit; font-size: 10px; font-weight: 600; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--accent); background: #fff;
  border: 1px solid var(--line); padding: 5px 10px; margin-top: 6px; cursor: pointer; }
.diff-toggle:hover { border-color: var(--accent); }
"""


def render_page(r) -> str:
    scores = r["scores"]
    stats = r.get("stats", {})
    grade = r.get("grade") or grade_for(scores["overall"])

    bars = "".join(
        f'<div class="bar-row"><div class="bar-head"><span class="bar-name">{esc(name)}</span>'
        f'<span class="bar-val">{pct(val)}</span></div>'
        f'<div class="bar-track"><div class="bar-fill" style="width:{pct(val)}%"></div></div></div>'
        for name, val in [
            ("Efficiency", scores.get("efficiency", 0)),
            ("Code Quality", scores.get("code_quality", 0)),
            ("Skill Coverage", scores.get("skill_coverage", 0)),
        ]
    )
    stat_cells = "".join(
        f'<div class="stat"><div class="num">{esc(value)}</div><div class="lbl">{esc(label)}</div></div>'
        for value, label in [
            (stats.get("sessions_analyzed", 0), "conversations scored"),
            (stats.get("skills_found", 0), "skills installed"),
            (stats.get("skills_used", 0), "skills invoked"),
        ]
    )
    findings = "".join(f"<li>{esc(finding)}</li>" for finding in r.get("top_findings", []))
    suggestions = "".join(
        f"""<li><b><code>{esc(s.get('skill'))}</code></b> — {esc(s.get('change'))}
        {('<div class="muted">Evidence: ' + esc(s['evidence']) + '</div>') if s.get('evidence') else ''}
        {render_diff(s.get('diff', ''), s.get('proposed_path', ''))}</li>"""
        for s in r.get("suggestions", [])
    ) or "<li>No skill change cleared the bar for this window.</li>"

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{esc(r.get('title', 'Skill Checkup Report'))}</title>
<style>{PAGE_CSS.replace('__CLAMP__', str(DIFF_CLAMP_PX))}</style></head><body>
<div class="tag">skill-checkup</div>
<div class="row title-row">
  <h1>{esc(r.get('title', 'Skill Checkup Report'))}</h1>
</div>
<p class="muted">Generated {esc(r.get('generated_at', ''))} &middot; harness: {esc(r.get('harness', 'claude'))} &middot; all analysis ran locally</p>
<div class="scorecard">
  <div class="grade-col"><div class="grade">{esc(grade)}</div>
    <div class="grade-label">overall {pct(scores['overall'])}</div></div>
  <div class="bars">{bars}</div>
</div>
<div class="stats">{stat_cells}</div>
<h2>Findings</h2><ul>{findings}</ul>
<h2>Suggested skill changes</h2><ol>{suggestions}</ol>
<script>{page_script()}</script>
</body></html>"""


def page_script() -> str:
    """Collapsible long diffs — no canvas/share-image, no external bundle."""
    script = r"""
(function () {
  var CLAMP = __CLAMP__;
  function syncToggle(wrap, button) {
    var view = wrap.querySelector('.diff-view');
    if (!view) return;
    var overflowing = view.scrollHeight > CLAMP + 24;
    wrap.dataset.overflowing = overflowing ? 'true' : 'false';
    button.hidden = !overflowing;
  }
  document.querySelectorAll('.diff-wrap').forEach(function (wrap) {
    var button = wrap.querySelector('.diff-toggle');
    var view = wrap.querySelector('.diff-view');
    if (!button || !view) return;
    button.addEventListener('click', function () {
      var collapsed = wrap.dataset.collapsed === 'true';
      wrap.dataset.collapsed = collapsed ? 'false' : 'true';
      button.textContent = collapsed ? 'show less' : 'show more';
      if (!collapsed) wrap.scrollIntoView({ block: 'nearest' });
    });
    syncToggle(wrap, button);
    if (window.ResizeObserver) {
      new ResizeObserver(function () { syncToggle(wrap, button); }).observe(view);
    }
  });
})();
"""
    return script.replace("__CLAMP__", str(DIFF_CLAMP_PX))


def main():
    report_path = Path(
        sys.argv[1] if len(sys.argv) > 1 else "./skill-checkup-report/report.json"
    ).expanduser()
    if not report_path.exists():
        print(f"error: {report_path} not found", file=sys.stderr)
        sys.exit(1)
    r = json.loads(report_path.read_text())
    r.setdefault("grade", grade_for(r["scores"]["overall"]))

    out_path = report_path.parent / "report.html"
    out_path.write_text(render_page(r))
    print(f"report: {out_path}")


if __name__ == "__main__":
    main()
