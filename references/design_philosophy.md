# Design Philosophy — reference tables

> **The canonical design standard lives in `DESIGN.md`.**
> This file only lists the loadable preset + font_pair values the builder
> accepts. Read DESIGN.md first.

## Loadable presets (`--style-preset` values)

These are the 13 values `build_deck.py` / `build_workspace.py` /
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

## Design DNA Patterns

Pick one design DNA before writing `outline.json`; do not use the whole
variant menu as a substitute for taste.

| DNA | Presets | Primary variants | Motifs and guardrails |
|---|---|---|---|
| Lab results dashboard | `lab-report`, `data-heavy-boardroom` | `scientific-figure`, `lab-run-results`, `image-sidebar`, `table`, `comparison-2col` | Evidence dominates. Use captions, semantic table fills, and interpretation strips. Do not use icons as evidence substitutes. |
| Board risk memo | `charcoal-safety`, `data-heavy-boardroom` | `stats`, `matrix`, `image-sidebar`, `timeline`, `table` | Dark command-center opener, sparse risk language, explicit asks. Icons can support scanability. |
| Product/investor reveal | `bold-startup-narrative`, `midnight-neon`, `sunset-investor` | optional `kpi-hero`, `cards-3` with `promote_card`, `image-sidebar`, `timeline`, `comparison-2col` | Use one cinematic KPI or hero moment only when the content earns it, then proof. Avoid generic SaaS card walls. |
| Editorial report | `paper-journal`, `editorial-minimal` | `section`, `image-sidebar`, `timeline`, `cards-2`, `generated-image` | Masthead, artifact imagery, warm paper, compact prose. Keep generated imagery standalone and labeled. |
| Civic science policy | `arctic-minimal`, `warm-terracotta`, `forest-research` | `stats`, `scientific-figure`, `matrix`, `table`, `comparison-2col` | Map/data first, plain-language policy tradeoffs, accessible contrast, visible source lines. |

Preset treatments now include cover and structure variation, not just palette:
lab decks default to `title_layout: lab-plate`, board decks to
`command-center` plus `stats_mode: feature-left`, product decks to `poster`
plus `timeline_mode: chapter-spread` when a launch milestone deserves visual
priority, editorial decks to `masthead` plus `timeline_mode: open-events` or
`bands`, and civic decks to `light-atlas` plus `matrix_mode: open-quadrants` /
`stats_mode: policy-bands`.
