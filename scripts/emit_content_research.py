#!/usr/bin/env python3
"""Emit a subagent prompt that pushes for concrete content, not hedged prose.

Different from `emit_outline_critique.py`: that script critiques layout
and composition. This one targets the CONTENT QUALITY axis — specifically,
"are the claims on this slide researched and concrete, or hedged and
generic?"

Use this before the final rebuild. The research subagent's job is to
return a punch list of specific facts (years, named entities, figures,
cases) the author should fold into the outline. It does not rewrite the
outline; it surfaces missing substance.

Usage:
    python3 scripts/emit_content_research.py --outline outline.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_PROMPT_HEADER = """\
You are a research reviewer for a .pptx outline. Your job is to decide
whether each content slide is load-bearing (has at least one concrete,
verifiable fact) or hedged (uses words like "usually", "often", "can
be", "tends to", without anchoring to specifics).

Read these refs first:
- {design_philosophy}
- {codex_guardrails}

For EACH content slide in the outline below, do the following:

1. **Classify** the slide as:
   - LOAD-BEARING: has ≥1 concrete anchor per bullet (year, percentage,
     named person/place/org with a role, $ figure, quantity with unit).
   - HEDGED: prose reads as generic; bullets could apply to many topics.

2. For every HEDGED slide, propose **2-3 concrete substitutions** the
   author should research. Format:
   - Weak bullet: (quote the current bullet)
   - Replace with a specific version: (draft a bullet with a real
     number/date/name the author can verify)
   - Suggested source type: (one of: primary source [IAEA, NRC],
     encyclopedia [Wikipedia], named study, industry report)

3. Flag bullets that are **likely wrong** or internally inconsistent with
   other slides (e.g., dates that don't line up, claims that contradict
   the stated theme).

4. Flag any slide that would benefit from a **chart, table, or diagram**
   (parallel fields, numeric comparison, sequential process). Say which
   variant would fit:
   - `variant: table` — parallel-field rows (entity + date + role + metric)
   - `variant: chart` — numeric comparison or trend
   - `variant: kpi-hero` — one specific number that anchors the deck
   - `variant: comparison-2col` — before/after, us/them, hypothesis/result
   - `visual_intent: flow` with `assets.mermaid_source` — boxes-and-arrows

Do NOT rewrite the outline. Produce a slide-indexed punch list the author
can apply. Under 500 words. Be specific — "add a fact" is useless;
"add the 1957 founding date of the IAEA" is actionable.

--- Outline JSON ---

{outline_json}
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit a subagent prompt for content-quality review."
    )
    parser.add_argument("--outline", required=True, help="Path to outline.json")
    parser.add_argument("--output", help="Write prompt to file (default: stdout)")
    parser.add_argument(
        "--truncate-outline",
        type=int,
        default=10000,
        help="Max chars of outline.json to inline (default 10000).",
    )
    args = parser.parse_args()

    outline_path = Path(args.outline).expanduser().resolve()
    if not outline_path.exists():
        print(f"Error: outline not found: {outline_path}", file=sys.stderr)
        return 1
    try:
        json.loads(outline_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Error: outline malformed: {exc}", file=sys.stderr)
        return 2

    outline_text = outline_path.read_text(encoding="utf-8")
    if len(outline_text) > args.truncate_outline:
        outline_text = (
            outline_text[: args.truncate_outline]
            + f"\n\n... [truncated at {args.truncate_outline} chars; full outline at {outline_path}]"
        )

    repo_root = Path(__file__).resolve().parent.parent
    refs = {
        "design_philosophy": str(repo_root / "references" / "design_philosophy.md"),
        "codex_guardrails": str(repo_root / "references" / "codex_guardrails.md"),
    }

    prompt = _PROMPT_HEADER.format(outline_json=outline_text, **refs)

    if args.output:
        Path(args.output).expanduser().resolve().write_text(prompt, encoding="utf-8")
        print(f"Content-research prompt written to {args.output}", file=sys.stderr)
    else:
        print("=" * 72)
        print("CONTENT-RESEARCH SUBAGENT PROMPT (paste into an Explore agent)")
        print("=" * 72)
        print(prompt)
        print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
