"""
訊息處理器
"""
import logging
import pandas as pd
from linebot.models import MessageEvent, TextMessage, PostbackEvent
from ..services.line_bot_service import LineBotService, translate_genres
from ..services.recommendation_service import RecommendationService
from ..services.gemini_service import GeminiService
from ..services.user_preference_service import UserPreferenceService

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self):
        self.line_bot_service = LineBotService()
        self.recommendation_service = RecommendationService()
        self.gemini_service = GeminiService()
        self.user_preference_service = UserPreferenceService()
        
    def handle_text_message(self, event: MessageEvent):
        """處理文字訊息"""
        try:
            user_message = event.message.text
            user_id = event.source.user_id
            reply_token = event.reply_token
            
            logger.info(f"收到使用者 {user_id} 的訊息: {user_message}")
            
            # 處理不同類型的訊息
            if user_message in ["你好", "hi", "hello", "開始"]:
                response = self.handle_greeting()
            elif "查看偏好" in user_message or "我的偏好" in user_message or "偏好設定" in user_message:
                response = self.handle_view_preferences(user_id)
            elif "重置偏好" in user_message or "清除偏好" in user_message:
                response = self.handle_reset_preferences(user_id)
            elif any(keyword in user_message for keyword in ["怎麼用", "如何操作", "使用方法", "操作說明", "功能說明", "有什麼功能", "指令"]):
                response = self.handle_help_guide()
            elif "推薦" in user_message or "電影" in user_message:
                response = self.handle_movie_recommendation(user_message, user_id)
            elif user_message.startswith("搜尋"):
                response = self.handle_movie_search(user_message)
            else:
                response = self.handle_general_message(user_message, user_id)
            
            # 回覆訊息
            self.line_bot_service.reply_message(reply_token, response)
            
        except Exception as e:
            logger.error(f"處理文字訊息時發生錯誤: {e}")
            error_message = "抱歉，系統發生錯誤，請稍後再試。"
            self.line_bot_service.reply_message(event.reply_token, error_message)
    
    def handle_greeting(self):
        """處理問候訊息"""
        return self.line_bot_service.get_welcome_message()
    
    def handle_view_preferences(self, user_id: str):
        """處理查看偏好請求"""
        summary = self.user_preference_service.get_preference_summary(user_id)
        
        response = "📋 你的偏好設定：\n\n" + summary
        response += "\n\n💡 提示："
        response += "\n• 說「重置偏好」可以清除所有偏好記錄"
        response += "\n• 說「我不喜歡XX電影」可以更新排除列表"
        response += "\n• 繼續聊天推薦電影會自動更新偏好"
        
        return response
    
    def handle_reset_preferences(self, user_id: str):
        """處理重置偏好請求"""
        self.user_preference_service.reset_preferences(user_id)
        
        response = "✅ 偏好已重置！\n\n"
        response += "你現在可以重新開始建立偏好設定了。"
        response += "\n\n試試說：「我想看喜劇電影」來開始新的偏好設定！"
        
        return response
    
    def handle_help_guide(self):
        """處理操作指示請求"""
        guide = """🎬 電影推薦機器人 - 操作說明

✨ 主要功能：

1️⃣ 電影推薦
   • "推薦電影" - 根據你的偏好推薦
   • "我想看喜劇電影" - 指定類型推薦
   • "2023年的電影" - 按年份推薦
   • "我不喜歡恐怖片" - 排除類型

2️⃣ 偏好管理
   • "查看偏好" - 查看目前偏好設定
   • "重置偏好" - 清除所有偏好記錄

3️⃣ 電影資訊
   • 點擊電影卡片上的"更多資訊"按鈕
   • 查看詳細電影資訊和推薦原因

4️⃣ 其他
   • "搜尋 電影名稱" - 搜尋特定電影
   • "怎麼用" - 查看本說明

💡 使用技巧：
• 系統會記住你的喜好，越用越懂你
• 可以同時指定多個條件（類型+年份+排除）
• 偏好設定會自動從對話中學習

🎯 範例對話：
• "我想看喜劇電影"
• "推薦2023年的動作片"
• "我不喜歡恐怖和兒童電影"
• "查看偏好"

需要更多幫助可以隨時詢問！"""
        
        return guide
    
    def handle_movie_recommendation(self, message: str, user_id: str):
        """處理電影推薦請求"""
        # 1. 使用 AI 驅動的推薦系統（帶有用戶偏好）
        candidates = self._get_personalized_recommendations(message, user_id)
        
        if not candidates:
            return "抱歉，找不到符合條件的電影推薦。請試試其他描述！"
        
        # 2. 生成推薦解釋
        explanation = self.recommendation_service.get_recommendation_explanation(message, candidates)
        
        # 3. 創建 Flex Message
        flex_message = self.line_bot_service.create_movie_flex_message(candidates)
        
        # 4. 組合回應
        response = [explanation, flex_message]
        
        # 5. 添加後續互動
        follow_up = "💡 你可以：\n• 點擊「更多資訊」了解詳情\n• 說「再推薦一些」獲得更多選擇\n• 告訴我其他偏好"
        response.append(follow_up)
        
        return response
    
    def _get_personalized_recommendations(self, message: str, user_id: str):
        """獲取個人化推薦"""
        # 獲取用戶的歷史偏好
        user_preferences = self.user_preference_service.get_personalized_preferences(user_id)
        
        # 生成增強後的查詢（加入個人化偏好）
        enhanced_message = self._enhance_message_with_preferences(message, user_preferences)
        
        # 獲取推薦
        candidates = self.recommendation_service.recommend_by_text(enhanced_message, top_k=5)
        
        # 記錄本次查詢的偏好
        preferences = self.gemini_service.extract_preferences(message)
        self.user_preference_service.update_preferences_from_query(user_id, preferences)
        
        return candidates
    
    def _enhance_message_with_preferences(self, message: str, user_preferences: dict) -> str:
        """根據用戶偏好增強查詢訊息"""
        if not user_preferences:
            return message
        
        # 如果有偏好的類型，自動加入
        if user_preferences.get("favorite_genres"):
            favorite_genres = " ".join(user_preferences["favorite_genres"])
            message = f"{message} {favorite_genres}"
        
        return message
    
    def handle_movie_search(self, message: str):
        """處理電影搜尋"""
        # 提取搜尋關鍵字
        search_term = message.replace("搜尋", "").strip()
        
        if not search_term:
            return "請告訴我你想搜尋的電影名稱，例如：「搜尋 玩具總動員」"
        
        # 暫時回傳簡單回應
        response = f"正在搜尋「{search_term}」相關的電影...\n\n" \
                  f"找到以下結果：\n" \
                  f"🎬 {search_term} (1995)\n" \
                  f"類型：冒險|動畫|兒童|喜劇|奇幻\n\n" \
                  f"需要更多資訊嗎？"
        
        return response
    
    def handle_general_message(self, message: str, user_id: str):
        """處理一般訊息"""
        response = f"🎬 我是電影推薦機器人！\n\n" \
                  f"我可以幫你：\n" \
                  f"• 🎯 推薦電影（說「推薦電影」或指定類型）\n" \
                  f"• 🔍 搜尋電影（說「搜尋 電影名稱」）\n" \
                  f"• 👤 查看偏好（說「查看偏好」）\n" \
                  f"• 📖 操作說明（說「怎麼用」）\n\n" \
                  f"💡 試試說：「我想看喜劇電影」或「怎麼用」來開始！"
        
        return response
    
    def handle_movie_info_request(self, movie_id: str, movie_title: str):
        """處理電影資訊請求，生成詳細電影資訊"""
        try:
            # 從資料庫獲取電影詳細資訊
            movie_details = self._get_movie_details(movie_id, movie_title)
            
            # 構建結構化的電影資訊
            year = movie_details.get("year", "未知")
            genres_en = movie_details.get("genres", "未分類")
            genres_cn = movie_details.get("genres_cn", "未分類")
            avg_rating = movie_details.get("avg_rating", 0)
            rating_count = movie_details.get("rating_count", 0)
            
            # 使用 Gemini 生成推薦原因
            movie_info = {
                "movieId": movie_id,
                "title": movie_title,
                "year": year,
                "genres": genres_cn,  # 使用中文類型
                "avg_rating": avg_rating
            }
            
            explanation = self.gemini_service.generate_movie_recommendation_reason(movie_info)
            
            # 構建詳細回應
            response = f"🎬 {movie_title}\n\n"
            
            response += "📊 電影資訊：\n"
            response += f"• 📅 年份：{year}\n" if year != "未知" else ""
            response += f"• 🏷️ 類型：{genres_cn}\n"
            
            if avg_rating > 0:
                rating_text = f"⭐ {avg_rating:.1f} / 5.0"
                if rating_count > 0:
                    rating_text += f" ({rating_count:,} 人評分)"
                response += f"• ⭐ 整體評價：{rating_text}\n"
            
            response += f"\n💡 推薦原因：\n{explanation}\n\n"
            response += "💬 想了解更多電影推薦嗎？告訴我你的偏好！"
            
            return response
            
        except Exception as e:
            logger.error(f"生成電影資訊失敗: {e}")
            return f"🎬 {movie_title}\n\n" \
                   f"這是一部值得觀看的電影！\n\n" \
                   f"💡 想了解更多電影推薦嗎？告訴我你的偏好！"
    
    def _get_movie_details(self, movie_id: str, movie_title: str) -> dict:
        """獲取電影詳細資訊"""
        try:
            movies = self.recommendation_service.movies
            if movies is None:
                return {}
            
            # 查找電影
            movie = movies[movies["movieId"] == int(movie_id)]
            
            if movie.empty:
                return {"title": movie_title}
            
            movie = movie.iloc[0]
            
            # 提取年份
            year = "未知"
            if pd.notna(movie.get("year")):
                year = int(movie["year"])
            
            # 提取類型
            genres_en = movie.get("genres", "未分類")
            genres_cn = translate_genres(genres_en)  # 轉換為中文
            
            # 提取評分
            avg_rating = 0
            rating_count = 0
            if "avg_rating" in movie and pd.notna(movie["avg_rating"]):
                avg_rating = float(movie["avg_rating"])
            if "rating_count" in movie and pd.notna(movie["rating_count"]):
                rating_count = int(movie["rating_count"])
            
            return {
                "title": movie.get("title", movie_title),
                "year": year,
                "genres": genres_en,
                "genres_cn": genres_cn,
                "avg_rating": avg_rating,
                "rating_count": rating_count
            }
            
        except Exception as e:
            logger.error(f"獲取電影詳細資訊失敗: {e}")
            return {"title": movie_title}
    
    def handle_postback(self, event: PostbackEvent):
        """處理 Postback 事件"""
        try:
            data = event.postback.data
            reply_token = event.reply_token
            
            logger.info(f"收到 Postback 事件: {data}")
            
            # 根據 postback data 處理不同動作
            if data.startswith("movie_info_"):
                # 解析電影資訊請求
                parts = data.replace("movie_info_", "").split("_", 1)
                if len(parts) >= 2:
                    movie_id = parts[0]
                    movie_title = parts[1]
                    response = self.handle_movie_info_request(movie_id, movie_title)
                else:
                    response = "抱歉，無法獲取電影資訊。"
            else:
                response = "收到你的操作請求！"
            
            self.line_bot_service.reply_message(reply_token, response)
            
        except Exception as e:
            logger.error(f"處理 Postback 事件時發生錯誤: {e}")
            error_message = "抱歉，系統發生錯誤，請稍後再試。"
            self.line_bot_service.reply_message(event.reply_token, error_message)
