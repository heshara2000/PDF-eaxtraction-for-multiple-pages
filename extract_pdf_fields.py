import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import pymupdf as fitz


PRODUCT_PATTERN = re.compile(r"(?im)^\s*Product\s*:\s*(.+?)\s*$")
PRODUCT_EXTRA_PATTERN = re.compile(r"\s+FOR\s*:\s*.*$", re.IGNORECASE)
DOCUMENT_PATTERN = re.compile(
    r"(?i)Original\s+document\s*#\s*:?\s*([A-Za-z0-9_-]+)"
)


def clean_value(value):
    if value is None:
        return None
    value = " ".join(value.split())
    return value.strip(" :-") or None


def clean_product(value):
    value = clean_value(value)
    if value is None:
        return None
    value = PRODUCT_EXTRA_PATTERN.sub("", value)
    return clean_value(value)


def ocr_page(page):
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise RuntimeError(
            "OCR is needed for this page. Install Python OCR packages with: "
            "pip install pytesseract pillow"
        )

    tesseract_path = shutil.which("tesseract")
    default_windows_path = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    elif default_windows_path.exists():
        pytesseract.pytesseract.tesseract_cmd = str(default_windows_path)
    else:
        raise RuntimeError(
            "OCR is needed for this PDF, but the Tesseract OCR program is not installed "
            "or is not in PATH. Install it from: "
            "https://github.com/UB-Mannheim/tesseract/wiki"
        )

    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    return pytesseract.image_to_string(image)


def get_page_text(page):
    text = page.get_text("text")
    if text.strip():
        return text
    return ocr_page(page)


def extract_fields(text):
    product_match = PRODUCT_PATTERN.search(text)
    document_match = DOCUMENT_PATTERN.search(text)

    return {
        "product": clean_product(product_match.group(1)) if product_match else None,
        "original_document_number": clean_value(document_match.group(1))
        if document_match
        else None,
    }


def extract_pdf(pdf_path):
    results = []
    with fitz.open(pdf_path) as document:
        for page_index, page in enumerate(document, start=1):
            text = get_page_text(page)
            fields = extract_fields(text)
            results.append(
                {
                    "pdf_file": pdf_path.name,
                    "page": page_index,
                    "product": fields["product"],
                    "original_document_number": fields["original_document_number"],
                }
            )
    return results


def extract_folder(input_folder):
    pdf_files = sorted(input_folder.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in {input_folder}")

    results = []
    for pdf_path in pdf_files:
        results.extend(extract_pdf(pdf_path))
    return results


def make_output_filename():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(f"multiple_prefix_{timestamp}.json")


def main():
    parser = argparse.ArgumentParser(
        description="Extract Product and Original document number from each PDF page."
    )
    parser.add_argument("--input", default="docs", help="Folder containing PDF files")
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file. Default: multiple_prefix_YYYYMMDD_HHMMSS.json",
    )
    args = parser.parse_args()

    input_folder = Path(args.input)
    output_file = Path(args.output) if args.output else make_output_filename()

    results = extract_folder(input_folder)
    output_file.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"Extracted {len(results)} page records")
    print(f"Saved JSON to {output_file}")


if __name__ == "__main__":
    main()