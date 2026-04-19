from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, aliased
from datetime import datetime as dt, timezone as tz

from database.session import get_db
from database.model import Word, Translation
from api.model import WordCreate, ReviewInput, TranslationInput, WordResponse, TranslationResponse
from service.fsrs_service import apply_review

router = APIRouter()

# Words ----------------------------------------------------------------------------------------------------------------
@router.post("/word", status_code=status.HTTP_201_CREATED, response_model=WordResponse)
def create_word(
    data: WordCreate,
    db: Session = Depends(get_db),
):
    # Check if word already exists in this language to avoid duplicates
    existing = db.execute(
        select(Word).where(Word.word == data.word, Word.language == data.language)
    ).scalars().first()

    if existing:
        return existing

    word = Word(
        word = data.word,
        language = data.language,
        reading = data.reading
    )
    db.add(word)
    db.commit()
    db.refresh(word)

    return word

@router.get("/word", status_code=status.HTTP_200_OK, response_model=WordResponse)
def get_word(
    word: str = Query(..., min_length=1, description="The word to search for"),
    language: int | None = Query(None, description="Optionally filter by language"),
    db: Session = Depends(get_db),
):
    stmt = select(Word).where(Word.word == word)
    if language is not None:
        stmt = stmt.where(Word.language == language)
    results = db.execute(stmt).scalars().all()

    if not results:
        raise HTTPException(status_code=404, detail="No words found")

    return results

# Learning -------------------------------------------------------------------------------------------------------------
@router.post("/translation/learn", status_code=status.HTTP_200_OK, response_model=TranslationResponse)
def start_learning_translation(
    data: TranslationInput,
    db: Session = Depends(get_db)
):
    translation = db.execute(
        select(Translation).where(Translation.id == data.id_translation)
    ).scalars().first()

    if translation is None:
        raise HTTPException(status_code=404, detail="Translation not found")
    elif translation.state is not None:
        raise HTTPException(status_code=404, detail="Already learning translation")

    translation.dt_due = dt.now(tz=tz.utc)
    db.refresh(translation)

    return(translation)

# Reviewing ------------------------------------------------------------------------------------------------------------
@router.get("/due", status_code=status.HTTP_200_OK)
def get_due_words(
    language: str,
    db: Session = Depends(get_db)
):
    WordSource = aliased(Word)
    WordTarget = aliased(Word)

    stmt = (
        select(Translation, WordSource, WordTarget)
        .join(WordSource, Translation.source_word)
        .join(WordTarget, Translation.target_word)
        .where(
            Translation.dt_due < func.now(),
            or_(
                WordSource.language == language,
                WordTarget.language == language
            )
        )
    )
    results = db.execute(stmt)

    if not results:
        raise HTTPException(status_code=404, detail="No due words found")

    return results

@router.post("/review/submit", status_code=status.HTTP_200_OK, response_model=TranslationResponse)
def submit_review(
    data: ReviewInput,
    db: Session = Depends(get_db)
):
    translation = db.execute(
        select(Translation).where(Translation.id == data.id_translation)
    ).scalars().first()

    if translation is None:
        raise HTTPException(status_code=404, detail="Translation not found")

    review = apply_review(translation, data.rating)
    db.add(review)
    db.commit()
    db.refresh(translation)

    return translation
