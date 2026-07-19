#!/usr/bin/env python3
"""
build_video.py — Production Documentary Video Builder
======================================================
Target: Android Termux ARM64 · 2 GB RAM · CPU-only · Long sessions

Features
--------
- Dynamic batch sizing (resolution + storage + cores + image count)
- Natural image ordering  (1, 2, 10  not  1, 10, 2)
- Multi-format narration  (.wav .mp3 .m4a .aac .flac)
- Auto encoder detection  (libx264 / h264_mediacodec / h264_nvenc / h264_qsv / h264_amf)
- Variable per-image durations via script.txt
- ASS subtitle renderer   (animation, fonts, karaoke, highlight)
- Full checkpoint system  (image index · batch · files · progress · versions)
- --dry-run / --resume / --clean CLI flags
- Configurable via config.json (all tunables exposed)
- Standard-library only + FFmpeg/FFprobe; zero heavy deps

Usage
-----
  python build_video.py                          # build from current directory
  python build_video.py --project /path/to/proj
  python build_video.py --dry-run
  python build_video.py --resume
  python build_video.py --clean
  DEBUG=1 python build_video.py

Project layout
--------------
  project/
  ├── images/          (required)  jpg png webp bmp
  ├── narration.wav    (required)  also .mp3 .m4a .aac .flac
  ├── config.json      (optional)
  ├── music.mp3        (optional)  background track
  ├── subtitles.srt    (optional)  also .ass
  └── script.txt       (optional)  per-image duration overrides

Author : Kasaf Documentary Pipeline
Version: 3.0 (Production)
"""

from __future__ import annotations

# ── stdlib only ──────────────────────────────────────────────────────────────
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ═════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═════════════════════════════════════════════════════════════════════════════

VERSION: str = "3.0"

SUPPORTED_IMAGE_EXTS: Tuple[str, ...] = (
    ".jpg", ".jpeg", ".png", ".webp", ".bmp",
)

SUPPORTED_AUDIO_EXTS: Tuple[str, ...] = (
    ".wav", ".mp3", ".m4a", ".aac", ".flac",
)

NARRATION_STEMS: Tuple[str, ...] = ("narration", "audio", "voice", "narration_audio")

OUTPUT_FILENAME:     str = "final_video.mp4"
CHECKPOINT_FILENAME: str = ".build_checkpoint.json"
SCRIPT_FILENAME:     str = "script.txt"
TEMP_PREFIX:         str = "docbuild_"
LOG_FILENAME:        str = "build.log"

# Resolution look-up tables
RES_HORIZONTAL: Dict[str, Tuple[int, int]] = {
    "480p":  (854,  480),
    "720p":  (1280, 720),
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "4k":    (3840, 2160),
}
RES_VERTICAL: Dict[str, Tuple[int, int]] = {
    "480p":  (480,  854),
    "720p":  (720,  1280),
    "1080p": (1080, 1920),
    "1440p": (1440, 2560),
    "4k":    (2160, 3840),
}

# Ken Burns
KB_ZOOM_MIN:  float = 1.08
KB_ZOOM_MAX:  float = 1.18
KB_ZOOM_STEP: float = 0.0005

# Batch sizing guard-rails
BATCH_MIN:  int = 3
BATCH_MAX:  int = 20

# Minimum free storage (bytes) to allow rendering
MIN_FREE_STORAGE_BYTES: int = 512 * 1024 * 1024   # 512 MB

# Fade transition default
DEFAULT_FADE_DURATION: float = 0.75

# Default AAC audio bitrate
DEFAULT_AAC_BITRATE: str = "192k"

# FFmpeg progress pattern
_TIME_RE: re.Pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")

# Natural sort helper
_NS_RE: re.Pattern = re.compile(r"(\d+)")


# ═════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═════════════════════════════════════════════════════════════════════════════

class AspectRatio(str, Enum):
    H16_9 = "16:9"
    V9_16 = "9:16"


class EncoderID(str, Enum):
    LIBX264        = "libx264"
    H264_MEDIACODEC = "h264_mediacodec"
    H264_NVENC     = "h264_nvenc"
    H264_QSV       = "h264_qsv"
    H264_AMF       = "h264_amf"
    MPEG4          = "mpeg4"       # absolute fallback


class ResumeMode(str, Enum):
    AUTO   = "auto"    # resume if checkpoint exists, else fresh
    FORCE  = "force"   # always resume (error if no checkpoint)
    NEVER  = "never"   # always start fresh (delete checkpoint)


# ═════════════════════════════════════════════════════════════════════════════
# DATA-CLASSES
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class VideoConfig:
    """
    All user-facing tunables.  Loaded from config.json; any missing key
    keeps the default below.
    """
    # ── video ────────────────────────────────────────────────────────────────
    aspect_ratio:   str  = AspectRatio.H16_9.value
    resolution:     str  = "1080p"
    fps:            int  = 30
    crf:            int  = 23          # H.264 quality 0-51 (lower = better)
    preset:         str  = "veryfast"  # FFmpeg -preset
    pix_fmt:        str  = "yuv420p"

    # ── encoder (auto = detect best available) ───────────────────────────────
    encoder:        str  = "auto"      # "auto" | EncoderID value
    threads:        int  = 0           # 0 = let FFmpeg decide

    # ── ken burns ────────────────────────────────────────────────────────────
    enable_ken_burns: bool = True

    # ── transitions ──────────────────────────────────────────────────────────
    fade_duration:  float = DEFAULT_FADE_DURATION

    # ── audio ────────────────────────────────────────────────────────────────
    audio_bitrate:     str   = DEFAULT_AAC_BITRATE
    audio_normalization: bool = True
    enable_music:      bool  = True
    music_volume:      float = 0.12    # 0.0-1.0

    # ── subtitles ────────────────────────────────────────────────────────────
    enable_subtitles:  bool  = True
    subtitle_style:    str   = "default"   # "default" | "minimal" | "dramatic"

    # ── output ───────────────────────────────────────────────────────────────
    output_filename:   str   = OUTPUT_FILENAME
    temp_directory:    str   = ""          # "" = system temp
    keep_temp:         bool  = False

    # ── batch / memory ───────────────────────────────────────────────────────
    batch_size_override: int = 0       # 0 = auto-calculate

    # ── resume ───────────────────────────────────────────────────────────────
    resume_mode:       str   = ResumeMode.AUTO.value

    def __post_init__(self) -> None:
        if self.aspect_ratio not in [r.value for r in AspectRatio]:
            raise ValueError(f"Invalid aspect_ratio '{self.aspect_ratio}'")
        res_table = (
            RES_VERTICAL if self.aspect_ratio == AspectRatio.V9_16.value
            else RES_HORIZONTAL
        )
        if self.resolution not in res_table:
            raise ValueError(f"Invalid resolution '{self.resolution}'")
        if not (1 <= self.fps <= 60):
            raise ValueError(f"fps must be 1-60, got {self.fps}")
        if not (0 <= self.crf <= 51):
            raise ValueError(f"crf must be 0-51, got {self.crf}")
        if not (0.0 <= self.music_volume <= 1.0):
            raise ValueError(f"music_volume must be 0-1, got {self.music_volume}")


@dataclass
class EncoderProfile:
    """Describes the selected H.264 encoder and its parameters."""
    encoder_id:  str
    preset_flag: str   # -preset value (empty string if unsupported)
    crf_flag:    str   # -crf value    (empty string if unsupported)
    extra_flags: List[str] = field(default_factory=list)

    @property
    def is_hw(self) -> bool:
        return self.encoder_id != EncoderID.LIBX264.value


@dataclass
class ImageFrame:
    """One image entry in the render timeline."""
    path:       Path
    index:      int
    start_time: float
    duration:   float

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration


@dataclass
class RenderBatch:
    """A contiguous slice of the timeline processed by one FFmpeg call."""
    batch_id:       int
    frames:         List[ImageFrame]
    start_time:     float
    total_duration: float


@dataclass
class BuildCheckpoint:
    """Persisted state that allows resuming an interrupted build."""
    build_version:      str
    ffmpeg_version:     str
    timestamp:          str
    project_hash:       str          # hash of sorted image names
    total_frames:       int
    total_batches:      int
    completed_batches:  List[int]
    last_frame_index:   int          # highest frame index rendered so far
    batch_output_files: Dict[str, str]   # str(batch_id) -> str(path)
    config_snapshot:    Dict[str, Any]


# ═════════════════════════════════════════════════════════════════════════════
# LOGGER
# ═════════════════════════════════════════════════════════════════════════════

class Logger:
    """
    Thread-safe console + optional file logger.
    Levels: DEBUG INFO OK WARN ERROR
    Activated debug output via env-var DEBUG=1.
    """

    _log_file: Optional[Path] = None
    _debug_on: bool = bool(os.environ.get("DEBUG", ""))

    @classmethod
    def configure(cls, log_file: Optional[Path] = None) -> None:
        cls._log_file = log_file
        cls._debug_on = bool(os.environ.get("DEBUG", ""))

    @classmethod
    def _emit(cls, level: str, msg: str) -> None:
        ts   = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] [{level:<5}] {msg}"
        print(line)
        if cls._log_file:
            try:
                with open(cls._log_file, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except Exception:
                pass

    @classmethod
    def debug(cls, msg: str) -> None:
        if cls._debug_on:
            cls._emit("DEBUG", msg)

    @classmethod
    def info(cls, msg: str) -> None:
        cls._emit("INFO", msg)

    @classmethod
    def ok(cls, msg: str) -> None:
        cls._emit("OK", msg)

    @classmethod
    def warn(cls, msg: str) -> None:
        cls._emit("WARN", msg)

    @classmethod
    def error(cls, msg: str) -> None:
        cls._emit("ERROR", msg)

    @classmethod
    def section(cls, title: str) -> None:
        bar = "─" * 60
        cls._emit("INFO", bar)
        cls._emit("INFO", f"  {title}")
        cls._emit("INFO", bar)


# ═════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═════════════════════════════════════════════════════════════════════════════

def natural_sort_key(path: Path) -> List[Any]:
    """Return sort key that orders 1,2,10 correctly instead of 1,10,2."""
    parts = _NS_RE.split(path.stem.lower())
    return [int(p) if p.isdigit() else p for p in parts]


def escape_ffmpeg(path: Path) -> str:
    """Normalise path separators for FFmpeg on all platforms."""
    return str(path).replace("\\", "/")


def escape_subtitle_path(path: Path) -> str:
    """Escape colons in subtitle paths (required by libavfilter)."""
    return escape_ffmpeg(path).replace(":", "\\:")


def seconds_to_hms(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"


def parse_ffmpeg_time(line: str) -> Optional[float]:
    """Extract elapsed seconds from an FFmpeg stderr line."""
    m = _TIME_RE.search(line)
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def project_hash(image_paths: List[Path]) -> str:
    """Stable hash of image names — used to detect project changes."""
    names = "|".join(p.name for p in image_paths)
    h = 0
    for ch in names:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return f"{h:08x}"


def get_free_bytes(path: Path) -> int:
    try:
        return shutil.disk_usage(path).free
    except Exception:
        return 0


def get_cpu_cores() -> int:
    return os.cpu_count() or 2


# ═════════════════════════════════════════════════════════════════════════════
# SYSTEM / ENVIRONMENT
# ═════════════════════════════════════════════════════════════════════════════

class SystemInfo:
    """Collects and exposes platform information."""

    @staticmethod
    def get_ffmpeg_version() -> str:
        try:
            r = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True, text=True, timeout=10,
            )
            first = r.stdout.splitlines()[0] if r.stdout else ""
            return first.split("version")[-1].strip().split()[0] if "version" in first else "unknown"
        except Exception:
            return "unknown"

    @staticmethod
    def verify_ffmpeg() -> None:
        if not shutil.which("ffmpeg"):
            Logger.error("FFmpeg not found.  Install: pkg install ffmpeg")
            sys.exit(1)
        if not shutil.which("ffprobe"):
            Logger.error("FFprobe not found.  Install: pkg install ffmpeg")
            sys.exit(1)
        Logger.ok(f"FFmpeg {SystemInfo.get_ffmpeg_version()} detected")

    @staticmethod
    def report() -> None:
        Logger.section("System Environment")
        Logger.info(f"Python   : {sys.version.split()[0]}")
        Logger.info(f"Platform : {sys.platform}")
        Logger.info(f"CPU cores: {get_cpu_cores()}")
        Logger.info(f"FFmpeg   : {SystemInfo.get_ffmpeg_version()}")


# ═════════════════════════════════════════════════════════════════════════════
# ENCODER DETECTION
# ═════════════════════════════════════════════════════════════════════════════

class EncoderDetector:
    """
    Probes FFmpeg for available H.264 encoders and returns the best one.
    Priority: h264_mediacodec (Android HW) > h264_nvenc > h264_qsv >
              h264_amf > libx264 > mpeg4
    """

    # (encoder_id, preset_support, crf_support, extra_flags)
    _PRIORITY: List[Tuple[str, bool, bool, List[str]]] = [
        (EncoderID.H264_MEDIACODEC.value, False, False, ["-b:v", "4M"]),
        (EncoderID.H264_NVENC.value,      True,  True,  []),
        (EncoderID.H264_QSV.value,        False, True,  []),
        (EncoderID.H264_AMF.value,        False, True,  []),
        (EncoderID.LIBX264.value,         True,  True,  []),
        (EncoderID.MPEG4.value,           False, False, []),
    ]

    @staticmethod
    def _available_encoders() -> str:
        try:
            r = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=15,
            )
            return r.stdout
        except Exception:
            return ""

    @classmethod
    def detect(cls, preferred: str, config: VideoConfig) -> EncoderProfile:
        """Return best available EncoderProfile."""
        available = cls._available_encoders()

        # If user pinned a specific encoder, try it first
        if preferred != "auto":
            if preferred in available:
                return cls._make_profile(preferred, config)
            Logger.warn(f"Requested encoder '{preferred}' not found; auto-detecting")

        for enc_id, has_preset, has_crf, extras in cls._PRIORITY:
            if enc_id in available:
                profile = cls._make_profile(enc_id, config, has_preset, has_crf, extras)
                Logger.ok(f"Encoder selected: {enc_id}")
                return profile

        Logger.error("No usable H.264 encoder found in FFmpeg")
        sys.exit(1)

    @classmethod
    def _make_profile(
        cls,
        enc_id: str,
        config: VideoConfig,
        has_preset: bool = True,
        has_crf: bool = True,
        extras: Optional[List[str]] = None,
    ) -> EncoderProfile:
        return EncoderProfile(
            encoder_id  = enc_id,
            preset_flag = config.preset if has_preset else "",
            crf_flag    = str(config.crf) if has_crf else "",
            extra_flags = extras or [],
        )


# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURATION LOADER
# ═════════════════════════════════════════════════════════════════════════════

class ConfigLoader:
    """Reads config.json and returns a validated VideoConfig."""

    @staticmethod
    def load(project_dir: Path) -> VideoConfig:
        path = project_dir / "config.json"
        cfg  = VideoConfig()

        if not path.exists():
            Logger.warn("config.json not found — using built-in defaults")
            return cfg

        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("config.json must be a JSON object")
            for k, v in data.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
                else:
                    Logger.warn(f"config.json: unknown key '{k}' ignored")
            cfg.__post_init__()          # re-validate after overrides
            Logger.ok("config.json loaded")
        except Exception as exc:
            Logger.warn(f"config.json parse error — using defaults: {exc}")

        return cfg


# ═════════════════════════════════════════════════════════════════════════════
# PROJECT VALIDATOR
# ═════════════════════════════════════════════════════════════════════════════

class ProjectValidator:
    """Validates the project directory structure."""

    @staticmethod
    def validate(project_dir: Path) -> None:
        Logger.section("Project Validation")

        if not project_dir.is_dir():
            Logger.error(f"Project directory not found: {project_dir}")
            sys.exit(1)

        img_dir = project_dir / "images"
        if not img_dir.is_dir():
            Logger.error("Missing images/ directory")
            sys.exit(1)

        # narration — try multiple names + extensions
        narration = ProjectValidator._find_narration(project_dir)
        if narration is None:
            Logger.error(
                "No narration file found.  Expected one of: "
                + ", ".join(
                    f"{s}{e}"
                    for s in NARRATION_STEMS
                    for e in SUPPORTED_AUDIO_EXTS
                )
            )
            sys.exit(1)

        Logger.ok(f"Narration : {narration.name}")

        for optional in ("music.mp3", "subtitles.srt", "subtitles.ass",
                         "config.json", SCRIPT_FILENAME):
            p = project_dir / optional
            if p.exists():
                Logger.ok(f"Found     : {optional}")
            else:
                Logger.debug(f"Optional missing: {optional}")

        free_gb = get_free_bytes(project_dir) / 1024 ** 3
        if free_gb < 0.5:
            Logger.warn(f"Low storage: {free_gb:.2f} GB free")
        else:
            Logger.info(f"Free storage: {free_gb:.2f} GB")

        Logger.ok("Validation passed")

    @staticmethod
    def _find_narration(project_dir: Path) -> Optional[Path]:
        for stem in NARRATION_STEMS:
            for ext in SUPPORTED_AUDIO_EXTS:
                p = project_dir / f"{stem}{ext}"
                if p.is_file():
                    return p
        return None


# ═════════════════════════════════════════════════════════════════════════════
# AUDIO UTILITIES
# ═════════════════════════════════════════════════════════════════════════════

class AudioUtils:
    """Handles narration duration, conversion, and segment extraction."""

    @staticmethod
    def find_narration(project_dir: Path) -> Path:
        for stem in NARRATION_STEMS:
            for ext in SUPPORTED_AUDIO_EXTS:
                p = project_dir / f"{stem}{ext}"
                if p.is_file():
                    return p
        Logger.error("Narration file not found (should have been caught earlier)")
        sys.exit(1)

    @staticmethod
    def get_duration(audio_path: Path) -> float:
        """Return duration in seconds — WAV via stdlib, others via FFprobe."""
        if audio_path.suffix.lower() == ".wav":
            try:
                with wave.open(str(audio_path), "rb") as wf:
                    dur = wf.getnframes() / float(wf.getframerate())
                    Logger.info(f"Narration duration: {dur:.2f}s (WAV)")
                    return dur
            except wave.Error:
                pass   # fall through to FFprobe

        # Use FFprobe for all other formats
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            escape_ffmpeg(audio_path),
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            dur = float(r.stdout.strip())
            Logger.info(f"Narration duration: {dur:.2f}s ({audio_path.suffix})")
            return dur
        except Exception as exc:
            Logger.error(f"Cannot read narration duration: {exc}")
            sys.exit(1)

    @staticmethod
    def extract_segment(
        src:        Path,
        dst:        Path,
        start:      float,
        duration:   float,
        bitrate:    str = DEFAULT_AAC_BITRATE,
    ) -> None:
        """Extract [start, start+duration] from src and encode to AAC."""
        cmd = [
            "ffmpeg", "-y",
            "-loglevel", "error",
            "-ss",  f"{start:.3f}",
            "-t",   f"{duration:.3f}",
            "-i",   escape_ffmpeg(src),
            "-c:a", "aac",
            "-b:a", bitrate,
            escape_ffmpeg(dst),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            Logger.debug(f"Audio segment: {dst.name}  [{start:.2f}s +{duration:.2f}s]")
        except subprocess.CalledProcessError as exc:
            Logger.error(f"Audio extraction failed: {exc}")
            raise


# ═════════════════════════════════════════════════════════════════════════════
# IMAGE DISCOVERY
# ═════════════════════════════════════════════════════════════════════════════

class ImageDiscovery:
    """Finds, validates, and naturally-sorts images."""

    @staticmethod
    def discover(image_dir: Path) -> List[Path]:
        Logger.info("Discovering images...")
        found: List[Path] = []
        for ext in SUPPORTED_IMAGE_EXTS:
            found.extend(image_dir.glob(f"*{ext}"))
            found.extend(image_dir.glob(f"*{ext.upper()}"))

        # Deduplicate (case-insensitive overlap on some FS)
        seen:   set  = set()
        unique: List[Path] = []
        for p in found:
            key = p.resolve()
            if key not in seen:
                seen.add(key)
                unique.append(p)

        # Natural sort: 1.jpg, 2.jpg, 10.jpg — NOT 1.jpg, 10.jpg, 2.jpg
        unique.sort(key=natural_sort_key)

        if not unique:
            Logger.error("No supported images found in images/")
            sys.exit(1)

        Logger.ok(f"Found {len(unique)} images")
        return unique

    @staticmethod
    def validate(images: List[Path]) -> List[Path]:
        Logger.info("Validating images with FFprobe...")
        valid:   List[Path] = []
        invalid: List[Path] = []

        for img in images:
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries",   "stream=width,height",
                "-of",             "csv=p=0",
                escape_ffmpeg(img),
            ]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
                if r.returncode == 0 and r.stdout.strip():
                    valid.append(img)
                else:
                    invalid.append(img)
            except (subprocess.TimeoutExpired, Exception):
                invalid.append(img)

        for p in invalid:
            Logger.warn(f"Skipping corrupt/unreadable image: {p.name}")

        if not valid:
            Logger.error("No valid images remain after validation")
            sys.exit(1)

        Logger.ok(f"{len(valid)} valid images ready")
        return valid


# ═════════════════════════════════════════════════════════════════════════════
# SCRIPT / TIMELINE LOADER
# ═════════════════════════════════════════════════════════════════════════════

class ScriptLoader:
    """
    Reads an optional script.txt that specifies per-image display durations.

    Format (one entry per line, comments with #):
        filename_or_index  duration_seconds  [optional description]

    Examples:
        001.jpg   5.0   Opening shot
        002.jpg   3.5
        003.jpg   8.0   Long establishing shot
        4         4.0   (index-based, 1-indexed)

    Images not listed keep the default calculated duration.
    Lines that cannot be parsed are warned and skipped.
    """

    @staticmethod
    def load(
        script_path: Path,
        images: List[Path],
        default_duration: float,
    ) -> Dict[int, float]:
        """Return {frame_index: duration} overrides."""
        overrides: Dict[int, float] = {}

        if not script_path.exists():
            return overrides

        Logger.info(f"Loading per-image durations from {script_path.name}")
        name_to_index = {p.name: i for i, p in enumerate(images)}

        with open(script_path, "r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, 1):
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    Logger.warn(f"script.txt line {lineno}: not enough columns — skipped")
                    continue
                key_str, dur_str = parts[0], parts[1]
                try:
                    dur = float(dur_str)
                except ValueError:
                    Logger.warn(f"script.txt line {lineno}: bad duration '{dur_str}' — skipped")
                    continue
                if dur <= 0:
                    Logger.warn(f"script.txt line {lineno}: duration must be > 0 — skipped")
                    continue

                # resolve key as filename or 1-based index
                idx: Optional[int] = None
                if key_str in name_to_index:
                    idx = name_to_index[key_str]
                else:
                    try:
                        n = int(key_str)
                        if 1 <= n <= len(images):
                            idx = n - 1
                    except ValueError:
                        pass

                if idx is None:
                    Logger.warn(
                        f"script.txt line {lineno}: '{key_str}' not found — skipped"
                    )
                    continue

                overrides[idx] = dur
                Logger.debug(f"  script override: image[{idx}] {images[idx].name} → {dur}s")

        Logger.ok(f"  {len(overrides)} duration overrides applied")
        return overrides


# ═════════════════════════════════════════════════════════════════════════════
# TIMELINE GENERATOR
# ═════════════════════════════════════════════════════════════════════════════

class TimelineGenerator:
    """Builds the ordered list of ImageFrame objects with precise timing."""

    @staticmethod
    def build(
        images:           List[Path],
        narration_secs:   float,
        duration_overrides: Dict[int, float],
    ) -> List[ImageFrame]:
        """
        If script.txt provides overrides for some images, those images use
        their specified duration.  Remaining images share the leftover time
        equally (with a minimum of 1 second).
        """
        n = len(images)

        # 1. Sum of fixed durations
        fixed_total = sum(duration_overrides.get(i, 0.0) for i in range(n) if i in duration_overrides)
        free_count  = n - len(duration_overrides)
        remaining   = max(0.0, narration_secs - fixed_total)

        default_dur = 1.0
        if free_count > 0:
            default_dur = max(1.0, remaining / free_count)

        Logger.info(
            f"Timeline: {n} frames — "
            f"{len(duration_overrides)} overridden, "
            f"{free_count} auto @ {default_dur:.2f}s each"
        )

        frames: List[ImageFrame] = []
        t = 0.0
        for i, path in enumerate(images):
            dur = duration_overrides.get(i, default_dur)
            frames.append(ImageFrame(path=path, index=i, start_time=t, duration=dur))
            t += dur

        Logger.ok(f"Total timeline duration: {t:.2f}s")
        return frames


# ═════════════════════════════════════════════════════════════════════════════
# DYNAMIC BATCH SIZER
# ═════════════════════════════════════════════════════════════════════════════

class BatchSizer:
    """
    Calculates a safe BATCH_SIZE for the current machine.

    Model
    -----
    Each image held in FFmpeg's internal buffer costs approximately:
        width × height × 3 bytes (raw RGB frame)
    Plus ~30 % FFmpeg processing overhead.
    We target staying under 700 MB total (leaving headroom in 2 GB device).
    """

    TARGET_RAM_BYTES: int = 700 * 1024 * 1024   # 700 MB

    @staticmethod
    def calculate(
        config:      VideoConfig,
        image_count: int,
    ) -> int:
        # User override takes priority
        if config.batch_size_override > 0:
            size = max(BATCH_MIN, min(config.batch_size_override, BATCH_MAX))
            Logger.info(f"Batch size: {size} (user override)")
            return size

        res_table = (
            RES_VERTICAL if config.aspect_ratio == AspectRatio.V9_16.value
            else RES_HORIZONTAL
        )
        w, h = res_table[config.resolution]

        bytes_per_frame   = w * h * 3          # raw RGB
        overhead_factor   = 1.30
        ram_per_frame     = int(bytes_per_frame * overhead_factor)

        cpu_cores = get_cpu_cores()

        # base: how many fit in RAM budget
        size = max(BATCH_MIN, min(
            BatchSizer.TARGET_RAM_BYTES // max(ram_per_frame, 1),
            BATCH_MAX,
        ))

        # clamp to number of images
        size = min(size, image_count)

        Logger.info(
            f"Batch size: {size}  "
            f"(RAM/frame≈{ram_per_frame//1024//1024} MB, "
            f"cores={cpu_cores}, res={w}×{h})"
        )
        return size


# ═════════════════════════════════════════════════════════════════════════════
# BATCH MANAGER
# ═════════════════════════════════════════════════════════════════════════════

class BatchManager:
    """Splits the timeline into RenderBatch objects."""

    @staticmethod
    def create(frames: List[ImageFrame], batch_size: int) -> List[RenderBatch]:
        batches: List[RenderBatch] = []
        for i in range(0, len(frames), batch_size):
            chunk = frames[i : i + batch_size]
            batches.append(RenderBatch(
                batch_id       = len(batches),
                frames         = chunk,
                start_time     = chunk[0].start_time,
                total_duration = sum(f.duration for f in chunk),
            ))
        Logger.info(f"Batches: {len(batches)}  ×  up to {batch_size} frames each")
        return batches


# ═════════════════════════════════════════════════════════════════════════════
# KEN BURNS EFFECT
# ═════════════════════════════════════════════════════════════════════════════

class KenBurns:
    """Generates deterministic-ish zoompan filter strings."""

    _DIRS: List[str] = [
        "center",
        "top_left",  "top_right",
        "bottom_left", "bottom_right",
        "left", "right", "top", "bottom",
    ]
    _COORDS: Dict[str, Tuple[str, str]] = {
        "center":       ("(iw-iw/zoom)/2",  "(ih-ih/zoom)/2"),
        "top_left":     ("0",               "0"),
        "top_right":    ("(iw-iw/zoom)",    "0"),
        "bottom_left":  ("0",               "(ih-ih/zoom)"),
        "bottom_right": ("(iw-iw/zoom)",    "(ih-ih/zoom)"),
        "left":         ("0",               "(ih-ih/zoom)/2"),
        "right":        ("(iw-iw/zoom)",    "(ih-ih/zoom)/2"),
        "top":          ("(iw-iw/zoom)/2",  "0"),
        "bottom":       ("(iw-iw/zoom)/2",  "(ih-ih/zoom)"),
    }

    def __init__(self, width: int, height: int, fps: int) -> None:
        self.width  = width
        self.height = height
        self.fps    = fps

    def build(self, duration: float, frame_index: int) -> str:
        """Build a zoompan filter; direction cycles with frame index."""
        import random as _rnd
        _rnd.seed(frame_index * 17 + 3)      # reproducible per-frame seed

        zoom = round(_rnd.uniform(KB_ZOOM_MIN, KB_ZOOM_MAX), 3)
        direction = self._DIRS[frame_index % len(self._DIRS)]
        x, y = self._COORDS[direction]
        d = max(1, int(duration * self.fps))

        return (
            f"zoompan="
            f"z='min(zoom+{KB_ZOOM_STEP},{zoom})':"
            f"x='{x}':y='{y}':"
            f"d={d}:s={self.width}x{self.height}:fps={self.fps}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# SUBTITLE HANDLER
# ═════════════════════════════════════════════════════════════════════════════

class SubtitleHandler:
    """
    Locates subtitle file and builds the FFmpeg filter.

    Supports
    --------
    - .srt  — rendered via libavfilter subtitles filter with ASS force_style
    - .ass  — native ASS, full animation / karaoke / highlighting supported

    Styles (config.subtitle_style)
    ------
    "default"   — white text, black outline, bottom-centred
    "minimal"   — smaller, semi-transparent, no shadow
    "dramatic"  — larger, yellow text, heavier outline
    """

    _STYLES: Dict[str, str] = {
        "default": (
            "FontName=DejaVu Sans,FontSize=24,"
            "PrimaryColour=&H00FFFFFF,"    # white
            "OutlineColour=&H00000000,"    # black
            "BackColour=&H80000000,"       # semi-transparent black bg
            "Bold=0,Italic=0,"
            "Outline=2,Shadow=1,"
            "Alignment=2,"                 # bottom-centre
            "MarginL=20,MarginR=20,MarginV=40"
        ),
        "minimal": (
            "FontName=DejaVu Sans,FontSize=18,"
            "PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,"
            "BackColour=&H40000000,"
            "Bold=0,Italic=0,"
            "Outline=1,Shadow=0,"
            "Alignment=2,"
            "MarginL=20,MarginR=20,MarginV=30"
        ),
        "dramatic": (
            "FontName=DejaVu Sans Bold,FontSize=30,"
            "PrimaryColour=&H0000FFFF,"    # yellow
            "OutlineColour=&H00000000,"
            "BackColour=&HA0000000,"
            "Bold=1,Italic=0,"
            "Outline=3,Shadow=2,"
            "Alignment=2,"
            "MarginL=20,MarginR=20,MarginV=50"
        ),
    }

    @staticmethod
    def find(project_dir: Path) -> Optional[Path]:
        for name in ("subtitles.ass", "subtitles.srt"):   # .ass preferred
            p = project_dir / name
            if p.is_file():
                Logger.ok(f"Subtitles: {name}")
                return p
        Logger.debug("No subtitle file found")
        return None

    @classmethod
    def build_filter(
        cls,
        path: Optional[Path],
        style: str,
        enable: bool,
    ) -> Optional[str]:
        if not enable or path is None:
            return None

        esc    = escape_subtitle_path(path)
        chosen = cls._STYLES.get(style, cls._STYLES["default"])

        if path.suffix.lower() == ".ass":
            # Native ASS: karaoke, animation, per-line effects all work
            return f"ass='{esc}'"
        else:
            # SRT with forced ASS styling
            return f"subtitles='{esc}':force_style='{chosen}'"


# ═════════════════════════════════════════════════════════════════════════════
# AUDIO MIXER
# ═════════════════════════════════════════════════════════════════════════════

class AudioMixer:
    """Constructs FFmpeg audio filter graphs."""

    @staticmethod
    def build(
        config:          VideoConfig,
        narration_idx:   int,
        music_idx:       Optional[int],
    ) -> str:
        """
        Returns the audio portion of -filter_complex ending at [finalaudio].

        If music is present: mix narration (primary) + music (ducked).
        Otherwise: normalise narration only.
        """
        norm = "loudnorm=I=-16:TP=-1.5:LRA=11," if config.audio_normalization else ""

        if not config.enable_music or music_idx is None:
            return (
                f"[{narration_idx}:a]"
                f"aresample=48000,{norm}aformat=sample_rates=48000"
                "[finalaudio]"
            )

        vol  = config.music_volume
        return (
            # music: fade in/out, volume reduce
            f"[{music_idx}:a]"
            f"aresample=48000,"
            f"volume={vol},"
            f"afade=t=in:st=0:d=2,"
            f"afade=t=out:st=999999:d=3"
            "[music];"
            # voice: normalise + ensure correct format
            f"[{narration_idx}:a]"
            f"aresample=48000,{norm}aformat=sample_rates=48000"
            "[voice];"
            # mix voice dominant, music as bed
            "[voice][music]"
            "amix=inputs=2:weights='1 0.30':duration=first"
            "[finalaudio]"
        )


# ═════════════════════════════════════════════════════════════════════════════
# FILTER GRAPH BUILDER
# ═════════════════════════════════════════════════════════════════════════════

class FilterGraph:
    """
    Constructs the complete -filter_complex string for one render batch.

    Graph stages per frame
    ----------------------
    1. scale + crop           → [scaled{i}]
    2. Ken Burns  OR  setpts  → [video{i}]
    3. xfade chain            → [videoout]
    4. audio mix              → [finalaudio]
    5. subtitle overlay       (appended after -vf map if needed)
    """

    def __init__(
        self,
        config:   VideoConfig,
        width:    int,
        height:   int,
        kb:       KenBurns,
    ) -> None:
        self.config = config
        self.width  = width
        self.height = height
        self.kb     = kb

    def build(
        self,
        batch:         RenderBatch,
        audio_idx:     int,
        music_idx:     Optional[int],
    ) -> str:
        parts: List[str] = []

        # ── per-frame: scale → ken burns / static ─────────────────────────
        for local_i, frame in enumerate(batch.frames):
            global_i = frame.index

            # scale + fill-crop to exact output resolution
            parts.append(
                f"[{local_i}:v]"
                f"scale={self.width}:{self.height}:"
                f"force_original_aspect_ratio=increase,"
                f"crop={self.width}:{self.height},setsar=1"
                f"[scaled{local_i}]"
            )

            if self.config.enable_ken_burns:
                kb_filter = self.kb.build(frame.duration, global_i)
                parts.append(
                    f"[scaled{local_i}]{kb_filter}[video{local_i}]"
                )
            else:
                # static: hold frame at correct fps
                parts.append(
                    f"[scaled{local_i}]"
                    f"fps={self.config.fps}"
                    f"[video{local_i}]"
                )

        # ── xfade transition chain ─────────────────────────────────────────
        n = len(batch.frames)
        if n == 1:
            parts.append(f"[video0]null[videoout]")
        else:
            prev_label = "[video0]"
            for li in range(1, n):
                is_last  = li == n - 1
                out      = "[videoout]" if is_last else f"[xf{li}]"
                # offset relative to batch start
                rel_off  = batch.frames[li].start_time - batch.start_time
                offset   = max(0.0, rel_off - self.config.fade_duration)
                parts.append(
                    f"{prev_label}[video{li}]"
                    f"xfade=transition=fade:"
                    f"duration={self.config.fade_duration:.3f}:"
                    f"offset={offset:.3f}"
                    f"{out}"
                )
                prev_label = out

        # ── audio ─────────────────────────────────────────────────────────
        audio_graph = AudioMixer.build(self.config, audio_idx, music_idx)
        parts.append(audio_graph)

        return ";".join(parts)


# ═════════════════════════════════════════════════════════════════════════════
# FFMPEG COMMAND BUILDER
# ═════════════════════════════════════════════════════════════════════════════

class FFmpegCommandBuilder:
    """
    Assembles the complete FFmpeg argv list for rendering one batch.

    Output: batch MP4 with H.264 video + AAC audio, no subtitle burn-in
    (subtitles are handled at concatenation or via a second pass).
    """

    def __init__(
        self,
        config:   VideoConfig,
        encoder:  EncoderProfile,
        width:    int,
        height:   int,
    ) -> None:
        self.config  = config
        self.encoder = encoder
        self.width   = width
        self.height  = height
        self.kb      = KenBurns(width, height, config.fps)
        self.fg      = FilterGraph(config, width, height, self.kb)

    def build(
        self,
        batch:         RenderBatch,
        audio_path:    Path,
        music_path:    Optional[Path],
        output_path:   Path,
        subtitle_path: Optional[Path],
    ) -> List[str]:

        cmd: List[str] = ["ffmpeg", "-y"]

        # ── image inputs ──────────────────────────────────────────────────
        for frame in batch.frames:
            cmd += [
                "-loop", "1",
                "-t",    f"{frame.duration:.3f}",
                "-i",    escape_ffmpeg(frame.path),
            ]

        narration_idx = len(batch.frames)
        music_idx: Optional[int] = None

        # ── narration input ───────────────────────────────────────────────
        cmd += ["-i", escape_ffmpeg(audio_path)]

        # ── music input (stream-loop so it covers full batch) ─────────────
        if self.config.enable_music and music_path and music_path.is_file():
            music_idx = narration_idx + 1
            cmd += ["-stream_loop", "-1", "-i", escape_ffmpeg(music_path)]

        # ── filter_complex ────────────────────────────────────────────────
        fg_str = self.fg.build(batch, narration_idx, music_idx)
        cmd += ["-filter_complex", fg_str]

        # ── output map ────────────────────────────────────────────────────
        cmd += ["-map", "[videoout]", "-map", "[finalaudio]"]

        # ── video codec ───────────────────────────────────────────────────
        cmd += ["-c:v", self.encoder.encoder_id]
        if self.encoder.preset_flag:
            cmd += ["-preset", self.encoder.preset_flag]
        if self.encoder.crf_flag:
            cmd += ["-crf", self.encoder.crf_flag]
        cmd += ["-pix_fmt", self.config.pix_fmt]
        if self.encoder.extra_flags:
            cmd += self.encoder.extra_flags
        if self.config.threads > 0:
            cmd += ["-threads", str(self.config.threads)]

        # ── audio codec ───────────────────────────────────────────────────
        cmd += ["-c:a", "aac", "-b:a", self.config.audio_bitrate]

        # ── container / output ────────────────────────────────────────────
        cmd += [
            "-r",         str(self.config.fps),
            "-movflags",  "+faststart",
        ]

        # Subtitle burn-in (optional, batch-level)
        if subtitle_path:
            sub_f = SubtitleHandler.build_filter(
                subtitle_path,
                self.config.subtitle_style,
                self.config.enable_subtitles,
            )
            if sub_f:
                cmd += ["-vf", sub_f]

        cmd.append(escape_ffmpeg(output_path))
        Logger.debug(f"FFmpeg cmd: {' '.join(cmd[:12])} ...")
        return cmd


# ═════════════════════════════════════════════════════════════════════════════
# FFMPEG EXECUTOR
# ═════════════════════════════════════════════════════════════════════════════

class FFmpegExecutor:
    """
    Executes an FFmpeg command with real-time progress reporting.
    Returns True on success, False on failure.
    """

    @staticmethod
    def run(cmd: List[str], expected_duration: float) -> bool:
        Logger.info(f"Rendering {expected_duration:.1f}s ...")
        t0 = time.time()

        try:
            proc = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                universal_newlines=True,
                bufsize=1,
            )
        except FileNotFoundError:
            Logger.error("ffmpeg binary not found")
            return False
        except Exception as exc:
            Logger.error(f"Failed to launch FFmpeg: {exc}")
            return False

        last_pct = -1

        while True:
            line = proc.stderr.readline()
            if not line:
                if proc.poll() is not None:
                    break
                time.sleep(0.05)
                continue

            elapsed = parse_ffmpeg_time(line)
            if elapsed is not None and expected_duration > 0:
                pct = min(100, int(elapsed / expected_duration * 100))
                if pct != last_pct:
                    last_pct = pct
                    wall     = time.time() - t0
                    if pct > 0:
                        eta = wall / (pct / 100.0) - wall
                        print(
                            f"\r  Progress {pct:3d}%  "
                            f"elapsed {wall:5.0f}s  "
                            f"ETA {eta:5.0f}s     ",
                            end="", flush=True,
                        )

        print()   # newline after progress
        rc = proc.wait()

        if rc != 0:
            Logger.error(f"FFmpeg exited with code {rc}")
            return False

        wall = time.time() - t0
        Logger.ok(f"Batch done in {wall:.1f}s")
        return True


# ═════════════════════════════════════════════════════════════════════════════
# CHECKPOINT MANAGER
# ═════════════════════════════════════════════════════════════════════════════

class CheckpointManager:
    """
    Full persistence of render state for reliable resume after interruption.

    Persisted fields
    ----------------
    build_version      — detects incompatible checkpoint format
    ffmpeg_version     — informational
    timestamp          — ISO-8601 of last save
    project_hash       — detects if images changed between runs
    total_frames       — total image count
    total_batches      — number of batches planned
    completed_batches  — list of batch_ids that produced a valid MP4
    last_frame_index   — highest frame index successfully rendered
    batch_output_files — {str(batch_id): str(abs_path)}
    config_snapshot    — copy of VideoConfig at checkpoint creation time
    """

    def __init__(self, project_dir: Path) -> None:
        self._path = project_dir / CHECKPOINT_FILENAME
        self._cp:  Optional[BuildCheckpoint] = None

    # ── public interface ──────────────────────────────────────────────────

    def load(self) -> Optional[BuildCheckpoint]:
        if not self._path.exists():
            return None
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                d = json.load(fh)
            cp = BuildCheckpoint(
                build_version      = d.get("build_version", ""),
                ffmpeg_version     = d.get("ffmpeg_version", ""),
                timestamp          = d.get("timestamp", ""),
                project_hash       = d.get("project_hash", ""),
                total_frames       = d.get("total_frames", 0),
                total_batches      = d.get("total_batches", 0),
                completed_batches  = d.get("completed_batches", []),
                last_frame_index   = d.get("last_frame_index", -1),
                batch_output_files = d.get("batch_output_files", {}),
                config_snapshot    = d.get("config_snapshot", {}),
            )
            if cp.build_version != VERSION:
                Logger.warn(
                    f"Checkpoint version {cp.build_version} ≠ current {VERSION} — ignoring"
                )
                return None
            self._cp = cp
            Logger.ok(
                f"Checkpoint loaded: {len(cp.completed_batches)}/{cp.total_batches} batches done"
            )
            return cp
        except Exception as exc:
            Logger.warn(f"Checkpoint corrupted ({exc}) — starting fresh")
            return None

    def initialise(
        self,
        images:   List[Path],
        batches:  List[RenderBatch],
        config:   VideoConfig,
    ) -> None:
        """Create a fresh checkpoint before rendering starts."""
        self._cp = BuildCheckpoint(
            build_version      = VERSION,
            ffmpeg_version     = SystemInfo.get_ffmpeg_version(),
            timestamp          = datetime.now().isoformat(),
            project_hash       = project_hash(images),
            total_frames       = len(images),
            total_batches      = len(batches),
            completed_batches  = [],
            last_frame_index   = -1,
            batch_output_files = {},
            config_snapshot    = asdict(config),
        )
        self._save()

    def mark_complete(self, batch: RenderBatch, output_path: Path) -> None:
        assert self._cp is not None
        bid = batch.batch_id
        if bid not in self._cp.completed_batches:
            self._cp.completed_batches.append(bid)
        self._cp.last_frame_index   = batch.frames[-1].index
        self._cp.batch_output_files[str(bid)] = str(output_path)
        self._cp.timestamp          = datetime.now().isoformat()
        self._save()

    def is_complete(self, batch_id: int) -> bool:
        return (
            self._cp is not None
            and batch_id in self._cp.completed_batches
        )

    def get_output_path(self, batch_id: int) -> Optional[Path]:
        if self._cp is None:
            return None
        p = self._cp.batch_output_files.get(str(batch_id))
        return Path(p) if p else None

    def clear(self) -> None:
        if self._path.exists():
            self._path.unlink()
        self._cp = None
        Logger.debug("Checkpoint cleared")

    # ── private ───────────────────────────────────────────────────────────

    def _save(self) -> None:
        assert self._cp is not None
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(asdict(self._cp), fh, indent=2)
        Logger.debug(f"Checkpoint saved ({len(self._cp.completed_batches)} complete)")


# ═════════════════════════════════════════════════════════════════════════════
# VIDEO CONCATENATOR
# ═════════════════════════════════════════════════════════════════════════════

class Concatenator:
    """Joins rendered batch MP4s into a single final video using concat demuxer."""

    @staticmethod
    def run(videos: List[Path], output: Path, temp_dir: Path) -> None:
        Logger.section("Concatenation")

        if not videos:
            Logger.error("No batch videos to concatenate")
            sys.exit(1)

        if len(videos) == 1:
            shutil.copy2(videos[0], output)
            Logger.ok(f"Single batch — copied to {output.name}")
            return

        concat_txt = temp_dir / "concat.txt"
        with open(concat_txt, "w", encoding="utf-8") as fh:
            for v in videos:
                fh.write(f"file '{escape_ffmpeg(v)}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f",    "concat",
            "-safe", "0",
            "-i",    escape_ffmpeg(concat_txt),
            "-c",    "copy",
            "-movflags", "+faststart",
            escape_ffmpeg(output),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            Logger.ok(f"Concatenated {len(videos)} batches → {output.name}")
        except subprocess.CalledProcessError as exc:
            Logger.error(f"Concatenation failed: {exc}")
            sys.exit(1)


# ═════════════════════════════════════════════════════════════════════════════
# OUTPUT VALIDATOR
# ═════════════════════════════════════════════════════════════════════════════

class OutputValidator:
    """Verifies the final MP4 is present, non-trivial, and well-formed."""

    MIN_SIZE_BYTES: int = 100 * 1024    # 100 KB

    @staticmethod
    def validate(path: Path) -> bool:
        if not path.exists():
            Logger.error(f"Output file not found: {path}")
            return False
        size = path.stat().st_size
        if size < OutputValidator.MIN_SIZE_BYTES:
            Logger.error(f"Output suspiciously small: {size} bytes")
            return False

        # Quick stream check via FFprobe
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_type",
            "-of",           "default=noprint_wrappers=1",
            escape_ffmpeg(path),
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            has_video = "codec_type=video" in r.stdout
            has_audio = "codec_type=audio" in r.stdout
            if not has_video or not has_audio:
                Logger.error(f"Output missing streams (video={has_video}, audio={has_audio})")
                return False
        except Exception as exc:
            Logger.warn(f"FFprobe validation skipped: {exc}")

        mb = size / 1024 / 1024
        Logger.ok(f"Output validated: {path.name}  ({mb:.1f} MB)")
        return True


# ═════════════════════════════════════════════════════════════════════════════
# BATCH RENDERER  (the core loop)
# ═════════════════════════════════════════════════════════════════════════════

class BatchRenderer:
    """
    Iterates over all RenderBatch objects, renders each to a temp MP4,
    respects checkpoints for resume, and cleans up immediately after each batch.
    """

    def __init__(
        self,
        config:      VideoConfig,
        encoder:     EncoderProfile,
        width:       int,
        height:      int,
        project_dir: Path,
        temp_dir:    Path,
        checkpoint:  CheckpointManager,
        narration:   Path,
        music:       Optional[Path],
        subtitle:    Optional[Path],
        dry_run:     bool = False,
    ) -> None:
        self.config       = config
        self.cmd_builder  = FFmpegCommandBuilder(config, encoder, width, height)
        self.project_dir  = project_dir
        self.temp_dir     = temp_dir
        self.checkpoint   = checkpoint
        self.narration    = narration
        self.music        = music
        self.subtitle     = subtitle
        self.dry_run      = dry_run

    def render_all(self, batches: List[RenderBatch]) -> List[Path]:
        """
        Returns ordered list of per-batch MP4 paths.
        Raises SystemExit on unrecoverable failure.
        """
        Logger.section("Rendering")
        output_videos: List[Path] = []
        total = len(batches)

        for batch in batches:
            bid = batch.batch_id

            # ── resume: skip already-done batches ─────────────────────────
            if self.checkpoint.is_complete(bid):
                saved = self.checkpoint.get_output_path(bid)
                if saved and saved.exists():
                    Logger.info(
                        f"[{bid+1}/{total}] Batch {bid} — skipping (checkpoint)"
                    )
                    output_videos.append(saved)
                    continue
                else:
                    Logger.warn(
                        f"[{bid+1}/{total}] Batch {bid} — checkpoint exists "
                        f"but file missing, re-rendering"
                    )

            Logger.info(
                f"[{bid+1}/{total}] Batch {bid}  "
                f"({len(batch.frames)} frames  "
                f"{batch.total_duration:.1f}s)"
            )

            if self.dry_run:
                Logger.info("  [dry-run] would render this batch")
                output_videos.append(
                    self.temp_dir / f"batch_{bid:04d}.mp4"
                )
                continue

            # ── extract narration segment for this batch ───────────────────
            audio_seg = self.temp_dir / f"audio_{bid:04d}.m4a"
            try:
                AudioUtils.extract_segment(
                    self.narration,
                    audio_seg,
                    batch.start_time,
                    batch.total_duration,
                    self.config.audio_bitrate,
                )
            except Exception as exc:
                Logger.error(f"Audio extraction failed for batch {bid}: {exc}")
                sys.exit(1)

            # ── build FFmpeg command ───────────────────────────────────────
            batch_out = self.temp_dir / f"batch_{bid:04d}.mp4"
            cmd = self.cmd_builder.build(
                batch        = batch,
                audio_path   = audio_seg,
                music_path   = self.music,
                output_path  = batch_out,
                subtitle_path= self.subtitle,
            )

            # ── execute ───────────────────────────────────────────────────
            ok = FFmpegExecutor.run(cmd, batch.total_duration)

            # ── immediate cleanup of audio segment ────────────────────────
            if audio_seg.exists():
                audio_seg.unlink()

            if not ok:
                Logger.error(f"Batch {bid} render failed — aborting")
                sys.exit(1)

            # ── verify batch output ───────────────────────────────────────
            if not batch_out.exists() or batch_out.stat().st_size < 1024:
                Logger.error(f"Batch {bid} output missing or empty")
                sys.exit(1)

            # ── checkpoint ────────────────────────────────────────────────
            self.checkpoint.mark_complete(batch, batch_out)
            output_videos.append(batch_out)

            # ── storage check after each batch ────────────────────────────
            free = get_free_bytes(self.temp_dir)
            if free < MIN_FREE_STORAGE_BYTES:
                Logger.warn(
                    f"Low storage: {free // 1024 // 1024} MB free after batch {bid}"
                )

        return output_videos


# ═════════════════════════════════════════════════════════════════════════════
# RESOLUTION HELPER
# ═════════════════════════════════════════════════════════════════════════════

def get_resolution(config: VideoConfig) -> Tuple[int, int]:
    table = (
        RES_VERTICAL if config.aspect_ratio == AspectRatio.V9_16.value
        else RES_HORIZONTAL
    )
    return table[config.resolution]


# ═════════════════════════════════════════════════════════════════════════════
# DRY-RUN REPORT
# ═════════════════════════════════════════════════════════════════════════════

def dry_run_report(
    config:   VideoConfig,
    images:   List[Path],
    frames:   List[ImageFrame],
    batches:  List[RenderBatch],
    narration: Path,
    narration_secs: float,
    encoder:  EncoderProfile,
    width:    int,
    height:   int,
    batch_size: int,
) -> None:
    Logger.section("DRY RUN REPORT — no rendering performed")
    Logger.info(f"Images         : {len(images)}")
    Logger.info(f"Total frames   : {len(frames)}")
    Logger.info(f"Narration      : {narration.name}  ({narration_secs:.2f}s)")
    Logger.info(f"Resolution     : {width}×{height}  ({config.aspect_ratio})")
    Logger.info(f"FPS            : {config.fps}")
    Logger.info(f"Encoder        : {encoder.encoder_id}")
    Logger.info(f"Preset         : {encoder.preset_flag or 'n/a'}")
    Logger.info(f"CRF            : {encoder.crf_flag or 'n/a'}")
    Logger.info(f"Ken Burns      : {config.enable_ken_burns}")
    Logger.info(f"Music          : {config.enable_music}")
    Logger.info(f"Subtitles      : {config.enable_subtitles}")
    Logger.info(f"Batch size     : {batch_size}  ({len(batches)} batches)")
    Logger.info(f"Output file    : {config.output_filename}")
    Logger.info("")
    Logger.info("Timeline preview (first 10 frames):")
    for f in frames[:10]:
        Logger.info(f"  [{f.index:04d}] {f.path.name:<35} {f.start_time:8.2f}s  +{f.duration:.2f}s")
    if len(frames) > 10:
        Logger.info(f"  ... and {len(frames)-10} more frames")
    Logger.ok("Dry-run complete — all assets validated successfully")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═════════════════════════════════════════════════════════════════════════════

class Pipeline:
    """
    Orchestrates the full build in 9 phases:

    1. Environment check
    2. Project validation
    3. Config loading
    4. Asset discovery
    5. Timeline generation
    6. Batch planning
    7. Rendering (with checkpoint resume)
    8. Concatenation
    9. Validation + cleanup
    """

    def __init__(self, project_dir: Path, args: argparse.Namespace) -> None:
        self.project_dir = project_dir.resolve()
        self.args        = args

    # ── entry point ───────────────────────────────────────────────────────

    def run(self) -> int:
        try:
            return self._run()
        except KeyboardInterrupt:
            print()
            Logger.warn("Interrupted by user — checkpoint saved, run again to resume")
            return 130
        except SystemExit as exc:
            return int(exc.code) if exc.code is not None else 1
        except Exception as exc:
            Logger.error(f"Unexpected error: {exc}")
            raise

    # ── internal ──────────────────────────────────────────────────────────

    def _run(self) -> int:

        # ── 0. logging setup ─────────────────────────────────────────────
        Logger.configure(self.project_dir / LOG_FILENAME)

        # ── 1. environment ───────────────────────────────────────────────
        SystemInfo.verify_ffmpeg()
        SystemInfo.report()

        # ── 2. validation ────────────────────────────────────────────────
        ProjectValidator.validate(self.project_dir)

        # ── clean mode ───────────────────────────────────────────────────
        if self.args.clean:
            self._clean()
            return 0

        # ── 3. config ────────────────────────────────────────────────────
        config = ConfigLoader.load(self.project_dir)
        Logger.info(f"Resolution: {config.resolution}  Aspect: {config.aspect_ratio}")

        width, height = get_resolution(config)

        # ── 4. asset discovery ───────────────────────────────────────────
        Logger.section("Asset Discovery")
        images    = ImageDiscovery.discover(self.project_dir / "images")
        images    = ImageDiscovery.validate(images)

        narration = AudioUtils.find_narration(self.project_dir)
        narr_secs = AudioUtils.get_duration(narration)

        music: Optional[Path] = None
        if config.enable_music:
            mp = self.project_dir / "music.mp3"
            if mp.is_file():
                music = mp
                Logger.ok(f"Music: {mp.name}")

        subtitle = SubtitleHandler.find(self.project_dir)

        # ── 5. timeline ──────────────────────────────────────────────────
        Logger.section("Timeline")
        script_path  = self.project_dir / SCRIPT_FILENAME
        overrides    = ScriptLoader.load(script_path, images, narr_secs / len(images))
        frames       = TimelineGenerator.build(images, narr_secs, overrides)

        # ── 6. batch planning ────────────────────────────────────────────
        Logger.section("Batch Planning")
        batch_size = BatchSizer.calculate(config, len(images))
        batches    = BatchManager.create(frames, batch_size)

        encoder = EncoderDetector.detect(config.encoder, config)

        # ── dry-run exit ─────────────────────────────────────────────────
        if self.args.dry_run:
            dry_run_report(
                config, images, frames, batches,
                narration, narr_secs, encoder, width, height, batch_size,
            )
            return 0

        # ── temp directory ───────────────────────────────────────────────
        if config.temp_directory:
            temp_dir = Path(config.temp_directory)
            temp_dir.mkdir(parents=True, exist_ok=True)
        else:
            temp_dir = Path(tempfile.mkdtemp(prefix=TEMP_PREFIX))
        Logger.info(f"Temp dir: {temp_dir}")

        # ── 7. checkpoint / resume ───────────────────────────────────────
        cp = CheckpointManager(self.project_dir)

        resume_mode = getattr(ResumeMode, config.resume_mode.upper(), ResumeMode.AUTO)
        if self.args.resume:
            resume_mode = ResumeMode.FORCE

        existing = cp.load()

        if resume_mode == ResumeMode.NEVER and existing:
            Logger.info("Resume mode=never — discarding existing checkpoint")
            cp.clear()
            existing = None

        if resume_mode == ResumeMode.FORCE and existing is None:
            Logger.error("--resume requested but no checkpoint found")
            return 1

        if existing is None:
            cp.initialise(images, batches, config)
        else:
            # Detect if images changed since checkpoint
            ph = project_hash(images)
            if ph != existing.project_hash:
                Logger.warn(
                    "Project images changed since last checkpoint — starting fresh"
                )
                cp.initialise(images, batches, config)

        # ── 8. rendering ─────────────────────────────────────────────────
        renderer = BatchRenderer(
            config       = config,
            encoder      = encoder,
            width        = width,
            height       = height,
            project_dir  = self.project_dir,
            temp_dir     = temp_dir,
            checkpoint   = cp,
            narration    = narration,
            music        = music,
            subtitle     = subtitle,
            dry_run      = False,
        )

        batch_videos = renderer.render_all(batches)

        # ── 9. concatenation ─────────────────────────────────────────────
        output_path = self.project_dir / config.output_filename
        Concatenator.run(batch_videos, output_path, temp_dir)

        # ── 10. final validation ─────────────────────────────────────────
        if not OutputValidator.validate(output_path):
            Logger.error("Output validation failed")
            return 1

        # ── 11. cleanup ──────────────────────────────────────────────────
        cp.clear()

        if not config.keep_temp:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                Logger.ok("Temp files cleaned")
            except Exception as exc:
                Logger.warn(f"Temp cleanup failed: {exc}")

        # ── final report ─────────────────────────────────────────────────
        self._final_report(output_path, narr_secs, len(images), batches)
        return 0

    def _clean(self) -> None:
        """Remove checkpoint and temp directories."""
        Logger.section("Clean")
        cp_path = self.project_dir / CHECKPOINT_FILENAME
        if cp_path.exists():
            cp_path.unlink()
            Logger.ok("Checkpoint removed")
        else:
            Logger.info("No checkpoint to remove")

        for d in Path(tempfile.gettempdir()).glob(f"{TEMP_PREFIX}*"):
            try:
                shutil.rmtree(d)
                Logger.ok(f"Removed temp dir: {d}")
            except Exception as exc:
                Logger.warn(f"Could not remove {d}: {exc}")

        Logger.ok("Clean complete")

    @staticmethod
    def _final_report(
        output: Path,
        duration: float,
        image_count: int,
        batches: List[RenderBatch],
    ) -> None:
        mb = output.stat().st_size / 1024 / 1024
        Logger.section("Build Complete")
        Logger.info(f"Output     : {output}")
        Logger.info(f"Size       : {mb:.1f} MB")
        Logger.info(f"Duration   : {duration:.2f}s  ({seconds_to_hms(duration)})")
        Logger.info(f"Images     : {image_count}")
        Logger.info(f"Batches    : {len(batches)}")
        Logger.ok("✓ Documentary video built successfully")


# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="build_video.py",
        description="Production Documentary Video Builder — Android Termux / ARM64",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
  python build_video.py
  python build_video.py --project /sdcard/my_doc
  python build_video.py --dry-run
  python build_video.py --resume
  python build_video.py --clean
  DEBUG=1 python build_video.py --project ./my_doc

Config keys (config.json)
--------------------------
  aspect_ratio, resolution, fps, crf, preset, pix_fmt,
  encoder, threads, enable_ken_burns, fade_duration,
  audio_bitrate, audio_normalization, enable_music, music_volume,
  enable_subtitles, subtitle_style,
  output_filename, temp_directory, keep_temp,
  batch_size_override, resume_mode
        """,
    )
    p.add_argument(
        "--project", type=Path, default=Path("."),
        help="Path to project directory (default: current directory)",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Validate all assets and print plan; do not render",
    )
    p.add_argument(
        "--resume", action="store_true",
        help="Force resume from existing checkpoint (error if none found)",
    )
    p.add_argument(
        "--clean", action="store_true",
        help="Remove checkpoint and temp files then exit",
    )
    p.add_argument(
        "--version", action="version", version=f"build_video.py {VERSION}",
    )
    return p


# ═════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

def main() -> int:
    parser = build_parser()
    args   = parser.parse_args()

    project_dir = args.project.resolve()
    if not project_dir.exists():
        print(f"[ERROR] Project directory not found: {project_dir}", file=sys.stderr)
        return 1

    return Pipeline(project_dir, args).run()


if __name__ == "__main__":
    sys.exit(main())
