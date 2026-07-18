#!/usr/bin/env python3
"""
Generate narration audio using Gemini TTS.

Usage:

export GEMINI_API_KEY="YOUR_API_KEY"

python3 scripts/generate_audio.py \
    --project-dir "/storage/emulated/0/DCIM/manga/Ancient Egypt"

Output:

<project-dir>/narration.wav
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import requests


MODEL_NAME = "gemini-3.1-flash-tts-preview"

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL_NAME}:generateContent"
)


# --------------------------------------------------------
# Helpers
# --------------------------------------------------------

def load_script(project_dir: Path) -> str:

    script_path = project_dir / "script.txt"

    if not script_path.exists():

        raise FileNotFoundError(
            f"Missing script:\n{script_path}"
        )

    return script_path.read_text(
        encoding="utf-8"
    )


def build_payload(
    script_text: str,
    voice_name: str,
) -> dict:

    return {

        "contents": [

            {

                "parts": [

                    {

                        "text": script_text

                    }

                ]

            }

        ],

        "generationConfig": {

            "responseModalities": [

                "AUDIO"

            ],

            "speechConfig": {

                "voiceConfig": {

                    "prebuiltVoiceConfig": {

                        "voiceName": voice_name

                    }

                }

            }

        }

    }
# --------------------------------------------------------
# Gemini TTS
# --------------------------------------------------------

def generate_audio_bytes(
    script_text: str,
    api_key: str,
    voice_name: str,
) -> bytes:

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    payload = build_payload(
        script_text,
        voice_name,
    )

    try:

        response = requests.post(
            GEMINI_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=300,
        )

    except requests.RequestException as e:

        raise RuntimeError(
            f"Network error:\n{e}"
        )

    if response.status_code != 200:

        try:
            error = response.json()
        except Exception:
            error = response.text

        raise RuntimeError(
            "Gemini TTS Error\n\n"
            f"HTTP Status : {response.status_code}\n\n"
            f"{json.dumps(error, indent=2, ensure_ascii=False)}"
        )

    data = response.json()

    candidates = data.get(
        "candidates",
        [],
    )

    if not candidates:

        raise RuntimeError(
            "No candidates returned.\n\n"
            + json.dumps(data, indent=2)[:4000]
        )

    audio_b64 = None

    for candidate in candidates:

        content = candidate.get(
            "content",
            {},
        )

        parts = content.get(
            "parts",
            [],
        )

        for part in parts:

            if not isinstance(
                part,
                dict,
            ):
                continue

            inline = part.get("inlineData")

            if isinstance(
                inline,
                dict,
            ):

                audio_b64 = inline.get(
                    "data"
                )

                if audio_b64:
                    break

            audio = part.get("audio")

            if isinstance(
                audio,
                dict,
            ):

                audio_b64 = audio.get(
                    "data"
                )

                if audio_b64:
                    break

        if audio_b64:
            break

    if not audio_b64:

        raise RuntimeError(
            "Gemini returned no audio.\n\n"
            + json.dumps(data, indent=2)[:4000]
        )

    return base64.b64decode(audio_b64)
# --------------------------------------------------------
# Main
# --------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description="Generate narration audio using Gemini TTS."
    )

    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project directory containing script.txt",
    )

    parser.add_argument(
        "--voice",
        default="Kore",
        help="Gemini voice name",
    )

    parser.add_argument(
        "--output",
        default="narration.wav",
        help="Output filename",
    )

    args = parser.parse_args()

    api_key = os.environ.get(
        "GEMINI_API_KEY"
    )

    if not api_key:

        print(
            "\nERROR: GEMINI_API_KEY is not set.\n"
        )

        sys.exit(1)

    project_dir = Path(
        args.project_dir
    )

    script_text = load_script(
        project_dir
    )

    print("\nGenerating narration...\n")

    try:

        audio_bytes = generate_audio_bytes(
            script_text,
            api_key,
            args.voice,
        )

        output_path = (
            project_dir / args.output
        )

        output_path.write_bytes(
            audio_bytes
        )

    except Exception as e:

        print("\nGeneration failed.\n")

        print(e)

        sys.exit(1)

    print("===================================")
    print(" Narration Generated Successfully")
    print("===================================")

    print(f"\nSaved : {output_path}")

    print("\nDone.\n")


if __name__ == "__main__":
    main()
