from __future__ import annotations

import secrets
import unittest
from datetime import datetime
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from pdf_processor import process_pdf, sha256_file

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "tests" / "results"
ADDRESS = ROOT / "assets" / "address.png"
REPORT = RESULTS / "pdf_processing_test_report.txt"


def make_pdf(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y = 35
    for line in lines:
        page.insert_text((28, y), line, fontsize=14)
        y += 34
    doc.save(path)
    doc.close()


class Step4PdfProcessingTest(unittest.TestCase):
    report_lines: list[str] = []

    def setUp(self):
        self.run_id = f"step4_{datetime.now():%Y%m%d_%H%M%S}_{secrets.token_hex(2)}"
        self.base = RESULTS / self.run_id
        self.input = self.base / "input"
        self.output = self.base / "output"
        self.base.mkdir(parents=True, exist_ok=True)

    def record(self, name: str, result: dict) -> None:
        self.report_lines.append(
            f"{name}: status={result.get('status')} carrier={result.get('carrier')} "
            f"source_sha256={result.get('source_sha256')} output_sha256={result.get('output_sha256')} "
            f"message={result.get('message')}"
        )

    def test_ups_overlay(self):
        source = self.input / "UPS-SHOE US 9 910001.pdf"
        target = self.output / source.name
        make_pdf(source, ["UPS GROUND", "TRACKING #: 1Z999AA10123456784", "OLD SENDER ADDRESS"])
        result = process_pdf(source, target, ADDRESS, "acct", self.run_id)
        self.record("UPS overlay", result)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["carrier"], "UPS")
        self.assertTrue(target.exists())
        self.assertNotEqual(result["source_sha256"], result["output_sha256"])
        self.assertTrue(source.exists())

    def test_usps_erase(self):
        source = self.input / "USPS-TEE XL 910002.pdf"
        target = self.output / source.name
        make_pdf(source, ["USPS GROUND ADVANTAGE", "9400111899223856928499", "KICKS CREW SNEAKERS"])
        result = process_pdf(source, target, ADDRESS, "acct", self.run_id)
        self.record("USPS erase", result)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["carrier"], "USPS")
        self.assertTrue(target.exists())
        self.assertNotEqual(result["source_sha256"], result["output_sha256"])

    def test_fedex_hash_unchanged(self):
        source = self.input / "FEDEX-HAT M 910003.pdf"
        target = self.output / source.name
        make_pdf(source, ["FedEx", "TRK# 1234 5678 9012", "INTL ECONOMY", "ORIGIN ID", "BILL SENDER"])
        result = process_pdf(source, target, ADDRESS, "acct", self.run_id)
        self.record("FedEx unchanged", result)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["carrier"], "FEDEX")
        self.assertEqual(result["source_sha256"], result["output_sha256"])
        self.assertEqual(sha256_file(source), sha256_file(target))

    def test_unknown_copied_without_modification(self):
        source = self.input / "UNKNOWN 910004.pdf"
        target = self.output / source.name
        make_pdf(source, ["PLAIN DOCUMENT", "NO CARRIER HINTS"])
        result = process_pdf(source, target, ADDRESS, "acct", self.run_id)
        self.record("UNKNOWN unchanged", result)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["carrier"], "UNKNOWN")
        self.assertEqual(result["source_sha256"], result["output_sha256"])

    def test_corrupt_pdf_fails_safely(self):
        source = self.input / "BROKEN 910005.pdf"
        target = self.output / source.name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"not a pdf")
        result = process_pdf(source, target, ADDRESS, "acct", self.run_id)
        self.record("Corrupt fails", result)
        self.assertEqual(result["status"], "PDF_PROCESS_FAILED")
        self.assertTrue(source.exists())
        self.assertFalse(target.exists())

    def test_missing_address_for_ups_fails_without_deleting_source(self):
        source = self.input / "UPS-MISSING US 10 910006.pdf"
        target = self.output / source.name
        make_pdf(source, ["UPS GROUND", "TRACKING #: 1Z999AA10123456784"])
        result = process_pdf(source, target, self.base / "missing_address.png", "acct", self.run_id)
        self.record("UPS missing address", result)
        self.assertEqual(result["status"], "PDF_PROCESS_FAILED")
        self.assertIn("address image missing", result["message"])
        self.assertTrue(source.exists())
        self.assertFalse(target.exists())

    @classmethod
    def tearDownClass(cls):
        RESULTS.mkdir(parents=True, exist_ok=True)
        REPORT.write_text("\n".join(cls.report_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main(verbosity=2)
