from __future__ import annotations

import unittest

from windowswitcher import RECT, visible_marker_positions


class VisibleMarkerPositionTests(unittest.TestCase):
    WINDOW = 1000
    OTHER = 2000

    def test_uncovered_window_keeps_all_positions(self) -> None:
        rect = RECT(0, 0, 1200, 800)
        positions = visible_marker_positions(
            self.WINDOW, rect, probe=lambda x, y: self.WINDOW
        )
        self.assertGreater(len(positions), 1)

    def test_fully_covered_window_gets_no_position(self) -> None:
        rect = RECT(0, 0, 1200, 800)
        positions = visible_marker_positions(
            self.WINDOW, rect, probe=lambda x, y: self.OTHER
        )
        self.assertEqual(positions, [])

    def test_partially_covered_window_keeps_exposed_positions(self) -> None:
        rect = RECT(0, 0, 1200, 800)
        covered_until = 600

        def probe(x: int, y: int) -> int:
            return self.OTHER if x < covered_until else self.WINDOW

        positions = visible_marker_positions(self.WINDOW, rect, probe=probe)
        self.assertTrue(positions)
        self.assertTrue(all(position.x >= covered_until for position in positions))

    def test_narrow_window_uses_single_probe_point(self) -> None:
        rect = RECT(100, 100, 240, 300)
        probed: list[tuple[int, int]] = []

        def probe(x: int, y: int) -> int:
            probed.append((x, y))
            return self.WINDOW

        positions = visible_marker_positions(self.WINDOW, rect, probe=probe)
        self.assertEqual(len(positions), 1)
        self.assertEqual(len(probed), 2)
