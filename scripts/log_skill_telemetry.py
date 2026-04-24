#!/usr/bin/env python3
"""Append per-build failure telemetry to a skill-level JSONL log.

Every build run produces preflight issues, QA violations, iterate_deck
outcomes, and narration-verifier diffs. Most of them are transient and
workspace-specific. A subset represents *repeating patterns* worth
fixing at the skill level (a rule that fires across many decks is a
guardrail candidate). This script captures them in a durable log that
`summarize_skill_log.py` can mine later.

One JSONL row per issue. Non-blocking — failures here never break the
build.

Usage (usually called from build_workspace.py):
    python3 scripts/log_skill_telemetry.py \\
        --workspace decks/my-deck \\
        --qa-report decks/my-deck/build/qa/report.json \\
        --preflight-json /tmp/preflight-out.json \\
        --iterate-report decks/my-deck/build/iterate.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Iterable


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _row(
    *,
    workspace: str,
    phase: str,
    rule: str,
    severity: str,
    slide_index: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ts": _iso_now(),
        "workspace": workspace,
        "phase": phase,
        "rule": rule,
        "severity": severity,
        "slide_index": slide_index,
        "metadata": metadata or {},
    }


def _rows_from_preflight(
    path: Path, workspace: str
) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    for issue in payload.get("issues") or []:
        yield _row(
            workspace=workspace,
            phase="preflight",
            rule=str(issue.get("rule", "unknown")),
            severity=str(issue.get("severity", "info")),
            slide_index=issue.get("slide_index")
            if isinstance(issue.get("slide_index"), int) and issue.get("slide_index") >= 0
            else None,
        )


def _rows_from_qa(path: Path, workspace: str) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    # Surface scalar counts first so summarize can tell if a build was clean.
    yield _row(
        workspace=workspace,
        phase="qa_summary",
        rule="counts",
        severity="info",
        metadata={
            "overflow_count": payload.get("overflow_count", 0),
            "overlap_count": payload.get("overlap_count", 0),
            "geometry_error_count": payload.get("geometry_error_count", 0),
            "geometry_warning_count": payload.get("geometry_warning_count", 0),
            "visual_warning_count": payload.get("visual_warning_count", 0),
            "design_warning_count": payload.get("design_warning_count", 0),
        },
    )
    for v in payload.get("geometry_violations") or []:
        yield _row(
            workspace=workspace,
            phase="qa_geometry",
            rule=str(v.get("type", "unknown")),
            severity=str(v.get("severity", "warning")),
            slide_index=v.get("slide_index"),
            metadata={
                "delta_inches": v.get("delta_inches"),
                "slide_type": v.get("slide_type"),
            },
        )


def _rows_from_iterate(
    path: Path, workspace: str
) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    yield _row(
        workspace=workspace,
        phase="iterate",
        rule="convergence",
        severity="info",
        metadata={
            "converged": payload.get("converged"),
            "loops_executed": payload.get("loops_executed"),
        },
    )


def _rows_from_verify_narration(
    text: str, workspace: str
) -> Iterable[dict[str, Any]]:
    # verify_narration emits stderr lines like "  slide 1 :: asset_missing :: ..."
    for line in (text or "").splitlines():
        line = line.strip()
        if "::" not in line or "asset_missing" not in line and "asset_plan_missing" not in line:
            continue
        parts = [p.strip() for p in line.split("::")]
        if len(parts) < 3:
            continue
        loc = parts[0]
        rule = parts[1]
        slide_index: int | None = None
        if loc.startswith("slide "):
            try:
                slide_index = int(loc.split()[-1])
            except ValueError:
                slide_index = None
        yield _row(
            workspace=workspace,
            phase="verify_narration",
            rule=rule,
            severity="warning",
            slide_index=slide_index,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Append build telemetry to skill log.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--preflight-json", help="Path to preflight stdout capture")
    parser.add_argument("--qa-report", help="Path to qa_gate report.json")
    parser.add_argument("--iterate-report", help="Path to iterate_deck report")
    parser.add_argument("--verify-narration-log", help="Path to verify_narration stderr capture")
    parser.add_argument(
        "--log",
        help="Log file path (default: <skill>/.skill_telemetry/failures.jsonl)",
    )
    args = parser.parse_args()

    if args.log:
        log_path = Path(args.log).expanduser().resolve()
    else:
        log_path = (
            Path(__file__).resolve().parent.parent
            / ".skill_telemetry"
            / "failures.jsonl"
        )
    log_path.parent.mkdir(parents=True, exist_ok=True)

    workspace = str(Path(args.workspace).expanduser().resolve())

    rows: list[dict[str, Any]] = []
    if args.preflight_json:
        rows.extend(_rows_from_preflight(Path(args.preflight_json), workspace))
    if args.qa_report:
        rows.extend(_rows_from_qa(Path(args.qa_report), workspace))
    if args.iterate_report:
        rows.extend(_rows_from_iterate(Path(args.iterate_report), workspace))
    if args.verify_narration_log:
        try:
            text = Path(args.verify_narration_log).read_text(encoding="utf-8")
        except OSError:
            text = ""
        rows.extend(_rows_from_verify_narration(text, workspace))

    if not rows:
        return 0
    with log_path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[log_skill_telemetry] non-blocking error: {exc}", file=sys.stderr)
        raise SystemExit(0)
