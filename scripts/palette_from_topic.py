#!/usr/bin/env python3
"""Choose a deterministic presentation palette from a topic string."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PALETTE_PRESETS: list[dict[str, object]] = [
    {
        "id": "space_mission_v1",
        "keywords": {"space", "lunar", "moon", "mission", "nasa", "rocket", "artemis", "orbit"},
        "palette_key": "enterprise_graphite_v1",
        "palette": {
            "dominant": "07111F",
            "support": "102443",
            "accent": "6FE7FF",
            "neutral": "EAF1FA",
        },
    },
    {
        "id": "climate_coastal_v1",
        "keywords": {"climate", "ocean", "coastal", "water", "marine", "sustainability"},
        "palette_key": "climate_coastal_v1",
        "palette": {
            "dominant": "0C4A6E",
            "support": "155E75",
            "accent": "14B8A6",
            "neutral": "ECFEFF",
        },
    },
    {
        "id": "energy_sunset_v1",
        "keywords": {"energy", "grid", "power", "solar", "battery", "industrial"},
        "palette_key": "energy_sunset_v1",
        "palette": {
            "dominant": "7C2D12",
            "support": "9A3412",
            "accent": "F59E0B",
            "neutral": "FFF7ED",
        },
    },
    {
        "id": "clinical_labs_v1",
        "keywords": {"clinical", "health", "biotech", "lab", "diagnostic", "medical", "research"},
        "palette_key": "enterprise_graphite_v1",
        "palette": {
            "dominant": "0F172A",
            "support": "1E3A5F",
            "accent": "14B8A6",
            "neutral": "F8FAFC",
        },
    },
    {
        "id": "finance_boardroom_v1",
        "keywords": {"finance", "bank", "revenue", "market", "capital", "strategy", "board"},
        "palette_key": "enterprise_graphite_v1",
        "palette": {
            "dominant": "111827",
            "support": "374151",
            "accent": "2563EB",
            "neutral": "F8FAFC",
        },
    },
    {
        "id": "education_civic_v1",
        "keywords": {"education", "school", "learning", "curriculum", "public", "community"},
        "palette_key": "climate_coastal_v1",
        "palette": {
            "dominant": "1F2937",
            "support": "0C4A6E",
            "accent": "0EA5E9",
            "neutral": "F8FAFC",
        },
    },
]

FALLBACKS = [
    "space_mission_v1",
    "clinical_labs_v1",
    "finance_boardroom_v1",
    "climate_coastal_v1",
    "energy_sunset_v1",
]


def choose_palette_for_topic(topic: str) -> dict[str, object]:
    cleaned = " ".join(str(topic or "").lower().split())
    tokens = {token for token in cleaned.replace("/", " ").replace("-", " ").split() if token}
    for preset in PALETTE_PRESETS:
        if tokens & set(preset["keywords"]):
            return {
                "topic": topic,
                "palette_id": preset["id"],
                "palette_key": preset["palette_key"],
                "palette": preset["palette"],
                "matched_keywords": sorted(tokens & set(preset["keywords"])),
            }

    digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest() if cleaned else "0"
    fallback_id = FALLBACKS[int(digest[:2], 16) % len(FALLBACKS)]
    preset = next(item for item in PALETTE_PRESETS if item["id"] == fallback_id)
    return {
        "topic": topic,
        "palette_id": preset["id"],
        "palette_key": preset["palette_key"],
        "palette": preset["palette"],
        "matched_keywords": [],
    }


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Choose a deterministic PPTX palette from a topic.")
    parser.add_argument("topic", help="Topic or prompt describing the deck")
    parser.add_argument("--output", help="Optional JSON output path")
    return parser.parse_args()


def main() -> int:
    args = _args()
    payload = choose_palette_for_topic(args.topic)
    rendered = json.dumps(payload, indent=2)
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
