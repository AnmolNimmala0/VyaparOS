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

from app.api.dependencies import get_demo_context, get_demo_store_id
from app.core.database import get_db
from app.integrations.gemini import GeminiError
from app.integrations.prisma import PrismaError, transcribe_audio
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

    print("DEBUG AUDIO CONTENT TYPE:", repr(raw_content_type))
    print("DEBUG NORMALIZED CONTENT TYPE:", repr(content_type))

    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio format: {raw_content_type}",
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

