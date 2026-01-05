from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dotenv import load_dotenv
import google.generativeai as genai

import fitz  # PyMuPDF
import pandas as pd
from docx import Document

import zipfile
import io
import os
import re

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

# Enkel global state för nuvarande dokument
CURRENT_DOCUMENT_TEXT: str = ""


# --------------------------------------------------
# Models
# --------------------------------------------------

class ChatRequest(BaseModel):
    question: str


# --------------------------------------------------
# Text helpers
# --------------------------------------------------

def clean_text_for_display(text: str) -> str:
    """
    Normaliserar whitespace så texten blir sökbar och jämn.
    Radbrytningar behålls.
    """
    if not text:
        return ""

    text = text.replace("\xa0", " ").replace("\u202f", " ")
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def extract_text_from_file(file_content: bytes, filename: str) -> str:
    """
    Extraherar text beroende på filtyp.
    Returnerar tom sträng vid okänd eller trasig fil.
    """
    filename = filename.lower()
    text = ""

    try:
        if filename.endswith(".pdf"):
            doc = fitz.open(stream=file_content, filetype="pdf")
            for page in doc:
                text += page.get_text() + "\n"

        elif filename.endswith(".docx"):
            doc = Document(io.BytesIO(file_content))
            paragraphs = [
                clean_text_for_display(p.text)
                for p in doc.paragraphs
                if p.text.strip()
            ]
            text = "\n\n".join(paragraphs)

        elif filename.endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(file_content))
            text = df.to_string(index=False)

        elif filename.endswith(".txt"):
            text = file_content.decode("utf-8", errors="ignore")

    except Exception as e:
        return f"[Fel vid textutvinning: {e}]"

    return text


def add_document_header(text: str, filename: str) -> str:
    """
    Lägger till en tydlig dokumentseparator.
    """
    header = (
        f"\n\n{'=' * 40}\n"
        f"📄 DOKUMENT: {os.path.basename(filename)}\n"
        f"{'=' * 40}\n"
    )
    return header + text


# --------------------------------------------------
# API endpoints
# --------------------------------------------------

@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):
    global CURRENT_DOCUMENT_TEXT

    content = await file.read()
    full_text = ""
    file_list: list[str] = []
    is_complex = False

    # ZIP: flera dokument
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

    # Office / text-filer
    elif file.filename.endswith((".docx", ".xlsx", ".txt")):
        is_complex = True
        extracted = extract_text_from_file(content, file.filename)
        full_text = add_document_header(extracted, file.filename)
        file_list.append(file.filename)

    # PDF eller annat
    else:
        full_text = extract_text_from_file(content, file.filename)
        file_list.append(file.filename)

    CURRENT_DOCUMENT_TEXT = full_text

    result = extractor.analyze_document(full_text)

    if not result:
        return {"error": "Analysen misslyckades."}

    response = result.dict()

    if is_complex:
        response["extracted_text_view"] = full_text
        response["file_list"] = file_list

    return response


@app.post("/chat")
async def chat_with_doc(req: ChatRequest):
    """
    Enkel RAG-liknande chatt mot senaste analyserade dokument.
    """
    global CURRENT_DOCUMENT_TEXT

    try:
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

        model = genai.GenerativeModel("gemini-flash-latest")

        prompt = (
            "Underlag:\n"
            f"{CURRENT_DOCUMENT_TEXT[:500_000]}\n\n"
            f"Fråga: {req.question}"
        )

        response = model.generate_content(prompt)

        return {"answer": response.text}

    except Exception as e:
        return {"answer": f"Fel: {e}"}
