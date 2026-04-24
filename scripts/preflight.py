#!/usr/bin/env python3
"""Fast pre-build linter for presentation-skill outlines.

Runs static checks on outline.json in <1s to catch common authoring errors
before the slow build+render cycle (~60s) in build_workspace.py --qa.

CLI:
  python3 scripts/preflight.py --outline outline.json [--strict]

Exit codes:
  0 - no issues
  1 - warnings only (non-blocking)
  2 - errors present (blocking when --strict)
  3 - malformed outline JSON (always blocking)

Output: JSON to stdout with {"issues": [...], "error_count": N, "warning_count": N};
human-readable summary to stderr.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Numeric KPI regex for stats.facts[].value. Mirrors design_rules_qa /
# layout_lint but expressed per the preflight spec. Accepts optional
# leading sign ("-" or unicode "−"), digits/dot/comma/percent, and an
# optional short unit suffix.
_STATS_NUMERIC_VALUE_RE = re.compile(
    r"^[-−]?[\d,.%]+[a-zA-Z%°×x$€£¥]{0,3}$"
)

_VALID_FONT_PAIRS = {
    "system_clean_v1",
    "editorial_serif_v1",
    "clean_modern_v1",
}

_ASSET_ALIAS_PREFIXES = ("asset:", "image:", "background:", "chart:", "generated:")
_REACT_ICON_PREFIXES = ("fa6:", "fa:", "bi:", "bs:", "md:", "lu:")

_ASSET_FIELDS_SCALAR = ("hero_image", "generated_image", "diagram", "mermaid_source", "logo", "chart_data")
_ASSET_FIELDS_ARRAY = ("icons",)


def _make_issue(
    slide_index: int | None,
    rule: str,
    severity: str,
    message: str,
    suggested_fix: str = "",
) -> dict[str, Any]:
    return {
        "slide_index": slide_index if slide_index is not None else -1,
        "rule": rule,
        "severity": severity,
        "message": message,
        "suggested_fix": suggested_fix,
    }


def _is_numeric_stats_value(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True  # empty handled upstream
    if not any(ch.isdigit() for ch in stripped):
        return False
    return bool(_STATS_NUMERIC_VALUE_RE.match(stripped))


def _check_asset_path(
    value: str,
    outline_parent: Path,
) -> bool:
    """Return True if path resolves locally (or is aliased), False if missing.

    Aliased prefixes (asset:/image:/background:/chart:) are always OK.
    """
    if not value or not isinstance(value, str):
        return True
    for prefix in _ASSET_ALIAS_PREFIXES:
        if value.startswith(prefix):
            return True
    p = Path(value)
    if p.is_absolute():
        return p.exists()
    # relative: try outline_parent, outline_parent/assets, outline_parent/assets/staged
    candidates = [
        outline_parent / p,
        outline_parent / "assets" / p,
        outline_parent / "assets" / "staged" / p,
    ]
    return any(c.exists() for c in candidates)


def _check_icon_path(value: str, outline_parent: Path) -> bool:
    """Return True if an icon string resolves under the workspace.

    Mirrors `_resolve_icon_path` in build_deck.py:
      - absolute path exists;
      - relative path with extension in assets/icons/ or outline_parent;
      - bare name <name>.{png,svg,jpg,jpeg} under assets/icons/.
    """
    if not value or not isinstance(value, str):
        return True
    raw = value.strip()
    if not raw:
        return True
    if raw.startswith(_REACT_ICON_PREFIXES):
        return True
    icons_dir = outline_parent / "assets" / "icons"
    if raw.startswith("/"):
        return Path(raw).exists()
    p = Path(raw)
    has_ext = p.suffix.lower() in {".png", ".svg", ".jpg", ".jpeg"}
    if has_ext or "/" in raw or "\\" in raw:
        return (icons_dir / p).exists() or (outline_parent / p).exists()
    for ext in (".png", ".svg", ".jpg", ".jpeg"):
        if (icons_dir / f"{raw}{ext}").exists():
            return True
    return False


def _check_chart(slide: dict[str, Any], idx: int) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    chart = slide.get("chart")
    if not isinstance(chart, dict):
        issues.append(
            _make_issue(
                idx,
                "chart_missing",
                "error",
                "Slide has variant: chart but no `chart` object.",
                "Add a `chart` object with `series` and either `categories` or per-series `labels`.",
            )
        )
        return issues

    series = chart.get("series")
    if not isinstance(series, list) or len(series) < 1:
        issues.append(
            _make_issue(
                idx,
                "chart_series_missing",
                "error",
                "`chart.series` must be a non-empty array.",
                "Add at least one series: [{\"name\": \"...\", \"values\": [...]}].",
            )
        )
        return issues

    categories = chart.get("categories")
    has_top_categories = isinstance(categories, list) and len(categories) > 0

    for s_idx, s in enumerate(series):
        if not isinstance(s, dict):
            issues.append(
                _make_issue(
                    idx,
                    "chart_series_malformed",
                    "error",
                    f"series[{s_idx}] is not an object.",
                    "Each series must be an object with `values`.",
                )
            )
            continue
        values = s.get("values")
        if not isinstance(values, list) or len(values) < 1:
            issues.append(
                _make_issue(
                    idx,
                    "chart_series_values_missing",
                    "error",
                    f"series[{s_idx}] has no `values` array.",
                    "Add a `values` array of numbers to every series.",
                )
            )
            continue

        labels = s.get("labels")
        has_series_labels = isinstance(labels, list) and len(labels) > 0

        if not has_top_categories and not has_series_labels:
            issues.append(
                _make_issue(
                    idx,
                    "chart_categories_missing",
                    "error",
                    f"series[{s_idx}] has no category source: neither chart.categories nor series.labels.",
                    "Add `categories` at the chart level or `labels` inside the series.",
                )
            )
            continue

        if has_top_categories and len(categories) != len(values):
            issues.append(
                _make_issue(
                    idx,
                    "chart_categories_length_mismatch",
                    "error",
                    f"chart.categories length ({len(categories)}) != series[{s_idx}].values length ({len(values)}).",
                    "Make categories and values the same length.",
                )
            )
        if has_series_labels and len(labels) != len(values):
            issues.append(
                _make_issue(
                    idx,
                    "chart_labels_length_mismatch",
                    "error",
                    f"series[{s_idx}].labels length ({len(labels)}) != values length ({len(values)}).",
                    "Make labels and values the same length.",
                )
            )
    return issues


def _check_stats(slide: dict[str, Any], idx: int) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    facts = slide.get("facts")
    if not isinstance(facts, list):
        return issues
    for f_idx, fact in enumerate(facts):
        if not isinstance(fact, dict):
            continue
        value = fact.get("value")
        if value is None:
            continue
        value_str = str(value)
        if not _is_numeric_stats_value(value_str):
            issues.append(
                _make_issue(
                    idx,
                    "stats_value_non_numeric",
                    "warning",
                    f"facts[{f_idx}].value = {value_str!r} is not numeric; stats KPIs render badly with adjectives.",
                    "Use a real number + unit (e.g., \"14%\", \"2.1pt\") or switch variant to cards-3.",
                )
            )
    return issues


def _check_variant_required(slide: dict[str, Any], idx: int) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    variant = (slide.get("variant") or "").strip().lower()

    if variant in ("cards-2", "cards-3"):
        expected = 2 if variant == "cards-2" else 3
        cards = slide.get("cards")
        if not isinstance(cards, list):
            issues.append(
                _make_issue(
                    idx,
                    "cards_missing",
                    "error",
                    f"variant: {variant} requires a `cards` array with {expected} entries.",
                    f"Add a `cards` array of length {expected}.",
                )
            )
        elif len(cards) != expected:
            issues.append(
                _make_issue(
                    idx,
                    "cards_count_wrong",
                    "error",
                    f"variant: {variant} expects {expected} cards, got {len(cards)}.",
                    f"Adjust `cards` length to {expected}.",
                )
            )

    elif variant == "timeline":
        milestones = slide.get("milestones")
        if not isinstance(milestones, list) or len(milestones) < 2:
            issues.append(
                _make_issue(
                    idx,
                    "timeline_milestones_missing",
                    "error",
                    "variant: timeline requires a `milestones` array with >= 2 entries.",
                    "Add at least 2 `milestones` objects.",
                )
            )

    elif variant == "matrix":
        quadrants = slide.get("quadrants")
        if not isinstance(quadrants, list) or len(quadrants) != 4:
            issues.append(
                _make_issue(
                    idx,
                    "matrix_quadrants_wrong",
                    "error",
                    f"variant: matrix requires exactly 4 `quadrants` (got {len(quadrants) if isinstance(quadrants, list) else 'none'}).",
                    "Provide exactly 4 quadrant objects.",
                )
            )

    elif variant == "split":
        highlights = slide.get("highlights")
        body = slide.get("body")
        bullets = slide.get("bullets")
        empty_highlights = not highlights
        empty_body = not body and not bullets
        if empty_highlights and empty_body:
            issues.append(
                _make_issue(
                    idx,
                    "split_empty",
                    "warning",
                    "variant: split has neither `highlights` nor `body`/`bullets`.",
                    "Add content to at least one side (highlights or body/bullets).",
                )
            )

    elif variant == "kpi-hero":
        value = slide.get("value")
        label = slide.get("label")
        if not (isinstance(value, (str, int, float)) and str(value).strip()):
            issues.append(
                _make_issue(
                    idx,
                    "kpi_hero_missing_value",
                    "error",
                    "variant: kpi-hero requires a non-empty `value` string.",
                    'Add `"value": "42%"` or similar numeric+unit headline.',
                )
            )
        elif isinstance(value, str) and len(value.strip()) > 12:
            issues.append(
                _make_issue(
                    idx,
                    "kpi_hero_value_too_long",
                    "warning",
                    f"kpi-hero value {value.strip()!r} is {len(value.strip())} chars; "
                    "the autosize drops font to 60pt at 9+ chars and may still overflow wider slides.",
                    "Shorten the headline (e.g., '$1.2M' instead of '$1,200,000') and move "
                    "precision to `context` or `label`.",
                )
            )
        if not (isinstance(label, str) and label.strip()):
            issues.append(
                _make_issue(
                    idx,
                    "kpi_hero_missing_label",
                    "error",
                    "variant: kpi-hero requires a non-empty `label` string.",
                    "Add `label` naming what the value measures.",
                )
            )

    elif variant == "image-sidebar":
        assets = slide.get("assets") or {}
        has_image = bool(
            isinstance(assets, dict)
            and (assets.get("hero_image") or assets.get("image"))
        )
        if not has_image:
            issues.append(
                _make_issue(
                    idx,
                    "image_sidebar_missing_image",
                    "warning",
                    "variant: image-sidebar works best with an image; "
                    "without assets.hero_image it falls back to a "
                    "sidebar-only layout.",
                    'Stage an image and reference it as '
                    '`"assets": {"hero_image": "assets/<name>.png"}`.',
                )
            )
        sections = slide.get("sidebar_sections")
        if not isinstance(sections, list) or not sections:
            issues.append(
                _make_issue(
                    idx,
                    "image_sidebar_missing_sections",
                    "error",
                    "variant: image-sidebar requires sidebar_sections "
                    "(2-4 labeled sections).",
                    'Add `"sidebar_sections": [{"title": "...", "body": "..."}]`.',
                )
            )

    elif variant == "generated-image":
        assets = slide.get("assets") or {}
        image_generation = slide.get("image_generation")
        has_image = bool(
            isinstance(assets, dict)
            and (assets.get("hero_image") or assets.get("generated_image") or assets.get("image"))
        )
        if not has_image:
            issues.append(
                _make_issue(
                    idx,
                    "generated_image_missing_asset",
                    "error",
                    "variant: generated-image requires assets.hero_image or assets.generated_image.",
                    'Reference the generated asset with `"assets": {"hero_image": "generated:<name>"}`.',
                )
            )
        if not isinstance(image_generation, dict):
            issues.append(
                _make_issue(
                    idx,
                    "generated_image_missing_metadata",
                    "warning",
                    "variant: generated-image should include an image_generation object with prompt/model/purpose.",
                    "Add image_generation.prompt, image_generation.model, and image_generation.purpose so the slide is auditable.",
                )
            )
        elif not str(image_generation.get("prompt") or "").strip():
            issues.append(
                _make_issue(
                    idx,
                    "generated_image_prompt_missing",
                    "warning",
                    "image_generation.prompt is empty.",
                    "Store the prompt or a concise prompt summary with the slide.",
                )
            )

    elif variant == "table":
        headers = slide.get("headers")
        rows = slide.get("rows")
        if not isinstance(headers, list) or not headers:
            issues.append(
                _make_issue(
                    idx,
                    "table_missing_headers",
                    "error",
                    "variant: table requires a non-empty `headers` array.",
                    'Add `"headers": ["Col A", "Col B", "Col C"]`.',
                )
            )
            return issues
        if not isinstance(rows, list) or not rows:
            issues.append(
                _make_issue(
                    idx,
                    "table_missing_rows",
                    "error",
                    "variant: table requires a non-empty `rows` array.",
                    'Add `"rows": [["cell", "cell", "cell"], ...]`.',
                )
            )
            return issues
        col_count = len(headers)
        for row_idx, row in enumerate(rows):
            if not isinstance(row, list):
                issues.append(
                    _make_issue(
                        idx,
                        "table_row_malformed",
                        "error",
                        f"rows[{row_idx}] is not a list.",
                        "Every row must be an array of cell values.",
                    )
                )
                continue
            if len(row) != col_count:
                issues.append(
                    _make_issue(
                        idx,
                        "table_row_width_mismatch",
                        "error",
                        f"rows[{row_idx}] has {len(row)} cells but headers "
                        f"defines {col_count} columns.",
                        "Pad or trim the row to match the header count.",
                    )
                )
        if len(rows) > 10:
            issues.append(
                _make_issue(
                    idx,
                    "table_too_many_rows",
                    "warning",
                    f"Table has {len(rows)} rows; readability degrades past "
                    "~8 rows at typical slide sizes.",
                    "Consider splitting across two slides, or promoting the "
                    "most-important rows and moving details to an appendix.",
                )
            )

    elif variant == "comparison-2col":
        left = slide.get("left")
        right = slide.get("right")
        if not isinstance(left, dict):
            issues.append(
                _make_issue(
                    idx,
                    "comparison_missing_left",
                    "error",
                    "variant: comparison-2col requires a `left` object with title + body.",
                    'Add `"left": {"title": "...", "body": "..."}`.',
                )
            )
        elif not (isinstance(left.get("title"), str) and left.get("title").strip()):
            issues.append(
                _make_issue(
                    idx,
                    "comparison_left_missing_title",
                    "warning",
                    "comparison-2col `left.title` is empty.",
                    "Add a clear left-column heading (e.g., 'Before', 'Hypothesis').",
                )
            )
        if not isinstance(right, dict):
            issues.append(
                _make_issue(
                    idx,
                    "comparison_missing_right",
                    "error",
                    "variant: comparison-2col requires a `right` object with title + body.",
                    'Add `"right": {"title": "...", "body": "..."}`.',
                )
            )
        elif not (isinstance(right.get("title"), str) and right.get("title").strip()):
            issues.append(
                _make_issue(
                    idx,
                    "comparison_right_missing_title",
                    "warning",
                    "comparison-2col `right.title` is empty.",
                    "Add a clear right-column heading (e.g., 'After', 'Result').",
                )
            )

    return issues


def _check_assets(
    slide: dict[str, Any],
    idx: int,
    outline_parent: Path,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    assets = slide.get("assets")
    if not isinstance(assets, dict):
        return issues
    for field in _ASSET_FIELDS_SCALAR:
        value = assets.get(field)
        if isinstance(value, str) and value:
            if not _check_asset_path(value, outline_parent):
                issues.append(
                    _make_issue(
                        idx,
                        "asset_not_found",
                        "warning",
                        f"assets.{field} = {value!r} not found at lint time.",
                        "Stage the asset under the workspace's assets/ or assets/staged/ folder, or use an alias prefix.",
                    )
                )
    for field in _ASSET_FIELDS_ARRAY:
        arr = assets.get(field)
        if isinstance(arr, list):
            for i, value in enumerate(arr):
                if isinstance(value, str) and value:
                    # Icons resolve against assets/icons/ with bare-name +
                    # extension fallbacks. Missing icons are a soft warning
                    # (enrichment only), so we check a wider path set here.
                    if field == "icons" and _check_icon_path(value, outline_parent):
                        continue
                    if not _check_asset_path(value, outline_parent):
                        issues.append(
                            _make_issue(
                                idx,
                                "asset_not_found",
                                "warning",
                                f"assets.{field}[{i}] = {value!r} not found at lint time.",
                                "Stage the asset or use an alias prefix.",
                            )
                        )
    return issues


# Variants that support `assets.icons`. The renderer draws icons above each
# card/tile/milestone; omitting them is fine but tends to produce text-only
# decks on topics with clear visual metaphors. See Visual Enrichment Defaults
# in SKILL.md.
_ICON_SUPPORTED_VARIANTS = {
    "cards-2": 2,
    "cards-3": 3,
    "timeline": None,  # length = len(milestones)
    "stats": None,     # length = len(facts)
    "matrix": 4,
}


# Rhythm-break detection. "Even with different variants, six slides of
# title+bullets/cards/columns on the same light background feel monotonous"
# is the most common Codex failure mode after variant-awareness was added.
#
# A "rhythm-breaker" must break COMPOSITION, not just layout:
#   - kpi-hero (dark by default, one giant number)
#   - any slide with theme: dark
#   - cards-3 with promote_card (asymmetric, breaks the 3-up grid)
# comparison-2col is layout variety but still light-bg text — good to
# have, but not sufficient on its own for a 5+ slide deck.


def _slide_is_rhythm_breaker(slide: dict[str, Any]) -> bool:
    if not isinstance(slide, dict):
        return False
    variant = (slide.get("variant") or "").strip().lower()
    if variant == "kpi-hero":
        return True
    # cards-3 with a promoted card (asymmetric layout) counts.
    if variant == "cards-3" and isinstance(slide.get("promote_card"), int):
        return True
    # Any slide with theme: dark inverts the palette — big rhythm break.
    if str(slide.get("theme", "")).strip().lower() == "dark":
        return True
    return False


# Heuristics for "hedged prose" — bullets that signal un-researched or
# uncommitted claims rather than specific facts. A deck full of these
# reads as generic. The signals are word-boundary regexes so partial
# matches don't fire (e.g., "typically" matches, "atypically" doesn't).
_HEDGE_WORDS = [
    "usually",
    "often",
    "typically",
    "generally",
    "tends? to",
    "can be",
    "may be",
    "might be",
    "could be",
    "largely",
    "mostly",
    "broadly",
    "generally speaking",
    "in most cases",
    "in many cases",
    "relatively",
    "somewhat",
]

# Concrete-claim signals — if a bullet has any of these, it's not hedged:
# specific years, dollar/percent figures, named entities (capitalized
# proper nouns that aren't sentence-starts are hard to detect reliably
# so we focus on numeric anchors).
_CONCRETE_RE = re.compile(
    r"\b("
    r"19\d{2}|20\d{2}"               # 4-digit year
    r"|\d+(?:\.\d+)?\s*%"            # percent
    r"|\$\s?\d"                      # dollar
    r"|\d+(?:,\d{3})+"               # 1,000+ comma-separated numbers
    r"|\d+\s*(?:km|mi|kg|lb|GW|MW|kW|g|m|s|ms|Hz|ppm|mg|x|×)"  # unit
    r")\b"
)
_HEDGE_RE = re.compile(
    r"\b(?:" + "|".join(_HEDGE_WORDS) + r")\b",
    re.IGNORECASE,
)


def _slide_body_lines(slide: dict[str, Any]) -> list[str]:
    """Extract all prose strings from a slide for hedge detection."""
    lines: list[str] = []
    bullets = slide.get("bullets")
    if isinstance(bullets, list):
        for b in bullets:
            if isinstance(b, str):
                lines.append(b)
            elif isinstance(b, dict) and b.get("text"):
                lines.append(str(b["text"]))
    body = slide.get("body")
    if isinstance(body, str) and body.strip():
        lines.append(body)
    elif isinstance(body, list):
        lines.extend(str(x) for x in body if isinstance(x, str))
    for field in ("highlights", "caption", "subtitle"):
        v = slide.get(field)
        if isinstance(v, str) and v.strip():
            lines.append(v)
        elif isinstance(v, list):
            lines.extend(str(x) for x in v if isinstance(x, str))
    for container in ("left", "right"):
        side = slide.get(container)
        if isinstance(side, dict):
            b = side.get("body")
            if isinstance(b, str):
                lines.append(b)
            elif isinstance(b, list):
                lines.extend(str(x) for x in b if isinstance(x, str))
    cards = slide.get("cards")
    if isinstance(cards, list):
        for card in cards:
            if isinstance(card, dict):
                for field in ("body", "text"):
                    v = card.get(field)
                    if isinstance(v, str) and v.strip():
                        lines.append(v)
    return [l.strip() for l in lines if l and l.strip()]


def _check_content_quality(slide: dict[str, Any], idx: int) -> list[dict[str, Any]]:
    """Flag slides whose prose is dominated by hedges and lacks concrete
    anchors (years, percents, quantities, named dollars). Info-level —
    the slide isn't wrong, it just isn't load-bearing.
    """
    stype = (slide.get("type") or "content").strip().lower()
    if stype != "content":
        return []
    lines = _slide_body_lines(slide)
    if len(lines) < 2:
        return []  # tables / kpi-hero / short slides
    hedge_hits = sum(1 for l in lines if _HEDGE_RE.search(l))
    concrete_hits = sum(1 for l in lines if _CONCRETE_RE.search(l))
    # Flag when >= 50% of lines are hedged AND there are 0 concrete anchors.
    if hedge_hits >= max(2, len(lines) // 2) and concrete_hits == 0:
        return [
            _make_issue(
                idx,
                "content_vague_hedged",
                "info",
                (
                    f"{hedge_hits}/{len(lines)} prose lines on this slide use "
                    "hedges (usually/often/can be/typically/tends to) and "
                    "zero lines carry a concrete anchor (year, %, quantity, "
                    "named entity with a number). The slide reads as "
                    "uncommitted."
                ),
                (
                    "Research at least one specific fact per bullet: a year, "
                    "a percentage, a named case, a dollar figure. Replace "
                    "'reactors usually take many years' with '~10-15 years "
                    "median from permit to first criticality (EIA, NRC).' "
                    "If the content genuinely doesn't have specifics, ask "
                    "the user rather than shipping hedged prose."
                ),
            )
        ]
    return []


def _check_rhythm_break(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    content = [
        s for s in slides
        if isinstance(s, dict)
        and (s.get("type") or "content").strip().lower() == "content"
    ]
    if len(content) < 5:
        return []
    if any(_slide_is_rhythm_breaker(s) for s in content):
        return []
    return [
        _make_issue(
            None,
            "rhythm_break_absent",
            "info",
            (
                f"Deck has {len(content)} content slides but no composition "
                "rhythm-breaker (kpi-hero, promote_card on cards-3, or "
                "theme: dark). Varying the variant across cards/split/matrix/"
                "timeline still reads as uniform when every slide is "
                "title+bullets on a light background."
            ),
            (
                "Add at least ONE of: (1) a kpi-hero slide pulling out the "
                "deck's most memorable number (kpi-hero renders dark by "
                "default — the biggest rhythm break); (2) promote_card: N "
                "on one cards-3 slide to break the symmetric 3-up grid; "
                "(3) theme: \"dark\" on one content slide. comparison-2col "
                "is useful but doesn't count on its own — it's still "
                "light-bg text. If the content doesn't naturally offer a "
                "quantitative anchor or a pillar that dominates, ASK THE "
                "USER for one before building rather than shipping a "
                "uniform deck."
            ),
        )
    ]


def _derive_icon_suggestion(title: str) -> str:
    """Derive a reasonable bare-name icon slug from a card/item title.

    Lowercased, spaces/punctuation to hyphens, trimmed to the first 1-2
    meaningful words. Not a lookup — just a starting-point suggestion
    the author can keep or refine when staging actual icons.
    """
    if not title:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", title.lower())
    words = [w for w in cleaned.split() if w and w not in {"the", "a", "an", "and", "or", "of"}]
    if not words:
        return ""
    # Prefer the first 1-2 content words; keep short for filesystem friendliness.
    slug = "-".join(words[:2])
    return slug[:28]


def _collect_icon_candidates(slide: dict[str, Any]) -> list[str]:
    """For a slide that supports icons, return 1 suggested bare name per
    card/milestone/fact, derived from each item's title. Empty list when
    there's nothing to suggest.
    """
    variant = (slide.get("variant") or "").strip().lower()
    if variant not in _ICON_SUPPORTED_VARIANTS:
        return []
    items: list[dict[str, Any]] = []
    if variant in ("cards-2", "cards-3") and isinstance(slide.get("cards"), list):
        items = [c for c in slide["cards"] if isinstance(c, dict)]
    elif variant == "timeline" and isinstance(slide.get("milestones"), list):
        items = [m for m in slide["milestones"] if isinstance(m, dict)]
    elif variant == "matrix" and isinstance(slide.get("quadrants"), list):
        items = [q for q in slide["quadrants"] if isinstance(q, dict)]
    elif variant == "stats" and isinstance(slide.get("facts"), list):
        items = [f for f in slide["facts"] if isinstance(f, dict)]

    suggestions: list[str] = []
    for item in items:
        title = str(item.get("title") or item.get("label") or "").strip()
        slug = _derive_icon_suggestion(title)
        if slug:
            suggestions.append(slug)
    return suggestions


def _check_variant_overuse(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag when the deck uses the full variant menu instead of picking
    a thoughtful subset. Recent Codex runs cycle through kpi-hero +
    comparison-2col + matrix + timeline + cards-3 + split on nearly
    every deck regardless of topic — the rhythm-break guardrails
    rewarded variant COUNT rather than variant FIT.

    Fires as info-level on decks where distinct_variants / content_slides
    exceeds 0.75 (i.e., almost every slide introduces a new variant).
    Suggestion: commit to 2-3 variants and use them intentionally.
    """
    content = [
        s for s in slides
        if isinstance(s, dict)
        and (s.get("type") or "content").strip().lower() == "content"
    ]
    if len(content) < 5:
        return []
    variants = [
        (s.get("variant") or "").strip().lower()
        for s in content
    ]
    # Treat empty variant as "standard" for counting purposes.
    normalized = [v or "standard" for v in variants]
    distinct = set(normalized)
    ratio = len(distinct) / len(content)
    # "Menu-fitting" threshold: at least 5 distinct variants AND the
    # ratio is ≥ 0.75 (almost every slide is a different variant).
    if len(distinct) < 5 or ratio < 0.75:
        return []
    return [
        _make_issue(
            None,
            "variant_overuse",
            "info",
            (
                f"Deck has {len(content)} content slides using "
                f"{len(distinct)} distinct variants "
                f"({sorted(distinct)}). When nearly every slide is a "
                "different variant, the deck reads as 'menu-fitting the "
                "skill' rather than designed for this topic."
            ),
            (
                "Pick 2-3 variants that fit the topic's voice and use "
                "them intentionally: an editorial primer might use "
                "standard + kpi-hero + image-lead; a research brief "
                "might use cards-3 + table + comparison-2col; a "
                "methodology might use timeline + matrix + standard. "
                "Retire the variants that don't serve the argument. "
                "Don't treat the rhythm-break rule as 'must use every "
                "variant once' — one strong rhythm-breaker plus "
                "consistent supporting variants reads as intentional."
            ),
        )
    ]


def _check_icon_absence_systemic(
    slides: list[dict[str, Any]],
    prior_issues: list[dict[str, Any]],  # unused; kept for signature stability
) -> list[dict[str, Any]]:
    """Single deck-level icon rule. Fires when ≥2 icon-supporting slides
    (cards-2/cards-3/timeline/stats/matrix) have no `assets.icons` AND
    the deck has zero icons anywhere. Concrete suggestion: bare-name
    slugs derived from each card/milestone/quadrant title.

    Replaces three earlier overlapping rules (`icons_absent_enrichment_hint`
    per slide, `enrichment_missing_pattern` deck-level, plus this one).
    """
    icon_supporting = []
    for idx, s in enumerate(slides):
        if not isinstance(s, dict):
            continue
        variant = (s.get("variant") or "").strip().lower()
        if variant in _ICON_SUPPORTED_VARIANTS:
            icon_supporting.append((idx, s))

    if len(icon_supporting) < 2:
        return []

    # Any slide already has icons set? Then nothing systemic.
    for s in slides:
        if not isinstance(s, dict):
            continue
        assets = s.get("assets") or {}
        if isinstance(assets, dict) and assets.get("icons"):
            return []

    # Build per-slide suggestion map from card titles.
    suggestions_by_slide: dict[int, list[str]] = {}
    for idx, s in icon_supporting:
        slugs = _collect_icon_candidates(s)
        if slugs:
            suggestions_by_slide[idx] = slugs

    if not suggestions_by_slide:
        return []

    suggestion_lines = [
        f"slide {idx}: {suggestions_by_slide[idx]}"
        for idx in sorted(suggestions_by_slide)
    ]
    suggestion_blob = "; ".join(suggestion_lines)

    return [
        _make_issue(
            None,
            "icons_systemically_absent",
            "warning",
            (
                f"{len(icon_supporting)} icon-supporting slide(s) have "
                "no `assets.icons` and the deck has zero icons anywhere. "
                "Icons often clarify cards that share a visual metaphor."
            ),
            (
                "If icons would help, stage PNGs under "
                "<workspace>/assets/icons/<name>.png and add "
                "`assets.icons` arrays to the flagged slides using these "
                f"derived candidate names: {suggestion_blob}. If the deck "
                "genuinely doesn't benefit from icons (pure prose primer, "
                "minimal aesthetic), ignore this warning."
            ),
        )
    ]


def _check_enrichment_pattern(
    slides: list[dict[str, Any]],
    prior_issues: list[dict[str, Any]],
    outline_parent: Path,
) -> list[dict[str, Any]]:
    """Promote scattered icons_absent_enrichment_hint notes to a single
    deck-level warning when the pattern is systemic — ≥3 slides flagged,
    no staged images, no mermaid/diagram source, no asset_plan images
    array populated. This is the "Codex acknowledged the nudges and
    shipped anyway" failure mode.
    """
    icon_hints = [i for i in prior_issues if i.get("rule") == "icons_absent_enrichment_hint"]
    if len(icon_hints) < 3:
        return []

    # Is there any staged visual anywhere in the deck?
    has_any_visual = False
    for s in slides:
        if not isinstance(s, dict):
            continue
        assets = s.get("assets") or {}
        if not isinstance(assets, dict):
            continue
        if (
            assets.get("hero_image")
            or assets.get("generated_image")
            or assets.get("mermaid_source")
            or assets.get("diagram")
        ):
            has_any_visual = True
            break
    if has_any_visual:
        return []

    plan_path = outline_parent / "asset_plan.json"
    plan_has_images = False
    if plan_path.exists():
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan_has_images = bool(
                (plan.get("images") or [])
                or (plan.get("generated_images") or [])
                or (plan.get("icons") or [])
            )
        except (json.JSONDecodeError, OSError):
            plan_has_images = False
    if plan_has_images:
        return []

    slide_indices = sorted({i.get("slide_index") for i in icon_hints if isinstance(i.get("slide_index"), int)})
    return [
        _make_issue(
            None,
            "enrichment_missing_pattern",
            "warning",
            (
                f"{len(icon_hints)} slides were flagged with "
                "icons_absent_enrichment_hint; the deck also has zero "
                "staged hero images, generated images, zero mermaid diagrams, "
                "and an empty asset_plan.json images/generated_images/icons array. "
                "This is systemic — "
                "the deck will ship as text-only despite multiple nudges."
            ),
            (
                "Take ONE of these three actions before declaring done: "
                f"(1) stage icons for the flagged slides {slide_indices} "
                "under <workspace>/assets/icons/<name>.png and add "
                "`assets.icons` arrays to those slides; (2) populate "
                "asset_plan.json with at least one wikimedia_query for a "
                "photographic hero image and re-run the build; (3) if the "
                "deck genuinely doesn't need visuals (pure-prose primer), "
                "note that decision explicitly in notes.md and accept the "
                "warning. Don't ignore this rule silently — it means the "
                "deck looks uniform and the earlier per-slide nudges "
                "didn't bite."
            ),
        )
    ]


def _check_icon_nudge(slide: dict[str, Any], idx: int) -> list[dict[str, Any]]:
    variant = (slide.get("variant") or "").strip().lower()
    if variant not in _ICON_SUPPORTED_VARIANTS:
        return []
    assets = slide.get("assets")
    icons = assets.get("icons") if isinstance(assets, dict) else None
    if isinstance(icons, list) and any(isinstance(i, str) and i.strip() for i in icons):
        return []
    expected = _ICON_SUPPORTED_VARIANTS[variant]
    if expected is None:
        if variant == "timeline":
            expected = len(slide.get("milestones") or []) or 4
        elif variant == "stats":
            expected = len(slide.get("facts") or []) or 3
    return [
        _make_issue(
            idx,
            "icons_absent_enrichment_hint",
            "info",
            f"variant: {variant} supports `assets.icons` but none are set; "
            f"icons often clarify cards that share a visual metaphor.",
            f"If the {variant} cards/items have a clear visual anchor, add "
            f"`assets.icons`: [ {expected} bare names ] and stage PNGs under "
            f"`<workspace>/assets/icons/<name>.png`.",
        )
    ]


def _check_section_empty(slide: dict[str, Any], idx: int) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    slide_type = (slide.get("type") or "").strip().lower()
    if slide_type != "section":
        return issues
    has_bullets = bool(slide.get("bullets"))
    has_caption = bool(slide.get("caption"))
    has_body = bool(slide.get("body"))
    hero_image = ""
    assets = slide.get("assets")
    if isinstance(assets, dict):
        hero_image = assets.get("hero_image") or ""
    has_hero = bool(hero_image)
    if not (has_bullets or has_caption or has_body or has_hero):
        issues.append(
            _make_issue(
                idx,
                "section_auto_motif",
                "info",
                "Section divider has no bullets/caption/body/hero_image; renderer will auto-draw a motif.",
                "This is expected. Add `bullets` or `caption` if you want real transition content.",
            )
        )
    return issues


def _check_sources_stretch(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    run_start: int | None = None
    run_len = 0
    for idx, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        slide_type = (slide.get("type") or "content").strip().lower()
        if slide_type not in ("content", "text"):
            # Reset run at non-content boundaries (title/section).
            if run_len >= 3 and run_start is not None:
                issues.append(
                    _make_issue(
                        run_start,
                        "sources_missing_streak",
                        "info",
                        f"{run_len} consecutive content slides (starting index {run_start}) have no `sources`.",
                        "Add at least one `sources` entry per evidence-bearing slide for citation discipline.",
                    )
                )
            run_start = None
            run_len = 0
            continue
        sources = slide.get("sources")
        if not sources:
            if run_start is None:
                run_start = idx
            run_len += 1
        else:
            if run_len >= 3 and run_start is not None:
                issues.append(
                    _make_issue(
                        run_start,
                        "sources_missing_streak",
                        "info",
                        f"{run_len} consecutive content slides (starting index {run_start}) have no `sources`.",
                        "Add at least one `sources` entry per evidence-bearing slide.",
                    )
                )
            run_start = None
            run_len = 0
    if run_len >= 3 and run_start is not None:
        issues.append(
            _make_issue(
                run_start,
                "sources_missing_streak",
                "info",
                f"{run_len} consecutive content slides (starting index {run_start}) have no `sources`.",
                "Add at least one `sources` entry per evidence-bearing slide.",
            )
        )
    return issues


def lint_outline(outline: dict[str, Any], outline_parent: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    # Deck-level font_pair check.
    deck_style = outline.get("deck_style")
    if isinstance(deck_style, dict):
        font_pair = deck_style.get("font_pair")
        if font_pair is not None and font_pair not in _VALID_FONT_PAIRS:
            issues.append(
                _make_issue(
                    None,
                    "invalid_font_pair",
                    "error",
                    f"deck_style.font_pair = {font_pair!r} is not one of {sorted(_VALID_FONT_PAIRS)}.",
                    f"Set font_pair to one of: {', '.join(sorted(_VALID_FONT_PAIRS))}.",
                )
            )

    slides = outline.get("slides")
    if not isinstance(slides, list):
        issues.append(
            _make_issue(
                None,
                "slides_missing",
                "error",
                "Top-level `slides` array is missing or not a list.",
                "Add a `slides` array to the outline.",
            )
        )
        return issues

    # Slide 1 must be title.
    if slides:
        first = slides[0]
        if isinstance(first, dict):
            first_type = (first.get("type") or "content").strip().lower()
            if first_type != "title":
                issues.append(
                    _make_issue(
                        0,
                        "slide1_not_title",
                        "warning",
                        f"Slide 1 has type={first_type!r}; the title-slide motif only fires on type: title.",
                        "Set slide 0 to type: title, or accept that the opener will use the content motif.",
                    )
                )

    for idx, slide in enumerate(slides):
        if not isinstance(slide, dict):
            issues.append(
                _make_issue(
                    idx,
                    "slide_malformed",
                    "error",
                    "Slide entry is not an object.",
                    "Replace the entry with a slide object.",
                )
            )
            continue

        title = slide.get("title") or ""
        if isinstance(title, str) and len(title) > 85:
            issues.append(
                _make_issue(
                    idx,
                    "title_too_long",
                    "warning",
                    f"Title is {len(title)} chars (> 85); likely to wrap 3+ lines and trip overflow.",
                    "Shorten to <= 60 chars.",
                )
            )

        variant = (slide.get("variant") or "").strip().lower()
        if slide.get("render_mode") is not None:
            issues.append(
                _make_issue(
                    idx,
                    "legacy_render_mode",
                    "warning",
                    "`render_mode` is a legacy field and should not be used in new outlines.",
                    "Remove render_mode and let build_workspace.py --renderer auto choose the renderer.",
                )
            )
        if variant == "chart":
            issues.extend(_check_chart(slide, idx))
        if variant == "stats":
            issues.extend(_check_stats(slide, idx))

        issues.extend(_check_variant_required(slide, idx))
        issues.extend(_check_assets(slide, idx, outline_parent))
        issues.extend(_check_section_empty(slide, idx))
        # Removed: _check_icon_nudge per-slide info. icons_systemically_absent
        # now fires at the deck level with concrete suggestions.
        # Removed: _check_content_quality (hedged-prose linter was firing on
        # decent prose too often). See SKILL.md "Visual Enrichment Defaults"
        # for the soft guidance on specific-vs-hedged claims.

    issues.extend(_check_sources_stretch(slides))
    # Removed: _check_rhythm_break (turned a taste call into a rule that
    # fired on every ≥5-slide deck). Rhythm is a design judgement, not
    # a schema invariant. SKILL.md covers when to reach for a
    # rhythm-break.
    # Removed: _check_enrichment_pattern (overlapped with the rule below).
    issues.extend(_check_icon_absence_systemic(slides, issues))
    issues.extend(_check_variant_overuse(slides))

    return issues


def _summary_to_stderr(issues: list[dict[str, Any]], error_count: int, warning_count: int, info_count: int) -> None:
    if not issues:
        print("[preflight] OK - no issues.", file=sys.stderr)
        return
    print(
        f"[preflight] {error_count} error(s), {warning_count} warning(s), {info_count} info note(s).",
        file=sys.stderr,
    )
    for it in issues:
        slide = it["slide_index"]
        loc = f"slide {slide}" if slide is not None and slide >= 0 else "deck"
        sev = it["severity"].upper()
        print(f"  [{sev}] {loc} :: {it['rule']} :: {it['message']}", file=sys.stderr)
        if it.get("suggested_fix"):
            print(f"        fix: {it['suggested_fix']}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Static preflight linter for presentation-skill outlines.")
    parser.add_argument("--outline", required=True, help="Path to outline.json.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 2 if any errors are found (default: warnings-only exit 1).",
    )
    args = parser.parse_args()

    outline_path = Path(args.outline).expanduser().resolve()
    if not outline_path.exists():
        print(
            json.dumps(
                {
                    "issues": [
                        {
                            "slide_index": -1,
                            "rule": "outline_missing",
                            "severity": "error",
                            "message": f"Outline file not found: {outline_path}",
                            "suggested_fix": "Pass the correct --outline path.",
                        }
                    ],
                    "error_count": 1,
                    "warning_count": 0,
                }
            )
        )
        print(f"[preflight] outline not found: {outline_path}", file=sys.stderr)
        return 3

    try:
        outline = json.loads(outline_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(
            json.dumps(
                {
                    "issues": [
                        {
                            "slide_index": -1,
                            "rule": "outline_malformed",
                            "severity": "error",
                            "message": f"Outline JSON is malformed: {exc}",
                            "suggested_fix": "Fix the JSON syntax before running preflight.",
                        }
                    ],
                    "error_count": 1,
                    "warning_count": 0,
                }
            )
        )
        print(f"[preflight] malformed JSON: {exc}", file=sys.stderr)
        return 3

    if not isinstance(outline, dict):
        print(
            json.dumps(
                {
                    "issues": [
                        {
                            "slide_index": -1,
                            "rule": "outline_malformed",
                            "severity": "error",
                            "message": "Outline root is not a JSON object.",
                            "suggested_fix": "Wrap the outline in a top-level object.",
                        }
                    ],
                    "error_count": 1,
                    "warning_count": 0,
                }
            )
        )
        print("[preflight] outline root is not an object", file=sys.stderr)
        return 3

    issues = lint_outline(outline, outline_path.parent)

    error_count = sum(1 for it in issues if it["severity"] == "error")
    warning_count = sum(1 for it in issues if it["severity"] == "warning")
    info_count = sum(1 for it in issues if it["severity"] == "info")

    print(
        json.dumps(
            {
                "issues": issues,
                "error_count": error_count,
                "warning_count": warning_count,
                "info_count": info_count,
            },
            indent=2,
        )
    )

    _summary_to_stderr(issues, error_count, warning_count, info_count)

    # Exit code semantics:
    #   0 -> no issues
    #   1 -> warnings only
    #   2 -> errors present (caller decides blocking via --strict-preflight / --qa)
    #   3 -> malformed JSON (handled above)
    # --strict is a CLI convenience that forces non-zero on errors; today
    # any error already yields 2, so --strict is a no-op at this layer and
    # exists for parity with the integration flag name.
    if error_count > 0:
        return 2
    if warning_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
