from __future__ import annotations

import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import xlsxwriter

EXCEPTION_STATUSES = {
    "LOGIN_EXPIRED",
    "PAGE_LOAD_FAILED",
    "AWB_GENERATION_FAILED",
    "AWB_MODAL_TIMEOUT",
    "ORDER_ON_HOLD",
    "DOWNLOAD_FAILED",
    "DOWNLOAD_CAPTURE_FAILED",
    "ZIP_CORRUPTED",
    "PDF_PROCESS_FAILED",
    "REQUIRED_FIELD_MISSING",
    "ACCOUNT_FAILED",
    "FAILED",
    "CHECK",
}
NON_SHIPPING_STATUSES = {
    "NO_ORDERS",
    "DUPLICATE_SKIPPED",
    "LOGIN_EXPIRED",
    "PAGE_LOAD_FAILED",
    "AWB_GENERATION_FAILED",
    "AWB_MODAL_TIMEOUT",
    "ORDER_ON_HOLD",
    "DOWNLOAD_FAILED",
    "DOWNLOAD_CAPTURE_FAILED",
    "ZIP_CORRUPTED",
    "PDF_PROCESS_FAILED",
    "REQUIRED_FIELD_MISSING",
    "ACCOUNT_FAILED",
    "ACCOUNT_TIMEOUT",
    "FAILED",
    "CHECK",
}
MAX_EXCEL_ERROR_LEN = 180
BASE_DIR = Path(__file__).resolve().parent


def parse_filename(filename: str) -> Dict[str, str]:
    stem = Path(filename).stem
    sale_id = ""
    match = re.search(r"(?:^|\s)(\d{6,})(?:$|\s)", stem) or re.search(r"(\d{6,})$", stem)
    if match:
        sale_id = match.group(1)
    size = ""
    size_match = re.search(r"\bUS\s*([0-9.]+)\b", stem, re.I)
    if size_match:
        size = f"US {size_match.group(1)}"
    else:
        apparel = re.search(r"\b(XXXL|XXL|XL|L|M|S|XS)\b", stem, re.I)
        if apparel:
            size = apparel.group(1).upper()
    product = stem
    if sale_id:
        product = re.sub(rf"\s*{re.escape(sale_id)}\s*$", "", product).strip()
    if size:
        product = re.sub(rf"\s*{re.escape(size)}\s*", " ", product, flags=re.I).strip()
    return {"sale_id": sale_id, "product": product, "sku": product, "size": size}


def short_text(value: str, limit: int = MAX_EXCEL_ERROR_LEN) -> str:
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return value if len(value) <= limit else value[: limit - 3] + "..."


def rel_path(value: str) -> str:
    if not value:
        return ""
    path = Path(value)
    try:
        return str(path.resolve().relative_to(BASE_DIR)).replace("\\", "/")
    except Exception:
        return path.name if path.name else str(value)


def record_key(record: Dict[str, str]) -> str:
    return record.get("source_sha256") or "|".join([
        record.get("account", ""),
        record.get("sale_id", ""),
        record.get("tracking_number") or record.get("tracking", ""),
        record.get("filename", ""),
    ])


def dedupe_report_records(records: List[Dict[str, str]]) -> List[Dict[str, str]]:
    deduped: List[Dict[str, str]] = []
    seen = set()
    for record in records:
        status = record.get("status", "")
        if status == "DUPLICATE_SKIPPED":
            deduped.append(record)
            continue
        if status != "NO_ORDERS":
            key = record_key(record)
            if key and key in seen:
                continue
            if key:
                seen.add(key)
        deduped.append(record)
    return deduped


def shipping_rows(records: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [r for r in records if r.get("status") in {"SUCCESS", "UNKNOWN"}]


def exception_rows(records: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [r for r in records if r.get("status") in EXCEPTION_STATUSES]


def account_state(records: List[Dict[str, str]]) -> str:
    statuses = {r.get("status", "") for r in records}
    success_pdf_count = sum(r.get("status") == "SUCCESS" for r in records)
    has_exception = any(s in EXCEPTION_STATUSES for s in statuses)
    if success_pdf_count > 0 and has_exception:
        return "PARTIAL_SUCCESS"
    if success_pdf_count > 0:
        return "SUCCESS"
    if statuses and statuses <= {"NO_ORDERS", "DUPLICATE_SKIPPED"}:
        return "NO_ORDERS"
    if has_exception:
        return "FAILED"
    return "SUCCESS"


def create_report(records: List[Dict[str, str]], report_path: Path) -> Path:
    records = dedupe_report_records(records)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(report_path)
    workbook.set_properties({
        "title": "Daily Shipping Report",
        "subject": "CrewSupply AWB and PDF processing results",
        "author": "CrewSupplyMobileAuto",
    })

    header = workbook.add_format({"bold": True, "font_color": "white", "bg_color": "#1F4E78", "border": 1})
    normal = workbook.add_format({"border": 1, "valign": "top"})
    wrap = workbook.add_format({"border": 1, "text_wrap": True, "valign": "top"})
    date_fmt = workbook.add_format({"border": 1, "num_format": "yyyy-mm-dd", "align": "center"})
    success_fmt = workbook.add_format({"border": 1, "bg_color": "#E2F0D9", "align": "center"})
    warning_fmt = workbook.add_format({"border": 1, "bg_color": "#FFF2CC", "align": "center"})
    failed_fmt = workbook.add_format({"border": 1, "bg_color": "#FCE4D6", "align": "center"})
    no_orders_fmt = workbook.add_format({"border": 1, "bg_color": "#D9EAF7", "align": "center"})

    today_ws = workbook.add_worksheet("今日发货")
    today_headers = ["日期", "运行批次", "账号", "Sale ID", "SKU", "尺码", "数量", "运输公司", "运单号", "原始文件", "处理后文件", "状态", "备注"]
    today_ws.write_row(0, 0, today_headers, header)
    today_ws.freeze_panes(1, 0)
    rows = shipping_rows(records)
    for row_index, record in enumerate(rows, start=1):
        parsed = parse_filename(record.get("filename", ""))
        status = record.get("status", "")
        values = [
            record.get("date") or datetime.now().strftime("%Y-%m-%d"),
            record.get("run_id", ""),
            record.get("account", ""),
            record.get("sale_id") or parsed["sale_id"],
            record.get("sku") or parsed["sku"],
            record.get("size") or parsed["size"],
            record.get("quantity") or "1",
            record.get("carrier", ""),
            record.get("tracking_number") or record.get("tracking", ""),
            rel_path(record.get("source_file", "")),
            rel_path(record.get("output_file") or record.get("processed_file", "")),
            status,
            short_text(record.get("message") or record.get("action") or record.get("error", "")),
        ]
        for col, value in enumerate(values):
            fmt = wrap if col in {4, 9, 10, 12} else normal
            if col == 0:
                fmt = date_fmt
            elif col == 11:
                fmt = success_fmt if status == "SUCCESS" else warning_fmt if status == "UNKNOWN" else failed_fmt
            today_ws.write(row_index, col, value, fmt)
    today_ws.autofilter(0, 0, max(1, len(rows)), len(today_headers) - 1)
    for col, width in enumerate([12, 20, 18, 13, 24, 10, 8, 12, 24, 34, 34, 16, 30]):
        today_ws.set_column(col, col, width)

    err_ws = workbook.add_worksheet("异常订单")
    err_headers = ["日期", "运行批次", "账号", "Sale ID", "文件", "状态", "错误摘要", "文件位置"]
    err_ws.write_row(0, 0, err_headers, header)
    err_ws.freeze_panes(1, 0)
    errors = exception_rows(records)
    for row_index, record in enumerate(errors, start=1):
        parsed = parse_filename(record.get("filename", ""))
        err_ws.write_row(row_index, 0, [
            record.get("date") or datetime.now().strftime("%Y-%m-%d"),
            record.get("run_id", ""),
            record.get("account", ""),
            record.get("sale_id") or parsed["sale_id"],
            record.get("filename", ""),
            record.get("status", ""),
            short_text(record.get("error") or record.get("message") or record.get("action", "")),
            rel_path(record.get("output_file") or record.get("processed_file") or record.get("source_file", "")),
        ], wrap)
    err_ws.autofilter(0, 0, max(1, len(errors)), len(err_headers) - 1)
    for col, width in enumerate([12, 20, 18, 13, 28, 22, 42, 40]):
        err_ws.set_column(col, col, width)

    summary_ws = workbook.add_worksheet("账号汇总")
    summary_headers = ["账号", "运行状态", "待发订单数", "成功PDF数", "UPS", "USPS", "FedEx", "Unknown", "重复跳过", "异常数", "开始时间", "完成时间", "备注"]
    summary_ws.write_row(0, 0, summary_headers, header)
    summary_ws.freeze_panes(1, 0)
    by_account: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for record in records:
        by_account[record.get("account", "")].append(record)
    for row_index, account in enumerate(sorted(by_account), start=1):
        account_records = by_account[account]
        ship = shipping_rows(account_records)
        counts = Counter((r.get("carrier", "") or "").upper() for r in ship)
        duplicates = sum(r.get("status") == "DUPLICATE_SKIPPED" for r in account_records)
        failures = len(exception_rows(account_records))
        successes = sum(r.get("status") == "SUCCESS" for r in ship)
        state = account_state(account_records)
        start_times = [r.get("start_time", "") for r in account_records if r.get("start_time")]
        end_times = [r.get("completed_at", "") or r.get("finish_time", "") for r in account_records if r.get("completed_at") or r.get("finish_time")]
        remarks = []
        if any(r.get("status") == "NO_ORDERS" for r in account_records):
            remarks.append("无待发订单")
        if duplicates:
            remarks.append(f"重复跳过 {duplicates}")
        if failures:
            remarks.append(f"异常 {failures}")
        values = [
            account, state, len(ship), successes, counts["UPS"], counts["USPS"], counts["FEDEX"], counts["UNKNOWN"],
            duplicates, failures, min(start_times) if start_times else "", max(end_times) if end_times else "", "; ".join(remarks),
        ]
        for col, value in enumerate(values):
            fmt = normal
            if col == 1:
                fmt = success_fmt if state == "SUCCESS" else no_orders_fmt if state == "NO_ORDERS" else warning_fmt if state == "PARTIAL_SUCCESS" else failed_fmt
            summary_ws.write(row_index, col, value, fmt)
    summary_ws.autofilter(0, 0, max(1, len(by_account)), len(summary_headers) - 1)
    for col, width in enumerate([18, 18, 12, 12, 8, 8, 8, 10, 12, 10, 20, 20, 30]):
        summary_ws.set_column(col, col, width)

    workbook.close()
    return report_path


def zip_processed(records: Iterable[Dict[str, str]], zip_path: Path) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        used = set()
        seen_hashes = set()
        for record in records:
            if record.get("status") == "DUPLICATE_SKIPPED":
                continue
            path = Path(record.get("output_file") or record.get("processed_file", ""))
            if not path.exists() or path.suffix.lower() != ".pdf":
                continue
            digest = record.get("output_sha256") or ""
            if digest and digest in seen_hashes:
                continue
            if digest:
                seen_hashes.add(digest)
            account = record.get("account", "account")
            arcname = f"{account}/{path.name}"
            if arcname in used:
                arcname = f"{account}/{path.stem}_{len(used)}{path.suffix}"
            used.add(arcname)
            archive.write(path, arcname)
    return zip_path




