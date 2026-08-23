import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Input & Output default directories
DEFAULT_SOURCE_DIR = os.path.join(BASE_DIR, "video")
DEFAULT_DEST_DIR = os.path.join(BASE_DIR, "Tiktok_Builder_Output")

# FFmpeg binary path
BIN_DIR = os.path.join(BASE_DIR, "bin")
FFMPEG_PATH = os.path.join(BIN_DIR, "ffmpeg.exe") if os.name == 'nt' else "ffmpeg"
FFPROBE_PATH = os.path.join(BIN_DIR, "ffprobe.exe") if os.name == 'nt' else "ffprobe"

# Default font
DEFAULT_FONT_PATH = os.path.join(BASE_DIR, "Poppins-Bold.ttf")

# Settings and History storage
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
ACCOUNTS_FILE = os.path.join(BASE_DIR, "accounts.json")
ACCOUNTS_EXAMPLE_FILE = os.path.join(BASE_DIR, "accounts.example.json")
HISTORY_FILE = os.path.join(BASE_DIR, "edit_history.json")

# Ensure required directories exist
for path in [DEFAULT_SOURCE_DIR, DEFAULT_DEST_DIR, BIN_DIR]:
    os.makedirs(path, exist_ok=True)
