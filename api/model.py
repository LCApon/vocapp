from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

# --- Input Models ---

class WordCreate(BaseModel):
    word: str = Field(..., min_length=1, description="The word to add")
    language: str = Field(..., min_length=2, max_length=2, description="ISO Language Code (e.g., 'en', 'jp', 'vn')")
    reading: Optional[str] = None

class ReviewInput(BaseModel):
    id_translation: int = Field(..., description="ID of the translation to review")
    rating: int = Field(..., description="SRS Rating: 0=Again, 1=Hard, 2=Good, 3=Easy")

class TranslationInput(BaseModel):
    id_translation: int = Field(..., description="ID of the translation to start learning")

# --- Output Models ---

class WordResponse(BaseModel):
    id: int
    word: str
    language: str

    model_config = {"from_attributes": True}

class TranslationResponse(BaseModel):
    id: int

    id_word_source: str
    id_word_target: str

    dt_started: Optional[datetime]
    dt_last_review: Optional[datetime]
    dt_due: Optional[datetime]

    model_config = {"from_attributes": True}
