from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict
from enum import Enum
from fsrs import Rating

# --- Predefined values ---
# Languages
class LanguageISO639(str, Enum):
    id: int

    def __new__(cls, iso639: str, id_language: int):
        obj: str = str.__new__(cls, iso639)
        obj._value_ = iso639
        obj.id = id_language
        return obj

    Dutch      = ("nl", 1)
    Japanese   = ("jp", 2)
    Vietnamese = ("vi", 3)
    Chinese    = ("zh", 4)

# Parts of speech
class PartOfSpeech(str, Enum):
    Adjecive = "adj"
    Adnominal = "adnominal"
    Adverb = "adv"
    Affix = "affix"
    Character = "character"
    Circumposition = "circumpos"
    Classifier = "classifier"
    CombiningForm = "combining_form"
    Conjunction = "conj"
    Counter = "counter"
    Determiner = "det"
    Infix = "infix"
    Noun = "noun"
    Numeral = "num"
    Particle = "particle"
    Postposition = "postp"
    Prefix = "prefix"
    Preposition = "prep"
    Pronoun = "pron"
    Root = "root"
    Suffix = "suffix"
    Verb = "verb"

# --- Input Models ---
class EntryCreate(BaseModel):
    lexeme: str = Field(..., min_length=1, description="The lexeme of the word to add")
    word: str = Field(..., min_length=1, description="The word form to add")
    sense: str = Field(..., min_length=1, description="The sense to add")
    pos: PartOfSpeech = Field(
        ...,
        min_length=1,
        description="The part of speech of the sense to add",
        examples=["noun", "verb"]
    )

    iso639: LanguageISO639 = Field(
        ...,
        min_length=2, max_length=2,
        description="ISO-639 Language Code (2-letter)",
        examples=["vi", "jp", "zh", "nl"]
    )
    pronunciation: Optional[Dict[str, str]] = Field(
        dict(),
        description="Pronunciation(s) of the word to add",
        examples=[{"ipa": "[maj˧˧]", "dialect": "Hà-Nội"}]
    )
    source: Optional[str] = Field(
        None,
        description="Source of entry to add",
        examples=["Wiktionary"]
    )
    addToReview: bool = Field(
        True,
        description="Whether to immediately add the word to the review stack"
    )

class ReviewAdd(BaseModel):
    idSense: int = Field(..., description="ID of the sense to add to reviews")

class ReviewSubmit(BaseModel):
    idReview: int = Field(..., description="ID of the review")
    dtReview: datetime = Field(..., description="Datetime of review, UTC")
    rating: Rating = Field(..., description="SRS Rating: 0=Again, 1=Hard, 2=Good, 3=Easy")

class ReviewReschedule(BaseModel):
    idReview: Optional[int] = Field(None, description="ID of the review to reschedule")

class ExampleInput(BaseModel):
    example: str = Field(..., min_length=1, description="Example sentence in the language being studied")
    translation: str = Field(..., min_length=1, description="Translation of the example sentence in English")

class ReviewDataUpdate(BaseModel):
    idReview: int = Field(..., description="ID of the review for which data should be updated")
    lexeme: Optional[str] = Field(None, description="New lexeme text")
    word: Optional[str] = Field(None, description="New word text")
    sense: Optional[str] = Field(None, description="New sense text")
    example: Optional[ExampleInput]

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
