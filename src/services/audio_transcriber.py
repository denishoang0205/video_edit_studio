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


import html

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
    """Loại bỏ thẻ HTML, thực thể HTML (&gt;), ký hiệu người nói (>>, Speaker:, [Music]) và chuẩn hóa khoảng trắng"""
    if not text:
        return ""
    # 1. Giải mã thực thể HTML (&gt; -> >, &amp; -> &, &quot; -> ", v.v.)
    text = html.unescape(text)
    # 2. Xóa thẻ WebVTT/HTML <...> và {...}
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\{[^\}]+\}', '', text)
    # 3. Xóa các ký hiệu chỉ định người nói của YouTube và phim ảnh
    text = re.sub(r'(?:^|\s)(?:&gt;|>|-){1,3}\s*', ' ', text)
    text = re.sub(r'\[[^\]]+\]', ' ', text)  # [Music], [Applause]
    text = re.sub(r'\([^\)]+\)', ' ', text)  # (laughing), (cheers)
    text = re.sub(r'^[A-Z0-9_\s]{2,20}:\s*', '', text)  # JOHN:, SPEAKER 1:
    text = re.sub(r'[\r\n]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_vtt_or_srt(sub_path):
    """
    Đọc và chuyển đổi tệp WebVTT hoặc SRT thành danh sách timed segments sạch sẽ:
    - Loại bỏ triệt để hiện tượng lặp lại dòng (rolling cues) của YouTube WebVTT.
    - Xóa sạch ký tự người nói (>>, >) và các thẻ âm thanh nền ([Music], [Applause]).
    - Gom nhóm các câu thoại tự nhiên, ngắn gọn (4-8 từ/phân đoạn), chuẩn nhịp TikTok.
    """
    if not os.path.exists(sub_path):
        return []

    with open(sub_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    cue_pattern = re.compile(
        r'(?:(\d+)\s*\n)?'
        r'(\d{1,2}:\d{2}:\d{2}[,\.]\d{2,3}|\d{2}:\d{2}[,\.]\d{2,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{2,3}|\d{2}:\d{2}[,\.]\d{2,3})[^\n]*\n'
        r'([\s\S]*?)(?=\n\s*(?:\d+\s*\n)?\d{1,2}:\d{2}:\d{2}[,\.]|\n\s*\n\s*$|\Z)',
        re.MULTILINE
    )

    # 1. Bóc tách danh sách từ kèm mốc thời gian chi tiết
    timed_words = []
    
    for match in cue_pattern.finditer(content):
        _, start_str, end_str, text_raw = match.groups()
        cue_start = parse_timestamp(start_str)
        cue_end = parse_timestamp(end_str)
        
        lines = text_raw.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Xử lý cue có karaoke timestamps <00:00:00.000><c> word</c>
            if '<' in line and '>' in line:
                tokens = re.findall(r'(?:<(\d{1,2}:\d{2}:\d{2}[,\.]\d{3})>)?(?:<c>)?([^<]+)(?:</c>)?', line)
                current_time = cue_start
                for ts_match, word in tokens:
                    if ts_match:
                        current_time = parse_timestamp(ts_match)
                    w_clean = clean_subtitle_text(word)
                    if w_clean:
                        for sub_w in w_clean.split():
                            timed_words.append((round(current_time, 2), sub_w))
            else:
                # Xử lý dòng tĩnh (chống trùng lặp với các từ vừa nạp)
                clean_static = clean_subtitle_text(line)
                if clean_static:
                    words = clean_static.split()
                    recent_words = " ".join([w[1] for w in timed_words[-len(words):]]) if timed_words else ""
                    if recent_words.lower() != clean_static.lower():
                        dur_per_word = (cue_end - cue_start) / max(1, len(words))
                        for i, w in enumerate(words):
                            timed_words.append((round(cue_start + i * dur_per_word, 2), w))

    # 2. Khử trùng lặp các từ phát sinh liên tiếp trong khoảng thời gian hẹp
    deduped_words = []
    for t, w in timed_words:
        if deduped_words and deduped_words[-1][1].lower() == w.lower() and abs(deduped_words[-1][0] - t) < 0.35:
            continue
        deduped_words.append((t, w))

    if not deduped_words:
        return []

    # 3. Gom nhóm từ thành các phân đoạn phụ đề ngắn gọn, chuẩn nhịp TikTok
    segments = []
    curr_chunk = []
    curr_start = 0.0
    
    for t, w in deduped_words:
        if not curr_chunk:
            curr_start = t
            curr_chunk.append(w)
        else:
            curr_chunk.append(w)
            chunk_text = " ".join(curr_chunk)
            dur = t - curr_start
            
            # Điều kiện ngắt phân đoạn:
            # - Kết thúc câu bằng dấu chấm, hỏi, than (. ! ?)
            # - Hoặc đạt 6-8 từ hoặc thời lượng >= 3.0s
            # - Hoặc dấu phẩy khi đã có từ 4 từ trở lên
            if w.endswith(('.', '!', '?')) or len(curr_chunk) >= 7 or dur >= 3.0 or (w.endswith(',') and len(curr_chunk) >= 4):
                segments.append({
                    "start": curr_start,
                    "end": round(t + 0.5, 2),
                    "duration": round(t + 0.5 - curr_start, 2),
                    "text": chunk_text
                })
                curr_chunk = []
                
    if curr_chunk:
        segments.append({
            "start": curr_start,
            "end": round(curr_start + 1.8, 2),
            "duration": 1.8,
            "text": " ".join(curr_chunk)
        })
        
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
