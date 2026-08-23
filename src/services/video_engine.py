import os
import sys
import subprocess
import re
import textwrap
from PIL import Image, ImageDraw, ImageFont
from config import FFMPEG_EXE

def get_video_duration(input_path):
    """Lấy thời lượng video (giây) bằng FFmpeg"""
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
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Tìm kiếm font từ thư mục dự án, thư mục fonts/ hoặc font hệ thống Windows
    font_candidates = [
        os.path.join(base_dir, f"{font_name}.ttf"),
        os.path.join(base_dir, f"{font_name}.otf"),
        os.path.join(base_dir, "fonts", f"{font_name}.ttf"),
        os.path.join(base_dir, "fonts", f"{font_name}.otf"),
        os.path.join(r"C:\Windows\Fonts", f"{font_name}.ttf"),
        os.path.join(base_dir, "Poppins-Bold.ttf"),
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\tahoma.ttf"
    ]
    
    font_path = None
    for cand in font_candidates:
        if os.path.exists(cand):
            font_path = cand
            break

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
        import subprocess
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
                # Sắp xếp theo VRAM giảm dần để lấy card mạnh nhất
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

def process_video_custom(input_path, output_full_path, video_title, settings=None):
    """
    Biên tập Video theo cấu hình Webform Studio:
    - aspect_ratio: 3:4, 9:16, 16:9, 4:3, 1:1
    - blur_bg: True/False
    - hflip: True/False
    - color_boost: True/False
    - banner_box_style: white-rounded, dark-glass, pill-badge, none
    - banner_font: Poppins-Bold, Montserrat-Bold, Arial-Bold
    - banner_font_size: 46
    - banner_position: top, center, bottom
    """
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

    # Xác định kích thước Canvas (W x H)
    canvas_map = {
        "3:4": (1080, 1440),
        "9:16": (1080, 1920),
        "16:9": (1920, 1080),
        "4:3": (1440, 1080),
        "1:1": (1080, 1080)
    }
    canvas_w, canvas_h = canvas_map.get(aspect_ratio, (1080, 1440))

    output_dir = os.path.dirname(output_full_path)
    os.makedirs(output_dir, exist_ok=True)
    banner_png_path = os.path.join(output_dir, "title_banner.png")
    banner_height = create_styled_banner(video_title, banner_png_path, style=banner_style, font_name=banner_font, font_size=banner_font_size, canvas_width=canvas_w)

    # Tính toán tọa độ banner Y
    if banner_pos == "top":
        banner_y = 70 if canvas_h >= 1440 else 35
    elif banner_pos == "center":
        banner_y = f"(H-h)/2 - 120"
    else:  # bottom
        banner_y = f"H - h - 70"

    # Xây dựng FFmpeg Filter Graph
    filters = []
    # 1. Base input filter (lật hoặc tăng màu nếu có)
    pre_filters = []
    if hflip:
        pre_filters.append("hflip")
    if color_boost:
        pre_filters.append("eq=saturation=1.12:contrast=1.05")
    
    pre_filter_str = ("," + ",".join(pre_filters)) if pre_filters else ""

    if blur_bg and aspect_ratio in ["3:4", "9:16", "1:1"]:
        # 2 lớp: nền mờ + video sắc nét ở giữa
        scale_bg = f"scale={canvas_w//4}:{canvas_h//4}:force_original_aspect_ratio=increase,crop={canvas_w//4}:{canvas_h//4},boxblur=luma_radius=6:luma_power=1,scale={canvas_w}:{canvas_h}"
        scale_fg = f"scale={canvas_w}:{int(canvas_w * 0.75)}:force_original_aspect_ratio=decrease" if aspect_ratio == "3:4" else f"scale={canvas_w}:{int(canvas_w * 0.5625)}:force_original_aspect_ratio=decrease"
        
        filter_complex = (
            f"[0:v]{scale_bg}{pre_filter_str}[bg];"
            f"[0:v]{scale_fg}{pre_filter_str}[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[combined];"
            f"[combined][1:v]overlay=0:{banner_y}[v]"
        )
    else:
        # Scale vừa canvas
        filter_complex = (
            f"[0:v]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=decrease,pad={canvas_w}:{canvas_h}:(ow-iw)/2:(oh-ih)/2:black{pre_filter_str}[base];"
            f"[base][1:v]overlay=0:{banner_y}[v]"
        )

    # Lấy cấu hình GPU tối ưu nhất dựa trên VRAM
    gpu_config = get_best_gpu_config()
    best_encoder = gpu_config.get("encoder", "libx264")
    gpu_index = gpu_config.get("gpu_index")
    gpu_name = gpu_config.get("name", "CPU")

    # Thử chạy với GPU, nếu thất bại thì fallback CPU libx264
    def build_cmd(use_gpu=True):
        cmd = [
            FFMPEG_EXE, "-y",
            "-hwaccel", "auto" if use_gpu else "none",
            "-i", input_path,
            "-i", banner_png_path,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "0:a?",
        ]
        if use_gpu and best_encoder != "libx264":
            cmd.extend(["-c:v", best_encoder])
            if best_encoder == "h264_nvenc":
                cmd.extend(["-preset", "p1", "-cq", "28"])
            elif best_encoder == "h264_amf":
                cmd.extend(["-quality", "speed"])
            elif best_encoder == "h264_qsv":
                cmd.extend(["-preset", "veryfast"])
        else:
            cmd.extend(["-c:v", "libx264", "-preset", "veryfast", "-crf", "24"])
        cmd.extend(["-c:a", "copy", output_full_path])
        return cmd

    print(f"🎬 Đang render: {video_title} (Tỉ lệ {aspect_ratio}) bằng {gpu_name}...")
    res = subprocess.run(build_cmd(use_gpu=True), stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    
    if res.returncode != 0:
        print(f"⚠️ GPU {gpu_name} tăng tốc thất bại hoặc không khả dụng, tự động chuyển sang render bằng CPU (libx264)...")
        res_cpu = subprocess.run(build_cmd(use_gpu=False), stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
        if res_cpu.returncode != 0:
            print("❌ Lỗi biên tập video:")
            print(res_cpu.stderr[-400:])
            return False

    print(f"✅ Đã xuất video: {output_full_path}")
    return True

def split_video_custom(edited_file, output_folder, duration, split_mode="auto"):
    """
    Cắt video theo tùy chọn Webform Studio:
    - auto: >12p chia 6, <12p chia 3
    - fixed-3: 3 phần
    - fixed-6: 6 phần
    - no-split: không cắt
    """
    if split_mode == "no-split":
        return [edited_file]

    if split_mode == "fixed-3":
        parts_count = 3
    elif split_mode == "fixed-6":
        parts_count = 6
    else:  # auto
        parts_count = 6 if duration >= 720 else 3

    part_duration = duration / parts_count
    print(f"✂️ Cắt video ({duration:.1f}s) thành {parts_count} phần...")

    split_files = []
    video_title = os.path.basename(output_folder)
    for i in range(parts_count):
        start_time = i * part_duration
        out_part_path = os.path.join(output_folder, f"{video_title} - part {i+1}.mp4")
        cmd = [
            FFMPEG_EXE, "-y",
            "-ss", str(start_time),
            "-i", edited_file,
            "-t", str(part_duration),
            "-c", "copy",
            out_part_path
        ]
        subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        if os.path.exists(out_part_path):
            split_files.append(out_part_path)
            print(f"   + Part {i+1}: {os.path.basename(out_part_path)}")

    return split_files
