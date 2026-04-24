# Planning Schema

Use these files before authoring `outline.json` when the deck needs researched
content, sourced numbers, or a reusable narrative structure.

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
