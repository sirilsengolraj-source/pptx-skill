# Design Philosophy — reference tables

> **The canonical design standard lives in `DESIGN.md`.**
> This file only lists the loadable preset + font_pair values the builder
> accepts. Read DESIGN.md first.

## Loadable presets (`--style-preset` values)

These are the 14 values `build_deck.py` / `build_workspace.py` /
`build_deck_pptxgenjs.js` accept. DESIGN.md explains
when to pick each one.

| Preset | Mood |
|---|---|
| `executive-clinical` | Cool navy + teal/amber — default for strategy and enterprise |
| `bold-startup-narrative` | Saturated, confident — pitch decks |
| `data-heavy-boardroom` | Restrained, high-contrast data — metrics, board memos |
| `sunset-investor` | Warm oranges + navy — fundraising, vision arcs |
| `forest-research` | Green + cream — climate, biology, sustainability |
| `midnight-neon` | Dark bg, cyan + rose accents — product launches, tech reveals |
| `paper-journal` | Warm paper + serif-ready — editorial, qualitative research |
| `arctic-minimal` | Cool gray + single accent — design systems, minimal briefs |
| `charcoal-safety` | Dark + safety red — incident reports, risk reviews |
| `lavender-ops` | Muted purple — ops dashboards, internal tooling |
| `warm-terracotta` | Earthy reds + sand — social impact, hospitality, heritage |
| `sage-calm` | Soft greens — healthcare, wellness |
| `coral-energy` | Coral + gold + navy — energy, climate action, advocacy |
| `cherry-bold` | Cherry + cream + navy — marketing, brand, fashion |

Run `python3 -c "from scripts.design_tokens import available_presets; print(available_presets())"`
to confirm the current set if this list drifts.

## Loadable font_pair values

Pass one of these to `deck_style.font_pair`:

| `font_pair` | Title | Body | Caption |
|---|---|---|---|
| `system_clean_v1` (default) | Trebuchet MS | Calibri | Calibri |
| `editorial_serif_v1` | Georgia | Calibri | Calibri |
| `clean_modern_v1` | Trebuchet MS | Calibri | Calibri |

These are the only validated values; others silently fall back to the
default (see `_normalize_deck_style` in `build_deck.py`). If you need a
new pairing, add it to `FONT_PAIRS` in `design_tokens.py` and whitelist
its name in `_normalize_deck_style`. Do not hand-roll font names in the
outline.

## Adding a new preset or font_pair

If a deck needs a mood none of the current presets match, **add a preset
to `design_tokens.py`** rather than hand-rolling colors inline. Only
presets are validated by the builder, the renderer, and `qa_gate.py`.
Inline custom colors fall silently back to defaults in several places.
