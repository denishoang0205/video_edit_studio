# 🤖 Hướng Dẫn Tích Hợp n8n với TikTok Studio Pro

Tài liệu này hướng dẫn bạn cách kết nối **n8n (Workflow Automation)** với **TikTok Video Studio Pro** để tạo ra một cỗ máy tự động hóa hoàn toàn: tự động chọn video chưa đăng, dùng AI (Gemini/OpenAI) viết caption & hashtag triệu view, tự kích hoạt HMA VPN đổi IP, mở AdsPower và đăng lên TikTok, sau đó gửi báo cáo về Telegram.

---

## 📑 Mục Lục
1. [Mô hình Hoạt động](#1-mô-hình-hoạt-động)
2. [Cài đặt n8n (Trên máy tính Windows)](#2-cài-đặt-n8n-trên-máy-tính-windows)
3. [Import Workflow mẫu vào n8n](#3-import-workflow-mẫu-vào-n8n)
4. [Cấu hình Credentials & Thông số](#4-cấu-hình-credentials--thông-số)
5. [Tài liệu Chi tiết về các REST API Endpoint](#5-tài-liệu-chi-tiết-về-các-rest-api-endpoint)

---

## 1. Mô hình Hoạt động

```text
[Cron Schedule: 4 tiếng/lần]
       │
       ▼
[GET /api/n8n/pending_clips] ──► (Lấy clip chờ đăng từ Ma trận)
       │
       ▼
[Node AI Gemini / ChatGPT]  ──► (Sinh Caption & Hashtag viral)
       │
       ▼
[POST /api/pipeline/auto_process_and_post] ──► (Python Server thực thi)
       ├── HMA VPN đổi IP đúng quốc gia
       ├── AdsPower khởi động Profile Chrome
       ├── Playwright nạp video, điền caption, click Post
       └── Cập nhật dấu tích xanh trên Ma trận
       │
       ▼
[Telegram Bot Notification]  ──► (Bắn thông báo thành công về điện thoại)
```

---

## 2. Cài đặt n8n (Trên máy tính Windows)

Cách nhanh nhất và không tốn phí là cài n8n trực tiếp trên máy tính thông qua `npm` (NodeJS) hoặc `Docker`:

### Cách 1: Dùng NPM (Khuyến nghị)
1. Cài đặt [Node.js LTS](https://nodejs.org/).
2. Mở PowerShell / Command Prompt và chạy lệnh:
   ```bash
   npx n8n
   ```
3. Sau khi khởi động, mở trình duyệt vào địa chỉ: **`http://localhost:5678`**.

### Cách 2: Dùng Docker
```bash
docker run -it --rm --name n8n -p 5678:5678 -v ~/.n8n:/home/node/.n8n n8nio/n8n
```

---

## 3. Import Workflow mẫu vào n8n

1. Trong giao diện n8n (`http://localhost:5678`), bấm vào nút **`+ Add workflow`**.
2. Ở góc trên bên phải, bấm vào biểu tượng dấu 3 chấm `...` -> Chọn **`Import from File`**.
3. Chọn file **[`n8n_workflow_tiktok_studio.json`](./n8n_workflow_tiktok_studio.json)** trong thư mục dự án.
4. Toàn bộ sơ đồ 6 node sẽ hiển thị trực quan trên màn hình.

---

## 4. Cấu hình Credentials & Thông số

### 4.1. Cấu hình Node AI Gemini / OpenAI (Node 4)
- Nếu dùng **Gemini API**: Tạo API Key miễn phí tại [Google AI Studio](https://aistudio.google.com/).
- Điền API Key vào Header `Authorization: Bearer YOUR_GEMINI_KEY` hoặc dùng node Google Gemini có sẵn của n8n.

### 4.2. Cấu hình Telegram Bot (Node 6)
1. Mở Telegram, chat với `@BotFather` để tạo bot mới và lấy **`Bot Token`**.
2. Chat với `@userinfobot` để lấy **`Chat ID`** của bạn.
3. Trong n8n, chọn Node **`Telegram`**, tạo Credential mới và dán Token vào. Điền Chat ID vào ô `Chat ID`.

### 4.3. Khởi động Python Studio Server
Đảm bảo bạn đã bật server Python:
```bash
python server.py
```
Server chạy tại `http://localhost:8000`.

---

## 5. Tài liệu Chi tiết về các REST API Endpoint

Dưới đây là danh sách các API mà n8n có thể gọi vào Python Server:

### 1. `GET /api/n8n/pending_clips`
Lấy danh sách các video đã render thành phẩm nhưng chưa đăng trên TikTok.

**Query Parameters:**
- `account_name` *(tùy chọn)*: Lọc theo tên tài khoản TikTok (VD: `acc_us_01`).
- `channel_name` *(tùy chọn)*: Lọc theo tên kênh YouTube (VD: `Channel 1`).
- `only_current_target` *(mặc định: `true`)*: Chỉ lấy các video thuộc kênh mục tiêu hiện tại của tài khoản.

**Ví dụ Phản hồi (Response JSON):**
```json
{
  "success": true,
  "total_pending": 3,
  "items": [
    {
      "account_name": "sample_account",
      "channel": "Sample Channel",
      "title": "Video Huong Dan 01",
      "clip_key": "Sample Channel/Video Huong Dan 01",
      "part_label": "Part 1",
      "part_name": "part 1.mp4",
      "video_file": "C:\\path\\to\\Tiktok_Builder_Output\\Sample Channel\\Video Huong Dan 01\\Video Huong Dan 01 - part 1.mp4",
      "hashtag": "#viral #trending #fyp",
      "target_ip": "US",
      "adspower_id": "k123abc"
    }
  ]
}
```

---

### 2. `POST /api/pipeline/auto_process_and_post`
Kích hoạt toàn bộ quy trình Auto-Post (HMA IP -> AdsPower -> Playwright -> Matrix update) trong nền.

**Request Body (JSON):**
```json
{
  "account_name": "sample_account",
  "clip_key": "Sample Channel/Video Huong Dan 01",
  "channel": "Sample Channel",
  "title": "Video Huong Dan 01",
  "video_file": "C:\\path\\to\\video.mp4",
  "part_label": "Part 1",
  "override_caption": "Bí quyết làm video triệu view cực hot 😱",
  "override_hashtags": "#learnontiktok #fyp #viral2026",
  "auto_submit": true,
  "callback_url": "http://localhost:5678/webhook/tiktok-callback"
}
```

**Phản hồi (Response JSON):**
```json
{
  "success": true,
  "status": "queued",
  "job_id": "job_1771772648000_a1b2",
  "message": "Pipeline đã được khởi chạy trong nền. Kiểm tra tiến độ tại /api/pipeline/job_status?job_id=job_1771772648000_a1b2"
}
```

---

### 3. `GET /api/pipeline/job_status?job_id=...`
Kiểm tra tiến độ chi tiết, logs và kết quả của Job.

**Response JSON:**
```json
{
  "success": true,
  "job": {
    "job_id": "job_1771772648000_a1b2",
    "type": "auto_process_and_post",
    "status": "completed",
    "progress": 100,
    "current_task": "Quy trình Auto-Post hoàn tất thành công!",
    "logs": [
      "[21:50:10] 🚀 [Auto-Post] Bắt đầu quy trình...",
      "[21:50:12] 🛡️ [1/4] Kích hoạt HMA VPN...",
      "[21:50:18] ⚡ [2/4] Khởi chạy Profile AdsPower...",
      "[21:50:25] 🌐 [3/4] Nạp video thành công...",
      "[21:50:40] 🎉 [4/4] Đã đăng clip thành công!"
    ],
    "result": {
      "success": true,
      "message": "Đăng clip lên TikTok thành công!"
    }
  }
}
```
