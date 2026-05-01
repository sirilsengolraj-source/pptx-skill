# Power and Coal

This workspace is the saved authoring source for the `power-and-coal` deck.

## Files

- `outline.json`: canonical structured slide source
- `style_contract.json`: stable style + layout contract for later slide additions
- `asset_plan.json`: source-backed imagery/background/chart staging plan
- `notes.md`: deck-specific data sources, decisions, and manual design notes
- `assets/`: local images, diagrams, logos, and tables used by the deck
- `build/`: generated `.pptx` output plus QA reports

## Commands

Build the deck:

```bash
python3 ../../scripts/build_workspace.py --workspace . --overwrite
```

Build and run strict QA:

```bash
python3 ../../scripts/build_workspace.py --workspace . --qa --overwrite
```

Use non-render QA when LibreOffice is unavailable:

```bash
python3 ../../scripts/build_workspace.py --workspace . --qa --skip-render --overwrite
```

Allow Wikimedia Commons fetches while staging assets:

```bash
python3 ../../scripts/build_workspace.py --workspace . --allow-network-assets --overwrite
```

## Iteration Pattern

1. Update `notes.md` with sources, data rules, and slide-specific constraints.
2. Add source-backed image/background/chart requests to `asset_plan.json`.
3. Stage local assets inside `assets/` when needed.
4. Edit `outline.json` to add, replace, or reorder slides.
5. Reference staged assets with aliases such as `asset:hero_name` or `image:crew_portrait`.
6. Re-run `build_workspace.py`.
7. Keep the source files. Do not rely on inline heredoc generation if you want to extend the deck later.
