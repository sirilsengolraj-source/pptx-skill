#!/usr/bin/env python3
"""Emit a ready-to-paste subagent prompt for pre-build outline critique.

The prompt points at design_philosophy.md + outline_schema.md (authoritative
refs) plus the concrete outline under review, so the critiquing subagent
applies the skill's rules rather than its own priors.

Pair this with render_slides.py --emit-visual-prompt: run outline critique
before build, visual QA after render. Together they cover editorial
issues (outline level) and composition issues (rendered level).

Usage:
    python3 scripts/emit_outline_critique.py --outline outline.json
    python3 scripts/emit_outline_critique.py --outline outline.json \\
        --style-preset forest-research
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def _summarize_outline(outline: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    title = outline.get("title", "<untitled>")
    subtitle = outline.get("subtitle", "")
    deck_style = outline.get("deck_style", {}) or {}
    slides = outline.get("slides", []) or []

    lines.append(f"Deck title: {title}")
    if subtitle:
        lines.append(f"Deck subtitle: {subtitle}")
    lines.append(
        f"deck_style: font_pair={deck_style.get('font_pair', '<default>')}, "
        f"palette_key={deck_style.get('palette_key', '<default>')}, "
        f"title_motif={deck_style.get('title_motif', '<auto>')}"
    )
    lines.append("")

    variant_counts: Counter[str] = Counter()
    for idx, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        stype = slide.get("type", "content")
        variant = (slide.get("variant") or "").strip() or "-"
        if stype == "content":
            variant_counts[variant] += 1
        slide_title = slide.get("title", "")
        intent = slide.get("slide_intent", "")
        visual_intent = slide.get("visual_intent", "")
        has_icons = bool(
            isinstance(slide.get("assets"), dict)
            and slide["assets"].get("icons")
        )
        has_hero = bool(
            isinstance(slide.get("assets"), dict)
            and slide["assets"].get("hero_image")
        )
        theme = slide.get("theme", "")
        promote = slide.get("promote_card")
        flags = []
        if has_icons:
            flags.append("icons")
        if has_hero:
            flags.append("hero_image")
        if theme:
            flags.append(f"theme={theme}")
        if promote is not None:
            flags.append(f"promote_card={promote}")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        lines.append(
            f"slide {idx:02d}: type={stype} variant={variant} "
            f"intent={intent or '-'} visual={visual_intent or '-'}"
            f"{flag_str}"
        )
        if slide_title:
            lines.append(f"    title: {slide_title}")
    lines.append("")
    lines.append("variant histogram (content slides):")
    for variant, count in variant_counts.most_common():
        lines.append(f"  {variant}: {count}")
    return lines


_PROMPT_HEADER = """\
You are critiquing an outline.json BEFORE the .pptx builder runs. Catch
editorial issues the automated preflight + layout_lint can't see: monotony,
missing visual elements, weak palette choice, text-heavy slides that would
work better in a rhythm-breaking variant.

Read these refs FIRST (they're the skill's authoritative rules — apply
them, don't invent your own criteria):
- {design_philosophy}
- {outline_schema}
- {subagent_patterns}

Then analyze the outline below.

Look specifically for:

1. Layout monotony AND variant overuse. Both are failure modes:
   - **Monotony**: a variant appears 3+ times in a row, or 4+ times
     overall in a ≤10-slide deck. Flag candidate slides where a
     rhythm-breaker (kpi-hero / promote_card / theme:dark) fits.
   - **Overuse**: the deck uses 5+ distinct variants in 6-8 slides,
     i.e., Codex cycled the menu instead of picking thoughtfully. Flag
     which 2-3 variants actually fit the topic's voice and recommend
     retiring the rest. An editorial primer doesn't need a matrix; a
     research brief doesn't need comparison-2col unless there's an
     actual A-vs-B argument. Topic shape decides the variant set.
2. Text-only slides. Every content slide needs a visual element
   (assets.icons / assets.hero_image / chart / stats / matrix / timeline).
   Preflight flags this with `icons_absent_enrichment_hint` on
   cards-2/3/matrix/stats/timeline; expand the check here to
   standard/split variants too.
3. Palette fit. Is `deck_style.palette_key` absent or left at default?
   If the deck topic has a clear mood (climate → forest-research,
   executive strategy → executive-clinical, incident/risk →
   charcoal-safety), name the preset that fits. Don't pick a mood name
   from the palette moods inspiration table — only the loadable presets
   listed at the top of design_philosophy.md.
4. KPI candidates. If any content slide's `body` or `bullets` highlight
   a single number as the anchor claim, flag it as a kpi-hero candidate.
5. Comparison candidates. If any slide argues "A vs B" (before/after,
   us/them, hypothesis/result), flag it as comparison-2col. Currently-
   split slides with `highlights` often read better as comparison-2col.
6. Hero-opener gap. If the title slide lacks `assets.hero_image` and the
   deck has a clear visual anchor (a product, a geography, a specific
   dataset), suggest staging a hero image.
7. Source citations. If 3+ consecutive evidence slides have no `sources`
   array, flag them (parallels preflight's `sources_missing_streak`).

For each issue, output:
- slide index (or "deck" for deck-level issues)
- specific recommendation (what variant / asset / preset to change to)
- why (cite the design_philosophy rule or the data pattern you observed)

Don't rewrite the outline. Produce a punch list the author can apply.
Under 400 words. Be direct — if the outline is fine, say so in one
sentence.

--- Outline summary ---

{summary}

--- Full outline.json for reference ---

{outline_json}
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit a subagent prompt for pre-build outline critique."
    )
    parser.add_argument("--outline", required=True, help="Path to outline.json")
    parser.add_argument(
        "--output",
        help="Write the prompt to this file instead of stdout.",
    )
    parser.add_argument(
        "--truncate-outline",
        type=int,
        default=8000,
        help="Max chars of outline.json to inline (default 8000; large "
        "decks get truncated with a pointer to the full path).",
    )
    args = parser.parse_args()

    outline_path = Path(args.outline).expanduser().resolve()
    if not outline_path.exists():
        print(f"Error: outline not found: {outline_path}", file=sys.stderr)
        return 1
    try:
        outline = json.loads(outline_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Error: outline JSON malformed: {exc}", file=sys.stderr)
        return 2

    summary = "\n".join(_summarize_outline(outline))

    repo_root = Path(__file__).resolve().parent.parent
    refs = {
        "design_philosophy": str(repo_root / "references" / "design_philosophy.md"),
        "outline_schema": str(repo_root / "references" / "outline_schema.md"),
        "subagent_patterns": str(repo_root / "references" / "subagent_patterns.md"),
    }

    outline_text = outline_path.read_text(encoding="utf-8")
    if len(outline_text) > args.truncate_outline:
        outline_text = (
            outline_text[: args.truncate_outline]
            + f"\n\n... [truncated at {args.truncate_outline} chars; full outline at {outline_path}]"
        )

    prompt = _PROMPT_HEADER.format(
        summary=summary,
        outline_json=outline_text,
        **refs,
    )

    if args.output:
        Path(args.output).expanduser().resolve().write_text(prompt, encoding="utf-8")
        print(f"Outline-critique prompt written to {args.output}", file=sys.stderr)
    else:
        print("=" * 72)
        print("OUTLINE CRITIQUE SUBAGENT PROMPT (paste into an Explore agent)")
        print("=" * 72)
        print(prompt)
        print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
