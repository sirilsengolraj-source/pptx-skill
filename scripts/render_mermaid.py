#!/usr/bin/env python3
"""Render Mermaid source to a PNG without depending on another skill.

Preferred path: use `mmdc` (Mermaid CLI) when it is already installed.
Fallback path: draw a simple left-to-right flow diagram with Pillow. The
fallback is intentionally conservative but keeps deck builds open-source and
offline-friendly.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


EDGE_RE = re.compile(
    r"^\s*([A-Za-z0-9_]+)(?:\s*(?:\[([^\]]+)\]|\(([^)]+)\)|\{([^}]+)\}))?\s*[-=.]+>\s*"
    r"([A-Za-z0-9_]+)(?:\s*(?:\[([^\]]+)\]|\(([^)]+)\)|\{([^}]+)\}))?"
)
NODE_RE = re.compile(r"^\s*([A-Za-z0-9_]+)\s*(?:\[([^\]]+)\]|\(([^)]+)\)|\{([^}]+)\})")


def _clean_label(value: str | None, fallback: str) -> str:
    text = (value or fallback).strip().strip('"').strip("'")
    return re.sub(r"\s+", " ", text) or fallback


def _parse_mermaid(text: str) -> tuple[list[str], dict[str, str], list[tuple[str, str]]]:
    nodes: list[str] = []
    labels: dict[str, str] = {}
    edges: list[tuple[str, str]] = []

    def add_node(node_id: str, label: str | None = None) -> None:
        if node_id not in labels:
            nodes.append(node_id)
        labels[node_id] = _clean_label(label, node_id)

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("%") or line.startswith("%%"):
            continue
        if line.lower().startswith(("flowchart", "graph", "sequenceDiagram", "subgraph", "end")):
            continue
        edge = EDGE_RE.match(line)
        if edge:
            left, l1, l2, l3, right, r1, r2, r3 = edge.groups()
            add_node(left, l1 or l2 or l3)
            add_node(right, r1 or r2 or r3)
            edges.append((left, right))
            continue
        node = NODE_RE.match(line)
        if node:
            node_id, n1, n2, n3 = node.groups()
            add_node(node_id, n1 or n2 or n3)

    if not nodes:
        nodes = ["A", "B", "C"]
        labels = {
            "A": "Start",
            "B": "Process",
            "C": "Outcome",
        }
        edges = [("A", "B"), ("B", "C")]
    return nodes, labels, edges


def _render_with_mmdc(input_path: Path, output_path: Path) -> bool:
    mmdc = shutil.which("mmdc")
    if not mmdc:
        return False
    cmd = [
        mmdc,
        "-i",
        str(input_path),
        "-o",
        str(output_path),
        "-b",
        "transparent",
        "--scale",
        "2",
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0 and output_path.exists():
        return True
    print(
        "[render_mermaid] mmdc failed; falling back to native renderer: "
        + (result.stderr.strip() or result.stdout.strip() or "no output"),
        file=sys.stderr,
    )
    return False


def _render_fallback(input_path: Path, output_path: Path) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Pillow is required for Mermaid fallback rendering when mmdc is unavailable") from exc

    nodes, labels, edges = _parse_mermaid(input_path.read_text(encoding="utf-8"))
    width = max(1100, 280 * len(nodes))
    height = 520
    margin = 80
    box_w = min(240, max(170, (width - margin * 2) // max(1, len(nodes)) - 36))
    box_h = 92
    y = height // 2 - box_h // 2

    image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    try:
        title_font = ImageFont.truetype("Arial Bold.ttf", 24)
        body_font = ImageFont.truetype("Arial.ttf", 20)
    except OSError:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

    positions: dict[str, tuple[int, int, int, int]] = {}
    if len(nodes) == 1:
        xs = [width // 2 - box_w // 2]
    else:
        step = (width - margin * 2 - box_w) / (len(nodes) - 1)
        xs = [int(margin + step * i) for i in range(len(nodes))]

    for idx, node_id in enumerate(nodes):
        x = xs[idx]
        positions[node_id] = (x, y, x + box_w, y + box_h)

    for left, right in edges:
        if left not in positions or right not in positions:
            continue
        lx1, ly1, lx2, ly2 = positions[left]
        rx1, ry1, rx2, ry2 = positions[right]
        start = (lx2, (ly1 + ly2) // 2)
        end = (rx1, (ry1 + ry2) // 2)
        draw.line([start, end], fill=(11, 107, 120, 255), width=4)
        draw.polygon(
            [(end[0], end[1]), (end[0] - 14, end[1] - 8), (end[0] - 14, end[1] + 8)],
            fill=(11, 107, 120, 255),
        )

    for idx, node_id in enumerate(nodes):
        x1, y1, x2, y2 = positions[node_id]
        fill = (244, 248, 251, 255) if idx % 2 == 0 else (255, 255, 255, 255)
        draw.rounded_rectangle([x1, y1, x2, y2], radius=18, fill=fill, outline=(7, 30, 58, 255), width=3)
        draw.rectangle([x1, y1, x2, y1 + 10], fill=(245, 158, 11, 255))
        label = labels.get(node_id, node_id)
        words = label.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), candidate, font=body_font)
            if bbox[2] - bbox[0] <= box_w - 24:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        lines = lines[:3]
        line_h = 23
        total_h = line_h * len(lines)
        ty = y1 + (box_h - total_h) // 2
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=body_font)
            tx = x1 + (box_w - (bbox[2] - bbox[0])) // 2
            draw.text((tx, ty), line, fill=(15, 23, 42, 255), font=body_font)
            ty += line_h

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Mermaid source to PNG.")
    parser.add_argument("--input", required=True, help="Input .mmd/.mermaid file")
    parser.add_argument("--output", required=True, help="Output PNG path")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Mermaid source not found: {input_path}")
    if _render_with_mmdc(input_path, output_path):
        return 0
    _render_fallback(input_path, output_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
