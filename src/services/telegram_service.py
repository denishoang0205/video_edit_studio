import os
import json
import urllib.request
import urllib.error

def get_active_telegram_config():
    """Lấy cấu hình Telegram bot_token và chat_id từ settings.json hoặc env"""
    bot_token = ""
    chat_id = ""
    enabled = True

    # 1. Từ settings.json
    try:
        from src.services.drive_service import load_settings
        settings = load_settings()
        tg = settings.get("telegram", {})
        bot_token = tg.get("bot_token", "").strip()
        chat_id = str(tg.get("chat_id", "")).strip()
        enabled = tg.get("enabled", True)
    except Exception:
        pass

    # 2. Fallback sang biến môi trường
    if not bot_token:
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not chat_id:
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    return {
        "bot_token": bot_token,
        "chat_id": chat_id,
        "enabled": enabled
    }

def send_telegram_message(message: str, bot_token: str = None, chat_id: str = None, parse_mode: str = "HTML"):
    """Gửi thông báo tin nhắn văn bản đến Telegram"""
    cfg = get_active_telegram_config()
    token = bot_token or cfg.get("bot_token")
    cid = chat_id or cfg.get("chat_id")

    if not token or not cid:
        return False, "Thiếu Telegram Bot Token hoặc Chat ID"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    headers = {"Content-Type": "application/json"}
    payload = {
        "chat_id": cid,
        "text": message,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return True, "Gửi tin nhắn Telegram thành công!"
            return False, f"Telegram API Error: {data.get('description', 'Unknown error')}"
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return False, f"Lỗi HTTP {e.code}: {err_msg}"
    except Exception as e:
        return False, f"Lỗi gửi Telegram: {str(e)}"

def test_telegram_connection(bot_token: str, chat_id: str):
    """Gửi tin nhắn kiểm tra kết nối Telegram"""
    if not bot_token or not chat_id:
        return False, "Vui lòng nhập đầy đủ Bot Token và Chat ID"
    
    test_msg = """<b>🤖 [TikTok Studio Pro] KIỂM TRA KẾT NỐI TELEGRAM THÀNH CÔNG!</b>
━━━━━━━━━━━━━━━━━━━━
✅ <b>Trạng thái:</b> Đã kết nối với TikTok Automation Hub!
⏰ <b>Thời gian:</b> Hệ thống đã sẵn sàng nhận thông báo tự động khi xuất bản video.
🔒 <b>Bảo mật:</b> Bot Token của bạn được mã hóa an toàn trên máy cục bộ."""
    
    return send_telegram_message(test_msg, bot_token=bot_token, chat_id=chat_id)
