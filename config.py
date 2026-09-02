import os
import sys

# Hỗ trợ PyInstaller (lấy thư mục chứa file .exe)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. PHÂN TẦNG DỮ LIỆU CẤU HÌNH & TRẠNG THÁI (DATA)
DATA_DIR = os.path.join(BASE_DIR, "data")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")
ACCOUNTS_EXAMPLE_FILE = os.path.join(DATA_DIR, "accounts.example.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
SETTINGS_EXAMPLE_FILE = os.path.join(DATA_DIR, "settings.example.json")
COOKIES_FILE = os.path.join(DATA_DIR, "cookies.txt")

# 2. PHÂN TẦNG TÀI NGUYÊN ĐỒ HỌA & HIỆU ỨNG (ASSETS)
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")
PRESETS_DIR = os.path.join(ASSETS_DIR, "presets")
AUDIOS_DIR = os.path.join(ASSETS_DIR, "audios")
OVERLAYS_DIR = os.path.join(ASSETS_DIR, "overlays")
DEFAULT_FONT_PATH = os.path.join(FONTS_DIR, "Poppins-Bold.ttf")

# 3. PHÂN TẦNG RUNTIME STORAGE (VIDEO, OUTPUT, TEMP, LOGS)
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
STORAGE_INPUT_DIR = os.path.join(STORAGE_DIR, "inputs")
STORAGE_OUTPUT_DIR = os.path.join(STORAGE_DIR, "outputs")
TEMP_DIR = os.path.join(STORAGE_DIR, "temp")
LOGS_DIR = os.path.join(STORAGE_DIR, "logs")

# Giữ tương thích ngược với cấu trúc cũ nếu đang có file
LEGACY_INPUT_DIR = os.path.join(BASE_DIR, "input_sources")
LEGACY_OUTPUT_DIR = os.path.join(BASE_DIR, "output_product")
VIDEO_DIR = LEGACY_INPUT_DIR if os.path.exists(LEGACY_INPUT_DIR) else STORAGE_INPUT_DIR
OUTPUT_BASE_DIR = LEGACY_OUTPUT_DIR if os.path.exists(LEGACY_OUTPUT_DIR) else STORAGE_OUTPUT_DIR

# 4. BINARIES & THỰC THI (BIN)
BIN_DIR = os.path.join(BASE_DIR, "bin")
FFMPEG_EXE = os.path.join(BIN_DIR, "ffmpeg.exe") if os.name == 'nt' else "ffmpeg"
FFPROBE_EXE = os.path.join(BIN_DIR, "ffprobe.exe") if os.name == 'nt' else "ffprobe"

# Thêm BIN_DIR vào hệ thống PATH
if BIN_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = BIN_DIR + os.pathsep + os.environ.get("PATH", "")

# Tự động đảm bảo tất cả thư mục cần thiết đều tồn tại
REQUIRED_DIRS = [
    DATA_DIR, ASSETS_DIR, FONTS_DIR, PRESETS_DIR, AUDIOS_DIR, OVERLAYS_DIR,
    STORAGE_DIR, STORAGE_INPUT_DIR, STORAGE_OUTPUT_DIR, TEMP_DIR, LOGS_DIR,
    VIDEO_DIR, OUTPUT_BASE_DIR, BIN_DIR
]
for d in REQUIRED_DIRS:
    os.makedirs(d, exist_ok=True)
