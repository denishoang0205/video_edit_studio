import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import json
import time
import threading
import subprocess
from urllib.parse import urlparse, parse_qs, unquote
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import mimetypes
import re

def sanitize_filename(name):
    """Xóa các ký tự không hợp lệ trong tên file/thư mục Windows và dấu chấm/khoảng trắng cuối tên"""
    if not name:
        return ""
    for ext in ['.mp4', '.mkv', '.mov', '.avi', '.webm']:
        if name.lower().endswith(ext):
            name = name[:-len(ext)]
            break
    sanitized = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return re.sub(r'\.+$', '', sanitized).strip()

# Set base dir
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)


from drive_manager import (
    scan_source_directory, scan_finished_results, load_history, save_history, 
    delete_finished_result, delete_all_finished_results,
    get_publishing_matrix, toggle_publishing_clip_status, change_account_target_channel, batch_toggle_publishing_clips,
    load_accounts_data, save_accounts_data, ensure_channel_folders
)
from video_processor import get_video_duration, process_video_custom, split_video_custom

PORT = 8000
LOG_MESSAGES = []
CURRENT_TASK = "Sẵn sàng"
PROGRESS_PERCENT = 0
IS_RUNNING = False
CANCEL_REQUESTED = False

def log_message(msg):
    global LOG_MESSAGES
    timestamp = time.strftime("[%H:%M:%S]")
    formatted = f"{timestamp} {msg}"
    print(formatted)
    LOG_MESSAGES.append(formatted)
    if len(LOG_MESSAGES) > 200:
        LOG_MESSAGES.pop(0)

def batch_worker(payload):
    global IS_RUNNING, CANCEL_REQUESTED, PROGRESS_PERCENT, CURRENT_TASK
    IS_RUNNING = True
    CANCEL_REQUESTED = False
    PROGRESS_PERCENT = 0
    
    video_items = payload.get("video_items", [])
    dest_folder = payload.get("dest_folder", os.path.join(BASE_DIR, "Tiktok_Builder_Output"))
    from drive_manager import resolve_google_drive_path
    dest_folder = resolve_google_drive_path(dest_folder)
    if not dest_folder or dest_folder.startswith(('http://', 'https://')):
        dest_folder = os.path.join(BASE_DIR, "Tiktok_Builder_Output")
        
    settings = {
        "aspect_ratio": payload.get("aspect_ratio", "3:4"),
        "blur_bg": payload.get("blur_bg", True),
        "hflip": payload.get("hflip", False),
        "color_boost": payload.get("color_boost", True),
        "banner_box_style": payload.get("banner_box_style", "white-rounded"),
        "banner_font": payload.get("banner_font", "Poppins-Bold"),
        "banner_font_size": payload.get("banner_font_size", 46),
        "banner_position": payload.get("banner_position", "top"),
    }
    split_mode = payload.get("split_mode", "auto")
    export_full = payload.get("export_full", True)

    # Convert simple paths list to items list if only paths sent (backwards compatibility)
    if not video_items and payload.get("video_paths"):
        for path in payload.get("video_paths"):
            title = os.path.splitext(os.path.basename(path))[0]
            parent = os.path.basename(os.path.dirname(path))
            # Determine grandparent/channel fallback
            grandparent = os.path.basename(os.path.dirname(os.path.dirname(path)))
            channel = parent if parent else "Channel"
            video_items.append({
                "path": path,
                "title": title,
                "channel": channel
            })

    total = len(video_items)
    log_message(f"🚀 Bắt đầu Batch Render: {total} video | Tỉ lệ: {settings['aspect_ratio']} | Nơi xuất: {dest_folder}")

    history = load_history()

    for idx, item in enumerate(video_items):
        if CANCEL_REQUESTED:
            log_message("⚠️ Tiến trình đã bị dừng bởi người dùng.")
            break

        raw_path = item.get("path")
        title = item.get("title")
        channel = item.get("channel", "Channel")

        # Nếu path là folder, tìm file video bên trong
        actual_video_file = raw_path
        if raw_path and os.path.isdir(raw_path):
            files = os.listdir(raw_path)
            for f in files:
                if f.endswith(('.mp4', '.mkv', '.mov', '.avi')) and not f.startswith(('part_', 'edited_')):
                    actual_video_file = os.path.join(raw_path, f)
                    break
            if actual_video_file == raw_path:
                for f in files:
                    if f.endswith(('.mp4', '.mkv', '.mov')):
                        actual_video_file = os.path.join(raw_path, f)
                        break

        # Kiểm tra an toàn: Nếu không tìm thấy file video hợp lệ (hoặc là thư mục rỗng)
        if not actual_video_file or os.path.isdir(actual_video_file) or not os.path.exists(actual_video_file):
            log_message(f"❌ Lỗi: Thư mục nguồn '{title}' không chứa file video hợp lệ!")
            continue

        CURRENT_TASK = f"({idx+1}/{total}) Đang render: {title}"
        log_message(f"▶️ [{idx+1}/{total}] Đang xử lý: {title} (Kênh: {channel})")
        PROGRESS_PERCENT = int((idx / total) * 100)

        # Thư mục xuất thành phẩm phân cấp: dest_folder / channel / title
        sanitized_channel = sanitize_filename(channel)
        sanitized_title = sanitize_filename(title)
        video_out_dir = os.path.join(dest_folder, sanitized_channel, sanitized_title)
        os.makedirs(video_out_dir, exist_ok=True)
        edited_full_path = os.path.join(video_out_dir, "edited_full.mp4")

        # 1. Biên tập Video
        success = process_video_custom(actual_video_file, edited_full_path, title, settings)
        if not success:
            log_message(f"❌ Thất bại khi biên tập: {title}")
            continue

        # 2. Split Video
        duration = get_video_duration(edited_full_path)
        log_message(f"⏱️ Thời lượng: {duration:.1f}s | Chế độ cắt: {split_mode}")
        split_files = split_video_custom(edited_full_path, video_out_dir, duration, split_mode=split_mode)

        # Xóa file full nếu người dùng không yêu cầu giữ
        if not export_full and split_mode != "no-split" and os.path.exists(edited_full_path):
            try:
                os.remove(edited_full_path)
            except Exception:
                pass

        # Ghi nhận trạng thái vào history
        history[title] = {
            "title": title,
            "status": "edited",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "output_dir": video_out_dir,
            "parts_count": len(split_files)
        }
        save_history(history)
        log_message(f"🎉 Hoàn thành xuất sắc: {title} ({len(split_files)} parts)")

        # Xóa file video gốc để tiết kiệm dung lượng đĩa
        if actual_video_file and os.path.exists(actual_video_file):
            try:
                os.remove(actual_video_file)
                log_message(f"🗑️ Đã xóa tệp video gốc: {os.path.basename(actual_video_file)}")
            except Exception as e:
                log_message(f"⚠️ Lỗi khi xóa video gốc: {e}")

    PROGRESS_PERCENT = 100
    CURRENT_TASK = "Hoàn thành toàn bộ batch!"
    log_message("🏁 ĐÃ HOÀN TẤT TẤT CẢ CÁC TÁC VỤ BIÊN TẬP.")
    IS_RUNNING = False

class StudioServerHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Serve UI directory for frontend assets
        parsed = urlparse(path).path
        if parsed == "/" or parsed.startswith("/ui"):
            if parsed == "/":
                parsed = "/ui/index.html"
            rel_path = parsed.lstrip("/")
            return os.path.join(BASE_DIR, rel_path)
        return super().translate_path(path)

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        # Root redirect
        if parsed.path == "/":
            self.send_response(302)
            self.send_header("Location", "/ui/index.html")
            self.end_headers()
            return

        # API: Progress & Logs
        if parsed.path == "/api/progress":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            data = {
                "is_running": IS_RUNNING,
                "percentage": PROGRESS_PERCENT,
                "current_task": CURRENT_TASK,
                "logs": LOG_MESSAGES[-40:]
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        # API: Finished Results
        if parsed.path == "/api/results":
            dest = query.get("dest", [os.path.join(BASE_DIR, "Tiktok_Builder_Output")])[0]
            data = scan_finished_results(dest)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        # API: Accounts & YouTube Channels list
        if parsed.path == "/api/accounts":
            source_path = query.get("source", [""])[0]
            data = load_accounts_data()
            
            # Giải mã/ánh xạ đường dẫn Google Drive nếu có
            from drive_manager import resolve_google_drive_path
            resolved_source = resolve_google_drive_path(source_path)
            
            # Tính toán số lượng video đã tải cho mỗi kênh
            if resolved_source and os.path.exists(resolved_source):
                for chan in data.get("youtube_channels", []):
                    folder_name = chan.get("folder_name", chan.get("name"))
                    chan_dir = os.path.join(resolved_source, folder_name)
                    video_count = 0
                    if os.path.exists(chan_dir) and os.path.isdir(chan_dir):
                        try:
                            sub_items = os.listdir(chan_dir)
                            for sub in sub_items:
                                sub_path = os.path.join(chan_dir, sub)
                                if os.path.isdir(sub_path):
                                    sub_files = os.listdir(sub_path)
                                    if any(f.endswith(('.mp4', '.mkv', '.mov', '.avi')) and not f.startswith(('part_', 'edited_')) for f in sub_files):
                                        video_count += 1
                                elif sub.lower().endswith(('.mp4', '.mkv', '.mov', '.avi')):
                                    video_count += 1
                        except Exception:
                            pass
                    chan["total_downloaded"] = video_count
            else:
                for chan in data.get("youtube_channels", []):
                    chan["total_downloaded"] = 0

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        # API: Publishing Tracker Matrix
        if parsed.path == "/api/publishing_matrix":
            dest = query.get("dest", [""])[0]
            data = get_publishing_matrix(dest if dest else None)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        # Stream Video file for preview modal
        if parsed.path == "/video_stream":
            vpath = query.get("path", [""])[0]
            vpath = unquote(vpath)
            if vpath and os.path.exists(vpath) and os.path.isfile(vpath):
                try:
                    file_size = os.path.getsize(vpath)
                    range_header = self.headers.get('Range', None)
                    
                    if range_header:
                        match = re.search(r'bytes=(\d+)-(\d*)', range_header)
                        if match:
                            start_byte = int(match.group(1))
                            end_byte = int(match.group(2)) if match.group(2) else file_size - 1
                            if end_byte >= file_size:
                                end_byte = file_size - 1
                            content_len = (end_byte - start_byte) + 1
                            
                            self.send_response(206)
                            self.send_header("Content-Type", "video/mp4")
                            self.send_header("Content-Range", f"bytes {start_byte}-{end_byte}/{file_size}")
                            self.send_header("Content-Length", str(content_len))
                            self.send_header("Accept-Ranges", "bytes")
                            self.end_headers()
                            
                            with open(vpath, "rb") as f:
                                f.seek(start_byte)
                                remaining = content_len
                                while remaining > 0:
                                    chunk_size = min(65536, remaining)
                                    chunk = f.read(chunk_size)
                                    if not chunk:
                                        break
                                    try:
                                        self.wfile.write(chunk)
                                    except Exception:
                                        break
                                    remaining -= len(chunk)
                            return

                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Length", str(file_size))
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    with open(vpath, "rb") as f:
                        while chunk := f.read(65536):
                            try:
                                self.wfile.write(chunk)
                            except Exception:
                                break
                except Exception:
                    pass
                return
            else:
                self.send_error(404, "Video Not Found")
                return

        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else "{}"
        try:
            body_data = json.loads(post_body)
        except Exception:
            body_data = {}

        # API: Scan Source Directory / Drive
        if parsed.path == "/api/scan_source":
            source = body_data.get("source", "")
            dest = body_data.get("dest", None)
            result = scan_source_directory(source, dest)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode("utf-8"))
            return

        # API: Start Batch Processing
        if parsed.path == "/api/start_batch":
            global IS_RUNNING
            if IS_RUNNING:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Tiến trình render đang chạy!"}).encode("utf-8"))
                return

            t = threading.Thread(target=batch_worker, args=(body_data,), daemon=True)
            t.start()

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started"}).encode("utf-8"))
            return

        # API: Stop Batch Processing
        if parsed.path == "/api/stop_batch":
            global CANCEL_REQUESTED
            CANCEL_REQUESTED = True
            log_message("🛑 Nhận được tín hiệu dừng từ người dùng.")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "stopping"}).encode("utf-8"))
            return

        # API: Open Folder in Explorer
        if parsed.path == "/api/open_folder":
            fpath = body_data.get("path", body_data.get("folder_path", ""))
            if fpath:
                fpath = fpath.strip().strip('"').strip("'")
                if os.path.exists(fpath):
                    if os.name == 'nt':
                        os.startfile(fpath)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "opened"}).encode("utf-8"))
            return

        # API: Open File in explorer and select it
        if parsed.path == "/api/open_file":
            filepath = body_data.get("path", "")
            if filepath:
                filepath = filepath.strip().strip('"').strip("'")
                if os.path.exists(filepath):
                    if os.name == 'nt':
                        # Dùng os.startfile (ShellExecute) để mở nổi cửa sổ lên trên cùng màn hình
                        os.startfile('explorer.exe', arguments='/select,' + os.path.abspath(filepath))
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "opened"}).encode("utf-8"))
            return

        # API: Save Accounts & YouTube Channels list
        if parsed.path == "/api/accounts/save":
            success = save_accounts_data(body_data)
            if success:
                created = ensure_channel_folders(body_data)
                for f in created:
                    log_message(f"📁 Tự động tạo thư mục: {f}")
            self.send_response(200 if success else 500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "saved" if success else "failed"}).encode("utf-8"))
            return

        # API: Select Local Folder via OS Picker
        if parsed.path == "/api/select_folder":
            folder_path = ""
            try:
                cmd = [
                    sys.executable,
                    "-c",
                    "import tkinter as tk; from tkinter import filedialog; root = tk.Tk(); root.withdraw(); root.wm_attributes('-topmost', 1); print(filedialog.askdirectory(title='Chọn Thư Mục Dự Án'))"
                ]
                output = subprocess.check_output(cmd, text=True).strip()
                folder_path = output
            except Exception as e:
                print(f"Lỗi khi chạy subprocess file picker: {e}")
                
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"folder_path": folder_path}).encode("utf-8"))
            return

        # API: Delete Finished Result Video
        if parsed.path == "/api/delete_result":
            item_path = body_data.get("path", "")
            title = body_data.get("title", "")
            channel = body_data.get("channel", "")
            dest_path = body_data.get("dest", "")
            
            success, errors = delete_finished_result(item_path, title, channel, dest_path)
            log_message(f"🗑️ Đã xóa video thành phẩm: {title or os.path.basename(item_path)}")
            
            self.send_response(200 if success else 500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "errors": errors, "title": title}).encode("utf-8"))
            return

        # API: Delete All Finished Results
        if parsed.path == "/api/delete_all_results":
            dest_path = body_data.get("dest", os.path.join(BASE_DIR, "Tiktok_Builder_Output"))
            success, errors = delete_all_finished_results(dest_path)
            log_message("🗑️ Đã xóa toàn bộ video thành phẩm trong thư mục đích.")
            
            self.send_response(200 if success else 500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "errors": errors}).encode("utf-8"))
            return

        # API: Toggle Posted status of a clip
        if parsed.path == "/api/publishing/toggle_post":
            acc_name = body_data.get("account_name", "")
            clip_key = body_data.get("clip_key", "")
            channel = body_data.get("channel", "")
            title = body_data.get("title", "")
            posted = bool(body_data.get("posted", True))
            
            success, res_val = toggle_publishing_clip_status(acc_name, clip_key, channel, title, posted)
            self.send_response(200 if success else 400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "posted": posted, "posted_at": res_val if success else "", "error": res_val if not success else ""}).encode("utf-8"))
            return

        # API: Change TikTok Account Target YouTube Channel
        if parsed.path == "/api/publishing/change_target":
            acc_name = body_data.get("account_name", "")
            new_target = body_data.get("new_target_channel", "")
            
            success, err = change_account_target_channel(acc_name, new_target)
            log_message(f"🎯 Đổi kênh mục tiêu của tài khoản {acc_name} sang: {new_target}")
            
            self.send_response(200 if success else 400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "new_target": new_target, "error": err}).encode("utf-8"))
            return

        # API: Batch Toggle Posted status
        if parsed.path == "/api/publishing/batch_toggle":
            acc_name = body_data.get("account_name", "")
            clip_keys = body_data.get("clip_keys", [])
            posted = bool(body_data.get("posted", True))
            
            success, err = batch_toggle_publishing_clips(acc_name, clip_keys, posted)
            self.send_response(200 if success else 400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "error": err}).encode("utf-8"))
            return

        self.send_error(404)

def run_server():
    try:
        ensure_channel_folders()
    except Exception as e:
        print(f"Lỗi khởi tạo thư mục kênh: {e}")
        
    server_address = ('', PORT)
    httpd = ThreadingHTTPServer(server_address, StudioServerHandler)
    try:
        print(f"🎬 TikTok Studio Webform đang chạy tại: http://localhost:{PORT}")
    except Exception:
        print(f"TikTok Studio Webform running at: http://localhost:{PORT}")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()
