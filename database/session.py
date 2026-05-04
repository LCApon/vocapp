from database.model import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from typing import Generator

from config import settings

# Engine
engine = create_engine(
    settings.urlDatabase,
    echo=settings.envApp == "development",
)

# Session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    Base.metadata.create_all(engine)
