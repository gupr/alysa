from pydantic import BaseModel, Field
from typing import List, Optional

class Requirement(BaseModel):
    id: str
    text: str
    classification: str
    page: int
    matched_terms: List[str]
    confidence: int = 10
    reasoning: str = "Hittades via mönstermatchning."

class ExtractionResult(BaseModel):
    filename: str
    page_count: int
    requirement_count: int
    requirements: List[Requirement]
    used_ocr: bool = False