# termcade web

The public site for [termcade](https://github.com/aviorstudio/termcade), the
terminal arcade. One static Astro page: what it is, what it comes with, what
the four pixel styles look like, and how to write a game for it.

There is no authentication, no application state, no backend and no runtime
environment configuration — the arcade and its registry are the application,
and this is only the front door. The page ships no JavaScript, which is why
there are no integrations in `astro.config.mjs` and why CI rejects any
executable `<script>` in the build output — external or inline, with only the
`application/ld+json` metadata allowed — and then loads the built page in
headless Chrome (1280×800 and 390×844, 10s link timeout, zero tolerated
console or resource errors; the full list is in `tools/browser-check.mjs`).

## Commands

| Command | Action |
| --- | --- |
| `bun install` | Install dependencies |
| `bun dev` | Start the Astro development server |
| `bun run build` | Generate the static site in `dist/` |
| `bun preview` | Preview the static build |

## The frames

Every terminal frame on the page is a capture of the real arcade, not a
mock-up and not a screenshot. `tools/capture.py` runs termcade on a pty, types
at it, replays the ANSI it writes back into a grid of cells, and prints that
grid as spans:

```sh
python3 tools/capture.py /path/to/termcade   # rewrites src/frames/*.html
```

Text rather than an image, for the same reason the arcade is text: it stays
selectable, it scales with the reader's font, and it cannot go blurry on a
display nobody captured it for. The classes are a one-for-one map of what the
arcade printed — `logo`, `pick`, `on`, `dim` and `edge` are the colours in
`internal/shell/menu.go` and the playfield border, `void` is the black the
canvas clears to, and a `fill-` class is a cell whose background was painted
because the pixel filled the whole cell and left no half-block to draw.

Frames are only ever taken from a full repaint. The arcade sends cell diffs
between them, and a diff replayed against the wrong screen is how you get a
frame with the last one's asteroids still in it; `capture.py` forces a repaint
by resizing the pty and letting the shell redraw.

What is in each one, and what a re-run would change:

- **`asteroid.html`** — the hero. Asteroid a few seconds in, with a wave that
  has been shot at. The rocks are seeded from the clock (`games/asteroid`
  reseeds on `Reset`), so a re-run gets a different field. The HUD, the border,
  the controls hint and the high score are the arcade's own.
- **`index-screen.html`** — the arcade's index. Whatever is in the machine's
  recently-played list is what lands on the page, Brickough included.
- **`pixels-*.html`** — the same ship in the same cells, four times.
  Asteroid starts a wave with the ship dead centre, so these four are
  reproducible and differ in nothing but how a cell is subdivided. They are
  trimmed to the ship's bounding box — the ship's absolute cell can wander by
  one between runs, its shape cannot, and the trimmed margin was the same
  black the page frames them on. They are set at 28px on the page: the type
  is larger, rather than a small capture being scaled up, so a pixel the
  arcade drew is still a pixel you see.

## The capture contract

A capture is only comparable to another capture when the inputs are fixed, so
they are fixed in one place — the docstring of `tools/capture.py` — and
summarised here:

- **Binary**: the GitHub release pinned in `tools/termcade-release`
  (currently v0.0.7), with the SHA-256 of the Linux x86_64 archive committed
  in `tools/termcade-release.sha256` — CI verifies the download against that
  hash, not against checksums hosted beside the release, so replacing release
  assets cannot make CI run an unreviewed binary. `--check` verifies
  `termcade version` against the pin. Bump both files deliberately,
  regenerate, and review the diff.
- **Terminal**: a pty of exactly 96 columns × 30 rows, `TERM=xterm-256color`,
  `COLORTERM=truecolor`.
- **Pixel mode**: `TERMCADE_PIXELS=quad` for the index and hero frames; each
  style for its own crop.
- **Timing**: a game is started from the library screen — every installed
  game, sorted by title — by reading the screen and walking the selection to
  the game's row. Not the index screen: its recent rows are the machine's
  play history, empty on a fresh arcade, and not fixed keystrokes: a fixed
  number of moves on a screen whose rows vary starts a different game on a
  different machine. Keys after launch are typed on a fixed schedule from
  the game's first screen; frames are taken only from full repaints (forced
  by a pty resize); capture ends 1.0s after the last scripted event; a run
  that never reaches the wave is retried rather than captured wrong.

CI runs `python3 tools/capture.py --check` against the pinned release on every
pull request. It regenerates the four `pixels-*.html` in an isolated, empty
state directory and fails if they differ from what is checked in — those four
are deterministic. It cannot do the same for the hero and the index screen:

- **`asteroid.html`** is clock-seeded — `games/asteroid` reseeds on `Reset`,
  so the rock field is different on every run no matter what is pinned.
- **`index-screen.html`** is the capturing machine's library: recently-played
  order and high scores are state, and no two machines share it.

For those two, `--check` asserts structure only (the hero keeps its playfield
border over the cleared canvas, the index keeps a selected row), and freshness
is a review habit rather than a gate: when the arcade's menu, HUD or borders
change, run a full capture against the new release, read the diff of
`asteroid.html` and `index-screen.html` by eye — the rocks and the row order
will move on every run and that is fine; anything else moving is the signal —
and commit it with the release bump that caused it.

## What else is on the page, and where it came from

Nothing is invented. The claims worth re-checking when the arcade changes:

- **The three games and their descriptions** are the arcade's own README. All
  three are starter-pack `.tcade` packages committed in the arcade repository
  and embedded in the binary.
- **The pixel table** — the values, the grids and the font requirements are
  `TERMCADE_PIXELS`', including that `quad` is the default and that `sextant`
  needs Unicode 13 or renders as tofu.
- **The command table** is `usage` in `cli.go`, trimmed to the commands a
  first-time reader needs.
- **The contract list** is `sdk/game.go` and `sdk/input.go`: 60 ticks a second
  off the measured clock, a seven-key vocabulary plus releases where the
  terminal reports them, a canvas in square logical units, a structured HUD the
  shell styles, an sdk that depends on nothing outside the standard library,
  and a frozen wasm ABI v1.
- **The sandbox claims** are `internal/plugin` and `internal/engine`: wazero,
  no filesystem, no network, per-call watchdog deadlines, and `SafeGame`
  turning a panic into a crash screen rather than a dead arcade.
- **The held-key section** is the arcade's input handling: the Kitty keyboard
  protocol's event-type reporting where the terminal answers, and the
  auto-repeat fallback in `sdk.KeyTracker` everywhere else.

**The registry is live.** Released clients use `https://api.termca.de`.
`TERMCADE_REGISTRY` selects a different registry for development; the public
site describes the production path.

## Colour

The palette is the arcade's. `#3fc4c9` is the colour `internal/shell/menu.go`
renders the wordmark in and `#e6c945` the colour it renders the selected row
in; the greys are its normal and dim rows, and the greens and blues that turn
up in a frame are whatever the game drew. Nothing was chosen from a swatch,
which is also why a capture can be pasted in as it came out and still look like
itself.

The page is dark because the product is. A terminal arcade shown on paper is a
picture of something else.

Fonts are the platform's own. No font is fetched, so no visitor's IP reaches a
font CDN and no CSP exception is needed to render the page — and the frames are
drawn by the reader's own monospace font, which is the only way the columns
line up.

## Domain

`src/layouts/Full.astro`, `public/robots.txt` and `public/sitemap.xml` assume
`https://termcade.com`. If the site lands somewhere else, those three files are
the only places the host appears.
