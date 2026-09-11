from __future__ import annotations

import unittest

from windowswitcher import KEY_ORDER, label_for, labels


class LabelTests(unittest.TestCase):
    def test_first_labels_use_key_order(self) -> None:
        self.assertEqual(labels(len(KEY_ORDER)), list(KEY_ORDER))

    def test_second_and_third_groups_are_prefixed(self) -> None:
        size = len(KEY_ORDER)
        self.assertEqual(label_for(size), "af")
        self.assertEqual(label_for(size * 2 - 1), "ay")
        self.assertEqual(label_for(size * 2), "sf")
        self.assertEqual(label_for(size * 3 - 1), "sy")

    def test_labels_are_unique(self) -> None:
        generated = labels(100)
        self.assertEqual(len(generated), len(set(generated)))

    def test_negative_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            label_for(-1)
        with self.assertRaises(ValueError):
            labels(-1)
