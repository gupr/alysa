import fitz
import re
from typing import List
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

from services.models import Requirement, ExtractionResult

SKALL_TERMS = [
    "ska", "skall", "måste", "krävs", "åligger", "får ej", "icke", "förbinder sig att"
]
BOR_TERMS = [
    "bör", "borde", "önskvärt", "meriterande", "eftersträvas", "ser gärna", "bedöms positivt"
]

def split_into_sentences(text: str) -> List[str]:
    return [
        s.strip()
        for s in re.split(r'(?<=[.!?])\s+', text)
        if len(s.strip()) > 15
    ]

def extract_with_ocr(pdf_path: str) -> List[str]:
    pages = convert_from_path(pdf_path, dpi=300)
    texts = []

    for img in pages:
        text = pytesseract.image_to_string(img, lang="swe")
        texts.append(text)

    return texts

def extract_requirements(pdf_path: str, filename: str) -> ExtractionResult:
    doc = fitz.open(pdf_path)
    used_ocr = False
    all_pages_text = []

    for page in doc:
        txt = page.get_text("text").strip()
        all_pages_text.append(txt)

    # OCR fallback
    if sum(len(t) for t in all_pages_text) < 200:
        all_pages_text = extract_with_ocr(pdf_path)
        used_ocr = True

    requirements = []
    counter = 1

    for page_idx, page_text in enumerate(all_pages_text):
        for sentence in split_into_sentences(page_text):
            lower = sentence.lower()

            skall = [t for t in SKALL_TERMS if t in lower]
            bor = [t for t in BOR_TERMS if t in lower]

            if not (skall or bor):
                continue

            requirements.append(
                Requirement(
                    id=f"p{page_idx+1}_r{counter:03d}",
                    text=sentence.replace("\n", " "),
                    classification="SKALL" if skall else "BÖR",
                    page=page_idx + 1,
                    matched_terms=skall or bor
                )
            )
            counter += 1

    return ExtractionResult(
        filename=filename,
        page_count=len(all_pages_text),
        requirement_count=len(requirements),
        requirements=requirements,
        used_ocr=used_ocr
    )
