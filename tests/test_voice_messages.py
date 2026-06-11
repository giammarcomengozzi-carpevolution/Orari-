from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from orari_agent.ai_agent import AiHandleResult
from orari_agent.bot import commands
from orari_agent.storage.db import connect
from orari_agent.storage.voice_transcripts_repository import VoiceTranscriptsRepository
from orari_agent.voice import (
    AudioTranscriptionError,
    MAX_AUDIO_FILE_BYTES,
    OpenAiUnavailableError,
)


class FakeTelegramFile:
    def __init__(self, content: bytes):
        self.content = content
        self.downloads: list[Path] = []

    async def download_to_drive(self, custom_path):
        path = Path(custom_path)
        path.write_bytes(self.content)
        self.downloads.append(path)


class FakeAttachment:
    def __init__(
        self,
        content: bytes = b"audio",
        *,
        file_size: int | None = None,
        file_name: str | None = None,
        mime_type: str | None = None,
        file_unique_id: str = "unique",
    ):
        self.file_size = len(content) if file_size is None else file_size
        self.file_name = file_name
        self.mime_type = mime_type
        self.file_unique_id = file_unique_id
        self.telegram_file = FakeTelegramFile(content)

    async def get_file(self):
        return self.telegram_file


class FakeMessage:
    def __init__(self, *, voice=None, audio=None, document=None):
        self.text = ""
        self.voice = voice
        self.audio = audio
        self.document = document
        self.photo = []
        self.caption = ""
        self.replies: list[str] = []
        self.documents = []

    async def reply_text(self, text: str, **kwargs):
        self.replies.append(text)

    async def reply_document(self, **kwargs):
        self.documents.append(kwargs)


class FakeUser:
    id = 123


class FakeUpdate:
    def __init__(self, message: FakeMessage):
        self.effective_message = message
        self.effective_user = FakeUser()


class FakeTranscriber:
    def __init__(self, transcript: str, fail: bool = False, unavailable: bool = False):
        self.transcript = transcript
        self.fail = fail
        self.unavailable = unavailable
        self.paths: list[Path] = []

    def transcribe(self, audio_path: Path) -> str:
        self.paths.append(audio_path)
        if self.unavailable:
            raise OpenAiUnavailableError("auth")
        if self.fail:
            raise AudioTranscriptionError("boom")
        return self.transcript


class FakeAiAgent:
    configured = True

    def __init__(self):
        self.calls: list[tuple[int, str]] = []

    def handle_message(self, user_id: int, text: str):
        self.calls.append((user_id, text))
        return AiHandleResult("Ho interpretato:\n- vincolo salvato")


def _context(
    tmp_path, *, transcriber, repository=None, voice_debug=False, ai_agent=None
):
    bot_data = {
        "allowed_user_id": 123,
        "notes_repository": object(),
        "schedule_service": object(),
        "wife_calendar_repository": object(),
        "operational_memory_repository": object(),
        "audio_transcriber": transcriber,
        "audio_dir": tmp_path / "audio",
        "voice_debug": voice_debug,
        "ai_agent": ai_agent or FakeAiAgent(),
    }
    if repository is not None:
        bot_data["voice_transcripts_repository"] = repository
    return SimpleNamespace(
        application=SimpleNamespace(bot_data=bot_data), args=[], user_data={}
    )


def test_voice_note_downloads_transcribes_stores_routes_and_cleans_up(tmp_path):
    connection = connect(tmp_path / "orari.sqlite3")
    repository = VoiceTranscriptsRepository(connection)
    ai_agent = FakeAiAgent()
    transcriber = FakeTranscriber("Settimana prossima giovedì commercialista 10 12")
    voice = FakeAttachment(content=b"ogg-data", mime_type="audio/ogg")
    update = FakeUpdate(FakeMessage(voice=voice))

    asyncio.run(
        commands.voice_message(
            update,
            _context(
                tmp_path,
                transcriber=transcriber,
                repository=repository,
                ai_agent=ai_agent,
            ),
        )
    )

    assert voice.telegram_file.downloads
    assert transcriber.paths
    assert not transcriber.paths[0].exists()
    assert repository.latest_for_user(123).transcript.startswith("Settimana prossima")
    assert ai_agent.calls == [(123, "Settimana prossima giovedì commercialista 10 12")]
    assert update.effective_message.replies[0].startswith("🎤 Trascrizione:")
    assert "🤖 Interpretazione:" in update.effective_message.replies[0]


def test_audio_file_downloads_correctly(tmp_path):
    connection = connect(tmp_path / "orari.sqlite3")
    repository = VoiceTranscriptsRepository(connection)
    audio = FakeAttachment(content=b"mp3", file_name="nota.mp3", mime_type="audio/mpeg")
    transcriber = FakeTranscriber("Lorenzo esce sabato alle 15")
    update = FakeUpdate(FakeMessage(audio=audio))

    asyncio.run(
        commands.voice_message(
            update, _context(tmp_path, transcriber=transcriber, repository=repository)
        )
    )

    assert audio.telegram_file.downloads[0].suffix == ".mp3"
    assert repository.latest_for_user(123).transcript == "Lorenzo esce sabato alle 15"


def test_document_with_audio_mime_type_is_supported_in_debug_mode(tmp_path):
    connection = connect(tmp_path / "orari.sqlite3")
    repository = VoiceTranscriptsRepository(connection)
    document = FakeAttachment(
        content=b"wav", file_name="registrazione", mime_type="audio/wav"
    )
    transcriber = FakeTranscriber("Angelo non c'è venerdì")
    update = FakeUpdate(FakeMessage(document=document))

    asyncio.run(
        commands.voice_message(
            update,
            _context(
                tmp_path,
                transcriber=transcriber,
                repository=repository,
                voice_debug=True,
            ),
        )
    )

    assert transcriber.paths[0].suffix == ".wav"
    assert transcriber.paths[0].exists()
    assert (
        transcriber.paths[0].with_suffix(".wav.txt").read_text()
        == "Angelo non c'è venerdì"
    )


def test_missing_api_key_handled(tmp_path):
    update = FakeUpdate(FakeMessage(voice=FakeAttachment()))

    asyncio.run(commands.voice_message(update, _context(tmp_path, transcriber=None)))

    assert update.effective_message.replies == [
        "Trascrizione non disponibile: controlla OPENAI_API_KEY."
    ]


def test_large_file_handled_before_download(tmp_path):
    update = FakeUpdate(
        FakeMessage(voice=FakeAttachment(file_size=MAX_AUDIO_FILE_BYTES + 1))
    )

    asyncio.run(
        commands.voice_message(
            update, _context(tmp_path, transcriber=FakeTranscriber("x"))
        )
    )

    assert update.effective_message.replies == ["Messaggio vocale troppo grande."]


def test_openai_unavailable_message(tmp_path):
    update = FakeUpdate(FakeMessage(voice=FakeAttachment()))

    asyncio.run(
        commands.voice_message(
            update,
            _context(tmp_path, transcriber=FakeTranscriber("", unavailable=True)),
        )
    )

    assert update.effective_message.replies == [
        "Trascrizione non disponibile: controlla OPENAI_API_KEY."
    ]


def test_transcription_failure_message(tmp_path):
    update = FakeUpdate(FakeMessage(voice=FakeAttachment()))

    asyncio.run(
        commands.voice_message(
            update,
            _context(tmp_path, transcriber=FakeTranscriber("", fail=True)),
        )
    )

    assert update.effective_message.replies == [
        "Non sono riuscito a trascrivere il messaggio vocale."
    ]


def test_trascrivi_ultimo_shows_last_transcript(tmp_path):
    connection = connect(tmp_path / "orari.sqlite3")
    repository = VoiceTranscriptsRepository(connection)
    repository.add("a.ogg", "prima", 123)
    repository.add("b.ogg", "seconda", 123)
    update = FakeUpdate(FakeMessage())

    asyncio.run(
        commands.trascrivi_ultimo(
            update, _context(tmp_path, transcriber=None, repository=repository)
        )
    )

    assert "🎤 Ultima trascrizione:" in update.effective_message.replies[0]
    assert "seconda" in update.effective_message.replies[0]
    assert "b.ogg" in update.effective_message.replies[0]


def test_long_transcript_is_truncated_in_reply_but_stored_full(tmp_path):
    connection = connect(tmp_path / "orari.sqlite3")
    repository = VoiceTranscriptsRepository(connection)
    long_transcript = "a" * 1005
    update = FakeUpdate(FakeMessage(voice=FakeAttachment()))

    asyncio.run(
        commands.voice_message(
            update,
            _context(
                tmp_path,
                transcriber=FakeTranscriber(long_transcript),
                repository=repository,
            ),
        )
    )

    assert (
        "Trascrizione completa salvata internamente"
        in update.effective_message.replies[0]
    )
    assert repository.latest_for_user(123).transcript == long_transcript
