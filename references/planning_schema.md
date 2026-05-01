# Planning Schema

Use these files before authoring `outline.json` when the deck needs researched
content, sourced numbers, or a reusable narrative and design structure.

## `design_brief.json`

Purpose: lock the design strategy before slide variants are chosen. This is
the taste layer: audience posture, cover concept, grid constants, and the
rules that prevent generic card-heavy decks.

Recommended shape:

```json
{
  "topic": "Deck topic",
  "content_maturity": "silly/playful | casual/explainer | serious/work | technical/educational | premium/brand",
  "audience_posture": "friends/fans | students/learners | coworkers/operators | execs/buyers | public/brand",
  "emotional_register": "fun | warm | curious | urgent | trustworthy | cinematic | premium",
  "format_promise": "What the deck should feel like and what it must avoid",
  "anti_format": ["repeated title + 3 cards", "generic dashboard opener"],
  "canvas_and_grid": {
    "aspect": "16:9",
    "margin_x_in": 0.5,
    "footer_reserve_in": 0.32,
    "header_policy": "measured title/subtitle stack; body starts at returned contentTop"
  },
  "title_page_concept": {
    "chosen_archetype": "editorial masthead | typographic poster | full-bleed image | artifact cover | one-number cover",
    "dominant_element": "What owns slide 1",
    "supporting_element": "Optional secondary element",
    "why_this_could_only_be_this_deck": "Why the cover is topic-specific"
  },
  "structure_strategy": {
    "primary_scaffold": "open editorial content slides",
    "repeated_elements": ["shared margins", "consistent footer/source treatment"],
    "allowed_variations": ["standard", "split", "table", "flow", "optional kpi-hero"],
    "container_policy": "When cards/boxes are allowed and when they are not",
    "rhythm_break_plan": "Where the deck breaks the grid on purpose"
  },
  "design_dna": "lab results dashboard | board risk memo | product/investor reveal | editorial report | civic science policy | custom",
  "renderer_treatments": {
    "header_mode": "bar | stack | eyebrow | lab-clean | lab-card",
    "title_layout": "split-hero | lab-plate | command-center | poster | masthead | light-atlas",
    "title_motif": "orbit | network | editorial | none",
    "section_motif": "rail-dots | none",
    "timeline_mode": "rail-cards | staggered | open-events | bands | chapter-spread",
    "matrix_mode": "cards | open-quadrants",
    "stats_mode": "tiles | feature-left | policy-bands",
    "footer_mode": "standard | source-line",
    "summary_callout_mode": "default | lab-box"
  }
}
```

Rules:

- Write `design_brief.json` before `outline.json` for any deck that should
  look designed rather than mechanically rendered.
- Cards are not a default visual language. Use them only for modular evidence,
  comparisons, dashboards, worksheets, or other content that benefits from
  containment.
- Preserve degrees of freedom. The design brief should constrain what matters
  (readability, alignment, source footer, audience tone) but should not force a
  fixed 8-slide arc, a KPI hero closer, or the full variant menu.
- A cover should have one archetype and one dominant idea. Do not start with
  a generic dashboard, KPI strip, or title-plus-card grid unless the user asks
  for that exact format.
- `design_dna` should limit the variant set. A lab deck should bias toward
  `scientific-figure`, `lab-run-results`, and `image-sidebar`; a product deck
  can use `kpi-hero`, icons, asymmetric cards, and timeline only when the story
  has a real hero metric or image; an editorial deck can use `stack` headers
  and fewer, larger blocks.

## `content_plan.json`

Purpose: decide the story and visual strategy before rendering.

Required shape:

```json
{
  "topic": "Deck topic",
  "audience": "Who will read this",
  "objective": "What the deck should accomplish",
  "thesis": "One-sentence main argument",
  "narrative_arc": [
    {
      "act": "setup",
      "purpose": "Why this matters",
      "slides": ["s1", "s2"]
    }
  ],
  "slide_plan": [
    {
      "slide_id": "s1",
      "role": "title | context | evidence | mechanism | comparison | implication",
      "message": "Single slide takeaway",
      "variant": "title | split | cards-3 | timeline | table | chart | generated-image",
      "visual_strategy": "hero_image | icon_system | chart | table | mermaid | generated-image | none",
      "evidence_needs": ["ev1"],
      "asset_needs": ["image:hero_photo"]
    }
  ],
  "design_notes": {
    "style_preset_reason": "",
    "rhythm_break": "",
    "visual_motif": ""
  }
}
```

Rules:

- Every planned content slide should have a specific `message`.
- Every planned content slide should choose a `visual_strategy`; use `none`
  only with an explicit reason in `notes.md`.
- `evidence_needs` should reference IDs in `evidence_plan.json` when the slide
  makes factual claims.
- For public/researched topics, prefer `visual_strategy: "source-backed-image"`
  on 1-2 slides with a clear visual role. The helper
  `scripts/plan_research_assets.py` can convert those opportunities into
  Wikimedia queries, staged `image:<name>` aliases, and an attribution-backed
  Image Sources slide.

## `evidence_plan.json`

Purpose: keep factual substance and citations separate from layout.

Required shape:

```json
{
  "topic": "Deck topic",
  "source_policy": "Prefer primary or source-backed facts.",
  "items": [
    {
      "id": "ev1",
      "claim": "Claim to support",
      "value": "42",
      "unit": "%",
      "date_or_period": "2024",
      "source_title": "Source title",
      "source_url": "https://example.org/report",
      "source_note": "Table 2",
      "used_on_slides": ["s3"],
      "visual_use": "bullet | kpi | chart | table | footer-source"
    }
  ],
  "chart_candidates": [
    {
      "id": "chart1",
      "question": "What should this chart answer?",
      "series_needed": ["series A", "series B"],
      "source_ids": ["ev1"],
      "target_slide": "s4"
    }
  ],
  "open_questions": []
}
```

Rules:

- Do not put unsupported numbers directly into `outline.json`; stage them here
  first.
- `source_url` or `source_note` is expected for any item used as a KPI, chart,
  table, or source footer.
- `chart_candidates` should become either staged chart JSON in `asset_plan.json`
  or a deliberate non-chart decision in `notes.md`.

## Build Integration

`build_workspace.py` runs `scripts/validate_planning.py` when these files exist.
Malformed JSON or broken evidence references should be fixed before the final
deck build.

For a source-backed visual pass, run:

```bash
python3 scripts/build_workspace.py --workspace decks/my-deck \
  --plan-research-assets --allow-network-assets --qa --overwrite
```

Use this only when online image sourcing is appropriate for the deck. Private
lab data, proprietary screenshots, or source-free internal readouts should use
local assets instead.
