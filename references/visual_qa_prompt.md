# Visual QA Subagent Prompt

This is the canonical "assume problems" prompt used in Verification
step 2. It pairs with `qa_gate.py` (geometric, step 1) and the
`markitdown` placeholder grep (content, step 3). See SKILL.md →
"Verification Loop" for the full flow.

## Why a separate subagent pass

`qa_gate.py` catches deterministic geometry issues (overflow, overlap,
density, empty-ratio). `visual_review.py` adds a deterministic rendered
packet: contact sheet, wrap-risk heuristics, orphan-word risks,
footer-clearance risks, and layout-rhythm checks. Neither can fully see
composition problems that only surface visually: line-through-text
collisions, wrapped-title decoration mismatches, uneven gaps, low
contrast, or a slide that is technically correct but reads as empty.
Those still need fresh eyes.

You will not see these issues yourself — you've been staring at the
outline and the code, and you see what you expect to see. A subagent
inspecting rendered JPGs with no prior context will find things you
missed.

## Assume there are problems

Your first render is almost never correct. Approach the pass as a bug
hunt, not a confirmation step. If the subagent reports zero issues on
first inspection, it wasn't looking hard enough — ask again more
critically.

## How to invoke

Render the deck to JPGs and emit the prompt:

```bash
python3 scripts/render_slides.py --input deck.pptx --outdir renders/ \
  --emit-visual-prompt
python3 scripts/visual_review.py --input deck.pptx --outdir review/ \
  --renders-dir renders/ --outline outline.json
```

`--emit-visual-prompt` prints a ready-to-paste block with the absolute
JPG paths already filled in. Paste it into a fresh `Explore` subagent.
Do not copy the prompt body from this doc — the CLI is the source of
truth and stays in sync automatically.

## The canonical prompt

```
Visually inspect these slides. Assume there are issues — find them.

Look for:
- Overlapping elements (text through shapes, lines through words,
  stacked elements)
- Text overflow or cut off at edges/box boundaries
- Decorative lines positioned for single-line text but title wrapped
  to two lines (the line now sits at the wrong y)
- Source citations or footers colliding with content above
- Elements too close (< 0.3" gaps) or cards/sections nearly touching
- Uneven gaps (large empty area in one place, cramped in another)
- Insufficient margin from slide edges (< 0.5")
- Columns or similar elements not aligned consistently
- Low-contrast text (e.g., light gray text on cream-colored background)
- Low-contrast icons (e.g., dark icons on dark backgrounds without
  a contrasting circle)
- Text boxes too narrow causing excessive wrapping
- Leftover placeholder content

For each slide, list issues or areas of concern, even if minor.

Read and analyze these images — run `ls -1 "$PWD"/slide-*.jpg` and use
the exact absolute paths it prints:
1. <absolute-path>/slide-N.jpg — (Expected: [brief description])
2. <absolute-path>/slide-N.jpg — (Expected: [brief description])
...

Report ALL issues found, including minor ones.
```

## Verification cycle

1. Generate slides → render to JPG → inspect (with subagent).
2. Run `visual_review.py` and inspect the contact sheet.
3. **List issues found.** If none reported, ask again more critically.
4. Fix issues at the source (outline or renderer), not in the mutated
   PPTX.
5. **Re-verify affected slides** — one fix often creates another
   problem (e.g., shortening a title changes wrapping and decoration
   position).
6. Repeat until a full pass reveals no new issues.

**Do not declare success until at least one fix-and-verify cycle has
completed.** A clean `qa_gate.py` plus "looks OK at a glance" is not
enough.

## Pair with automated QA, don't replace it

`qa_gate.py --strict-geometry` catches overflow, overlap, density, and
contrast via shape inspection — faster than any subagent and
deterministic. The visual-QA pass is the second layer, not the only
layer. Ship both:

```bash
python3 scripts/qa_gate.py --input deck.pptx --outdir qa/ \
  --strict-geometry --fail-on-visual-warnings --fail-on-design-warnings \
  --run-visual-review
python3 scripts/render_slides.py --input deck.pptx --outdir renders/ \
  --emit-visual-prompt
# Then paste the emitted block into a fresh Explore subagent.
```
