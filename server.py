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
    load_accounts_data, save_accounts_data, ensure_channel_folders,
    load_settings, save_settings, get_pending_publishing_queue, resolve_google_drive_path
)
from hma_manager import (
    find_hma_executable, get_current_public_ip, connect_hma, change_ip_hma, disconnect_hma
)
from adspower_manager import (
    check_adspower_status, get_adspower_profiles, start_adspower_browser, stop_adspower_browser, is_browser_active
)
from tiktok_uploader import upload_video_to_tiktok_cdp
from video_processor import get_video_duration, process_video_custom, split_video_custom


PORT = 8000
LOG_MESSAGES = []
CURRENT_TASK = "Sẵn sàng"
PROGRESS_PERCENT = 0
IS_RUNNING = False
CANCEL_REQUESTED = False

# Quản lý Jobs đa nhiệm cho n8n & REST API
JOBS = {}
JOBS_LOCK = threading.Lock()

def create_job(job_type, payload=None):
    job_id = f"job_{int(time.time()*1000)}_{os.urandom(2).hex()}"
    with JOBS_LOCK:
        JOBS[job_id] = {
            "job_id": job_id,
            "type": job_type,
            "status": "queued",
            "progress": 0,
            "current_task": "Khởi tạo job...",
            "logs": [],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": "",
            "result": None,
            "error": None,
            "callback_url": payload.get("callback_url", "") if payload else ""
        }
    return job_id

def update_job(job_id, **kwargs):
    if not job_id:
        return
    with JOBS_LOCK:
        if job_id in JOBS:
            for k, v in kwargs.items():
                if k == "log":
                    timestamp = time.strftime("[%H:%M:%S]")
                    log_entry = f"{timestamp} {v}"
                    JOBS[job_id]["logs"].append(log_entry)
                    if len(JOBS[job_id]["logs"]) > 200:
                        JOBS[job_id]["logs"].pop(0)
                else:
                    JOBS[job_id][k] = v

def get_job(job_id):
    with JOBS_LOCK:
        if job_id in JOBS:
            return dict(JOBS[job_id])
    return None

def notify_webhook(job_id):
    job = get_job(job_id)
    if job and job.get("callback_url"):
        callback_url = job["callback_url"]
        def send_callback():
            try:
                import urllib.request
                data_bytes = json.dumps(job, ensure_ascii=False).encode('utf-8')
                req = urllib.request.Request(
                    callback_url,
                    data=data_bytes,
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                        "User-Agent": "TikTok-Studio-n8n-Dispatcher/1.0"
                    }
                )
                with urllib.request.urlopen(req, timeout=15) as res:
                    print(f"📡 Webhook sent to {callback_url}, response code: {res.status}")
            except Exception as e:
                print(f"⚠️ Webhook callback error to {callback_url}: {e}")
        threading.Thread(target=send_callback, daemon=True).start()

def verify_auth_if_configured(handler):
    """Xác thực X-API-Key hoặc Authorization Bearer nếu được cấu hình trong settings.json"""
    settings = load_settings()
    api_key_cfg = settings.get("api_key", "").strip()
    if not api_key_cfg:
        return True
        
    auth_header = handler.headers.get("X-API-Key", "") or handler.headers.get("x-api-key", "")
    if not auth_header:
        auth = handler.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            auth_header = auth[7:].strip()
            
    if auth_header == api_key_cfg:
        return True
        
    handler.send_response(401)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.end_headers()
    handler.wfile.write(json.dumps({"success": False, "error": "Unauthorized: Invalid or missing API Key"}).encode("utf-8"))
    return False

def log_message(msg):
    global LOG_MESSAGES
    timestamp = time.strftime("[%H:%M:%S]")
    formatted = f"{timestamp} {msg}"
    print(formatted)
    LOG_MESSAGES.append(formatted)
    if len(LOG_MESSAGES) > 200:
        LOG_MESSAGES.pop(0)

def execute_single_tiktok_post(
    acc_name,
    clip_key="",
    channel="",
    title="",
    specific_file="",
    part_label="",
    override_caption="",
    override_hashtags="",
    auto_submit_override=None,
    log_func=None
):
    """
    Quy trình chuẩn hóa đăng video lên TikTok (HMA -> AdsPower -> Playwright -> Matrix update)
    Dùng chung cho cả Web Dashboard và n8n API.
    """
    def emit_log(msg):
        if log_func:
            log_func(msg)
        log_message(msg)

    accounts_data = load_accounts_data()
    target_acc = None
    for a in accounts_data.get("tiktok_accounts", []):
        if a.get("account_name") == acc_name:
            target_acc = a
            break

    if not target_acc:
        return {"success": False, "error": f"Không tìm thấy thông tin tài khoản @{acc_name}"}

    settings = load_settings()
    adspower_settings = settings.get("adspower", {})
    hma_settings = settings.get("hma", {})
    tiktok_settings = settings.get("tiktok_upload", {})

    auto_submit = auto_submit_override if auto_submit_override is not None else tiktok_settings.get("auto_submit", True)
    close_browser = tiktok_settings.get("close_browser_after_finish", False)
    wait_timeout = tiktok_settings.get("wait_timeout", 60)

    # Tìm tệp video thực tế
    video_file = specific_file
    if not video_file or not os.path.exists(video_file):
        dest_dir = accounts_data.get("dest_path", os.path.join(BASE_DIR, "Tiktok_Builder_Output"))
        resolved_dest = resolve_google_drive_path(dest_dir)
        target_dir = os.path.join(resolved_dest, sanitize_filename(channel), sanitize_filename(title))
        
        if os.path.exists(target_dir):
            mp4s = [f for f in os.listdir(target_dir) if f.endswith('.mp4')]
            if part_label:
                p_match = [f for f in mp4s if part_label.lower() in f.lower() or f"{part_label.replace(' ', '')}".lower() in f.lower()]
                if p_match:
                    video_file = os.path.join(target_dir, p_match[0])
            if not video_file:
                part_1 = [f for f in mp4s if 'part 1.mp4' in f or 'part_1.mp4' in f]
                if part_1:
                    video_file = os.path.join(target_dir, part_1[0])
                elif mp4s:
                    video_file = os.path.join(target_dir, mp4s[0])

    if not video_file or not os.path.exists(video_file):
        return {"success": False, "error": f"Không tìm thấy tệp video để tải lên cho clip '{title}'"}

    upload_title = override_caption if override_caption else title
    if part_label and part_label not in upload_title:
        upload_title = f"{upload_title} ({part_label})"

    hashtags = override_hashtags if override_hashtags is not None else target_acc.get("hashtag", "")

    emit_log(f"🚀 [Auto-Post] Bắt đầu quy trình đăng clip '{upload_title}' cho tài khoản @{acc_name}")
    step_logs = []

    # 1. Chuyển IP HMA nếu được bật
    hma_enabled = hma_settings.get("enabled", True)
    hma_cli = hma_settings.get("cli_path", "")
    target_ip_loc = target_acc.get("build_up_ip") or target_acc.get("original_ip") or ""

    if hma_enabled and target_ip_loc:
        emit_log(f"🛡️ [1/4] Kích hoạt HMA VPN chuyển IP sang: '{target_ip_loc}'...")
        hma_res = connect_hma(target_ip_loc, hma_cli)
        step_logs.append(f"HMA kết nối: {hma_res.get('message') or hma_res.get('error')}")
        wait_sec = int(hma_settings.get("wait_seconds_after_switch", 4))
        time.sleep(wait_sec)
    else:
        step_logs.append("HMA: Bỏ qua (chưa cấu hình vị trí hoặc HMA tắt)")

    # 2. Khởi chạy Profile AdsPower
    profile_id = target_acc.get("adspower_id") or target_acc.get("adspower_serial") or target_acc.get("account_name")
    emit_log(f"⚡ [2/4] Khởi chạy Profile AdsPower: '{profile_id}'...")
    ads_url = adspower_settings.get("api_url", "http://local.adspower.net:50325")
    ads_key = adspower_settings.get("api_key", "")

    ads_res = start_adspower_browser(profile_id, ads_url, ads_key)
    if not ads_res.get("success"):
        error_msg = f"Không thể mở Profile AdsPower '{profile_id}': {ads_res.get('error')}"
        emit_log(f"❌ {error_msg}")
        return {"success": False, "error": error_msg, "step_logs": step_logs}

    ws_endpoint = ads_res.get("ws_endpoint")
    emit_log(f"🌐 [3/4] Đã mở Chrome AdsPower (CDP: {ws_endpoint}). Tiến hành upload clip '{upload_title}'...")

    # 3. Tự động hóa đăng video bằng Playwright CDP
    def uploader_log(msg):
        emit_log(f"  └─ {msg}")
        step_logs.append(msg)

    upload_res = upload_video_to_tiktok_cdp(
        ws_endpoint=ws_endpoint,
        video_path=video_file,
        title=upload_title,
        hashtags=hashtags,
        auto_submit=auto_submit,
        close_browser_after=close_browser,
        wait_timeout=wait_timeout,
        log_callback=uploader_log
    )

    if upload_res.get("success"):
        # 4. Đánh dấu Đã đăng
        toggle_publishing_clip_status(acc_name, clip_key, channel, title, posted=True, part_label=part_label)
        emit_log(f"🎉 [4/4] Đã đăng clip '{upload_title}' thành công!")
        return {
            "success": True,
            "message": f"Đăng clip '{upload_title}' lên TikTok thành công!",
            "video_file": video_file,
            "part_label": part_label,
            "caption": upload_title,
            "hashtags": hashtags,
            "step_logs": step_logs
        }
    else:
        return {
            "success": False,
            "error": upload_res.get("error", "Lỗi trong quá trình đăng clip"),
            "step_logs": step_logs
        }

def batch_worker(payload, job_id=None):
    global IS_RUNNING, CANCEL_REQUESTED, PROGRESS_PERCENT, CURRENT_TASK
    IS_RUNNING = True
    CANCEL_REQUESTED = False
    PROGRESS_PERCENT = 0
    if job_id:
        update_job(job_id, status="running", progress=0, current_task="Bắt đầu batch render")
    
    video_items = payload.get("video_items", [])
    dest_folder = payload.get("dest_folder", os.path.join(BASE_DIR, "Tiktok_Builder_Output"))
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
            channel = parent if parent else "Channel"
            video_items.append({
                "path": path,
                "title": title,
                "channel": channel
            })

    total = len(video_items)
    log_message(f"🚀 Bắt đầu Batch Render: {total} video | Tỉ lệ: {settings['aspect_ratio']} | Nơi xuất: {dest_folder}")
    if job_id:
        update_job(job_id, log=f"Bắt đầu Batch Render: {total} video | Tỉ lệ: {settings['aspect_ratio']}")

    history = load_history()
    rendered_results = []

    for idx, item in enumerate(video_items):
        if CANCEL_REQUESTED:
            log_message("⚠️ Tiến trình đã bị dừng bởi người dùng.")
            if job_id:
                update_job(job_id, status="cancelled", log="Tiến trình đã bị dừng bởi người dùng")
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
        if job_id:
            update_job(job_id, progress=PROGRESS_PERCENT, current_task=CURRENT_TASK, log=f"[{idx+1}/{total}] Đang render: {title}")

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
            "channel": channel,
            "status": "edited",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "output_dir": video_out_dir,
            "parts_count": len(split_files)
        }
        save_history(history)
        log_message(f"🎉 Hoàn thành xuất sắc: {title} ({len(split_files)} parts)")

        rendered_results.append({
            "title": title,
            "channel": channel,
            "output_dir": video_out_dir,
            "split_files": split_files
        })

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
    if job_id:
        update_job(
            job_id,
            status="completed",
            progress=100,
            current_task=CURRENT_TASK,
            finished_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            result={"rendered_videos": rendered_results, "total": len(rendered_results)}
        )
        notify_webhook(job_id)

def auto_pipeline_worker(job_id, payload):
    """
    Worker xử lý trọn gói quy trình tự động hóa cho n8n:
    Render GPU -> Cắt part -> Đổi IP HMA -> Mở AdsPower -> Playwright Upload -> Cập nhật ma trận -> Callback Webhook
    """
    action = payload.get("action", "full_pipeline")
    update_job(job_id, status="running", progress=5, current_task="Khởi chạy pipeline...")
    
    try:
        if action in ["render_only", "full_pipeline"]:
            update_job(job_id, progress=10, current_task="Đang render video...")
            batch_worker(payload, job_id=job_id)
            if CANCEL_REQUESTED:
                return

        if action in ["post_only", "full_pipeline"]:
            update_job(job_id, progress=65, current_task="Đang kết nối TikTok & đăng bài...")
            acc_name = payload.get("account_name", "")
            clip_key = payload.get("clip_key", "")
            channel = payload.get("channel", "")
            title = payload.get("title", "")
            specific_file = payload.get("video_file", "")
            part_label = payload.get("part_label", "")
            override_caption = payload.get("override_caption", "")
            override_hashtags = payload.get("override_hashtags", "")
            auto_submit = payload.get("auto_submit", None)

            def job_log(msg):
                update_job(job_id, log=msg)

            post_res = execute_single_tiktok_post(
                acc_name=acc_name,
                clip_key=clip_key,
                channel=channel,
                title=title,
                specific_file=specific_file,
                part_label=part_label,
                override_caption=override_caption,
                override_hashtags=override_hashtags,
                auto_submit_override=auto_submit,
                log_func=job_log
            )

            if not post_res.get("success"):
                update_job(
                    job_id,
                    status="failed",
                    progress=100,
                    error=post_res.get("error", "Lỗi đăng bài"),
                    result=post_res,
                    finished_at=time.strftime("%Y-%m-%d %H:%M:%S")
                )
                notify_webhook(job_id)
                return

            update_job(
                job_id,
                status="completed",
                progress=100,
                current_task="Quy trình Auto-Post hoàn tất thành công!",
                result=post_res,
                finished_at=time.strftime("%Y-%m-%d %H:%M:%S")
            )
            notify_webhook(job_id)
            return

    except Exception as e:
        update_job(
            job_id,
            status="failed",
            error=str(e),
            finished_at=time.strftime("%Y-%m-%d %H:%M:%S")
        )
        notify_webhook(job_id)


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
            dest_path = data.get("dest_path", os.path.join(BASE_DIR, "Tiktok_Builder_Output"))
            
            # Quét tổng số video thực tế (cả thô và thành phẩm) của mỗi kênh
            scan_res = scan_source_directory(source_path, dest_path)
            folder_counts = {}
            for f in scan_res.get("folders", []):
                fname = f.get("name", "")
                folder_counts[fname] = len(f.get("videos", []))
                folder_counts[sanitize_filename(fname)] = len(f.get("videos", []))

            for chan in data.get("youtube_channels", []):
                folder_name = chan.get("folder_name", chan.get("name"))
                c_count = folder_counts.get(folder_name, folder_counts.get(sanitize_filename(folder_name), 0))
                chan["total_downloaded"] = c_count

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

        # API: Get System Settings (AdsPower, HMA, TikTok Upload)
        if parsed.path == "/api/settings":
            settings = load_settings()
            settings["hma_detected_path"] = find_hma_executable()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(settings).encode("utf-8"))
            return

        # API: Get AdsPower Profiles List
        if parsed.path == "/api/adspower/profiles":
            settings = load_settings()
            api_url = query.get("api_url", [settings.get("adspower", {}).get("api_url", "")])[0]
            api_key = query.get("api_key", [settings.get("adspower", {}).get("api_key", "")])[0]
            res = get_adspower_profiles(api_url=api_url, api_key=api_key)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        # API: n8n Pending Clips Queue
        if parsed.path == "/api/n8n/pending_clips":
            if not verify_auth_if_configured(self):
                return
            acc_filter = query.get("account_name", [None])[0]
            chan_filter = query.get("channel_name", [None])[0]
            only_target_raw = query.get("only_current_target", ["true"])[0]
            only_target = only_target_raw.lower() not in ["false", "0", "no"]
            
            queue = get_pending_publishing_queue(
                account_name=acc_filter,
                channel_name=chan_filter,
                only_current_target=only_target
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "total_pending": len(queue),
                "items": queue
            }, ensure_ascii=False).encode("utf-8"))
            return

        # API: Pipeline Job Status
        if parsed.path == "/api/pipeline/job_status":
            if not verify_auth_if_configured(self):
                return
            target_job_id = query.get("job_id", [None])[0]
            if target_job_id:
                job = get_job(target_job_id)
                if not job:
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "error": f"Không tìm thấy Job ID '{target_job_id}'"}).encode("utf-8"))
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "job": job}, ensure_ascii=False).encode("utf-8"))
                return
            else:
                with JOBS_LOCK:
                    all_jobs = list(JOBS.values())[-30:]
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "jobs": all_jobs}, ensure_ascii=False).encode("utf-8"))
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
        if parsed.path == "/api/start_batch" or parsed.path == "/api/pipeline/start_batch":
            if parsed.path.startswith("/api/pipeline/") and not verify_auth_if_configured(self):
                return
            global IS_RUNNING
            if IS_RUNNING:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Tiến trình render đang chạy!"}).encode("utf-8"))
                return

            job_id = create_job("batch_render", body_data)
            t = threading.Thread(target=batch_worker, args=(body_data, job_id), daemon=True)
            t.start()

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started", "job_id": job_id}).encode("utf-8"))
            return

        # API: Stop Batch Processing
        if parsed.path == "/api/stop_batch" or parsed.path == "/api/pipeline/stop_batch":
            if parsed.path.startswith("/api/pipeline/") and not verify_auth_if_configured(self):
                return
            global CANCEL_REQUESTED
            CANCEL_REQUESTED = True
            log_message("🛑 Nhận được tín hiệu dừng từ người dùng.")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "stopping"}).encode("utf-8"))
            return

        # API: n8n All-in-One Pipeline (Auto Process & Post)
        if parsed.path == "/api/pipeline/auto_process_and_post":
            if not verify_auth_if_configured(self):
                return
            job_id = create_job("auto_process_and_post", body_data)
            t = threading.Thread(target=auto_pipeline_worker, args=(job_id, body_data), daemon=True)
            t.start()

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "status": "queued",
                "job_id": job_id,
                "message": f"Pipeline đã được khởi chạy trong nền. Kiểm tra tiến độ tại /api/pipeline/job_status?job_id={job_id}"
            }, ensure_ascii=False).encode("utf-8"))
            return

        # API: Open Folder in Explorer
        if parsed.path == "/api/open_folder":
            fpath = body_data.get("path", body_data.get("folder_path", ""))
            log_message(f"📂 Yêu cầu mở thư mục: {fpath}")
            if fpath:
                fpath = fpath.strip().strip('"').strip("'")
                
                # Nếu là liên kết web
                if fpath.startswith("http://") or fpath.startswith("https://"):
                    import webbrowser
                    webbrowser.open(fpath)
                else:
                    from drive_manager import resolve_google_drive_path
                    resolved = resolve_google_drive_path(fpath)
                    if resolved and os.path.exists(resolved):
                        fpath = resolved

                    norm_path = os.path.normpath(fpath)
                    
                    if os.path.isfile(norm_path):
                        norm_path = os.path.dirname(norm_path)
                        
                    if os.path.exists(norm_path):
                        if os.name == 'nt':
                            try:
                                os.startfile(norm_path)
                            except Exception:
                                subprocess.Popen(f'explorer "{norm_path}"', shell=True)
                        else:
                            subprocess.Popen(['xdg-open', norm_path])
                    else:
                        # Thử tạo thư mục nếu chưa tồn tại
                        try:
                            os.makedirs(norm_path, exist_ok=True)
                            if os.name == 'nt':
                                os.startfile(norm_path)
                        except Exception as e:
                            log_message(f"❌ Không thể mở thư mục '{norm_path}': {e}")
                            
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "opened", "path": fpath}).encode("utf-8"))
            return

        # API: Open File in explorer and select it
        if parsed.path == "/api/open_file":
            filepath = body_data.get("path", "")
            log_message(f"📄 Yêu cầu mở file: {filepath}")
            if filepath:
                filepath = filepath.strip().strip('"').strip("'")
                norm_path = os.path.normpath(filepath)
                if os.path.exists(norm_path):
                    if os.name == 'nt':
                        subprocess.Popen(f'explorer /select,"{norm_path}"', shell=True)
                    else:
                        subprocess.Popen(['xdg-open', os.path.dirname(norm_path)])
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
                output = subprocess.check_output(cmd, text=True, timeout=60).strip()
                folder_path = output
            except Exception as e:
                log_message(f"⚠️ Lỗi Tkinter file picker ({e}), thử fallback PowerShell...")
                try:
                    ps_cmd = [
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        "Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.FolderBrowserDialog; $f.Description = 'Chọn Thư Mục Dự Án'; if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $f.SelectedPath }"
                    ]
                    output = subprocess.check_output(ps_cmd, text=True, timeout=60).strip()
                    folder_path = output
                except Exception as ps_err:
                    log_message(f"❌ Lỗi PowerShell folder picker: {ps_err}")
                
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

        # API: Toggle Posted status of a clip or specific part
        if parsed.path == "/api/publishing/toggle_post":
            acc_name = body_data.get("account_name", "")
            clip_key = body_data.get("clip_key", "")
            channel = body_data.get("channel", "")
            title = body_data.get("title", "")
            posted = bool(body_data.get("posted", True))
            part_label = body_data.get("part_label", None)
            
            success, res_val = toggle_publishing_clip_status(acc_name, clip_key, channel, title, posted, part_label=part_label)
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
            self.send_response(200 if success else 400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "error": err if not success else ""}).encode("utf-8"))
            return

        # API: Batch Toggle Posted status for multiple clips
        if parsed.path == "/api/publishing/batch_toggle_post":
            acc_name = body_data.get("account_name", "")
            clip_keys = body_data.get("clip_keys", [])
            posted = bool(body_data.get("posted", True))
            
            success, count = batch_toggle_publishing_clips(acc_name, clip_keys, posted)
            self.send_response(200 if success else 400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "count": count}).encode("utf-8"))
            return

        # API: Save Settings (AdsPower, HMA, TikTok Upload)
        if parsed.path == "/api/settings/save":
            settings = load_settings()
            if "adspower" in body_data:
                settings["adspower"] = body_data["adspower"]
            if "hma" in body_data:
                settings["hma"] = body_data["hma"]
            if "tiktok_upload" in body_data:
                settings["tiktok_upload"] = body_data["tiktok_upload"]
            save_settings(settings)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "message": "Đã lưu cài đặt thành công"}).encode("utf-8"))
            return

        # API: Test AdsPower Connection & Load Profiles
        if parsed.path == "/api/adspower/test":
            api_url = body_data.get("api_url", "")
            api_key = body_data.get("api_key", "")
            status_res = check_adspower_status(api_url, api_key)
            if status_res.get("connected"):
                prof_res = get_adspower_profiles(api_url, api_key)
                status_res["profiles"] = prof_res.get("profiles", [])
                status_res["total"] = prof_res.get("total", 0)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(status_res).encode("utf-8"))
            return

        # API: Start AdsPower Browser
        if parsed.path == "/api/adspower/start":
            profile_id = body_data.get("profile_id", "")
            api_url = body_data.get("api_url", "")
            api_key = body_data.get("api_key", "")
            res = start_adspower_browser(profile_id, api_url, api_key)
            self.send_response(200 if res.get("success") else 400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        # API: Stop AdsPower Browser
        if parsed.path == "/api/adspower/stop":
            profile_id = body_data.get("profile_id", "")
            api_url = body_data.get("api_url", "")
            api_key = body_data.get("api_key", "")
            res = stop_adspower_browser(profile_id, api_url, api_key)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        # API: Test HMA IP & Location
        if parsed.path == "/api/hma/test_ip":
            res = get_current_public_ip()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        # API: Connect HMA VPN
        if parsed.path == "/api/hma/connect":
            location = body_data.get("location", "")
            cli_path = body_data.get("cli_path", "")
            res = connect_hma(location, cli_path)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        # API: Change HMA VPN IP
        if parsed.path == "/api/hma/change_ip":
            cli_path = body_data.get("cli_path", "")
            res = change_ip_hma(cli_path)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        # API: Disconnect HMA VPN
        if parsed.path == "/api/hma/disconnect":
            cli_path = body_data.get("cli_path", "")
            res = disconnect_hma(cli_path)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        # API: Comprehensive Auto-Post to TikTok (HMA IP -> AdsPower Browser -> Playwright Upload -> Update Status)
        if parsed.path == "/api/publishing/post_to_tiktok" or parsed.path == "/api/pipeline/post_to_tiktok":
            if parsed.path.startswith("/api/pipeline/") and not verify_auth_if_configured(self):
                return

            acc_name = body_data.get("account_name", "")
            clip_key = body_data.get("clip_key", "")
            channel = body_data.get("channel", "")
            title = body_data.get("title", "")
            specific_file = body_data.get("video_file", "")
            part_label = body_data.get("part_label", "")
            override_caption = body_data.get("override_caption", "")
            override_hashtags = body_data.get("override_hashtags", "")
            auto_submit_override = body_data.get("auto_submit", None)
            is_async = body_data.get("async", False) or bool(body_data.get("callback_url"))

            if is_async:
                job_id = create_job("post_to_tiktok", body_data)
                def async_post():
                    update_job(job_id, status="running", progress=10, current_task=f"Đang đăng clip cho @{acc_name}")
                    def job_log(msg):
                        update_job(job_id, log=msg)
                    res = execute_single_tiktok_post(
                        acc_name=acc_name,
                        clip_key=clip_key,
                        channel=channel,
                        title=title,
                        specific_file=specific_file,
                        part_label=part_label,
                        override_caption=override_caption,
                        override_hashtags=override_hashtags,
                        auto_submit_override=auto_submit_override,
                        log_func=job_log
                    )
                    if res.get("success"):
                        update_job(job_id, status="completed", progress=100, current_task="Đăng clip thành công!", result=res, finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))
                    else:
                        update_job(job_id, status="failed", progress=100, error=res.get("error", "Lỗi đăng bài"), result=res, finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))
                    notify_webhook(job_id)

                threading.Thread(target=async_post, daemon=True).start()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "status": "queued",
                    "job_id": job_id,
                    "message": f"Yêu cầu đăng clip đã được xếp hàng. Kiểm tra tại /api/pipeline/job_status?job_id={job_id}"
                }, ensure_ascii=False).encode("utf-8"))
                return

            # Chạy đồng bộ (Sync)
            post_res = execute_single_tiktok_post(
                acc_name=acc_name,
                clip_key=clip_key,
                channel=channel,
                title=title,
                specific_file=specific_file,
                part_label=part_label,
                override_caption=override_caption,
                override_hashtags=override_hashtags,
                auto_submit_override=auto_submit_override
            )

            if post_res.get("success"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(post_res, ensure_ascii=False).encode("utf-8"))
                return
            else:
                self.send_response(500 if "Lỗi" in str(post_res.get("error", "")) else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(post_res, ensure_ascii=False).encode("utf-8"))
                return

        # API: System Scheduled Shutdown (Cho kịch bản ban đêm)
        if parsed.path == "/api/system/shutdown":
            if not verify_auth_if_configured(self):
                return
            delay_sec = int(body_data.get("delay_seconds", 900))
            msg = f"Hẹn giờ tắt máy tính sau {delay_sec} giây ({round(delay_sec/60)} phút)"
            log_message(f"💤 {msg}")
            try:
                subprocess.Popen(["shutdown", "/s", "/t", str(delay_sec), "/c", "TikTok Studio Pro: Hoàn thành tác vụ ban đêm. Máy tính sẽ tự động tắt."])
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": msg, "delay_seconds": delay_sec}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        # API: Cancel Scheduled Shutdown
        if parsed.path == "/api/system/cancel_shutdown":
            if not verify_auth_if_configured(self):
                return
            log_message("⚡ Đã hủy lệnh hẹn giờ tắt máy tính.")
            try:
                subprocess.Popen(["shutdown", "/a"])
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": "Đã hủy lệnh tắt máy tính thành công!"}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
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
