#!/usr/bin/env bash
# ==============================================================================
# TikTok Studio Pro - 1-Click Deployment Script for Linux / Ubuntu / Debian VPS
# ==============================================================================
set -e

echo "========================================================================"
echo "    🎬 TIKTOK STUDIO PRO - LINUX VPS DEPLOYMENT SETUP"
echo "========================================================================"
echo ""

# 1. Update and install required packages
echo "[1/5] Updating system and installing dependencies (Python3, FFmpeg, Curl)..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv ffmpeg curl git

# 2. Setup Python virtual environment
echo "[2/5] Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# 3. Install Python dependencies
echo "[3/5] Installing Python libraries from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Initialize directories and example configs
echo "[4/5] Initializing data folders and configurations..."
mkdir -p data storage/inputs storage/outputs storage/temp storage/logs input_sources output_product bin

if [ ! -f "data/accounts.json" ] && [ -f "data/accounts.example.json" ]; then
    cp data/accounts.example.json data/accounts.json
    echo "  -> Initialized data/accounts.json from template."
fi

if [ ! -f "data/settings.json" ] && [ -f "data/settings.example.json" ]; then
    cp data/settings.example.json data/settings.json
    echo "  -> Initialized data/settings.json from template."
fi

# 5. Create Systemd Service for Auto-start & Restart
echo "[5/5] Configuring systemd background service (tiktok-studio.service)..."
CURRENT_DIR=$(pwd)
CURRENT_USER=$(whoami)

sudo tee /etc/systemd/system/tiktok-studio.service > /dev/null <<EOF
[Unit]
Description=TikTok Studio Pro Video Automation Web Service
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${CURRENT_DIR}
ExecStart=${CURRENT_DIR}/venv/bin/python ${CURRENT_DIR}/server.py
Restart=always
RestartSec=5
Environment=PORT=8000
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable tiktok-studio
sudo systemctl restart tiktok-studio

echo ""
echo "========================================================================"
echo "  🎉 DEPLOYMENT HOÀN TẤT THÀNH CÔNG!"
echo "  🌐 Dịch vụ đang chạy tại: http://localhost:8000 (hoặc http://YOUR_SERVER_IP:8000)"
echo ""
echo "  Quản lý dịch vụ:"
echo "  - Kiểm tra trạng thái: sudo systemctl status tiktok-studio"
echo "  - Khởi động lại:       sudo systemctl restart tiktok-studio"
echo "  - Xem log thời gian thực: journalctl -u tiktok-studio -f"
echo "========================================================================"
