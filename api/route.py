from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Path
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy import select, or_, case, and_
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy.sql.functions import coalesce
from sqlalchemy.exc import NoResultFound
from datetime import datetime as dt, timezone as tz, timedelta as td

from database.session import get_db
from database.model import Lexeme, Word, Sense, Review, Example, Language
from api.model import LanguageISO639, ReviewType, PartOfSpeech
from api.model import EntryCreate, ReviewAdd, ReviewSubmit, ReviewId, ReviewDataUpdate, SearchDataUpdate, LanguageInput
from typing import Optional
from random import shuffle, choice
# from service.fsrs_service import apply_review

router = APIRouter()
templates = Jinja2Templates(directory="./templates")

# Entries --------------------------------------------------------------------------------------------------------------
@router.post("/entry/create", status_code=status.HTTP_201_CREATED)
def create_entry(
    data: EntryCreate,
    db: Session = Depends(get_db),
):
    # Check if entry already exists in this language to avoid duplicates
    lexeme = db.execute(
        select(Lexeme)
            .join(Language)
            .where(Lexeme.lexeme == data.lexeme, Lexeme.idLanguage == data.iso639.id)
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
            ).scalar()

            if sense:
                return((lexeme, word, sense))
    else:
        lexeme = Lexeme(
            lexeme=data.lexeme,
            idLanguage=data.iso639.id,
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
    db.flush()

    if data.addToReview:
        sense.add_review()

    db.commit()

    return (lexeme, word, sense)

@router.post("/update/review", status_code=status.HTTP_200_OK)
def update_entry_review(
    data: ReviewDataUpdate,
    db: Session = Depends(get_db),
):
    rl = db.execute(select(Review).where(Review.id == data.idReview)).scalar_one()

    if data.sense:
        rl.sense.sense = data.sense
    
    if data.note:
        rl.note = data.note

    if data.usage:
        rl.sense.usage = data.usage

    if data.word:
        rl.sense.word.word = data.word

    if data.lexeme:
        rl.sense.word.lexeme.lexeme = data.lexeme
    
    if data.example:
        rl.sense.example.append(
            Example(
                example=data.example.example,
                translation=data.example.translation
            )
        )

    if not data.isActive:
        for r in rl.sense.review:
            r.isActive = data.isActive

    db.commit()

@router.post("/update/search", status_code=status.HTTP_200_OK)
def update_entry_search(
    data: SearchDataUpdate,
    db: Session = Depends(get_db),
):
    sense = db.execute(select(Sense).where(Sense.id == data.idSense)).scalar_one()

    if data.coltype == "Sense":
        sense.sense = data.valueNew
    elif data.coltype == "Usage":
        sense.usage = data.valueNew
    elif data.coltype == "Note":
        sense.note = data.valueNew
    elif data.coltype in ("Example", "Translation"):
        if data.idExample:
            example = db.execute(select(Example).where(Example.id == data.idExample)).scalar_one()
            if data.coltype == "Example":
                example.example = data.valueNew
            else:
                example.translation = data.valueNew
        else:
            if data.coltype == "Example":
                example = Example(example=data.valueNew, translation="NOG INVULLEN", sense=[sense])
            else:
                example = Example(example="NOG INVULLEN", translation=data.valueNew, sense=[sense])
            db.add(example)
    
    db.commit()

# Search & get ---------------------------------------------------------------------------------------------------------
@router.get("/search/term/{term}", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
def search_term(
    request: Request,
    term: str = Path(description="The term to search"),
    searchSense: bool = Query(False, description="Whether to search sense, or lexeme-word (default)"),
    iso639: Optional[LanguageISO639] = Query(None, description="The language to search (iso639-2)"),
    db: Session = Depends(get_db),
):
    termLike = f"%{term}%"
    stmtBase = (
        select(
            Lexeme.id.label("idLexeme"),
            Word.id.label("idWord"),
            Sense.id.label("idSense"),
            Language.iso639.label("Language"),
            case(
                (Lexeme.lexeme == Word.word, Word.word),
                else_=(Lexeme.lexeme + " (" + Word.word + ")")
            ).label("Word"),
            Sense.pos.label("PoS"),
            Sense.sense.label("Sense"),
            coalesce(Sense.usage, "").label("Usage"),
            coalesce(Sense.note, "").label("Note"),
            and_(Review.id.is_not(None), Review.isActive).label("isActive")
        )
        .select_from(Word)
        .join(Lexeme)
        .join(Language)
        .join(Sense)
        .join(Review, isouter=True)
        .where(or_(Review.id.is_(None), Review.typeReview == 1))
    )

    if iso639:
        stmtBase = stmtBase.where(Lexeme.idLanguage == iso639.id)

    if searchSense:
        filterSearchExact = Sense.sense == term
        filterSearchLike = Sense.sense.ilike(termLike)
    else:
        filterSearchExact = or_(Lexeme.lexeme == term, Word.word == term)
        filterSearchLike = or_(Lexeme.lexeme.ilike(termLike), Word.word.ilike(termLike))

    stmt = (
        # First the complete matches
        stmtBase
        .where(
            filterSearchExact
        )
        .order_by(Sense.id)
        .union_all(
            # then the partial matches (limited to 50 entries)
            stmtBase
            .where(
                filterSearchLike,
                ~filterSearchExact
            )
            .limit(50)
            .order_by(Lexeme.lexeme, Language.iso639, Word.word, Sense.id))
    )

    result = db.execute(stmt).all()

    if not result:
        return ""

    seqSense = db.execute(
        select(Sense)
        .where(Sense.id.in_([row.idSense for row in result]))
    ).scalars().all()
    dctExamples = {sense.id: choice(sense.example).__dict__ for sense in seqSense if sense.example}

    resultsFlat = []
    for i in range(len(result)):
        resultsFlat += [dict()]
        
        for k, v in result[i]._asdict().items():
            resultsFlat[i][k] = v

            if k in (("Lexeme", "Word"), ("Sense",))[searchSense]:
                resultsFlat[i][k] = resultsFlat[i][k].replace(term, f"<b style='color:var(--highlight);'>{term}</b>")
            elif k == "idSense":
                rowExample = {"id": "", "example": "", "translation": ""}
                if v in dctExamples:
                    rowExample["id"] = dctExamples[v]["id"]
                    rowExample["example"] = dctExamples[v]["example"]
                    rowExample["translation"] = dctExamples[v]["translation"]
                
                resultsFlat[i]["idExample"] = rowExample["id"]    
                resultsFlat[i]["Example"] = rowExample["example"]
                resultsFlat[i]["Translation"] = rowExample["translation"]

    return templates.TemplateResponse(
        request,
        "table.html",
        {
            "rows": resultsFlat,
            "columns": ["Language", "Word", "PoS", "Sense", "Usage", "Note", "Example", "Translation"]
        }
    )

@router.get("/get/languages", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
def get_languages_selector(
    request: Request,
    db: Session = Depends(get_db),
):
    results = db.execute(select(Language.iso639.label("value"), Language.language.label("label"))).all()
    resultsFlat = [{"value": "", "label": "Language"}] + [row._asdict() for row in results]

    return templates.TemplateResponse(
        request,
        "selector.html",
        {
            "options": resultsFlat
        }
    )

@router.get("/get/pos", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
def get_pos_selector(
    request: Request
):
    ctxt = [{"value": "", "label": "Part of Speech"}] + [{'value': i.value, 'label': i.name } for i in PartOfSpeech]

    return templates.TemplateResponse(
        request,
        "selector.html",
        {
            "options": ctxt
        }
    )

@router.get("/get/reviewtypes", status_code=status.HTTP_200_OK)
def get_review_types(
    request: Request
):
    return {type.id: type.name for type in ReviewType}

# Learning -------------------------------------------------------------------------------------------------------------
@router.post("/add/review", status_code=status.HTTP_200_OK)
def start_learning_translation(
    data: ReviewAdd,
    db: Session = Depends(get_db)
):
    # Get Sense, with eager loading of neede relationships
    try:
        sense = db.execute(
            select(Sense)
            .where(Sense.id == data.idSense)
            .options(
                joinedload(Sense.word)
                .joinedload(Word.lexeme)
                .joinedload(Lexeme.language),
                selectinload(Sense.review)
            )
        ).scalar_one()
    except NoResultFound:
        raise HTTPException(status_code=404, detail=f"Sense with id '{data.idSense}' not found")
    except Exception:
        raise HTTPException(status_code=404, detail="Unknown error occured during query for Sense related to review to add")

    setReviewType = {i.id for i in ReviewType}

    # Activate any existing reviews
    rExisting = db.execute(
        select(Review).where(Review.idSense == data.idSense)
    ).scalars().all()

    lstReview = []

    for r in rExisting:
        r.isActive = True
        setReviewType.remove(r.typeReview)
        lstReview += [r]


    dtNow = dt.now(tz=tz.utc)
    dctKwargs = {
        "idSense": sense.id,
        "dtStarted": dtNow,
        "sense": sense
    }

    # Skip review for the reading if unnecessary
    if not (sense.word.lexeme.language.iso639 in ("jp", "zh") and (sense.word.lexeme.lexeme != sense.word.word)):
        setReviewType.remove(ReviewType("reading").id)

    dctDueAdd = {
        1: td(days=0),
        2: td(days=7),
        # 3: td(days=14), Cloze not yet implemented
        4: td(days=0)
    }

    lstReview += [
        Review(
            typeReview=idType,
            dtDue=dtNow + dctDueAdd[idType],
            **dctKwargs
        )
        for idType in setReviewType
    ]

    db.add_all(lstReview)
    db.commit()

    return(lstReview)

@router.post("/due", status_code=status.HTTP_200_OK)
def get_due_words(
    data: LanguageInput,
    db: Session = Depends(get_db)
):
    stmt = (
        select(
            Review.id,
            Review.typeReview,
            Language.language,
            Lexeme.lexeme,
            Word.word,
            Review.note,
            Sense.sense,
            Sense.pos,
            Sense.usage
        )
        .select_from(Review)
        .join(Sense)
        .join(Word)
        .join(Lexeme)
        .join(Language)
        .where(
            Review.dtDue < dt.now(tz.utc),
            Review.isActive
        )
    )

    if (data.iso639.id != 0):
        stmt = stmt.where(Language.id == data.iso639.id)

    results = db.execute(stmt).all()

    if not results:
        return []

    resultsFlat = [row._asdict() for row in results]
    shuffle(resultsFlat)

    return resultsFlat

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

# Go back 1 review
@router.post("/undo/review", status_code=status.HTTP_200_OK)
def undo_review(
    data: ReviewId,
    db: Session = Depends(get_db)
):
    review = db.execute(
        select(Review)
        .where(Review.id == data.idReview)
        .options(selectinload(Review.reviewLog))
    ).scalar_one()

    dtMax = max([rl.dtReview for rl in review.reviewLog])
    
    if ((dt.now(tz.utc) - dtMax).total_seconds() / 60) > 5:
        return review
    
    review.reviewLog = [rl for rl in review.reviewLog if rl.dtReview != dtMax]
    review.reschedule()

    db.commit()

    return review

# Reschedule reviews
@router.post("/reschedule", status_code=status.HTTP_200_OK)
def reschedule_reviews(
    db: Session = Depends(get_db)
):
    stmt = select(Review)
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
#         stmt = stmt.where(Lexeme.idLanguage == iso639.id)

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
