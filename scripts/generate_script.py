#!/usr/bin/env python3
"""
generate_script.py

Professional Documentary Script Generator
-----------------------------------------

Features:
- Uses the latest Gemini API
- Generates cinematic documentary scripts
- Saves script.txt inside the project folder
- Better error handling
- Future-proof structure

Usage:

export GEMINI_API_KEY="YOUR_API_KEY"

python3 scripts/generate_script.py \
    --topic "Ancient Egypt" \
    --output-dir "/storage/emulated/0/DCIM/manga"

"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests

MODEL_NAME = "gemini-3.5-flash"

GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL_NAME}:generateContent"
)


# --------------------------------------------------------
# Helpers
# --------------------------------------------------------

def slugify_folder_name(text: str) -> str:
    """
    Convert topic into a safe folder name.
    """

    text = text.strip()

    text = re.sub(
        r"[\\/:*?\"<>|]+",
        "_",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text[:120]


def build_prompt(topic: str) -> str:

    return f"""
You are an award-winning documentary writer.

Create a premium documentary script about:

{topic}

Requirements

• Professional documentary narration

• Cinematic storytelling

• Factually accurate

• Strong emotional hook

• Natural narration

• Clear scene progression

• 8–12 scenes

For every scene provide:

Scene Title:

Narration:

Image:

The Image line must describe ONE highly detailed cinematic image.

Image descriptions should include:

- subject
- location
- lighting
- camera angle
- realism
- atmosphere

Do NOT use markdown.

Do NOT use tables.

End with a short powerful conclusion.
"""
# --------------------------------------------------------
# Gemini API
# --------------------------------------------------------

def generate_script(topic: str, api_key: str) -> str:
    """
    Generate a documentary script using Gemini.
    """

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": build_prompt(topic)
                    }
                ]
            }
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    try:

        response = requests.post(
            GEMINI_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=120,
        )

    except requests.RequestException as e:
        raise RuntimeError(
            f"Network error while contacting Gemini:\n{e}"
        )

    if response.status_code != 200:

        try:
            error_json = response.json()
        except Exception:
            error_json = response.text

        raise RuntimeError(
            "Gemini API Error\n\n"
            f"HTTP Status : {response.status_code}\n\n"
            f"{json.dumps(error_json, indent=2, ensure_ascii=False)}"
        )

    data = response.json()

    candidates = data.get("candidates")

    if not candidates:
        raise RuntimeError(
            "Gemini returned no candidates.\n\n"
            + json.dumps(data, indent=2)[:3000]
        )

    content = candidates[0].get("content", {})

    parts = content.get("parts", [])

    script = ""

    for part in parts:

        if not isinstance(part, dict):
            continue

        if "text" in part:
            script += part["text"]

    script = script.strip()

    if not script:

        raise RuntimeError(
            "Gemini returned an empty script."
        )

    return script


# --------------------------------------------------------
# Save Script
# --------------------------------------------------------

def save_script(
    topic: str,
    output_dir: Path,
    script: str,
) -> Path:

    project_dir = output_dir / slugify_folder_name(topic)

    project_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    script_path = project_dir / "script.txt"

    script_path.write_text(
        script,
        encoding="utf-8",
    )

    return script_path
# --------------------------------------------------------
# Main
# --------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description="Generate a professional documentary script using Gemini."
    )

    parser.add_argument(
        "--topic",
        required=True,
        help="Documentary topic",
    )

    parser.add_argument(
        "--output-dir",
        default=str(Path.home() / "Documents"),
        help="Directory where the project folder will be created",
    )

    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:

        print(
            "\nERROR: GEMINI_API_KEY environment variable is not set.\n"
        )

        print("Example:\n")

        print('export GEMINI_API_KEY="YOUR_API_KEY"\n')

        sys.exit(1)

    output_dir = Path(args.output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("\nGenerating documentary script...\n")

    try:

        script = generate_script(
            args.topic,
            api_key,
        )

        script_path = save_script(
            args.topic,
            output_dir,
            script,
        )

    except Exception as e:

        print("\nGeneration failed.\n")

        print(e)

        sys.exit(1)

    print("===================================")
    print(" Script Generated Successfully")
    print("===================================")

    print(f"\nTopic : {args.topic}")

    print(f"\nSaved : {script_path}")

    print("\nDone.\n")


if __name__ == "__main__":
    main()
