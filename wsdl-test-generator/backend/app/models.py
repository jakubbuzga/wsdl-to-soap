# backend/app/models.py
from pydantic import BaseModel
from typing import List, Optional

class GenerationResponse(BaseModel):
    generationId: str
    xmlContent: Optional[str] = None
    errorMessage: Optional[str] = None

class FeedbackRequest(BaseModel):
    feedback: str

class FeedbackResponse(BaseModel):
    xmlContent: Optional[str] = None
    errorMessage: Optional[str] = None
