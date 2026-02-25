#!/bin/bash

# 設置固定的專案目錄、應用文件路徑和日誌文件路徑
PROJECT_DIR="/volume1/homes/penguin94003gmail.com/Side_Project/hasselblad_cameramark"
APP_FILE="$PROJECT_DIR/home.py"
LOG_FILE="$PROJECT_DIR/log.log"

# 1. 關閉任何正在運行的 Hasselblad Flask 應用
echo "Shutting down any existing Hasselblad application..."
# 確保精準砍掉這個 python 進程
pkill -f "$APP_FILE"
sleep 2 # 稍微暫停 2 秒，確保 Port 被完全釋放

# 2. 進入專案資料夾並從 GitHub 更新最新文件
cd "$PROJECT_DIR" || exit
echo "Pulling the latest files from GitHub..."
git checkout .  # 放棄所有 NAS 上未提交的修改，確保與 GitHub 完全一致
git pull origin main

# 3. 使用 nohup 後台啟動 Flask 應用，並將輸出寫入日誌文件
echo "Starting Hasselblad application in background..."
# Synology 環境通常使用 python3
nohup python3 "$APP_FILE" > "$LOG_FILE" 2>&1 &

echo "Hasselblad Camera Mark application started."
echo "Logs can be found at $LOG_FILE."