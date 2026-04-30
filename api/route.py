from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Path
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, or_, case
from sqlalchemy.orm import Session, aliased, InstrumentedAttribute
from datetime import datetime as dt, timezone as tz

from database.session import get_db
from database.model import Lexeme, Word, Sense, Review, Example, Language, Pronunciation, ReviewLog
from api.model import EntryCreate, LanguageISO639
from typing import Optional
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
@router.get("/search/term/{term}", status_code=status.HTTP_200_OK)
def search_term(
    request: Request,
    term: str = Path(description="The term to search"),
    iso639: Optional[LanguageISO639] = Query(None, description="The language to search (iso639-2)"),
    db: Session = Depends(get_db),
):
    termLike = f"%{term}%"
    stmt = (
        select(
            Lexeme.id,
            Word.id,
            Sense.id,
            Language.iso639.label("Language"),
            Lexeme.lexeme.label("Lexeme"),
            Word.word.label("Word"),
            Sense.pos.label("PoS"),
            Sense.sense.label("Sense"),
            case(
                (Review.id.is_not(None), "active"),
                else_=""
            ).label("stateActive"),
            case(
                (Review.id.is_not(None), "true"),
                else_=""
            ).label("stateAriaPressed"),
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
        raise HTTPException(status_code=404, detail=f"No entries found for '{term}'")

    flat_results = []
    button_results = []
    for i in range(len(result)):
        flat_results += [dict()]
        button_results += [dict()]
        
        for k, v in result[i]._asdict().items():

            if k in ("idLexeme", "idWord", "idSense"):
                button_results[i]

            flat_results[i][k] = v

            if k in ("lexeme", "word"):
                flat_results[i][k] = flat_results[i][k].replace(term, f"<b>{term}</b>")

    return templates.TemplateResponse(
        request,
        "table.html",
        {
            "rows": flat_results,
            "columns": ["Language", "Lexeme", "Word", "PoS", "Sense"]
        }
    )



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

# # Learning -------------------------------------------------------------------------------------------------------------
# @router.post("/translation/learn", status_code=status.HTTP_200_OK)
# def start_learning_translation(
#     data: TranslationInput,
#     db: Session = Depends(get_db)
# ):
#     translation = db.execute(
#         select(Translation).where(Translation.id == data.id_translation)
#     ).scalars().first()

#     if translation is None:
#         raise HTTPException(status_code=404, detail="Translation not found")
#     elif translation.state is not None:
#         raise HTTPException(status_code=404, detail="Already learning translation")

#     translation.dt_due = dt.now(tz=tz.utc)
#     db.refresh(translation)

#     return(translation)

# # Reviewing ------------------------------------------------------------------------------------------------------------
# @router.get("/due", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
# def get_due_words(
#     request: Request,
#     # language: str,
#     db: Session = Depends(get_db)
# ):
#     WordSource = aliased(Word)
#     WordTarget = aliased(Word)

#     stmt = (
#         select(
#             Translation.id.label("ID"),
#             # Translation.id_word_source.label("ID (van)"),
#             WordSource.word.label("Van"),
#             # Translation.id_word_target.label("ID (naar)"),
#             WordTarget.word.label("Naar")
#         )
#         .join(WordSource, Translation.source_word)
#         .join(WordTarget, Translation.target_word)
#         # .where(
#         #     Translation.dt_due < func.now(),
#         #     # or_(
#         #     #     WordSource.language == language,
#         #     #     WordTarget.language == language
#         #     # )
#         # )
#     )
#     results = db.execute(stmt).all()

#     if not results:
#         raise HTTPException(status_code=404, detail="No due words found")

#     flat_results = [row._asdict() for row in results]
    
#     return templates.TemplateResponse(
#         request,
#         "table.html",
#         {
#             "rows": flat_results,
#             "columns": list(flat_results[0].keys()) if flat_results else []
#         }
#     )

# @router.post("/review/submit", status_code=status.HTTP_200_OK)
# def submit_review(
#     data: ReviewInput,
#     db: Session = Depends(get_db)
# ):
#     translation = db.execute(
#         select(Translation).where(Translation.id == data.id_translation)
#     ).scalars().first()

#     if translation is None:
#         raise HTTPException(status_code=404, detail="Translation not found")

#     review = apply_review(translation, data.rating)
#     db.add(review)
#     db.commit()
#     db.refresh(translation)

#     return translation
