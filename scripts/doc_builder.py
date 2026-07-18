#!/usr/bin/env python3
"""
Interactive documentary project builder for Termux.

This script asks for:
- topic
- video format (16:9 or 9:16)
- video length
- image quality

Then it writes a project config and optionally generates a Gemini script.

Environment variables:
- GEMINI_API_KEY

Usage:
  python3 scripts/doc_builder.py
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import requests

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
BASE_DIR = Path("/storage/emulated/0/DCIM/manga")
if not BASE_DIR.exists():
    BASE_DIR = Path.home() / "DCIM" / "manga"


def slugify_folder_name(text: str) -> str:
    text = text.strip()
    text = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    text = re.sub(r"\s+", " ", text)
    return text[:120] if len(text) > 120 else text


def prompt_choice(title: str, options: list[str]) -> str:
    print(f"\n{title}")
    for i, option in enumerate(options, start=1):
        print(f"  {i}. {option}")
    while True:
        choice = input("> ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]
        print("Enter a valid number.")


def build_prompt(topic: str, video_format: str, length_label: str, image_quality: str) -> str:
    return f"""Write a professional documentary-style script about: {topic}

Requirements:
- Target format: {video_format}
- Target length: {length_label}
- Image quality preference: {image_quality}
- Make it polished, cinematic, and engaging.
- Structure it into scenes appropriate for the selected length.
- For each scene include:
  1) Scene title
  2) Narration
  3) A single line starting with 'Image:' describing the best image to download for that scene
- Keep each image description specific and visual.
- Use plain text only.
- Do not include markdown tables.
- End with a short closing line.
"""


def generate_script(topic: str, video_format: str, length_label: str, image_quality: str, api_key: str) -> str:
    payload = {
        "contents": [
            {"parts": [{"text": build_prompt(topic, video_format, length_label, image_quality)}]}
        ]
    }
    resp = requests.post(
        f"{GEMINI_ENDPOINT}?key={api_key}",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {json.dumps(data)[:500]}")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    if not text.strip():
        raise RuntimeError(f"Gemini returned empty text: {json.dumps(data)[:500]}")
    return text.strip()


def main() -> None:
    print("=========================================")
    print(" AI Documentary Creator")
    print("=========================================")

    topic = input("Topic:\n> ").strip()
    if not topic:
        raise SystemExit("Topic is required.")

    video_format = prompt_choice("Video format?", ["16:9 (YouTube)", "9:16 (Shorts/Reels)"])
    length_label = prompt_choice("Video length?", ["30 sec", "60 sec", "3 min", "5 min", "10 min", "Custom"])
    image_quality = prompt_choice("Image quality?", ["Standard", "HD", "Highest"])

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment.")

    project_dir = BASE_DIR / slugify_folder_name(topic)
    project_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "topic": topic,
        "video_format": video_format,
        "video_length": length_label,
        "image_quality": image_quality,
    }
    (project_dir / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    script = generate_script(topic, video_format, length_label, image_quality, api_key)
    (project_dir / "script.txt").write_text(script, encoding="utf-8")

    print("\nDone.")
    print(str(project_dir))


if __name__ == "__main__":
    main()
