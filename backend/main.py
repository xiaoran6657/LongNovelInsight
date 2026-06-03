from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    from db import init_db

    init_db()
    yield


app = FastAPI(title="LongNovelInsight", version="0.2.0-dev", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers import (  # noqa: E402
    analysis_jobs,
    analysis_outputs,
    analysis_runs,
    chat,
    cross_work,
    documents,
    entities,
    health,
    model_providers,
    parse,
    provider_presets,
    retrieve,
    search,
    topic_provider_config,
    topics,
    works,
)

app.include_router(health.router, prefix="/api")
app.include_router(topics.router, prefix="/api")
app.include_router(model_providers.router, prefix="/api")
app.include_router(provider_presets.router, prefix="/api")
app.include_router(topic_provider_config.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(parse.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(retrieve.router, prefix="/api")
app.include_router(entities.router, prefix="/api")
app.include_router(analysis_jobs.topic_router, prefix="/api")
app.include_router(analysis_jobs.job_router, prefix="/api")
app.include_router(analysis_outputs.router, prefix="/api")
app.include_router(chat.topic_router, prefix="/api")
app.include_router(chat.session_router, prefix="/api")
app.include_router(analysis_runs.topic_router, prefix="/api")
app.include_router(analysis_runs.run_router, prefix="/api")
app.include_router(works.topic_router, prefix="/api")
app.include_router(works.work_router, prefix="/api")
app.include_router(works.doc_router, prefix="/api")
app.include_router(cross_work.router, prefix="/api")
