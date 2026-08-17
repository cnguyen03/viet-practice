from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

OLLAMA_MODEL = "qwen2.5:7b-instruct"
OLLAMA_HOST = "http://localhost:11434"

PROGRESS_JSON_PATH = PROJECT_ROOT / "data" / "vietnamese_progress.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Serving HTTPS is what lets the phone use its microphone: getUserMedia is
# gated on a secure context, and a plain-http LAN address doesn't qualify.
CERT_FILE = PROJECT_ROOT / "certs" / "cert.pem"
KEY_FILE = PROJECT_ROOT / "certs" / "key.pem"


def tls_available() -> bool:
    return CERT_FILE.exists() and KEY_FILE.exists()

HOST = "0.0.0.0"
PORT = 8000

MAX_TURNS_PER_TOPIC = 10

WHISPER_MODEL_SIZE = "small"
WHISPER_DOWNLOAD_DIR = PROJECT_ROOT / "models" / "whisper"
WHISPER_COMPUTE_TYPE = "int8"  # fast on Apple Silicon CPU; float16 needs CUDA
SPOKEN_LANGUAGE = "vi"

# Populated in Phase 4:
PIPER_VOICE = "vi_VN-vais1000-medium"
