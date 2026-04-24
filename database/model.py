from sqlalchemy import ForeignKey, UniqueConstraint, Sequence, Integer, String, DateTime, Index, Table, Column
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from typing import List, Optional
from datetime import datetime, timezone, timedelta

from service.fsrs_service import get_updated_review

class Base(DeclarativeBase):
    pass

wordsense_example = Table(
    "wordsense_example",
    Base.metadata,
    Column("id_wordsense", ForeignKey("wordsense.id"), primary_key=True),
    Column("id_example", ForeignKey("example.id"), primary_key=True),
)

class Sound(Base):
    """Written pronunciation for words in different langauges and dialects
    """
    __tablename__ = "sound"
    id: Mapped[int] = mapped_column(Integer, Sequence("seq_sound_id"), primary_key=True)

    id_word: Mapped[int] = mapped_column(ForeignKey("wordsense.id"))

    ipa: Mapped[str]
    tags: Mapped[str]

    def __repr__(self) -> str:
        return (
            f"Sound({self.id}, iso639={self.ipa}, language={self.tags})"
        )

class Example(Base):
    """Example phrases and sentences, with their translation
    """
    __tablename__ = "example"
    id: Mapped[int] = mapped_column(Integer, Sequence("seq_example_id"), primary_key=True)

    example: Mapped[str]
    translation: Mapped[str]

    wordsense: Mapped[List["WordSense"]] = relationship(
        secondary=wordsense_example,
        back_populates="example"
    )

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

    wordsense: Mapped[List["WordSense"]] = relationship(back_populates="language")

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

    reviews: Mapped[List["Review"]] = relationship(
        argument="Review"
    )

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
        UniqueConstraint("id_wordsense"),
        Index("ix_review_id", "id"),
    )
    id: Mapped[int] = mapped_column(Integer, Sequence("seq_translation_id"), primary_key=True)

    id_wordsense: Mapped[str] = mapped_column(ForeignKey("wordsense.id"))
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

    # Word row with source word
    wordsense: Mapped["WordSense"] = relationship(
        "WordSense",
        back_populates="review"
    )

    # Logged Reviews
    reviewLog: Mapped[List["ReviewLog"]] = relationship(
        "ReviewLog",
        foreign_keys="[ReviewLog.id_review]",
        back_populates="reviews",
        cascade="all, delete-orphan",
    )

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
            reviewNew = get_updated_review(self, rating)
        except:
            print("Something went wrong updating the review")
        else:
            self.reviewLog.append(rLog)
            self = reviewNew
            
            print(f"Review and log updated:\n{self}\n{rLog}")

        return self, rLog

    def __repr__(self) -> str:
        return (
            f"Review({self.id} ({self.id_wordsense}), " +
            f"word={self.wordsense.word}, sense={self.wordsense.sense}, " +
            f"dt_started={self.dt_started}, dt_last_review={self.dt_last_review}, dt_due={self.dt_due})"
        )

class WordSense(Base):
    """Word table, containing all words intended to learn, currently learning or learnt
    """
    __tablename__ = "wordsense"
    __table_args__ = (
        UniqueConstraint("word", "id_language"),
        Index("ix_wordsense_id", "id"),
        Index("ix_wordsense_word", "word"),
    )
    id: Mapped[int] = mapped_column(Integer, Sequence("seq_word_id"), primary_key=True)
    id_word: Mapped[Optional[int]]
    word: Mapped[str]
    sense: Mapped[str]
    translation: Mapped[str]
    id_language: Mapped[int] = mapped_column(ForeignKey("language.id"))
    reading: Mapped[Optional[str]]
    definition: Mapped[Optional[str]]

    # Timestamps
    dt_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    dt_updated: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.datetime.now()
    )

    # Linked review
    review: Mapped[List[Review]] = relationship(
        "Review",
        foreign_keys="[Review.id_wordsense]",
        back_populates="wordsense",
        cascade="all, delete-orphan"
    )

    # Language info
    language: Mapped[Language] = relationship(back_populates="wordsense")

    example: Mapped[List[Example]] = relationship(
        secondary=wordsense_example,
        back_populates="wordsense"
    )

    def add_review(
        self
        # date_review: datetime | None = None
    ) -> list:
        """
        Convenience helper: create a Review from self → target and reverse.
        """
        reviews = []
        if not self.review:
            reviews = [
                Review(
                    wordsense=self,
                    is_reverse=False
                ),
                Review(
                    wordsense=self,
                    is_reverse=True,
                    dt_due=datetime.now(tz=timezone.utc) + timedelta(days=7)
                )
            ]

        return reviews

    def __repr__(self) -> str:
        return f"WordSense({self.id}, {self.word}, language={self.language})"
