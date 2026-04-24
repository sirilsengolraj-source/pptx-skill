# Editing Existing Decks

Use this flow when you have a `.pptx` you did not generate from an outline, and
you need to change it without rebuilding from scratch.

## Three Tools, Three Levels

1. `scripts/edit_deck.py` — python-pptx edits for common cases.
2. `scripts/unpack_pptx.py` + `scripts/pack_pptx.py` — XML-level edits.
3. Outline rebuild (`scripts/build_deck.py`) — anything structural or stylistic.

Pick the lowest-level tool that can do the job.

## Use `edit_deck.py` For

- Replacing literal strings across every shape, table cell, and speaker note (`replace-text`). Charts, SmartArt, and slide-master text are not covered; see the gap list below.
- Listing slide titles to confirm indexes before a destructive op (`list-slides`).
- Dropping a slide by 1-based index (`delete-slide`).
- Any small text or metadata tweak on a deck you don't have an outline for.

```bash
python3 scripts/edit_deck.py list-slides --input deck.pptx
python3 scripts/edit_deck.py replace-text \
  --input deck.pptx --output deck_v2.pptx \
  --find "Q3 2025" --replace "Q4 2025"
python3 scripts/edit_deck.py delete-slide \
  --input deck.pptx --output deck_trim.pptx --index 3
```

### Output safety (applies to `replace-text` and `delete-slide`)

Both subcommands refuse to clobber data by default:

- If `--output` already exists, you must pass `--overwrite` or the script
  exits 3 with an error on stderr.
- If `--output` resolves to the same path as `--input`, the script always
  refuses and exits 3. Point `--output` at a different file. This is a hard
  rule — `--overwrite` does not unlock same-path writes, because a partial
  save would corrupt the source deck.

### What `replace-text` scans

Matches work at the run level to preserve formatting. A match that spans two
runs (e.g. because PowerPoint split styling mid-word) will not be caught.

Covered:

- Every shape's text frame on every slide.
- Every cell's text frame in every table (including tables inside group shapes).
- Group shapes (recursively).
- Speaker-notes text on each slide.

NOT covered (known gaps — use `unpack_pptx.py` + XML edits if you need these):

- Chart titles, axis labels, data labels, and chart data.
- SmartArt diagram text.
- Slide master / slide layout text (e.g. footer placeholders inherited from
  the master).

Run `list-slides` after a replace to sanity-check, and run the QA gate
afterward (see below).

### `--require-match` on `replace-text`

By default `replace-text` exits 0 even when 0 occurrences are found (the
output file is still written as a copy). Pass `--require-match` to exit 4
and skip writing the output if the find string produced no matches. Use this
in scripts where a silent no-op is a bug.

```bash
python3 scripts/edit_deck.py replace-text \
  --input deck.pptx --output deck_v2.pptx \
  --find "Q3 2025" --replace "Q4 2025" \
  --overwrite --require-match
```

Notes on `delete-slide`: the slide's `sldId` is removed from `sldIdLst` and the
relationship is dropped. The slide part is left in the package as an orphan,
which PowerPoint ignores. This is the standard python-pptx workaround — there
is no public delete API.

## Use Outline Rebuild For

- Layout changes (hero opener, split panel, card grid, comparison, etc.).
- Style or palette changes, font swaps, or theme token updates.
- Adding slides that need to participate in the skill's visual system.
- Anything where `references/reproducible_workflow.md` rules apply.

If the deck didn't come from an outline, extract one first:

```bash
python3 scripts/extract_outline.py --input deck.pptx --format json \
  --output outline.json
```

Then edit `outline.json` and rebuild with `build_deck.py`.

## Use `unpack_pptx.py` / `pack_pptx.py` For

XML-level edits python-pptx can't cleanly express. Examples:

- Custom XML tags, custom properties, or embedded JSON in a slide part.
- Swapping embedded media (images, audio, video) at the package level.
- Repairing broken relationships or content types.
- Scripted find-replace inside theme or master XML.
- Adapting an existing branded `.pptx` as a template (see next section).

```bash
python3 scripts/unpack_pptx.py --input deck.pptx --outdir /tmp/deck-unpacked \
  --pretty-print --escape-smart-quotes
# edit files under /tmp/deck-unpacked/ (ppt/slides/slideN.xml, etc.)
python3 scripts/clean_unpacked.py --input /tmp/deck-unpacked
python3 scripts/pack_pptx.py --indir /tmp/deck-unpacked --output deck_new.pptx
```

Flags worth using:

- `--pretty-print` reformats every `.xml`/`.rels` part with 2-space indent
  and keeps the conventional OOXML prefixes (`p:`, `a:`, `r:`). Makes
  hand-editing readable; semantically identical to the original.
- `--escape-smart-quotes` replaces `" " ' ' – — …` with XML numeric
  entities (`&#x201C;`, etc.). Generic text editors that normalize unicode
  will otherwise quietly corrupt the glyphs on save.

`pack_pptx.py` writes `[Content_Types].xml` first and uses DEFLATE, which is
what PowerPoint expects. Do not rezip with a shell `zip` command; ordering and
compression flags matter.

Always run `clean_unpacked.py` before `pack_pptx.py`. Edits that delete or
swap slides leave orphans (slide XML files not referenced from
`presentation.xml`, media files not referenced from any slide's `.rels`,
stale `Content_Types.xml` overrides). The cleaner walks the rels graph,
removes everything unreachable, and loops until fixed-point so one pass
handles cascades.

## Template-adaptation workflow

When the user brings a branded `.pptx` and wants its look applied to new
content, you do NOT rebuild from outline — you adapt the template. The
workflow:

1. **Analyze the template** with a thumbnail grid and a text extraction:
   ```bash
   python3 scripts/thumbnail.py --input template.pptx --output template-grid.jpg
   python3 -m markitdown template.pptx > template-text.md
   ```
   The grid shows you every layout in one image; markitdown surfaces
   placeholder text (e.g., `"XXXX"`, `"Lorem ipsum"`, `"Click to add
   title"`) you will need to replace or delete.
2. **Plan slide mapping**: for each content section of the new deck, pick
   the best-matching template slide. **Use varied layouts** — monotonous
   decks are the default failure mode. Actively mix:
   - Multi-column (2-column, 3-column)
   - Image + text compositions
   - Full-bleed or half-bleed image slides
   - Quote / callout slides
   - Section dividers
   - Stat / number callouts
   - Icon grid or icon + text rows
   Don't default to "title + bullets" for every slide.
3. **Unpack**:
   ```bash
   python3 scripts/unpack_pptx.py --input template.pptx \
     --outdir /tmp/template-unpacked --pretty-print --escape-smart-quotes
   ```
4. **Structural edits** — get slide count and order right BEFORE editing
   content. Duplicate slides you'll reuse, delete ones you won't,
   reorder via the `<p:sldIdLst>` in `ppt/presentation.xml`:
   ```bash
   python3 scripts/add_slide.py duplicate \
     --input /tmp/template-unpacked --source slide2.xml
   # Prints an <p:sldId .../> line to insert into sldIdLst
   ```
   For a brand-new slide that pulls only a layout:
   ```bash
   python3 scripts/add_slide.py from-layout \
     --input /tmp/template-unpacked --layout slideLayout3.xml
   ```
   **Complete all structural changes before step 5.** Reordering after
   text edits risks losing tracked changes inside the duplicate.
5. **Content edits per slide**: update `<a:t>` text runs inside each
   `ppt/slides/slideN.xml`. Rules:
   - Bold every title, section header, and inline label ("Status:",
     "Description:") by setting `<a:rPr b="1">` on the run.
   - **Never** insert unicode bullets (`•`). Use the layout-inherited
     bullet or add `<a:buChar char="•"/>` / `<a:buAutoNum type="arabicPeriod"/>`
     in `<a:pPr>`. Plain `•` produces doubled bullets on some themes.
   - Preserve `xml:space="preserve"` on `<a:t>` runs with leading or
     trailing whitespace — dropping it collapses indentation.
   - Smart quotes: if you unpacked with `--escape-smart-quotes`, keep
     them as entities (`&#x201C;` etc.). Don't "normalize" back to `"`.
   - Multi-item content (e.g., a 4-step process): one `<a:p>` per step.
     Do not concatenate into one paragraph with `\n`.
   - If the template has 4 placeholders and you have 3 items, **delete
     the full shape group** (text box plus any icon/image siblings),
     not just the text — otherwise you keep floating frames.
6. **Clean orphans**:
   ```bash
   python3 scripts/clean_unpacked.py --input /tmp/template-unpacked
   ```
7. **Pack**:
   ```bash
   python3 scripts/pack_pptx.py --indir /tmp/template-unpacked \
     --output branded_deck.pptx --overwrite
   ```
8. **QA** — same gate as any other deck:
   ```bash
   python3 scripts/qa_gate.py --input branded_deck.pptx \
     --outdir /tmp/branded-qa --strict-geometry
   python3 scripts/render_slides.py --input branded_deck.pptx \
     --outdir /tmp/branded-renders --emit-visual-prompt
   ```
   The visual-QA subagent pass catches placeholder leaks
   (`"XXXX"`, `"Click to add title"`) that slipped the content edit.

### XML-editing gotchas

- Use `defusedxml.minidom` or stdlib `xml.etree.ElementTree` for XML
  parsing when you need structure; never `sed`/`awk` for anything beyond
  trivial literal swaps, which will corrupt CDATA sections.
- ET rewrites namespace prefixes as `ns0:`/`ns1:` unless you call
  `ET.register_namespace("p", "http://.../presentationml/...")` etc.
  before serialization. `unpack_pptx.py --pretty-print` handles this for
  you; if you're doing your own serialization, register the prefixes.
- Parallel slide-XML edits are safe — slides are independent XML files,
  so subagents can edit several in parallel if the deck is large.
- `replace-text` on `edit_deck.py` is run-level; a match that spans runs
  (styled mid-word) won't fire. Either split the run first or fall back
  to raw XML.

## Mandatory QA After Any Edit

Text replacement often overflows. A 20-character phrase becoming a 40-character
phrase is the single most common regression, and it will not be obvious from a
JSON diff. Re-run the gate:

```bash
python3 scripts/qa_gate.py \
  --input deck_v2.pptx \
  --outdir /tmp/pptx-qa-edit \
  --style-preset executive-clinical \
  --strict-geometry
```

If overflow is reported, either shorten the replacement, widen the box via an
outline rebuild, or fall back to a manual layout fix in the source deck.
