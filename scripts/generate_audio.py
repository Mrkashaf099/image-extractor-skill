#!/usr/bin/env python3
"""
Generate narration audio from script.txt using Gemini TTS.

Expected environment variable:
- GEMINI_API_KEY

Usage:
  python3 scripts/generate_audio.py --project-dir "/storage/emulated/0/DCIM/manga/Ancient Egypt"

This script expects a text file at:
  <project-dir>/script.txt
and saves narration audio to:
  <project-dir>/narration.wav

Note: depending on the Gemini TTS output format available in your account/model,
you may need to adjust the response handling.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path

import requests

GEMINI_TTS_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash-exp:generateContent"
)


def load_script(project_dir: Path) -> str:
    script_path = project_dir / "script.txt"
    if not script_path.exists():
        raise FileNotFoundError(f"Missing script file: {script_path}")
    return script_path.read_text(encoding="utf-8")


def generate_audio_bytes(script_text: str, api_key: str, voice_name: str) -> bytes:
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": script_text}
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": voice_name
                    }
                }
            }
        },
    }

    resp = requests.post(
        f"{GEMINI_TTS_ENDPOINT}?key={api_key}",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    # Gemini audio responses can vary by model/version.
    # We try a few likely locations for base64 audio bytes.
    candidates = []
    for item in data.get("candidates", []):
        content = item.get("content", {}) if isinstance(item, dict) else {}
        parts = content.get("parts", []) if isinstance(content, dict) else []
        for part in parts:
            if not isinstance(part, dict):
                continue
            if "inlineData" in part and isinstance(part["inlineData"], dict):
                inline = part["inlineData"]
                mime = inline.get("mimeType", "")
                b64 = inline.get("data")
                if b64:
                    candidates.append((mime, b64))
            if "audio" in part and isinstance(part["audio"], dict):
                audio = part["audio"]
                mime = audio.get("mimeType", "")
                b64 = audio.get("data")
                if b64:
                    candidates.append((mime, b64))

    if not candidates:
        raise RuntimeError(f"No audio bytes found in Gemini response: {json.dumps(data)[:1000]}")

    mime, b64 = candidates[0]
    audio_bytes = base64.b64decode(b64)
    return audio_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate narration audio using Gemini TTS.")
    parser.add_argument("--project-dir", required=True, help="Project folder containing script.txt")
    parser.add_argument("--voice", default="Kore", help="Gemini voice name")
    parser.add_argument("--output", default="narration.wav", help="Output audio filename")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment.")

    project_dir = Path(args.project_dir)
    script_text = load_script(project_dir)

    audio_bytes = generate_audio_bytes(script_text, api_key, args.voice)
    output_path = project_dir / args.output
    output_path.write_bytes(audio_bytes)

    print(str(output_path))


if __name__ == "__main__":
    main()
