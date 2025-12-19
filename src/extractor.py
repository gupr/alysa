import os
import logging
import json
import google.generativeai as genai
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AlysaCore")

# --- DATAMODELLER (NU MED SMART TVÄTT) ---
class Requirement(BaseModel):
    text: str = Field(..., description="Exakt citat.")
    classification: str = Field(..., description="SKALL eller BÖR")
    confidence: int = Field(..., ge=1, le=10)
    reasoning: str

    # Denna funktion körs INNAN validering och fixar AI:ns ordval
    @field_validator('classification', mode='before')
    @classmethod
    def normalize_classification(cls, v):
        v = str(v).upper().strip()
        # Mappa synonymer till rätt standard
        if v in ['SKA', 'MÅSTE', 'KRAV', 'OBLIGATORISKT', 'FÅR INTE', 'FÅR EJ']:
            return 'SKALL'
        if v in ['BÖR', 'ÖNSKEMÅL', 'MERITERANDE']:
            return 'BÖR'
        # Om det är något helt annat, anta BÖR (för att undvika krasch)
        if v not in ['SKALL', 'BÖR']:
            return 'BÖR'
        return v
    
class Risk(BaseModel):
    text: str = Field(..., description="Riskfylld text.")
    severity: str = Field(..., description="HÖG, MEDEL eller LÅG")
    reasoning: str

    @field_validator('severity', mode='before')
    @classmethod
    def normalize_severity(cls, v):
        v = str(v).upper().strip()
        if v not in ['HÖG', 'MEDEL', 'LÅG']:
            return 'MEDEL' # Fallback
        return v

class ExtractionResult(BaseModel):
    summary: str
    file_structure: List[str] = []
    requirements: List[Requirement]
    risks: List[Risk] = []

class RequirementExtractor:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key: logger.error("❌ Saknar GOOGLE_API_KEY!")
        
        genai.configure(api_key=api_key)
        
        # Vi kör på den modell som fungerar för din nyckel
        self.model_name = 'gemini-flash-latest'

        self.model = genai.GenerativeModel(
            self.model_name,
            generation_config={"response_mime_type": "application/json"}
        )
        
        try:
            with open("system_prompt.txt", "r", encoding="utf-8") as f: self.system_prompt = f.read()
        except: self.system_prompt = "Analysera underlaget."

    def analyze_document(self, text_chunk: str) -> Optional[ExtractionResult]:
        try:
            logger.info(f"✨ Skickar {len(text_chunk)} tecken till {self.model_name}...")
            
            prompt = f"{self.system_prompt}\n\nANALYSERA:\n{text_chunk}"
            
            response = self.model.generate_content(prompt)
            
            json_str = response.text.strip()
            # Städa JSON-strängen
            if json_str.startswith("```json"): json_str = json_str[7:]
            if json_str.endswith("```"): json_str = json_str[:-3]
            
            data = json.loads(json_str)
            
            # Self-healing för saknade listor
            if "file_structure" not in data: data["file_structure"] = []
            if "risks" not in data: data["risks"] = []
            if "requirements" not in data: data["requirements"] = []

            # Nu körs Pydantic med våra nya validators
            return ExtractionResult(**data)

        except Exception as e:
            logger.error(f"Gemini/Validation Error: {e}")
            return None