# Creating Decks From Scratch

**Before anything else, read `references/codex_guardrails.md`.** It covers the
four shortcuts that produce broken decks. The steps below assume you will not
take those shortcuts.

For scratch builds, use this order:

1. Read `references/outline_schema.md` for the accepted deck structure.
2. Read `references/planning_schema.md` when the deck needs sourced facts,
   evidence, charts, or later extension.
3. Read `references/reproducible_workflow.md` for style and QA requirements.
4. Write `outline.json`. Do **not** write inline python-pptx. If the schema
   doesn't cover what you need, extend the outline, not the builder.
5. Generate the initial draft:

```bash
node scripts/build_deck_pptxgenjs.js --outline outline.json --output draft.pptx --style-preset executive-clinical
```

6. Run the strict QA gate (non-optional — use `--skip-render` if LibreOffice is absent, but never skip the gate itself):

```bash
python3 scripts/qa_gate.py \
  --input draft.pptx \
  --outdir /tmp/pptx-qa \
  --style-preset executive-clinical \
  --strict-geometry \
  --fail-on-visual-warnings \
  --fail-on-design-warnings
```

7. If the draft fails, run the iterative QA loop (bounded at 3 loops, never unbounded):

```bash
python3 scripts/iterate_deck.py --input draft.pptx --output draft.pptx --style-preset executive-clinical --max-loops 3 --outdir /tmp/pptx-iterations
```
