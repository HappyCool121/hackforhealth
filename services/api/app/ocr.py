from __future__ import annotations
import base64
from io import BytesIO
from pathlib import Path
from typing import Any
import fitz
import pytesseract
from PIL import Image, ImageOps, UnidentifiedImageError


def inspect_upload(content: bytes, media_type: str, filename: str, max_pages: int) -> int:
    """Validate an uploaded document before it enters the worker queue."""
    is_pdf = media_type == "application/pdf" or Path(filename).suffix.lower() == ".pdf"
    if is_pdf:
        try:
            with fitz.open(stream=content, filetype="pdf") as document:
                if document.needs_pass:
                    raise ValueError("Password-protected PDFs are not supported")
                if document.page_count < 1:
                    raise ValueError("The PDF has no readable pages")
                if document.page_count > max_pages:
                    raise ValueError(f"PDFs are limited to {max_pages} pages")
                return document.page_count
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("The PDF is damaged or unreadable") from exc

    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("The image is damaged or unsupported") from exc
    return 1


def _image_data_url(image: Image.Image, max_dimension: int, jpeg_quality: int) -> str:
    normalized = ImageOps.exif_transpose(image)
    if normalized.mode not in {"RGB", "L"}:
        background = Image.new("RGB", normalized.size, "white")
        if "A" in normalized.getbands():
            background.paste(normalized, mask=normalized.getchannel("A"))
        else:
            background.paste(normalized)
        normalized = background
    else:
        normalized = normalized.convert("RGB")
    normalized.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    encoded = BytesIO()
    normalized.save(encoded, format="JPEG", quality=jpeg_quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(encoded.getvalue()).decode("ascii")


def prepare_document_images(
    filename: str,
    max_pages: int = 6,
    max_dimension: int = 1800,
    jpeg_quality: int = 85,
) -> list[str]:
    """Render every supported page into a private, normalized AGNES image input."""
    path = Path(filename)
    if path.suffix.lower() == ".pdf":
        images: list[str] = []
        with fitz.open(path) as document:
            if document.needs_pass:
                raise ValueError("Password-protected PDFs are not supported")
            if document.page_count > max_pages:
                raise ValueError(f"PDFs are limited to {max_pages} pages")
            for page in document:
                pixmap = page.get_pixmap(dpi=180, alpha=False)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                images.append(_image_data_url(image, max_dimension, jpeg_quality))
        return images

    with Image.open(path) as image:
        return [_image_data_url(image, max_dimension, jpeg_quality)]


def _pdf_evidence(path: Path) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    with fitz.open(path) as document:
        for page_number, page in enumerate(document, start=1):
            words = page.get_text("words")
            if words:
                for index, (x0, y0, x1, y1, text, *_rest) in enumerate(words):
                    if str(text).strip():
                        evidence.append({"evidence_id": f"p{page_number}-w{index}", "page": page_number, "text": str(text), "bbox": [x0, y0, x1, y1]})
            else:
                pixmap = page.get_pixmap(dpi=200)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                evidence.extend(_image_evidence(image, page_number))
    return evidence


def _image_evidence(image: Image.Image, page: int = 1) -> list[dict[str, Any]]:
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    result: list[dict[str, Any]] = []
    for index, text in enumerate(data["text"]):
        text = text.strip()
        if not text:
            continue
        left, top = data["left"][index], data["top"][index]
        width, height = data["width"][index], data["height"][index]
        result.append({"evidence_id": f"p{page}-w{index}", "page": page, "text": text, "bbox": [left, top, left + width, top + height]})
    return result


def extract_evidence(filename: str) -> tuple[list[dict[str, Any]], list[str]]:
    path = Path(filename)
    warnings: list[str] = []
    try:
        if path.suffix.lower() == ".pdf":
            evidence = _pdf_evidence(path)
        else:
            with Image.open(path) as image:
                evidence = _image_evidence(image.convert("RGB"))
    except Exception as exc:
        return [], [f"OCR could not read this file: {type(exc).__name__}"]
    if len(evidence) < 5:
        warnings.append("Very little readable text was detected; manual review is recommended.")
    return evidence, warnings
