import re
import subprocess
import tempfile
from pathlib import Path

from server.config import TTS_RATE_WPM, TTS_VOICE

# The reply may carry a short English gloss in parentheses. A Vietnamese voice
# mangles English, so those asides are shown on screen but not spoken.
_PARENTHETICAL = re.compile(r"\([^)]*\)")


def speakable(text: str) -> str:
    return re.sub(r"\s{2,}", " ", _PARENTHETICAL.sub("", text)).strip()


def synthesize(text: str) -> bytes:
    """Render Vietnamese text to WAV bytes using the macOS voice."""
    spoken = speakable(text)
    if not spoken:
        return b""

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "reply.wav"
        subprocess.run(
            [
                "say",
                "-v", TTS_VOICE,
                "-r", str(TTS_RATE_WPM),
                "--file-format=WAVE",
                "--data-format=LEI16@22050",
                "-o", str(out),
                spoken,
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return out.read_bytes()
