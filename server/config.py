import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Gemma-based, with continued pre-training across Southeast Asian languages.
# Chosen over qwen2.5:7b and gemma3:12b after benchmarking all three on real
# failures from practice sessions: it writes the most idiomatic Vietnamese,
# teaches whole sentences rather than fragments, and keeps feedback in English.
# Override to try another without editing code: VP_MODEL=gemma3:12b …
OLLAMA_MODEL = os.environ.get(
    "VP_MODEL", "hf.co/aisingapore/Gemma-SEA-LION-v3-9B-IT-GGUF:Q4_K_M"
)
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

# macOS ships a Vietnamese voice, so no extra TTS model is needed. Check with:
#   say -v '?' | grep vi_VN
TTS_VOICE = "Linh"
TTS_RATE_WPM = 160  # a little under the 180 default — easier for a learner
