# Speed and Rendering

Render-based QA is the single largest cost in the build/iterate cycle. This
document explains where the time goes, the two complementary speedups the
repo now supports, and how they compose.

## Why Render Is Slow

`scripts/render_slides.py` converts `.pptx` to PDF via LibreOffice, then
rasterizes the PDF with Poppler's `pdftoppm`. The `pdftoppm` step is cheap
(sub-second per slide). The cost is LibreOffice:

- `soffice --headless --convert-to pdf` starts a full LibreOffice process
  every time it is invoked.
- Startup cost on a typical laptop: **~10-15 seconds**, regardless of deck
  size. A 5-slide deck and a 40-slide deck pay roughly the same price.
- A 3-loop `iterate_deck.py` run therefore pays the startup cost 3x (~30-45s
  of pure cold-start overhead).

The `qa_gate.py`, `render_slides.py`, and `benchmark_decks.py` entry points
all route through the same shell out, so the cost compounds across harnesses.

## Speedup 1: Skip Render in Intermediate Loops

`scripts/iterate_deck.py` no longer renders on every loop by default.

- **Loops `1..N-1`**: non-render QA only (`qa_gate.py --skip-render`).
  Geometry, text-fit, overflow, and overlap checks still run.
- **Loop `N` (final)**: full QA **with** render — this is the publish-grade
  pass.
- **`--always-render`**: restores the old behavior where every loop renders.
  Use this when you genuinely need the render diff at every iteration.
- **`--skip-render`**: suppresses render on every loop, including the final
  one. Useful when LibreOffice is unavailable.
- **`--fast`**: convenience alias for quick drafts. Equivalent to
  `--max-loops 3 --skip-render`.

Typical effect for a 3-loop run: ~60-80% wall-clock reduction because two of
the three soffice invocations are eliminated.

## Speedup 2: Run LibreOffice as a Persistent Daemon (`unoserver`)

`unoserver` keeps a single LibreOffice process alive and exposes a thin
client, `unoconvert`, that is a drop-in replacement for
`soffice --convert-to`. Each conversion drops from ~15s to ~1s because the
LibreOffice UNO bridge is already warm.

### Install

```bash
pip install unoserver
unoserver &  # run in background; persists across builds
```

Verify it is running:

```bash
which unoconvert
# /usr/local/bin/unoconvert (or similar)
```

### How the Skill Uses It

`scripts/render_slides.py` has a helper `_render_with_daemon_or_fallback`:

1. If `unoconvert` is on `PATH`, it tries `unoconvert --convert-to pdf`.
2. If `unoconvert` is missing or the call fails, it falls back to
   `soffice --headless --convert-to pdf`.
3. Either way, the chosen path and elapsed time are logged to stderr, so you
   see the speedup as soon as the daemon is picked up:

   ```
   [render] unoconvert (unoserver daemon) -> PDF in 0.92s
   ```

   vs. the cold path:

   ```
   [render] soffice --convert-to (no daemon) -> PDF in 14.31s
         (install unoserver for ~15x speedup)
   ```

Because `qa_gate.py`, `benchmark_decks.py`, and any other harness that needs
rendered slides all shell out to `render_slides.py`, they inherit the
speedup automatically — no CLI surface change.

## Composition

The two speedups stack:

| Setup                                  | Render calls / run | Wall-clock per call | Per-run render cost |
|----------------------------------------|--------------------|---------------------|---------------------|
| Old default (render every loop, soffice) | 3                | ~15s                | ~45s                |
| New default (render only final loop)    | 1                 | ~15s                | ~15s                |
| New default + `unoserver`              | 1                  | ~1s                 | ~1s                 |
| `--always-render` + `unoserver`        | 3                  | ~1s                 | ~3s                 |

The "new default + unoserver" row is the recommended local setup. If
`unoserver` is not available in your environment (e.g. CI without
LibreOffice installed), the fallback still works.

## Troubleshooting

- **`unoconvert: command not found`**: `pip install unoserver`, then restart
  the shell or `hash -r`.
- **`unoconvert` hangs**: the daemon is not running. `unoserver &` in a
  terminal that persists, or use `launchctl`/`systemd` to keep it up.
- **Render output differs between `unoconvert` and `soffice`**: they share
  the same LibreOffice rasterizer; geometry should match. If it doesn't,
  your daemon may be a different LibreOffice version — check with
  `unoserver --help` and `soffice --version`.
- **Publish-grade check before shipping**: run the final QA gate with render
  enabled (`iterate_deck.py` does this automatically on the last loop, or
  call `qa_gate.py` directly without `--skip-render`).
