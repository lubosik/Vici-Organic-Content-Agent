"""ElevenLabs TTS wrapper."""

import os
import re
import requests
from pathlib import Path

VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
API_KEY = lambda: os.getenv("ELEVENLABS_API_KEY")

PRONUNCIATIONS = {
    r'\btirzepatide\b': 'tir-ZEP-a-tide',
    r'\bsemaglutide\b': 'SEM-ah-gloo-tide',
    r'\bretatrutide\b': 'ret-ah-TROO-tide',
    r'\btesamorelin\b': 'tess-am-oh-REL-in',
    r'\bGHK-Cu\b': 'G-H-K copper',
    r'\bHPLC\b': 'H-P-L-C',
    r'\bCoA\b': 'C-O-A',
}


def fix_pronunciations(text: str) -> str:
    for pattern, replacement in PRONUNCIATIONS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def generate_voiceover(script: str, output_path: str) -> bool:
    corrected = fix_pronunciations(script)
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": API_KEY(),
    }
    payload = {
        "text": corrected,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.75,
            "similarity_boost": 0.85,
            "style": 0.10,
            "use_speaker_boost": True,
        },
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        r.raise_for_status()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f"ElevenLabs REST error: {e}")
        try:
            from elevenlabs.client import ElevenLabs
            client = ElevenLabs(api_key=API_KEY())
            audio = client.text_to_speech.convert(
                text=corrected,
                voice_id=VOICE_ID,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
            return True
        except Exception as e2:
            print(f"ElevenLabs SDK fallback failed: {e2}")
            return False
