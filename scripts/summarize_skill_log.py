#!/usr/bin/env python3
"""Summarize the skill-level failure telemetry log.

Reads `.skill_telemetry/failures.jsonl` and produces a markdown report:
- Top rules by frequency across all builds.
- Rules that fire across ≥N distinct decks (skill-level-fix candidates).
- Per-workspace totals (which decks are the noisiest).
- Recency: last 10 builds' summary lines.

This is how we mine the log for patterns worth promoting into guardrails
or preflight rules. Recurring issues → doc/code fix; one-off issues →
workspace-level fix.

Usage:
    python3 scripts/summarize_skill_log.py
    python3 scripts/summarize_skill_log.py --min-decks 3 --top 15
    python3 scripts/summarize_skill_log.py --output docs/skill_trends.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _default_log() -> Path:
    return Path(__file__).resolve().parent.parent / ".skill_telemetry" / "failures.jsonl"


def _load(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with log_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _format_report(
    rows: list[dict[str, Any]],
    *,
    top_n: int,
    min_decks: int,
) -> str:
    if not rows:
        return "# Skill Telemetry Report\n\nNo log entries yet.\n"

    out: list[str] = ["# Skill Telemetry Report", ""]

    builds = _distinct_builds(rows)
    workspaces = {r.get("workspace") for r in rows if r.get("workspace")}
    first_ts = min((r.get("ts", "") for r in rows), default="")
    last_ts = max((r.get("ts", "") for r in rows), default="")

    out.append(f"- Total log rows: **{len(rows)}**")
    out.append(f"- Distinct builds: **{len(builds)}**")
    out.append(f"- Distinct workspaces: **{len(workspaces)}**")
    out.append(f"- First entry: `{first_ts}`  Last entry: `{last_ts}`")
    out.append("")

    # --- rule frequency ---
    rule_counter: Counter[tuple[str, str]] = Counter()
    rule_deck_sets: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in rows:
        rule = r.get("rule", "unknown")
        phase = r.get("phase", "unknown")
        if rule == "counts" or rule == "convergence":
            continue  # skip pure metadata rows
        key = (phase, rule)
        rule_counter[key] += 1
        if r.get("workspace"):
            rule_deck_sets[key].add(r["workspace"])

    out.append(f"## Top {top_n} rules by frequency")
    out.append("")
    out.append("| Phase | Rule | Fires | Across decks |")
    out.append("|---|---|---:|---:|")
    for (phase, rule), count in rule_counter.most_common(top_n):
        decks = len(rule_deck_sets[(phase, rule)])
        out.append(f"| {phase} | `{rule}` | {count} | {decks} |")
    out.append("")

    # --- systemic rules: fire across ≥ min_decks distinct workspaces ---
    systemic = [
        (key, count, len(rule_deck_sets[key]))
        for key, count in rule_counter.items()
        if len(rule_deck_sets[key]) >= min_decks
    ]
    systemic.sort(key=lambda t: (-t[2], -t[1]))

    out.append(f"## Skill-level fix candidates (rules firing across ≥{min_decks} decks)")
    out.append("")
    if not systemic:
        out.append(f"_No rule fires across ≥{min_decks} decks yet._")
        out.append("")
    else:
        out.append(
            "These rules keep recurring across different workspaces. "
            "Consider promoting each from per-slide nudge to deck-level "
            "warning, or addressing the root cause at the renderer / "
            "schema / guardrail level."
        )
        out.append("")
        out.append("| Phase | Rule | Across decks | Total fires |")
        out.append("|---|---|---:|---:|")
        for (phase, rule), count, deck_count in systemic[:top_n]:
            out.append(f"| {phase} | `{rule}` | {deck_count} | {count} |")
        out.append("")

    # --- per-workspace totals ---
    ws_counter: Counter[str] = Counter()
    for r in rows:
        w = r.get("workspace")
        if w:
            ws_counter[w] += 1
    out.append("## Noisiest workspaces (by total telemetry rows)")
    out.append("")
    out.append("| Workspace | Rows |")
    out.append("|---|---:|")
    for ws, count in ws_counter.most_common(10):
        # Show only the last 2 path components so the table stays readable.
        short = "/".join(ws.split("/")[-2:])
        out.append(f"| `{short}` | {count} |")
    out.append("")

    # --- recency: last N builds by qa_summary row ---
    summaries = [r for r in rows if r.get("phase") == "qa_summary"]
    summaries.sort(key=lambda r: r.get("ts", ""))
    out.append("## Last 10 builds (qa_summary rows)")
    out.append("")
    out.append("| Timestamp | Workspace | Overflow | Overlap | Geom err | Geom warn |")
    out.append("|---|---|---:|---:|---:|---:|")
    for r in summaries[-10:]:
        meta = r.get("metadata") or {}
        short = "/".join(str(r.get("workspace", "")).split("/")[-2:])
        out.append(
            f"| `{r.get('ts', '')[:19]}` | `{short}` | "
            f"{meta.get('overflow_count', '-')} | "
            f"{meta.get('overlap_count', '-')} | "
            f"{meta.get('geometry_error_count', '-')} | "
            f"{meta.get('geometry_warning_count', '-')} |"
        )
    out.append("")

    return "\n".join(out) + "\n"


def _distinct_builds(rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
    """Group by (workspace, minute-granularity timestamp) as build signature."""
    builds: set[tuple[str, str]] = set()
    for r in rows:
        ws = r.get("workspace", "")
        ts = r.get("ts", "")
        if ws and ts:
            minute = ts[:16]  # YYYY-MM-DDTHH:MM
            builds.add((ws, minute))
    return builds


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize skill-level failure telemetry.")
    parser.add_argument("--log", help="Path to failures.jsonl (default: auto)")
    parser.add_argument("--top", type=int, default=15, help="Top N rules to report")
    parser.add_argument(
        "--min-decks",
        type=int,
        default=3,
        help="Rule must fire across this many distinct decks to be a skill-fix candidate",
    )
    parser.add_argument("--output", help="Write report to file (default: stdout)")
    args = parser.parse_args()

    log_path = Path(args.log).expanduser().resolve() if args.log else _default_log()
    rows = _load(log_path)
    report = _format_report(rows, top_n=args.top, min_decks=args.min_decks)

    if args.output:
        out_path = Path(args.output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"Wrote {out_path}", file=sys.stderr)
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
