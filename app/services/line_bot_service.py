"""
LINE Bot 服務
"""
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, 
    FlexSendMessage, QuickReply, QuickReplyButton, MessageAction, PostbackAction
)
import logging
from ..config import settings
from .movie_image_service import MovieImageService

logger = logging.getLogger(__name__)

# 電影類型翻譯對照表
GENRE_TRANSLATION = {
    "Adventure": "冒險",
    "Animation": "動畫",
    "Children": "兒童",
    "Comedy": "喜劇",
    "Fantasy": "奇幻",
    "Romance": "愛情",
    "Drama": "劇情",
    "Action": "動作",
    "Crime": "犯罪",
    "Thriller": "驚悚",
    "Horror": "恐怖",
    "Mystery": "懸疑",
    "Sci-Fi": "科幻",
    "War": "戰爭",
    "Musical": "音樂",
    "Documentary": "紀錄片",
    "Western": "西部",
    "Film-Noir": "黑色電影",
    "IMAX": "IMAX",
    "None": "無分類"
}

def translate_genres(genres_str: str) -> str:
    """將英文電影類型轉換為中文"""
    if not genres_str:
        return "未分類"
    
    # 分割類型（用 | 或空格分隔）
    genres_list = genres_str.replace("|", " ").split()
    
    # 翻譯每個類型
    translated_genres = []
    for genre in genres_list:
        translated = GENRE_TRANSLATION.get(genre, genre)
        translated_genres.append(translated)
    
    return " • ".join(translated_genres)

def translate_genres_to_english(genres_list: list) -> list:
    """將中文電影類型轉換為英文"""
    if not genres_list:
        return []
    
    # 建立反向映射（中文→英文）
    reverse_translation = {v: k for k, v in GENRE_TRANSLATION.items()}
    
    translated_genres = []
    for genre in genres_list:
        genre_str = str(genre).strip()
        # 嘗試精確匹配
        english_genre = reverse_translation.get(genre_str)
        if english_genre:
            translated_genres.append(english_genre)
        else:
            # 嘗試部分匹配（支援「動作片」「喜劇片」等）
            for cn, en in reverse_translation.items():
                if cn in genre_str or genre_str in cn:
                    translated_genres.append(en)
                    break
            else:
                # 如果找不到，保留原文（可能是英文）
                translated_genres.append(genre_str)
    
    return translated_genres if translated_genres else genres_list

class LineBotService:
    def __init__(self):
        """初始化 LINE Bot API"""
        try:
            self.line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
            self.handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)
            self.movie_image_service = MovieImageService()
            logger.info("LINE Bot Service 初始化成功")
        except Exception as e:
            logger.error(f"LINE Bot Service 初始化失敗: {e}")
            raise
    
    def verify_signature(self, body: str, signature: str) -> bool:
        """驗證 LINE 簽名"""
        try:
            self.handler.handle(body, signature)
            return True
        except InvalidSignatureError:
            logger.error("Invalid signature")
            return False
    
    def reply_message(self, reply_token: str, messages):
        """回覆訊息"""
        try:
            # 確保 messages 是列表格式
            if isinstance(messages, str):
                messages = [TextSendMessage(text=messages)]
            elif not isinstance(messages, list):
                messages = [messages]
            
            # 確保列表中的每個元素都是正確的 LINE Bot 訊息物件
            processed_messages = []
            for msg in messages:
                if isinstance(msg, str):
                    processed_messages.append(TextSendMessage(text=msg))
                else:
                    processed_messages.append(msg)
            
            self.line_bot_api.reply_message(reply_token, processed_messages)
            logger.info("訊息回覆成功")
        except LineBotApiError as e:
            logger.error(f"LINE Bot API 錯誤: {e}")
            raise
        except Exception as e:
            logger.error(f"回覆訊息失敗: {e}")
            raise
    
    def push_message(self, user_id: str, messages):
        """推送訊息給特定使用者"""
        try:
            # 確保 messages 是列表格式
            if isinstance(messages, str):
                messages = [TextSendMessage(text=messages)]
            elif not isinstance(messages, list):
                messages = [messages]
            
            # 確保列表中的每個元素都是正確的 LINE Bot 訊息物件
            processed_messages = []
            for msg in messages:
                if isinstance(msg, str):
                    processed_messages.append(TextSendMessage(text=msg))
                else:
                    processed_messages.append(msg)
            
            self.line_bot_api.push_message(user_id, processed_messages)
            logger.info(f"推送訊息給使用者 {user_id} 成功")
        except LineBotApiError as e:
            logger.error(f"LINE Bot API 錯誤: {e}")
            raise
    
    def create_movie_flex_message(self, movies_data: list) -> FlexSendMessage:
        """創建電影推薦的 Flex Message"""
        if not movies_data:
            return TextSendMessage(text="抱歉，找不到符合條件的電影推薦。")
        
        # 使用更緊湊的佈局，減少空白
        carousel_contents = []
        
        for movie in movies_data[:5]:  # 最多顯示5部電影
            movie_title = movie.get("title", "未知電影")
            genres_en = movie.get("genres", "")
            genres_cn = translate_genres(genres_en)  # 轉換為中文
            
            # 如果有評分，顯示評分
            rating_text = ""
            if "avg_rating" in movie and movie.get("avg_rating", 0) > 0:
                rating = movie["avg_rating"]
                rating_text = f"⭐ {rating:.1f}"
            
            bubble = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "paddingAll": "13px",
                    "contents": [
                        {
                            "type": "text",
                            "text": movie_title,
                            "weight": "bold",
                            "size": "lg",
                            "wrap": True,
                            "color": "#1DB446"
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "margin": "md",
                            "spacing": "xs",
                            "contents": [
                        {
                            "type": "text",
                                    "text": genres_cn,
                            "size": "sm",
                            "color": "#666666",
                                    "wrap": True
                                }
                            ]
                        }
                    ]
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "height": "sm",
                            "action": {
                                "type": "postback",
                                "label": "更多資訊",
                                "data": f"movie_info_{movie.get('movieId', '')}_{movie_title}"
                            }
                        }
                    ]
                }
            }
            
            # 如果有評分，加入評分文字
            if rating_text:
                bubble["body"]["contents"].insert(1, {
                    "type": "text",
                    "text": rating_text,
                    "size": "sm",
                    "color": "#ff6600",
                    "margin": "md"
                })
            
            carousel_contents.append(bubble)
        
        flex_message = FlexSendMessage(
            alt_text="電影推薦",
            contents={
                "type": "carousel",
                "contents": carousel_contents
            }
        )
        
        return flex_message
    
    def create_quick_reply_buttons(self) -> QuickReply:
        """創建快速回覆按鈕"""
        items = [
            QuickReplyButton(action=MessageAction(label="🎬 熱門電影", text="推薦熱門電影")),
            QuickReplyButton(action=MessageAction(label="😂 喜劇片", text="我想看喜劇電影")),
            QuickReplyButton(action=MessageAction(label="🎭 劇情片", text="我想看劇情電影")),
            QuickReplyButton(action=MessageAction(label="🚀 動作片", text="我想看動作電影")),
            QuickReplyButton(action=MessageAction(label="❤️ 愛情片", text="我想看愛情電影")),
            QuickReplyButton(action=MessageAction(label="🔍 搜尋電影", text="搜尋特定電影")),
        ]
        
        return QuickReply(items=items)
    
    def get_welcome_message(self) -> list:
        """獲取歡迎訊息"""
        welcome_text = """🎬 歡迎使用電影推薦機器人！

我可以幫你：
• 根據你的喜好推薦電影
• 搜尋特定電影資訊
• 提供個人化推薦

請告訴我你想看什麼類型的電影，或是直接點選下方的快速選項！"""
        
        welcome_message = TextSendMessage(
            text=welcome_text,
            quick_reply=self.create_quick_reply_buttons()
        )
        
        return [welcome_message]
