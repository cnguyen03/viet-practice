import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from server import session as session_store
from server.config import (
    CERT_FILE,
    HOST,
    KEY_FILE,
    MAX_TURNS_PER_TOPIC,
    PORT,
    PROGRESS_JSON_PATH,
    STATIC_DIR,
    tls_available,
)
from server.llm import chat, load_progress
from server.net import startup_banner
from server.stt import get_model, transcribe
from server.tts import synthesize


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load Whisper up front so the first spoken turn isn't 15s slower than the rest.
    await asyncio.to_thread(get_model)
    print(startup_banner(PORT, tls_available()), flush=True)
    yield


app = FastAPI(title="viet-practice", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    reply_en: str = ""
    feedback: str = ""
    correction: str = ""
    assessment: str = "good"
    session_id: str
    turn_count: int
    max_turns: int
    topic_complete: bool


class VoiceResponse(ChatResponse):
    transcript: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    session_id, state = session_store.get_or_create(req.session_id)
    progress = load_progress(PROGRESS_JSON_PATH)
    result = chat(state, req.message, progress)
    return ChatResponse(
        **result,
        session_id=session_id,
        turn_count=state.turn_count,
        max_turns=MAX_TURNS_PER_TOPIC,
        topic_complete=state.should_wrap_up(),
    )


@app.post("/voice", response_model=VoiceResponse)
async def voice_endpoint(
    audio: UploadFile = File(...),
    session_id: str | None = Form(None),
):
    """Spoken turn: transcribe the recording, then answer it.

    Transcript comes back alongside the reply so the user can see what was
    actually heard — important when a misheard word is what derailed the answer.
    """
    raw = await audio.read()
    transcript = await asyncio.to_thread(transcribe, raw)

    sid, state = session_store.get_or_create(session_id)
    if not transcript:
        return VoiceResponse(
            transcript="",
            reply="Mình chưa nghe rõ. Bạn nói lại được không?",
            session_id=sid,
            turn_count=state.turn_count,
            max_turns=MAX_TURNS_PER_TOPIC,
            topic_complete=state.should_wrap_up(),
        )

    progress = load_progress(PROGRESS_JSON_PATH)
    result = await asyncio.to_thread(chat, state, transcript, progress)
    return VoiceResponse(
        **result,
        transcript=transcript,
        session_id=sid,
        turn_count=state.turn_count,
        max_turns=MAX_TURNS_PER_TOPIC,
        topic_complete=state.should_wrap_up(),
    )


class SpeakRequest(BaseModel):
    text: str


@app.post("/speak")
async def speak_endpoint(req: SpeakRequest):
    """Render a reply to speech. Kept separate from /chat so the text can
    appear immediately, and so a line can be replayed without re-asking."""
    wav = await asyncio.to_thread(synthesize, req.text)
    return Response(content=wav, media_type="audio/wav")


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

    ssl = (
        {"ssl_certfile": str(CERT_FILE), "ssl_keyfile": str(KEY_FILE)}
        if tls_available()
        else {}
    )
    uvicorn.run("server.main:app", host=HOST, port=PORT, **ssl)
