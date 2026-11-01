from pathlib import Path

from .client import api_key, get_client


def transcribe_audio(uploaded_file):
    if not api_key():
        raise RuntimeError("Add OPENAI_API_KEY to your .env file to enable audio transcription.")
    client = get_client()
    suffix = Path(uploaded_file.name).suffix or ".wav"
    temp_path = Path(f"temp_voice_note{suffix}")
    try:
        temp_path.write_bytes(uploaded_file.getvalue())
        with temp_path.open("rb") as audio:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=audio)
        return transcript.text
    finally:
        if temp_path.exists():
            temp_path.unlink()
