from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi.responses import Response

from app.api.dependencies import get_demo_context, get_demo_store_id
from app.core.database import get_db
from app.integrations.gemini import GeminiError
from app.integrations.prisma import PrismaError, transcribe_audio
from app.integrations.timbre import TimbreError, synthesize_speech
from app.schemas.voice import VoiceProcessResponse
from app.services.voice_orchestration_service import process_text_request, process_voice_request

router = APIRouter(prefix="/voice", tags=["Voice"])

MAX_AUDIO_SIZE = 15 * 1024 * 1024

ALLOWED_CONTENT_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/vnd.wave",
    "audio/mpeg",
    "audio/mp3",
    "audio/x-mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/aac",
    "audio/webm",
    "audio/ogg",
    "audio/flac",
    "audio/x-flac",
    "audio/3gpp",
    "application/octet-stream",
}


class TextProcessRequest(BaseModel):
    text: str
    conversation_id: UUID | None = None


class TranscriptionResponse(BaseModel):
    transcript: str
    detected_language: str | None = None
    request_id: str | None = None
    provider: str


async def read_valid_audio(audio: UploadFile) -> tuple[bytes, str]:
    raw_content_type = audio.content_type or ""
    content_type = raw_content_type.split(";", 1)[0].strip().lower()

    audio_extensions = {
        ".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac",
        ".webm", ".aiff", ".aif", ".wma", ".3gp", ".amr", ".opus", ".mp4"
    }
    filename = (audio.filename or "").lower()
    has_audio_ext = any(filename.endswith(ext) for ext in audio_extensions)
    is_audio_mime = (
        content_type.startswith("audio/")
        or content_type in ALLOWED_CONTENT_TYPES
        or content_type == "application/octet-stream"
    )

    if not (is_audio_mime or has_audio_ext):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio format: {raw_content_type or 'unknown'}",
        )

    audio_bytes = await audio.read(MAX_AUDIO_SIZE + 1)

    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file is empty.",
        )

    if len(audio_bytes) > MAX_AUDIO_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file exceeds the 15 MB limit.",
        )

    return audio_bytes, content_type


@router.post(
    "/transcribe",
    response_model=TranscriptionResponse,
)
async def transcribe(
    audio: UploadFile = File(...),
    store_id=Depends(get_demo_store_id),
    db: AsyncSession = Depends(get_db),
):
    del store_id, db

    audio_bytes, content_type = await read_valid_audio(audio)

    try:
        return await transcribe_audio(
            audio_bytes=audio_bytes,
            filename=audio.filename or "recording.wav",
            content_type=content_type,
        )
    except PrismaError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post(
    "/process",
    response_model=VoiceProcessResponse,
)
async def process_voice(
    audio: UploadFile = File(...),
    conversation_id: UUID | None = Form(default=None),
    context=Depends(get_demo_context),
    db: AsyncSession = Depends(get_db),
):
    store_id, user_id = context

    audio_bytes, content_type = await read_valid_audio(audio)

    try:
        return await process_voice_request(
            db=db,
            store_id=store_id,
            user_id=user_id,
            audio_bytes=audio_bytes,
            filename=audio.filename or "recording.wav",
            content_type=content_type,
            conversation_id=conversation_id,
        )
    except PrismaError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except GeminiError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

@router.post("/process-text", response_model=VoiceProcessResponse)
async def process_text(
    request: TextProcessRequest,
    context=Depends(get_demo_context),
    db: AsyncSession = Depends(get_db),
):
    store_id, user_id = context

    try:
        return await process_text_request(
            db=db,
            store_id=store_id,
            user_id=user_id,
            text=request.text,
            conversation_id=request.conversation_id,
        )
    except GeminiError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


class SpeakRequest(BaseModel):
    text: str
    language: str | None = "hi"
    voice: str | None = "Devansh"


@router.post("/speak")
async def speak_text(request: SpeakRequest):
    """Synthesize voice response audio via Gnani Timbre v3.0."""
    try:
        lang_code = (
            "hi-IN" if (request.language or "").startswith("hi") else "en-IN"
        )
        wav_bytes = await synthesize_speech(
            text=request.text,
            language_code=lang_code,
            voice=request.voice or "Devansh",
        )
        return Response(content=wav_bytes, media_type="audio/wav")
    except TimbreError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


