# Display Simulator

A pixel-perfect tkinter mock of the **Waveshare 5" e-paper panel (960×552,
1-bit mono)** so the reader UI can be built and iterated without flashing the
ESP32. Comes with a small sample e-reader UX to start from.

## Why it's pixel-perfect

The reader never draws to the screen directly. It draws into a **1-bit packed
framebuffer that matches the panel's exact byte layout** — 8 px/byte, MSB-first,
120 bytes/row, 66,240 bytes total (the ~64.7 KB per-page figure from the build
guide). The reader hands those packed bytes to a mock EPD driver, and the window
**reconstructs the pixels from the bytes** (`Image.frombytes("1", …)`) before
painting them at an integer zoom. So what you see on screen is literally the
device buffer — if the packing is wrong, the preview is wrong, which is exactly
the validation you want.

The mock `EPD` mirrors the Waveshare driver surface (`init` / `clear` /
`display` / `display_partial` / `sleep`), and the reader follows the firmware's
refresh discipline: partial refresh on page turns, full refresh every few turns
(and on screen changes) to clear ghosting. Full refreshes show a brief e-ink
"flash".

**Orientation.** The hardware framebuffer is always 960×552 (the panel is a
landscape strip). The reader runs **portrait** by default — you mount the panel
on its side and draw into a 552×960 logical `Canvas`, which rotates into the real
960×552 device buffer at push time (and the window rotates it back for display).
Portrait is still validated against the true packed bytes, not a sideways image.

## Run

```bash
pip install -r simulator/requirements.txt   # Pillow; tkinter ships with CPython
python simulator/run.py                          # portrait, Literata, native 1×
python simulator/run.py --orientation landscape  # landscape layout
python simulator/run.py --font pixel             # start on a different font
python simulator/run.py --actual-size --ppi 109  # true physical ~5" size
python simulator/run.py --ruler --actual-size --ppi 109   # calibration ruler
```

Font, weight, size, and orientation are all **switchable live** from the
controls at the top of the window — no restart needed.

| Option | Meaning |
|--------|---------|
| `--orientation {portrait,landscape}` | reader layout (default `portrait`). |
| `--font {literata,bitter,crimson,atkinson,palladio,source-serif,pixel,serif}` | starting font (default `literata`). |
| `--size {S,M,L,XL}` | starting text size (default `M`). |
| `--weight NAME` | starting body weight (e.g. `Regular`, `Medium`, `SemiBold`, `Bold`). |
| `--scale N` | zoom factor. Integer ≥1 = pixel-perfect (NEAREST). Fractional = resampled (LANCZOS). |
| `--actual-size` | show at true physical 5" size, using `--ppi`. |
| `--ppi P` | your monitor's pixels-per-inch (default 109). |
| `--ruler` | draw a calibration ruler instead of the reader. |
| `--demo dither` | show the 1-bit dithering comparison card. |

### Sizing / actual physical size

At **1×** one device pixel is one screen pixel, so on a typical ~100 PPI monitor
the panel looks roughly **2× life-size** (the real panel is ~220 PPI). For true
physical size use `--actual-size --ppi <yours>`, or set `--scale` directly.

macOS/Tk reports a useless 72 PPI (logical points, Retina-blind), so true size
can't be auto-detected. If unsure of your PPI, **calibrate by eye**:

```bash
python simulator/run.py --ruler --scale 0.5
```

Hold a real ruler to the screen, adjust `--scale` until the on-screen
centimetres match, then run the reader at that same `--scale` — the panel is now
life-size. (`--actual-size --ppi P` is just a shortcut for `scale = P / 220`.)

> Fractional / actual-size zoom resamples for display only — the underlying
> framebuffer stays an exact 960×552 1-bit buffer, so it's still byte-accurate.

## Fonts

Switchable live in the window or with `--font`. All bundled fonts are
open-licensed (see `reader/assets/fonts/NOTICE.md` for licenses + sources):

- **`literata`** (default) — Google's e-reader serif (OFL). Warm, screen-tuned.
- **`bitter`** — Bitter (OFL), a slab serif built for low-DPI screens; its
  sturdy stems survive 1-bit rendering particularly well.
- **`crimson`** — Crimson Text (OFL), a classic literary book serif.
- **`atkinson`** — Atkinson Hyperlegible (OFL), the Braille Institute's
  legibility-first sans; its disambiguated letterforms hold up well small and
  on 1-bit e-ink.
- **`palladio`** — URW Palladio / P052 (AGPL+font exception), an open
  **Palatino** clone — the redistributable stand-in for "Palatino"-style faces.
- **`source-serif`** — Source Serif 4 (OFL, Adobe), a clean modern serif.
- **`pixel`** — Pixel Operator (CC0), a *proportional* bitmap font; crisp 1-bit
  at native 16px and multiples (body 32px). The literal low-PPI mono look. (The
  Open Book / `libros` firmware uses GNU Unifont, but it's monospace and reads
  poorly for prose.)
- **`serif`** — whatever host TrueType serif is installed (fallback/compare).

**Weight & size.** The window's *Weight* dropdown lists the weights the current
family actually ships (Literata and Bitter offer Regular→Bold; the others just
Regular/Bold), and *Size* (S/M/L/XL, each labelled with its body px for the
current font, e.g. `M · 25px`) re-paginates on the fly — the build guide's
"on-device font resize" in text mode. A heavier body weight (Medium/SemiBold)
reads better on e-ink, which renders fine strokes a touch thin.
> openly/redistributably licensed (display/personal-use faces; "Palatino" is
> trademarked), so they can't be bundled — the OFL serifs above cover the same
> intent, with `palladio` as the open Palatino. See `NOTICE.md`.

## 1-bit rendering (no anti-aliasing)

The panel is pure black/white — no greys. Two consequences shape the rendering:

**Text** is drawn straight into the 1-bit `Canvas`, where PIL/FreeType uses
**monochrome hinting** — glyph stems are snapped to the pixel grid — so text is
crisp at small sizes (this is what the firmware does too). *Never dither text.*
For legibility, prefer fonts with sturdy stems and a large x-height (Bitter,
Literata) over delicate ones; e-ink also reads slightly thin, so a heavier weight
can help.

**Images** (covers, illustrations) have no good 1-bit form without
**halftoning** — faking grey with the density of black dots. `epd_sim.dither`
offers three methods; see them compared with `python simulator/run.py --demo dither`:

| Method | Use it for |
|--------|-----------|
| `threshold` | line art / already-bilevel art (tone is lost). |
| `ordered` (Bayer 8×8) | **default on e-ink** — deterministic per pixel, so it doesn't shimmer when only part of the screen partial-refreshes. |
| `floyd` (Floyd–Steinberg) | best tonal detail for a cover shown on a full refresh; error diffusion can crawl between partial refreshes. |

```python
from epd_sim import dither
dither.paste(canvas, cover_img, (x, y, w, h), method="ordered", gamma=0.8)
```

The **library cover thumbnails** (`reader/covers.py`) put this into practice:
books with real artwork (`book.cover` → a file in `assets/images/`, here the
public-domain Project Gutenberg covers) are auto-contrasted and ordered-dithered
at exact thumbnail size; books without art fall back to a tonal background plus a
crisp undithered initial. `--demo dither` dithers a real NASA photo three ways.
Sample images are public domain — see `assets/images/NOTICE.md`. Drop a file in
that folder and point a book's `cover=` at it to add your own.

The `gamma` knob pre-lightens midtones (e-ink reads darker than sRGB). Other
practical touches: snap everything to integer pixels (we do), and prefer 2px
rules/borders over 1px hairlines so they render evenly.

## Controls

| Button | Key | Library | Reading |
|--------|-----|---------|---------|
| Back   | ←   | move selection up | previous page |
| Menu   | m / Enter | open selected book | back to library |
| Fwd    | → / Space | move selection down | next page |

Buttons and pin labels match the hardware map in `CLAUDE.md`. Font and
orientation selectors sit above the panel for live switching.

## Layout

```
simulator/
  run.py                 entry point
  epd_sim/
    framebuffer.py        MonoFrameBuffer (device buffer) + Canvas (logical, rotates)
    epd.py                EPD — Waveshare-shaped driver mock + refresh timings
    panel.py              Panel — tkinter window, renders bytes + buttons + selectors
    dither.py             1-bit halftoning for images (threshold/ordered/floyd)
  reader/
    fonts.py              font-family registry (weights + sizes) + per-family metrics
    content.py            Book model, text-mode pagination, sample books
    app.py                ReaderApp — library/reading UX, orientation-aware geometry
    covers.py             procedural dithered 1-bit cover thumbnails
    ruler.py              calibration-ruler screen for --actual-size
    demo_dither.py        the --demo dither comparison card
    assets/fonts/         bundled open fonts + licenses + NOTICE.md
```

## Building your own UI

Draw into a `Canvas` (orientation-aware) with PIL and push it through `panel.epd`:

```python
from epd_sim import Canvas, PORTRAIT
cv = Canvas(PORTRAIT)               # 552×960 logical; LANDSCAPE = 960×552
cv.clear(255)                       # white
cv.draw.text((40, 40), "Hello", fill=0, font=...)
panel.epd.display(cv.packed())          # full refresh (rotates into 960×552)
panel.epd.display_partial(cv.packed())  # partial (page-turn) refresh
```

(`MonoFrameBuffer` is still available for raw landscape 960×552 buffers.) When
porting to firmware, swap `epd_sim.EPD` for the real Waveshare driver and reuse
the same packed-buffer composition — the byte layout already matches.
