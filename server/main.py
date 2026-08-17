from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from server import session as session_store
from server.config import HOST, MAX_TURNS_PER_TOPIC, PORT, PROGRESS_JSON_PATH, STATIC_DIR
from server.llm import chat, load_progress
from server.net import startup_banner


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(startup_banner(PORT), flush=True)
    yield


app = FastAPI(title="viet-practice", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    turn_count: int
    max_turns: int
    topic_complete: bool


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    session_id, state = session_store.get_or_create(req.session_id)
    progress = load_progress(PROGRESS_JSON_PATH)
    reply = chat(state, req.message, progress)
    return ChatResponse(
        reply=reply,
        session_id=session_id,
        turn_count=state.turn_count,
        max_turns=MAX_TURNS_PER_TOPIC,
        topic_complete=state.should_wrap_up(),
    )


@app.post("/session/reset")
def reset_session(req: ChatRequest):
    """Clear history so the next message starts a fresh topic."""
    session_id, state = session_store.get_or_create(req.session_id)
    state.reset_topic()
    return {"session_id": session_id, "turn_count": state.turn_count}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server.main:app", host=HOST, port=PORT)
