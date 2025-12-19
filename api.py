from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from src.extractor import RequirementExtractor
import fitz
import os
import io
import zipfile
import pandas as pd
from docx import Document
from dotenv import load_dotenv
from pydantic import BaseModel
import google.generativeai as genai
import re

load_dotenv()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

extractor = RequirementExtractor()
CURRENT_DOCUMENT_TEXT = ""

class ChatRequest(BaseModel):
    question: str

def clean_text_for_display(text: str) -> str:
    """Gör texten sökbar genom att normalisera mellanslag."""
    if not text: return ""
    # Byt ut konstiga Word-mellanslag mot vanliga
    text = text.replace('\xa0', ' ').replace('\u202f', ' ')
    # Ta bort överflödiga tabbar men behåll radbrytningar
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def extract_text_from_file(file_content: bytes, filename: str) -> str:
    text = ""
    filename = filename.lower()
    try:
        if filename.endswith(".pdf"):
            doc = fitz.open(stream=file_content, filetype="pdf")
            for page in doc: text += page.get_text() + "\n"
        elif filename.endswith(".docx"):
            doc = Document(io.BytesIO(file_content))
            parts = []
            for para in doc.paragraphs:
                # Vi tvättar varje stycke
                cleaned = clean_text_for_display(para.text)
                if cleaned: parts.append(cleaned)
            # Lägg in dubbla radbrytningar för att separera stycken tydligt
            text = "\n\n".join(parts)
        elif filename.endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(file_content))
            text = df.to_string()
        elif filename.endswith(".txt"):
            text = file_content.decode("utf-8", errors='ignore')
    except Exception as e: return f"[Fel: {e}]"
    return text

@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):
    global CURRENT_DOCUMENT_TEXT
    content = await file.read()
    full_text = ""
    file_list = []
    is_complex = False

    if file.filename.endswith(".zip"):
        is_complex = True
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            for filename in sorted(z.namelist()):
                if not filename.endswith("/") and "__MACOSX" not in filename:
                    with z.open(filename) as f:
                        extracted = extract_text_from_file(f.read(), filename)
                        if extracted.strip():
                            header = f"\n\n{'='*40}\n📄 DOKUMENT: {os.path.basename(filename)}\n{'='*40}\n"
                            full_text += header + extracted
                            file_list.append(os.path.basename(filename))
    elif file.filename.endswith((".docx", ".xlsx", ".txt")):
        is_complex = True
        full_text = f"\n\n{'='*40}\n📄 DOKUMENT: {file.filename}\n{'='*40}\n" + extract_text_from_file(content, file.filename)
        file_list.append(file.filename)
    else:
        full_text = extract_text_from_file(content, file.filename)
        file_list.append(file.filename)

    CURRENT_DOCUMENT_TEXT = full_text
    
    result = extractor.analyze_document(full_text)
    
    if result:
        res = result.dict()
        if is_complex:
            res["extracted_text_view"] = full_text
            res["file_list"] = file_list
        return res
    return {"error": "Analysen misslyckades."}

@app.post("/chat")
async def chat_with_doc(req: ChatRequest):
    global CURRENT_DOCUMENT_TEXT
    try:
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        # Vi använder den modell vi vet funkar
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content(f"Underlag:\n{CURRENT_DOCUMENT_TEXT[:500000]}\n\nFråga: {req.question}")
        return {"answer": response.text}
    except Exception as e: return {"answer": f"Fel: {e}"}