from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dotenv import load_dotenv
import google.generativeai as genai

import fitz
import pandas as pd
from docx import Document

import zipfile
import io
import os
import re
import uuid
from typing import Dict

from src.extractor import RequirementExtractor


# --------------------------------------------------
# App & config
# --------------------------------------------------

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

extractor = RequirementExtractor()


# --------------------------------------------------
# In-memory document store
# --------------------------------------------------

# document_id -> extracted full text
DOCUMENT_STORE: Dict[str, str] = {}


# --------------------------------------------------
# Models
# --------------------------------------------------

class ChatRequest(BaseModel):
    document_id: str
    question: str


# --------------------------------------------------
# Text helpers
# --------------------------------------------------

def clean_text_for_display(text: str) -> str:
    """Normaliserar whitespace utan att ta bort struktur."""
    if not text:
        return ""

    text = text.replace("\xa0", " ").replace("\u202f", " ")
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def extract_text_from_file(file_content: bytes, filename: str) -> str:
    """Extraherar text baserat på filtyp."""
    filename = filename.lower()
    text = ""

    try:
        if filename.endswith(".pdf"):
            doc = fitz.open(stream=file_content, filetype="pdf")
            for page in doc:
                text += page.get_text() + "\n"

        elif filename.endswith(".docx"):
            doc = Document(io.BytesIO(file_content))
            parts = [
                clean_text_for_display(p.text)
                for p in doc.paragraphs
                if p.text.strip()
            ]
            text = "\n\n".join(parts)

        elif filename.endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(file_content))
            text = df.to_string(index=False)

        elif filename.endswith(".txt"):
            text = file_content.decode("utf-8", errors="ignore")

    except Exception as e:
        return f"[Fel vid textutvinning: {e}]"

    return text


def add_document_header(text: str, filename: str) -> str:
    """Tydlig separator mellan dokument."""
    return (
        f"\n\n{'=' * 40}\n"
        f"DOKUMENT: {os.path.basename(filename)}\n"
        f"{'=' * 40}\n"
        f"{text}"
    )


# --------------------------------------------------
# API endpoints
# --------------------------------------------------

@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):
    content = await file.read()

    full_text = ""
    file_list = []
    is_complex = False

    # ZIP = flera dokument
    if file.filename.endswith(".zip"):
        is_complex = True

        with zipfile.ZipFile(io.BytesIO(content)) as z:
            for name in sorted(z.namelist()):
                if name.endswith("/") or "__MACOSX" in name:
                    continue

                with z.open(name) as f:
                    extracted = extract_text_from_file(f.read(), name)

                if extracted.strip():
                    full_text += add_document_header(extracted, name)
                    file_list.append(os.path.basename(name))

    # Office / text
    elif file.filename.endswith((".docx", ".xlsx", ".txt")):
        is_complex = True
        extracted = extract_text_from_file(content, file.filename)
        full_text = add_document_header(extracted, file.filename)
        file_list.append(file.filename)

    # PDF eller övrigt
    else:
        full_text = extract_text_from_file(content, file.filename)
        file_list.append(file.filename)

    # Kör analys
    result = extractor.analyze_document(full_text)
    if not result:
        return {"error": "Analysen misslyckades."}

    # Skapa dokument-ID
    document_id = str(uuid.uuid4())
    DOCUMENT_STORE[document_id] = full_text

    response = result.dict()
    response["document_id"] = document_id

    if is_complex:
        response["extracted_text_view"] = full_text
        response["file_list"] = file_list

    return response


@app.post("/chat")
async def chat_with_doc(req: ChatRequest):
    document_text = DOCUMENT_STORE.get(req.document_id)

    if not document_text:
        raise HTTPException(status_code=404, detail="Dokument hittades inte.")

    try:
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel("gemini-flash-latest")

        prompt = (
            "Underlag:\n"
            f"{document_text[:500_000]}\n\n"
            f"Fråga: {req.question}"
        )

        response = model.generate_content(prompt)

        return {"answer": response.text}

    except Exception as e:
        return {"answer": f"Fel: {e}"}
