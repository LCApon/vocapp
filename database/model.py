from sqlalchemy import ForeignKey, UniqueConstraint, Sequence, Integer, String, DateTime, Index, Table, Column
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from typing import List, Optional
from datetime import datetime, timezone, timedelta

from service.fsrs_service import get_updated_card

class Base(DeclarativeBase):
    pass

sense_example = Table(
    "sense_example",
    Base.metadata,
    Column("id_wordsense", ForeignKey("sense.id"), primary_key=True),
    Column("id_example", ForeignKey("example.id"), primary_key=True),
)

class WordAttributeType(Base):
    """Types for language specific word attributes
    """
    __tablename__ = "word_attribute_type"
    id: Mapped[int] = mapped_column(Integer, Sequence("seq_word_attribute_type_id"), primary_key=True)
    id_language: Mapped[int] = mapped_column(ForeignKey("language.id"))

    name: Mapped[str]
    description: Mapped[str]

    ### Relations ###
    attribute: Mapped[List["WordAttribute"]] = relationship(back_populates="type")

class WordAttribute(Base):
    """Language specific attributes for words
    """
    __tablename__ = "word_attribute"
    id: Mapped[int] = mapped_column(Integer, Sequence("seq_word_attribute_id"), primary_key=True)
    id_word: Mapped[int] = mapped_column(ForeignKey("word.id"))
    id_type: Mapped[int] = mapped_column(ForeignKey("word_attribute_type.id"))

    value: Mapped[str]

    ### Relations ###
    word: Mapped["Word"] = relationship(back_populates="attribute")
    type: Mapped[WordAttributeType] = relationship(back_populates="attribute")

class Pronunciation(Base):
    """Written pronunciation for words in different langauges, esp. for different dialects
    """
    __tablename__ = "pronunciation"
    id: Mapped[int] = mapped_column(Integer, Sequence("seq_sound_id"), primary_key=True)
    id_word: Mapped[int] = mapped_column(ForeignKey("word.id"))

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
    id: Mapped[int] = mapped_column(Integer, Sequence("seq_example_id"), primary_key=True)

    example: Mapped[str]
    translation: Mapped[str]

    ### Relations ###
    sense: Mapped[List["Sense"]] = relationship(
        secondary=sense_example,
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
    __tablename__ = "language"
    id: Mapped[int] = mapped_column(Integer, Sequence("seq_language_id"), primary_key=True)

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
    id: Mapped[int] = mapped_column(Integer, Sequence("seq_review_id"), primary_key=True)

    id_review: Mapped[int] = mapped_column(ForeignKey("review.id"))

    dt_due: Mapped[datetime] =  mapped_column(DateTime(timezone=True))
    dt_review: Mapped[datetime] =  mapped_column(DateTime(timezone=True), server_default=func.now())
    rating: Mapped[int]
    state: Mapped[int]
    stability: Mapped[float]
    difficulty: Mapped[float]

    ### Relations ###
    reviews: Mapped[List["Review"]] = relationship(
        back_populates="reviewLog"
    )

    ### Methods ###
    def __repr__(self) -> str:
        return (
            f"ReviewLog({self.id}, id_review={self.id_review}, " +
            f"dt_review={self.dt_review}, rating={self.rating}, state={self.state}, " +
            f"stability={self.stability}, difficulty={self.difficulty})"
        )

class Review(Base):
    """Review table, contains info for words and their current review
    """
    __tablename__ = "review"
    __table_args__ = (
        UniqueConstraint("id_sense", "is_reverse"),
        Index("ix_review_id", "id"),
    )
    id: Mapped[int] = mapped_column(Integer, Sequence("seq_review_id"), primary_key=True)

    id_sense: Mapped[str] = mapped_column(ForeignKey("sense.id"))
    is_reverse: Mapped[bool]

    dt_started: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    dt_due: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    dt_last_review: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    state: Mapped[Optional[int]]
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
    def update_review(self, rating, dt_review = datetime.now(timezone.utc)):
        try:
            rLog = ReviewLog(
                id_review=self.id,
                dt_due=self.dt_due,
                dt_review=dt_review,
                rating=rating,
                state=self.state,
                stability=self.stability,
                difficulty=self.difficulty
            )

            self.dt_last_review = dt_review
            cardUpdate = get_updated_card(self, rating)

        except Exception as e:
            print(f"Error composing review log and/or card update: {e}")
            raise
        else:
            try:
                self.reviewLog.append(rLog)

                # Write updated FSRS state back onto the review
                self.dt_due = cardUpdate.due
                self.state = int(cardUpdate.state)
                if self.state == 1:
                    self.lapses += 1
                self.step = cardUpdate.step
                self.stability = cardUpdate.stability
                self.difficulty = cardUpdate.difficulty
                self.reps += 1
            except Exception as e:
                print(f"Error updating review and/or log: {e}")
                raise
            else:
                print(f"Review and log successfully updated:\n{self}\n{rLog}")

        return self, rLog

    def __repr__(self) -> str:
        return (
            f"Review({self.id} ({self.id_sense}), " +
            f"word={self.sense.word.word}, sense={self.sense.sense}, " +
            f"dt_started={self.dt_started}, dt_last_review={self.dt_last_review}, dt_due={self.dt_due})"
        )

class Sense(Base):
    """Senses table, containing the various meanings for all words
    """
    __tablename__ = "sense"
    __table_args__ = (
        Index("ix_sense_id", "id"),
        Index("ix_sense_id_word", "id_word"),
    )
    id: Mapped[int] = mapped_column(Integer, Sequence("seq_sense_id"), primary_key=True)
    id_word: Mapped[int] = mapped_column(ForeignKey("word.id"))
    pos: Mapped[str] # pos: Part of speech
    sense: Mapped[str]
    translation: Mapped[str]
    definition: Mapped[Optional[str]]
    usage: Mapped[Optional[str]]
    note: Mapped[Optional[str]]
    source: Mapped[Optional[str]]

    # Timestamps
    dt_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    dt_updated: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.datetime.now()
    )

    ### Relations ###
    word: Mapped["Word"] = relationship(
        back_populates="sense"
    )
    review: Mapped[List[Review]] = relationship(
        back_populates="sense",
        cascade="all, delete-orphan"
    )
    example: Mapped[List[Example]] = relationship(
        secondary=sense_example,
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
                    is_reverse=False
                ),
                Review(
                    sense=self,
                    is_reverse=True,
                    dt_due=datetime.now(tz=timezone.utc) + timedelta(days=7)
                )
            ]

        self.review = reviews

        return reviews

    def __repr__(self) -> str:
        return f"Sense({self.id}, {self.word.lexeme.lexeme}, {self.pos}, {self.sense}, {self.word.lexeme.language.iso639})"

class Word(Base):
    """Word table, containing all lexeme variants and their senses
    """
    __tablename__ = "word"
    __table_args__ = (
        UniqueConstraint("id_lexeme", "word"),
        Index("ix_word_id", "id"),
        Index("ix_word_word", "word"),
    )
    id: Mapped[int] = mapped_column(Integer, Sequence("seq_word_id"), primary_key=True)
    id_lexeme: Mapped[int] = mapped_column(ForeignKey("lexeme.id"))
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
        UniqueConstraint("lexeme", "id_language"),
        Index("ix_lexeme_id", "id"),
        Index("ix_lexeme_lexeme", "lexeme"),
        Index("ix_lexeme_id_language", "id_language"),
    )
    id: Mapped[int] = mapped_column(Integer, Sequence("seq_lexeme_id"), primary_key=True)
    id_language: Mapped[int] = mapped_column(ForeignKey("language.id"))
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
