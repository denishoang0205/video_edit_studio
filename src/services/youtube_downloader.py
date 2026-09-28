import os
import sys
import time
import json
import re
import shutil
import uuid
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
import yt_dlp

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    from src.core.config import BASE_DIR, DATA_DIR, VIDEO_DIR, OUTPUT_BASE_DIR, FFMPEG_EXE, COOKIES_FILE, BIN_DIR, HISTORY_FILE
except ImportError:
    from config import BASE_DIR, DATA_DIR, VIDEO_DIR, OUTPUT_BASE_DIR, FFMPEG_EXE, COOKIES_FILE, BIN_DIR, HISTORY_FILE

DENO_EXE = os.path.join(BASE_DIR, "bin", "deno.exe")
ARIA2C_EXE = os.path.join(BASE_DIR, "bin", "aria2c.exe")

# Global Download Queue & Task Status
DOWNLOAD_TASKS_LOCK = threading.Lock()
DOWNLOAD_TASKS = {}
DOWNLOAD_WORKER_QUEUE = queue.Queue()
QUEUE_WORKER_STARTED = False
QUEUE_WORKER_LOCK = threading.Lock()


def safe_log(msg):
    """In log ra console an toàn không bao giờ bị UnicodeEncodeError trên Windows"""
    try:
        print(msg)
    except Exception:
        try:
            cleaned = msg.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')
            print(cleaned)
        except Exception:
            pass

def sanitize_filename(name):
    """Chuẩn hóa tên tệp và thư mục an toàn cho Windows"""
    if not name:
        return ""
    for ext in ['.mp4', '.mkv', '.mov', '.avi', '.webm']:
        if name.lower().endswith(ext):
            name = name[:-len(ext)]
            break
    sanitized = re.sub(r'[\\/*?:"<>|]', '', name).strip()
    return re.sub(r'\.+$', '', sanitized).strip()

def format_views(views):
    """Định dạng lượt xem dễ đọc: 1.4M, 850K, 1.2K"""
    if not views or views <= 0:
        return "0 views"
    if views >= 1_000_000:
        val = views / 1_000_000
        return f"{val:.1f}M views" if val < 10 else f"{int(val)}M views"
    if views >= 1_000:
        val = views / 1_000
        return f"{val:.1f}K views" if val < 10 else f"{int(val)}K views"
    return f"{views:,} views"

def format_duration(seconds):
    """Định dạng thời lượng: 12:45 hoặc 1:05:30"""
    if not seconds or seconds <= 0:
        return "0:00"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"

def get_channel_clean_base_url(url):
    """Chuẩn hóa URL kênh YouTube về base URL sạch (loại bỏ /videos, /shorts, /featured...)"""
    if not url:
        return ""
    url = url.strip()
    # Nếu người dùng nhập @handle
    if url.startswith("@"):
        return f"https://www.youtube.com/{url}"
    if not url.startswith("http://") and not url.startswith("https://"):
        if "/" not in url and not url.startswith("@"):
            return f"https://www.youtube.com/@{url}"
        return f"https://{url}"
        
    url = re.sub(r'/(videos|shorts|streams|playlists|community|featured|channels)/?$', '', url, flags=re.IGNORECASE)
    return url.rstrip('/')

def get_existing_product_titles(custom_source_dir=None, custom_dest_dir=None):
    """
    Thu thập tiêu đề video:
    - current: Video thực sự đang tồn tại trên đĩa (output_product hoặc input_sources)
    - previously: Video đã từng tải / từng biên tập nhưng hiện không còn file trên đĩa (hoặc đã xóa trên webapp)
    """
    current = set()
    previously = set()
    history_file = HISTORY_FILE
    
    # 1. Từ output_product hoặc custom_dest_dir (Đang có sẵn thành phẩm trên đĩa)
    dest_dir = custom_dest_dir or OUTPUT_BASE_DIR
    if os.path.exists(dest_dir):
        for root, dirs, files in os.walk(dest_dir):
            for d in dirs:
                current.add(d.strip().lower())
                current.add(sanitize_filename(d).lower())
            for f in files:
                if f.endswith((".mp4", ".mkv", ".mov")):
                    fname = os.path.splitext(f)[0].strip().lower()
                    base_fname = re.sub(r'\s*-\s*part\s*\d+', '', fname)
                    current.add(fname)
                    current.add(base_fname)

    # 2. Từ input_sources hoặc custom_source_dir (Đang có sẵn video gốc trên đĩa)
    src_dir = custom_source_dir or VIDEO_DIR
    if os.path.exists(src_dir):
        for root, dirs, files in os.walk(src_dir):
            for d in dirs:
                current.add(d.strip().lower())
                current.add(sanitize_filename(d).lower())
            for f in files:
                if f.endswith((".mp4", ".mkv", ".mov", ".webm")):
                    fname = os.path.splitext(f)[0].strip().lower()
                    current.add(fname)

    # 3. Từ history.json (Kiểm tra lịch sử tải / biên tập)
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                hist = json.load(f)
                for k, v in hist.items():
                    title = ""
                    vid_id = ""
                    if isinstance(v, dict):
                        title = v.get("title", "").strip().lower()
                        vid_id = v.get("video_id", "").strip().lower()
                    elif isinstance(v, str):
                        title = v.strip().lower()

                    folder_name = k.split("/")[-1].strip().lower()
                    identifiers = [x for x in [title, sanitize_filename(title).lower() if title else "", folder_name, vid_id] if x]

                    for ident in identifiers:
                        if ident in current:
                            continue
                        previously.add(ident)
        except Exception:
            pass

    return current, previously

# Bộ nhớ đệm cache cho kết quả quét kênh: {cache_key: (timestamp, raw_result_dict)}
_CHANNEL_SCAN_CACHE = {}
_SCAN_CACHE_TTL_SEC = 120  # Cache tồn tại 2 phút giúp chuyển kênh tức thì

def get_resolved_cookie_file():
    """Lấy file cookie YouTube: ưu tiên youtube_cookies.txt, dự phòng cookies.txt"""
    yt_cookies = os.path.join(DATA_DIR, "youtube_cookies.txt")
    if os.path.exists(yt_cookies) and os.path.getsize(yt_cookies) > 50:
        return yt_cookies
    if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 50:
        return COOKIES_FILE
    return None

def get_cookies_status():
    """Kiểm tra trạng thái file cookies YouTube hiện tại"""
    yt_cookies = os.path.join(DATA_DIR, "youtube_cookies.txt")
    legacy_cookies = COOKIES_FILE
    
    if os.path.exists(yt_cookies) and os.path.getsize(yt_cookies) > 50:
        return {
            "has_cookies": True,
            "file": "youtube_cookies.txt",
            "path": yt_cookies,
            "size_bytes": os.path.getsize(yt_cookies),
            "last_modified": os.path.getmtime(yt_cookies)
        }
    elif os.path.exists(legacy_cookies) and os.path.getsize(legacy_cookies) > 50:
        return {
            "has_cookies": True,
            "file": "cookies.txt",
            "path": legacy_cookies,
            "size_bytes": os.path.getsize(legacy_cookies),
            "last_modified": os.path.getmtime(legacy_cookies)
        }
    return {
        "has_cookies": False,
        "file": None,
        "path": None,
        "size_bytes": 0,
        "last_modified": None
    }

def save_youtube_cookies(content: str):
    """Lưu nội dung cookie YouTube (định dạng Netscape) vào data/youtube_cookies.txt"""
    yt_cookies = os.path.join(DATA_DIR, "youtube_cookies.txt")
    with open(yt_cookies, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    safe_log(f"💾 Đã lưu file cookie YouTube thành công: {yt_cookies} ({os.path.getsize(yt_cookies)} bytes)")
    return {
        "success": True,
        "path": yt_cookies,
        "size_bytes": os.path.getsize(yt_cookies)
    }

def _fetch_playlist_entries(target_url, max_scan=40):
    """Hàm helper chạy yt-dlp flat playlist extraction tốc độ cao"""
    ydl_opts = {
        "extract_flat": True,
        "playlistend": max_scan,
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "socket_timeout": 8,
        "lazy_playlist": True,
        "extractor_args": {"youtube": {"player_client": ["web"]}}
    }
    cookie_f = get_resolved_cookie_file()
    if cookie_f:
        ydl_opts["cookiefile"] = cookie_f

        
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)
            if not info:
                return [], {}
            entries = info.get("entries", [])
            channel_info = {
                "uploader": info.get("uploader", "") or info.get("channel", ""),
                "channel_id": info.get("channel_id", "") or info.get("id", ""),
                "channel_url": info.get("channel_url", "") or info.get("uploader_url", ""),
            }
            return [e for e in entries if e], channel_info
    except Exception as e:
        safe_log(f"⚠️ Lỗi quét URL {target_url}: {e}")
        return [], {}

def scan_channel_all_media(channel_url, channel_name="", min_views=0, max_duration_sec=0, max_scan=40, custom_source_dir=None, custom_dest_dir=None, force_refresh=False):
    """
    Quét đồng thời cả Video dài (/videos) và YouTube Shorts (/shorts) của kênh YouTube:
    - Trích xuất siêu nhanh: id, title, sanitized_title, url, views, duration, thumbnails, is_short, is_downloaded
    - Tích hợp bộ đệm TTL Cache 120s giúp chuyển đổi và xem danh sách clip tức thì
    - Sắp xếp theo view count giảm dần
    """
    base_url = get_channel_clean_base_url(channel_url)
    if not base_url:
        return {"success": False, "error": "URL kênh không hợp lệ", "videos": [], "shorts": []}

    cache_key = f"{base_url}_{max_scan}_{min_views}_{max_duration_sec}_{custom_source_dir}_{custom_dest_dir}"
    now_ts = time.time()
    
    # Kiểm tra cache nếu không yêu cầu quét ép buộc (force_refresh)
    if not force_refresh and cache_key in _CHANNEL_SCAN_CACHE:
        cached_ts, cached_res = _CHANNEL_SCAN_CACHE[cache_key]
        if (now_ts - cached_ts) < _SCAN_CACHE_TTL_SEC:
            return cached_res
        else:
            del _CHANNEL_SCAN_CACHE[cache_key]

    videos_url = f"{base_url}/videos"
    shorts_url = f"{base_url}/shorts"
    
    # Quét song song cả 2 tab bằng ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_videos = executor.submit(_fetch_playlist_entries, videos_url, max_scan)
        future_shorts = executor.submit(_fetch_playlist_entries, shorts_url, max_scan)
        
        video_entries, v_info = future_videos.result()
        short_entries, s_info = future_shorts.result()

    current_titles, previous_titles = get_existing_product_titles(custom_source_dir, custom_dest_dir)
    detected_channel_name = channel_name or v_info.get("uploader") or s_info.get("uploader") or base_url.split("/")[-1].replace("@", "")

    # 1. Xử lý danh sách Video dài
    parsed_videos = []
    seen_video_ids = set()
    for e in video_entries:
        vid_id = e.get("id", "")
        if not vid_id or vid_id in seen_video_ids:
            continue
        seen_video_ids.add(vid_id)
        
        title = e.get("title", "")
        if not title:
            continue
            
        views = e.get("view_count") or 0
        duration = e.get("duration") or 0
        
        # Áp dụng bộ lọc nếu có yêu cầu
        if min_views > 0 and views < min_views:
            continue
        if max_duration_sec > 0 and duration > max_duration_sec:
            continue
            
        title_sanitized = sanitize_filename(title)
        title_low = title.strip().lower()
        san_low = title_sanitized.lower()
        vid_low = vid_id.lower()

        is_current = (
            title_low in current_titles or 
            san_low in current_titles or
            vid_low in current_titles
        )
        is_previous = (
            not is_current and (
                title_low in previous_titles or
                san_low in previous_titles or
                vid_low in previous_titles
            )
        )
        
        if is_current:
            status = "downloaded"
        elif is_previous:
            status = "previously_downloaded"
        else:
            status = "ready"
        
        # Lấy thumbnail chất lượng tốt nhất
        thumbnails = e.get("thumbnails", [])
        thumb_url = thumbnails[-1].get("url") if thumbnails else f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"
        
        # Gắn tag 'short' nếu video có thời lượng dưới 2 phút (< 120s), gắn tag 'long' nếu video trên 15 phút (> 900s)
        is_short_duration = bool(duration and duration < 120)
        is_long_duration = bool(duration and duration > 900)
        video_tag = "short" if is_short_duration else ("long" if is_long_duration else "medium")
        
        parsed_videos.append({
            "id": vid_id,
            "title": title,
            "sanitized_title": title_sanitized,
            "url": f"https://www.youtube.com/watch?v={vid_id}",
            "views": views,
            "formatted_views": format_views(views),
            "duration": duration,
            "formatted_duration": format_duration(duration),
            "thumbnail": thumb_url,
            "channel": detected_channel_name,
            "is_short": is_short_duration,
            "is_long": is_long_duration,
            "video_tag": video_tag,
            "is_downloaded": is_current,
            "is_previously_downloaded": is_previous,
            "status": status
        })

    # 2. Xử lý danh sách Shorts
    parsed_shorts = []
    seen_short_ids = set()
    for e in short_entries:
        vid_id = e.get("id", "")
        if not vid_id or vid_id in seen_short_ids or vid_id in seen_video_ids:
            continue
        seen_short_ids.add(vid_id)
        
        title = e.get("title", "")
        if not title:
            continue
            
        views = e.get("view_count") or 0
        duration = e.get("duration") or 0
        
        if min_views > 0 and views < min_views:
            continue
            
        title_sanitized = sanitize_filename(title)
        title_low = title.strip().lower()
        san_low = title_sanitized.lower()
        vid_low = vid_id.lower()

        is_current = (
            title_low in current_titles or 
            san_low in current_titles or
            vid_low in current_titles
        )
        is_previous = (
            not is_current and (
                title_low in previous_titles or
                san_low in previous_titles or
                vid_low in previous_titles
            )
        )
        
        if is_current:
            status = "downloaded"
        elif is_previous:
            status = "previously_downloaded"
        else:
            status = "ready"
        
        thumbnails = e.get("thumbnails", [])
        thumb_url = thumbnails[-1].get("url") if thumbnails else f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"
        
        parsed_shorts.append({
            "id": vid_id,
            "title": title,
            "sanitized_title": title_sanitized,
            "url": f"https://www.youtube.com/shorts/{vid_id}",
            "views": views,
            "formatted_views": format_views(views),
            "duration": duration,
            "formatted_duration": format_duration(duration),
            "thumbnail": thumb_url,
            "channel": detected_channel_name,
            "is_short": True,
            "is_long": False,
            "video_tag": "short",
            "is_downloaded": is_current,
            "is_previously_downloaded": is_previous,
            "status": status
        })

    # Sắp xếp theo lượt xem giảm dần
    parsed_videos.sort(key=lambda x: x["views"], reverse=True)
    parsed_shorts.sort(key=lambda x: x["views"], reverse=True)

    result_data = {
        "success": True,
        "channel_name": detected_channel_name,
        "channel_url": base_url,
        "videos": parsed_videos,
        "shorts": parsed_shorts,
        "total_videos": len(parsed_videos),
        "total_shorts": len(parsed_shorts)
    }
    _CHANNEL_SCAN_CACHE[cache_key] = (now_ts, result_data)
    return result_data

def scan_and_filter_youtube_channel(channel_url, channel_name="", min_views=1000000, max_duration_sec=1200, max_scan=100):
    """Hàm tương thích ngược với code cũ"""
    res = scan_channel_all_media(channel_url, channel_name, min_views=min_views, max_duration_sec=max_duration_sec, max_scan=max_scan)
    if res.get("success"):
        # Trả về các video chưa tải
        return [v for v in res.get("videos", []) if not v.get("is_downloaded")]
    return []

def cleanup_temporary_files(target_dir, base_title="", video_id=""):
    """Dọn dẹp triệt để các file rác .part, .ytdl, .temp, .vtt, .srt khi tải dở hoặc hoàn tất"""
    if not os.path.exists(target_dir):
        return
    for f in os.listdir(target_dir):
        is_temp = f.endswith(('.part', '.ytdl', '.temp', '.vtt', '.srt')) or any(tag in f for tag in ['.f399.', '.f301.', '.f300.', '.f140.', '.f251.', '.f136.', '.f298.', '.f299.', '.f788.', '.f779.', '.f780.', '.f787.'])
        if is_temp:
            matches = False
            if not base_title and not video_id:
                matches = True
            elif base_title and (base_title[:15].lower() in f.lower() or f.lower().startswith(base_title[:10].lower())):
                matches = True
            elif video_id and video_id.lower() in f.lower():
                matches = True
            elif f.endswith(('.part', '.ytdl', '.temp', '.vtt', '.srt')):
                matches = True

                
            if matches:
                try:
                    fpath = os.path.join(target_dir, f)
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                except Exception:
                    pass

def download_youtube_video(video_url, channel_name, video_title=None, preferred_quality="1080p", custom_source_dir=None, task_id=None, progress_callback=None):
    """
    Tải video YouTube lưu thẳng vào input_sources/<channel_name>/<video_title>.mp4
    Đảm bảo:
    - Tự động xóa sạch mọi file .part / .temp trước và sau khi tải để tránh lỗi HTTP 403 Forbidden.
    - Luôn xuất ra định dạng .mp4 chuẩn duy nhất.
    - Xử lý mượt mà khi có Title Mismatch giữa yêu cầu và metadata gốc.
    - Tải dự phòng đa tầng (Tier 1 -> Tier 2 -> Tier 3).
    - Báo cáo tiến độ thời gian thực cho task_id và callback.
    """
    base_src_dir = custom_source_dir or VIDEO_DIR
    sanitized_channel = sanitize_filename(channel_name or "Downloads")
    target_channel_dir = os.path.join(base_src_dir, sanitized_channel)
    os.makedirs(target_channel_dir, exist_ok=True)
    
    # Trích xuất video id từ URL nếu có
    video_id = ""
    id_match = re.search(r'(?:v=|/shorts/|youtu\.be/)([a-zA-Z0-9_-]{11})', video_url)
    if id_match:
        video_id = id_match.group(1)

    requested_title = video_title or ""
    requested_sanitized = sanitize_filename(requested_title) if requested_title else ""
    
    # Dọn dẹp trước file rác cũ của video này nếu có (tránh lỗi Resume HTTP 403)
    cleanup_temporary_files(target_channel_dir, requested_sanitized, video_id)
    
    if requested_sanitized:
        out_tmpl = os.path.join(target_channel_dir, f"{requested_sanitized}.%(ext)s")
    else:
        out_tmpl = os.path.join(target_channel_dir, "%(title)s.%(ext)s")

    def yt_progress_hook(d):
        if not task_id:
            return
        status = d.get('status')
        if status == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes') or 0
            percent = int((downloaded / total) * 100) if total > 0 else 0
            speed = d.get('speed') or 0
            speed_mb = speed / (1024 * 1024) if speed else 0
            speed_str = f"{speed_mb:.1f} MB/s" if speed_mb > 0 else "Đang tải..."
            eta = d.get('eta') or 0
            eta_str = f"{eta}s" if eta > 0 else ""
            
            with DOWNLOAD_TASKS_LOCK:
                if task_id in DOWNLOAD_TASKS:
                    DOWNLOAD_TASKS[task_id]["progress_percent"] = min(percent, 98)
                    DOWNLOAD_TASKS[task_id]["downloaded_bytes"] = downloaded
                    DOWNLOAD_TASKS[task_id]["total_bytes"] = total
                    DOWNLOAD_TASKS[task_id]["speed_str"] = speed_str
                    DOWNLOAD_TASKS[task_id]["eta_str"] = eta_str
                    DOWNLOAD_TASKS[task_id]["status"] = "downloading"
            
            if progress_callback:
                try:
                    progress_callback(percent, speed_str, eta_str)
                except Exception:
                    pass
        elif status == 'finished':
            with DOWNLOAD_TASKS_LOCK:
                if task_id in DOWNLOAD_TASKS:
                    DOWNLOAD_TASKS[task_id]["progress_percent"] = 99
                    DOWNLOAD_TASKS[task_id]["status"] = "processing"

    base_ydl_opts = {
        "outtmpl": out_tmpl,
        "nocheckcertificate": True,
        "quiet": False,
        "overwrites": True,
        "no_continue": False,
        "writesubtitles": False,
        "writeautomaticsub": False,
        "progress_hooks": [yt_progress_hook],
    }

    
    if os.path.exists(FFMPEG_EXE):
        base_ydl_opts["ffmpeg_location"] = FFMPEG_EXE
        base_ydl_opts["merge_output_format"] = "mp4"

    if os.path.exists(DENO_EXE):
        base_ydl_opts["js_runtimes"] = {"deno": {"path": DENO_EXE}}
        base_ydl_opts["remote_components"] = ["ejs:github"]

    cookie_file_to_use = get_resolved_cookie_file()
    if cookie_file_to_use:
        base_ydl_opts["cookiefile"] = cookie_file_to_use
        safe_log(f"🍪 Nạp cookie YouTube từ: {os.path.basename(cookie_file_to_use)}")

    start_time = time.time()
    res_info = None
    download_success = False
    
    # ----------------------------------------------------
    # TIER 1: Chất lượng cao nhất 1080p/720p (Deno JS Engine + MP4 Merger)
    # ----------------------------------------------------
    ydl_opts_tier1 = dict(base_ydl_opts)
    ydl_opts_tier1["format"] = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
        
    try:
        with yt_dlp.YoutubeDL(ydl_opts_tier1) as ydl:
            res_info = ydl.extract_info(video_url, download=True)
            if res_info:
                download_success = True
    except Exception as e1:
        safe_log(f"⚠️ Lỗi tải Tier 1 ({e1}), kích hoạt Tier 2 Fallback (Android/Web-Creator Client)...")
        cleanup_temporary_files(target_channel_dir, requested_sanitized, video_id)
        
        # ----------------------------------------------------
        # TIER 2: Fallback Android / Web Creator (Bypass Token 403)
        # ----------------------------------------------------
        try:
            ydl_opts_tier2 = dict(base_ydl_opts)
            ydl_opts_tier2["quiet"] = True
            ydl_opts_tier2["extractor_args"] = {"youtube": {"player_client": ["android", "web_creator"]}}
            ydl_opts_tier2["format"] = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
            
            with yt_dlp.YoutubeDL(ydl_opts_tier2) as ydl:
                res_info = ydl.extract_info(video_url, download=True)
                if res_info:
                    download_success = True
        except Exception as e2:
            safe_log(f"⚠️ Lỗi tải Tier 2 ({e2}), kích hoạt Tier 3 Fallback (Direct Progressive MP4)...")
            cleanup_temporary_files(target_channel_dir, requested_sanitized, video_id)
            
            # ----------------------------------------------------
            # TIER 3: Fallback Cuối Cùng - Progressive Direct MP4
            # ----------------------------------------------------
            try:
                ydl_opts_tier3 = dict(base_ydl_opts)
                ydl_opts_tier3["quiet"] = True
                ydl_opts_tier3["extractor_args"] = {"youtube": {"player_client": ["android"]}}
                ydl_opts_tier3["format"] = "22/18/best[ext=mp4]/best"
                with yt_dlp.YoutubeDL(ydl_opts_tier3) as ydl:
                    res_info = ydl.extract_info(video_url, download=True)
                    if res_info:
                        download_success = True
            except Exception as e3:
                safe_log(f"❌ Toàn bộ các tầng tải đều thất bại cho video {video_title or video_url}: {e3}")
                download_success = False

    end_time = time.time()
    elapsed = end_time - start_time
    
    # Dọn dẹp triệt để file rác .part / .ytdl / .temp ngay sau khi tải
    cleanup_temporary_files(target_channel_dir, requested_sanitized, video_id)
    
    # Xác định tiêu đề thực tế & tiêu đề mong muốn
    actual_title = (res_info.get("title") if res_info else "") or requested_title or "video"
    actual_sanitized = sanitize_filename(actual_title)
    final_display_title = requested_title or actual_title
    
    # ----------------------------------------------------
    # TÌM KIẾM FILE MP4 ĐẦU RA MỘT CÁCH THÔNG MINH
    # ----------------------------------------------------
    final_file = None
    candidate_paths = []
    
    # Ưu tiên 1: Tên theo requested_sanitized.mp4
    if requested_sanitized:
        candidate_paths.append(os.path.join(target_channel_dir, f"{requested_sanitized}.mp4"))
        
    # Ưu tiên 2: Tên theo actual_sanitized.mp4
    if actual_sanitized:
        candidate_paths.append(os.path.join(target_channel_dir, f"{actual_sanitized}.mp4"))
        
    for cp in candidate_paths:
        if os.path.exists(cp) and os.path.isfile(cp) and os.path.getsize(cp) > 500 * 1024:
            final_file = cp
            break
            
    # Nếu chưa tìm thấy trực tiếp, quét thư mục tìm file tương ứng
    if not final_file and os.path.exists(target_channel_dir):
        # Kiểm tra nếu có file .part đã tải xong nhưng Windows bị vướng lock chưa kịp đổi tên
        for f in os.listdir(target_channel_dir):
            if f.endswith('.part'):
                pf_path = os.path.join(target_channel_dir, f)
                if os.path.isfile(pf_path) and os.path.getsize(pf_path) > 500 * 1024:
                    time.sleep(0.5)
                    target_mp4 = pf_path[:-5]
                    if not target_mp4.endswith('.mp4'):
                        target_mp4 += '.mp4'
                    try:
                        if os.path.exists(target_mp4):
                            os.remove(target_mp4)
                        os.rename(pf_path, target_mp4)
                        final_file = target_mp4
                        safe_log(f"✅ Tự động cứu và hoàn tất tệp video: {os.path.basename(final_file)}")
                        break
                    except Exception:
                        pass

        all_files = os.listdir(target_channel_dir)
        # Sắp xếp file theo thời gian sửa đổi mới nhất
        all_files.sort(key=lambda fn: os.path.getmtime(os.path.join(target_channel_dir, fn)) if os.path.exists(os.path.join(target_channel_dir, fn)) else 0, reverse=True)
        
        for f in all_files:
            if f.endswith(('.part', '.ytdl', '.temp', '.json')):
                continue
            cand_path = os.path.join(target_channel_dir, f)
            if not os.path.isfile(cand_path) or os.path.getsize(cand_path) < 500 * 1024:
                continue
                
            fname_lower = f.lower()
            matches = False
            if requested_sanitized and (requested_sanitized.lower() in fname_lower or fname_lower.startswith(requested_sanitized[:15].lower())):
                matches = True
            elif actual_sanitized and (actual_sanitized.lower() in fname_lower or fname_lower.startswith(actual_sanitized[:15].lower())):
                matches = True
            elif video_id and video_id.lower() in fname_lower:
                matches = True
                
            if matches:
                # Nếu là định dạng webm hoặc mkv thì convert sang mp4
                if f.endswith(('.webm', '.mkv')) and os.path.exists(FFMPEG_EXE):
                    import subprocess
                    target_mp4 = os.path.splitext(cand_path)[0] + ".mp4"
                    safe_log(f"🔄 Đang chuyển đổi {f} sang định dạng chuẩn .mp4...")
                    conv_cmd = [FFMPEG_EXE, "-y", "-i", cand_path, "-c", "copy", target_mp4]
                    subprocess.run(conv_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    try:
                        os.remove(cand_path)
                    except Exception:
                        pass
                    final_file = target_mp4
                    break
                elif f.endswith('.mp4'):
                    final_file = cand_path
                    break

    # Lưu thông tin heatmap vào thư mục temp (không lưu vào input_sources để thư mục chỉ chứa duy nhất file mp4)
    try:
        heatmap_data = res_info.get("heatmap") if res_info else None
        if heatmap_data and final_file:
            from config import TEMP_DIR
            os.makedirs(TEMP_DIR, exist_ok=True)
            heatmap_file = os.path.join(TEMP_DIR, f"{sanitize_filename(os.path.basename(final_file))}.heatmap.json")
            with open(heatmap_file, "w", encoding="utf-8") as hf:
                json.dump(heatmap_data, hf)
    except Exception:
        pass


    # Kiểm tra tính hợp lệ của file mp4 cuối cùng (lớn hơn 500KB)
    is_valid_mp4 = bool(final_file and os.path.exists(final_file) and final_file.endswith('.mp4') and (os.path.getsize(final_file) > 500 * 1024))
    
    # Đảm bảo chỉ giữ lại duy nhất tệp .mp4 trong thư mục tải về, xóa sạch mọi file phụ đề nếu có
    if is_valid_mp4 and final_file:
        base_target = os.path.splitext(final_file)[0]
        for sub_ext in ['.vtt', '.en.vtt', '.en-orig.vtt', '.en-US.vtt', '.srt', '.en.srt']:
            sf = base_target + sub_ext
            if os.path.exists(sf):
                try:
                    os.remove(sf)
                except Exception:
                    pass

    if not is_valid_mp4:

        cleanup_temporary_files(target_channel_dir, requested_sanitized, video_id)
        with DOWNLOAD_TASKS_LOCK:
            if task_id in DOWNLOAD_TASKS:
                DOWNLOAD_TASKS[task_id]["status"] = "error"
                DOWNLOAD_TASKS[task_id]["error_msg"] = "Tệp video không hợp lệ hoặc tải thất bại"
                DOWNLOAD_TASKS[task_id]["finish_time"] = time.time()
                
        return {
            "success": False,
            "file_path": None,
            "title": final_display_title,
            "channel": channel_name,
            "size_mb": 0,
            "download_time_s": elapsed,
            "speed_mb_s": 0
        }
        
    file_size_mb = os.path.getsize(final_file) / (1024 * 1024)
    speed_mb_s = file_size_mb / elapsed if elapsed > 0 else 0
    
    with DOWNLOAD_TASKS_LOCK:
        if task_id in DOWNLOAD_TASKS:
            DOWNLOAD_TASKS[task_id]["status"] = "completed"
            DOWNLOAD_TASKS[task_id]["progress_percent"] = 100
            DOWNLOAD_TASKS[task_id]["file_path"] = final_file
            DOWNLOAD_TASKS[task_id]["size_mb"] = round(file_size_mb, 2)
            DOWNLOAD_TASKS[task_id]["download_time_s"] = round(elapsed, 1)
            DOWNLOAD_TASKS[task_id]["finish_time"] = time.time()
            DOWNLOAD_TASKS[task_id]["error_msg"] = None
    
    return {
        "success": True,
        "file_path": final_file,
        "title": final_display_title,
        "channel": channel_name,
        "size_mb": file_size_mb,
        "download_time_s": elapsed,
        "speed_mb_s": speed_mb_s
    }

def _download_queue_worker():
    """Luồng worker nền liên tục xử lý các video trong hàng đợi tuần tự (FIFO)"""
    safe_log("🚀 Khởi động Background Download Queue Worker...")
    while True:
        try:
            task_info = DOWNLOAD_WORKER_QUEUE.get()
            if task_info is None:
                break
                
            task_id = task_info.get("task_id")
            url = task_info.get("url")
            channel = task_info.get("channel", "Downloads")
            title = task_info.get("title", "video")
            custom_source_dir = task_info.get("custom_source_dir")
            
            with DOWNLOAD_TASKS_LOCK:
                if task_id in DOWNLOAD_TASKS:
                    DOWNLOAD_TASKS[task_id]["status"] = "downloading"
                    
            safe_log(f"▶️ [Queue Worker] Bắt đầu tải: {title} (Kênh: {channel})...")
            download_youtube_video(
                video_url=url,
                channel_name=channel,
                video_title=title,
                custom_source_dir=custom_source_dir,
                task_id=task_id
            )
        except Exception as e:
            safe_log(f"❌ Lỗi trong Download Queue Worker: {e}")
        finally:
            DOWNLOAD_WORKER_QUEUE.task_done()
            time.sleep(0.5)

def ensure_queue_worker_started():
    """Đảm bảo worker chạy ngầm luôn sẵn sàng nhận việc"""
    global QUEUE_WORKER_STARTED
    with QUEUE_WORKER_LOCK:
        if not QUEUE_WORKER_STARTED:
            t = threading.Thread(target=_download_queue_worker, daemon=True)
            t.start()
            QUEUE_WORKER_STARTED = True

def enqueue_download_task(item, custom_source_dir=None):
    """Đưa 1 video vào hàng đợi tải chạy nền bất đồng bộ theo thứ tự FIFO"""
    ensure_queue_worker_started()
    url = item.get("url")
    title = item.get("title") or "video"
    channel = item.get("channel") or item.get("channel_name") or "Downloads"
    is_short = item.get("is_short", False)
    thumbnail = item.get("thumbnail") or ""
    task_id = item.get("task_id") or f"dl_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
    
    with DOWNLOAD_TASKS_LOCK:
        # Nếu video đã có trong hàng đợi và đang chờ hoặc đang tải -> trả về task hiện tại
        for tid, t in DOWNLOAD_TASKS.items():
            if t["url"] == url and t["status"] in ["queued", "downloading", "processing"]:
                return t
                
        task_obj = {
            "task_id": task_id,
            "url": url,
            "title": title,
            "sanitized_title": sanitize_filename(title),
            "channel": channel,
            "is_short": is_short,
            "thumbnail": thumbnail,
            "status": "queued",
            "progress_percent": 0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "speed_str": "0 MB/s",
            "eta_str": "--",
            "size_mb": 0,
            "file_path": None,
            "error_msg": None,
            "start_time": time.time(),
            "finish_time": None
        }
        DOWNLOAD_TASKS[task_id] = task_obj

    DOWNLOAD_WORKER_QUEUE.put({
        "task_id": task_id,
        "url": url,
        "channel": channel,
        "title": title,
        "custom_source_dir": custom_source_dir
    })
    
    safe_log(f"📥 Đã thêm vào hàng đợi tải: {title} (Kênh: {channel})")
    return task_obj

def get_download_queue_status():
    """Lấy danh sách và thống kê toàn bộ tác vụ tải video hiện tại"""
    with DOWNLOAD_TASKS_LOCK:
        tasks = list(DOWNLOAD_TASKS.values())
        active_count = sum(1 for t in tasks if t["status"] in ["downloading", "processing"])
        queued_count = sum(1 for t in tasks if t["status"] == "queued")
        completed_count = sum(1 for t in tasks if t["status"] == "completed")
        error_count = sum(1 for t in tasks if t["status"] == "error")
        
        return {
            "tasks": tasks[-50:],
            "active_count": active_count,
            "queued_count": queued_count,
            "completed_count": completed_count,
            "error_count": error_count,
            "total_count": len(tasks)
        }

def clear_completed_tasks():
    """Xóa các tác vụ đã hoàn thành hoặc lỗi khỏi danh sách hiển thị"""
    with DOWNLOAD_TASKS_LOCK:
        to_delete = [tid for tid, t in DOWNLOAD_TASKS.items() if t["status"] in ["completed", "error"]]
        for tid in to_delete:
            del DOWNLOAD_TASKS[tid]
        return len(to_delete)

