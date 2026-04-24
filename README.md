# presentation-skill

Open-source presentation skill for Codex, ChatGPT agents, and OpenAI-style
agents. It builds, edits, and verifies editable PowerPoint `.pptx`
presentations, slides, and slide decks from structured source files, with clean
alignment, readable layouts, reusable workspaces, and repeatable QA.

Call the skill as `presentation-skill`. Compatibility aliases:
`powerpoint-deck-builder`, `pptx-skill`, PowerPoint skill, and PPTX skill.

## What It Does

- Builds PowerPoint `.pptx` files from `outline.json` using the repo-owned `pptxgenjs`
  renderer by default.
- Falls back to the Python renderer for variants that need `python-pptx`
  features, such as charts and image-sidebar layouts.
- Supports saved deck workspaces with `content_plan.json`,
  `evidence_plan.json`, `asset_plan.json`, `outline.json`, `notes.md`, and
  reusable assets.
- Stages source-backed assets, charts, icons, Mermaid diagrams, and optional
  generated images.
- Verifies decks for overflow, overlap, sparse layouts, placeholder text, and
  design-rule issues.

## Install

Clone or copy this repo into:

```bash
$CODEX_HOME/skills/presentation-skill
```

Codex, ChatGPT agents, and other OpenAI-style agents should trigger it for
requests involving PowerPoint, PPTX, slide decks, slides, presentation design,
deck generation, deck editing, layout QA, or reusable presentation workspaces.

Search aliases: PowerPoint skill, PPTX skill, presentation skill, slide deck
generator, slides generator, deck builder, presentation generator.

Install dependencies once from the repo root:

```bash
pip install python-pptx "markitdown[pptx]"
npm install
```

Core generation does not require LibreOffice. Render-based verification uses
LibreOffice `soffice` and Poppler `pdftoppm` when available.

Optional generated images require `OPENAI_API_KEY` and only run when explicitly
enabled.

## Quick Start

Build directly from an outline:

```bash
node scripts/build_deck_pptxgenjs.js \
  --outline examples/outline.json \
  --output out.pptx \
  --style-preset executive-clinical
```

Run verification without rendering slides:

```bash
python3 scripts/qa_gate.py \
  --input out.pptx \
  --outdir /tmp/pptx-qa \
  --style-preset executive-clinical \
  --strict-geometry \
  --skip-render \
  --fail-on-design-warnings \
  --report /tmp/pptx-qa/report.json
```

## Saved Workspace Flow

Use a workspace when the deck will be extended, audited, or rebuilt later:

```bash
python3 scripts/init_deck_workspace.py \
  --workspace decks/artemis-ii \
  --title "Artemis II Mission Update" \
  --style-preset executive-clinical
```

Edit the workspace source files, then rebuild:

```bash
python3 scripts/build_workspace.py \
  --workspace decks/artemis-ii \
  --qa \
  --overwrite
```

Workspace files:

- `content_plan.json`: audience, thesis, slide roles, and visual strategy.
- `evidence_plan.json`: sourced claims, metrics, chart candidates, and gaps.
- `asset_plan.json`: images, generated images, charts, icons, and backgrounds
  to stage.
- `outline.json`: renderable slide structure.
- `notes.md`: data rules, design decisions, and unresolved assumptions.
- `assets/`: local source-backed images, diagrams, icons, and staged files.
- `build/`: generated deck and verification reports.

## Assets And Generated Images

Stage source-backed assets through `asset_plan.json`:

```bash
python3 scripts/build_workspace.py \
  --workspace decks/artemis-ii \
  --allow-network-assets \
  --overwrite
```

Generated images are optional and should usually land on their own removable
slide:

```bash
OPENAI_API_KEY=... python3 scripts/build_workspace.py \
  --workspace decks/artemis-ii \
  --allow-generated-images \
  --overwrite
```

Use `variant: "generated-image"` and
`assets.generated_image: "generated:<name>"` in `outline.json`. The generated
image slide includes model, prompt, purpose, and a deletion note.

## Verification

For deliverable decks, run the workspace build with QA:

```bash
python3 scripts/build_workspace.py --workspace decks/artemis-ii --qa --overwrite
```

For full visual review, render slides and inspect the generated images:

```bash
python3 scripts/render_slides.py \
  --input decks/artemis-ii/build/artemis-ii.pptx \
  --outdir /tmp/artemis-renders \
  --emit-visual-prompt
```

For benchmark/regression work:

```bash
python3 scripts/benchmark_decks.py --outdir /tmp/pptx-benchmark --max-loops 2
```

## Project Layout

- `SKILL.md`: agent entrypoint.
- `DESIGN.md`: design contract and layout rules.
- `ROADMAP.md`: improvement loops and release criteria.
- `agents/openai.yaml`: Codex/OpenAI skill metadata.
- `scripts/`: renderers, staging, QA, editing, and inspection tools.
- `templates/pptxgenjs/`: default renderer templates and style presets.
- `references/`: schema docs, workflow notes, and QA guidance.

## Licensing

MIT for this repository's original code. See `LICENSE`.

Third-party npm/Python packages, optional external tools, source images, and
generated images keep their own licenses or usage terms. This repo does not
redistribute those dependencies.
