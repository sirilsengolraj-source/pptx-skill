#!/usr/bin/env python3
"""Remove orphaned files from an unpacked PPTX directory.

After editing an unpacked .pptx (typically via `unpack_pptx.py` → hand-edit
→ `pack_pptx.py`), the directory may contain files no longer referenced
from presentation.xml / rels graphs. Packing orphans back in bloats the
deck and can confuse some consumers. This pass removes them.

What it cleans:
- Slides not in presentation.xml's <p:sldIdLst> (+ matching .rels)
- [trash]/ directory
- Media, embeddings, charts, diagrams, tags, drawings, ink not reachable
  from any slide's rels graph
- Theme files not referenced in rels
- Notes slides with no corresponding content slide
- Orphan .rels files whose target resource no longer exists
- Matching <Override> entries in [Content_Types].xml

Loops until no further orphans are removed (removing a resource may
unreference another).

Usage:
    python3 clean_unpacked.py --input /path/to/unpacked_dir [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

_REL_ROOT = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_CT_ROOT = "{http://schemas.openxmlformats.org/package/2006/content-types}"
_PML = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_REL_OFFICE = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


# Register default namespaces so ElementTree serializes them with
# `xmlns=` instead of `ns0:` / `ns1:` prefixes. Without this,
# presentation.xml.rels ends up with `<ns0:Relationships>`, which
# breaks downstream regex-based editors (e.g., add_slide.py looking
# for `</Relationships>`) and mismatches PowerPoint's expected form.
ET.register_namespace("", "http://schemas.openxmlformats.org/package/2006/relationships")
ET.register_namespace(
    "pkg_ct",
    "http://schemas.openxmlformats.org/package/2006/content-types",
)
# Content-Types.xml specifically uses the ct namespace as DEFAULT
# (xmlns="..."), so we re-register at write-time as empty for that file.

ET.register_namespace("p", "http://schemas.openxmlformats.org/presentationml/2006/main")
ET.register_namespace("a", "http://schemas.openxmlformats.org/drawingml/2006/main")
ET.register_namespace(
    "r",
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
)


def _parse(path: Path) -> ET.ElementTree:
    return ET.parse(str(path))


def _write(tree: ET.ElementTree, path: Path) -> None:
    # ElementTree emits its own XML declaration but without standalone="yes"
    # which PPTX consumers expect. Write to a buffer and prepend the
    # canonical declaration manually.
    import io

    # [Content_Types].xml uses the content-types namespace as the default
    # (xmlns=...). Swap our default-prefix registration right before
    # writing so the serialized output matches PowerPoint's expected form.
    if path.name == "[Content_Types].xml":
        ET.register_namespace(
            "",
            "http://schemas.openxmlformats.org/package/2006/content-types",
        )
    else:
        ET.register_namespace(
            "",
            "http://schemas.openxmlformats.org/package/2006/relationships",
        )

    buf = io.BytesIO()
    tree.write(buf, xml_declaration=False, encoding="UTF-8")
    declaration = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    path.write_bytes(declaration + buf.getvalue())


def _relationships(rels_path: Path) -> list[tuple[str, str, str]]:
    """Return list of (Id, Type, Target) for a .rels file. [] if missing."""
    if not rels_path.exists():
        return []
    tree = _parse(rels_path)
    out: list[tuple[str, str, str]] = []
    for rel in tree.getroot().findall(f"{_REL_ROOT}Relationship"):
        out.append(
            (
                rel.get("Id", ""),
                rel.get("Type", ""),
                rel.get("Target", ""),
            )
        )
    return out


def _slides_in_sldidlst(unpacked: Path) -> set[str]:
    pres = unpacked / "ppt" / "presentation.xml"
    pres_rels = unpacked / "ppt" / "_rels" / "presentation.xml.rels"
    if not pres.exists() or not pres_rels.exists():
        return set()

    rid_to_slide: dict[str, str] = {}
    for rid, rtype, target in _relationships(pres_rels):
        if "slide" in rtype and target.startswith("slides/"):
            rid_to_slide[rid] = target[len("slides/"):]

    referenced: set[str] = set()
    tree = _parse(pres)
    sld_id_lst = tree.getroot().find(f"{_PML}sldIdLst")
    if sld_id_lst is None:
        return referenced
    for sld_id in sld_id_lst.findall(f"{_PML}sldId"):
        rid = sld_id.get(f"{_REL_OFFICE}id") or sld_id.get("r:id") or ""
        if rid in rid_to_slide:
            referenced.add(rid_to_slide[rid])
    return referenced


def _remove_orphaned_slides(unpacked: Path, removed: list[Path]) -> None:
    slides_dir = unpacked / "ppt" / "slides"
    if not slides_dir.exists():
        return
    keep = _slides_in_sldidlst(unpacked)
    for slide_file in slides_dir.glob("slide*.xml"):
        if slide_file.name not in keep:
            removed.append(slide_file)
            slide_file.unlink()
            rels_file = slides_dir / "_rels" / f"{slide_file.name}.rels"
            if rels_file.exists():
                removed.append(rels_file)
                rels_file.unlink()

    # Drop matching <Relationship> entries from presentation.xml.rels.
    pres_rels = unpacked / "ppt" / "_rels" / "presentation.xml.rels"
    if not pres_rels.exists():
        return
    tree = _parse(pres_rels)
    root = tree.getroot()
    changed = False
    for rel in list(root.findall(f"{_REL_ROOT}Relationship")):
        target = rel.get("Target", "")
        if target.startswith("slides/") and target[len("slides/"):] not in keep:
            root.remove(rel)
            changed = True
    if changed:
        _write(tree, pres_rels)


def _remove_trash(unpacked: Path, removed: list[Path]) -> None:
    trash = unpacked / "[trash]"
    if trash.exists() and trash.is_dir():
        for f in sorted(trash.rglob("*")):
            if f.is_file():
                removed.append(f)
                f.unlink()
        # Remove now-empty directories deepest-first.
        for d in sorted(trash.rglob("*"), reverse=True):
            if d.is_dir():
                try:
                    d.rmdir()
                except OSError:
                    pass
        try:
            trash.rmdir()
        except OSError:
            pass


def _all_referenced_parts(unpacked: Path) -> set[Path]:
    """Walk every .rels file and return the set of referenced file paths
    (relative to unpacked/ root, resolved), so an orphan pass can compare.
    """
    referenced: set[Path] = set()
    root = unpacked.resolve()
    for rels_file in unpacked.rglob("*.rels"):
        try:
            rels = _relationships(rels_file)
        except ET.ParseError:
            continue
        for _, _, target in rels:
            if not target:
                continue
            # External (mode="External") relationships won't resolve locally.
            if target.startswith("http://") or target.startswith("https://"):
                continue
            target_path = (rels_file.parent.parent / target).resolve()
            try:
                referenced.add(target_path.relative_to(root))
            except ValueError:
                pass
    return referenced


def _remove_orphan_resources(unpacked: Path, removed: list[Path]) -> int:
    """Remove unreferenced files in ppt/media, embeddings, charts, diagrams,
    tags, drawings, ink, notesSlides, and theme. Returns count removed.
    """
    referenced = _all_referenced_parts(unpacked)
    count = 0
    resource_dirs = [
        "media",
        "embeddings",
        "charts",
        "diagrams",
        "tags",
        "drawings",
        "ink",
    ]
    for name in resource_dirs:
        rdir = unpacked / "ppt" / name
        if not rdir.exists():
            continue
        for f in rdir.glob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(unpacked)
            if rel not in referenced:
                removed.append(f)
                f.unlink()
                count += 1

    # Theme files.
    theme_dir = unpacked / "ppt" / "theme"
    if theme_dir.exists():
        for f in theme_dir.glob("theme*.xml"):
            rel = f.relative_to(unpacked)
            if rel not in referenced:
                removed.append(f)
                f.unlink()
                count += 1
                # Matching theme rels.
                theme_rels = theme_dir / "_rels" / f"{f.name}.rels"
                if theme_rels.exists():
                    removed.append(theme_rels)
                    theme_rels.unlink()
                    count += 1

    # Notes slides whose corresponding content slide is gone.
    notes_dir = unpacked / "ppt" / "notesSlides"
    if notes_dir.exists():
        for f in notes_dir.glob("*.xml"):
            rel = f.relative_to(unpacked)
            if rel not in referenced:
                removed.append(f)
                f.unlink()
                count += 1
        notes_rels_dir = notes_dir / "_rels"
        if notes_rels_dir.exists():
            for rf in notes_rels_dir.glob("*.rels"):
                corresponding = notes_dir / rf.name.replace(".rels", "")
                if not corresponding.exists():
                    removed.append(rf)
                    rf.unlink()
                    count += 1
    return count


def _remove_orphan_rels(unpacked: Path, removed: list[Path]) -> int:
    """Remove .rels files whose target resource file no longer exists."""
    count = 0
    for rels_file in unpacked.rglob("*.rels"):
        target_base = rels_file.name.replace(".rels", "")
        if target_base == "":
            continue
        expected = rels_file.parent.parent / target_base
        # presentation.xml.rels, *.xml.rels variants — keep if the target exists.
        if target_base.endswith(".xml") and expected.exists():
            continue
        # chart1.xml.rels etc — check if the chart1.xml still exists.
        if expected.exists() or expected.is_file():
            continue
        removed.append(rels_file)
        rels_file.unlink()
        count += 1
    return count


def _update_content_types(unpacked: Path, removed_files: list[Path]) -> None:
    ct_path = unpacked / "[Content_Types].xml"
    if not ct_path.exists():
        return
    tree = _parse(ct_path)
    root = tree.getroot()
    removed_parts = {f"/{p.relative_to(unpacked).as_posix()}" for p in removed_files}
    changed = False
    for override in list(root.findall(f"{_CT_ROOT}Override")):
        part_name = override.get("PartName", "")
        if part_name in removed_parts:
            root.remove(override)
            changed = True
    if changed:
        _write(tree, ct_path)


def clean(unpacked: Path, *, dry_run: bool = False) -> list[Path]:
    removed: list[Path] = []
    if dry_run:
        # Run through without mutating: compute what would go and return it.
        # Simplest approach: do a real pass into a copy-on-write sandbox
        # later if we add it. For v1, dry_run is the same pass without
        # writing — we don't delete in dry-run, so we cheat by collecting
        # candidates via a shadow list. Keep simple: dry-run unsupported
        # for v1, raise instead of silently deleting.
        raise NotImplementedError("--dry-run not yet implemented")

    _remove_orphaned_slides(unpacked, removed)
    _remove_trash(unpacked, removed)

    # Iterate until no further orphans — removing a file can free its .rels
    # which can free another resource.
    while True:
        pass_removed_before = len(removed)
        _remove_orphan_resources(unpacked, removed)
        _remove_orphan_rels(unpacked, removed)
        if len(removed) == pass_removed_before:
            break

    if removed:
        _update_content_types(unpacked, removed)
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove orphaned files from an unpacked PPTX directory."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to unpacked PPTX directory (from unpack_pptx.py)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-file removal log on stdout.",
    )
    args = parser.parse_args()

    unpacked = Path(args.input).expanduser().resolve()
    if not unpacked.exists() or not unpacked.is_dir():
        print(f"Error: {unpacked} not found or not a directory", file=sys.stderr)
        return 1

    removed = clean(unpacked)
    if removed:
        if not args.quiet:
            print(f"Removed {len(removed)} unreferenced file(s):")
            for f in removed:
                try:
                    print(f"  {f.relative_to(unpacked)}")
                except ValueError:
                    print(f"  {f}")
        else:
            print(f"Removed {len(removed)} unreferenced file(s)")
    else:
        print("No unreferenced files found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
