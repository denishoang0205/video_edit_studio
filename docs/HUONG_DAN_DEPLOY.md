# 🚀 Hướng Dẫn Deploy TikTok Studio Pro

Tài liệu hướng dẫn triển khai **TikTok Studio Pro** lên các môi trường máy chủ: **Docker**, **Linux VPS (Ubuntu/Debian)**, **Windows Server** hoặc **Cloud VM**.

---

## 📌 Cách 1: Triển khai bằng Docker & Docker Compose (Khuyên dùng)

Cách nhanh nhất, gọn nhất và không lo xung đột môi trường.

### 1. Chuẩn bị
* Cài đặt **Docker** & **Docker Compose** trên máy chủ:
  ```bash
  curl -fsSL https://get.docker.com -o get-docker.sh
  sudo sh get-docker.sh
  ```

### 2. Triển khai
1. Clone repository về máy chủ:
   ```bash
   git clone https://github.com/denishoang0205/video_edit_studio.git
   cd video_edit_studio
   ```
2. Khởi chạy bằng Docker Compose:
   ```bash
   docker compose up -d --build
   ```
3. Kiểm tra container:
   ```bash
   docker compose ps
   docker compose logs -f
   ```
4. Truy cập Web Dashboard tại: `http://YOUR_SERVER_IP:8000`.

---

## 📌 Cách 2: Triển khai trực tiếp trên Linux VPS (Ubuntu / Debian)

### 1. Triển khai 1-Click bằng Script
```bash
git clone https://github.com/denishoang0205/video_edit_studio.git
cd video_edit_studio
chmod +x deploy.sh
./deploy.sh
```

Script sẽ tự động:
* Cài đặt Python 3, FFmpeg, Curl.
* Tạo môi trường ảo `venv` và cài đặt `requirements.txt`.
* Thiết lập dịch vụ chạy ngầm **Systemd** tự khởi động cùng hệ thống (`tiktok-studio.service`).

### 2. Quản lý dịch vụ trên VPS
* Xem trạng thái: `sudo systemctl status tiktok-studio`
* Khởi động lại: `sudo systemctl restart tiktok-studio`
* Xem log trực tiếp: `journalctl -u tiktok-studio -f`

---

## 📌 Cách 3: Cấu hình Nginx Reverse Proxy & Chứng chỉ SSL (HTTPS)

Nếu bạn muốn truy cập qua tên miền riêng dạng `https://studio.yourdomain.com`:

1. Cài đặt Nginx & Certbot:
   ```bash
   sudo apt install -y nginx certbot python3-certbot-nginx
   ```
2. Tạo file cấu hình Nginx `/etc/nginx/sites-available/tiktok-studio`:
   ```nginx
   server {
       server_name studio.yourdomain.com;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           client_max_body_size 500M;
       }
   }
   ```
3. Kích hoạt và cấp SSL miễn phí Let's Encrypt:
   ```bash
   sudo ln -s /etc/nginx/sites-available/tiktok-studio /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   sudo certbot --nginx -d studio.yourdomain.com
   ```

---

## 📌 Cách 4: Triển khai trên Windows Server / Máy tính Windows

1. Cài đặt **Python 3.8+** (tích chọn `Add python.exe to PATH`).
2. Clone repo về thư mục bất kỳ.
3. Nhấp đúp **`Install_Dependencies.bat`** (tự động cài thư viện và tải FFmpeg).
4. Nhấp đúp **`Open_Studio.vbs`** để mở Studio ngầm.

---

## 🛡️ Lưu ý bảo mật khi Deploy
* Không bao giờ commit file `data/accounts.json` hoặc `data/settings.json` lên Git public.
* Cấu hình tường lửa (UFW / Security Group) mở port `8000` (hoặc `80/443` nếu dùng Nginx).
