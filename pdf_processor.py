from __future__ import annotations

import hashlib
import os
import re
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

try:
    import pymupdf as fitz
except ImportError:  # PyMuPDF old import style
    import fitz

UPS_COVER_RECT = fitz.Rect(0, 0, 290, 82)
UPS_IMAGE_RECT = fitz.Rect(0, 8, 277, 77)
USPS_ERASE_RECTS_RATIO: List[Tuple[float, float, float, float]] = [
    (0.045, 0.305, 0.390, 0.334),
]
OCR_ZOOM = 4
COMMON_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]
_TESSERACT_CACHE: Tuple[bool, str] | None = None
OCR_CALL_TIMEOUT_SECONDS = 10

EXCLUDED_INPUT_DIRS = {
    "processed", "output", "unknown", "failed", "reports", "screenshots",
    "backup", "backups", "__pycache__", "pycache", "tmp", "temp", "test_tmp",
}


def configure_tesseract() -> Tuple[bool, str]:
    global _TESSERACT_CACHE
    if _TESSERACT_CACHE is not None:
        return _TESSERACT_CACHE
    try:
        import pytesseract
    except Exception as exc:
        _TESSERACT_CACHE = (False, f"pytesseract unavailable: {exc}")
        return _TESSERACT_CACHE

    exe_from_path = shutil.which("tesseract")
    if exe_from_path:
        pytesseract.pytesseract.tesseract_cmd = exe_from_path
    else:
        for candidate in COMMON_TESSERACT_PATHS:
            if os.path.exists(candidate):
                pytesseract.pytesseract.tesseract_cmd = candidate
                break

    try:
        version = pytesseract.get_tesseract_version()
        _TESSERACT_CACHE = (True, f"Tesseract {version}")
    except Exception as exc:
        _TESSERACT_CACHE = (False, f"tesseract.exe unavailable: {exc}")
    return _TESSERACT_CACHE


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(text: str) -> str:
    text = (text or "").upper().replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def extract_ups_tracking(text: str) -> Optional[str]:
    raw = normalize_text(text)
    patterns = [
        r"TRACKING\s*#?\s*:?\s*((?:1|I)\s*(?:Z|2)[\sA-Z0-9]{10,40})",
        r"((?:1|I)\s*(?:Z|2)[\sA-Z0-9]{10,40})",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, raw, re.I):
            candidate = match.group(1) if match.lastindex else match.group(0)
            tracking = re.sub(r"[^A-Z0-9]", "", candidate.upper())
            if len(tracking) >= 2:
                first = "1" if tracking[0] in {"1", "I", "L"} else tracking[0]
                second = "Z" if tracking[1] in {"Z", "2"} else tracking[1]
                tracking = first + second + tracking[2:]
            if tracking.startswith("1Z") and len(tracking) >= 18:
                return tracking[:18]
    return None


def extract_fedex_tracking(text: str) -> Optional[str]:
    raw = normalize_text(text)
    for match in re.finditer(r"(?<!\d)(\d{4})\s+(\d{4})\s+(\d{4})(?!\d)", raw):
        return "".join(match.groups())
    digit_runs = re.findall(r"(?<!\d)\d{12,22}(?!\d)", raw)
    for length in [12, 15, 20, 22, 14]:
        for number in digit_runs:
            if len(number) == length:
                return number
    return max(digit_runs, key=len) if digit_runs else None


def is_probably_fedex(raw: str, compact: str) -> bool:
    if "FEDEX" in compact or "FEDERALEXPRESS" in compact:
        return True
    hints = [
        "TRK#", "ACTWGT", "DIMS", "ORIGIN ID", "BILL SENDER",
        "NO EEI", "INTL ECONOMY", "INTERNATIONAL ECONOMY", "CAD:",
    ]
    hint_count = sum(1 for hint in hints if hint in raw)
    has_service = "INTLECONOMY" in compact or "INTERNATIONALECONOMY" in compact
    has_tracking = extract_fedex_tracking(raw) is not None
    return (has_service and has_tracking) or (hint_count >= 3 and has_tracking)


def ocr_first_page(pdf_path: Path) -> str:
    ready, _ = configure_tesseract()
    if not ready:
        return ""
    try:
        import pytesseract
        from PIL import Image, ImageOps
    except Exception:
        return ""

    texts: List[str] = []

    def add_ocr(image, config: str) -> None:
        try:
            value = pytesseract.image_to_string(
                image, lang="eng", config=config, timeout=OCR_CALL_TIMEOUT_SECONDS
            )
            if value and value.strip():
                texts.append(value)
        except Exception:
            pass

    doc = None
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        # One high-quality full-page pass plus targeted fallbacks. This is much
        # faster than the old 10 OCR calls per PDF and still covers carrier text.
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        width, height = image.size
        add_ocr(image, "--psm 6")
        gray = ImageOps.grayscale(image)
        bw = gray.point(lambda x: 0 if x < 180 else 255, "1")
        add_ocr(bw, "--psm 6")
        bottom = bw.crop((0, int(height * 0.50), width, int(height * 0.82)))
        add_ocr(bottom, "--psm 11")
    except Exception:
        return ""
    finally:
        if doc is not None:
            doc.close()
    return "\n".join(texts)

def extract_pdf_text(pdf_path: Path) -> str:
    text = ""
    doc = None
    try:
        doc = fitz.open(pdf_path)
        if doc.page_count:
            text = doc[0].get_text("text") or ""
    finally:
        if doc is not None:
            doc.close()

    compact = re.sub(r"[^A-Z0-9]", "", text.upper())
    clear_word = any(
        key in compact
        for key in [
            "FEDEX", "FEDERALEXPRESS", "USPS", "UNITEDSTATESPOSTALSERVICE",
            "POSTALSERVICE", "UPSGROUND", "UNITEDPARCELSERVICE",
        ]
    ) or bool(re.search(r"\bUPS\b", text.upper()))

    if len(text.strip()) < 20 or not clear_word:
        ocr_text = ocr_first_page(pdf_path)
        if ocr_text.strip():
            text += "\n" + ocr_text
    return text


def detect_carrier(filename: str, text: str) -> str:
    raw = normalize_text(f"{filename}\n{text}")
    compact = re.sub(r"[^A-Z0-9]", "", raw)
    if is_probably_fedex(raw, compact):
        return "FEDEX"
    if (
        "USPS" in compact
        or "UNITEDSTATESPOSTALSERVICE" in compact
        or "POSTALSERVICE" in compact
        or "GROUNDADVANTAGE" in compact
        or re.search(r"9[2345]\d{18,24}", compact)
    ):
        return "USPS"
    if (
        "UPS GROUND" in raw
        or "UPSGROUND" in compact
        or re.search(r"\bUPS\b", raw)
        or re.search(r"TRACKING\s*#?:?\s*(?:1|I)\s*(?:Z|2)", raw)
        or "UNITEDPARCELSERVICE" in compact
        or extract_ups_tracking(raw)
    ):
        return "UPS"
    return "UNKNOWN"


def extract_tracking(carrier: str, filename: str, text: str) -> str:
    raw = normalize_text(f"{filename}\n{text}")
    compact = re.sub(r"[^A-Z0-9]", "", raw)
    if carrier == "UPS":
        return extract_ups_tracking(raw) or ""
    if carrier == "USPS":
        match = re.search(r"9[2345]\d{18,24}", compact)
        return match.group(0) if match else ""
    if carrier == "FEDEX":
        return extract_fedex_tracking(raw) or ""
    return extract_ups_tracking(raw) or extract_fedex_tracking(raw) or ""


def parse_label_filename(filename: str) -> Dict[str, str]:
    stem = Path(filename).stem
    sale_id = ""
    sale_match = re.search(r"(?:^|\s)(\d{6,})(?:$|\s)", stem) or re.search(r"(\d{6,})$", stem)
    if sale_match:
        sale_id = sale_match.group(1)
    size = ""
    size_match = re.search(r"\bUS\s*([0-9.]+)\b", stem, re.I)
    if size_match:
        size = f"US {size_match.group(1)}"
    else:
        apparel = re.search(r"\b(XXXL|XXL|XL|L|M|S|XS)\b", stem, re.I)
        if apparel:
            size = apparel.group(1).upper()
    sku = stem
    if sale_id:
        sku = re.sub(rf"\s*{re.escape(sale_id)}\s*$", "", sku).strip()
    if size:
        sku = re.sub(rf"\s*{re.escape(size)}\s*", " ", sku, flags=re.I).strip()
    return {"sale_id": sale_id, "sku": sku, "size": size, "quantity": "1"}


def overlay_ups_address(source: Path, address_file: Path, target: Path) -> None:
    doc = fitz.open(source)
    try:
        page = doc[0]
        page.draw_rect(UPS_COVER_RECT, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
        if address_file.suffix.lower() == ".pdf":
            address_doc = fitz.open(address_file)
            try:
                page.show_pdf_page(UPS_IMAGE_RECT, address_doc, 0, overlay=True)
            finally:
                address_doc.close()
        else:
            page.insert_image(UPS_IMAGE_RECT, filename=str(address_file), overlay=True)
        doc.save(target, garbage=4, deflate=True)
    finally:
        doc.close()


def erase_usps_area(source: Path, target: Path) -> None:
    doc = fitz.open(source)
    try:
        page = doc[0]
        page_rect = page.rect
        for x0, y0, x1, y1 in USPS_ERASE_RECTS_RATIO:
            rect = fitz.Rect(
                page_rect.width * x0,
                page_rect.height * y0,
                page_rect.width * x1,
                page_rect.height * y1,
            )
            page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
        doc.save(target, garbage=4, deflate=True)
    finally:
        doc.close()


def safe_output_path(path: Path, source_sha256: str = "") -> Path:
    if not path.exists():
        return path
    suffix = source_sha256[:8] if source_sha256 else "diff"
    candidate = path.with_name(f"{path.stem}__{suffix}{path.suffix}")
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        next_candidate = path.with_name(f"{path.stem}__{suffix}_{index}{path.suffix}")
        if not next_candidate.exists():
            return next_candidate
        index += 1


def is_excluded_input_path(path: Path) -> bool:
    return any(part.lower() in EXCLUDED_INPUT_DIRS for part in path.parts)


def collect_input_pdfs(source_dir: Path, run_date: str | None = None) -> List[Path]:
    pdfs: List[Path] = []
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for pdf_path in sorted(source_dir.rglob("*.pdf")):
        if is_excluded_input_path(pdf_path):
            continue
        if run_date:
            date_parts = [part for part in pdf_path.parts if date_pattern.match(part)]
            if date_parts and run_date not in date_parts:
                continue
        pdfs.append(pdf_path)
    return pdfs


def base_record(
    source_pdf: Path,
    account: str,
    run_id: str,
    source_sha256: str = "",
) -> Dict[str, str]:
    parsed = parse_label_filename(source_pdf.name)
    return {
        "account": account,
        "run_id": run_id,
        "source_file": str(source_pdf),
        "processed_file": "",
        "output_file": "",
        "filename": source_pdf.name,
        "carrier": "",
        "tracking": "",
        "tracking_number": "",
        "sale_id": parsed["sale_id"],
        "sku": parsed["sku"],
        "size": parsed["size"],
        "quantity": parsed["quantity"],
        "status": "",
        "action": "",
        "message": "",
        "error": "",
        "source_sha256": source_sha256,
        "output_sha256": "",
    }


def process_pdf(
    source_pdf: Path,
    output_pdf: Path,
    address_file: Path,
    account: str = "",
    run_id: str = "",
    extracted_text: str | None = None,
    detected_carrier: str | None = None,
) -> Dict[str, str]:
    source_pdf = Path(source_pdf)
    output_pdf = Path(output_pdf)
    source_hash = sha256_file(source_pdf)
    record = base_record(source_pdf, account, run_id, source_hash)
    try:
        text = extracted_text if extracted_text is not None else extract_pdf_text(source_pdf)
        carrier = detected_carrier or detect_carrier(source_pdf.name, text)
        tracking = extract_tracking(carrier, source_pdf.name, text)
        record.update({"carrier": carrier, "tracking": tracking, "tracking_number": tracking})
        output_pdf.parent.mkdir(parents=True, exist_ok=True)

        if carrier == "UPS":
            if not address_file.exists():
                raise FileNotFoundError(f"UPS address image missing: {address_file}")
            overlay_ups_address(source_pdf, address_file, output_pdf)
            message = "UPS address overlaid"
            status = "SUCCESS"
        elif carrier == "USPS":
            erase_usps_area(source_pdf, output_pdf)
            message = "USPS sender line erased"
            status = "SUCCESS"
        elif carrier == "FEDEX":
            shutil.copy2(source_pdf, output_pdf)
            output_hash = sha256_file(output_pdf)
            if output_hash != source_hash:
                raise RuntimeError("FedEx copy hash mismatch")
            message = "FedEx copied unchanged"
            status = "SUCCESS"
        else:
            shutil.copy2(source_pdf, output_pdf)
            message = "Unknown carrier copied unchanged"
            status = "UNKNOWN"

        record.update({
            "processed_file": str(output_pdf),
            "output_file": str(output_pdf),
            "status": status,
            "action": message,
            "message": message,
            "output_sha256": sha256_file(output_pdf),
        })
        return record
    except Exception as exc:
        record.update({
            "status": "PDF_PROCESS_FAILED",
            "action": "PDF processing failed",
            "message": str(exc),
            "error": str(exc),
        })
        return record


def process_pdf_to_dirs(
    source_pdf: Path,
    processed_dir: Path,
    unknown_dir: Path,
    failed_dir: Path,
    address_file: Path,
    account: str = "",
    run_id: str = "",
) -> Dict[str, str]:
    source_hash = sha256_file(source_pdf)
    try:
        text = extract_pdf_text(source_pdf)
        carrier = detect_carrier(source_pdf.name, text)
    except Exception:
        carrier = "UNKNOWN"
    if carrier == "UNKNOWN":
        target_dir = unknown_dir
    else:
        target_dir = processed_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    output_pdf = safe_output_path(target_dir / source_pdf.name, source_hash)
    record = process_pdf(
        source_pdf, output_pdf, address_file, account=account, run_id=run_id,
        extracted_text=text, detected_carrier=carrier,
    )
    if record["status"] == "PDF_PROCESS_FAILED":
        failed_dir.mkdir(parents=True, exist_ok=True)
        failed_target = safe_output_path(failed_dir / source_pdf.name, source_hash)
        try:
            shutil.copy2(source_pdf, failed_target)
            record.update({"processed_file": str(failed_target), "output_file": str(failed_target)})
        except Exception:
            pass
    return record


def process_pdf_list(
    pdf_paths: Iterable[Path],
    processed_dir: Path,
    unknown_dir: Path,
    failed_dir: Path,
    address_file: Path,
    account: str = "",
    run_id: str = "",
    seen_hashes: Optional[Set[str]] = None,
) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    seen = seen_hashes if seen_hashes is not None else set()
    ordered = sorted(Path(path) for path in pdf_paths)
    total = len(ordered)
    for index, source_pdf in enumerate(ordered, start=1):
        if is_excluded_input_path(source_pdf):
            continue
        print(f"[pdf] {index}/{total} 开始 {source_pdf.name}", flush=True)
        try:
            source_hash = sha256_file(source_pdf)
        except Exception as exc:
            record = base_record(source_pdf, account, run_id)
            record.update({
                "status": "PDF_PROCESS_FAILED",
                "action": "PDF processing failed",
                "message": str(exc),
                "error": str(exc),
            })
            records.append(record)
            continue
        if source_hash in seen:
            record = base_record(source_pdf, account, run_id, source_hash)
            record.update({
                "status": "DUPLICATE_SKIPPED",
                "action": "Duplicate PDF skipped",
                "message": "Duplicate PDF skipped by SHA256",
            })
            records.append(record)
            continue
        seen.add(source_hash)
        record = process_pdf_to_dirs(
            source_pdf, processed_dir, unknown_dir, failed_dir, address_file,
            account=account, run_id=run_id,
        )
        records.append(record)
        print(f"[pdf] {index}/{total} 完成 {source_pdf.name} {record.get('carrier', '')} {record.get('status', '')}", flush=True)
    return records


def process_folder(
    source_dir: Path,
    processed_dir: Path,
    unknown_dir: Path,
    failed_dir: Path,
    address_file: Path,
    account: str = "",
    run_id: str = "",
    run_date: str | None = None,
) -> List[Dict[str, str]]:
    pdfs = collect_input_pdfs(source_dir, run_date=run_date)
    return process_pdf_list(
        pdfs, processed_dir, unknown_dir, failed_dir, address_file,
        account=account, run_id=run_id,
    )
