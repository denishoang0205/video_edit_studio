import os
import sys

# Hỗ trợ PyInstaller (lấy thư mục chứa file .exe)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Thư mục chứa dữ liệu (tương đối theo BASE_DIR để dễ share)
VIDEO_DIR = os.path.join(BASE_DIR, "video")
# Đổi OUTPUT về cùng thư mục app thay vì ổ C cứng để người khác dùng không bị lỗi
OUTPUT_BASE_DIR = os.path.join(BASE_DIR, "Tiktok_Builder_Output")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
BIN_DIR = os.path.join(BASE_DIR, "bin")

# Đường dẫn thực thi FFmpeg
FFMPEG_EXE = os.path.join(BIN_DIR, "ffmpeg.exe")

# Thêm BIN_DIR vào hệ thống PATH
if BIN_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = BIN_DIR + os.pathsep + os.environ.get("PATH", "")

# Đảm bảo thư mục video tồn tại
os.makedirs(VIDEO_DIR, exist_ok=True)
