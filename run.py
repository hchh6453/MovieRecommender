"""
應用程式啟動腳本
"""
import uvicorn
from app.config import settings
import logging

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        # 驗證設定
        settings.validate_settings()
        logger.info("✅ 設定驗證成功")
        
        # 顯示服務資訊
        logger.info("🚀 啟動電影推薦 LINE Bot 服務")
        logger.info(f"📡 Host: {settings.HOST}")
        logger.info(f"🔌 Port: {settings.PORT}")
        logger.info(f"🐛 Debug 模式: {settings.DEBUG}")
        
        # 啟動服務器
        uvicorn.run(
            "app.main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=settings.DEBUG,
            log_level="info"
        )
        
    except ValueError as e:
        logger.error(f"❌ 設定驗證失敗: {e}")
        logger.info("📝 請檢查 .env 檔案中的設定")
        logger.info("💡 參考 LINE_OA_SETUP_GUIDE.md 取得 LINE Bot 金鑰")
        exit(1)
    except Exception as e:
        logger.error(f"❌ 啟動失敗: {e}")
        exit(1)



