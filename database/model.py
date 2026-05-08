from sqlalchemy import ForeignKey, UniqueConstraint, Integer, String, DateTime, Index, Table, Column, Identity
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from typing import List, Optional
from datetime import datetime, timezone, timedelta

from service.fsrs_service import get_cardUpdated, get_rescheduled_card
from config import settings


SCHEMA = settings.schemaDb

class Base(DeclarativeBase):
    """Base class that all other objects inherit from
    """
    __table_args__ = {"schema": SCHEMA}

    # Timestamps
    dtCreated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    dtUpdated: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

tblSenseExample = Table(
    "sense_example",
    Base.metadata,
    Column("idSense", ForeignKey(f"{SCHEMA}.sense.id"), primary_key=True, index=True),
    Column("idExample", ForeignKey(f"{SCHEMA}.example.id"), primary_key=True, index=True),
    schema=SCHEMA
)

class WordAttributeType(Base):
    """Types for language specific word attributes
    """
    __tablename__ = "word_attribute_type"
    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    idLanguage: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.language.id"))

    name: Mapped[str]
    description: Mapped[str]

    ### Relations ###
    attribute: Mapped[List["WordAttribute"]] = relationship(back_populates="type")

class WordAttribute(Base):
    """Language specific attributes for words
    """
    __tablename__ = "word_attribute"
    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    idWord: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.word.id"))
    idType: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.word_attribute_type.id"))

    value: Mapped[str]

    ### Relations ###
    word: Mapped["Word"] = relationship(back_populates="attribute")
    type: Mapped[WordAttributeType] = relationship(back_populates="attribute")

class Pronunciation(Base):
    """Written pronunciation for words in different langauges, esp. for different dialects
    """
    __tablename__ = "pronunciation"
    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    idWord: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.word.id"))

    pronunciation: Mapped[str]
    dialect: Mapped[str]

    ### Relations ###
    word: Mapped["Word"] = relationship(
        back_populates="pronunciation"
    )

    ### Methods ###
    def __repr__(self) -> str:
        return (
            f"Pronunciation({self.id}, pronunciation={self.pronunciation}, dialect={self.dialect})"
        )

class Example(Base):
    """Example phrases and sentences, with their translation
    """
    __tablename__ = "example"
    __table_args__ = (
        UniqueConstraint("example", "translation"),
        Index("ix_example_id", "id"),
        {"schema": SCHEMA}
    )
    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)

    example: Mapped[str]
    translation: Mapped[str]

    ### Relations ###
    sense: Mapped[List["Sense"]] = relationship(
        secondary=tblSenseExample,
        back_populates="example"
    )

    ### Methods ###
    def __repr__(self) -> str:
        return (
            f"Example({self.id}, example={self.example}, translation={self.translation})"
        )

class Language(Base):
    """Languages used in vocapp
    """
    __table_args__ = (
        UniqueConstraint("iso639"),
        UniqueConstraint("language"),
        {"schema": SCHEMA}
    )
    __tablename__ = "language"
    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)

    iso639: Mapped[str] = mapped_column(String(2))
    language: Mapped[str]
    emoji: Mapped[str]

    ### Relations ###
    lexeme: Mapped[List["Lexeme"]] = relationship(back_populates="language")

    ### Methods ###
    def __repr__(self) -> str:
        return (
            f"Language({self.id}, iso639={self.iso639}, language={self.language})"
        )

class ReviewLog(Base):
    """Review log table, the complete history of all reviews done
    """
    __tablename__ = "reviewlog"
    __table_args__ = (
        Index("ix_reviewlog_idReview", "idReview"),
        {"schema": SCHEMA}
    )
    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)

    idReview: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.review.id"))

    dtDue: Mapped[datetime] =  mapped_column(DateTime(timezone=True))
    dtReview: Mapped[datetime] =  mapped_column(DateTime(timezone=True), server_default=func.now())
    rating: Mapped[int]
    state: Mapped[int]
    stability: Mapped[Optional[float]]
    difficulty: Mapped[Optional[float]]

    ### Relations ###
    reviews: Mapped[List["Review"]] = relationship(
        back_populates="reviewLog"
    )

    ### Methods ###
    def __repr__(self) -> str:
        return (
            f"ReviewLog({self.id}, idReview={self.idReview}, " +
            f"dtReview={self.dtReview}, rating={self.rating}, state={self.state}, " +
            f"stability={self.stability}, difficulty={self.difficulty})"
        )

class Review(Base):
    """Review table, contains info for words and their current review
    """
    __tablename__ = "review"
    __table_args__ = (
        UniqueConstraint("idSense", "typeReview"),
        Index("ix_review_id", "id"),
        Index("ix_review_idSense", "idSense"),
        {"schema": SCHEMA}
    )
    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)

    idSense: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.sense.id"))
    typeReview: Mapped[int]

    dtStarted: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    dtDue: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    dtLastReview: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    state: Mapped[int] = mapped_column(Integer, default=1)
    step: Mapped[Optional[int]]
    stability: Mapped[Optional[float]]
    difficulty: Mapped[Optional[float]]

    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)

    ### Relations ###
    sense: Mapped["Sense"] = relationship(
        "Sense",
        back_populates="review"
    )
    reviewLog: Mapped[List["ReviewLog"]] = relationship(
        back_populates="reviews",
        cascade="all, delete-orphan",
    )

    ### Methods ###
    def update_review(self, rating, dtReview = datetime.now(timezone.utc)):
        try:
            rLog = ReviewLog(
                idReview=self.id,
                dtDue=self.dtDue,
                dtReview=dtReview,
                rating=rating,
                state=self.state,
                stability=self.stability,
                difficulty=self.difficulty
            )

            self.dtLastReview = dtReview
            cardUpdate = get_cardUpdated(self, rating)

        except Exception as e:
            print(f"Error composing review log and/or card update: {e}")
            raise
        else:
            try:
                self.reviewLog.append(rLog)

                # Write updated FSRS state back onto the review
                self.dtDue = cardUpdate.due
                self.state = int(cardUpdate.state)
                if self.state == 3 and rLog.state != 3:
                    self.lapses += 1
                self.step = cardUpdate.step
                self.stability = cardUpdate.stability
                self.difficulty = cardUpdate.difficulty
                self.reps += 1
            except Exception as e:
                print(f"Error updating review and/or log: {e}")
                raise
            else:
                print(f"Review and log successfully updated:\n{self}\n{rLog}\n")

        return self, rLog

    def reschedule(self):
        cardRescheduled = get_rescheduled_card(self, self.reviewLog)

        # Write updated FSRS state back onto the review
        self.dtDue = cardRescheduled.due
        self.state = int(cardRescheduled.state)
        self.step = cardRescheduled.step
        self.stability = cardRescheduled.stability
        self.difficulty = cardRescheduled.difficulty

    def __repr__(self) -> str:
        return (
            f"Review({self.id} ({self.idSense}), " +
            f"word={self.sense.word.word}, sense={self.sense.sense}, " +
            f"dtStarted={self.dtStarted}, dtLastReview={self.dtLastReview}, dtDue={self.dtDue})"
        )

class Sense(Base):
    """Senses table, containing the various meanings for all words
    """
    __tablename__ = "sense"
    __table_args__ = (
        Index("ix_sense_id", "id"),
        Index("ix_sense_idWord", "idWord"),
        Index("ix_sense_sense", "sense"),
        {"schema": SCHEMA}
    )
    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    idWord: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.word.id"))
    pos: Mapped[str] # pos: Part of speech
    sense: Mapped[str]
    definition: Mapped[Optional[str]]
    usage: Mapped[Optional[str]]
    note: Mapped[Optional[str]]
    source: Mapped[Optional[str]]

    ### Relations ###
    word: Mapped["Word"] = relationship(
        back_populates="sense"
    )
    review: Mapped[List[Review]] = relationship(
        back_populates="sense",
        cascade="all, delete-orphan"
    )
    example: Mapped[List[Example]] = relationship(
        secondary=tblSenseExample,
        back_populates="sense"
    )

    ### Methods ###
    def add_review(
        self
        # date_review: datetime | None = None
    ) -> list:
        """
        Convenience helper: create a Review from self → target and reverse.
        """
        reviews: List[Review] = []
        if not self.review:
            reviews = [
                Review(
                    sense=self,
                    typeReview=1
                ),
                Review(
                    sense=self,
                    typeReview=2,
                    dtDue=datetime.now(tz=timezone.utc) + timedelta(days=7)
                )
            ]

        self.review = reviews

        return reviews

    def __repr__(self) -> str:
        return f"Sense({self.id}, {self.word.lexeme.lexeme}, {self.pos}, {self.sense}, {self.word.lexeme.language.iso639})"

class Word(Base):
    """Word table, containing all lexeme variants, linking them to their senses
    """
    __tablename__ = "word"
    __table_args__ = (
        UniqueConstraint("idLexeme", "word"),
        Index("ix_word_id", "id"),
        Index("ix_word_word", "word"),
        {"schema": SCHEMA}
    )
    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    idLexeme: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.lexeme.id"))
    word: Mapped[str]
    source: Mapped[Optional[str]]

    ### Relations ###
    lexeme: Mapped["Lexeme"] = relationship(
        back_populates="word"
    )
    sense: Mapped[List[Sense]] = relationship(
        back_populates="word",
        cascade="all, delete-orphan"
    )
    attribute: Mapped[List[WordAttribute]] = relationship(back_populates="word")
    pronunciation: Mapped[List[Pronunciation]] = relationship(back_populates="word")

    ### Methods ###
    def __repr__(self) -> str:
        return f"Word({self.id}, {self.lexeme.lexeme}, {self.word}, {self.lexeme.language.iso639})"

class Lexeme(Base):
    """Lexeme table, containing all entries with words and senses intended to learn, currently learning or learnt
    """
    __tablename__ = "lexeme"
    __table_args__ = (
        UniqueConstraint("lexeme", "idLanguage"),
        Index("ix_lexeme_id", "id"),
        Index("ix_lexeme_lexeme", "lexeme"),
        Index("ix_lexeme_idLanguage", "idLanguage"),
        {"schema": SCHEMA}
    )
    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    idLanguage: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.language.id"))
    lexeme: Mapped[str]
    source: Mapped[Optional[str]]

    ### Relations ###
    word: Mapped[List[Word]] = relationship(
        back_populates="lexeme",
        cascade="all, delete-orphan"
    )
    language: Mapped[Language] = relationship(back_populates="lexeme")

    ### Methods ###
    def __repr__(self) -> str:
        return f"Lexeme({self.id}, {self.lexeme}, {self.language.iso639})"
