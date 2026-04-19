from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, aliased
from datetime import datetime as dt, timezone as tz

from database.session import get_db
from database.model import Word, Translation
from api.model import WordCreate, ReviewInput, TranslationInput, WordResponse, TranslationResponse
from service.fsrs_service import apply_review

router = APIRouter()
templates = Jinja2Templates(directory="./templates")

# Words ----------------------------------------------------------------------------------------------------------------
@router.post("/word", status_code=status.HTTP_201_CREATED)
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

@router.get("/word", status_code=status.HTTP_200_OK)
def get_word(
    word: str = Query(..., min_length=1, description="The word to search for"),
    language: int | None = Query(None, description="Optionally filter by language"),
    db: Session = Depends(get_db),
):
    stmt = select(Word).where(Word.word == word)
    if language is not None:
        stmt = stmt.where(Word.language == language)
    result = db.execute(stmt).scalars().first()

    if not result:
        raise HTTPException(status_code=404, detail="No words found")

    return result

# Learning -------------------------------------------------------------------------------------------------------------
@router.post("/translation/learn", status_code=status.HTTP_200_OK)
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
@router.get("/due", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
def get_due_words(
    request: Request,
    # language: str,
    db: Session = Depends(get_db)
):
    WordSource = aliased(Word)
    WordTarget = aliased(Word)

    stmt = (
        select(
            Translation.id.label("ID"),
            # Translation.id_word_source.label("ID (van)"),
            WordSource.word.label("Van"),
            # Translation.id_word_target.label("ID (naar)"),
            WordTarget.word.label("Naar")
        )
        .join(WordSource, Translation.source_word)
        .join(WordTarget, Translation.target_word)
        # .where(
        #     Translation.dt_due < func.now(),
        #     # or_(
        #     #     WordSource.language == language,
        #     #     WordTarget.language == language
        #     # )
        # )
    )
    results = db.execute(stmt).all()

    if not results:
        raise HTTPException(status_code=404, detail="No due words found")

    flat_results = [row._asdict() for row in results]
    
    return templates.TemplateResponse(
        request,
        "table.html",
        {
            "rows": flat_results,
            "columns": list(flat_results[0].keys()) if flat_results else []
        }
    )

@router.post("/review/submit", status_code=status.HTTP_200_OK)
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
