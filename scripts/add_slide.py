#!/usr/bin/env python3
"""Add a new slide to an unpacked PPTX directory.

Two modes:
  - duplicate:   copy an existing slide (preserves layout, text, shapes)
  - from-layout: create an empty slide from a slideLayoutN.xml

After this runs, edit the new slide's XML, then re-pack with pack_pptx.py.
Always run clean_unpacked.py before packing to remove any garbage left
behind by earlier delete operations.

Usage:
    python3 add_slide.py duplicate \\
        --input /path/to/unpacked --source slide2.xml

    python3 add_slide.py from-layout \\
        --input /path/to/unpacked --layout slideLayout2.xml

Both modes print the <p:sldId> line you need to insert into
presentation.xml's <p:sldIdLst> at the desired position.

List available layouts:
    ls /path/to/unpacked/ppt/slideLayouts/
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

_EMPTY_SLIDE_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" \
xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" \
xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr>
        <a:xfrm>
          <a:off x="0" y="0"/>
          <a:ext cx="0" cy="0"/>
          <a:chOff x="0" y="0"/>
          <a:chExt cx="0" cy="0"/>
        </a:xfrm>
      </p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr>
    <a:masterClrMapping/>
  </p:clrMapOvr>
</p:sld>
"""


def _next_slide_number(slides_dir: Path) -> int:
    nums = []
    for f in slides_dir.glob("slide*.xml"):
        m = re.match(r"slide(\d+)\.xml", f.name)
        if m:
            nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def _add_to_content_types(unpacked: Path, dest_slide: str) -> None:
    ct_path = unpacked / "[Content_Types].xml"
    if not ct_path.exists():
        raise FileNotFoundError(f"[Content_Types].xml missing from {unpacked}")
    text = ct_path.read_text(encoding="utf-8")
    part_name = f"/ppt/slides/{dest_slide}"
    if part_name in text:
        return
    override = (
        f'<Override PartName="{part_name}" '
        'ContentType="application/vnd.openxmlformats-officedocument'
        '.presentationml.slide+xml"/>'
    )
    # Refuse to silently no-op if the close tag isn't where we expect —
    # usually means a prior script rewrote the namespace prefix (e.g.,
    # <ns0:Types> instead of <Types>). Fail loudly instead.
    if "</Types>" not in text:
        raise RuntimeError(
            f"{ct_path} has no '</Types>' close tag; likely rewritten "
            "with a non-default namespace prefix. Check recent edits."
        )
    text = text.replace("</Types>", f"  {override}\n</Types>", 1)
    ct_path.write_text(text, encoding="utf-8")


def _add_to_presentation_rels(unpacked: Path, dest_slide: str) -> str:
    rels_path = unpacked / "ppt" / "_rels" / "presentation.xml.rels"
    if not rels_path.exists():
        raise FileNotFoundError(f"presentation.xml.rels missing from {unpacked}")
    text = rels_path.read_text(encoding="utf-8")
    # Allocate a fresh rId above any existing one.
    existing = [int(m) for m in re.findall(r'Id="rId(\d+)"', text)]
    next_rid = (max(existing) + 1) if existing else 1
    rid = f"rId{next_rid}"
    target = f"slides/{dest_slide}"
    if target in text:
        # Slide was already registered; find its rId and return it.
        match = re.search(rf'Id="(rId\d+)"[^>]*Target="{re.escape(target)}"', text)
        if match:
            return match.group(1)
    rel = (
        f'<Relationship Id="{rid}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        f'relationships/slide" Target="{target}"/>'
    )
    if "</Relationships>" not in text:
        raise RuntimeError(
            f"{rels_path} has no '</Relationships>' close tag; likely "
            "rewritten with a non-default namespace prefix. Check recent edits."
        )
    text = text.replace("</Relationships>", f"  {rel}\n</Relationships>", 1)
    rels_path.write_text(text, encoding="utf-8")
    return rid


def _next_slide_id(unpacked: Path) -> int:
    pres_path = unpacked / "ppt" / "presentation.xml"
    text = pres_path.read_text(encoding="utf-8")
    ids = [int(m) for m in re.findall(r'<p:sldId[^>]*id="(\d+)"', text)]
    # PPTX slide IDs start at 256 by convention.
    return (max(ids) + 1) if ids else 256


def _strip_notes_rel(rels_path: Path) -> None:
    """When duplicating a slide, drop any notesSlide relationship so the
    copy doesn't share a notes page with the original.
    """
    if not rels_path.exists():
        return
    text = rels_path.read_text(encoding="utf-8")
    text_new = re.sub(
        r'\s*<Relationship[^>]*Type="[^"]*notesSlide"[^>]*/>\s*',
        "\n",
        text,
    )
    if text_new != text:
        rels_path.write_text(text_new, encoding="utf-8")


def duplicate_slide(unpacked: Path, source: str) -> tuple[str, str, int]:
    slides_dir = unpacked / "ppt" / "slides"
    rels_dir = slides_dir / "_rels"
    source_slide = slides_dir / source
    if not source_slide.exists():
        raise FileNotFoundError(f"Source slide not found: {source_slide}")

    next_num = _next_slide_number(slides_dir)
    dest = f"slide{next_num}.xml"
    dest_slide = slides_dir / dest

    shutil.copy2(source_slide, dest_slide)

    source_rels = rels_dir / f"{source}.rels"
    dest_rels = rels_dir / f"{dest}.rels"
    if source_rels.exists():
        shutil.copy2(source_rels, dest_rels)
        _strip_notes_rel(dest_rels)

    _add_to_content_types(unpacked, dest)
    rid = _add_to_presentation_rels(unpacked, dest)
    slide_id = _next_slide_id(unpacked)
    return dest, rid, slide_id


def create_from_layout(unpacked: Path, layout_file: str) -> tuple[str, str, int]:
    slides_dir = unpacked / "ppt" / "slides"
    rels_dir = slides_dir / "_rels"
    layouts_dir = unpacked / "ppt" / "slideLayouts"
    layout_path = layouts_dir / layout_file
    if not layout_path.exists():
        raise FileNotFoundError(f"Layout not found: {layout_path}")

    next_num = _next_slide_number(slides_dir)
    dest = f"slide{next_num}.xml"
    dest_slide = slides_dir / dest
    dest_rels = rels_dir / f"{dest}.rels"

    dest_slide.write_text(_EMPTY_SLIDE_XML, encoding="utf-8")

    rels_dir.mkdir(exist_ok=True)
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
        '2006/relationships">\n'
        f'  <Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        f'relationships/slideLayout" Target="../slideLayouts/{layout_file}"/>\n'
        "</Relationships>\n"
    )
    dest_rels.write_text(rels_xml, encoding="utf-8")

    _add_to_content_types(unpacked, dest)
    rid = _add_to_presentation_rels(unpacked, dest)
    slide_id = _next_slide_id(unpacked)
    return dest, rid, slide_id


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add a slide to an unpacked PPTX.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    dup = subparsers.add_parser("duplicate", help="Duplicate an existing slide")
    dup.add_argument("--input", required=True, help="Unpacked PPTX directory")
    dup.add_argument(
        "--source",
        required=True,
        help="Source slide filename (e.g., slide2.xml)",
    )

    fl = subparsers.add_parser("from-layout", help="Create a slide from a layout template")
    fl.add_argument("--input", required=True, help="Unpacked PPTX directory")
    fl.add_argument(
        "--layout",
        required=True,
        help="Layout filename (e.g., slideLayout2.xml)",
    )

    args = parser.parse_args()
    unpacked = Path(args.input).expanduser().resolve()
    if not unpacked.exists() or not unpacked.is_dir():
        print(f"Error: {unpacked} is not a directory", file=sys.stderr)
        return 1

    try:
        if args.command == "duplicate":
            dest, rid, slide_id = duplicate_slide(unpacked, args.source)
            source_display = args.source
        else:
            dest, rid, slide_id = create_from_layout(unpacked, args.layout)
            source_display = args.layout
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"Created {dest} from {source_display}")
    print(
        f'Add to presentation.xml <p:sldIdLst>: '
        f'<p:sldId id="{slide_id}" r:id="{rid}"/>'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
