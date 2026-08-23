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
ACCOUNTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.json")
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

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
            "wait_seconds_after_switch": 5
        },
        "tiktok_upload": {
            "auto_submit": True,
            "close_browser_after_finish": False,
            "wait_timeout": 60
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
    return url_or_path

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
            if not mp4_files:
                continue

            full_vid = [f for f in mp4_files if f.startswith('edited_') or 'edited_full' in f]
            
            # Nhận diện tất cả các file parts:
            # 1. Các file có 'part' trong tên (part_1, Part 1, - part 1, d - part_1, etc.)
            # 2. Các file cắt đoạn nhỏ không phải full/original
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
                
                # Sắp xếp các part theo số thứ tự (part 1, part 2,...) hoặc timestamp/tên file
                def get_part_sort_key(filename):
                    # Tìm số part rõ ràng: part_1, part 1, part-1, etc.
                    match = re.search(r'part[_\s\-]*(\d+)', filename, re.IGNORECASE)
                    if match:
                        return (0, int(match.group(1)), filename)
                    # Nếu là timestamp dạng 00.00.00.000
                    ts_match = re.search(r'-(\d\d)\.(\d\d)\.(\d\d)', filename)
                    if ts_match:
                        sec = int(ts_match.group(1))*3600 + int(ts_match.group(2))*60 + int(ts_match.group(3))
                        return (1, sec, filename)
                    return (2, 0, filename)

                parts_list = []
                for p in sorted(candidate_parts, key=get_part_sort_key):
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


def scan_source_directory(source_path, dest_path=None):
    """
    Quét toàn diện thư mục nguồn và thư mục đích:
    - Quét các video thô (raw) đang có ở Source.
    - Quét các video đã biên tập (finished) ở Destination (Output) và trong history.json.
    - Đảm bảo các chỉ số trên Dashboard, Editor Studio và Kênh YouTube luôn chính xác 100%
      ngay cả sau khi video gốc đã được biên tập và xóa để tiết kiệm dung lượng đĩa.
    """
    resolved_source = resolve_google_drive_path(source_path)
    resolved_dest = resolve_google_drive_path(dest_path)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    if not resolved_source or not os.path.exists(resolved_source):
        default_candidates = [
            os.path.join(base_dir, "video"),
            r"c:\Users\bao huy\Documents\Tiktok builder"
        ]
        for cand in default_candidates:
            if os.path.exists(cand):
                resolved_source = cand
                break
        if not resolved_source or not os.path.exists(resolved_source):
            resolved_source = os.path.join(base_dir, "video")
            os.makedirs(resolved_source, exist_ok=True)

    if not resolved_dest or not os.path.exists(resolved_dest):
        resolved_dest = os.path.join(base_dir, "Tiktok_Builder_Output")
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
                                channel_map[matched_cname]["videos_dict"][v_title] = {
                                    "title": v_title,
                                    "path": video_file_path,
                                    "dir_path": sub_path,
                                    "edited": False,
                                    "is_finished_only": False
                                }
                        # File video trực tiếp (vd: SoyPato / Video1.mp4)
                        elif sub.lower().endswith(('.mp4', '.mkv', '.mov', '.avi', '.webm')):
                            v_title = os.path.splitext(sub)[0]
                            channel_map[matched_cname]["videos_dict"][v_title] = {
                                "title": v_title,
                                "path": sub_path,
                                "dir_path": full_entry_path,
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
            channel_map[matched_cname]["videos_dict"][f_title] = {
                "title": f_title,
                "path": finished_item.get("path", ""),
                "dir_path": finished_item.get("path", ""),
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
            channel_map[matched_cname]["videos_dict"][h_title] = {
                "title": h_title,
                "path": h_out,
                "dir_path": h_out,
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

    return {"folders": result_folders, "source_path": source_path}

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
                parts_status = post_info.get("parts_status", {})
                
                # Nạp thông tin chi tiết từng part
                parts_data = []
                for idx, p in enumerate(c.get("parts", [])):
                    p_label = f"Part {idx + 1}"
                    p_stat = parts_status.get(p_label, {})
                    p_is_posted = bool(p_stat.get("posted", False)) if parts_status else is_posted
                    p_posted_at = p_stat.get("posted_at", posted_at) if parts_status else posted_at
                    
                    parts_data.append({
                        "name": p.get("name"),
                        "label": p_label,
                        "part_index": idx + 1,
                        "file_path": p.get("file_path"),
                        "url": p.get("url"),
                        "posted": p_is_posted,
                        "posted_at": p_posted_at
                    })
                
                # Nếu có parts_status, kiểm tra xem toàn bộ các part đã đăng hết chưa
                if parts_data and parts_status:
                    is_posted = all(p["posted"] for p in parts_data)
                
                clips_feed.append({
                    "key": clip_key,
                    "title": c.get("title"),
                    "channel": c_channel,
                    "is_current_target": (sanitize_filename(c_channel) == sanitize_filename(target_channel)),
                    "path": c.get("path"),
                    "parts": parts_data,
                    "parts_count": len(parts_data),
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
            "adspower_id": acc.get("adspower_id", ""),
            "adspower_serial": acc.get("adspower_serial", ""),
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

def toggle_publishing_clip_status(account_name, clip_key, channel=None, title=None, posted=True, part_label=None):
    """
    Cập nhật trạng thái Đã đăng / Chưa đăng cho 1 clip hoặc 1 part cụ thể của tài khoản TikTok
    """
    accounts_data = load_accounts_data()
    found = False
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    
    for acc in accounts_data.get("tiktok_accounts", []):
        if acc.get("account_name") == account_name:
            found = True
            if "posted_clips" not in acc:
                acc["posted_clips"] = {}
                
            entry = acc["posted_clips"].get(clip_key, {})
            if not isinstance(entry, dict):
                entry = {"posted": bool(entry)}
                
            if "parts_status" not in entry:
                entry["parts_status"] = {}
                
            if part_label:
                # Cập nhật riêng cho part này
                entry["parts_status"][part_label] = {
                    "posted": posted,
                    "posted_at": now_str if posted else ""
                }
                # Kiểm tra nếu có bất kỳ part nào đã đăng
                has_any_posted = any(p.get("posted") for p in entry["parts_status"].values())
                entry["posted"] = has_any_posted
                if posted and not entry.get("posted_at"):
                    entry["posted_at"] = now_str
            else:
                # Cập nhật cho toàn bộ clip
                entry["posted"] = posted
                entry["posted_at"] = now_str if posted else ""
                if posted:
                    for pk in entry.get("parts_status", {}):
                        entry["parts_status"][pk]["posted"] = True
                        entry["parts_status"][pk]["posted_at"] = now_str
                else:
                    for pk in entry.get("parts_status", {}):
                        entry["parts_status"][pk]["posted"] = False
                        entry["parts_status"][pk]["posted_at"] = ""
                        
            entry["channel"] = channel or os.path.dirname(clip_key)
            entry["title"] = title or os.path.basename(clip_key)
            acc["posted_clips"][clip_key] = entry
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

def get_pending_publishing_queue(account_name=None, channel_name=None, only_current_target=True):
    """
    Lấy danh sách các clip/part đang chờ xuất bản (posted == False) trên ổ đĩa.
    Được chuẩn hóa cho n8n workflow và automated cron triggers.
    """
    matrix_data = get_publishing_matrix()
    pending_queue = []
    
    for acc in matrix_data.get("accounts", []):
        curr_acc_name = acc.get("account_name", "")
        if account_name and curr_acc_name.lower() != str(account_name).lower():
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
                
            parts = clip.get("parts", [])
            if parts:
                for p in parts:
                    if not p.get("posted"):
                        pending_queue.append({
                            "account_name": curr_acc_name,
                            "channel": clip_channel,
                            "title": clip.get("title", ""),
                            "clip_key": clip.get("key", ""),
                            "part_label": p.get("label", ""),
                            "part_name": p.get("name", ""),
                            "video_file": p.get("file_path", ""),
                            "hashtag": acc.get("hashtag", ""),
                            "target_ip": acc.get("build_up_ip") or acc.get("original_ip", ""),
                            "adspower_id": acc.get("adspower_id") or acc.get("adspower_serial") or curr_acc_name,
                            "parent_folder": clip.get("path", "")
                        })
            else:
                if not clip.get("posted"):
                    # Tìm file mp4 trong thư mục
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
                        "clip_key": clip.get("key", ""),
                        "part_label": "",
                        "part_name": "",
                        "video_file": video_file,
                        "hashtag": acc.get("hashtag", ""),
                        "target_ip": acc.get("build_up_ip") or acc.get("original_ip", ""),
                        "adspower_id": acc.get("adspower_id") or acc.get("adspower_serial") or curr_acc_name,
                        "parent_folder": clip.get("path", "")
                    })
                    
    return pending_queue

