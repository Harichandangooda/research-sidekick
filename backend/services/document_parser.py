from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader
from backend.limits import MAX_PDF_PAGES, MAX_PAPER_CHARACTERS


def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError(f"PDFs must contain at most {MAX_PDF_PAGES} pages")
    page_text = []
    characters = 0

    for page in reader.pages:
        text = page.extract_text() or ""
        characters += len(text) + 2
        if characters > MAX_PAPER_CHARACTERS:
            raise ValueError("The PDF contains too much text to process")
        page_text.append(text)

    return "\n\n".join(text for text in page_text if text.strip())
