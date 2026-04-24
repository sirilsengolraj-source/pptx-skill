/*
 * Slide-family renderers for the pptxgenjs peer path.
 *
 * Canvas: LAYOUT_16x9 = 10.00" x 5.625".
 *   Side margins: 0.50"
 *   Title bar:    0.90" tall at y=0, full-bleed, dark fill, white text
 *   Content rail: starts at y = 0.90 (bar bottom edge)
 *
 * Each exported function has the shape:
 *   renderXxx(pptx, slide, slideData, preset)
 *
 * Important pptxgenjs rules respected here:
 *   - Hex colors NEVER carry a '#'. "1493A4" not "#1493A4".
 *   - Option objects are NEVER shared across addShape / addText calls.
 *     Use the factory helpers (txt(), shape(), card()) which return fresh
 *     objects each time. pptxgenjs mutates what you pass in, so reuse
 *     across slides produces silently broken output.
 *   - All text boxes set margin: 0 for precise alignment.
 */

'use strict';

const fs = require('fs');

// Canvas constants -- keep in sync with pptx.layout = 'LAYOUT_16x9'.
const SLIDE_W = 10.0;
const SLIDE_H = 5.625;
const MARGIN_X = 0.5;
// The dark title bar sits at y=0 (full-bleed) and is 0.90" tall. HEADER_TOP is
// kept for backwards compatibility with callers that reference it, but the bar
// itself now starts at y=0.
const HEADER_TOP = 0.0;
const TITLE_BAR_H = 0.9;
const CONTENT_TOP = HEADER_TOP + TITLE_BAR_H; // 0.90
const FOOTER_H = 0.32;

// ---------------------------------------------------------------------------
// Factory helpers. These exist because pptxgenjs mutates option objects in
// place during rendering. Reusing one object across shapes = silent bugs.
// ---------------------------------------------------------------------------

function textOpts(extra) {
  return Object.assign(
    {
      margin: 0,
      fontFace: 'Helvetica Neue',
      fontSize: 14,
      color: '0F172A',
      valign: 'top',
      align: 'left',
      isTextBox: true,
    },
    extra || {},
  );
}

function shapeOpts(extra) {
  return Object.assign(
    {
      line: { color: 'FFFFFF', width: 0 },
    },
    extra || {},
  );
}

function cardShadow() {
  // Fresh shadow descriptor every call. pptxgenjs will attach and mutate it.
  return {
    type: 'outer',
    color: '0F172A',
    opacity: 0.12,
    blur: 8,
    offset: 2,
    angle: 90,
  };
}

function safeText(value, fallback) {
  if (value === null || value === undefined) return fallback || '';
  const s = String(value).trim();
  return s.length ? s : fallback || '';
}

function truncate(s, max) {
  if (!s) return '';
  return s.length > max ? s.slice(0, Math.max(1, max - 1)) + '…' : s;
}

function imageDimensions(imagePath) {
  try {
    const buf = fs.readFileSync(imagePath);
    if (buf.length >= 24 && buf.toString('ascii', 1, 4) === 'PNG') {
      return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
    }
    if (buf.length >= 4 && buf[0] === 0xff && buf[1] === 0xd8) {
      let offset = 2;
      while (offset + 9 < buf.length) {
        if (buf[offset] !== 0xff) { offset += 1; continue; }
        const marker = buf[offset + 1];
        const len = buf.readUInt16BE(offset + 2);
        if (marker >= 0xc0 && marker <= 0xc3) {
          return { w: buf.readUInt16BE(offset + 7), h: buf.readUInt16BE(offset + 5) };
        }
        offset += 2 + len;
      }
    }
  } catch (_e) {}
  return null;
}

function imageSizingContainLocal(imagePath, x, y, w, h) {
  const size = imageDimensions(imagePath);
  if (!size || !size.w || !size.h) return { x, y, w, h };
  const boxRatio = w / Math.max(h, 0.01);
  const imageRatio = size.w / size.h;
  let fitW;
  let fitH;
  if (imageRatio >= boxRatio) {
    fitW = w;
    fitH = w / imageRatio;
  } else {
    fitH = h;
    fitW = h * imageRatio;
  }
  return { x: x + (w - fitW) / 2, y: y + (h - fitH) / 2, w: fitW, h: fitH };
}

function generatedImageMeta(imagePath, slideData) {
  const meta = {};
  if (imagePath) {
    const metaPath = `${imagePath}.metadata.json`;
    if (fs.existsSync(metaPath)) {
      try {
        Object.assign(meta, JSON.parse(fs.readFileSync(metaPath, 'utf8')));
      } catch (_e) {}
    }
  }
  if (slideData.image_generation && typeof slideData.image_generation === 'object') {
    Object.assign(meta, slideData.image_generation);
  }
  return meta;
}

// ---------------------------------------------------------------------------
// Shared chrome: background, title bar, footer, optional background image.
// ---------------------------------------------------------------------------

function paintBackground(slide, color) {
  slide.background = { color: color };
}

function addBackgroundImage(slide, imagePath, preset) {
  if (!imagePath) return;
  if (!fs.existsSync(imagePath)) {
    console.warn(`[pptxgenjs] background_image not found, skipping: ${imagePath}`);
    return;
  }
  slide.addImage({
    path: imagePath,
    x: 0,
    y: 0,
    w: SLIDE_W,
    h: SLIDE_H,
    sizing: { type: 'cover', w: SLIDE_W, h: SLIDE_H },
    transparency: 15,
  });
  // Dim overlay so text stays readable.
  slide.addShape('rect', shapeOpts({
    x: 0, y: 0, w: SLIDE_W, h: SLIDE_H,
    fill: { color: preset.bg_dark, transparency: 55 },
  }));
}

function addDarkTitleBar(slide, preset, title, subtitle) {
  // Full-bleed dark bar at the top of every content slide. Invariant: the bar
  // is TITLE_BAR_H (0.90") tall at y=0. Content region starts at CONTENT_TOP
  // (= bar bottom edge = 0.90").
  slide.addShape('rect', shapeOpts({
    x: 0, y: 0, w: SLIDE_W, h: TITLE_BAR_H,
    fill: { color: preset.bg_dark },
  }));
  // Thin accent underline sits flush with the bar's bottom edge.
  // When the preset opts into `header_accent_stripe`, use
  // accent_secondary so the stripe is visible even on presets where
  // accent_primary matches bg_dark (e.g., lab-report's clinical-red
  // under-stripe against the navy header).
  const stripeColor = preset.header_accent_stripe
    ? (preset.accent_secondary || preset.accent_primary)
    : preset.accent_primary;
  slide.addShape('rect', shapeOpts({
    x: 0, y: TITLE_BAR_H, w: SLIDE_W, h: 0.04,
    fill: { color: stripeColor },
  }));

  slide.addText(safeText(title, 'Untitled'), textOpts({
    x: MARGIN_X,
    y: 0,
    w: SLIDE_W - MARGIN_X * 2,
    h: subtitle ? 0.52 : TITLE_BAR_H,
    fontFace: preset.font_heading,
    fontSize: 26,
    bold: true,
    color: 'FFFFFF',
    valign: subtitle ? 'bottom' : 'middle',
  }));

  if (subtitle) {
    slide.addText(safeText(subtitle), textOpts({
      x: MARGIN_X,
      y: 0.55,
      w: SLIDE_W - MARGIN_X * 2,
      h: 0.32,
      fontFace: preset.font_body,
      fontSize: 13,
      color: preset.accent_primary,
      bold: false,
    }));
  }
}

function extractSourceText(src) {
  if (src === null || src === undefined) return '';
  if (typeof src === 'string') return src.trim();
  if (typeof src === 'number' || typeof src === 'boolean') return String(src);
  if (typeof src === 'object') {
    // Prefer explicit text-bearing fields, in priority order.
    const keys = ['text', 'citation', 'source', 'title', 'label', 'name'];
    for (const k of keys) {
      const v = src[k];
      if (typeof v === 'string' && v.trim()) return v.trim();
    }
    // Last-ditch: first string-valued property.
    for (const k of Object.keys(src)) {
      const v = src[k];
      if (typeof v === 'string' && v.trim()) return v.trim();
    }
  }
  return '';
}

function addFooter(slide, preset, slideData) {
  const footer = safeText(slideData.footer);
  const sources = Array.isArray(slideData.sources)
    ? slideData.sources.map(extractSourceText).filter(Boolean)
    : [];
  if (!footer && sources.length === 0) return;

  const y = SLIDE_H - FOOTER_H;
  // Thin accent line above footer.
  slide.addShape('rect', shapeOpts({
    x: MARGIN_X, y: y - 0.04, w: SLIDE_W - MARGIN_X * 2, h: 0.02,
    fill: { color: preset.line },
  }));

  if (footer) {
    slide.addText(footer, textOpts({
      x: MARGIN_X,
      y: y,
      w: (SLIDE_W - MARGIN_X * 2) * 0.55,
      h: FOOTER_H,
      fontFace: preset.font_body,
      fontSize: 10,
      color: preset.text_muted,
      valign: 'middle',
    }));
  }
  if (sources.length) {
    slide.addText('Sources: ' + sources.join('; '), textOpts({
      x: MARGIN_X + (SLIDE_W - MARGIN_X * 2) * 0.45,
      y: y,
      w: (SLIDE_W - MARGIN_X * 2) * 0.55,
      h: FOOTER_H,
      fontFace: preset.font_body,
      fontSize: 9,
      color: preset.text_muted,
      italic: true,
      align: 'right',
      valign: 'middle',
    }));
  }
}

function attachNotes(slide, slideData) {
  const notes = safeText(slideData.notes);
  if (notes) slide.addNotes(notes);
}

// ---------------------------------------------------------------------------
// Title slide: big hero title, centered, no dark header bar.
// ---------------------------------------------------------------------------

function renderTitle(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg_dark);
  addBackgroundImage(slide, slideData.background_image, preset);

  // When a hero image is staged, place it on the right half and narrow the
  // text column to the left half. Otherwise use the standard full-width layout.
  const heroPath = slideData.__heroPath;
  const hasHero = heroPath && fs.existsSync(heroPath);
  const textRight = hasHero ? 5.3 : SLIDE_W - MARGIN_X;
  const textW = textRight - MARGIN_X;

  if (hasHero) {
    try {
      const imgX = 5.6;
      const imgY = 0.85;
      const imgW = SLIDE_W - imgX - MARGIN_X;
      const imgH = SLIDE_H - imgY - 0.85;
      const sized = imageSizingContainLocal(heroPath, imgX, imgY, imgW, imgH);
      slide.addImage(Object.assign({ path: heroPath }, sized));
    } catch (e) {
      console.warn('[pptxgenjs] hero_image failed:', e.message);
    }
  }

  // Accent stripe, left-aligned, as an editorial touch.
  slide.addShape('rect', shapeOpts({
    x: MARGIN_X,
    y: 1.85,
    w: 0.6,
    h: 0.08,
    fill: { color: preset.accent_primary },
  }));

  slide.addText(safeText(slideData.title, 'Untitled Deck'), textOpts({
    x: MARGIN_X,
    y: 2.00,
    w: textW,
    h: 1.4,
    fontFace: preset.font_heading,
    fontSize: hasHero ? 36 : 44,
    bold: true,
    color: 'FFFFFF',
    valign: 'top',
  }));

  const subtitle = safeText(slideData.subtitle);
  if (subtitle) {
    slide.addText(subtitle, textOpts({
      x: MARGIN_X,
      y: 3.45,
      w: textW,
      h: 0.9,
      fontFace: preset.font_body,
      fontSize: hasHero ? 16 : 20,
      color: preset.accent_primary,
      valign: 'top',
    }));
  }

  const footer = safeText(slideData.footer);
  if (footer) {
    slide.addText(footer, textOpts({
      x: MARGIN_X,
      y: SLIDE_H - 0.55,
      w: SLIDE_W - MARGIN_X * 2,
      h: 0.35,
      fontFace: preset.font_body,
      fontSize: 11,
      color: preset.text_muted,
      valign: 'middle',
    }));
  }
  attachNotes(slide, slideData);
}

// ---------------------------------------------------------------------------
// Section divider: full-bleed dark slide, oversized title, optional subtitle.
// ---------------------------------------------------------------------------

function renderSection(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg_dark);
  addBackgroundImage(slide, slideData.background_image, preset);

  // Large accent block as divider motif.
  slide.addShape('rect', shapeOpts({
    x: MARGIN_X,
    y: 2.55,
    w: 1.2,
    h: 0.10,
    fill: { color: preset.accent_primary },
  }));

  slide.addText(safeText(slideData.title, 'Section'), textOpts({
    x: MARGIN_X,
    y: 1.40,
    w: SLIDE_W - MARGIN_X * 2,
    h: 1.10,
    fontFace: preset.font_heading,
    fontSize: 40,
    bold: true,
    color: 'FFFFFF',
  }));

  const subtitle = safeText(slideData.subtitle);
  if (subtitle) {
    slide.addText(subtitle, textOpts({
      x: MARGIN_X,
      y: 2.80,
      w: SLIDE_W - MARGIN_X * 2,
      h: 1.20,
      fontFace: preset.font_body,
      fontSize: 18,
      color: preset.text_muted,
    }));
  }
  attachNotes(slide, slideData);
}

// ---------------------------------------------------------------------------
// Bullet helpers: shared by standard + split variants.
// ---------------------------------------------------------------------------

function normalizeBullets(items) {
  if (!Array.isArray(items)) return [];
  const out = [];
  for (const item of items) {
    if (item === null || item === undefined) continue;
    if (typeof item === 'string') {
      const t = item.trim();
      if (t) out.push({ text: t, level: 0 });
    } else if (typeof item === 'object') {
      const t = safeText(item.text);
      if (t) {
        let level = Number(item.level);
        if (!Number.isFinite(level) || level < 0) level = 0;
        if (level > 2) level = 2;
        out.push({ text: t, level });
      }
    }
  }
  return out;
}

function bulletTextArray(bullets, preset) {
  // pptxgenjs accepts an array of { text, options } for mixed bullet levels.
  // Two invariants from references/pptxgenjs.md:
  //   - `bullet: { code: '2022' }` (unicode bullet code) renders reliably
  //     in LibreOffice; `{ type: 'bullet' }` sometimes doesn't.
  //   - Every item except the last must carry `breakLine: true` or
  //     pptxgenjs concatenates them into a single paragraph.
  const n = bullets.length;
  return bullets.map((b, i) => ({
    text: b.text,
    options: {
      bullet: { code: '2022' },
      fontFace: preset.font_body,
      fontSize: b.level === 0 ? 16 : 14,
      color: b.level === 0 ? preset.text : preset.text_muted,
      paraSpaceAfter: 6,
      indentLevel: b.level,
      breakLine: i < n - 1,
    },
  }));
}

// ---------------------------------------------------------------------------
// Standard content: title + bullets column, optional pull-quote on right.
// ---------------------------------------------------------------------------

function renderStandard(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle);

  let bullets = normalizeBullets(slideData.bullets);
  const highlights = Array.isArray(slideData.highlights)
    ? slideData.highlights.map((h) => safeText(h)).filter(Boolean)
    : [];

  // Matrix fallback: if no bullets/body/paragraphs but `quadrants` is present,
  // synthesize bullets from each quadrant so the content is not silently lost.
  // (Native matrix layout is not yet implemented in the pptxgenjs peer path.)
  if (bullets.length === 0
      && !safeText(slideData.body)
      && !(Array.isArray(slideData.paragraphs) && slideData.paragraphs.length)
      && Array.isArray(slideData.quadrants) && slideData.quadrants.length) {
    console.warn(
      '[pptxgenjs] matrix variant is not implemented; ' +
      'synthesizing bullets from quadrants so content is preserved.',
    );
    bullets = slideData.quadrants.slice(0, 4).map((q) => {
      const title = safeText(q && q.title);
      const body = safeText(q && q.body);
      const text = title && body ? `${title}: ${body}` : (title || body);
      return text;
    }).filter(Boolean).map((t) => ({ text: t, level: 0 }));
  }

  const contentY = CONTENT_TOP + 0.25;
  const contentH = SLIDE_H - contentY - 0.55;

  const hasHighlights = highlights.length > 0;
  const leftW = hasHighlights ? 5.6 : SLIDE_W - MARGIN_X * 2;

  if (bullets.length) {
    // Mirror python renderer's "body + bullets" composition: if the
    // outline has both `body` (prose) AND bullets, render body as an
    // intro paragraph above the bullets. Matches _add_standard_content.
    const introText = safeText(slideData.body);
    let currentY = contentY;
    if (introText) {
      const introH = Math.min(1.0, Math.max(0.48, 0.20 + introText.length / 180));
      slide.addText(introText, textOpts({
        x: MARGIN_X,
        y: currentY,
        w: leftW,
        h: introH,
        fontFace: preset.font_body,
        fontSize: 16,
        color: preset.text,
        valign: 'top',
        paraSpaceAfter: 8,
      }));
      currentY += introH + 0.12;
    }
    slide.addText(bulletTextArray(bullets, preset), textOpts({
      x: MARGIN_X,
      y: currentY,
      w: leftW,
      h: Math.max(0.5, contentH - (currentY - contentY)),
      fontFace: preset.font_body,
      fontSize: 16,
      color: preset.text,
      valign: 'top',
      paraSpaceAfter: 6,
    }));
  } else {
    // Fall back to `paragraphs` (array of strings) or `body` (single string).
    // Schema lists both as Common Text Fields; without this, schema-valid
    // slides authored with only `body` would render empty below the title.
    let paragraphs = [];
    if (Array.isArray(slideData.paragraphs) && slideData.paragraphs.length) {
      paragraphs = slideData.paragraphs
        .map((p) => safeText(p))
        .filter(Boolean);
    } else {
      const body = safeText(slideData.body);
      if (body) paragraphs = [body];
    }
    if (paragraphs.length) {
      const items = paragraphs.map((p, i) => ({
        text: p,
        options: {
          fontFace: preset.font_body,
          fontSize: 16,
          color: preset.text,
          paraSpaceAfter: i < paragraphs.length - 1 ? 10 : 0,
        },
      }));
      slide.addText(items, textOpts({
        x: MARGIN_X,
        y: contentY,
        w: leftW,
        h: contentH,
        fontFace: preset.font_body,
        fontSize: 16,
        color: preset.text,
        valign: 'top',
      }));
    }
  }

  if (hasHighlights) {
    const cardX = MARGIN_X + leftW + 0.2;
    const cardW = SLIDE_W - cardX - MARGIN_X;
    slide.addShape('roundRect', shapeOpts({
      x: cardX, y: contentY, w: cardW, h: contentH,
      fill: { color: preset.surface || 'FFFFFF' },
      line: { color: preset.line, width: 0.75 },
      rectRadius: 0.08,
      shadow: cardShadow(),
    }));
    slide.addText('Key takeaways', textOpts({
      x: cardX + 0.2, y: contentY + 0.15, w: cardW - 0.4, h: 0.3,
      fontFace: preset.font_heading,
      fontSize: 11,
      bold: true,
      color: preset.accent_primary,
    }));
    const hiItems = highlights.map((h) => ({
      text: h,
      options: {
        bullet: { type: 'bullet', indent: 12 },
        fontFace: preset.font_body,
        fontSize: 13,
        color: preset.text,
        paraSpaceAfter: 5,
      },
    }));
    slide.addText(hiItems, textOpts({
      x: cardX + 0.2,
      y: contentY + 0.5,
      w: cardW - 0.4,
      h: contentH - 0.65,
      fontFace: preset.font_body,
      fontSize: 13,
      color: preset.text,
      valign: 'top',
    }));
  }

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

// ---------------------------------------------------------------------------
// Cards grid: 2- or 3-column card layout.
// ---------------------------------------------------------------------------

function renderCards(pptx, slide, slideData, preset, columns) {
  paintBackground(slide, preset.bg);
  addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle);

  const rawCards = Array.isArray(slideData.cards) ? slideData.cards : [];
  const cols = columns === 2 ? 2 : 3;
  const cards = rawCards.slice(0, cols);
  while (cards.length < cols) {
    cards.push({ title: '', body: '', accent: 'accent_primary' });
  }

  const gutter = 0.24;
  const usableW = SLIDE_W - MARGIN_X * 2;
  const cardY = CONTENT_TOP + 0.35;
  const cardH = SLIDE_H - cardY - 0.65;

  // Asymmetric cards-3 when `promote_card` is set (integer 0-2). One
  // card takes the full left column at double height; the other two
  // stack on the right. Breaks the 3-up grid without a new variant.
  const promote = slideData.promote_card;
  const useAsymmetric =
    cols === 3 &&
    Number.isInteger(promote) &&
    promote >= 0 &&
    promote < cards.length;

  // Per-card positions: each entry is {x, y, w, h, accentKey, maxLines}
  let placements;
  if (useAsymmetric) {
    const leftW = usableW * 0.60 - gutter / 2;
    const rightW = usableW - leftW - gutter;
    const smallH = (cardH - gutter) / 2;
    const others = [0, 1, 2].filter((i) => i !== promote);
    placements = [null, null, null];
    placements[promote] = { x: MARGIN_X, y: cardY, w: leftW, h: cardH, big: true };
    placements[others[0]] = {
      x: MARGIN_X + leftW + gutter, y: cardY, w: rightW, h: smallH, big: false,
    };
    placements[others[1]] = {
      x: MARGIN_X + leftW + gutter, y: cardY + smallH + gutter, w: rightW, h: smallH, big: false,
    };
  } else {
    const cardW = (usableW - gutter * (cols - 1)) / cols;
    placements = cards.map((_, idx) => ({
      x: MARGIN_X + idx * (cardW + gutter),
      y: cardY,
      w: cardW,
      h: cardH,
      big: false,
    }));
  }

  const iconPaths = Array.isArray(slideData.__iconPaths) ? slideData.__iconPaths : [];

  cards.forEach((card, idx) => {
    const pos = placements[idx];
    const cx = pos.x;
    const cy = pos.y;
    const cw = pos.w;
    const ch = pos.h;
    const accentKey = card.accent === 'accent_secondary' ? 'accent_secondary' : 'accent_primary';
    const accentColor = preset[accentKey] || preset.accent_primary;

    // Card surface.
    slide.addShape('roundRect', shapeOpts({
      x: cx, y: cy, w: cw, h: ch,
      fill: { color: preset.surface || 'FFFFFF' },
      line: { color: preset.line, width: 0.75 },
      rectRadius: 0.08,
      shadow: cardShadow(),
    }));
    // Top accent rail.
    slide.addShape('rect', shapeOpts({
      x: cx, y: cy, w: cw, h: 0.10,
      fill: { color: accentColor },
    }));

    // Optional icon above card title. Icons are pre-resolved to PNG paths by
    // the build script (react-icons slugs like 'fa6:FaLightbulb' get
    // rasterized; bare filenames resolve against the outline dir).
    const iconPath = iconPaths[idx];
    const iconSize = 0.5;
    const hasIcon = iconPath && fs.existsSync(iconPath);
    const titleYShift = hasIcon ? (iconSize + 0.08) : 0;

    if (hasIcon) {
      slide.addImage({
        path: iconPath,
        x: cx + (cw - iconSize) / 2,
        y: cy + 0.22,
        w: iconSize,
        h: iconSize,
      });
    }

    const padX = 0.25;
    slide.addText(safeText(card.title, ''), textOpts({
      x: cx + padX,
      y: cy + 0.28 + titleYShift,
      w: cw - padX * 2,
      h: 0.55,
      fontFace: preset.font_heading,
      fontSize: pos.big ? 22 : 18,
      bold: true,
      color: preset.text,
    }));
    slide.addText(safeText(card.body, ''), textOpts({
      x: cx + padX,
      y: cy + 0.92 + titleYShift,
      w: cw - padX * 2,
      h: ch - 1.05 - titleYShift,
      fontFace: preset.font_body,
      fontSize: pos.big ? 14 : 13,
      color: preset.text_muted,
      valign: 'top',
      paraSpaceAfter: 4,
    }));
  });

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

// ---------------------------------------------------------------------------
// Split layout: bullets on the left, highlight panel on the right.
// ---------------------------------------------------------------------------

function renderSplit(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle);

  const contentY = CONTENT_TOP + 0.30;
  const contentH = SLIDE_H - contentY - 0.60;
  const usableW = SLIDE_W - MARGIN_X * 2;
  const leftW = usableW * 0.58;
  const gutter = 0.25;
  const rightW = usableW - leftW - gutter;
  const rightX = MARGIN_X + leftW + gutter;

  const bullets = normalizeBullets(slideData.bullets);
  if (bullets.length) {
    slide.addText(bulletTextArray(bullets, preset), textOpts({
      x: MARGIN_X,
      y: contentY,
      w: leftW,
      h: contentH,
      fontFace: preset.font_body,
      fontSize: 16,
      color: preset.text,
      valign: 'top',
      paraSpaceAfter: 6,
    }));
  }

  // Right panel -- dark card with highlights or subtitle-style text.
  slide.addShape('roundRect', shapeOpts({
    x: rightX, y: contentY, w: rightW, h: contentH,
    fill: { color: preset.bg_dark },
    line: { color: preset.bg_dark, width: 0 },
    rectRadius: 0.08,
    shadow: cardShadow(),
  }));
  // Accent stripe on the right panel.
  slide.addShape('rect', shapeOpts({
    x: rightX, y: contentY, w: 0.10, h: contentH,
    fill: { color: preset.accent_primary },
  }));

  const highlights = Array.isArray(slideData.highlights)
    ? slideData.highlights.map((h) => safeText(h)).filter(Boolean)
    : [];
  const label = safeText(slideData.highlights_label, 'Focus');
  slide.addText(label.toUpperCase(), textOpts({
    x: rightX + 0.3,
    y: contentY + 0.25,
    w: rightW - 0.5,
    h: 0.30,
    fontFace: preset.font_heading,
    fontSize: 11,
    bold: true,
    color: preset.accent_primary,
    charSpacing: 2,
  }));

  if (highlights.length) {
    const n = Math.min(highlights.length, 5);
    const items = highlights.slice(0, n).map((h, i) => ({
      text: h,
      options: {
        bullet: { code: '2022' },
        fontFace: preset.font_body,
        fontSize: 14,
        color: 'FFFFFF',
        paraSpaceAfter: 6,
        breakLine: i < n - 1,
      },
    }));
    slide.addText(items, textOpts({
      x: rightX + 0.3,
      y: contentY + 0.65,
      w: rightW - 0.5,
      h: contentH - 0.85,
      fontFace: preset.font_body,
      fontSize: 14,
      color: 'FFFFFF',
      valign: 'top',
    }));
  } else {
    // Fall back to subtitle / footer as the right-panel narrative.
    const narrative = safeText(slideData.subtitle) || safeText(slideData.footer);
    if (narrative) {
      slide.addText(narrative, textOpts({
        x: rightX + 0.3,
        y: contentY + 0.65,
        w: rightW - 0.5,
        h: contentH - 0.85,
        fontFace: preset.font_body,
        fontSize: 14,
        color: 'FFFFFF',
        valign: 'top',
      }));
    }
  }

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

// ---------------------------------------------------------------------------
// Timeline: horizontal milestone rail with marker dots + label cards.
// ---------------------------------------------------------------------------

function renderTimeline(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle);

  const defaults = [
    { label: 'Q1', title: 'Discover', body: 'Define baseline' },
    { label: 'Q2', title: 'Build', body: 'Pilot delivery' },
    { label: 'Q3', title: 'Scale', body: 'Expand coverage' },
    { label: 'Q4', title: 'Optimize', body: 'Harden operations' },
  ];
  const rawItems = Array.isArray(slideData.milestones) && slideData.milestones.length
    ? slideData.milestones.slice(0, 5)
    : defaults;
  const count = rawItems.length;

  const usableW = SLIDE_W - MARGIN_X * 2;
  const gutter = 0.20;
  const cardW = Math.max(1.5, (usableW - gutter * (count - 1)) / count);
  const totalW = cardW * count + gutter * (count - 1);
  const startX = MARGIN_X + (usableW - totalW) / 2;

  const railY = CONTENT_TOP + 0.85;
  const markerR = 0.22;

  // Horizontal rail.
  slide.addShape('rect', shapeOpts({
    x: startX, y: railY - 0.03, w: totalW, h: 0.06,
    fill: { color: preset.line },
  }));

  const iconPaths = Array.isArray(slideData.__iconPaths) ? slideData.__iconPaths : [];

  // Markers + cards.
  rawItems.forEach((item, idx) => {
    const cardX = startX + idx * (cardW + gutter);
    const cx = cardX + cardW / 2;
    const accentKey = idx % 2 === 0 ? 'accent_primary' : 'accent_secondary';
    const accentColor = preset[accentKey] || preset.accent_primary;

    // Marker circle.
    slide.addShape('ellipse', shapeOpts({
      x: cx - markerR,
      y: railY - markerR,
      w: markerR * 2,
      h: markerR * 2,
      fill: { color: accentColor },
      line: { color: preset.bg, width: 1.5 },
    }));

    // Label text above the rail.
    slide.addText(safeText(item.label, `Phase ${idx + 1}`), textOpts({
      x: cardX,
      y: railY - 0.80,
      w: cardW,
      h: 0.32,
      fontFace: preset.font_heading,
      fontSize: 12,
      bold: true,
      color: accentColor,
      align: 'center',
      charSpacing: 2,
    }));

    // Card below the rail.
    const cardY = railY + 0.35;
    const cardH = SLIDE_H - cardY - 0.65;
    slide.addShape('roundRect', shapeOpts({
      x: cardX, y: cardY, w: cardW, h: cardH,
      fill: { color: preset.surface || 'FFFFFF' },
      line: { color: preset.line, width: 0.75 },
      rectRadius: 0.08,
      shadow: cardShadow(),
    }));
    // Top accent rail on the card.
    slide.addShape('rect', shapeOpts({
      x: cardX, y: cardY, w: cardW, h: 0.08,
      fill: { color: accentColor },
    }));

    // Optional icon above the card title.
    const iconPath = iconPaths[idx];
    const iconSize = 0.35;
    const hasIcon = iconPath && fs.existsSync(iconPath);
    const cardShift = hasIcon ? (iconSize + 0.04) : 0;
    if (hasIcon) {
      slide.addImage({
        path: iconPath,
        x: cardX + (cardW - iconSize) / 2,
        y: cardY + 0.18,
        w: iconSize,
        h: iconSize,
      });
    }

    slide.addText(safeText(item.title, item.label || `Step ${idx + 1}`), textOpts({
      x: cardX + 0.15,
      y: cardY + 0.22 + cardShift,
      w: cardW - 0.30,
      h: 0.50,
      fontFace: preset.font_heading,
      fontSize: 15,
      bold: true,
      color: preset.text,
    }));
    slide.addText(safeText(item.body || item.text, ''), textOpts({
      x: cardX + 0.15,
      y: cardY + 0.75 + cardShift,
      w: cardW - 0.30,
      h: cardH - 0.85,
      fontFace: preset.font_body,
      fontSize: 11,
      color: preset.text_muted,
      valign: 'top',
      paraSpaceAfter: 4,
    }));
  });

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

// ---------------------------------------------------------------------------
// Stats: oversized fact tiles (value + label + optional caption/source).
// ---------------------------------------------------------------------------

function normalizeFacts(facts) {
  if (!Array.isArray(facts)) return [];
  return facts
    .map((f) => {
      if (!f || typeof f !== 'object') return null;
      const accentRaw = typeof f.accent === 'string' ? f.accent.trim() : '';
      let accent = null;
      if (accentRaw === 'accent_primary' || accentRaw === 'accent_secondary') {
        accent = accentRaw;
      }
      return {
        value: safeText(f.value || f.stat || f.number),
        label: safeText(f.label || f.title),
        caption: safeText(f.detail || f.caption || f.body || f.text),
        source: safeText(f.source),
        accent: accent,
      };
    })
    .filter((f) => f && (f.value || f.label));
}

function renderStats(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle);

  const facts = normalizeFacts(slideData.facts).slice(0, 4);
  if (facts.length === 0) {
    slide.addText('No facts provided.', textOpts({
      x: MARGIN_X,
      y: CONTENT_TOP + 1.0,
      w: SLIDE_W - MARGIN_X * 2,
      h: 0.5,
      fontFace: preset.font_body,
      fontSize: 14,
      color: preset.text_muted,
      align: 'center',
    }));
    addFooter(slide, preset, slideData);
    attachNotes(slide, slideData);
    return;
  }

  const cols = facts.length;
  const gutter = 0.28;
  const usableW = SLIDE_W - MARGIN_X * 2;
  const tileW = (usableW - gutter * (cols - 1)) / cols;
  const tileY = CONTENT_TOP + 0.45;
  const tileH = SLIDE_H - tileY - 0.75;

  const iconPaths = Array.isArray(slideData.__iconPaths) ? slideData.__iconPaths : [];

  facts.forEach((fact, idx) => {
    const tx = MARGIN_X + idx * (tileW + gutter);
    // Per-fact accent when explicitly set on the fact; otherwise alternate.
    const accentKey = fact.accent
      ? fact.accent
      : (idx % 2 === 0 ? 'accent_primary' : 'accent_secondary');
    const accentColor = preset[accentKey] || preset.accent_primary;

    slide.addShape('roundRect', shapeOpts({
      x: tx, y: tileY, w: tileW, h: tileH,
      fill: { color: preset.bg_dark },
      line: { color: preset.bg_dark, width: 0 },
      rectRadius: 0.08,
      shadow: cardShadow(),
    }));
    // Left accent rail.
    slide.addShape('rect', shapeOpts({
      x: tx, y: tileY, w: 0.08, h: tileH,
      fill: { color: accentColor },
    }));

    // Optional icon above the stat value (smaller than cards — value stays
    // the dominant element).
    const iconPath = iconPaths[idx];
    const iconSize = 0.4;
    const hasIcon = iconPath && fs.existsSync(iconPath);
    const valueYShift = hasIcon ? (iconSize + 0.06) : 0;
    if (hasIcon) {
      slide.addImage({
        path: iconPath,
        x: tx + 0.25,
        y: tileY + 0.22,
        w: iconSize,
        h: iconSize,
      });
    }

    // Large stat value.
    slide.addText(truncate(fact.value || '-', 10), textOpts({
      x: tx + 0.25,
      y: tileY + 0.28 + valueYShift,
      w: tileW - 0.4,
      h: tileH * 0.45,
      fontFace: preset.font_heading,
      fontSize: 44,
      bold: true,
      color: accentColor,
      valign: 'middle',
    }));
    slide.addText(fact.label || '', textOpts({
      x: tx + 0.25,
      y: tileY + tileH * 0.50,
      w: tileW - 0.4,
      h: 0.45,
      fontFace: preset.font_heading,
      fontSize: 14,
      bold: true,
      color: 'FFFFFF',
      valign: 'top',
    }));
    if (fact.caption) {
      slide.addText(fact.caption, textOpts({
        x: tx + 0.25,
        y: tileY + tileH * 0.68,
        w: tileW - 0.4,
        h: tileH * 0.28,
        fontFace: preset.font_body,
        fontSize: 11,
        color: preset.text_muted,
        valign: 'top',
        paraSpaceAfter: 3,
      }));
    }
    if (fact.source) {
      slide.addText('Source: ' + fact.source, textOpts({
        x: tx + 0.25,
        y: tileY + tileH - 0.30,
        w: tileW - 0.4,
        h: 0.22,
        fontFace: preset.font_body,
        fontSize: 9,
        color: preset.text_muted,
        italic: true,
      }));
    }
  });

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// kpi-hero variant — single giant number on a dark bg. The rhythm-break
// moment of the deck. Mirrors the python renderer (build_deck.py) closely
// so switching renderers produces the same composition.
// ---------------------------------------------------------------------------

function kpiValueFontSize(valueText) {
  const n = (valueText || '').trim().length;
  if (n <= 4) return 120;
  if (n <= 6) return 96;
  if (n <= 8) return 72;
  return 60;
}

function renderKpiHero(pptx, slide, slideData, preset) {
  const dark = slideData.theme !== 'light';
  const bgColor = dark ? (preset.bg_dark || '0F172A') : preset.bg;
  paintBackground(slide, bgColor);

  // Title + subtitle on the top of the slide in light text for dark mode.
  const titleColor = dark ? 'FFFFFF' : preset.text_primary;
  const subtitleColor = dark ? 'CBD5E1' : preset.text_muted;
  slide.addText(String(slideData.title || '').trim(), textOpts({
    x: MARGIN_X,
    y: 0.34,
    w: SLIDE_W - MARGIN_X * 2,
    h: 0.62,
    fontFace: preset.font_title,
    fontSize: 28,
    color: titleColor,
    bold: true,
  }));
  const subtitle = String(slideData.subtitle || '').trim();
  if (subtitle) {
    slide.addText(subtitle, textOpts({
      x: MARGIN_X,
      y: 0.96,
      w: SLIDE_W - MARGIN_X * 2,
      h: 0.42,
      fontFace: preset.font_caption,
      fontSize: 14,
      color: subtitleColor,
    }));
  }

  const value = String(slideData.value || '?').trim();
  const label = String(slideData.label || '').trim();
  const context = String(slideData.context || '').trim();
  const valueFont = kpiValueFontSize(value);

  const valueColor = dark
    ? (preset.accent_secondary || preset.accent_primary || 'F59E0B')
    : preset.accent_primary;

  // Center value vertically in the content zone, but reserve space for the
  // subtitle. Without this reservation, the big value shape overlaps the
  // subtitle (subtitle bottom = 0.96 + 0.42 = 1.38).
  const effectiveContentTop = subtitle ? 1.50 : CONTENT_TOP;
  const contentH = SLIDE_H - effectiveContentTop - 0.6;
  const valueH = Math.min(2.1, Math.max(1.3, valueFont / 72 * 1.25));
  const labelH = label ? 0.5 : 0;
  // Context box: scale height with line count. 13pt font across a ~7.4"-wide
  // box fits ~80 chars per line. Short strings get 0.42"; longer ones get
  // 0.42" per estimated line up to 3 lines. Previous flat 0.42" overflowed.
  let contextH = 0;
  if (context) {
    const charsPerLine = 80;
    const estimatedLines = Math.min(3, Math.max(1, Math.ceil(context.length / charsPerLine)));
    contextH = 0.42 * estimatedLines;
  }
  const totalStack = valueH + (label ? 0.15 : 0) + labelH +
                     (context ? 0.10 : 0) + contextH;
  const startY = effectiveContentTop + Math.max(0.2, (contentH - totalStack) / 2);

  slide.addText(value, textOpts({
    x: MARGIN_X,
    y: startY,
    w: SLIDE_W - MARGIN_X * 2,
    h: valueH,
    fontFace: preset.font_title,
    fontSize: valueFont,
    color: valueColor,
    bold: true,
    align: 'center',
  }));
  if (label) {
    slide.addText(label, textOpts({
      x: MARGIN_X,
      y: startY + valueH + 0.15,
      w: SLIDE_W - MARGIN_X * 2,
      h: labelH,
      fontFace: preset.font_title,
      fontSize: 24,
      color: titleColor,
      bold: true,
      align: 'center',
    }));
  }
  if (context) {
    const contextY = startY + valueH + (label ? 0.15 + labelH + 0.10 : 0.15);
    slide.addText(context, textOpts({
      x: MARGIN_X + 0.8,
      y: contextY,
      w: SLIDE_W - (MARGIN_X + 0.8) * 2,
      h: contextH,
      fontFace: preset.font_caption,
      fontSize: 13,
      color: subtitleColor,
      align: 'center',
    }));
  }

  addFooter(slide, preset, slideData, { dark });
  attachNotes(slide, slideData);
}


// ---------------------------------------------------------------------------
// table variant — native pptxgenjs addTable. Cleaner typography than the
// python renderer's add_table; this is the reason the HTML path exists.
// ---------------------------------------------------------------------------

function renderTable(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle);

  const headers = Array.isArray(slideData.headers) ? slideData.headers : [];
  const rows = Array.isArray(slideData.rows) ? slideData.rows : [];
  if (headers.length === 0 || rows.length === 0) {
    slide.addText('table variant requires `headers` + `rows`.', textOpts({
      x: MARGIN_X,
      y: CONTENT_TOP + 0.4,
      w: SLIDE_W - MARGIN_X * 2,
      h: 0.5,
      fontFace: preset.font_body,
      fontSize: 14,
      color: preset.text_muted,
    }));
    addFooter(slide, preset, slideData);
    attachNotes(slide, slideData);
    return;
  }

  const caption = String(slideData.caption || '').trim();
  const captionGap = caption ? 0.14 : 0;
  const captionH = caption ? 0.34 : 0;
  const availableH = SLIDE_H - CONTENT_TOP - 0.6 - captionH - captionGap;

  // Build pptxgenjs table rows. Header row first, styled distinctly.
  const headerCellStyle = {
    fill: { color: preset.accent_primary || '14B8A6' },
    color: 'FFFFFF',
    bold: true,
    fontFace: preset.font_title,
    fontSize: 13,
    align: 'left',
    valign: 'middle',
    margin: 0.05,
  };
  const bodyCellStyleA = {
    fill: { color: preset.surface || 'FFFFFF' },
    color: preset.text_primary || '0F172A',
    fontFace: preset.font_body,
    fontSize: 11,
    align: 'left',
    valign: 'middle',
    margin: 0.05,
  };
  const bodyCellStyleB = Object.assign({}, bodyCellStyleA, {
    fill: { color: preset.bg || 'F8FAFC' },
  });

  const tableRows = [
    headers.map((h) => ({ text: String(h || ''), options: headerCellStyle })),
  ];
  rows.forEach((row, idx) => {
    const style = idx % 2 === 0 ? bodyCellStyleA : bodyCellStyleB;
    const cells = [];
    for (let c = 0; c < headers.length; c++) {
      const v = Array.isArray(row) && row[c] !== undefined ? row[c] : '';
      cells.push({ text: String(v), options: style });
    }
    tableRows.push(cells);
  });

  // Column widths from column_weights, else equal.
  let colW;
  const weights = Array.isArray(slideData.column_weights)
    ? slideData.column_weights
    : null;
  const usableW = SLIDE_W - MARGIN_X * 2;
  if (weights && weights.length === headers.length) {
    const total = weights.reduce((a, b) => a + b, 0);
    colW = weights.map((w) => (usableW * w) / total);
  } else {
    colW = Array(headers.length).fill(usableW / headers.length);
  }

  const tableY = CONTENT_TOP + 0.2;
  const tableH = Math.min(availableH, 0.55 + tableRows.length * 0.42);
  slide.addTable(tableRows, {
    x: MARGIN_X,
    y: tableY,
    w: usableW,
    h: tableH,
    colW,
    fontSize: 11,
    rowH: 0.42,
  });

  if (caption) {
    // Caption sits immediately below the table, not at a fixed bottom
    // offset — that caused overlap when the table ran long.
    slide.addText(caption, textOpts({
      x: MARGIN_X,
      y: tableY + tableH + captionGap,
      w: usableW,
      h: captionH,
      fontFace: preset.font_caption,
      fontSize: 11,
      color: preset.text_muted,
      italic: true,
    }));
  }

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}


// ---------------------------------------------------------------------------
// comparison-2col — two-column A-vs-B layout with a dark verdict strip.
// Mirrors build_deck.py's _add_comparison_content composition.
// ---------------------------------------------------------------------------

function renderComparison2col(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle);

  const left = (slideData.left && typeof slideData.left === 'object') ? slideData.left : {};
  const right = (slideData.right && typeof slideData.right === 'object') ? slideData.right : {};
  const verdict = String(slideData.verdict || '').trim();

  const gutter = 0.35;
  const usableW = SLIDE_W - MARGIN_X * 2;
  const colW = (usableW - gutter) / 2;
  const hasVerdict = verdict.length > 0;
  const verdictH = hasVerdict ? 0.55 : 0;
  const verdictGap = hasVerdict ? 0.20 : 0;

  const colTop = CONTENT_TOP + 0.20;
  const colBottom = SLIDE_H - 0.65 - verdictH - verdictGap;
  const colH = Math.max(2.0, colBottom - colTop);

  const renderColumn = (spec, x, accentKey) => {
    const title = String(spec.title || '—').trim();
    let bodyLines;
    if (Array.isArray(spec.body)) {
      bodyLines = spec.body.map(String).filter((s) => s.trim());
    } else {
      bodyLines = String(spec.body || '')
        .split(/[.\n]/)
        .map((s) => s.trim())
        .filter((s) => s);
    }
    // Oversized colored title — the column's identity is the color + size,
    // not a thin accent rail (mirrors the python renderer's AI-tell fix).
    slide.addText(title, textOpts({
      x, y: colTop,
      w: colW, h: 0.72,
      fontFace: preset.font_title,
      fontSize: 24,
      bold: true,
      color: preset[accentKey] || preset.accent_primary,
    }));
    // Body bullets.
    const bodyY = colTop + 0.86;
    const bodyH = Math.max(0.8, colH - (bodyY - colTop) - 0.08);
    if (bodyLines.length) {
      slide.addText(
        bodyLines.map((line, i) => ({
          text: line,
          options: {
            bullet: { code: '2022' },
            breakLine: i < bodyLines.length - 1,
          },
        })),
        textOpts({
          x, y: bodyY, w: colW, h: bodyH,
          fontFace: preset.font_body,
          fontSize: 14,
          color: preset.text_primary,
          valign: 'top',
          paraSpaceAfter: 6,
        }),
      );
    }
  };

  renderColumn(left, MARGIN_X, 'accent_primary');
  renderColumn(right, MARGIN_X + colW + gutter, 'accent_secondary');

  // Vertical divider between the columns.
  const dividerX = MARGIN_X + colW + gutter / 2 - 0.02;
  slide.addShape('rect', shapeOpts({
    x: dividerX, y: colTop + 0.06,
    w: 0.04, h: colH - 0.12,
    fill: { color: preset.line || 'CBD5E1' },
    line: { color: preset.line || 'CBD5E1', width: 0 },
  }));

  if (hasVerdict) {
    const verdictY = colBottom + verdictGap;
    const verdictX = MARGIN_X + 0.5;
    const verdictW = usableW - 1.0;
    slide.addShape('rect', shapeOpts({
      x: verdictX, y: verdictY,
      w: verdictW, h: verdictH,
      fill: { color: preset.bg_dark || '0F172A' },
      line: { color: preset.bg_dark || '0F172A', width: 0 },
    }));
    // Left accent stripe inside the verdict strip.
    slide.addShape('rect', shapeOpts({
      x: verdictX, y: verdictY,
      w: 0.08, h: verdictH,
      fill: { color: preset.accent_primary || '14B8A6' },
      line: { color: preset.accent_primary || '14B8A6', width: 0 },
    }));
    slide.addText(verdict, textOpts({
      x: verdictX + 0.22, y: verdictY + 0.04,
      w: verdictW - 0.38, h: verdictH - 0.08,
      fontFace: preset.font_body,
      fontSize: 14,
      bold: true,
      color: 'FFFFFF',
      align: 'center',
      valign: 'middle',
    }));
  }

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}


// ---------------------------------------------------------------------------
// matrix — 2×2 quadrant grid. Mirrors _add_matrix_content.
// ---------------------------------------------------------------------------

function renderMatrix(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle);

  const quadrants = Array.isArray(slideData.quadrants) ? slideData.quadrants.slice(0, 4) : [];
  while (quadrants.length < 4) {
    quadrants.push({ title: `Quadrant ${quadrants.length + 1}`, body: '' });
  }

  const gutter = 0.30;
  const usableW = SLIDE_W - MARGIN_X * 2;
  const cardW = (usableW - gutter) / 2;
  const topY = CONTENT_TOP + 0.20;
  const usableH = SLIDE_H - topY - 0.65;
  const cardH = (usableH - gutter) / 2;
  const iconPaths = Array.isArray(slideData.__iconPaths) ? slideData.__iconPaths : [];

  quadrants.forEach((q, idx) => {
    const row = Math.floor(idx / 2);
    const col = idx % 2;
    const accentKey = idx % 2 === 0 ? 'accent_primary' : 'accent_secondary';
    const accentColor = preset[accentKey] || preset.accent_primary;
    const cx = MARGIN_X + col * (cardW + gutter);
    const cy = topY + row * (cardH + gutter);
    const railH = 0.08;

    // Card body
    slide.addShape('rect', shapeOpts({
      x: cx, y: cy,
      w: cardW, h: cardH,
      fill: { color: preset.surface || 'FFFFFF' },
      line: { color: preset.line || 'E5E7EB', width: 1 },
    }));
    // Top rail
    slide.addShape('rect', shapeOpts({
      x: cx, y: cy,
      w: cardW, h: railH,
      fill: { color: accentColor },
      line: { color: accentColor, width: 0 },
    }));

    // Optional icon in top-right corner of the quadrant.
    const iconPath = iconPaths[idx];
    const iconSize = 0.40;
    const hasIcon = iconPath && fs.existsSync(iconPath);
    if (hasIcon) {
      slide.addImage({
        path: iconPath,
        x: cx + cardW - iconSize - 0.20,
        y: cy + railH + 0.14,
        w: iconSize,
        h: iconSize,
      });
    }

    const title = String(q.title || '').trim() || `Quadrant ${idx + 1}`;
    const body = String(q.body || q.text || '').trim();

    slide.addText(title, textOpts({
      x: cx + 0.18, y: cy + railH + 0.10,
      w: cardW - 0.36, h: 0.44,
      fontFace: preset.font_title,
      fontSize: 18,
      bold: true,
      color: preset.text_primary,
    }));
    if (body) {
      const bodyLines = body.split(/\n|(?<=\.)\s+/)
        .map((s) => s.trim())
        .filter((s) => s)
        .slice(0, 4);
      slide.addText(
        bodyLines.map((line, i) => ({
          text: line,
          options: { breakLine: i < bodyLines.length - 1 },
        })),
        textOpts({
          x: cx + 0.18, y: cy + railH + 0.60,
          w: cardW - 0.36, h: cardH - railH - 0.78,
          fontFace: preset.font_body,
          fontSize: 12,
          color: preset.text_primary,
          valign: 'top',
          paraSpaceAfter: 4,
        }),
      );
    }
  });

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}


// ---------------------------------------------------------------------------
// Universal summary callout (the rounded "oval" box at the bottom).
// Called by the build_deck_pptxgenjs dispatcher for any variant that
// doesn't already carry its own bottom emphasis.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Flow: slide with title + subtitle on top, diagram image filling the body.
// Triggered when assets.mermaid_source or assets.diagram is present.
// The build script pre-renders .mmd to PNG before calling this.
// ---------------------------------------------------------------------------
function renderFlow(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle);

  const diagramPath = slideData.__mermaidPath || slideData.__diagramPath;
  if (!diagramPath || !fs.existsSync(diagramPath)) {
    // Fall back to standard text layout if the diagram is missing, so the
    // slide still renders something useful instead of a blank body.
    renderStandard(pptx, slide, slideData, preset);
    return;
  }

  // Body region: below header, leaving space for footer/callout.
  const bodyTop = CONTENT_TOP + 0.15;
  const hasFooter = !!(String(slideData.footer || '').trim());
  const hasCallout = !!(String(slideData.summary_callout || '').trim());
  const bottomReserve = (hasFooter ? 0.40 : 0.20) + (hasCallout ? 0.75 : 0.0);
  const bodyH = SLIDE_H - bodyTop - bottomReserve;
  const bodyW = SLIDE_W - MARGIN_X * 2;

  try {
    const sized = imageSizingContainLocal(diagramPath, MARGIN_X, bodyTop, bodyW, bodyH);
    slide.addImage(Object.assign({ path: diagramPath }, sized));
  } catch (e) {
    console.warn('[pptxgenjs] flow diagram embed failed:', e.message);
    renderStandard(pptx, slide, slideData, preset);
    return;
  }

  // Footer caption below diagram if provided.
  const footer = safeText(slideData.footer);
  if (footer) {
    slide.addText(footer, textOpts({
      x: MARGIN_X, y: SLIDE_H - 0.40,
      w: SLIDE_W - MARGIN_X * 2, h: 0.30,
      fontFace: preset.font_body, fontSize: 11,
      color: preset.text_muted, valign: 'middle',
    }));
  }
  attachNotes(slide, slideData);
}

function renderGeneratedImage(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle);

  const imagePath = slideData.__generatedImagePath || slideData.__heroPath;
  const contentY = CONTENT_TOP + 0.24;
  const contentH = SLIDE_H - contentY - 0.56;
  const panelW = 3.05;
  const gutter = 0.28;
  const imageX = MARGIN_X;
  const imageW = SLIDE_W - MARGIN_X * 2 - panelW - gutter;
  const panelX = imageX + imageW + gutter;

  slide.addShape('rect', shapeOpts({
    x: imageX, y: contentY, w: imageW, h: contentH,
    fill: { color: preset.surface || 'FFFFFF' },
    line: { color: preset.line, width: 0.75 },
  }));

  if (imagePath && fs.existsSync(imagePath)) {
    const sized = imageSizingContainLocal(imagePath, imageX + 0.08, contentY + 0.08, imageW - 0.16, contentH - 0.16);
    slide.addImage(Object.assign({ path: imagePath }, sized));
  } else {
    slide.addText('Generated image asset missing. Rebuild with --allow-generated-images or replace this slide.', textOpts({
      x: imageX + 0.35,
      y: contentY + contentH / 2 - 0.25,
      w: imageW - 0.70,
      h: 0.55,
      fontFace: preset.font_body,
      fontSize: 13,
      color: preset.text_muted,
      align: 'center',
      valign: 'middle',
    }));
  }

  slide.addShape('rect', shapeOpts({
    x: panelX, y: contentY, w: panelW, h: contentH,
    fill: { color: preset.bg_dark },
    line: { color: preset.bg_dark, width: 0 },
  }));

  const meta = generatedImageMeta(imagePath, slideData);
  slide.addText('GENERATED VISUAL', textOpts({
    x: panelX + 0.20,
    y: contentY + 0.22,
    w: panelW - 0.40,
    h: 0.28,
    fontFace: preset.font_heading,
    fontSize: 11,
    bold: true,
    color: preset.accent_primary,
  }));

  const details = [
    `Model: ${safeText(meta.model, 'OpenAI image model')}`,
    `Purpose: ${safeText(meta.purpose, 'Concept visual')}`,
    'Delete this slide if source-backed imagery is preferred.',
  ];
  const editNote = safeText(meta.edit_note);
  if (editNote) details.push(`Edit note: ${editNote}`);
  const prompt = safeText(meta.prompt) || safeText(meta.revised_prompt);
  if (prompt) details.push(`Prompt: ${truncate(prompt, 260)}`);

  slide.addText(details.map((line, i) => ({
    text: line,
    options: {
      fontFace: preset.font_body,
      fontSize: i === 0 ? 12 : 11,
      color: 'FFFFFF',
      breakLine: i < details.length - 1,
      paraSpaceAfter: 6,
    },
  })), textOpts({
    x: panelX + 0.20,
    y: contentY + 0.62,
    w: panelW - 0.40,
    h: contentH - 0.82,
    fontFace: preset.font_body,
    fontSize: 11,
    color: 'FFFFFF',
    valign: 'top',
  }));

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

function addSummaryCallout(pptx, slide, slideData, preset) {
  const text = String(slideData.summary_callout || '').trim();
  if (!text) return;
  const hasFooter = !!(String(slideData.footer || '').trim());
  const footerReserve = hasFooter ? 0.40 : 0.20;
  const calloutH = 0.62;
  const calloutY = SLIDE_H - footerReserve - calloutH;
  const calloutW = SLIDE_W - MARGIN_X * 2.2;
  const calloutX = MARGIN_X * 1.1;
  const accent = preset.accent_primary || '14B8A6';
  slide.addShape('roundRect', shapeOpts({
    x: calloutX, y: calloutY, w: calloutW, h: calloutH,
    fill: { color: accent },
    line: { color: accent, width: 0 },
    rectRadius: 0.22,
  }));
  slide.addText(text, textOpts({
    x: calloutX + 0.25, y: calloutY + 0.06,
    w: calloutW - 0.50, h: calloutH - 0.12,
    fontFace: preset.font_body,
    fontSize: 14,
    bold: true,
    color: 'FFFFFF',
    align: 'center',
    valign: 'middle',
  }));
}


// Exports
// ---------------------------------------------------------------------------

module.exports = {
  // Canvas constants, exposed so the builder can assert the same layout math.
  SLIDE_W,
  SLIDE_H,
  MARGIN_X,
  HEADER_TOP,
  TITLE_BAR_H,
  CONTENT_TOP,

  renderTitle,
  renderSection,
  renderStandard,
  renderCards,
  renderSplit,
  renderTimeline,
  renderStats,
  renderKpiHero,
  renderTable,
  renderComparison2col,
  renderMatrix,
  renderFlow,
  renderGeneratedImage,
  addSummaryCallout,
};
