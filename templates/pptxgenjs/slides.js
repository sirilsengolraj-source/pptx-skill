/*
 * Slide-family renderers for the pptxgenjs peer path.
 *
 * Canvas: LAYOUT_16x9 = 10.00" x 5.625".
 *   Side margins: 0.50"
 *   Title bar:    minimum 0.90" tall at y=0, full-bleed, dark fill
 *   Content rail: starts at the measured header bottom, not a fixed y
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

function cleanHex(value, fallback) {
  const raw = String(value || fallback || '').replace(/^#/, '').trim();
  return /^[0-9a-fA-F]{6}$/.test(raw) ? raw.toUpperCase() : String(fallback || '0F172A');
}

function darkSlideSubtitleColor(preset) {
  return cleanHex(
    preset.title_subtitle_color ||
      (preset.header_accent_stripe ? preset.accent_secondary : preset.accent_primary),
    'CBD5E1',
  );
}

function addTitleMotif(slide, preset, hasHero) {
  const motif = String(preset.title_motif || 'orbit').trim().toLowerCase();
  if (motif === 'none') return;
  const accent = cleanHex(preset.accent_primary, '14B8A6');
  const secondary = cleanHex(preset.accent_secondary, accent);
  const ink = cleanHex(preset.bg_dark, '0F172A');

  if (motif === 'network') {
    const pts = [
      [6.4, 1.2], [7.5, 0.85], [8.7, 1.45], [6.9, 2.45],
      [8.2, 2.65], [7.4, 3.55], [9.1, 3.8],
    ];
    for (let i = 0; i < pts.length - 1; i += 1) {
      slide.addShape('line', shapeOpts({
        x: pts[i][0], y: pts[i][1], w: pts[i + 1][0] - pts[i][0], h: pts[i + 1][1] - pts[i][1],
        line: { color: accent, transparency: 74, width: 1.2 },
      }));
    }
    pts.forEach(([x, y], idx) => {
      slide.addShape('ellipse', shapeOpts({
        x: x - 0.055, y: y - 0.055, w: 0.11, h: 0.11,
        fill: { color: idx % 2 ? secondary : accent, transparency: 18 },
        line: { color: 'FFFFFF', transparency: 85, width: 0.4 },
      }));
    });
    return;
  }

  if (motif === 'editorial') {
    slide.addShape('rect', shapeOpts({
      x: hasHero ? 5.35 : 7.15,
      y: 0,
      w: hasHero ? 0.18 : 1.85,
      h: SLIDE_H,
      fill: { color: accent, transparency: 78 },
      line: { color: accent, transparency: 100, width: 0 },
    }));
    slide.addShape('rect', shapeOpts({
      x: hasHero ? 5.62 : 7.55,
      y: 0.72,
      w: hasHero ? 3.35 : 1.2,
      h: 0.05,
      fill: { color: secondary, transparency: 18 },
    }));
    return;
  }

  // Default orbit motif: a few quiet rings make the cover feel authored
  // without depending on external imagery.
  const cx = hasHero ? 7.55 : 7.35;
  const cy = hasHero ? 2.70 : 2.35;
  [1.05, 1.55, 2.10].forEach((r, idx) => {
    slide.addShape('ellipse', shapeOpts({
      x: cx - r,
      y: cy - r,
      w: r * 2,
      h: r * 2,
      fill: { color: ink, transparency: 100 },
      line: { color: idx % 2 ? secondary : accent, transparency: 70, width: 1.0 },
    }));
  });
  slide.addShape('ellipse', shapeOpts({
    x: cx + 1.12,
    y: cy - 0.68,
    w: 0.16,
    h: 0.16,
    fill: { color: accent, transparency: 8 },
    line: { color: 'FFFFFF', transparency: 100, width: 0 },
  }));
}

function addSectionMotif(slide, preset) {
  const motif = String(preset.section_motif || 'rail-dots').trim().toLowerCase();
  if (motif === 'none') return;
  const accent = cleanHex(preset.accent_primary, '14B8A6');
  const secondary = cleanHex(preset.accent_secondary, accent);

  // The right-side wash intentionally fills dead space on divider slides so
  // section breaks read like designed pauses, not sparse placeholders.
  slide.addShape('rect', shapeOpts({
    x: SLIDE_W - 2.25,
    y: 0,
    w: 2.25,
    h: SLIDE_H,
    fill: { color: accent, transparency: 84 },
    line: { color: accent, transparency: 100, width: 0 },
  }));
  [0.72, 1.05, 1.42].forEach((r, idx) => {
    slide.addShape('ellipse', shapeOpts({
      x: SLIDE_W - 1.55 - r,
      y: 2.80 - r,
      w: r * 2,
      h: r * 2,
      fill: { color: accent, transparency: 100 },
      line: { color: idx % 2 ? secondary : 'FFFFFF', transparency: 72, width: 1.0 },
    }));
  });
  for (let i = 0; i < 5; i += 1) {
    slide.addShape('ellipse', shapeOpts({
      x: SLIDE_W - 0.82,
      y: 1.05 + i * 0.46,
      w: 0.10,
      h: 0.10,
      fill: { color: i % 2 ? secondary : accent, transparency: 12 },
      line: { color: 'FFFFFF', transparency: 100, width: 0 },
    }));
  }
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

function estimateTextLines(text, fontSize, boxW) {
  const value = safeText(text);
  if (!value) return 0;
  const avgCharW = Math.max(0.055, (fontSize / 72) * 0.56);
  const charsPerLine = Math.max(10, Math.floor(Math.max(0.2, boxW - 0.08) / avgCharW));
  return value.split(/\n+/).reduce((sum, paragraph) => {
    const len = paragraph.trim().length;
    return sum + Math.max(1, Math.ceil(len / charsPerLine));
  }, 0);
}

function estimateTextHeight(text, fontSize, boxW, lineHeight) {
  const lines = estimateTextLines(text, fontSize, boxW);
  if (!lines) return 0;
  return lines * (fontSize / 72) * (lineHeight || 1.18);
}

function titleFontForLength(title) {
  const len = safeText(title).length;
  if (len > 100) return 17;
  if (len > 82) return 17;
  if (len > 64) return 16;
  if (len > 52) return 18;
  if (len > 42) return 20;
  return 26;
}

function headerMetrics(title, subtitle, options) {
  const opts = options || {};
  const titleText = safeText(title, 'Untitled');
  const subtitleText = safeText(subtitle);
  const textW = opts.textW || (SLIDE_W - MARGIN_X * 2);
  const titleFont = opts.titleFont || titleFontForLength(titleText);
  const subtitleFont = opts.subtitleFont || 13;
  const titleH = Math.max(0.42, estimateTextHeight(titleText, titleFont, textW, 1.50));
  const subtitleH = subtitleText
    ? Math.max(0.32, estimateTextHeight(subtitleText, subtitleFont, textW, 1.30))
    : 0;
  const topPad = opts.topPad === undefined ? 0.10 : opts.topPad;
  const titleSubtitleGap = subtitleText ? 0.05 : 0;
  const bottomPad = opts.bottomPad === undefined ? 0.12 : opts.bottomPad;
  const barH = Math.max(
    TITLE_BAR_H,
    topPad + titleH + titleSubtitleGap + subtitleH + bottomPad,
  );
  const titleY = subtitleText ? topPad : Math.max(topPad, (barH - titleH) / 2);
  const subtitleY = topPad + titleH + titleSubtitleGap;
  return {
    barH,
    stripeY: barH,
    contentTop: barH + 0.04,
    textW,
    titleText,
    subtitleText,
    titleFont,
    subtitleFont,
    titleY,
    titleH,
    subtitleY,
    subtitleH,
  };
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

function addDarkTitleBar(slide, preset, title, subtitle, slideData = {}) {
  // Full-bleed dark bar at the top of every content slide. The bar height is
  // measured from the title/subtitle stack so folded titles reserve real space
  // before the body layout starts.
  const headerMode = String(slideData.header_mode || preset.header_mode || 'bar').trim().toLowerCase();
  const isLabHeader = headerMode === 'lab-clean' || headerMode === 'lab-card';
  const metrics = isLabHeader
    ? headerMetrics(title, subtitle, {
      titleFont: Math.min(21, titleFontForLength(title)),
      subtitleFont: 9.2,
      topPad: 0.20,
      bottomPad: 0.10,
    })
    : headerMetrics(title, subtitle);

  if (isLabHeader) {
    const titleColor = preset.text || preset.text_primary || '0F172A';
    const subtitleColor = preset.text_muted || '64748B';
    const accent = cleanHex(slideData.header_fill || preset.accent_primary, '0B2545');
    const lineColor = cleanHex(preset.line, 'D1D5DB');
    const titleW = metrics.textW;
    const titleH = metrics.titleH;
    const subtitleH = metrics.subtitleH;
    const titleY = 0.19;
    let contentTop = 0.80;

    if (headerMode === 'lab-card') {
      const estimatedTitleW = Math.max(
        2.40,
        Math.min(6.80, metrics.titleText.length * 0.115 + 0.70),
      );
      const cardH = Math.max(0.94, titleH + 0.30);
      slide.addShape('rect', shapeOpts({
        x: MARGIN_X,
        y: titleY,
        w: estimatedTitleW,
        h: cardH,
        fill: { color: accent },
        line: { color: accent, width: 0 },
      }));
      slide.addText(metrics.titleText, textOpts({
        x: MARGIN_X + 0.16,
        y: titleY + 0.08,
        w: estimatedTitleW - 0.32,
        h: cardH - 0.16,
        fontFace: preset.font_heading,
        fontSize: metrics.titleFont,
        bold: true,
        color: 'FFFFFF',
        fit: 'shrink',
      }));
      if (metrics.subtitleText) {
        slide.addText(metrics.subtitleText, textOpts({
          x: MARGIN_X,
          y: titleY + cardH + 0.08,
          w: titleW,
          h: subtitleH,
          fontFace: preset.font_body,
          fontSize: metrics.subtitleFont,
          color: subtitleColor,
          fit: 'shrink',
        }));
      }
      contentTop = titleY + cardH + (metrics.subtitleText ? subtitleH + 0.24 : 0.22);
    } else {
      slide.addText(metrics.titleText, textOpts({
        x: MARGIN_X,
        y: titleY,
        w: titleW,
        h: titleH,
        fontFace: preset.font_heading,
        fontSize: metrics.titleFont,
        bold: true,
        color: titleColor,
        fit: 'shrink',
      }));
      if (metrics.subtitleText) {
        slide.addText(metrics.subtitleText, textOpts({
          x: MARGIN_X,
          y: titleY + titleH + 0.04,
          w: titleW,
          h: subtitleH,
          fontFace: preset.font_body,
          fontSize: metrics.subtitleFont,
          color: subtitleColor,
          fit: 'shrink',
        }));
      }
      contentTop = titleY + titleH + (metrics.subtitleText ? subtitleH + 0.20 : 0.16);
    }

    const ruleY = Math.max(0.62, contentTop - 0.10);
    slide.addShape('rect', shapeOpts({
      x: MARGIN_X,
      y: ruleY,
      w: SLIDE_W - MARGIN_X * 2,
      h: 0.018,
      fill: { color: lineColor },
      line: { color: lineColor, width: 0 },
    }));
    if (headerMode === 'lab-clean') {
      slide.addShape('rect', shapeOpts({
        x: MARGIN_X,
        y: ruleY - 0.035,
        w: 0.85,
        h: 0.035,
        fill: { color: accent },
        line: { color: accent, width: 0 },
      }));
    }
    return Object.assign({}, metrics, {
      barH: ruleY + 0.02,
      stripeY: ruleY,
      contentTop: Math.max(contentTop, ruleY + 0.14),
      titleY,
    });
  }

  if (headerMode === 'stack' || headerMode === 'eyebrow') {
    const titleColor = preset.text || preset.text_primary || '0F172A';
    const subtitleColor = preset.text_muted || '64748B';
    const stripeW = headerMode === 'eyebrow' ? 0.85 : 1.25;
    slide.addShape('rect', shapeOpts({
      x: MARGIN_X,
      y: metrics.contentTop - 0.10,
      w: stripeW,
      h: 0.05,
      fill: { color: preset.accent_primary },
      line: { color: preset.accent_primary, width: 0 },
    }));
    slide.addText(metrics.titleText, textOpts({
      x: MARGIN_X,
      y: metrics.titleY,
      w: metrics.textW,
      h: metrics.titleH,
      fontFace: preset.font_heading,
      fontSize: metrics.titleFont,
      bold: true,
      color: titleColor,
    }));
    if (metrics.subtitleText) {
      slide.addText(metrics.subtitleText, textOpts({
        x: MARGIN_X,
        y: metrics.subtitleY,
        w: metrics.textW,
        h: metrics.subtitleH,
        fontFace: preset.font_body,
        fontSize: metrics.subtitleFont,
        color: subtitleColor,
      }));
    }
    return metrics;
  }

  slide.addShape('rect', shapeOpts({
    x: 0, y: 0, w: SLIDE_W, h: metrics.barH,
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
    x: 0, y: metrics.stripeY, w: SLIDE_W, h: 0.04,
    fill: { color: stripeColor },
  }));

  slide.addText(metrics.titleText, textOpts({
    x: MARGIN_X,
    y: metrics.titleY,
    w: metrics.textW,
    h: metrics.titleH,
    fontFace: preset.font_heading,
    fontSize: metrics.titleFont,
    bold: true,
    color: 'FFFFFF',
    valign: 'top',
  }));

  if (metrics.subtitleText) {
    slide.addText(metrics.subtitleText, textOpts({
      x: MARGIN_X,
      y: metrics.subtitleY,
      w: metrics.textW,
      h: metrics.subtitleH,
      fontFace: preset.font_body,
      fontSize: metrics.subtitleFont,
      color: preset.accent_primary,
      bold: false,
    }));
  }
  return metrics;
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
  const footerMode = String(slideData.footer_mode || preset.footer_mode || '').trim().toLowerCase();
  const pageNumber = slideData.__slideIndex && slideData.__slideCount
    ? `${slideData.__slideIndex}/${slideData.__slideCount}`
    : '';
  const showPageNumber = slideData.show_page_number === false
    ? false
    : Boolean(slideData.page_number || preset.footer_page_numbers || footerMode === 'source-line');
  if (!footer && sources.length === 0 && !showPageNumber) return;

  const y = SLIDE_H - FOOTER_H;
  // Thin accent line above footer.
  slide.addShape('rect', shapeOpts({
    x: MARGIN_X, y: y - 0.04, w: SLIDE_W - MARGIN_X * 2, h: 0.02,
    fill: { color: preset.line },
  }));

  if (footerMode === 'source-line') {
    const leftParts = [];
    if (footer) leftParts.push(footer);
    if (sources.length) leftParts.push('Sources: ' + sources.join('; '));
    const leftText = leftParts.join(' · ');
    const pageW = showPageNumber && pageNumber ? 0.55 : 0;
    const textW = SLIDE_W - MARGIN_X * 2 - pageW - (pageW ? 0.16 : 0);
    const fontSize = leftText.length > 170 ? 6.7 : leftText.length > 115 ? 7.5 : 8.4;
    if (leftText) {
      slide.addText(leftText, textOpts({
        x: MARGIN_X,
        y: y + 0.02,
        w: textW,
        h: FOOTER_H - 0.02,
        fontFace: preset.font_body,
        fontSize,
        color: preset.text_muted,
        valign: 'middle',
        fit: 'shrink',
      }));
    }
    if (showPageNumber && pageNumber) {
      slide.addText(pageNumber, textOpts({
        x: SLIDE_W - MARGIN_X - pageW,
        y: y + 0.02,
        w: pageW,
        h: FOOTER_H - 0.02,
        fontFace: preset.font_body,
        fontSize: 8.4,
        color: preset.text_muted,
        align: 'right',
        valign: 'middle',
      }));
    }
    return;
  }

  if (footer) {
    const totalW = SLIDE_W - MARGIN_X * 2;
    const hasSources = sources.length > 0;
    const footerFont = hasSources
      ? (footer.length > 75 ? 7.2 : footer.length > 55 ? 8.0 : 9.0)
      : (footer.length > 105 ? 8.0 : footer.length > 75 ? 9.0 : 10);
    slide.addText(footer, textOpts({
      x: MARGIN_X,
      y: y,
      w: hasSources ? totalW * 0.48 : totalW * 0.55,
      h: FOOTER_H,
      fontFace: preset.font_body,
      fontSize: footerFont,
      color: preset.text_muted,
      valign: 'middle',
      fit: 'shrink',
    }));
  }
  if (sources.length) {
    const sourceText = 'Sources: ' + sources.join('; ');
    const totalW = SLIDE_W - MARGIN_X * 2;
    const sourceOnly = !footer;
    const sourceX = sourceOnly ? MARGIN_X : MARGIN_X + totalW * 0.52;
    const sourceW = sourceOnly ? totalW : totalW * 0.48;
    const sourceFont = sourceText.length > 170 ? 7.2 : sourceText.length > 115 ? 8.0 : 9.0;
    slide.addText(sourceText, textOpts({
      x: sourceX,
      y: y,
      w: sourceW,
      h: FOOTER_H,
      fontFace: preset.font_body,
      fontSize: sourceFont,
      color: preset.text_muted,
      italic: true,
      align: sourceOnly ? 'left' : 'right',
      valign: 'middle',
      fit: 'shrink',
    }));
  }
  if (showPageNumber && pageNumber) {
    slide.addText(pageNumber, textOpts({
      x: SLIDE_W - MARGIN_X - 0.50,
      y,
      w: 0.50,
      h: FOOTER_H,
      fontFace: preset.font_body,
      fontSize: 9,
      color: preset.text_muted,
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

function addTitleFooter(slide, preset, slideData, colorOverride) {
  const footer = safeText(slideData.footer);
  if (!footer) return;
  slide.addText(footer, textOpts({
    x: MARGIN_X,
    y: SLIDE_H - 0.40,
    w: SLIDE_W - MARGIN_X * 2,
    h: 0.25,
    fontFace: preset.font_body,
    fontSize: 10,
    color: colorOverride || preset.text_muted,
    valign: 'middle',
  }));
}

function addTitleKicker(slide, preset, text, box) {
  const label = safeText(text, 'PRESENTATION');
  slide.addText(label.toUpperCase(), textOpts({
    x: box.x,
    y: box.y,
    w: box.w,
    h: box.h,
    fontFace: preset.font_heading,
    fontSize: box.fontSize || 9,
    bold: true,
    color: box.color || preset.accent_primary,
    charSpacing: box.charSpacing === undefined ? 1.8 : box.charSpacing,
  }));
}

function addHeroFrame(slide, heroPath, preset, box, options) {
  if (!heroPath || !fs.existsSync(heroPath)) return false;
  const opts = options || {};
  const pad = opts.pad === undefined ? 0.08 : opts.pad;
  if (opts.surface !== false) {
    slide.addShape('rect', shapeOpts({
      x: box.x,
      y: box.y,
      w: box.w,
      h: box.h,
      fill: { color: opts.fill || preset.surface || 'FFFFFF', transparency: opts.fillTransparency || 0 },
      line: { color: opts.line || preset.line || 'CBD5E1', width: opts.lineWidth || 0.75 },
    }));
  }
  try {
    const sized = imageSizingContainLocal(
      heroPath,
      box.x + pad,
      box.y + pad,
      box.w - pad * 2,
      box.h - pad * 2,
    );
    slide.addImage(Object.assign({ path: heroPath }, sized));
    return true;
  } catch (e) {
    console.warn('[pptxgenjs] hero_image failed:', e.message);
    return false;
  }
}

function titleTextSizing(titleText, boxW, baseFont, minFont) {
  const titleFont = Math.max(minFont || 27, Math.min(baseFont, Math.floor(baseFont - Math.max(0, titleText.length - 32) * 0.32)));
  // Cover titles use display fonts and tend to wrap taller than body-text
  // estimates, especially with serif pairs. Over-reserve slightly so a
  // folded title cannot collide with subtitle or hero metadata.
  const titleH = Math.min(2.28, Math.max(0.96, estimateTextHeight(titleText, titleFont, boxW, 1.32) + 0.22));
  return { titleFont, titleH };
}

function renderTitleSplit(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg_dark);
  addBackgroundImage(slide, slideData.background_image, preset);

  // When a hero image is staged, place it on the right half and narrow the
  // text column to the left half. Otherwise use the standard full-width layout.
  const heroPath = slideData.__heroPath;
  const hasHero = heroPath && fs.existsSync(heroPath);
  const textRight = hasHero ? 5.3 : SLIDE_W - MARGIN_X;
  const textW = textRight - MARGIN_X;

  addTitleMotif(slide, preset, hasHero);

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

  const titleText = safeText(slideData.title, 'Untitled Deck');
  const titleFont = hasHero
    ? (titleText.length > 30 ? 32 : 36)
    : (titleText.length > 28 ? 40 : 44);
  const titleH = hasHero
    ? (titleText.length > 30 ? 1.72 : 1.35)
    : (titleText.length > 24 ? 1.85 : 1.45);
  const titleY = 2.00;

  slide.addText(titleText, textOpts({
    x: MARGIN_X,
    y: titleY,
    w: textW,
    h: titleH,
    fontFace: preset.font_heading,
    fontSize: titleFont,
    bold: true,
    color: 'FFFFFF',
    valign: 'top',
  }));

  const subtitle = safeText(slideData.subtitle);
  if (subtitle) {
    slide.addText(subtitle, textOpts({
      x: MARGIN_X,
      y: titleY + titleH + 0.10,
      w: textW,
      h: subtitle.length > 70 ? 1.12 : 0.9,
      fontFace: preset.font_body,
      fontSize: hasHero ? 13 : 20,
      color: darkSlideSubtitleColor(preset),
      valign: 'top',
    }));
  }

  addTitleFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

function renderTitleLabPlate(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg || 'FFFFFF');
  const heroPath = slideData.__heroPath;
  const hasHero = heroPath && fs.existsSync(heroPath);
  const titleText = safeText(slideData.title, 'Untitled Deck');
  const subtitle = safeText(slideData.subtitle);
  const dark = cleanHex(preset.bg_dark, '0B2545');
  const red = cleanHex(preset.accent_secondary, 'C9302C');

  slide.addShape('rect', shapeOpts({
    x: 0, y: 0, w: SLIDE_W, h: 0.72,
    fill: { color: dark },
    line: { color: dark, width: 0 },
  }));
  slide.addShape('rect', shapeOpts({
    x: 0, y: 0.72, w: SLIDE_W, h: 0.06,
    fill: { color: red },
    line: { color: red, width: 0 },
  }));
  addTitleKicker(slide, preset, slideData.kicker || 'LAB PRESENTATION', {
    x: MARGIN_X,
    y: 0.28,
    w: 3.0,
    h: 0.20,
    color: 'FFFFFF',
    fontSize: 8.5,
  });

  const textW = hasHero ? 5.05 : SLIDE_W - MARGIN_X * 2;
  const sizing = titleTextSizing(titleText, textW, hasHero ? 32 : 36, 25);
  slide.addShape('rect', shapeOpts({
    x: MARGIN_X,
    y: 1.22,
    w: 0.10,
    h: Math.max(1.35, sizing.titleH + (subtitle ? 0.75 : 0.15)),
    fill: { color: red },
    line: { color: red, width: 0 },
  }));
  slide.addText(titleText, textOpts({
    x: MARGIN_X + 0.25,
    y: 1.16,
    w: textW - 0.25,
    h: sizing.titleH,
    fontFace: preset.font_heading,
    fontSize: sizing.titleFont,
    bold: true,
    color: dark,
    fit: 'shrink',
  }));
  if (subtitle) {
    slide.addText(subtitle, textOpts({
      x: MARGIN_X + 0.25,
      y: 1.16 + sizing.titleH + 0.18,
      w: textW - 0.25,
      h: 0.82,
      fontFace: preset.font_body,
      fontSize: hasHero ? 12.5 : 15,
      color: preset.text_muted,
      fit: 'shrink',
    }));
  }

  if (hasHero) {
    addHeroFrame(slide, heroPath, preset, { x: 6.25, y: 1.10, w: 3.05, h: 3.10 }, {
      pad: 0.07,
      line: preset.line,
    });
  }

  const labelY = 4.58;
  const micro = ['Evidence', 'Readout', 'Next run'];
  micro.forEach((label, idx) => {
    const x = MARGIN_X + idx * 2.15;
    slide.addShape('rect', shapeOpts({
      x,
      y: labelY,
      w: 1.82,
      h: 0.34,
      fill: { color: idx === 0 ? dark : 'F8FAFC' },
      line: { color: idx === 0 ? dark : preset.line, width: 0.75 },
    }));
    slide.addText(label.toUpperCase(), textOpts({
      x: x + 0.10,
      y: labelY + 0.06,
      w: 1.62,
      h: 0.22,
      fontFace: preset.font_heading,
      fontSize: 7.5,
      bold: true,
      color: idx === 0 ? 'FFFFFF' : dark,
      charSpacing: 1.2,
    }));
  });

  addTitleFooter(slide, preset, slideData, preset.text_muted);
  attachNotes(slide, slideData);
}

function renderTitleCommandCenter(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg_dark);
  addBackgroundImage(slide, slideData.background_image, preset);
  const heroPath = slideData.__heroPath;
  const hasHero = heroPath && fs.existsSync(heroPath);
  const accent = cleanHex(preset.accent_secondary || preset.accent_primary, 'DC2626');
  const titleText = safeText(slideData.title, 'Untitled Deck');
  const subtitle = safeText(slideData.subtitle);
  const textW = hasHero ? 5.55 : SLIDE_W - 1.30;

  addTitleMotif(slide, Object.assign({}, preset, { title_motif: preset.title_motif || 'network' }), hasHero);
  slide.addShape('rect', shapeOpts({
    x: MARGIN_X,
    y: 0.62,
    w: SLIDE_W - MARGIN_X * 2,
    h: 0.02,
    fill: { color: 'FFFFFF', transparency: 76 },
  }));
  addTitleKicker(slide, preset, slideData.kicker || 'BOARD BRIEF', {
    x: MARGIN_X,
    y: 0.34,
    w: 2.6,
    h: 0.18,
    color: accent,
    fontSize: 8.2,
  });

  if (hasHero) {
    addHeroFrame(slide, heroPath, preset, { x: 6.45, y: 1.05, w: 3.0, h: 3.30 }, {
      pad: 0.05,
      fill: preset.bg_dark,
      fillTransparency: 15,
      line: accent,
      lineWidth: 1.0,
    });
  }

  const sizing = titleTextSizing(titleText, textW, 36, 27);
  slide.addText(titleText, textOpts({
    x: MARGIN_X,
    y: 1.12,
    w: textW,
    h: sizing.titleH,
    fontFace: preset.font_heading,
    fontSize: sizing.titleFont,
    bold: true,
    color: 'FFFFFF',
    fit: 'shrink',
  }));
  if (subtitle) {
    slide.addText(subtitle, textOpts({
      x: MARGIN_X,
      y: 1.12 + sizing.titleH + 0.18,
      w: textW,
      h: 0.86,
      fontFace: preset.font_body,
      fontSize: 13,
      color: darkSlideSubtitleColor(preset),
      fit: 'shrink',
    }));
  }

  const stripY = 4.55;
  const stripW = (SLIDE_W - MARGIN_X * 2 - 0.16 * 2) / 3;
  ['Risk', 'Control', 'Action'].forEach((label, idx) => {
    const x = MARGIN_X + idx * (stripW + 0.16);
    slide.addShape('rect', shapeOpts({
      x, y: stripY, w: stripW, h: 0.34,
      fill: { color: idx === 0 ? accent : 'FFFFFF', transparency: idx === 0 ? 8 : 88 },
      line: { color: idx === 0 ? accent : 'FFFFFF', transparency: idx === 0 ? 0 : 82, width: 0.6 },
    }));
    slide.addText(label.toUpperCase(), textOpts({
      x: x + 0.10,
      y: stripY + 0.09,
      w: stripW - 0.20,
      h: 0.16,
      fontFace: preset.font_heading,
      fontSize: 7.8,
      bold: true,
      color: 'FFFFFF',
      charSpacing: 1.3,
      align: 'center',
    }));
  });

  addTitleFooter(slide, preset, slideData, '94A3B8');
  attachNotes(slide, slideData);
}

function renderTitlePoster(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg_dark);
  const heroPath = slideData.__heroPath;
  const hasHero = heroPath && fs.existsSync(heroPath);
  const titleText = safeText(slideData.title, 'Untitled Deck');
  const subtitle = safeText(slideData.subtitle);
  const accent = cleanHex(preset.accent_primary, 'FF6B35');
  const secondary = cleanHex(preset.accent_secondary, '22C55E');

  slide.addShape('ellipse', shapeOpts({
    x: -1.1, y: -1.0, w: 3.6, h: 3.6,
    fill: { color: accent, transparency: 78 },
    line: { color: accent, transparency: 100, width: 0 },
  }));
  slide.addShape('rect', shapeOpts({
    x: 0, y: 4.48, w: SLIDE_W, h: 0.56,
    fill: { color: secondary, transparency: 18 },
    line: { color: secondary, transparency: 100, width: 0 },
  }));

  if (hasHero) {
    try {
      slide.addImage({
        path: heroPath,
        x: 5.15,
        y: 0.0,
        w: SLIDE_W - 5.15,
        h: SLIDE_H,
        sizing: { type: 'cover', w: SLIDE_W - 5.15, h: SLIDE_H },
        transparency: 8,
      });
      slide.addShape('rect', shapeOpts({
        x: 4.65, y: 0, w: 5.35, h: SLIDE_H,
        fill: { color: preset.bg_dark, transparency: 42 },
        line: { color: preset.bg_dark, transparency: 100, width: 0 },
      }));
    } catch (e) {
      console.warn('[pptxgenjs] hero_image failed:', e.message);
    }
  }

  addTitleKicker(slide, preset, slideData.kicker || 'LAUNCH STORY', {
    x: MARGIN_X,
    y: 0.72,
    w: 2.8,
    h: 0.20,
    color: accent,
    fontSize: 8.8,
  });
  slide.addShape('rect', shapeOpts({
    x: MARGIN_X,
    y: 1.02,
    w: 0.72,
    h: 0.08,
    fill: { color: accent },
    line: { color: accent, width: 0 },
  }));

  const textW = hasHero ? 4.65 : 8.6;
  const x = hasHero ? MARGIN_X : 0.70;
  const align = hasHero ? 'left' : 'center';
  const sizing = titleTextSizing(titleText, textW, hasHero ? 39 : 46, 30);
  slide.addText(titleText, textOpts({
    x,
    y: hasHero ? 1.34 : 1.55,
    w: textW,
    h: sizing.titleH,
    fontFace: preset.font_heading,
    fontSize: sizing.titleFont,
    bold: true,
    color: 'FFFFFF',
    align,
    fit: 'shrink',
  }));
  if (subtitle) {
    slide.addText(subtitle, textOpts({
      x,
      y: (hasHero ? 1.34 : 1.55) + sizing.titleH + 0.18,
      w: textW,
      h: 0.85,
      fontFace: preset.font_body,
      fontSize: hasHero ? 13.5 : 16,
      color: darkSlideSubtitleColor(preset),
      align,
      fit: 'shrink',
    }));
  }

  addTitleFooter(slide, preset, slideData, 'CBD5E1');
  attachNotes(slide, slideData);
}

function renderTitleMasthead(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg || 'FAF6EC');
  const heroPath = slideData.__heroPath;
  const hasHero = heroPath && fs.existsSync(heroPath);
  const titleText = safeText(slideData.title, 'Untitled Deck');
  const subtitle = safeText(slideData.subtitle);
  const textColor = cleanHex(preset.text || preset.text_primary, '2A2118');
  const muted = cleanHex(preset.text_muted, '6B5B42');
  const accent = cleanHex(preset.accent_primary, '8B4513');
  const secondary = cleanHex(preset.accent_secondary, accent);

  slide.addShape('rect', shapeOpts({
    x: MARGIN_X,
    y: 0.55,
    w: SLIDE_W - MARGIN_X * 2,
    h: 0.02,
    fill: { color: accent },
    line: { color: accent, width: 0 },
  }));
  slide.addShape('rect', shapeOpts({
    x: MARGIN_X,
    y: 0.66,
    w: SLIDE_W - MARGIN_X * 2,
    h: 0.01,
    fill: { color: preset.line || 'D9CBA8' },
    line: { color: preset.line || 'D9CBA8', width: 0 },
  }));
  addTitleKicker(slide, preset, slideData.kicker || 'EDITORIAL REPORT', {
    x: MARGIN_X,
    y: 0.28,
    w: 3.2,
    h: 0.18,
    color: accent,
    fontSize: 8.2,
  });

  const textW = hasHero ? 5.05 : 8.65;
  const sizing = titleTextSizing(titleText, textW, hasHero ? 31 : 41, 24);
  if (hasHero) {
    sizing.titleH = Math.max(sizing.titleH, 1.82);
  }
  slide.addText(titleText, textOpts({
    x: MARGIN_X,
    y: 1.18,
    w: textW,
    h: sizing.titleH,
    fontFace: preset.font_heading,
    fontSize: sizing.titleFont,
    bold: true,
    color: textColor,
    fit: 'shrink',
  }));
  if (subtitle) {
    slide.addText(subtitle, textOpts({
      x: MARGIN_X,
      y: 1.18 + sizing.titleH + 0.18,
      w: textW,
      h: 0.82,
      fontFace: preset.font_body,
      fontSize: 13.5,
      color: muted,
      fit: 'shrink',
    }));
  }

  if (hasHero) {
    slide.addShape('rect', shapeOpts({
      x: 5.92,
      y: 1.00,
      w: 0.02,
      h: 3.72,
      fill: { color: preset.line || 'D9CBA8' },
      line: { color: preset.line || 'D9CBA8', width: 0 },
    }));
    addHeroFrame(slide, heroPath, preset, { x: 6.25, y: 1.00, w: 3.05, h: 3.72 }, {
      pad: 0.06,
      fill: 'FFFFFF',
      line: preset.line,
    });
  } else {
    slide.addShape('rect', shapeOpts({
      x: 6.75,
      y: 1.15,
      w: 1.70,
      h: 3.25,
      fill: { color: secondary, transparency: 84 },
      line: { color: secondary, transparency: 100, width: 0 },
    }));
  }

  slide.addShape('rect', shapeOpts({
    x: MARGIN_X,
    y: 4.62,
    w: 1.35,
    h: 0.06,
    fill: { color: secondary },
    line: { color: secondary, width: 0 },
  }));
  addTitleFooter(slide, preset, slideData, muted);
  attachNotes(slide, slideData);
}

function renderTitleLightAtlas(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg || 'F8FAFC');
  const heroPath = slideData.__heroPath;
  const hasHero = heroPath && fs.existsSync(heroPath);
  const titleText = safeText(slideData.title, 'Untitled Deck');
  const subtitle = safeText(slideData.subtitle);
  const accent = cleanHex(preset.accent_primary, '0EA5E9');
  const textColor = cleanHex(preset.text || preset.text_primary, '0F172A');
  const muted = cleanHex(preset.text_muted, '64748B');

  for (let i = 0; i < 7; i += 1) {
    slide.addShape('line', shapeOpts({
      x: 6.05 + i * 0.42,
      y: 0.52,
      w: 0,
      h: 4.38,
      line: { color: preset.line || 'E2E8F0', transparency: 12, width: 0.5 },
    }));
  }
  [0.42, 0.76, 1.12].forEach((r, idx) => {
    slide.addShape('ellipse', shapeOpts({
      x: 7.65 - r,
      y: 2.70 - r,
      w: r * 2,
      h: r * 2,
      fill: { color: accent, transparency: 100 },
      line: { color: idx % 2 ? preset.accent_secondary : accent, transparency: 68, width: 0.9 },
    }));
  });

  addTitleKicker(slide, preset, slideData.kicker || 'POLICY BRIEF', {
    x: MARGIN_X,
    y: 0.72,
    w: 2.6,
    h: 0.18,
    color: accent,
    fontSize: 8.4,
  });
  const textW = hasHero ? 5.30 : 7.4;
  const sizing = titleTextSizing(titleText, textW, hasHero ? 38 : 42, 29);
  slide.addText(titleText, textOpts({
    x: MARGIN_X,
    y: 1.10,
    w: textW,
    h: sizing.titleH,
    fontFace: preset.font_heading,
    fontSize: sizing.titleFont,
    bold: true,
    color: textColor,
    fit: 'shrink',
  }));
  slide.addShape('rect', shapeOpts({
    x: MARGIN_X,
    y: 1.10 + sizing.titleH + 0.10,
    w: 0.95,
    h: 0.06,
    fill: { color: accent },
    line: { color: accent, width: 0 },
  }));
  if (subtitle) {
    slide.addText(subtitle, textOpts({
      x: MARGIN_X,
      y: 1.10 + sizing.titleH + 0.30,
      w: textW,
      h: 0.86,
      fontFace: preset.font_body,
      fontSize: 14,
      color: muted,
      fit: 'shrink',
    }));
  }

  if (hasHero) {
    addHeroFrame(slide, heroPath, preset, { x: 6.28, y: 1.00, w: 3.10, h: 3.65 }, {
      pad: 0.07,
      line: preset.line,
    });
  }
  addTitleFooter(slide, preset, slideData, muted);
  attachNotes(slide, slideData);
}

function renderTitle(pptx, slide, slideData, preset) {
  const layout = String(slideData.title_layout || preset.title_layout || 'split-hero')
    .trim()
    .toLowerCase();
  if (layout === 'lab-plate') {
    renderTitleLabPlate(pptx, slide, slideData, preset);
  } else if (layout === 'command-center') {
    renderTitleCommandCenter(pptx, slide, slideData, preset);
  } else if (layout === 'poster') {
    renderTitlePoster(pptx, slide, slideData, preset);
  } else if (layout === 'masthead') {
    renderTitleMasthead(pptx, slide, slideData, preset);
  } else if (layout === 'light-atlas') {
    renderTitleLightAtlas(pptx, slide, slideData, preset);
  } else {
    renderTitleSplit(pptx, slide, slideData, preset);
  }
}

// ---------------------------------------------------------------------------
// Section divider: full-bleed dark slide, oversized title, optional subtitle.
// ---------------------------------------------------------------------------

function renderSection(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg_dark);
  addBackgroundImage(slide, slideData.background_image, preset);
  addSectionMotif(slide, preset);

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
    const subtitleH = Math.min(
      1.20,
      Math.max(0.45, estimateTextHeight(subtitle, 16, SLIDE_W - MARGIN_X * 2, 1.22) + 0.18),
    );
    slide.addText(subtitle, textOpts({
      x: MARGIN_X,
      y: 2.80,
      w: SLIDE_W - MARGIN_X * 2,
      h: subtitleH,
      fontFace: preset.font_body,
      fontSize: 16,
      color: cleanHex(preset.section_subtitle_color, 'E5E7EB'),
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
  const header = addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle, slideData);

  let bullets = normalizeBullets(slideData.bullets);
  const highlights = Array.isArray(slideData.highlights)
    ? slideData.highlights.map((h) => safeText(h)).filter(Boolean)
    : [];

  // Compatibility fallback: old outlines sometimes omitted `variant: matrix`
  // but still supplied quadrants. Preserve that content as bullets instead of
  // rendering an empty slide.
  if (bullets.length === 0
      && !safeText(slideData.body)
      && !(Array.isArray(slideData.paragraphs) && slideData.paragraphs.length)
      && Array.isArray(slideData.quadrants) && slideData.quadrants.length) {
    console.warn(
      '[pptxgenjs] quadrants supplied without variant: matrix; ' +
      'synthesizing bullets so content is preserved.',
    );
    bullets = slideData.quadrants.slice(0, 4).map((q) => {
      const title = safeText(q && q.title);
      const body = safeText(q && q.body);
      const text = title && body ? `${title}: ${body}` : (title || body);
      return text;
    }).filter(Boolean).map((t) => ({ text: t, level: 0 }));
  }

  const contentY = header.contentTop + 0.25;
  const hasBottomSummary = !!safeText(slideData.summary_callout || slideData.key_summary || slideData.takeaway);
  const summaryReserve = hasBottomSummary ? 0.66 : 0;
  const contentH = SLIDE_H - contentY - 0.55 - summaryReserve;

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
    const bulletText = bullets.map((b) => b.text).join('\n');
    const bulletH = Math.min(
      Math.max(0.5, contentH - (currentY - contentY)),
      Math.max(0.95, estimateTextHeight(bulletText, 16, leftW, 1.24) + 0.32),
    );
    slide.addText(bulletTextArray(bullets, preset), textOpts({
      x: MARGIN_X,
      y: currentY,
      w: leftW,
      h: bulletH,
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
          breakLine: i < paragraphs.length - 1,
        },
      }));
      const paragraphText = paragraphs.join('\n');
      const paragraphH = Math.min(
        contentH,
        Math.max(0.75, estimateTextHeight(paragraphText, 16, leftW, 1.24) + 0.25),
      );
      slide.addText(items, textOpts({
        x: MARGIN_X,
        y: contentY,
        w: leftW,
        h: paragraphH,
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
      y: contentY + 0.56,
      w: cardW - 0.4,
      h: contentH - 0.71,
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
  const header = addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle, slideData);

  const rawCards = Array.isArray(slideData.cards) ? slideData.cards : [];
  const cols = columns === 2 ? 2 : 3;
  const cards = rawCards.slice(0, cols);
  while (cards.length < cols) {
    cards.push({ title: '', body: '', accent: 'accent_primary' });
  }

  const gutter = 0.24;
  const usableW = SLIDE_W - MARGIN_X * 2;
  const avgBodyLen = cards.reduce((sum, card) => sum + safeText(card.body || card.text).length, 0) /
    Math.max(1, cards.length);
  const compactCardRow = cols === 2 && avgBodyLen > 0 && avgBodyLen < 170;
  const cardY = header.contentTop + (compactCardRow ? 0.78 : 0.35);
  const maxCardH = SLIDE_H - cardY - 0.65;
  const cardH = compactCardRow ? Math.min(maxCardH, 2.30) : maxCardH;

  // cards_mode gives presets an anti-sameness lever without creating more
  // variants. feature-left promotes the first/selected card; staggered-row
  // keeps equal width but varies the vertical silhouette.
  const cardsMode = String(slideData.cards_mode || preset.cards_mode || '').trim().toLowerCase();
  const explicitPromote = Number.isInteger(slideData.promote_card) ? slideData.promote_card : null;
  const promote = explicitPromote !== null
    ? explicitPromote
    : (cols === 3 && cardsMode === 'feature-left' ? 0 : null);
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
  } else if (cols === 3 && cardsMode === 'staggered-row') {
    const cardW = (usableW - gutter * (cols - 1)) / cols;
    const offsets = [0.00, 0.18, 0.36];
    placements = cards.map((_, idx) => ({
      x: MARGIN_X + idx * (cardW + gutter),
      y: cardY + offsets[idx],
      w: cardW,
      h: Math.max(1.4, cardH - offsets[idx]),
      big: false,
    }));
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
    const padX = 0.25;

    // Card surface. Use a square body so the top accent rail sits flush.
    slide.addShape('rect', shapeOpts({
      x: cx, y: cy, w: cw, h: ch,
      fill: { color: preset.surface || 'FFFFFF' },
      line: { color: preset.line, width: 0.75 },
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
    const iconSize = pos.big ? 0.52 : 0.34;
    const hasIcon = iconPath && fs.existsSync(iconPath);
    let titleX = cx + padX;
    let titleY = cy + 0.28;
    let titleW = cw - padX * 2;
    let bodyY = cy + 0.92;
    const compactStackCard = useAsymmetric && !pos.big;
    if (compactStackCard) {
      titleY = cy + 0.18;
      bodyY = cy + 0.64;
    }
    if (hasIcon && pos.big) {
      slide.addImage({
        path: iconPath,
        x: cx + (cw - iconSize) / 2,
        y: cy + 0.22,
        w: iconSize,
        h: iconSize,
      });
      titleY = cy + 0.84;
      bodyY = cy + 1.48;
    } else if (hasIcon) {
      slide.addImage({
        path: iconPath,
        x: cx + 0.20,
        y: cy + 0.23,
        w: iconSize,
        h: iconSize,
      });
      titleX = cx + 0.62;
      titleY = cy + 0.20;
      titleW = cw - 0.82;
      bodyY = cy + 0.72;
    }

    slide.addText(safeText(card.title, ''), textOpts({
      x: titleX,
      y: titleY,
      w: titleW,
      h: pos.big ? 0.55 : (compactStackCard ? 0.34 : 0.42),
      fontFace: preset.font_heading,
      fontSize: pos.big ? 22 : (compactStackCard ? 12.4 : 13.5),
      bold: true,
      color: preset.text,
      fit: 'shrink',
    }));
    const bodyText = safeText(card.body, '');
    const bodyBoxMaxH = Math.max(0.38, ch - (bodyY - cy) - 0.22);
    const bodyFontSize = pos.big ? 14 : (compactStackCard ? 9.4 : 10.6);
    const estimatedBodyH = estimateTextHeight(bodyText, bodyFontSize, cw - padX * 2, 1.20);
    const bodyBoxH = Math.min(
      bodyBoxMaxH,
      Math.max(compactStackCard ? 0.46 : 0.55, estimatedBodyH + 0.18),
    );
    slide.addText(bodyText, textOpts({
      x: cx + padX,
      y: bodyY,
      w: cw - padX * 2,
      h: bodyBoxH,
      fontFace: preset.font_body,
      fontSize: bodyFontSize,
      color: preset.text_muted,
      valign: 'top',
      paraSpaceAfter: 4,
      fit: 'shrink',
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
  const header = addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle, slideData);

  const contentY = header.contentTop + 0.30;
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
  // The accent stripe needs a square body to align cleanly at the edge.
  slide.addShape('rect', shapeOpts({
    x: rightX, y: contentY, w: rightW, h: contentH,
    fill: { color: preset.bg_dark },
    line: { color: preset.bg_dark, width: 0 },
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
    const highlightText = highlights.slice(0, n).join('\n');
    const highlightH = Math.min(
      contentH - 0.98,
      Math.max(0.75, estimateTextHeight(highlightText, 14, rightW - 0.5, 1.22) + 0.25),
    );
    slide.addText(items, textOpts({
      x: rightX + 0.3,
      y: contentY + 0.78,
      w: rightW - 0.5,
      h: highlightH,
      fontFace: preset.font_body,
      fontSize: 14,
      color: 'FFFFFF',
      valign: 'top',
    }));
  } else {
    // Fall back to subtitle / footer as the right-panel narrative.
    const narrative = safeText(slideData.subtitle) || safeText(slideData.footer);
    if (narrative) {
      const narrativeH = Math.min(
        contentH - 0.98,
        Math.max(0.75, estimateTextHeight(narrative, 14, rightW - 0.5, 1.22) + 0.25),
      );
      slide.addText(narrative, textOpts({
        x: rightX + 0.3,
        y: contentY + 0.78,
        w: rightW - 0.5,
        h: narrativeH,
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
// Timeline: milestone sequence renderers. Prefer non-card modes when a rail
// would make the slide feel templated.
// ---------------------------------------------------------------------------

function normalizeTimelineItems(slideData) {
  const defaults = [
    { label: 'Q1', title: 'Discover', body: 'Define baseline' },
    { label: 'Q2', title: 'Build', body: 'Pilot delivery' },
    { label: 'Q3', title: 'Scale', body: 'Expand coverage' },
    { label: 'Q4', title: 'Optimize', body: 'Harden operations' },
  ];
  return Array.isArray(slideData.milestones) && slideData.milestones.length
    ? slideData.milestones.slice(0, 5)
    : defaults;
}

function renderTimelineOpenEvents(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  const header = addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle, slideData);
  const rawItems = normalizeTimelineItems(slideData);
  const count = rawItems.length;
  const usableW = SLIDE_W - MARGIN_X * 2;
  const gutter = 0.18;
  const eventW = Math.max(1.24, (usableW - gutter * (count - 1)) / count);
  const totalW = eventW * count + gutter * (count - 1);
  const startX = MARGIN_X + (usableW - totalW) / 2;
  const railY = header.contentTop + 0.86;
  const accent = cleanHex(preset.accent_primary, '8B4513');
  const secondary = cleanHex(preset.accent_secondary, accent);

  slide.addShape('rect', shapeOpts({
    x: startX,
    y: railY,
    w: totalW,
    h: 0.025,
    fill: { color: preset.line || 'D9CBA8' },
    line: { color: preset.line || 'D9CBA8', width: 0 },
  }));

  rawItems.forEach((item, idx) => {
    const x = startX + idx * (eventW + gutter);
    const cx = x + eventW / 2;
    const color = idx % 2 ? secondary : accent;
    slide.addShape('line', shapeOpts({
      x: cx,
      y: railY - 0.38,
      w: 0,
      h: 2.70,
      line: { color: preset.line || 'D9CBA8', transparency: 12, width: 0.6 },
    }));
    slide.addShape('ellipse', shapeOpts({
      x: cx - 0.09,
      y: railY - 0.09,
      w: 0.18,
      h: 0.18,
      fill: { color },
      line: { color: preset.bg || 'FAF6EC', width: 1.1 },
    }));
    slide.addText(safeText(item.label, `Phase ${idx + 1}`).toUpperCase(), textOpts({
      x,
      y: railY - 0.58,
      w: eventW,
      h: 0.20,
      fontFace: preset.font_heading,
      fontSize: 8.2,
      bold: true,
      color,
      align: 'center',
      charSpacing: 1.1,
    }));
    slide.addText(safeText(item.title, item.label || `Step ${idx + 1}`), textOpts({
      x,
      y: railY + 0.32,
      w: eventW,
      h: 0.42,
      fontFace: preset.font_heading,
      fontSize: count >= 5 ? 10.4 : 11.2,
      bold: true,
      color: preset.text || preset.text_primary,
      align: 'center',
      fit: 'shrink',
    }));
    const bodyText = safeText(item.body || item.text, '');
    slide.addText(bodyText, textOpts({
      x,
      y: railY + 0.82,
      w: eventW,
      h: 0.72,
      fontFace: preset.font_body,
      fontSize: count >= 5 ? 7.6 : 8.4,
      color: preset.text_muted,
      align: 'center',
      valign: 'top',
      fit: 'shrink',
    }));
  });

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

function renderTimelineStaggered(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  const header = addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle, slideData);
  const rawItems = normalizeTimelineItems(slideData);
  const count = rawItems.length;
  const usableW = SLIDE_W - MARGIN_X * 2;
  const gutter = 0.18;
  const cardW = Math.max(1.34, (usableW - gutter * (count - 1)) / count);
  const totalW = cardW * count + gutter * (count - 1);
  const startX = MARGIN_X + (usableW - totalW) / 2;
  const railY = Math.min(2.90, header.contentTop + 1.88);
  const topCardY = header.contentTop + 0.18;
  const topCardH = Math.max(1.18, railY - topCardY - 0.34);
  const bottomCardY = railY + 0.36;
  const bottomCardH = Math.max(1.00, SLIDE_H - bottomCardY - 0.72);
  const iconPaths = Array.isArray(slideData.__iconPaths) ? slideData.__iconPaths : [];

  slide.addShape('rect', shapeOpts({
    x: startX,
    y: railY - 0.025,
    w: totalW,
    h: 0.05,
    fill: { color: preset.line || 'CBD5E1' },
    line: { color: preset.line || 'CBD5E1', width: 0 },
  }));

  rawItems.forEach((item, idx) => {
    const x = startX + idx * (cardW + gutter);
    const above = idx % 2 === 0;
    const y = above ? topCardY : bottomCardY;
    const h = above ? topCardH : bottomCardH;
    const cx = x + cardW / 2;
    const accentKey = idx % 2 === 0 ? 'accent_primary' : 'accent_secondary';
    const accentColor = preset[accentKey] || preset.accent_primary;
    const connectorY = above ? y + h : railY;
    const connectorH = above ? railY - (y + h) : y - railY;

    slide.addShape('line', shapeOpts({
      x: cx,
      y: connectorY,
      w: 0,
      h: connectorH,
      line: { color: accentColor, transparency: 32, width: 1.0 },
    }));
    slide.addShape('ellipse', shapeOpts({
      x: cx - 0.12,
      y: railY - 0.12,
      w: 0.24,
      h: 0.24,
      fill: { color: accentColor },
      line: { color: preset.bg, width: 1.2 },
    }));

    slide.addShape('rect', shapeOpts({
      x,
      y,
      w: cardW,
      h,
      fill: { color: preset.surface || 'FFFFFF' },
      line: { color: preset.line, width: 0.75 },
      shadow: cardShadow(),
    }));
    slide.addShape('rect', shapeOpts({
      x,
      y,
      w: 0.08,
      h,
      fill: { color: accentColor },
      line: { color: accentColor, width: 0 },
    }));

    const iconPath = iconPaths[idx];
    const hasIcon = iconPath && fs.existsSync(iconPath);
    if (hasIcon) {
      slide.addImage({ path: iconPath, x: x + cardW - 0.34, y: y + 0.12, w: 0.22, h: 0.22 });
    }

    slide.addText(safeText(item.label, `Phase ${idx + 1}`).toUpperCase(), textOpts({
      x: x + 0.18,
      y: y + 0.12,
      w: cardW - 0.36,
      h: 0.16,
      fontFace: preset.font_heading,
      fontSize: 7.4,
      bold: true,
      color: accentColor,
      charSpacing: 1.2,
    }));
    slide.addText(safeText(item.title, item.label || `Step ${idx + 1}`), textOpts({
      x: x + 0.18,
      y: y + 0.36,
      w: cardW - 0.36,
      h: above ? 0.34 : 0.42,
      fontFace: preset.font_heading,
      fontSize: count >= 5 ? 10.0 : 10.8,
      bold: true,
      color: preset.text,
      fit: 'shrink',
    }));
    slide.addText(safeText(item.body || item.text, ''), textOpts({
      x: x + 0.18,
      y: y + (above ? 0.84 : 0.92),
      w: cardW - 0.36,
      h: Math.max(above ? 0.46 : 0.34, h - (above ? 0.96 : 1.06)),
      fontFace: preset.font_body,
      fontSize: above ? 7.2 : 8.0,
      color: preset.text_muted,
      fit: 'shrink',
    }));
  });

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

function renderTimelineBands(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  const header = addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle, slideData);
  const items = normalizeTimelineItems(slideData).slice(0, 5);
  const contentY = header.contentTop + 0.34;
  const usableW = SLIDE_W - MARGIN_X * 2;
  const rowGap = 0.16;
  const rowH = Math.min(
    0.70,
    (SLIDE_H - contentY - 0.72 - rowGap * (items.length - 1)) / Math.max(1, items.length),
  );
  const accent = cleanHex(preset.accent_primary, '0EA5E9');
  const secondary = cleanHex(preset.accent_secondary, accent);

  items.forEach((item, idx) => {
    const y = contentY + idx * (rowH + rowGap);
    const color = idx % 2 ? secondary : accent;
    const fillColor = idx % 2 ? (preset.surface || 'FFFFFF') : (preset.bg || 'F8FAFC');
    slide.addShape('rect', shapeOpts({
      x: MARGIN_X,
      y,
      w: usableW,
      h: rowH,
      fill: { color: fillColor },
      line: { color: preset.line || 'E2E8F0', width: 0.75 },
    }));
    slide.addShape('rect', shapeOpts({
      x: MARGIN_X,
      y,
      w: 0.08,
      h: rowH,
      fill: { color },
      line: { color, width: 0 },
    }));
    slide.addText(safeText(item.label, `Step ${idx + 1}`).toUpperCase(), textOpts({
      x: MARGIN_X + 0.22,
      y: y + 0.16,
      w: 1.05,
      h: 0.20,
      fontFace: preset.font_heading,
      fontSize: 8.0,
      bold: true,
      color,
      charSpacing: 1.0,
      fit: 'shrink',
    }));
    slide.addText(safeText(item.title, item.label || `Step ${idx + 1}`), textOpts({
      x: MARGIN_X + 1.42,
      y: y + 0.10,
      w: 2.20,
      h: 0.28,
      fontFace: preset.font_heading,
      fontSize: 11.4,
      bold: true,
      color: preset.text || preset.text_primary,
      fit: 'shrink',
    }));
    slide.addText(safeText(item.body || item.text, ''), textOpts({
      x: MARGIN_X + 3.82,
      y: y + 0.12,
      w: usableW - 3.98,
      h: Math.max(0.26, rowH - 0.22),
      fontFace: preset.font_body,
      fontSize: 8.8,
      color: preset.text_muted,
      fit: 'shrink',
    }));
  });

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

function renderTimelineChapterSpread(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  const header = addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle, slideData);
  const items = normalizeTimelineItems(slideData).slice(0, 4);
  const contentY = header.contentTop + 0.34;
  const contentH = SLIDE_H - contentY - 0.70;
  const usableW = SLIDE_W - MARGIN_X * 2;
  const leftW = Math.min(3.25, usableW * 0.38);
  const rightX = MARGIN_X + leftW + 0.44;
  const rightW = usableW - leftW - 0.44;
  const focus = items[0] || { label: '01', title: 'Start', body: '' };
  const accent = cleanHex(preset.accent_primary, 'FF6B35');
  const secondary = cleanHex(preset.accent_secondary, accent);

  slide.addShape('rect', shapeOpts({
    x: MARGIN_X,
    y: contentY,
    w: leftW,
    h: contentH,
    fill: { color: preset.bg_dark || '0F172A' },
    line: { color: preset.bg_dark || '0F172A', width: 0 },
    shadow: cardShadow(),
  }));
  slide.addText('01', textOpts({
    x: MARGIN_X + 0.22,
    y: contentY + 0.08,
    w: leftW - 0.44,
    h: 0.68,
    fontFace: preset.font_heading,
    fontSize: 34,
    bold: true,
    color: accent,
    transparency: 14,
  }));
  slide.addText(safeText(focus.label, 'Start').toUpperCase(), textOpts({
    x: MARGIN_X + 0.28,
    y: contentY + 1.00,
    w: leftW - 0.56,
    h: 0.20,
    fontFace: preset.font_heading,
    fontSize: 8.2,
    bold: true,
    color: secondary,
    charSpacing: 1.3,
    fit: 'shrink',
  }));
  slide.addText(safeText(focus.title, focus.label || 'Milestone'), textOpts({
    x: MARGIN_X + 0.28,
    y: contentY + 1.38,
    w: leftW - 0.56,
    h: 0.62,
    fontFace: preset.font_heading,
    fontSize: 20,
    bold: true,
    color: 'FFFFFF',
    fit: 'shrink',
  }));
  const focusBody = safeText(focus.body || focus.text, '');
  const focusBodyH = Math.min(
    Math.max(0.48, estimateTextHeight(focusBody, 10.2, leftW - 0.56, 1.20) + 0.18),
    Math.max(0.48, contentH - 2.48),
  );
  slide.addText(focusBody, textOpts({
    x: MARGIN_X + 0.28,
    y: contentY + 2.20,
    w: leftW - 0.56,
    h: focusBodyH,
    fontFace: preset.font_body,
    fontSize: 10.2,
    color: 'CBD5E1',
    fit: 'shrink',
  }));
  slide.addShape('rect', shapeOpts({
    x: MARGIN_X,
    y: contentY + contentH - 0.10,
    w: leftW,
    h: 0.10,
    fill: { color: secondary },
    line: { color: secondary, width: 0 },
  }));

  const rest = items.slice(1);
  const rowGap = 0.22;
  const rowH = (contentH - rowGap * Math.max(0, rest.length - 1)) / Math.max(1, rest.length);
  rest.forEach((item, idx) => {
    const y = contentY + idx * (rowH + rowGap);
    const number = String(idx + 2).padStart(2, '0');
    const color = idx % 2 ? secondary : accent;
    slide.addShape('line', shapeOpts({
      x: rightX,
      y: y + rowH - 0.02,
      w: rightW,
      h: 0,
      line: { color: preset.line || 'E2E8F0', width: 0.85 },
    }));
    slide.addText(number, textOpts({
      x: rightX,
      y: y + 0.04,
      w: 0.62,
      h: 0.36,
      fontFace: preset.font_heading,
      fontSize: 18,
      bold: true,
      color,
      fit: 'shrink',
    }));
    slide.addText(safeText(item.label, `Step ${idx + 2}`).toUpperCase(), textOpts({
      x: rightX + 0.82,
      y: y + 0.10,
      w: rightW - 0.82,
      h: 0.16,
      fontFace: preset.font_heading,
      fontSize: 7.4,
      bold: true,
      color,
      charSpacing: 1.0,
      fit: 'shrink',
    }));
    slide.addText(safeText(item.title, item.label || `Milestone ${idx + 2}`), textOpts({
      x: rightX + 0.82,
      y: y + 0.38,
      w: rightW - 0.82,
      h: 0.30,
      fontFace: preset.font_heading,
      fontSize: 12.2,
      bold: true,
      color: preset.text || preset.text_primary,
      fit: 'shrink',
    }));
    slide.addText(safeText(item.body || item.text, ''), textOpts({
      x: rightX + 0.82,
      y: y + 0.82,
      w: rightW - 0.82,
      h: Math.max(0.35, rowH - 0.92),
      fontFace: preset.font_body,
      fontSize: 8.7,
      color: preset.text_muted,
      fit: 'shrink',
    }));
  });

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

function renderTimeline(pptx, slide, slideData, preset) {
  const mode = String(slideData.timeline_mode || preset.timeline_mode || 'rail-cards')
    .trim()
    .toLowerCase();
  if (mode === 'bands' || mode === 'report-bands') {
    renderTimelineBands(pptx, slide, slideData, preset);
    return;
  }
  if (mode === 'chapter-spread' || mode === 'focus-stack') {
    renderTimelineChapterSpread(pptx, slide, slideData, preset);
    return;
  }
  if (mode === 'open-events') {
    renderTimelineOpenEvents(pptx, slide, slideData, preset);
    return;
  }
  if (mode === 'staggered') {
    renderTimelineStaggered(pptx, slide, slideData, preset);
    return;
  }

  paintBackground(slide, preset.bg);
  const header = addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle, slideData);

  const rawItems = normalizeTimelineItems(slideData);
  const count = rawItems.length;

  const usableW = SLIDE_W - MARGIN_X * 2;
  const gutter = 0.30;
  const cardW = Math.max(1.5, (usableW - gutter * (count - 1)) / count);
  const totalW = cardW * count + gutter * (count - 1);
  const startX = MARGIN_X + (usableW - totalW) / 2;

  const railY = header.contentTop + 0.85;
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
    slide.addShape('rect', shapeOpts({
      x: cardX, y: cardY, w: cardW, h: cardH,
      fill: { color: preset.surface || 'FFFFFF' },
      line: { color: preset.line, width: 0.75 },
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
    const bodyText = safeText(item.body || item.text, '');
    const bodyFont = count >= 5 ? 9.2 : 10.0;
    const bodyY = cardY + 0.82 + cardShift;
    const bodyMaxH = Math.max(0.40, cardH - (bodyY - cardY) - 0.16);
    const bodyH = Math.min(
      bodyMaxH,
      Math.max(0.48, estimateTextHeight(bodyText, bodyFont, cardW - 0.30, 1.22) + 0.26),
    );
    slide.addText(bodyText, textOpts({
      x: cardX + 0.15,
      y: bodyY,
      w: cardW - 0.30,
      h: bodyH,
      fontFace: preset.font_body,
      fontSize: bodyFont,
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

function renderStatsFeatureLeft(slide, slideData, preset, header, facts, iconPaths) {
  const contentY = header.contentTop + 0.30;
  const contentH = SLIDE_H - contentY - 0.72;
  const usableW = SLIDE_W - MARGIN_X * 2;
  const gutter = 0.32;
  const leftW = Math.min(3.75, usableW * 0.42);
  const rightX = MARGIN_X + leftW + gutter;
  const rightW = usableW - leftW - gutter;
  const primary = facts[0];
  const primaryAccent = preset[primary.accent || 'accent_secondary'] || preset.accent_secondary || preset.accent_primary;

  slide.addShape('rect', shapeOpts({
    x: MARGIN_X,
    y: contentY,
    w: leftW,
    h: contentH,
    fill: { color: preset.bg_dark || '0F172A' },
    line: { color: preset.bg_dark || '0F172A', width: 0 },
    shadow: cardShadow(),
  }));
  slide.addShape('rect', shapeOpts({
    x: MARGIN_X,
    y: contentY,
    w: 0.10,
    h: contentH,
    fill: { color: primaryAccent },
    line: { color: primaryAccent, width: 0 },
  }));
  const primaryIcon = iconPaths[0];
  if (primaryIcon && fs.existsSync(primaryIcon)) {
    slide.addImage({ path: primaryIcon, x: MARGIN_X + leftW - 0.60, y: contentY + 0.28, w: 0.36, h: 0.36 });
  }
  slide.addText(truncate(primary.value || '-', 10), textOpts({
    x: MARGIN_X + 0.34,
    y: contentY + 0.48,
    w: leftW - 0.58,
    h: 0.95,
    fontFace: preset.font_heading,
    fontSize: String(primary.value || '').length > 5 ? 42 : 50,
    bold: true,
    color: primaryAccent,
    fit: 'shrink',
  }));
  slide.addText(primary.label || '', textOpts({
    x: MARGIN_X + 0.34,
    y: contentY + 1.58,
    w: leftW - 0.58,
    h: 0.68,
    fontFace: preset.font_heading,
    fontSize: 14,
    bold: true,
    color: 'FFFFFF',
    fit: 'shrink',
  }));
  if (primary.caption) {
    slide.addText(primary.caption, textOpts({
      x: MARGIN_X + 0.34,
      y: contentY + 2.42,
      w: leftW - 0.58,
      h: Math.max(0.46, contentH - 2.70),
      fontFace: preset.font_body,
      fontSize: 10.5,
      color: 'CBD5E1',
      fit: 'shrink',
    }));
  }

  const rest = facts.slice(1, 4);
  const rowGap = 0.16;
  const rowH = (contentH - rowGap * (rest.length - 1)) / Math.max(1, rest.length);
  rest.forEach((fact, idx) => {
    const y = contentY + idx * (rowH + rowGap);
    const accentKey = fact.accent || (idx % 2 ? 'accent_primary' : 'accent_secondary');
    const accentColor = preset[accentKey] || preset.accent_primary;
    slide.addShape('rect', shapeOpts({
      x: rightX,
      y,
      w: rightW,
      h: rowH,
      fill: { color: preset.surface || 'FFFFFF' },
      line: { color: preset.line || 'D1D5DB', width: 0.75 },
    }));
    slide.addShape('rect', shapeOpts({
      x: rightX,
      y,
      w: 0.07,
      h: rowH,
      fill: { color: accentColor },
      line: { color: accentColor, width: 0 },
    }));
    const iconPath = iconPaths[idx + 1];
    if (iconPath && fs.existsSync(iconPath)) {
      slide.addImage({ path: iconPath, x: rightX + rightW - 0.42, y: y + 0.13, w: 0.24, h: 0.24 });
    }
    slide.addText(truncate(fact.value || '-', 8), textOpts({
      x: rightX + 0.20,
      y: y + 0.10,
      w: 1.20,
      h: 0.42,
      fontFace: preset.font_heading,
      fontSize: 16,
      bold: true,
      color: accentColor,
      fit: 'shrink',
    }));
    slide.addText(fact.label || '', textOpts({
      x: rightX + 0.20,
      y: y + 0.60,
      w: rightW - 0.48,
      h: 0.26,
      fontFace: preset.font_heading,
      fontSize: 10.8,
      bold: true,
      color: preset.text || preset.text_primary,
      fit: 'shrink',
    }));
    if (fact.caption) {
      const captionH = Math.min(
        Math.max(0.22, estimateTextHeight(fact.caption, 8.8, rightW - 0.40, 1.15) + 0.10),
        Math.max(0.22, rowH - 1.18),
      );
      slide.addText(fact.caption, textOpts({
        x: rightX + 0.20,
        y: y + 1.08,
        w: rightW - 0.40,
        h: captionH,
        fontFace: preset.font_body,
        fontSize: 8.8,
        color: preset.text_muted,
        fit: 'shrink',
      }));
    }
  });

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

function renderStatsPolicyBands(slide, slideData, preset, header, facts, iconPaths) {
  const contentY = header.contentTop + 0.35;
  const contentH = SLIDE_H - contentY - 0.72;
  const usableW = SLIDE_W - MARGIN_X * 2;
  const leftW = 3.20;
  const rightX = MARGIN_X + leftW + 0.44;
  const rightW = usableW - leftW - 0.44;
  const primary = facts[0];
  const accent = preset[primary.accent || 'accent_primary'] || preset.accent_primary;
  const circleX = MARGIN_X - 0.20;
  const circleY = contentY + 0.18;
  const circleW = 2.65;
  const circlePad = 0.26;

  slide.addShape('ellipse', shapeOpts({
    x: circleX,
    y: circleY,
    w: circleW,
    h: circleW,
    fill: { color: accent, transparency: 88 },
    line: { color: accent, transparency: 100, width: 0 },
  }));
  const primaryIcon = iconPaths[0];
  if (primaryIcon && fs.existsSync(primaryIcon)) {
    slide.addImage({ path: primaryIcon, x: MARGIN_X + 2.55, y: contentY + 0.20, w: 0.34, h: 0.34 });
  }
  slide.addText(truncate(primary.value || '-', 10), textOpts({
    x: circleX + circlePad,
    y: circleY + 0.50,
    w: circleW - circlePad * 2,
    h: 0.92,
    fontFace: preset.font_heading,
    fontSize: String(primary.value || '').length > 5 ? 42 : 50,
    bold: true,
    color: accent,
    align: 'center',
    fit: 'shrink',
  }));
  slide.addText(primary.label || '', textOpts({
    x: circleX + circlePad,
    y: circleY + 1.48,
    w: circleW - circlePad * 2,
    h: 0.54,
    fontFace: preset.font_heading,
    fontSize: 13.5,
    bold: true,
    color: preset.text || preset.text_primary,
    align: 'center',
    fit: 'shrink',
  }));
  if (primary.caption) {
    slide.addText(primary.caption, textOpts({
      x: circleX + circlePad,
      y: circleY + 2.08,
      w: circleW - circlePad * 2,
      h: Math.min(0.62, Math.max(0.36, estimateTextHeight(primary.caption, 10.0, circleW - circlePad * 2, 1.20) + 0.18)),
      fontFace: preset.font_body,
      fontSize: 10.0,
      color: preset.text_muted,
      align: 'center',
      fit: 'shrink',
    }));
  }

  slide.addShape('line', shapeOpts({
    x: rightX - 0.22,
    y: contentY + 0.02,
    w: 0,
    h: contentH - 0.04,
    line: { color: preset.line || 'E2E8F0', width: 1.1 },
  }));

  const rest = facts.slice(1, 4);
  const rowH = contentH / Math.max(1, rest.length);
  rest.forEach((fact, idx) => {
    const y = contentY + idx * rowH;
    const factAccent = preset[fact.accent || (idx % 2 ? 'accent_secondary' : 'accent_primary')] || preset.accent_primary;
    if (idx > 0) {
      slide.addShape('line', shapeOpts({
        x: rightX,
        y,
        w: rightW,
        h: 0,
        line: { color: preset.line || 'E2E8F0', width: 0.8 },
      }));
    }
    const iconPath = iconPaths[idx + 1];
    if (iconPath && fs.existsSync(iconPath)) {
      slide.addImage({ path: iconPath, x: rightX, y: y + 0.22, w: 0.24, h: 0.24 });
    }
    slide.addText(truncate(fact.value || '-', 9), textOpts({
      x: rightX + 0.36,
      y: y + 0.18,
      w: 1.05,
      h: 0.34,
      fontFace: preset.font_heading,
      fontSize: 18,
      bold: true,
      color: factAccent,
      fit: 'shrink',
    }));
    slide.addText(fact.label || '', textOpts({
      x: rightX + 1.50,
      y: y + 0.18,
      w: rightW - 1.50,
      h: 0.28,
      fontFace: preset.font_heading,
      fontSize: 10.8,
      bold: true,
      color: preset.text || preset.text_primary,
      fit: 'shrink',
    }));
    if (fact.caption) {
      const captionH = Math.min(
        Math.max(0.22, estimateTextHeight(fact.caption, 8.8, rightW - 1.50, 1.15) + 0.10),
        Math.max(0.28, rowH - 0.78),
      );
      slide.addText(fact.caption, textOpts({
        x: rightX + 1.50,
        y: y + 0.70,
        w: rightW - 1.50,
        h: captionH,
        fontFace: preset.font_body,
        fontSize: 8.8,
        color: preset.text_muted,
        fit: 'shrink',
      }));
    }
  });

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

function renderStats(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  const header = addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle, slideData);

  const facts = normalizeFacts(slideData.facts).slice(0, 4);
  if (facts.length === 0) {
    slide.addText('No facts provided.', textOpts({
      x: MARGIN_X,
      y: header.contentTop + 1.0,
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
  const tileY = header.contentTop + 0.45;
  const tileH = SLIDE_H - tileY - 0.75;

  const iconPaths = Array.isArray(slideData.__iconPaths) ? slideData.__iconPaths : [];
  const statsMode = String(slideData.stats_mode || preset.stats_mode || 'tiles')
    .trim()
    .toLowerCase();
  if (statsMode === 'feature-left' && facts.length >= 3) {
    renderStatsFeatureLeft(slide, slideData, preset, header, facts, iconPaths);
    return;
  }
  if (statsMode === 'policy-bands' && facts.length >= 3) {
    renderStatsPolicyBands(slide, slideData, preset, header, facts, iconPaths);
    return;
  }

  facts.forEach((fact, idx) => {
    const tx = MARGIN_X + idx * (tileW + gutter);
    // Per-fact accent when explicitly set on the fact; otherwise alternate.
    const accentKey = fact.accent
      ? fact.accent
      : (idx % 2 === 0 ? 'accent_primary' : 'accent_secondary');
    const accentColor = preset[accentKey] || preset.accent_primary;

    slide.addShape('rect', shapeOpts({
      x: tx, y: tileY, w: tileW, h: tileH,
      fill: { color: preset.bg_dark },
      line: { color: preset.bg_dark, width: 0 },
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
    const iconSize = 0.34;
    const hasIcon = iconPath && fs.existsSync(iconPath);
    if (hasIcon) {
      slide.addImage({
        path: iconPath,
        x: tx + tileW - iconSize - 0.22,
        y: tileY + 0.22,
        w: iconSize,
        h: iconSize,
      });
    }

    // Large stat value.
    const valueFont = String(fact.value || '').length > 5 ? 36 : 40;
    const valueY = tileY + 0.34;
    const valueH = Math.min(0.86, tileH * 0.28);
    const labelY = valueY + valueH + 0.13;
    const labelH = 0.74;
    const captionY = labelY + labelH + 0.12;
    slide.addText(truncate(fact.value || '-', 10), textOpts({
      x: tx + 0.25,
      y: valueY,
      w: tileW - 0.4,
      h: valueH,
      fontFace: preset.font_heading,
      fontSize: valueFont,
      bold: true,
      color: accentColor,
      valign: 'middle',
    }));
    slide.addText(fact.label || '', textOpts({
      x: tx + 0.25,
      y: labelY,
      w: tileW - 0.4,
      h: labelH,
      fontFace: preset.font_heading,
      fontSize: 12.5,
      bold: true,
      color: 'FFFFFF',
      valign: 'top',
    }));
    if (fact.caption) {
      slide.addText(fact.caption, textOpts({
        x: tx + 0.25,
        y: captionY,
        w: tileW - 0.4,
        h: Math.min(0.58, Math.max(0.36, 0.16 + estimateTextLines(fact.caption, 11, tileW - 0.4) * 0.18)),
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
  const title = String(slideData.title || '').trim();
  const subtitle = String(slideData.subtitle || '').trim();
  const header = headerMetrics(title, subtitle, {
    topPad: 0.28,
    bottomPad: 0.10,
    titleFont: titleFontForLength(title) + 2,
    subtitleFont: 14,
  });
  slide.addText(title, textOpts({
    x: MARGIN_X,
    y: header.titleY,
    w: header.textW,
    h: header.titleH,
    fontFace: preset.font_title,
    fontSize: header.titleFont,
    color: titleColor,
    bold: true,
  }));
  if (subtitle) {
    slide.addText(subtitle, textOpts({
      x: MARGIN_X,
      y: header.subtitleY,
      w: header.textW,
      h: header.subtitleH,
      fontFace: preset.font_caption,
      fontSize: header.subtitleFont,
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
  const effectiveContentTop = Math.max(subtitle ? 1.50 : CONTENT_TOP, header.contentTop + 0.16);
  const contentH = SLIDE_H - effectiveContentTop - 0.85;
  let valueH = Math.min(2.1, Math.max(1.55, valueFont / 72 * 1.25));
  const labelH = label ? 0.5 : 0;
  // Context box: scale height with line count. 13pt font across a ~7.4"-wide
  // box fits ~80 chars per line. Short strings get 0.42"; longer ones get
  // 0.42" per estimated line up to 3 lines. Previous flat 0.42" overflowed.
  let contextH = 0;
  if (context) {
    contextH = Math.min(
      0.78,
      Math.max(
        0.46,
        estimateTextHeight(context, 12, SLIDE_W - (MARGIN_X + 0.8) * 2, 1.22) + 0.12,
      ),
    );
  }
  const maxStack = Math.max(1.5, SLIDE_H - FOOTER_H - 0.16 - effectiveContentTop);
  let totalStack = valueH + (label ? 0.15 : 0) + labelH +
                   (context ? 0.10 : 0) + contextH;
  if (totalStack > maxStack) {
    const overflow = totalStack - maxStack;
    valueH = Math.max(1.55, valueH - overflow);
    totalStack = valueH + (label ? 0.15 : 0) + labelH +
                 (context ? 0.10 : 0) + contextH;
  }
  const idealStartY = effectiveContentTop + Math.max(0.2, (contentH - totalStack) / 2);
  const bottomLimit = SLIDE_H - 0.78;
  const startY = Math.max(
    effectiveContentTop + 0.05,
    Math.min(idealStartY, bottomLimit - totalStack),
  );

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
    fit: 'shrink',
  }));
  if (label) {
    slide.addText(label, textOpts({
      x: MARGIN_X,
      y: startY + valueH + 0.22,
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
    const contextY = startY + valueH + (label ? 0.22 + labelH + 0.10 : 0.15);
    slide.addText(context, textOpts({
      x: MARGIN_X + 0.8,
      y: contextY,
      w: SLIDE_W - (MARGIN_X + 0.8) * 2,
      h: contextH,
      fontFace: preset.font_caption,
      fontSize: 12,
      color: subtitleColor,
      align: 'center',
      fit: 'shrink',
    }));
  }

  addFooter(slide, preset, slideData, { dark });
  attachNotes(slide, slideData);
}


// ---------------------------------------------------------------------------
// table variant — native pptxgenjs addTable. Cleaner typography than the
// python renderer's add_table; this is the reason the HTML path exists.
// ---------------------------------------------------------------------------

function normalizeTableSpec(slideData) {
  const nested = (slideData.table && typeof slideData.table === 'object') ? slideData.table : {};
  const get = (key, fallback) => (
    slideData[key] !== undefined ? slideData[key] :
      nested[key] !== undefined ? nested[key] :
        fallback
  );
  return {
    title: String(get('title', '') || '').trim(),
    headers: Array.isArray(get('headers', [])) ? get('headers', []) : [],
    rows: Array.isArray(get('rows', [])) ? get('rows', []) : [],
    column_weights: Array.isArray(get('column_weights', null)) ? get('column_weights', null) : null,
    caption: String(get('caption', '') || '').trim(),
    footnotes: Array.isArray(get('footnotes', [])) ? get('footnotes', []) : [],
    cell_styles: get('cell_styles', null),
    row_styles: get('row_styles', null),
    header_style: get('header_style', null),
  };
}

function normalizeTables(slideData) {
  const rawTables = Array.isArray(slideData.tables)
    ? slideData.tables
    : Array.isArray(slideData.table_groups)
      ? slideData.table_groups
      : [];
  if (rawTables.length) {
    return rawTables
      .filter((item) => item && typeof item === 'object')
      .map((item) => normalizeTableSpec({ table: item }));
  }
  return [normalizeTableSpec(slideData)].filter((item) => item.headers.length && item.rows.length);
}

function stripHashColor(value, fallback) {
  const raw = String(value || fallback || '').trim().replace(/^#/, '');
  return /^[0-9a-fA-F]{6}$/.test(raw) ? raw.toUpperCase() : String(fallback || 'FFFFFF');
}

function tableStyle(base, override) {
  const extra = (override && typeof override === 'object') ? override : {};
  const merged = Object.assign({}, base);
  const fillColor = extra.fill || extra.fill_color || (base.fill && base.fill.color);
  if (fillColor) merged.fill = { color: stripHashColor(fillColor, base.fill && base.fill.color) };
  const textColor = extra.color || extra.text_color || base.color;
  if (textColor) merged.color = stripHashColor(textColor, base.color);
  if (extra.bold !== undefined) merged.bold = !!extra.bold;
  if (extra.italic !== undefined) merged.italic = !!extra.italic;
  if (extra.align) merged.align = String(extra.align);
  if (extra.valign) merged.valign = String(extra.valign);
  if (extra.fontSize || extra.font_size) merged.fontSize = Number(extra.fontSize || extra.font_size);
  if (extra.margin !== undefined) merged.margin = Number(extra.margin);
  if (extra.border_color) merged.border = { color: stripHashColor(extra.border_color, 'CBD5E1'), pt: 0.5 };
  return merged;
}

function tableCellOverride(table, rowIdx, colIdx) {
  const cellStyles = table.cell_styles;
  if (Array.isArray(cellStyles)) {
    const row = cellStyles[rowIdx];
    if (Array.isArray(row) && row[colIdx] && typeof row[colIdx] === 'object') return row[colIdx];
  } else if (cellStyles && typeof cellStyles === 'object') {
    const direct = cellStyles[`${rowIdx},${colIdx}`] || cellStyles[`${rowIdx}:${colIdx}`];
    if (direct && typeof direct === 'object') return direct;
  }
  const highlights = Array.isArray(table.cell_highlights) ? table.cell_highlights : [];
  for (const item of highlights) {
    if (!item || typeof item !== 'object') continue;
    if (Number(item.row) === rowIdx && Number(item.col) === colIdx) return item;
  }
  return null;
}

function tableRowOverride(table, rowIdx) {
  const rowStyles = table.row_styles;
  if (Array.isArray(rowStyles) && rowStyles[rowIdx] && typeof rowStyles[rowIdx] === 'object') {
    return rowStyles[rowIdx];
  }
  if (rowStyles && typeof rowStyles === 'object') {
    const direct = rowStyles[String(rowIdx)];
    if (direct && typeof direct === 'object') return direct;
  }
  return null;
}

function buildTableRows(table, preset, opts) {
  const options = opts || {};
  const headerFill = stripHashColor(
    options.headerFill || (table.header_style && table.header_style.fill) || preset.accent_primary,
    '1F4E79',
  );
  const headerFont = options.headerFontSize || 11;
  const bodyFont = options.bodyFontSize || 9.5;
  const headerCellStyle = {
    fill: { color: headerFill },
    color: 'FFFFFF',
    bold: true,
    fontFace: preset.font_title,
    fontSize: headerFont,
    align: 'left',
    valign: 'middle',
    margin: 0.04,
  };
  const bodyCellStyleA = {
    fill: { color: preset.surface || 'FFFFFF' },
    color: preset.text_primary || preset.text || '0F172A',
    fontFace: preset.font_body,
    fontSize: bodyFont,
    align: 'left',
    valign: 'middle',
    margin: 0.04,
  };
  const bodyCellStyleB = tableStyle(bodyCellStyleA, {
    fill: options.zebraFill || preset.bg || 'F8FAFC',
  });

  const headerStyle = tableStyle(headerCellStyle, table.header_style);
  const tableRows = [
    table.headers.map((h) => ({ text: String(h || ''), options: tableStyle(headerStyle, {}) })),
  ];
  table.rows.forEach((row, idx) => {
    const rowBase = idx % 2 === 0 ? bodyCellStyleA : bodyCellStyleB;
    const rowExtra = tableRowOverride(table, idx);
    const cells = [];
    for (let c = 0; c < table.headers.length; c++) {
      const v = Array.isArray(row) && row[c] !== undefined ? row[c] : '';
      const override = tableCellOverride(table, idx, c);
      cells.push({ text: String(v), options: tableStyle(tableStyle(rowBase, rowExtra), override) });
    }
    tableRows.push(cells);
  });
  return tableRows;
}

function tableColumnWidths(headers, weights, usableW) {
  if (weights && weights.length === headers.length) {
    const total = weights.reduce((a, b) => a + Number(b || 0), 0);
    if (total > 0) return weights.map((w) => (usableW * Number(w || 0)) / total);
  }
  return Array(headers.length).fill(usableW / headers.length);
}

function addTableCaptionAndFootnotes(slide, preset, table, x, y, w, maxH, opts) {
  const lines = [];
  if (table.caption) lines.push(table.caption);
  for (const note of table.footnotes || []) {
    const text = String(note || '').trim();
    if (text) lines.push(text);
  }
  if (!lines.length || maxH <= 0.08) return;
  slide.addText(lines.join('\n'), textOpts({
    x,
    y,
    w,
    h: maxH,
    fontFace: preset.font_caption || preset.font_body,
      fontSize: (opts && opts.fontSize) || 8.2,
    color: preset.text_muted,
    italic: true,
    breakLine: false,
    fit: 'shrink',
  }));
}

function addCompactTable(slide, preset, table, box, opts) {
  const options = opts || {};
  const title = String(table.title || '').trim();
  const titleH = title ? (options.titleH || 0.24) : 0;
  const gap = title ? 0.07 : 0;
  if (title) {
    slide.addText(title, textOpts({
      x: box.x,
      y: box.y,
      w: box.w,
      h: titleH,
      fontFace: preset.font_heading,
      fontSize: options.titleFont || 10.5,
      bold: true,
      color: preset.text || preset.text_primary,
      fit: 'shrink',
    }));
  }
  const noteLines = (table.caption ? 1 : 0) + (Array.isArray(table.footnotes) ? table.footnotes.length : 0);
  const notesH = Math.min(options.maxNotesH || 0.42, noteLines ? 0.14 + noteLines * 0.13 : 0);
  const tableY = box.y + titleH + gap;
  const tableH = Math.max(0.55, box.h - titleH - gap - notesH - (noteLines ? 0.08 : 0));
  const tableRows = buildTableRows(table, preset, {
    headerFontSize: options.headerFontSize || 9,
    bodyFontSize: options.bodyFontSize || 8,
    headerFill: options.headerFill,
  });
  const colW = tableColumnWidths(table.headers, table.column_weights, box.w);
  const rowH = Math.min(options.rowH || 0.30, Math.max(0.18, tableH / Math.max(1, tableRows.length)));
  slide.addTable(tableRows, {
    x: box.x,
    y: tableY,
    w: box.w,
    h: tableH,
    colW,
    fontSize: options.bodyFontSize || 8,
    rowH,
  });
  if (noteLines) {
    addTableCaptionAndFootnotes(slide, preset, table, box.x, tableY + tableH + 0.06, box.w, notesH, {
      fontSize: options.notesFontSize || 8.0,
    });
  }
}

function renderTable(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  const header = addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle, slideData);

  const table = normalizeTableSpec(slideData);
  const headers = table.headers;
  const rows = table.rows;
  if (headers.length === 0 || rows.length === 0) {
    slide.addText('table variant requires `headers` + `rows`.', textOpts({
      x: MARGIN_X,
      y: header.contentTop + 0.4,
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

  const usableW = SLIDE_W - MARGIN_X * 2;
  const captionLines = (table.caption ? 1 : 0) + table.footnotes.length;
  const captionGap = captionLines ? 0.12 : 0;
  const captionH = captionLines ? Math.min(0.54, 0.18 + captionLines * 0.14) : 0;
  const availableH = SLIDE_H - header.contentTop - 0.56 - captionH - captionGap;
  const tableRows = buildTableRows(table, preset, { headerFontSize: 12, bodyFontSize: 10 });
  const colW = tableColumnWidths(headers, table.column_weights, usableW);
  const tableY = header.contentTop + 0.2;
  const tableH = Math.min(availableH, 0.55 + tableRows.length * 0.38);
  slide.addTable(tableRows, {
    x: MARGIN_X,
    y: tableY,
    w: usableW,
    h: tableH,
    colW,
    fontSize: 11,
    rowH: 0.42,
  });

  if (captionLines) {
    // Caption sits immediately below the table, not at a fixed bottom
    // offset — that caused overlap when the table ran long.
    addTableCaptionAndFootnotes(
      slide,
      preset,
      table,
      MARGIN_X,
      tableY + tableH + captionGap,
      usableW,
      captionH,
      { fontSize: 9 },
    );
  }

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

function renderLabRunResults(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  const header = addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle, slideData);
  const tables = normalizeTables(slideData);
  if (!tables.length) {
    slide.addText('lab-run-results requires `tables` or table `headers` + `rows`.', textOpts({
      x: MARGIN_X,
      y: header.contentTop + 0.4,
      w: SLIDE_W - MARGIN_X * 2,
      h: 0.5,
      fontFace: preset.font_body,
      fontSize: 13,
      color: preset.text_muted,
    }));
    addFooter(slide, preset, slideData);
    attachNotes(slide, slideData);
    return;
  }

  const usableW = SLIDE_W - MARGIN_X * 2;
  const callout = String(slideData.interpretation || slideData.takeaway || '').trim();
  const calloutReserve = callout ? 0.50 : 0;
  const usableH = SLIDE_H - header.contentTop - FOOTER_H - 0.34 - calloutReserve;
  const topY = header.contentTop + 0.18;
  const gutter = 0.24;

  if (tables.length === 1) {
    addCompactTable(slide, preset, tables[0], { x: MARGIN_X, y: topY, w: usableW, h: usableH }, {
      headerFontSize: 10,
      bodyFontSize: 8.6,
      rowH: 0.30,
      maxNotesH: 0.50,
    });
  } else if (tables.length === 2) {
    const colW = (usableW - gutter) / 2;
    addCompactTable(slide, preset, tables[0], { x: MARGIN_X, y: topY, w: colW, h: usableH }, {
      headerFontSize: 9.5,
      bodyFontSize: 8,
      rowH: 0.28,
      maxNotesH: 0.46,
    });
    addCompactTable(slide, preset, tables[1], { x: MARGIN_X + colW + gutter, y: topY, w: colW, h: usableH }, {
      headerFontSize: 9.5,
      bodyFontSize: 8,
      rowH: 0.28,
      maxNotesH: 0.46,
    });
  } else {
    const leftW = usableW * 0.58;
    const rightW = usableW - leftW - gutter;
    addCompactTable(slide, preset, tables[0], { x: MARGIN_X, y: topY, w: leftW, h: usableH }, {
      headerFontSize: 9,
      bodyFontSize: 8.2,
      rowH: 0.26,
      maxNotesH: 0.44,
    });
    const stackCount = Math.min(2, tables.length - 1);
    const stackH = (usableH - gutter * (stackCount - 1)) / stackCount;
    for (let i = 0; i < stackCount; i += 1) {
      addCompactTable(
        slide,
        preset,
        tables[i + 1],
        {
          x: MARGIN_X + leftW + gutter,
          y: topY + i * (stackH + gutter),
          w: rightW,
          h: stackH,
        },
        {
          headerFontSize: 8.8,
          bodyFontSize: 8.0,
          rowH: 0.24,
          titleFont: 9.2,
          maxNotesH: 0.34,
        },
      );
    }
  }

  if (callout) {
    slide.addShape('rect', shapeOpts({
      x: MARGIN_X,
      y: SLIDE_H - FOOTER_H - 0.42,
      w: usableW,
      h: 0.30,
      fill: { color: preset.surface || 'FFFFFF' },
      line: { color: preset.line, width: 0.5 },
    }));
    slide.addText(callout, textOpts({
      x: MARGIN_X + 0.12,
      y: SLIDE_H - FOOTER_H - 0.36,
      w: usableW - 0.24,
      h: 0.22,
      fontFace: preset.font_body,
      fontSize: 8.4,
      color: preset.text || preset.text_primary,
      bold: true,
      fit: 'shrink',
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
  const header = addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle, slideData);

  const left = (slideData.left && typeof slideData.left === 'object') ? slideData.left : {};
  const right = (slideData.right && typeof slideData.right === 'object') ? slideData.right : {};
  const verdict = String(slideData.verdict || '').trim();

  const gutter = 0.35;
  const usableW = SLIDE_W - MARGIN_X * 2;
  const colW = (usableW - gutter) / 2;
  const hasVerdict = verdict.length > 0;
  const verdictH = hasVerdict ? (verdict.length > 80 ? 0.72 : 0.62) : 0;
  const verdictGap = hasVerdict ? 0.20 : 0;

  const colTop = header.contentTop + 0.20;
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
      fontSize: verdict.length > 80 ? 12 : 13,
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

function renderMatrixOpenQuadrants(slide, slideData, preset, header, quadrants, iconPaths) {
  const usableW = SLIDE_W - MARGIN_X * 2;
  const topY = header.contentTop + 0.25;
  const usableH = SLIDE_H - topY - 0.70;
  const centerX = MARGIN_X + usableW / 2;
  const centerY = topY + usableH / 2;
  const gutter = 0.34;
  const zoneW = (usableW - gutter) / 2;
  const zoneH = (usableH - gutter) / 2;

  slide.addShape('line', shapeOpts({
    x: centerX,
    y: topY,
    w: 0,
    h: usableH,
    line: { color: preset.line || 'E2E8F0', width: 1.0 },
  }));
  slide.addShape('line', shapeOpts({
    x: MARGIN_X,
    y: centerY,
    w: usableW,
    h: 0,
    line: { color: preset.line || 'E2E8F0', width: 1.0 },
  }));

  quadrants.forEach((q, idx) => {
    const row = Math.floor(idx / 2);
    const col = idx % 2;
    const x = MARGIN_X + col * (zoneW + gutter);
    const y = topY + row * (zoneH + gutter);
    const accentKey = idx % 2 === 0 ? 'accent_primary' : 'accent_secondary';
    const accentColor = preset[accentKey] || preset.accent_primary;
    const title = safeText(q.title, `Quadrant ${idx + 1}`);
    const body = safeText(q.body || q.text);
    const iconPath = iconPaths[idx];
    const hasIcon = iconPath && fs.existsSync(iconPath);

    slide.addShape('ellipse', shapeOpts({
      x: x + zoneW - 0.54,
      y: y + 0.04,
      w: 0.44,
      h: 0.44,
      fill: { color: accentColor, transparency: 86 },
      line: { color: accentColor, transparency: 100, width: 0 },
    }));
    slide.addText(String(idx + 1).padStart(2, '0'), textOpts({
      x: x,
      y: y + 0.02,
      w: 0.58,
      h: 0.30,
      fontFace: preset.font_heading,
      fontSize: 11,
      bold: true,
      color: accentColor,
      charSpacing: 1.2,
    }));
    if (hasIcon) {
      slide.addImage({
        path: iconPath,
        x: x + zoneW - 0.44,
        y: y + 0.14,
        w: 0.24,
        h: 0.24,
      });
    }
    slide.addText(title, textOpts({
      x,
      y: y + 0.42,
      w: zoneW - 0.18,
      h: 0.42,
      fontFace: preset.font_heading,
      fontSize: 15,
      bold: true,
      color: preset.text || preset.text_primary,
      fit: 'shrink',
    }));
    if (body) {
      const bodyLines = body.split(/\n|(?<=\.)\s+/)
        .map((s) => s.trim())
        .filter(Boolean)
        .slice(0, 4);
      slide.addText(bodyLines.map((line, i) => ({
        text: line,
        options: { breakLine: i < bodyLines.length - 1 },
      })), textOpts({
        x,
        y: y + 0.96,
        w: zoneW - 0.18,
        h: Math.max(0.45, zoneH - 1.04),
        fontFace: preset.font_body,
        fontSize: 10.6,
        color: preset.text_muted || preset.text,
        fit: 'shrink',
        paraSpaceAfter: 3,
      }));
    }
  });

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

function renderMatrix(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  const header = addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle, slideData);

  const quadrants = Array.isArray(slideData.quadrants) ? slideData.quadrants.slice(0, 4) : [];
  while (quadrants.length < 4) {
    quadrants.push({ title: `Quadrant ${quadrants.length + 1}`, body: '' });
  }

  const gutter = 0.30;
  const usableW = SLIDE_W - MARGIN_X * 2;
  const cardW = (usableW - gutter) / 2;
  const topY = header.contentTop + 0.20;
  const usableH = SLIDE_H - topY - 0.65;
  const cardH = (usableH - gutter) / 2;
  const iconPaths = Array.isArray(slideData.__iconPaths) ? slideData.__iconPaths : [];

  const matrixMode = String(slideData.matrix_mode || preset.matrix_mode || 'cards')
    .trim()
    .toLowerCase();
  if (matrixMode === 'open-quadrants') {
    renderMatrixOpenQuadrants(slide, slideData, preset, header, quadrants, iconPaths);
    return;
  }

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
      const bodyY = cy + railH + 0.68;
      const availableBodyH = Math.max(0.4, cardH - (bodyY - cy) - 0.18);
      const bodyBoxH = Math.min(
        availableBodyH,
        Math.max(0.48, 0.16 + bodyLines.length * 0.22),
      );
      slide.addText(
        bodyLines.map((line, i) => ({
          text: line,
          options: { breakLine: i < bodyLines.length - 1 },
        })),
        textOpts({
          x: cx + 0.18, y: bodyY,
          w: cardW - 0.36, h: bodyBoxH,
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
  const header = addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle, slideData);

  const diagramPath = slideData.__mermaidPath || slideData.__diagramPath;
  if (!diagramPath || !fs.existsSync(diagramPath)) {
    // Fall back to standard text layout if the diagram is missing, so the
    // slide still renders something useful instead of a blank body.
    renderStandard(pptx, slide, slideData, preset);
    return;
  }

  // Body region: below header, leaving space for footer/callout.
  const bodyTop = header.contentTop + 0.15;
  const hasFooter = !!(String(slideData.footer || '').trim());
  const hasCallout = !!(String(slideData.summary_callout || '').trim());
  const bottomReserve = (hasFooter ? 0.40 : 0.20) + (hasCallout ? 0.75 : 0.0);
  const bodyH = SLIDE_H - bodyTop - bottomReserve;
  const bodyW = SLIDE_W - MARGIN_X * 2;
  const hasRailContent = (
    (Array.isArray(slideData.sidebar_sections) && slideData.sidebar_sections.length > 0) ||
    !!safeText(slideData.body) ||
    normalizeBullets(slideData.bullets).length > 0 ||
    (Array.isArray(slideData.highlights) && slideData.highlights.some((h) => safeText(h)))
  );
  const railGap = 0.28;
  const railW = hasRailContent ? 2.25 : 0;
  const diagramW = hasRailContent ? Math.max(5.4, bodyW - railW - railGap) : bodyW;

  try {
    const sized = imageSizingContainLocal(diagramPath, MARGIN_X, bodyTop, diagramW, bodyH);
    slide.addImage(Object.assign({ path: diagramPath }, sized));
  } catch (e) {
    console.warn('[pptxgenjs] flow diagram embed failed:', e.message);
    renderStandard(pptx, slide, slideData, preset);
    return;
  }

  if (hasRailContent) {
    const railX = MARGIN_X + diagramW + railGap;
    const sections = normalizeSidebarSections(slideData).slice(0, 3);
    const sectionGap = 0.12;
    const sectionModels = sections.map((section, idx) => {
      const title = safeText(section.title || section.label, idx === 0 ? 'Readout' : `Note ${idx + 1}`);
      const rawLines = sectionBodyLines(section);
      const lines = rawLines.slice(0, rawLines.length <= 2 ? 2 : 3);
      const bodyText = lines.join('\n');
      const estimatedBodyH = estimateTextHeight(bodyText, 9.5, railW - 0.14, 1.25);
      const desiredH = Math.min(1.45, Math.max(0.74, 0.44 + estimatedBodyH + 0.16));
      return { section, title, lines, desiredH };
    });
    const totalGap = sectionGap * Math.max(0, sectionModels.length - 1);
    const desiredTotal = sectionModels.reduce((sum, model) => sum + model.desiredH, 0);
    const heightScale = desiredTotal + totalGap > bodyH
      ? Math.max(0.72, (bodyH - totalGap) / Math.max(0.01, desiredTotal))
      : 1;
    let y = bodyTop;
    sectionModels.forEach((model, idx) => {
      const sectionH = Math.max(0.54, model.desiredH * heightScale);
      const accent = idx % 2 === 0 ? preset.accent_primary : preset.accent_secondary;
      slide.addShape('rect', shapeOpts({
        x: railX,
        y,
        w: 0.04,
        h: sectionH,
        fill: { color: accent },
        line: { color: accent, width: 0 },
      }));
      slide.addText(model.title, textOpts({
        x: railX + 0.14,
        y,
        w: railW - 0.14,
        h: 0.25,
        fontFace: preset.font_heading,
        fontSize: 11,
        bold: true,
        color: accent,
      }));
      if (model.lines.length) {
        slide.addText(model.lines.join('\n'), textOpts({
          x: railX + 0.14,
          y: y + 0.31,
          w: railW - 0.14,
          h: Math.max(0.35, sectionH - 0.34),
          fontFace: preset.font_body,
          fontSize: sectionH < 0.92 ? 8.5 : 9.5,
          color: preset.text,
          breakLine: false,
          fit: 'shrink',
          valign: 'top',
        }));
      }
      y += sectionH + sectionGap;
    });
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

function normalizeSidebarSections(slideData) {
  const sections = Array.isArray(slideData.sidebar_sections)
    ? slideData.sidebar_sections.filter((s) => s && typeof s === 'object')
    : [];
  if (sections.length) return sections.slice(0, 4);

  const fallback = [];
  const body = safeText(slideData.body);
  const bullets = normalizeBullets(slideData.bullets).map((b) => b.text);
  const highlights = Array.isArray(slideData.highlights)
    ? slideData.highlights.map((h) => safeText(h)).filter(Boolean)
    : [];
  if (body) fallback.push({ title: 'Readout', body });
  if (bullets.length) fallback.push({ title: 'Key results', body: bullets.slice(0, 4) });
  if (highlights.length) fallback.push({ title: 'Interpretation', body: highlights.slice(0, 4) });
  if (!fallback.length) {
    fallback.push({ title: 'Figure note', body: 'Add sidebar_sections to explain the visual.' });
  }
  return fallback.slice(0, 4);
}

function sectionBodyLines(section) {
  const raw = section && section.body;
  if (Array.isArray(raw)) return raw.map((v) => safeText(v)).filter(Boolean);
  const text = safeText(raw || (section && section.text));
  if (!text) return [];
  return text
    .split(/\n|(?<=\.)\s+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 4);
}

function renderImageSidebar(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  const header = addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle, slideData);

  const imagePath = slideData.__heroPath || slideData.__generatedImagePath;
  const hasImage = imagePath && fs.existsSync(imagePath);
  const sections = normalizeSidebarSections(slideData);
  const imageSide = String(slideData.image_side || 'left').trim().toLowerCase() === 'right'
    ? 'right'
    : 'left';

  const contentY = header.contentTop + 0.18;
  const hasFooter = !!(safeText(slideData.footer) || (Array.isArray(slideData.sources) && slideData.sources.length));
  const caption = safeText(slideData.caption);
  const captionH = caption ? (caption.length > 95 ? 0.28 : 0.22) : 0;
  const footerReserve = hasFooter ? 0.55 : 0.18;
  const contentH = SLIDE_H - contentY - footerReserve - captionH - (caption ? 0.10 : 0);
  const usableW = SLIDE_W - MARGIN_X * 2;
  const gutter = 0.30;
  const imageW = hasImage ? usableW * 0.56 : 0;
  const sidebarW = hasImage ? usableW - imageW - gutter : usableW;
  const imageX = imageSide === 'left' ? MARGIN_X : MARGIN_X + sidebarW + gutter;
  const sidebarX = imageSide === 'left' ? MARGIN_X + imageW + gutter : MARGIN_X;

  if (hasImage) {
    slide.addShape('rect', shapeOpts({
      x: imageX,
      y: contentY,
      w: imageW,
      h: contentH,
      fill: { color: preset.surface || 'FFFFFF' },
      line: { color: preset.line, width: 0.75 },
    }));
    const sized = imageSizingContainLocal(imagePath, imageX + 0.06, contentY + 0.06, imageW - 0.12, contentH - 0.12);
    slide.addImage(Object.assign({ path: imagePath }, sized));
  }

  const sectionGap = 0.10;
  const sectionCount = Math.max(1, sections.length);
  const sectionH = (contentH - sectionGap * (sectionCount - 1)) / sectionCount;
  const iconPaths = Array.isArray(slideData.__iconPaths) ? slideData.__iconPaths : [];
  sections.forEach((section, idx) => {
    const y = contentY + idx * (sectionH + sectionGap);
    const title = safeText(section.title || section.label, idx === 0 ? 'Figure note' : `Note ${idx + 1}`);
    const lines = sectionBodyLines(section);
    const accent = idx % 2 === 0 ? preset.accent_primary : preset.accent_secondary;

    slide.addShape('rect', shapeOpts({
      x: sidebarX,
      y,
      w: 0.04,
      h: sectionH,
      fill: { color: accent },
      line: { color: accent, width: 0 },
    }));
    const iconPath = iconPaths[idx];
    const sectionIconSize = 0.18;
    const hasSectionIcon = iconPath && fs.existsSync(iconPath);
    if (hasSectionIcon) {
      slide.addImage({
        path: iconPath,
        x: sidebarX + 0.14,
        y: y + 0.02,
        w: sectionIconSize,
        h: sectionIconSize,
      });
    }
    slide.addText(title, textOpts({
      x: sidebarX + (hasSectionIcon ? 0.38 : 0.14),
      y,
      w: sidebarW - (hasSectionIcon ? 0.38 : 0.14),
      h: 0.24,
      fontFace: preset.font_heading,
      fontSize: 12,
      bold: true,
      color: accent,
    }));
    if (lines.length) {
      const bodyText = lines.join('\n');
      const bodyBoxH = Math.min(
        Math.max(0.35, sectionH - 0.32),
        Math.max(0.36, estimateTextHeight(bodyText, 8.8, sidebarW - 0.14, 1.25) + 0.14),
      );
      slide.addText(lines.map((line, i) => ({
        text: line,
        options: {
          bullet: { code: '2022' },
          breakLine: i < lines.length - 1,
        },
      })), textOpts({
        x: sidebarX + 0.14,
        y: y + 0.30,
        w: sidebarW - 0.14,
        h: bodyBoxH,
        fontFace: preset.font_body,
        fontSize: 8.8,
        color: preset.text,
        valign: 'top',
        paraSpaceAfter: 3,
        fit: 'shrink',
      }));
    }
  });

  if (caption) {
    const captionY = hasFooter
      ? Math.min(contentY + contentH + 0.10, SLIDE_H - 0.84)
      : contentY + contentH + 0.10;
    slide.addText(caption, textOpts({
      x: MARGIN_X,
      y: captionY,
      w: usableW,
      h: captionH,
      fontFace: preset.font_body,
      fontSize: 8.5,
      color: preset.text_muted,
      italic: true,
    }));
  }

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

function normalizeFigures(slideData) {
  const raw = Array.isArray(slideData.figures)
    ? slideData.figures
    : (slideData.assets && Array.isArray(slideData.assets.figures))
      ? slideData.assets.figures
      : [];
  const paths = Array.isArray(slideData.__figurePaths) ? slideData.__figurePaths : [];
  return raw.slice(0, 4).map((item, idx) => {
    const spec = typeof item === 'string' ? { path: item } : (item || {});
    return {
      path: paths[idx] || '',
      label: safeText(spec.label, String.fromCharCode(65 + idx)),
      title: safeText(spec.title || spec.heading),
      caption: safeText(spec.caption || spec.note),
    };
  }).filter((item) => item.path && fs.existsSync(item.path));
}

function renderScientificFigure(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  const header = addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle, slideData);
  const figures = normalizeFigures(slideData);
  if (!figures.length) {
    renderImageSidebar(pptx, slide, slideData, preset);
    return;
  }

  const caption = safeText(slideData.caption || slideData.figure_caption);
  const interpretation = safeText(slideData.interpretation || slideData.takeaway);
  const hasFooter = !!(safeText(slideData.footer) || (Array.isArray(slideData.sources) && slideData.sources.length));
  const bottomText = [caption, interpretation].filter(Boolean).join('\n');
  const bottomReserve = bottomText ? 0.62 : 0.18;
  const footerReserve = hasFooter ? 0.50 : 0.12;
  const topY = header.contentTop + 0.16;
  const gridH = SLIDE_H - topY - bottomReserve - footerReserve;
  const usableW = SLIDE_W - MARGIN_X * 2;
  const gap = 0.30;
  const count = Math.min(figures.length, 4);
  const cols = count === 1 ? 1 : 2;
  const rows = count <= 2 ? 1 : 2;
  const panelW = (usableW - gap * (cols - 1)) / cols;
  const panelH = (gridH - gap * (rows - 1)) / rows;

  figures.slice(0, count).forEach((figure, idx) => {
    const row = Math.floor(idx / cols);
    const col = idx % cols;
    const x = MARGIN_X + col * (panelW + gap);
    const y = topY + row * (panelH + gap);
    slide.addShape('rect', shapeOpts({
      x,
      y,
      w: panelW,
      h: panelH,
      fill: { color: preset.surface || 'FFFFFF' },
      line: { color: preset.line || 'CBD5E1', width: 0.75 },
    }));
    slide.addShape('rect', shapeOpts({
      x,
      y,
      w: panelW,
      h: 0.05,
      fill: { color: preset.bg_dark || '0F172A' },
      line: { color: preset.bg_dark || '0F172A', width: 0 },
    }));
    const heading = figure.title ? `${figure.label}. ${figure.title}` : figure.label;
    const titleH = heading ? 0.22 : 0;
    slide.addText(heading, textOpts({
      x: x + 0.08,
      y: y + 0.09,
      w: panelW - 0.16,
      h: titleH,
      fontFace: preset.font_heading,
      fontSize: 8.5,
      bold: true,
      color: preset.text || preset.text_primary,
      fit: 'shrink',
    }));
    const figCaptionH = figure.caption ? (figure.caption.length > 90 ? 0.28 : 0.22) : 0;
    const imageY = y + 0.12 + titleH;
    const imageH = panelH - (imageY - y) - figCaptionH - 0.08;
    const sized = imageSizingContainLocal(figure.path, x + 0.06, imageY, panelW - 0.12, imageH);
    slide.addImage(Object.assign({ path: figure.path }, sized));
    if (figure.caption) {
      slide.addText(figure.caption, textOpts({
        x: x + 0.08,
        y: y + panelH - figCaptionH - 0.04,
        w: panelW - 0.16,
        h: figCaptionH,
        fontFace: preset.font_caption || preset.font_body,
        fontSize: 8.2,
        color: preset.text_muted,
        italic: true,
        fit: 'shrink',
      }));
    }
  });

  if (bottomText) {
    const bottomY = topY + gridH + 0.12;
    slide.addShape('rect', shapeOpts({
      x: MARGIN_X,
      y: bottomY,
      w: usableW,
      h: bottomReserve - 0.16,
      fill: { color: preset.surface || 'FFFFFF' },
      line: { color: preset.line || 'CBD5E1', width: 0.5 },
    }));
    slide.addText(bottomText, textOpts({
      x: MARGIN_X + 0.14,
      y: bottomY + 0.08,
      w: usableW - 0.28,
      h: bottomReserve - 0.30,
      fontFace: preset.font_body,
      fontSize: 8.2,
      color: preset.text || preset.text_primary,
      fit: 'shrink',
    }));
  }

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

function renderGeneratedImage(pptx, slide, slideData, preset) {
  paintBackground(slide, preset.bg);
  const header = addDarkTitleBar(slide, preset, slideData.title, slideData.subtitle, slideData);

  const imagePath = slideData.__generatedImagePath || slideData.__heroPath;
  const contentY = header.contentTop + 0.24;
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
    `Model: ${truncate(safeText(meta.model, 'OpenAI image model'), 56)}`,
    `Purpose: ${truncate(safeText(meta.purpose, 'Concept visual'), 76)}`,
    'Standalone disclosure slide. Delete if source imagery is preferred.',
  ];
  const prompt = safeText(meta.prompt) || safeText(meta.revised_prompt);
  if (prompt) details.push(`Prompt: ${truncate(prompt, 120)}`);

  slide.addText(details.map((line, i) => ({
    text: line,
    options: {
      fontFace: preset.font_body,
      fontSize: i === 0 ? 9 : 8.5,
      color: 'FFFFFF',
      breakLine: i < details.length - 1,
      paraSpaceAfter: 4,
    },
  })), textOpts({
    x: panelX + 0.20,
    y: contentY + 0.62,
    w: panelW - 0.40,
    h: contentH - 0.74,
    fontFace: preset.font_body,
    fontSize: 8.5,
    color: 'FFFFFF',
    valign: 'top',
    fit: 'shrink',
  }));

  addFooter(slide, preset, slideData);
  attachNotes(slide, slideData);
}

function addSummaryCallout(pptx, slide, slideData, preset) {
  const text = String(slideData.summary_callout || slideData.key_summary || slideData.takeaway || '').trim();
  if (!text) return;
  const hasFooter = !!(String(slideData.footer || '').trim());
  const mode = String(slideData.summary_callout_mode || preset.summary_callout_mode || '').trim().toLowerCase();
  const labBox = mode === 'lab-box';
  const footerReserve = hasFooter ? 0.40 : 0.36;
  const calloutH = labBox ? 0.44 : 0.62;
  const calloutY = SLIDE_H - footerReserve - calloutH;
  const calloutW = SLIDE_W - MARGIN_X * 2.2;
  const calloutX = MARGIN_X * 1.1;
  const accent = preset.accent_primary || '14B8A6';
  if (labBox) {
    const y = SLIDE_H - FOOTER_H - calloutH - 0.12;
    slide.addShape('rect', shapeOpts({
      x: MARGIN_X,
      y,
      w: SLIDE_W - MARGIN_X * 2,
      h: calloutH,
      fill: { color: preset.surface || 'FFFFFF' },
      line: { color: preset.line || 'D1D5DB', width: 0.55 },
    }));
    slide.addShape('rect', shapeOpts({
      x: MARGIN_X,
      y,
      w: 0.055,
      h: calloutH,
      fill: { color: accent },
      line: { color: accent, width: 0 },
    }));
    slide.addText(text, textOpts({
      x: MARGIN_X + 0.14,
      y: y + 0.06,
      w: SLIDE_W - MARGIN_X * 2 - 0.28,
      h: calloutH - 0.12,
      fontFace: preset.font_body,
      fontSize: text.length > 150 ? 8.2 : 9.2,
      bold: true,
      color: preset.text || preset.text_primary || '0F172A',
      valign: 'middle',
      fit: 'shrink',
    }));
    return;
  }
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
  renderLabRunResults,
  renderComparison2col,
  renderMatrix,
  renderFlow,
  renderImageSidebar,
  renderScientificFigure,
  renderGeneratedImage,
  addSummaryCallout,
};
