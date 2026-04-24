#!/usr/bin/env python3
"""Build a deck from a persistent workspace scaffold."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and optionally QA a persistent deck workspace.")
    parser.add_argument("--workspace", required=True, help="Workspace directory created by init_deck_workspace.py")
    parser.add_argument("--qa", action="store_true", help="Run qa_gate.py after building")
    parser.add_argument("--skip-render", action="store_true", help="Pass --skip-render through to qa_gate.py")
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip the static outline preflight linter that normally runs before build.",
    )
    parser.add_argument(
        "--strict-preflight",
        action="store_true",
        help="Abort the build if preflight finds blocking errors (exit code 2).",
    )
    parser.add_argument(
        "--skip-asset-staging",
        action="store_true",
        help="Do not run asset_stage.py even when asset_plan.json exists",
    )
    parser.add_argument(
        "--allow-network-assets",
        action="store_true",
        help="Allow Wikimedia Commons downloads during asset staging",
    )
    parser.add_argument(
        "--allow-generated-images",
        action="store_true",
        help="Allow OpenAI Images API calls for generated_images entries in asset_plan.json",
    )
    parser.add_argument(
        "--strict-provenance",
        action="store_true",
        help="Require local staged assets to include provenance metadata",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite the built .pptx output")
    parser.add_argument(
        "--renderer",
        choices=("python", "pptxgenjs", "auto"),
        default="auto",
        help=(
            "Which renderer to invoke for the .pptx. 'auto' (default) routes to pptxgenjs "
            "unless the outline has a python-only variant (chart, image-sidebar). "
            "'python' forces build_deck.py. 'pptxgenjs' forces build_deck_pptxgenjs.js via node."
        ),
    )
    return parser.parse_args()


def _pick_auto_renderer(outline_path: Path) -> str:
    """Return 'pptxgenjs' if the outline looks like it benefits from it, else 'python'.

    Route to pptxgenjs (HTML-typography path) when ANY slide:
    - is a `section` divider, OR
    - has visual_intent in {timeline, hero, comparison}, OR
    - uses the `timeline`, `stats`, `kpi-hero`, or `table` variant
      (pptxgenjs renders these with richer typography than python-pptx,
      especially tables where the HTML path uses native addTable).
    Route to python when the outline has variants pptxgenjs can't
    render (matrix, chart, comparison-2col), since a mixed-renderer
    deck isn't supported and python-pptx is the superset.
    """
    try:
        data = json.loads(outline_path.read_text(encoding="utf-8"))
    except Exception:
        return "python"
    slides = data.get("slides") if isinstance(data, dict) else None
    if not isinstance(slides, list):
        return "python"

    # Variants that only render correctly under python-pptx because the
    # pptxgenjs path hasn't implemented them yet:
    #   - chart: native OOXML chart generation (pptxgenjs supports chart but
    #     the outline → pptxgenjs chart mapping isn't wired yet)
    #   - image-sidebar: 2-col layout with PIL aspect-ratio fitting
    # Note: mermaid_source, hero_image, diagram, and visual_intent:flow are
    # now handled natively by the pptxgenjs path (see renderFlow in slides.js
    # and the pre-render hook in build_deck_pptxgenjs.js).
    python_only_variants = {"chart", "image-sidebar"}
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        variant = str(slide.get("variant", "") or "").strip().lower()
        if variant in python_only_variants:
            return "python"

    # Default: pptxgenjs. It's the richer-typography path with native mermaid
    # and hero support.
    return "pptxgenjs"


def main() -> int:
    args = _args()
    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        raise FileNotFoundError(f"Workspace not found: {workspace}")

    manifest = _load_json(workspace / "workspace.json")
    contract = _load_json(workspace / manifest["style_contract"])

    outline_path = workspace / manifest["outline"]
    build_cfg = contract.get("build", {})
    build_dir = workspace / manifest.get("build_dir", "build")
    build_dir.mkdir(parents=True, exist_ok=True)

    output_pptx = workspace / build_cfg.get("output_pptx", "build/deck.pptx")
    qa_dir = workspace / build_cfg.get("qa_dir", "build/qa")
    qa_report = workspace / build_cfg.get("qa_report", "build/qa/report.json")
    qa_dir.mkdir(parents=True, exist_ok=True)

    if output_pptx.exists() and not args.overwrite:
        raise FileExistsError(
            f"Output already exists: {output_pptx}. Pass --overwrite to replace it."
        )

    scripts_dir = Path(__file__).resolve().parent
    py = sys.executable

    planning_script = scripts_dir / "validate_planning.py"
    if planning_script.exists():
        planning_report = build_dir / "planning_validation.json"
        planning_cmd = [
            py,
            str(planning_script),
            "--workspace",
            str(workspace),
            "--report",
            str(planning_report),
        ]
        planning = subprocess.run(
            planning_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if planning.stdout:
            print(planning.stdout, end="")
        if planning.stderr:
            print(planning.stderr, end="", file=sys.stderr)
        if planning.returncode == 2 and args.qa:
            print(
                "[build_workspace] Planning validation found blocking errors. "
                "Fix content_plan.json / evidence_plan.json or run without --qa.",
                file=sys.stderr,
            )
            return 2

    # Preflight: fast static outline linter. Runs before build so we can
    # catch common authoring errors in <1s instead of failing during a
    # ~60s LibreOffice render. Safe-by-default: warnings are printed but
    # the build proceeds; errors only block when --strict-preflight or
    # --qa are set (QA will fail on these downstream regardless).
    preflight_stdout_capture = None  # path used for telemetry logging
    if not args.skip_preflight:
        preflight_script = scripts_dir / "preflight.py"
        if preflight_script.exists():
            preflight_cmd = [py, str(preflight_script), "--outline", str(outline_path)]
            pf = subprocess.run(
                preflight_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            # Surface the human-readable summary (stderr) to the user.
            if pf.stderr:
                print(pf.stderr, end="", file=sys.stderr)
            # pf.stdout is the JSON payload; keep it available for tooling.
            if pf.stdout:
                print(pf.stdout, end="")
                # Capture for skill-level telemetry aggregation.
                preflight_stdout_capture = workspace / "build" / "preflight.json"
                try:
                    preflight_stdout_capture.parent.mkdir(parents=True, exist_ok=True)
                    preflight_stdout_capture.write_text(pf.stdout, encoding="utf-8")
                except OSError:
                    preflight_stdout_capture = None
            if pf.returncode == 3:
                print(
                    "[build_workspace] Preflight aborted: outline JSON is malformed. Fix it and retry.",
                    file=sys.stderr,
                )
                return 3
            if pf.returncode == 2:
                if args.strict_preflight or args.qa:
                    print(
                        "[build_workspace] Preflight found blocking errors. Aborting build "
                        "(run with --skip-preflight to bypass, or fix the issues above).",
                        file=sys.stderr,
                    )
                    return 2
                else:
                    print(
                        "[build_workspace] Preflight found errors; proceeding anyway (no --strict-preflight / --qa). "
                        "These will likely surface as QA failures downstream.",
                        file=sys.stderr,
                    )

    asset_plan = workspace / manifest.get("asset_plan", "asset_plan.json")
    staged_assets_dir = workspace / manifest.get("staged_assets_dir", "assets/staged")
    attribution_csv = workspace / "assets" / "attribution.csv"

    # Nudge: if asset_plan is still the init stub (has __readme__ and
    # all arrays empty) AND the outline references no staged visuals,
    # the deck will render text-only. Warn loudly — this is the #1
    # "Codex skipped visual enrichment" failure mode.
    _warn_if_stub_and_text_only(asset_plan, outline_path)

    if asset_plan.exists() and not args.skip_asset_staging:
        stage_cmd = [
            py,
            str(scripts_dir / "asset_stage.py"),
            "--manifest",
            str(asset_plan),
            "--output-dir",
            str(staged_assets_dir),
            "--attribution-csv",
            str(attribution_csv),
        ]
        if args.allow_network_assets:
            stage_cmd.append("--allow-network")
        if args.allow_generated_images:
            stage_cmd.append("--allow-generated-images")
        if args.strict_provenance:
            stage_cmd.append("--strict-provenance")
        _run(stage_cmd)

    renderer = args.renderer
    if renderer == "auto":
        renderer = _pick_auto_renderer(outline_path)
        print(f"[build_workspace] --renderer auto picked '{renderer}'", file=sys.stderr)

    # `pptxgenjs` generates the same .pptx container format, so QA downstream
    # runs identically. If node or the module is missing we surface the error
    # rather than silently falling back to Python -- honoring the explicit
    # renderer request (per Fix 4).
    if output_pptx.exists() and args.overwrite:
        try:
            output_pptx.unlink()
        except OSError:
            pass

    if renderer == "pptxgenjs":
        js_script = scripts_dir / "build_deck_pptxgenjs.js"
        if not js_script.exists():
            raise FileNotFoundError(f"pptxgenjs renderer not found: {js_script}")
        build_cmd = [
            "node",
            str(js_script),
            "--outline",
            str(outline_path),
            "--output",
            str(output_pptx),
            "--style-preset",
            str(build_cfg.get("style_preset", "executive-clinical")),
        ]
        try:
            result = subprocess.run(
                build_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
            )
        except FileNotFoundError as exc:
            print(
                f"[build_workspace] pptxgenjs renderer failed: node not found on PATH ({exc})",
                file=sys.stderr,
            )
            return 1
        if result.stdout:
            print(result.stdout, end="")
        if result.returncode != 0:
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)
            print(
                "[build_workspace] pptxgenjs renderer failed. "
                "Ensure node is on PATH and the 'pptxgenjs' module is installed "
                "(see scripts/build_deck_pptxgenjs.js NODE_PATH hints).",
                file=sys.stderr,
            )
            return result.returncode
        if result.stderr:
            # pptxgenjs can print benign warnings; surface them.
            print(result.stderr, end="", file=sys.stderr)
    else:
        build_cmd = [
            py,
            str(scripts_dir / "build_deck.py"),
            "--outline",
            str(outline_path),
            "--output",
            str(output_pptx),
            "--style-preset",
            str(build_cfg.get("style_preset", "executive-clinical")),
        ]
        if build_cfg.get("font_pair"):
            build_cmd.extend(["--font-pair", str(build_cfg["font_pair"])])
        if build_cfg.get("palette_key"):
            build_cmd.extend(["--palette-key", str(build_cfg["palette_key"])])
        if args.overwrite:
            build_cmd.append("--overwrite")
        _run(build_cmd)

    if args.qa:
        qa_cmd = [
            py,
            str(scripts_dir / "qa_gate.py"),
            "--input",
            str(output_pptx),
            "--outdir",
            str(qa_dir),
            "--style-preset",
            str(build_cfg.get("style_preset", "executive-clinical")),
            "--strict-geometry",
            "--skip-manual-review",
            "--fail-on-visual-warnings",
            "--fail-on-design-warnings",
            "--outline",
            str(outline_path),
            "--report",
            str(qa_report),
        ]
        if args.skip_render:
            qa_cmd.append("--skip-render")
        _run(qa_cmd)

    # Narration check: fail loudly when the outline references assets
    # that don't exist on disk. Catches the "Codex narrated 'adding
    # icons' but assets/icons/ was never created" failure mode.
    verify_script = scripts_dir / "verify_narration.py"
    verify_log_path = None
    if verify_script.exists():
        vn = subprocess.run(
            [py, str(verify_script), "--workspace", str(workspace)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Echo to user-visible channels the same way the script would
        # when run standalone.
        if vn.stdout:
            print(vn.stdout, end="")
        if vn.stderr:
            print(vn.stderr, end="", file=sys.stderr)
        # Persist stderr for telemetry (that's where asset-missing lines go).
        if vn.stderr:
            verify_log_path = workspace / "build" / "verify_narration.log"
            try:
                verify_log_path.write_text(vn.stderr, encoding="utf-8")
            except OSError:
                verify_log_path = None

    # Skill-level telemetry. Non-blocking — harvests preflight + QA +
    # narration results into a JSONL log we can mine for patterns with
    # `summarize_skill_log.py`. Safe to skip on any error.
    telemetry_script = scripts_dir / "log_skill_telemetry.py"
    if telemetry_script.exists() and args.qa:
        telem_cmd = [py, str(telemetry_script), "--workspace", str(workspace)]
        if preflight_stdout_capture and preflight_stdout_capture.exists():
            telem_cmd.extend(["--preflight-json", str(preflight_stdout_capture)])
        if qa_report.exists():
            telem_cmd.extend(["--qa-report", str(qa_report)])
        if verify_log_path and verify_log_path.exists():
            telem_cmd.extend(["--verify-narration-log", str(verify_log_path)])
        subprocess.run(telem_cmd, check=False)

    # After a successful build, surface the outline-critique subagent
    # prompt for any deck with >=5 content slides. Automated preflight
    # catches schema-level issues; the subagent critique catches
    # editorial ones (monotony, weak palette, text-only bias) that a
    # deterministic linter can't see. Non-blocking — just printed so the
    # agent sees it and can paste it into an Explore subagent.
    _maybe_emit_critique_prompt(
        outline_path=outline_path,
        scripts_dir=scripts_dir,
        py=py,
    )

    return 0


def _warn_if_stub_and_text_only(asset_plan_path: Path, outline_path: Path) -> None:
    """Emit a warning when the deck is about to render with no staged
    visuals AND the asset_plan is still the init stub.

    This is the failure mode Codex falls into: it scaffolds a workspace,
    never populates asset_plan.json, and the outline has no hero/icons/
    mermaid — so the deck renders text-only despite the skill having
    every tool needed for visual enrichment.
    """
    if not asset_plan_path.exists():
        return
    try:
        plan = json.loads(asset_plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    # Stub signature: __readme__ present, and every asset array is empty.
    is_stub = "__readme__" in plan and all(
        not plan.get(k)
        for k in ("images", "backgrounds", "charts", "generated_images", "icons")
    )
    if not is_stub:
        return

    # Inspect outline for any staged-asset references.
    try:
        outline = json.loads(outline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    slides = outline.get("slides") or []
    has_visual = False
    for s in slides:
        if not isinstance(s, dict):
            continue
        assets = s.get("assets") or {}
        if not isinstance(assets, dict):
            continue
        if (
            assets.get("hero_image")
            or assets.get("generated_image")
            or assets.get("icons")
            or assets.get("mermaid_source")
            or assets.get("diagram")
        ):
            has_visual = True
            break
    if has_visual:
        return

    print(
        "",
        file=sys.stderr,
    )
    print(
        "[build_workspace] WARNING: asset_plan.json is still the init "
        "stub AND the outline references no staged visuals (no "
        "assets.hero_image, no assets.generated_image, no assets.icons, "
        "no assets.mermaid_source, no assets.diagram). The deck will render TEXT-ONLY.",
        file=sys.stderr,
    )
    print(
        "[build_workspace] If that's intentional (qualitative primer, "
        "no natural visual anchor), continue. Otherwise: populate "
        f"{asset_plan_path.name} with topic-specific images/icons, or "
        "reference assets inline via `assets.hero_image` / "
        "`assets.generated_image` / `assets.icons` / `assets.mermaid_source` "
        "on individual slides. "
        "See references/outline_schema.md #Visual Enrichment Defaults.",
        file=sys.stderr,
    )
    print("", file=sys.stderr)


def _maybe_emit_critique_prompt(*, outline_path: Path, scripts_dir: Path, py: str) -> None:
    try:
        outline = json.loads(outline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    slides = outline.get("slides") or []
    content_count = sum(
        1 for s in slides
        if isinstance(s, dict)
        and (s.get("type") or "content").strip().lower() == "content"
    )
    if content_count < 5:
        return

    emitter = scripts_dir / "emit_outline_critique.py"
    if not emitter.exists():
        return

    result = subprocess.run(
        [py, str(emitter), "--outline", str(outline_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        return

    # Write to stderr so pipelines that capture stdout aren't polluted.
    print("", file=sys.stderr)
    print(
        "[build_workspace] Deck has "
        f"{content_count} content slides. "
        "Editorial critique recommended — paste the prompt below into a "
        "fresh Explore subagent to catch monotony, weak palette, and "
        "missing rhythm-breakers that preflight can't see. Re-run the "
        "build after addressing the findings.",
        file=sys.stderr,
    )
    print(result.stdout, file=sys.stderr)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"Error: {exc}")
        raise SystemExit(1)
