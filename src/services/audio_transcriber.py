import os
import sys
import re
import subprocess
import json

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    from src.core.config import FFMPEG_EXE
except ImportError:
    from config import FFMPEG_EXE


def parse_timestamp(ts_str):
    """Chuyển chuỗi timestamp (00:01:23.456 hoặc 00:01:23,456) sang số giây (float)"""
    ts_str = ts_str.strip().replace(',', '.')
    parts = ts_str.split(':')
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


def clean_subtitle_text(text):
    """Loại bỏ thẻ HTML, định dạng WebVTT thừa và chuẩn hóa khoảng trắng"""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\{[^\}]+\}', '', text)
    text = re.sub(r'[\r\n]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_vtt_or_srt(sub_path):
    """Đọc và chuyển đổi tệp WebVTT hoặc SRT thành danh sách timed segments"""
    if not os.path.exists(sub_path):
        return []

    segments = []
    with open(sub_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    pattern = re.compile(
        r'(?:(\d+)\s*\n)?'
        r'(\d{1,2}:\d{2}:\d{2}[,\.]\d{2,3}|\d{2}:\d{2}[,\.]\d{2,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{2,3}|\d{2}:\d{2}[,\.]\d{2,3})[^\n]*\n'
        r'([\s\S]*?)(?=\n\s*(?:\d+\s*\n)?\d{1,2}:\d{2}:\d{2}[,\.]|\n\s*\n\s*$|\Z)',
        re.MULTILINE
    )

    last_text = ""
    for match in pattern.finditer(content):
        _, start_str, end_str, text_raw = match.groups()
        start = parse_timestamp(start_str)
        end = parse_timestamp(end_str)
        text = clean_subtitle_text(text_raw)

        if not text or text == last_text:
            continue

        if segments and (start - segments[-1]["end"]) <= 0.4 and len(segments[-1]["text"].split()) < 12 and not segments[-1]["text"].endswith(('.', '!', '?')):
            segments[-1]["end"] = end
            segments[-1]["text"] = f"{segments[-1]['text']} {text}"
            last_text = text
        else:
            segments.append({
                "start": round(start, 2),
                "end": round(end, 2),
                "duration": round(end - start, 2),
                "text": text
            })
            last_text = text

    return segments


def find_subtitle_for_video(video_path):
    """Tìm kiếm file phụ đề đi kèm video (.vtt, .srt, .en.vtt, .en.srt)"""
    if not video_path:
        return None

    base_without_ext = os.path.splitext(video_path)[0]
    folder = os.path.dirname(video_path)

    candidates = [
        f"{base_without_ext}.en.vtt",
        f"{base_without_ext}.en.srt",
        f"{base_without_ext}.vtt",
        f"{base_without_ext}.srt",
        f"{base_without_ext}.en-orig.vtt",
        f"{base_without_ext}.en-US.vtt"
    ]

    for cand in candidates:
        if os.path.exists(cand) and os.path.getsize(cand) > 0:
            return cand

    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.endswith(('.vtt', '.srt')) and not f.startswith(('part_', 'edited_')):
                full_p = os.path.join(folder, f)
                if os.path.getsize(full_p) > 0:
                    return full_p

    return None


def extract_audio_segment(video_path, output_audio_path, start_time=None, duration=None):
    """Trích xuất âm thanh từ video sang định dạng WAV 16kHz mono phục vụ xử lý AI"""
    os.makedirs(os.path.dirname(output_audio_path), exist_ok=True)
    cmd = [FFMPEG_EXE, "-y"]
    if start_time is not None and start_time > 0:
        cmd.extend(["-ss", str(start_time)])
    cmd.extend(["-i", video_path])
    if duration is not None and duration > 0:
        cmd.extend(["-t", str(duration)])
    cmd.extend([
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_audio_path
    ])
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    return res.returncode == 0 and os.path.exists(output_audio_path)


def transcribe_video_audio(video_path, start_time=None, duration=None, log_cb=None):
    """Trích xuất danh sách câu thoại kèm mốc thời gian"""
    if log_cb is None:
        log_cb = print

    sub_file = find_subtitle_for_video(video_path)
    if sub_file:
        log_cb(f"📄 Tìm thấy phụ đề gốc: {os.path.basename(sub_file)}")
        all_segs = parse_vtt_or_srt(sub_file)
        
        if start_time is not None or duration is not None:
            st = start_time or 0.0
            et = st + duration if duration is not None else 999999.0
            filtered = []
            for s in all_segs:
                if s["end"] > st and s["start"] < et:
                    rel_start = max(0.0, round(s["start"] - st, 2))
                    rel_end = min(round(et - st, 2), round(s["end"] - st, 2))
                    if rel_end > rel_start:
                        filtered.append({
                            "start": rel_start,
                            "end": rel_end,
                            "duration": round(rel_end - rel_start, 2),
                            "text": s["text"]
                        })
            return filtered
        return all_segs

    return []
