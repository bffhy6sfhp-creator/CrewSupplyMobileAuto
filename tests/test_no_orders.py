from __future__ import annotations

import unittest

from auto_all_integrated import evaluate_to_ship_download_state, has_selectable_orders


class FakeElement:
    def __init__(self, visible=True, enabled=True, attrs=None):
        self.visible = visible
        self.enabled = enabled
        self.attrs = attrs or {}
        self.clicked = False

    def is_visible(self):
        return self.visible

    def is_enabled(self):
        return self.enabled

    def get_attribute(self, name):
        return self.attrs.get(name)

    def click(self, timeout=None):
        if not self.enabled:
            raise AssertionError("disabled element should not be clicked")
        self.clicked = True


class FakeLocator:
    def __init__(self, items=None, text=""):
        self.items = items or []
        self.text = text

    def count(self):
        return len(self.items)

    def nth(self, index):
        return self.items[index]

    def inner_text(self, timeout=None):
        return self.text


class FakePage:
    def __init__(self, body_text="", download_buttons=None, checkboxes=None, timeout=False):
        self.body_text = body_text
        self.download_buttons = download_buttons or []
        self.checkboxes = checkboxes or []
        self.timeout = timeout

    def get_by_text(self, text, exact=True):
        if self.timeout:
            raise TimeoutError("page timed out")
        if text == "Download All":
            return FakeLocator(self.download_buttons)
        return FakeLocator([])

    def locator(self, selector):
        if self.timeout:
            raise TimeoutError("page timed out")
        if selector == "body":
            return FakeLocator(text=self.body_text)
        if selector in {"input[type='checkbox']", "[role='checkbox']"}:
            return FakeLocator(self.checkboxes)
        return FakeLocator([])


class NoOrdersDetectionTest(unittest.TestCase):
    def test_normal_download_ready(self):
        page = FakePage(
            body_text="3 orders",
            download_buttons=[FakeElement()],
            checkboxes=[FakeElement()],
        )
        self.assertTrue(has_selectable_orders(page))
        self.assertEqual(evaluate_to_ship_download_state(page), "ready")

    def test_download_all_disabled(self):
        cases = [
            FakeElement(enabled=False),
            FakeElement(attrs={"disabled": ""}),
            FakeElement(attrs={"aria-disabled": "true"}),
            FakeElement(attrs={"class": "pointer-events-none"}),
            FakeElement(attrs={"class": "cursor-not-allowed"}),
            FakeElement(attrs={"class": "opacity-50"}),
        ]
        for button in cases:
            with self.subTest(attrs=button.attrs, enabled=button.enabled):
                page = FakePage(
                    body_text="3 orders",
                    download_buttons=[button],
                    checkboxes=[FakeElement()],
                )
                self.assertEqual(evaluate_to_ship_download_state(page), "no_orders")
                self.assertFalse(button.clicked)

    def test_download_all_missing(self):
        page = FakePage(body_text="3 orders", download_buttons=[], checkboxes=[FakeElement()])
        self.assertEqual(evaluate_to_ship_download_state(page), "no_orders")

    def test_real_page_timeout_propagates(self):
        page = FakePage(timeout=True)
        with self.assertRaises(TimeoutError):
            evaluate_to_ship_download_state(page)


if __name__ == "__main__":
    unittest.main(verbosity=2)
