#!/usr/bin/env python3
"""Capture termcade screens as the HTML in src/frames/.

The frames on the site are not mock-ups and not screenshots. This runs the real
arcade on a real pty, replays the ANSI it writes into a grid of cells, and
prints that grid as spans — so what the page shows is what the terminal showed,
still selectable, still scaling with the reader's font.

    python3 tools/capture.py /path/to/termcade > /dev/null   # refresh all frames
    python3 tools/capture.py --check /path/to/termcade       # CI freshness gate

THE CAPTURE CONTRACT. A capture is only comparable to another capture when all
of this holds, so it is written down once, here, and enforced by --check:

- binary: the GitHub release pinned in tools/termcade-release, nothing else.
  --check verifies `termcade version` against it; a full run warns on anything
  else. CI verifies the downloaded archive against the SHA-256 committed in
  tools/termcade-release.sha256 — the release's own checksums sit beside the
  assets and could be replaced with them. Bump the pin deliberately,
  regenerate, and review the diff.
- terminal: a pty of exactly 96 columns x 30 rows (ROWS, COLS below), with
  TERM=xterm-256color and COLORTERM=truecolor.
- pixel mode: TERMCADE_PIXELS=quad for the index and hero frames; each style
  for its own ship crop.
- timing: a game is started from the library screen — every installed game,
  sorted by title — by reading the screen and walking the selection to the
  game's row. Not the index screen: its recent rows are the machine's play
  history, empty on a fresh arcade and ordered by it everywhere else, and not
  fixed keystrokes: a fixed number of moves on a screen whose rows vary
  starts a different game on a different machine. The library is read until
  the game's row and the selection marker are on it, up to 30s — a cold
  state directory is unpacked between the logo and the list, and "the output
  went quiet" is not a menu. Once the game is up, keys are typed on a fixed
  schedule in seconds from the game's first screen (the scripts in main). A frame is only ever taken from a full repaint — the
  arcade otherwise sends cell diffs, and a diff is only meaningful against the
  screen it was diffed from — which is forced by nudging the pty size and
  letting the shell redraw. A repaint segment shorter than 400 bytes is a
  redraw cut off by the next one and is dropped. Capture ends 1.0s after the
  last scripted event; the pty is polled every 20ms; the resize nudge settles
  for 150ms. A run that never reaches the wave is retried (ATTEMPTS) rather
  than captured wrong.

WHAT --check GATES. Pixel-style captures wait for a complete game screen with
SCORE/WAVE and a visible white ship, bounded to 30s per launch. They crop to the
ship's white bounds and reject a clock-seeded rock crossing those bounds. The
initial invulnerability blink cannot select an empty capture. The timing and
resize script above still applies to the nondeterministic hero/index frames.
The four pixels-*.html crops are deterministic in shape:
Asteroid starts every wave with the ship dead centre and untouched, so a
re-run of the pinned binary draws the same ship in the same pixels. Its
absolute cell can wander by one between runs (sub-cell spawn rounding), so the
crops are written and compared trimmed to the ship's bounding box — position
is presentation, shape is content. --check fails if the checked-in files
differ byte for byte. asteroid.html is clock-seeded (games/asteroid reseeds on
Reset) and index-screen.html reflects the capturing machine's library and
recently-played order, so exact comparison would be a coin flip dressed as a
gate; --check asserts only their deterministic structure and the README
describes how they are reviewed and refreshed. --check runs against an
isolated, empty state directory, because a fresh arcade is the only
reproducible one.
"""
import difflib
import fcntl
import os
import pty
import re
import signal
import struct
import select
import subprocess
import sys
import tempfile
import termios
import time
from html.parser import HTMLParser

ROWS, COLS = 30, 96
ATTEMPTS = 3
FRAMES = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'frames')
RELEASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'termcade-release')

# The arcade's own colours, named so the markup reads as a palette rather than
# as c0..cN. Sources: internal/shell/menu.go for the wordmark, the selected row
# and the normal row; the playfield border; and the games' own drawing.
NAMES = {
    (63, 196, 201): 'logo',
    (230, 201, 69): 'pick',
    (242, 242, 242): 'on',
    (138, 138, 138): 'dim',
    (58, 58, 58): 'edge',
    (79, 201, 100): 'green',
    (79, 125, 224): 'blue',
    (0, 0, 0): 'void',
}
BLANK = (' ', None, None, False)


class LaunchError(Exception):
    """The game never came up: its row was missing from the index, or the
    screen after Enter was not its game screen. Transient (a slow unpack, a
    half-read menu), so callers retry."""


# --- running it ------------------------------------------------------------

def drive(binary, script, pixels):
    """Run the arcade on a pty, type the script at it, keep everything it says.

    script is a list of (seconds_from_start, keys | 'RESIZE'). RESIZE nudges
    the window and puts it back, which is what makes the shell repaint in full.
    """
    pid, fd = fork(binary, pixels)
    try:
        out = bytearray()
        play(fd, pid, script, out)
        return out.decode('utf-8', 'replace')
    finally:
        reap(pid, fd)


def drive_game(binary, game, script, pixels, *, ship_frame=False):
    """Start `game` from the library — wherever the library happens to list
    it — then play `script`, timed in seconds from the game's first screen,
    and keep everything the arcade said from the first menu paint onward."""
    pid, fd = fork(binary, pixels)
    try:
        out = read_menu(fd, game)
        if out is None:
            raise LaunchError(f'the library screen never listed {game} — '
                              'the arcade is slower than the capture contract '
                              'allows')
        rows = [''.join(ch for ch, _, _, _ in row)
                for row in replay(out.decode('utf-8', 'replace'))]
        selected = next((i for i, r in enumerate(rows) if '▸' in r), None)
        target = next((i for i, r in enumerate(rows) if game in r), None)
        if selected is None or target is None:
            raise LaunchError(f'the library screen has no row for {game} — '
                              'is this the pinned release?')
        moves = target - selected
        os.write(fd, (b'j' if moves > 0 else b'k') * abs(moves))
        # Wait until the selection actually sits on the game's row before
        # committing to it — a busy runner can take a moment per move, and an
        # Enter against a selection that has not landed starts the wrong game.
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if not select.select([fd], [], [], 0.05)[0]:
                continue
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
            rows = [''.join(ch for ch, _, _, _ in row)
                    for row in replay(out.decode('utf-8', 'replace'))]
            if target < len(rows) and '▸' in rows[target]:
                break
        os.write(fd, b'\r')
        if ship_frame:
            return read_ship_frame(fd, game, out)
        play(fd, pid, script, out)
        text = out.decode('utf-8', 'replace')
        # The menu alone contains the name, so check the settled final screen:
        # the game is up when its name is on a screen with the canvas's black
        # behind it — the menu never paints a background.
        screen = replay(text)
        final = '\n'.join(''.join(ch for ch, _, _, _ in row) for row in screen)
        has_canvas = any(bg == (0, 0, 0) for row in screen for _, _, bg, _ in row)
        if not (has_canvas and game in final):
            raise LaunchError(f'{game} did not start — the keys reached the '
                              'arcade but the game screen never came up')
        return text
    finally:
        reap(pid, fd)



def ship_crop(screen):
    """The white ship's bounds, excluding clock-seeded rocks and blank blinks."""
    crop = [row[42:56] for row in screen[12:18]]
    white = (242, 242, 242)
    points = [(r, c) for r, row in enumerate(crop) for c, (_, fg, bg, _) in enumerate(row)
              if fg == white or bg == white]
    if not points:
        return None
    top, bottom = min(r for r, _ in points), max(r for r, _ in points)
    left, right = min(c for _, c in points), max(c for _, c in points)
    frame = [row[left:right + 1] for row in crop[top:bottom + 1]]
    # A rock crossing these cells is not part of the ship's deterministic bitmap.
    if any(fg not in (None, white, (0, 0, 0)) or bg not in (None, white, (0, 0, 0))
           for row in frame for _, fg, bg, _ in row):
        return None
    return frame


def read_ship_frame(fd, game, out, limit=30.0):
    """Wait for a complete game paint with a visible ship, not a timed blink.

    The pinned game blinks every four ticks during its initial invulnerability.
    A fixed wall-clock sample can therefore be empty on a faster runner.
    The first intact visible ship is content; the tick it arrives on is not.
    """
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        screen = replay(out.decode('utf-8', 'replace'))
        rows = [''.join(ch for ch, _, _, _ in row) for row in screen]
        if (any(game in row for row in rows) and any('SCORE' in row and 'WAVE' in row for row in rows)
                and any(bg == (0, 0, 0) for row in screen for _, _, bg, _ in row)
                and ship_crop(screen) is not None):
            return out.decode('utf-8', 'replace')
        if not select.select([fd], [], [], 0.02)[0]:
            continue
        try:
            chunk = os.read(fd, 65536)
        except OSError:
            break
        if not chunk:
            break
        out += chunk
    raise LaunchError(f'{game} produced no complete visible ship frame within {limit}s')


def reap(pid, fd):
    """Kill the arcade and close its pty, however the capture ended. Every
    path through drive/drive_game — clean, LaunchError, an interrupted read,
    a Ctrl-C — owes the runner no leftover process and no open fd."""
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        os.waitpid(pid, 0)
    except ChildProcessError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


def fork(binary, pixels):
    pid, fd = pty.fork()
    if pid == 0:
        env = dict(os.environ, TERM='xterm-256color', COLORTERM='truecolor',
                   TERMCADE_PIXELS=pixels)
        os.execve(binary, [binary], env)
    setwin(fd, ROWS, COLS)
    return pid, fd


def read_menu(fd, game, limit=30.0):
    """Read the index, open the library with 'l', and read until the library
    lists `game` next to a selection marker.

    The library, not the index: the index's recent rows are the machine's
    play history — empty on a fresh arcade, ordered by it everywhere else —
    while the library is every installed game sorted by title, the same rows
    on any machine with the same games installed. And not "until the output
    goes quiet": a cold state directory is unpacked between the logo and the
    list, and on a slow runner that pause outlasts any idle threshold that
    does not also add seconds to every warm run. The screen containing the
    row is the only honest signal."""
    out = bytearray()
    start = time.time()
    opened = False
    while time.time() - start < limit:
        if not select.select([fd], [], [], 0.05)[0]:
            continue
        try:
            chunk = os.read(fd, 65536)
        except OSError:
            break
        if not chunk:
            break
        out += chunk
        rows = [''.join(ch for ch, _, _, _ in row)
                for row in replay(out.decode('utf-8', 'replace'))]
        if not opened:
            if any('▸' in r for r in rows):
                os.write(fd, b'l')
                opened = True
        # The title row, not the index's '→ LIBRARY' action: the index of a
        # machine with history can list the game itself, and navigating that
        # would walk the wrong screen.
        elif (any(r.strip() == 'LIBRARY' for r in rows)
              and any('▸' in r for r in rows)
              and any(game in r for r in rows)):
            return out
    return None


def play(fd, pid, script, out):
    """Type the timed script at the pty, appending everything the arcade says
    while it runs."""
    start = time.time()
    pending = list(script)
    end = (pending[-1][0] if pending else 0.0) + 1.0
    while time.time() - start < end:
        while pending and pending[0][0] <= time.time() - start:
            _, keys = pending.pop(0)
            if keys == 'RESIZE':
                setwin(fd, ROWS, COLS - 1)
                os.kill(pid, signal.SIGWINCH)
                time.sleep(0.15)
                setwin(fd, ROWS, COLS)
                os.kill(pid, signal.SIGWINCH)
            else:
                os.write(fd, keys.encode())
        if select.select([fd], [], [], 0.02)[0]:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            out += chunk


def setwin(fd, rows, cols):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))


# --- reading it back -------------------------------------------------------

class Screen:
    """Only as much terminal as the arcade actually uses: absolute cursor
    moves, erase-display, erase-character, truecolor SGR."""

    def __init__(self):
        self.cells = [[BLANK] * COLS for _ in range(ROWS)]
        self.r = self.c = 0
        self.fg = self.bg = None
        self.bold = False

    def put(self, ch):
        if self.c < COLS and 0 <= self.r < ROWS:
            self.cells[self.r][self.c] = (ch, self.fg, self.bg, self.bold)
        self.c += 1

    def sgr(self, params):
        ps = params.split(';') if params else ['0']
        i = 0
        while i < len(ps):
            v = ps[i] or '0'
            if v == '0':
                self.fg = self.bg = None
                self.bold = False
            elif v == '1':
                self.bold = True
            elif v == '39':
                self.fg = None
            elif v == '49':
                self.bg = None
            elif v in ('38', '48') and i + 4 < len(ps) and ps[i + 1] == '2':
                colour = (int(ps[i + 2]), int(ps[i + 3]), int(ps[i + 4]))
                if v == '38':
                    self.fg = colour
                else:
                    self.bg = colour
                i += 4
            i += 1


def replay(data):
    s = Screen()
    i = 0
    while i < len(data):
        ch = data[i]
        if ch == '\x1b':
            m = re.match(r'\x1b\[([0-9;?<>=]*)([a-zA-Z])', data[i:])
            if m:
                params, cmd = m.group(1), m.group(2)
                i += m.end()
                if cmd == 'H' and not params.startswith('?'):
                    p = [int(x) if x else 1 for x in params.split(';')] if params else [1, 1]
                    s.r, s.c = p[0] - 1, (p[1] - 1 if len(p) > 1 else 0)
                elif cmd == 'J' and params in ('', '0', '2'):
                    s.cells = [[BLANK] * COLS for _ in range(ROWS)]
                elif cmd == 'X':
                    n = int(params) if params else 1
                    for c in range(s.c, min(COLS, s.c + n)):
                        s.cells[s.r][c] = (' ', None, s.bg, False)
                elif cmd == 'm':
                    s.sgr(params)
                elif cmd in 'ABCD':
                    n = int(params) if params else 1
                    s.r += {'A': -n, 'B': n}.get(cmd, 0)
                    s.c += {'C': n, 'D': -n}.get(cmd, 0)
                continue
            m = re.match(r'\x1b\][^\x07\x1b]*(\x07|\x1b\\)', data[i:])
            i += m.end() if m else 2
            continue
        if ch == '\n':
            s.r, s.c, i = s.r + 1, 0, i + 1
        elif ch == '\r':
            s.c, i = 0, i + 1
        elif ch in '\x00\x07':
            i += 1
        else:
            s.put(ch)
            i += 1
    return s.cells


def repaints(data):
    """Every full repaint of a game screen, each replayed from blank so no
    earlier screen leaks into it. A repaint is the only frame worth taking:
    everything between two of them is a diff against the last one.

    Game screens are drawn with absolute cursor moves only, so the first
    newline after a clear is where the repaint ended and the diffs began.
    Anything too short to be a screen is a repaint that was cut off by the next
    one — the arcade redraws twice around a resize — and is dropped rather than
    returned half-drawn."""
    out = []
    for m in re.finditer(re.escape('\x1b[H\x1b[2J'), data):
        tail = data[m.start():]
        stop = re.search(r'[\r\n\t]', tail)
        seg = tail[:stop.start()] if stop else tail
        if len(seg) > 400:
            out.append(replay(seg))
    return out


# --- writing it out --------------------------------------------------------

def classes(row):
    """One class key per cell, with blanks folded into the run around them so a
    line of words does not come out as one span per word."""
    keys = []
    for ch, fg, bg, bold in row:
        if ch == ' ' or fg == (0, 0, 0):
            fg, bold = None, False
        keys.append((fg, bg, bold))
    for i, (ch, _, _, _) in enumerate(row):
        if ch != ' ' or keys[i][1] is not None:
            continue
        before = next((keys[j] for j in range(i - 1, -1, -1) if row[j][0] != ' '), None)
        after = next((keys[j] for j in range(i + 1, len(row)) if row[j][0] != ' '), None)
        if before is not None and before == after:
            keys[i] = before
    return keys


def to_html(frame):
    lines = []
    for row in frame:
        end = len(row)
        while end and row[end - 1][0] in ' \t' and row[end - 1][2] is None:
            end -= 1
        keys, line, run, cur = classes(row), '', '', object()
        for i in range(end):
            if keys[i] != cur:
                line += span(cur, run)
                run, cur = '', keys[i]
            run += {'&': '&amp;', '<': '&lt;', '>': '&gt;'}.get(row[i][0], row[i][0])
        lines.append(line + span(cur, run))
    return '\n'.join(lines)


def span(key, text):
    if not text:
        return ''
    fg, bg, bold = key
    names = ([NAMES[fg]] if fg else []) + \
            (['void' if bg == (0, 0, 0) else 'fill-' + NAMES[bg]] if bg else []) + \
            (['b'] if bold else [])
    return f'<span class="{" ".join(names)}">{text}</span>' if names else text


def trim(frame):
    """Drop the blank margin the screen is centred in, keeping every row and
    column between the first and last thing drawn."""
    rows = [i for i, r in enumerate(frame) if any(c[0] != ' ' for c in r)]
    if not rows:
        return []
    frame = frame[rows[0]:rows[-1] + 1]
    left = min(min((i for i, c in enumerate(r) if c[0] != ' '), default=COLS) for r in frame)
    right = max(max((i for i, c in enumerate(r) if c[0] != ' '), default=0) for r in frame)
    return [r[left:right + 1] for r in frame]


def write(name, frame):
    path = os.path.join(FRAMES, name + '.html')
    with open(path, 'w') as f:
        f.write(to_html(frame) + '\n')
    print(f'{path}: {len(frame)} rows', file=sys.stderr)


def main(binary):
    warn_unpinned(binary)

    # The index screen. Whatever is in the arcade's recently-played list is
    # what lands on the page, so run it against an arcade worth showing.
    menu = drive(binary, [(1.5, 'RESIZE')], 'quad')
    write('index-screen', trim(replay(menu)))

    # The hero: Asteroid, a few seconds in, so there are bullets and a wave
    # that has been shot at rather than an untouched one. Timed from the
    # game's first screen.
    play = [(1.2, ' '), (1.5, 'w'), (2.1, 'd'),
            (2.4, ' '), (2.8, 'w'), (3.4, ' '), (4.4, 'RESIZE')]
    try:
        hero = drive_game(binary, 'ASTEROID', play, 'quad')
    except LaunchError as e:
        sys.exit(str(e))
    write('asteroid', trim(repaints(hero)[-1]))

    for style, frame in pixels_frames(binary):
        # Trimmed to the ship's bounding box: the absolute cell can wander by
        # one between runs, the ship cannot, and the painted black margin is
        # the same black the page frames them on. Trimming is what makes these
        # four files byte-for-byte reproducible, which is what --check gates.
        write('pixels-' + style, trim(frame))


def pixels_frames(binary):
    """Capture each style on its first complete visible ship paint.

    Ship shape is deterministic; its invulnerability blink and the rocks are
    driven by simulation ticks. Do not use runner speed to select that content.
    """
    for style in ('quad', 'sextant', 'half', 'ascii'):
        yield style, wave_frame(binary, style)


def wave_frame(binary, style):
    """Keep the exact bitmap comparison, retrying only a failed game launch."""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            data = drive_game(binary, 'ASTEROID', [], style, ship_frame=True)
        except LaunchError as e:
            print(f'{style}: attempt {attempt}/{ATTEMPTS}: {e}', file=sys.stderr)
            continue
        return ship_crop(replay(data))
    sys.exit(f'{style}: no visible ship frame in {ATTEMPTS} attempts')


# --- structural assertions for the nondeterministic frames ------------------

class FrameHTML(HTMLParser):
    """Parse a frame file back into rows of (text, frozenset(classes)) spans.
    Only understands what to_html emits: <span class="...">escaped text</span>
    runs and bare text."""

    def __init__(self):
        super().__init__()
        self.rows = [[]]
        self.classes = frozenset()

    def handle_starttag(self, tag, attrs):
        if tag == 'span':
            self.classes = frozenset(dict(attrs).get('class', '').split())

    def handle_data(self, data):
        for i, line in enumerate(data.split('\n')):
            if i:
                self.rows.append([])
            if line:
                self.rows[-1].append((line, self.classes))

    def handle_endtag(self, tag):
        if tag == 'span':
            self.classes = frozenset()


def parse_frame(path):
    with open(path) as f:
        parser = FrameHTML()
        parser.feed(f.read())
    return parser.rows


def cells(row):
    return [(ch, classes) for text, classes in row for ch in text]


def row_text(row):
    return ''.join(text for text, _ in row)


def check_asteroid(rows):
    """The hero frame, seed-independent: a HUD title row, a rectangular
    playfield border of the arcade's edge style with the canvas painted
    edge-to-edge inside it, and the score/hint row below. A truncated file
    loses the bottom border; an unrelated fragment has no rectangle at all."""
    problems = []
    texts = [row_text(r) for r in rows]
    if not any(classes >= {'pick', 'b'} and text.strip() == 'ASTEROID'
               for text, classes in rows[0]):
        problems.append('title row has no pick-styled ASTEROID')
    if 'HIGH' not in texts[0]:
        problems.append('title row has no HIGH score')
    top = next((i for i, t in enumerate(texts)
                if re.fullmatch(r'\s*╭─+╮\s*', t)), None)
    bottom = next((i for i, t in enumerate(texts)
                   if re.fullmatch(r'\s*╰─+╯\s*', t)), None)
    if top is None or bottom is None or bottom <= top:
        problems.append('no rectangular playfield border (╭─╮ top, ╰─╯ bottom)')
        return problems
    width = len(texts[top].strip())
    if texts[top].count('─') != texts[bottom].count('─'):
        problems.append('top and bottom playfield borders differ in width')
    for i in range(top + 1, bottom):
        cs = [(ch, c) for ch, c in cells(rows[i]) if ch != ' ' or c]
        line = texts[i].strip()
        if len(line) != width:
            problems.append(f'playfield row {i + 1} is wider or narrower than the border')
            continue
        if not (cs[0][0] == '│' and 'edge' in cs[0][1]):
            problems.append(f'playfield row {i + 1} does not start with the edge border')
        if not (cs[-1][0] == '│' and 'edge' in cs[-1][1]):
            problems.append(f'playfield row {i + 1} does not end with the edge border')
        unpainted = [ch for ch, c in cs[1:-1] if 'void' not in c]
        if unpainted:
            problems.append(f'playfield row {i + 1} has cells without the painted canvas')
    last = next((t for t in reversed(texts) if t.strip()), '')
    for want in ('SCORE', 'WAVE', 'fire'):
        if want not in last:
            problems.append(f'score row is missing {want!r}')
    return problems


def check_index_screen(rows):
    """The index screen, history-independent: the three-row wordmark in the
    logo style, exactly one selection marker on exactly one selected row, the
    library action, and the controls hint at the bottom."""
    problems = []
    texts = [row_text(r) for r in rows]
    logo = [i for i, r in enumerate(rows)
            if any({'logo', 'b'} <= c and ('██' in t or '▄▄' in t)
                   for t, c in r)]
    if len(logo) != 3 or logo != list(range(logo[0], logo[0] + len(logo))):
        problems.append('the wordmark is not three consecutive logo rows')
    markers = [i for i, t in enumerate(texts) if '▸' in t]
    if len(markers) != 1:
        problems.append(f'expected exactly one selection marker, found {len(markers)}')
    else:
        row = rows[markers[0]]
        if not any('pick' in c and t.startswith('▸')
                   for t, c in row):
            problems.append('the selection marker is not on a pick-styled row')
    if sum(t.count('▸') for t in texts) != len(markers):
        problems.append('a row carries more than one selection marker')
    if not any(t.strip() == '→ LIBRARY' for t in texts):
        problems.append('no → LIBRARY action row')
    hint = next((t for t in reversed(texts) if t.strip()), '')
    if 'select' not in hint or 'enter' not in hint:
        problems.append('the bottom row is not the controls hint')
    return problems


# --- the freshness gate ----------------------------------------------------

def expected_release():
    with open(RELEASE) as f:
        return f.read().strip()


def binary_version(binary):
    out = subprocess.run([binary, 'version'], capture_output=True, text=True,
                         timeout=10)
    return out.stdout.strip()


def warn_unpinned(binary):
    tag = expected_release()
    version = binary_version(binary)
    if not version.startswith(f'termcade {tag}'):
        print(f'warning: {binary} is {version!r}, not the pinned release '
              f'{tag} — frames captured from it will fail --check',
              file=sys.stderr)


def check(binary):
    """Fail if the deterministic captures are stale. Nondeterministic frames
    are asserted on structure only; anything exact would be gating a dice
    roll."""
    tag = expected_release()
    version = binary_version(binary)
    if not version.startswith(f'termcade {tag}'):
        sys.exit(f'{binary} is {version!r}, not the pinned release {tag} — '
                 'captures must come from the release in tools/termcade-release')

    # A fresh arcade is the only reproducible one: recently-played order and
    # high scores are state, and state the runner happens to have must not
    # leak into a capture. That means the config directory too -- scores live
    # in os.UserConfigDir(), not next to the games.
    with tempfile.TemporaryDirectory() as state:
        os.environ['HOME'] = state
        os.environ['XDG_DATA_HOME'] = state
        os.environ['XDG_CONFIG_HOME'] = state
        fresh = {style: to_html(trim(frame)) + '\n'
                 for style, frame in pixels_frames(binary)}

    stale = []
    for style, text in fresh.items():
        name = f'pixels-{style}.html'
        try:
            with open(os.path.join(FRAMES, name)) as f:
                committed = f.read()
                if committed != text:
                    stale.append(name)
                    print(''.join(difflib.unified_diff(
                        committed.splitlines(keepends=True), text.splitlines(keepends=True),
                        fromfile='checked-in/' + name, tofile='generated/' + name)),
                        file=sys.stderr)
        except FileNotFoundError:
            stale.append(name + ' (missing)')
    if stale:
        sys.exit('stale capture(s): ' + ', '.join(stale) + ' — regenerate with '
                 '`python3 tools/capture.py <binary>` against the pinned '
                 'release and review the diff')

    # The clock-seeded hero and the machine-state index screen cannot be
    # compared exactly. What can be asserted is that they are the screens they
    # claim to be, structurally: the hero keeps its HUD, its rectangular
    # playfield border and its fully painted canvas; the index keeps its
    # wordmark, exactly one selected row, the library action and the hint.
    for name, examine in (('asteroid.html', check_asteroid),
                          ('index-screen.html', check_index_screen)):
        path = os.path.join(FRAMES, name)
        if not os.path.exists(path):
            sys.exit(f'{name}: missing — regenerate with '
                     '`python3 tools/capture.py <binary>`')
        problems = examine(parse_frame(path))
        if problems:
            sys.exit(f'{name}: not the screen it claims to be — '
                     + '; '.join(problems)
                     + '. Regenerate with `python3 tools/capture.py <binary>` '
                     'and review the diff')
    print('captures are fresh: pixels-*.html match the pinned release '
          f'{tag} byte for byte; asteroid.html and index-screen.html have '
          'their expected structure', file=sys.stderr)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--check':
        check(os.path.abspath(sys.argv[2]))
    elif len(sys.argv) == 2:
        main(os.path.abspath(sys.argv[1]))
    else:
        sys.exit('usage: capture.py [--check] /path/to/termcade')
