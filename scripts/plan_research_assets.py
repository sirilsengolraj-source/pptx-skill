#!/usr/bin/env python3
"""Create a source-backed visual asset plan from an outline.

This script does not fetch anything. It turns the model's slide plan into a
concrete `asset_plan.json` with Wikimedia Commons queries and, optionally,
updates `outline.json` so selected slides reference the staged aliases.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SKIP_VARIANTS = {
    "generated-image",
    "kpi-hero",
    "table",
    "lab-run-results",
    "flow",
    "chart",
}

QUERY_STOP_WORDS = {
    "a",
    "an",
    "and",
    "brief",
    "context",
    "deck",
    "for",
    "from",
    "introduction",
    "mission",
    "of",
    "overview",
    "presentation",
    "report",
    "slide",
    "slides",
    "strategy",
    "summary",
    "the",
    "to",
    "with",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _slugify(value: str, *, max_len: int = 38) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", value.strip().lower()).strip("_")
    value = re.sub(r"_+", "_", value)
    return (value[:max_len].strip("_") or "visual")


def _clean_query(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"[^\w\s:()+,./-]", "", value)
    return value[:110].strip()


def _query_from(topic: str, title: str) -> str:
    raw_tokens = re.findall(r"[A-Za-z0-9]+", f"{topic} {title}")
    tokens: list[str] = []
    for token in raw_tokens:
        lowered = token.lower()
        if lowered in QUERY_STOP_WORDS and not token.isdigit():
            continue
        if lowered in {t.lower() for t in tokens}:
            continue
        tokens.append(token)
    if len(tokens) >= 2:
        return _clean_query(" ".join(tokens[:9]))
    return _clean_query(f"{topic} {title}")


def _topic_from_outline(outline: dict[str, Any]) -> str:
    for key in ("title", "topic"):
        if isinstance(outline.get(key), str) and outline[key].strip():
            return outline[key].strip()
    slides = outline.get("slides")
    if isinstance(slides, list):
        for slide in slides:
            if isinstance(slide, dict) and str(slide.get("title") or "").strip():
                return str(slide["title"]).strip()
    return "presentation topic"


def _is_stub_asset_plan(plan: dict[str, Any]) -> bool:
    return "__readme__" in plan and all(
        not plan.get(key)
        for key in ("images", "backgrounds", "charts", "generated_images", "icons")
    )


def _has_image_asset(slide: dict[str, Any]) -> bool:
    assets = slide.get("assets")
    if not isinstance(assets, dict):
        return False
    return any(
        assets.get(key)
        for key in ("hero_image", "image", "generated_image", "background_image")
    )


def _slide_score(slide: dict[str, Any], idx: int) -> int:
    if str(slide.get("type") or "content").strip().lower() != "content":
        return -100
    if _has_image_asset(slide):
        return -100

    variant = str(slide.get("variant") or "standard").strip().lower()
    if variant in SKIP_VARIANTS:
        return -100

    score = 0
    intent = str(slide.get("visual_intent") or "").strip().lower()
    if intent in {"hero", "image", "figure", "photo", "artifact"}:
        score += 8
    if variant in {"image-sidebar", "scientific-figure"}:
        score += 7
    if variant in {"standard", "split", "content", ""}:
        score += 4
    if variant in {"cards-2", "cards-3", "matrix", "stats"}:
        score += 1

    text = " ".join(
        str(slide.get(key) or "")
        for key in ("title", "subtitle", "body", "caption")
    ).lower()
    if any(
        word in text
        for word in (
            "origin",
            "architecture",
            "pipeline",
            "mechanism",
            "mission",
            "system",
            "landscape",
            "horizon",
            "context",
            "overview",
            "figure",
            "readout",
        )
    ):
        score += 3
    if idx <= 3:
        score += 1
    return score


def _candidate_slides(outline: dict[str, Any], max_images: int) -> list[tuple[int, dict[str, Any]]]:
    slides = outline.get("slides")
    if not isinstance(slides, list):
        return []
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for idx, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            continue
        score = _slide_score(slide, idx)
        if score > 0:
            scored.append((score, idx, slide))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [(idx, slide) for _, idx, slide in scored[:max_images]]


def _source_entry(topic: str, idx: int, slide: dict[str, Any]) -> dict[str, Any]:
    title = str(slide.get("title") or f"slide {idx}").strip()
    explicit_query = (
        slide.get("wikimedia_query")
        or slide.get("image_query")
        or slide.get("asset_query")
    )
    query = _clean_query(str(explicit_query)) if explicit_query else _query_from(topic, title)
    name = f"source_s{idx:02d}_{_slugify(title)}"
    return {
        "name": name,
        "wikimedia_query": query,
        "limit": 16,
        "allow_sharealike": True,
        "target_slide": idx,
        "intended_use": "source-backed slide visual",
    }


def _append_unique(items: list[Any], value: Any) -> list[Any]:
    if value not in items:
        items.append(value)
    return items


def _sidebar_sections_from_slide(slide: dict[str, Any]) -> list[dict[str, Any]]:
    existing = slide.get("sidebar_sections")
    if isinstance(existing, list) and existing:
        return existing

    sections: list[dict[str, Any]] = []
    body = str(slide.get("body") or "").strip()
    bullets = slide.get("bullets")
    highlights = slide.get("highlights")
    if body:
        sections.append({"title": "Readout", "body": body})
    if isinstance(bullets, list):
        clean = [
            item if isinstance(item, str) else str(item.get("text") or "").strip()
            for item in bullets
            if isinstance(item, (str, dict))
        ]
        clean = [item.strip() for item in clean if item and item.strip()]
        if clean:
            sections.append({"title": "Key points", "body": clean[:4]})
    if isinstance(highlights, list):
        clean = [str(item).strip() for item in highlights if str(item).strip()]
        if clean:
            sections.append({"title": "Interpretation", "body": clean[:4]})
    if not sections:
        sections.append(
            {
                "title": "Visual note",
                "body": "Source-backed image staged from asset_plan.json.",
            }
        )
    if len(sections) == 1:
        sections.append(
            {
                "title": "Attribution",
                "body": "Full image credit appears on the Image Sources slide.",
            }
        )
    return sections[:4]


def _apply_to_slide(slide: dict[str, Any], entry: dict[str, Any]) -> None:
    name = str(entry["name"])
    alias = f"image:{name}"
    variant = str(slide.get("variant") or "standard").strip().lower()
    assets = slide.setdefault("assets", {})
    if not isinstance(assets, dict):
        assets = {}
        slide["assets"] = assets

    if variant == "scientific-figure":
        figures = slide.get("figures")
        if not isinstance(figures, list) or not figures:
            slide["figures"] = [
                {
                    "path": alias,
                    "label": "A",
                    "title": str(slide.get("title") or "Source-backed visual"),
                    "caption": "Source-backed image staged from asset_plan.json.",
                }
            ]
        else:
            first = figures[0]
            if isinstance(first, dict) and not first.get("path"):
                first["path"] = alias
            elif isinstance(first, str):
                figures[0] = {"path": alias, "label": "A", "caption": first}
        slide.setdefault(
            "caption",
            "Source-backed figure. Full attribution appears on the Image Sources slide.",
        )
    else:
        slide["variant"] = "image-sidebar"
        assets["image"] = alias
        slide["sidebar_sections"] = _sidebar_sections_from_slide(slide)
        slide.setdefault(
            "caption",
            "Source-backed image. Full attribution appears on the Image Sources slide.",
        )

    sources = slide.get("sources")
    if not isinstance(sources, list):
        sources = []
        slide["sources"] = sources
    _append_unique(sources, "Image attribution: assets/attribution.csv")


def _plan_payload(topic: str, outline: dict[str, Any], max_images: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    selected = _candidate_slides(outline, max_images)
    images = [_source_entry(topic, idx, slide) for idx, slide in selected]
    return (
        {
            "topic": topic,
            "research_visual_mode": True,
            "images": images,
            "backgrounds": [],
            "charts": [],
            "generated_images": [],
            "icons": [],
            "visual_strategy": {
                "mode": "source-backed",
                "policy": (
                    "Wikimedia Commons assets are staged only when the build is run "
                    "with --allow-network-assets. Exact credits are written to "
                    "assets/attribution.csv and an Image Sources slide."
                ),
            },
        },
        images,
    )


def _workspace_paths(workspace: Path) -> tuple[Path, Path]:
    manifest = _load_json(workspace / "workspace.json")
    return workspace / manifest["outline"], workspace / manifest.get("asset_plan", "asset_plan.json")


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan source-backed visual assets for a deck workspace.")
    parser.add_argument("--workspace", help="Workspace containing workspace.json")
    parser.add_argument("--outline", help="Path to outline.json when not using --workspace")
    parser.add_argument("--asset-plan", help="Path to asset_plan.json when not using --workspace")
    parser.add_argument("--max-images", type=int, default=2, help="Maximum Wikimedia image requests to create")
    parser.add_argument("--apply-to-outline", action="store_true", help="Update selected slides to reference staged aliases")
    parser.add_argument("--overwrite", action="store_true", help="Replace a non-stub asset_plan.json")
    parser.add_argument("--report", help="Optional JSON report path")
    return parser.parse_args()


def main() -> int:
    args = _args()
    if args.workspace:
        workspace = Path(args.workspace).expanduser().resolve()
        outline_path, asset_plan_path = _workspace_paths(workspace)
    else:
        if not args.outline or not args.asset_plan:
            raise SystemExit("--outline and --asset-plan are required without --workspace")
        outline_path = Path(args.outline).expanduser().resolve()
        asset_plan_path = Path(args.asset_plan).expanduser().resolve()

    outline = _load_json(outline_path)
    topic = _topic_from_outline(outline)
    existing = _load_json(asset_plan_path) if asset_plan_path.exists() else {}
    existing_is_stub = not existing or _is_stub_asset_plan(existing)
    if existing and not existing_is_stub and not args.overwrite:
        report = {
            "changed": False,
            "reason": "asset_plan_not_stub",
            "asset_plan": str(asset_plan_path),
        }
        if args.report:
            _write_json(Path(args.report).expanduser().resolve(), report)
        print(json.dumps(report, indent=2))
        return 0

    plan, images = _plan_payload(topic, outline, max(0, int(args.max_images or 0)))
    _write_json(asset_plan_path, plan)

    if args.apply_to_outline and images:
        by_slide = {int(entry["target_slide"]): entry for entry in images}
        for idx, slide in enumerate(outline.get("slides") or [], start=1):
            if isinstance(slide, dict) and idx in by_slide:
                _apply_to_slide(slide, by_slide[idx])
        deck_style = outline.setdefault("deck_style", {})
        if isinstance(deck_style, dict):
            deck_style["research_visual_mode"] = True
        compliance = outline.setdefault("compliance", {})
        if isinstance(compliance, dict):
            compliance.setdefault("attribution_file", "assets/attribution.csv")
            compliance.setdefault("auto_image_sources", True)
            compliance.setdefault("require_attribution", True)
        _write_json(outline_path, outline)

    report = {
        "changed": True,
        "outline": str(outline_path),
        "asset_plan": str(asset_plan_path),
        "image_count": len(images),
        "images": images,
        "applied_to_outline": bool(args.apply_to_outline and images),
    }
    if args.report:
        _write_json(Path(args.report).expanduser().resolve(), report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
