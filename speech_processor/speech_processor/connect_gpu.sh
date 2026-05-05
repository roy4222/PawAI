#!/bin/bash
echo "🧹 正在清理卡住的舊地道..."
killall ssh 2>/dev/null

echo "🚧 正在重新開挖 8000 和 8001 的地道..."
# 這裡會要求妳輸入實驗室伺服器的密碼
ssh -f -N -L 8001:localhost:8001 -L 8000:localhost:8000 roy422@140.136.155.5

echo "✅ 地道開通完畢！準備好呼叫 PawAI 囉！"
