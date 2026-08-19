# 🎬 TikTok Video Studio Pro (Automation Pipeline & Webform)

> Một công cụ tự động hóa toàn diện giúp cắt lát, biên tập, gắn tiêu đề phong cách và quản lý ma trận tài khoản TikTok & kênh YouTube mục tiêu với giao diện Webform trực quan, tốc độ cao.

---

## ✨ Tính Năng Nổi Bật (Key Features)

- 🎨 **Biên tập Video Đa Tỉ Lệ (Multi Aspect Ratios):** Hỗ trợ `3:4`, `9:16 (Shorts/TikTok)`, `16:9 (YouTube)`, `4:3`, `1:1`.
- 🪄 **Hiệu ứng Chống Quét Bản Quyền:**
  - Double-layer Background Blur (Mờ nền 2 lớp giữ chủ thể trung tâm sắc nét).
  - Horizontal Flip (Lật video ngang).
  - Color & Contrast Boost (Tăng độ tươi và sắc nét).
- 🏷️ **Banner Tiêu Đề Tự Động (Styled Header Banner):** Tự động render tiêu đề với các phong cách: Rounded White, Dark Glassmorphism, Pill Badge hoặc Shadowed Text. Tự động hỗ trợ font chữ tùy chỉnh (`.ttf`, `.otf`).
- ⚡ **Tự động Cắt Lát (Auto Video Splitting):** Tự động chia video dài thành các part nhỏ tối ưu thời lượng đăng TikTok (`part 1`, `part 2`,...).
- 📁 **Tự động Đồng Bộ & Tạo Thư Mục Kênh:** Thêm kênh trên Webform -> Tự động sinh thư mục tại Nguồn (Input) và Đích (Output).
- 🚀 **Hardware Acceleration (GPU NVENC/AMD/Intel):** Tận dụng GPU NVIDIA / AMD / Intel để tăng tốc render gấp 5–10 lần so với CPU.
- 📊 **Posting Tracker & Analytics Dashboard:** Theo dõi tiến độ đăng video, ma trận phân phối clip theo từng tài khoản TikTok và kênh đích.
- 🌐 **Hỗ trợ Google Drive Sync & Local Drive:** Tự động nhận diện thư mục đồng bộ Google Drive Desktop (ổ `G:\`) hoặc ổ cứng bất kỳ trên máy tính.

---

## 📂 Cấu Trúc Thư Mục (Folder Structure)

```text
tiktok_studio/
├── 📁 bin/                    # Chứa ffmpeg.exe (Engine render video)
├── 📁 ui/                     # Giao diện Webform (HTML, CSS, JS)
├── 📁 video/                  # Thư mục chứa Video Nguồn (Input)
├── 📁 Tiktok_Builder_Output/  # Thư mục lưu Video Thành Phẩm (Output)
├── 📄 Poppins-Bold.ttf        # Font chữ tiêu đề mặc định
├── 📄 config.py               # Cấu hình đường dẫn cơ bản
├── 📄 server.py               # Backend Web Server (Python HTTP & REST API)
├── 📄 drive_manager.py        # Module quản lý tệp, thư mục, tài khoản & matrix
├── 📄 video_processor.py      # Module xử lý video & FFmpeg Filter Graph
├── 📄 accounts.example.json   # File mẫu cấu hình kênh & tài khoản
├── 📄 requirements.txt        # Danh sách thư viện Python
├── 📄 Install_Dependencies.bat# Script cài đặt thư viện 1-click
├── 📄 Run_Studio.bat          # Script khởi động ứng dụng
└── 📄 README.md               # Tài liệu hướng dẫn
```

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy (Quick Start)

### 1. Yêu cầu hệ thống
- Hệ điều hành: **Windows 10 / 11**
- Đã cài đặt **Python 3.8+** ([Tải Python tại đây](https://www.python.org/downloads/))  
  *(⚠️ **Lưu ý quan trọng:** Khi cài đặt Python, nhớ tích chọn ô **"Add python.exe to PATH"**)*.

### 2. Cài đặt (Chỉ cần làm 1 lần đầu)
1. Tải toàn bộ mã nguồn về máy hoặc dùng lệnh:
   ```bash
   git clone https://github.com/your-username/tiktok-video-studio.git
   cd tiktok-video-studio
   ```
2. Nhấp đúp chuột vào file **`Install_Dependencies.bat`**.  
   *(Script sẽ tự động cài đặt `Pillow` và kiểm tra `FFmpeg`)*.

### 3. Khởi động ứng dụng
- Nhấp đúp chuột vào file **`Run_Studio.bat`**.
- Trình duyệt web sẽ tự động mở trang quản trị tại: **`http://localhost:8000`**.

---

## 📖 Hướng Dẫn Sử Dụng Cơ Bản

### Bước 1: Cấu hình Workspace (Thư mục Nguồn & Đích)
- Vào tab **Workspaces**.
- Mặc định tool sẽ sử dụng ngay thư mục `./video` và `./Tiktok_Builder_Output`.
- Nếu muốn đổi sang ổ đĩa khác (ví dụ `D:\VideoRaw` hoặc Google Drive), bấm vào biểu tượng 📁 để chọn thư mục rồi bấm **"Save Paths"**.

### Bước 2: Quản lý Kênh & Bỏ Video Gốc
- Vào tab **YouTube Channels** -> Bấm **"Add New Channel"** để thêm kênh.
- Hệ thống sẽ **tự động tạo thư mục tên kênh** ở cả Source và Output.
- Copy video gốc thả vào thư mục tên kênh vừa tạo.

### Bước 3: Tùy Chỉnh & Render
- Vào tab **Editor Studio** -> Chọn video cần render.
- Chọn tỉ lệ (`3:4` hoặc `9:16`), kiểu banner, font chữ và hiệu ứng mong muốn.
- Bấm **"Start Batch Process"** và theo dõi tiến trình trực quan theo thời gian thực.

### Bước 4: Kiểm tra & Theo dõi Đăng bài
- Vào tab **Finished Library** để xem trước video thành phẩm hoặc mở trực tiếp trên Windows Explorer.
- Vào tab **Posting Tracker** để đánh dấu các clip đã đăng lên TikTok.

---

## 🔤 Thêm Font Chữ Tùy Biến (Custom Fonts)
Bạn có thể tải bất kỳ file font `.ttf` hoặc `.otf` nào từ Google Fonts / DaFont rồi bỏ trực tiếp vào thư mục gốc của dự án hoặc cài vào Windows. Tool sẽ tự động nhận diện!

---

## 📜 Giấy Phép (License)
Dự án được phân phối dưới giấy phép **MIT License**. Bạn có thể tự do sử dụng, chỉnh sửa và phân phối.
