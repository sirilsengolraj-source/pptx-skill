#!/usr/bin/env python3
"""Generate and QA 10 diverse decks to benchmark skill robustness."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DeckSpec:
    name: str
    preset: str
    subtitle: str
    objective: str
    pillars: list[str]
    milestones: list[tuple[str, str]]
    risks: list[tuple[str, str]]
    actions: list[str]
    archetype: str = "strategy"


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "deck"


def _run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return result.returncode, result.stdout


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_benchmark_chart(deck_dir: Path, stem: str, kind: str) -> str | None:
    """Create a small local PNG so benchmark decks exercise image layouts."""
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None

    assets_dir = deck_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    out = assets_dir / f"{stem}.png"
    width, height = 1200, 680
    img = Image.new("RGB", (width, height), "#F8FAFC")
    draw = ImageDraw.Draw(img)
    ink = "#0F172A"
    muted = "#64748B"
    blue = "#2563EB"
    teal = "#0F766E"
    amber = "#D97706"
    red = "#DC2626"

    for y in range(90, height - 70, 90):
        draw.line([(80, y), (width - 70, y)], fill="#E2E8F0", width=2)
    draw.text((80, 34), stem.replace("_", " ").title(), fill=ink)

    if kind == "bars":
        values = [42, 57, 71, 66, 84]
        labels = ["A", "B", "C", "D", "E"]
        bar_w = 110
        gap = 70
        base_y = height - 95
        for idx, value in enumerate(values):
            x = 120 + idx * (bar_w + gap)
            h = int(value * 4.9)
            color = [blue, teal, amber, red, blue][idx]
            draw.rounded_rectangle([x, base_y - h, x + bar_w, base_y], radius=18, fill=color)
            draw.text((x + 35, base_y + 18), labels[idx], fill=muted)
            draw.text((x + 28, base_y - h - 30), f"{value}%", fill=ink)
    elif kind == "heatmap":
        cols, rows = 7, 5
        cell = 82
        start_x, start_y = 150, 130
        colors = ["#D6E4F0", "#B9E0C1", "#FDE68A", "#E9B6BC"]
        for r in range(rows):
            for c in range(cols):
                color = colors[(r * 2 + c) % len(colors)]
                x = start_x + c * (cell + 16)
                y = start_y + r * (cell + 12)
                draw.rounded_rectangle([x, y, x + cell, y + cell], radius=10, fill=color, outline="#CBD5E1")
        draw.text((150, 590), "QC intensity by run and target", fill=muted)
    elif kind == "plate":
        cols, rows = 8, 4
        start_x, start_y = 140, 150
        dx, dy = 105, 92
        for r in range(rows):
            for c in range(cols):
                x = start_x + c * dx
                y = start_y + r * dy
                color = [teal, "#BAE6FD", amber, red][(r + c) % 4]
                draw.ellipse([x, y, x + 54, y + 54], fill=color, outline="#334155", width=2)
        draw.text((140, 565), "Synthetic assay plate visualization for layout testing", fill=muted)
    else:
        points = [(90, 500), (260, 430), (430, 455), (600, 315), (770, 260), (940, 210), (1110, 150)]
        draw.line(points, fill=blue, width=10, joint="curve")
        for x, y in points:
            draw.ellipse([x - 15, y - 15, x + 15, y + 15], fill=teal, outline="white", width=4)
        draw.line([(90, 540), (1110, 540)], fill="#94A3B8", width=3)
        draw.text((90, 575), "Trend readout with annotated improvement", fill=muted)

    img.save(out)
    return str(Path("assets") / out.name)


def _write_mermaid_asset(deck_dir: Path, stem: str) -> str:
    assets_dir = deck_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    out = assets_dir / f"{stem}.mmd"
    out.write_text(
        "\n".join(
            [
                "flowchart LR",
                "  A[Signal] --> B[Triage]",
                "  B --> C{Gate}",
                "  C -->|pass| D[Scale]",
                "  C -->|fail| E[Revise]",
                "  D --> F[Review]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return str(Path("assets") / out.name)


def _run_qa(
    *,
    py: str,
    scripts: Path,
    input_path: Path,
    qa_dir: Path,
    qa_report: Path,
    outline_path: Path,
    preset: str,
    skip_render: bool,
) -> tuple[int, str, dict[str, Any]]:
    qa_cmd = [
        py,
        str(scripts / "qa_gate.py"),
        "--input",
        str(input_path),
        "--outdir",
        str(qa_dir),
        "--style-preset",
        preset,
        "--strict-geometry",
        "--skip-manual-review",
        "--fail-on-visual-warnings",
        "--fail-on-design-warnings",
        "--report",
        str(qa_report),
        "--outline",
        str(outline_path),
    ]
    if skip_render:
        qa_cmd.append("--skip-render")
    rc, out = _run(qa_cmd)
    return rc, out, _load_json(qa_report)


def _outline_for(spec: DeckSpec, deck_dir: Path) -> dict[str, Any]:
    cards = [
        {"title": f"Pillar {idx + 1}", "body": text, "accent": "accent_primary" if idx % 2 == 0 else "accent_secondary"}
        for idx, text in enumerate(spec.pillars[:3])
    ]
    milestones = [
        {"label": year, "title": year, "body": milestone}
        for year, milestone in spec.milestones[:4]
    ]
    quadrants = [
        {"title": f"Risk: {title}", "body": mitigation}
        for title, mitigation in spec.risks[:4]
    ]
    facts = [
        {"value": "94%", "label": "primary gate", "caption": spec.actions[0] if spec.actions else spec.objective, "accent": "accent_primary"},
        {"value": "3.2x", "label": "cycle leverage", "caption": spec.actions[1] if len(spec.actions) > 1 else "Reusable operating loop", "accent": "accent_secondary"},
        {"value": "12", "label": "tracked signals", "caption": spec.actions[2] if len(spec.actions) > 2 else "Weekly review cadence", "accent": "accent_primary"},
    ]
    archetype = spec.archetype.strip().lower()

    if archetype == "lab":
        plate = _write_benchmark_chart(deck_dir, "assay_plate", "plate")
        trend = _write_benchmark_chart(deck_dir, "run_trend", "trend")
        heatmap = _write_benchmark_chart(deck_dir, "target_heatmap", "heatmap")
        figures = [
            {"path": path, "label": label, "title": title, "caption": caption}
            for path, label, title, caption in [
                (plate, "A", "Plate map", "Control wells separate cleanly."),
                (trend, "B", "Run trend", "Signal stabilizes after gate two."),
                (heatmap, "C", "Target heatmap", "Discordant targets stay localized."),
            ]
            if path
        ]
        image_slide: dict[str, Any]
        if trend:
            image_slide = {
                "type": "content",
                "variant": "image-sidebar",
                "title": "Figure Readout",
                "subtitle": "One visual, explicit interpretation rail",
                "assets": {"image": trend},
                "caption": "Synthetic benchmark chart generated locally to exercise image-sidebar layout.",
                "sidebar_sections": [
                    {"title": "Readout", "body": spec.actions[:2]},
                    {"title": "Interpretation", "body": spec.actions[2:4]},
                    {"title": "Caveat", "body": "Treat as layout evidence, not external scientific evidence."},
                ],
                "sources": ["Benchmark-local synthetic figure"],
            }
        else:
            image_slide = {
                "type": "content",
                "variant": "stats",
                "title": "Figure Readout",
                "subtitle": "Fallback when local image generation is unavailable",
                "facts": facts,
            }
        figure_slide: dict[str, Any]
        if figures:
            figure_slide = {
                "type": "content",
                "variant": "scientific-figure",
                "title": "Panel Evidence",
                "subtitle": "Academic multi-panel figure staging",
                "figures": figures,
                "caption": "Panels are synthetic benchmark assets used to test caption and panel spacing.",
                "interpretation": spec.objective,
                "sources": ["Benchmark-local synthetic panels"],
            }
        else:
            figure_slide = {
                "type": "content",
                "variant": "stats",
                "title": "Panel Evidence",
                "subtitle": "Evidence summary",
                "facts": facts,
            }
        return {
            "deck_style": {
                "visual_density": "high",
                "cards_mode": "feature-left",
                "header_mode": "lab-clean",
                "footer_mode": "source-line",
                "summary_callout_mode": "lab-box",
                "footer_page_numbers": True,
            },
            "slides": [
                {"type": "title", "title": spec.name, "subtitle": spec.subtitle, "footer": "Generated by Codex PPTX benchmark"},
                {
                    "type": "content",
                    "variant": "standard",
                    "header_mode": "lab-card",
                    "title": "Assay Readout",
                    "subtitle": "Clean lab-summary slide with no heavy template pressure",
                    "body": spec.objective,
                    "bullets": spec.actions[:4],
                    "summary_callout": "Quick PI-facing summary before detailed tables.",
                    "sources": ["Benchmark-local synthetic data"],
                },
                {
                    "type": "content",
                    "variant": "table",
                    "title": "Run Summary",
                    "subtitle": "Numeric gates before interpretation",
                    "headers": ["Readout", "Value", "Interpretation"],
                    "rows": [["Primary gate", "94%", "Pass"], ["Cycle leverage", "3.2x", "Directional"], ["Tracked signals", "12", "Review weekly"]],
                    "caption": "Benchmark values are synthetic and deterministic.",
                    "sources": ["Benchmark-local synthetic data"],
                },
                {
                    "type": "content",
                    "variant": "lab-run-results",
                    "title": "Concordance Table",
                    "subtitle": "Editable result table with compact interpretation",
                    "tables": [
                        {
                            "title": "Primary comparison",
                            "headers": ["Metric", "Result", "Gate"],
                            "rows": [["Agreement", "94%", "Pass"], ["Invalids", "2", "Review"], ["Median Cq", "27.4", "Pass"]],
                            "caption": "Compact table keeps the data editable in PowerPoint.",
                        },
                        {
                            "title": "Breakdown",
                            "headers": ["Group", "n", "Flag"],
                            "rows": [["Positive", "31", "OK"], ["Negative", "18", "OK"], ["Borderline", "3", "Check"]],
                        },
                    ],
                    "interpretation": "Use the table as the source of truth; bullets only interpret the readout.",
                },
                figure_slide,
                image_slide,
                {
                    "type": "content",
                    "variant": "table",
                    "title": "Follow-Up Queue",
                    "subtitle": "Small table for next wet-lab actions",
                    "headers": ["Item", "Owner", "Due", "Status"],
                    "rows": [["Repeat borderline wells", "Lab", "48h", "Open"], ["Freeze analysis rule", "Data", "Today", "Ready"], ["Update slide notes", "PI", "Today", "Open"]],
                    "caption": "Tabular action lists avoid card-grid overuse.",
                },
                {
                    "type": "content",
                    "variant": "standard",
                    "title": "Summary for Follow-Up",
                    "subtitle": "Editable bullets, source footer, and bottom takeaway box",
                    "bullets": [
                        "Repeat borderline wells and freeze the cutoff rule before adding new claims.",
                        "Keep table values as the source of truth; use bullets only for interpretation.",
                        "Move run-level caveats into notes when the slide starts to crowd.",
                    ],
                    "summary_callout": "Bottom takeaway: repeat borderline wells within 48h, then update the deck from source files.",
                    "sources": ["Benchmark-local synthetic data"],
                },
            ],
        }

    if archetype == "data":
        chart = _write_benchmark_chart(deck_dir, "metric_bars", "bars")
        return {
            "deck_style": {"stats_mode": "policy-bands", "cards_mode": "staggered-row"},
            "slides": [
                {"type": "title", "title": spec.name, "subtitle": spec.subtitle, "footer": "Generated by Codex PPTX benchmark"},
                {
                    "type": "content",
                    "variant": "stats",
                    "title": "Metric Snapshot",
                    "subtitle": "Start with the numbers before the plan",
                    "facts": facts + [{"value": "6", "label": "risk gates", "caption": "Escalation thresholds", "accent": "accent_secondary"}],
                },
                {
                    "type": "content",
                    "variant": "table",
                    "title": "Operating Dashboard",
                    "subtitle": "Board-readable rows with crisp status",
                    "headers": ["Workstream", "Metric", "Target", "Status"],
                    "rows": [["Acquisition", "Loss rate", "<1.2%", "Watch"], ["Ops", "SLA", "99.5%", "Pass"], ["Risk", "Exceptions", "<20", "Pass"], ["Finance", "Runway", "12 mo", "Pass"]],
                    "caption": "Use native tables when fields are parallel.",
                },
                {
                    "type": "content",
                    "variant": "comparison-2col",
                    "title": "Before vs Target State",
                    "subtitle": "Contrast drives the recommendation",
                    "left": {"title": "Current", "bullets": spec.risks[:3]},
                    "right": {"title": "Target", "bullets": spec.actions[:3]},
                    "verdict": spec.objective,
                },
                {
                    "type": "content",
                    "variant": "image-sidebar" if chart else "matrix",
                    "title": "Trend Evidence",
                    "subtitle": "Chart plus interpretation, not another card row",
                    "assets": {"image": chart} if chart else {},
                    "quadrants": quadrants,
                    "sidebar_sections": [
                        {"title": "Signal", "body": spec.actions[:2]},
                        {"title": "Decision rule", "body": spec.actions[2:4]},
                    ],
                    "caption": "Synthetic chart generated locally for benchmark layout testing.",
                },
                {"type": "content", "variant": "matrix", "title": "Risk Register", "subtitle": "Open quadrant layout", "quadrants": quadrants},
                {"type": "content", "variant": "timeline", "title": "Decision Cadence", "subtitle": "Gates stay sparse by design", "milestones": milestones},
                {
                    "type": "content",
                    "variant": "table",
                    "title": "Decision Log",
                    "subtitle": "Close with the operating decision, not a forced hero number",
                    "headers": ["Decision", "Owner", "Evidence", "Next check"],
                    "rows": [["Approve corridor pilot", "Risk", "Loss rate + SLA", "Weekly"], ["Hold global rollout", "Ops", "Latency watch", "QBR"], ["Archive stale rules", "Audit", "Rule registry", "Monthly"]],
                    "caption": spec.objective,
                },
            ],
        }

    if archetype == "ops":
        mermaid = _write_mermaid_asset(deck_dir, "workflow")
        return {
            "deck_style": {"cards_mode": "feature-left"},
            "slides": [
                {"type": "title", "title": spec.name, "subtitle": spec.subtitle, "footer": "Generated by Codex PPTX benchmark"},
                {"type": "section", "title": "Command Model", "subtitle": spec.objective},
                {
                    "type": "content",
                    "variant": "flow",
                    "title": "Escalation Flow",
                    "subtitle": "Workflow diagram with interpretation rail",
                    "assets": {"mermaid_source": mermaid},
                    "sidebar_sections": [
                        {"title": "Trigger", "body": spec.actions[:2]},
                        {"title": "Gate", "body": spec.actions[2:4]},
                    ],
                    "footer": "Mermaid rendered locally when available",
                },
                {"type": "content", "variant": "matrix", "title": "Failure Modes", "subtitle": "Risks are mapped to mitigations", "quadrants": quadrants},
                {"type": "content", "variant": "cards-2", "title": "Team Interface", "subtitle": "Two lanes, clear ownership", "cards": cards[:2]},
                {"type": "content", "variant": "table", "title": "Runbook Checklist", "subtitle": "Short rows beat crowded bullets", "headers": ["Step", "Owner", "Trigger"], "rows": [["Detect", "Ops", "Signal spike"], ["Contain", "Lead", "Gate failed"], ["Communicate", "Comms", "Severity 2"], ["Review", "Owner", "Closure"]], "caption": "Native table remains editable."},
                {"type": "content", "variant": "timeline", "title": "Readiness Timeline", "subtitle": "Staggered milestones", "milestones": milestones},
                {
                    "type": "content",
                    "variant": "standard",
                    "title": "Operator Close",
                    "subtitle": "Actions, owners, and one bottom synthesis",
                    "bullets": spec.actions[:4],
                    "highlights": [
                        "Close on the runbook change.",
                        "Promote a hero metric only when one number carries the decision.",
                    ],
                    "footer": "Benchmark deck output",
                },
            ],
        }

    if archetype == "evidence":
        trend = _write_benchmark_chart(deck_dir, "evidence_trend", "trend")
        heatmap = _write_benchmark_chart(deck_dir, "evidence_heatmap", "heatmap")
        figures = [
            {"path": path, "label": label, "title": title, "caption": caption}
            for path, label, title, caption in [
                (trend, "A", "Trend", "Primary outcome moves in the expected direction."),
                (heatmap, "B", "Heatmap", "Residual variation is isolated to a few groups."),
            ]
            if path
        ]
        return {
            "deck_style": {"visual_density": "medium", "stats_mode": "feature-left"},
            "slides": [
                {"type": "title", "title": spec.name, "subtitle": spec.subtitle, "footer": "Generated by Codex PPTX benchmark"},
                {"type": "content", "variant": "split", "title": "Research Question", "subtitle": "Frame before evidence", "bullets": spec.actions[:4], "highlights": spec.actions[4:8]},
                {"type": "content", "variant": "stats", "title": "Evidence Markers", "subtitle": "Numeric claims first", "facts": facts},
                {"type": "content", "variant": "scientific-figure" if figures else "timeline", "title": "Figure Panel", "subtitle": "Report-style evidence staging", "figures": figures, "milestones": milestones, "caption": "Synthetic benchmark panels for figure layout QA.", "interpretation": spec.objective},
                {"type": "content", "variant": "lab-run-results", "title": "Data Extract", "subtitle": "Compact rows for academic review", "tables": [{"title": "Evidence table", "headers": ["Claim", "Measure", "Status"], "rows": [["Primary", "94%", "Supported"], ["Secondary", "3.2x", "Directional"], ["Caveat", "n=12", "Monitor"]], "caption": "Keep caveats close to the table."}]},
                {"type": "content", "variant": "comparison-2col", "title": "Interpretation", "subtitle": "What changes if the evidence holds", "left": {"title": "Supports", "bullets": spec.pillars[:2]}, "right": {"title": "Still Needs", "bullets": [risk for risk, _ in spec.risks[:2]]}, "verdict": spec.objective},
                {"type": "content", "variant": "matrix", "title": "Threats to Validity", "subtitle": "Explicit caveats", "quadrants": quadrants},
                {
                    "type": "content",
                    "variant": "standard",
                    "title": "Next Evidence Gate",
                    "subtitle": "Research close without oversized KPI treatment",
                    "bullets": ["Resolve the two most decision-relevant caveats first.", "Keep figure captions tied to the source chart or table.", "Only promote a metric to kpi-hero if it changes the decision."],
                    "footer": spec.objective,
                    "sources": ["Benchmark-local synthetic evidence"],
                },
            ],
        }

    if archetype == "narrative":
        return {
            "deck_style": {"cards_mode": "staggered-row"},
            "slides": [
                {"type": "title", "title": spec.name, "subtitle": spec.subtitle, "footer": "Generated by Codex PPTX benchmark"},
                {"type": "content", "variant": "split", "title": "Narrative Tension", "subtitle": "Why now, why this", "bullets": spec.risks[:3], "highlights": spec.actions[:3]},
                {"type": "content", "variant": "stats", "title": "Proof Points", "subtitle": "Evidence without a table", "facts": facts},
                {"type": "content", "variant": "cards-3", "title": "Offer Architecture", "subtitle": "Cards vary by preset treatment", "cards": cards},
                {"type": "content", "variant": "comparison-2col", "title": "Market Shift", "subtitle": "Before and after", "left": {"title": "Old behavior", "bullets": [risk for risk, _ in spec.risks[:3]]}, "right": {"title": "New wedge", "bullets": spec.actions[:3]}, "verdict": spec.objective},
                {"type": "content", "variant": "timeline", "title": "Launch Sequence", "subtitle": "Milestones are not the whole deck", "milestones": milestones},
                {"type": "content", "variant": "cards-2", "title": "Operating Loop", "subtitle": "Two-card close; no automatic KPI hero", "cards": cards[:2]},
                {
                    "type": "content",
                    "variant": "standard",
                    "title": "Decision and Next Step",
                    "subtitle": "Narrative close",
                    "body": spec.objective,
                    "highlights": spec.actions[:3],
                    "footer": "Benchmark deck output",
                },
            ],
        }

    return {
        "slides": [
            {
                "type": "title",
                "title": spec.name,
                "subtitle": spec.subtitle,
                "footer": "Generated by Codex PPTX benchmark",
            },
            {
                "type": "section",
                "title": "Execution Thesis",
                "subtitle": spec.objective,
            },
            {
                "type": "content",
                "variant": "split",
                "title": "Strategic Focus",
                "subtitle": "Primary narrative and operator checklist",
                "bullets": spec.actions[:4],
                "highlights": spec.actions[4:8],
                "footer": "Prioritize measurable execution over activity volume",
            },
            {
                "type": "content",
                "variant": "cards-3",
                "title": "Core Pillars",
                "subtitle": "What carries the plan",
                "cards": cards,
            },
            {
                "type": "content",
                "variant": "timeline",
                "title": "Milestone Timeline",
                "subtitle": "Gated path to traction",
                "milestones": milestones,
            },
            {
                "type": "content",
                "variant": "matrix",
                "title": "Top Risks and Mitigations",
                "subtitle": "Design for resilience",
                "quadrants": quadrants,
            },
            {
                "type": "content",
                "variant": "cards-2",
                "title": "Operating Model",
                "subtitle": "How teams execute together",
                "cards": [
                    {
                        "title": "Build",
                        "body": spec.actions[0] if spec.actions else "Ship in short loops.",
                        "accent": "accent_primary",
                    },
                    {
                        "title": "Scale",
                        "body": spec.actions[1] if len(spec.actions) > 1 else "Standardize and expand.",
                        "accent": "accent_secondary",
                    },
                ],
            },
            {
                "type": "content",
                "variant": "standard",
                "title": "Decision and Next Step",
                "subtitle": "What happens this week",
                "body": spec.objective,
                "bullets": spec.actions[:3],
                "footer": "Benchmark deck output",
            },
        ]
    }


def _deck_specs() -> list[DeckSpec]:
    return [
        DeckSpec(
            name="Clinical AI Diagnostics Strategy",
            preset="lab-report",
            subtitle="From pilot evidence to scaled deployment",
            objective="Win first with one high-confidence diagnostic wedge, then scale platform capabilities.",
            pillars=[
                "Clinical validity with reproducible assay controls.",
                "Workflow fit for lab + provider operations.",
                "Regulatory and reimbursement sequencing discipline.",
            ],
            milestones=[("2026", "Pilot validation"), ("2027", "Regulatory package"), ("2028", "Regional expansion"), ("2029", "Multi-indication platform")],
            risks=[("Data drift", "Weekly model checks and frozen baseline slices"), ("Regulatory delay", "Parallel pre-submission advisory"), ("Pilot failure", "Tight inclusion criteria and fallback sites"), ("Team overload", "Role clarity and delegated ops lead")],
            actions=[
                "Lock one indication and one endpoint.",
                "Define success metrics before launch.",
                "Build traceable sample-to-report workflow.",
                "Run weekly evidence review with red flags.",
                "Capture all implementation decisions in memory.md.",
                "Translate durable rules into AGENTS.md.",
                "Promote repeated tasks into reusable skills.",
                "Audit stale assumptions every sprint.",
            ],
            archetype="lab",
        ),
        DeckSpec(
            name="Fintech Fraud Platform Rollout",
            preset="data-heavy-boardroom",
            subtitle="Reducing chargeback loss with precision controls",
            objective="Lower fraud loss while keeping approval rate stable across key corridors.",
            pillars=[
                "Real-time risk scoring with explainable rules.",
                "Analyst tooling for rapid review loops.",
                "Tiered controls by region and merchant profile.",
            ],
            milestones=[("Q1", "Baseline model"), ("Q2", "Analyst console"), ("Q3", "Regional tuning"), ("Q4", "Global policy layer")],
            risks=[("False declines", "Champion/challenger thresholds"), ("Latency spikes", "SLA budget and circuit breakers"), ("Policy sprawl", "Central rule registry"), ("Audit gaps", "Immutable event logging")],
            actions=[
                "Start with top 3 loss corridors.",
                "Backtest policy changes before promotion.",
                "Instrument fraud-review turnaround time.",
                "Build daily fraud drift report.",
                "Standardize incident taxonomy.",
                "Require approval for high-impact rule edits.",
                "Compact weekly learnings into durable memory.",
                "Run strict QA for dashboard decks.",
            ],
            archetype="data",
        ),
        DeckSpec(
            name="Cybersecurity Incident Command Playbook",
            preset="charcoal-safety",
            subtitle="Fast containment with accountable communication",
            objective="Improve mean-time-to-contain through explicit command structure and rehearsed runbooks.",
            pillars=[
                "Detection signal quality and triage speed.",
                "Incident commander authority and escalation paths.",
                "Post-incident learning that updates controls.",
            ],
            milestones=[("Week 1", "Runbook audit"), ("Week 4", "Tabletop drills"), ("Week 8", "SOC instrumentation"), ("Week 12", "Executive simulation")],
            risks=[("Alert fatigue", "Tiered severity + suppression rules"), ("Ownership confusion", "Named incident roles"), ("Comms lag", "Prepared stakeholder templates"), ("Repeat incidents", "Mandatory control updates")],
            actions=[
                "Define incident severity matrix.",
                "Assign on-call ownership by system.",
                "Pre-write customer and legal comms.",
                "Track MTTA, MTTC, and residual risk.",
                "Enforce postmortem within 48 hours.",
                "Convert repeated fixes into guardrail automation.",
            ],
            archetype="ops",
        ),
        DeckSpec(
            name="Climate Grid Modernization Program",
            preset="forest-research",
            subtitle="Reliability and decarbonization without service disruption",
            objective="Upgrade grid intelligence and storage orchestration to reduce peak stress and outage risk.",
            pillars=[
                "Forecast-driven load balancing.",
                "Distributed storage dispatch optimization.",
                "Field-operations coordination with real-time telemetry.",
            ],
            milestones=[("Phase 1", "Telemetry baseline"), ("Phase 2", "Dispatch pilot"), ("Phase 3", "Multi-region rollout"), ("Phase 4", "Autonomous optimization")],
            risks=[("Forecast error", "Blend models and sensor QA"), ("Asset downtime", "Staged maintenance windows"), ("Community pushback", "Transparent service-level reporting"), ("Budget overrun", "Milestone-based spend controls")],
            actions=[
                "Prioritize highest-risk substations first.",
                "Define outage prevention success metrics.",
                "Publish weekly reliability dashboard.",
                "Run quarterly resilience drills.",
                "Document deployment playbooks by region.",
            ],
            archetype="evidence",
        ),
        DeckSpec(
            name="EdTech Adaptive Learning Initiative",
            preset="arctic-minimal",
            subtitle="Personalized mastery pathways at district scale",
            objective="Improve learner outcomes with adaptive pathways and measurable teacher workload reduction.",
            pillars=[
                "Mastery-based diagnostics and pacing.",
                "Teacher-in-the-loop intervention workflows.",
                "District-level reporting for adoption confidence.",
            ],
            milestones=[("Semester 1", "Pilot schools"), ("Semester 2", "Teacher tooling"), ("Semester 3", "District analytics"), ("Semester 4", "State expansion")],
            risks=[("Low adoption", "Teacher co-design councils"), ("Content mismatch", "Curriculum alignment QA"), ("Data quality", "Ingestion validation checks"), ("Equity gap", "Disaggregated impact monitoring")],
            actions=[
                "Start with one grade band and subject.",
                "Capture intervention outcomes weekly.",
                "Minimize extra teacher clicks.",
                "Use evidence gates before expansion.",
            ],
            archetype="evidence",
        ),
        DeckSpec(
            name="Logistics Network Reconfiguration",
            preset="bold-startup-narrative",
            subtitle="Margin protection through routing and fulfillment redesign",
            objective="Cut delivery cost per order while improving on-time performance in top markets.",
            pillars=[
                "Dynamic routing and capacity planning.",
                "Node-level fulfillment optimization.",
                "Operational visibility and exception handling.",
            ],
            milestones=[("M1", "Lane audit"), ("M2", "Routing engine"), ("M3", "Hub redesign"), ("M4", "Scale + QA")],
            risks=[("Capacity crunch", "Flexible carrier contracts"), ("Data lag", "Near-real-time ETL"), ("Siloed teams", "Shared KPI scorecard"), ("Service dips", "Canary rollout by zone")],
            actions=[
                "Define top 20 cost-intensive lanes.",
                "Pilot dynamic routing in one region.",
                "Set threshold-based escalation rules.",
                "Benchmark SLA and margin together.",
                "Publish exceptions daily.",
            ],
            archetype="ops",
        ),
        DeckSpec(
            name="AI Product Launch Narrative",
            preset="sunset-investor",
            subtitle="Category entry with disciplined product-market proof",
            objective="Launch with one painful workflow and prove retention before broad feature expansion.",
            pillars=[
                "Clear user pain and measurable time savings.",
                "Onboarding friction under five minutes.",
                "Reliable support and release cadence.",
            ],
            milestones=[("Launch", "Core workflow"), ("Month 2", "Usage depth"), ("Month 4", "Team adoption"), ("Month 6", "Expansion")],
            risks=[("Low activation", "Guided onboarding checkpoints"), ("Churn", "Value realization milestones"), ("Feature creep", "Roadmap gates"), ("Support overload", "Tiered support playbook")],
            actions=[
                "Ship smallest viable value loop.",
                "Measure week-1 and week-4 retention.",
                "Interview churned users every week.",
                "Gate roadmap by usage proof.",
            ],
            archetype="narrative",
        ),
        DeckSpec(
            name="Public Health Response Coordination",
            preset="lab-report",
            subtitle="Operational readiness for distributed response teams",
            objective="Coordinate data, labs, and field teams with one evidence-driven command cadence.",
            pillars=[
                "Early signal detection and triage.",
                "Inter-agency workflow interoperability.",
                "Transparent reporting for policy decisions.",
            ],
            milestones=[("Stage A", "Signal ingest"), ("Stage B", "Triage network"), ("Stage C", "Regional response"), ("Stage D", "Outcome review")],
            risks=[("Data fragmentation", "Unified schema and mapping"), ("Coordination delay", "Standard handoff protocol"), ("Public confusion", "Single source status dashboard"), ("Resource imbalance", "Dynamic allocation board")],
            actions=[
                "Define trigger criteria for escalation.",
                "Run weekly inter-agency drills.",
                "Track response time and case closure.",
                "Publish concise daily briefings.",
            ],
            archetype="lab",
        ),
        DeckSpec(
            name="Robotics Manufacturing Ramp",
            preset="midnight-neon",
            subtitle="From prototype to repeatable high-yield production",
            objective="Stabilize yield and throughput before opening new manufacturing lines.",
            pillars=[
                "Process capability and tolerance control.",
                "Supplier quality and inbound reliability.",
                "Factory analytics for root-cause speed.",
            ],
            milestones=[("Line 0", "Process lock"), ("Line 1", "Yield uplift"), ("Line 2", "Throughput targets"), ("Line 3", "Cross-site standardization")],
            risks=[("Yield volatility", "Control charts + stop criteria"), ("Supplier defects", "Incoming lot sampling"), ("Downtime", "Predictive maintenance"), ("Rework cost", "Tight defect taxonomy")],
            actions=[
                "Lock critical process windows first.",
                "Instrument every defect class.",
                "Escalate recurring defects within 24h.",
                "Standardize work instructions per station.",
            ],
            archetype="data",
        ),
        DeckSpec(
            name="Nonprofit Fundraising Transformation",
            preset="warm-terracotta",
            subtitle="Sustainable donor growth with measurable impact proof",
            objective="Increase recurring donor retention through clearer impact loops and donor segmentation.",
            pillars=[
                "Impact storytelling tied to verifiable outcomes.",
                "Segmented donor journeys and lifecycle messaging.",
                "Operational cadence for campaign optimization.",
            ],
            milestones=[("Month 1", "Donor baseline"), ("Month 3", "Journey redesign"), ("Month 6", "Retention lift"), ("Month 9", "Scale channels")],
            risks=[("Message fatigue", "Cadence controls + tests"), ("Attribution gaps", "Unified campaign taxonomy"), ("Team bandwidth", "Content calendar automation"), ("Trust loss", "Transparent impact reporting")],
            actions=[
                "Define top retention drivers.",
                "Test segment-specific narratives.",
                "Publish monthly impact snapshots.",
                "Promote winning patterns into templates.",
            ],
            archetype="narrative",
        ),
    ]


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark deck generation across diverse themes.")
    parser.add_argument(
        "--outdir",
        default="/tmp/pptx-benchmark-10",
        help="Output directory for benchmark artifacts",
    )
    parser.add_argument(
        "--max-loops",
        type=int,
        default=3,
        help="Max iteration loops passed to iterate_deck.py",
    )
    parser.add_argument(
        "--skip-render",
        action="store_true",
        help="Skip rendering during QA (faster benchmark)",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    base_dir = Path(args.outdir).expanduser().resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    py = sys.executable
    scripts = Path(__file__).resolve().parent
    results: list[dict[str, Any]] = []

    for idx, spec in enumerate(_deck_specs(), start=1):
        slug = f"{idx:02d}-{_slugify(spec.name)}"
        deck_dir = base_dir / slug
        deck_dir.mkdir(parents=True, exist_ok=True)

        outline_path = deck_dir / "outline.json"
        draft_path = deck_dir / "draft.pptx"
        final_path = deck_dir / "final.pptx"
        iter_dir = deck_dir / "iterations"
        qa_dir = deck_dir / "qa"
        qa_report = qa_dir / "report.json"

        outline = _outline_for(spec, deck_dir)
        outline_path.write_text(json.dumps(outline, indent=2), encoding="utf-8")

        build_cmd = [
            "node",
            str(scripts / "build_deck_pptxgenjs.js"),
            "--outline",
            str(outline_path),
            "--output",
            str(draft_path),
            "--style-preset",
            spec.preset,
        ]
        build_rc, build_out = _run(build_cmd)

        qa_rc, qa_out, qa_payload = _run_qa(
            py=py,
            scripts=scripts,
            input_path=draft_path,
            qa_dir=qa_dir,
            qa_report=qa_report,
            outline_path=outline_path,
            preset=spec.preset,
            skip_render=args.skip_render,
        )
        iter_rc = 0
        iter_out = "skipped: renderer draft passed QA\n"
        iter_payload: dict[str, Any] = {"converged": True, "loops_executed": 0}
        output_path = draft_path

        if build_rc == 0 and qa_rc != 0 and args.max_loops > 0:
            iter_cmd = [
                py,
                str(scripts / "iterate_deck.py"),
                "--input",
                str(draft_path),
                "--output",
                str(final_path),
                "--style-preset",
                spec.preset,
                "--max-loops",
                str(args.max_loops),
                "--outdir",
                str(iter_dir),
            ]
            if args.skip_render:
                iter_cmd.append("--skip-render")
            iter_rc, iter_out = _run(iter_cmd)
            output_path = final_path if final_path.exists() else draft_path
            qa_rc, qa_out, qa_payload = _run_qa(
                py=py,
                scripts=scripts,
                input_path=output_path,
                qa_dir=qa_dir,
                qa_report=qa_report,
                outline_path=outline_path,
                preset=spec.preset,
                skip_render=args.skip_render,
            )
            iter_payload = _load_json(iter_dir / "iteration_report.json")
        elif build_rc == 0:
            shutil.copy2(draft_path, final_path)
            output_path = final_path
        passed = (
            qa_rc == 0
            and qa_payload.get("issue_shape_count", 0) == 0
            and qa_payload.get("overflow_count", 0) == 0
            and qa_payload.get("overlap_count", 0) == 0
            and qa_payload.get("geometry_error_count", 0) == 0
            and qa_payload.get("visual_warning_count", 0) == 0
            and qa_payload.get("design_error_count", 0) == 0
            and qa_payload.get("design_warning_count", 0) == 0
        )

        result = {
            "deck": spec.name,
            "preset": spec.preset,
            "archetype": spec.archetype,
            "path": str(output_path),
            "passed": passed,
            "build_rc": build_rc,
            "iter_rc": iter_rc,
            "qa_rc": qa_rc,
            "issue_shape_count": qa_payload.get("issue_shape_count", 0),
            "overflow_count": qa_payload.get("overflow_count", 0),
            "overlap_count": qa_payload.get("overlap_count", 0),
            "geometry_error_count": qa_payload.get("geometry_error_count", 0),
            "geometry_warning_count": qa_payload.get("geometry_warning_count", 0),
            "visual_warning_count": qa_payload.get("visual_warning_count", 0),
            "design_error_count": qa_payload.get("design_error_count", 0),
            "design_warning_count": qa_payload.get("design_warning_count", 0),
            "font_families": qa_payload.get("font_families", []),
            "converged": iter_payload.get("converged"),
            "build_stdout_tail": build_out[-1000:],
            "iter_stdout_tail": iter_out[-1000:],
            "qa_stdout_tail": qa_out[-1000:],
        }
        results.append(result)
        print(
            f"[{idx:02d}/10] {spec.name} ({spec.preset}) -> "
            f"{'PASS' if passed else 'FAIL'} | "
            f"issues={result['issue_shape_count']} geo_err={result['geometry_error_count']} "
            f"visual_warn={result['visual_warning_count']} design_warn={result['design_warning_count']}"
        )

    summary = {
        "total": len(results),
        "passed": sum(1 for item in results if item["passed"]),
        "failed": sum(1 for item in results if not item["passed"]),
        "results": results,
    }
    summary_path = base_dir / "benchmark_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md_lines = [
        "# PPTX Benchmark Summary",
        "",
        f"- Total: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        "",
        "| Deck | Preset | Archetype | Pass | Issues | Overflow | Overlap | Geo Errors | Geo Warnings | Visual Warn | Design Warn |",
        "|------|--------|-----------|------|--------|----------|---------|------------|--------------|-------------|-------------|",
    ]
    for item in results:
        md_lines.append(
            "| {deck} | `{preset}` | `{archetype}` | {passed} | {issues} | {overflow} | {overlap} | {geo_err} | {geo_warn} | {visual_warn} | {design_warn} |".format(
                deck=item["deck"],
                preset=item["preset"],
                archetype=item["archetype"],
                passed="yes" if item["passed"] else "no",
                issues=item["issue_shape_count"],
                overflow=item["overflow_count"],
                overlap=item["overlap_count"],
                geo_err=item["geometry_error_count"],
                geo_warn=item["geometry_warning_count"],
                visual_warn=item["visual_warning_count"],
                design_warn=item["design_warning_count"],
            )
        )
    (base_dir / "benchmark_summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Benchmark summary: {summary_path}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
