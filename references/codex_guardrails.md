# Codex Guardrails

Read this file **before** writing any code in this skill. It encodes the
anti-patterns that Codex-style agents tend to fall into on this repo and the
counter-moves that keep runs deterministic.

## The Anti-Patterns

Codex models, when given a "make a .pptx" request, tend to drift toward one of
these shortcuts. All of them produce worse decks than this skill's pipeline.
Do not take any of them.

### 1. "I'll just write python-pptx inline"

**Symptom:** Agent opens a heredoc / inline script that imports `python-pptx`
directly, builds slides by hand, and writes straight to `out.pptx` without
touching `scripts/build_deck.py`.

**Why it fails:** Skips text measurement, card sizing, header-stack layout,
content-slide intent routing, style contract, and every QA layer. The result
looks fine on slide 1 and falls apart by slide 6 (overflow, overlapping cards,
missing footers, inconsistent fonts).

**Counter-move:** Always express the deck as an `outline.json` that satisfies
`references/outline_schema.md` and invoke `scripts/build_deck.py`. If you are
tempted to write `from pptx import Presentation`, stop and edit the outline
instead.

### 2. "I'll force --renderer python to be safe"

**Symptom:** Agent passes `--renderer python` to `build_workspace.py`,
or invokes `build_deck.py` directly for a deck that doesn't use `chart`
or `image-sidebar`.

**Why it fails:** pptxgenjs is the default and produces richer typography
on timeline, hero, comparison, cards, stats, kpi-hero, table, and section
dividers. Forcing python silently downgrades the deck. The auto-picker in
`build_workspace.py` already routes chart and image-sidebar variants to
python; everything else should go through pptxgenjs.

**Counter-move:** Let the auto-picker choose. Use `build_workspace.py`
without `--renderer`, or invoke `build_deck_pptxgenjs.js` directly:

```bash
node scripts/build_deck_pptxgenjs.js --outline deck.json --output out.pptx --style-preset <preset>
```

Only reach for `build_deck.py` when the outline actually needs `chart`
or `image-sidebar`. Do not invent a new renderer or fall back to inline
pptxgenjs API calls.

### 3. "I'll skip the QA gate, the draft looks fine"

**Symptom:** Agent runs `build_deck.py`, opens the `.pptx`, does not run
`qa_gate.py` / `layout_lint.py` / `inventory.py`, and declares the deck done.

**Why it fails:** Overflow and overlap are invisible in the outline but
deterministic in the rendered geometry. The gate catches them. Skipping it
ships broken decks.

**Counter-move:** After every build, run at minimum:

```bash
python3 scripts/qa_gate.py --input out.pptx --outdir /tmp/pptx-qa \
  --style-preset <preset> --strict-geometry --skip-render \
  --fail-on-design-warnings
```

Use `--skip-render` if LibreOffice is unavailable — never skip the gate
entirely. If the gate fails, run `iterate_deck.py --max-loops 3` before
reporting the task complete.

### 4. "I'll install new deps / pip install at runtime"

**Symptom:** Agent runs `pip install python-pptx` or `npm install pptxgenjs`
inside the task, or writes a script that does.

**Why it fails:** This skill treats installs as **one-time environment setup**.
Reinstalling per-run is slow, non-deterministic, and breaks sandboxed /
read-only environments.

**Counter-move:** Assume the environment is already provisioned. If an import
fails, report the missing dep to the user and stop — do not auto-install.

## Pipeline Discipline

Every deck build goes through exactly this shape. Do not reorder, skip, or
inline steps.

1. **Outline** — JSON per `references/outline_schema.md`. For persistent decks,
   scaffold a workspace with `init_deck_workspace.py` and keep outline,
   style contract, notes, and staged assets together.
2. **Build** — `build_workspace.py` (auto-picks pptxgenjs) or
   `build_deck_pptxgenjs.js` directly. Use `build_deck.py` only for
   `chart` or `image-sidebar` variants. Never call a builder you didn't
   load from this repo.
3. **Verify** — three steps, all required: `qa_gate.py` (geometric) +
   `render_slides.py --emit-visual-prompt` into a fresh subagent (visual)
   + `markitdown` placeholder grep (content). See SKILL.md →
   "Verification Loop" for the canonical flow.
4. **Iterate** — `iterate_deck.py --max-loops 3` if geometric QA fails.
   Cap at 3; do not let it run unbounded.
5. **Deliver** — Final `.pptx` plus a slide-by-slide change summary and
   assumption notes. Confirm a fix-and-verify cycle has completed before
   declaring done.

## When Codex Tendencies Are Actually Right

Not every shortcut is wrong. These are legitimate:

- **Editing a single slide's bullet text** — fine to edit `outline.json`
  directly without rebuilding the workspace.
- **Adding a new asset** — fine to drop a file into `assets/` and reference it
  by alias, no need to re-run `asset_stage.py` if the manifest is up to date.
- **Using a generated concept visual** — fine when source-backed imagery is
  weak, but it must be explicit: add it under `asset_plan.json`
  `generated_images`, run with `--allow-generated-images`, and put it on a
  `variant: generated-image` slide with prompt/model/purpose metadata.
- **Skipping render-based QA** when LibreOffice is unavailable — use
  `--skip-render` on `qa_gate.py`, the geometry/design gates still run.

The rule: shortcuts that skip I/O are fine, shortcuts that skip measurement or
verification are not.

### A Fifth Trap: Rebuilding When You Should Be Editing

**Symptom:** User sends a `.pptx` and asks for "fix the typo on slide 3."
Agent reconstructs an `outline.json` by staring at the deck, rebuilds from
scratch, gets ~60% of the original layout back.

**Why it fails:** The outline is a lossy approximation of an authored deck.
You will lose formatting, embedded media, custom layouts, and speaker notes.

**Counter-move:** Use `scripts/edit_deck.py` for text / slide-deletion /
metadata edits. Use `scripts/unpack_pptx.py` + `scripts/pack_pptx.py` for
XML-level surgery. Only rebuild from outline if the user explicitly wants a
restyle or the original outline is already in the workspace. Read
`references/editing.md` for the full policy.

### Design-quality traps (text-only slides, uniform decks)

These are now covered in `DESIGN.md` (in particular
the "Avoid (the AI-slide tells)" list and the "Rhythm break" guidance).
Read that file before drafting an outline; it replaces the long-form
"text-only" and "uniform deck" traps that used to live here.

## Behaviors Worth Copying

The anti-patterns above tell you what not to do. These are the moves
Codex runs have gotten RIGHT — copy them on new work.

### 1. Fix at source, not in the mutated PPTX

From a good history-of-nuclear run:

> *"The auto-fit loop removed the overflows, but it expanded the title
> boxes enough to create new title/subtitle overlaps on two slides.
> I'm fixing that at the source by shortening those slide headlines in
> the outline and rebuilding cleanly from the workspace instead of
> shipping a mutated PPTX."*

When `iterate_deck.py` produces a passing `.pptx` by mutating it in
place, don't stop there. Ask whether the fix belongs in the outline
(yes, usually). Rebuilding from a cleaned outline is the durable state;
a mutated PPTX is a snapshot you can't re-run next month.

### 2. Check existing workspaces for file shape, not structure

Reading `decks/power-and-coal/outline.json` to remember what fields the
schema takes → fine. Treating it as a house-style skeleton to
pattern-match for a new topic → the 8th Trap (see above). A good run:

> *"There's already a power-and-nuclear example in the skill repo, but
> I'm not going to clone it since this is a new topic. I'm only
> checking a couple of existing outlines to confirm the expected file
> shape."*

That's the distinction: "what does valid JSON look like?" (yes) vs.
"what variants did the prior deck use?" (no — pick by this topic's
argument arc).

### 3. Narrate what you did, not what you meant to do

Codex transcripts occasionally claim actions that didn't happen — e.g.
"adding a small icon set inside the workspace" when `assets/icons/` was
never created. Don't narrate staging you didn't perform. If you
considered icons and skipped them, say so; if you added them, show the
`ls -la assets/icons/` output.

`scripts/verify_narration.py` runs at the end of `build_workspace.py
--qa` and will flag any `assets.hero_image` / `assets.icons[]` /
`assets.mermaid_source` that points at a missing file. Don't leave that
warning in the final report.

### 4. Push past "functional" to "good"

Every transcript ends with "If you want, I can do a second pass to...".
That's polite, and it's also stopping early. A deck with zero overflow
is not automatically a good deck. Before declaring done:

- Did preflight emit `rhythm_break_absent` or `enrichment_missing_pattern`?
  Act on them, don't just narrate them.
- Did preflight emit `content_vague_hedged` on any slide? Run the
  content-research subagent (`scripts/emit_content_research.py`).
- Does the deck have ≥1 staged visual (hero, icons, mermaid, table, or
  chart)? If not, ask yourself whether the topic genuinely has no
  visual anchor or whether you ran out of energy.

"The QA gate passed" is a floor, not a ceiling. Don't ship at the floor
unless the user asked for a quick draft.

## Self-Check Before Declaring "Done"

Honor-system checklists do not work on Codex agents. Each of the four boxes
below requires a **pasted command output** in the final report. No output,
no claim.

- [ ] **Outline JSON exists.**
      Evidence: `ls -l outline.json` (or workspace `outline.json`) showing
      non-zero size.
- [ ] **Build was done with a repo script.**
      Evidence: the exact command line used, e.g.
      `python3 scripts/build_deck.py --outline outline.json --output out.pptx …`
      If the report shows inline python-pptx, the task has failed.
- [ ] **QA gate ran and passed** (or `iterate_deck.py` was invoked).
      Evidence: the last ~10 lines of `qa_gate.py` stdout plus exit code 0,
      or the `iterate_deck.py` output showing loop exit on pass.
- [ ] **No installs were run during this task.**
      Evidence: a grep over the task's shell history, e.g.
      `history | grep -E 'pip install|npm install'` returning empty,
      or an explicit statement that no `pip`/`npm install` command was issued.

If any evidence is missing, the task is not done — regardless of how the deck
looks when opened.
