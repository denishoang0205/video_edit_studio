import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.error

# Các đường dẫn mặc định thường gặp của HMA VPN trên Windows
COMMON_HMA_PATHS = [
    r"C:\Program Files\Privax\HMA VPN\Vpn.exe",
    r"C:\Program Files (x86)\Privax\HMA VPN\Vpn.exe",
    r"C:\Program Files\Privax\HMA VPN\bin\HMA.exe",
    r"C:\Program Files (x86)\Privax\HMA VPN\bin\HMA.exe",
    r"C:\Program Files\Privax\HMA! Pro VPN\bin\HMA.exe",
    r"C:\Program Files (x86)\Privax\HMA! Pro VPN\bin\HMA.exe",
    r"C:\Program Files\HMA VPN\hma-vpn.exe",
    r"C:\Program Files (x86)\HMA VPN\hma-vpn.exe",
    r"C:\Program Files\HMA VPN\bin\hma-vpn.exe",
    r"C:\Program Files\HideMyAss\HMA.exe",
    r"C:\Program Files (x86)\HideMyAss\HMA.exe",
]

def find_hma_executable():
    """Tự động tìm kiếm file thực thi của HMA VPN trên hệ thống"""
    # 1. Kiểm tra danh sách đường dẫn cố định
    for path in COMMON_HMA_PATHS:
        if os.path.exists(path) and os.path.isfile(path):
            return path
            
    # 2. Kiểm tra theo biến môi trường ProgramFiles
    prog_files = [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("LOCALAPPDATA", "")
    ]
    for pf in prog_files:
        if not pf:
            continue
        for candidate_sub in [
            r"Privax\HMA VPN\Vpn.exe",
            r"Privax\HMA VPN\bin\HMA.exe",
            r"Privax\HMA! Pro VPN\bin\HMA.exe",
            r"HMA VPN\hma-vpn.exe",
            r"HMA VPN\bin\hma-vpn.exe",
            r"HideMyAss\HMA.exe"
        ]:
            full_p = os.path.join(pf, candidate_sub)
            if os.path.exists(full_p) and os.path.isfile(full_p):
                return full_p
                
    return ""


def get_current_public_ip(timeout=5):
    """
    Lấy thông tin IP công khai hiện tại kèm Quốc gia, Thành phố và ISP
    """
    endpoints = [
        ("http://ip-api.com/json/?fields=status,message,country,countryCode,regionName,city,query,isp", "ip-api"),
        ("https://api.ipify.org?format=json", "ipify")
    ]
    
    for url, provider in endpoints:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    if provider == "ip-api" and data.get("status") == "success":
                        return {
                            "ip": data.get("query", ""),
                            "country": data.get("country", ""),
                            "country_code": data.get("countryCode", ""),
                            "city": data.get("city", ""),
                            "isp": data.get("isp", ""),
                            "success": True
                        }
                    elif provider == "ipify":
                        return {
                            "ip": data.get("ip", ""),
                            "country": "",
                            "country_code": "",
                            "city": "",
                            "isp": "",
                            "success": True
                        }
        except Exception as e:
            continue
            
    return {
        "ip": "Unknown",
        "country": "Unknown",
        "country_code": "",
        "city": "",
        "isp": "",
        "success": False,
        "error": "Không thể kết nối đến máy chủ định tuyến IP"
    }

def bring_hma_window_to_front(cli_path=""):
    """
    Tự động bật cửa sổ HMA VPN lên màn hình chính
    """
    exec_path = cli_path.strip().strip('"').strip("'") if cli_path else find_hma_executable()
    if exec_path and os.path.exists(exec_path):
        try:
            subprocess.Popen([exec_path])
            return True
        except Exception:
            pass
    return False

def connect_hma(location_or_country="", cli_path=""):
    """
    Kết nối HMA VPN đến một quốc gia hoặc vị trí cụ thể.
    Tự động bật giao diện HMA lên màn hình và kiểm tra đối chiếu IP công khai thời gian thực.
    """
    exec_path = cli_path.strip().strip('"').strip("'") if cli_path else find_hma_executable()
    location = location_or_country.strip()
    
    # 1. Kiểm tra IP hiện tại trước
    current_ip_info = get_current_public_ip()
    curr_country = current_ip_info.get("country", "").lower()
    curr_code = current_ip_info.get("country_code", "").lower()
    loc_lower = location.lower()
    
    # Nếu IP hiện tại đã đúng quốc gia mục tiêu
    is_already_matching = False
    if location:
        if loc_lower in curr_country or curr_country in loc_lower or loc_lower == curr_code:
            is_already_matching = True
            
    if is_already_matching:
        return {
            "success": True,
            "message": f"IP hiện tại đã khớp vùng mục tiêu: {current_ip_info.get('ip')} ({current_ip_info.get('country')})",
            "current_ip": current_ip_info
        }
        
    # 2. Bật cửa sổ HMA lên màn hình cho người dùng
    bring_hma_window_to_front(exec_path)
    
    # 3. Gửi lệnh CLI nếu có hỗ trợ
    if exec_path and os.path.exists(exec_path):
        try:
            cmd = [exec_path]
            if location:
                cmd.extend(["-connect", location])
            else:
                cmd.extend(["-connect"])
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        except Exception:
            pass
            
    # Chờ 3-4s và lấy IP mới nhất
    time.sleep(3)
    new_ip_info = get_current_public_ip()
    
    return {
        "success": True,
        "message": f"IP hiện tại: {new_ip_info.get('ip')} ({new_ip_info.get('country', 'N/A')})",
        "current_ip": new_ip_info
    }


def change_ip_hma(cli_path=""):
    """
    Đổi sang một IP mới trên HMA VPN (-changeip)
    """
    exec_path = cli_path.strip().strip('"').strip("'") if cli_path else find_hma_executable()
    if not exec_path or not os.path.exists(exec_path):
        return {
            "success": False,
            "error": f"Không tìm thấy file HMA CLI tại đường dẫn: '{exec_path or 'Chưa cấu hình'}'",
            "current_ip": get_current_public_ip()
        }
        
    try:
        proc = subprocess.run([exec_path, "-changeip"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        time.sleep(3)
        ip_info = get_current_public_ip()
        return {
            "success": True,
            "message": "Đã thực hiện đổi IP qua HMA VPN",
            "stdout": proc.stdout,
            "current_ip": ip_info
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Lỗi khi đổi IP HMA: {str(e)}",
            "current_ip": get_current_public_ip()
        }

def disconnect_hma(cli_path=""):
    """
    Ngắt kết nối HMA VPN (-disconnect)
    """
    exec_path = cli_path.strip().strip('"').strip("'") if cli_path else find_hma_executable()
    if not exec_path or not os.path.exists(exec_path):
        return {
            "success": False,
            "error": f"Không tìm thấy file HMA CLI tại: '{exec_path or 'Chưa cấu hình'}'"
        }
        
    try:
        proc = subprocess.run([exec_path, "-disconnect"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        time.sleep(2)
        return {
            "success": True,
            "message": "Đã ngắt kết nối HMA VPN",
            "current_ip": get_current_public_ip()
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Lỗi ngắt kết nối HMA: {str(e)}"
        }
