import os
import sys
import json
import re
import shutil
import gc
import stat
import time
import datetime
import subprocess

import hashlib

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

def generate_video_id(channel, title):
    """
    Sinh ID unique duy nhất cho mỗi video dựa trên channel và title.
    Định dạng: vid_<10 ký tự hash>
    Đảm bảo 1 video luôn có đúng 1 ID cố định, nhất quán giữa mọi tiến trình.
    """
    clean_c = sanitize_filename(str(channel or "")).strip().lower()
    clean_t = sanitize_filename(str(title or "")).strip().lower()
    raw = f"{clean_c}/{clean_t}"
    h = hashlib.md5(raw.encode("utf-8")).hexdigest()[:10]
    return f"vid_{h}"

from config import HISTORY_FILE, ACCOUNTS_FILE, SETTINGS_FILE, VIDEO_DIR, OUTPUT_BASE_DIR

def load_settings():
    default_settings = {
        "adspower": {
            "api_url": "http://local.adspower.net:50325",
            "api_key": ""
        },
        "hma": {
            "cli_path": "",
            "enabled": True,
            "switch_mode": "country",
            "wait_seconds_after_switch": 5,
            "block_vietnam_ip": True,
            "require_foreign_ip": True
        },
        "tiktok_upload": {
            "auto_submit": True,
            "close_browser_after_finish": True,
            "wait_timeout": 240,
            "max_daily_posts_per_account": 3,
            "strip_part_from_caption": True
        },
        "gemini": {
            "api_key": "",
            "model": "gemini-3.7-flash"
        },
        "telegram": {
            "bot_token": "",
            "chat_id": "",
            "enabled": True
        }
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in default_settings.items():
                    if k not in data:
                        data[k] = v
                    elif isinstance(v, dict) and isinstance(data[k], dict):
                        for sub_k, sub_v in v.items():
                            if sub_k not in data[k]:
                                data[k][sub_k] = sub_v
                return data
        except Exception:
            return default_settings
    return default_settings

def save_settings(settings_data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_history(history_data):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving history: {e}")

def extract_drive_folder_id(url_or_path):
    """Trích xuất Folder ID nếu là link Google Drive"""
    if "drive.google.com" in url_or_path:
        match = re.search(r"folders/([a-zA-Z0-9_-]+)", url_or_path)
        if match:
            return match.group(1)
        match_id = re.search(r"id=([a-zA-Z0-9_-]+)", url_or_path)
        if match_id:
            return match_id.group(1)
    return None

def resolve_google_drive_path(url_or_path):
    """Ánh xạ Link URL Google Drive sang thư mục cục bộ của Google Drive Desktop (ổ G:)"""
    if not url_or_path:
        return ""
    url_or_path = url_or_path.strip().strip('"').strip("'")
    
    drive_id = extract_drive_folder_id(url_or_path)
    if drive_id:
        # Kiểm tra thư mục ánh xạ trên ổ G: của Windows
        g_base = os.path.join("G:\\.shortcut-targets-by-id", drive_id)
        if os.path.exists(g_base):
            # Nếu có thư mục con sản phẩm/nguồn, ưu tiên trỏ thẳng vào
            for sub in ["video_source", "products"]:
                sub_path = os.path.join(g_base, sub)
                if os.path.exists(sub_path) and os.path.isdir(sub_path):
                    return sub_path
            return g_base
    return os.path.normpath(url_or_path)

_CACHE_SCAN_SOURCE = {}
_CACHE_FINISHED_RESULTS = {}
_CACHE_TTL = 4.0  # Giữ cache 4 giây để UI phản hồi tức thì (<5ms) khi chuyển tab

def invalidate_drive_caches():
    global _CACHE_SCAN_SOURCE, _CACHE_FINISHED_RESULTS
    _CACHE_SCAN_SOURCE.clear()
    _CACHE_FINISHED_RESULTS.clear()

def get_clip_disk_part_labels(channel, title, dest_path=None):
    """
    Lấy danh sách các label part ('Part 1', 'Part 2',...) thực tế trên đĩa của một video.
    Đảm bảo việc xét duyệt video đã đăng chỉ hoàn tất khi 100% các part trên đĩa đã đăng.
    """
    try:
        if not dest_path:
            acc_d = load_accounts_data()
            dest_path = acc_d.get("dest_path", "")
            if not dest_path or not os.path.exists(dest_path):
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                candidates = [
                    OUTPUT_BASE_DIR,
                    os.path.join(base_dir, "output_product"),
                    os.path.join(base_dir, "storage", "outputs"),
                    os.path.join(base_dir, "Tiktok_Builder_Output")
                ]
                for cand in candidates:
                    if cand and os.path.exists(cand):
                        dest_path = cand
                        break

        resolved_dest = resolve_google_drive_path(dest_path)
        if not resolved_dest or not os.path.exists(resolved_dest):
            return []

        c_chan = str(channel or "").strip()
        c_title = str(title or "").strip()

        # Thử tìm trực tiếp thư mục theo các quy ước đường dẫn
        candidates = [
            os.path.join(resolved_dest, c_chan, c_title),
            os.path.join(resolved_dest, sanitize_filename(c_chan), sanitize_filename(c_title))
        ]
        target_dir = None
        for cand in candidates:
            if os.path.isdir(cand):
                target_dir = cand
                break

        # Nếu không thấy theo đường dẫn trực tiếp, quét đệ quy các folder
        if not target_dir:
            san_chan = sanitize_filename(c_chan).lower()
            san_title = sanitize_filename(c_title).lower()
            for root, dirs, files in os.walk(resolved_dest):
                folder_name = os.path.basename(os.path.dirname(root)) or os.path.basename(root)
                video_title = os.path.basename(root)
                if ((sanitize_filename(folder_name).lower() == san_chan or not san_chan) and
                    sanitize_filename(video_title).lower() == san_title):
                    target_dir = root
                    break

        if not target_dir or not os.path.isdir(target_dir):
            return []

        files = os.listdir(target_dir)
        mp4_files = [f for f in files if f.endswith('.mp4')]
        if not mp4_files:
            return []

        full_vid = [f for f in mp4_files if f.startswith('edited_') or 'edited_full' in f]
        candidate_parts = [
            f for f in mp4_files 
            if f not in full_vid 
            and f.lower() != 'original.mp4' 
            and not f.startswith('original_')
            and not f.endswith('-original.mp4')
        ]

        def get_part_sort_key_internal(filename):
            match = re.search(r'part[_\s\-]*(\d+)', filename, re.IGNORECASE)
            if match:
                return (0, int(match.group(1)), filename)
            ts_match = re.search(r'-(\d\d)\.(\d\d)\.(\d\d)', filename)
            if ts_match:
                sec = int(ts_match.group(1))*3600 + int(ts_match.group(2))*60 + int(ts_match.group(3))
                return (1, sec, filename)
            return (2, 0, filename)

        sorted_parts = sorted(candidate_parts, key=get_part_sort_key_internal)
        return [f"Part {idx + 1}" for idx in range(len(sorted_parts))]
    except Exception as e:
        print(f"Lỗi get_clip_disk_part_labels ({channel}/{title}): {e}")
        return []

def scan_finished_results(dest_path=None, force=False):
    """
    Quét các video thành phẩm đã xuất trong thư mục đích.
    Sắp xếp có logic rõ ràng theo yêu cầu:
    1. Video CHƯA upload lên TikTok đứng trước.
    2. Video ĐÃ upload lên TikTok đứng sau.
    3. Trong mỗi nhóm: Video MỚI NHẤT (mtime gần nhất) đứng trước, video cũ đứng sau cùng.
    """
    global _CACHE_FINISHED_RESULTS
    
    if not dest_path:
        acc_d = load_accounts_data()
        dest_path = acc_d.get("dest_path", "")
        if not dest_path or not os.path.exists(dest_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            candidates = [
                OUTPUT_BASE_DIR,
                os.path.join(base_dir, "output_product"),
                os.path.join(base_dir, "storage", "outputs"),
                os.path.join(base_dir, "Tiktok_Builder_Output")
            ]
            for cand in candidates:
                if cand and os.path.exists(cand):
                    dest_path = cand
                    break

    resolved_dest = resolve_google_drive_path(dest_path)
    cache_key = str(resolved_dest or "")
    now = time.time()
    if not force and cache_key in _CACHE_FINISHED_RESULTS:
        c_time, c_val = _CACHE_FINISHED_RESULTS[cache_key]
        if now - c_time < _CACHE_TTL:
            return c_val

    if not resolved_dest or not os.path.exists(resolved_dest):
        empty_res = {"results": [], "total_count": 0, "unuploaded_count": 0, "uploaded_count": 0}
        _CACHE_FINISHED_RESULTS[cache_key] = (now, empty_res)
        return empty_res

    # Nạp dữ liệu tài khoản TikTok để kiểm tra trạng thái đã đăng
    accounts_data = load_accounts_data()
    tiktok_accounts = accounts_data.get("tiktok_accounts", [])

    def check_clip_tiktok_status(c_channel, c_title):
        """Kiểm tra clip hoặc các parts đã được đăng lên tài khoản TikTok nào chưa"""
        matched_acc = ""
        matched_at = ""
        matched_parts_status = {}
        is_clip_posted = False

        for acc in tiktok_accounts:
            acc_name = acc.get("account_name", "")
            posted_clips = acc.get("posted_clips", {})
            for pk, pv in posted_clips.items():
                pv_chan = pv.get("channel", "")
                pv_title = pv.get("title", "")
                
                # Khớp theo key chính xác hoặc tên chuẩn hóa
                if (pk == f"{c_channel}/{c_title}" or 
                    (sanitize_filename(pv_chan) == sanitize_filename(c_channel) and sanitize_filename(pv_title) == sanitize_filename(c_title)) or
                    (sanitize_filename(pk) == sanitize_filename(f"{c_channel}/{c_title}")) or
                    (sanitize_filename(pv_title) == sanitize_filename(c_title))):
                    
                    p_stat = pv.get("parts_status", {})
                    if p_stat:
                        matched_parts_status.update(p_stat)
                    if pv.get("posted_at") and not matched_at:
                        matched_at = pv.get("posted_at")
                    if not matched_acc:
                        matched_acc = acc_name

                    if pv.get("posted"):
                        is_clip_posted = True
                        return True, acc_name, pv.get("posted_at", ""), pv.get("parts_status", {})

        return is_clip_posted, matched_acc, matched_at, matched_parts_status

    results = []
    try:
        # Duyệt thư mục đích (Tiktok_Builder_Output hoặc Documents/Tiktok builder)
        for root, dirs, files in os.walk(resolved_dest):
            mp4_files = [f for f in files if f.endswith('.mp4')]
            if not mp4_files:
                continue

            full_vid = [f for f in mp4_files if f.startswith('edited_') or 'edited_full' in f]
            
            # Nhận diện tất cả các file parts:
            candidate_parts = [
                f for f in mp4_files 
                if f not in full_vid 
                and f.lower() != 'original.mp4' 
                and not f.startswith('original_')
                and not f.endswith('-original.mp4')
            ]

            if candidate_parts or full_vid:
                folder_name = os.path.basename(os.path.dirname(root)) or os.path.basename(root)
                video_title = os.path.basename(root)
                
                # Tính thời gian sửa đổi gần nhất (mtime)
                file_mtimes = []
                for f in mp4_files:
                    try:
                        file_mtimes.append(os.path.getmtime(os.path.join(root, f)))
                    except Exception:
                        pass
                mtime = max(file_mtimes) if file_mtimes else os.path.getmtime(root)
                created_at_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

                # Quản lý ID unique duy nhất cho mỗi video (lưu vào video_meta.json nếu chưa có)
                vid_id = generate_video_id(folder_name, video_title)
                meta_file = os.path.join(root, "video_meta.json")
                if os.path.exists(meta_file):
                    try:
                        with open(meta_file, "r", encoding="utf-8") as mf:
                            m_data = json.load(mf)
                            if m_data.get("video_id"):
                                vid_id = m_data["video_id"]
                    except Exception:
                        pass
                else:
                    try:
                        with open(meta_file, "w", encoding="utf-8") as mf:
                            json.dump({
                                "video_id": vid_id,
                                "channel": folder_name,
                                "title": video_title,
                                "created_at": created_at_str
                            }, mf, ensure_ascii=False, indent=2)
                    except Exception:
                        pass

                # Kiểm tra trạng thái đã đăng TikTok
                is_uploaded, posted_acc, posted_at, parts_status = check_clip_tiktok_status(folder_name, video_title)

                # Sắp xếp các part theo số thứ tự (part 1, part 2,...) hoặc timestamp/tên file
                def get_part_sort_key(filename):
                    match = re.search(r'part[_\s\-]*(\d+)', filename, re.IGNORECASE)
                    if match:
                        return (0, int(match.group(1)), filename)
                    ts_match = re.search(r'-(\d\d)\.(\d\d)\.(\d\d)', filename)
                    if ts_match:
                        sec = int(ts_match.group(1))*3600 + int(ts_match.group(2))*60 + int(ts_match.group(3))
                        return (1, sec, filename)
                    return (2, 0, filename)

                parts_list = []
                for idx, p in enumerate(sorted(candidate_parts, key=get_part_sort_key)):
                    part_label = f"Part {idx + 1}"
                    p_stat = parts_status.get(part_label, {})
                    p_posted = bool(p_stat.get("posted", False)) if parts_status else is_uploaded
                    p_posted_at = p_stat.get("posted_at", posted_at) if parts_status else posted_at

                    parts_list.append({
                        "name": p,
                        "label": part_label,
                        "part_id": f"{vid_id}_p{idx + 1}",
                        "file_path": os.path.join(root, p),
                        "url": f"/video_stream?path={os.path.join(root, p)}",
                        "posted": p_posted,
                        "posted_at": p_posted_at
                    })

                # QUY TẮC QUYẾT ĐỊNH: Nếu video có các parts thì CHỈ KHI 100% CÁC PARTS ĐÃ ĐĂNG
                # thì video mới được coi là is_uploaded = True!
                if parts_list:
                    is_uploaded = all(p["posted"] for p in parts_list)

                results.append({
                    "video_id": vid_id,
                    "title": video_title,
                    "folder_name": folder_name,
                    "path": root,
                    "parts": parts_list,
                    "has_full": len(full_vid) > 0,
                    "is_uploaded": is_uploaded,
                    "posted_account": posted_acc,
                    "posted_at": posted_at,
                    "mtime": mtime,
                    "created_at": created_at_str
                })
    except Exception as e:
        print(f"Lỗi quét output: {e}")

    # SẮP XẾP LOGIC CHÍNH XÁC:
    # 1. is_uploaded == False (Chưa upload) lên ĐẦU TIÊN (0), is_uploaded == True (Đã upload) xếp PHÍA SAU (1).
    # 2. Trong mỗi nhóm: mtime mới nhất đứng trước (-mtime).
    results.sort(key=lambda x: (1 if x.get("is_uploaded", False) else 0, -x.get("mtime", 0)))

    unuploaded_count = sum(1 for r in results if not r.get("is_uploaded", False))
    uploaded_count = sum(1 for r in results if r.get("is_uploaded", False))

    res_data = {
        "results": results,
        "total_count": len(results),
        "unuploaded_count": unuploaded_count,
        "uploaded_count": uploaded_count
    }
    _CACHE_FINISHED_RESULTS[cache_key] = (now, res_data)
    return res_data


_DURATION_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "storage", "video_durations.json")
_DURATION_CACHE = {}
_DURATION_CACHE_LOADED = False

def load_duration_cache():
    global _DURATION_CACHE, _DURATION_CACHE_LOADED
    if not _DURATION_CACHE_LOADED:
        if os.path.exists(_DURATION_CACHE_FILE):
            try:
                with open(_DURATION_CACHE_FILE, "r", encoding="utf-8") as f:
                    _DURATION_CACHE = json.load(f)
            except Exception:
                _DURATION_CACHE = {}
        _DURATION_CACHE_LOADED = True
    return _DURATION_CACHE

def save_duration_cache():
    global _DURATION_CACHE
    try:
        os.makedirs(os.path.dirname(_DURATION_CACHE_FILE), exist_ok=True)
        with open(_DURATION_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_DURATION_CACHE, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def format_duration(seconds):
    if not seconds or seconds <= 0:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def get_cached_duration(file_path):
    if not file_path or not os.path.exists(file_path):
        return 0.0, "0:00"
    
    target_file = file_path
    if os.path.isdir(file_path):
        try:
            for f in os.listdir(file_path):
                if f.lower().endswith(('.mp4', '.mkv', '.mov', '.avi', '.webm')):
                    target_file = os.path.join(file_path, f)
                    break
        except Exception:
            pass
            
    if not os.path.isfile(target_file):
        return 0.0, "0:00"

    cache = load_duration_cache()
    try:
        mtime = os.path.getmtime(target_file)
        size = os.path.getsize(target_file)
    except Exception:
        return 0.0, "0:00"

    cache_entry = cache.get(target_file)
    if cache_entry and isinstance(cache_entry, dict) and cache_entry.get("mtime") == mtime and cache_entry.get("size") == size:
        dur = cache_entry.get("duration", 0.0)
        return dur, format_duration(dur)

    try:
        from src.services.video_processor import get_video_duration
        dur = get_video_duration(target_file)
    except Exception:
        dur = 0.0

    cache[target_file] = {
        "mtime": mtime,
        "size": size,
        "duration": dur,
        "duration_str": format_duration(dur)
    }
    return dur, format_duration(dur)


def scan_source_directory(source_path, dest_path=None, force=False):
    """
    Quét toàn diện thư mục nguồn và thư mục đích:
    - Quét các video thô (raw) đang có ở Source.
    - Quét các video đã biên tập (finished) ở Destination (Output) và trong history.json.
    - Đảm bảo các chỉ số trên Dashboard, Editor Studio và Kênh YouTube luôn chính xác 100%
      ngay cả sau khi video gốc đã được biên tập và xóa để tiết kiệm dung lượng đĩa.
    """
    global _CACHE_SCAN_SOURCE
    cache_key = f"{source_path or ''}|{dest_path or ''}"
    now = time.time()
    if not force and cache_key in _CACHE_SCAN_SOURCE:
        c_time, c_val = _CACHE_SCAN_SOURCE[cache_key]
        if now - c_time < _CACHE_TTL:
            return c_val

    resolved_source = resolve_google_drive_path(source_path)
    resolved_dest = resolve_google_drive_path(dest_path)

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if not resolved_source or not os.path.exists(resolved_source):
        default_candidates = [
            os.path.join(base_dir, "input_sources"),
            os.path.join(base_dir, "storage", "inputs"),
            os.path.join(base_dir, "video")
        ]
        for cand in default_candidates:
            if os.path.exists(cand):
                resolved_source = cand
                break
        if not resolved_source or not os.path.exists(resolved_source):
            resolved_source = os.path.join(base_dir, "input_sources")
            os.makedirs(resolved_source, exist_ok=True)

    if not resolved_dest or not os.path.exists(resolved_dest):
        resolved_dest = os.path.join(base_dir, "output_product")
        os.makedirs(resolved_dest, exist_ok=True)

    history = load_history()
    accounts_data = load_accounts_data()

    # Dùng map để gom nhóm video theo kênh
    channel_map = {}

    # 1. Khởi tạo từ danh sách YouTube Channels đã cấu hình
    for chan in accounts_data.get("youtube_channels", []):
        cname = chan.get("folder_name") or chan.get("name")
        if not cname:
            continue
        c_path = os.path.join(resolved_source, sanitize_filename(cname)) if resolved_source else ""
        channel_map[cname] = {
            "name": cname,
            "path": c_path if (c_path and os.path.exists(c_path)) else (os.path.join(resolved_source, cname) if resolved_source else ""),
            "videos_dict": {}
        }

    # 2. Quét các folder và video trong resolved_source
    if resolved_source and os.path.exists(resolved_source):
        try:
            entries = sorted(os.listdir(resolved_source))
            for entry in entries:
                full_entry_path = os.path.join(resolved_source, entry)
                if not os.path.isdir(full_entry_path) or entry.startswith('.'):
                    continue

                matched_cname = None
                for k in channel_map:
                    if k == entry or sanitize_filename(k) == sanitize_filename(entry):
                        matched_cname = k
                        break
                if not matched_cname:
                    matched_cname = entry
                    channel_map[matched_cname] = {
                        "name": entry,
                        "path": full_entry_path,
                        "videos_dict": {}
                    }

                # Quét video bên trong folder kênh này
                try:
                    sub_items = sorted(os.listdir(full_entry_path))
                    for sub in sub_items:
                        sub_path = os.path.join(full_entry_path, sub)
                        
                        # Subfolder chứa video (vd: SoyPato / Video 1 / raw.mp4)
                        if os.path.isdir(sub_path):
                            v_title = sub
                            sub_files = os.listdir(sub_path)
                            video_file_path = None
                            for f in sub_files:
                                if f.endswith(('.mp4', '.mkv', '.mov', '.avi')) and not f.startswith(('part_', 'edited_', 'title_banner')):
                                    if ' - part ' not in f:
                                        video_file_path = os.path.join(sub_path, f)
                                        break
                            if not video_file_path:
                                for f in sub_files:
                                    if f.endswith(('.mp4', '.mkv', '.mov', '.avi')):
                                        video_file_path = os.path.join(sub_path, f)
                                        break
                            
                            if video_file_path:
                                dur, dur_str = get_cached_duration(video_file_path)
                                channel_map[matched_cname]["videos_dict"][v_title] = {
                                    "title": v_title,
                                    "path": video_file_path,
                                    "dir_path": sub_path,
                                    "duration": dur,
                                    "duration_str": dur_str,
                                    "edited": False,
                                    "is_finished_only": False
                                }
                        # File video trực tiếp (vd: SoyPato / Video1.mp4)
                        elif sub.lower().endswith(('.mp4', '.mkv', '.mov', '.avi', '.webm')):
                            v_title = os.path.splitext(sub)[0]
                            dur, dur_str = get_cached_duration(sub_path)
                            channel_map[matched_cname]["videos_dict"][v_title] = {
                                "title": v_title,
                                "path": sub_path,
                                "dir_path": full_entry_path,
                                "duration": dur,
                                "duration_str": dur_str,
                                "edited": False,
                                "is_finished_only": False
                            }
                except Exception as err:
                    print(f"Lỗi đọc thư mục {entry}: {err}")
        except Exception as e:
            print(f"Lỗi đọc thư mục nguồn: {e}")

    # 3. Quét kết quả thành phẩm trong resolved_dest (Output)
    finished_data = scan_finished_results(resolved_dest)
    for finished_item in finished_data.get("results", []):
        f_channel = finished_item.get("folder_name", "")
        f_title = finished_item.get("title", "")
        if not f_title:
            continue

        matched_cname = None
        for k in channel_map:
            if k == f_channel or sanitize_filename(k) == sanitize_filename(f_channel):
                matched_cname = k
                break
        if not matched_cname:
            matched_cname = f_channel if f_channel else "Output"
            channel_map[matched_cname] = {
                "name": matched_cname,
                "path": os.path.join(resolved_dest, f_channel) if f_channel else resolved_dest,
                "videos_dict": {}
            }

        # Tìm video trong channel_map
        matched_vtitle = None
        for v_k in channel_map[matched_cname]["videos_dict"]:
            if v_k == f_title or sanitize_filename(v_k) == sanitize_filename(f_title):
                matched_vtitle = v_k
                break

        if matched_vtitle:
            channel_map[matched_cname]["videos_dict"][matched_vtitle]["edited"] = True
        else:
            f_path = finished_item.get("path", "")
            dur, dur_str = get_cached_duration(f_path)
            channel_map[matched_cname]["videos_dict"][f_title] = {
                "title": f_title,
                "path": f_path,
                "dir_path": f_path,
                "duration": dur,
                "duration_str": dur_str,
                "edited": True,
                "is_finished_only": True
            }

    # 4. Kiểm tra thêm trong history.json (đề phòng trường hợp file output bị sync trễ)
    for h_key, h_val in history.items():
        if not isinstance(h_val, dict):
            continue
        h_title = h_val.get("title") or h_key
        h_channel = h_val.get("channel", "")
        h_out = h_val.get("output_dir", "")
        if not h_channel and h_out:
            h_channel = os.path.basename(os.path.dirname(h_out))
            
        if not h_channel:
            continue

        matched_cname = None
        for k in channel_map:
            if k == h_channel or sanitize_filename(k) == sanitize_filename(h_channel):
                matched_cname = k
                break
        if not matched_cname:
            matched_cname = h_channel
            channel_map[matched_cname] = {
                "name": matched_cname,
                "path": os.path.join(resolved_dest, h_channel) if h_channel else resolved_dest,
                "videos_dict": {}
            }

        matched_vtitle = None
        for v_k in channel_map[matched_cname]["videos_dict"]:
            if v_k == h_title or sanitize_filename(v_k) == sanitize_filename(h_title):
                matched_vtitle = v_k
                break

        if matched_vtitle:
            channel_map[matched_cname]["videos_dict"][matched_vtitle]["edited"] = True
        elif h_out and os.path.exists(h_out):
            # Chỉ thêm khi thư mục output thực tế vẫn tồn tại trên đĩa
            dur, dur_str = get_cached_duration(h_out)
            channel_map[matched_cname]["videos_dict"][h_title] = {
                "title": h_title,
                "path": h_out,
                "dir_path": h_out,
                "duration": dur,
                "duration_str": dur_str,
                "edited": True,
                "is_finished_only": True
            }

    # 5. Đóng gói kết quả trả về
    result_folders = []
    for cname, cdata in channel_map.items():
        v_list = list(cdata["videos_dict"].values())
        # Sắp xếp: Unedited lên trước để tiện biên tập, Edited xuống dưới
        v_list.sort(key=lambda x: (x.get("edited", False), x.get("title", "")))
        result_folders.append({
            "name": cdata["name"],
            "path": cdata["path"],
            "videos": v_list
        })

    save_duration_cache()

    out_res = {"folders": result_folders, "source_path": source_path}
    _CACHE_SCAN_SOURCE[cache_key] = (now, out_res)
    return out_res

def remove_readonly(func, path, excinfo):
    """Callback xử lý file Read-Only trên Windows khi rmtree"""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

def robust_remove(target_path, retries=4, delay=0.25):
    """
    Xóa thư mục hoặc file một cách bền bỉ trên Windows:
    - Giải phóng Garbage Collector của Python
    - Xử lý quyền Read-only
    - Thử lại nhiều lần (chờ Google Drive Sync / File Explorer nhả file lock)
    - Fallback sang PowerShell / CMD Force Remove nếu cần
    """
    if not target_path or not os.path.exists(target_path):
        return True, None

    target_path = os.path.abspath(target_path)
    gc.collect()

    last_error = None
    for attempt in range(retries):
        try:
            if os.path.isdir(target_path):
                # Xóa sạch các thuộc tính read-only của file con trước
                for root, dirs, files in os.walk(target_path):
                    for f in files:
                        try:
                            os.chmod(os.path.join(root, f), stat.S_IWRITE)
                        except Exception:
                            pass
                shutil.rmtree(target_path, onerror=remove_readonly)
            else:
                try:
                    os.chmod(target_path, stat.S_IWRITE)
                except Exception:
                    pass
                os.remove(target_path)
            return True, None
        except Exception as e:
            last_error = e
            gc.collect()
            time.sleep(delay * (attempt + 1))

    # Fallback 1: Dùng PowerShell Force Remove
    try:
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", f"Remove-Item -LiteralPath '{target_path}' -Recurse -Force -ErrorAction SilentlyContinue"]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=6)
        if not os.path.exists(target_path):
            return True, None
    except Exception as e:
        last_error = e

    # Fallback 2: Dùng CMD rd / del
    try:
        if os.path.isdir(target_path):
            subprocess.run(f'cmd /c rd /s /q "{target_path}"', shell=True, timeout=5)
        else:
            subprocess.run(f'cmd /c del /f /q "{target_path}"', shell=True, timeout=5)
        if not os.path.exists(target_path):
            return True, None
    except Exception as e:
        last_error = e

    if os.path.exists(target_path):
        return False, str(last_error)
    return True, None

def is_folder_empty_or_only_meta(folder_path):
    """Kiểm tra xem thư mục có rỗng hoặc chỉ chứa file rác hệ thống (desktop.ini, Thumbs.db) không"""
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return True
    try:
        items = os.listdir(folder_path)
        valid_items = [f for f in items if f.lower() not in ['desktop.ini', 'thumbs.db', '.ds_store']]
        if not valid_items:
            return True
        for item in valid_items:
            sub = os.path.join(folder_path, item)
            if os.path.isfile(sub):
                return False
            elif os.path.isdir(sub):
                if not is_folder_empty_or_only_meta(sub):
                    return False
        return True
    except Exception:
        return False

def cleanup_empty_parent_folder(parent_dir, stop_at_dir=None):
    """Dọn dẹp thư mục cha nếu chỉ chứa file metadata hệ thống hoặc rỗng"""
    if not parent_dir or not os.path.exists(parent_dir):
        return
    try:
        if stop_at_dir and os.path.abspath(parent_dir) == os.path.abspath(stop_at_dir):
            return
        if is_folder_empty_or_only_meta(parent_dir):
            robust_remove(parent_dir)
    except Exception:
        pass

def delete_finished_result(item_path, title=None, channel=None, dest_path=None):
    """
    Xóa thư mục thành phẩm của video trong thư mục Output, đồng thời cập nhật history.json
    """
    errors = []
    attempted_paths = set()
    parent_dirs_to_check = set()
    resolved_dest = resolve_google_drive_path(dest_path) if dest_path else None
    
    # 1. Xóa thư mục/tệp theo item_path nếu tồn tại
    if item_path:
        norm_item_path = os.path.abspath(item_path.strip().strip('"').strip("'"))
        attempted_paths.add(norm_item_path)
        parent_dir = os.path.dirname(norm_item_path)
        if parent_dir:
            parent_dirs_to_check.add(parent_dir)
            
        if os.path.exists(norm_item_path):
            success, err = robust_remove(norm_item_path)
            if not success:
                errors.append(f"Không thể xóa thư mục {norm_item_path}: {err}")

    # 2. Nếu có dest_path và title/channel, kiểm tra thêm các đường dẫn biến thể
    if title:
        candidates = []
        raw_title = title.strip()
        san_title = sanitize_filename(title)
        
        # Bổ sung các biến thể tên (có hoặc không có .mp4 ở cuối)
        title_variants = {raw_title, san_title}
        for t in list(title_variants):
            if t.lower().endswith('.mp4'):
                title_variants.add(t[:-4].strip())
            title_variants.add(f"{t}mp4")

        # Tìm trong dest_path
        if resolved_dest and os.path.exists(resolved_dest):
            channel_variants = {channel, sanitize_filename(channel)} if channel else set()
            if not channel_variants:
                try:
                    for sub_c in os.listdir(resolved_dest):
                        sub_c_path = os.path.join(resolved_dest, sub_c)
                        if os.path.isdir(sub_c_path):
                            channel_variants.add(sub_c)
                except Exception:
                    pass
                    
            for c in channel_variants:
                chan_dir = os.path.join(resolved_dest, c)
                parent_dirs_to_check.add(chan_dir)
                for t in title_variants:
                    candidates.append(os.path.join(chan_dir, t))
            for t in title_variants:
                candidates.append(os.path.join(resolved_dest, t))
                
        for cand in candidates:
            cand_abs = os.path.abspath(cand)
            if cand_abs not in attempted_paths:
                attempted_paths.add(cand_abs)
                if os.path.exists(cand_abs):
                    cand_parent = os.path.dirname(cand_abs)
                    if cand_parent:
                        parent_dirs_to_check.add(cand_parent)
                    success, err = robust_remove(cand_abs)
                    if not success:
                        errors.append(f"Lỗi khi xóa đường dẫn {cand_abs}: {err}")

    # 3. Dọn dẹp các thư mục cha (kênh trong output) nếu đã rỗng
    for p_dir in parent_dirs_to_check:
        cleanup_empty_parent_folder(p_dir, stop_at_dir=resolved_dest)

    # 4. Cập nhật dữ liệu video trong history.json thành "previously_downloaded" (ghi nhận đã từng tải)
    try:
        history = load_history()
        keys_to_update = []
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for k, v in history.items():
            k_match = (title and (k == title or sanitize_filename(k) == sanitize_filename(title)))
            v_match = False
            if isinstance(v, dict):
                v_title = v.get("title", "")
                v_out = v.get("output_dir", "")
                v_folder = v.get("folder", "") or v.get("output_folder", "")
                if title and (v_title == title or sanitize_filename(v_title) == sanitize_filename(title)):
                    v_match = True
                elif item_path and (item_path in v_out or item_path in v_folder):
                    v_match = True
            if k_match or v_match:
                keys_to_update.append(k)

        for k in keys_to_update:
            if k in history and isinstance(history[k], dict):
                history[k]["status"] = "previously_downloaded"
                history[k]["is_deleted"] = True
                history[k]["deleted_at"] = now_str
            elif k in history:
                history[k] = {
                    "title": title or k,
                    "channel": channel or "",
                    "status": "previously_downloaded",
                    "is_deleted": True,
                    "deleted_at": now_str
                }

        # Nếu không có key nào khớp nhưng có title, ghi nhận mới với status previously_downloaded
        if not keys_to_update and title:
            new_k = f"{channel}/{title}" if channel else title
            history[new_k] = {
                "title": title,
                "channel": channel or "",
                "status": "previously_downloaded",
                "is_deleted": True,
                "deleted_at": now_str
            }
            keys_to_update.append(new_k)

        if keys_to_update:
            save_history(history)
    except Exception as e:
        errors.append(f"Lỗi cập nhật history.json: {e}")

    invalidate_drive_caches()
    return len(errors) == 0, errors

def delete_all_finished_results(dest_path):
    """
    Xóa toàn bộ nội dung thành phẩm trong thư mục đích và cập nhật history.json thành đã từng tải
    """
    resolved_dest = resolve_google_drive_path(dest_path)
    if not resolved_dest or not os.path.exists(resolved_dest):
        return False, ["Thư mục đích không tồn tại"]

    errors = []
    try:
        for item in os.listdir(resolved_dest):
            item_path = os.path.join(resolved_dest, item)
            success, err = robust_remove(item_path)
            if not success:
                errors.append(f"Không thể xóa {item}: {err}")
    except Exception as e:
        errors.append(f"Lỗi đọc thư mục đích: {e}")

    # Cập nhật toàn bộ lịch sử thành đã từng tải
    try:
        history = load_history()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for k, v in history.items():
            if isinstance(v, dict):
                v["status"] = "previously_downloaded"
                v["is_deleted"] = True
                v["deleted_at"] = now_str
        save_history(history)
    except Exception as e:
        errors.append(f"Lỗi reset history.json: {e}")

    invalidate_drive_caches()
    return len(errors) == 0, errors

def ensure_channel_folders(data=None):
    """
    Tự động tạo thư mục tên kênh tại cả Source (Input) và Destination (Output)
    ngay khi một kênh được thêm, chỉnh sửa hoặc khi lưu cấu hình.
    """
    if data is None:
        data = load_accounts_data()
        
    source_path = data.get("source_path", "")
    dest_path = data.get("dest_path", "")
    
    resolved_source = resolve_google_drive_path(source_path) if source_path else ""
    resolved_dest = resolve_google_drive_path(dest_path) if dest_path else ""
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if not resolved_source:
        resolved_source = os.path.join(base_dir, "video")
    if not resolved_dest:
        resolved_dest = os.path.join(base_dir, "output_product")
        
    created_info = []
    channels = data.get("youtube_channels", [])
    
    for chan in channels:
        raw_name = chan.get("folder_name") or chan.get("name") or ""
        folder_name = sanitize_filename(raw_name)
        if not folder_name:
            continue
            
        # 1. Tạo thư mục tại Source (Input)
        try:
            if resolved_source:
                os.makedirs(resolved_source, exist_ok=True)
                src_chan_dir = os.path.join(resolved_source, folder_name)
                if not os.path.exists(src_chan_dir):
                    os.makedirs(src_chan_dir, exist_ok=True)
                    created_info.append(f"Source: {src_chan_dir}")
        except Exception as e:
            print(f"Lỗi tạo thư mục source cho kênh {folder_name}: {e}")
            
        # 2. Tạo thư mục tại Destination (Output)
        try:
            if resolved_dest:
                os.makedirs(resolved_dest, exist_ok=True)
                dest_chan_dir = os.path.join(resolved_dest, folder_name)
                if not os.path.exists(dest_chan_dir):
                    os.makedirs(dest_chan_dir, exist_ok=True)
                    created_info.append(f"Output: {dest_chan_dir}")
        except Exception as e:
            print(f"Lỗi tạo thư mục dest cho kênh {folder_name}: {e}")
            
    return created_info

def load_accounts_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    default_source = os.path.join(base_dir, "video")
    default_dest = os.path.join(base_dir, "output_product")
    
    data = None
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
            
    if not data:
        data = {
            "source_path": default_source,
            "dest_path": default_dest,
            "youtube_channels": [],
            "tiktok_accounts": []
        }
        try:
            with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
            
    if not data.get("source_path"):
        data["source_path"] = default_source
    if not data.get("dest_path"):
        data["dest_path"] = default_dest
    if "youtube_channels" not in data:
        data["youtube_channels"] = []
    if "tiktok_accounts" not in data:
        data["tiktok_accounts"] = []
        
    for acc in data.get("tiktok_accounts", []):
        if "target_history" not in acc:
            target = acc.get("target_channel", "")
            acc["target_history"] = [target] if target else []
        elif acc.get("target_channel") and acc.get("target_channel") not in acc["target_history"]:
            acc["target_history"].append(acc.get("target_channel"))
        if "posted_clips" not in acc:
            acc["posted_clips"] = {}
        if "adspower_id" not in acc:
            acc["adspower_id"] = ""
        if "adspower_serial" not in acc:
            acc["adspower_serial"] = ""
        
    return data


def save_accounts_data(data):
    try:
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # Tự động tạo thư mục Source & Output cho tất cả các kênh ngay lặp tức
        ensure_channel_folders(data)
        invalidate_drive_caches()
        return True
    except Exception as e:
        print(f"Error saving accounts: {e}")
        return False

def sync_tiktok_accounts_with_adspower():
    """
    Đồng bộ dữ liệu tài khoản TikTok với AdsPower Local API:
    - Bổ sung group_name, ip, country, created_date, adspower_serial, adspower_id, adspower_name
    - Bỏ các trường cũ không cần thiết như password, mail_confirm, original_ip, build_up_ip
    - Tự động nạp các profile mới xuất hiện từ AdsPower (kể cả profile được chia sẻ từ người khác)
    """
    from src.services.adspower_service import get_adspower_profiles
    ads_res = get_adspower_profiles(fetch_all=True)
    if not ads_res.get("success"):
        return {"success": False, "error": ads_res.get("error", "Không thể lấy danh sách profiles từ AdsPower Local API")}
        
    ads_profiles = ads_res.get("profiles", [])
    data = load_accounts_data()
    tiktok_accs = data.get("tiktok_accounts", [])
    
    # Map AdsPower profiles by user_id, serial_number, and name
    ads_by_id = {p["user_id"]: p for p in ads_profiles if p.get("user_id")}
    ads_by_serial = {str(p["serial_number"]): p for p in ads_profiles if p.get("serial_number")}
    ads_by_name = {p["name"].lower().replace("\n", " ").strip(): p for p in ads_profiles if p.get("name")}
    
    updated_accs = []
    matched_adspower_ids = set()
    
    for acc in tiktok_accs:
        u_id = acc.get("adspower_id", "")
        s_num = str(acc.get("adspower_serial", ""))
        a_name = acc.get("account_name", "").lower().strip()
        
        matched_p = ads_by_id.get(u_id) or ads_by_serial.get(s_num) or ads_by_name.get(a_name)
        
        new_acc = {
            "account_name": acc.get("account_name", ""),
            "adspower_id": acc.get("adspower_id", ""),
            "adspower_serial": acc.get("adspower_serial", ""),
            "adspower_name": acc.get("adspower_name", ""),
            "group_name": acc.get("group_name", "Default"),
            "ip": acc.get("ip", acc.get("build_up_ip", acc.get("original_ip", ""))),
            "country": acc.get("country", ""),
            "created_date": acc.get("created_date", ""),
            "target_channel": acc.get("target_channel", ""),
            "target_history": acc.get("target_history", []),
            "content": acc.get("content", ""),
            "hashtag": acc.get("hashtag", ""),
            "note": acc.get("note", ""),
            "mail": acc.get("mail", ""),
            "posted_clips": acc.get("posted_clips", {})
        }
        
        if matched_p:
            new_acc["adspower_id"] = matched_p["user_id"]
            new_acc["adspower_serial"] = matched_p["serial_number"]
            new_acc["adspower_name"] = matched_p["name"]
            new_acc["group_name"] = matched_p["group_name"]
            new_acc["ip"] = matched_p["ip"] or new_acc["ip"]
            new_acc["country"] = matched_p["country"] or new_acc["country"]
            if matched_p.get("created_date"):
                new_acc["created_date"] = matched_p["created_date"]
            matched_adspower_ids.add(matched_p["user_id"])
            
        updated_accs.append(new_acc)
        
    # Tự động nạp thêm các profile AdsPower chưa có trong danh sách (kể cả profile được share)
    for p in ads_profiles:
        if p["user_id"] not in matched_adspower_ids:
            clean_acc_name = p["name"]
            new_acc = {
                "account_name": clean_acc_name,
                "adspower_id": p["user_id"],
                "adspower_serial": p["serial_number"],
                "adspower_name": p["name"],
                "group_name": p["group_name"],
                "ip": p["ip"],
                "country": p["country"],
                "created_date": p["created_date"],
                "target_channel": "",
                "target_history": [],
                "content": "",
                "hashtag": "#fyp #viral #trending",
                "note": p.get("remark", ""),
                "mail": "",
                "posted_clips": {}
            }
            updated_accs.append(new_acc)
            matched_adspower_ids.add(p["user_id"])
            
    data["tiktok_accounts"] = updated_accs
    save_accounts_data(data)
    return {
        "success": True,
        "total_accounts": len(updated_accs),
        "synced_adspower_count": len(ads_profiles)
    }


def get_publishing_matrix(dest_path=None):
    """
    Tổng hợp ma trận liên kết giữa TikTok Accounts, Kênh YouTube mục tiêu, các video clips thành phẩm và trạng thái đăng.
    Hỗ trợ ánh xạ 2 chiều giữa Tên Kênh (name) và Tên Thư Mục (folder_name) trên ổ đĩa.
    """
    accounts_data = load_accounts_data()
    if not dest_path:
        dest_path = accounts_data.get("dest_path", os.path.join(os.path.dirname(os.path.abspath(__file__)), "output_product"))
    
    finished_data = scan_finished_results(dest_path)
    all_finished = finished_data.get("results", [])
    
    # Tạo mapping 2 chiều giữa name <-> folder_name của youtube_channels
    channel_name_to_folder = {}
    channel_folder_to_name = {}
    for chan in accounts_data.get("youtube_channels", []):
        c_n = str(chan.get("name", "")).strip()
        c_f = str(chan.get("folder_name", "") or c_n).strip()
        if c_n:
            channel_name_to_folder[c_n] = c_f
            channel_name_to_folder[c_n.lower()] = c_f
            channel_name_to_folder[sanitize_filename(c_n).lower()] = c_f
        if c_f:
            channel_folder_to_name[c_f] = c_n
            channel_folder_to_name[c_f.lower()] = c_n
            channel_folder_to_name[sanitize_filename(c_f).lower()] = c_n

    # Tạo map tra cứu nhanh theo channel -> list of clips
    channel_clips_map = {}
    for clip in all_finished:
        cname = clip.get("folder_name", "")
        if cname not in channel_clips_map:
            channel_clips_map[cname] = []
        channel_clips_map[cname].append(clip)
        
    accounts_matrix = []
    for acc in accounts_data.get("tiktok_accounts", []):
        acc_name = acc.get("account_name", "")
        target_channel = acc.get("target_channel", "")
        target_history = acc.get("target_history", [])
        if not target_history and target_channel:
            target_history = [target_channel]
        elif target_channel and target_channel not in target_history:
            target_history.append(target_channel)
            
        posted_clips = acc.get("posted_clips", {})
        
        # Tập hợp tất cả các kênh liên quan đến tài khoản này
        all_relevant_channels = []
        if target_channel:
            all_relevant_channels.append(target_channel)
        for h in target_history:
            if h and h not in all_relevant_channels:
                all_relevant_channels.append(h)
                
        # Candidate names for current target
        current_target_aliases = set()
        if target_channel:
            current_target_aliases.add(target_channel.lower())
            current_target_aliases.add(sanitize_filename(target_channel).lower())
            f_tar = channel_name_to_folder.get(target_channel.lower()) or channel_name_to_folder.get(sanitize_filename(target_channel).lower())
            if f_tar:
                current_target_aliases.add(f_tar.lower())
                current_target_aliases.add(sanitize_filename(f_tar).lower())
            n_tar = channel_folder_to_name.get(target_channel.lower()) or channel_folder_to_name.get(sanitize_filename(target_channel).lower())
            if n_tar:
                current_target_aliases.add(n_tar.lower())
                current_target_aliases.add(sanitize_filename(n_tar).lower())

        clips_feed = []
        seen_keys = set()
        
        # 1. Thêm các clip từ kênh mục tiêu hiện tại và các kênh trong lịch sử có sẵn trên ổ đĩa
        for ch in all_relevant_channels:
            if not ch:
                continue
            possible_keys = [ch, sanitize_filename(ch), ch.lower(), sanitize_filename(ch).lower()]
            f_name = channel_name_to_folder.get(ch.lower()) or channel_name_to_folder.get(sanitize_filename(ch).lower())
            if f_name:
                possible_keys.extend([f_name, sanitize_filename(f_name), f_name.lower(), sanitize_filename(f_name).lower()])
            n_name = channel_folder_to_name.get(ch.lower()) or channel_folder_to_name.get(sanitize_filename(ch).lower())
            if n_name:
                possible_keys.extend([n_name, sanitize_filename(n_name), n_name.lower(), sanitize_filename(n_name).lower()])

            matched_clips = []
            for pk in possible_keys:
                if pk in channel_clips_map:
                    matched_clips = channel_clips_map[pk]
                    break
            
            if not matched_clips:
                for k, v in channel_clips_map.items():
                    if any(k.lower() == pk.lower() or sanitize_filename(k).lower() == sanitize_filename(pk).lower() for pk in possible_keys):
                        matched_clips = v
                        break
                        
            for c in matched_clips:
                c_channel = c.get('folder_name', ch)
                clip_key = f"{c_channel}/{c.get('title')}"
                if clip_key in seen_keys:
                    continue
                seen_keys.add(clip_key)
                
                # Check is_current_target
                is_cur_target = False
                if c_channel.lower() in current_target_aliases or sanitize_filename(c_channel).lower() in current_target_aliases or ch.lower() in current_target_aliases:
                    is_cur_target = True

                clip_vid_id = c.get("video_id") or generate_video_id(c_channel, c.get("title"))

                # Kiểm tra trạng thái đã đăng cho CHÍNH TÀI KHOẢN NÀY (account_id + video_id)
                post_info = posted_clips.get(clip_key, {})
                if not post_info:
                    for pk, pv in posted_clips.items():
                        if (pv.get("video_id") and pv.get("video_id") == clip_vid_id) or \
                           sanitize_filename(pk).lower() == sanitize_filename(clip_key).lower() or \
                           (pv.get("title") == c.get("title") and sanitize_filename(pv.get("channel", "")).lower() == sanitize_filename(c_channel).lower()):
                            post_info = pv
                            break
                            
                is_posted = bool(post_info.get("posted", False))
                posted_at = post_info.get("posted_at", "")
                parts_status = post_info.get("parts_status", {})
                
                # Nạp thông tin chi tiết từng part
                parts_data = []
                clip_parts = c.get("parts", [])
                for idx, p in enumerate(clip_parts):
                    p_label = f"Part {idx + 1}"
                    p_stat = parts_status.get(p_label, {})
                    
                    if p_stat:
                        p_is_posted = bool(p_stat.get("posted", False))
                        p_posted_at = p_stat.get("posted_at", "")
                    elif is_posted and not parts_status:
                        p_is_posted = True
                        p_posted_at = posted_at
                    else:
                        p_is_posted = False
                        p_posted_at = ""
                    
                    parts_data.append({
                        "name": p.get("name"),
                        "label": p_label,
                        "part_index": idx + 1,
                        "file_path": p.get("file_path"),
                        "url": p.get("url"),
                        "posted": p_is_posted,
                        "posted_at": p_posted_at
                    })
                
                # QUY TẮC CỐT LÕI: Nếu clip có các part trên đĩa, clip CHỈ ĐƯỢC ĐÁNH DẤU ĐÃ ĐĂNG
                # khi và chỉ khi 100% TẤT CẢ các part đều đã đăng xong!
                if parts_data:
                    is_posted = all(p["posted"] for p in parts_data)
                
                clips_feed.append({
                    "video_id": clip_vid_id,
                    "key": clip_key,
                    "title": c.get("title"),
                    "channel": c_channel,
                    "is_current_target": is_cur_target,
                    "path": c.get("path"),
                    "parts": parts_data,
                    "parts_count": len(parts_data),
                    "has_full": c.get("has_full", False),
                    "posted": is_posted,
                    "posted_at": posted_at,
                    "mtime": c.get("mtime", 0),
                    "created_at": c.get("created_at", ""),
                    "on_disk": True
                })
                
        # 2. Thêm các clip cũ đã từng đăng trước đó nhưng hiện tại file trên đĩa đã bị xóa
        for pkey, pval in posted_clips.items():
            if pkey not in seen_keys and pval.get("posted"):
                seen_keys.add(pkey)
                pchannel = pval.get("channel", "")
                is_cur_target = False
                if pchannel.lower() in current_target_aliases or sanitize_filename(pchannel).lower() in current_target_aliases:
                    is_cur_target = True

                clips_feed.append({
                    "key": pkey,
                    "title": pval.get("title", os.path.basename(pkey)),
                    "channel": pchannel,
                    "is_current_target": is_cur_target,
                    "path": "",
                    "parts": [],
                    "parts_count": 0,
                    "has_full": False,
                    "posted": True,
                    "posted_at": pval.get("posted_at", ""),
                    "mtime": 0,
                    "created_at": pval.get("posted_at", ""),
                    "on_disk": False
                })
                
        # Sắp xếp clips CHÍNH XÁC:
        # 1. Ưu tiên kênh mục tiêu hiện tại lên trước (is_current_target True)
        # 2. Clip CHƯA đăng (posted False) lên trước clip ĐÃ đăng (posted True)
        # 3. Clip MỚI BIÊN TẬP NHẤT lên đầu theo mtime giảm dần (-mtime) để đảm bảo không đăng video cũ trước
        # 4. Tiêu đề
        clips_feed.sort(key=lambda x: (
            0 if x.get("is_current_target") else 1,
            1 if x.get("posted") else 0,
            -float(x.get("mtime") or 0),
            x.get("title", "")
        ))

        total_clips = len(clips_feed)
        posted_count = sum(1 for c in clips_feed if c["posted"])
        pending_count = total_clips - posted_count
        rate = round((posted_count / total_clips * 100)) if total_clips > 0 else 0
        
        # Tính thời gian biên tập gần nhất của các clip chưa đăng thuộc kênh mục tiêu
        unposted_mtimes = [float(c.get("mtime", 0) or 0) for c in clips_feed if not c.get("posted") and c.get("is_current_target") and c.get("on_disk")]
        max_unposted_mtime = max(unposted_mtimes) if unposted_mtimes else 0

        accounts_matrix.append({
            "account_name": acc_name,
            "password": acc.get("password", ""),
            "mail": acc.get("mail", ""),
            "original_ip": acc.get("original_ip", ""),
            "build_up_ip": acc.get("build_up_ip", ""),
            "adspower_id": acc.get("adspower_id", ""),
            "adspower_serial": acc.get("adspower_serial", ""),
            "target_channel": target_channel,
            "target_history": target_history,
            "hashtag": acc.get("hashtag", ""),
            "content": acc.get("content", ""),
            "note": acc.get("note", ""),
            "posted_clips": posted_clips,
            "clips": clips_feed,
            "max_unposted_mtime": max_unposted_mtime,
            "stats": {
                "total": total_clips,
                "posted": posted_count,
                "pending": pending_count,
                "completion_rate": rate
            }
        })

        
    return {
        "accounts": accounts_matrix,
        "youtube_channels": accounts_data.get("youtube_channels", []),
        "dest_path": dest_path
    }

def toggle_publishing_clip_status(account_name, clip_key, channel=None, title=None, posted=True, part_label=None, video_id=None):
    """
    Cập nhật trạng thái Đã đăng / Chưa đăng cho 1 clip hoặc 1 part cụ thể của tài khoản TikTok
    """
    # Tự động tái tạo clip_key nếu bị rỗng nhưng có channel và title
    if not clip_key and channel and title:
        clip_key = f"{channel}/{title}"

    if not clip_key:
        return False, "Thiếu clip_key hợp lệ"

    # Chuẩn hóa part_label: e.g. "part 1" -> "Part 1"
    if part_label:
        m_p = re.search(r'part[\s_\-]*(\d+)', str(part_label), re.I)
        if m_p:
            part_label = f"Part {m_p.group(1)}"

    accounts_data = load_accounts_data()
    found = False
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    
    for acc in accounts_data.get("tiktok_accounts", []):
        if acc.get("account_name") == account_name:
            found = True
            if "posted_clips" not in acc:
                acc["posted_clips"] = {}

            # Dọn dẹp key rỗng "" nếu vô tình tồn tại trong account này
            if "" in acc["posted_clips"]:
                bogus = acc["posted_clips"].pop("")
                b_chan = bogus.get("channel")
                b_title = bogus.get("title")
                if b_chan and b_title:
                    b_key = f"{b_chan}/{b_title}"
                    if b_key not in acc["posted_clips"]:
                        acc["posted_clips"][b_key] = bogus
                
            entry = acc["posted_clips"].get(clip_key, {})
            if not isinstance(entry, dict):
                entry = {"posted": bool(entry)}
                
            if "parts_status" not in entry:
                entry["parts_status"] = {}

            eff_channel = entry.get("channel") or channel or (clip_key.split("/", 1)[0] if "/" in clip_key else "")
            eff_title = entry.get("title") or title or (clip_key.split("/", 1)[1] if "/" in clip_key else clip_key)
            disk_parts = get_clip_disk_part_labels(eff_channel, eff_title)

            if part_label:
                # Cập nhật riêng cho part này
                entry["parts_status"][part_label] = {
                    "posted": posted,
                    "posted_at": now_str if posted else ""
                }
                # Kiểm tra nếu tất cả các part trên đĩa đã đăng đủ 100%
                if disk_parts:
                    all_posted = (len(disk_parts) > 0) and all(entry["parts_status"].get(p, {}).get("posted") for p in disk_parts)
                else:
                    all_posted = all(p.get("posted") for p in entry["parts_status"].values()) if entry["parts_status"] else posted

                entry["posted"] = all_posted
                if all_posted:
                    if not entry.get("posted_at"):
                        entry["posted_at"] = now_str
                else:
                    # Nếu chưa đăng đủ tất cả các part, clip tổng BẮT BUỘC là posted=False
                    entry["posted"] = False
            else:
                # Cập nhật cho toàn bộ clip
                entry["posted"] = posted
                entry["posted_at"] = now_str if posted else ""
                target_parts = disk_parts or list(entry.get("parts_status", {}).keys())
                for pk in target_parts:
                    p_entry = entry["parts_status"].setdefault(pk, {})
                    p_entry["posted"] = posted
                    p_entry["posted_at"] = now_str if posted else ""
                        
            entry["channel"] = eff_channel
            entry["title"] = eff_title
            entry["video_id"] = video_id or entry.get("video_id") or generate_video_id(entry["channel"], entry["title"])
            acc["posted_clips"][clip_key] = entry
            break
            
    if found:
        save_accounts_data(accounts_data)
        if posted:
            sync_publishing_history_with_queue()
        invalidate_drive_caches()
        return True, now_str if posted else ""
    return False, "Không tìm thấy tài khoản"

def sync_publishing_history_with_queue():
    """
    Quét và đối soát đồng bộ lịch sử đăng cho từng tài khoản TikTok độc lập:
    1. Chuẩn hóa video_id (ID unique duy nhất cho mỗi clip) cho tất cả các bản ghi.
    2. Tự động di trú và dọn dẹp bất kỳ key rỗng nào ("") về đúng key f"{channel}/{title}".
    3. Đảm bảo tính nhất quán giữa các part: nếu clip cha đã posted=True thì toàn bộ parts đều là đã đăng.
       Nếu tất cả các part đều posted=True thì clip cha tự động chuyển thành posted=True.
    4. TUYỆT ĐỐI KHÔNG ĐỒNG BỘ CHÉO GIỮA CÁC TÀI KHOẢN (Per-Account Isolation):
       Mỗi tài khoản có lịch sử đăng riêng biệt theo cặp (account_id + video_id).
    """
    accounts_data = load_accounts_data()
    dest_path = accounts_data.get("dest_path", os.path.join(os.path.dirname(os.path.abspath(__file__)), "output_product"))
    scan = scan_finished_results(dest_path)
    all_finished = scan.get("results", [])
    
    # Map tiêu đề / thư mục với danh sách part thực tế trên đĩa
    clip_disk_parts = {}
    for c in all_finished:
        c_chan = c.get("folder_name", "")
        c_title = c.get("title", "")
        k = f"{c_chan}/{c_title}"
        san_k = sanitize_filename(k).lower()
        san_t = sanitize_filename(c_title).lower()
        parts = [p.get("label") for p in c.get("parts", [])]
        clip_disk_parts[san_k] = parts
        clip_disk_parts[san_t] = parts

    changed = False
    synced_count = 0

    # Di trú key rỗng, chuẩn hóa video_id và multi-part cho từng tài khoản độc lập
    for acc in accounts_data.get("tiktok_accounts", []):
        posted_clips = acc.setdefault("posted_clips", {})
        
        # Tự động di trú key rỗng "" về key chuẩn channel/title
        if "" in posted_clips:
            bogus = posted_clips.pop("")
            b_chan = bogus.get("channel")
            b_title = bogus.get("title")
            if b_chan and b_title:
                b_key = f"{b_chan}/{b_title}"
                if b_key not in posted_clips:
                    posted_clips[b_key] = bogus
                else:
                    if isinstance(bogus, dict) and "parts_status" in bogus:
                        target_ps = posted_clips[b_key].setdefault("parts_status", {})
                        for pk, pv in bogus.get("parts_status", {}).items():
                            if pv.get("posted"):
                                target_ps[pk] = pv
                                posted_clips[b_key]["posted"] = True
            changed = True
            synced_count += 1

        for clip_key, info in list(posted_clips.items()):
            if not clip_key or not isinstance(info, dict):
                continue
            
            c_chan = info.get("channel") or (clip_key.split("/", 1)[0] if "/" in clip_key else "")
            c_title = info.get("title") or (clip_key.split("/", 1)[1] if "/" in clip_key else clip_key)
            
            # Gắn video_id unique nếu chưa có
            if not info.get("video_id"):
                info["video_id"] = generate_video_id(c_chan, c_title)
                changed = True

            is_clip_posted = bool(info.get("posted", False))
            parts_status = info.setdefault("parts_status", {})
            now_str = info.get("posted_at") or time.strftime("%Y-%m-%d %H:%M:%S")

            san_k = sanitize_filename(clip_key).lower()
            san_t = sanitize_filename(c_title).lower()
            disk_parts = clip_disk_parts.get(san_k) or clip_disk_parts.get(san_t) or []

            if disk_parts:
                # Clip có danh sách part trên đĩa:
                # Khởi tạo entry cho các disk_parts nếu chưa có (mặc định posted=False)
                for p_lbl in disk_parts:
                    if p_lbl not in parts_status:
                        parts_status[p_lbl] = {"posted": False, "posted_at": ""}
                        changed = True

                posted_parts_count = sum(1 for p_lbl in disk_parts if parts_status.get(p_lbl, {}).get("posted"))
                all_parts_posted = (len(disk_parts) > 0 and posted_parts_count == len(disk_parts))

                # TUYỆT ĐỐI KHÔNG tự tiện set tất cả disk_parts thành posted=True!
                # Chỉ khi toàn bộ 100% các part đã đăng thì info["posted"] mới là True
                if all_parts_posted:
                    if not is_clip_posted:
                        info["posted"] = True
                        info["posted_at"] = now_str
                        changed = True
                        synced_count += 1
                else:
                    # Nếu chưa đăng đủ 100% số part, clip tổng BẮT BUỘC posted = False!
                    if is_clip_posted:
                        info["posted"] = False
                        changed = True
                        synced_count += 1
            elif parts_status:
                # Không có file trên đĩa nhưng có lịch sử parts cũ
                if all(isinstance(p, dict) and p.get("posted") for p in parts_status.values()):
                    if not is_clip_posted:
                        info["posted"] = True
                        info["posted_at"] = now_str
                        changed = True
                        synced_count += 1
                else:
                    if is_clip_posted:
                        info["posted"] = False
                        changed = True
                        synced_count += 1

    if changed:
        save_accounts_data(accounts_data)
        invalidate_drive_caches()
    return synced_count


def change_account_target_channel(account_name, new_target_channel):
    """
    Thay đổi kênh YouTube mục tiêu cho tài khoản TikTok, tự động lưu kênh cũ vào target_history,
    và lập tức đồng bộ lịch sử để loại bỏ toàn bộ các clip cũ đã từng đăng của kênh mới.
    """
    accounts_data = load_accounts_data()
    found = False
    
    for acc in accounts_data.get("tiktok_accounts", []):
        if acc.get("account_name") == account_name:
            found = True
            old_target = acc.get("target_channel", "")
            if "target_history" not in acc:
                acc["target_history"] = []
                
            if old_target and old_target not in acc["target_history"]:
                acc["target_history"].append(old_target)
                
            acc["target_channel"] = new_target_channel
            if new_target_channel and new_target_channel not in acc["target_history"]:
                acc["target_history"].append(new_target_channel)
            break
            
    if found:
        save_accounts_data(accounts_data)
        sync_publishing_history_with_queue()
        invalidate_drive_caches()
        return True, None
    return False, "Không tìm thấy tài khoản"

def batch_toggle_publishing_clips(account_name, clip_keys, posted=True):
    """
    Đánh dấu đã đăng / chưa đăng hàng loạt cho nhiều clips của 1 tài khoản
    """
    accounts_data = load_accounts_data()
    found = False
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    
    for acc in accounts_data.get("tiktok_accounts", []):
        if acc.get("account_name") == account_name:
            found = True
            if "posted_clips" not in acc:
                acc["posted_clips"] = {}
            for k in clip_keys:
                acc["posted_clips"][k] = {
                    "posted": posted,
                    "posted_at": now_str if posted else "",
                    "channel": os.path.dirname(k),
                    "title": os.path.basename(k)
                }
            break
            
    if found:
        save_accounts_data(accounts_data)
        return True, None
    return False, "Không tìm thấy tài khoản"

def get_account_daily_posted_count(account_dict_or_name, target_date=None):
    """
    Đếm số lượng clip/part mà tài khoản TikTok đã đăng trong ngày target_date (mặc định hôm nay YYYY-MM-DD)
    """
    if not target_date:
        target_date = time.strftime("%Y-%m-%d")
        
    acc = None
    if isinstance(account_dict_or_name, dict):
        if "posted_clips" in account_dict_or_name:
            acc = account_dict_or_name
        else:
            acc_name = account_dict_or_name.get("account_name", "")
            if acc_name:
                accounts_data = load_accounts_data()
                for a in accounts_data.get("tiktok_accounts", []):
                    if a.get("account_name", "").lower() == acc_name.lower():
                        acc = a
                        break
    elif isinstance(account_dict_or_name, str):
        accounts_data = load_accounts_data()
        for a in accounts_data.get("tiktok_accounts", []):
            if a.get("account_name", "").lower() == account_dict_or_name.lower():
                acc = a
                break
                
    if not acc:
        return 0
        
    posted_clips = acc.get("posted_clips", {})
    daily_count = 0
    
    for clip_key, clip_data in posted_clips.items():
        if not clip_key or not isinstance(clip_data, dict):
            continue
        parts_status = clip_data.get("parts_status", {})
        if parts_status:
            for p_label, p_data in parts_status.items():
                if isinstance(p_data, dict) and p_data.get("posted"):
                    p_at = str(p_data.get("posted_at", "")).strip()
                    if p_at.startswith(target_date):
                        daily_count += 1
        else:
            if clip_data.get("posted"):
                c_at = str(clip_data.get("posted_at", "")).strip()
                if c_at.startswith(target_date):
                    daily_count += 1
                    
    return daily_count

def get_pending_publishing_queue(account_name=None, channel_name=None, only_current_target=True, check_daily_limit=True):
    """
    Lấy danh sách các clip/part đang chờ xuất bản (posted == False) trên ổ đĩa.
    Hỗ trợ lọc theo 1 tài khoản hoặc danh sách nhiều tài khoản chọn lọc.
    Áp dụng giới hạn tối đa 3 clip/ngày/account theo quy tắc nuôi kênh an toàn.
    Được chuẩn hóa cho n8n workflow và automated cron triggers.
    """
    matrix_data = get_publishing_matrix()
    settings = load_settings()
    max_daily_posts = int(settings.get("tiktok_upload", {}).get("max_daily_posts_per_account", 3))
    
    pending_queue = []
    today_str = time.strftime("%Y-%m-%d")
    
    # Chuẩn hóa bộ lọc tài khoản (hỗ trợ single account, list, hoặc chuỗi 'acc1,acc2')
    allowed_accounts = None
    if account_name:
        if isinstance(account_name, (list, set, tuple)):
            allowed_accounts = {str(a).strip().lower() for a in account_name if str(a).strip()}
        elif isinstance(account_name, str):
            allowed_accounts = {str(a).strip().lower() for a in account_name.split(",") if str(a).strip()}
    
    raw_accounts = matrix_data.get("accounts", [])
    # Nếu không giới hạn tài khoản cụ thể, sắp xếp tài khoản có clip MỚI BIÊN TẬP NHẤT lên đầu để Auto-Pilot ưu tiên video vừa render hôm nay
    if not allowed_accounts:
        accounts_to_process = sorted(raw_accounts, key=lambda a: -float(a.get("max_unposted_mtime") or 0))
    else:
        accounts_to_process = raw_accounts

    for acc in accounts_to_process:
        curr_acc_name = acc.get("account_name", "")
        if allowed_accounts and curr_acc_name.lower() not in allowed_accounts:
            continue
            
        # Kiểm tra giới hạn 3 clip / ngày của tài khoản
        if check_daily_limit and max_daily_posts > 0:
            today_posted = get_account_daily_posted_count(curr_acc_name, today_str)
            if today_posted >= max_daily_posts:
                continue
            
        target_channel = acc.get("target_channel", "")
        
        for clip in acc.get("clips", []):
            if not clip.get("on_disk"):
                continue
                
            clip_channel = clip.get("channel", "")
            if channel_name and sanitize_filename(clip_channel) != sanitize_filename(channel_name):
                continue
                
            if only_current_target and target_channel and sanitize_filename(clip_channel) != sanitize_filename(target_channel):
                continue
                
            clip_vid = clip.get("video_id") or generate_video_id(clip_channel, clip.get("title", ""))
            parts = clip.get("parts", [])
            if parts:
                unposted_parts = [p for p in parts if not p.get("posted")]
                if not unposted_parts:
                    continue  # Bỏ qua nếu toàn bộ part đã đăng đủ
                for p in unposted_parts:
                    pending_queue.append({
                        "account_name": curr_acc_name,
                        "channel": clip_channel,
                        "title": clip.get("title", ""),
                        "video_id": clip_vid,
                        "part_id": p.get("part_id") or f"{clip_vid}_{p.get('label', '')}",
                        "clip_key": clip.get("key", ""),
                        "part_label": p.get("label", ""),
                        "part_name": p.get("name", ""),
                        "video_file": p.get("file_path", ""),
                        "hashtag": acc.get("hashtag", ""),
                        "target_ip": acc.get("build_up_ip") or acc.get("original_ip", ""),
                        "adspower_id": acc.get("adspower_id") or acc.get("adspower_serial") or curr_acc_name,
                        "parent_folder": clip.get("path", ""),
                        "mtime": clip.get("mtime", 0),
                        "created_at": clip.get("created_at", "")
                    })
            else:
                if clip.get("posted"):
                    continue
                    v_path = clip.get("path", "")
                    video_file = ""
                    if v_path and os.path.isdir(v_path):
                        mp4s = [f for f in os.listdir(v_path) if f.endswith('.mp4')]
                        if mp4s:
                            video_file = os.path.join(v_path, mp4s[0])
                    elif v_path and os.path.isfile(v_path):
                        video_file = v_path
                        
                    pending_queue.append({
                        "account_name": curr_acc_name,
                        "channel": clip_channel,
                        "title": clip.get("title", ""),
                        "video_id": clip_vid,
                        "part_id": f"{clip_vid}_full",
                        "clip_key": clip.get("key", ""),
                        "part_label": "",
                        "part_name": "",
                        "video_file": video_file,
                        "hashtag": acc.get("hashtag", ""),
                        "target_ip": acc.get("build_up_ip") or acc.get("original_ip", ""),
                        "adspower_id": acc.get("adspower_id") or acc.get("adspower_serial") or curr_acc_name,
                        "parent_folder": clip.get("path", ""),
                        "mtime": clip.get("mtime", 0),
                        "created_at": clip.get("created_at", "")
                    })
                    
    return pending_queue


