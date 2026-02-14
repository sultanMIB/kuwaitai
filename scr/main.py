from fastapi import FastAPI, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from routes import baseroutes, data, nlp
from helper.config import get_settings
from stores.LLM.providers.LLMProviderFactory import LLMProviderFactory
from stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from stores.LLM.Templete.templete_parser import TemplateParser
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from utiltis.matrics import setup_metrics

app = FastAPI()

# API Router prefix
api = APIRouter(prefix="/api")
api.include_router(baseroutes.router_base)
api.include_router(data.router_data)
api.include_router(nlp.nlp_router)
app.include_router(api)

setup_metrics(app)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware to hide server information headers
@app.middleware("http")
async def hide_server_headers(request: Request, call_next):
    response = await call_next(request)
    # Remove or override headers that reveal server technology
    response.headers["server"] = ""
    response.headers["x-powered-by"] = ""
    return response

async def startup_span():
    settings = get_settings()

    postgres_conn = (
        f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:"
        f"{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:"
        f"{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    )

    app.db_engine = create_async_engine(postgres_conn)
    app.db_client = sessionmaker(
        app.db_engine, class_=AsyncSession, expire_on_commit=False
    )

    llm_factory = LLMProviderFactory(settings)
    vectordb_factory = VectorDBProviderFactory(settings, app.db_client)

    app.generation_client = llm_factory.create(settings.GENERATION_BACKEND)
    app.generation_client.set_generation_model(settings.GENERATION_MODEL_ID)

    app.embedding_client = llm_factory.create(settings.EMBEDDING_BACKEND)
    app.embedding_client.set_embedding_model(
        settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE
    )

    app.vectordb_client = vectordb_factory.create(settings.VECTOR_DB_BACKEND)
    await app.vectordb_client.connect()

    app.template_parser = TemplateParser(settings.DEFAULT_LANG)

async def shutdown_span():
    await app.db_engine.dispose()
    await app.vectordb_client.disconnect()

app.on_event("startup")(startup_span)
app.on_event("shutdown")(shutdown_span)
