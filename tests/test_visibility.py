from __future__ import annotations

import unittest

from windowswitcher import RECT, clamp_to_work_area, visible_marker_positions


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


class ClampToWorkAreaTests(unittest.TestCase):
    """A maximized window reports the invisible resize border as part of its rect."""

    def test_maximized_window_on_a_negative_origin_monitor(self) -> None:
        rect = RECT(-2251, -11, 11, 1339)
        work = RECT(-2240, 0, 0, 1328)
        placed = clamp_to_work_area(rect, work)
        self.assertEqual(
            (placed.left, placed.top, placed.right, placed.bottom),
            (-2240, 0, 0, 1328),
        )

    def test_markers_stay_on_screen_after_clamping(self) -> None:
        rect = RECT(-2251, -11, 11, 1339)
        work = RECT(-2240, 0, 0, 1328)
        placed = clamp_to_work_area(rect, work)
        positions = visible_marker_positions(1, placed, probe=lambda x, y: 1)
        self.assertTrue(positions)
        self.assertTrue(all(position.y >= work.top for position in positions))
        self.assertTrue(all(work.left <= position.x <= work.right for position in positions))

    def test_window_inside_the_work_area_is_untouched(self) -> None:
        rect = RECT(100, 100, 900, 700)
        placed = clamp_to_work_area(rect, RECT(0, 0, 1920, 1032))
        self.assertEqual(
            (placed.left, placed.top, placed.right, placed.bottom), (100, 100, 900, 700)
        )

    def test_missing_monitor_info_keeps_the_original_rect(self) -> None:
        rect = RECT(10, 20, 300, 400)
        placed = clamp_to_work_area(rect, None)
        self.assertIs(placed, rect)

    def test_window_off_the_work_area_keeps_its_own_rect(self) -> None:
        rect = RECT(500, 500, 800, 800)
        placed = clamp_to_work_area(rect, RECT(0, 0, 100, 100))
        self.assertEqual(
            (placed.left, placed.top, placed.right, placed.bottom), (500, 500, 800, 800)
        )
