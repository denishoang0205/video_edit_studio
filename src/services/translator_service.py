import sys
import time
from deep_translator import GoogleTranslator

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Bản đồ mã ngôn ngữ chuẩn cho deep_translator
LANG_CODE_MAP = {
    "pt-br": "pt",
    "pt": "pt",
    "brazil": "pt",
    "es-mx": "es",
    "es": "es",
    "mexico": "es",
    "vi": "vi",
    "vietnam": "vi",
    "id": "id",
    "indonesia": "id"
}

def translate_segments(segments, target_lang="pt-br", source_lang="en", log_cb=None):
    """
    Dịch danh sách các đoạn thoại sang ngôn ngữ đích (Brazil, Mexico, Vietnam...)
    Giữ nguyên cấu trúc mốc thời gian (start, end, duration).
    """
    if log_cb is None:
        log_cb = print

    if not segments:
        return []

    clean_target = LANG_CODE_MAP.get(target_lang.lower(), "pt")
    if clean_target == source_lang:
        return segments

    log_cb(f"🌍 Đang dịch {len(segments)} câu thoại sang ngôn ngữ mục tiêu: {target_lang.upper()}...")
    
    translator = GoogleTranslator(source=source_lang, target=clean_target)
    translated_segments = []

    # Dịch theo lô (Batch) hoặc từng câu có xử lý lỗi & retry
    for idx, seg in enumerate(segments):
        orig_text = seg.get("text", "").strip()
        if not orig_text:
            continue

        trans_text = orig_text
        try:
            trans_text = translator.translate(orig_text)
        except Exception as e:
            try:
                time.sleep(0.5)
                trans_text = GoogleTranslator(source="auto", target=clean_target).translate(orig_text)
            except Exception:
                trans_text = orig_text

        translated_segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "duration": seg["duration"],
            "original_text": orig_text,
            "text": trans_text
        })

    log_cb(f"✅ Hoàn tất dịch thuật {len(translated_segments)} câu thoại.")
    return translated_segments
