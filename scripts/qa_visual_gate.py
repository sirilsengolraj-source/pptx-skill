#!/usr/bin/env python3
"""Strict QA gate for reliable/hybrid PPTX visual quality."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or f"Command failed: {' '.join(cmd)}")


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _issue_summary(issues_payload: dict[str, Any]) -> tuple[int, int]:
    overflow_count = 0
    overlap_count = 0
    for slide_shapes in issues_payload.values():
        if not isinstance(slide_shapes, dict):
            continue
        for shape_data in slide_shapes.values():
            if not isinstance(shape_data, dict):
                continue
            if "overflow" in shape_data:
                overflow_count += 1
            if "overlap" in shape_data:
                overlap_count += 1
    return overflow_count, overlap_count


def _overflow_inches(shape_data: dict[str, Any]) -> float | None:
    overflow = shape_data.get("overflow")
    if overflow is None:
        return None
    if isinstance(overflow, (int, float)):
        return float(overflow)
    if isinstance(overflow, str):
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", overflow)
        return float(match.group(1)) if match else None
    if not isinstance(overflow, dict):
        return None
    for key in (
        "overflow_inches",
        "overflow_in",
        "overflow_amount_inches",
        "overflow_amount_in",
        "excess_in",
        "delta_in",
        "inches",
    ):
        value = overflow.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            match = re.search(r"([0-9]+(?:\.[0-9]+)?)", value)
            if match:
                return float(match.group(1))
    return None


def _major_overflow_count(issues_payload: dict[str, Any], threshold: float) -> tuple[int, int]:
    major = 0
    unknown = 0
    for slide_shapes in issues_payload.values():
        if not isinstance(slide_shapes, dict):
            continue
        for shape_data in slide_shapes.values():
            if not isinstance(shape_data, dict) or "overflow" not in shape_data:
                continue
            amount = _overflow_inches(shape_data)
            if amount is None:
                unknown += 1
                continue
            if amount > threshold:
                major += 1
    return major, unknown


def _metadata_sidecars(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    return sorted(root.rglob("*.metadata.json"))


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append({k: str(v or "").strip() for k, v in row.items()})
    return rows


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visual QA gate for PPTX outputs")
    parser.add_argument("--input", required=True, help="Input .pptx file")
    parser.add_argument("--mode", default="hybrid", choices=["reliable", "hybrid"], help="Render mode policy")
    parser.add_argument("--major-overflow-threshold", type=float, default=0.05)
    parser.add_argument("--assets-root", help="Directory to scan for external asset metadata sidecars")
    parser.add_argument(
        "--attribution-file",
        help="Attribution CSV path (default: <input_dir>/assets/attribution.csv)",
    )
    parser.add_argument("--outdir", help="Artifact output directory")
    parser.add_argument("--report", help="Write machine-readable report JSON")
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument("--keep-artifacts", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _args()
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    cleanup = False
    if args.outdir:
        outdir = Path(args.outdir).expanduser().resolve()
    else:
        outdir = Path(tempfile.mkdtemp(prefix="pptx-visual-gate-")).resolve()
        cleanup = not args.keep_artifacts and not args.report
    outdir.mkdir(parents=True, exist_ok=True)

    base = Path(__file__).resolve().parent
    py = sys.executable

    issues_json = outdir / "issues.json"
    outline_md = outdir / "outline.md"
    render_dir = outdir / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    report_path = Path(args.report).expanduser().resolve() if args.report else outdir / "qa_visual_gate.json"

    _run([py, str(base / "inventory.py"), str(input_path), str(issues_json), "--issues-only"])
    _run(
        [
            py,
            str(base / "extract_outline.py"),
            "--input",
            str(input_path),
            "--format",
            "markdown",
            "--output",
            str(outline_md),
        ]
    )
    if not args.skip_render:
        _run(
            [
                py,
                str(base / "render_slides.py"),
                "--input",
                str(input_path),
                "--outdir",
                str(render_dir),
                "--dpi",
                "180",
                "--format",
                "jpeg",
            ]
        )

    issues_payload = _load_json(issues_json)
    overflow_count, overlap_count = _issue_summary(issues_payload)
    major_overflow, unknown_overflow = _major_overflow_count(
        issues_payload,
        threshold=args.major_overflow_threshold,
    )

    assets_root = (
        Path(args.assets_root).expanduser().resolve()
        if args.assets_root
        else input_path.parent
    )
    sidecars = _metadata_sidecars(assets_root)
    attribution_file = (
        Path(args.attribution_file).expanduser().resolve()
        if args.attribution_file
        else (input_path.parent / "assets" / "attribution.csv").resolve()
    )
    attribution_rows = _read_csv_rows(attribution_file)

    failed = False
    failures: list[str] = []

    if args.mode == "reliable":
        if overflow_count > 0:
            failed = True
            failures.append("Reliable mode requires zero overflow issues.")
    else:
        if major_overflow > 0:
            failed = True
            failures.append(
                f"Hybrid mode found major overflow > {args.major_overflow_threshold:.2f}in."
            )
        if unknown_overflow > 0:
            failed = True
            failures.append("Hybrid mode found overflow entries without measurable inches.")

    if overlap_count > 0:
        failed = True
        failures.append("Overlap issues detected.")

    if sidecars and not attribution_rows:
        failed = True
        failures.append(
            "External asset metadata exists but attribution.csv is missing or empty."
        )

    payload = {
        "input": str(input_path),
        "mode": args.mode,
        "overflow_count": overflow_count,
        "overlap_count": overlap_count,
        "major_overflow_count": major_overflow,
        "unknown_overflow_count": unknown_overflow,
        "major_overflow_threshold_in": args.major_overflow_threshold,
        "assets_root": str(assets_root),
        "external_metadata_count": len(sidecars),
        "attribution_file": str(attribution_file),
        "attribution_rows": len(attribution_rows),
        "failed": failed,
        "failures": failures,
        "artifacts": str(outdir),
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"QA artifacts: {outdir}")
    print(f"Mode: {args.mode}")
    print(f"Overflow: {overflow_count}")
    print(f"Overlap: {overlap_count}")
    print(f"Major overflow: {major_overflow}")
    print(f"Unknown overflow: {unknown_overflow}")
    print(f"External metadata files: {len(sidecars)}")
    print(f"Attribution rows: {len(attribution_rows)}")
    print(f"QA report: {report_path}")

    if cleanup:
        shutil.rmtree(outdir, ignore_errors=True)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
