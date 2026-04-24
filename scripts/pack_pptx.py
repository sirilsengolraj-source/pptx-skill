"""Repack an unpacked .pptx directory back into a valid .pptx file.

Preserves the zip layout PowerPoint expects:
- `[Content_Types].xml` written first at the archive root.
- All other parts stored with forward-slash paths, using DEFLATE compression.

Optional `--fix-xml-space` auto-repairs the xml:space="preserve" attribute
on DrawingML text runs whose content has leading/trailing whitespace —
prevents external XML editors from silently stripping significant
whitespace (a list item like "  Second tier" would otherwise collapse to
"Second tier" on save).
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path


CONTENT_TYPES_NAME = "[Content_Types].xml"

# Matches an <a:t> element with text content. Captures:
#   g1 = open tag without the closing '>' (e.g., '<a:t' or '<a:t xml:space="preserve"')
#   g2 = rest of the open tag after the element name (attributes portion)
#   g3 = text content
_AT_ELEMENT_RE = re.compile(r"(<a:t)((?:\s[^>]*)?)>([^<]*)</a:t>")
_XML_SPACE_ATTR_RE = re.compile(r'\bxml:space\s*=\s*"[^"]*"')


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repack a directory tree into a .pptx file PowerPoint can open.",
    )
    parser.add_argument(
        "--indir",
        required=True,
        help="Source directory previously produced by unpack_pptx.py",
    )
    parser.add_argument("--output", required=True, help="Output .pptx path")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing output file",
    )
    parser.add_argument(
        "--fix-xml-space",
        action="store_true",
        help=(
            "Before packing, scan every slide/layout/master XML for "
            "<a:t> elements whose text has leading/trailing whitespace "
            "and add xml:space=\"preserve\" if missing. Prevents silent "
            "whitespace-stripping by external XML editors."
        ),
    )
    return parser.parse_args()


def _iter_files(indir: Path) -> list[Path]:
    return sorted(p for p in indir.rglob("*") if p.is_file())


def _ensure_xml_space_preserve(text: str) -> tuple[str, int]:
    """Ensure <a:t> elements whose text has leading/trailing whitespace
    carry `xml:space="preserve"`. Returns (new_text, repair_count).

    Only touches `<a:t>` tags; never modifies element *content*. Elements
    already carrying `xml:space="preserve"` or that don't need it are
    left alone.
    """
    repairs = 0

    def _repair(match: re.Match[str]) -> str:
        nonlocal repairs
        open_prefix = match.group(1)  # '<a:t'
        attrs = match.group(2) or ""   # existing attribute string
        content = match.group(3)       # text between <a:t> and </a:t>
        if not content:
            return match.group(0)
        needs_preserve = content != content.strip()
        if not needs_preserve:
            return match.group(0)
        if _XML_SPACE_ATTR_RE.search(attrs):
            return match.group(0)
        new_attrs = attrs + ' xml:space="preserve"'
        repairs += 1
        return f"{open_prefix}{new_attrs}>{content}</a:t>"

    new_text = _AT_ELEMENT_RE.sub(_repair, text)
    return new_text, repairs


def _apply_xml_space_fix(indir: Path) -> int:
    total = 0
    for xml_path in indir.rglob("*.xml"):
        if xml_path.name == "[Content_Types].xml":
            continue
        try:
            text = xml_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new_text, repaired = _ensure_xml_space_preserve(text)
        if repaired:
            xml_path.write_text(new_text, encoding="utf-8")
            total += repaired
    return total


def main() -> int:
    args = _args()
    indir = Path(args.indir).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()

    if not indir.exists():
        print(f"Error: indir not found: {indir}", file=sys.stderr)
        return 2
    if not indir.is_dir():
        print(f"Error: indir is not a directory: {indir}", file=sys.stderr)
        return 2

    content_types_path = indir / CONTENT_TYPES_NAME
    if not content_types_path.exists():
        print(
            f"Error: missing {CONTENT_TYPES_NAME} in indir; this does not look "
            f"like an unpacked pptx: {indir}",
            file=sys.stderr,
        )
        return 2

    if output.exists() and not args.overwrite:
        print(
            f"Error: output exists (use --overwrite to replace): {output}",
            file=sys.stderr,
        )
        return 2

    output.parent.mkdir(parents=True, exist_ok=True)

    if args.fix_xml_space:
        repaired = _apply_xml_space_fix(indir)
        if repaired:
            print(
                f"Added xml:space=\"preserve\" to {repaired} <a:t> element(s)",
                file=sys.stderr,
            )

    all_files = _iter_files(indir)
    # Ensure [Content_Types].xml is the first entry in the archive.
    ordered: list[Path] = [content_types_path]
    for path in all_files:
        if path == content_types_path:
            continue
        ordered.append(path)

    try:
        with zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as zf:
            for path in ordered:
                rel = path.relative_to(indir).as_posix()
                zf.write(path, arcname=rel)
    except OSError as exc:
        print(f"Error: failed to write {output}: {exc}", file=sys.stderr)
        return 3

    print(f"Packed {indir} -> {output} ({len(ordered)} parts)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
