import urllib.request
import urllib.parse
import urllib.error
import json
import time

DEFAULT_ADSPOWER_URL = "http://local.adspower.net:50325"

def get_default_adspower_config():
    try:
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cand_files = [
            os.path.join(base_dir, "data", "settings.json"),
            os.path.join(base_dir, "settings.json"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
        ]
        for sett_file in cand_files:
            if os.path.exists(sett_file):
                with open(sett_file, "r", encoding="utf-8") as f:
                    st = json.load(f)
                    ads = st.get("adspower", {})
                    if ads.get("api_key") or ads.get("api_url"):
                        return ads.get("api_url", DEFAULT_ADSPOWER_URL), ads.get("api_key", "")
    except Exception:
        pass
    return DEFAULT_ADSPOWER_URL, ""

def clean_api_url(url):
    if not url:
        default_url, _ = get_default_adspower_config()
        return default_url or DEFAULT_ADSPOWER_URL
    url = url.strip().rstrip('/')
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
    return url

def _make_request(endpoint_url, api_key="", timeout=10):
    if not api_key:
        _, api_key = get_default_adspower_config()
        
    headers = {
        "User-Agent": "TikTok-Studio-Pro/1.0",
        "Accept": "application/json"
    }
    if api_key:
        headers["api-key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
        
    req = urllib.request.Request(endpoint_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content = response.read().decode('utf-8')
            return json.loads(content)
    except urllib.error.URLError as e:
        return {"code": -1, "msg": f"Không thể kết nối đến AdsPower API: {str(e)}"}
    except Exception as e:
        return {"code": -1, "msg": f"Lỗi gọi AdsPower API: {str(e)}"}


def check_adspower_status(api_url=DEFAULT_ADSPOWER_URL, api_key=""):
    """
    Kiểm tra trạng thái hoạt động của AdsPower Local API
    """
    base_url = clean_api_url(api_url)
    url = f"{base_url}/status"
    res = _make_request(url, api_key, timeout=5)
    
    if res.get("code") == 0 or res.get("status") == "Active":
        return {
            "connected": True,
            "message": "AdsPower Local API đang hoạt động tốt!",
            "data": res.get("data", {})
        }
    return {
        "connected": False,
        "message": res.get("msg", "Không thể kết nối tới AdsPower. Hãy đảm bảo ứng dụng AdsPower đang mở và Local API đã được bật.")
    }

def get_adspower_profiles(api_url=DEFAULT_ADSPOWER_URL, api_key="", page=1, page_size=100):
    """
    Lấy danh sách các hồ sơ (Profiles / Environments) trên AdsPower
    """
    base_url = clean_api_url(api_url)
    params = urllib.parse.urlencode({"page": page, "page_size": page_size})
    url = f"{base_url}/api/v1/user/list?{params}"
    
    res = _make_request(url, api_key, timeout=8)
    if res.get("code") == 0:
        raw_list = res.get("data", {}).get("list", [])
        profiles = []
        for item in raw_list:
            profiles.append({
                "user_id": item.get("user_id", ""),
                "serial_number": str(item.get("serial_number", "")),
                "name": item.get("name", item.get("username", "")),
                "group_name": item.get("group_name", "Default"),
                "ip": item.get("ip", ""),
                "country": item.get("country", ""),
                "remark": item.get("remark", "")
            })
        return {
            "success": True,
            "profiles": profiles,
            "total": res.get("data", {}).get("total", len(profiles))
        }
    return {
        "success": False,
        "error": res.get("msg", "Lỗi khi lấy danh sách profile AdsPower"),
        "profiles": []
    }

def resolve_profile_identifier(profile_identifier, api_url=DEFAULT_ADSPOWER_URL, api_key=""):
    """
    Phân giải định danh profile (Tên, User ID, hoặc Serial) thành User ID chuẩn của AdsPower
    """
    ident = str(profile_identifier).strip()
    if not ident:
        return ""
        
    # Lấy danh sách profiles từ AdsPower
    profiles_res = get_adspower_profiles(api_url, api_key)
    if profiles_res.get("success"):
        profiles = profiles_res.get("profiles", [])
        
        # 1. Khớp chính xác user_id
        for p in profiles:
            if p.get("user_id") == ident:
                return p.get("user_id")
                
        # 2. Khớp chính xác serial_number
        for p in profiles:
            if str(p.get("serial_number")) == ident:
                return p.get("user_id")
                
        # 3. Khớp chính xác name (không phân biệt hoa thường)
        for p in profiles:
            if p.get("name", "").lower() == ident.lower():
                return p.get("user_id")
                
        # 4. Khớp chứa chuỗi tên (tên profile chứa ident hoặc ngược lại)
        for p in profiles:
            p_name = p.get("name", "").lower()
            i_name = ident.lower()
            if p_name and (i_name in p_name or p_name in i_name):
                return p.get("user_id")
                
    return ident

def start_adspower_browser(profile_identifier, api_url=DEFAULT_ADSPOWER_URL, api_key="", open_tabs=1, headless=False):
    """
    Khởi chạy trình duyệt AdsPower tương ứng với Profile ID, Serial Number hoặc Profile Name
    Hỗ trợ chế độ headless (chạy ngầm không hiện cửa sổ) để lấy dữ liệu siêu tốc.
    """
    if not profile_identifier:
        return {"success": False, "error": "Chưa chọn Profile ID / Serial Number của AdsPower"}
        
    base_url = clean_api_url(api_url)
    raw_ident = str(profile_identifier).strip()
    
    # Phân giải định danh thành user_id chuẩn nếu là profile name
    resolved_id = resolve_profile_identifier(raw_ident, api_url, api_key)
    
    query = {"open_tabs": open_tabs}
    if headless:
        query["headless"] = "1"
        
    if resolved_id.isdigit() and len(resolved_id) <= 6:
        query["serial_number"] = resolved_id
    else:
        query["user_id"] = resolved_id
        
    params = urllib.parse.urlencode(query)
    url = f"{base_url}/api/v1/browser/start?{params}"
    
    res = _make_request(url, api_key, timeout=20)
    if res.get("code") == 0:
        data = res.get("data", {})
        ws_endpoint = data.get("ws", {}).get("puppeteer", "")
        debug_port = data.get("debug_port", "")
        webdriver_path = data.get("webdriver", "")
        
        # Nếu chưa có ws_endpoint nhưng có debug_port, tạo ws URL chuẩn
        if not ws_endpoint and debug_port:
            ws_endpoint = f"http://127.0.0.1:{debug_port}"
            
        return {
            "success": True,
            "ws_endpoint": ws_endpoint,
            "debug_port": debug_port,
            "webdriver": webdriver_path,
            "profile_id": resolved_id,
            "data": data
        }
        
    # Thử lại lần cuối với serial nếu raw_ident là số
    if raw_ident != resolved_id and raw_ident.isdigit():
        params = urllib.parse.urlencode({"serial_number": raw_ident, "open_tabs": open_tabs})
        res2 = _make_request(f"{base_url}/api/v1/browser/start?{params}", api_key, timeout=20)
        if res2.get("code") == 0:
            data = res2.get("data", {})
            return {
                "success": True,
                "ws_endpoint": data.get("ws", {}).get("puppeteer", "") or f"http://127.0.0.1:{data.get('debug_port', '')}",
                "debug_port": data.get("debug_port", ""),
                "webdriver": data.get("webdriver", ""),
                "profile_id": raw_ident,
                "data": data
            }
            
    return {
        "success": False,
        "error": res.get("msg", f"Lỗi khởi chạy profile AdsPower '{profile_identifier}'")
    }

def stop_adspower_browser(profile_identifier, api_url=DEFAULT_ADSPOWER_URL, api_key=""):
    """
    Đóng trình duyệt AdsPower đang mở
    """
    if not profile_identifier:
        return {"success": False, "error": "Chưa chỉ định Profile AdsPower"}
        
    base_url = clean_api_url(api_url)
    resolved_id = resolve_profile_identifier(str(profile_identifier).strip(), api_url, api_key)
    
    query = {}
    if resolved_id.isdigit() and len(resolved_id) <= 6:
        query["serial_number"] = resolved_id
    else:
        query["user_id"] = resolved_id
        
    params = urllib.parse.urlencode(query)
    url = f"{base_url}/api/v1/browser/stop?{params}"
    
    res = _make_request(url, api_key, timeout=10)
    return {
        "success": res.get("code") == 0,
        "message": res.get("msg", "")
    }


def is_browser_active(profile_identifier, api_url=DEFAULT_ADSPOWER_URL, api_key=""):
    """
    Kiểm tra xem profile AdsPower này có đang chạy browser hay không
    """
    if not profile_identifier:
        return False
        
    base_url = clean_api_url(api_url)
    ident = str(profile_identifier).strip()
    
    query = {}
    if ident.isdigit() and len(ident) <= 6:
        query["serial_number"] = ident
    else:
        query["user_id"] = ident
        
    params = urllib.parse.urlencode(query)
    url = f"{base_url}/api/v1/browser/active?{params}"
    
    res = _make_request(url, api_key, timeout=5)
    if res.get("code") == 0:
        return res.get("data", {}).get("status") == "Active"
    return False
