#!/usr/bin/env python3
"""Capture termcade screens as the HTML in src/frames/.

The frames on the site are not mock-ups and not screenshots. This runs the real
arcade on a real pty, replays the ANSI it writes into a grid of cells, and
prints that grid as spans — so what the page shows is what the terminal showed,
still selectable, still scaling with the reader's font.

    python3 tools/capture.py /path/to/termcade > /dev/null

Writes src/frames/*.html. Every frame is taken from a full repaint (the arcade
otherwise sends cell diffs, and a diff is only meaningful against the screen it
was diffed from), which is forced by resizing the pty and letting the shell
redraw. Games seed themselves from the clock, so the rocks in the hero frame
are whatever that run rolled; the ship crops are the same five cells in every
style because Asteroid starts a wave with the ship dead centre.
"""
import fcntl
import os
import pty
import re
import signal
import struct
import select
import sys
import termios
import time

ROWS, COLS = 30, 96
FRAMES = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'frames')

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


# --- running it ------------------------------------------------------------

def drive(binary, script, pixels):
    """Run the arcade on a pty, type the script at it, keep everything it says.

    script is a list of (seconds_from_start, keys | 'RESIZE'). RESIZE nudges
    the window and puts it back, which is what makes the shell repaint in full.
    """
    pid, fd = pty.fork()
    if pid == 0:
        env = dict(os.environ, TERM='xterm-256color', COLORTERM='truecolor',
                   TERMCADE_PIXELS=pixels)
        os.execve(binary, [binary], env)
    setwin(fd, ROWS, COLS)
    out = bytearray()
    start = time.time()
    pending = list(script)
    end = pending[-1][0] + 1.0
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
    os.kill(pid, signal.SIGKILL)
    os.waitpid(pid, 0)
    os.close(fd)
    return out.decode('utf-8', 'replace')


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
    # The index screen. Whatever is in the arcade's recently-played list is
    # what lands on the page, so run it against an arcade worth showing.
    menu = drive(binary, [(1.5, 'RESIZE')], 'quad')
    write('index-screen', trim(replay(menu)))

    # The hero: Asteroid, a few seconds in, so there are bullets and a wave
    # that has been shot at rather than an untouched one.
    play = [(1.5, 'l'), (2.0, '\r'), (3.2, ' '), (3.5, 'w'), (4.1, 'd'),
            (4.4, ' '), (4.8, 'w'), (5.4, ' '), (6.4, 'RESIZE')]
    write('asteroid', trim(repaints(drive(binary, play, 'quad'))[-1]))

    # The ship, in each pixel style, from the same cells of the same screen:
    # Asteroid puts the ship dead centre at the start of a wave, so four runs
    # differ in nothing but how a cell is cut up.
    start = [(1.5, 'l'), (2.0, '\r'), (2.6, 'RESIZE')]
    for style in ('quad', 'sextant', 'half', 'ascii'):
        crops = [[row[42:56] for row in frame[12:18]]
                 for frame in repaints(drive(binary, start, style))]
        # A repaint of the library screen is still a repaint, and the wave can
        # be one frame from being drawn: take the last one with a ship in it
        # rather than the last one, and say so if a run never got that far.
        drawn = [c for c in crops if any(cell[0] != ' ' for row in c for cell in row)]
        if not drawn:
            sys.exit(f'{style}: no frame with the ship in it — try again')
        write('pixels-' + style, drawn[-1])


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('usage: capture.py /path/to/termcade')
    main(os.path.abspath(sys.argv[1]))
