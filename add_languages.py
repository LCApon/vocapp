from sqlalchemy import select, text

from database.session import SessionLocal
from database.model import Language
from config import settings

with SessionLocal() as db:
    db.execute(text(f"ALTER DATABASE {settings.dbNamer} SET timezone TO 'UTC';"))

    if not db.execute(select(Language)).all():
        langNl = Language(
            iso639="nl",
            language="Dutch",
            emoji="🇳🇱"
        )
        langJp = Language(
            iso639="jp",
            language="Japanese",
            emoji="🇯🇵"
        )
        langVi = Language(
            iso639="vi",
            language="Vietnamese",
            emoji="🇻🇳"
        )
        langZh = Language(
            iso639="zh",
            language="Chinese",
            emoji="🇨🇳"
        )

        db.add(langNl)
        db.add(langJp)
        db.add(langVi)
        db.add(langZh)
    
    db.commit()
