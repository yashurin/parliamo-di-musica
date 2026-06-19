from contextlib import asynccontextmanager

from chainlit.utils import mount_chainlit
from fastapi import FastAPI, HTTPException

from api.auth_routes import router as auth_router
from config import get_settings
from llm.ollama_client import test_ollama_connection
from logging_config import get_logger, setup_logging
from persistence.chat_store import chat_store
from persistence.redis_client import close_redis, ping_redis
from persistence.redis_store import redis_store

settings = get_settings()
setup_logging(level=settings.log_level, log_file=settings.log_file or None)
logger = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await chat_store.initialize()
    memory = await redis_store.get_memory_info()
    logger.info(
        "Application started (Redis memory: %s)",
        memory.get("used_memory_human", "unknown"),
    )
    yield
    await close_redis()
    logger.info("Application shutdown complete")


app = FastAPI(title="Music AI Chat", version="0.2.0", lifespan=lifespan)
app.include_router(auth_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": "Music AI Chat backend is running. Visit /chat for the interface.",
    }


@app.get("/health")
async def health() -> dict[str, str | bool]:
    redis_ok = await ping_redis()
    status = "ok" if redis_ok else "degraded"
    return {"status": status, "redis": redis_ok}


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