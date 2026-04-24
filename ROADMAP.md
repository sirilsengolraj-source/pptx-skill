# pptx-skill Improvement Plan

This roadmap keeps improvement loops concrete and publishable. Each loop should
ship only after the saved-workspace example builds and passes QA.

## North Star

Generate editable PowerPoint decks that are cleaner and more reliable than
generic native slide generation: aligned layouts, readable hierarchy, strong
visual rhythm, traceable sources, and no overlapping elements.

## Quality Goals

- Zero text overflow and zero object overlap on release examples.
- Wrapped titles must push subtitles and body content down automatically.
- Every content slide should have a clear visual anchor: image, chart, icon
  system, table, diagram, large KPI, or strong two-column composition.
- Optional generated imagery must be standalone, visibly labeled, and removable.
- Normal deck generation must not reinstall dependencies or require LibreOffice.

## Iteration Loops

1. **Layout Reliability Loop**
   - Expand synthetic benchmark decks across title lengths, dense cards, tables,
     timelines, generated-image slides, and chart-heavy slides.
   - Promote recurring QA warnings into preflight guidance when they are
     source-authoring problems.
   - Release gate: benchmark examples show zero overflow and zero overlap.

2. **Visual Richness Loop**
   - Improve asset planning so agents select one of: source-backed image,
     mermaid diagram, chart, icon set, generated-image slide, or no visual with
     explicit rationale.
   - Add stronger topic-to-preset and topic-to-icon heuristics.
   - Release gate: no 5+ slide deck ships as text-only unless `notes.md`
     explains why.

3. **Evidence And Facts Loop**
   - Add a fact/evidence staging format for sourced metrics, quotes, and dates.
   - Render source-aware KPI, chart, and evidence-card slides from the same
     staged data.
   - Release gate: sourced-number slides include compact footer provenance and
     pass placeholder/source lint.

4. **Generated Image Loop**
   - Keep OpenAI image generation optional and API-key gated.
   - Generate only staged assets with prompt/model/purpose metadata.
   - Land each generated asset on a `generated-image` slide by default.
   - Release gate: generated-image smoke test passes preflight and QA with no
     overlap/overflow.

5. **Open-Source Hygiene Loop**
   - Do not vendor third-party helper code into the public repo.
   - Depend only on declared npm/Python packages or repo-owned code.
   - Keep license language scoped to original repo code and third-party
     dependencies.
   - Release gate: search finds no third-party helper code, no unstaged
     generated build outputs, and no undocumented runtime install path.

## Push Criteria

Before pushing a skill release:

1. `python3 -m py_compile` passes for edited Python scripts.
2. `node --check` passes for edited JS templates/renderers.
3. At least one generated-image smoke build passes preflight and QA.
4. A saved workspace deck builds through `build_workspace.py --qa --overwrite`
   or the specific limitation is documented.
5. `git status` is reviewed so unrelated local artifacts are not accidentally
   committed.
