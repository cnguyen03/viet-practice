from fastapi import FastAPI
from pydantic import BaseModel

from server.config import HOST, PORT, PROGRESS_JSON_PATH
from server.llm import chat, load_progress
from server.session import SessionState

app = FastAPI(title="viet-practice")

# Phase 1: a single in-memory session shared by localhost curl calls.
# Phase 2+ will key sessions per WebSocket connection instead.
_session = SessionState()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    turn_count: int


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    progress = load_progress(PROGRESS_JSON_PATH)
    reply = chat(_session, req.message, progress)
    return ChatResponse(reply=reply, turn_count=_session.turn_count)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server.main:app", host=HOST, port=PORT, reload=True)
