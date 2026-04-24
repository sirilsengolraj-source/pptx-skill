#!/usr/bin/env python3
"""Stage source-backed deck assets into a local manifest."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any

from fetch_wikimedia_cc import search_and_download
from generate_openai_image import DEFAULT_FORMAT, DEFAULT_MODEL, DEFAULT_QUALITY, DEFAULT_SIZE, generate_image
from palette_from_topic import choose_palette_for_topic


ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value).strip("_")


def _write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _copy_local_asset(src: Path, target_dir: Path, name: str) -> Path:
    suffix = src.suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise RuntimeError(
            f"Unsupported local asset format for {src.name}. "
            "Use PNG or JPG/JPEG for the open-source-safe staging path."
        )
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{name}{suffix}"
    shutil.copy2(src, target)
    return target


def _metadata_payload(spec: dict[str, Any], *, provider: str, source: str | None = None) -> dict[str, Any]:
    return {
        "provider": provider,
        "source": source,
        "source_note": spec.get("source_note"),
        "source_url": spec.get("source_url"),
        "source_page": spec.get("source_page"),
        "license": spec.get("license"),
        "license_url": spec.get("license_url"),
        "artist": spec.get("artist"),
        "credit": spec.get("credit"),
        "provenance": spec.get("provenance") or provider,
        "generated": bool(spec.get("generated")),
    }


def _write_metadata(target: Path, metadata: dict[str, Any]) -> Path:
    metadata_path = Path(f"{target}.metadata.json")
    _write_json(metadata_path, metadata)
    return metadata_path


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_provenance(spec: dict[str, Any], *, name: str) -> None:
    if bool(spec.get("generated")):
        raise RuntimeError(f"Asset '{name}' is marked generated. Use source-backed or licensed assets instead.")
    required = ("source_note", "source_url", "source_page", "license", "provenance")
    if not any(spec.get(key) for key in required):
        raise RuntimeError(
            f"Asset '{name}' is missing provenance metadata. "
            "Provide at least one of source_note, source_url, source_page, license, or provenance."
        )


def _row_for_asset(
    *,
    target: Path,
    title: str,
    query: str = "",
    source_page: str = "",
    source_url: str = "",
    license_name: str = "",
    license_url: str = "",
    artist: str = "",
    credit: str = "",
) -> dict[str, str]:
    return {
        "file_name": target.name,
        "file_path": str(target),
        "title": title,
        "source_page": source_page,
        "image_url": source_url,
        "license": license_name,
        "license_url": license_url,
        "artist": artist,
        "credit": credit,
        "query": query,
    }


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
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _stage_local_or_remote(
    entries: list[dict[str, Any]],
    *,
    kind: str,
    output_dir: Path,
    attribution_rows: list[dict[str, str]],
    allow_network: bool,
    strict_provenance: bool,
) -> list[dict[str, Any]]:
    staged: list[dict[str, Any]] = []
    kind_dir = output_dir / kind
    kind_dir.mkdir(parents=True, exist_ok=True)

    for index, spec in enumerate(entries):
        name = _safe_name(str(spec.get("name") or f"{kind}_{index + 1}")) or f"{kind}_{index + 1}"
        if spec.get("path"):
            if strict_provenance:
                _ensure_provenance(spec, name=name)
            src = Path(str(spec["path"])).expanduser().resolve()
            if not src.exists():
                raise FileNotFoundError(f"Asset path not found for '{name}': {src}")
            target = _copy_local_asset(src, kind_dir, name)
            metadata_path = _write_metadata(target, _metadata_payload(spec, provider="local_file", source=str(src)))
            attribution_rows.append(
                _row_for_asset(
                    target=target,
                    title=str(spec.get("title") or name),
                    source_page=str(spec.get("source_page") or ""),
                    source_url=str(spec.get("source_url") or src),
                    license_name=str(spec.get("license") or ""),
                    license_url=str(spec.get("license_url") or ""),
                    artist=str(spec.get("artist") or ""),
                    credit=str(spec.get("credit") or ""),
                )
            )
            staged.append(
                {
                    "kind": kind,
                    "name": name,
                    "path": str(target),
                    "metadata_path": str(metadata_path),
                    "source": str(src),
                }
            )
            continue

        if spec.get("wikimedia_query"):
            if not allow_network:
                raise RuntimeError(
                    f"Asset '{name}' requests Wikimedia fetches. Re-run with --allow-network."
                )
            result = search_and_download(
                str(spec["wikimedia_query"]),
                kind_dir,
                limit=int(spec.get("limit", 12)),
                allow_sharealike=bool(spec.get("allow_sharealike", True)),
                name=name,
            )
            target = Path(result["image_path"]).resolve()
            metadata_path = Path(result["metadata_path"]).resolve()
            attribution_rows.append(
                _row_for_asset(
                    target=target,
                    title=result["title"],
                    query=str(spec["wikimedia_query"]),
                    source_page=result["source_page"],
                    source_url=result["image_url"],
                    license_name=result["license"],
                    license_url=result["license_url"],
                    artist=result["artist"],
                    credit=result["credit"],
                )
            )
            staged.append(
                {
                    "kind": kind,
                    "name": name,
                    "path": str(target),
                    "metadata_path": str(metadata_path),
                    "source_query": str(spec["wikimedia_query"]),
                    "source_page": result["source_page"],
                    "license": result["license"],
                }
            )
            continue

        raise RuntimeError(f"Asset '{name}' must specify either 'path' or 'wikimedia_query'.")

    return staged


def _stage_charts(charts: list[dict[str, Any]], output_dir: Path) -> list[dict[str, Any]]:
    chart_dir = output_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    staged: list[dict[str, Any]] = []
    for index, spec in enumerate(charts):
        name = _safe_name(str(spec.get("name") or f"chart_{index + 1}")) or f"chart_{index + 1}"
        target = chart_dir / f"{name}.json"
        if spec.get("path"):
            src = Path(str(spec["path"])).expanduser().resolve()
            if not src.exists():
                raise FileNotFoundError(f"Chart path not found for '{name}': {src}")
            payload = json.loads(src.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise RuntimeError(f"Chart JSON must decode to an object: {src}")
        else:
            payload = dict(spec)
        payload["name"] = name
        payload.pop("path", None)
        _write_json(target, payload)
        staged.append({"kind": "chart", "name": name, "path": str(target)})
    return staged


def _stage_generated_images(
    entries: list[dict[str, Any]],
    *,
    output_dir: Path,
    allow_generation: bool,
    attribution_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    generated_dir = output_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    staged: list[dict[str, Any]] = []
    for index, spec in enumerate(entries):
        name = _safe_name(str(spec.get("name") or f"generated_{index + 1}")) or f"generated_{index + 1}"
        output_format = str(spec.get("output_format") or DEFAULT_FORMAT).strip().lower().lstrip(".")
        if output_format not in {"png", "webp", "jpg", "jpeg"}:
            raise RuntimeError(f"Generated image '{name}' has unsupported output_format: {output_format}")
        target = generated_dir / f"{name}.{output_format}"

        if spec.get("path"):
            src = Path(str(spec["path"])).expanduser().resolve()
            if not src.exists():
                raise FileNotFoundError(f"Generated image path not found for '{name}': {src}")
            target = _copy_local_asset(src, generated_dir, name)
            metadata_path = _write_metadata(
                target,
                _metadata_payload(spec, provider="generated_openai_image", source=str(src))
                | {
                    "generated": True,
                    "prompt": spec.get("prompt"),
                    "model": spec.get("model"),
                    "purpose": spec.get("purpose"),
                    "edit_note": spec.get("edit_note"),
                },
            )
        else:
            prompt = str(spec.get("prompt") or "").strip()
            if not prompt:
                raise RuntimeError(f"Generated image '{name}' must specify either 'path' or 'prompt'.")
            if not allow_generation:
                raise RuntimeError(
                    f"Generated image '{name}' requires an OpenAI API call. "
                    "Re-run with --allow-generated-images."
                )
            result = generate_image(
                prompt=prompt,
                output=target,
                metadata_path=Path(f"{target}.metadata.json"),
                model=str(spec.get("model") or DEFAULT_MODEL),
                size=str(spec.get("size") or DEFAULT_SIZE),
                quality=str(spec.get("quality") or DEFAULT_QUALITY),
                output_format=output_format,
                background=str(spec.get("background") or "auto"),
                purpose=str(spec.get("purpose") or ""),
                edit_note=str(spec.get("edit_note") or ""),
            )
            metadata_path = Path(result["metadata_path"]).resolve()

        attribution_rows.append(
            _row_for_asset(
                target=target,
                title=str(spec.get("title") or name),
                source_page=str(spec.get("source_page") or "OpenAI Images API"),
                source_url=str(spec.get("source_url") or ""),
                license_name=str(spec.get("license") or "Generated asset"),
                license_url=str(spec.get("license_url") or ""),
                artist=str(spec.get("artist") or "OpenAI image model"),
                credit=str(spec.get("credit") or "Generated image"),
                query=str(spec.get("prompt") or ""),
            )
        )
        staged.append(
            {
                "kind": "generated_image",
                "name": name,
                "path": str(target.resolve()),
                "metadata_path": str(metadata_path),
                "generated": True,
                "model": str(spec.get("model") or DEFAULT_MODEL),
                "purpose": str(spec.get("purpose") or ""),
            }
        )
    return staged


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage source-backed deck assets into a reusable manifest.")
    parser.add_argument("--manifest", required=True, help="JSON manifest describing images/backgrounds/charts")
    parser.add_argument("--output-dir", required=True, help="Directory for staged assets")
    parser.add_argument("--attribution-csv", help="CSV file to write attribution rows")
    parser.add_argument("--allow-network", action="store_true", help="Allow Wikimedia Commons fetches")
    parser.add_argument(
        "--allow-generated-images",
        action="store_true",
        help="Allow OpenAI Images API calls for manifest.generated_images entries",
    )
    parser.add_argument(
        "--strict-provenance",
        action="store_true",
        help="Reject local assets that lack source/provenance metadata",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    manifest = _load_manifest(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    topic = str(manifest.get("topic") or manifest.get("palette_topic") or "general presentation").strip()
    palette_payload = choose_palette_for_topic(topic)
    palette_path = output_dir / "palette.json"
    _write_json(palette_path, palette_payload)

    attribution_rows: list[dict[str, str]] = []
    images = _stage_local_or_remote(
        list(manifest.get("images", [])),
        kind="images",
        output_dir=output_dir,
        attribution_rows=attribution_rows,
        allow_network=args.allow_network,
        strict_provenance=args.strict_provenance,
    )
    backgrounds = _stage_local_or_remote(
        list(manifest.get("backgrounds", [])),
        kind="backgrounds",
        output_dir=output_dir,
        attribution_rows=attribution_rows,
        allow_network=args.allow_network,
        strict_provenance=args.strict_provenance,
    )
    charts = _stage_charts(list(manifest.get("charts", [])), output_dir)
    generated_images = _stage_generated_images(
        list(manifest.get("generated_images", [])),
        output_dir=output_dir,
        allow_generation=args.allow_generated_images,
        attribution_rows=attribution_rows,
    )

    attribution_csv = (
        Path(args.attribution_csv).expanduser().resolve()
        if args.attribution_csv
        else output_dir.parent / "attribution.csv"
    )
    _write_attribution_csv(attribution_csv, attribution_rows)

    staged_manifest = {
        "workspace_assets_version": 1,
        "topic": topic,
        "palette_path": str(palette_path),
        "palette": palette_payload,
        "images": images,
        "backgrounds": backgrounds,
        "charts": charts,
        "generated_images": generated_images,
        "attribution_csv": str(attribution_csv),
    }
    staged_manifest_path = output_dir / "staged_manifest.json"
    _write_json(staged_manifest_path, staged_manifest)
    print(json.dumps({"staged_manifest": str(staged_manifest_path), **staged_manifest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
