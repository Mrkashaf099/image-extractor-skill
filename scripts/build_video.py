#!/usr/bin/env python3
"""Build a final MP4 from downloaded images, narration and optional subtitles/music.

Pipeline:
1. Read images/ directory
2. Read narration.wav
3. Create slideshow with FFmpeg
4. Add Ken Burns zoom/pan
5. Overlay subtitles if subtitles.srt exists
6. Mix background music if music.mp3 exists
7. Export final_video.mp4

TODO:
- Animated captions
- Sticker/icon overlays
- Intro/outro
- Lower thirds
- Progress bar
- Automatic timing from narration length
"""

from pathlib import Path
import subprocess
import shutil
import sys

if shutil.which('ffmpeg') is None:
    sys.exit('FFmpeg is not installed. Install with: pkg install ffmpeg')

print('Video builder scaffold created. Full FFmpeg pipeline will be implemented in future commits.')
