# viet-practice

A fully local, offline Vietnamese speaking-practice agent. Runs entirely on your laptop — a local LLM (Ollama), speech-to-text, and text-to-speech — so it works with zero internet or cellular connection, e.g. practicing on a bus or in a car. Your phone connects over a Wi-Fi network the laptop itself broadcasts.

Vocabulary and progress are grounded in your real Duolingo data, synced to a local JSON file (`data/vietnamese_progress.json`, gitignored — see `data/vietnamese_progress.example.json` for the shape) whenever you have internet, ahead of a trip.

## Status

Build follows a phased plan (see project history / plan doc):
1. ✅ Core loop: text-only `/chat` endpoint against Ollama, grounded in the local progress JSON.
2. Phone-accessible web client over a laptop-hosted hotspot.
3. Speech-to-text (faster-whisper).
4. Text-to-speech (Piper) + turn-cap / correction-loop session logic.
5. Duolingo sync script.

## Setup

```bash
uv sync
brew services start ollama   # if not already running
ollama pull qwen2.5:7b-instruct
```

## Run (Phase 1)

```bash
uv run uvicorn server.main:app --host 127.0.0.1 --port 8000
```

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Xin chào"}'
```

## Duolingo sync (Phase 5)

Copy `.env.example` to `.env` and fill in your Duolingo credentials (never committed). Run the sync script while on wifi, before a trip:

```bash
uv run scripts/sync_duolingo.py
```
