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

# Danh sách ký tự tiếng Việt đặc trưng (không bao gồm các dấu tiếng Tây Ban Nha / Bồ Đào Nha)
VIETNAMESE_UNIQUE_CHARS = set(
    "ăằắẳẵặâầấẩẫậđĐêềếểễệơờớởỡợưừứửữự"
    "ĂẰẮẲẴẶÂẦẤẨẪẬÊỀẾỂỄỆƠỜỚỞỠỢƯỪỨỬỮỰ"
    "ảạẻẽẹỉĩịỏọồổỗộủụỳỷỹỵ"
    "ẢẠẺẼẸỈĨỊỎỌỒỔỖỘỦỤỲỶỸỴ"
)

VIETNAMESE_COMMON_WORDS = [
    "cái kết", "bạn nghĩ", "xem ngay", "kỷ lục", "đỉnh cao", "kỹ năng", 
    "thần sầu", "thách đấu", "bài học", "sự thật", "không thể tin", "theo dõi",
    "thả tim", "đừng quên", "phần", "tập", "siêu phẩm", "kịch tính", "hôm nay",
    "cực căng", "đắt giá", "đoạn", "khoảnh khắc", "triệu view", "người", "nhé",
    "xuhuong", "xu hướng", "kẻo lỡ", "xem tiếp", "trọn bộ", "câu chuyện",
    "diễn biến", "tiêu đề", "của", "không", "được", "trong", "cho", "với", "này"
]

def contains_vietnamese(text: str) -> bool:
    """Kiểm tra xem văn bản có chứa ký tự hoặc từ tiếng Việt nào không"""
    if not text:
        return False
    if any(c in VIETNAMESE_UNIQUE_CHARS for c in text):
        return True
    low = f" {text.lower()} "
    for w in VIETNAMESE_COMMON_WORDS:
        if f" {w} " in low or w in low:
            return True
    return False

def detect_video_language(video_title: str, channel_name: str = "") -> str:
    """
    Nhận diện ngôn ngữ mục tiêu của video:
    - 'pt': Portuguese (Brazil, Nobru, v.v.)
    - 'es': Spanish (Mexico, Latin, v.v.)
    - 'en': English (US, UK, Global)
    Tuyệt đối không bao giờ trả về tiếng Việt.
    """
    c_lower = str(channel_name).lower().strip()
    if c_lower in ["nobru", "pizão", "pizao"]:
        return "pt"
    if c_lower in ["love island", "markwiens", "mark wiens", "mrbeast"]:
        return "en"
        
    lower = f" {video_title} {channel_name} ".lower()
    
    # Portuguese indicators
    pt_indicators = [
        " do ", " da ", " dos ", " das ", " no ", " na ", " nos ", " nas ",
        " para ", " com ", " mais ", " não ", " roubam ", " início ", " partida ", " vida ",
        " passa ", " sensi ", " nobru ", " jogando ", " estratégia ", " pizado ", " piza0 ", " pizão "
    ]
    if any(w in lower for w in pt_indicators):
        return "pt"
        
    # Spanish indicators (Hầu hết các kênh meme, roblox, free fire, drama Latin)
    es_indicators = [
        " el ", " la ", " los ", " las ", " de ", " en ", " y ", " que ", " por ", " un ", " una ",
        " con ", " para ", " como ", " pero ", " más ", " mi ", " tu ", " su ", " es ",
        "probé", "robé", "hice", "animé", "estilo", "juego", "conseguí", "cuenta", "mundo",
        "morimos", "hermana", "mamá", "novio", "esposo", "suegra", "boda", "mujer", "hombre",
        "mentira", "verdad", "reflexion", "historia", "refritos", "amiga", "vestido", "ladrón",
        "cuñada", "familia", "triste", "peleó", "lección", "círculo", "último", "pato", "donato",
        "desmentí", "mitos", "traicionaron", "encontré", "chicos", "chicas", "regalen", "soypato",
        "neto", "grequito", "marian", "lópez", "mayfer", "relatos", "confesiones", "suco", "hectorino",
        "¿", "¡", "á", "é", "í", "ó", "ú", "ñ"
    ]
    if any(w in lower for w in es_indicators):
        return "es"
        
    # English indicators
    en_indicators = [
        " the ", " a ", " an ", " of ", " in ", " and ", " to ", " is ", " are ", " was ", " were ",
        " with ", " for ", " on ", " at ", " from ", " by ", " about ", " into ", " through ",
        " love island ", " mark wiens ", " islanders ", " villa ", " kiss ", " bad ",
        " challenge ", " gameplay ", " review ", " guide ", " secret ", " epic ", " how to ",
        " what ", " why ", " who ", " when ", " where ", " managed ", " capital ", " dividing "
    ]
    if any(w in lower for w in en_indicators):
        return "en"
        
    return "es"

def generate_smart_builtin_caption(video_title: str, channel_name: str = "", style: str = "viral") -> dict:
    """
    Bộ Sinh Caption & Hashtags Thông Minh Tích Hợp (Built-in NLP Engine):
    - Hoạt động 100% Offline / Độc lập, không cần bất kỳ API Key nào.
    - Nhận diện Game & Niche thông minh (Roblox, Free Fire, Drama, Meme, Gaming, Story...).
    - TUYỆT ĐỐI KHÔNG TẠO HOOK / TIÊU ĐỀ BẰNG TIẾNG VIỆT: Tự động dùng tiếng Tây Ban Nha (Spanish)
      hoặc tiếng Anh (English) / Bồ Đào Nha (Portuguese) chuẩn bản địa 100%.
    """
    clean_t = re.sub(r'#\S+', '', video_title).strip()
    clean_t = re.sub(r'\s*-\s*part\s*\d+', '', clean_t, flags=re.I).strip()
    clean_t = re.sub(r'[\\/*?:"<>|]', '', clean_t).strip()
    
    # Loại bỏ bất kỳ dấu vết tiếng Việt nếu tiêu đề gốc vô tình dính
    if contains_vietnamese(clean_t):
        clean_t = re.sub(r'[^\x00-\x7F]+', ' ', clean_t).strip()
        
    lang = detect_video_language(video_title, channel_name)
    if not clean_t:
        clean_t = "Momento épico" if lang == "es" else ("Momento insano" if lang == "pt" else "Epic moment")

    lower = (video_title + " " + channel_name).lower()
    
    if lang == "es":
        # SPANISH HOOKS & HASHTAGS (Chuẩn Tây Ban Nha / Mỹ Latinh)
        if any(k in lower for k in ["roblox", "rivals", "blade ball", "bloxfruits", "pato", "romak", "baitomi"]):
            tags = "#roblox #robloxstory #robloxedit #robloxmexico #robloxtiktok #gaming #fyp #parati"
            hook_templates = [
                f"{clean_t} 😱🔥 ¡El final que nadie esperaba!",
                f"¡Nuevo récord en Roblox: {clean_t}! 🤯💥",
                f"{clean_t} 👀 ¡El nivel de habilidad es insano!",
                f"{clean_t} ✨ ¡No te lo puedes perder!"
            ]
        elif any(k in lower for k in ["free fire", "freefire", "suco", "donato", "hectorino", "ely2"]):
            tags = "#freefire #freefirelatino #freefireclips #garenafreefire #freefirelover #gaming #fyp #parati"
            hook_templates = [
                f"{clean_t} 😱🔥 ¡Jugada maestra en Free Fire!",
                f"Duelo épico: {clean_t} 🤯💥",
                f"{clean_t} 🎯 ¡One shot legendario!",
                f"{clean_t} ✨ ¡Mira esta increíble jugada!"
            ]
        elif any(k in lower for k in ["hermana", "mamá", "novio", "esposo", "suegra", "reflexion", "historia", "love", "amor", "marian"]):
            tags = "#historia #reflexiones #historiasreales #drama #amor #viral #parati #fyp"
            hook_templates = [
                f"{clean_t} 💔🥺 La verdad detrás de esta historia...",
                f"¡No lo vas a creer: {clean_t}! 😭✨",
                f"{clean_t} 👀 Una lección para todos nosotros.",
                f"{clean_t} 🎬 ¡Mira el desenlace completo!"
            ]
        else:
            tags = "#viral #parati #fyp #foryou #trending #tiktok #viralvideo"
            hook_templates = [
                f"{clean_t} 😱🔥 ¡Tienes que ver este momento!",
                f"Momento viral: {clean_t} 🤯✨",
                f"{clean_t} 👀 ¿Qué opinas de esto?",
                f"{clean_t} 🚀 ¡Dale like y sígueme para más!"
            ]
    elif lang == "pt":
        # PORTUGUESE HOOKS & HASHTAGS (Brazil / Nobru)
        tags = "#freefire #nobru #brasil #viral #fyp #foryou #trending #tiktok"
        hook_templates = [
            f"{clean_t} 😱🔥 O final que ninguém esperava!",
            f"Momento insano: {clean_t} 🤯💥",
            f"{clean_t} 👀 Assista até o final!",
            f"{clean_t} 🚀 Deixe o like e siga para mais!"
        ]
    else:
        # ENGLISH HOOKS & HASHTAGS (Global / US / UK)
        if any(k in lower for k in ["roblox", "gaming", "game"]):
            tags = "#roblox #robloxgames #gaming #gamingontiktok #fyp #viral #trending"
            hook_templates = [
                f"{clean_t} 😱🔥 The ending nobody expected!",
                f"New record: {clean_t} 🤯💥",
                f"{clean_t} 👀 Insane skills right here!",
                f"{clean_t} ✨ Wait until the end!"
            ]
        elif any(k in lower for k in ["love", "story", "island", "relationship"]):
            tags = "#loveisland #drama #viral #fyp #foryou #trending #tiktok"
            hook_templates = [
                f"{clean_t} 😱🔥 You won't believe what happened!",
                f"Dramatic moment: {clean_t} 🤯✨",
                f"{clean_t} 👀 What are your thoughts on this?",
                f"{clean_t} 🎬 Watch till the very end!"
            ]
        else:
            tags = "#viral #trending #fyp #foryou #foryoupage #tiktok #viralvideo"
            hook_templates = [
                f"{clean_t} 😱🔥 You need to see this moment!",
                f"Viral moment: {clean_t} 🤯✨",
                f"{clean_t} 👀 What do you think about this?",
                f"{clean_t} 🚀 Like and follow for more!"
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
    candidate_chain = []
    if model and model != "builtin" and "3.6" not in model:
        candidate_chain.append(model)
    for m in ["gemini-3-flash-preview", "gemini-3.5-flash", "gemini-2.5-flash"]:
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
    Sinh Caption và Hashtags triệu view cho TikTok với cơ chế Fallback Built-in 100% mượt mà.
    TUYỆT ĐỐI KHÔNG TẠO HOOK HOẶC TIÊU ĐỀ BẰNG TIẾNG VIỆT:
    Cố định 100% bằng ngôn ngữ gốc của video (tiếng Tây Ban Nha, tiếng Anh hoặc Bồ Đào Nha).
    """
    key = clean_api_key(api_key) or get_active_gemini_key()
    lang = detect_video_language(video_title, channel_name)
    target_lang_name = "Spanish" if lang == "es" else ("Portuguese" if lang == "pt" else "English")
    
    # 1. Thử gọi qua API nếu có Key hợp lệ và không chọn model 'builtin'
    if key and model != "builtin" and not key.startswith("AQ."):
        prompt = f"""You are a top viral TikTok content creator.
Create 1 short viral TikTok caption (under 60 words, engaging hook, with emojis) and 5-7 viral hashtags for the following video:
- Video Title: {video_title}
- Channel/Topic: {channel_name}

CRITICAL RULES:
1. ABSOLUTELY NEVER USE VIETNAMESE. Under NO circumstances should any Vietnamese word or character appear.
2. The caption MUST be written purely in {target_lang_name} to match the original video content.
3. DO NOT include "Part 1", "Part 2", or any part numbers in the caption.
4. Keep it engaging, natural, and high-retention.

Output ONLY pure JSON format (no markdown code fences):
{{"caption": "Viral hook and caption in {target_lang_name} 🔥", "hashtags": "#tag1 #tag2 #tag3 #tag4 #tag5"}}"""

        raw_text = ""
        ok = False
        if key.startswith("gsk_"):
            ok, _, raw_text, _ = call_openai_compatible_api(key, "llama-3.3-70b-versatile", prompt)
        elif key.startswith("sk-"):
            ok, _, raw_text, _ = call_openai_compatible_api(key, "gpt-4o-mini", prompt)
        elif key.startswith("AIzaSy"):
            target_m = model if (model and "3.6" not in model and model != "builtin") else "gemini-3-flash-preview"
            ok, _, raw_text, _ = call_single_gemini_model(key, target_m, prompt, timeout=3)
            if not ok:
                ok, _, raw_text, _ = call_single_gemini_model(key, "gemini-2.5-flash", prompt, timeout=3)

        if ok and raw_text:
            try:
                clean_json_str = re.sub(r'```json|```', '', raw_text).strip()
                parsed = json.loads(clean_json_str)
                cand_caption = parsed.get("caption", video_title).strip()
                cand_hashtags = parsed.get("hashtags", "").strip()
                
                # BẢO VỆ TUYỆT ĐỐI CHỐNG TIẾNG VIỆT:
                # Nếu AI vô tình sinh ra tiếng Việt, hủy bỏ ngay kết quả AI và chuyển sang Built-in NLP
                if not contains_vietnamese(cand_caption) and not contains_vietnamese(cand_hashtags):
                    if not cand_hashtags:
                        cand_hashtags = "#viral #parati #fyp" if lang == "es" else "#viral #fyp #trending"
                    return {
                        "success": True,
                        "engine": "Cloud AI",
                        "caption": cand_caption,
                        "hashtags": cand_hashtags
                    }
            except Exception:
                pass

    # 2. Tự động dùng Built-in Smart NLP Engine (100% Hoạt động ngay, không tiếng Việt)
    return generate_smart_builtin_caption(video_title, channel_name, style)
