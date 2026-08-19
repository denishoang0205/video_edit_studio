import os
import sys
import json
import re
import shutil
import gc
import stat
import time
import subprocess

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

# Database or history tracking
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.json")

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
    return url_or_path

def scan_source_directory(source_path, dest_path=None):
    """
    Quét thư mục nguồn (Local Path hoặc Google Drive Synced Folder)
    Phân tích cấu trúc thư mục phân cấp:
    Thư mục gốc -> Thư mục Kênh (vd: SoyPato) -> Các video con
    """
    resolved_source = resolve_google_drive_path(source_path)
    resolved_dest = resolve_google_drive_path(dest_path)

    # 1. Fallback nếu thư mục nguồn không tồn tại
    if not resolved_source or not os.path.exists(resolved_source):
        default_candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "video"),
            r"c:\Users\bao huy\Documents\Tiktok builder"
        ]
        for cand in default_candidates:
            if os.path.exists(cand):
                resolved_source = cand
                break
        if not resolved_source or not os.path.exists(resolved_source):
            resolved_source = os.path.join(os.path.dirname(os.path.abspath(__file__)), "video")
            os.makedirs(resolved_source, exist_ok=True)

    # 2. Fallback nếu thư mục đích không tồn tại
    if not resolved_dest or not os.path.exists(resolved_dest):
        resolved_dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Tiktok_Builder_Output")
        os.makedirs(resolved_dest, exist_ok=True)

    history = load_history()
    result_folders = []

    # Duyệt các folder con trong resolved_source
    try:
        entries = sorted(os.listdir(resolved_source))
    except Exception as e:
        return {"error": f"Không thể đọc thư mục nguồn: {str(e)}"}

    for entry in entries:
        full_entry_path = os.path.join(resolved_source, entry)
        if not os.path.isdir(full_entry_path) or entry.startswith('.'):
            continue

        folder_data = {
            "name": entry,
            "path": full_entry_path,
            "videos": []
        }

        # Duyệt các video trong folder này
        try:
            sub_items = sorted(os.listdir(full_entry_path))
            for sub in sub_items:
                sub_path = os.path.join(full_entry_path, sub)
                
                # Trường hợp 1: Sub folder chứa video (như cấu trúc TikTok Builder: SoyPato / Tên Video / edited_full.mp4 hoặc raw.mp4)
                if os.path.isdir(sub_path):
                    video_title = sub
                    sub_files = os.listdir(sub_path)
                    
                    # 1. Kiểm tra xem folder đã được xuất ở thư mục đích chưa (Quét 2 chiều cả raw và sanitized)
                    dest_has_edited = False
                    if resolved_dest:
                        dirs_to_check = [
                            os.path.join(resolved_dest, entry, video_title),
                            os.path.join(resolved_dest, sanitize_filename(entry), sanitize_filename(video_title)),
                            os.path.join(resolved_dest, sanitize_filename(entry), video_title),
                            os.path.join(resolved_dest, entry, sanitize_filename(video_title))
                        ]
                        for dest_video_dir in dirs_to_check:
                            if os.path.exists(dest_video_dir):
                                dest_files = os.listdir(dest_video_dir)
                                if any(f.endswith('.mp4') and (' - part ' in f or f.startswith('edited_')) for f in dest_files):
                                    dest_has_edited = True
                                    break
                    
                    # 2. Kiểm tra cục bộ trong folder nguồn
                    local_has_edited = any(f.startswith("part_") or f.startswith("edited_") or ' - part ' in f for f in sub_files)
                    
                    # Tìm file raw
                    video_file_path = None
                    for f in sub_files:
                        if f.endswith(('.mp4', '.mkv', '.mov', '.avi')) and not f.startswith(('part_', 'edited_', 'title_banner')):
                            if ' - part ' not in f:
                                video_file_path = os.path.join(sub_path, f)
                                break
                    
                    # Nếu không có file raw, tìm bất kỳ file video nào
                    if not video_file_path:
                        for f in sub_files:
                            if f.endswith(('.mp4', '.mkv', '.mov', '.avi')):
                                video_file_path = os.path.join(sub_path, f)
                                break
                    
                    # Nếu thư mục rỗng hoàn toàn không chứa file video nào, bỏ qua
                    if not video_file_path:
                        continue
                    
                    # Logic xác định trạng thái Đã Edit:
                    # Nếu có resolved_dest -> dựa vào sự tồn tại của file thành phẩm ở thư mục đích
                    # Nếu không có resolved_dest -> dùng lịch sử & local check
                    if resolved_dest:
                        is_edited = dest_has_edited
                    else:
                        is_edited = local_has_edited or (sub in history) or (sub_path in history)
                        
                    folder_data["videos"].append({
                        "title": video_title,
                        "path": video_file_path,
                        "dir_path": sub_path,
                        "edited": is_edited
                    })
                    
                # Trường hợp 2: File video trực tiếp
                elif sub.lower().endswith(('.mp4', '.mkv', '.mov', '.avi', '.webm')):
                    video_title = os.path.splitext(sub)[0]
                    
                    # Kiểm tra xem folder đã được xuất ở thư mục đích chưa (Quét 2 chiều cả raw và sanitized)
                    dest_has_edited = False
                    if resolved_dest:
                        dirs_to_check = [
                            os.path.join(resolved_dest, entry, video_title),
                            os.path.join(resolved_dest, sanitize_filename(entry), sanitize_filename(video_title)),
                            os.path.join(resolved_dest, sanitize_filename(entry), video_title),
                            os.path.join(resolved_dest, entry, sanitize_filename(video_title))
                        ]
                        for dest_video_dir in dirs_to_check:
                            if os.path.exists(dest_video_dir):
                                dest_files = os.listdir(dest_video_dir)
                                if any(f.endswith('.mp4') and (' - part ' in f or f.startswith('edited_')) for f in dest_files):
                                    dest_has_edited = True
                                    break

                    if resolved_dest:
                        is_edited = dest_has_edited
                    else:
                        is_edited = (video_title in history) or (sub_path in history)
                        
                    folder_data["videos"].append({
                        "title": video_title,
                        "path": sub_path,
                        "dir_path": full_entry_path,
                        "edited": is_edited
                    })

        except Exception as err:
            print(f"Lỗi đọc subfolder {entry}: {err}")

        if folder_data["videos"]:
            result_folders.append(folder_data)

    return {"folders": result_folders, "source_path": source_path}

def scan_finished_results(dest_path):
    """Quét các video thành phẩm đã xuất trong thư mục đích"""
    resolved_dest = resolve_google_drive_path(dest_path)
    if not resolved_dest or not os.path.exists(resolved_dest):
        return {"results": []}

    results = []
    try:
        # Duyệt thư mục đích (Tiktok_Builder_Output hoặc Documents/Tiktok builder)
        for root, dirs, files in os.walk(resolved_dest):
            mp4_files = [f for f in files if f.endswith('.mp4')]
            parts = [f for f in mp4_files if ' - part ' in f]
            full_vid = [f for f in mp4_files if f.startswith('edited_')]

            if parts or full_vid:
                folder_name = os.path.basename(os.path.dirname(root)) or os.path.basename(root)
                video_title = os.path.basename(root)
                
                parts_list = []
                # Sắp xếp theo số thứ tự part ở cuối tên file
                def get_part_num(filename):
                    match = re.search(r'- part (\d+)\.mp4$', filename)
                    return int(match.group(1)) if match else 0

                for p in sorted(parts, key=get_part_num):
                    parts_list.append({
                        "name": p,
                        "file_path": os.path.join(root, p),
                        "url": f"/video_stream?path={os.path.join(root, p)}"
                    })

                results.append({
                    "title": video_title,
                    "folder_name": folder_name,
                    "path": root,
                    "parts": parts_list,
                    "has_full": len(full_vid) > 0
                })
    except Exception as e:
        print(f"Lỗi quét output: {e}")

    return {"results": results}

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

    # 4. Xóa dữ liệu video tương ứng trong history.json
    try:
        history = load_history()
        keys_to_remove = []
        for k, v in history.items():
            k_match = (title and (k == title or sanitize_filename(k) == sanitize_filename(title)))
            v_match = False
            if isinstance(v, dict):
                v_title = v.get("title", "")
                v_out = v.get("output_dir", "")
                v_folder = v.get("folder", "")
                if title and (v_title == title or sanitize_filename(v_title) == sanitize_filename(title)):
                    v_match = True
                elif item_path and (item_path in v_out or item_path in v_folder):
                    v_match = True
            if k_match or v_match:
                keys_to_remove.append(k)

        for k in keys_to_remove:
            if k in history:
                del history[k]

        if keys_to_remove:
            save_history(history)
    except Exception as e:
        errors.append(f"Lỗi cập nhật history.json: {e}")

    return len(errors) == 0, errors

def delete_all_finished_results(dest_path):
    """
    Xóa toàn bộ nội dung thành phẩm trong thư mục đích và làm sạch history.json
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

    # Xóa sạch lịch sử render
    try:
        save_history({})
    except Exception as e:
        errors.append(f"Lỗi reset history.json: {e}")

    return len(errors) == 0, errors

ACCOUNTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.json")

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
        resolved_dest = os.path.join(base_dir, "Tiktok_Builder_Output")
        
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
    default_dest = os.path.join(base_dir, "Tiktok_Builder_Output")
    
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
        
    return data

def save_accounts_data(data):
    try:
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # Tự động tạo thư mục Source & Output cho tất cả các kênh ngay lặp tức
        ensure_channel_folders(data)
        return True
    except Exception as e:
        print(f"Error saving accounts: {e}")
        return False

def get_publishing_matrix(dest_path=None):
    """
    Tổng hợp ma trận liên kết giữa TikTok Accounts, Kênh YouTube mục tiêu, các video clips thành phẩm và trạng thái đăng
    """
    accounts_data = load_accounts_data()
    if not dest_path:
        dest_path = accounts_data.get("dest_path", os.path.join(os.path.dirname(os.path.abspath(__file__)), "Tiktok_Builder_Output"))
    
    finished_data = scan_finished_results(dest_path)
    all_finished = finished_data.get("results", [])
    
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
                
        clips_feed = []
        seen_keys = set()
        
        # 1. Thêm các clip từ kênh mục tiêu hiện tại và các kênh trong lịch sử có sẵn trên ổ đĩa
        for ch in all_relevant_channels:
            matched_clips = channel_clips_map.get(ch, [])
            if not matched_clips:
                for k, v in channel_clips_map.items():
                    if sanitize_filename(k) == sanitize_filename(ch):
                        matched_clips = v
                        break
                        
            for c in matched_clips:
                c_channel = c.get('folder_name', ch)
                clip_key = f"{c_channel}/{c.get('title')}"
                if clip_key in seen_keys:
                    continue
                seen_keys.add(clip_key)
                
                # Kiểm tra trạng thái đã đăng
                post_info = posted_clips.get(clip_key, {})
                if not post_info:
                    for pk, pv in posted_clips.items():
                        if sanitize_filename(pk) == sanitize_filename(clip_key) or (pv.get("title") == c.get("title") and sanitize_filename(pv.get("channel", "")) == sanitize_filename(c_channel)):
                            post_info = pv
                            break
                            
                is_posted = bool(post_info.get("posted", False))
                posted_at = post_info.get("posted_at", "")
                
                clips_feed.append({
                    "key": clip_key,
                    "title": c.get("title"),
                    "channel": c_channel,
                    "is_current_target": (sanitize_filename(c_channel) == sanitize_filename(target_channel)),
                    "path": c.get("path"),
                    "parts": c.get("parts", []),
                    "parts_count": len(c.get("parts", [])),
                    "has_full": c.get("has_full", False),
                    "posted": is_posted,
                    "posted_at": posted_at,
                    "on_disk": True
                })
                
        # 2. Thêm các clip cũ đã từng đăng trước đó nhưng hiện tại file trên đĩa đã bị xóa
        for pkey, pval in posted_clips.items():
            if pkey not in seen_keys and pval.get("posted"):
                seen_keys.add(pkey)
                pchannel = pval.get("channel", "")
                clips_feed.append({
                    "key": pkey,
                    "title": pval.get("title", os.path.basename(pkey)),
                    "channel": pchannel,
                    "is_current_target": (sanitize_filename(pchannel) == sanitize_filename(target_channel)),
                    "path": "",
                    "parts": [],
                    "parts_count": 0,
                    "has_full": False,
                    "posted": True,
                    "posted_at": pval.get("posted_at", ""),
                    "on_disk": False
                })

        total_clips = len(clips_feed)
        posted_count = sum(1 for c in clips_feed if c["posted"])
        pending_count = total_clips - posted_count
        rate = round((posted_count / total_clips * 100)) if total_clips > 0 else 0
        
        accounts_matrix.append({
            "account_name": acc_name,
            "password": acc.get("password", ""),
            "mail": acc.get("mail", ""),
            "original_ip": acc.get("original_ip", ""),
            "build_up_ip": acc.get("build_up_ip", ""),
            "target_channel": target_channel,
            "target_history": target_history,
            "hashtag": acc.get("hashtag", ""),
            "content": acc.get("content", ""),
            "note": acc.get("note", ""),
            "clips": clips_feed,
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

def toggle_publishing_clip_status(account_name, clip_key, channel=None, title=None, posted=True):
    """
    Cập nhật trạng thái Đã đăng / Chưa đăng cho 1 clip của tài khoản TikTok
    """
    accounts_data = load_accounts_data()
    found = False
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    
    for acc in accounts_data.get("tiktok_accounts", []):
        if acc.get("account_name") == account_name:
            found = True
            if "posted_clips" not in acc:
                acc["posted_clips"] = {}
                
            acc["posted_clips"][clip_key] = {
                "posted": posted,
                "posted_at": now_str if posted else "",
                "channel": channel or os.path.dirname(clip_key),
                "title": title or os.path.basename(clip_key)
            }
            break
            
    if found:
        save_accounts_data(accounts_data)
        return True, now_str if posted else ""
    return False, "Không tìm thấy tài khoản"

def change_account_target_channel(account_name, new_target_channel):
    """
    Thay đổi kênh YouTube mục tiêu cho tài khoản TikTok, tự động lưu kênh cũ vào target_history
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
