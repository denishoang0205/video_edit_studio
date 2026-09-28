import os
import sys

if hasattr(sys, 'stdout') and sys.stdout is not None and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys, 'stderr') and sys.stderr is not None and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import json
import time
import socket
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

import urllib.request

# Set base dir
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
try:
    os.chdir(BASE_DIR)
except Exception:
    pass

from src.services.drive_service import (
    scan_source_directory, scan_finished_results, load_history, save_history, 
    delete_finished_result, delete_all_finished_results, invalidate_drive_caches,
    get_publishing_matrix, toggle_publishing_clip_status, change_account_target_channel, batch_toggle_publishing_clips,
    load_accounts_data, save_accounts_data, ensure_channel_folders,
    load_settings, save_settings, get_pending_publishing_queue, get_account_daily_posted_count,
    generate_video_id
)
from src.services.hma_service import (
    find_hma_executable, get_current_public_ip, connect_hma, change_ip_hma, disconnect_hma
)
from src.services.adspower_service import (
    check_adspower_status, get_adspower_profiles, start_adspower_browser, stop_adspower_browser, is_browser_active
)
from src.services.tiktok_uploader import upload_video_to_tiktok_cdp, upload_multiple_videos_to_tiktok_cdp, clean_caption_text
from src.services.video_processor import (
    get_video_duration, process_video_custom, split_video_custom,
    detect_video_highlights, process_and_split_video
)


PORT = int(os.environ.get("PORT", 8000))
LOG_MESSAGES = []
CURRENT_TASK = "Sẵn sàng"
PROGRESS_PERCENT = 0
IS_RUNNING = False
CANCEL_REQUESTED = False
IS_ANALYTICS_COLLECTING = False
ANALYTICS_LOGS = []
PUBLISHING_LOCK = threading.Lock()
LAST_PUBLISHING_STATE = {
    "is_busy": False,
    "account_name": "",
    "success": False,
    "count": 0,
    "error": "",
    "today_posted_count": 0,
    "timestamp": 0
}

def send_telegram_notification(message, parse_mode="HTML"):
    """Gửi thông báo đến Telegram Bot cá nhân với cơ chế Fallback chống lỗi định dạng"""
    try:
        settings = load_settings()
        tg = settings.get("telegram", {})
        if not tg.get("enabled", True):
            return False
        bot_token = tg.get("bot_token", "").strip()
        chat_id = str(tg.get("chat_id", "")).strip()
        if not bot_token or not chat_id:
            return False
            
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        # 1. Thử gửi với parse_mode (HTML hoặc Markdown)
        payload = {
            "chat_id": chat_id,
            "text": message
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
            
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "TikTokStudio/1.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except urllib.error.HTTPError as he:
            # 2. Fallback: Nếu lỗi parse HTML/Markdown, tự động gửi dạng Plain Text thuần túy để đảm bảo 100% tin nhắn đến đích
            payload.pop("parse_mode", None)
            plain_data = json.dumps(payload).encode("utf-8")
            req_plain = urllib.request.Request(
                url,
                data=plain_data,
                headers={"Content-Type": "application/json", "User-Agent": "TikTokStudio/1.0"}
            )
            with urllib.request.urlopen(req_plain, timeout=10) as resp_plain:
                return resp_plain.status == 200
    except Exception as e:
        print(f"[Telegram Error] Không thể gửi tin nhắn Telegram: {e}")
        return False

def log_message(msg):
    global LOG_MESSAGES
    timestamp = time.strftime("[%H:%M:%S]")
    formatted = f"{timestamp} {msg}"
    try:
        if sys.stdout is not None:
            print(formatted)
    except Exception:
        pass
    LOG_MESSAGES.append(formatted)
    if len(LOG_MESSAGES) > 500:
        LOG_MESSAGES.pop(0)

def batch_worker(payload):
    global IS_RUNNING, CANCEL_REQUESTED, PROGRESS_PERCENT, CURRENT_TASK
    IS_RUNNING = True
    CANCEL_REQUESTED = False
    PROGRESS_PERCENT = 0
    
    video_items = payload.get("video_items", [])
    from src.services.drive_service import resolve_google_drive_path
    dest_folder = payload.get("dest_folder", os.path.join(BASE_DIR, "output_product"))
    dest_folder = resolve_google_drive_path(dest_folder)
    if not dest_folder or dest_folder.startswith(('http://', 'https://')):
        dest_folder = os.path.join(BASE_DIR, "output_product")
        
    settings = {
        "aspect_ratio": payload.get("aspect_ratio", "3:4"),
        "blur_bg": payload.get("blur_bg", True),
        "hflip": payload.get("hflip", False),
        "color_boost": payload.get("color_boost", True),
        "banner_box_style": payload.get("banner_box_style", "white-rounded"),
        "banner_font": payload.get("banner_font", "Poppins-Bold"),
        "banner_font_size": payload.get("banner_font_size", 46),
        "banner_position": payload.get("banner_position", "top"),
        "localization": payload.get("localization_settings", {})
    }
    split_mode = payload.get("split_mode", "auto")
    export_full = payload.get("export_full", False)

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
    log_message(f"🚀 Bắt đầu Batch Render: {total} video | Tỉ lệ: {settings['aspect_ratio']} | Chế độ: {split_mode} | Nơi xuất: {dest_folder}")

    history = load_history()

    try:
        for idx, item in enumerate(video_items):
            if CANCEL_REQUESTED:
                log_message("⚠️ Tiến trình đã bị dừng bởi người dùng.")
                break

            raw_path = item.get("path")
            title = item.get("title")
            channel = item.get("channel", "Channel")
            is_short_flag = item.get("is_short", False)

            # 1. Làm sạch và unescape đường dẫn / tiêu đề nếu bị escape từ Webform
            if raw_path:
                raw_path = raw_path.replace(r"\'", "'").replace(r'\"', '"').strip().strip('"').strip("'")
                raw_path = os.path.normpath(raw_path)

            if title:
                title = title.replace(r"\'", "'").replace(r'\"', '"').strip()

            if channel:
                channel = channel.replace(r"\'", "'").replace(r'\"', '"').strip()

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

            # 2. Tìm kiếm dự phòng thông minh nếu đường dẫn trực tiếp không tồn tại
            if not actual_video_file or os.path.isdir(actual_video_file) or not os.path.exists(actual_video_file):
                from src.core.config import VIDEO_DIR
                clean_title = (title or "").replace(r"\'", "'").replace(r'\"', '"').strip()
                san_title = sanitize_filename(clean_title)
                
                candidate_dirs = [
                    os.path.join(VIDEO_DIR, channel),
                    os.path.join(VIDEO_DIR, sanitize_filename(channel)),
                    os.path.join(BASE_DIR, "video", channel),
                    os.path.join(BASE_DIR, "video", sanitize_filename(channel)),
                    VIDEO_DIR,
                    os.path.join(BASE_DIR, "video")
                ]
                
                found_file = None
                for cdir in candidate_dirs:
                    if not os.path.exists(cdir):
                        continue
                    for root, dirs, files in os.walk(cdir):
                        for f in files:
                            if not f.lower().endswith(('.mp4', '.mkv', '.mov', '.avi', '.webm')) or f.startswith(('part_', 'edited_', 'title_banner')):
                                continue
                            f_stem = os.path.splitext(f)[0]
                            if (f_stem == clean_title or 
                                f_stem == san_title or 
                                sanitize_filename(f_stem).lower() == san_title.lower() or
                                (clean_title and clean_title[:25].lower() in f_stem.lower()) or
                                (san_title and san_title[:25].lower() in sanitize_filename(f_stem).lower())):
                                found_file = os.path.join(root, f)
                                break
                        if found_file:
                            break
                    if found_file:
                        break
                
                if found_file and os.path.exists(found_file):
                    actual_video_file = found_file
                    log_message(f"🔍 Tự động phát hiện tệp video nguồn: {os.path.basename(actual_video_file)}")

            # Kiểm tra an toàn lần cuối
            if not actual_video_file or os.path.isdir(actual_video_file) or not os.path.exists(actual_video_file):
                log_message(f"❌ Lỗi: Thư mục nguồn '{title}' không chứa file video hợp lệ!")
                continue

            CURRENT_TASK = f"({idx+1}/{total}) Đang xử lý: {title}"
            log_message(f"▶️ [{idx+1}/{total}] Bắt đầu xử lý: {title} (Kênh: {channel})")
            PROGRESS_PERCENT = int((idx / total) * 100)

            # Thư mục xuất thành phẩm phân cấp: dest_folder / channel / title
            sanitized_channel = sanitize_filename(channel)
            sanitized_title = sanitize_filename(title)
            video_out_dir = os.path.join(dest_folder, sanitized_channel, sanitized_title)
            os.makedirs(video_out_dir, exist_ok=True)

            # Kiểm tra file heatmap cache nếu có
            heatmap_data = None
            from config import TEMP_DIR
            heatmap_cand = os.path.join(TEMP_DIR, f"{sanitize_filename(os.path.basename(actual_video_file))}.heatmap.json")
            if not os.path.exists(heatmap_cand):
                heatmap_cand = os.path.splitext(actual_video_file)[0] + ".heatmap.json"
            if os.path.exists(heatmap_cand):

                try:
                    with open(heatmap_cand, "r", encoding="utf-8") as hf:
                        heatmap_data = json.load(hf)
                except Exception:
                    pass

            def item_progress_cb(done_parts, total_parts):
                global PROGRESS_PERCENT
                base = (idx / total) * 100
                step = (1.0 / total) * (done_parts / max(1, total_parts)) * 100
                PROGRESS_PERCENT = min(99, int(base + step))

            # Thực thi quy trình biên tập thông minh (Short giữ nguyên 1 clip, Long cắt cao trào 30s-45s/1m)
            split_files = process_and_split_video(
                actual_video_file=actual_video_file,
                video_out_dir=video_out_dir,
                title=title,
                settings=settings,
                split_mode=split_mode,
                is_short=is_short_flag,
                export_full=export_full,
                youtube_heatmap=heatmap_data,
                log_cb=log_message,
                progress_cb=item_progress_cb
            )

            if not split_files:
                log_message(f"❌ Thất bại khi biên tập: {title}")
                continue

            # Ghi nhận trạng thái vào history kèm ID unique duy nhất cho video
            v_uid = generate_video_id(channel, title)
            history[title] = {
                "video_id": v_uid,
                "title": title,
                "channel": channel,
                "status": "edited",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "output_dir": video_out_dir,
                "parts_count": len(split_files)
            }
            save_history(history)

            # Lưu file video_meta.json trong thư mục video
            try:
                meta_file_path = os.path.join(video_out_dir, "video_meta.json")
                with open(meta_file_path, "w", encoding="utf-8") as mf:
                    json.dump({
                        "video_id": v_uid,
                        "channel": channel,
                        "title": title,
                        "parts_count": len(split_files),
                        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    }, mf, ensure_ascii=False, indent=2)
            except Exception:
                pass

            log_message(f"🎉 Hoàn thành xuất sắc: {title} ({len(split_files)} parts) [ID: {v_uid}]")

            # Xóa file video gốc, heatmap cache & file phụ đề tạm đi kèm để tiết kiệm dung lượng đĩa
            if actual_video_file and os.path.exists(actual_video_file):
                try:
                    os.remove(actual_video_file)
                    log_message(f"🗑️ Đã xóa tệp video gốc: {os.path.basename(actual_video_file)}")
                    if os.path.exists(heatmap_cand):
                        os.remove(heatmap_cand)
                    # Dọn dẹp sạch các file phụ đề .vtt/.srt đi kèm trong thư mục nguồn
                    base_raw = os.path.splitext(actual_video_file)[0]
                    dir_raw = os.path.dirname(actual_video_file)
                    for ext in ['.vtt', '.en.vtt', '.en-orig.vtt', '.en-US.vtt', '.srt', '.en.srt']:
                        cand_sub = base_raw + ext
                        if os.path.exists(cand_sub):
                            try:
                                os.remove(cand_sub)
                            except Exception:
                                pass
                except Exception as e:
                    log_message(f"⚠️ Lỗi khi xóa video gốc: {e}")


        PROGRESS_PERCENT = 100
        CURRENT_TASK = "Hoàn thành toàn bộ batch!"
        log_message("🏁 ĐÃ HOÀN TẤT TẤT CẢ CÁC TÁC VỤ BIÊN TẬP.")
        
        # Bắn thông báo Telegram
        try:
            send_telegram_notification(
                f"🎉 <b>[HOÀN TẤT BIÊN TẬP BATCH VIDEO]</b>\n\n"
                f"🎬 <b>Tổng số video đã xử lý:</b> {total} video\n"
                f"📐 <b>Tỉ lệ khung hình:</b> {settings.get('aspect_ratio', '3:4')}\n"
                f"⚡ <b>Chế độ biên tập:</b> {split_mode}\n"
                f"📁 <b>Thư mục xuất:</b> <code>{os.path.basename(dest_folder)}</code>\n\n"
                f"🚀 Các clip đã sẵn sàng trong Pipeline để tự động đăng lên TikTok!"
            )
        except Exception as te:
            log_message(f"⚠️ Không thể gửi thông báo Telegram: {te}")
    except Exception as batch_err:
        log_message(f"❌ Lỗi ngoài dự kiến trong Batch Render: {batch_err}")
    finally:
        IS_RUNNING = False

def execute_tiktok_publish(body_data):
    acc_name = body_data.get("account_name", "")
    clip_key = body_data.get("clip_key", "")
    channel = body_data.get("channel", "")
    title = body_data.get("title", "")
    auto_submit_override = body_data.get("auto_submit", None)
    override_caption = body_data.get("override_caption", "").strip()
    override_hashtags = body_data.get("override_hashtags", "").strip()

    # Hỗ trợ nhận danh sách nhiều part (ví dụ 3 part) để mở 3 tab cùng lúc
    incoming_items = body_data.get("items", [])
    if not incoming_items:
        incoming_items = [{
            "video_file": body_data.get("video_file", ""),
            "part_label": body_data.get("part_label", ""),
            "title": title,
            "clip_key": clip_key,
            "channel": channel
        }]

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

    # 0. Kiểm tra Giới hạn Đăng bài (Max 3 clips / ngày / tài khoản)
    max_daily_posts = int(tiktok_settings.get("max_daily_posts_per_account", 3))
    if max_daily_posts > 0:
        today_count = get_account_daily_posted_count(target_acc)
        if today_count >= max_daily_posts:
            err_quota = f"Tài khoản @{acc_name} đã đăng {today_count}/{max_daily_posts} clip hôm nay (đã đạt giới hạn tối đa 3 clip/ngày)."
            log_message(f"⚠️ [Daily Quota Block] {err_quota}")
            send_telegram_notification(
                f"⚠️ *[GIỚI HẠN ĐĂNG BÀI]*\n"
                f"👤 **Tài khoản:** @{acc_name}\n"
                f"📊 **Hôm nay:** Đã đăng đủ `{today_count}/{max_daily_posts}` clip.\n"
                f"🛑 **Hành động:** Tự động dừng để bảo vệ tài khoản và chống spam thuật toán!"
            )
            return {
                "success": False, 
                "error": err_quota, 
                "daily_quota_reached": True,
                "today_count": today_count,
                "max_daily_posts": max_daily_posts
            }

    auto_submit = auto_submit_override if auto_submit_override is not None else tiktok_settings.get("auto_submit", True)
    close_browser = tiktok_settings.get("close_browser_after_finish", False)
    wait_timeout = tiktok_settings.get("wait_timeout", 120)

    dest_dir = accounts_data.get("dest_path", os.path.join(BASE_DIR, "output_product"))
    from src.services.drive_service import resolve_google_drive_path
    resolved_dest = resolve_google_drive_path(dest_dir)

    resolved_upload_items = []
    for item in incoming_items:
        item_title = item.get("title", title)
        item_channel = item.get("channel", channel)
        item_part = item.get("part_label", "")
        item_clip_key = item.get("clip_key", clip_key)
        video_file = item.get("video_file") or item.get("video_path") or item.get("file_path") or ""

        if not video_file or not os.path.exists(video_file):
            target_dir = os.path.join(resolved_dest, sanitize_filename(item_channel), sanitize_filename(item_title))
            if os.path.exists(target_dir):
                mp4s = [f for f in os.listdir(target_dir) if f.endswith('.mp4')]
                if item_part:
                    p_match = [f for f in mp4s if item_part.lower() in f.lower() or f"{item_part.replace(' ', '')}".lower() in f.lower()]
                    if p_match:
                        video_file = os.path.join(target_dir, p_match[0])
                if not video_file:
                    part_1 = [f for f in mp4s if 'part 1.mp4' in f or 'part_1.mp4' in f]
                    if part_1:
                        video_file = os.path.join(target_dir, part_1[0])
                    elif mp4s:
                        video_file = os.path.join(target_dir, mp4s[0])

        # Tự động trích xuất Part X từ tên file nếu item_part bị rỗng
        if not item_part and video_file:
            m_part = re.search(r'part[\s_\-]*(\d+)', os.path.basename(video_file), re.I)
            if m_part:
                item_part = f"Part {m_part.group(1)}"

        # Tự động kiến tạo clip_key nếu bị thiếu
        if not item_clip_key and item_channel and item_title:
            item_clip_key = f"{item_channel}/{item_title}"

        item_vid = item.get("video_id") or generate_video_id(item_channel, item_title)
        if video_file and os.path.exists(video_file):
            resolved_upload_items.append({
                "video_path": video_file,
                "video_id": item_vid,
                "title": item_title,
                "override_caption": item.get("override_caption") or (override_caption if override_caption else None),
                "part_label": item_part,
                "clip_key": item_clip_key,
                "channel": item_channel
            })

    if not resolved_upload_items:
        return {"success": False, "error": f"Không tìm thấy tệp video nào hợp lệ để tải lên"}

    # Pre-Upload Deduplication Safeguard: Kiểm tra theo quy tắc (Account ID + Video ID)
    # Chỉ xem là đã đăng khi CHÍNH TÀI KHOẢN NÀY (@{acc_name}) đã từng đăng video_id đó.
    target_posted_clips = target_acc.get("posted_clips", {})
    filtered_upload_items = []
    skipped_duplicates = []
    
    for item in resolved_upload_items:
        i_key = item.get("clip_key", "")
        i_part = item.get("part_label", "")
        i_title = item.get("title", "")
        i_chan = item.get("channel", "")
        i_vid = item.get("video_id") or generate_video_id(i_chan, i_title)
        
        is_already_posted = False
        post_rec = target_posted_clips.get(i_key, {})
        if not post_rec:
            for pk, pv in target_posted_clips.items():
                if (pv.get("video_id") and pv.get("video_id") == i_vid) or \
                   sanitize_filename(pk).lower() == sanitize_filename(i_key).lower() or \
                   (pv.get("title") == i_title and sanitize_filename(pv.get("channel", "")).lower() == sanitize_filename(i_chan).lower()):
                    post_rec = pv
                    break
        if post_rec:
            if i_part:
                p_stat = post_rec.get("parts_status", {})
                if i_part in p_stat:
                    is_already_posted = bool(p_stat[i_part].get("posted", False))
                elif post_rec.get("posted") and not p_stat:
                    is_already_posted = True
                else:
                    is_already_posted = False
            else:
                is_already_posted = bool(post_rec.get("posted", False))
                
        if is_already_posted:
            skipped_duplicates.append(f"'{i_title}' ({i_part}) [Tài khoản @{acc_name} đã đăng]")
        else:
            filtered_upload_items.append(item)
            
    if skipped_duplicates:
        for s_msg in skipped_duplicates:
            log_message(f"   🛡️ [Chống trùng lặp tài khoản] Bỏ qua clip đã đăng: {s_msg}")
            
    if not filtered_upload_items:
        log_message(f"🛑 [Pre-Upload Check] Toàn bộ video yêu cầu đã được tài khoản @{acc_name} đăng trước đó. Hủy đăng an toàn!")
        return {
            "success": True,
            "count": 0,
            "message": f"Toàn bộ video yêu cầu đã được tài khoản @{acc_name} đăng trước đó trên TikTok. Đã bỏ qua an toàn!",
            "skipped_duplicates": skipped_duplicates
        }
        
    resolved_upload_items = filtered_upload_items

    total_items = len(resolved_upload_items)
    log_message(f"🚀 [Multi-Tab Post] Bắt đầu quy trình đăng đồng thời {total_items} video trên {total_items} tab cho tài khoản @{acc_name}")
    step_logs = []

    global LAST_PUBLISHING_STATE
    LAST_PUBLISHING_STATE["is_busy"] = True
    LAST_PUBLISHING_STATE["account_name"] = acc_name
    LAST_PUBLISHING_STATE["success"] = False
    LAST_PUBLISHING_STATE["count"] = 0
    LAST_PUBLISHING_STATE["error"] = ""
    LAST_PUBLISHING_STATE["timestamp"] = time.time()

    # 1. Kiểm tra An toàn IP (Pre-flight IP Verification)
    hma_enabled = hma_settings.get("enabled", True)
    hma_cli = hma_settings.get("cli_path", "")
    target_ip_loc = target_acc.get("build_up_ip") or target_acc.get("original_ip") or ""
    block_vn_ip = hma_settings.get("block_vietnam_ip", True)

    curr_ip_info = get_current_public_ip()
    curr_country = str(curr_ip_info.get("country", "")).lower()
    curr_code = str(curr_ip_info.get("country_code", "")).upper()
    curr_ip = curr_ip_info.get("ip", "Unknown")

    if block_vn_ip and target_ip_loc and (curr_code == "VN" or "vietnam" in curr_country):
        ip_err_msg = f"Phát hiện IP máy tính là Việt Nam ({curr_ip}). Chưa bật HMA VPN!"
        log_message(f"🛑 [IP SAFETY BLOCK] {ip_err_msg} Đã hủy đăng cho @{acc_name} để bảo vệ nick.")
        send_telegram_notification(
            f"🛑 *[BẢO VỆ TÀI KHOẢN TIKTOK]*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ **Phát hiện IP Việt Nam (VN):** `{curr_ip}`\n"
            f"👤 **Tài khoản:** @{acc_name} (Vùng đích: {target_ip_loc})\n"
            f"🚫 **Hành động:** ĐÃ HỦY ĐĂNG VIDEO để tránh bị TikTok bóp reach hoặc shadowban!\n"
            f"👉 **Hướng dẫn:** Vui lòng bật HMA VPN kết nối sang *{target_ip_loc}* rồi chạy lại."
        )
        return {
            "success": False,
            "error": ip_err_msg,
            "ip_blocked": True,
            "current_ip": curr_ip_info
        }

    if hma_enabled and target_ip_loc:
        log_message(f"🛡️ [1/4] IP hiện tại: {curr_ip} ({curr_ip_info.get('country', 'N/A')}). Mục tiêu: '{target_ip_loc}'...")
        step_logs.append(f"IP kiểm tra: {curr_ip} ({curr_ip_info.get('country', 'N/A')})")
    else:
        step_logs.append("HMA: Bỏ qua kiểm tra vị trí")

    # 1.5. Thiết lập Tiêu đề & Hook chuẩn xác 100% theo tên video trên Channel (GỠ BỎ HOÀN TOÀN AI)
    effective_hashtags = override_hashtags if override_hashtags else target_acc.get("hashtag", "")
    log_message(f"📝 [Tiêu đề Video] Đặt tiêu đề và hook theo đúng tên video gốc từ channel cho {total_items} video (Không dùng AI)...")
    for item in resolved_upload_items:
        raw_t = clean_caption_text(item.get("title", "").strip())
        if override_caption:
            item["override_caption"] = clean_caption_text(override_caption.strip())
        else:
            item["override_caption"] = raw_t
        step_logs.append(f"Tiêu đề: {item['override_caption']}")

    # 2. Khởi chạy Profile AdsPower
    profile_id = target_acc.get("adspower_id") or target_acc.get("adspower_serial") or target_acc.get("account_name")
    log_message(f"⚡ [2/4] Khởi chạy Profile AdsPower: '{profile_id}'...")
    ads_url = adspower_settings.get("api_url", "http://local.adspower.net:50325")
    ads_key = adspower_settings.get("api_key", "")

    ads_res = start_adspower_browser(profile_id, ads_url, ads_key)
    if not ads_res.get("success"):
        error_msg = f"Không thể mở Profile AdsPower '{profile_id}': {ads_res.get('error')}"
        log_message(f"❌ {error_msg}")
        send_telegram_notification(f"❌ *[LỖI ADSPOWER]*\n👤 Tài khoản @{acc_name}\n⚠️ Không thể mở Profile AdsPower `{profile_id}`: {ads_res.get('error')}")
        return {"success": False, "error": error_msg, "step_logs": step_logs}

    ws_endpoint = ads_res.get("ws_endpoint")
    log_message(f"🌐 [3/4] Đã kết nối Chrome AdsPower (CDP: {ws_endpoint}). Tiến hành mở {total_items} tab đồng thời...")

    # 3. Tự động hóa đăng video đa tab bằng Playwright CDP
    def uploader_log(msg):
        log_message(f"  └─ {msg}")
        step_logs.append(msg)

    upload_res = upload_multiple_videos_to_tiktok_cdp(
        ws_endpoint=ws_endpoint,
        items=resolved_upload_items,
        hashtags=effective_hashtags,
        auto_submit=auto_submit,
        close_browser_after=close_browser,
        wait_timeout=wait_timeout,
        log_callback=uploader_log
    )

    # 5. Tự động đóng trình duyệt AdsPower Profile để chuẩn bị sạch sẽ cho tài khoản tiếp theo
    if close_browser or auto_submit:
        from src.services.adspower_service import stop_adspower_browser
        try:
            time.sleep(1) # Chờ 1s để đảm bảo request gửi TikTok hoàn tất
            stop_res = stop_adspower_browser(profile_id, api_url=ads_url, api_key=ads_key)
            if stop_res.get("success"):
                log_message(f"🔒 Đã đóng trình duyệt AdsPower Profile `{profile_id}` (@{acc_name}) thành công.")
            else:
                log_message(f"⚠️ Thông báo đóng AdsPower Profile `{profile_id}`: {stop_res.get('message', 'Không rõ')}")
        except Exception as e_close:
            log_message(f"⚠️ Không thể đóng AdsPower Profile `{profile_id}`: {e_close}")

    if upload_res.get("success"):
        actual_posted_items = upload_res.get("items", resolved_upload_items)
        for item in actual_posted_items:
            effective_clip_key = item.get("clip_key") or clip_key or (f"{item.get('channel', channel)}/{item.get('title', title)}" if (item.get('channel') or channel) and (item.get('title') or title) else "")
            effective_channel = item.get("channel") or channel or (os.path.dirname(effective_clip_key) if effective_clip_key else "")
            effective_title = item.get("title") or title or (os.path.basename(effective_clip_key) if effective_clip_key else "")

            toggle_publishing_clip_status(
                acc_name,
                clip_key=effective_clip_key,
                channel=effective_channel,
                title=effective_title,
                posted=True,
                part_label=item.get("part_label"),
                video_id=item.get("video_id") or generate_video_id(effective_channel, effective_title)
            )

        log_message(f"🎉 [4/4] Đã đăng đồng thời toàn bộ {len(actual_posted_items)} video thành công!")
        
        today_count_after = get_account_daily_posted_count(acc_name)
        first_item = resolved_upload_items[0]

        LAST_PUBLISHING_STATE["is_busy"] = False
        LAST_PUBLISHING_STATE["success"] = True
        LAST_PUBLISHING_STATE["count"] = len(actual_posted_items)
        LAST_PUBLISHING_STATE["today_posted_count"] = today_count_after
        LAST_PUBLISHING_STATE["error"] = ""
        LAST_PUBLISHING_STATE["timestamp"] = time.time()

        send_telegram_notification(
            f"🎉 <b>[TikTok Studio Pro] ĐÃ ĐĂNG VIDEO THÀNH CÔNG!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Tài khoản:</b> @{acc_name}\n"
            f"📺 <b>Kênh:</b> {first_item.get('channel')}\n"
            f"🎬 <b>Tiêu đề:</b> {first_item.get('title')}\n"
            f"🌐 <b>IP Đăng:</b> <code>{curr_ip}</code> ({curr_ip_info.get('country', 'N/A')})\n"
            f"⏰ <b>Thời gian:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📊 <b>Tiến độ hôm nay:</b> Đã đăng <code>{today_count_after}/{max_daily_posts}</code> clip\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Trạng thái: Thành công 100%"
        )
        
        return {
            "success": True,
            "message": f"Đăng thành công {total_items} video trên {total_items} tab cùng lúc lên TikTok!",
            "count": total_items,
            "today_posted_count": today_count_after,
            "items": resolved_upload_items,
            "step_logs": step_logs
        }
    else:
        err_upload = upload_res.get("error") or upload_res.get("message") or "Lỗi trong quá trình đăng clip"
        LAST_PUBLISHING_STATE["is_busy"] = False
        LAST_PUBLISHING_STATE["success"] = False
        LAST_PUBLISHING_STATE["count"] = 0
        LAST_PUBLISHING_STATE["error"] = err_upload
        LAST_PUBLISHING_STATE["timestamp"] = time.time()

        send_telegram_notification(
            f"❌ <b>[LỖI ĐĂNG VIDEO TIKTOK]</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Tài khoản:</b> @{acc_name}\n"
            f"⚠️ <b>Chi tiết lỗi:</b> {err_upload}\n"
            f"⏰ <b>Thời gian:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return {
            "success": False,
            "error": err_upload,
            "step_logs": step_logs
        }

AUTOPILOT_RUNNING = False
AUTOPILOT_CANCEL_REQUESTED = False
AUTOPILOT_STATE = {
    "is_running": False,
    "total_accounts": 0,
    "current_index": 0,
    "current_account": "",
    "success_count": 0,
    "fail_count": 0,
    "summary": {},
    "logs": []
}

def run_autopilot_publishing_worker(payload):
    global AUTOPILOT_RUNNING, AUTOPILOT_CANCEL_REQUESTED, AUTOPILOT_STATE
    AUTOPILOT_RUNNING = True
    AUTOPILOT_CANCEL_REQUESTED = False
    
    target_accounts = payload.get("accounts", [])
    auto_submit = payload.get("auto_submit", True)
    
    # Load all pending clips
    all_pending = get_pending_publishing_queue()
    if isinstance(all_pending, dict):
        all_pending = all_pending.get("items", [])
    
    # Group pending clips by account
    accounts_map = {}
    for item in all_pending:
        acc = item.get("account_name", "")
        if acc not in accounts_map:
            accounts_map[acc] = []
        accounts_map[acc].append(item)
        
    if not target_accounts:
        target_accounts = list(accounts_map.keys())
        
    # Maintain user selection order, filtering only active accounts
    active_accounts = [acc for acc in target_accounts if acc in accounts_map and accounts_map[acc]]
    total_accs = len(active_accounts)
    
    AUTOPILOT_STATE["is_running"] = True
    AUTOPILOT_STATE["total_accounts"] = total_accs
    AUTOPILOT_STATE["current_index"] = 0
    AUTOPILOT_STATE["current_account"] = ""
    AUTOPILOT_STATE["success_count"] = 0
    AUTOPILOT_STATE["fail_count"] = 0
    AUTOPILOT_STATE["summary"] = {}
    AUTOPILOT_STATE["logs"] = []
    
    log_message(f"🚀 [Auto-Pilot Server] Bắt đầu quy trình tự động đăng cho {total_accs} tài khoản...")
    
    try:
        for idx, acc_name in enumerate(active_accounts):
            if AUTOPILOT_CANCEL_REQUESTED:
                log_message("⚠️ [Auto-Pilot Server] Tiến trình đã bị người dùng dừng lại!")
                break
                
            clips = accounts_map.get(acc_name, [])
            if not clips:
                continue

            # Kiểm tra hạn mức đăng trong ngày còn lại của tài khoản
            settings = load_settings()
            max_daily_posts = int(settings.get("tiktok_upload", {}).get("max_daily_posts_per_account", 3))
            today_posted = get_account_daily_posted_count(acc_name)
            remaining_quota = max(0, max_daily_posts - today_posted) if max_daily_posts > 0 else len(clips)
            if remaining_quota <= 0:
                log_message(f"   🎯 [Auto-Pilot] Tài khoản @{acc_name} đã đăng {today_posted}/{max_daily_posts} clip hôm nay (đạt giới hạn) -> Bỏ qua an toàn!")
                continue

            batch_clips = clips[:min(3, remaining_quota)]
            if not batch_clips:
                continue
                
            AUTOPILOT_STATE["current_index"] = idx + 1
            AUTOPILOT_STATE["current_account"] = acc_name
            
            global CURRENT_TASK, PROGRESS_PERCENT
            PROGRESS_PERCENT = int((idx / max(total_accs, 1)) * 100)
            CURRENT_TASK = f"[{idx+1}/{total_accs}] @{acc_name}: Đang đăng {len(batch_clips)} clip (3 tab)"
            
            log_message(f"▶️ [Auto-Pilot {idx+1}/{total_accs}] Khởi chạy AdsPower Chrome cho @{acc_name} ({len(batch_clips)} clip)...")
            for c_i, c in enumerate(batch_clips):
                log_message(f"   📑 [Tab {c_i+1}] Clip: \"{c.get('title')}\" [{c.get('channel')}]")
                
            acc_payload = {
                "account_name": acc_name,
                "channel": batch_clips[0].get("channel", ""),
                "items": batch_clips,
                "auto_submit": auto_submit
            }
            
            # Đăng video cho tài khoản này (khóa publishing lock)
            with PUBLISHING_LOCK:
                pub_res = execute_tiktok_publish(acc_payload)
                
            if pub_res.get("success"):
                posted_num = pub_res.get("count", len(batch_clips))
                AUTOPILOT_STATE["success_count"] += posted_num
                log_message(f"   🎉 [Auto-Pilot] ĐÃ ĐĂNG THÀNH CÔNG ĐỒNG THỜI {posted_num} CLIP CHO @{acc_name}!")
                if acc_name not in AUTOPILOT_STATE["summary"]:
                    AUTOPILOT_STATE["summary"][acc_name] = {"count": 0, "clips": []}
                AUTOPILOT_STATE["summary"][acc_name]["count"] += posted_num
                AUTOPILOT_STATE["summary"][acc_name]["clips"].extend([c.get("title") for c in batch_clips])
            else:
                if pub_res.get("daily_quota_reached"):
                    log_message(f"   🎯 [Auto-Pilot] Tài khoản @{acc_name} đã đạt giới hạn 3/3 clip hôm nay -> Đã bỏ qua an toàn!")
                else:
                    AUTOPILOT_STATE["fail_count"] += len(batch_clips)
                    log_message(f"   ❌ [Auto-Pilot] Thất bại @{acc_name}: {pub_res.get('error', 'Lỗi không xác định')}")
                    
            # Nghỉ ngắn 2 giây giữa các tài khoản trên server
            if not AUTOPILOT_CANCEL_REQUESTED and idx < total_accs - 1:
                log_message("   ⏳ Chờ 2 giây trước khi mở tài khoản tiếp theo...")
                time.sleep(2)
                
        PROGRESS_PERCENT = 100
        CURRENT_TASK = "Hoàn tất Auto-Pilot"
        log_message(f"🏁 [Auto-Pilot Server] Đã hoàn thành toàn bộ tiến trình! Thành công: {AUTOPILOT_STATE['success_count']} clip, Thất bại: {AUTOPILOT_STATE['fail_count']} clip.")
        
        # Gửi báo cáo tổng hợp qua Telegram
        if AUTOPILOT_STATE["success_count"] > 0:
            summary_text = f"📊 <b>[BÁO CÁO TỔNG KẾT AUTO-PILOT TIKTOK]</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            summary_text += f"🎉 <b>Tổng clip đăng thành công:</b> <code>{AUTOPILOT_STATE['success_count']}</code>\n"
            if AUTOPILOT_STATE['fail_count'] > 0:
                summary_text += f"⚠️ <b>Số clip thất bại/bỏ qua:</b> <code>{AUTOPILOT_STATE['fail_count']}</code>\n"
            summary_text += f"⏰ <b>Hoàn tất lúc:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n<b>Chi tiết theo tài khoản:</b>\n"
            for s_acc, s_info in AUTOPILOT_STATE["summary"].items():
                summary_text += f"• <b>@{s_acc}:</b> {s_info['count']} clip\n"
            send_telegram_notification(summary_text)
            
    except Exception as e_pilot:
        log_message(f"❌ [Auto-Pilot Server Error] {str(e_pilot)}")
    finally:
        AUTOPILOT_RUNNING = False
        AUTOPILOT_STATE["is_running"] = False


class StudioServerHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def send_json(self, data, status=200):
        try:
            body = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass
        except Exception as e:
            try:
                self.send_error(500, f"Server Error: {e}")
            except Exception:
                pass

    def translate_path(self, path):
        # Serve UI, Assets, and Storage directory
        parsed = urlparse(path).path
        if parsed in ["", "/"]:
            parsed = "/ui/index.html"
        elif not parsed.startswith(("/ui", "/assets", "/storage", "/data")):
            ui_candidate = os.path.join(BASE_DIR, "ui", parsed.lstrip("/"))
            if os.path.exists(ui_candidate):
                return ui_candidate
        rel_path = parsed.lstrip("/")
        return os.path.join(BASE_DIR, rel_path)

    def _handle_post_to_tiktok(self, body_data):
        res = execute_tiktok_publish(body_data)
        status_code = 200 if res.get("success") else (400 if (res.get("daily_quota_reached") or res.get("ip_blocked")) else 500)
        self.send_json(res, status=status_code)

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/api/autopilot/status":
            self.send_json({
                "is_running": AUTOPILOT_RUNNING,
                "state": AUTOPILOT_STATE
            })
            return

        if parsed.path == "/api/heartbeat":
            global LAST_HEARTBEAT
            LAST_HEARTBEAT = time.time()
            self.send_json({"status": "ok"})
            return

        # Root path serves UI directly
        if parsed.path in ["", "/"]:
            self.path = "/ui/index.html"
            return super().do_GET()

        # API: Available Assets & Fonts
        if parsed.path == "/api/assets/fonts":
            try:
                from src.core.asset_manager import AssetManager
                fonts = AssetManager.list_fonts()
            except Exception as e:
                fonts = []
            self.send_json({"success": True, "fonts": fonts})
            return

        # API: Progress & Logs
        if parsed.path == "/api/progress":
            data = {
                "is_running": IS_RUNNING,
                "is_publishing": PUBLISHING_LOCK.locked() or LAST_PUBLISHING_STATE.get("is_busy", False) or AUTOPILOT_RUNNING,
                "is_autopilot_running": AUTOPILOT_RUNNING,
                "autopilot_state": AUTOPILOT_STATE,
                "publishing_state": LAST_PUBLISHING_STATE,
                "percentage": PROGRESS_PERCENT,
                "current_task": CURRENT_TASK,
                "logs": LOG_MESSAGES[-120:]
            }
            self.send_json(data)
            return

        # API: Finished Results
        if parsed.path == "/api/results":
            acc_dest = load_accounts_data().get("dest_path", os.path.join(BASE_DIR, "output_product"))
            dest = query.get("dest", [acc_dest])[0]
            if not dest:
                dest = acc_dest
            data = scan_finished_results(dest)
            self.send_json(data)
            return

        # API: Accounts & YouTube Channels list
        if parsed.path == "/api/accounts":
            source_path = query.get("source", [""])[0]
            data = load_accounts_data()
            dest_path = data.get("dest_path", os.path.join(BASE_DIR, "output_product"))
            
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

            self.send_json(data)
            return

        # API: Publishing Tracker Matrix
        if parsed.path == "/api/publishing_matrix":
            dest = query.get("dest", [""])[0]
            data = get_publishing_matrix(dest if dest else None)
            self.send_json(data)
            return

        # API: Get System Settings (AdsPower, HMA, TikTok Upload)
        if parsed.path == "/api/settings":
            settings = load_settings()
            settings["hma_detected_path"] = find_hma_executable()
            self.send_json(settings)
            return

        # API: TikTok Analytics Data
        if parsed.path == "/api/analytics/data":
            from src.services.tiktok_analytics_service import load_analytics_data, get_current_ip_info
            analytics_data = load_analytics_data()
            ip_info = get_current_ip_info()
            self.send_json({
                "success": True,
                "data": analytics_data,
                "current_ip": ip_info
            })
            return

        # API: TikTok Analytics Collection Status
        if parsed.path == "/api/analytics/status":
            global IS_ANALYTICS_COLLECTING
            self.send_json({
                "is_collecting": globals().get("IS_ANALYTICS_COLLECTING", False),
                "progress_log": globals().get("ANALYTICS_LOGS", [])[-20:]
            })
            return

        # API: Get AdsPower Profiles List
        if parsed.path == "/api/adspower/profiles":
            settings = load_settings()
            api_url = query.get("api_url", [settings.get("adspower", {}).get("api_url", "")])[0]
            api_key = query.get("api_key", [settings.get("adspower", {}).get("api_key", "")])[0]
            res = get_adspower_profiles(api_url=api_url, api_key=api_key)
            self.send_json(res)
            return

        # API: n8n Pending Clips Queue
        if parsed.path == "/api/n8n/pending_clips":
            acc_filter = query.get("accounts", [None])[0] or query.get("account", [None])[0]
            chan_filter = query.get("channel", [None])[0]
            only_curr = query.get("only_current_target", ["true"])[0].lower() in ["true", "1", "yes"]
            items = get_pending_publishing_queue(account_name=acc_filter, channel_name=chan_filter, only_current_target=only_curr)
            self.send_json({"success": True, "count": len(items), "items": items})
            return

        # API: YouTube Dual Scanner (Videos & Shorts)
        if parsed.path == "/api/youtube/scan_channel_media":
            channel_url = query.get("url", [""])[0]
            channel_name = query.get("name", [""])[0]
            min_views = int(query.get("min_views", ["0"])[0])
            max_duration = int(query.get("max_duration", ["0"])[0])
            max_scan = int(query.get("max_scan", ["40"])[0])
            source_dir = query.get("source", [""])[0]
            dest_dir = query.get("dest", [""])[0]
            force_refresh = query.get("refresh", ["false"])[0].lower() in ["true", "1", "yes"]
            
            if not channel_url:
                self.send_json({"error": "Thiếu URL kênh YouTube"}, status=400)
                return
                
            from src.services.youtube_downloader import scan_channel_all_media
            from src.services.drive_service import resolve_google_drive_path
            resolved_source = resolve_google_drive_path(source_dir) if source_dir else None
            resolved_dest = resolve_google_drive_path(dest_dir) if dest_dir else None
            
            res = scan_channel_all_media(
                channel_url=channel_url,
                channel_name=channel_name,
                min_views=min_views,
                max_duration_sec=max_duration,
                max_scan=max_scan,
                custom_source_dir=resolved_source,
                custom_dest_dir=resolved_dest,
                force_refresh=force_refresh
            )
            
            self.send_json(res, status=200 if res.get("success") else 400)
            return

        # API: YouTube Download Queue Status
        if parsed.path == "/api/youtube/download_queue":
            from src.services.youtube_downloader import get_download_queue_status
            status_data = get_download_queue_status()
            self.send_json(status_data)
            return

        # API: YouTube Cookies Status
        if parsed.path == "/api/youtube/cookies_status":
            from src.services.youtube_downloader import get_cookies_status
            status_data = get_cookies_status()
            self.send_json(status_data)
            return


        # API: YouTube Smart Channel Scanner (Legacy)
        if parsed.path == "/api/youtube/scan_channel":
            channel_url = query.get("url", [""])[0]
            channel_name = query.get("name", [""])[0]
            min_views = int(query.get("min_views", ["1000000"])[0])
            max_duration = int(query.get("max_duration", ["1200"])[0])
            if not channel_url:
                self.send_json({"error": "Thiếu channel url"}, status=400)
                return
            from src.services.youtube_downloader import scan_and_filter_youtube_channel
            videos = scan_and_filter_youtube_channel(channel_url, channel_name, min_views, max_duration)
            self.send_json({"success": True, "count": len(videos), "videos": videos})
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
            invalidate_drive_caches()
            result = scan_source_directory(source, dest, force=True)
            self.send_json(result)
            return

        # API: Trigger Batch TikTok Analytics Collection
        if parsed.path == "/api/analytics/collect":
            global IS_ANALYTICS_COLLECTING, ANALYTICS_LOGS
            if globals().get("IS_ANALYTICS_COLLECTING", False):
                self.send_json({"success": False, "error": "Tiến trình thu thập Analytics đang chạy!"}, status=400)
                return

            def analytics_worker():
                global IS_ANALYTICS_COLLECTING, ANALYTICS_LOGS
                IS_ANALYTICS_COLLECTING = True
                ANALYTICS_LOGS = []
                def log_cb(msg):
                    ANALYTICS_LOGS.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
                    log_message(f"[Analytics] {msg}")

                try:
                    from src.services.tiktok_analytics_service import collect_all_accounts_analytics
                    settings = load_settings()
                    ads_cfg = settings.get("adspower", {})
                    collect_all_accounts_analytics(
                        api_url=ads_cfg.get("api_url", ""),
                        api_key=ads_cfg.get("api_key", ""),
                        log_callback=log_cb
                    )
                except Exception as ex:
                    log_cb(f"❌ Ngoại lệ tiến trình Analytics: {ex}")
                finally:
                    IS_ANALYTICS_COLLECTING = False

            t = threading.Thread(target=analytics_worker, daemon=True)
            t.start()

            self.send_json({"success": True, "message": "Đã bắt đầu thu thập Analytics."})
            return

        # API: Collect Single Account Analytics
        if parsed.path == "/api/analytics/collect_single":
            acc_id = body_data.get("account_id") or body_data.get("channel_name")
            target_acc = None
            for acc in load_accounts_data().get("tiktok_accounts", []):
                if str(acc.get("id")) == str(acc_id) or str(acc.get("adspower_id")) == str(acc_id) or acc.get("channel_name") == acc_id:
                    target_acc = acc
                    break

            if not target_acc:
                self.send_json({"success": False, "error": "Không tìm thấy tài khoản tương ứng."}, status=404)
                return

            def single_worker(acc):
                from src.services.tiktok_analytics_service import collect_single_account_analytics, load_analytics_data, save_analytics_data, calculate_overall_metrics
                settings = load_settings()
                ads_cfg = settings.get("adspower", {})
                res = collect_single_account_analytics(
                    acc,
                    api_url=ads_cfg.get("api_url", ""),
                    api_key=ads_cfg.get("api_key", ""),
                    log_callback=lambda m: log_message(f"[Analytics] {m}")
                )
                if res.get("success"):
                    cur = load_analytics_data()
                    acc_key = str(acc.get("id") or acc.get("adspower_id") or acc.get("channel_name"))
                    cur.setdefault("accounts", {})[acc_key] = res
                    cur["overall"] = calculate_overall_metrics(cur["accounts"])
                    cur["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    save_analytics_data(cur)

            t = threading.Thread(target=single_worker, args=(target_acc,), daemon=True)
            t.start()

            self.send_json({"success": True, "message": f"Đang thu thập dữ liệu cho {target_acc.get('channel_name')}"})
            return

        # API: Start Batch Processing
        if parsed.path == "/api/start_batch":
            global IS_RUNNING
            if IS_RUNNING:
                self.send_json({"error": "Tiến trình render đang chạy!"}, status=400)
                return

            t = threading.Thread(target=batch_worker, args=(body_data,), daemon=True)
            t.start()

            self.send_json({"status": "started"})
            return

        # API: Stop Batch Processing
        if parsed.path == "/api/stop_batch":
            global CANCEL_REQUESTED
            CANCEL_REQUESTED = True
            log_message("🛑 Nhận được tín hiệu dừng từ người dùng.")
            self.send_json({"status": "stopping"})
            return

        # API: YouTube Download Single Item (Auto-Triggered on Checkbox)
        if parsed.path == "/api/youtube/download_item":
            url = body_data.get("url", "")
            title = body_data.get("title", "")
            channel = body_data.get("channel", "Downloads")
            is_short = body_data.get("is_short", False)
            source_dir = body_data.get("source_dir", "")
            
            if not url:
                self.send_json({"success": False, "error": "Thiếu URL video"}, status=400)
                return
                
            from src.services.drive_service import resolve_google_drive_path
            resolved_source = resolve_google_drive_path(source_dir) if source_dir else None
            
            from src.services.youtube_downloader import enqueue_download_task
            log_message(f"⬇️ [Auto Pipeline] Kích hoạt tải video: {title} (Kênh: {channel})...")
            task = enqueue_download_task(body_data, custom_source_dir=resolved_source)
            
            self.send_json({"success": True, "task": task})
            return

        # API: YouTube Download Batch of Selected Items
        if parsed.path == "/api/youtube/download_batch":
            items = body_data.get("items", [])
            source_dir = body_data.get("source_dir", "")
            
            if not items:
                self.send_json({"success": False, "error": "Không có video nào được chọn"}, status=400)
                return
                
            from src.services.drive_service import resolve_google_drive_path
            resolved_source = resolve_google_drive_path(source_dir) if source_dir else None
            
            from src.services.youtube_downloader import enqueue_download_task
            created_tasks = []
            log_message(f"🚀 [Batch Pipeline] Kích hoạt tải hàng loạt {len(items)} video vào kho nguồn...")
            for it in items:
                t = enqueue_download_task(it, custom_source_dir=resolved_source)
                created_tasks.append(t)
                
            self.send_json({"success": True, "count": len(created_tasks), "tasks": created_tasks})
            return

        # API: YouTube Clear Completed/Failed Queue Items
        if parsed.path == "/api/youtube/clear_completed_queue":
            from src.services.youtube_downloader import clear_completed_tasks
            cleared = clear_completed_tasks()
            self.send_json({"success": True, "cleared_count": cleared})
            return

        # API: Save YouTube Cookies (Netscape format)
        if parsed.path == "/api/youtube/save_cookies":
            content = body_data.get("cookies", "") or body_data.get("content", "")
            if not content or len(content.strip()) < 10:
                self.send_json({"success": False, "error": "Nội dung cookie trống hoặc quá ngắn"}, status=400)
                return
            from src.services.youtube_downloader import save_youtube_cookies
            res = save_youtube_cookies(content)
            self.send_json(res)
            return


        # API: YouTube Auto Download Top Video(s)
        if parsed.path == "/api/youtube/auto_download":
            channel_url = body_data.get("channel_url", "")
            channel_name = body_data.get("channel_name", "")
            min_views = int(body_data.get("min_views", 1000000))
            max_duration = int(body_data.get("max_duration_sec", 1200))
            count = int(body_data.get("count", 1))
            
            if not channel_url:
                self.send_json({"error": "Thiếu channel_url"}, status=400)
                return

            def download_worker():
                from src.services.youtube_downloader import scan_and_filter_youtube_channel, download_youtube_video
                log_message(f"🔍 Đang quét kênh YouTube: {channel_name or channel_url} (>={min_views:,} views, <={max_duration//60}p)...")
                vids = scan_and_filter_youtube_channel(channel_url, channel_name, min_views, max_duration)
                downloaded = 0
                idx = 0
                while downloaded < count and idx < len(vids):
                    v = vids[idx]
                    idx += 1
                    log_message(f"⬇️ [{downloaded+1}/{count}] Đang tải video: {v['title']} ({v['views']:,} views)...")
                    res = download_youtube_video(v['url'], channel_name or v.get('channel', 'Downloads'), v['title'])
                    if res.get('success') and res.get('file_path') and res['file_path'].endswith('.mp4'):
                        downloaded += 1
                        log_message(f"✅ [{downloaded}/{count}] Tải thành công ({res['size_mb']:.1f} MB): {res['title']}")
                    else:
                        log_message(f"⚠️ Video '{v['title']}' tải không thành công, đã dọn sạch file tạm và tự động chuyển sang clip khác...")
                    time.sleep(1)
                log_message(f"🎉 Hoàn tất! Đã tải đủ {downloaded} video .mp4 chuẩn vào kho nguồn.")

            t = threading.Thread(target=download_worker, daemon=True)
            t.start()
            
            self.send_json({"status": "downloading_started"})
            return

        # API: Open Folder in Explorer
        if parsed.path == "/api/open_folder":
            fpath = body_data.get("path", body_data.get("folder_path", ""))
            base_dest = body_data.get("base_dest", "")
            channel = body_data.get("channel", "")
            title = body_data.get("title", "")

            # 1. Nếu client truyền base_dest (đường link trả video kết quả được setting trên webapp)
            if base_dest:
                base_dest = base_dest.strip().strip('"').strip("'")
                
                # Nếu là đường dẫn Web Google Drive
                if base_dest.startswith("http://") or base_dest.startswith("https://"):
                    import webbrowser
                    webbrowser.open(base_dest)
                    self.send_json({"status": "opened", "path": base_dest})
                    return

                from src.services.drive_service import resolve_google_drive_path
                resolved_base = resolve_google_drive_path(base_dest)
                if resolved_base and os.path.exists(resolved_base):
                    base_dest = resolved_base

                target_parts = [base_dest]
                if channel:
                    target_parts.append(channel)
                if title:
                    target_parts.append(title)
                
                target_path = os.path.normpath(os.path.join(*target_parts))

                # Kiểm tra nếu chưa tồn tại, thử tìm theo biến thể sanitize_filename
                if not os.path.exists(target_path):
                    cand_parts = [base_dest]
                    if channel:
                        cand_parts.append(sanitize_filename(channel))
                    if title:
                        cand_parts.append(sanitize_filename(title))
                    cand_path = os.path.normpath(os.path.join(*cand_parts))
                    if os.path.exists(cand_path):
                        target_path = cand_path
                    else:
                        # Tự động tạo thư mục nếu chưa tồn tại để sẵn sàng cho người dùng
                        try:
                            os.makedirs(target_path, exist_ok=True)
                        except Exception:
                            pass
                
                fpath = target_path

            log_message(f"📂 Yêu cầu mở thư mục kết quả: {fpath}")
            if fpath:
                fpath = fpath.strip().strip('"').strip("'")
                
                # Nếu là liên kết web
                if fpath.startswith("http://") or fpath.startswith("https://"):
                    import webbrowser
                    webbrowser.open(fpath)
                else:
                    from src.services.drive_service import resolve_google_drive_path
                    resolved = resolve_google_drive_path(fpath)
                    if resolved and os.path.exists(resolved):
                        fpath = resolved

                    norm_path = os.path.normpath(fpath)
                    
                    if os.path.isfile(norm_path):
                        norm_path = os.path.dirname(norm_path)
                        
                    if not os.path.exists(norm_path):
                        # Thử tạo thư mục nếu chưa tồn tại
                        try:
                            os.makedirs(norm_path, exist_ok=True)
                        except Exception:
                            pass

                    if os.path.exists(norm_path):
                        if os.name == 'nt':
                            try:
                                os.startfile(norm_path)
                            except Exception:
                                subprocess.Popen(f'explorer "{norm_path}"', shell=True)
                        else:
                            subprocess.Popen(['xdg-open', norm_path])
                    else:
                        log_message(f"❌ Không thể mở thư mục '{norm_path}'")
                            
            self.send_json({"status": "opened", "path": fpath})
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
            self.send_json({"status": "opened"})
            return

        # API: Save Accounts & YouTube Channels list
        if parsed.path == "/api/accounts/save":
            success = save_accounts_data(body_data)
            if success:
                created = ensure_channel_folders(body_data)
                for f in created:
                    log_message(f"📁 Tự động tạo thư mục: {f}")
            self.send_json({"status": "saved" if success else "failed"}, status=(200 if success else 500))
            return

        # API: Sync TikTok Accounts with AdsPower Local API
        if parsed.path == "/api/accounts/sync_adspower":
            from src.services.drive_service import sync_tiktok_accounts_with_adspower
            res = sync_tiktok_accounts_with_adspower()
            self.send_json(res, status=(200 if res.get("success") else 500))
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
                
            self.send_json({"folder_path": folder_path})
            return


        # API: Delete Finished Result Video
        if parsed.path == "/api/delete_result":
            item_path = body_data.get("path", "")
            title = body_data.get("title", "")
            channel = body_data.get("channel", "")
            dest_path = body_data.get("dest", "")
            
            success, errors = delete_finished_result(item_path, title, channel, dest_path)
            log_message(f"🗑️ Đã xóa video thành phẩm: {title or os.path.basename(item_path)}")
            self.send_json({"success": success, "errors": errors, "title": title}, status=(200 if success else 500))
            return

        # API: Delete All Finished Results
        if parsed.path == "/api/delete_all_results":
            dest_path = body_data.get("dest", os.path.join(BASE_DIR, "output_product"))
            success, errors = delete_all_finished_results(dest_path)
            log_message("🗑️ Đã xóa toàn bộ video thành phẩm trong thư mục đích.")
            self.send_json({"success": success, "errors": errors}, status=(200 if success else 500))
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
            invalidate_drive_caches()
            self.send_json({"success": success, "posted": posted, "posted_at": res_val if success else "", "error": res_val if not success else ""}, status=(200 if success else 400))
            return

        # API: Change TikTok Account Target YouTube Channel
        if parsed.path == "/api/publishing/change_target":
            acc_name = body_data.get("account_name", "")
            new_target = body_data.get("new_target_channel", "")
            
            success, err = change_account_target_channel(acc_name, new_target)
            invalidate_drive_caches()
            self.send_json({"success": success, "error": err if not success else ""}, status=(200 if success else 400))
            return

        # API: Batch Toggle Posted status for multiple clips
        if parsed.path in ["/api/publishing/batch_toggle_post", "/api/publishing/batch_toggle"]:
            acc_name = body_data.get("account_name", "")
            clip_keys = body_data.get("clip_keys", [])
            posted = bool(body_data.get("posted", True))
            
            success, count = batch_toggle_publishing_clips(acc_name, clip_keys, posted)
            invalidate_drive_caches()
            self.send_json({"success": success, "count": count}, status=(200 if success else 400))
            return

        # API: Sync Publishing History & Pending Queue
        if parsed.path == "/api/publishing/sync_history":
            from src.services.drive_service import sync_publishing_history_with_queue, get_pending_publishing_queue
            synced = sync_publishing_history_with_queue()
            queue = get_pending_publishing_queue(only_current_target=True)
            self.send_json({
                "success": True, 
                "synced_count": synced,
                "count": len(queue), 
                "items": queue, 
                "message": f"Đã đồng bộ thành công {synced} clip từ lịch sử đăng vào hàng đợi!"
            })
            return

        # API: Save Settings (AdsPower, HMA, TikTok Upload, Gemini AI, Telegram)
        if parsed.path == "/api/settings/save":
            settings = load_settings()
            if "adspower" in body_data:
                settings["adspower"] = body_data["adspower"]
            if "hma" in body_data:
                settings["hma"] = body_data["hma"]
            if "tiktok_upload" in body_data:
                settings["tiktok_upload"] = body_data["tiktok_upload"]
            if "gemini" in body_data:
                settings["gemini"] = body_data["gemini"]
            if "telegram" in body_data:
                settings["telegram"] = body_data["telegram"]
            save_settings(settings)
            self.send_json({"success": True, "message": "Đã lưu cài đặt thành công"})
            return

        # API: Test Telegram Bot Connection
        if parsed.path == "/api/telegram/test":
            from src.services.telegram_service import test_telegram_connection
            bot_token = body_data.get("bot_token", "").strip()
            chat_id = str(body_data.get("chat_id", "")).strip()
            success, msg = test_telegram_connection(bot_token, chat_id)
            self.send_json({"success": success, "message": msg})
            return

        # API: Send Telegram Notification
        if parsed.path == "/api/telegram/send":
            from src.services.telegram_service import send_telegram_message
            message = body_data.get("message", "Thông báo từ TikTok Studio Pro")
            bot_token = body_data.get("bot_token", None)
            chat_id = body_data.get("chat_id", None)
            success, msg = send_telegram_message(message, bot_token=bot_token, chat_id=chat_id)
            self.send_json({"success": success, "message": msg})
            return

        # API: Test Gemini AI Key
        if parsed.path == "/api/ai/test_key":
            from src.services.gemini_service import test_gemini_api
            api_key = body_data.get("api_key", "").strip()
            model = body_data.get("model", "gemini-1.5-flash")
            success, msg = test_gemini_api(api_key, model=model)
            self.send_json({"success": success, "message": msg})
            return

        # API: Caption & Hashtags (Tuân thủ nghiêm ngặt tên video trên Channel, không dùng AI)
        if parsed.path == "/api/ai/generate_caption":
            video_title = body_data.get("video_title", "TikTok Video")
            clean_title = clean_caption_text(video_title)
            self.send_json({
                "success": True,
                "engine": "Direct Channel Title (Strict No-AI)",
                "caption": clean_title,
                "hashtags": ""
            })
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
            self.send_json(status_res)
            return

        # API: Start AdsPower Browser
        if parsed.path == "/api/adspower/start":
            profile_id = body_data.get("profile_id", "")
            api_url = body_data.get("api_url", "")
            api_key = body_data.get("api_key", "")
            res = start_adspower_browser(profile_id, api_url, api_key)
            self.send_json(res, status=(200 if res.get("success") else 400))
            return

        # API: Stop AdsPower Browser
        if parsed.path == "/api/adspower/stop":
            profile_id = body_data.get("profile_id", "")
            api_url = body_data.get("api_url", "")
            api_key = body_data.get("api_key", "")
            res = stop_adspower_browser(profile_id, api_url, api_key)
            self.send_json(res)
            return

        # API: Test HMA IP & Location
        if parsed.path == "/api/hma/test_ip":
            res = get_current_public_ip()
            self.send_json(res)
            return

        # API: Connect HMA VPN
        if parsed.path == "/api/hma/connect":
            location = body_data.get("location", "")
            cli_path = body_data.get("cli_path", "")
            res = connect_hma(location, cli_path)
            self.send_json(res)
            return

        # API: Change HMA VPN IP
        if parsed.path == "/api/hma/change_ip":
            cli_path = body_data.get("cli_path", "")
            res = change_ip_hma(cli_path)
            self.send_json(res)
            return

        # API: Disconnect HMA VPN
        if parsed.path == "/api/hma/disconnect":
            cli_path = body_data.get("cli_path", "")
            res = disconnect_hma(cli_path)
            self.send_json(res)
            return

        # API: Test Telegram Notification
        if parsed.path == "/api/telegram/test":
            custom_msg = body_data.get("message", "🔔 *[TikTok Studio Pro]*\n✅ Kết nối Telegram Bot thành công! Hệ thống đã sẵn sàng nhận thông báo tự động.")
            success = send_telegram_notification(custom_msg)
            self.send_json({
                "success": success,
                "message": "Đã gửi thông báo Telegram thành công!" if success else "Không thể gửi Telegram. Vui lòng kiểm tra bot_token và chat_id."
            }, status=(200 if success else 400))
            return

        # API: Server-side Native Auto-Pilot Publishing Pipeline (Đăng tự động tuần tự đa tài khoản siêu mượt)
        if parsed.path == "/api/autopilot/start":
            global AUTOPILOT_RUNNING
            if AUTOPILOT_RUNNING:
                self.send_json({"success": False, "error": "Auto-Pilot đang chạy rồi! Vui lòng chờ hoặc bấm Dừng trước khi chạy lại."}, status=400)
                return
            threading.Thread(target=run_autopilot_publishing_worker, args=(body_data,), daemon=True).start()
            self.send_json({"success": True, "message": "Đã khởi chạy Auto-Pilot thành công trên máy chủ!"})
            return

        if parsed.path == "/api/autopilot/stop":
            global AUTOPILOT_CANCEL_REQUESTED
            AUTOPILOT_CANCEL_REQUESTED = True
            log_message("⚠️ [Auto-Pilot Server] Nhận được tín hiệu dừng tiến trình từ người dùng...")
            self.send_json({"success": True, "message": "Đã gửi tín hiệu dừng Auto-Pilot!"})
            return

        # API: Comprehensive Auto-Post to TikTok (HMA IP -> AdsPower Browser -> Multi-Tab Playwright Upload -> Update Status)
        # Hỗ trợ cả 2 endpoint: /api/publishing/post_to_tiktok và /api/pipeline/auto_process_and_post
        if parsed.path in ["/api/publishing/post_to_tiktok", "/api/pipeline/auto_process_and_post"]:
            if not PUBLISHING_LOCK.acquire(blocking=True, timeout=300):
                self.send_json({"success": False, "error": "Hệ thống đang bận đăng video cho tài khoản khác. Vui lòng chờ..."}, status=429)
                return
            try:
                self._handle_post_to_tiktok(body_data)
            finally:
                PUBLISHING_LOCK.release()
            return

        # API: System Scheduled Shutdown
        if parsed.path == "/api/system/shutdown":
            delay_sec = int(body_data.get("delay_seconds", 900))
            msg = f"Hẹn giờ tắt máy tính sau {delay_sec} giây ({round(delay_sec/60)} phút)"
            log_message(f"💤 {msg}")
            try:
                subprocess.Popen(["shutdown", "/s", "/t", str(delay_sec), "/c", "TikTok Studio Pro: Hoàn thành tác vụ ban đêm. Máy tính sẽ tự động tắt."])
                self.send_json({"success": True, "message": msg, "delay_seconds": delay_sec})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, status=500)
            return

        # API: Cancel Scheduled Shutdown
        if parsed.path == "/api/system/cancel_shutdown":
            log_message("⚡ Đã hủy lệnh hẹn giờ tắt máy tính.")
            try:
                subprocess.Popen(["shutdown", "/a"])
                self.send_json({"success": True, "message": "Đã hủy lệnh tắt máy tính thành công!"})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, status=500)
            return

        self.send_error(404)


class DualStackServer(ThreadingHTTPServer):
    """Máy chủ HTTP hỗ trợ kết nối song song cả IPv4 (127.0.0.1) và IPv6 (localhost ::1)"""
    address_family = socket.AF_INET6
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except Exception:
            pass
        super().server_bind()

def kill_process_on_port(port):
    """Tự động giải phóng cổng nếu bị kẹt tiến trình cũ"""
    import subprocess
    try:
        cmd = f'powershell -Command "Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"'
        subprocess.run(cmd, shell=True, capture_output=True)
    except Exception:
        pass

LAST_HEARTBEAT = time.time()

def heartbeat_monitor():
    while True:
        time.sleep(30)
        # Giữ máy chủ WebApp luôn hoạt động bền bỉ, không tự ngắt kết nối của người dùng khi rảnh
        pass

# Bắt đầu luồng kiểm tra heartbeat
threading.Thread(target=heartbeat_monitor, daemon=True).start()

def run_server():
    try:
        ensure_channel_folders()
    except Exception:
        pass
        
    httpd = None
    for attempt in range(2):
        try:
            ThreadingHTTPServer.allow_reuse_address = True
            httpd = ThreadingHTTPServer(('127.0.0.1', PORT), StudioServerHandler)
            httpd.daemon_threads = True
            break
        except OSError:
                if attempt == 0:
                    kill_process_on_port(PORT)
                    time.sleep(1)
                else:
                    try:
                        if sys.stdout is not None:
                            print(f"ℹ️ Máy chủ đã đang hoạt động trên cổng {PORT}.")
                    except Exception:
                        pass
                    return

    if httpd:
        try:
            if sys.stdout is not None:
                print(f"🎬 TikTok Studio Webform đang chạy tại: http://localhost:{PORT}")
        except Exception:
            pass
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
