#!/usr/bin/env python3
"""Render Mermaid source to a PNG without depending on another skill.

Preferred path: use `mmdc` (Mermaid CLI) when it is already installed.
Fallback path: draw a simple left-to-right flow diagram with Pillow. The
fallback is intentionally conservative but keeps deck builds open-source and
offline-friendly.
"""

from __future__ import annotations

import argparse
import math
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
            return
        if label is not None:
            labels[node_id] = _clean_label(label, node_id)

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("%") or line.startswith("%%"):
            continue
        lowered = line.lower()
        if lowered.startswith(("classdef ", "class ", "style ", "linkstyle ")):
            continue
        if ":::" in line and not any(token in line for token in ("-->", "---", "==>")):
            continue
        if lowered.startswith(("flowchart", "graph", "sequencediagram", "subgraph", "end")):
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

    def balanced_rows(values: list[str], max_per_row: int) -> list[list[str]]:
        if not values:
            return []
        row_count = max(1, math.ceil(len(values) / max_per_row))
        base = len(values) // row_count
        extra = len(values) % row_count
        rows: list[list[str]] = []
        cursor = 0
        for row_idx in range(row_count):
            size = base + (1 if row_idx < extra else 0)
            rows.append(values[cursor : cursor + size])
            cursor += size
        return rows

    nodes, labels, edges = _parse_mermaid(input_path.read_text(encoding="utf-8"))
    max_per_row = 4
    rows = balanced_rows(nodes, max_per_row)
    cols = max((len(row) for row in rows), default=1)
    box_w = 230
    box_h = 104
    gap_x = 42
    gap_y = 46
    margin_x = 44
    margin_y = 34
    width = max(820, margin_x * 2 + cols * box_w + max(0, cols - 1) * gap_x)
    height = max(470, margin_y * 2 + len(rows) * box_h + max(0, len(rows) - 1) * gap_y)

    image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    try:
        body_font = ImageFont.truetype("Arial.ttf", 20)
    except OSError:
        body_font = ImageFont.load_default()

    positions: dict[str, tuple[int, int, int, int]] = {}
    for row_idx, row in enumerate(rows):
        row_width = len(row) * box_w + max(0, len(row) - 1) * gap_x
        start_x = (width - row_width) // 2
        y = margin_y + row_idx * (box_h + gap_y)
        for idx_in_row, node_id in enumerate(row):
            # Snake long flows so row transitions stay close instead of drawing
            # long diagonal connectors across the whole canvas.
            visual_col = idx_in_row if row_idx % 2 == 0 else len(row) - 1 - idx_in_row
            x = start_x + visual_col * (box_w + gap_x)
            positions[node_id] = (x, y, x + box_w, y + box_h)

    def _connector(
        source: tuple[int, int, int, int],
        target: tuple[int, int, int, int],
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        sx1, sy1, sx2, sy2 = source
        tx1, ty1, tx2, ty2 = target
        scx = (sx1 + sx2) / 2
        scy = (sy1 + sy2) / 2
        tcx = (tx1 + tx2) / 2
        tcy = (ty1 + ty2) / 2
        dx = tcx - scx
        dy = tcy - scy
        if abs(dx) >= abs(dy):
            if dx >= 0:
                return (sx2, scy), (tx1, tcy)
            return (sx1, scy), (tx2, tcy)
        if dy >= 0:
            return (scx, sy2), (tcx, ty1)
        return (scx, sy1), (tcx, ty2)

    def _draw_arrow(start: tuple[float, float], end: tuple[float, float]) -> None:
        draw.line([start, end], fill=(11, 107, 120, 255), width=4)
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = max(1.0, math.hypot(dx, dy))
        ux = dx / length
        uy = dy / length
        px = -uy
        py = ux
        size = 16
        wing = 8
        arrow = [
            (end[0], end[1]),
            (end[0] - ux * size + px * wing, end[1] - uy * size + py * wing),
            (end[0] - ux * size - px * wing, end[1] - uy * size - py * wing),
        ]
        draw.polygon(arrow, fill=(11, 107, 120, 255))

    for left, right in edges:
        if left not in positions or right not in positions:
            continue
        _draw_arrow(*_connector(positions[left], positions[right]))

    for idx, node_id in enumerate(nodes):
        x1, y1, x2, y2 = positions[node_id]
        fill = (244, 248, 251, 255) if idx % 2 == 0 else (255, 255, 255, 255)
        draw.rectangle([x1, y1, x2, y2], fill=fill, outline=(7, 30, 58, 255), width=3)
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
