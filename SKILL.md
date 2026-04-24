---
name: presentation-skill
description: "Presentation skill for Codex, ChatGPT agents, and OpenAI-style agents that build, edit, verify, or iterate polished PowerPoint `.pptx` presentations, slides, and slide decks from structured `outline.json` or saved workspaces. Use for editable deck generation, presentation design, source-backed assets, optional generated-image slides, alignment QA, overflow/overlap checks, and reusable deck workspaces. Aliases: `powerpoint-deck-builder`, `pptx-skill`, PowerPoint skill, PPTX skill."
---

# Presentation Skill

Repo-native PowerPoint skill for editable, aligned, QA-checked `.pptx`
decks. The model plans the story and visual strategy; scripts handle fragile
rendering, staging, and verification.

Call this skill as `presentation-skill`. Compatibility aliases:
`powerpoint-deck-builder` and `pptx-skill`.

Search aliases: PowerPoint skill, PPTX skill, presentation skill, slide deck
generator, slides generator, deck builder, presentation generator.

## Non-Negotiables

- Do not write ad hoc inline `python-pptx` or `pptxgenjs` deck code. Author
  `outline.json` and run repo scripts.
- Do not reinstall dependencies during deck generation. Missing dependency:
  report it and stop.
- Do not skip QA for a deliverable deck. Use render-free QA when LibreOffice is
  unavailable.
- Fix source files (`outline.json`, plans, assets, renderer code), not mutated
  `.pptx` artifacts.
- For a new topic, scaffold fresh. Do not clone another deck's structure as a
  house style.

## First Files To Read

- `DESIGN.md`: compact design contract, colors, hierarchy, alignment rules,
  generated-image disclosure.
- `references/outline_schema.md`: accepted `outline.json` fields and variants.
- `references/planning_schema.md`: `content_plan.json` and
  `evidence_plan.json` shape.
- `references/deck_workspace_mode.md`: saved-workspace workflow.
- `references/visual_qa_prompt.md`: fresh-eyes visual inspection prompt.
- `references/editing.md`: only when editing an existing deck.
- `references/pptxgenjs.md`: only when editing JS renderer/templates.

## Workflow

### Quick Deck

Use for one-shot 5-10 slide decks.

```bash
node scripts/build_deck_pptxgenjs.js \
  --outline outline.json \
  --output out.pptx \
  --style-preset <preset>

python3 scripts/qa_gate.py \
  --input out.pptx \
  --outdir /tmp/pptx-qa \
  --style-preset <preset> \
  --strict-geometry \
  --skip-render \
  --fail-on-design-warnings
```

### Saved Workspace

Use when the deck will be extended, audited, or rebuilt later.

```bash
python3 scripts/init_deck_workspace.py \
  --workspace decks/my-deck \
  --title "My Deck" \
  --style-preset <preset>

# edit content_plan.json, evidence_plan.json, asset_plan.json, notes.md, outline.json
python3 scripts/build_workspace.py --workspace decks/my-deck --qa --overwrite
```

Workspace source files:

- `content_plan.json`: thesis, audience, slide roles, visual strategy.
- `evidence_plan.json`: sourced facts, metrics, claims, chart candidates.
- `asset_plan.json`: source-backed images, charts, icons, optional generated images.
- `outline.json`: final renderable deck structure.
- `notes.md`: data rules, manual design choices, unresolved assumptions.

## Renderer Policy

- Default renderer: `scripts/build_deck_pptxgenjs.js`.
- Python fallback: `scripts/build_deck.py`, selected by `build_workspace.py`
  only for variants that need python-pptx features such as native charts.
- Mermaid diagrams render through `scripts/render_mermaid.py`; it uses `mmdc`
  when installed and a repo-native fallback otherwise.
- Generated imagery is optional and API-key gated. It must be staged through
  `asset_plan.json` and placed on `variant: "generated-image"` slides unless
  the user explicitly asks otherwise.

## Design Rules

- Alignment and readability outrank decoration.
- Every content slide needs a visual strategy: image, chart, icon system,
  table, diagram, oversized KPI, or strong two-column composition.
- Wrapped titles must reserve vertical space before subtitles/body content.
- Generated visuals must be labeled with prompt/model/purpose metadata and be
  removable without damaging the narrative.
- Prefer source-backed imagery/facts; use generated imagery for concept visuals
  when source-backed assets are weak or unavailable.

## QA Gate

For final deliverables, run:

```bash
python3 scripts/qa_gate.py \
  --input out.pptx \
  --outdir /tmp/pptx-qa \
  --style-preset <preset> \
  --strict-geometry \
  --fail-on-visual-warnings \
  --fail-on-design-warnings
```

Then render and inspect visually:

```bash
python3 scripts/render_slides.py --input out.pptx --outdir renders/ \
  --emit-visual-prompt
```

Finally check placeholders:

```bash
python -m markitdown out.pptx | grep -iE "\bx{3,}\b|lorem|ipsum|\bTODO|\[insert|\[placeholder"
```

If any check fails, fix source, rebuild, and rerun the affected checks.
