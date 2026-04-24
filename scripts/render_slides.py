#!/usr/bin/env python3
"""Render a PPTX file into per-slide images using soffice (or unoserver) + pdftoppm."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _soffice_env() -> dict[str, str]:
    """Return an env dict for soffice/unoconvert subprocesses.

    Forces the "svp" (Server Virtual Plugin) backend so LibreOffice
    renders headlessly even in sandboxed environments without a display
    server. On macOS the default backend already works; setting this is
    harmless. On Linux sandboxes (CI, containers) the default backend
    can fail to initialize, so pinning to svp avoids silent render
    failures.
    """
    env = os.environ.copy()
    env.setdefault("SAL_USE_VCLPLUGIN", "svp")
    return env


def _run(command: list[str]) -> None:
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_soffice_env(),
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(command)
            + "\n"
            + (result.stderr.strip() or result.stdout.strip() or "No error output.")
        )


def _render_with_daemon_or_fallback(pptx_path: Path, out_dir: Path) -> Path:
    """Convert a .pptx to PDF using unoserver (if available) or soffice.

    Tries ``unoconvert`` first (talks to a persistent LibreOffice daemon via
    ``unoserver``, ~1s per call). Falls back to ``soffice --headless --convert-to``
    (~10-15s per call due to LibreOffice startup cost).

    Returns the path to the resulting PDF inside ``out_dir``.
    Logs the chosen path and timing to stderr.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    expected_pdf = out_dir / f"{pptx_path.stem}.pdf"

    if shutil.which("unoconvert"):
        t0 = time.perf_counter()
        result = subprocess.run(
            [
                "unoconvert",
                "--convert-to",
                "pdf",
                str(pptx_path),
                str(expected_pdf),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=_soffice_env(),
        )
        elapsed = time.perf_counter() - t0
        if result.returncode == 0 and expected_pdf.exists():
            # Quiet — one-liner with timing only. Daemon path is the
            # expected fast path; no nagging banner.
            print(f"[render] PDF via unoserver in {elapsed:.2f}s", file=sys.stderr)
            return expected_pdf
        # Non-zero exit or missing artifact: log and fall through to soffice.
        err = (result.stderr.strip() or result.stdout.strip() or "no output")
        print(
            f"[render] unoconvert failed ({elapsed:.2f}s): {err}; "
            "falling back to soffice",
            file=sys.stderr,
        )

    t0 = time.perf_counter()
    _run(
        [
            "soffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(pptx_path),
        ]
    )
    elapsed = time.perf_counter() - t0
    # Terse by default. Emit the "install unoserver" hint only on a truly
    # cold start (≥8s) — the usual case on first build after a reboot —
    # so repeated rapid rebuilds don't nag with the same line every run.
    if elapsed >= 8.0:
        print(
            f"[render] PDF via soffice in {elapsed:.2f}s — "
            "install unoserver for ~15x speedup "
            "(`pip install unoserver && unoserver &`)",
            file=sys.stderr,
        )
    else:
        print(f"[render] PDF via soffice in {elapsed:.2f}s", file=sys.stderr)
    if not expected_pdf.exists():
        raise FileNotFoundError(f"Expected converted PDF not found: {expected_pdf}")
    return expected_pdf


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a .pptx to individual slide images.")
    parser.add_argument("--input", required=True, help="Input .pptx path")
    parser.add_argument("--outdir", required=True, help="Directory for rendered slides")
    parser.add_argument("--dpi", type=int, default=150, help="Rendering DPI for pdftoppm")
    parser.add_argument("--format", choices=["jpeg", "png"], default="jpeg", help="Image format")
    parser.add_argument(
        "--emit-visual-prompt",
        action="store_true",
        help=(
            "After rendering, print the visual-QA subagent prompt with the "
            "rendered image paths substituted. Copy-paste the output into a "
            "fresh Explore agent to run the post-automated-QA inspection "
            "described in references/visual_qa_prompt.md."
        ),
    )
    return parser.parse_args()


_VISUAL_PROMPT_TEMPLATE = """\
Visually inspect these slides. Assume there are issues — find them.

Look for:
- Overlapping elements (text through shapes, lines through words, stacked elements)
- Text overflow or cut off at edges/box boundaries
- Decorative lines positioned for single-line text but the title wrapped to two lines
- Source citations or footers colliding with content above
- Elements too close (< 0.3" gaps) or cards/sections nearly touching
- Uneven gaps (large empty area in one place, cramped in another)
- Insufficient margin from slide edges (< 0.5")
- Columns or similar elements not aligned consistently
- Low-contrast text (e.g., light gray text on cream-colored background)
- Low-contrast icons (e.g., dark icons on dark backgrounds without a contrasting circle)
- Text boxes too narrow causing excessive wrapping
- Leftover placeholder content (Lorem, xxxx, "Prepared deck", etc.)
- AI-slide tells: thin accent rules directly under/over titles, all slides
  using the identical card-3-up layout, every palette key given equal
  weight instead of one dominant color

For each slide, list issues or areas of concern, even if minor.

Read and analyze these images:
{numbered_paths}

Report ALL issues found, including minor ones. Also note any slide that
feels derivative, templatey, or indistinguishable from other slides in the deck.
"""


def _emit_visual_prompt(jpg_paths: list[Path]) -> None:
    numbered = "\n".join(
        f"{i}. {p} (Expected: [fill in per-slide intent])"
        for i, p in enumerate(jpg_paths, start=1)
    )
    print()
    print("=" * 72)
    print("VISUAL QA SUBAGENT PROMPT (copy-paste the block below into an Explore agent)")
    print("=" * 72)
    print(_VISUAL_PROMPT_TEMPLATE.format(numbered_paths=numbered))
    print("=" * 72)


def _require_binary(name: str) -> None:
    if shutil.which(name):
        return
    raise RuntimeError(f"Required binary not found in PATH: {name}")


def _sort_key(path: Path, prefix: str) -> int:
    suffix = path.stem.replace(prefix, "").lstrip("-")
    try:
        return int(suffix)
    except ValueError:
        return 10**9


def main() -> int:
    args = _args()
    input_path = Path(args.input).expanduser().resolve()
    outdir = Path(args.outdir).expanduser().resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # unoconvert is optional (preferred); soffice is the fallback.
    if not shutil.which("unoconvert"):
        _require_binary("soffice")
    _require_binary("pdftoppm")

    outdir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="pptx-render-") as tmp:
        tmp_path = Path(tmp)
        pdf_path = _render_with_daemon_or_fallback(input_path, tmp_path)

        render_prefix = tmp_path / "slide"
        if args.format == "png":
            _run(["pdftoppm", "-png", "-r", str(args.dpi), str(pdf_path), str(render_prefix)])
            extension = ".png"
        else:
            _run(["pdftoppm", "-jpeg", "-r", str(args.dpi), str(pdf_path), str(render_prefix)])
            extension = ".jpg"

        generated = sorted(tmp_path.glob(f"slide-*{extension}"), key=lambda p: _sort_key(p, "slide"))
        if not generated:
            raise RuntimeError("No slide images were generated.")

        final_paths: list[Path] = []
        for index, source in enumerate(generated, start=1):
            target = outdir / f"slide-{index:02d}{extension}"
            shutil.move(str(source), str(target))
            final_paths.append(target)

    print(f"Rendered {len(generated)} slide image(s) to {outdir}")
    if args.emit_visual_prompt:
        _emit_visual_prompt(final_paths)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"Error: {exc}")
        raise SystemExit(1)
