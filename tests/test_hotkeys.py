from __future__ import annotations

import unittest

from windowswitcher import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_SHIFT,
    VK_ESCAPE,
    key_name,
    parse_hotkey,
)


class HotkeyParsingTests(unittest.TestCase):
    def test_single_modifier_and_letter(self) -> None:
        self.assertEqual(parse_hotkey("alt+q"), (MOD_ALT, ord("Q")))

    def test_multiple_modifiers_and_named_key(self) -> None:
        self.assertEqual(
            parse_hotkey("ctrl+alt+space"), (MOD_CONTROL | MOD_ALT, 0x20)
        )

    def test_tokens_are_case_and_space_insensitive(self) -> None:
        self.assertEqual(parse_hotkey(" Shift + F5 "), (MOD_SHIFT, 0x74))

    def test_key_without_modifier_is_allowed(self) -> None:
        self.assertEqual(parse_hotkey("f12"), (0, 0x7B))

    def test_invalid_hotkeys_are_rejected(self) -> None:
        for text in ("alt", "alt+", "alt+q+w", "alt+nope", ""):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_hotkey(text)


class KeyNameTests(unittest.TestCase):
    def test_letters_map_to_lowercase(self) -> None:
        self.assertEqual(key_name(ord("Q")), "q")

    def test_escape_and_backspace_have_names(self) -> None:
        self.assertEqual(key_name(VK_ESCAPE), "escape")
        self.assertEqual(key_name(0x08), "backspace")

    def test_other_keys_have_no_action(self) -> None:
        self.assertIsNone(key_name(0x20))
        self.assertIsNone(key_name(0x70))
