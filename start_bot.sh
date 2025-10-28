#!/bin/bash

echo "🎬 啟動電影推薦 LINE Bot 系統"
echo "================================"

# 檢查是否在正確的目錄
if [ ! -f "run.py" ]; then
    echo "❌ 錯誤：請在專案根目錄執行此腳本"
    exit 1
fi

# 檢查虛擬環境
if [ ! -d ".venv" ]; then
    echo "❌ 錯誤：找不到虛擬環境，請先執行 python -m venv .venv"
    exit 1
fi

# 啟動虛擬環境
echo "🔧 啟動虛擬環境..."
source .venv/bin/activate

# 檢查必要套件
echo "📦 檢查套件..."
python -c "import fastapi, line_bot_sdk" 2>/dev/null || {
    echo "📥 安裝必要套件..."
    pip install -r requirements.txt
}

# 檢查 8000 端口是否被占用
if lsof -i :8000 >/dev/null 2>&1; then
    echo "⚠️  端口 8000 已被使用，正在停止舊服務..."
    pkill -f "python run.py" 2>/dev/null || true
    sleep 2
fi

# 啟動 LINE Bot 服務
echo "🚀 啟動 LINE Bot 服務..."
python run.py &
BOT_PID=$!

# 等待服務啟動
echo "⏳ 等待服務啟動..."
sleep 3

# 檢查服務是否正常
if curl -s http://localhost:8000/health >/dev/null; then
    echo "✅ LINE Bot 服務啟動成功！"
    echo ""
    echo "📋 接下來請手動執行："
    echo "1. 在新終端視窗執行: ngrok http 8000"
    echo "2. 複製 ngrok URL"
    echo "3. 更新 LINE Developers Console 的 Webhook URL"
    echo ""
    echo "🔗 本地服務地址: http://localhost:8000"
    echo "📊 健康檢查: http://localhost:8000/health"
    echo ""
    echo "按 Ctrl+C 停止服務"
    
    # 等待用戶中斷
    wait $BOT_PID
else
    echo "❌ 服務啟動失敗，請檢查錯誤訊息"
    kill $BOT_PID 2>/dev/null
    exit 1
fi







