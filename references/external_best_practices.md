# External Best Practices Integrated

This file records the public ideas benchmarked while keeping the bundled repository code independent.

## Sources Consulted

- PptxGenJS: https://github.com/gitbrent/PptxGenJS
- `pptx-automizer`: https://github.com/singerla/pptx-automizer
- Public presentation-engineering repos and docs for layout and QA patterns

These sources informed the workflow shape and the quality bar. Their code is not redistributed here.

## Imported Patterns

1. **Artifact-driven pipeline**
- Keep reproducible outputs: `outline`, `issues`, `renders`, `reports`.
- Write QA artifacts to stable per-run folders.

2. **Deterministic quality gates**
- Overflow/overlap scan (`inventory.py --issues-only`).
- Geometry and density lint (`layout_lint.py`).
- Visual and design warnings promoted into the final gate (`qa_gate.py`).

3. **Iterative remediation**
- Bounded auto-fix loop (`iterate_deck.py`) with explicit loop limits.
- Deterministic text-fit policy (`text_fit.py`) before delivery.
- Multi-deck regression harness (`benchmark_decks.py`) to catch systemic layout regressions.

4. **Geometry discipline**
- Shared edge alignment checks for rows and columns.
- Rail-to-card coherence checks so accent bars and card bodies stay consistent.
- Margin, gutter, and footer-safe validation.

5. **Dual-render comparison without vendoring**
- Keep the reliable builder in-repo.
- Keep renderer dependencies explicit and repo-owned. External tools should be
  optional CLIs such as LibreOffice, Poppler, or Mermaid CLI, not hidden deck
  rendering stacks.

## Where Enforced

- `scripts/build_deck.py`
- `scripts/qa_gate.py`
- `scripts/layout_lint.py`
- `scripts/visual_qa.py`
- `scripts/design_rules_qa.py`
- `scripts/iterate_deck.py`
