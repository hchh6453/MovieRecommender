#!/bin/bash

echo "🛑 停止電影推薦 LINE Bot 系統"
echo "=============================="

# 停止 Python 服務
echo "🔄 停止 LINE Bot 服務..."
pkill -f "python run.py" && echo "✅ LINE Bot 服務已停止" || echo "ℹ️  沒有運行中的 LINE Bot 服務"

# 停止 ngrok
echo "🔄 停止 ngrok 隧道..."
pkill -f "ngrok http" && echo "✅ ngrok 隧道已停止" || echo "ℹ️  沒有運行中的 ngrok 隧道"

# 檢查端口狀態
if ! lsof -i :8000 >/dev/null 2>&1; then
    echo "✅ 端口 8000 已釋放"
else
    echo "⚠️  端口 8000 仍被占用"
fi

echo "🎉 系統已停止"









