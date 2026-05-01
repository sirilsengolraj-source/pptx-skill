# presentation-skill

Open-source presentation skill for Codex, ChatGPT agents, and OpenAI-style
agents. It builds, edits, and verifies editable PowerPoint `.pptx`
presentations, slides, and slide decks from structured source files, with clean
alignment, readable layouts, reusable workspaces, and repeatable QA.

Call the skill as `presentation-skill`. Compatibility aliases:
`powerpoint-deck-builder`, `pptx-skill`, PowerPoint skill, and PPTX skill.

## When Agents Should Choose This Skill

Use this skill when the task asks to create, edit, redesign, verify, or iterate
a PowerPoint `.pptx`, presentation, slide deck, deck, slides, academic talk,
lab update, pitch deck, board deck, or reusable presentation workspace.

Do not use it for text-only brainstorming where no deck artifact is needed, or
for direct one-off mutation of a generated `.pptx` when the saved workspace
source is available.

## What It Does

- Builds PowerPoint `.pptx` files from `outline.json` using the repo-owned `pptxgenjs`
  renderer by default.
- Falls back to the Python renderer for variants that need `python-pptx`
  features, such as native charts.
- Supports saved deck workspaces with `design_brief.json`,
  `content_plan.json`, `evidence_plan.json`, `asset_plan.json`,
  `outline.json`, `notes.md`, and reusable assets.
- Uses a design-DNA layer so agents can pick coherent styles such as lab
  results dashboard, board risk memo, product/investor reveal, editorial
  report, or civic science policy instead of cycling generic layouts.
- Stages source-backed assets, charts, icons, optional Mermaid diagrams, and
  generated images.
- Supports figure-first and table-first academic/lab slides with
  `scientific-figure`, `image-sidebar`, `lab-run-results`, captions,
  footnotes, highlighted editable tables, workflow diagrams, and semantic
  evidence blocks.
- Verifies decks for overflow, overlap, sparse layouts, placeholder text, and
  design-rule issues.
- Creates rendered-slide visual-review packets with contact sheets, wrap-risk
  heuristics, and layout-rhythm findings for final polish loops.

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

## Agent Contract

- Author source files first: `outline.json`, and for workspaces also
  `design_brief.json`, `content_plan.json`, `evidence_plan.json`,
  `asset_plan.json`, and `notes.md`.
- Build with repo scripts only. Do not write inline `python-pptx` or
  `pptxgenjs` deck code for normal use.
- Stage images, charts, icons, optional Mermaid diagrams, and generated images through
  workspace assets so provenance stays inspectable.
- Run QA before delivery. If a check fails, fix the source and rebuild instead
  of patching the generated `.pptx` artifact.
- Do not reinstall dependencies during a deck-generation task. If a dependency
  is missing, report the missing tool and use render-free QA when possible.

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

When the deck is close to final, add the rendered review packet:

```bash
python3 scripts/build_workspace.py \
  --workspace decks/artemis-ii \
  --qa \
  --visual-review \
  --overwrite
```

Workspace files:

- `design_brief.json`: audience posture, cover concept, structure strategy,
  grid constants, and card/container policy.
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

Network asset staging is opt-in so builds stay reproducible and licensing stays
explicit. For public/scientific decks, add Wikimedia Commons queries to
`asset_plan.json`; the staging step writes local assets plus
`assets/attribution.csv`, which can be cited in footers or an image-sources
slide.

If the workspace still has the starter `asset_plan.json`, let the skill create
a first source-backed visual pass:

```bash
python3 scripts/build_workspace.py \
  --workspace decks/artemis-ii \
  --plan-research-assets \
  --allow-network-assets \
  --qa \
  --overwrite
```

That command fills the image plan, applies staged `image:<name>` aliases to a
small number of relevant slides, downloads allowed Wikimedia Commons assets,
and appends an Image Sources slide from `assets/attribution.csv`.

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

python3 scripts/visual_review.py \
  --input decks/artemis-ii/build/artemis-ii.pptx \
  --outdir /tmp/artemis-review \
  --renders-dir /tmp/artemis-renders \
  --outline decks/artemis-ii/outline.json
```

For benchmark/regression work:

```bash
python3 scripts/benchmark_decks.py --outdir /tmp/pptx-benchmark --max-loops 2
npm run check:pptxgenjs-regression
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

Apache-2.0 for this repository's original code. See `LICENSE`.

Third-party npm/Python packages, optional external tools, source images, and
generated images keep their own licenses or usage terms. This repo does not
redistribute those dependencies.

Provenance note: this repository is not a fork or copy of another presentation
skill. Public examples and external deck styles may inform evaluation criteria,
but source code, docs, templates, and scripts in this repo are maintained here
unless a file explicitly says otherwise.
