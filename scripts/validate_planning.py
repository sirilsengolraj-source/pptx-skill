#!/usr/bin/env python3
"""Validate workspace planning files before rendering a deck."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _issue(path: str, severity: str, message: str) -> dict[str, str]:
    return {"path": path, "severity": severity, "message": message}


def _load_json(path: Path) -> tuple[Any | None, list[dict[str, str]]]:
    if not path.exists():
        return None, []
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [_issue(str(path), "error", f"malformed JSON: {exc}")]


def _validate_content_plan(plan: Any, evidence_ids: set[str]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if plan is None:
        return issues
    if not isinstance(plan, dict):
        return [_issue("content_plan.json", "error", "root must be an object")]

    thesis = str(plan.get("thesis") or "").strip()
    if not thesis:
        issues.append(_issue("content_plan.thesis", "warning", "missing thesis"))

    slide_plan = plan.get("slide_plan")
    if not isinstance(slide_plan, list):
        issues.append(_issue("content_plan.slide_plan", "error", "must be a list"))
        return issues

    seen_slide_ids: set[str] = set()
    for idx, slide in enumerate(slide_plan):
        base = f"content_plan.slide_plan[{idx}]"
        if not isinstance(slide, dict):
            issues.append(_issue(base, "error", "slide plan item must be an object"))
            continue
        slide_id = str(slide.get("slide_id") or "").strip()
        if not slide_id:
            issues.append(_issue(f"{base}.slide_id", "error", "missing slide_id"))
        elif slide_id in seen_slide_ids:
            issues.append(_issue(f"{base}.slide_id", "error", f"duplicate slide_id {slide_id!r}"))
        else:
            seen_slide_ids.add(slide_id)
        if not str(slide.get("message") or "").strip() and str(slide.get("role") or "") != "title":
            issues.append(_issue(f"{base}.message", "warning", "content slide has no message"))
        if not str(slide.get("visual_strategy") or "").strip():
            issues.append(_issue(f"{base}.visual_strategy", "warning", "missing visual strategy"))
        needs = slide.get("evidence_needs") or []
        if not isinstance(needs, list):
            issues.append(_issue(f"{base}.evidence_needs", "error", "must be a list"))
            continue
        for ev_id in needs:
            ev = str(ev_id)
            if evidence_ids and ev not in evidence_ids:
                issues.append(_issue(f"{base}.evidence_needs", "warning", f"unknown evidence id {ev!r}"))
    return issues


def _validate_evidence_plan(plan: Any) -> tuple[set[str], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    ids: set[str] = set()
    if plan is None:
        return ids, issues
    if not isinstance(plan, dict):
        return ids, [_issue("evidence_plan.json", "error", "root must be an object")]

    items = plan.get("items")
    if not isinstance(items, list):
        return ids, [_issue("evidence_plan.items", "error", "must be a list")]

    for idx, item in enumerate(items):
        base = f"evidence_plan.items[{idx}]"
        if not isinstance(item, dict):
            issues.append(_issue(base, "error", "evidence item must be an object"))
            continue
        ev_id = str(item.get("id") or "").strip()
        if not ev_id:
            issues.append(_issue(f"{base}.id", "error", "missing id"))
        elif ev_id in ids:
            issues.append(_issue(f"{base}.id", "error", f"duplicate id {ev_id!r}"))
        else:
            ids.add(ev_id)
        if not str(item.get("claim") or "").strip():
            issues.append(_issue(f"{base}.claim", "warning", "missing claim"))
        visual_use = str(item.get("visual_use") or "").strip()
        source_url = str(item.get("source_url") or "").strip()
        source_note = str(item.get("source_note") or "").strip()
        if visual_use in {"kpi", "chart", "table", "footer-source"} and not (source_url or source_note):
            issues.append(
                _issue(
                    f"{base}.source_url",
                    "warning",
                    f"{visual_use} evidence should include source_url or source_note",
                )
            )
    return ids, issues


def _validate_design_brief(brief: Any) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if brief is None:
        return issues
    if not isinstance(brief, dict):
        return [_issue("design_brief.json", "error", "root must be an object")]

    if not str(brief.get("format_promise") or "").strip():
        issues.append(_issue("design_brief.format_promise", "warning", "missing format promise"))

    structure = brief.get("structure_strategy")
    if not isinstance(structure, dict):
        issues.append(_issue("design_brief.structure_strategy", "warning", "missing structure strategy object"))
    elif not str(structure.get("container_policy") or "").strip():
        issues.append(_issue("design_brief.structure_strategy.container_policy", "warning", "missing container/card policy"))

    title_page = brief.get("title_page_concept")
    if not isinstance(title_page, dict):
        issues.append(_issue("design_brief.title_page_concept", "warning", "missing title page concept object"))
    elif not str(title_page.get("chosen_archetype") or "").strip():
        issues.append(_issue("design_brief.title_page_concept.chosen_archetype", "warning", "missing cover archetype"))
    return issues


def validate(workspace: Path) -> dict[str, Any]:
    content_plan, content_load_issues = _load_json(workspace / "content_plan.json")
    design_brief, design_load_issues = _load_json(workspace / "design_brief.json")
    evidence_plan, evidence_load_issues = _load_json(workspace / "evidence_plan.json")
    evidence_ids, evidence_issues = _validate_evidence_plan(evidence_plan)
    content_issues = _validate_content_plan(content_plan, evidence_ids)
    design_issues = _validate_design_brief(design_brief)
    issues = [
        *content_load_issues,
        *design_load_issues,
        *evidence_load_issues,
        *evidence_issues,
        *content_issues,
        *design_issues,
    ]
    return {
        "issues": issues,
        "error_count": sum(1 for issue in issues if issue["severity"] == "error"),
        "warning_count": sum(1 for issue in issues if issue["severity"] == "warning"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate content_plan.json, design_brief.json, and evidence_plan.json.")
    parser.add_argument("--workspace", required=True, help="Deck workspace directory")
    parser.add_argument("--report", help="Optional JSON report path")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    payload = validate(workspace)
    if args.report:
        report = Path(args.report).expanduser().resolve()
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if payload["error_count"]:
        return 2
    if payload["warning_count"]:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
