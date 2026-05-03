from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Path, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, or_, case
from sqlalchemy.orm import Session
from datetime import datetime as dt, timezone as tz, timedelta as td

from database.session import get_db
from database.model import Lexeme, Word, Sense, Review, Example, Language, Pronunciation, ReviewLog
from api.model import EntryCreate, LanguageISO639, ReviewAdd, ReviewSubmit, ReviewReschedule
from typing import Optional
from random import shuffle
# from service.fsrs_service import apply_review

router = APIRouter()
templates = Jinja2Templates(directory="./templates")

# Entries --------------------------------------------------------------------------------------------------------------
@router.post("/entry", status_code=status.HTTP_201_CREATED)
def create_entry(
    data: EntryCreate,
    db: Session = Depends(get_db),
):
    # Check if entry already exists in this language to avoid duplicates
    lexeme = db.execute(
        select(Lexeme)
            .join(Language)
            .where(Lexeme.lexeme == data.lexeme, Lexeme.id_language == data.iso639.id)
    ).scalar()

    word = None
    if lexeme:
        word = db.execute(
            select(Word)
                .where(Word.lexeme == lexeme, Word.word == data.word)
        ).scalar()

        if word:
            sense = db.execute(
                select(Sense)
                    .where(Sense.word == word, Sense.sense == data.sense)
            )

            if sense:
                return((lexeme, word, sense))
    else:
        lexeme = Lexeme(
            lexeme=data.lexeme,
            id_language=data.iso639,
            source=data.source
        )
        db.add(lexeme)
        db.flush()

    if not word:
        word = Word(
            word=data.word,
            lexeme=lexeme,
            source=data.source
        )
        db.add(word)
        db.flush()

    sense = Sense(
        pos=data.pos,
        sense=data.sense,
        word=word,
        source=data.source
    )
    db.add(sense)
    db.commit()

    return (lexeme, word, sense)

# Search & get ---------------------------------------------------------------------------------------------------------
@router.get("/search/term/{term}", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
def search_term(
    request: Request,
    term: str = Path(description="The term to search"),
    iso639: Optional[LanguageISO639] = Query(None, description="The language to search (iso639-2)"),
    db: Session = Depends(get_db),
):
    termLike = f"%{term}%"
    stmt = (
        select(
            Lexeme.id.label("idLexeme"),
            Word.id.label("idWord"),
            Sense.id.label("idSense"),
            Language.iso639.label("Language"),
            case(
                (Lexeme.lexeme == Word.word, Word.word),
                else_=(Lexeme.lexeme + " (" + Word.word + ")")
            ).label("Word"),
            # Lexeme.lexeme.label("Lexeme"),
            # Word.word.label("Word"),
            Sense.pos.label("PoS"),
            Sense.sense.label("Sense"),
            case(
                (Review.id.is_not(None), True),
                else_=False
            ).label("isActive")
        )
        .select_from(Word)
        .join(Lexeme)
        .join(Language)
        .join(Sense)
        .join(Review, isouter=True)
        .where(or_(Lexeme.lexeme.like(termLike), Word.word.like(termLike)))
        .where(or_(Review.id.is_(None), ~Review.is_reverse))
        .limit(50)
        .order_by(Lexeme.lexeme, Language.iso639, Word.word, Sense.pos, Sense.sense)
    )

    if iso639:
        stmt = stmt.where(Lexeme.id_language == iso639.id)

    result = db.execute(stmt).all()

    if not result:
        return ""

    flat_results = []
    for i in range(len(result)):
        flat_results += [dict()]
        
        for k, v in result[i]._asdict().items():
            flat_results[i][k] = v

            if k in ("Lexeme", "Word"):
                flat_results[i][k] = flat_results[i][k].replace(term, f"<b style='color:var(--highlight);'>{term}</b>")

    return templates.TemplateResponse(
        request,
        "table.html",
        {
            "rows": flat_results,
            "columns": ["Language", "Word", "PoS", "Sense"]
        }
    )

# Learning -------------------------------------------------------------------------------------------------------------
@router.post("/add/review/", status_code=status.HTTP_200_OK)
def start_learning_translation(
    data: ReviewAdd,
    db: Session = Depends(get_db)
):

    rExisting = db.execute(
        select(Review).where(Review.id_sense == data.idSense)
    ).all()
    if rExisting:
        return rExisting
    
    sData = db.execute(
        select(Sense).where(Sense.id == data.idSense)
    )

    if not sData:
        raise HTTPException(status_code=404, detail=f"Sense with id '{data.idSense}' not found")

    dctKwargs = {
        "id_sense": data.idSense,
        "dt_started": dt.now(tz=tz.utc),
        "sense": sData.scalar_one()
    }

    rData = [
        Review(
            is_reverse=False,
            dt_due=dt.now(tz=tz.utc),
            **dctKwargs
        ),
        Review(
            is_reverse=True,
            dt_due=dt.now(tz=tz.utc) + td(days=7),
            **dctKwargs
        ),
    ]

    db.add_all(rData)
    db.commit()

    return(rData)

@router.get("/due", status_code=status.HTTP_200_OK)
def get_due_words(db: Session = Depends(get_db)):
    stmt = (
        select(
            Review.id,
            Review.is_reverse,
            Language.language,
            Lexeme.lexeme,
            Word.word,
            Sense.sense,
            Sense.pos
        )
        .select_from(Review)
        .join(Sense)
        .join(Word)
        .join(Lexeme)
        .join(Language)
        .where(Review.dt_due < dt.now(tz.utc))
    )
    results = db.execute(stmt).all()

    if not results:
        return []

    flat_results = [row._asdict() for row in results]
    shuffle(flat_results)

    return flat_results

@router.post("/submit/review", status_code=status.HTTP_200_OK)
def submit_review(
    data: ReviewSubmit,
    db: Session = Depends(get_db)
):
    review = db.execute(
        select(Review).where(Review.id == data.idReview)
    ).scalar_one()

    review.update_review(
        data.rating,
        data.dtReview
    )
    db.commit()

    return review

# Reschedule reviews
@router.post("/reschedule", status_code=status.HTTP_200_OK)
def reschedule_reviews(
    data: ReviewReschedule,
    db: Session = Depends(get_db)
):
    stmt = select(Review)

    if data.idReview:
        stmt = stmt.where(Review.id == data.idReview)
    results = db.execute(stmt).scalars().all()

    for result in results:
        result.reschedule()

    db.commit()

    return dict()

# # Generic function
# def get_entry(
#     db: Session,
#     object: InstrumentedAttribute[str | int],
#     term: str | int,
#     iso639: Optional[LanguageISO639] = None
# ):
#     stmt = (
#         select(Lexeme.lexeme, Word.word, Sense.pos, Sense.sense)
#         .join(Lexeme)
#         .join(Sense)
#         .where(object == term)
#     )

#     if iso639:
#         stmt = stmt.where(Lexeme.id_language == iso639.id)

#     result = db.execute(stmt).all()

#     if not result:
#         raise HTTPException(status_code=404, detail=f"No '{object}' found for '{term}'")

#     return result

# # By 'name'
# @router.get("/search/lexeme/{lexeme}/{iso639}", status_code=status.HTTP_200_OK)
# def search_lexeme_language(
#     lexeme: str = Path(description="The lexeme to search"),
#     iso639: LanguageISO639 = Path(description="The language to search (iso639-2)"),
#     db: Session = Depends(get_db),
# ):
#     result = get_entry(db, Lexeme.lexeme, lexeme, iso639=iso639)
#     return [row._asdict() for row in result]

# @router.get("/search/lexeme/{lexeme}", status_code=status.HTTP_200_OK)
# def search_lexeme(
#     lexeme: str = Path(description="The lexeme to search"),
#     db: Session = Depends(get_db),
# ):
#     result = get_entry(db, Lexeme.lexeme, lexeme)
#     return [row._asdict() for row in result]

# @router.get("/search/word/{word}/", status_code=status.HTTP_200_OK)
# def search_word(
#     word: str = Path(description="The word to search"),
#     db: Session = Depends(get_db),
# ):
#     result = get_entry(db, Word.word, word)
#     return [row._asdict() for row in result]

# # By ID
# @router.get("/get/lexeme/{id}", status_code=status.HTTP_200_OK)
# def get_lexeme(
#     id: str = Path(description="The id of the lexeme to search"),
#     db: Session = Depends(get_db),
# ):
#     result = get_entry(db, Lexeme.id, id)
#     return [row._asdict() for row in result]

# @router.get("/get/word/{word}/", status_code=status.HTTP_200_OK)
# def get_word(
#     id: str = Path(description="The id of the word to search"),
#     db: Session = Depends(get_db),
# ):
#     result = get_entry(db, Word.id, id)
#     return [row._asdict() for row in result]
