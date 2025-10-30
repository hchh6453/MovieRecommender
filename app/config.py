"""
應用程式設定檔
"""
import os
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

class Settings:
    # LINE Bot 設定
    LINE_CHANNEL_ACCESS_TOKEN: str = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    LINE_CHANNEL_SECRET: str = os.getenv("LINE_CHANNEL_SECRET", "")
    
    # Google Gemini AI 設定
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # 外部電影資料來源 API（選填）
    TMDB_API_KEY: str = os.getenv("TMDB_API_KEY", "")
    OMDB_API_KEY: str = os.getenv("OMDB_API_KEY", "")
    
    # 資料庫設定
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./movies.db")
    
    # 應用程式設定
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Webhook URL
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    
    def validate_settings(self):
        """驗證必要的設定是否已填入"""
        missing = []
        
        if not self.LINE_CHANNEL_ACCESS_TOKEN:
            missing.append("LINE_CHANNEL_ACCESS_TOKEN")
        if not self.LINE_CHANNEL_SECRET:
            missing.append("LINE_CHANNEL_SECRET")
        if not self.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")
            
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        return True

# 建立全域設定實例
settings = Settings()



