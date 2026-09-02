import os
import json
import re
import urllib.request
import urllib.error

def clean_api_key(key: str) -> str:
    """Làm sạch chuỗi API key khỏi khoảng trắng và dấu ngoặc kép thừa khi copy-paste"""
    if not key:
        return ""
    return str(key).strip().strip('"').strip("'").strip()

def get_active_gemini_key() -> str:
    """Lấy API Key từ data/settings.json hoặc biến môi trường"""
    try:
        from src.services.drive_service import load_settings
        settings = load_settings()
        key = clean_api_key(settings.get("gemini", {}).get("api_key", ""))
        if key:
            return key
    except Exception:
        pass
    return clean_api_key(os.environ.get("GEMINI_API_KEY", ""))

def generate_smart_builtin_caption(video_title: str, channel_name: str = "", style: str = "viral") -> dict:
    """
    Bộ Sinh Caption & Hashtags Thông Minh Tích Hợp (Built-in NLP Engine):
    - Hoạt động 100% Offline / Độc lập, không cần bất kỳ API Key nào.
    - Nhận diện Game & Niche thông minh (Roblox, Free Fire, Drama, Meme, Gaming, Story...).
    - Tự động tạo Hook cuốn hút + CTA + 6-8 Hashtags triệu view chuẩn SEO TikTok.
    """
    clean_t = re.sub(r'#\S+', '', video_title).strip()
    clean_t = re.sub(r'\s*-\s*part\s*\d+', '', clean_t, flags=re.I).strip()
    clean_t = re.sub(r'[\\/*?:"<>|]', '', clean_t).strip()
    if not clean_t:
        clean_t = "Siêu phẩm kịch tính hôm nay"

    lower = (video_title + " " + channel_name).lower()
    
    # Nhận diện Niche & Bộ Hashtag tương ứng
    if any(k in lower for k in ["roblox", "rivals", "blade ball", "bloxfruits", "pato", "romak", "baitomi"]):
        tags = "#roblox #robloxstory #robloxedit #robloxmexico #robloxtiktok #gaming #fyp"
        hook_templates = [
            f"{clean_t} 😱🔥 Cái kết không ai ngờ tới!",
            f"Kỷ lục mới trong Roblox: {clean_t} 🤯💥",
            f"{clean_t} 👀 Đỉnh cao kỹ năng là đây!",
            f"{clean_t} ✨ Xem ngay kẻo lỡ!"
        ]
    elif any(k in lower for k in ["free fire", "freefire", "suco", "donato", "hectorino", "ely2"]):
        tags = "#freefire #freefirelatino #freefireclips #garenafreefire #freefirelover #gaming #fyp"
        hook_templates = [
            f"{clean_t} 😱🔥 Pha xử lý thần sầu trong Free Fire!",
            f"Thách đấu cực căng: {clean_t} 🤯💥",
            f"{clean_t} 🎯 One shot đỉnh cao!",
            f"{clean_t} ✨ Theo dõi để xem tiếp phần sau!"
        ]
    elif any(k in lower for k in ["hermana", "mamá", "novio", "esposo", "suegra", "reflexion", "historia", "love", "bạn trai", "mẹ chồng"]):
        tags = "#historia #reflexiones #historiasreales #drama #amor #viral #parati"
        hook_templates = [
            f"{clean_t} 💔🥺 Sự thật đằng sau câu chuyện...",
            f"Không thể tin được: {clean_t} 😭✨",
            f"{clean_t} 👀 Bài học đắt giá cho tất cả chúng ta!",
            f"{clean_t} 🎬 Theo dõi trọn bộ diễn biến!"
        ]
    else:
        tags = "#viral #trending #fyp #foryou #xuhuong #tiktok #viralvideo"
        hook_templates = [
            f"{clean_t} 😱🔥 Xem ngay phân đoạn kịch tính này!",
            f"Khoảnh khắc triệu view: {clean_t} 🤯✨",
            f"{clean_t} 👀 Bạn nghĩ sao về điều này?",
            f"{clean_t} 🚀 Đừng quên thả tim và follow nhé!"
        ]

    # Chọn hook phù hợp theo độ dài tiêu đề
    selected_caption = hook_templates[len(clean_t) % len(hook_templates)]

    return {
        "success": True,
        "engine": "Built-in Smart NLP Engine",
        "caption": selected_caption,
        "hashtags": tags
    }

def call_openai_compatible_api(api_key: str, model_name: str, prompt: str, endpoint: str = "https://api.groq.com/openai/v1/chat/completions", timeout: int = 8):
    """
    Gọi các API chuẩn OpenAI (Groq, OpenRouter, DeepSeek, OpenAI)
    """
    clean_key = clean_api_key(api_key)
    if not clean_key:
        return False, "Chưa cung cấp API Key", "", model_name

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {clean_key}"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a professional viral TikTok caption generator. Output only pure JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return True, "Thành công", text.strip(), model_name
    except Exception as e:
        return False, str(e), "", model_name

def call_single_gemini_model(api_key: str, model_name: str, prompt: str, timeout: int = 8):
    """
    Gọi trực tiếp Google Generative Language REST API
    """
    clean_key = clean_api_key(api_key)
    clean_model = model_name.strip().replace("models/", "")

    if not clean_key:
        return False, "Chưa cung cấp API Key", "", clean_model

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={clean_key}"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": clean_key
    }
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return True, "Thành công", text.strip(), clean_model
    except urllib.error.HTTPError as e:
        err_raw = e.read().decode("utf-8", errors="ignore")
        return False, f"HTTP {e.code}: {err_raw[:150]}", "", clean_model
    except Exception as e:
        return False, str(e), "", clean_model

def test_gemini_api(api_key: str, model: str = "gemini-3.6-flash"):
    """
    Kiểm tra kết nối với hệ thống AI Caption
    """
    clean_key = clean_api_key(api_key)

    # 1. Nếu không có key hoặc chọn built-in
    if not clean_key or model == "builtin" or clean_key.lower() == "builtin":
        sample = generate_smart_builtin_caption("Conseguí TODO en Roblox Rivals!", "baitomiTV")
        return True, f"🎉 Đã kích hoạt Bộ Sinh Caption & Hashtags Thông Minh Tích Hợp (Built-in NLP Engine) — Sẵn sàng 100% không cần Key! Mẫu sinh: '{sample['caption']}'"

    # 2. Nếu là Groq API Key (gsk_...)
    if clean_key.startswith("gsk_"):
        ok, msg, text, m = call_openai_compatible_api(clean_key, "llama-3.3-70b-versatile", "Respond with 'OK - Groq is connected' only.")
        if ok:
            return True, f"🎉 Kết nối Groq AI (Llama 3.3) thành công! Phản hồi: '{text}'"
        return False, f"Không thể kết nối Groq: {msg}"

    # 3. Nếu là OpenAI / OpenRouter Key (sk-...)
    if clean_key.startswith("sk-"):
        endpoint = "https://openrouter.ai/api/v1/chat/completions" if "or" in clean_key else "https://api.openai.com/v1/chat/completions"
        ok, msg, text, m = call_openai_compatible_api(clean_key, "gpt-4o-mini", "Respond with 'OK - AI connected' only.", endpoint=endpoint)
        if ok:
            return True, f"🎉 Kết nối AI Provider thành công! Phản hồi: '{text}'"
        return False, f"Không thể kết nối: {msg}"

    # 4. Nếu là Google Gemini Key (Hỗ trợ hoàn hảo cả AQ... và AIzaSy...)
    candidate_chain = [model] if model and model != "builtin" else []
    for m in ["gemini-3.6-flash", "gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.7-flash", "gemini-2.5-flash"]:
        if m not in candidate_chain:
            candidate_chain.append(m)

    last_err = ""
    for m in candidate_chain:
        ok, msg, text, used_m = call_single_gemini_model(clean_key, m, "Hello, respond with 'OK - Gemini is connected' only.")
        if ok and text:
            return True, f"🎉 Kết nối Google Gemini thành công [{used_m}]! Phản hồi: '{text}'"
        last_err = msg

    return False, f"Không thể kết nối Gemini: {last_err}"

def generate_tiktok_caption(video_title: str, channel_name: str = "", api_key: str = None, model: str = None, style: str = "viral"):
    """
    Sinh Caption và Hashtags triệu view cho TikTok với cơ chế Fallback Built-in 100% mượt mà
    """
    key = clean_api_key(api_key) or get_active_gemini_key()
    
    # 1. Thử gọi qua API nếu có Key hợp lệ
    if key:
        prompt = f"""Bạn là chuyên gia sáng tạo nội dung TikTok. Tạo 1 Caption ngắn (dưới 80 từ, có emoji) và 5-7 Hashtags triệu view cho video TikTok sau:
- Tiêu đề: {video_title}
- Kênh/Chủ đề: {channel_name}
Định dạng JSON thuần: {{"caption": "Nội dung caption 🔥", "hashtags": "#tag1 #tag2 #tag3 #tag4 #tag5"}}"""

        raw_text = ""
        if key.startswith("gsk_"):
            ok, _, raw_text, _ = call_openai_compatible_api(key, "llama-3.3-70b-versatile", prompt)
        elif key.startswith("sk-"):
            ok, _, raw_text, _ = call_openai_compatible_api(key, "gpt-4o-mini", prompt)
        else:
            # Gemini (Hỗ trợ cả AQ... và AIzaSy...)
            candidate_chain = [model] if model and model != "builtin" else []
            for m in ["gemini-3.6-flash", "gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.7-flash", "gemini-2.5-flash"]:
                if m not in candidate_chain:
                    candidate_chain.append(m)
            
            for m in candidate_chain:
                ok, _, raw_text, _ = call_single_gemini_model(key, m, prompt)
                if ok and raw_text:
                    break

        if ok and raw_text:
            try:
                clean_json_str = re.sub(r'```json|```', '', raw_text).strip()
                parsed = json.loads(clean_json_str)
                return {
                    "success": True,
                    "engine": "Cloud AI",
                    "caption": parsed.get("caption", video_title),
                    "hashtags": parsed.get("hashtags", "#fyp #viral #trending")
                }
            except Exception:
                pass

    # 2. Tự động dùng Built-in Smart NLP Engine (100% Hoạt động ngay, không cần Key)
    return generate_smart_builtin_caption(video_title, channel_name, style)
