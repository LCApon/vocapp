from sqlalchemy import ForeignKey, UniqueConstraint, Sequence, Integer, String, DateTime, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from typing import List, Optional
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Review(Base):
    """Review table, with complete history of all reviews done
    """
    __tablename__ = "review"
    id: Mapped[int] = mapped_column(Integer, Sequence("seq_review_id"), primary_key=True)

    id_translation: Mapped[int] = mapped_column(ForeignKey("translation.id"))

    dt_review: Mapped[datetime] =  mapped_column(DateTime(timezone=True), server_default=func.now())
    rating: Mapped[int]
    state_prev: Mapped[int]
    stability: Mapped[float]
    difficulty: Mapped[float]

    def __repr__(self) -> str:
        return (
            f"Review({self.id}, id_translation={self.id_translation}, " +
            f"dt_review={self.dt_review}, rating={self.rating}, state_prev={self.state_prev}, " +
            f"stability={self.stability}, difficulty={self.difficulty})"
        )

class Translation(Base):
    """Translation table, links words to their translation in another language
    """
    __tablename__ = "translation"
    __table_args__ = (
        UniqueConstraint("id_word_source", "id_word_target"),
    )
    id: Mapped[int] = mapped_column(Integer, Sequence("seq_translation_id"), primary_key=True)

    id_word_source: Mapped[str] = mapped_column(ForeignKey("word.id"))
    id_word_target: Mapped[str] = mapped_column(ForeignKey("word.id"))

    dt_started: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    dt_last_review: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    dt_due: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    rating: Mapped[Optional[int]]
    state: Mapped[Optional[int]]
    step: Mapped[Optional[int]]
    stability: Mapped[Optional[float]]
    difficulty: Mapped[Optional[float]]

    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)

    # Word row with source word
    source_word: Mapped["Word"] = relationship(
        "Word", foreign_keys=[id_word_source], back_populates="translations_as_source"
    )
    # Word row with target word
    target_word: Mapped["Word"] = relationship(
        "Word", foreign_keys=[id_word_target], back_populates="translations_as_target"
    )

    def __repr__(self) -> str:
        return (
            f"Translation(source={self.id_word_source}, target={self.id_word_target}, "
            f"dt_started={self.dt_started}, dt_next_review={self.dt_last_review}, dt_next_review={self.dt_due})"
        )

class Word(Base):
    """Word table, containing all words intended to learn, currently learning or learnt
    """
    __tablename__ = "word"
    __table_args__ = (
        UniqueConstraint("word", "language"),
        Index("ix_id", "id"),
        Index("ix_word", "word"),
    )
    id: Mapped[int] = mapped_column(Integer, Sequence("seq_word_id"), primary_key=True)
    word: Mapped[str]
    language: Mapped[str] = mapped_column(String(2))
    reading: Mapped[Optional[str]]
    definition: Mapped[Optional[str]]

    # Timestamps
    dt_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    dt_updated: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.datetime.now()
    )

    # Translation rows where this word is the source (left side)
    translations_as_source: Mapped[List[Translation]] = relationship(
        "Translation",
        foreign_keys="[Translation.id_word_source]",
        back_populates="source_word",
        cascade="all, delete-orphan",
    )

    # Translation rows where this word is the target (right side)
    translations_as_target: Mapped[List[Translation]] = relationship(
        "Translation",
        foreign_keys="[Translation.id_word_target]",
        back_populates="target_word",
        cascade="all, delete-orphan",
    )

    def add_translation(
        self,
        target,
        # date_review: datetime | None = None
    ) -> Translation:
        """
        Convenience helper: create a Translation from self → target and reverse.
        """
        t = Translation(
            source_word=self,
            target_word=target
        )
        self.translations_as_source.append(t)

        reverse = Translation(
            source_word=target,
            target_word=self
        )
        target.translations_as_source.append(reverse)

        return t

    def __repr__(self) -> str:
        return f"Word({self.id}, {self.word}, language={self.language})"
