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
- Duration-aware word-count targeting
- Style, tone, audience, language, format control
- Automatic retry with exponential backoff

Usage:

export GEMINI_API_KEY="YOUR_API_KEY"

# Original usage (unchanged):
python3 scripts/generate_script.py \
    --topic "Ancient Egypt" \
    --output-dir "/storage/emulated/0/DCIM/manga"

# Extended usage:
python3 scripts/generate_script.py \
    --topic "Ancient Egypt" \
    --output-dir "/storage/emulated/0/DCIM/manga" \
    --duration 120 \
    --style cinematic \
    --tone dramatic \
    --audience general \
    --language English \
    --format sections \
    --voice-speed normal \
    --max-retries 3
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import requests

# --------------------------------------------------------
# Constants  (unchanged from original)
# --------------------------------------------------------

MODEL_NAME = "gemini-3.5-flash"

GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL_NAME}:generateContent"
)

# --------------------------------------------------------
# New: spoken-words-per-second table per voice speed
# Used by estimate_word_count(); not exposed to any
# existing function so backward compatibility is intact.
# --------------------------------------------------------

_WORDS_PER_SECOND: dict[str, float] = {
    "slow":   2.0,
    "normal": 2.5,
    "fast":   3.2,
}

# --------------------------------------------------------
# New: valid choices for each new argument
# --------------------------------------------------------

VALID_STYLES: tuple[str, ...] = (
    "documentary",
    "cinematic",
    "educational",
    "storytelling",
    "news",
)

VALID_TONES: tuple[str, ...] = (
    "professional",
    "dramatic",
    "inspirational",
    "neutral",
    "suspenseful",
)

VALID_AUDIENCES: tuple[str, ...] = (
    "general",
    "children",
    "students",
    "experts",
)

VALID_FORMATS: tuple[str, ...] = (
    "plain",
    "markdown",
    "json",
    "sections",
)

VALID_VOICE_SPEEDS: tuple[str, ...] = (
    "slow",
    "normal",
    "fast",
)


# --------------------------------------------------------
# Helpers  (originals preserved verbatim)
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


# --------------------------------------------------------
# New helper: word-count estimator
# --------------------------------------------------------

def estimate_word_count(
    duration_seconds: Optional[int],
    voice_speed: str,
) -> Optional[int]:
    """
    Return the target word count for a requested narration duration.

    Returns None when duration is not specified so that build_prompt()
    can skip the word-count requirement entirely (backward-compatible).

    Args:
        duration_seconds: Requested narration length in seconds, or None.
        voice_speed: One of "slow", "normal", "fast".

    Returns:
        Integer word count target, or None.
    """
    if duration_seconds is None:
        return None

    wps = _WORDS_PER_SECOND.get(voice_speed, _WORDS_PER_SECOND["normal"])
    return round(duration_seconds * wps)


# --------------------------------------------------------
# New helper: style/tone/audience text fragments
# These are injected into the existing prompt block so
# the original prompt structure is fully preserved.
# --------------------------------------------------------

_STYLE_INSTRUCTIONS: dict[str, str] = {
    "documentary": (
        "Write in a classic documentary narration voice — authoritative, "
        "informative, and measured."
    ),
    "cinematic": (
        "Write with highly cinematic language — vivid imagery, deliberate "
        "pacing, and a strong sense of place and atmosphere."
    ),
    "educational": (
        "Write in a clear, pedagogical style that explains concepts "
        "step-by-step and reinforces key facts."
    ),
    "storytelling": (
        "Write as a human-centred narrative — focus on personal stories, "
        "character arcs, and emotional journeys."
    ),
    "news": (
        "Write in a concise, journalistic style — objective, factual, "
        "and structured like a broadcast news report."
    ),
}

_TONE_INSTRUCTIONS: dict[str, str] = {
    "professional": "Maintain a professional, composed, and credible tone throughout.",
    "dramatic":     "Use dramatic tension, rising stakes, and emotionally charged language.",
    "inspirational":"Write with an uplifting, motivational energy that leaves the audience inspired.",
    "neutral":      "Keep a balanced, impartial, and matter-of-fact tone.",
    "suspenseful":  "Build suspense progressively — use short sentences and strategic pauses.",
}

_AUDIENCE_INSTRUCTIONS: dict[str, str] = {
    "general":  "Assume a broad general audience with no specialist knowledge.",
    "children": (
        "Write for a young audience (ages 8–12). Use simple vocabulary, "
        "short sentences, and relatable comparisons."
    ),
    "students": (
        "Target secondary-school or university students. Balance accessibility "
        "with academic rigour."
    ),
    "experts":  (
        "Assume the audience has deep domain expertise. Use technical "
        "terminology freely and skip introductory explanations."
    ),
}

_FORMAT_INSTRUCTIONS: dict[str, str] = {
    "plain": (
        "Output plain text only. No markdown, no headers, no bullet points."
    ),
    "markdown": (
        "Format the output in Markdown. Use ## for scene titles, "
        "**bold** for emphasis, and --- between scenes."
    ),
    "json": (
        "Output valid JSON only — no prose outside the JSON block. "
        "Use this exact structure:\n"
        '{"title": "...", "scenes": [{"scene_title": "...", '
        '"narration": "...", "image": "..."}], "conclusion": "..."}'
    ),
    "sections": (
        "Structure the script into exactly four labelled sections:\n"
        "  Hook\n"
        "  Introduction\n"
        "  Main Content\n"
        "  Conclusion\n"
        "Label each section clearly before its content."
    ),
}


def _language_instruction(language: str) -> str:
    """Return a language instruction string for the prompt."""
    if language.lower() in ("english", "en"):
        return ""   # default — no extra instruction needed
    return (
        f"Write the entire script in {language}. "
        f"Keep all structural labels (Scene Title, Narration, Image) "
        f"in {language} as well."
    )


def _word_count_instruction(word_count: Optional[int]) -> str:
    """Return a word-count constraint line, or empty string."""
    if word_count is None:
        return ""
    return (
        f"Target narration length: approximately {word_count} words "
        f"(this matches the requested audio duration)."
    )


# --------------------------------------------------------
# Prompt builder  — EXTENDED
# Original build_prompt(topic) signature preserved;
# new overload build_prompt_extended() adds the new args
# without altering the original function's behaviour.
# --------------------------------------------------------

def build_prompt(topic: str) -> str:
    """
    Original prompt builder — unchanged.
    Called when no new arguments are passed (full backward compatibility).
    """

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


def build_prompt_extended(
    topic:       str,
    style:       str,
    tone:        str,
    audience:    str,
    language:    str,
    output_format: str,
    word_count:  Optional[int],
) -> str:
    """
    Extended prompt builder used when any new argument differs from its
    default value.  The original prompt block is kept intact as the base;
    extra requirement lines are appended before the structural rules.

    Args:
        topic:         Documentary topic (same as original).
        style:         Writing style (documentary / cinematic / …).
        tone:          Emotional tone (professional / dramatic / …).
        audience:      Target audience (general / children / …).
        language:      Output language (e.g. "English", "Spanish").
        output_format: Output format (plain / markdown / json / sections).
        word_count:    Target word count, or None for no constraint.

    Returns:
        Complete prompt string ready to send to Gemini.
    """

    # Gather optional instruction lines (skip empty strings)
    extra_lines: list[str] = [
        line for line in [
            _style_line     := _STYLE_INSTRUCTIONS.get(style, ""),
            _tone_line      := _TONE_INSTRUCTIONS.get(tone, ""),
            _audience_line  := _AUDIENCE_INSTRUCTIONS.get(audience, ""),
            _language_line  := _language_instruction(language),
            _wc_line        := _word_count_instruction(word_count),
            _format_line    := _FORMAT_INSTRUCTIONS.get(output_format, ""),
        ]
        if line
    ]

    # Format lines as bullet points to match the original prompt style
    extra_block = "\n".join(f"• {line}" for line in extra_lines)

    # Determine whether markdown/plain-text output rules from the original
    # prompt still apply.  If the user chose "json" or "markdown" format we
    # must NOT tell Gemini "Do NOT use markdown", so we conditionally include
    # those two lines.
    no_markdown_rule = (
        "\nDo NOT use markdown.\n\nDo NOT use tables."
        if output_format in ("plain", "sections", "")
        else ""
    )

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

{extra_block}

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
{no_markdown_rule}

End with a short powerful conclusion.
"""


# --------------------------------------------------------
# New helper: decide which prompt builder to use
# --------------------------------------------------------

_DEFAULT_STYLE    = "documentary"
_DEFAULT_TONE     = "professional"
_DEFAULT_AUDIENCE = "general"
_DEFAULT_LANGUAGE = "English"
_DEFAULT_FORMAT   = "plain"
_DEFAULT_SPEED    = "normal"


def _needs_extended_prompt(
    style:    str,
    tone:     str,
    audience: str,
    language: str,
    fmt:      str,
    speed:    str,
    duration: Optional[int],
) -> bool:
    """
    Return True when the caller supplied any non-default new argument.
    If all new args are at their defaults AND no duration was given we
    fall back to the original build_prompt() to guarantee identical
    output to previous versions.
    """
    return (
        style    != _DEFAULT_STYLE
        or tone  != _DEFAULT_TONE
        or audience != _DEFAULT_AUDIENCE
        or language.lower() not in ("english", "en")
        or fmt   != _DEFAULT_FORMAT
        or speed != _DEFAULT_SPEED
        or duration is not None
    )


# --------------------------------------------------------
# Gemini API  — EXTENDED with retry logic
# Original generate_script(topic, api_key) preserved;
# new generate_script_extended() adds retry + new params.
# --------------------------------------------------------

def generate_script(topic: str, api_key: str) -> str:
    """
    Original function — unchanged.
    Retained for backward compatibility; called when no new
    arguments are in use.
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


def _call_gemini(prompt: str, api_key: str) -> str:
    """
    Single Gemini API call.  Shared by generate_script_extended().
    Raises RuntimeError on HTTP or empty-response failures so the
    retry wrapper can catch and retry them uniformly.
    """

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
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
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Network error while contacting Gemini:\n{exc}"
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
    parts   = content.get("parts", [])
    script  = "".join(
        part["text"]
        for part in parts
        if isinstance(part, dict) and "text" in part
    )
    script = script.strip()

    if not script:
        raise RuntimeError("Gemini returned an empty script.")

    return script


def generate_script_extended(
    topic:       str,
    api_key:     str,
    style:       str          = _DEFAULT_STYLE,
    tone:        str          = _DEFAULT_TONE,
    audience:    str          = _DEFAULT_AUDIENCE,
    language:    str          = _DEFAULT_LANGUAGE,
    output_format: str        = _DEFAULT_FORMAT,
    duration:    Optional[int]= None,
    voice_speed: str          = _DEFAULT_SPEED,
    max_retries: int          = 1,
) -> str:
    """
    Extended version of generate_script() with new parameters.

    Implements exponential backoff on network/API failures.
    Falls back to the original prompt when all new args are at defaults
    (guarantees identical output to the original script).

    Args:
        topic:         Documentary topic.
        api_key:       Gemini API key.
        style:         Writing style (documentary/cinematic/educational/
                       storytelling/news).
        tone:          Emotional tone (professional/dramatic/inspirational/
                       neutral/suspenseful).
        audience:      Target audience (general/children/students/experts).
        language:      Output language, e.g. "English", "Spanish".
        output_format: Output format (plain/markdown/json/sections).
        duration:      Requested narration length in seconds, or None.
        voice_speed:   Speaking pace used to estimate word count
                       (slow/normal/fast).
        max_retries:   Maximum number of attempts before giving up.

    Returns:
        Generated script string.

    Raises:
        RuntimeError: After all retries are exhausted.
    """

    # Choose prompt builder
    if _needs_extended_prompt(
        style, tone, audience, language, output_format, voice_speed, duration
    ):
        word_count = estimate_word_count(duration, voice_speed)
        prompt = build_prompt_extended(
            topic         = topic,
            style         = style,
            tone          = tone,
            audience      = audience,
            language      = language,
            output_format = output_format,
            word_count    = word_count,
        )
    else:
        # Fully backward-compatible path: identical to original
        prompt = build_prompt(topic)

    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                # Exponential backoff: 2s, 4s, 8s, …
                wait = 2 ** (attempt - 1)
                print(
                    f"Retry {attempt}/{max_retries} "
                    f"(waiting {wait}s after previous failure)..."
                )
                time.sleep(wait)

            return _call_gemini(prompt, api_key)

        except RuntimeError as exc:
            last_error = exc
            print(f"\nAttempt {attempt} failed: {exc}\n")

    raise RuntimeError(
        f"All {max_retries} attempt(s) failed.\n\n"
        f"Last error:\n{last_error}"
    )


# --------------------------------------------------------
# Save Script  (unchanged from original)
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
# Main  — EXTENDED
# Original argument structure preserved verbatim;
# new optional arguments appended after.
# --------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Generate a professional documentary script using Gemini.\n\n"
            "All new arguments are optional. Omitting them produces exactly\n"
            "the same output as the original script."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------

# Original usage (unchanged):
python3 generate_script.py \\
    --topic "Ancient Egypt" \\
    --output-dir "/storage/emulated/0/DCIM/manga"

# 2-minute cinematic script in Spanish with sections format:
python3 generate_script.py \\
    --topic "Ancient Egypt" \\
    --output-dir "/storage/emulated/0/DCIM/manga" \\
    --duration 120 \\
    --style cinematic \\
    --tone dramatic \\
    --language Spanish \\
    --format sections

# 5-minute educational script for students, JSON output, 3 retries:
python3 generate_script.py \\
    --topic "Climate Change" \\
    --output-dir "~/docs" \\
    --duration 300 \\
    --style educational \\
    --audience students \\
    --format json \\
    --max-retries 3

# Slow-voiced inspirational narration (adjusts word count target):
python3 generate_script.py \\
    --topic "Ocean Life" \\
    --duration 60 \\
    --voice-speed slow \\
    --tone inspirational

Argument reference
------------------
  --duration      Seconds  : 30, 60, 120, 300, 600  (default: not set)
  --style         Style    : documentary (default), cinematic, educational,
                             storytelling, news
  --tone          Tone     : professional (default), dramatic, inspirational,
                             neutral, suspenseful
  --audience      Audience : general (default), children, students, experts
  --language      Language : English (default), Spanish, French, German, …
  --format        Format   : plain (default), markdown, json, sections
  --voice-speed   Speed    : slow, normal (default), fast
  --max-retries   Retries  : integer ≥ 1 (default: 1)
""",
    )

    # ── Original arguments (preserved verbatim) ──────────────────────────

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

    # ── New optional arguments ────────────────────────────────────────────

    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        metavar="SECONDS",
        help=(
            "Target narration duration in seconds (e.g. 30, 60, 120, 300, 600). "
            "Word count is calculated automatically from this value and --voice-speed. "
            "Omit to use no word-count constraint (original behaviour)."
        ),
    )

    parser.add_argument(
        "--style",
        default=_DEFAULT_STYLE,
        choices=VALID_STYLES,
        metavar="STYLE",
        help=(
            f"Writing style. Choices: {', '.join(VALID_STYLES)}. "
            f"Default: {_DEFAULT_STYLE}"
        ),
    )

    parser.add_argument(
        "--tone",
        default=_DEFAULT_TONE,
        choices=VALID_TONES,
        metavar="TONE",
        help=(
            f"Emotional tone. Choices: {', '.join(VALID_TONES)}. "
            f"Default: {_DEFAULT_TONE}"
        ),
    )

    parser.add_argument(
        "--audience",
        default=_DEFAULT_AUDIENCE,
        choices=VALID_AUDIENCES,
        metavar="AUDIENCE",
        help=(
            f"Target audience. Choices: {', '.join(VALID_AUDIENCES)}. "
            f"Default: {_DEFAULT_AUDIENCE}"
        ),
    )

    parser.add_argument(
        "--language",
        default=_DEFAULT_LANGUAGE,
        metavar="LANGUAGE",
        help=(
            "Output language for the script (e.g. English, Spanish, French, "
            "German, Japanese). Default: English"
        ),
    )

    parser.add_argument(
        "--format",
        dest="output_format",
        default=_DEFAULT_FORMAT,
        choices=VALID_FORMATS,
        metavar="FORMAT",
        help=(
            f"Output format. Choices: {', '.join(VALID_FORMATS)}. "
            "'sections' produces Hook / Introduction / Main Content / Conclusion. "
            f"Default: {_DEFAULT_FORMAT}"
        ),
    )

    parser.add_argument(
        "--voice-speed",
        default=_DEFAULT_SPEED,
        choices=VALID_VOICE_SPEEDS,
        metavar="SPEED",
        help=(
            "Spoken pace used to compute target word count when --duration is set. "
            f"Choices: {', '.join(VALID_VOICE_SPEEDS)} "
            f"({_WORDS_PER_SECOND['slow']} / {_WORDS_PER_SECOND['normal']} / "
            f"{_WORDS_PER_SECOND['fast']} words/second). "
            f"Default: {_DEFAULT_SPEED}"
        ),
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        metavar="N",
        help=(
            "Maximum number of API call attempts with exponential backoff "
            "(2s, 4s, 8s, …). Must be ≥ 1. Default: 1"
        ),
    )

    args = parser.parse_args()

    # ── Validate new arguments ────────────────────────────────────────────

    if args.duration is not None and args.duration <= 0:
        print("\nERROR: --duration must be a positive integer (seconds).\n")
        sys.exit(1)

    if args.max_retries < 1:
        print("\nERROR: --max-retries must be ≥ 1.\n")
        sys.exit(1)

    # ── API key check (unchanged) ─────────────────────────────────────────

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:

        print(
            "\nERROR: GEMINI_API_KEY environment variable is not set.\n"
        )

        print("Example:\n")

        print('export GEMINI_API_KEY="YOUR_API_KEY"\n')

        sys.exit(1)

    # ── Output directory setup (unchanged) ────────────────────────────────

    output_dir = Path(args.output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ── Progress output ───────────────────────────────────────────────────

    print("\nGenerating documentary script...\n")

    # Show new parameters only when they differ from defaults
    if _needs_extended_prompt(
        args.style,
        args.tone,
        args.audience,
        args.language,
        args.output_format,
        args.voice_speed,
        args.duration,
    ):
        wc = estimate_word_count(args.duration, args.voice_speed)
        print(f"  Style       : {args.style}")
        print(f"  Tone        : {args.tone}")
        print(f"  Audience    : {args.audience}")
        print(f"  Language    : {args.language}")
        print(f"  Format      : {args.output_format}")
        if args.duration:
            print(f"  Duration    : {args.duration}s")
            print(f"  Voice speed : {args.voice_speed}")
            print(f"  Target words: ~{wc}")
        if args.max_retries > 1:
            print(f"  Max retries : {args.max_retries}")
        print()

    # ── Generation ────────────────────────────────────────────────────────

    try:

        script = generate_script_extended(
            topic          = args.topic,
            api_key        = api_key,
            style          = args.style,
            tone           = args.tone,
            audience       = args.audience,
            language       = args.language,
            output_format  = args.output_format,
            duration       = args.duration,
            voice_speed    = args.voice_speed,
            max_retries    = args.max_retries,
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

    # ── Success output (original format preserved) ────────────────────────

    print("===================================")
    print(" Script Generated Successfully")
    print("===================================")

    print(f"\nTopic : {args.topic}")

    print(f"\nSaved : {script_path}")

    print("\nDone.\n")


if __name__ == "__main__":
    main()
