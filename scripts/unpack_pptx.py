"""Unpack a .pptx file into a directory so its XML parts can be edited."""

from __future__ import annotations

import argparse
import io
import os
import stat
import sys
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import zipfile
from pathlib import Path


_SMART_QUOTE_ENTITIES = {
    "\u201c": "&#x201C;",  # left double quote
    "\u201d": "&#x201D;",  # right double quote
    "\u2018": "&#x2018;",  # left single quote
    "\u2019": "&#x2019;",  # right single quote / apostrophe
    "\u2013": "&#x2013;",  # en dash
    "\u2014": "&#x2014;",  # em dash
    "\u2026": "&#x2026;",  # ellipsis
}


def _escape_smart_quotes(text: str) -> str:
    """Replace smart quotes with XML numeric entities.

    Why: agents editing unpacked XML with generic text-edit tools routinely
    save files in whatever encoding the tool defaults to. Literal smart
    quotes survive the round-trip inconsistently (some tools normalize to
    ASCII, breaking the rendered glyph). Storing entities keeps the source
    portable — PowerPoint reads them back correctly on pack.
    """
    for ch, entity in _SMART_QUOTE_ENTITIES.items():
        text = text.replace(ch, entity)
    return text


# Canonical OOXML namespace prefixes. Without these, ElementTree
# auto-generates ns0/ns1/… when re-serializing, which breaks downstream
# tools that regex on the conventional prefixes.
_OOXML_NAMESPACES = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "cx": "http://schemas.microsoft.com/office/drawing/2014/chartex",
    "dgm": "http://schemas.openxmlformats.org/drawingml/2006/diagram",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "v": "urn:schemas-microsoft-com:vml",
    "o": "urn:schemas-microsoft-com:office:office",
    "w": "urn:schemas-microsoft-com:office:word",
    "sl": "http://schemas.openxmlformats.org/schemaLibrary/2006/main",
    "xml": "http://www.w3.org/XML/1998/namespace",
}


def _register_ooxml_namespaces() -> None:
    for prefix, uri in _OOXML_NAMESPACES.items():
        ET.register_namespace(prefix, uri)


def _prettify_xml(raw_bytes: bytes) -> bytes:
    """Pretty-print XML bytes with 2-space indent.

    Preserves text content inside `<a:t>` and other whitespace-significant
    elements (indent is inserted between sibling tags, not inside text
    nodes). Keeps conventional OOXML prefixes (`p:`, `a:`, `r:`) via
    `register_namespace` — without that, ET rewrites to `ns0:` etc. and
    downstream regex tooling breaks.
    """
    _register_ooxml_namespaces()
    try:
        tree = ET.ElementTree(ET.fromstring(raw_bytes))
    except ET.ParseError:
        return raw_bytes
    ET.indent(tree, space="  ", level=0)
    buf = io.BytesIO()
    tree.write(buf, xml_declaration=False, encoding="UTF-8")
    declaration = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    return declaration + buf.getvalue()


def _postprocess_unpacked(outdir: Path, *, pretty: bool, escape_quotes: bool) -> None:
    if not (pretty or escape_quotes):
        return
    for path in outdir.rglob("*"):
        if not path.is_file():
            continue
        # Only process XML-like parts (including .rels).
        suffix = path.suffix.lower()
        if suffix not in {".xml", ".rels"}:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        changed = False
        if pretty:
            new_data = _prettify_xml(data)
            if new_data != data:
                data = new_data
                changed = True
        if escape_quotes:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                continue
            new_text = _escape_smart_quotes(text)
            if new_text != text:
                data = new_text.encode("utf-8")
                changed = True
        if changed:
            path.write_bytes(data)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Unpack a .pptx (zip) file into a directory for XML-level editing.",
    )
    parser.add_argument("--input", required=True, help="Input .pptx path")
    parser.add_argument(
        "--outdir",
        required=True,
        help="Directory to extract into (created if it does not exist)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow extracting into a non-empty outdir",
    )
    parser.add_argument(
        "--pretty-print",
        action="store_true",
        help=(
            "Reformat every .xml/.rels part with 2-space indent. Makes "
            "hand-editing easier; does not change semantics."
        ),
    )
    parser.add_argument(
        "--escape-smart-quotes",
        action="store_true",
        help=(
            "Replace smart quotes, en/em-dashes, and ellipses with XML "
            "numeric entities (&#x201C; etc.) so Edit-tool edits that "
            "normalize unicode don't silently corrupt the glyphs."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    input_path = Path(args.input).expanduser().resolve()
    outdir = Path(args.outdir).expanduser().resolve()

    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 2
    if not input_path.is_file():
        print(f"Error: input is not a file: {input_path}", file=sys.stderr)
        return 2
    if not zipfile.is_zipfile(input_path):
        print(
            f"Error: input is not a valid zip/pptx archive: {input_path}",
            file=sys.stderr,
        )
        return 2

    if outdir.exists():
        if not outdir.is_dir():
            print(
                f"Error: outdir exists and is not a directory: {outdir}",
                file=sys.stderr,
            )
            return 2
        if any(outdir.iterdir()) and not args.overwrite:
            print(
                f"Error: outdir is not empty (use --overwrite to allow): {outdir}",
                file=sys.stderr,
            )
            return 2
    else:
        outdir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(input_path, "r") as zf:
            outdir_resolved = outdir.resolve()
            outdir_prefix = str(outdir_resolved) + os.sep
            # Canonicalize every member against outdir and reject symlinks.
            for zinfo in zf.infolist():
                member = zinfo.filename
                # Reject symlink entries (Unix mode bit in external_attr).
                mode = (zinfo.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    print(
                        f"Error: symlink entries not allowed: {member}",
                        file=sys.stderr,
                    )
                    return 3
                # Reject empty filenames and any absolute paths up front.
                if not member or member.startswith("/") or member.startswith("\\"):
                    print(
                        f"Error: unsafe archive member: {member}",
                        file=sys.stderr,
                    )
                    return 3
                dest = (outdir / member).resolve()
                if (
                    not str(dest).startswith(outdir_prefix)
                    and dest != outdir_resolved
                ):
                    print(
                        f"Error: unsafe archive member: {member}",
                        file=sys.stderr,
                    )
                    return 3
            zf.extractall(outdir)
    except zipfile.BadZipFile as exc:
        print(f"Error: bad zip archive: {exc}", file=sys.stderr)
        return 3

    _postprocess_unpacked(
        outdir,
        pretty=args.pretty_print,
        escape_quotes=args.escape_smart_quotes,
    )

    print(f"Unpacked {input_path} -> {outdir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
