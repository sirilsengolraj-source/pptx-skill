# Alignment and Visual Coherence

Use this checklist for every deck when alignment and polish matter.

## Non-Negotiables

1. Use a grid and keep shared edges aligned (cards, columns, icon rows).
2. Keep consistent spacing increments (for example, 0.3" or 0.5" rhythm).
3. Keep strong typographic hierarchy (title/section/body/caption).
4. Keep limited font families (target <= 3 in one deck).
5. Keep high contrast on dark backgrounds.
6. Keep one visual motif repeated across slides.

## Execution Pattern

1. Build or edit deck.
2. Run issue detection:
   - `python3 scripts/inventory.py output.pptx issues.json --issues-only`
3. Render slides:
   - `python3 scripts/render_slides.py --input output.pptx --outdir /tmp/slide-review`
4. Run QA gate:
   - `python3 scripts/qa_gate.py --input output.pptx --outdir /tmp/pptx-qa --style-preset executive-clinical --strict-geometry`
5. Optionally run the iterative fix loop first:
   - `python3 scripts/iterate_deck.py --input output.pptx --output output.pptx --style-preset executive-clinical --max-loops 3 --outdir /tmp/pptx-iterations`
6. Fix and re-verify.

## Common Failure Modes

- Text box widths differ slightly across visually similar cards.
- Inconsistent left edges between heading and body regions.
- Rows look misaligned because internal text padding differs.
- Long titles wrap unexpectedly and break top alignment.
- Footer bars/callouts use cramped text heights.
- Slide mixes too many font families, reducing coherence.

## Tool-Specific Notes

- `python-pptx`: set predictable text frame margins for consistent alignment.
- `PptxGenJS`: use `margin: 0` when precise edge alignment is required.
- Render-based QA should run sequentially. Parallel `soffice` conversions can flap and create false failures.

## Quality Gate (Recommended Thresholds)

- Distinct font families: <= 3
- Text overflow issues: 0
- Overlap issues: 0
- Visual defects found in render pass: resolved before delivery
