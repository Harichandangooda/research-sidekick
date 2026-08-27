from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader


def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    page_text = []

    for page in reader.pages:
        page_text.append(page.extract_text() or "")

    return "\n\n".join(text for text in page_text if text.strip())
