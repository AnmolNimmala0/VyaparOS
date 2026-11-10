import io
import wave
import httpx

from app.core.config import settings


class TimbreError(Exception):
    """Raised when Timbre TTS synthesis fails."""


TIMBRE_INFERENCE_URL = "https://api.vachana.ai/api/v1/tts/inference"


def pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 24000) -> bytes:
    """Wrap raw 16-bit mono linear PCM bytes into standard WAV container."""
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return wav_io.getvalue()


async def synthesize_speech(
    text: str,
    language_code: str = "hi-IN",
    voice: str = "Devansh",
) -> bytes:
    """
    Synthesize speech audio from text using Gnani Timbre v3.0.

    Supported voices include: Devansh, Shivani, Avinash, Lakshmi, Kalpana.
    Returns standard WAV audio bytes.
    """
    api_key = settings.TIMBRE_API_KEY or settings.GNANI_API_KEY
    if not api_key:
        raise TimbreError("Gnani API key is not configured for Timbre TTS.")

    lang = "hi-IN" if language_code.startswith("hi") else "en-IN"

    headers = {
        "X-API-Key-ID": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "model": "timbre-v3.0",
        "text": text,
        "voice": voice,
        "language_code": lang,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            TIMBRE_INFERENCE_URL,
            headers=headers,
            json=payload,
        )

    if response.status_code != 200:
        raise TimbreError(
            f"Timbre returned HTTP {response.status_code}: {response.text[:200]}"
        )

    return pcm_to_wav(response.content, sample_rate=24000)
