import logging
from contextlib import asynccontextmanager

from chainlit.utils import mount_chainlit
from fastapi import FastAPI, HTTPException

from config import get_settings
from llm.ollama_client import test_ollama_connection
from persistence.chat_store import chat_store

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await chat_store.initialize()
    logger.info("Chat store initialized at %s", settings.chat_db_path)
    yield


app = FastAPI(title="Music AI Chat", version="0.1.0", lifespan=lifespan)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": "Music AI Chat backend is running. Visit /chat for the interface.",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/test-ollama")
async def test_ollama() -> dict[str, str]:
    try:
        response = await test_ollama_connection()
        return {"status": "ok", "model": settings.ollama_model, "response": response}
    except Exception as exc:
        logger.exception("Ollama test failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/threads")
async def list_threads() -> dict:
    threads = await chat_store.list_threads()
    return {"threads": threads}


mount_chainlit(
    app=app,
    target="chainlit_app.py",
    path="/chat",
)