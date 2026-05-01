# Subagent Patterns

When a subagent helps vs. hurts pptx creation. Short rules, curated
patterns, and anti-patterns.

## Decision rule

Use a subagent when **at least one** of these is true:
- The work benefits from **fresh eyes** (main agent has been staring at
  code and will confirm its own assumptions).
- Sub-tasks are **independent** and parallelizable (N slide XML files).
- The task needs **specialized context** that would otherwise dilute the
  main agent's working memory.

Don't use a subagent when:
- A deterministic script can do it (`preflight.py`, `layout_lint.py`,
  `qa_gate.py` — all faster than any agent and don't drift).
- The task is **trivial** (single palette pick, single variant choice).
  Overhead of spawning > value.
- The subagent needs to know **what the main agent is doing mid-task**.
  Spawn overhead and context transfer cost > benefit.

## Instruction-drift prevention

A common failure mode when using multiple agents: each one's system
prompt/instructions drift from the others, so "good palette" means
different things to different agents. Mitigations, in order:

1. **Never define custom plugin-level agent types for pptx work.** Use
   temporary subagent invocations with explicit prompts instead. The
   skill's authoritative refs (`codex_guardrails.md`,
   `design_philosophy.md`, `outline_schema.md`) are the only source of
   truth; every subagent prompt should cite them.
2. **Always pass the relevant ref file paths** to the subagent's prompt
   so it reads from the same canonical docs, not its own priors.
3. **Use the `Explore` subagent type for read/analysis tasks.** It's
   lighter than general-purpose and won't try to edit files.
4. **Don't chain subagents N deep.** Main → subagent → subagent quickly
   loses instruction fidelity. Keep it two-deep max.

## High-value patterns (use these)

### 1. Visual QA after render

Fresh eyes on rendered JPGs. Automated `qa_gate.py` misses
composition-level issues (ambiguous hierarchy, wrapped-title decorations,
cramped typography).

**Operational**: `render_slides.py --emit-visual-prompt` prints a
ready-to-paste prompt with numbered JPG paths. Spawn an `Explore`
subagent with that prompt. Details in `references/visual_qa_prompt.md`.

### 2. Parallel slide-XML editing (template adaptation)

When adapting a branded template with many content slides, the per-slide
XML edits are independent. Spawn N parallel subagents, one per slide XML
file, with identical prompts pointing at the template analysis and the
new content. Each edits `ppt/slides/slideN.xml` and nothing else.

**When it pays off**: ≥5 slides need text substitution. Below that, the
main agent's single pass is faster than N spawns.

**Prompt pattern**:
```
You are editing one slide of an unpacked PPTX template.

File: /path/to/unpacked/ppt/slides/slide{N}.xml
Original content: <excerpt from markitdown>
New content:
  Title: "..."
  Body: [...]

Rules (from references/editing.md):
- Bold every title and section header (<a:rPr b="1">)
- Never insert unicode bullets; use layout-inherited or <a:buChar>
- Preserve xml:space="preserve" on existing runs
- One <a:p> per list item, do not concatenate
- If the template has more placeholders than your content items,
  delete the entire shape group, not just the text

Edit only slide{N}.xml. Report what you changed.
```

### 3. Outline critique before build

Dedicated agent reads `outline.json` + `references/design_philosophy.md`
and flags editorial issues: monotony (same variant 3 in a row), no
visual elements on content slides, weak or generic palette choice,
text-heavy slides that would fit kpi-hero or comparison-2col. Catches
things the main agent glosses over because it's focused on content.

**Operational**: `scripts/emit_outline_critique_prompt.py --outline
outline.json` emits a ready-to-paste prompt. Run before `build_deck.py`.

### 4. Template analysis before reuse

When the user hands you a branded `.pptx` to adapt, spawn an `Explore`
subagent to analyze it. Give it the thumbnail grid path and the
`markitdown` text extraction. Ask it to:
- List each layout's purpose (title, section, content, closing, stats,
  quote).
- Identify the placeholder text patterns that'll need replacement
  (`"XXXX"`, `"Click to add"`, `"Lorem"`).
- Note brand colors (hex values visible in palette usage).
- Flag slides that look like they host charts / tables / icon grids vs.
  plain bullets.

The subagent's output drives the "Plan slide mapping" step in
`references/editing.md`'s template-adaptation workflow.

## Anti-patterns (don't do)

### Custom plugin-defined agent types for pptx

Tempting to define a `pptx-outline-author` or `pptx-palette-picker`
plugin-level agent with its own system prompt. Don't. Each such
definition drifts from the others and from this skill's own
conventions. A "pptx-palette-picker" that picks "Cherry Bold" for a
climate deck because its system prompt says "bold colors" violates
`design_philosophy.md`'s "palette should feel designed for THIS topic"
rule. Use temporary invocations tied to the skill's refs instead.

### Subagent for deterministic work

If `preflight.py` can answer the question in <1s, don't ask a subagent.
Examples where the script is better:
- "Is the outline schema valid?" → `preflight.py`
- "Does any slide have overflow?" → `layout_lint.py`
- "What font pairs are loadable?" → read `design_tokens.py`

### Subagent to pick a variant

Variant selection for a single slide is trivial (the outline schema
covers the whole decision matrix). Spawning an agent per slide adds
seconds per slide with no quality win over the main agent.

### Agent-per-slide on tiny decks

Parallel XML editing is for ≥5 slides. On a 3-slide deck, the main
agent's sequential pass finishes before three subagents finish
spawning.

### Letting a subagent define "good design"

A subagent asked "make this slide look better" without explicit
constraints will drift. Always give specific rules (cite
`design_philosophy.md`, specify allowed variants, pass the palette).
Open-ended authorship from a fresh subagent produces generic output
because it has no context for what's right for THIS deck.
