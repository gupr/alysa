from fastapi import APIRouter, UploadFile, File, HTTPException
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
import tempfile
import os

router = APIRouter(tags=["PDF"])

@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Endast PDF-filer stöds")

    pdf_bytes = await file.read()

    extracted_pages = []
    used_ocr = False

    # --- Försök textbaserad extraktion ---
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    try:
        tmp.write(pdf_bytes)
        tmp.close()

        with pdfplumber.open(tmp.name) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                extracted_pages.append({
                    "page": i + 1,
                    "text": text.strip()
                })
    finally:
        os.unlink(tmp.name)

    total_text_length = sum(len(p["text"]) for p in extracted_pages)

    # --- OCR fallback ---
    if total_text_length < 100:
        used_ocr = True
        extracted_pages = []

        images = convert_from_bytes(pdf_bytes)
        for i, image in enumerate(images):
            text = pytesseract.image_to_string(image, lang="swe+eng")
            extracted_pages.append({
                "page": i + 1,
                "text": text.strip()
            })

    return {
        "filename": file.filename,
        "page_count": len(extracted_pages),
        "used_ocr": used_ocr,
        "pages": extracted_pages
    }
