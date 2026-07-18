#!/usr/bin/env python3
"""
Interactive documentary project builder.

Creates a documentary project folder, saves config,
and generates a professional script using Gemini.

Environment:
    GEMINI_API_KEY

Usage:
    python3 scripts/doc_builder.py
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import requests


MODEL_NAME = "gemini-3.5-flash"

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL_NAME}:generateContent"
)

BASE_DIR = Path("/storage/emulated/0/DCIM/manga")

if not BASE_DIR.exists():
    BASE_DIR = Path.home() / "DCIM" / "manga"


def slugify_folder_name(text: str) -> str:

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

    return text[:120] if len(text) > 120 else text


def prompt_choice(
    title: str,
    options: list[str],
) -> str:

    print(f"\n{title}")

    for i, option in enumerate(options, start=1):

        print(f"  {i}. {option}")

    while True:

        choice = input("> ").strip()

        if (
            choice.isdigit()
            and
            1 <= int(choice) <= len(options)
        ):
            return options[int(choice) - 1]

        print("Enter a valid number.")


def build_prompt(
    topic: str,
    video_format: str,
    length_label: str,
    image_quality: str,
) -> str:

    return f"""Write a professional documentary-style script about: {topic}

Requirements:

- Target format: {video_format}
- Target length: {length_label}
- Image quality: {image_quality}
- Make it polished, cinematic and engaging.
- Divide into scenes.
- Every scene must include:
  1. Scene title
  2. Narration
  3. One line beginning with "Image:"
- Keep image descriptions visual and specific.
- Plain text only.
- No markdown tables.
- Finish with a short closing narration.
"""
# --------------------------------------------------------
# Gemini Script Generation
# --------------------------------------------------------

def generate_script(
    topic: str,
    video_format: str,
    length_label: str,
    image_quality: str,
    api_key: str,
) -> str:

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": build_prompt(
                            topic,
                            video_format,
                            length_label,
                            image_quality,
                        )
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
            error = response.json()
        except Exception:
            error = response.text

        raise RuntimeError(
            "Gemini API Error\n\n"
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
            "Gemini returned no candidates.\n\n"
            + json.dumps(data, indent=2)[:4000]
        )

    content = candidates[0].get(
        "content",
        {},
    )

    parts = content.get(
        "parts",
        [],
    )

    script = ""

    for part in parts:

        if not isinstance(
            part,
            dict,
        ):
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
# Main
# --------------------------------------------------------

def main() -> None:

    print("=========================================")
    print(" AI Documentary Creator")
    print("=========================================")

    topic = input("Topic:\n> ").strip()

    if not topic:
        raise SystemExit("Topic is required.")

    video_format = prompt_choice(
        "Video format?",
        [
            "16:9 (YouTube)",
            "9:16 (Shorts/Reels)",
        ],
    )

    length_label = prompt_choice(
        "Video length?",
        [
            "30 sec",
            "60 sec",
            "3 min",
            "5 min",
            "10 min",
            "Custom",
        ],
    )

    image_quality = prompt_choice(
        "Image quality?",
        [
            "Standard",
            "HD",
            "Highest",
        ],
    )

    api_key = os.environ.get(
        "GEMINI_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "GEMINI_API_KEY is not set."
        )

    project_dir = (
        BASE_DIR /
        slugify_folder_name(topic)
    )

    project_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    config = {
        "topic": topic,
        "video_format": video_format,
        "video_length": length_label,
        "image_quality": image_quality,
        "model": MODEL_NAME,
    }

    (project_dir / "config.json").write_text(
        json.dumps(
            config,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\nGenerating documentary script...\n")

    try:

        script = generate_script(
            topic,
            video_format,
            length_label,
            image_quality,
            api_key,
        )

        (project_dir / "script.txt").write_text(
            script,
            encoding="utf-8",
        )

    except Exception as e:

        print("\nGeneration failed.\n")
        print(e)
        raise SystemExit(1)

    print("===================================")
    print(" Documentary Project Created")
    print("===================================")

    print(f"\nProject : {project_dir}")
    print(f"Script  : {project_dir / 'script.txt'}")
    print(f"Config  : {project_dir / 'config.json'}")

    print("\nDone.\n")


if __name__ == "__main__":
    main()
