#!/usr/bin/env python3
"""Create thumbnail grids from a PPTX for bird's-eye review.

Renders each slide to a JPG, arranges them in a labeled grid, and writes
one or more grid images. Useful for (a) analyzing an unfamiliar template
deck before duplicating from it, and (b) a fast visual-QA scan of the
finished deck that's faster than paging through per-slide JPGs.

Hidden slides are rendered as diagonal-hatch placeholders so the grid
still numbers correctly.

Usage:
    python3 thumbnail.py --input deck.pptx
    # Creates: thumbnails.jpg

    python3 thumbnail.py --input template.pptx --output grid --cols 4
    # Creates: grid.jpg (or grid-1.jpg, grid-2.jpg for large decks)

Dependencies: Pillow, LibreOffice (`soffice` or `unoconvert`), `pdftoppm`.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Reuse the render helper so we pick up unoserver when available.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_slides import _render_with_daemon_or_fallback  # type: ignore

THUMBNAIL_WIDTH = 300
CONVERSION_DPI = 100
MAX_COLS = 6
DEFAULT_COLS = 3
JPEG_QUALITY = 95
GRID_PADDING = 20
BORDER_WIDTH = 2
FONT_SIZE_RATIO = 0.10
LABEL_PADDING_RATIO = 0.4

_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_PML = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_REL_OFFICE = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _slide_info(pptx: Path) -> list[dict]:
    """Read sldIdLst + .rels to return ordered slide metadata, including
    `hidden` status (from `show="0"` attribute).
    """
    info: list[dict] = []
    with zipfile.ZipFile(pptx, "r") as zf:
        rels_text = zf.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
        rid_to_name: dict[str, str] = {}
        rels_tree = ET.fromstring(rels_text)
        for rel in rels_tree.findall(f"{_REL_NS}Relationship"):
            rtype = rel.get("Type", "")
            target = rel.get("Target", "")
            if "slide" in rtype and target.startswith("slides/"):
                rid_to_name[rel.get("Id", "")] = target[len("slides/"):]

        pres_text = zf.read("ppt/presentation.xml").decode("utf-8")
        pres_tree = ET.fromstring(pres_text)
        sld_id_lst = pres_tree.find(f"{_PML}sldIdLst")
        if sld_id_lst is None:
            return info
        for sld_id in sld_id_lst.findall(f"{_PML}sldId"):
            rid = sld_id.get(f"{_REL_OFFICE}id") or ""
            if not rid:
                # ElementTree doesn't expand namespace in attribute names
                # the same way on all systems; fall back to raw regex.
                match = re.search(r'r:id="([^"]+)"', ET.tostring(sld_id, encoding="unicode"))
                if match:
                    rid = match.group(1)
            hidden = sld_id.get("show") == "0"
            if rid in rid_to_name:
                info.append({"name": rid_to_name[rid], "hidden": hidden})
    return info


def _convert_to_images(pptx: Path, out_dir: Path) -> list[Path]:
    pdf_path = _render_with_daemon_or_fallback(pptx, out_dir)
    subprocess.run(
        [
            "pdftoppm",
            "-jpeg",
            "-r",
            str(CONVERSION_DPI),
            str(pdf_path),
            str(out_dir / "slide"),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return sorted(out_dir.glob("slide-*.jpg"))


def _hidden_placeholder(size: tuple[int, int]) -> Image.Image:
    img = Image.new("RGB", size, color="#F0F0F0")
    draw = ImageDraw.Draw(img)
    line_w = max(5, min(size) // 100)
    draw.line([(0, 0), size], fill="#CCCCCC", width=line_w)
    draw.line([(size[0], 0), (0, size[1])], fill="#CCCCCC", width=line_w)
    return img


def _build_slide_list(
    slide_info: list[dict],
    visible_images: list[Path],
    workdir: Path,
) -> list[tuple[Path, str]]:
    if visible_images:
        with Image.open(visible_images[0]) as probe:
            placeholder_size = probe.size
    else:
        placeholder_size = (1920, 1080)

    slides: list[tuple[Path, str]] = []
    visible_idx = 0
    for info in slide_info:
        if info["hidden"]:
            pph_path = workdir / f"hidden-{info['name']}.jpg"
            _hidden_placeholder(placeholder_size).save(pph_path, "JPEG")
            slides.append((pph_path, f"{info['name']} (hidden)"))
        else:
            if visible_idx < len(visible_images):
                slides.append((visible_images[visible_idx], info["name"]))
                visible_idx += 1
    return slides


def _build_grid(
    slides: list[tuple[Path, str]],
    cols: int,
    thumb_width: int,
) -> Image.Image:
    font_size = int(thumb_width * FONT_SIZE_RATIO)
    label_pad = int(font_size * LABEL_PADDING_RATIO)

    with Image.open(slides[0][0]) as probe:
        aspect = probe.height / probe.width
    thumb_h = int(thumb_width * aspect)

    rows = (len(slides) + cols - 1) // cols
    grid_w = cols * thumb_width + (cols + 1) * GRID_PADDING
    grid_h = rows * (thumb_h + font_size + label_pad * 2) + (rows + 1) * GRID_PADDING

    grid = Image.new("RGB", (grid_w, grid_h), "white")
    draw = ImageDraw.Draw(grid)
    try:
        font = ImageFont.load_default(size=font_size)
    except Exception:  # pragma: no cover - old Pillow
        font = ImageFont.load_default()

    for i, (src_path, label) in enumerate(slides):
        row, col = divmod(i, cols)
        x = col * thumb_width + (col + 1) * GRID_PADDING
        y_base = row * (thumb_h + font_size + label_pad * 2) + (row + 1) * GRID_PADDING

        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        draw.text(
            (x + (thumb_width - text_w) // 2, y_base + label_pad),
            label,
            fill="black",
            font=font,
        )
        y_thumb = y_base + label_pad + font_size + label_pad

        with Image.open(src_path) as img:
            img.thumbnail((thumb_width, thumb_h), Image.Resampling.LANCZOS)
            w, h = img.size
            tx = x + (thumb_width - w) // 2
            ty = y_thumb + (thumb_h - h) // 2
            grid.paste(img, (tx, ty))
            if BORDER_WIDTH > 0:
                draw.rectangle(
                    [
                        (tx - BORDER_WIDTH, ty - BORDER_WIDTH),
                        (tx + w + BORDER_WIDTH - 1, ty + h + BORDER_WIDTH - 1),
                    ],
                    outline="gray",
                    width=BORDER_WIDTH,
                )
    return grid


def _write_grids(
    slides: list[tuple[Path, str]],
    cols: int,
    thumb_width: int,
    output_path: Path,
) -> list[Path]:
    max_per_grid = cols * (cols + 1)
    grid_files: list[Path] = []
    chunks = list(range(0, len(slides), max_per_grid))

    for chunk_idx, start in enumerate(chunks):
        end = min(start + max_per_grid, len(slides))
        chunk = slides[start:end]
        grid = _build_grid(chunk, cols, thumb_width)
        if len(chunks) == 1:
            target = output_path
        else:
            target = output_path.with_name(
                f"{output_path.stem}-{chunk_idx + 1}{output_path.suffix}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        grid.save(str(target), quality=JPEG_QUALITY)
        grid_files.append(target)
    return grid_files


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a .pptx as labeled thumbnail grid(s)."
    )
    parser.add_argument("--input", required=True, help="Input .pptx path")
    parser.add_argument(
        "--output",
        default="thumbnails.jpg",
        help="Output JPG path. Large decks emit <stem>-1.jpg, <stem>-2.jpg, ...",
    )
    parser.add_argument(
        "--cols",
        type=int,
        default=DEFAULT_COLS,
        help=f"Columns per grid (default {DEFAULT_COLS}, max {MAX_COLS})",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=THUMBNAIL_WIDTH,
        help=f"Thumbnail width in pixels (default {THUMBNAIL_WIDTH})",
    )
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists() or input_path.suffix.lower() != ".pptx":
        print(f"Error: invalid .pptx path: {args.input}", file=sys.stderr)
        return 1

    cols = min(args.cols, MAX_COLS)
    if args.cols > MAX_COLS:
        print(f"Warning: --cols clamped to {MAX_COLS}", file=sys.stderr)

    output_path = Path(args.output).expanduser().resolve()
    if output_path.suffix.lower() != ".jpg":
        output_path = output_path.with_suffix(".jpg")

    slide_info = _slide_info(input_path)
    with tempfile.TemporaryDirectory(prefix="pptx-thumb-") as tmp:
        tmp_path = Path(tmp)
        visible = _convert_to_images(input_path, tmp_path)
        if not visible and not any(s["hidden"] for s in slide_info):
            print("Error: no slides rendered", file=sys.stderr)
            return 2
        slides = _build_slide_list(slide_info, visible, tmp_path)
        grids = _write_grids(slides, cols, args.width, output_path)

    print(f"Created {len(grids)} grid(s):")
    for g in grids:
        print(f"  {g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
