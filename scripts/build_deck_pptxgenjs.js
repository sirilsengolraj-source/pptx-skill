#!/usr/bin/env node
/*
 * pptxgenjs peer renderer for the presentation-skill outline.json format.
 *
 * Reads the same outline.json as scripts/build_deck.py and emits a .pptx
 * using pptxgenjs directly -- no Playwright and no html2pptx.
 *
 * CLI:
 *   node scripts/build_deck_pptxgenjs.js \
 *     --outline deck.json \
 *     --output  out.pptx \
 *     --style-preset executive-clinical
 *
 * Supported slide types:
 *   - title
 *   - section
 *   - content variants: standard, cards-2/3, split, timeline, stats,
 *     kpi-hero, table, lab-run-results, comparison-2col, matrix, flow,
 *     image-sidebar, scientific-figure, generated-image.
 *
 * Native chart slides are still routed to build_deck.py by workspace auto
 * selection because python-pptx owns the OOXML chart path.
 */

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');
const Module = require('module');

// ---------------------------------------------------------------------------
// Make pptxgenjs resolvable even when node_modules lives outside the skill.
// ---------------------------------------------------------------------------
function configureNodePath() {
  const sep = path.delimiter;
  const existing = String(process.env.NODE_PATH || '')
    .split(sep)
    .map((s) => s.trim())
    .filter(Boolean);
  const candidates = [
    process.env.PPTX_NODE_MODULES || '',
    path.resolve(__dirname, '..', 'node_modules'),
    path.resolve(process.cwd(), 'node_modules'),
    path.resolve(os.homedir(), 'codex', 'CascadeProjects', 'pptx_ab_comparison', 'node_modules'),
  ].filter(Boolean);
  let changed = false;
  for (const candidate of candidates) {
    if (!candidate || !fs.existsSync(candidate)) continue;
    if (existing.includes(candidate)) continue;
    existing.push(candidate);
    changed = true;
  }
  if (changed) {
    process.env.NODE_PATH = existing.join(sep);
    Module._initPaths();
  }
}
configureNodePath();

let PptxGenJS;
try {
  PptxGenJS = require('pptxgenjs');
} catch (err) {
  console.error(
    'Error: missing dependency "pptxgenjs". Install with: npm install pptxgenjs\n' +
      'Or set PPTX_NODE_MODULES to a directory that contains it.',
  );
  process.exit(2);
}

const TEMPLATES_DIR = path.resolve(__dirname, '..', 'templates', 'pptxgenjs');
const { getPreset, DEFAULT_PRESET_NAME, listPresets } = require(path.join(TEMPLATES_DIR, 'presets.js'));
const slides = require(path.join(TEMPLATES_DIR, 'slides.js'));

// ---------------------------------------------------------------------------
// CLI parsing
// ---------------------------------------------------------------------------

function parseArgs(argv) {
  const args = {
    outline: '',
    output: '',
    stylePreset: DEFAULT_PRESET_NAME,
  };
  for (let i = 2; i < argv.length; i += 1) {
    const tok = argv[i];
    const next = () => {
      const v = argv[i + 1];
      i += 1;
      return v;
    };
    switch (tok) {
      case '-h':
      case '--help':
        printUsage();
        process.exit(0);
        break;
      case '--outline':
        args.outline = next();
        break;
      case '--output':
        args.output = next();
        break;
      case '--style-preset':
        args.stylePreset = next();
        break;
      default:
        if (tok.startsWith('--outline=')) args.outline = tok.slice('--outline='.length);
        else if (tok.startsWith('--output=')) args.output = tok.slice('--output='.length);
        else if (tok.startsWith('--style-preset=')) args.stylePreset = tok.slice('--style-preset='.length);
        else {
          console.error(`Unknown argument: ${tok}`);
          printUsage();
          process.exit(2);
        }
    }
  }
  return args;
}

function printUsage() {
  const usage = [
    'Usage: node scripts/build_deck_pptxgenjs.js \\',
    '         --outline <path/to/outline.json> \\',
    '         --output  <path/to/out.pptx> \\',
    '         [--style-preset executive-clinical]',
    '',
    `Presets: ${listPresets().join(' | ')}`,
  ].join('\n');
  console.log(usage);
}

// ---------------------------------------------------------------------------
// Outline loading
// ---------------------------------------------------------------------------

function loadOutline(outlinePath) {
  const resolved = path.resolve(outlinePath);
  if (!fs.existsSync(resolved)) {
    throw new Error(`outline not found: ${resolved}`);
  }
  const raw = fs.readFileSync(resolved, 'utf8');
  let data;
  try {
    data = JSON.parse(raw);
  } catch (err) {
    throw new Error(`outline is not valid JSON (${resolved}): ${err.message}`);
  }
  if (!data || typeof data !== 'object') {
    throw new Error(`outline root must be an object`);
  }
  const slideList = Array.isArray(data.slides) ? data.slides : [];
  if (!slideList.length) {
    throw new Error(`outline has no slides`);
  }
  return {
    data,
    slideList,
    outlineDir: path.dirname(resolved),
  };
}

const STAGED_LOOKUP_CACHE = new Map();

function stagedAssetLookup(outlineDir) {
  const manifestPath = path.resolve(outlineDir, 'assets', 'staged', 'staged_manifest.json');
  if (STAGED_LOOKUP_CACHE.has(manifestPath)) return STAGED_LOOKUP_CACHE.get(manifestPath);
  const lookup = new Map();
  if (fs.existsSync(manifestPath)) {
    try {
      const payload = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
      const sections = [
        ['images', ['asset', 'image']],
        ['backgrounds', ['asset', 'background']],
        ['charts', ['asset', 'chart']],
        ['generated_images', ['asset', 'image', 'generated']],
      ];
      for (const [section, prefixes] of sections) {
        const entries = Array.isArray(payload[section]) ? payload[section] : [];
        for (const entry of entries) {
          if (!entry || typeof entry !== 'object') continue;
          const name = String(entry.name || '').trim().toLowerCase();
          const assetPath = String(entry.path || '').trim();
          if (!name || !assetPath) continue;
          for (const prefix of prefixes) {
            lookup.set(`${prefix}:${name}`, assetPath);
          }
        }
      }
    } catch (err) {
      console.warn(`[pptxgenjs] failed to read staged manifest ${manifestPath}: ${err.message}`);
    }
  }
  STAGED_LOOKUP_CACHE.set(manifestPath, lookup);
  return lookup;
}

// Resolve an image path or staged alias against the outline directory.
function resolveAssetPath(p, outlineDir) {
  if (!p) return '';
  const raw = String(p).trim();
  const normalized = raw.toLowerCase();
  if (/^(asset|image|background|chart|generated):/.test(normalized)) {
    const staged = stagedAssetLookup(outlineDir).get(normalized);
    if (!staged) {
      console.warn(`[pptxgenjs] staged asset alias not found: ${raw}`);
      return '';
    }
    return path.isAbsolute(staged) ? staged : path.resolve(outlineDir, staged);
  }
  const abs = path.isAbsolute(raw) ? raw : path.resolve(outlineDir, raw);
  return abs;
}

function parseCsvLine(line) {
  const cells = [];
  let current = '';
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"' && quoted && line[i + 1] === '"') {
      current += '"';
      i += 1;
    } else if (ch === '"') {
      quoted = !quoted;
    } else if (ch === ',' && !quoted) {
      cells.push(current);
      current = '';
    } else {
      current += ch;
    }
  }
  cells.push(current);
  return cells;
}

function readCsv(pathname) {
  if (!pathname || !fs.existsSync(pathname)) return [];
  const lines = fs.readFileSync(pathname, 'utf8').split(/\r?\n/).filter((line) => line.trim());
  if (lines.length < 2) return [];
  const headers = parseCsvLine(lines[0]).map((h) => h.trim());
  return lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    const row = {};
    headers.forEach((header, idx) => {
      row[header] = String(values[idx] || '').trim();
    });
    return row;
  });
}

function attributionPath(data, outlineDir) {
  const compliance = (data && data.compliance && typeof data.compliance === 'object')
    ? data.compliance
    : {};
  const raw = String(compliance.attribution_file || 'assets/attribution.csv').trim();
  return path.isAbsolute(raw) ? raw : path.resolve(outlineDir, raw);
}

function isSourceBackedRow(row) {
  const license = String(row.license || '').trim().toLowerCase();
  const sourcePage = String(row.source_page || '').trim();
  const imageUrl = String(row.image_url || '').trim();
  if (!license && !sourcePage && !imageUrl) return false;
  if (license === 'generated asset') return false;
  return /^https?:/i.test(sourcePage) || /^https?:/i.test(imageUrl) || license.startsWith('cc') || license.includes('public');
}

function compactUrl(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  try {
    const u = new URL(raw);
    const tail = u.pathname.split('/').filter(Boolean).pop() || '';
    return `${u.hostname}/${decodeURIComponent(tail).slice(0, 46)}`;
  } catch (_err) {
    return raw.slice(0, 62);
  }
}

function trimCell(value, limit) {
  const raw = String(value || '').replace(/\s+/g, ' ').trim();
  if (raw.length <= limit) return raw;
  return `${raw.slice(0, Math.max(4, limit - 1)).trim()}…`;
}

function hasImageSourcesSlide(slideList) {
  return slideList.some((slide) => {
    if (!slide || typeof slide !== 'object') return false;
    const variant = String(slide.variant || '').trim().toLowerCase();
    const title = String(slide.title || '').trim().toLowerCase();
    return variant === 'image-sources' || title === 'image sources' || title === 'asset sources';
  });
}

function withAutoImageSourcesSlide(slideList, data, outlineDir) {
  const compliance = (data && data.compliance && typeof data.compliance === 'object')
    ? data.compliance
    : {};
  if (compliance.auto_image_sources === false) return slideList;
  if (hasImageSourcesSlide(slideList)) return slideList;

  const rows = readCsv(attributionPath(data, outlineDir)).filter(isSourceBackedRow);
  if (!rows.length) return slideList;

  const visibleRows = rows.slice(0, 8).map((row) => {
    const title = row.title || row.file_name || 'Source-backed image';
    const credit = row.artist || row.credit || 'Wikimedia Commons';
    const license = row.license || 'source-backed';
    const source = row.source_page || row.image_url || '';
    return [
      trimCell(title, 42),
      trimCell(credit, 50),
      trimCell(`${license} · ${compactUrl(source)}`, 72),
    ];
  });
  const caption = rows.length > visibleRows.length
    ? `Showing first ${visibleRows.length} of ${rows.length} source-backed assets. Full attribution: assets/attribution.csv.`
    : 'Full attribution metadata is stored in assets/attribution.csv.';

  return slideList.concat([
    {
      type: 'content',
      variant: 'table',
      title: 'Image Sources',
      subtitle: 'Source-backed assets used in this deck',
      headers: ['Asset', 'Credit', 'License / source'],
      rows: visibleRows,
      column_weights: [1.25, 1.35, 1.70],
      caption,
      footer_mode: 'source-line',
      footer: 'Automatically generated from asset attribution metadata',
      sources: ['assets/attribution.csv'],
    },
  ]);
}

// ---------------------------------------------------------------------------
// Slide dispatch
// ---------------------------------------------------------------------------

const CONTENT_VARIANTS = new Set([
  'standard',
  'cards-2',
  'cards-3',
  'split',
  'timeline',
  'stats',
  'kpi-hero',
  'table',
  'lab-run-results',
  'comparison-2col',
  'matrix',
  'flow',
  'image-sidebar',
  'scientific-figure',
  'generated-image',
]);

// Variants we know we don't handle in v1. Fall back to 'standard' with a warn.
const UNSUPPORTED_VARIANTS = new Set([
  'chart',
  'hero',
  'comparison',
]);

const FONT_PAIRS = {
  system_clean_v1: {
    font_heading: 'Trebuchet MS',
    font_body: 'Calibri',
  },
  editorial_serif_v1: {
    font_heading: 'Georgia',
    font_body: 'Calibri',
  },
  clean_modern_v1: {
    font_heading: 'Helvetica Neue',
    font_body: 'Helvetica Neue',
  },
};

const PRESET_TREATMENTS = {
  'executive-clinical': {
    header_mode: 'bar',
    title_layout: 'split-hero',
    title_motif: 'orbit',
    section_motif: 'rail-dots',
    timeline_mode: 'staggered',
    matrix_mode: 'cards',
    stats_mode: 'feature-left',
    cards_mode: 'feature-left',
  },
  'data-heavy-boardroom': {
    header_mode: 'eyebrow',
    title_layout: 'split-hero',
    title_motif: 'network',
    section_motif: 'rail-dots',
    timeline_mode: 'open-events',
    matrix_mode: 'open-quadrants',
    stats_mode: 'policy-bands',
    cards_mode: 'feature-left',
  },
  'forest-research': {
    header_mode: 'stack',
    title_layout: 'light-atlas',
    title_motif: 'editorial',
    section_motif: 'rail-dots',
    timeline_mode: 'open-events',
    matrix_mode: 'open-quadrants',
    stats_mode: 'policy-bands',
    cards_mode: 'staggered-row',
  },
  'sunset-investor': {
    header_mode: 'bar',
    title_layout: 'poster',
    title_motif: 'orbit',
    section_motif: 'rail-dots',
    timeline_mode: 'chapter-spread',
    matrix_mode: 'open-quadrants',
    stats_mode: 'feature-left',
    cards_mode: 'feature-left',
  },
  'lavender-ops': {
    header_mode: 'eyebrow',
    title_layout: 'command-center',
    title_motif: 'network',
    section_motif: 'rail-dots',
    timeline_mode: 'bands',
    matrix_mode: 'cards',
    stats_mode: 'policy-bands',
    cards_mode: 'staggered-row',
  },
  'warm-terracotta': {
    header_mode: 'stack',
    title_layout: 'masthead',
    title_motif: 'editorial',
    section_motif: 'rail-dots',
    timeline_mode: 'bands',
    matrix_mode: 'open-quadrants',
    stats_mode: 'policy-bands',
    cards_mode: 'staggered-row',
  },
  'paper-journal': {
    header_mode: 'stack',
    title_layout: 'masthead',
    title_motif: 'editorial',
    section_motif: 'rail-dots',
    timeline_mode: 'open-events',
    title_subtitle_color: 'D9CBA8',
    section_subtitle_color: 'EFE5D0',
  },
  'editorial-minimal': {
    header_mode: 'stack',
    title_layout: 'masthead',
    title_motif: 'editorial',
    section_motif: 'rail-dots',
    timeline_mode: 'open-events',
    title_subtitle_color: 'E5E7EB',
    section_subtitle_color: 'E5E7EB',
  },
  'arctic-minimal': {
    header_mode: 'eyebrow',
    title_layout: 'light-atlas',
    title_motif: 'orbit',
    section_motif: 'rail-dots',
    matrix_mode: 'open-quadrants',
    stats_mode: 'policy-bands',
  },
  'bold-startup-narrative': {
    header_mode: 'bar',
    title_layout: 'poster',
    title_motif: 'orbit',
    section_motif: 'rail-dots',
    timeline_mode: 'chapter-spread',
    cards_mode: 'feature-left',
  },
  'charcoal-safety': {
    header_mode: 'bar',
    title_layout: 'command-center',
    title_motif: 'network',
    section_motif: 'rail-dots',
    stats_mode: 'feature-left',
    timeline_mode: 'bands',
    title_subtitle_color: 'D1D5DB',
    section_subtitle_color: 'E5E7EB',
  },
  'midnight-neon': {
    header_mode: 'bar',
    title_layout: 'command-center',
    title_motif: 'network',
    section_motif: 'rail-dots',
    timeline_mode: 'chapter-spread',
    cards_mode: 'feature-left',
  },
  'lab-report': {
    header_mode: 'lab-clean',
    footer_mode: 'source-line',
    footer_page_numbers: true,
    summary_callout_mode: 'lab-box',
    title_layout: 'lab-plate',
    title_motif: 'none',
    section_motif: 'none',
    title_subtitle_color: 'D6E4F0',
    section_subtitle_color: 'D6E4F0',
  },
};

function applyDeckStyle(basePreset, data, presetName) {
  const preset = Object.assign({}, basePreset);
  const treatment = PRESET_TREATMENTS[String(presetName || '').trim().toLowerCase()] || {};
  Object.assign(preset, treatment);

  const deckStyle = (data && data.deck_style && typeof data.deck_style === 'object')
    ? data.deck_style
    : {};
  const fontPairKey = String(deckStyle.font_pair || '').trim();
  const fontPair = FONT_PAIRS[fontPairKey];
  if (fontPair) {
    preset.font_heading = fontPair.font_heading;
    preset.font_body = fontPair.font_body;
    preset.font_title = fontPair.font_heading;
    preset.font_caption = fontPair.font_body;
  }

  const visualDensity = String(deckStyle.visual_density || 'medium').trim().toLowerCase();
  if (['low', 'medium', 'high'].includes(visualDensity)) {
    preset.visual_density = visualDensity;
  }

  for (const key of [
    'header_mode',
    'title_layout',
    'title_motif',
    'section_motif',
    'timeline_mode',
    'matrix_mode',
    'stats_mode',
    'cards_mode',
    'footer_mode',
    'summary_callout_mode',
  ]) {
    if (deckStyle[key]) preset[key] = String(deckStyle[key]).trim().toLowerCase();
  }
  if (deckStyle.footer_page_numbers !== undefined) {
    preset.footer_page_numbers = Boolean(deckStyle.footer_page_numbers);
  }
  return preset;
}

// Pre-render a mermaid source file to PNG using the existing Python helper.
// Returns an absolute path to the PNG, or '' on failure.
function preRenderMermaid(sourcePath, outlineDir) {
  const abs = resolveAssetPath(sourcePath, outlineDir);
  if (!abs || !fs.existsSync(abs)) return '';
  const target = abs.replace(/\.(mmd|mermaid)$/i, '.png');
  const script = path.resolve(__dirname, 'render_mermaid.py');
  // Skip re-render if the PNG is already newer than the source.
  try {
    const targetMtime = fs.existsSync(target) ? fs.statSync(target).mtimeMs : 0;
    const sourceMtime = fs.statSync(abs).mtimeMs;
    const scriptMtime = fs.existsSync(script) ? fs.statSync(script).mtimeMs : 0;
    if (fs.existsSync(target) &&
        targetMtime >= sourceMtime &&
        targetMtime >= scriptMtime) {
      return target;
    }
  } catch (_e) {}
  if (!fs.existsSync(script)) {
    console.warn('[pptxgenjs] render_mermaid.py missing; skipping mermaid for', abs);
    return '';
  }
  const r = spawnSync('python3', [script, '--input', abs, '--output', target], {
    stdio: ['ignore', 'pipe', 'pipe'],
    encoding: 'utf8',
  });
  if (r.status === 0 && fs.existsSync(target)) return target;
  console.warn('[pptxgenjs] mermaid render failed for', abs, '-', (r.stderr || r.stdout || '').slice(0, 200));
  return '';
}

function normalizeSlide(spec, outlineDir) {
  const out = Object.assign({}, spec);
  out.type = String(spec.type || 'content').trim().toLowerCase();
  if (out.type === 'text') out.type = 'content';
  out.variant = String(spec.variant || 'standard').trim().toLowerCase();
  if (spec.background_image) {
    out.background_image = resolveAssetPath(spec.background_image, outlineDir);
  }

  // Resolve asset-family paths and pre-render mermaid to PNG.
  const assets = (spec.assets && typeof spec.assets === 'object') ? spec.assets : {};
  if (assets.hero_image || assets.image) {
    out.__heroPath = resolveAssetPath(assets.hero_image || assets.image, outlineDir);
  }
  if (assets.generated_image) {
    out.__generatedImagePath = resolveAssetPath(assets.generated_image, outlineDir);
  }
  const mermaidSrc = assets.mermaid_source || assets.mermaid;
  if (mermaidSrc) {
    const rendered = preRenderMermaid(mermaidSrc, outlineDir);
    if (rendered) out.__mermaidPath = rendered;
  }
  if (assets.diagram) {
    const p = resolveAssetPath(assets.diagram, outlineDir);
    if (p && fs.existsSync(p)) out.__diagramPath = p;
  }
  const figureSpecs = Array.isArray(spec.figures)
    ? spec.figures
    : Array.isArray(assets.figures)
      ? assets.figures
      : [];
  if (figureSpecs.length) {
    out.__figurePaths = figureSpecs.map((item) => {
      if (!item) return '';
      const raw = typeof item === 'string'
        ? item
        : (item.path || item.image || item.src || item.asset || '');
      const p = resolveAssetPath(raw, outlineDir);
      return p && fs.existsSync(p) ? p : '';
    });
  }

  // If a slide has a flow diagram image (rendered mermaid or supplied
  // diagram), promote it to a synthesized 'flow' variant so renderSlide
  // can dispatch to a diagram-aware renderer. Preserve original variant
  // for downstream metadata in case callers want it.
  const hasFlow = out.__mermaidPath || out.__diagramPath;
  if (hasFlow && (out.variant === 'standard' || out.variant === 'content' || out.variant === 'flow')) {
    out.variant = 'flow';
  }
  const visualIntent = String(out.visual_intent || '').trim().toLowerCase();
  if (out.type === 'content' && (out.variant === 'standard' || out.variant === 'content')) {
    if (Array.isArray(out.cards) && out.cards.length >= 2) {
      out.variant = out.cards.length >= 3 ? 'cards-3' : 'cards-2';
    } else if (Array.isArray(out.milestones) && out.milestones.length >= 2) {
      out.variant = 'timeline';
    } else if (Array.isArray(out.quadrants) && out.quadrants.length >= 4) {
      out.variant = 'matrix';
    } else if (Array.isArray(out.facts) && out.facts.length >= 2) {
      out.variant = 'stats';
    } else if (
      Array.isArray(out.headers) ||
      (out.table && Array.isArray(out.table.headers)) ||
      (Array.isArray(out.rows) && out.rows.length)
    ) {
      out.variant = 'table';
    } else if (visualIntent === 'timeline' && Array.isArray(out.milestones) && out.milestones.length >= 2) {
      out.variant = 'timeline';
    } else if (
      visualIntent === 'comparison' &&
      out.left && typeof out.left === 'object' &&
      out.right && typeof out.right === 'object'
    ) {
      out.variant = 'comparison-2col';
    } else if (
      visualIntent === 'data' &&
      (Array.isArray(out.headers) || (out.table && Array.isArray(out.table.headers)))
    ) {
      out.variant = 'table';
    }
  }
  if (
    out.type === 'content' &&
    out.__heroPath &&
    fs.existsSync(out.__heroPath) &&
    out.variant !== 'generated-image' &&
    (
      out.variant === 'image-sidebar' ||
      ['hero', 'image', 'figure'].includes(String(out.visual_intent || '').trim().toLowerCase())
    )
  ) {
    out.variant = 'image-sidebar';
  }
  return out;
}

function renderSlide(pptx, pSlide, slide, preset) {
  const t = slide.type;

  if (t === 'title') {
    slides.renderTitle(pptx, pSlide, slide, preset);
    return;
  }
  if (t === 'section') {
    slides.renderSection(pptx, pSlide, slide, preset);
    return;
  }

  // Skip the universal summary callout when the variant already carries
  // its own bottom emphasis (kpi-hero IS the callout; comparison-2col
  // with a verdict already has a strip). Matches the python dispatcher.
  const variantForCallout = String(slide.variant || '').trim().toLowerCase();
  const hasVerdict = !!String(slide.verdict || '').trim();
  const skipCallout =
    variantForCallout === 'kpi-hero' ||
    variantForCallout === 'generated-image' ||
    (variantForCallout === 'comparison-2col' && hasVerdict);

  // content variants
  let variant = slide.variant;
  if (UNSUPPORTED_VARIANTS.has(variant)) {
    if (variant === 'matrix') {
      // Kept for older versions where matrix lived in UNSUPPORTED_VARIANTS.
      // Native matrix rendering is now implemented below.
      console.warn(
        `[pptxgenjs] matrix was unexpectedly marked unsupported; falling back to 'standard'.`,
      );
    } else {
      console.warn(
        `[pptxgenjs] variant '${variant}' is not implemented in v1; ` +
          `falling back to 'standard'. Use build_deck.py for that variant.`,
      );
    }
    variant = 'standard';
  }
  if (!CONTENT_VARIANTS.has(variant)) {
    console.warn(`[pptxgenjs] unknown variant '${variant}'; rendering as 'standard'.`);
    variant = 'standard';
  }

  switch (variant) {
    case 'cards-2':
      slides.renderCards(pptx, pSlide, slide, preset, 2);
      break;
    case 'cards-3':
      slides.renderCards(pptx, pSlide, slide, preset, 3);
      break;
    case 'split':
      slides.renderSplit(pptx, pSlide, slide, preset);
      break;
    case 'timeline':
      slides.renderTimeline(pptx, pSlide, slide, preset);
      break;
    case 'stats':
      slides.renderStats(pptx, pSlide, slide, preset);
      break;
    case 'kpi-hero':
      slides.renderKpiHero(pptx, pSlide, slide, preset);
      break;
    case 'table':
      slides.renderTable(pptx, pSlide, slide, preset);
      break;
    case 'lab-run-results':
      slides.renderLabRunResults(pptx, pSlide, slide, preset);
      break;
    case 'comparison-2col':
      slides.renderComparison2col(pptx, pSlide, slide, preset);
      break;
    case 'matrix':
      slides.renderMatrix(pptx, pSlide, slide, preset);
      break;
    case 'flow':
      slides.renderFlow(pptx, pSlide, slide, preset);
      break;
    case 'image-sidebar':
      slides.renderImageSidebar(pptx, pSlide, slide, preset);
      break;
    case 'scientific-figure':
      slides.renderScientificFigure(pptx, pSlide, slide, preset);
      break;
    case 'generated-image':
      slides.renderGeneratedImage(pptx, pSlide, slide, preset);
      break;
    case 'standard':
    default:
      slides.renderStandard(pptx, pSlide, slide, preset);
      break;
  }
  if (!skipCallout) {
    slides.addSummaryCallout(pptx, pSlide, slide, preset);
  }
}

// ---------------------------------------------------------------------------
// Icon pre-resolution: rasterize react-icons slugs to PNG before slide render.
// ---------------------------------------------------------------------------

// Shared cache dir — icon PNGs are content-addressable (same slug+color+size
// → same PNG), so sharing across slides and across runs is safe.
const ICON_CACHE_DIR = path.join(os.tmpdir(), 'presentation-skill-icon-cache');

function iconCacheKey(slug, color, size) {
  // Filesystem-safe filename: replace ':' → '__', '#' → '', lowercase.
  const safeSlug = String(slug).replace(/[^\w-]/g, '_');
  const safeColor = String(color || '000000').replace(/[^\w]/g, '').toLowerCase();
  return path.join(ICON_CACHE_DIR, `${safeSlug}_${safeColor}_${size}.png`);
}

async function rasterizeIcon(slug, color, size) {
  const outPath = iconCacheKey(slug, color, size);
  if (fs.existsSync(outPath)) return outPath;
  fs.mkdirSync(ICON_CACHE_DIR, { recursive: true });
  const [pack, exportName] = String(slug).split(':');
  if (!pack || !exportName) {
    throw new Error(`invalid icon slug "${slug}" (expected pack:ExportName)`);
  }
  const packageByPack = {
    fa6: 'react-icons/fa6',
    fa: 'react-icons/fa',
    bi: 'react-icons/bi',
    bs: 'react-icons/bs',
    md: 'react-icons/md',
    lu: 'react-icons/lu',
  };
  const packageName = packageByPack[pack];
  if (!packageName) {
    throw new Error(`unsupported icon pack "${pack}"`);
  }

  let React;
  let ReactDOMServer;
  let sharp;
  let iconModule;
  try {
    React = require('react');
    ReactDOMServer = require('react-dom/server');
    sharp = require('sharp');
    iconModule = require(packageName);
  } catch (err) {
    throw new Error(
      `missing optional icon deps (${err.message}). Run npm install once or use local PNG icons.`,
    );
  }

  const Icon = iconModule[exportName];
  if (!Icon) {
    throw new Error(`icon export "${exportName}" not found in ${packageName}`);
  }
  const cleanColor = String(color || '#000000').startsWith('#') ? String(color) : `#${color}`;
  let svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(Icon, { size, color: cleanColor, title: exportName }),
  );
  if (!/\sxmlns=/.test(svg)) {
    svg = svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');
  }
  await sharp(Buffer.from(svg)).png().toFile(outPath);
  return outPath;
}

async function resolveIconsForSlides(slides, outlineDir, preset) {
  // Resolve each slide's assets.icons array in parallel. Slugs with ':' are
  // react-icons; others are filenames and we leave them alone.
  const tasks = [];
  for (const slide of slides) {
    const assets = slide && slide.assets;
    if (!assets || !Array.isArray(assets.icons) || assets.icons.length === 0) continue;
    // Default icon color: accent_primary from preset. Individual slides can
    // override with assets.icons_color. Normalize so we always pass '#rrggbb'.
    const normHex = (v) => '#' + String(v || '').replace(/^#/, '');
    const defaultColor = normHex(preset.accent_primary || '14B8A6');
    const color = assets.icons_color ? normHex(assets.icons_color) : defaultColor;
    const resolved = new Array(assets.icons.length).fill('');
    slide.__iconPaths = resolved;
    for (let i = 0; i < assets.icons.length; i += 1) {
      const s = String(assets.icons[i] || '').trim();
      if (!s) continue;
      if (s.includes(':')) {
        // react-icons slug: pack:ExportName. Bind index in closure so the
        // promise writes to the correct slot.
        const idx = i;
        const paths = resolved;
        tasks.push(
          rasterizeIcon(s, color, 256)
            .then((p) => { paths[idx] = p; })
            .catch((err) => {
              console.warn(`[pptxgenjs] icon '${s}' failed: ${err.message}`);
              paths[idx] = '';
            })
        );
      } else {
        // Plain filename — resolve against outline dir.
        const p = path.isAbsolute(s) ? s : path.resolve(outlineDir, s);
        const withExt = /\.(png|jpg|jpeg|svg)$/i.test(p) ? p : p + '.png';
        resolved[i] = fs.existsSync(withExt) ? withExt : '';
      }
    }
  }
  await Promise.all(tasks);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const args = parseArgs(process.argv);
  if (!args.outline || !args.output) {
    printUsage();
    process.exit(2);
  }

  const { data, slideList, outlineDir } = loadOutline(args.outline);
  const preset = applyDeckStyle(getPreset(args.stylePreset), data, args.stylePreset);

  const pptx = new PptxGenJS();
  pptx.defineLayout({ name: 'PPTX_SKILL_16x9', width: slides.SLIDE_W, height: slides.SLIDE_H });
  pptx.layout = 'PPTX_SKILL_16x9';
  pptx.title = String(data.title || 'Deck');
  pptx.subject = String(data.subtitle || '');

  const slidesWithSources = withAutoImageSourcesSlide(slideList, data, outlineDir);
  const normalized = slidesWithSources.map((s) => normalizeSlide(s, outlineDir));
  normalized.forEach((slide, idx) => {
    slide.__slideIndex = idx + 1;
    slide.__slideCount = normalized.length;
  });

  // Pre-resolve icon slugs to PNG files. Slugs with a colon (e.g.
  // "fa6:FaLightbulb") are react-icons that we rasterize on-the-fly using
  // declared npm dependencies. Plain filenames pass through unchanged — the
  // python path's workspace lookup still works if Codex staged files.
  await resolveIconsForSlides(normalized, outlineDir, preset);

  for (const slide of normalized) {
    const pSlide = pptx.addSlide();
    renderSlide(pptx, pSlide, slide, preset);
  }

  const outAbs = path.resolve(args.output);
  fs.mkdirSync(path.dirname(outAbs), { recursive: true });
  await pptx.writeFile({ fileName: outAbs });

  // pptxgenjs sometimes rewrites the path (adds .pptx). Report what's on disk.
  const produced = fs.existsSync(outAbs)
    ? outAbs
    : fs.existsSync(outAbs + '.pptx')
    ? outAbs + '.pptx'
    : outAbs;
  console.log(`Wrote ${produced} (${normalized.length} slides, preset=${args.stylePreset})`);
}

main().catch((err) => {
  console.error(`Error: ${err && err.stack ? err.stack : err}`);
  process.exit(1);
});
