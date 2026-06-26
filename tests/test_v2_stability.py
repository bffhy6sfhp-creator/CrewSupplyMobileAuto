from __future__ import annotations

import io
import json
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

import mobile_server
from auto_all_integrated import download_awb_zip


def valid_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("label.pdf", b"%PDF-1.4\n%%EOF")
    return buffer.getvalue()


class FakeJsonResponse:
    status = 201
    url = "https://api.example.invalid/airwaybill/bulk"
    headers = {"content-type": "application/json; charset=utf-8"}

    def json(self):
        return {"url": "https://example.invalid/awb.zip"}

    def text(self):
        return json.dumps(self.json())


class FakeFetchResponse:
    ok = True
    status = 200

    def body(self):
        return valid_zip_bytes()


class FakeRequestContext:
    def get(self, url, timeout=None):
        return FakeFetchResponse()


class FakeTracing:
    def start(self, **kwargs):
        return None

    def stop(self, path=None):
        if path:
            Path(path).write_bytes(b"trace")


class FakeContext:
    def __init__(self):
        self.request = FakeRequestContext()
        self.tracing = FakeTracing()
        self.handlers = {}

    def on(self, event, handler):
        self.handlers[event] = handler

    def remove_listener(self, event, handler):
        self.handlers.pop(event, None)


class FakePage:
    def __init__(self):
        self.context = FakeContext()
        self.handlers = {}
        self.evaluate_calls = 0

    def on(self, event, handler):
        self.handlers[event] = handler

    def remove_listener(self, event, handler):
        self.handlers.pop(event, None)

    def evaluate(self, script):
        self.evaluate_calls += 1
        response_handler = self.handlers.get("response")
        if response_handler:
            response_handler(FakeJsonResponse())
        return {"clicked": True, "text": "Download"}

    def wait_for_timeout(self, milliseconds):
        return None


class V2StabilityTest(unittest.TestCase):
    def test_signed_url_is_primary_download_path_and_clicks_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            dirs = {
                "downloads": base / "Downloads",
                "screenshots": base / "Screenshots",
            }
            for value in dirs.values():
                value.mkdir(parents=True, exist_ok=True)
            page = FakePage()
            saved = download_awb_zip(page, dirs, "account_YOUT", action_timeout=1)
            self.assertTrue(zipfile.is_zipfile(saved))
            self.assertEqual(page.evaluate_calls, 1)
            diagnostics = json.loads((dirs["screenshots"] / "account_YOUT_download_diagnostics.json").read_text(encoding="utf-8"))
            self.assertEqual(diagnostics["click_count"], 1)
            self.assertEqual(diagnostics["json_download_url"], "https://example.invalid/awb.zip")

    def test_old_running_status_with_dead_pid_is_interrupted(self):
        original = mobile_server.STATUS_PATH
        with tempfile.TemporaryDirectory() as tmp:
            mobile_server.STATUS_PATH = Path(tmp) / "status.json"
            mobile_server.STATUS_PATH.write_text(json.dumps({
                "state": "running",
                "pid": 99999999,
                "updated_at": "2020-01-01T00:00:00",
            }), encoding="utf-8")
            value = mobile_server.reconcile_stale_status()
            self.assertEqual(value["state"], "interrupted")
        mobile_server.STATUS_PATH = original

    def test_mobile_home_displays_version(self):
        from fastapi.testclient import TestClient
        response = TestClient(mobile_server.app).get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("APP_VERSION", response.text)
        self.assertIn(mobile_server.APP_VERSION, response.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
