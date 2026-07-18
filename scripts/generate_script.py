#!/usr/bin/env python3
"""
Generate a professional documentary-style script with Gemini.

Usage:
  export GEMINI_API_KEY="..."
  python3 scripts/generate_script.py --topic "Ancient Egypt" --output-dir "/storage/emulated/0/DCIM/manga"
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import requests

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"


def slugify_folder_name(text: str) -> str:
    text = text.strip()
    text = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    text = re.sub(r"\s+", " ", text)
    return text[:120] if len(text) > 120 else text


def build_prompt(topic: str) -> str:
    return f"""Write a professional documentary-style script about: {topic}

Requirements:
- Make it polished, cinematic, and engaging.
- Structure it into 8-12 scenes.
- For each scene include:
  1) Scene title
  2) Narration
  3) A single line starting with 'Image:' describing the best image to download for that scene
- Keep each image description specific and visual.
- Use plain text only.
- Do not include markdown tables.
- End with a short closing line.
"""


def generate_script(topic: str, api_key: str) -> str:
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": build_prompt(topic)}
                ]
            }
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
    parser = argparse.ArgumentParser(description="Generate documentary script with Gemini.")
    parser.add_argument("--topic", required=True, help="Script topic")
    parser.add_argument("--output-dir", default=str(Path.home() / "Documents"), help="Base output folder")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment.")

    base_dir = Path(args.output_dir)
    project_dir = base_dir / slugify_folder_name(args.topic)
    project_dir.mkdir(parents=True, exist_ok=True)

    script = generate_script(args.topic, api_key)
    (project_dir / "script.txt").write_text(script, encoding="utf-8")

    print(str(project_dir / "script.txt"))


if __name__ == "__main__":
    main()
