/*
 * Style presets for the pptxgenjs peer renderer.
 *
 * Each preset exports the minimal token surface the slide templates need:
 *   { bg, bg_dark, text, text_muted, accent_primary, accent_secondary,
 *     font_heading, font_body }
 *
 * Values mirror the Python design tokens (scripts/design_tokens.py) so
 * decks rendered through either path feel like the same family.
 *
 * HEX RULE (pptxgenjs): colors are strings without the leading '#'.
 * Always write "1493A4", never "#1493A4".
 */

'use strict';

const PRESETS = {
  'executive-clinical': {
    bg: 'F4F8FB',
    bg_dark: '071E3A',
    surface: 'FFFFFF',
    text: '0F172A',
    text_muted: '475569',
    accent_primary: '1493A4',
    accent_secondary: 'F59E0B',
    line: 'D5DEE8',
    font_heading: 'Helvetica Neue',
    font_body: 'Helvetica Neue',
  },
  'bold-startup-narrative': {
    bg: 'EEF6FF',
    bg_dark: '0B1220',
    surface: 'FFFFFF',
    text: '0B132B',
    text_muted: '334155',
    accent_primary: 'FF6B35',
    accent_secondary: '22C55E',
    line: 'CBD5E1',
    font_heading: 'Inter',
    font_body: 'Inter',
  },
  'midnight-neon': {
    bg: '0A1020',
    bg_dark: '030712',
    surface: '101A33',
    text: 'E2E8F0',
    text_muted: '94A3B8',
    accent_primary: '22D3EE',
    accent_secondary: 'F43F5E',
    line: '1E293B',
    font_heading: 'Inter',
    font_body: 'Inter',
  },
  'data-heavy-boardroom': {
    bg: 'F8FAFC',
    bg_dark: '0F172A',
    surface: 'FFFFFF',
    text: '111827',
    text_muted: '4B5563',
    accent_primary: '1D4ED8',
    accent_secondary: '0891B2',
    line: 'D1D5DB',
    font_heading: 'Helvetica Neue',
    font_body: 'Helvetica Neue',
  },
  'lab-report': {
    bg: 'FFFFFF',
    bg_dark: '0B2545',
    surface: 'FFFFFF',
    text: '1B2838',
    text_muted: '4B5563',
    accent_primary: '0B2545',
    accent_secondary: 'C9302C',
    line: 'D1D5DB',
    font_heading: 'Helvetica Neue',
    font_body: 'Helvetica Neue',
    // Clinical-red accent stripe under the dark header — the skill
    // signature for the lab-report aesthetic. Python path renders the
    // same stripe (see build_deck.py _content_header lab_report branch).
    header_accent_stripe: true,
  },
  'editorial-minimal': {
    bg: 'FFFFFF',
    bg_dark: '000000',
    surface: 'FFFFFF',
    text: '0A0A0A',
    text_muted: '6B7280',
    accent_primary: 'D4461E',
    accent_secondary: '1F2937',
    line: 'E5E7EB',
    font_heading: 'Georgia',
    font_body: 'Helvetica Neue',
  },
  // Parity port of the remaining python presets so auto-picker can route
  // any deck to the HTML path without tripping "unknown preset" errors.
  'paper-journal': {
    bg: 'FAF6EC',
    bg_dark: '3B2F1E',
    surface: 'FFFFFF',
    text: '2A2118',
    text_muted: '6B5B42',
    accent_primary: '8B4513',
    accent_secondary: 'A0522D',
    line: 'D9CBA8',
    font_heading: 'Georgia',
    font_body: 'Georgia',
  },
  'forest-research': {
    bg: 'F5F3EA',
    bg_dark: '1B3A2E',
    surface: 'FFFFFF',
    text: '1A2E20',
    text_muted: '51624D',
    accent_primary: '2F5D50',
    accent_secondary: 'C07A4B',
    line: 'D1D4B8',
    font_heading: 'Helvetica Neue',
    font_body: 'Helvetica Neue',
  },
  'sunset-investor': {
    bg: 'FFF7ED',
    bg_dark: '431407',
    surface: 'FFFFFF',
    text: '431407',
    text_muted: '9A3412',
    accent_primary: 'EA580C',
    accent_secondary: '1E293B',
    line: 'FED7AA',
    font_heading: 'Helvetica Neue',
    font_body: 'Helvetica Neue',
  },
  'charcoal-safety': {
    bg: 'F3F4F6',
    bg_dark: '111827',
    surface: 'FFFFFF',
    text: '1F2937',
    text_muted: '4B5563',
    accent_primary: '111827',
    accent_secondary: 'DC2626',
    line: 'D1D5DB',
    font_heading: 'Helvetica Neue',
    font_body: 'Helvetica Neue',
  },
  'arctic-minimal': {
    bg: 'F8FAFC',
    bg_dark: '0F172A',
    surface: 'FFFFFF',
    text: '0F172A',
    text_muted: '64748B',
    accent_primary: '0EA5E9',
    accent_secondary: '334155',
    line: 'E2E8F0',
    font_heading: 'Helvetica Neue',
    font_body: 'Helvetica Neue',
  },
  'lavender-ops': {
    bg: 'F5F3FF',
    bg_dark: '2E1065',
    surface: 'FFFFFF',
    text: '2E1065',
    text_muted: '6D28D9',
    accent_primary: '7C3AED',
    accent_secondary: '0E7490',
    line: 'DDD6FE',
    font_heading: 'Helvetica Neue',
    font_body: 'Helvetica Neue',
  },
  'warm-terracotta': {
    bg: 'FFF7ED',
    bg_dark: '7C2D12',
    surface: 'FFFFFF',
    text: '7C2D12',
    text_muted: '9A3412',
    accent_primary: 'C2410C',
    accent_secondary: '0891B2',
    line: 'FED7AA',
    font_heading: 'Helvetica Neue',
    font_body: 'Helvetica Neue',
  },
};

const DEFAULT_PRESET_NAME = 'executive-clinical';

function listPresets() {
  return Object.keys(PRESETS).sort();
}

function getPreset(name) {
  const key = String(name || '').trim().toLowerCase();
  if (!key) return { ...PRESETS[DEFAULT_PRESET_NAME] };
  if (!PRESETS[key]) {
    // Graceful fallback so a python-only preset name doesn't disqualify
    // the whole deck from the HTML path. Warn once then use the default.
    console.warn(
      `[pptxgenjs] preset '${name}' not defined in templates/pptxgenjs/presets.js; ` +
        `rendering with '${DEFAULT_PRESET_NAME}' fallback.`,
    );
    return { ...PRESETS[DEFAULT_PRESET_NAME] };
  }
  // Return a shallow clone so callers can mutate without bleeding into other
  // slides. pptxgenjs is touchy about reused option objects; we extend that
  // discipline to presets too.
  return { ...PRESETS[key] };
}

module.exports = {
  PRESETS,
  DEFAULT_PRESET_NAME,
  listPresets,
  getPreset,
};
