#!/usr/bin/env python3
"""Fast regression checks for the default pptxgenjs renderer.

These cases are intentionally small. They exercise layout failure modes that
full benchmark decks can hide: folded titles, subtitle clearance, table headroom,
and default-path variant coverage.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from pptx import Presentation

try:
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover - optional dependency path
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]


def _run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return result.returncode, result.stdout


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _cases() -> dict[str, dict[str, Any]]:
    long_title = (
        "This deliberately folded slide title should reserve enough vertical "
        "space before subtitles and body content"
    )
    return {
        "long-header-cards": {
            "style_preset": "executive-clinical",
            "outline": {
                "slides": [
                    {
                        "type": "title",
                        "title": "Header Regression",
                        "subtitle": "Folded title and subtitle clearance",
                    },
                    {
                        "type": "content",
                        "variant": "cards-3",
                        "title": long_title,
                        "subtitle": "The subtitle must sit below the folded title and above the card row.",
                        "cards": [
                            {
                                "title": "Measured header",
                                "body": (
                                    "The title bar height comes from estimated text lines, not a "
                                    "fixed 0.90 inch constant."
                                ),
                            },
                            {
                                "title": "Derived grid",
                                "body": (
                                    "Card x, y, width, and height still derive from the shared "
                                    "margin and gutter constants."
                                ),
                            },
                            {
                                "title": "Fast gate",
                                "body": (
                                    "Inventory catches title overflow early."
                                ),
                            },
                        ],
                    },
                ]
            },
        },
        "long-header-table": {
            "style_preset": "data-heavy-boardroom",
            "outline": {
                "slides": [
                    {"type": "title", "title": "Table Regression", "subtitle": "Header plus table fit"},
                    {
                        "type": "content",
                        "variant": "table",
                        "title": long_title,
                        "subtitle": "A larger header must shrink the table region instead of overlapping it.",
                        "headers": ["Risk", "Signal", "Action"],
                        "rows": [
                            ["Title overflow", "Long header wraps", "Increase measured bar height"],
                            ["Footer collision", "Dense table rows", "Reserve bottom safe area"],
                            ["Weak source line", "Caption too low", "Bind caption to table bottom"],
                            ["Variant drift", "Wrong renderer", "Use pptxgenjs by default"],
                        ],
                        "caption": "Regression case: dynamic header and table headroom.",
                    },
                ]
            },
        },
        "variant-coverage": {
            "style_preset": "forest-research",
            "outline": {
                "slides": [
                    {"type": "title", "title": "Variant Coverage", "subtitle": "Default renderer smoke test"},
                    {
                        "type": "content",
                        "variant": "matrix",
                        "title": "Matrix stays native in the default path",
                        "subtitle": "Four editable quadrants should render without falling back to bullets.",
                        "quadrants": [
                            {"title": "Grid", "body": "2 by 2 structure with shared gutters."},
                            {"title": "Type", "body": "Heading and body sizes stay consistent."},
                            {"title": "Rails", "body": "Accent rails align to every quadrant."},
                            {"title": "QA", "body": "No overflow or overlap should be reported."},
                        ],
                    },
                    {
                        "type": "content",
                        "variant": "comparison-2col",
                        "title": "Comparison uses open columns",
                        "subtitle": "A-versus-B arguments should not require the Python fallback.",
                        "left": {
                            "title": "Fixed header",
                            "body": ["Easy to place", "Breaks with folded titles"],
                        },
                        "right": {
                            "title": "Measured header",
                            "body": ["Uses line estimates", "Moves body content down safely"],
                        },
                        "verdict": "Default renderer owns this composition.",
                    },
                ]
            },
        },
        "lab-image-sidebar": {
            "style_preset": "lab-report",
            "fixture_image": "lod_fixture.png",
            "outline": {
                "slides": [
                    {
                        "type": "title",
                        "title": "Lab Figure Regression",
                        "subtitle": "Figure-first academic content slide",
                    },
                    {
                        "type": "content",
                        "variant": "image-sidebar",
                        "title": "LOD figure with interpretation sidebar",
                        "subtitle": "Figure panel, compact interpretation, caption, and footer should not collide.",
                        "assets": {"hero_image": "lod_fixture.png"},
                        "image_side": "left",
                        "sidebar_sections": [
                            {
                                "title": "Readout",
                                "body": [
                                    "TTD separates positive control from no-template control.",
                                    "Replicates remain visible at low copy input.",
                                ],
                            },
                            {
                                "title": "Interpretation",
                                "body": [
                                    "Use the figure for evidence; use sidebar text for conclusion.",
                                    "Caption carries fixture provenance instead of crowding the title.",
                                ],
                            },
                            {
                                "title": "Caveat",
                                "body": ["Synthetic fixture for layout regression only."],
                            },
                        ],
                        "caption": "Synthetic LOD plot fixture generated locally for regression testing.",
                        "footer": "Regression case: lab-report figure-first composition.",
                    },
                ]
            },
        },
        "lab-run-results": {
            "style_preset": "lab-report",
            "outline": {
                "slides": [
                    {
                        "type": "title",
                        "title": "Lab Table Regression",
                        "subtitle": "Editable compact result tables with semantic cell fills",
                    },
                    {
                        "type": "content",
                        "variant": "lab-run-results",
                        "title": "POC concordance stays readable as editable tables",
                        "subtitle": "Confusion matrix, metric block, and run status share one lab-report canvas.",
                        "tables": [
                            {
                                "title": "Any Cobas+ vs any LAMP+",
                                "headers": ["", "Cobas +", "Cobas -", "Total"],
                                "rows": [
                                    ["LAMP +", "32", "2", "34"],
                                    ["LAMP -", "3", "14", "17"],
                                    ["Total", "35", "16", "51"],
                                ],
                                "column_weights": [1.0, 0.8, 0.8, 0.8],
                                "cell_styles": [
                                    [{ "bold": True }, { "fill": "#D9EAD3", "bold": True }, { "fill": "#F4CCCC", "bold": True }, {}],
                                    [{ "bold": True }, { "fill": "#F4CCCC", "bold": True }, { "fill": "#D9EAD3", "bold": True }, {}],
                                    [{ "bold": True }, {}, {}, { "bold": True }],
                                ],
                                "footnotes": ["False positives: discordant LAMP+/Cobas- calls need repeat review."],
                            },
                            {
                                "title": "Diagnostic metrics",
                                "headers": ["Metric", "Value", "Detail"],
                                "rows": [
                                    ["Sensitivity", "91.4%", "32/35"],
                                    ["Specificity", "87.5%", "14/16"],
                                    ["Accuracy", "90.2%", "46/51"],
                                    ["PPV", "94.1%", "32/34"],
                                ],
                                "column_weights": [1.2, 0.8, 0.9],
                            },
                            {
                                "title": "CIN 2+ subgroup",
                                "headers": ["LAMP", "Cobas +", "Cobas -", "Total"],
                                "rows": [
                                    ["+", "17", "1", "18"],
                                    ["-", "0", "4", "4"],
                                ],
                                "cell_styles": [
                                    [{ "bold": True }, { "fill": "#D9EAD3", "bold": True }, { "fill": "#FCE5CD", "bold": True }, {}],
                                    [{ "bold": True }, { "fill": "#F4CCCC", "bold": True }, { "fill": "#D9EAD3", "bold": True }, {}],
                                ],
                            },
                        ],
                        "interpretation": "Pattern mirrors clean lab decks: data table first, interpretation second, no decorative clutter.",
                        "footer": "Regression case: compact table-heavy lab slide.",
                    },
                ]
            },
        },
        "scientific-figure-panels": {
            "style_preset": "lab-report",
            "fixture_image": "lod_fixture.png",
            "outline": {
                "slides": [
                    {
                        "type": "title",
                        "title": "Scientific Figure Regression",
                        "subtitle": "Multi-panel figure layout",
                    },
                    {
                        "type": "content",
                        "variant": "scientific-figure",
                        "title": "Two-panel LoD figure keeps captions compact",
                        "subtitle": "Panel labels, figure boxes, bottom caption, and footer should not collide.",
                        "figures": [
                            {
                                "path": "lod_fixture.png",
                                "label": "A",
                                "title": "ASM matrix",
                                "caption": "Synthetic positive-control dilution curve.",
                            },
                            {
                                "path": "lod_fixture.png",
                                "label": "B",
                                "title": "Saliva matrix",
                                "caption": "Same fixture reused to test panel geometry.",
                            },
                        ],
                        "caption": "Synthetic multi-panel fixture generated locally for regression testing.",
                        "interpretation": "Use scientific-figure when the evidence is the figure grid itself.",
                        "footer": "Regression case: lab-report multi-panel figure composition.",
                    },
                ]
            },
        },
        "auto-image-sources": {
            "style_preset": "editorial-minimal",
            "fixture_image": "lod_fixture.png",
            "attribution_rows": [
                {
                    "file_name": "lod_fixture.png",
                    "file_path": "lod_fixture.png",
                    "title": "Synthetic regression visual",
                    "source_page": "https://commons.wikimedia.org/wiki/File:Regression_visual.png",
                    "image_url": "https://upload.wikimedia.org/wikipedia/commons/example.png",
                    "license": "CC BY 4.0",
                    "license_url": "https://creativecommons.org/licenses/by/4.0/",
                    "artist": "Regression Fixture",
                    "credit": "Regression Fixture / Wikimedia Commons",
                    "query": "regression visual",
                }
            ],
            "expected_slides": 3,
            "outline": {
                "title": "Auto Attribution Regression",
                "deck_style": {"research_visual_mode": True},
                "compliance": {
                    "attribution_file": "assets/attribution.csv",
                    "auto_image_sources": True,
                    "require_attribution": True,
                },
                "slides": [
                    {
                        "type": "title",
                        "title": "Auto Attribution Regression",
                        "subtitle": "Source-backed image citation slide",
                    },
                    {
                        "type": "content",
                        "variant": "image-sidebar",
                        "title": "Source Visual With Sidebar",
                        "subtitle": "The builder should append an Image Sources slide.",
                        "assets": {"image": "lod_fixture.png"},
                        "sidebar_sections": [
                            {"title": "Readout", "body": ["One source-backed visual anchors the slide."]},
                            {"title": "Audit", "body": ["Attribution rows stay outside the body layout."]},
                        ],
                        "caption": "Source-backed fixture row in assets/attribution.csv.",
                        "sources": ["Image attribution: assets/attribution.csv"],
                    },
                ],
            },
        },
    }


def _write_fixture_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if Image is None or ImageDraw is None:
        # Tiny valid PNG fallback: transparent 1x1. The slide still exercises
        # path resolution and image placement, just not plot readability.
        import base64

        path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
            )
        )
        return

    img = Image.new("RGB", (1280, 720), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 1280, 70], fill="#0B2545")
    draw.text((40, 24), "Synthetic IS6110 LOD fixture", fill="#FFFFFF")
    plot = (105, 130, 1170, 600)
    draw.rectangle(plot, outline="#CBD5E1", width=3)
    for i in range(6):
        x = plot[0] + i * (plot[2] - plot[0]) / 5
        draw.line([x, plot[1], x, plot[3]], fill="#EEF2F7", width=2)
        draw.text((x - 18, plot[3] + 24), f"10^{5 - i}", fill="#475569")
    for tick in range(0, 61, 15):
        y = plot[3] - tick * (plot[3] - plot[1]) / 60
        draw.line([plot[0], y, plot[2], y], fill="#EEF2F7", width=2)
        draw.text((48, y - 8), str(tick), fill="#475569")
    series = [
        ("ASM", "#C9302C", [18, 22, 28, 34, 42, 56]),
        ("Saliva", "#1493A4", [20, 25, 31, 39, 48, 58]),
    ]
    for label, color, values in series:
        points = []
        for i, value in enumerate(values):
            x = plot[0] + i * (plot[2] - plot[0]) / 5
            y = plot[3] - value * (plot[3] - plot[1]) / 60
            points.append((x, y))
        draw.line(points, fill=color, width=5)
        for x, y in points:
            draw.ellipse([x - 8, y - 8, x + 8, y + 8], fill=color)
        draw.text((plot[2] - 135, points[-1][1] - 18), label, fill=color)
    draw.text((104, 635), "Copy number (copies/reaction)", fill="#1B2838")
    draw.text((32, 100), "TTD (min)", fill="#1B2838")
    img.save(path)


def _write_attribution_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "file_name",
        "file_path",
        "title",
        "source_page",
        "image_url",
        "license",
        "license_url",
        "artist",
        "credit",
        "query",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        import csv

        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: str(row.get(key, "")) for key in fieldnames})


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run fast pptxgenjs regression checks.")
    parser.add_argument(
        "--outdir",
        default="",
        help="Output directory. Defaults to a temp directory that is kept for inspection.",
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="Run render-based QA too. By default this stays render-free for speed.",
    )
    parser.add_argument(
        "--visual-review",
        action="store_true",
        help=(
            "Ask qa_gate.py to create a visual-review packet. With --render this "
            "also creates contact sheets; without --render it runs text/rhythm checks."
        ),
    )
    parser.add_argument(
        "--fail-on-visual-review-warnings",
        action="store_true",
        help="Fail regression cases when visual_review.py emits warning-level findings.",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    repo = Path(__file__).resolve().parent.parent
    outdir = Path(args.outdir).expanduser().resolve() if args.outdir else Path(
        tempfile.mkdtemp(prefix="presentation-skill-pptxgenjs-regression-")
    )
    outdir.mkdir(parents=True, exist_ok=True)

    py = sys.executable
    results: list[dict[str, Any]] = []
    for name, spec in _cases().items():
        case_dir = outdir / name
        case_dir.mkdir(parents=True, exist_ok=True)
        outline_path = case_dir / "outline.json"
        pptx_path = case_dir / f"{name}.pptx"
        qa_dir = case_dir / "qa"
        qa_report = qa_dir / "report.json"
        fixture = spec.get("fixture_image")
        if isinstance(fixture, str) and fixture:
            _write_fixture_image(case_dir / fixture)
        attribution_rows = spec.get("attribution_rows")
        if isinstance(attribution_rows, list) and attribution_rows:
            _write_attribution_csv(case_dir / "assets" / "attribution.csv", attribution_rows)  # type: ignore[arg-type]
        outline_path.write_text(json.dumps(spec["outline"], indent=2) + "\n", encoding="utf-8")

        build_cmd = [
            "node",
            str(repo / "scripts" / "build_deck_pptxgenjs.js"),
            "--outline",
            str(outline_path),
            "--output",
            str(pptx_path),
            "--style-preset",
            str(spec["style_preset"]),
        ]
        build_rc, build_out = _run(build_cmd)

        qa_rc = 99
        qa_out = ""
        qa_payload: dict[str, Any] = {}
        if build_rc == 0:
            slide_count = len(Presentation(str(pptx_path)).slides) if pptx_path.exists() else 0
            qa_cmd = [
                py,
                str(repo / "scripts" / "qa_gate.py"),
                "--input",
                str(pptx_path),
                "--outdir",
                str(qa_dir),
                "--style-preset",
                str(spec["style_preset"]),
                "--strict-geometry",
                "--skip-manual-review",
                "--fail-on-design-warnings",
                "--outline",
                str(outline_path),
                "--report",
                str(qa_report),
            ]
            if not args.render:
                qa_cmd.append("--skip-render")
            if args.visual_review:
                qa_cmd.append("--run-visual-review")
            if args.fail_on_visual_review_warnings:
                qa_cmd.append("--fail-on-visual-review-warnings")
            qa_rc, qa_out = _run(qa_cmd)
            qa_payload = _load_json(qa_report)
        else:
            slide_count = 0

        expected_slides = spec.get("expected_slides")
        slide_count_ok = (
            True
            if not isinstance(expected_slides, int)
            else slide_count == expected_slides
        )

        passed = (
            build_rc == 0
            and qa_rc == 0
            and slide_count_ok
            and qa_payload.get("overflow_count", 0) == 0
            and qa_payload.get("overlap_count", 0) == 0
            and qa_payload.get("geometry_error_count", 0) == 0
            and qa_payload.get("design_error_count", 0) == 0
            and qa_payload.get("design_warning_count", 0) == 0
        )
        result = {
            "case": name,
            "passed": passed,
            "pptx": str(pptx_path),
            "build_rc": build_rc,
            "qa_rc": qa_rc,
            "slide_count": slide_count,
            "expected_slides": expected_slides,
            "overflow_count": qa_payload.get("overflow_count"),
            "overlap_count": qa_payload.get("overlap_count"),
            "geometry_error_count": qa_payload.get("geometry_error_count"),
            "design_error_count": qa_payload.get("design_error_count"),
            "design_warning_count": qa_payload.get("design_warning_count"),
            "visual_review_warning_count": qa_payload.get("visual_review_warning_count"),
            "visual_review_report": qa_payload.get("visual_review_report", ""),
            "build_stdout_tail": build_out[-1200:],
            "qa_stdout_tail": qa_out[-1200:],
        }
        results.append(result)
        slide_part = (
            f"slides={slide_count}/{expected_slides} "
            if isinstance(expected_slides, int)
            else f"slides={slide_count} "
        )
        print(
            f"[{name}] {'PASS' if passed else 'FAIL'} "
            f"{slide_part}"
            f"overflow={result['overflow_count']} overlap={result['overlap_count']} "
            f"geo_err={result['geometry_error_count']} design={result['design_error_count']}/"
            f"{result['design_warning_count']} "
            f"visual_review={result['visual_review_warning_count']}"
        )

    summary = {
        "outdir": str(outdir),
        "render_enabled": bool(args.render),
        "visual_review_enabled": bool(args.visual_review),
        "total": len(results),
        "passed": sum(1 for item in results if item["passed"]),
        "failed": sum(1 for item in results if not item["passed"]),
        "results": results,
    }
    summary_path = outdir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Summary: {summary_path}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
