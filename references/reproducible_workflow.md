# Reproducible Workflow (Workspace Standard)

Use this file as the default execution contract for future deck work in this workspace.

## Objective

Generate decks with consistent visual quality and repeatable structure, not one-off styling.

## Environment Policy

- Install dependencies once per environment, not per run.
- Core deck generation only needs the Python builder stack.
- LibreOffice `soffice` and Poppler `pdftoppm` are optional unless you are running render-based QA or the full benchmark harness.
- Optional HTML rendering dependencies should only be installed when that path is explicitly needed.

## Default Inputs

- Minimum required user inputs:
  - Audience
  - Decision objective
  - Slide count target
  - Required sections

## Layout System

Use only these proven layout families unless user asks otherwise:

1. Hero opener (dark background, large title, short subtitle, motif icon/circles)
2. Card grid (2-3 columns with icon + heading + concise body)
3. Split panel (content left, metric/checklist/commands right)
4. Comparison layout (two mirrored rounded cards)
5. Table comparison (head-to-head features)
6. Closing slide (key takeaways with short bullets)

Do not repeat one layout family for consecutive slides unless required.

## Typography Rules

- Keep strong hierarchy:
  - Title: 36-48 pt
  - Section heading: 22-30 pt
  - Body: 14-20 pt
  - Caption/footer: 11-14 pt
- Use at most 2-3 font families in one deck.
- Keep body copy left-aligned.
- Keep line lengths reasonable; split dense text into cards.

## Color Rules

- Use one dominant background tone, one secondary support tone, one accent.
- Maintain contrast (especially on dark slides).
- Use accent color consistently for icons, rails, or callouts.

## Content Density Rules

- One core message per slide.
- 3-6 bullets max per content block.
- Prefer short lines over paragraph walls.
- Convert long lists into grids/cards where possible.

## Preflight (Static Outline Lint)

Before running the slow build + render cycle, run the static preflight
linter against `outline.json`. It catches common authoring errors in
under a second:

```bash
python3 scripts/preflight.py --outline outline.json
```

Exit codes:

- `0` - clean.
- `1` - warnings only (non-blocking).
- `2` - blocking errors (e.g., malformed chart, missing cards array,
  invalid `font_pair`).
- `3` - outline JSON is malformed.

`scripts/build_workspace.py` runs preflight first automatically. Use
`--strict-preflight` to abort the build on any preflight error, and
`--skip-preflight` to disable the check entirely. When `--qa` is set the
build already behaves strictly (blocking errors abort), because those
errors will reliably fail the downstream QA gate anyway and there's no
point paying the ~60s render cost to confirm it.

Use `--strict-preflight` when:

- You're iterating quickly and want fast failure feedback.
- You're running in CI and want build failures before render.
- You want to block authoring errors (non-numeric stats, malformed
  chart, bad font_pair) from ever reaching the renderer.

Skip preflight (`--skip-preflight`) only when you're intentionally
bypassing lint for a known-divergent outline, e.g., debugging a
renderer-side bug against a crafted edge-case input.

## Mandatory QA Loop

### 1) Content QA

```bash
python3 scripts/extract_outline.py --input output.pptx --format markdown
python3 -m markitdown output.pptx
```

Verify no placeholder remnants, missing sections, or ordering issues.

### 2) Visual QA

```bash
python3 scripts/render_slides.py --input output.pptx --outdir /tmp/slide-review
```

Verify:
- No clipping/overflow
- No overlaps
- Consistent margins
- Aligned cards/columns
- Adequate contrast

### 3) Fix-and-Reverify

- Run deterministic loop (max 3):

```bash
python3 scripts/iterate_deck.py \
  --input output.pptx \
  --output output.pptx \
  --style-preset executive-clinical \
  --max-loops 3 \
  --outdir /tmp/pptx-iterations
```

By default, intermediate iteration loops no longer render. Only the final
loop runs the full soffice render pass, which cuts total iteration time
roughly 60-80% for a 3-loop run. Pass `--always-render` to restore the old
behavior (render on every loop) when you genuinely need the render diff
between intermediate fixes. `--fast` is a render-free shortcut
(`--max-loops 3 --skip-render`) for quick drafts. See
`speed_and_rendering.md` for details and the `unoserver` daemon speedup.

- Run strict final gate:

```bash
python3 scripts/qa_gate.py \
  --input output.pptx \
  --outdir /tmp/pptx-qa-final \
  --style-preset executive-clinical \
  --strict-geometry \
  --report /tmp/pptx-qa-final/qa_report.json
```

- Add manual review artifact when visual pass is complete:

```bash
touch /tmp/pptx-qa-final/manual_review_passed.flag
```

## Delivery Standard

Before final delivery, provide:
- Final `.pptx`
- Brief slide-by-slide change summary
- Notes on assumptions/substitutions (fonts, icons, imagery)
