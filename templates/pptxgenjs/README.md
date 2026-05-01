# templates/pptxgenjs

Template modules for the default pptxgenjs renderer
(`scripts/build_deck_pptxgenjs.js`). These modules are plain CommonJS, so
`require()` from the builder pulls them in without a bundler.

The renderer is the default path. `scripts/build_deck.py` remains the fallback
for variants that need python-pptx features such as native charts.

## Modules

| File         | Responsibility                                                                 |
| ------------ | ------------------------------------------------------------------------------ |
| `presets.js` | Style presets (palette + font pair) keyed by the skill's canonical preset names. Exports `getPreset(name)` / `listPresets()`. |
| `slides.js`  | One function per slide family, plus the shared chrome (dark title bar, footer, notes). Exports `renderTitle`, `renderSection`, `renderStandard`, `renderCards`, `renderSplit`, `renderTimeline`, `renderStats`, `renderTable`, `renderLabRunResults`, and canvas constants (`SLIDE_W`, `SLIDE_H`, `MARGIN_X`, `HEADER_TOP`, `TITLE_BAR_H`, `CONTENT_TOP`). |

## Slide family map

| Outline shape                  | Renderer          | Notes                                                     |
| ------------------------------ | ----------------- | --------------------------------------------------------- |
| `type: title`                  | `renderTitle`     | Full-bleed dark hero; optional `background_image`.        |
| `type: section`                | `renderSection`   | Dark divider slide with oversized title.                  |
| `content / standard`           | `renderStandard`  | Bullets + optional right-side highlights card.            |
| `content / cards-2`            | `renderCards`     | Two square-edged cards with flush top accent rail.        |
| `content / cards-3`            | `renderCards`     | Three equal-width cards.                                  |
| `content / split`              | `renderSplit`     | Bullets left, dark highlights panel right.                |
| `content / timeline`           | `renderTimeline`  | Milestone sequence with rail, staggered, bands, or chapter-spread treatment. |
| `content / stats`              | `renderStats`     | Oversized fact tiles (value + label + caption + source).  |
| `content / kpi-hero`           | `renderKpiHero`   | Single dark KPI emphasis slide.                           |
| `content / table`              | `renderTable`     | Native editable table.                                    |
| `content / lab-run-results`    | `renderLabRunResults` | Compact editable lab/result dashboard with highlighted tables. |
| `content / comparison-2col`    | `renderComparison2col` | Two-column contrast with optional verdict.          |
| `content / matrix`             | `renderMatrix`    | 2x2 quadrant grid.                                        |
| `content / flow`               | `renderFlow`      | Mermaid/diagram image as the body.                        |
| `content / scientific-figure`  | `renderScientificFigure` | Multi-panel academic figure slide with labels/captions. |
| `content / generated-image`    | `renderGeneratedImage` | Standalone generated visual with metadata.           |

Variant `chart` is intentionally routed to `build_deck.py` by workspace auto
selection because native OOXML chart generation is stronger there.

## Style presets

All four canonical preset names are exported:

- `executive-clinical`
- `bold-startup-narrative`
- `midnight-neon`
- `data-heavy-boardroom`

Each returns `{ bg, bg_dark, surface, text, text_muted, accent_primary,
accent_secondary, line, font_heading, font_body }`. `surface` and `line` are
provided as convenience tokens that several slide families use but are not
part of the required preset shape.

## House rules (worth repeating)

1. pptxgenjs hex colors never carry `#`. Write `"1493A4"`, never `"#1493A4"`.
2. Never reuse an options object across `addShape` / `addText` calls.
   pptxgenjs mutates what you pass in. Use the factory helpers
   (`textOpts()`, `shapeOpts()`, `cardShadow()`) so every call gets a fresh
   object.
3. Every text box sets `margin: 0` so the baseline math matches the layout
   coordinates exactly.
4. Canvas is `10.0" x 5.625"` (16:9). Side margins 0.5". The dark title
   bar is at least 0.90" tall, but folded titles/subtitles are measured and
   the renderer returns `contentTop`; content must start from that value, not
   from a fixed y-coordinate.
5. Sandwich: dark title slide -> light content body -> dark closing /
   section. Don't bounce between light and dark mid-deck.
