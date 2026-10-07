import unittest
from unittest.mock import patch

import capture


def paint(visible):
    # Actual terminal escape sequences: a cleared black canvas, fixed HUD,
    # and the same ship glyph when the simulation is in its visible phase.
    frame = '\x1b[H\x1b[2J\x1b[48;2;0;0;0m'
    frame += '\x1b[1;1HASTEROID\x1b[25;1HSCORE 000000  WAVE 1'
    frame += '\x1b[15;47H'
    frame += '\x1b[38;2;242;242;242m▗' if visible else ' '
    return frame.encode()


class CaptureTimingTests(unittest.TestCase):
    def test_blank_blink_is_not_a_ship_capture(self):
        self.assertIsNone(capture.ship_crop(capture.replay(paint(False).decode())))

    def test_waits_past_empty_blink_for_a_visible_real_terminal_paint(self):
        with patch.object(capture.select, 'select', return_value=([7], [], [])), \
                patch.object(capture.os, 'read', return_value=paint(True)):
            data = capture.read_ship_frame(7, 'ASTEROID', bytearray(paint(False)), limit=1)
        self.assertIn('▗', capture.to_html(capture.ship_crop(capture.replay(data))))

    def test_missing_game_frame_fails_instead_of_accepting_empty_content(self):
        with patch.object(capture.select, 'select', return_value=([7], [], [])), \
                patch.object(capture.os, 'read', return_value=b''):
            with self.assertRaises(capture.LaunchError):
                capture.read_ship_frame(7, 'ASTEROID', bytearray(paint(False)), limit=1)

    def test_white_background_half_pixel_is_part_of_the_ship(self):
        screen = [[capture.BLANK] * capture.COLS for _ in range(capture.ROWS)]
        screen[14][46] = (' ', None, (242, 242, 242), False)
        self.assertEqual(len(capture.ship_crop(screen)), 1)


if __name__ == '__main__':
    unittest.main()
