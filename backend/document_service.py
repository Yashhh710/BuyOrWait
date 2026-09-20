"""
document_service.py

Extracts a product name + price from an uploaded receipt/screenshot,
either an image (PNG/JPG) or a PDF, so the frontend can prefill the
purchase form the same way it does for a pasted Amazon link.

Image OCR uses RapidOCR (onnxruntime backend). We intentionally avoid
PyTorch-based OCR (e.g. EasyOCR) here: on plain Windows setups its
native c10.dll/torch DLLs frequently fail to load (WinError 126) unless
the machine has the right Visual C++ Redistributable and a matching
CPU instruction set. onnxruntime is far more forgiving and has no
external binary/PATH requirement - just `pip install`.

PDF text extraction uses pdfplumber, which is pure Python and needs
no external binary either.
"""
import io
import re
from typing import Optional

PRICE_PATTERN = re.compile(r"(?:₹|Rs\.?|INR|\$|€|£)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.IGNORECASE)
BARE_NUMBER_PATTERN = re.compile(r"\b([0-9]{2,3}(?:,[0-9]{3})+(?:\.[0-9]{1,2})?|[0-9]+\.[0-9]{2})\b")

_ocr_engine = None  # lazily created + cached across requests


def _get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    return _ocr_engine


def _run_ocr(image_array) -> str:
    """image_array: an HxWx3 RGB numpy array. Returns the recognized text, one line per detection."""
    engine = _get_ocr_engine()
    result, _elapse = engine(image_array)
    if not result:
        return ""
    # Each item is [box_points, recognized_text, confidence]
    return "\n".join(str(item[1]) for item in result)


def _best_price(text: str) -> Optional[float]:
    candidates = [m.group(1) for m in PRICE_PATTERN.finditer(text)]
    if not candidates:
        candidates = [m.group(1) for m in BARE_NUMBER_PATTERN.finditer(text)]
    if not candidates:
        return None
    values = [float(c.replace(",", "")) for c in candidates]
    return max(values)


def _best_product_name(text: str) -> Optional[str]:
    for line in text.splitlines():
        cleaned = line.strip()
        if len(cleaned) >= 4 and not PRICE_PATTERN.fullmatch(cleaned):
            return cleaned[:120]
    return None


def extract_from_image(file_bytes: bytes) -> dict:
    """OCR an uploaded image (receipt/screenshot) for product name + price."""
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Image scanning requires the 'pillow' and 'numpy' packages to be installed on the server. "
            "Run: pip install -r requirements.txt"
        ) from exc

    try:
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    except Exception as exc:
        raise RuntimeError("Could not read that image file. Make sure it's a valid PNG/JPG.") from exc

    try:
        text = _run_ocr(np.array(image))
    except ImportError as exc:
        raise RuntimeError(
            "Image scanning requires the 'rapidocr-onnxruntime' package to be installed on the server. "
            "Run: pip install -r requirements.txt"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"The OCR engine failed on that image: {exc}") from exc

    return _finalize(text)


def extract_from_pdf(file_bytes: bytes) -> dict:
    """Extract product name + price from an uploaded PDF (invoice/receipt)."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError(
            "PDF scanning requires the 'pdfplumber' package to be installed on the server. "
            "Run: pip install -r requirements.txt"
        ) from exc

    try:
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text_parts.append(page.extract_text() or "")
        text = "\n".join(text_parts)
    except Exception as exc:
        raise RuntimeError("Could not read that PDF file. Make sure it isn't password-protected or corrupted.") from exc

    if not text.strip():
        # Scanned/image-only PDF with no embedded text layer - fall back to OCR-ing
        # each page as an image instead of giving up.
        try:
            import numpy as np
            from pdf2image import convert_from_bytes
        except ImportError as exc:
            raise RuntimeError(
                "That PDF has no selectable text (it looks like a scanned image). "
                "Scanning it as an image requires the 'pdf2image' package and Poppler to be installed."
            ) from exc
        pages = convert_from_bytes(file_bytes, dpi=200)
        ocr_lines = []
        for page_image in pages:
            page_text = _run_ocr(np.array(page_image.convert("RGB")))
            if page_text:
                ocr_lines.append(page_text)
        text = "\n".join(ocr_lines)

    return _finalize(text)


def _finalize(text: str) -> dict:
    text = text.strip()
    if not text:
        raise RuntimeError("No readable text was found in that file.")
    price = _best_price(text)
    name = _best_product_name(text)
    if price is None or name is None:
        raise RuntimeError(
            "A product name and price could not be identified in that file. "
            "Try a clearer photo/screenshot that shows the price."
        )
    return {"product_name": name, "price": price, "currency": "₹", "source": "document_scan"}
