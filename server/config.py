from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

OLLAMA_MODEL = "qwen2.5:7b-instruct"
OLLAMA_HOST = "http://localhost:11434"

PROGRESS_JSON_PATH = PROJECT_ROOT / "data" / "vietnamese_progress.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"

HOST = "0.0.0.0"
PORT = 8000

MAX_TURNS_PER_TOPIC = 10

# Populated in later phases:
WHISPER_MODEL_SIZE = "small"
PIPER_VOICE = "vi_VN-vais1000-medium"
