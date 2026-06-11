"""Supporto per download e trascrizione audio Telegram."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

SUPPORTED_AUDIO_EXTENSIONS = {".ogg", ".mp3", ".m4a", ".wav"}
SUPPORTED_AUDIO_MIME_TYPES = {
    "audio/ogg",
    "audio/oga",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
}
MAX_AUDIO_FILE_BYTES = 25 * 1024 * 1024
DEFAULT_TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"


class AudioTooLargeError(ValueError):
    """Audio oltre il limite accettato dalla pipeline di trascrizione."""


class MissingOpenAiApiKeyError(RuntimeError):
    """OPENAI_API_KEY non configurata per speech-to-text."""


class OpenAiUnavailableError(RuntimeError):
    """OpenAI non è raggiungibile o la chiave non è valida."""


class AudioTranscriptionError(RuntimeError):
    """Errore generico durante la trascrizione."""


class AudioTranscriber(Protocol):
    def transcribe(self, audio_path: Path) -> str:
        """Trascrive il file audio e ritorna testo plain."""


class OpenAiAudioTranscriber:
    """Wrapper dell'SDK OpenAI per audio transcriptions, mockabile nei test."""

    def __init__(
        self, api_key: str | None, model: str = DEFAULT_TRANSCRIPTION_MODEL
    ) -> None:
        if not api_key:
            raise MissingOpenAiApiKeyError("OPENAI_API_KEY mancante")
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def transcribe(self, audio_path: Path) -> str:
        try:
            with audio_path.open("rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                )
        except Exception as exc:  # noqa: BLE001 - errore esterno da normalizzare
            if _is_openai_unavailable_error(exc):
                raise OpenAiUnavailableError(str(exc)) from exc
            raise AudioTranscriptionError(str(exc)) from exc

        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
        if isinstance(response, str) and response.strip():
            return response.strip()
        raise AudioTranscriptionError("Risposta OpenAI senza testo trascritto")


def validate_audio_size(file_size: int | None) -> None:
    if file_size is not None and file_size > MAX_AUDIO_FILE_BYTES:
        raise AudioTooLargeError("Messaggio vocale troppo grande")


def supported_audio_extension(file_name: str) -> bool:
    return Path(file_name).suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS


def supported_audio_mime_type(mime_type: str | None) -> bool:
    if not mime_type:
        return False
    return mime_type.lower().split(";", 1)[0].strip() in SUPPORTED_AUDIO_MIME_TYPES


def _is_openai_unavailable_error(exc: Exception) -> bool:
    error_name = exc.__class__.__name__.lower()
    return any(
        token in error_name
        for token in (
            "authentication",
            "permission",
            "apierror",
            "apiconnection",
            "apitimeout",
            "ratelimit",
        )
    )
