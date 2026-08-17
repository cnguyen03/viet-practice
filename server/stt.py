import io

from faster_whisper import WhisperModel

from server.config import (
    SPOKEN_LANGUAGE,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DOWNLOAD_DIR,
    WHISPER_MODEL_SIZE,
)

_model: WhisperModel | None = None


def get_model() -> WhisperModel:
    """Load the model once and keep it resident — loading costs seconds."""
    global _model
    if _model is None:
        _model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type=WHISPER_COMPUTE_TYPE,
            download_root=str(WHISPER_DOWNLOAD_DIR),
        )
    return _model


def transcribe(audio: bytes) -> str:
    """Transcribe recorded speech. Accepts any container PyAV can decode
    (webm/opus from Chrome, mp4/aac from Safari, wav)."""
    segments, _info = get_model().transcribe(
        io.BytesIO(audio),
        language=SPOKEN_LANGUAGE,
        # Drops silence before it reaches the model, which both speeds things up
        # and avoids Whisper hallucinating words into empty audio.
        vad_filter=True,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()
