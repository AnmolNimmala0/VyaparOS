import asyncio

import httpx

from app.core.config import settings


class PrismaError(Exception):
    """Raised when the Prisma transcription service fails."""


async def convert_to_wav(audio_bytes: bytes) -> bytes:
    """Convert browser-recorded audio into 16 kHz mono PCM WAV with audio normalization."""

    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-i", "pipe:0",
        "-ar", "16000",
        "-ac", "1",
        "-af", "dynaudnorm",
        "-c:a", "pcm_s16le",
        "-f", "wav",
        "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate(input=audio_bytes)

    if process.returncode != 0:
        print("FFMPEG ERROR:", stderr.decode(errors="replace")[:1000])
        raise PrismaError("Could not convert recorded audio to WAV.")

    if not stdout:
        raise PrismaError("FFmpeg returned an empty WAV file.")

    return stdout


async def transcribe_audio(
    audio_bytes: bytes,
    filename: str,
    content_type: str,
) -> dict:

    if not settings.GNANI_API_KEY:
        raise PrismaError("Gnani API key is not configured.")

    if not audio_bytes:
        raise PrismaError("Received an empty audio file.")

    print("ORIGINAL AUDIO FORMAT:", content_type)
    print("ORIGINAL AUDIO SIZE:", len(audio_bytes))

    # Convert browser audio to Prisma-compatible WAV.
    audio_bytes = await convert_to_wav(audio_bytes)

    print("CONVERTED AUDIO FORMAT: audio/wav")
    print("CONVERTED AUDIO SIZE:", len(audio_bytes))

    files = {
        "audio_file": (
            "recording.wav",
            audio_bytes,
            "audio/wav",
        )
    }

    data = {
        "model": settings.PRISMA_MODEL,
        "language_code": "indic-auto",
        "format": "codemix",
        "keywords": "stock, rate, packet, packets, maggi, noodles, inventory, udhaar, cash, upi, customer, balance, bikri, vasooli, khata",
    }

    headers = {
        "X-API-Key-ID": settings.GNANI_API_KEY,
    }

    timeout = httpx.Timeout(60.0, connect=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                settings.PRISMA_BASE_URL,
                headers=headers,
                data=data,
                files=files,
            )

        response.raise_for_status()
        result = response.json()

        # If indic-auto produced empty transcript, retry with hi-IN
        transcript = result.get("transcript")
        if not transcript or not transcript.strip():
            retry_files = {
                "audio_file": (
                    "recording.wav",
                    audio_bytes,
                    "audio/wav",
                )
            }
            retry_data = {
                "model": settings.PRISMA_MODEL,
                "language_code": "hi-IN",
                "format": "codemix",
                "keywords": data["keywords"],
            }
            async with httpx.AsyncClient(timeout=timeout) as client:
                retry_response = await client.post(
                    settings.PRISMA_BASE_URL,
                    headers=headers,
                    data=retry_data,
                    files=retry_files,
                )
            if retry_response.is_success:
                retry_json = retry_response.json()
                if retry_json.get("transcript"):
                    result = retry_json

    except httpx.TimeoutException as exc:
        raise PrismaError("Prisma transcription timed out.") from exc

    except httpx.HTTPStatusError as exc:
        print("PRISMA ERROR STATUS:", exc.response.status_code)
        print("PRISMA ERROR BODY:", exc.response.text[:1500])

        raise PrismaError(
            f"Prisma returned HTTP {exc.response.status_code}."
        ) from exc

    except httpx.RequestError as exc:
        print("PRISMA CONNECTION ERROR:", str(exc))
        raise PrismaError("Could not connect to Prisma.") from exc

    except ValueError as exc:
        raise PrismaError("Prisma returned an invalid JSON response.") from exc

    transcript = result.get("transcript")

    if not isinstance(transcript, str):
        print("PRISMA INVALID RESPONSE:", str(result)[:1000])
        raise PrismaError("Prisma response did not contain a transcript.")

    return {
        "transcript": transcript,
        "detected_language": result.get("detected_language_code"),
        "request_id": result.get("request_id"),
        "provider": "gnani-prisma-v3",
    }
