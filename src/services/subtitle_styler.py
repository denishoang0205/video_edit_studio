import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


def format_ass_time(seconds):
    """Chuyển số giây sang định dạng thời gian ASS: H:MM:SS.cs"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


import html
import re

def clean_sub_text(text):
    """Làm sạch ký hiệu người nói, thực thể HTML và chuẩn hóa câu trước khi nạp vào ASS"""
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\{[^\}]+\}', '', text)
    text = re.sub(r'(?:^|\s)(?:&gt;|>|-){1,3}\s*', ' ', text)
    text = re.sub(r'\[[^\]]+\]', ' ', text)
    text = re.sub(r'\([^\)]+\)', ' ', text)
    text = re.sub(r'^[A-Z0-9_\s]{2,20}:\s*', '', text)
    text = re.sub(r'[\r\n]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def generate_ass_subtitles(segments, output_ass_path, style="tiktok-yellow", canvas_w=1080, canvas_h=1920):
    """
    Tạo tệp phụ đề .ass (Advanced SubStation Alpha) chuyên nghiệp cho TikTok/Shorts:
    - tiktok-yellow: Chữ vàng viền đen dày (Kinh điển TikTok)
    - white-glass: Chữ trắng nền hộp mờ
    - classic: Chữ trắng viền đen tối giản
    """
    dir_path = os.path.dirname(output_ass_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    font_size = 28 if canvas_h >= 1920 else 22
    margin_v = 280 if canvas_h >= 1920 else 180  # Đặt ở vùng an toàn 1/3 dưới, tránh che bởi giao diện TikTok

    # Định nghĩa bảng màu và style ASS
    if style == "tiktok-yellow":
        # Màu vàng BGR: &H0000E5FF& (RGB: #FFE500), Viền đen dày
        primary_color = "&H0000E5FF"
        outline_color = "&H00000000"
        back_color = "&H80000000"
        border_style = 1
        outline = 4.5
        shadow = 2.0
    elif style == "white-glass":
        # Chữ trắng BGR: &H00FFFFFF&, Nền hộp mờ
        primary_color = "&H00FFFFFF"
        outline_color = "&H00000000"
        back_color = "&H99111827"  # Hộp đen mờ #111827
        border_style = 3  # Opaque box
        outline = 2.0
        shadow = 0.0
    else:  # classic
        primary_color = "&H00FFFFFF"
        outline_color = "&H00000000"
        back_color = "&H80000000"
        border_style = 1
        outline = 3.0
        shadow = 1.5

    header = f"""[Script Info]
Title: TikTok Studio Subtitles
ScriptType: v4.00+
PlayResX: {canvas_w}
PlayResY: {canvas_h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TikTokSub,Arial,{font_size},{primary_color},&H000000FF,{outline_color},{back_color},-1,0,0,0,100,100,0.5,0,{border_style},{outline},{shadow},2,50,50,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    for seg in segments:
        text = clean_sub_text(seg.get("text", ""))
        if not text:
            continue
        
        # Ngắt dòng nếu câu dài quá 36 ký tự
        if len(text) > 36:
            words = text.split()
            half = len(words) // 2
            text = " ".join(words[:half]) + "\\N" + " ".join(words[half:])

        start_str = format_ass_time(seg["start"])
        end_str = format_ass_time(seg["end"])
        
        # Text UPPERCASE để bắt mắt đúng chuẩn TikTok
        display_text = text.upper()
        events.append(f"Dialogue: 0,{start_str},{end_str},TikTokSub,,0,0,0,,{display_text}")

    full_ass_content = header + "\n".join(events) + "\n"

    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(full_ass_content)

    return os.path.exists(output_ass_path)


def get_ffmpeg_subtitles_filter(ass_path):
    """Chuẩn hóa đường dẫn file .ass cho bộ lọc FFmpeg subtitles trên Windows"""
    if not ass_path or not os.path.exists(ass_path):
        return ""
    # Trên Windows: C:\path\file.ass -> C\\:/path/file.ass hoặc C\:/path/file.ass
    clean_path = ass_path.replace("\\", "/").replace(":", "\\:")
    return f"subtitles='{clean_path}'"
