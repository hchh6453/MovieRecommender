"""
FastAPI 主程式
"""
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, PostbackEvent

from .config import settings
from .handlers.message_handler import MessageHandler

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 創建 FastAPI 應用
app = FastAPI(
    title="Movie Recommender LINE Bot",
    description="電影推薦 LINE Bot API",
    version="1.0.0"
)

# 初始化訊息處理器
message_handler = MessageHandler()

@app.get("/", response_class=HTMLResponse)
async def root():
    """根路徑 - 顯示服務狀態"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Movie Recommender LINE Bot</title>
        <meta charset="UTF-8">
    </head>
    <body>
        <h1>🎬 電影推薦 LINE Bot</h1>
        <p>服務狀態: <span style="color: green;">運行中</span></p>
        <p>版本: 1.0.0</p>
        <hr>
        <h2>功能特色:</h2>
        <ul>
            <li>🤖 智能電影推薦</li>
            <li>🔍 電影搜尋</li>
            <li>💬 自然語言互動</li>
            <li>📱 LINE Bot 整合</li>
        </ul>
        <hr>
        <p>Webhook URL: <code>/webhook</code></p>
    </body>
    </html>
    """
    return html_content

@app.get("/health")
async def health_check():
    """健康檢查端點"""
    try:
        # 驗證設定
        settings.validate_settings()
        return {
            "status": "healthy",
            "version": "1.0.0",
            "services": {
                "line_bot": "configured" if settings.LINE_CHANNEL_ACCESS_TOKEN else "not_configured",
                "gemini_ai": "configured" if settings.GEMINI_API_KEY else "not_configured"
            }
        }
    except ValueError as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@app.post("/webhook")
async def webhook(request: Request):
    """LINE Bot Webhook 端點"""
    try:
        # 獲取請求內容
        body = await request.body()
        body_str = body.decode('utf-8')
        
        # 獲取簽名
        signature = request.headers.get('X-Line-Signature', '')
        
        if not signature:
            logger.error("缺少 X-Line-Signature header")
            raise HTTPException(status_code=400, detail="Missing signature")
        
        # 驗證簽名並處理事件
        try:
            message_handler.line_bot_service.handler.handle(body_str, signature)
        except InvalidSignatureError:
            logger.error("LINE 簽名驗證失敗")
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        logger.info("Webhook 請求處理成功")
        return {"status": "ok"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook 處理失敗: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# 註冊 LINE Bot 事件處理器
@message_handler.line_bot_service.handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """處理文字訊息事件"""
    message_handler.handle_text_message(event)

@message_handler.line_bot_service.handler.add(PostbackEvent)
def handle_postback(event):
    """處理 Postback 事件"""
    message_handler.handle_postback(event)

if __name__ == "__main__":
    import uvicorn
    
    # 驗證設定
    try:
        settings.validate_settings()
        logger.info("設定驗證成功")
    except ValueError as e:
        logger.error(f"設定驗證失敗: {e}")
        logger.info("請檢查 .env 檔案中的設定")
        exit(1)
    
    # 啟動服務器
    logger.info(f"啟動服務器 - Host: {settings.HOST}, Port: {settings.PORT}")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )


