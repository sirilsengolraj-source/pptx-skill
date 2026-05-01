#!/usr/bin/env python3
"""Iterative PPTX quality loop: QA -> fix -> QA."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return result.returncode, result.stdout


def _load_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run iterative QA/fix loop for PPTX.")
    parser.add_argument("--input", required=True, help="Input .pptx file")
    parser.add_argument("--output", help="Output .pptx file (default: overwrite input)")
    parser.add_argument(
        "--style-preset",
        default="executive-clinical",
        help="Style preset for geometry and text-fit rules",
    )
    parser.add_argument(
        "--max-loops",
        type=int,
        default=3,
        help="Maximum QA/fix loops (default: 3)",
    )
    parser.add_argument(
        "--outdir",
        help="Directory for per-loop reports (default: ephemeral temp dir)",
    )
    parser.add_argument(
        "--max-font-families",
        type=int,
        default=3,
        help="Maximum allowed distinct font families",
    )
    parser.add_argument("--max-density", type=float, help="Override density threshold")
    parser.add_argument("--max-empty-ratio", type=float, help="Override empty-ratio threshold")
    parser.add_argument(
        "--skip-render",
        action="store_true",
        help="Skip rendering slides during QA on every loop (including final loop)",
    )
    parser.add_argument(
        "--always-render",
        action="store_true",
        help=(
            "Run full QA (including soffice render) on every loop. "
            "Restores pre-speed-optimization behavior. Without this flag, "
            "intermediate loops skip render and only the final loop renders."
        ),
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help=(
            "Convenience alias for render-free iteration (equivalent to "
            "--max-loops 3 --skip-render). Useful for quick drafts."
        ),
    )
    parser.add_argument(
        "--allow-issues",
        action="store_true",
        help="Allow overflow/overlap issues during QA (not recommended)",
    )
    parser.add_argument(
        "--report",
        help="Optional path to final orchestrator report JSON",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep loop artifact directory when --outdir is not provided",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()

    # --fast is a convenience alias: render-free iteration with bounded loops.
    # Only apply if user did not override the relevant flags explicitly.
    if args.fast:
        args.skip_render = True
        # Only clamp max-loops if the user left it at the default of 3.
        if args.max_loops > 3:
            args.max_loops = 3

    if args.skip_render and args.always_render:
        print(
            "Warning: --always-render overrides --skip-render; final loop will render.",
            file=sys.stderr,
        )

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")

    output_path = Path(args.output).expanduser().resolve() if args.output else input_path
    if input_path != output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(input_path), str(output_path))

    persist_artifacts = bool(args.outdir or args.keep_artifacts or args.report)
    if args.outdir:
        outdir = Path(args.outdir).expanduser().resolve()
    else:
        outdir = Path(tempfile.mkdtemp(prefix="pptx-iterations-")).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    py = sys.executable
    base = Path(__file__).resolve().parent
    loops: list[dict[str, Any]] = []
    converged = False
    prev_density_count: int | None = None

    total_loops = max(1, args.max_loops)
    for loop in range(1, total_loops + 1):
        loop_dir = outdir / f"loop-{loop}"
        loop_dir.mkdir(parents=True, exist_ok=True)
        qa_report = loop_dir / "qa_report.json"
        fit_report = loop_dir / "text_fit_report.json"

        # Decide whether to render for this specific loop.
        # Defaults:
        #   - --skip-render       -> skip render on every loop.
        #   - --always-render     -> render on every loop (pre-speed behavior).
        #   - (neither flag set)  -> skip render on loops 1..N-1, render only on final loop.
        is_final_loop = loop == total_loops
        if args.skip_render:
            loop_skip_render = True
        elif args.always_render:
            loop_skip_render = False
        else:
            loop_skip_render = not is_final_loop

        qa_cmd = [
            py,
            str(base / "qa_gate.py"),
            "--input",
            str(output_path),
            "--outdir",
            str(loop_dir / "qa"),
            "--report",
            str(qa_report),
            "--style-preset",
            args.style_preset,
            "--max-font-families",
            str(args.max_font_families),
            "--strict-geometry",
            "--skip-manual-review",
            "--max-loops",
            str(args.max_loops),
        ]
        if args.max_density is not None:
            qa_cmd.extend(["--max-density", str(args.max_density)])
        if args.max_empty_ratio is not None:
            qa_cmd.extend(["--max-empty-ratio", str(args.max_empty_ratio)])
        if loop_skip_render:
            qa_cmd.append("--skip-render")
        if args.allow_issues:
            qa_cmd.append("--allow-issues")

        print(
            f"[iterate_deck] loop {loop}/{total_loops} "
            f"(render={'off' if loop_skip_render else 'on'})",
            file=sys.stderr,
        )

        qa_rc, qa_out = _run(qa_cmd)
        qa_payload = _load_report(qa_report)
        density_warnings = [
            v for v in qa_payload.get("geometry_violations", [])
            if v.get("type") == "density_too_high"
        ]
        loop_entry: dict[str, Any] = {
            "loop": loop,
            "qa_rc": qa_rc,
            "qa_report": str(qa_report),
            "render_skipped": loop_skip_render,
            "qa_summary": {
                "issue_shape_count": qa_payload.get("issue_shape_count"),
                "overflow_count": qa_payload.get("overflow_count"),
                "overlap_count": qa_payload.get("overlap_count"),
                "geometry_violation_count": len(qa_payload.get("geometry_violations", [])),
                "density_warning_count": len(density_warnings),
            },
            "qa_stdout_tail": qa_out[-2000:],
        }

        # Density warnings are QA warnings, not errors (qa_rc can still be 0),
        # but they are the most common remaining gripe on cards/matrix layouts.
        # When present, run one text_fit pass with density_autofix enabled so
        # the remediation actually fires even though QA would otherwise mark
        # the loop as converged.
        if qa_rc == 0 and not density_warnings:
            converged = True
            loops.append(loop_entry)
            break

        if qa_rc == 0 and density_warnings:
            loop_entry["triggered_by"] = "density_warning"

        fit_cmd = [
            py,
            str(base / "text_fit.py"),
            "--input",
            str(output_path),
            "--output",
            str(output_path),
            "--style-preset",
            args.style_preset,
            "--report",
            str(fit_report),
        ]
        # When QA is otherwise clean (qa_rc == 0) and only density warnings
        # remain, run text_fit in density-only mode. Font-reduce + shape-grow
        # on an already-clean deck can introduce edge-case overlaps on
        # tight title/subtitle spacing.
        if qa_rc == 0 and density_warnings:
            fit_cmd.append("--density-only")
        fit_rc, fit_out = _run(fit_cmd)
        loop_entry["text_fit_rc"] = fit_rc
        loop_entry["text_fit_report"] = str(fit_report)
        loop_entry["text_fit_stdout_tail"] = fit_out[-2000:]
        loop_entry["text_fit_summary"] = _load_report(fit_report)
        loops.append(loop_entry)

        # Break early when QA is clean except for density warnings AND
        # the warning count didn't drop between loops. Density residuals
        # on split/chart variants are structural — cards-area shrinks
        # won't reduce the count further, so further loops are wasted.
        fit_summary = loop_entry["text_fit_summary"] or {}
        if qa_rc == 0 and density_warnings:
            current_density_count = len(density_warnings)
            if prev_density_count is not None and current_density_count >= prev_density_count:
                converged = True
                break
            if not fit_summary.get("density_fix_count"):
                converged = True
                break
            prev_density_count = current_density_count

    final_report_path = None
    if args.report:
        final_report_path = Path(args.report).expanduser().resolve()
    elif persist_artifacts:
        final_report_path = outdir / "iteration_report.json"
    payload = {
        "input": str(input_path),
        "output": str(output_path),
        "style_preset": args.style_preset,
        "max_loops": args.max_loops,
        "converged": converged,
        "loops_executed": len(loops),
        "loops": loops,
    }
    if final_report_path is not None:
        final_report_path.parent.mkdir(parents=True, exist_ok=True)
        final_report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    status = "converged" if converged else "not_converged"
    print(f"Iteration status: {status}")
    if final_report_path is not None:
        print(f"Iteration report: {final_report_path}")
    else:
        print("Iteration report: ephemeral (not written)")

    if not persist_artifacts:
        shutil.rmtree(outdir, ignore_errors=True)

    return 0 if converged else 1


if __name__ == "__main__":
    raise SystemExit(main())
