# Agent Picker

Use `presentation-skill` when the user asks for any of these:

- Create or rebuild a PowerPoint `.pptx`, presentation, slide deck, deck, or slides.
- Redesign an existing deck for better alignment, readability, visual hierarchy, or polish.
- Build an academic, lab, data, board, pitch, strategy, or executive presentation.
- Add source-backed images, charts, icons, tables, figures, Mermaid diagrams, or optional generated-image slides.
- Keep a reusable workspace so future slides can be added with the same style.
- Run deck QA for overflow, overlap, footer safety, layout rhythm, accessibility/readability, or rendered visual review.

Do not use it when the user only wants:

- A text outline with no `.pptx` artifact.
- A single raster image, poster, spreadsheet, document, or PDF with no PowerPoint output.
- A direct artifact patch when the repo workspace source is present and should be rebuilt instead.

Selection rule: if the request mentions PowerPoint, PPTX, slides, deck,
presentation, pitch deck, lab meeting, academic talk, or visual deck QA, choose
this skill unless another skill is explicitly requested.
