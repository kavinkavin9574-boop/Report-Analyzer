"""
Turns an uploaded file into per-page text, falling back to OCR for pages
with little/no embedded text (i.e. scanned pages).

OCR backend: PaddleOCR (https://github.com/PaddlePaddle/PaddleOCR), via
app.document_processing.ocr_paddle.
"""
import os
from dataclasses import dataclass

import fitz  # PyMuPDF
from PIL import Image

from app.core.config import get_settings
from app.document_processing import ocr_paddle

settings = get_settings()

MIN_TEXT_LENGTH_BEFORE_OCR = 20  # below this, treat the page as "scanned"


@dataclass
class PageResult:
    page_number: int
    text: str
    used_ocr: bool
    image_path: str | None = None


def _run_ocr(image_path: str, context: str) -> str:
    try:
        return ocr_paddle.ocr_page_text(image_path)
    except Exception as exc:  # OCR failure shouldn't crash the whole pipeline
        print(f"[extractor] PaddleOCR failed on {context}: {exc}")
        return ""


def extract_pdf(file_path: str, image_output_dir: str) -> list[PageResult]:
    os.makedirs(image_output_dir, exist_ok=True)
    results: list[PageResult] = []

    doc = fitz.open(file_path)
    try:
        for i, page in enumerate(doc):
            page_number = i + 1
            text = page.get_text("text") or ""
            used_ocr = False

            # Always render the page image — needed later for evidence highlighting.
            pix = page.get_pixmap(dpi=150)
            image_path = os.path.join(image_output_dir, f"page_{page_number}.png")
            pix.save(image_path)

            if settings.ocr_enabled and len(text.strip()) < MIN_TEXT_LENGTH_BEFORE_OCR:
                ocr_text = _run_ocr(image_path, f"page {page_number}")
                if ocr_text:
                    text = ocr_text
                    used_ocr = True

            results.append(PageResult(page_number=page_number, text=text, used_ocr=used_ocr, image_path=image_path))
    finally:
        doc.close()

    return results


def extract_image(file_path: str, image_output_dir: str) -> list[PageResult]:
    """Single standalone image (PNG/JPG) treated as a one-page 'document'."""
    os.makedirs(image_output_dir, exist_ok=True)
    image_path = os.path.join(image_output_dir, "page_1.png")

    img = Image.open(file_path)
    img.convert("RGB").save(image_path)

    text = ""
    used_ocr = False
    if settings.ocr_enabled:
        text = _run_ocr(image_path, "standalone image")
        used_ocr = bool(text)

    return [PageResult(page_number=1, text=text, used_ocr=used_ocr, image_path=image_path)]


def build_full_text_with_page_markers(pages: list[PageResult]) -> str:
    """Used as the LLM-facing document text so the model can cite page numbers."""
    parts = []
    for p in pages:
        parts.append(f"[PAGE {p.page_number}]\n{p.text}")
    return "\n\n".join(parts)
