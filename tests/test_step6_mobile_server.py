from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient

import mobile_server

ROOT = Path(__file__).resolve().parents[1]


class FakeProcess:
    next_pid = 9000

    def __init__(self, *args, **kwargs):
        FakeProcess.next_pid += 1
        self.pid = FakeProcess.next_pid
        self.running = True
        self.args = args
        self.kwargs = kwargs

    def poll(self):
        return None if self.running else 0

    def terminate(self):
        self.running = False

    def wait(self, timeout=None):
        self.running = False
        return 0

    def kill(self):
        self.running = False


class Step6MobileServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(mobile_server.app)
        cls.original_popen = mobile_server.subprocess.Popen
        cls.original_status = mobile_server.STATUS_PATH.read_text(encoding="utf-8") if mobile_server.STATUS_PATH.exists() else None
        cls.original_history = mobile_server.HISTORY_PATH.read_text(encoding="utf-8") if mobile_server.HISTORY_PATH.exists() else None
        cls.original_limit_path = mobile_server.REAL_RUN_LIMIT_PATH
        cls.original_runtime_path = mobile_server.RUNTIME_MODE_PATH
        cls.original_production_history_path = mobile_server.PRODUCTION_HISTORY_PATH
        cls.original_report_dir = mobile_server.REPORT_DIR

    @classmethod
    def tearDownClass(cls):
        mobile_server.subprocess.Popen = cls.original_popen
        mobile_server._process = None
        mobile_server.REAL_RUN_LIMIT_PATH = cls.original_limit_path
        mobile_server.RUNTIME_MODE_PATH = cls.original_runtime_path
        mobile_server.PRODUCTION_HISTORY_PATH = cls.original_production_history_path
        mobile_server.REPORT_DIR = cls.original_report_dir
        if cls.original_status is None:
            if mobile_server.STATUS_PATH.exists():
                mobile_server.STATUS_PATH.unlink()
        else:
            mobile_server.STATUS_PATH.write_text(cls.original_status, encoding="utf-8")
        if cls.original_history is None:
            if mobile_server.HISTORY_PATH.exists():
                mobile_server.HISTORY_PATH.unlink()
        else:
            mobile_server.HISTORY_PATH.write_text(cls.original_history, encoding="utf-8")

    def setUp(self):
        mobile_server._process = None
        mobile_server.subprocess.Popen = FakeProcess

    def test_duplicate_start_is_rejected(self):
        first = self.client.post("/run/demo")
        self.assertEqual(first.status_code, 200)
        second = self.client.post("/run/demo")
        self.assertEqual(second.status_code, 409)


    def test_home_page_utf8_chinese_not_garbled(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("charset=utf-8", response.headers.get("content-type", "").lower())
        self.assertIn("CrewSupply \u624b\u673a\u63a7\u5236\u4e2d\u5fc3", response.text)
        self.assertIn("\u5f00\u59cb\u4eca\u65e5\u53d1\u8d27", response.text)
        self.assertIn("\u4e0b\u8f7d\u6700\u65b0Excel", response.text)
        self.assertNotRegex(response.text, r"\?{3,}")



    def test_stopped_production_status_does_not_fallback_to_old_recovery_report(self):
        mobile_server.STATUS_PATH.write_text(json.dumps({
            "state": "failed",
            "message": "?????",
            "current_step": "?????",
            "report": "",
            "success_pdf_count": 0,
            "exception_count": 0,
        }, ensure_ascii=False), encoding="utf-8")
        response = self.client.get("/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["state"], "failed")
        self.assertEqual(payload["current_step"], "?????")
        self.assertEqual(payload["success_pdf_count"], 0)
        self.assertEqual(payload["exception_count"], 0)
        self.assertNotEqual(payload.get("account_YOUT"), "PARTIAL_SUCCESS")

    def test_status_refreshes_counts_from_latest_report(self):
        from shipping_report import create_report
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "shipping_RECOVERY_test.xlsx"
            records = [
                {"account": "account_YOUT", "run_id": "recovery_test", "date": "2026-06-26", "filename": "A 1 9001.pdf", "carrier": "UPS", "status": "SUCCESS", "source_file": "in1.pdf", "output_file": "out1.pdf"},
                {"account": "account_YOUT", "run_id": "recovery_test", "date": "2026-06-26", "filename": "B 1 9002.pdf", "carrier": "USPS", "status": "SUCCESS", "source_file": "in2.pdf", "output_file": "out2.pdf"},
                {"account": "account_YOUT", "run_id": "recovery_test", "date": "2026-06-26", "filename": "C 1 9003.pdf", "carrier": "FEDEX", "status": "SUCCESS", "source_file": "in3.pdf", "output_file": "out3.pdf"},
                {"account": "account_YOUT", "run_id": "recovery_test", "date": "2026-06-26", "sale_id": "90933046", "filename": "90933046.pdf", "status": "ORDER_ON_HOLD", "error": "Order on hold"},
            ]
            create_report(records, report)
            mobile_server.STATUS_PATH.write_text(json.dumps({
                "state": "completed",
                "message": "Offline ZIP recovery completed",
                "report": str(report),
                "success_pdf_count": 0,
                "exception_count": 0,
            }, ensure_ascii=False), encoding="utf-8")
            response = self.client.get("/status")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["success_pdf_count"], 3)
            self.assertEqual(payload["successful_pdfs"], 3)
            self.assertEqual(payload["exception_count"], 1)
            self.assertEqual(payload["exceptions"], 1)
            self.assertEqual(payload["ups_count"], 1)
            self.assertEqual(payload["usps_count"], 1)
            self.assertEqual(payload["fedex_count"], 1)
            self.assertEqual(payload["account_YOUT"], "PARTIAL_SUCCESS")
            self.assertFalse(mobile_server.STATUS_PATH.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_status_json_utf8_chinese_round_trip(self):
        mobile_server.STATUS_PATH.write_text(
            json.dumps({"state": "running", "message": "\u4efb\u52a1\u5df2\u542f\u52a8", "current_step": "\u68c0\u67e5\u8ba2\u5355"}, ensure_ascii=False),
            encoding="utf-8",
        )
        response = self.client.get("/status")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response.headers.get("content-type", "").lower())
        self.assertIn("charset=utf-8", response.headers.get("content-type", "").lower())
        payload = response.json()
        self.assertEqual(payload["message"], "\u4efb\u52a1\u5df2\u542f\u52a8")
        self.assertEqual(payload["current_step"], "\u68c0\u67e5\u8ba2\u5355")
        self.assertIn("\u4efb\u52a1\u5df2\u542f\u52a8", response.text)
        self.assertNotRegex(response.text, r"\?{3,}")

    def test_illegal_download_path_rejected(self):
        with self.assertRaises(HTTPException):
            mobile_server.safe_report_path("..\\private\\account_YOUT.json", "*.xlsx")
        with self.assertRaises(HTTPException):
            mobile_server.safe_report_path("not_a_zip.xlsx", "*.zip")

    def test_stop_without_task_is_ok(self):
        mobile_server._process = None
        response = self.client.post("/stop")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_status_does_not_leak_sensitive_values(self):
        mobile_server.STATUS_PATH.write_text(
            '{"state":"running","message":"ok","Cookie":"abc","path":"' + str(ROOT).replace('\\', '\\\\') + '\\private\\account_YOUT.json"}',
            encoding="utf-8",
        )
        response = self.client.get("/status")
        self.assertEqual(response.status_code, 200)
        body = response.text.lower()
        self.assertNotIn("cookie", body)
        self.assertNotIn("account_yout.json", body)
        self.assertNotIn("private", body)


    def configure_runtime_files(self, tmp: str, production: bool = True):
        base = Path(tmp)
        limit = base / "real_run_limit.json"
        runtime = base / "runtime_mode.json"
        history = base / "production_run_history.json"
        limit.write_text(json.dumps({"allowed_real_runs": 2, "completed_real_runs": 2, "remaining_real_runs": 0, "runs": []}), encoding="utf-8")
        runtime.write_text(json.dumps({
            "mode": "production" if production else "testing",
            "production_enabled": production,
            "allow_mobile_run": production,
            "max_runs_per_day": 1,
            "require_confirmation": True,
            "show_account_debug": False,
        }), encoding="utf-8")
        history.write_text(json.dumps({"runs": [], "manual_resets": []}), encoding="utf-8")
        mobile_server.REAL_RUN_LIMIT_PATH = limit
        mobile_server.RUNTIME_MODE_PATH = runtime
        mobile_server.PRODUCTION_HISTORY_PATH = history
        return limit, runtime, history

    def test_testing_mode_real_run_limit_blocks_run_all_without_popen(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.configure_runtime_files(tmp, production=False)
            response = self.client.post("/run/all")
            self.assertEqual(response.status_code, 403)
            self.assertIsNone(mobile_server._process)

    def test_production_mode_independent_from_test_real_run_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            limit, _runtime, history = self.configure_runtime_files(tmp, production=True)
            response = self.client.post("/run/all")
            self.assertEqual(response.status_code, 200)
            command = mobile_server._process.args[0]
            self.assertIn("--production-run", command)
            payload = json.loads(limit.read_text(encoding="utf-8"))
            self.assertEqual(payload["completed_real_runs"], 2)
            production_history = json.loads(history.read_text(encoding="utf-8"))
            self.assertEqual(len(production_history["runs"]), 1)

    def test_second_production_run_same_day_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _limit, _runtime, _history = self.configure_runtime_files(tmp, production=True)
            first = self.client.post("/run/all")
            self.assertEqual(first.status_code, 200)
            first_pid = mobile_server._process.pid
            mobile_server._process = None
            second = self.client.post("/run/all")
            self.assertEqual(second.status_code, 403)
            self.assertIsNone(mobile_server._process)
            self.assertNotEqual(first_pid, FakeProcess.next_pid + 1)

    def test_duplicate_production_click_does_not_start_second_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.configure_runtime_files(tmp, production=True)
            first = self.client.post("/run/all")
            second = self.client.post("/run/all")
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 409)

    def test_production_home_hides_single_account_debug(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.configure_runtime_files(tmp, production=True)
            response = self.client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertIn("/run/all", response.text)
            self.assertIn("confirmPost", response.text)
            self.assertNotIn("/run/account/account_YOUT", response.text)


    def test_incomplete_rerun_plan_skips_completed_accounts(self):
        from shipping_report import create_report
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            mobile_server.REPORT_DIR = base
            self.configure_runtime_files(tmp, production=True)
            report = base / "today_RECOVERY_20260626.xlsx"
            records = [
                {"account": "account_YOUT", "run_id": "r1", "date": "2026-06-26", "filename": "Y 1 9091.pdf", "carrier": "UPS", "status": "SUCCESS", "source_file": "in.pdf", "output_file": "out.pdf"},
                {"account": "account_YOUT", "run_id": "r1", "date": "2026-06-26", "sale_id": "90933046", "filename": "90933046.pdf", "status": "ORDER_ON_HOLD", "error": "Order on hold"},
                {"account": "account_KAKOMAY", "run_id": "r1", "date": "2026-06-26", "status": "NO_ORDERS", "message": "no orders"},
            ]
            create_report(records, report)
            page = self.client.get("/")
            self.assertEqual(page.status_code, 200)
            self.assertIn("\u8865\u8dd1\u672a\u5b8c\u6210\u8d26\u53f7", page.text)
            plan = self.client.get("/pending-accounts")
            self.assertEqual(plan.status_code, 200)
            body = plan.json()
            self.assertEqual(body["account_statuses"]["account_YOUT"], "PARTIAL_SUCCESS")
            self.assertEqual(body["account_statuses"]["account_KAKOMAY"], "NO_ORDERS")
            self.assertEqual(body["to_run"], ["account_SUP"])
            self.assertNotIn("account_YOUT", body["pending_accounts"])
            response = self.client.post("/run-pending-accounts")
            self.assertEqual(response.status_code, 200)
            command = mobile_server._process.args[0]
            self.assertIn("--rerun-incomplete", command)
            self.assertIn("--production-run", command)


    def test_pending_accounts_rejects_yout_in_pending_list(self):
        from shipping_report import create_report
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            mobile_server.REPORT_DIR = base
            self.configure_runtime_files(tmp, production=True)
            report = base / "today_RECOVERY_20260626.xlsx"
            create_report([{
                "account": "account_KAKOMAY", "run_id": "r1", "date": "2026-06-26", "status": "NO_ORDERS", "message": "no orders"
            }], report)
            plan = self.client.get("/pending-accounts").json()
            self.assertIn("account_YOUT", plan["pending_accounts"])
            response = self.client.post("/run-pending-accounts")
            self.assertEqual(response.status_code, 409)
            self.assertIsNone(mobile_server._process)

    def test_pending_accounts_running_state_blocks_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.configure_runtime_files(tmp, production=True)
            mobile_server.STATUS_PATH.write_text(json.dumps({"state": "running", "message": "busy"}), encoding="utf-8")
            plan = self.client.get("/pending-accounts").json()
            self.assertTrue(plan["running"])
            self.assertEqual(plan["blocked_reason"], "\u8bf7\u5148\u505c\u6b62\u5f53\u524d\u4efb\u52a1")
            response = self.client.post("/run-pending-accounts")
            self.assertEqual(response.status_code, 409)
            self.assertIsNone(mobile_server._process)

    def test_download_existing_excel_and_zip_endpoints(self):
        report = mobile_server.REPORT_DIR / "offline_mobile_test.xlsx"
        archive = mobile_server.REPORT_DIR / "offline_mobile_test.zip"
        report.write_bytes(b"xlsx")
        archive.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
        try:
            excel_response = self.client.get("/download/latest-excel")
            zip_response = self.client.get("/download/latest-zip")
            self.assertEqual(excel_response.status_code, 200)
            self.assertEqual(zip_response.status_code, 200)
        finally:
            report.unlink(missing_ok=True)
            archive.unlink(missing_ok=True)

    def test_home_page_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("/run/all", response.text)
        self.assertIn("/download/latest-excel", response.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
