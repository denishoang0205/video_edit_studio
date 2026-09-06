import os
import sys
import time
import subprocess
import urllib.request

PORT = 8000
SERVER_URL = f"http://127.0.0.1:{PORT}"

def find_browser():
    candidates = [
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        os.path.expanduser(r'~\AppData\Local\Google\Chrome\Application\chrome.exe'),
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def free_port(port):
    """Kills any process currently using the specified port to prevent Address-in-Use errors."""
    try:
        cmd = f'powershell -Command "Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"'
        subprocess.run(cmd, shell=True, capture_output=True)
        time.sleep(1)
    except Exception:
        pass

def wait_for_server(url, timeout=15):
    """Wait until the server responds to HTTP requests."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2):
                return True
        except Exception:
            time.sleep(0.5)
    return False

def main():
    # 1. Clean up any hanging ports from previous abnormal exits
    free_port(PORT)
    
    # 2. Start the backend server quietly
    python_exe = sys.executable
    if not python_exe.endswith("w.exe") and "python.exe" in python_exe.lower():
        # Prefer pythonw.exe for true silent execution without command prompt windows
        pythonw_exe = python_exe.replace("python.exe", "pythonw.exe")
        if os.path.exists(pythonw_exe):
            python_exe = pythonw_exe

    CREATE_NO_WINDOW = 0x08000000
    server_process = subprocess.Popen(
        [python_exe, "server.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        creationflags=CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # 3. Wait for the server to spin up and bind to the port
    if not wait_for_server(SERVER_URL):
        # If server fails to start, abort
        server_process.kill()
        sys.exit(1)

    # 4. Find a Chromium browser and launch it in immersive App Mode
    browser_exe = find_browser()
    if not browser_exe:
        # Fallback if no Chrome/Edge found
        import webbrowser
        webbrowser.open(SERVER_URL)
        return

    browser_process = subprocess.Popen([
        browser_exe,
        f"--app={SERVER_URL}",
        "--new-window"
    ])

    # 5. Let server self-terminate via Heartbeat when Web UI is closed
    sys.exit(0)

if __name__ == "__main__":
    main()
