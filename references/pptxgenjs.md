# pptxgenjs Reference

Editing `scripts/build_deck_pptxgenjs.js` or `templates/pptxgenjs/` and not
sure why shadows render as solid blocks or your second shape gets the
wrong color? Start here. Most pptxgenjs bugs are silent — the file writes
successfully but opens corrupted or wrong.

Read this before touching the pptxgenjs peer renderer. These are repo-local
guardrails from observed pptxgenjs failure modes; the rules below are
load-bearing.

## Common pitfalls (silent file corruption)

⚠️ These cause file corruption, visual bugs, or broken output with no
error at build time. Fix them at the source, not by inspecting the
generated .pptx.

### 1. NEVER use `#` in hex colors

Corrupts the file silently. Every color accepts 6-char hex only.

```javascript
color: "FF0000"      // ✅ CORRECT
color: "#FF0000"     // ❌ WRONG — file corruption
```

Applies to `fill.color`, `line.color`, `shadow.color`, `color`, `chartColors`, every hex-accepting property.

### 2. NEVER encode opacity in the hex string

8-character hex (e.g. `"00000020"`) corrupts the file. Use the separate
`opacity` property.

```javascript
shadow: { type: "outer", blur: 6, offset: 2, color: "00000020" }
// ❌ CORRUPTS FILE

shadow: { type: "outer", blur: 6, offset: 2, color: "000000", opacity: 0.12 }
// ✅ CORRECT
```

### 3. Use `bullet: true`, NEVER unicode `•`

Unicode bullets create double-bullet rendering (one bullet from pptxgenjs
+ one from your text).

```javascript
// ✅ CORRECT
[{ text: "First item", options: { bullet: true, breakLine: true } }]

// ❌ WRONG — renders as "••  First item"
slide.addText("• First item", { ... })
```

### 4. `breakLine: true` between array runs

Without it, consecutive text runs flow into one line.

```javascript
slide.addText([
  { text: "Line 1", options: { breakLine: true } },
  { text: "Line 2", options: { breakLine: true } },
  { text: "Line 3" }  // last item doesn't need breakLine
], { x: 0.5, y: 0.5, w: 8, h: 2 });
```

### 5. Never reuse option objects across calls (MUTATION TRAP)

pptxgenjs mutates shape options in place (e.g. converts shadow offset
from pt to EMU on first use). If you share one options object across
multiple `addShape` or `addText` calls, the second call gets
already-converted values and renders wrong.

```javascript
// ❌ WRONG — second shape's shadow is broken
const shadow = { type: "outer", blur: 6, offset: 2, color: "000000", opacity: 0.15 };
slide.addShape(pres.shapes.RECTANGLE, { shadow, ... });
slide.addShape(pres.shapes.RECTANGLE, { shadow, ... });

// ✅ CORRECT — factory returns a fresh object each time
const makeShadow = () => ({ type: "outer", blur: 6, offset: 2, color: "000000", opacity: 0.15 });
slide.addShape(pres.shapes.RECTANGLE, { shadow: makeShadow(), ... });
slide.addShape(pres.shapes.RECTANGLE, { shadow: makeShadow(), ... });
```

**This repo already uses this pattern** in `templates/pptxgenjs/slides.js`
for `makeShadow()`, `makeTextOptions()`, `makeCardShape()`. Match it when
adding new helpers — never return a shared singleton.

### 6. Avoid `lineSpacing` with bullets

Produces visible excessive gaps. Use `paraSpaceAfter` instead.

```javascript
// ✅ CORRECT
{ bullet: true, paraSpaceAfter: 6 }
```

### 7. Don't pair `ROUNDED_RECTANGLE` with rectangular accent overlays

A rectangular accent bar at the top of a rounded-corner card won't cover
the rounded corners — you get a visible gap at the top-left and top-right
corners. Use `RECTANGLE` for the card body when any rectangular overlay
(accent rail, dark header strip) needs to sit flush.

```javascript
// ❌ WRONG — accent bar leaves rounded-corner gaps
slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 1, y: 1, w: 3, h: 1.5, fill: { color: "FFFFFF" } });
slide.addShape(pres.shapes.RECTANGLE,         { x: 1, y: 1, w: 0.08, h: 1.5, fill: { color: "0891B2" } });

// ✅ CORRECT — RECTANGLE + RECTANGLE
slide.addShape(pres.shapes.RECTANGLE, { x: 1, y: 1, w: 3, h: 1.5, fill: { color: "FFFFFF" } });
slide.addShape(pres.shapes.RECTANGLE, { x: 1, y: 1, w: 0.08, h: 1.5, fill: { color: "0891B2" } });
```

The Python renderer enforces the same rule via
`rounded_card_with_accent_rail` in `layout_lint.py`.

### 8. `letterSpacing` is silently ignored — use `charSpacing`

```javascript
// ❌ Ignored (no error, just doesn't apply)
{ letterSpacing: 6 }

// ✅ CORRECT
{ charSpacing: 6 }
```

### 9. Fresh `pptxgen()` instance per deck

Don't reuse a pptxgen instance across decks. Each `writeFile()` should
follow from a freshly-constructed instance — shared state leaks between
decks.

### 10. Set `margin: 0` on text boxes that need to align with shapes

pptxgenjs text boxes have internal padding by default. When you're
aligning a text baseline or edge with a shape at the same `x`, the
padding pushes the text inward and the alignment looks wrong.

```javascript
slide.addText("Title", {
  x: 0.5, y: 0.3, w: 9, h: 0.6,
  margin: 0,  // align text precisely with shapes at x=0.5
});
```

## Shadow options (reference)

| Property | Type | Range | Notes |
|----------|------|-------|-------|
| `type` | string | `"outer"`, `"inner"` | |
| `color` | string | 6-char hex | No `#`, no 8-char hex (see pitfalls 1, 2) |
| `blur` | number | 0–100 pt | |
| `offset` | number | 0–200 pt | **Must be non-negative** — negative corrupts the file |
| `angle` | number | 0–359 deg | 135 = bottom-right; 270 = upward |
| `opacity` | number | 0.0–1.0 | Use this for transparency, never encode in color |

To cast a shadow upward (e.g. under a footer bar), use `angle: 270` with
a positive offset — **never** negate the offset.

Gradient fills are not natively supported. Use a gradient image as a
background instead.

## Image sizing modes

```javascript
// Contain — fit inside the box, preserve ratio
{ sizing: { type: "contain", w: 4, h: 3 } }

// Cover — fill the box, preserve ratio, may crop
{ sizing: { type: "cover", w: 4, h: 3 } }

// Crop — cut a specific rectangle out of the source
{ sizing: { type: "crop", x: 0.5, y: 0.5, w: 2, h: 2 } }
```

Preserve aspect ratio manually when neither `contain`/`cover` fits:

```javascript
const origW = 1978, origH = 923, maxH = 3.0;
const calcW = maxH * (origW / origH);
const centerX = (10 - calcW) / 2;
slide.addImage({ path: "image.png", x: centerX, y: 1.2, w: calcW, h: maxH });
```

Supported: PNG, JPG, GIF (animated only in Microsoft 365), SVG (modern
PowerPoint / 365). Always set `altText` on images that convey meaning.

## Modern chart styling

pptxgenjs defaults look dated. Apply these options for a clean,
publication-ready chart:

```javascript
slide.addChart(pres.charts.BAR, chartData, {
  x: 0.5, y: 1, w: 9, h: 4, barDir: "col",

  // Use your palette's accent ramp, not default blues
  chartColors: ["0D9488", "14B8A6", "5EEAD4"],

  chartArea: { fill: { color: "FFFFFF" }, roundedCorners: true },

  // Muted axis labels — don't compete with the data
  catAxisLabelColor: "64748B",
  valAxisLabelColor: "64748B",

  // Value-axis gridlines only; hide category gridlines
  valGridLine: { color: "E2E8F0", size: 0.5 },
  catGridLine: { style: "none" },

  // Labels on bars, not a legend, for single-series charts
  showValue: true,
  dataLabelPosition: "outEnd",
  dataLabelColor: "1E293B",
  showLegend: false,
});
```

Key styling options: `chartColors`, `chartArea.fill|border|roundedCorners`,
`catGridLine`/`valGridLine` (use `style: "none"` to hide), `lineSmooth`
(line charts), `legendPos: "r"|"b"|"t"|"l"|"tr"`.

## Quick reference

- **Shapes**: `RECTANGLE`, `OVAL`, `LINE`, `ROUNDED_RECTANGLE`
- **Charts**: `BAR`, `LINE`, `PIE`, `DOUGHNUT`, `SCATTER`, `BUBBLE`, `RADAR`
- **Layouts**: `LAYOUT_16x9` (10"×5.625"), `LAYOUT_16x10`, `LAYOUT_4x3`, `LAYOUT_WIDE`
- **Alignment**: `"left"`, `"center"`, `"right"`
