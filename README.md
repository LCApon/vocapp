# Vocapp

A simple language learning app for personal use, at the moment only for vocabulary. Includes word lookup, so functions as a dictionary as well.

Makes use of:
- `SQLAlchemy` for the database setup (including `alembic`)
- `FastAPI` for the routing of requests from the static webpage
- `Pydantic` for type validations and config (`Pydantic-settings`)
- `py-fsrs` for the spaced repetition implementation
