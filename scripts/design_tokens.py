#!/usr/bin/env python3
"""Design token registry for PPTX style presets."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Dict


@dataclass(frozen=True)
class FontPairTokens:
    title: str
    body: str
    caption: str


@dataclass(frozen=True)
class TypographyTokens:
    title_max: int
    title_min: int
    section_max: int
    section_min: int
    body_max: int
    body_min: int
    caption_max: int
    caption_min: int


@dataclass(frozen=True)
class LayoutTokens:
    margin_x: float
    top_safe: float
    bottom_safe: float
    gutter: float
    rhythm: float
    rail_height: float
    radius_style: str
    edge_tolerance: float
    gutter_tolerance: float
    max_density: float
    max_empty_ratio: float


@dataclass(frozen=True)
class StylePreset:
    name: str
    palette: Dict[str, str]
    typography: TypographyTokens
    layout: LayoutTokens
    allowed_layout_families: list[str]

    def to_dict(self) -> dict:
        payload = asdict(self)
        # Keep key ordering stable for deterministic outputs.
        payload["allowed_layout_families"] = list(self.allowed_layout_families)
        return payload


PRESETS: dict[str, StylePreset] = {
    "executive-clinical": StylePreset(
        name="executive-clinical",
        palette={
            "bg_primary": "F4F8FB",
            "bg_dark": "071E3A",
            "surface": "FFFFFF",
            "text_primary": "0F172A",
            "text_muted": "475569",
            "accent_primary": "1493A4",
            "accent_secondary": "F59E0B",
            "line": "D5DEE8",
        },
        typography=TypographyTokens(
            title_max=44,
            title_min=34,
            section_max=30,
            section_min=24,
            body_max=22,
            body_min=15,
            caption_max=14,
            caption_min=11,
        ),
        layout=LayoutTokens(
            margin_x=0.70,
            top_safe=0.95,
            bottom_safe=0.35,
            gutter=0.28,
            rhythm=0.24,
            rail_height=0.10,
            radius_style="rounded-rectangle",
            edge_tolerance=0.06,
            gutter_tolerance=0.06,
            max_density=0.78,
            max_empty_ratio=0.62,
        ),
        allowed_layout_families=[
            "hero-opener",
            "card-grid",
            "split-panel",
            "timeline",
            "process-flow",
            "closing-summary",
        ],
    ),
    "bold-startup-narrative": StylePreset(
        name="bold-startup-narrative",
        palette={
            "bg_primary": "EEF6FF",
            "bg_dark": "0B1220",
            "surface": "FFFFFF",
            "text_primary": "0B132B",
            "text_muted": "334155",
            "accent_primary": "FF6B35",
            "accent_secondary": "22C55E",
            "line": "CBD5E1",
        },
        typography=TypographyTokens(
            title_max=48,
            title_min=36,
            section_max=32,
            section_min=24,
            body_max=22,
            body_min=15,
            caption_max=13,
            caption_min=11,
        ),
        layout=LayoutTokens(
            margin_x=0.65,
            top_safe=0.95,
            bottom_safe=0.32,
            gutter=0.30,
            rhythm=0.24,
            rail_height=0.10,
            radius_style="rounded-rectangle",
            edge_tolerance=0.07,
            gutter_tolerance=0.07,
            max_density=0.82,
            max_empty_ratio=0.60,
        ),
        allowed_layout_families=[
            "hero-opener",
            "card-grid",
            "stat-callout",
            "comparison",
            "process-flow",
            "closing-summary",
        ],
    ),
    "data-heavy-boardroom": StylePreset(
        name="data-heavy-boardroom",
        palette={
            "bg_primary": "F8FAFC",
            "bg_dark": "0F172A",
            "surface": "FFFFFF",
            "text_primary": "111827",
            "text_muted": "4B5563",
            "accent_primary": "1D4ED8",
            "accent_secondary": "0891B2",
            "line": "D1D5DB",
        },
        typography=TypographyTokens(
            title_max=40,
            title_min=30,
            section_max=28,
            section_min=22,
            body_max=22,
            body_min=15,
            caption_max=12,
            caption_min=10,
        ),
        layout=LayoutTokens(
            margin_x=0.65,
            top_safe=0.90,
            bottom_safe=0.30,
            gutter=0.24,
            rhythm=0.20,
            rail_height=0.08,
            radius_style="rectangle",
            edge_tolerance=0.05,
            gutter_tolerance=0.05,
            max_density=0.86,
            max_empty_ratio=0.55,
        ),
        allowed_layout_families=[
            "hero-opener",
            "table-comparison",
            "split-panel",
            "chart-heavy",
            "card-grid",
            "closing-summary",
        ],
    ),
    "sunset-investor": StylePreset(
        name="sunset-investor",
        palette={
            "bg_primary": "FFF7ED",
            "bg_dark": "431407",
            "surface": "FFFFFF",
            "text_primary": "7C2D12",
            "text_muted": "9A3412",
            "accent_primary": "EA580C",
            "accent_secondary": "B45309",
            "line": "FED7AA",
        },
        typography=TypographyTokens(
            title_max=46,
            title_min=34,
            section_max=30,
            section_min=22,
            body_max=22,
            body_min=15,
            caption_max=13,
            caption_min=11,
        ),
        layout=LayoutTokens(
            margin_x=0.70,
            top_safe=0.95,
            bottom_safe=0.35,
            gutter=0.28,
            rhythm=0.24,
            rail_height=0.10,
            radius_style="rounded-rectangle",
            edge_tolerance=0.06,
            gutter_tolerance=0.06,
            max_density=0.80,
            max_empty_ratio=0.60,
        ),
        allowed_layout_families=[
            "hero-opener",
            "card-grid",
            "split-panel",
            "timeline",
            "comparison",
            "closing-summary",
        ],
    ),
    "forest-research": StylePreset(
        name="forest-research",
        palette={
            "bg_primary": "F0FDF4",
            "bg_dark": "052E16",
            "surface": "FFFFFF",
            "text_primary": "14532D",
            "text_muted": "166534",
            "accent_primary": "16A34A",
            "accent_secondary": "65A30D",
            "line": "BBF7D0",
        },
        typography=TypographyTokens(
            title_max=44,
            title_min=32,
            section_max=30,
            section_min=22,
            body_max=22,
            body_min=15,
            caption_max=12,
            caption_min=10,
        ),
        layout=LayoutTokens(
            margin_x=0.68,
            top_safe=0.92,
            bottom_safe=0.32,
            gutter=0.28,
            rhythm=0.22,
            rail_height=0.09,
            radius_style="rounded-rectangle",
            edge_tolerance=0.06,
            gutter_tolerance=0.06,
            max_density=0.80,
            max_empty_ratio=0.58,
        ),
        allowed_layout_families=[
            "hero-opener",
            "card-grid",
            "process-flow",
            "split-panel",
            "timeline",
            "closing-summary",
        ],
    ),
    "midnight-neon": StylePreset(
        name="midnight-neon",
        palette={
            "bg_primary": "0A1020",
            "bg_dark": "030712",
            "surface": "101A33",
            "text_primary": "E2E8F0",
            "text_muted": "94A3B8",
            "accent_primary": "22D3EE",
            "accent_secondary": "F43F5E",
            "line": "1E293B",
        },
        typography=TypographyTokens(
            title_max=48,
            title_min=36,
            section_max=32,
            section_min=24,
            body_max=22,
            body_min=15,
            caption_max=13,
            caption_min=11,
        ),
        layout=LayoutTokens(
            margin_x=0.68,
            top_safe=0.90,
            bottom_safe=0.30,
            gutter=0.30,
            rhythm=0.24,
            rail_height=0.10,
            radius_style="rectangle",
            edge_tolerance=0.07,
            gutter_tolerance=0.07,
            max_density=0.84,
            max_empty_ratio=0.56,
        ),
        allowed_layout_families=[
            "hero-opener",
            "card-grid",
            "split-panel",
            "timeline",
            "process-flow",
            "closing-summary",
        ],
    ),
    "paper-journal": StylePreset(
        name="paper-journal",
        palette={
            "bg_primary": "FFFCF5",
            "bg_dark": "1F2937",
            "surface": "FFFFFF",
            "text_primary": "1F2937",
            "text_muted": "4B5563",
            "accent_primary": "0369A1",
            "accent_secondary": "B45309",
            "line": "E5E7EB",
        },
        typography=TypographyTokens(
            title_max=42,
            title_min=30,
            section_max=28,
            section_min=22,
            body_max=22,
            body_min=15,
            caption_max=12,
            caption_min=10,
        ),
        layout=LayoutTokens(
            margin_x=0.70,
            top_safe=0.95,
            bottom_safe=0.32,
            gutter=0.26,
            rhythm=0.22,
            rail_height=0.08,
            radius_style="rectangle",
            edge_tolerance=0.05,
            gutter_tolerance=0.05,
            max_density=0.82,
            max_empty_ratio=0.58,
        ),
        allowed_layout_families=[
            "hero-opener",
            "split-panel",
            "card-grid",
            "table-comparison",
            "process-flow",
            "closing-summary",
        ],
    ),
    "arctic-minimal": StylePreset(
        name="arctic-minimal",
        palette={
            "bg_primary": "EFF6FF",
            "bg_dark": "0F172A",
            "surface": "FFFFFF",
            "text_primary": "0F172A",
            "text_muted": "334155",
            "accent_primary": "0284C7",
            "accent_secondary": "0891B2",
            "line": "BFDBFE",
        },
        typography=TypographyTokens(
            title_max=42,
            title_min=30,
            section_max=28,
            section_min=22,
            body_max=22,
            body_min=15,
            caption_max=12,
            caption_min=10,
        ),
        layout=LayoutTokens(
            margin_x=0.70,
            top_safe=0.95,
            bottom_safe=0.32,
            gutter=0.28,
            rhythm=0.22,
            rail_height=0.08,
            radius_style="rectangle",
            edge_tolerance=0.05,
            gutter_tolerance=0.05,
            max_density=0.80,
            max_empty_ratio=0.58,
        ),
        allowed_layout_families=[
            "hero-opener",
            "card-grid",
            "split-panel",
            "timeline",
            "comparison",
            "closing-summary",
        ],
    ),
    "charcoal-safety": StylePreset(
        name="charcoal-safety",
        palette={
            "bg_primary": "F3F4F6",
            "bg_dark": "111827",
            "surface": "FFFFFF",
            "text_primary": "111827",
            "text_muted": "374151",
            "accent_primary": "DC2626",
            "accent_secondary": "F59E0B",
            "line": "D1D5DB",
        },
        typography=TypographyTokens(
            title_max=44,
            title_min=32,
            section_max=30,
            section_min=22,
            body_max=22,
            body_min=15,
            caption_max=12,
            caption_min=10,
        ),
        layout=LayoutTokens(
            margin_x=0.68,
            top_safe=0.92,
            bottom_safe=0.30,
            gutter=0.26,
            rhythm=0.22,
            rail_height=0.09,
            radius_style="rounded-rectangle",
            edge_tolerance=0.06,
            gutter_tolerance=0.06,
            max_density=0.82,
            max_empty_ratio=0.56,
        ),
        allowed_layout_families=[
            "hero-opener",
            "card-grid",
            "split-panel",
            "process-flow",
            "comparison",
            "closing-summary",
        ],
    ),
    "lavender-ops": StylePreset(
        name="lavender-ops",
        palette={
            "bg_primary": "F5F3FF",
            "bg_dark": "312E81",
            "surface": "FFFFFF",
            "text_primary": "312E81",
            "text_muted": "4338CA",
            "accent_primary": "7C3AED",
            "accent_secondary": "14B8A6",
            "line": "DDD6FE",
        },
        typography=TypographyTokens(
            title_max=44,
            title_min=32,
            section_max=30,
            section_min=22,
            body_max=22,
            body_min=15,
            caption_max=12,
            caption_min=10,
        ),
        layout=LayoutTokens(
            margin_x=0.68,
            top_safe=0.92,
            bottom_safe=0.30,
            gutter=0.28,
            rhythm=0.22,
            rail_height=0.09,
            radius_style="rounded-rectangle",
            edge_tolerance=0.06,
            gutter_tolerance=0.06,
            max_density=0.82,
            max_empty_ratio=0.56,
        ),
        allowed_layout_families=[
            "hero-opener",
            "card-grid",
            "split-panel",
            "timeline",
            "comparison",
            "closing-summary",
        ],
    ),
    "warm-terracotta": StylePreset(
        name="warm-terracotta",
        palette={
            "bg_primary": "FFF7ED",
            "bg_dark": "7C2D12",
            "surface": "FFFFFF",
            "text_primary": "7C2D12",
            "text_muted": "9A3412",
            "accent_primary": "C2410C",
            "accent_secondary": "0891B2",
            "line": "FED7AA",
        },
        typography=TypographyTokens(
            title_max=44,
            title_min=32,
            section_max=30,
            section_min=22,
            body_max=22,
            body_min=15,
            caption_max=12,
            caption_min=10,
        ),
        layout=LayoutTokens(
            margin_x=0.68,
            top_safe=0.92,
            bottom_safe=0.30,
            gutter=0.28,
            rhythm=0.22,
            rail_height=0.09,
            radius_style="rounded-rectangle",
            edge_tolerance=0.06,
            gutter_tolerance=0.06,
            max_density=0.82,
            max_empty_ratio=0.56,
        ),
        allowed_layout_families=[
            "hero-opener",
            "card-grid",
            "split-panel",
            "timeline",
            "process-flow",
            "closing-summary",
        ],
    ),
    # Lab-report: clinical/technical-data aesthetic. White body, full-width
    # dark header bar (navy) at the top carrying the title and subtitle in
    # white. Tuned for table-heavy content — wider margins for dense rows,
    # no soft background tint, body text in near-black for readability at
    # print scale. Use for LAMP-vs-Cobas-style comparison decks, materials
    # spec sheets, benchmark data presentations.
    "lab-report": StylePreset(
        name="lab-report",
        palette={
            "bg_primary": "FFFFFF",
            "bg_dark": "0B2545",  # Deep navy header
            "surface": "FFFFFF",
            "text_primary": "1B2838",
            "text_muted": "4B5563",
            "accent_primary": "0B2545",  # Same navy as header
            "accent_secondary": "C9302C",  # Clinical red for highlights
            "line": "D1D5DB",
        },
        typography=TypographyTokens(
            title_max=32,
            title_min=22,
            section_max=22,
            section_min=15,
            body_max=14,
            body_min=10,
            caption_max=11,
            caption_min=9,
        ),
        layout=LayoutTokens(
            margin_x=0.40,
            top_safe=1.20,  # Below the 1.00" header bar
            bottom_safe=0.30,
            gutter=0.24,
            rhythm=0.22,
            rail_height=0.04,
            radius_style="rectangle",
            edge_tolerance=0.05,
            gutter_tolerance=0.05,
            max_density=0.78,
            max_empty_ratio=0.55,
        ),
        allowed_layout_families=[
            "card-grid",
            "split-panel",
            "timeline",
            "closing-summary",
        ],
    ),
    # Editorial-minimal: pure white body with a single strong accent color
    # used on titles + motifs. No soft tints, no background bleed. The
    # content is carried by typography and spacing, not by chrome. Dark
    # slides (kpi-hero, theme: dark) flip to pure black. Use for reports,
    # research primers, executive briefings where the deck should read
    # like a well-designed page, not a slide template.
    "editorial-minimal": StylePreset(
        name="editorial-minimal",
        palette={
            "bg_primary": "FFFFFF",
            "bg_dark": "000000",
            "surface": "FFFFFF",
            "text_primary": "0A0A0A",
            "text_muted": "6B7280",
            "accent_primary": "D4461E",  # Oxide red for deliberate punch
            "accent_secondary": "1F2937",
            "line": "E5E7EB",
        },
        typography=TypographyTokens(
            title_max=46,
            title_min=34,
            section_max=28,
            section_min=20,
            body_max=18,
            body_min=13,
            caption_max=11,
            caption_min=9,
        ),
        layout=LayoutTokens(
            margin_x=0.75,
            top_safe=0.90,
            bottom_safe=0.32,
            gutter=0.28,
            rhythm=0.24,
            rail_height=0.10,
            radius_style="rectangle",
            edge_tolerance=0.05,
            gutter_tolerance=0.05,
            max_density=0.70,
            max_empty_ratio=0.65,  # deliberate whitespace is the point
        ),
        allowed_layout_families=[
            "hero-opener",
            "card-grid",
            "split-panel",
            "timeline",
            "process-flow",
            "closing-summary",
        ],
    ),
}

DEFAULT_FONT_PAIR_KEY = "system_clean_v1"

FONT_PAIRS: dict[str, FontPairTokens] = {
    # Backward-compatible default. Existing decks stay visually stable.
    "system_clean_v1": FontPairTokens(
        title="Trebuchet MS",
        body="Calibri",
        caption="Calibri",
    ),
    "editorial_serif_v1": FontPairTokens(
        title="Georgia",
        body="Calibri",
        caption="Calibri",
    ),
    "clean_modern_v1": FontPairTokens(
        title="Trebuchet MS",
        body="Calibri",
        caption="Calibri",
    ),
}


def available_presets() -> list[str]:
    return sorted(PRESETS.keys())


def get_style_preset(name: str) -> StylePreset:
    key = (name or "").strip().lower()
    if key not in PRESETS:
        valid = ", ".join(available_presets())
        raise ValueError(f"Unknown style preset: '{name}'. Valid presets: {valid}")
    return PRESETS[key]


def available_font_pairs() -> list[str]:
    return sorted(FONT_PAIRS.keys())


def get_font_pair(name: str | None) -> FontPairTokens:
    key = (name or DEFAULT_FONT_PAIR_KEY).strip().lower()
    if key not in FONT_PAIRS:
        valid = ", ".join(available_font_pairs())
        raise ValueError(f"Unknown font pair: '{name}'. Valid font pairs: {valid}")
    return FONT_PAIRS[key]


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print style design tokens for a preset.")
    parser.add_argument(
        "--style-preset",
        default="executive-clinical",
        help="Style preset name",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available style presets",
    )
    parser.add_argument(
        "--font-pair",
        default=DEFAULT_FONT_PAIR_KEY,
        help="Font pair key",
    )
    parser.add_argument(
        "--list-font-pairs",
        action="store_true",
        help="List available font pair keys",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    if args.list:
        print("\n".join(available_presets()))
        return 0
    if args.list_font_pairs:
        print("\n".join(available_font_pairs()))
        return 0
    preset = get_style_preset(args.style_preset)
    font_pair = get_font_pair(args.font_pair)
    payload = preset.to_dict()
    payload["font_pair_key"] = args.font_pair
    payload["font_pair"] = asdict(font_pair)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
