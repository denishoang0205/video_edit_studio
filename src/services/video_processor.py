import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import subprocess
import re
import textwrap
import time
from PIL import Image, ImageDraw, ImageFont
try:
    from src.core.config import FFMPEG_EXE, DEFAULT_FONT_PATH, FONTS_DIR
except ImportError:
    from config import FFMPEG_EXE, DEFAULT_FONT_PATH, FONTS_DIR
from src.core.asset_manager import AssetManager

try:
    from src.services.audio_transcriber import transcribe_video_audio
    from src.services.translator_service import translate_segments
    from src.services.ai_dubber import create_dubbed_audio_track
    from src.services.subtitle_styler import generate_ass_subtitles, get_ffmpeg_subtitles_filter
except ImportError:
    from audio_transcriber import transcribe_video_audio
    from translator_service import translate_segments
    from ai_dubber import create_dubbed_audio_track
    from subtitle_styler import generate_ass_subtitles, get_ffmpeg_subtitles_filter

def get_video_duration(input_path):
    """Lấy thời lượng video (giây) bằng FFmpeg"""
    if not input_path or not os.path.exists(input_path):
        return 0.0
    cmd = [FFMPEG_EXE, "-i", input_path]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if match:
        hours, minutes, seconds = match.groups()
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    return 0.0

def create_styled_banner(video_title, output_png_path, style="white-rounded", font_name="Poppins-Bold", font_size=46, canvas_width=1080):
    """
    Tạo ảnh banner tiêu đề với phong cách tùy biến:
    - white-rounded: Nền trắng bo góc, chữ đen
    - dark-glass: Nền đen mờ glassmorphism, chữ trắng
    - pill-badge: Bo tròn hình viên thuốc, chữ đen
    - none: Không nền, chữ trắng viền đen
    """
    # Tìm kiếm font thông minh qua AssetManager
    font_path = AssetManager.resolve_font_path(font_name, DEFAULT_FONT_PATH)

    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    wrap_width = max(20, int(canvas_width / (font_size * 0.85)))
    wrapped_text = textwrap.fill(video_title.upper(), width=wrap_width)

    # Đo kích thước chữ
    dummy_img = Image.new('RGB', (canvas_width, 600))
    draw_dummy = ImageDraw.Draw(dummy_img)
    bbox = draw_dummy.multiline_textbbox((0, 0), wrapped_text, font=font, align='center')
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    padding_y = 28
    padding_x = 35
    banner_height = text_height + (padding_y * 2)

    banner = Image.new('RGBA', (canvas_width, banner_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(banner)
    center_x = canvas_width / 2
    center_y = banner_height / 2

    if style == "white-rounded":
        rect_box = [padding_x, 0, canvas_width - padding_x, banner_height]
        draw.rounded_rectangle(rect_box, radius=22, fill=(255, 255, 255, 255))
        draw.multiline_text((center_x, center_y), wrapped_text, fill=(0, 0, 0, 255), font=font, align='center', anchor='mm')
    elif style == "dark-glass":
        rect_box = [padding_x, 0, canvas_width - padding_x, banner_height]
        draw.rounded_rectangle(rect_box, radius=22, fill=(15, 23, 42, 220), outline=(255, 255, 255, 60), width=2)
        draw.multiline_text((center_x, center_y), wrapped_text, fill=(255, 255, 255, 255), font=font, align='center', anchor='mm')
    elif style == "pill-badge":
        box_w = min(canvas_width - (padding_x * 2), text_width + 80)
        left = (canvas_width - box_w) / 2
        rect_box = [left, 0, left + box_w, banner_height]
        draw.rounded_rectangle(rect_box, radius=banner_height // 2, fill=(255, 255, 255, 255))
        draw.multiline_text((center_x, center_y), wrapped_text, fill=(0, 0, 0, 255), font=font, align='center', anchor='mm')
    else:  # none
        # Vẽ viền chữ đổ bóng
        for offset_x, offset_y in [(-2, -2), (2, -2), (-2, 2), (2, 2), (0, 3)]:
            draw.multiline_text((center_x + offset_x, center_y + offset_y), wrapped_text, fill=(0, 0, 0, 255), font=font, align='center', anchor='mm')
        draw.multiline_text((center_x, center_y), wrapped_text, fill=(255, 255, 255, 255), font=font, align='center', anchor='mm')

    banner.save(output_png_path)
    return banner_height

def get_best_gpu_config():
    """
    Tự động phát hiện tất cả card đồ họa trong hệ thống,
    so sánh dung lượng VRAM (AdapterRAM) để tìm card rời/mạnh nhất,
    và trả về cấu hình mã hóa phù hợp (encoder, gpu_index, name).
    """
    try:
        import json
        cmd = ["powershell", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -Property Name, AdapterRAM | ConvertTo-Json"]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            if not isinstance(data, list):
                data = [data]
            
            valid_gpus = []
            for idx, item in enumerate(data):
                name = item.get("Name", "")
                vram = item.get("AdapterRAM")
                if not name or vram is None:
                    continue
                name_lower = name.lower()
                if "wonder" in name_lower or "basic display" in name_lower:
                    continue
                valid_gpus.append({
                    "index": idx,
                    "name": name,
                    "vram": int(vram)
                })
            
            if valid_gpus:
                valid_gpus.sort(key=lambda x: x["vram"], reverse=True)
                best_gpu = valid_gpus[0]
                name_lower = best_gpu["name"].lower()
                
                if "nvidia" in name_lower:
                    return {
                        "encoder": "h264_nvenc",
                        "gpu_index": best_gpu["index"],
                        "name": best_gpu["name"]
                    }
                elif "amd" in name_lower or "radeon" in name_lower:
                    return {
                        "encoder": "h264_amf",
                        "gpu_index": best_gpu["index"],
                        "name": best_gpu["name"]
                    }
                elif "intel" in name_lower:
                    return {
                        "encoder": "h264_qsv",
                        "gpu_index": best_gpu["index"],
                        "name": best_gpu["name"]
                    }
    except Exception:
        pass
    
    return {
        "encoder": "libx264",
        "gpu_index": None,
        "name": "CPU (Software)"
    }

def analyze_audio_and_scenes(video_path):
    """
    Quét siêu tốc năng lượng âm thanh (ebur128 LUFS / Voice Peaks) cho highlight:
    - Sử dụng ffmpeg -vn và process.communicate() chống treo pipe 100%.
    - Thời gian quét chỉ ~1-2s cho video dài 15-30 phút.
    """
    audio_points = []
    scene_cuts = []
    
    if not os.path.exists(video_path):
        return audio_points, scene_cuts

    cmd = [
        FFMPEG_EXE, "-y", "-vn", "-i", video_path,
        "-filter_complex", "ebur128=peak=none:meter=18",
        "-f", "null", "-"
    ]
    try:
        proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, encoding="utf-8", errors="ignore")
        _, err = proc.communicate(timeout=30)
        
        for line in err.splitlines():
            if 'TARGET:' in line and 'M:' in line:
                m = re.search(r't:\s*([\d\.]+)\s+TARGET:.*?M:\s*([-\d\.]+)', line)
                if m:
                    audio_points.append((float(m.group(1)), float(m.group(2))))
    except Exception as e:
        try:
            proc.kill()
        except Exception:
            pass

    return audio_points, scene_cuts

def detect_video_highlights(video_path, target_duration=40.0, num_clips=3, min_clip_len=30.0, max_clip_len=60.0, youtube_heatmap=None, log_cb=None):
    """
    Thuật toán phân tích cao trào và trích xuất phân đoạn hấp dẫn nhất:
    - target_duration: Thời lượng mong muốn của mỗi clip (mặc định 40s ~ nằm trong phạm vi 30s-45s hoặc 60s)
    - num_clips: Số lượng clip cao trào cần trích xuất (mặc định 3)
    - youtube_heatmap: Dữ liệu Heatmap Most Replayed từ YouTube (nếu có)
    """
    import bisect
    duration = get_video_duration(video_path)
    if duration <= 0:
        return []

    # Nếu video ngắn hơn hoặc bằng thời lượng yêu cầu, lấy toàn bộ video
    if duration <= max_clip_len:
        return [{
            "start": 0.0,
            "end": duration,
            "duration": duration,
            "score": 1.0,
            "part_idx": 1
        }]

    if log_cb:
        log_cb(f"🔍 Đang phân tích năng lượng âm thanh & nhịp chuyển cảnh ({duration:.1f}s)...")

    audio_points, scene_cuts = analyze_audio_and_scenes(video_path)
    times_list = [pt for (pt, m) in audio_points]
    loudness_list = [m for (pt, m) in audio_points]

    # Đảm bảo target_duration hợp lệ
    target_duration = max(min_clip_len, min(target_duration, max_clip_len))
    step = 2.0  # Bước nhảy phân tích 2 giây

    # Loại bỏ vùng chết đầu video (5s intro) và cuối video (5s outro/endcard)
    dead_zone_start = min(5.0, duration * 0.05)
    dead_zone_end = min(5.0, duration * 0.05)

    windows = []
    t = dead_zone_start
    while t + target_duration <= duration - dead_zone_end:
        t_end = t + target_duration

        # 1. Điểm số âm thanh (Audio Energy & Peaks) qua tìm kiếm nhị phân bisect siêu tốc
        idx_start = bisect.bisect_left(times_list, t)
        idx_end = bisect.bisect_right(times_list, t_end)
        sample_loudness = loudness_list[idx_start:idx_end]
        
        if sample_loudness:
            avg_lufs = sum(sample_loudness) / len(sample_loudness)
            peak_lufs = max(sample_loudness)
            # Chuẩn hóa: -40 LUFS -> 0.0, -10 LUFS -> 1.0
            avg_norm = max(0.0, min(1.0, (avg_lufs + 40.0) / 30.0))
            peak_norm = max(0.0, min(1.0, (peak_lufs + 30.0) / 25.0))
            audio_score = (avg_norm * 0.6) + (peak_norm * 0.4)
        else:
            audio_score = 0.5  # Mặc định nếu không phân tích được audio

        # 2. Điểm số chuyển động & chuyển cảnh (Scene Activity)
        cuts_in_win = sum(1 for c in scene_cuts if t <= c <= t_end)
        scene_score = min(1.0, cuts_in_win / 8.0) if scene_cuts else 0.5

        # 3. Điểm số Heatmap Most Replayed từ YouTube (nếu có)
        heatmap_score = 0.0
        if youtube_heatmap and isinstance(youtube_heatmap, list):
            heat_vals = []
            for hp in youtube_heatmap:
                hp_start = hp.get("start_time", 0)
                hp_end = hp.get("end_time", hp_start + 2.0)
                if not (hp_end < t or hp_start > t_end):
                    heat_vals.append(hp.get("value", 0.0))
            if heat_vals:
                heatmap_score = sum(heat_vals) / len(heat_vals)

        # Tính điểm tổng hợp (Weighted Fusion)
        if youtube_heatmap and len(youtube_heatmap) > 0:
            total_score = (audio_score * 0.40) + (scene_score * 0.25) + (heatmap_score * 0.35)
        else:
            total_score = (audio_score * 0.65) + (scene_score * 0.35)

        windows.append({
            "start": t,
            "end": t_end,
            "score": total_score,
            "audio_score": audio_score,
            "scene_score": scene_score,
            "cuts": cuts_in_win
        })
        t += step

    if not windows:
        # Fallback: chia đều nếu video quá ngắn hoặc lỗi
        part_dur = duration / max(1, num_clips)
        return [{
            "start": i * part_dur,
            "end": min(duration, (i + 1) * part_dur),
            "duration": part_dur,
            "score": 0.5,
            "part_idx": i + 1
        } for i in range(num_clips)]

    # 4. Thuật toán Non-Maximum Suppression (NMS) chọn Top N Highlight không bị đè nhau
    windows.sort(key=lambda w: w["score"], reverse=True)
    selected_segments = []
    
    # Khoảng cách tối thiểu giữa 2 đoạn cao trào (ít nhất bằng nửa thời lượng clip)
    min_separation = target_duration * 0.6

    for cand in windows:
        overlap = False
        for sel in selected_segments:
            # Kiểm tra khoảng cách overlap
            if not (cand["end"] <= sel["start"] - min_separation or cand["start"] >= sel["end"] + min_separation):
                overlap = True
                break
        if not overlap:
            selected_segments.append(cand)
            if len(selected_segments) >= num_clips:
                break

    # Nếu chưa đủ num_clips, nới lỏng separation để lấy thêm
    if len(selected_segments) < num_clips:
        for cand in windows:
            if cand in selected_segments:
                continue
            overlap = False
            for sel in selected_segments:
                if not (cand["end"] <= sel["start"] or cand["start"] >= sel["end"]):
                    overlap = True
                    break
            if not overlap:
                selected_segments.append(cand)
                if len(selected_segments) >= num_clips:
                    break

    # Sắp xếp theo thứ tự thời gian xuất hiện trong video
    selected_segments.sort(key=lambda w: w["start"])

    # 5. Smart Cut Snapping: Căn chỉnh điểm bắt đầu / kết thúc vào điểm cắt cảnh hoặc khoảng lặng âm thanh
    final_clips = []
    for idx, seg in enumerate(selected_segments):
        st = seg["start"]
        en = seg["end"]

        # Tìm scene cut gần st trong phạm vi [-2s, +2s]
        nearby_start_cuts = [c for c in scene_cuts if abs(c - st) <= 2.0]
        if nearby_start_cuts:
            st = min(nearby_start_cuts, key=lambda c: abs(c - st))

        # Tìm scene cut gần en trong phạm vi [-2s, +2s]
        nearby_end_cuts = [c for c in scene_cuts if abs(c - en) <= 2.0]
        if nearby_end_cuts:
            en = min(nearby_end_cuts, key=lambda c: abs(c - en))

        # Đảm bảo giới hạn thời lượng min/max
        clip_dur = en - st
        if clip_dur < min_clip_len:
            en = min(duration, st + min_clip_len)
        elif clip_dur > max_clip_len:
            en = st + max_clip_len

        st = max(0.0, round(st, 2))
        en = min(duration, round(en, 2))
        actual_dur = round(en - st, 2)

        final_clips.append({
            "start": st,
            "end": en,
            "duration": actual_dur,
            "score": round(seg["score"], 3),
            "part_idx": idx + 1
        })

    return final_clips

def get_video_dimensions(input_path):
    """Lấy kích thước (width, height, ratio) của video bằng FFmpeg"""
    if not input_path or not os.path.exists(input_path):
        return 0, 0, 1.0
    cmd = [FFMPEG_EXE, "-i", input_path]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    match = re.search(r"Video:.*?,\s*(\d{3,5})x(\d{3,5})", result.stderr)
    if match:
        w, h = int(match.group(1)), int(match.group(2))
        return w, h, (w / h) if h > 0 else 1.0
    return 0, 0, 1.0

def process_video_custom(input_path, output_full_path, video_title, settings=None, start_time=None, duration=None, localization_settings=None, log_cb=None):
    """
    Biên tập Video theo cấu hình Webform Studio (Hỗ trợ GPU Acceleration, Smart Aspect Ratio & AI Localization/Dubbing):
    - aspect_ratio: auto, 3:4, 9:16, 16:9, 4:3, 1:1
    - blur_bg: True/False
    - hflip: True/False
    - color_boost: True/False
    - banner_box_style: white-rounded, dark-glass, pill-badge, none
    - banner_font: Poppins-Bold, Montserrat-Bold, Arial-Bold
    - banner_font_size: 46
    - banner_position: top, center, bottom
    - start_time: Giây bắt đầu cắt (nếu cắt trực tiếp từ video gốc)
    - duration: Số giây cần cắt (nếu cắt trực tiếp từ video gốc)
    - localization_settings: {target_lang, dubbing_mode, voice_gender, sub_style}
    """
    if log_cb is None:
        log_cb = print

    if settings is None:
        settings = {}

    aspect_ratio = settings.get("aspect_ratio", "3:4")
    blur_bg = settings.get("blur_bg", True)
    hflip = settings.get("hflip", False)
    color_boost = settings.get("color_boost", True)
    banner_style = settings.get("banner_box_style", "white-rounded")
    banner_font = settings.get("banner_font", "Poppins-Bold")
    banner_font_size = int(settings.get("banner_font_size", 46))
    banner_pos = settings.get("banner_position", "top")

    # Tự động nhận diện tỷ lệ khung hình thực tế của video nguồn
    in_w, in_h, in_ratio = get_video_dimensions(input_path)
    is_native_vertical = (in_h > 0 and in_w > 0 and in_h >= in_w * 1.35)

    # Nếu video gốc đã là video dọc chuẩn điện thoại (9:16 như Shorts/TikTok)
    # Tự động chuyển hoặc giữ tỷ lệ 9:16 để video tràn viền full màn hình, không bị thu nhỏ tí xíu vào khung 3:4
    if is_native_vertical and (aspect_ratio in ["3:4", "auto"] or settings.get("smart_vertical_adapt", True)):
        aspect_ratio = "9:16"

    # Xác định kích thước Canvas (W x H)
    canvas_map = {
        "3:4": (1080, 1440),
        "9:16": (1080, 1920),
        "16:9": (1920, 1080),
        "4:3": (1440, 1080),
        "1:1": (1080, 1080)
    }
    canvas_w, canvas_h = canvas_map.get(aspect_ratio, (1080, 1920 if is_native_vertical else 1440))

    output_dir = os.path.dirname(output_full_path)
    os.makedirs(output_dir, exist_ok=True)
    banner_png_path = os.path.join(output_dir, "title_banner.png")
    banner_height = create_styled_banner(video_title, banner_png_path, style=banner_style, font_name=banner_font, font_size=banner_font_size, canvas_width=canvas_w)

    # Tính toán tọa độ banner Y (Với 9:16 lùi xuống 100-120px vào vùng an toàn Safe Zone của TikTok)
    if banner_pos == "top":
        if canvas_h >= 1920:
            banner_y = 110
        elif canvas_h >= 1440:
            banner_y = 70
        else:
            banner_y = 35
    elif banner_pos == "center":
        banner_y = f"(H-h)/2 - 120"
    else:  # bottom
        banner_y = f"H - h - 140" if canvas_h >= 1920 else f"H - h - 70"

    # ----------------------------------------------------
    # AI LOCALIZATION & DUBBING PIPELINE (Brazil / Mexico...)
    # ----------------------------------------------------
    loc_cfg = localization_settings or settings.get("localization") or {}
    target_lang = loc_cfg.get("target_lang", "none")
    dubbing_mode = loc_cfg.get("dubbing_mode", "dub_and_sub")
    voice_gender = loc_cfg.get("voice_gender", "male")
    sub_style = loc_cfg.get("sub_style", "tiktok-yellow")

    has_localization = bool(target_lang and target_lang.lower() not in ["none", "no", "false", ""])
    translated_sub_path = None
    dubbed_audio_path = None

    if has_localization:
        log_cb(f"🌐 Kích hoạt AI Localization sang {target_lang.upper()} (Chế độ: {dubbing_mode})...")
        raw_segs = transcribe_video_audio(input_path, start_time=start_time, duration=duration, log_cb=log_cb)
        if raw_segs:
            trans_segs = translate_segments(raw_segs, target_lang=target_lang, source_lang="en", log_cb=log_cb)
            
            # Tạo phụ đề nếu cần
            if dubbing_mode in ["dub_and_sub", "sub_only"] and trans_segs:
                ass_sub_path = os.path.join(output_dir, f"subtitles_{target_lang}.ass")
                ok_ass = generate_ass_subtitles(trans_segs, ass_sub_path, style=sub_style, canvas_w=canvas_w, canvas_h=canvas_h)
                if ok_ass:
                    translated_sub_path = ass_sub_path
                    log_cb(f"📝 Đã tạo tệp phụ đề: {os.path.basename(ass_sub_path)}")

            # Tạo âm thanh lồng tiếng AI nếu cần
            if dubbing_mode in ["dub_and_sub", "dub_only"] and trans_segs:
                temp_dub = os.path.join(output_dir, f"dubbed_audio_{target_lang}.aac")
                ok_dub = create_dubbed_audio_track(trans_segs, temp_dub, target_lang=target_lang, gender=voice_gender, log_cb=log_cb)
                if ok_dub:
                    dubbed_audio_path = temp_dub
        else:
            log_cb("ℹ️ Video không có lời thoại hoặc không trích xuất được phụ đề, tiếp tục biên tập chuẩn.")

    # Xây dựng FFmpeg Filter Graph chất lượng cao (Super-Resolution & Sharpening)
    pre_filters = []
    if hflip:
        pre_filters.append("hflip")
    if color_boost:
        pre_filters.append("eq=saturation=1.15:contrast=1.06:brightness=0.01")
    
    # Thêm bộ lọc làm nét viền chủ thể (Unsharp Mask)
    pre_filters.append("unsharp=luma_msize_x=5:luma_msize_y=5:luma_amount=0.8:chroma_msize_x=5:chroma_msize_y=5:chroma_amount=0.0")
    
    pre_filter_str = ("," + ",".join(pre_filters)) if pre_filters else ""

    # Bộ lọc phụ đề nếu có
    sub_filter_str = ""
    if translated_sub_path and os.path.exists(translated_sub_path):
        clean_ass = translated_sub_path.replace("\\", "/").replace(":", "\\:")
        sub_filter_str = f",subtitles='{clean_ass}'"

    if blur_bg and aspect_ratio in ["3:4", "9:16", "1:1"]:
        # 2 lớp: Nền Mờ chuẩn avgblur phủ kín Canvas + Video tiền cảnh sắc nét ở trung tâm
        scale_bg = f"scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase:flags=lanczos,crop={canvas_w}:{canvas_h},avgblur=sizeX=30:sizeY=30"
        
        if is_native_vertical:
            if aspect_ratio == "3:4":
                scale_fg = f"scale=-2:1300:flags=lanczos"
            elif aspect_ratio == "9:16":
                scale_fg = f"scale=-2:1740:flags=lanczos"
            else:  # 1:1
                scale_fg = f"scale=-2:{int(canvas_h * 0.92)}:flags=lanczos"
        else:
            if aspect_ratio == "3:4":
                scale_fg = f"scale={canvas_w}:{int(canvas_w * 0.5625)}:force_original_aspect_ratio=decrease:flags=lanczos"
            elif aspect_ratio == "9:16":
                scale_fg = f"scale={canvas_w}:{int(canvas_w * 0.5625)}:force_original_aspect_ratio=decrease:flags=lanczos"
            else:  # 1:1
                scale_fg = f"scale={canvas_w}:{canvas_w}:force_original_aspect_ratio=decrease:flags=lanczos"
        
        filter_complex = (
            f"[0:v]{scale_bg}[bg];"
            f"[0:v]{scale_fg}{pre_filter_str}[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[combined];"
            f"[combined][1:v]overlay=0:{banner_y}{sub_filter_str},format=yuv420p[v]"
        )
    else:
        # Scale vừa canvas với Lanczos + format yuv420p
        filter_complex = (
            f"[0:v]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=decrease:flags=lanczos,pad={canvas_w}:{canvas_h}:(ow-iw)/2:(oh-ih)/2:black{pre_filter_str}[base];"
            f"[base][1:v]overlay=0:{banner_y}{sub_filter_str},format=yuv420p[v]"
        )

    # Nếu có audio lồng tiếng AI -> Audio Ducking: Trộn hạ âm gốc xuống 12%, lồng tiếng 100%
    audio_map = ["-map", "0:a?"]
    if dubbed_audio_path and os.path.exists(dubbed_audio_path):
        filter_complex += f";[0:a]volume=0.12[orig_a];[2:a]volume=1.0[dub_a];[orig_a][dub_a]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        audio_map = ["-map", "[aout]"]

    # Lấy cấu hình GPU tối ưu nhất dựa trên VRAM
    gpu_config = get_best_gpu_config()
    best_encoder = gpu_config.get("encoder", "libx264")
    gpu_name = gpu_config.get("name", "CPU")

    # Thử chạy với GPU, nếu thất bại thì fallback CPU libx264
    def build_cmd(use_gpu=True):
        cmd = [FFMPEG_EXE, "-y"]
        if start_time is not None and start_time > 0:
            cmd.extend(["-ss", str(start_time)])
        
        cmd.extend([
            "-hwaccel", "auto" if use_gpu else "none",
            "-i", input_path,
            "-i", banner_png_path,
        ])

        if dubbed_audio_path and os.path.exists(dubbed_audio_path):
            cmd.extend(["-i", dubbed_audio_path])
        
        if duration is not None and duration > 0:
            cmd.extend(["-t", str(duration)])

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[v]",
        ])
        cmd.extend(audio_map)
        cmd.extend(["-r", "60"])
        
        if use_gpu and best_encoder != "libx264":
            cmd.extend(["-c:v", best_encoder])
            if best_encoder == "h264_nvenc":
                cmd.extend(["-preset", "p4", "-cq", "22", "-b:v", "5500k", "-maxrate", "7500k", "-bufsize", "12000k"])
            elif best_encoder == "h264_amf":
                cmd.extend(["-quality", "quality", "-b:v", "5500k"])
            elif best_encoder == "h264_qsv":
                cmd.extend(["-preset", "medium", "-b:v", "5500k"])
        else:
            cmd.extend(["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-b:v", "5500k", "-maxrate", "7500k", "-bufsize", "12000k"])
        
        cmd.extend(["-c:a", "aac", "-b:a", "192k", "-ar", "44100", output_full_path])
        return cmd

    res = subprocess.run(build_cmd(use_gpu=True), stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    
    if res.returncode != 0:
        res_cpu = subprocess.run(build_cmd(use_gpu=False), stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
        if res_cpu.returncode != 0:
            print("❌ Lỗi biên tập video:")
            print(res_cpu.stderr[-400:])
            return False

    # Dọn dẹp tệp âm thanh lồng tiếng tạm thời sau khi render
    if dubbed_audio_path and os.path.exists(dubbed_audio_path):
        try:
            os.remove(dubbed_audio_path)
        except Exception:
            pass

    return True

    return True

import math

def split_video_custom(edited_file, output_folder, duration, split_mode="auto", log_cb=None):
    """
    Cắt video theo các tùy chọn:
    1. Theo thời lượng phút (Duration-based):
       - every-1m / every-60s: Cắt mỗi phần đúng 1 phút (60s)
       - every-2m / every-120s: Cắt mỗi phần đúng 2 phút (120s)
       - every-3m / every-180s: Cắt mỗi phần đúng 3 phút (180s)
    2. Chia đều số phần (Equal parts):
       - fixed-3: Chia đều 3 phần
       - fixed-6: Chia đều 6 phần
       - auto: <12p chia 3, >=12p chia 6
       - no-split: Không cắt
    """
    if log_cb is None:
        log_cb = print

    if split_mode == "no-split":
        return [edited_file]

    split_files = []
    video_title = os.path.basename(output_folder)

    # 1. Cắt theo phút cố định
    if split_mode in ["every-1m", "every-60s", "1m", "60s"]:
        part_duration = 60.0
        parts_count = max(1, int(math.ceil(duration / part_duration)))
        log_cb(f"⏱️ Cắt video theo từng phút ({duration:.1f}s) ➔ {parts_count} phần (mỗi part 60s)...")
    elif split_mode in ["every-2m", "every-120s", "2m", "120s"]:
        part_duration = 120.0
        parts_count = max(1, int(math.ceil(duration / part_duration)))
        log_cb(f"⏱️ Cắt video theo mỗi 2 phút ({duration:.1f}s) ➔ {parts_count} phần (mỗi part 120s)...")
    elif split_mode in ["every-3m", "every-180s", "3m", "180s"]:
        part_duration = 180.0
        parts_count = max(1, int(math.ceil(duration / part_duration)))
        log_cb(f"⏱️ Cắt video theo mỗi 3 phút ({duration:.1f}s) ➔ {parts_count} phần (mỗi part 180s)...")
    # 2. Chia đều theo số phần
    elif split_mode in ["fixed-3", "equal-3"]:
        parts_count = 3
        part_duration = duration / parts_count
        log_cb(f"✂️ Chia đều video ({duration:.1f}s) thành 3 phần (mỗi part ~{part_duration:.1f}s)...")
    elif split_mode in ["fixed-6", "equal-6"]:
        parts_count = 6
        part_duration = duration / parts_count
        log_cb(f"✂️ Chia đều video ({duration:.1f}s) thành 6 phần (mỗi part ~{part_duration:.1f}s)...")
    else:  # auto
        parts_count = 6 if duration >= 720 else 3
        part_duration = duration / parts_count
        log_cb(f"✂️ Auto chia đều ({duration:.1f}s) ➔ {parts_count} phần (mỗi part ~{part_duration:.1f}s)...")

    for i in range(parts_count):
        start_time = i * part_duration
        if start_time >= duration:
            break
        current_len = min(part_duration, duration - start_time)
        if current_len < 3.0:
            continue

        out_part_path = os.path.join(output_folder, f"{video_title} - part {i+1}.mp4")
        cmd = [
            FFMPEG_EXE, "-y",
            "-ss", str(start_time),
            "-i", edited_file,
            "-t", str(current_len),
            "-c", "copy",
            out_part_path
        ]
        subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        if os.path.exists(out_part_path):
            split_files.append(out_part_path)
            log_cb(f"   + Part {i+1}: {os.path.basename(out_part_path)} ({current_len:.1f}s)")

    return split_files

def process_and_split_video(
    actual_video_file,
    video_out_dir,
    title,
    settings=None,
    split_mode="auto-highlight-45s",
    is_short=False,
    export_full=False,
    youtube_heatmap=None,
    log_cb=None,
    progress_cb=None
):
    """
    Quy trình biên tập tổng thể nâng cấp:
    1. Short Video (thời lượng <= 60s hoặc is_short=True):
       - Biên tập trọn vẹn theo rule hiện tại, xuất 1 file '[Title] - part 1.mp4' (và edited_full nếu export_full=True).
    2. Long Video (thời lượng > 60s):
       - Tự động quét phân tích cao trào và trích xuất các đoạn 30s-45s hoặc 60s.
       - Xuất các Part Highlight chất lượng cao: '[Title] - part 1.mp4', '[Title] - part 2.mp4'...
    """
    if log_cb is None:
        log_cb = print

    duration = get_video_duration(actual_video_file)
    os.makedirs(video_out_dir, exist_ok=True)
    
    # 1. Nhận diện Video Ngắn (Shorts / Video dưới 2 phút)
    is_short_video = is_short or (0 < duration < 120.0)
    
    if is_short_video:
        log_cb(f"⚡ [Video Ngắn/Short] Thời lượng {duration:.1f}s (< 2 phút): Biên tập trọn vẹn 1 clip chuẩn...")
        part_1_path = os.path.join(video_out_dir, f"{title} - part 1.mp4")
        if progress_cb:
            progress_cb(0, 1)
        success = process_video_custom(actual_video_file, part_1_path, title, settings, log_cb=log_cb)
        if not success:
            return []
        
        if progress_cb:
            progress_cb(1, 1)
        
        if export_full:
            full_path = os.path.join(video_out_dir, "edited_full.mp4")
            try:
                import shutil
                shutil.copyfile(part_1_path, full_path)
            except Exception:
                pass
        return [part_1_path]

    # 2. Xử lý Video Dài (> 60s)
    log_cb(f"🎬 [Video Dài] Thời lượng {duration:.1f}s ({int(duration//60)}p{int(duration%60):02d}s) | Chế độ: {split_mode}")

    # Kiểm tra xem có phải chế độ cắt Highlight Cao Trào hay không
    is_highlight_mode = (
        "highlight" in split_mode or
        split_mode.startswith("ai-") or
        split_mode in ["auto-highlight-45s", "auto-highlight-60s", "auto-highlight-30s", "ai-highlight-25-30s", "ai-highlight-30-45s", "ai-highlight-45-60s"]
    ) and split_mode not in ["auto", "fixed-3", "fixed-6", "no-split", "every-1m", "every-2m", "every-3m", "every-60s", "every-120s", "every-180s"]

    if is_highlight_mode:
        # Xác định độ dài mục tiêu cho mỗi clip cao trào
        if "25" in split_mode or ("30s" in split_mode and "45" not in split_mode):
            target_dur = 28.0  # 25s - 30s
            min_len = 25.0
            max_len = 30.0
        elif "60s" in split_mode or "1m" in split_mode or "45-60" in split_mode:
            target_dur = 55.0  # 45s - 60s
            min_len = 45.0
            max_len = 60.0
        else:
            # Mặc định: 30s - 45s (Chuẩn TikTok Viral)
            target_dur = 40.0
            min_len = 30.0
            max_len = 45.0

        # Số lượng clip: Mặc định 3 clips (hoặc 2 clip nếu video < 5p, 3-5 clip nếu video >= 5p)
        num_clips = 3 if duration >= 300 else (2 if duration >= 120 else 1)

        log_cb(f"🔍 Đang quét AI tìm Top {num_clips} đoạn cao trào nhất (phạm vi {int(min_len)}s - {int(max_len)}s)...")
        highlights = detect_video_highlights(
            actual_video_file,
            target_duration=target_dur,
            num_clips=num_clips,
            min_clip_len=min_len,
            max_clip_len=max_len,
            youtube_heatmap=youtube_heatmap,
            log_cb=log_cb
        )

        if not highlights:
            log_cb("⚠️ Không tìm thấy đoạn cao trào phù hợp, chuyển sang chế độ cắt cơ bản...")
            # Fallback
            part_dur = min(duration, target_dur)
            highlights = [{
                "start": 0.0,
                "end": part_dur,
                "duration": part_dur,
                "score": 1.0,
                "part_idx": 1
            }]

        log_cb(f"🔥 Đã xác định {len(highlights)} đoạn cao trào đỉnh cao:")
        for h in highlights:
            st = h['start']
            en = h['end']
            st_str = f"{int(st//60)}:{int(st%60):02d}"
            en_str = f"{int(en//60)}:{int(en%60):02d}"
            log_cb(f"   + Part {h['part_idx']}: {st_str} ➔ {en_str} ({h['duration']:.1f}s | Điểm viral: {h['score']:.2f})")

        total_parts = len(highlights)
        split_files = []
        for p_idx, h in enumerate(highlights):
            part_idx = h["part_idx"]
            if progress_cb:
                progress_cb(p_idx, total_parts)
            out_part_path = os.path.join(video_out_dir, f"{title} - part {part_idx}.mp4")
            log_cb(f"⚙️ Đang biên tập & render Part {part_idx}/{total_parts} ({h['duration']:.1f}s)...")
            
            # Render trực tiếp từ video gốc với thời gian bắt đầu và thời lượng của highlight
            ok = process_video_custom(
                input_path=actual_video_file,
                output_full_path=out_part_path,
                video_title=title,
                settings=settings,
                start_time=h["start"],
                duration=h["duration"],
                log_cb=log_cb
            )
            if ok and os.path.exists(out_part_path):
                split_files.append(out_part_path)
                log_cb(f"   ✅ Hoàn thành Part {part_idx}: {os.path.basename(out_part_path)}")
            else:
                log_cb(f"   ❌ Lỗi khi render Part {part_idx}")
            if progress_cb:
                progress_cb(p_idx + 1, total_parts)

        if export_full:
            full_path = os.path.join(video_out_dir, "edited_full.mp4")
            log_cb(f"📦 Đang xuất thêm bản full video hoàn chỉnh...")
            process_video_custom(actual_video_file, full_path, title, settings, log_cb=log_cb)

        return split_files

    else:
        # Chế độ Cắt theo từng Phút hoặc Chia đều số phần
        edited_full_path = os.path.join(video_out_dir, "edited_full.mp4")
        log_cb(f"⚙️ Đang render bản Full Video để cắt theo chế độ '{split_mode}'...")
        success = process_video_custom(actual_video_file, edited_full_path, title, settings, log_cb=log_cb)
        if not success:
            return []

        split_files = split_video_custom(edited_full_path, video_out_dir, duration, split_mode=split_mode, log_cb=log_cb)

        if not export_full and split_mode != "no-split" and os.path.exists(edited_full_path):
            try:
                os.remove(edited_full_path)
            except Exception:
                pass

        return split_files

