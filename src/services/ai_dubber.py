import os
import sys
import asyncio
import subprocess
import edge_tts

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

# Danh mục giọng đọc Neural AI chuẩn cho từng quốc gia
VOICE_CATALOG = {
    "pt-br": {
        "male": "pt-BR-AntonioNeural",
        "female": "pt-BR-FranciscaNeural"
    },
    "es-mx": {
        "male": "es-MX-JorgeNeural",
        "female": "es-MX-DaliaNeural"
    },
    "vi": {
        "male": "vi-VN-NamMinhNeural",
        "female": "vi-VN-HoaiMyNeural"
    },
    "id": {
        "male": "id-ID-ArdiNeural",
        "female": "id-ID-GadisNeural"
    }
}

def resolve_voice(target_lang="pt-br", gender="male"):
    """Lấy mã Voice Neural AI phù hợp theo ngôn ngữ và giới tính"""
    clean_lang = target_lang.lower().replace("_", "-")
    lang_voices = VOICE_CATALOG.get(clean_lang)
    if not lang_voices:
        # Fallback tìm kiếm theo tiền tố
        for k in VOICE_CATALOG:
            if clean_lang.startswith(k[:2]):
                lang_voices = VOICE_CATALOG[k]
                break
    if not lang_voices:
        lang_voices = VOICE_CATALOG["pt-br"]

    return lang_voices.get(gender.lower(), lang_voices.get("male"))

async def generate_segment_tts_async(text, voice, out_path, rate="+0%"):
    """Tạo audio giọng đọc AI cho một câu thoại đơn lẻ"""
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(out_path)
    return os.path.exists(out_path) and os.path.getsize(out_path) > 0

def create_dubbed_audio_track(segments, output_audio_path, target_lang="pt-br", gender="male", total_duration=None, log_cb=None):
    """
    Tạo toàn bộ bản thu lồng tiếng AI đồng bộ theo mốc thời gian (start, end) của video:
    1. Tạo audio cho từng câu thoại.
    2. Ghép các đoạn thoại vào đúng mốc thời gian (Silence padding / delay).
    """
    if log_cb is None:
        log_cb = print

    if not segments:
        return False

    voice = resolve_voice(target_lang, gender)
    log_cb(f"🗣️ Đang tạo giọng đọc AI ({voice}) cho {len(segments)} phân đoạn thoại...")

    temp_dir = os.path.join(os.path.dirname(output_audio_path), "_temp_dub")
    os.makedirs(temp_dir, exist_ok=True)

    segment_audio_files = []

    async def generate_all():
        tasks = []
        for idx, seg in enumerate(segments):
            seg_text = seg.get("text", "").strip()
            if not seg_text:
                continue
            seg_out = os.path.join(temp_dir, f"seg_{idx:04d}.mp3")
            
            # Ước lượng số từ để điều chỉnh tốc độ đọc nếu câu dài mà thời gian ngắn
            target_dur = seg.get("duration", 2.0)
            word_count = len(seg_text.split())
            rate_str = "+0%"
            if target_dur > 0 and word_count > 0:
                words_per_sec = word_count / target_dur
                if words_per_sec > 3.2:
                    rate_str = "+20%"
                elif words_per_sec > 2.6:
                    rate_str = "+10%"
                elif words_per_sec < 1.2:
                    rate_str = "-10%"

            tasks.append((seg, seg_out, rate_str))

        # Thực thi tải song song
        for seg, seg_out, rate_str in tasks:
            await generate_segment_tts_async(seg["text"], voice, seg_out, rate=rate_str)
            if os.path.exists(seg_out):
                segment_audio_files.append((seg["start"], seg_out))

    try:
        asyncio.run(generate_all())
    except Exception as e:
        log_cb(f"⚠️ Lỗi tạo giọng đọc AI: {e}")
        return False

    if not segment_audio_files:
        log_cb("⚠️ Không tạo được tệp âm thanh lồng tiếng nào.")
        return False

    # Dùng FFmpeg filter adelay + amix để ghép nối chính xác tuyệt đối từng câu vào mốc giây (start time)
    inputs = []
    filter_parts = []
    for idx, (st_sec, a_file) in enumerate(segment_audio_files):
        inputs.extend(["-i", a_file])
        delay_ms = int(st_sec * 1000)
        filter_parts.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms}[a{idx}]")

    amix_inputs = "".join([f"[a{idx}]" for idx in range(len(segment_audio_files))])
    filter_complex = f"{';'.join(filter_parts)};{amix_inputs}amix=inputs={len(segment_audio_files)}:normalize=0[aout]"

    cmd = [FFMPEG_EXE, "-y"]
    cmd.extend(inputs)
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-ac", "2",
        "-ar", "44100",
        output_audio_path
    ])

    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    # Dọn dẹp thư mục tạm
    try:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass

    if res.returncode == 0 and os.path.exists(output_audio_path):
        log_cb(f"✅ Hoàn tất tạo Audio Lồng tiếng AI: {os.path.basename(output_audio_path)}")
        return True
    else:
        log_cb("❌ Lỗi ghép nối tệp âm thanh lồng tiếng.")
        return False

def mix_original_and_dubbed_audio(original_video_or_audio, dubbed_audio_path, output_mixed_path, orig_volume=0.12, dub_volume=1.0):
    """
    Audio Ducking: Trộn âm thanh gốc và giọng lồng tiếng AI:
    - Âm thanh gốc hạ nhỏ xuống 12% (làm nền / BGM).
    - Giọng lồng tiếng AI phát to 100%.
    """
    cmd = [
        FFMPEG_EXE, "-y",
        "-i", original_video_or_audio,
        "-i", dubbed_audio_path,
        "-filter_complex",
        f"[0:a]volume={orig_volume}[orig];[1:a]volume={dub_volume}[dub];[orig][dub]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "[aout]",
        "-c:a", "aac",
        "-b:a", "192k",
        output_mixed_path
    ]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    return res.returncode == 0 and os.path.exists(output_mixed_path)
