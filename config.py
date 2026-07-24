import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Prepend the virtual environment's bin directory to the PATH variable.
# This ensures that pydub and subprocesses can find local ffmpeg/ffprobe binaries.
venv_bin_dir = os.path.dirname(sys.executable)
if os.path.isdir(venv_bin_dir):
    os.environ["PATH"] = venv_bin_dir + os.path.pathsep + os.environ["PATH"]

# Project Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHORTS_DIR = os.path.join(BASE_DIR, "shorts")

# API Keys & Credentials
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
ASSEMBLYAI_API_KEY = os.environ.get("ASSEMBLYAI_API_KEY")

# Gemini AI Model Configuration
GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.0-flash")

# Video Settings
DEFAULT_WIDTH = 576
DEFAULT_HEIGHT = 1024
DEFAULT_FPS = 30
DEFAULT_FADE_DURATION_MS = 300  # Duration of the cross-fade between images in milliseconds

# Text-to-Speech Settings
DEFAULT_TTS_VOICE = "en-US-GuyNeural"
DEFAULT_TTS_RATE = "+10%"

# Caption/Subtitle styling defaults for FFmpeg subtitles filter
CAPTION_ALIGNMENT = 2    # 2 is bottom center, 1 is bottom left, 6 is top center
CAPTION_MARGIN_V = 150   # Vertical margin from the edge
CAPTION_FONT_SIZE = 30

def get_ffmpeg_binaries():
    """Locate and return paths to ffmpeg and ffprobe, preferring local virtualenv installation."""
    venv_bin_dir = os.path.dirname(sys.executable)
    
    ffmpeg_name = "ffmpeg.exe" if os.name == 'nt' else "ffmpeg"
    ffprobe_name = "ffprobe.exe" if os.name == 'nt' else "ffprobe"
    
    local_ffmpeg = os.path.join(venv_bin_dir, ffmpeg_name)
    local_ffprobe = os.path.join(venv_bin_dir, ffprobe_name)
    
    ffmpeg_bin = local_ffmpeg if (os.path.isfile(local_ffmpeg) and os.access(local_ffmpeg, os.X_OK)) else "ffmpeg"
    ffprobe_bin = local_ffprobe if (os.path.isfile(local_ffprobe) and os.access(local_ffprobe, os.X_OK)) else "ffprobe"
    
    return ffmpeg_bin, ffprobe_bin

def validate_environment():
    """Prints warning or logs if API keys are missing/exhausted."""
    warnings = []
    if not GEMINI_API_KEY:
        warnings.append("GEMINI_API_KEY/GOOGLE_API_KEY is not set in the environment. Script generation will fail unless running with --offline.")
    if not ASSEMBLYAI_API_KEY:
        warnings.append("ASSEMBLYAI_API_KEY is not set in the environment. Word-level caption generation will fail.")
    return warnings
