import base64
from io import BytesIO

import fitz
from PIL import Image

from app.ocr import inspect_upload, prepare_document_images


def test_image_normalization_returns_private_data_url(tmp_path):
    source = tmp_path / "camera.png"
    Image.new("RGB", (2400, 1200), "white").save(source)
    content = source.read_bytes()
    assert inspect_upload(content, "image/png", source.name, 6) == 1
    images = prepare_document_images(str(source), max_dimension=1800)
    assert len(images) == 1
    prefix, encoded = images[0].split(",", 1)
    assert prefix == "data:image/jpeg;base64"
    with Image.open(BytesIO(base64.b64decode(encoded))) as normalized:
        assert max(normalized.size) == 1800


def test_pdf_pages_are_rendered_for_vision(tmp_path):
    source = tmp_path / "two-pages.pdf"
    document = fitz.open()
    document.new_page().insert_text((72, 72), "SYNTHETIC PAGE ONE")
    document.new_page().insert_text((72, 72), "SYNTHETIC PAGE TWO")
    document.save(source)
    document.close()
    assert inspect_upload(source.read_bytes(), "application/pdf", source.name, 6) == 2
    assert len(prepare_document_images(str(source))) == 2
