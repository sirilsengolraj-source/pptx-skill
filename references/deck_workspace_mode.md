# Deck Workspace Mode

Use deck workspaces when you want a presentation to behave like a real authored project rather than a one-off generated file.

## Why This Mode Exists

Inline heredoc scripts and ad hoc JSON files are fine for a single pass, but they are weak for later extension. A durable deck needs:

- a saved outline or builder source
- a stable style contract
- staged local assets
- notes about data rules, measurements, and QA decisions
- one command that rebuilds the same deck later

`init_deck_workspace.py` and `build_workspace.py` provide that layer.

## Files In A Workspace

- `outline.json`: canonical structured slide source
- `content_plan.json`: thesis, audience, slide roles, and visual strategy
- `evidence_plan.json`: sourced claims, metrics, chart candidates, and open questions
- `style_contract.json`: style preset, token contract, reference-deck metadata, and build targets
- `asset_plan.json`: source-backed imagery/background/chart staging plan, plus optional generated-image requests
- `notes.md`: sources, data-cleaning rules, coordinate notes, and deck-specific design choices
- `assets/`: local images, diagrams, tables, logos
- `build/`: generated `.pptx` and QA reports

## Commands

Create a workspace:

```bash
python3 scripts/init_deck_workspace.py \
  --workspace decks/my-deck \
  --title "My Deck" \
  --style-preset executive-clinical
```

**New topic = fresh scaffold.** A new deck always scaffolds empty and
gets its outline authored from the topic's own argument arc. Do NOT
clone an existing deck's workspace as a "house style" starting point —
the source's variant mix and structural biases travel with the outline
and every new deck ossifies into the first one's rhythm. The init
script enforces this: if you pass `--source-outline` or
`--reference-pptx` pointing at another deck's workspace under `decks/`,
the script refuses unless you also pass `--followup-edit`.

### When to use `--followup-edit`

- User asks for an update to the SAME deck on the same topic
  (e.g., "add a Q3 slide to the coal deck" or "restyle the energy deck
  with a new palette"). This IS a followup edit. Pass the flag.
- User explicitly asks to start from an existing deck's structure for
  a known reason (e.g., "build a nuclear deck using the coal deck's
  narrative structure because both are energy-source primers"). This
  is a conscious clone decision. Pass the flag, but ALSO plan variant
  substitutions before building — otherwise you'll reproduce the
  source's monotony problems.

### When NOT to use `--followup-edit`

- User asks for a new deck on a new topic. Scaffold fresh.
- Codex would like a "house-style baseline" to write against. No — the
  house style lives in `design_philosophy.md` and the style presets,
  not in any one finished deck.

See `references/codex_guardrails.md` Eighth Trap for the fuller
rationale.

Build from the saved workspace:

```bash
python3 scripts/build_workspace.py --workspace decks/my-deck --qa
```

Allow Wikimedia Commons fetches while staging assets:

```bash
python3 scripts/build_workspace.py --workspace decks/my-deck --allow-network-assets
```

Allow optional OpenAI-generated images while staging assets:

```bash
OPENAI_API_KEY=... python3 scripts/build_workspace.py \
  --workspace decks/my-deck \
  --allow-generated-images
```

Use this only for deliberate concept visuals. Put each generated image on a
`variant: generated-image` slide so the prompt/model/purpose metadata is
visible and the user can delete the slide without breaking the rest of the deck.

### Renderer selection (`--renderer`)

`build_workspace.py` supports two renderers. Both emit the same `.pptx`
format and both are validated by the same `qa_gate.py` afterwards.

| Value | Behavior |
| --- | --- |
| `auto` (default) | Routes to `pptxgenjs` unless the outline uses a python-only variant (`chart`, `image-sidebar`); falls back to `python` in those cases. The chosen renderer is logged to stderr. This is what you want ~99% of the time. |
| `pptxgenjs` | Forces `node scripts/build_deck_pptxgenjs.js`. Richer typography on timeline/stats/kpi-hero/table/section. Covers `standard`, `cards-2/3`, `split`, `comparison-2col`, `matrix`, `timeline`, `stats`, `kpi-hero`, `table`. Fails loudly if `node` or the `pptxgenjs` module is missing. |
| `python` | Forces `scripts/build_deck.py`. Required for `chart` (native OOXML charts) and `image-sidebar` (PIL aspect-ratio fitting). |

Example:

```bash
python3 scripts/build_workspace.py --workspace decks/my-deck --qa
```

You almost never need to pass `--renderer` explicitly. The auto-picker
already selects pptxgenjs for every outline except those using `chart`
or `image-sidebar`. Passing `--renderer python` silently downgrades the
typography on timelines, cards, and section dividers — don't do it.

If you are continuing from an existing deck:

```bash
python3 scripts/init_deck_workspace.py \
  --workspace decks/refactor-deck \
  --title "Refactor Deck" \
  --style-preset executive-clinical \
  --reference-pptx /absolute/path/to/reference.pptx
```

## How The Skill Keeps Layouts Clean

The core engine is clean because it is not placing elements blindly.

1. Text is measured before major layout decisions.
   - `_estimate_text_lines()` and `_estimate_text_height()` estimate how much vertical space a given title/body block needs.
   - `_card_body_font()` reduces body size when the available height is tight.
   - `_card_title_layout()` reduces heading size and increases title box height when a card title is likely to wrap.

2. Cards are sized from content, not fixed templates.
   - `_preferred_card_height()` computes target height from rail, title, and body needs.
   - Split layouts share heights for dense side-by-side cards and collapse sparse sidecars instead of leaving empty mirrored boxes.
   - `visual_intent: hero` uses a reliable native image-right composition in the Python builder when a staged hero image is present.

3. Content slides reserve header space dynamically.
   - `_content_header()` now returns the bottom of the title/subtitle stack.
   - Content layouts start at `content_top`, which is derived from that stack instead of a fixed `y` coordinate.
   - This prevents wrapped slide titles from colliding with subtitles and with the top of the main content region.

4. The geometry is linted after generation.
   - `layout_lint.py` checks margins, top alignment, height consistency, gutters, density, empty ratio, and rail/card alignment.
   - `inventory.py` catches overflow and overlap from the actual PPTX text boxes.
   - `visual_qa.py` flags underfilled slides.
   - `design_rules_qa.py` catches polish issues that generic geometry misses.

5. The final gate combines those checks.
   - `qa_gate.py` runs the inventory, outline extraction, layout lint, render pass, visual QA, and design QA, then fails the build when the configured thresholds are violated.

## Recommended Iteration Pattern

1. Create a workspace once.
2. Use `content_plan.json` for the argument arc and visual strategy.
3. Use `evidence_plan.json` for sourced claims, numbers, and chart candidates.
4. Put persistent data rules, measurements, and unresolved assumptions in `notes.md`.
5. Stage source-backed images, backgrounds, charts, and deliberate generated images through `asset_plan.json`.
6. Reference staged assets in `outline.json` with aliases such as `asset:crew_portrait` or `chart:mission_profile`.
7. Keep any local diagrams and logos in `assets/`.
8. Add or replace slides by editing `outline.json`.
9. Rebuild with `build_workspace.py`.
10. Keep the workspace in version control if the deck matters.

This is the path that gets you closest to the clean “later I added two more slides and everything still matched” workflow.
