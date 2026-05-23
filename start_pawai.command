#!/bin/bash

# 取得現在的資料夾路徑
BASE_DIR=$(pwd)

echo "🐾 PawAI 一鍵啟動精靈準備就緒！正在召喚四個視窗..."

# 第 0 步：遠端大腦 (提醒字眼)
osascript -e 'tell application "Terminal" to do script "echo \"\n\n========================================\n🚨 第 0 步：請輸入密碼登入實驗室\n👉 登入後請手動貼上這兩行指令：\n1. conda activate pawai_gpu\n2. python3 sensevoice_server.py\n========================================\n\" && ssh roy422@140.136.155.5"'

# 第 1 步：挖地道
osascript -e 'tell application "Terminal" to do script "cd \"'$BASE_DIR'/speech_processor\" && echo \"\n\n========================================\n⛏️ 第 1 步：正在開挖地道 (請輸入密碼)\n========================================\n\" && ./connect_gpu.sh"'

# 第 2 步：啟動 Python 後端
osascript -e 'tell application "Terminal" to do script "cd \"'$BASE_DIR'/speech_processor\" && echo \"\n\n========================================\n🧠 第 2 步：啟動 Python 後端\n========================================\n\" && python -m uvicorn studio_api:app --reload --port 5000"'

# 第 3 步：啟動網頁前端
osascript -e 'tell application "Terminal" to do script "cd \"'$BASE_DIR'/pawai-studio/frontend\" && echo \"\n\n========================================\n💻 第 3 步：啟動網頁前端\n========================================\n\" && npm run dev"'

echo "✅ 魔法施放完畢！請去各個彈出來的視窗輸入密碼吧！"
