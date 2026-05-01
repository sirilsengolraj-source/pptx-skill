# Outline JSON Schema

Use this schema with `scripts/build_deck_pptxgenjs.js`, `scripts/build_deck.py`,
and `scripts/build_workspace.py`.

## Top-Level

```json
{
  "title": "Optional deck title",
  "subtitle": "Optional deck subtitle",
  "deck_style": {
    "font_pair": "editorial_serif_v1",
    "palette_key": "climate_coastal_v1",
    "visual_density": "medium",
    "emoji_mode": "selective",
    "research_visual_mode": true
  },
  "compliance": {
    "attribution_file": "assets/attribution.csv",
    "require_attribution": true,
    "auto_image_sources": true
  },
  "slides": [
    {
      "type": "title",
      "title": "Q2 Business Review",
      "subtitle": "Executive summary"
    },
    {
      "type": "content",
      "slide_intent": "evidence",
      "visual_intent": "comparison",
      "title": "Key Outcomes",
      "sources": ["Q2 earnings release, page 4"],
      "bullets": [
        "Revenue grew 14% YoY",
        { "text": "Enterprise segment grew 22%", "level": 1 },
        "Gross margin improved 2.1 points"
      ]
    }
  ]
}
```

## Defaults (Backward-Compatible)

If `deck_style`/`compliance` are omitted, current behavior remains:

- `deck_style.font_pair`: `system_clean_v1`
- `deck_style.palette_key`: preset palette
- `deck_style.visual_density`: `medium`
- `deck_style.emoji_mode`: `none`
- `deck_style.research_visual_mode`: `false`
- `deck_style.header_mode`: preset treatment (`bar`, `stack`, `eyebrow`, or
  clean lab/report modes)
- `deck_style.title_layout`: preset treatment (`split-hero`, `lab-plate`,
  `command-center`, `poster`, `masthead`, or `light-atlas`)
- `deck_style.title_motif`: preset treatment (`orbit`, `network`, `editorial`, or `none`)
- `deck_style.section_motif`: preset treatment (`rail-dots` or `none`)
- `deck_style.timeline_mode`: preset treatment (`rail-cards`, `staggered`,
  `open-events`, `bands`, or `chapter-spread`)
- `deck_style.matrix_mode`: preset treatment (`cards` or `open-quadrants`)
- `deck_style.stats_mode`: preset treatment (`tiles`, `feature-left`, or `policy-bands`)
- `deck_style.footer_mode`: preset treatment (`standard` or `source-line`)
- `deck_style.summary_callout_mode`: preset treatment (`default` or `lab-box`)
- `deck_style.footer_page_numbers`: optional boolean for slide index in footer
- `compliance.attribution_file`: `assets/attribution.csv`
- `compliance.require_attribution`: `false` unless external CC assets are detected
- `compliance.auto_image_sources`: `true` when attribution rows exist; set
  `false` only if you will author a custom source/credits slide.

## `deck_style` Fields

- `font_pair`: `system_clean_v1 | editorial_serif_v1 | clean_modern_v1`
- `palette_key`: optional palette override key (for example `climate_coastal_v1`)
- `visual_density`: `low | medium | high`
- `emoji_mode`: `none | selective`
- `research_visual_mode`: boolean. Use `true` when a deck should actively use
  source-backed images/figures and attribution, usually after running
  `build_workspace.py --plan-research-assets --allow-network-assets`.
- `header_mode`: optional renderer treatment override. Use `bar` for formal
  clinical/board decks, `stack` for editorial/report decks, `eyebrow` for
  minimal civic/product briefs, `lab-clean` for plain lab/report slides, and
  slide-level `lab-card` when a small colored heading card is useful.
- `title_layout`: optional cover archetype override. Supported values:
  `split-hero`, `lab-plate`, `command-center`, `poster`, `masthead`,
  `light-atlas`. Prefer preset defaults unless the design brief needs a
  deliberate cover change.
- `title_motif`: optional cover motif override. Supported values:
  `orbit`, `network`, `editorial`, `none`.
- `section_motif`: optional section-divider motif override. Supported values:
  `rail-dots`, `none`.
- `timeline_mode`: optional timeline composition override. Use `rail-cards`
  only when milestones need card-level detail, `staggered` for launch/product
  pacing, `open-events` for sparse editorial/report timelines, `bands` for
  simple academic/ops sequences, and `chapter-spread` when the first milestone
  should act as the visual anchor. If the content is not truly time-sequenced,
  use `image-sidebar`, `table`, `comparison-2col`, or `standard` instead.
- `matrix_mode`: optional matrix composition override. Use `cards` for formal
  risk/control matrices and `open-quadrants` for lighter policy tradeoffs.
- `stats_mode`: optional stats composition override. Use `tiles` for equal
  KPIs, `feature-left` when one metric dominates, and `policy-bands` for
  civic/report scorecards.
- `footer_mode`: optional footer override. Use `source-line` for a thin rule
  above sources and page number, especially in academic/lab decks.
- `summary_callout_mode`: optional bottom callout treatment. Use `lab-box` for
  a simple rectangular key-takeaway box instead of a colorful pill.
- `footer_page_numbers`: boolean. Use `true` for source-line/report decks.

Only override renderer treatments when the design brief requires it. The
renderer already applies sensible preset-specific treatments so decks do not
all share the same cover, card, timeline, or dark-bar house style.

## `compliance` Fields

- `attribution_file`: CSV path for external asset attributions
- `require_attribution`: force attribution checks even when metadata sidecars are not auto-detected
- `auto_image_sources`: append a final editable Image Sources table slide from
  `attribution_file` when source-backed image rows exist and no source slide is
  already present.

When external CC metadata sidecars (`*.metadata.json`) are present, attribution rows are mandatory.

## Slide Types

- `title`: Title + subtitle opening slide. Renderer picks a preset-specific
  cover archetype and motif by default. Optional `assets.hero_image` for a
  deck-specific visual anchor.
- `content`: Title + cards/list layouts.
- `section`: Section divider slide. Renderer draws an accent rail + dot motif
  by default so the lower 70% of the canvas isn't dead space. Override with
  `bullets` or `caption` if you have real transition content. Do NOT author
  a section divider as pure title+subtitle — the QA gate now flags excessive
  empty ratio on `section` slides as an error, not a warning.
- `text`: Alias for content behavior.

If `type` is omitted, `content` is used.

## New Slide-Level Optional Fields

- `slide_intent`: `message | evidence | decision | section | process`
- `visual_intent`: `hero | timeline | comparison | flow | data`
- `assets`: optional visual assets block:

```json
{
  "assets": {
    "hero_image": "assets/hero.png",
    "diagram": "assets/process.png",
    "chart_data": "chart:revenue_bridge",
    "mermaid_source": "diagrams/process.mmd",
    "logo": "assets/logo.png",
    "icons": ["fa6:FaChartLine", "fa6:FaShieldHalved"]
  }
}
```

### `assets.icons`

`icons` is an array of strings. Each entry is rendered as a small image
on the slide. **Supported on `cards-2`, `cards-3`, `timeline`, `stats`,
`matrix`, and `image-sidebar` variants.** Other variants (`standard`,
`split`, `chart`) ignore `icons` with a debug warning to stderr — the slide
still builds, the icons just aren't drawn.

Icons are positioned:

- **cards-2, cards-3**: centered above each card's title (one icon per card,
  0.5" × 0.5").
- **timeline**: centered above each milestone dot (0.5" × 0.5").
- **stats**: centered above each fact tile's KPI value (0.4" × 0.4" —
  smaller so the value remains the dominant element).
- **matrix**: centered above each of the 4 quadrant titles (0.4" × 0.4" —
  smaller because matrix cards are shorter than cards-3 columns).
- **image-sidebar**: small badges next to sidebar section titles. Use for
  product/board/policy readout sections, not as a substitute for lab evidence.

Provide fewer icons than elements to leave some blank; extras beyond the
element count are ignored.

**Icon resolution order** (each string is resolved at build time):

1. **react-icons slug** (`"fa6:FaLightbulb"`, `"bi:BiShield"`,
   `"lu:LuLeaf"`): rasterized to PNG at 256px in the preset's
   `accent_primary` color using declared npm dependencies (no staging
   required). This is the default and preferred form. Supported packs:
   `fa6` (Font Awesome 6), `fa` (FA5), `bi` (Bootstrap Icons), `bs`
   (Bootstrap), `md` (Material), `lu` (Lucide).
2. **Absolute path** (`/some/where/icon.png`): used directly if the file
   exists.
3. **Relative path with extension** (`myicons/sun.png`, `sun.svg`):
   resolved against `<workspace>/assets/icons/` first, then against the
   outline directory as a fallback.
4. **Bare name** (`sun`, `shield-check`, no colon): resolved against
   `<workspace>/assets/icons/<name>.png`, then `.svg`, then `.jpg`.

The react-icons path is zero-config — no staging, no PNGs on disk for
Codex to produce. Prefer it over bare names unless you specifically want
to use a custom locally-staged image. Icons are cached per
slug+color+size in `$TMPDIR/presentation-skill-icon-cache/` across runs.

**Custom color per slide**: add `assets.icons_color` as a hex string
(`"icons_color": "F59E0B"`) to override the preset accent.

If no file is found the builder prints a stderr warning
(`icon not found: <name>, expected at <path>`) and skips that one icon;
the rest of the slide still renders.

Example (`cards-3` with icons):

```json
{
  "variant": "cards-3",
  "title": "Three pillars",
  "assets": { "icons": ["fa6:FaSun", "fa6:FaDroplet", "fa6:FaBolt"] },
  "cards": [
    { "title": "Solar",   "body": "Direct radiation to electricity." },
    { "title": "Hydro",   "body": "Rivers and reservoirs." },
    { "title": "Storage", "body": "Batteries and load shifting." }
  ]
}
```

Notes:
- Renderer selection is handled by `build_workspace.py --renderer auto`; do not
  use slide-level renderer flags for new decks.
- `visual_intent: flow` uses a fixed template (headline + diagram + decision/caption zone).
  It is optional and fragile when overused. Prefer it only when the process,
  method, architecture, or causal chain is the actual evidence on the slide.
  Keep diagrams to four boxes in a visible row; split or summarize longer
  processes instead of forcing every step into one slide.
- `visual_intent: hero` can use a native figure-plus-sidebar composition in the reliable builder.
- `visual_intent: data` can use a native chart + evidence layout in the reliable builder.
- For `flow`, provide `assets.diagram` or `assets.mermaid_source`. The
  builder auto-renders `.mmd` files to PNG via `scripts/render_mermaid.py`
  at build time — you write the diagram in mermaid syntax (easy for
  processes, sequences, flowcharts), the build pipeline turns it into a
  slide-ready image. This is the fast path for technical diagrams; use
  it only when a slide's concept is genuinely "boxes and arrows" rather
  than text. Mermaid source goes in `<workspace>/assets/diagrams/*.mmd`.
  The built-in fallback caps Mermaid flow rows at four boxes and balances rows,
  but a 6+ step diagram should still be treated as a design smell unless
  those steps are necessary for the argument.
- For photographic or illustrative imagery (plant photos, historical
  figures, maps), use `assets.hero_image` pointing at a staged local
  file. `scripts/fetch_wikimedia_cc.py` can seed CC-licensed images into
  `assets/staged/` from a search query; record the query in
  `asset_plan.json`'s `images` array and let `asset_stage.py` resolve
  them during `build_workspace.py`.
- For generated technical illustrations (a chart that summarizes a concept,
  a stylized process diagram), `scripts/generate_openai_image.py` can
  request a specific image via an OpenAI image model. Use sparingly, and put
  the result on a standalone `generated-image` slide so it is labeled and easy
  to delete.
- Chart data can be inline under `chart`, or referenced from a staged JSON file with `chart:name` or `assets.chart_data`.
- Asset aliases can be resolved from `assets/staged/staged_manifest.json` using `asset:name`, `image:name`, `background:name`, `chart:name`, or `generated:name`.

## Content Variants (`type: "content"`)

Use `variant` to force layout family:

- `standard`: single primary card
- `split`: two-column narrative + checklist
- `cards-2`: two equal cards
- `cards-3`: three equal cards (with optional `promote_card: N` for an
  asymmetric big-left + two-stacked-right layout; N is the card index)
- `timeline`: milestone timeline. Supports multiple visual treatments through
  `timeline_mode`, including non-card modes (`bands`, `chapter-spread`) for
  decks where rail cards feel templated.
- `matrix`: 2x2 card matrix
- `stats`: fact/evidence card grid
- `chart`: chart frame with optional fact/evidence sidecars
- `kpi-hero`: single giant KPI number dominating the slide (requires
  `value`, `label`; optional `context`). Font autosizes by value length:
  ≤4 chars → 120pt, 5-6 → 96pt, 7-8 → 72pt, ≥9 → 60pt. Use only when the
  story has one number/date that genuinely deserves isolation. Do not add it
  as a default closing slide.
- `comparison-2col`: two-column side-by-side comparison with dividing rule
  (requires `left: {title, body}` and `right: {title, body}`; optional
  `verdict` caption at the bottom). Best for before/after, hypothesis/result,
  us/them. Body accepts a string or array of bullet points.
- `table`: native OOXML table (real rows/columns, not text in card boxes).
  Requires `headers: [...]` and `rows: [[...], ...]` of matching width.
  Optional `caption` (muted line below table) and
  `column_weights: [...]` (numeric proportions; equal widths if omitted).
  `headers`/`rows` may be top-level or nested under `"table": {...}`.
  Use optional `cell_styles` to highlight individual body cells; each entry
  may include `fill`, `color`, `bold`, `italic`, `align`, and `fontSize`.
  Reach for `table` over `cards-3` when rows share parallel fields
  (entity + date + role, or feature + option A + option B + option C).
  Cap at ~8 rows for readability; preflight warns past 10.
- `lab-run-results`: table-first lab/data dashboard modeled after clean
  lab and data-dashboard decks. Accepts `tables: [{title, headers, rows,
  column_weights, cell_styles, caption, footnotes}, ...]` and places one
  large editable table plus up to two compact side tables. Use for confusion
  matrices, assay run summaries, concordance, sensitivity/specificity blocks,
  sequencing QC tables, and POC validation slides. Add `interpretation` or
  `takeaway` for the bottom readout strip. Use green/red/yellow fills in
  `cell_styles` for agreement/discordance/borderline states; do not use icons
  as a substitute for the actual result table.
- `generated-image`: standalone image slide for optional AI-generated concept
  visuals. Requires `assets.generated_image`, `assets.hero_image`, or
  `assets.image`; prefer `assets.generated_image: "generated:<name>"`.
  Include `image_generation: {prompt, model, purpose, edit_note}` so the slide
  discloses the asset clearly. Do not mix generated visuals into evidence
  slides unless the user explicitly asks for that.
- `image-sidebar`: figure-first academic/lab layout. A staged image, plot,
  workflow screenshot, or generated local figure takes ~60% of the slide;
  a sidebar carries 2-4 labeled interpretation sections. Requires
  `assets.hero_image` or `assets.image`; add `image_side: "left"|"right"`,
  `caption`, and `sidebar_sections`. Use this for lab results, methods
  figures, LOD plots, gel/trace/readout images, microscopy, maps, and
  workflow screenshots before falling back to generic card grids.
- `scientific-figure`: multi-panel academic figure slide. Use `figures` or
  `assets.figures` with 1-4 entries such as
  `{ "path": "assets/panel_a.png", "label": "A", "title": "...", "caption": "..." }`.
  The renderer creates journal-style panel boxes, subfigure labels, optional
  panel titles/captions, and a bottom caption/interpretation strip. Use this
  for LOD panels, multi-plot summaries, gels, microscopy grids, and figure
  evidence slides where a sidebar would waste space.

### Hybrid Cases (Map Before Going Inline)

If a requested slide does not fit one variant cleanly, map it to the nearest
combination before reaching for raw python-pptx:

- **Roadmap / quarter-columns with milestones** → `variant: cards-3` where each
  card's `body` carries the milestone text, or `variant: timeline` with
  `milestones` plus a `facts` sidecar for the KPI strip.
- **Hero/figure image with interpretation sidebar** → use
  `variant: image-sidebar` or set `visual_intent: hero`, provide
  `assets.hero_image`, and fill `sidebar_sections`. Do not compose the image
  and sidebar manually.
- **Timeline + chart on one slide** → split into two slides
  (`variant: timeline` + `variant: chart`), not one custom layout.
- **KPI strip above bullets** → `variant: stats` with `facts` on top and
  `bullets` below.

If none of these fit, stop and ask the user. Never fall back to inline
python-pptx because the schema felt incomplete.

Variant-specific fields:

- `cards` (for `cards-2` / `cards-3`):
  - array of `{ "title": "...", "body": "...", "accent": "accent_primary|accent_secondary" }`
- `milestones` (for `timeline`):
  - array of `{ "label": "Q1", "title": "Discover", "body": "..." }`
- `quadrants` (for `matrix`):
  - array of `{ "title": "...", "body": "..." }`
- `highlights` (for `split`):
  - right-column checklist lines
- `summary_callout` / `key_summary` / `takeaway`:
  - optional bottom summary box for standard content and other variants that
    do not already carry a bottom synthesis. With `summary_callout_mode:
    "lab-box"` it renders as a clean rectangular key-point strip for academic
    and lab decks.
- `value`, `label`, `context` (for `kpi-hero`):
  - `value` is the headline number with unit (e.g., `"42%"`, `"$1.2M"`).
    Keep it ≤8 chars to avoid the 60pt floor.
  - `label` is the short noun phrase below the number (e.g., `"carbon reduction"`).
  - `context` is an optional 1-line footer caption in muted color.
- `headers`, `rows`, `column_weights`, `caption` (for `table`):
  - `headers` is the array of column labels; determines column count.
  - `rows` is an array of arrays; each row length must match `headers`.
  - `column_weights` (optional) is a numeric array of proportional widths
    (e.g., `[0.25, 0.15, 0.60]` weights a 3-col table as 1:0.6:2.4).
  - `caption` (optional) renders below the table in muted caption text,
    typically a source line.
  - `cell_styles` (optional) is a body-row matrix or keyed object such as
    `{ "0,1": {"fill": "#D9EAD3", "bold": true} }`.
  - `footnotes` (optional) is an array of small notes below the table.
- `tables`, `interpretation` / `takeaway` (for `lab-run-results`):
  - `tables` is an array of compact table objects with the same table fields
    above. One table uses the full width, two tables split the canvas, three
    tables render one large table left and two stacked tables right.
  - `interpretation` or `takeaway` is a one-line bottom synthesis. Keep it
    short; move caveats into table `footnotes`.
- `left`, `right`, `verdict` (for `comparison-2col`):
  - `left` and `right` are `{ "title": "...", "body": "..." }`. Body may be a
    string (split on ". ") or an array of bullet lines.
  - `verdict` is an optional one-line synthesis rendered in a surface strip
    beneath the two columns.
- `promote_card` (for `cards-3`):
  - integer 0, 1, or 2 — the index of the card to render at 2× area on the
    left, with the other two stacked on the right. Breaks the symmetric
    3-up grid. Use once or twice per deck, not on every cards-3 slide.
- `sidebar_sections` (for `image-sidebar`):
  - array of 2-4 `{ "title": "...", "body": "..." }` sections. `body` can be
    a string or array of short bullet strings. Keep titles short
    (`"Readout"`, `"Interpretation"`, `"Caveat"`). Add `caption` for figure
    provenance or assay/run metadata.
- `figures` / `assets.figures` (for `scientific-figure`):
  - array of 1-4 figure objects. Each figure needs `path` or `image`; optional
    `label`, `title`, and `caption` render inside the figure panel.
  - slide-level `caption`, `figure_caption`, `interpretation`, or `takeaway`
    renders beneath the panel grid. Keep this compact and move long methods
    text into notes or an appendix.
- `facts` / `stats` / `evidence` (for `stats` or `chart`):
  - array of `{ "value": "...", "label": "...", "detail": "...", "source": "...", "accent": "accent_primary|accent_secondary" }`
  - **`value` must be numeric** with optional unit suffix: `"14"`, `"14%"`,
    `"2.1pt"`, `"5×"`, `"$4.2B"`, `"98%"`. The QA gate flags non-numeric
    adjectives (`"Live"`, `"Higher"`, `"Clear"`) as `stats_value_non_numeric`
    because they render badly at KPI font size. For qualitative tiles,
    use `variant: cards-3` instead — the card heading takes qualifiers
    well, the stats KPI tile does not.
- `chart` (for `chart`):
  - either an inline object or a path / alias to staged chart JSON
  - the renderer accepts **two equivalent schema forms**. Labels and values
    must have the same length in either form, and values must be numeric —
    otherwise QA emits `chart_schema_invalid` (blocking error) and the slide
    renders a red "Chart data malformed" banner in place of the chart.
  - **Form A — series-level labels (legacy):**

```json
{
  "chart": {
    "type": "line",
    "series": [
      {
        "name": "Elapsed day",
        "labels": ["Launch", "Flyby", "Splashdown"],
        "values": [0, 5, 10]
      }
    ],
    "options": {
      "catAxisTitle": "Mission event",
      "valAxisTitle": "Day"
    },
    "sources": ["NASA mission timeline"],
    "facts": [
      { "value": "10", "label": "Mission days", "detail": "Launch to splashdown" }
    ]
  }
}
```

  - **Form B — chart-level `categories` shorthand (common):** omit
    per-series `labels`, put shared axis labels once at the chart level.
    The normalizer copies `categories` into each series' `labels` before
    rendering. Prefer this form when every series shares the same
    categories.

```json
{
  "chart": {
    "type": "bar",
    "title": "Illustrative Solar Irradiance Levels",
    "categories": ["Top of Atmosphere", "Clear Noon Surface", "Whole-Earth Average"],
    "series": [
      { "name": "Approximate W/m²", "values": [1361, 1000, 340] }
    ]
  }
}
```

### Example: standard

```json
{
  "type": "content",
  "variant": "standard",
  "title": "Q2 Product Roadmap Overview",
  "subtitle": "One plan, three workstreams",
  "sources": ["Product Ops planning doc, Apr 2026"],
  "body": "Q2 centers on shipping the unified billing API, rolling out the redesigned onboarding flow, and hardening observability across the platform.",
  "bullets": [
    "Billing API targets GA by end of May",
    "Onboarding redesign enters beta week 6",
    "Observability SLOs gate every release"
  ]
}
```

### Example: split

```json
{
  "type": "content",
  "variant": "split",
  "title": "Q2 Product Roadmap: Narrative vs. Commitments",
  "sources": ["Product Ops planning doc, Apr 2026"],
  "body": "We are trading scope for predictability this quarter. Fewer launches, tighter SLOs, and a single shared definition of done across Product, Design, and Platform.",
  "highlights": [
    "Unified billing API: GA May 28",
    "Onboarding redesign: 50% beta cohort by week 6",
    "Observability: p95 latency under 250ms",
    "Zero P0 incidents tied to billing migration"
  ]
}
```

### Example: cards-2

```json
{
  "type": "content",
  "variant": "cards-2",
  "title": "Q2 Product Roadmap: Two Pillars",
  "sources": ["Product Ops planning doc, Apr 2026"],
  "cards": [
    {
      "title": "Revenue Foundation",
      "body": "Unified billing API plus migration tooling for enterprise tenants. Owner: Platform. GA May 28.",
      "accent": "accent_primary"
    },
    {
      "title": "Activation Lift",
      "body": "Redesigned onboarding flow with in-product guidance. Owner: Growth. 50% beta by week 6.",
      "accent": "accent_secondary"
    }
  ]
}
```

### Example: cards-3

```json
{
  "type": "content",
  "variant": "cards-3",
  "title": "Q2 Product Roadmap: Three Workstreams",
  "sources": ["Product Ops planning doc, Apr 2026"],
  "cards": [
    {
      "title": "Billing",
      "body": "Unified API, migration tooling, reconciliation dashboards.",
      "accent": "accent_primary"
    },
    {
      "title": "Onboarding",
      "body": "Redesigned first-run flow, contextual guidance, activation analytics.",
      "accent": "accent_secondary"
    },
    {
      "title": "Observability",
      "body": "SLO framework, tracing coverage, incident review automation.",
      "accent": "accent_primary"
    }
  ]
}
```

### Example: timeline

```json
{
  "type": "content",
  "variant": "timeline",
  "title": "Q2 Product Roadmap: Delivery Timeline",
  "sources": ["Product Ops planning doc, Apr 2026"],
  "milestones": [
    { "label": "Apr", "title": "Kickoff", "body": "Scope lock and staffing confirmed across three workstreams." },
    { "label": "May", "title": "Billing GA", "body": "Unified billing API cuts over for all enterprise tenants." },
    { "label": "Jun", "title": "Onboarding Beta", "body": "Redesigned flow reaches 50% of new signups." },
    { "label": "Jul", "title": "Observability SLOs", "body": "Platform-wide SLO gating enforced on every release." }
  ]
}
```

### Example: matrix

```json
{
  "type": "content",
  "variant": "matrix",
  "title": "Q2 Product Roadmap: Impact vs. Effort",
  "sources": ["Product Ops planning doc, Apr 2026"],
  "quadrants": [
    { "title": "High impact, low effort", "body": "Onboarding copy refresh and activation email sequence." },
    { "title": "High impact, high effort", "body": "Unified billing API and enterprise migration tooling." },
    { "title": "Low impact, low effort", "body": "Legacy dashboard cleanup and deprecation notices." },
    { "title": "Low impact, high effort", "body": "Custom report builder rewrite — defer to Q3." }
  ]
}
```

### Example: stats

```json
{
  "type": "content",
  "variant": "stats",
  "title": "Q2 Product Roadmap: Targets at a Glance",
  "sources": ["Product Ops planning doc, Apr 2026"],
  "facts": [
    { "value": "May 28", "label": "Billing GA", "detail": "Enterprise cutover complete", "accent": "accent_primary" },
    { "value": "50%", "label": "Onboarding beta", "detail": "Of new signups by week 6", "accent": "accent_secondary" },
    { "value": "250ms", "label": "p95 latency SLO", "detail": "Gates every platform release", "accent": "accent_primary" },
    { "value": "0", "label": "P0 incidents", "detail": "Tied to billing migration", "accent": "accent_secondary" }
  ],
  "bullets": [
    "Targets reviewed weekly in Product Ops sync",
    "Misses trigger scope-trim, not date-slip"
  ]
}
```

### Example: chart

```json
{
  "type": "content",
  "variant": "chart",
  "title": "Q2 Product Roadmap: Engineering Capacity Allocation",
  "sources": ["Engineering headcount plan, Apr 2026"],
  "chart": {
    "type": "bar",
    "series": [
      {
        "name": "Engineer-weeks",
        "labels": ["Billing", "Onboarding", "Observability", "Reserve"],
        "values": [48, 32, 24, 16]
      }
    ],
    "options": {
      "catAxisTitle": "Workstream",
      "valAxisTitle": "Engineer-weeks"
    }
  },
  "facts": [
    { "value": "120", "label": "Total eng-weeks", "detail": "Across 10 engineers x 12 weeks" },
    { "value": "13%", "label": "Reserve buffer", "detail": "Held for incident response" }
  ]
}
```

## Common Slide Fields

- `title` (string)
- `subtitle` (string)
- `notes` (string)
- `footer` (string)
- `sources` (array of strings or objects; compact provenance/footer line)
- `variant` (string; content slides only)
- `background_image` (string; local image path)
- `thumbnails` (array of up to 3 local image paths)
- `caption` (string; used on flow/visual slides)
- `message` (string; recommended for decision-oriented flow slides)
- `chart` (object|string; inline chart data or staged `chart:name` alias)
- `facts` / `stats` / `evidence` (array; fact/evidence blocks for stats or chart slides)

## Text Fields

- `bullets`: array of strings or objects
  - string form: `"Short bullet text"`
  - object form: `{ "text": "Indented text", "level": 1 }`
- `paragraphs`: array of strings
- `body`: string

## Policy Notes

- Logo policy: only local user-provided or licensed assets.
- Source-backed staged assets can be referenced by alias after running `asset_stage.py` or `build_workspace.py`.
- Remote media URLs (`http://`/`https://`) are rejected.
- Emoji policy in `selective` mode:
  - allowed on `title`/`section` or informal slides
  - max `1` emoji in title, max `2` emojis per slide
  - disabled automatically for boardroom/data-heavy presets

## Tips

- Keep bullet lines short to reduce overflow.
- Keep `level` between `0` and `4` for predictable formatting.
- Use section, timeline, comparison, table, chart, and flow variants directly;
  `build_workspace.py --renderer auto` selects the appropriate renderer.

### Example: Complete Deck

A minimal but complete `outline.json` showing how a mixed-variant deck is
authored. **Do not copy this shape verbatim onto every topic** — it intentionally
uses `table`, `stats`, `kpi-hero`, `section`, and `image-sidebar` to model the
range of variants available. Most decks will use a *subset* tuned to the topic's
argument arc. Pick 3-4 variants that fit your topic's voice instead of defaulting
to split/cards-3 for every content slide.

```json
{
  "title": "Q2 Product Roadmap",
  "subtitle": "Planning review — April 2026",
  "deck_style": {
    "font_pair": "clean_modern_v1",
    "visual_density": "medium",
    "emoji_mode": "none"
  },
  "slides": [
    {
      "type": "title",
      "title": "Q2 Product Roadmap",
      "subtitle": "Planning review — April 2026"
    },
    {
      "type": "section",
      "title": "Where We Stand",
      "subtitle": "Entering Q2"
    },
    {
      "type": "content",
      "variant": "stats",
      "slide_intent": "evidence",
      "title": "The numbers heading into planning",
      "subtitle": "Three signals shaping priorities this quarter",
      "sources": ["Product Ops planning doc, Apr 2026"],
      "stats": [
        { "value": "42%", "label": "QoQ activation lift", "caption": "Onboarding v2 cohort" },
        { "value": "0.8%", "label": "API error rate", "caption": "Down from 2.3% in Q1" },
        { "value": "12", "label": "Enterprise logos in pilot", "caption": "4 converted in March" }
      ]
    },
    {
      "type": "content",
      "variant": "table",
      "slide_intent": "evidence",
      "title": "Workstream status at a glance",
      "subtitle": "What each team owns through May",
      "table": {
        "headers": ["Workstream", "Owner", "Milestone", "Status"],
        "rows": [
          ["Billing", "Ana", "Unified API GA May 28", "on track"],
          ["Onboarding", "Ravi", "50% beta by week 6", "at risk"],
          ["Observability", "Chen", "SLO gating every release", "on track"]
        ]
      }
    },
    {
      "type": "content",
      "variant": "kpi-hero",
      "slide_intent": "decision",
      "title": "One commitment above all",
      "value": "3",
      "label": "releases guaranteed by May 28",
      "context": "Billing unification is the gating dependency for the other two."
    },
    {
      "type": "section",
      "title": "Next: Risks and Open Questions",
      "subtitle": "Discussion"
    }
  ]
}
```

This example uses a `section` divider, `stats`, `table`, `kpi-hero`, and a
closing `section`. Notice what it *doesn't* do: no `split`, no `cards-3`. Those
are fine variants, but they're not the default skeleton — they're just two
options among many.
