# 🌙 Hướng Dẫn Tự Động Hóa Đăng Video Ban Đêm (100% Tiết Kiệm & Tự Tắt Máy)

Hướng dẫn này giúp bạn thiết lập máy tính để **tự động đăng video TikTok vào lúc 12h đêm** và **tự động tắt nguồn máy tính sau khi hoàn tất** mà bạn không cần phải thức canh máy.

---

## ⚡ 3 Bước Chuẩn Bị Trên Windows (Chỉ cần làm 1 lần)

### 1. Đối với LAPTOP (Gập máy vẫn chạy ngầm)
1. Bấm phím `Windows` -> Gõ tìm kiếm **`Control Panel`** và mở lên.
2. Chọn **`Hardware and Sound`** -> **`Power Options`**.
3. Ở menu bên trái, bấm vào dòng **`Choose what closing the lid does`** *(Chọn hành động khi gập nắp máy)*.
4. Ở dòng **When I close the lid** *(Khi tôi gập nắp)*:
   - Cột *Plugged in* (Khi cắm sạc): Chọn **`Do nothing`** *(Không làm gì cả)*.
5. Bấm **`Save changes`** để lưu.

> *Từ giờ, bạn cắm sạc laptop rồi gập nắp lại, màn hình sẽ tắt nhưng tool và n8n vẫn chạy ngầm bình thường.*

---

### 2. Đối với MÁY TÍNH BÀN (PC)
- Bạn chỉ cần **Tắt công tắc màn hình** (CPU thùng máy vẫn bật).
- Đảm bảo trong Windows Settings không bật chế độ tự động Sleep sau 15-30 phút (Vào *Settings > System > Power & sleep* -> Đặt mục *Sleep* thành **`Never`** khi cắm nguồn).

---

## 🚀 Quy Trình Vận Hành Hàng Ngày Trước Khi Đi Ngủ

Mỗi tối trước khi đi ngủ, bạn chỉ cần thực hiện 3 bước đơn giản:

```text
[1. Thả video vào thư mục Kênh]
              │
              ▼
[2. Nhấp đúp chạy file 'Run_Auto_Nightly.bat']
              │
              ▼
[3. Tắt màn hình / Gập Laptop và đi ngủ]
              │
              ▼
[Đúng 00:00: n8n kích hoạt đăng clip -> Gửi tin nhắn Telegram -> Tự động tắt máy sau 15p]
```

### Chi tiết:
1. **Bước 1:** Nhấp đúp vào file **[`Run_Auto_Nightly.bat`](./Run_Auto_Nightly.bat)**.
   - Script sẽ tự động khởi chạy cả **TikTok Studio Server** và **n8n Workflow Engine**.
2. **Bước 2:** Mở trình duyệt vào `http://localhost:5678`, mở workflow **`TikTok Studio Pro - Nightly 00:00 Auto Poster`** và gạt công tắc sang **`Active`** (Bật).
3. **Bước 3:** Tắt màn hình hoặc gập laptop và đi ngủ!

---

## 📱 Kết Quả Nhận Được Sáng Hôm Sau
- Sáng ngủ dậy, bạn sẽ thấy thông báo trên điện thoại qua **Telegram**:
  ```text
  🌙 [TikTok Nightly Bot] ĐÃ ĐĂNG VIDEO THÀNH CÔNG LÚC ĐÊM!
  ━━━━━━━━━━━━━━━━━━━━
  👤 Tài khoản: @sample_account
  📺 Kênh: Anime Recap Channel
  🎬 Clip: Attack On Titan - Part 1
  ✍️ Caption AI: Sự thật kinh hoàng đằng sau bức tường thành 😱 #aot #anime #fyp
  ⏰ Thời gian: 2026-08-24 00:00:15
  ━━━━━━━━━━━━━━━━━━━━
  💤 Máy tính đã tự động tắt sau 15 phút.
  ```
- Máy tính của bạn đã được tắt nguồn an toàn, tiết kiệm 100% điện năng và giữ mát phần cứng!
