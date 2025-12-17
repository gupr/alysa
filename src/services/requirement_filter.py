# services/pdf_extraction.py
# Unified, cleaned-up requirement extraction for Alysa

import fitz  # PyMuPDF
import re
from typing import List, Dict

# -----------------------------
# Rule vocabulary (single source of truth)
# -----------------------------

SKALL_TERMS = [
    "ska",
    "skall",
    "måste",
    "krävs",
    "åligger",
    "får ej",
    "icke",
    "förbinder sig att",
]

BOR_TERMS = [
    "bör",
    "borde",
    "önskvärt",
    "meriterande",
    "eftersträvas",
    "ser gärna",
    "bedöms positivt",
]


# -----------------------------
# Text utilities
# -----------------------------

def split_into_sentences(text: str) -> List[str]:
    """
    Simple sentence splitter.
    Avoids word-boundary regexes to remain robust for Swedish characters.
    """
    raw = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in raw if len(s.strip()) > 10]


# -----------------------------
# Classification
# -----------------------------

def classify_sentence(sentence: str) -> Dict | None:
    """
    Classify a sentence as SKALL / BÖR or ignore.
    Uses containment instead of \b regex to support Nordic characters.
    """
    lowered = sentence.lower()

    matched_skall = [t for t in SKALL_TERMS if t in lowered]
    if matched_skall:
        return {
            "rule": "SKALL",
            "matched_terms": matched_skall,
        }

    matched_bor = [t for t in BOR_TERMS if t in lowered]
    if matched_bor:
        return {
            "rule": "BÖR",
            "matched_terms": matched_bor,
        }

    return None


# -----------------------------
# PDF extraction pipeline
# -----------------------------

def extract_requirements_from_pdf(pdf_path: str) -> Dict:
    """
    Extracts requirement candidates from a PDF.
    Returns structured, deterministic output suitable for downstream AI.
    """
    doc = fitz.open(pdf_path)

    requirements: List[Dict] = []
    used_ocr = False
    req_counter = 1

    for page_index in range(doc.page_count):
        page = doc.load_page(page_index)
        page_text = page.get_text().strip()
        source = "text"

        # OCR fallback placeholder (future hook)
        if len(page_text) < 50:
            used_ocr = True
            page_text = ""  # OCR would populate this later
            source = "ocr"

        sentences = split_into_sentences(page_text)

        for sentence in sentences:
            classification = classify_sentence(sentence)
            if not classification:
                continue

            requirements.append({
                "id": f"p{page_index + 1}_r{req_counter:03d}",
                "page": page_index + 1,
                "source": source,
                "text": sentence,
                "rule": classification["rule"],
                "matched_terms": classification["matched_terms"],
            })

            req_counter += 1

    return {
        "page_count": doc.page_count,
        "used_ocr": used_ocr,
        "requirement_count": len(requirements),
        "requirements": requirements,
    }
