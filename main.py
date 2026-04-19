from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from database.model import Base
from database.session import engine
from api.route import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # at startup
    Base.metadata.create_all(engine)

    yield    
    # at shutdown
    engine.dispose()


vocapp = FastAPI(
    title="VocabSRS Server",
    description="Self-hosted Language Learning App",
    version="0.0.1",
    lifespan=lifespan
)

vocapp.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # allow_origins=["http://localhost:8000", "vocab_app_simple.html:1"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Basic setups
@vocapp.get("/")
async def root():
    return {"status": "OK", "message": "Vocabulary API is running. PWA Ready."}

vocapp.include_router(router, prefix="/api")
