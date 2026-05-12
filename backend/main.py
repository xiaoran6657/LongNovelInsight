from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    from db import init_db

    init_db()
    yield


app = FastAPI(title="LongNovelInsight", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers import documents, health, model_providers, parse, topics  # noqa: E402

app.include_router(health.router, prefix="/api")
app.include_router(topics.router, prefix="/api")
app.include_router(model_providers.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(parse.router, prefix="/api")
