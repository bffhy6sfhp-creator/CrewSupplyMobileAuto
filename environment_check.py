from __future__ import annotations

import importlib.util
import os
import shutil
import socket
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent


def check_port(host: str = "127.0.0.1", port: int = 8000) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def main() -> int:
    failures: list[str] = []
    print(f"Python: {sys.version.split()[0]}")

    modules = ["playwright", "fitz", "PIL", "pytesseract", "xlsxwriter", "openpyxl", "fastapi", "uvicorn"]
    for module in modules:
        ok = importlib.util.find_spec(module) is not None
        print(f"{module}: {'OK' if ok else 'MISSING'}")
        if not ok:
            failures.append(f"Python module missing: {module}")

    required = [
        "auto_all_integrated.py", "mobile_server.py", "pdf_processor.py",
        "shipping_report.py", "assets/address.png", "config.json",
    ]
    for item in required:
        ok = (BASE / item).exists()
        print(f"{item}: {'OK' if ok else 'MISSING'}")
        if not ok:
            failures.append(f"Required file missing: {item}")

    accounts = ["account_KAKOMAY.json", "account_YOUT.json", "account_SUP.json"]
    for name in accounts:
        path = BASE / "private" / name
        ok = path.exists() and path.stat().st_size > 0
        print(f"private/{name}: {'EXISTS' if ok else 'MISSING'}")
        if not ok:
            failures.append(f"Login state missing: private/{name}")

    tesseract = shutil.which("tesseract")
    if not tesseract:
        for candidate in [
            Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
            Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        ]:
            if candidate.exists():
                tesseract = str(candidate)
                break
    print(f"Tesseract: {'OK - ' + tesseract if tesseract else 'MISSING'}")
    if not tesseract:
        failures.append("Tesseract OCR missing")

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            executable = Path(p.chromium.executable_path)
            browser_ok = executable.exists()
            print(f"Playwright Chromium: {'OK' if browser_ok else 'MISSING'}")
            if not browser_ok:
                failures.append("Playwright Chromium missing")
    except Exception as exc:
        print(f"Playwright Chromium: CHECK_FAILED - {exc}")
        failures.append("Playwright Chromium check failed")

    for folder_name in ["Reports", "Label", "logs", "data"]:
        folder = BASE / folder_name
        try:
            folder.mkdir(parents=True, exist_ok=True)
            probe = folder / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            print(f"{folder_name} writable: OK")
        except Exception as exc:
            print(f"{folder_name} writable: FAILED - {exc}")
            failures.append(f"Folder not writable: {folder_name}")

    print(f"Port 8000: {'IN_USE (mobile service may already be running)' if check_port() else 'FREE'}")
    print("Account file contents were not printed.")

    if failures:
        print("\nEnvironment check FAILED:")
        for item in failures:
            print(f"- {item}")
        return 1
    print("\nEnvironment check PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
