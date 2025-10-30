"""
訊息處理器
"""
import logging
import pandas as pd
from typing import Dict, Optional, Union
from linebot.models import (
    MessageEvent, TextMessage, PostbackEvent, 
    FollowEvent, UnfollowEvent
)
from ..services.line_bot_service import LineBotService, translate_genres, translate_genres_to_english
from ..services.recommendation_service import RecommendationService
from ..services.gemini_service import GeminiService
from ..services.movie_metadata_service import MovieMetadataService
from ..services.movie_info_store import MovieInfoStoreService
from ..services.user_preference_service import UserPreferenceService
from ..services.movie_submission_service import MovieSubmissionService

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self):
        self.line_bot_service = LineBotService()
        self.recommendation_service = RecommendationService()
        self.gemini_service = GeminiService()
        self.user_preference_service = UserPreferenceService()
        self.movie_metadata_service = MovieMetadataService()
        self.movie_submission_service = MovieSubmissionService()
        self.movie_info_store = MovieInfoStoreService()
        
    def handle_text_message(self, event: MessageEvent):
        """處理文字訊息"""
        try:
            user_message = event.message.text
            user_id = event.source.user_id
            reply_token = event.reply_token
            
            logger.info(f"收到使用者 {user_id} 的訊息: {user_message}")
            
            # 先立即發送確認訊息（如果需要）
            confirmation_message = self._get_confirmation_message(user_message)
            # 如果目前有電影上下文，且使用者詢問的是針對該電影的資訊查詢，強制使用「整理電影資訊」的確認文案
            try:
                current_context = self.user_preference_service.get_current_movie_context(user_id)
                message_lower = user_message.lower()
                info_keywords = [
                    # 常見資訊類問題（中）
                    "總片長", "片長", "演員", "主要演員", "哪裡可以看", "平台", "看哪", "預告", "預告片",
                    "導演", "編劇", "評分", "上映", "年份", "年份是", "大綱", "簡介", "介紹",
                    # 推薦/評估意圖（中）
                    "推薦我看", "推薦嗎", "推不推薦", "值得看", "好看嗎", "要不要看",
                    # 常見資訊類問題（英）
                    "runtime", "length", "duration", "cast", "actors", "where to watch", "platform",
                    "trailer", "director", "writer", "rating", "year", "synopsis", "overview", "plot",
                    # 推薦/評估意圖（英）
                    "recommend", "would you recommend", "should i watch", "worth watching"
                ]
                if current_context and any(k in message_lower for k in info_keywords):
                    confirmation_message = "🔎 正在整理電影資訊，請稍候..."
            except Exception:
                pass
            use_push = False  # 預設使用 reply_message（更快）
            
            if confirmation_message:
                try:
                    self.line_bot_service.reply_message(reply_token, confirmation_message)
                    use_push = True  # 如果已發送確認訊息，後續使用 push_message
                except Exception as e:
                    logger.warning(f"發送確認訊息失敗: {e}，將直接回覆結果")
                    use_push = False  # 發送失敗則回退到直接回覆
            
            # 然後處理實際請求
            response = ""
            try:
                # 處理不同類型的訊息
                # 標準化打招呼訊息（去除空白、全形半形轉換）
                normalized_message = user_message.strip().lower().replace("　", " ").replace("，", ",").replace("。", ".")
                if normalized_message in ["你好", "hi", "hello", "開始", "嗨", "哈囉", "hey"]:
                    response = self.handle_greeting()
                elif "查看偏好" in user_message or "我的偏好" in user_message or "偏好設定" in user_message:
                    response = self.handle_view_preferences(user_id)
                elif "重置偏好" in user_message or "清除偏好" in user_message:
                    response = self.handle_reset_preferences(user_id)
                elif any(keyword in user_message for keyword in ["怎麼用", "如何操作", "使用方法", "操作說明", "功能說明", "有什麼功能", "指令"]):
                    response = self.handle_help_guide()
                elif "新增電影" in user_message or "提交電影" in user_message or "添加電影" in user_message or "更新電影" in user_message or "更改電影" in user_message or "修改電影" in user_message:
                    response = self.handle_movie_submission(user_message, user_id)
                elif "申訴" in user_message or "我要申訴" in user_message:
                    response = self.handle_appeal_submission(user_message, user_id)
                elif user_message.startswith("搜尋"):
                    response = self.handle_movie_search(user_message, user_id)
                elif "推薦" in user_message or "電影" in user_message or "看" in user_message or any(genre in user_message for genre in ["喜劇", "動作", "劇情", "愛情", "恐怖", "驚悚", "科幻", "懸疑", "冒險", "戰爭", "動畫", "兒童", "奇幻", "音樂", "犯罪", "西部", "紀錄片", "驚悚", "懸疑"]):
                    # 包含電影相關關鍵字，嘗試推薦
                    try:
                        logger.info("進入推薦分支：handle_movie_recommendation")
                        response = self.handle_movie_recommendation(user_message, user_id)
                    except Exception as rec_e:
                        logger.error(f"推薦流程發生錯誤：{rec_e}")
                        response = f"❌ 處理推薦時發生錯誤：{str(rec_e)}\n\n請試試其他描述或稍後再試。"
                else:
                    # 檢查是否有當前討論的電影上下文
                    movie_context = self.user_preference_service.get_current_movie_context(user_id)
                    if movie_context:
                        ml = user_message.lower()
                        info_keywords = [
                            "總片長", "片長", "演員", "主要演員", "哪裡可以看", "平台", "預告", "預告片",
                            "導演", "編劇", "評分", "上映", "年份", "大綱", "簡介", "介紹",
                            "推薦我看", "推薦嗎", "推不推薦", "值得看", "好看嗎", "要不要看",
                            "runtime", "length", "duration", "cast", "actors", "where to watch", "platform",
                            "trailer", "director", "writer", "rating", "year", "synopsis", "overview", "plot",
                            "recommend", "would you recommend", "should i watch", "worth watching"
                        ]
                        if any(k in ml for k in info_keywords):
                            response = self.handle_movie_question(user_message, user_id, movie_context)
                        else:
                            response = self.handle_general_message(user_message, user_id)
                    else:
                        response = self.handle_general_message(user_message, user_id)
            
                # 根據是否有確認訊息決定使用 reply_message 或 push_message
                # 確保回覆不為空
                if not response or (isinstance(response, str) and not response.strip()):
                    response = (
                        "我懂你的意思～如果想看電影，我也可以幫你推薦！\n"
                        "🔎 不確定怎麼用？試試：\n"
                        "• 說「推薦電影」或指定類型\n"
                        "• 說「搜尋 Toy Story」\n"
                        "• 說「怎麼用」查看更多"
                    )
                if use_push:
                    # 如果已經發送確認訊息，使用 push_message
                    self.line_bot_service.push_message(user_id, response)
                else:
                    # 如果沒有確認訊息，使用 reply_message（更快）
                    self.line_bot_service.reply_message(reply_token, response)
                
            except Exception as e:
                logger.error(f"處理請求時發生錯誤: {e}")
                # 優先處理明確的推薦需求，避免誤回精簡指南
                try:
                    if ("推薦" in user_message or "電影" in user_message or any(g in user_message for g in ["喜劇","動作","劇情","愛情","恐怖","驚悚","科幻","懸疑","冒險","戰爭"])):
                        logger.info("例外時嘗試直接走推薦分支（降級）")
                        response = self.handle_movie_recommendation(user_message, user_id)
                    else:
                        response = self.handle_general_message(user_message, user_id)
                except Exception:
                    response = (
                        "我懂你的意思～如果想看電影，我也可以幫你推薦！\n"
                        "🔎 不確定怎麼用？試試：\n"
                        "• 說「推薦電影」或指定類型\n"
                        "• 說「搜尋 Toy Story」\n"
                        "• 說「怎麼用」查看更多"
                    )
                if use_push:
                    self.line_bot_service.push_message(user_id, response)
                else:
                    try:
                        self.line_bot_service.reply_message(reply_token, response)
                    except:
                        self.line_bot_service.push_message(user_id, response)
            
        except Exception as e:
            logger.error(f"處理文字訊息時發生錯誤: {e}")
            # 如果連確認訊息都發送失敗，嘗試發送錯誤訊息
            try:
                error_message = "❌ 系統發生錯誤，請稍後再試。"
                self.line_bot_service.reply_message(event.reply_token, error_message)
            except:
                pass
    
    def _get_confirmation_message(self, user_message: str) -> str:
        """根據訊息類型生成確認訊息"""
        message_lower = user_message.lower().strip()
        
        # 快速回應（不需要確認）
        quick_responses = ["你好", "hi", "hello", "開始", "查看偏好", "我的偏好", "偏好設定", 
                          "重置偏好", "清除偏好", "怎麼用", "如何操作", "使用方法", 
                          "操作說明", "功能說明", "有什麼功能", "指令", "幫助", "help",
                          "哈囉", "嗨", "hey", "早上好", "午安", "晚安", "早安", "晚安"]
        
        # 檢查是否是純打招呼（僅包含打招呼詞語，沒有其他內容）
        is_greeting_only = False
        greeting_only_patterns = ["你好", "hi", "hello", "哈囉", "嗨", "hey", "開始", 
                                 "早上好", "午安", "晚安", "早安"]
        for pattern in greeting_only_patterns:
            if user_message.strip().lower() == pattern.lower():
                is_greeting_only = True
                break
        
        # 如果是純打招呼或快速回應，不需要確認
        if is_greeting_only or any(msg in user_message for msg in quick_responses):
            return ""  # 這些訊息處理很快，不需要確認
        
        # 開放性「全部資訊」詢問（優先顯示整理中，而非推薦）
        open_info_keywords = [
            # 中文常見說法
            "全部資訊", "所有資訊", "更多資訊", "所有的資訊", "全部的資訊",
            "你知道關於這部電影", "關於這部電影的全部資訊", "告訴我所有資訊", "告訴我全部資訊", "介紹一下這部電影",
            # 中文（資訊/信息）雙寫
            "所有信息", "全部信息", "更多信息",
            # 英文常見說法
            "all info", "all information", "everything", "tell me everything", "more info"
        ]
        if any(k in message_lower for k in open_info_keywords):
            return "🔎 正在整理電影資訊，請稍候..."

        # 根據訊息類型返回不同的確認訊息
        if "搜尋" in user_message:
            return "🔍 正在搜尋電影，請稍候..."
        elif "新增電影" in user_message or "提交電影" in user_message or "添加電影" in user_message:
            return "📝 正在處理電影資訊提交，請稍候..."
        elif "申訴" in user_message or "我要申訴" in user_message:
            return "🔄 正在處理申訴請求，請稍候..."
        elif "推薦" in user_message or "電影" in user_message or any(genre in user_message for genre in ["喜劇", "動作", "劇情", "愛情", "恐怖", "驚悚", "科幻", "懸疑", "冒險", "戰爭"]):
            return "🤖 正在為你推薦電影，請稍候..."
        else:
            # 非電影相關或難以判斷的訊息：顯示確認訊息，然後由 AI 友善回覆並引導回主題
            return "🤖 正在處理你的訊息，請稍候..."

    
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
        guide = """🎬 電影推薦機器人 - 完整操作指南

✨ 主要功能：

1️⃣ 電影推薦
   • "推薦電影" - 根據你的偏好推薦
   • "我想看喜劇電影" - 指定類型推薦
   • "2023年的電影" - 按年份推薦
   • "我不喜歡恐怖片" - 排除類型

2️⃣ 串流平台推薦（新功能！）
   • "Netflix 可以看的動作片"
   • "Disney+ 喜劇"
   • "Apple TV+ 有什麼推薦"
   • "Prime Video 電影"
   支援平台：Netflix、Disney+、Amazon Prime Video、Apple TV+、HBO Max、Hulu、Catchplay

3️⃣ 偏好管理
   • "查看偏好" - 查看目前偏好設定
   • "重置偏好" - 清除所有偏好記錄

4️⃣ 電影資訊與提問（新功能！）
   • 點擊電影卡片上的"更多資訊"按鈕
   • 查看基本資訊：年份、片長、類型、評價、推薦原因
   • 查看後可繼續提問：
     - "主要演員有哪些？"
     - "在哪裡可以看？" 或 "有什麼平台？"
     - "有預告片嗎？"
     - "這部電影好看嗎？"
     - 或其他關於這部電影的問題！

5️⃣ 新增電影資訊（新功能！）
   • "新增電影：電影名稱 (年份)\n類型：動作|喜劇"
   • "怎麼新增電影" - 查看提交格式說明
   • 找不到電影？可以提交新電影資訊給管理員審核

6️⃣ 其他功能
   • "搜尋 電影名稱" - 搜尋特定電影
   • "怎麼用" / "幫助" / "help" - 查看本說明

💡 使用技巧：
• 系統會記住你的喜好，越用越懂你
• 可以同時指定多個條件（類型+年份+排除+平台）
• 偏好設定會自動從對話中學習
• 看過電影資訊後，直接問問題即可獲得更多資訊

🎯 完整範例對話：

【基本推薦】
• "我想看喜劇電影"
• "推薦2023年的動作片"
• "我不喜歡恐怖和兒童電影"

【串流平台推薦】
• "Netflix 可以看的動作片"
• "Disney+ 喜劇推薦"
• "Prime Video 有什麼好看的"

【查看與提問】
• 點擊"更多資訊" → 查看基本資訊
• 接著問："主要演員有哪些？" → 獲得演員名單
• 接著問："在哪裡可以看？" → 獲得串流平台資訊
• 接著問："有預告片嗎？" → 獲得 YouTube 連結

【偏好管理】
• "查看偏好" - 查看已儲存的偏好
• "重置偏好" - 清除所有偏好

【新增電影】
• "新增電影：我的新電影 (2024)\n類型：動作|科幻"
• "怎麼新增電影" - 查看完整格式說明

需要更多幫助可以隨時詢問！"""
        
        return guide
    
    def handle_movie_recommendation(self, message: str, user_id: str):
        """處理電影推薦請求"""
        try:
            # 清除之前的電影上下文（開始新的推薦會覆蓋上下文）
            self.user_preference_service.clear_current_movie_context(user_id)
            
            # 1. 使用 AI 驅動的推薦系統（帶有用戶偏好）
            candidates = self._get_personalized_recommendations(message, user_id)
            
            if not candidates:
                return "抱歉，找不到符合條件的電影推薦。請試試其他描述，例如：「推薦喜劇電影」或「我想看動作片」！"

            # 1.1 依指定串流平台過濾（若訊息中包含平台名稱）
            provider = self._extract_provider_preference(message)
            if provider and candidates:
                try:
                    filtered = []
                    for m in candidates:
                        try:
                            mid = int(m.get("movieId")) if m.get("movieId") is not None else None
                            if not mid:
                                continue
                            extras = self.movie_metadata_service.fetch_extras(mid)
                            providers = extras.get("watch_providers", []) or []
                            if any(provider.lower() in (p or "").lower() for p in providers):
                                filtered.append(m)
                        except Exception as e:
                            logger.warning(f"處理電影 {mid} 的平台資訊時出錯: {e}")
                            # 如果無法取得平台資訊，仍然保留該電影（不因為平台查詢失敗而排除）
                            filtered.append(m)
                    if filtered:
                        candidates = filtered
                except Exception as e:
                    logger.error(f"串流平台過濾失敗: {e}")
                    # 如果平台過濾失敗，繼續使用原始推薦列表
            
            if not candidates:
                return f"抱歉，在 {provider} 平台上找不到符合條件的電影推薦。請試試其他平台或移除平台限制！"
            
            # 2. 生成推薦解釋
            try:
                explanation = self.recommendation_service.get_recommendation_explanation(message, candidates)
            except Exception as e:
                logger.error(f"生成推薦解釋失敗: {e}")
                explanation = f"根據「{message}」為你推薦了 {len(candidates)} 部電影！"
            
            # 3. 創建 Flex Message
            try:
                flex_message = self.line_bot_service.create_movie_flex_message(candidates)
            except Exception as e:
                logger.error(f"創建 Flex Message 失敗: {e}")
                # 降級為文字回應
                response = f"{explanation}\n\n"
                for i, movie in enumerate(candidates[:5], 1):
                    movie_title = movie.get("title", "未知電影")
                    year = movie.get("year", "")
                    genres_cn = translate_genres(movie.get("genres", ""))
                    response += f"{i}. {movie_title}"
                    if year:
                        response += f" ({year})"
                    response += f"\n   類型：{genres_cn}\n"
                return response
            
            # 4. 組合回應
            response = [explanation, flex_message]
            
            # 5. 添加後續互動
            follow_up = "💡 你可以：\n• 點擊「更多資訊」了解詳情\n• 說「再推薦一些」獲得更多選擇\n• 告訴我其他偏好"
            response.append(follow_up)
            
            return response
    
        except Exception as e:
            logger.error(f"處理電影推薦失敗: {e}", exc_info=True)
            return f"❌ 處理推薦時發生錯誤：{str(e)}\n\n請試試其他描述或稍後再試。"

    def _extract_provider_preference(self, text: str) -> Optional[str]:
        """從文字中辨識串流平台偏好，回傳 TMDb provider_name。"""
        if not text:
            return None
        mapping = {
            "netflix": "Netflix",
            "奈飛": "Netflix",
            "disney+": "Disney Plus",
            "disney plus": "Disney Plus",
            "迪士尼": "Disney Plus",
            "prime video": "Amazon Prime Video",
            "amazon": "Amazon Prime Video",
            "亞馬遜": "Amazon Prime Video",
            "apple tv+": "Apple TV Plus",
            "apple tv plus": "Apple TV Plus",
            "hbo max": "HBO Max",
            "max": "HBO Max",
            "hulu": "Hulu",
            "catchplay": "Catchplay",
        }
        low = text.lower()
        for k, v in mapping.items():
            if k in low:
                return v
        return None
    
    def _get_personalized_recommendations(self, message: str, user_id: str):
        """獲取個人化推薦"""
        try:
            # 獲取用戶的歷史偏好
            user_preferences = self.user_preference_service.get_personalized_preferences(user_id)
            
            # 檢查訊息中是否明確指定了類型
            current_preferences = self.gemini_service.extract_preferences(message)
            has_explicit_genres = current_preferences.get("genres") and len(current_preferences["genres"]) > 0
            
            # 判斷是否為模糊或未指定類型的訊息
            vague_keywords = ["推薦", "電影", "想看", "有什麼", "介紹", "找", "給"]
            is_vague_request = not has_explicit_genres and any(keyword in message for keyword in vague_keywords)
            
            # 如果是模糊請求且有歷史偏好，加強個人化偏好的權重
            if is_vague_request and user_preferences.get("favorite_genres"):
                logger.info(f"檢測到模糊請求，將加強使用者的歷史偏好：{user_preferences.get('favorite_genres')}")
                # 直接使用歷史偏好作為主要查詢條件
                enhanced_message = " ".join(user_preferences["favorite_genres"])
            else:
                # 生成增強後的查詢（加入個人化偏好）
                enhanced_message = self._enhance_message_with_preferences(message, user_preferences)
            
            # 獲取推薦
            candidates = self.recommendation_service.recommend_by_text(enhanced_message, top_k=5)
            
            if not candidates:
                logger.warning(f"推薦服務返回空列表，查詢：{enhanced_message}")
                return []
            
            # 記錄本次查詢的偏好
            try:
                preferences = self.gemini_service.extract_preferences(message)
                self.user_preference_service.update_preferences_from_query(user_id, preferences)
            except Exception as e:
                logger.warning(f"記錄用戶偏好失敗: {e}，繼續推薦流程")
            
            return candidates
            
        except Exception as e:
            logger.error(f"獲取個人化推薦失敗: {e}", exc_info=True)
            # 嘗試降級到基本推薦（不使用個人化）
            try:
                return self.recommendation_service.recommend_by_text(message, top_k=5)
            except Exception as e2:
                logger.error(f"基本推薦也失敗: {e2}")
                return []
    
    def _enhance_message_with_preferences(self, message: str, user_preferences: dict) -> str:
        """根據用戶偏好增強查詢訊息"""
        if not user_preferences:
            return message
        
        # 檢查訊息中是否明確指定了類型
        current_preferences = self.gemini_service.extract_preferences(message)
        has_explicit_genres = current_preferences.get("genres") and len(current_preferences["genres"]) > 0
        
        # 如果使用者明確指定了類型，不加入歷史偏好（讓使用者意圖優先）
        # 如果使用者沒有明確指定類型，加入歷史偏好（重複多次以增加權重）
        if not has_explicit_genres and user_preferences.get("favorite_genres"):
            favorite_genres = " ".join(user_preferences["favorite_genres"])
            # 重複歷史偏好以增強 TF-IDF 權重
            message = f"{message} {favorite_genres} {favorite_genres}"
        
        return message
    
    def handle_movie_submission(self, message: str, user_id: str):
        """處理電影資訊提交"""
        try:
            # 如果是詢問如何提交
            if "怎麼" in message and ("新增" in message or "提交" in message):
                return self.movie_submission_service.get_submission_instructions()
            
            # 驗證並提交
            result = self.movie_submission_service.validate_and_submit(user_id, message)
            
            response = result["message"]
            
            if result["success"]:
                response += f"\n\n📌 提交ID：{result['submission_id']}"
                
                if result["needs_review"]:
                    response += "\n⏳ 審核完成後，你會收到通知。"
                
                # 顯示剩餘提交次數
                status = self.movie_submission_service.get_user_submission_status(user_id)
                remaining = status["remaining_submissions"]
                if remaining > 0:
                    response += f"\n\n📊 今日剩餘提交次數：{remaining} / {status['max_per_day']}"
            
            return response
            
        except Exception as e:
            logger.error(f"處理電影提交失敗: {e}")
            return "❌ 處理提交時發生錯誤，請稍後再試。"
    
    def handle_appeal_submission(self, message: str, user_id: str):
        """處理申訴請求"""
        try:
            # 檢查是否有可申訴的提交
            result = self.movie_submission_service.appeal_rejected_submission(user_id)
            return result["message"]
            
        except Exception as e:
            logger.error(f"處理申訴失敗: {e}")
            return "❌ 處理申訴時發生錯誤，請稍後再試。"
    
    def handle_movie_search(self, message: str, user_id: str = None):
        """處理電影搜尋"""
        # 提取搜尋關鍵字
        search_term = message.replace("搜尋", "").strip()
        
        if not search_term:
            return "請告訴我你想搜尋的電影名稱，例如：「搜尋 玩具總動員」"
        
        try:
            # 若疑似中文名稱，嘗試用 AI 翻成英文再精確搜尋一次
            is_likely_chinese = any('\u4e00' <= char <= '\u9fff' for char in search_term)
            translated_term = None
            if is_likely_chinese:
                try:
                    translated_term = self.gemini_service.translate_title_to_english(search_term)
                except Exception:
                    translated_term = None

            # 1. 先嘗試精確搜尋
            exact_match = self.recommendation_service.search_exact_movie(search_term)
            if not exact_match and translated_term:
                exact_match = self.recommendation_service.search_exact_movie(translated_term)
            
            if exact_match:
                # 找到對應電影，顯示所有詳細資訊
                movie_id = str(exact_match["movieId"])
                movie_title = exact_match["title"]
                
                # 獲取電影詳細資訊
                movie_details = self._get_movie_details(movie_id, movie_title)
                
                # 記錄搜尋行為
                if user_id:
                    self.user_preference_service.record_movie_interaction(
                        user_id, 
                        movie_id, 
                        "search"
                    )
                
                # 使用 Gemini 生成電影大綱（不劇透）
                movie_synopsis = self.gemini_service.generate_movie_synopsis(
                    movie_title,
                    movie_details.get("year"),
                    movie_details.get("genres_cn", ""),
                    movie_details.get("avg_rating", 0)
                )
                
                # 構建詳細回應
                response = f"🎬 {movie_title}\n\n"
                
                # 中文搜尋提示（仍保留建議英文，但已嘗試自動翻譯）
                if is_likely_chinese:
                    response += "💡 提示：為了更準確的搜尋結果，建議使用英文電影名稱搜尋（例如：「Search Toy Story」）。\n"
                    response += "   某些電影在各國翻譯可能不同，使用英文名稱可獲得最準確的結果。\n\n"
                
                # 基本資訊
                response += "📊 電影資訊：\n"
                if movie_details.get("year") and movie_details.get("year") != "未知":
                    response += f"• 📅 年份：{movie_details.get('year')}\n"
                
                if movie_details.get("genres_cn"):
                    response += f"• 🏷️ 類型：{movie_details.get('genres_cn')}\n"
                
                if movie_details.get("runtime"):
                    response += f"• ⏱️ 片長：{movie_details.get('runtime')} 分鐘\n"
                
                if movie_details.get("avg_rating", 0) > 0:
                    rating_text = f"⭐ {movie_details.get('avg_rating'):.1f} / 5.0"
                    if movie_details.get("rating_count", 0) > 0:
                        rating_text += f" ({movie_details.get('rating_count'):,} 人評分)"
                    response += f"• ⭐ 整體評價：{rating_text}\n"
                
                # 電影大綱（不劇透）
                response += f"\n📖 電影大綱：\n{movie_synopsis}\n\n"
                
                # 提示可以問更多資訊
                response += "❓ 想了解更多？可以問我：\n"
                response += "• 主要演員有哪些？\n"
                response += "• 在哪裡可以看？\n"
                response += "• 有預告片嗎？\n"
                response += "• 或其他關於這部電影的問題！"
                
                # 記錄當前電影上下文（供後續提問使用）
                if user_id:
                    self.user_preference_service.set_current_movie_context(
                        user_id,
                        movie_id,
                        movie_title,
                        movie_details
                    )
                
                return response
            else:
                # 找不到對應電影，推薦類似電影並提供新增指南
                response = f"❌ 抱歉，資料庫中沒有找到「{search_term}」這部電影。\n\n"
                
                # 檢查是否使用中文搜尋
                if is_likely_chinese:
                    response += "💡 我已嘗試自動將中文片名翻譯後搜尋；若仍找不到，建議改用英文片名再試一次（例如：「Search Toy Story」）。\n"
                    response += "   某些電影在各國翻譯不同，英文名稱較能命中。\n\n"
                
                # 推薦類似電影
                similar_movies = self.recommendation_service.search_similar_movies(search_term, top_k=3)
                
                if similar_movies:
                    response += "🎬 為你推薦類似電影：\n\n"
                    for i, movie in enumerate(similar_movies, 1):
                        movie_title = movie.get("title", "未知電影")
                        year = movie.get("year", "")
                        genres_cn = translate_genres(movie.get("genres", ""))
                        
                        response += f"{i}. {movie_title}"
                        if year:
                            response += f" ({year})"
                        response += f"\n   類型：{genres_cn}\n\n"
                
                # 提供新增電影指南
                response += "💡 找不到這部電影？你可以：\n"
                response += "• 回覆「新增電影」查看如何提交新電影資訊\n"
                response += "• 或直接使用格式：「新增電影：Movie Title (年份)\n"
                response += "  類型：動作|喜劇」（電影名稱必須是英文，類型可用中文）\n\n"
                response += "📝 我們會審核後加入資料庫！"
                
                return response
        except Exception as e:
            logger.error(f"處理電影搜尋失敗: {e}")
            # 指導正確用法（僅在系統異常時才回通用錯誤由外層擋）
            guide = """
🔎 我可以幫你這樣搜尋：
• 「搜尋 Toy Story」
• 「搜尋 玩具總動員」（我會嘗試翻成英文再找）
• 若找不到：可回覆「新增電影」查看提交/更新說明
            """.strip()
            return guide
    
    def handle_general_message(self, message: str, user_id: str):
        """處理模糊訊息（由 Gemini AI 友善回覆並導回電影推薦）"""
        try:
            # 使用 Gemini AI 分析使用者意圖並產生友善回覆
            response = self._get_ai_response(message, user_id)
            # 附上精簡上手指引
            response += (
                "\n\n🔎 不確定怎麼用？試試：\n"
                "• 說「推薦電影」或指定類型\n"
                "• 說「搜尋 Toy Story」\n"
                "• 說「怎麼用」查看更多"
            )
            return response
        except Exception as e:
            logger.error(f"AI 回應失敗: {e}")
            return (
                "我懂你的意思～如果想看電影，我也可以幫你推薦！\n"
                "🔎 不確定怎麼用？試試：\n"
                "• 說「推薦電影」或指定類型\n"
                "• 說「搜尋 Toy Story」\n"
                "• 說「怎麼用」查看更多"
            )
    
    def _get_ai_response(self, message: str, user_id: str) -> str:
        """使用 AI 生成智能回應"""
        if not self.gemini_service.model:
            return (
                "我懂你的意思～如果想看電影，我也可以幫你推薦！\n"
                "💡 試試說：「推薦電影」或「搜尋 Toy Story」。"
            )
        
        prompt = f"""
        你是一個友善的電影推薦機器人。使用者對你說：「{message}」
        
        請分析使用者的意圖並給予適當回應。回應要求：
        1. 用繁體中文回答
        2. 語氣親切友善
        3. 如果使用者提到電影相關內容，引導他們使用推薦功能
        4. 如果使用者只是在聊天，可以簡單回應並引導到推薦功能
        5. 保持簡潔，最多3句話
        
        以下是機器人可提供的功能：
        - 推薦電影（「推薦電影」或「我想看喜劇」）
        - 查看偏好（「查看偏好」）
        - 操作說明（「怎麼用」）
        - 搜尋電影（「搜尋 電影名稱」）
        
        直接回傳回應內容，不要加其他格式。
        """
        
        try:
            ai_response = self.gemini_service.model.generate_content(prompt)
            response_text = (ai_response.text or "").strip()
            if not response_text:
                response_text = (
                    "我懂你的意思～如果想看電影，我也可以幫你推薦！\n"
                    "💡 試試說：「推薦電影」或「搜尋 Toy Story」。"
                )
            
            # 如果 AI 回應太短，添加引導
            if len(response_text) < 30:
                response_text += "\n\n💡 試試說：「推薦電影」或「怎麼用」來開始！"
            
            return response_text
        except Exception as e:
            logger.error(f"AI 回應生成失敗: {e}")
            return (
                "我懂你的意思～如果想看電影，我也可以幫你推薦！\n"
                "💡 試試說：「推薦電影」或「搜尋 Toy Story」。"
            )
    
    def handle_movie_question(self, question: str, user_id: str, movie_context: Dict) -> str:
        """處理針對當前電影的問題"""
        try:
            movie_title = movie_context.get("movie_title", "這部電影")
            movie_details = movie_context.get("movie_details", {})
            # 檢測是否為要求「全部資訊」的開放性問題
            lower_q = (question or "").lower()
            open_info_keywords = [
                "全部資訊", "所有資訊", "更多資訊", "你知道關於這部電影", "告訴我所有資訊", "告訴我全部資訊", "介紹一下這部電影",
                "all info", "everything", "tell me everything", "all information"
            ]
            if any(k in lower_q for k in open_info_keywords):
                # 使用條列式整理全部已知資訊 + 大綱
                year = movie_details.get("year", "未知")
                genres_cn = movie_details.get("genres_cn", "未分類")
                avg_rating = movie_details.get("avg_rating", 0)
                rating_count = movie_details.get("rating_count", 0)
                runtime_min = movie_details.get("runtime")
                cast_names = movie_details.get("cast", [])
                trailer_url = movie_details.get("trailer_url")
                providers = movie_details.get("watch_providers", [])

                # 生成大綱
                synopsis = self.gemini_service.generate_movie_synopsis(
                    movie_title,
                    year,
                    genres_cn,
                    avg_rating if isinstance(avg_rating, (int, float)) else 0
                )

                response = f"🎬 {movie_title}\n\n"
                if synopsis:
                    response += f"📖 大綱：\n{synopsis}\n\n"
                response += "📊 電影資訊：\n"
                if year != "未知":
                    response += f"• 📅 年份：{year}\n"
                response += f"• 🏷️ 類型：{genres_cn}\n"
                if runtime_min:
                    response += f"• ⏱️ 片長：{runtime_min} 分鐘\n"
                if avg_rating and avg_rating > 0:
                    rating_text = f"⭐ {avg_rating:.1f} / 5.0"
                    if rating_count and rating_count > 0:
                        rating_text += f" ({rating_count:,} 人評分)"
                    response += f"• ⭐ 整體評價：{rating_text}\n"
                if cast_names:
                    response += f"• 🎭 主要演員：{', '.join(cast_names[:5])}\n"
                if providers:
                    response += f"• 📺 可看平台：{', '.join(providers)}\n"
                if trailer_url:
                    response += f"• ▶️ 預告片：{trailer_url}\n"
                return response
            
            # 構建電影資訊摘要
            movie_info_text = f"""
電影名稱：{movie_title}
年份：{movie_details.get('year', '未知')}
類型：{movie_details.get('genres_cn', '未分類')}
平均評分：{movie_details.get('avg_rating', 0):.1f} / 5.0
評分人數：{movie_details.get('rating_count', 0):,}
"""
            if movie_details.get('runtime'):
                movie_info_text += f"片長：{movie_details.get('runtime')} 分鐘\n"
            if movie_details.get('cast'):
                movie_info_text += f"主要演員：{', '.join(movie_details.get('cast', [])[:5])}\n"
            if movie_details.get('watch_providers'):
                movie_info_text += f"可看平台：{', '.join(movie_details.get('watch_providers', []))}\n"
            
            # 使用 Gemini 回答問題
            answer = self.gemini_service.answer_movie_question(
                question=question,
                movie_title=movie_title,
                movie_info=movie_info_text.strip()
            )
            
            return answer
            
        except Exception as e:
            logger.error(f"處理電影問題失敗: {e}")
            return f"關於《{movie_context.get('movie_title', '這部電影')}》，我暫時無法回答。請試試其他問題，或說「推薦電影」來找新電影！"
    
    def _get_fallback_response(self) -> str:
        """備用回應（當 AI 失敗時）"""
        return """🎬 我是電影推薦機器人！

我可以幫你：
• 🎯 推薦電影（說「推薦電影」或指定類型）
• 🔍 搜尋電影（說「搜尋 電影名稱」）
• 👤 查看偏好（說「查看偏好」）
• 📖 操作說明（說「怎麼用」）

💡 試試說：「我想看喜劇電影」或「怎麼用」來開始！"""
    
    def handle_movie_info_request(self, movie_id: str, movie_title: str, user_id: str = None):
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
            runtime_min = movie_details.get("runtime")
            cast_names = movie_details.get("cast", [])
            trailer_url = movie_details.get("trailer_url")
            providers = movie_details.get("watch_providers", [])
            
            # 生成推薦原因（不顯示大綱，符合預期格式）
            movie_info_for_reason = {
                "movieId": movie_id,
                "title": movie_title,
                "year": year,
                "genres": genres_cn,
                "avg_rating": avg_rating if isinstance(avg_rating, (int, float)) else 0
            }
            explanation = self.gemini_service.generate_movie_recommendation_reason(movie_info_for_reason)

            # 構建詳細回應（條列式、含推薦原因）
            response = f"🎬 {movie_title}\n\n"

            # 條列資訊
            response += "📊 電影資訊：\n"
            if year != "未知":
                response += f"• 📅 年份：{year}\n"
            response += f"• 🏷️ 類型：{genres_cn}\n"
            if runtime_min:
                response += f"• ⏱️ 片長：{runtime_min} 分鐘\n"
            if avg_rating > 0:
                rating_text = f"⭐ {avg_rating:.1f} / 5.0"
                if rating_count > 0:
                    rating_text += f" ({rating_count:,} 人評分)"
                response += f"• ⭐ 整體評價：{rating_text}\n"
            # 不在「更多資訊」初次顯示演員/平台/預告片（保留於後續提問）

            # 推薦原因
            if explanation:
                response += f"\n💡 推薦原因：\n{explanation}\n\n"

            # 後續提問引導
            response += "\n❓ 想了解更多？可以問我：\n"
            response += "• 主要演員有哪些？\n"
            response += "• 在哪裡可以看？\n"
            response += "• 有預告片嗎？\n"
            response += "• 或其他關於這部電影的問題！"
            
            # 記錄當前電影上下文（供後續提問使用）
            if user_id:
                self.user_preference_service.set_current_movie_context(
                    user_id,
                    movie_id,
                    movie_title,
                    movie_details
                )
            
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

            # 先查詢本地 movie_info 儲存（優先級最高）
            stored = {}
            try:
                stored = self.movie_info_store.get_by_id(int(movie_id)) or self.movie_info_store.get_by_title_year(movie_title, year)
            except Exception:
                stored = {}

            # 取得片長與 TMDb 擴充資訊（若本地無對應欄位時再取得）
            runtime_min = stored.get("runtime")
            cast_list = stored.get("cast")
            trailer_url = stored.get("trailer_url")
            providers = stored.get("watch_providers")

            if runtime_min is None:
                runtime_min = self.movie_metadata_service.get_runtime(int(movie_id))
            extras = {"cast": cast_list, "trailer_url": trailer_url, "watch_providers": providers}
            if not cast_list or not trailer_url or not providers:
                try:
                    api_extras = self.movie_metadata_service.fetch_extras(int(movie_id))
                    # 僅在缺少時補齊
                    extras["cast"] = extras.get("cast") or api_extras.get("cast", [])
                    extras["trailer_url"] = extras.get("trailer_url") or api_extras.get("trailer_url")
                    extras["watch_providers"] = extras.get("watch_providers") or api_extras.get("watch_providers", [])
                except Exception:
                    pass

            # 將最新整合結果回寫到本地儲存（避免下次再打 API）
            try:
                self.movie_info_store.upsert({
                    "movieId": int(movie_id),
                    "title": movie.get("title", movie_title),
                    "year": year,
                    "genres": genres_en,
                    "genres_cn": genres_cn,
                    "avg_rating": avg_rating,
                    "rating_count": rating_count,
                    "runtime": runtime_min,
                    "cast": extras.get("cast", []),
                    "trailer_url": extras.get("trailer_url"),
                    "watch_providers": extras.get("watch_providers", [])
                })
            except Exception:
                pass
            
            return {
                "title": movie.get("title", movie_title),
                "year": year,
                "genres": genres_en,
                "genres_cn": genres_cn,
                "avg_rating": avg_rating,
                "rating_count": rating_count,
                "runtime": runtime_min,
                "cast": extras.get("cast", []),
                "trailer_url": extras.get("trailer_url"),
                "watch_providers": extras.get("watch_providers", [])
            }
            
        except Exception as e:
            logger.error(f"獲取電影詳細資訊失敗: {e}")
            return {"title": movie_title}
    
    def handle_postback(self, event: PostbackEvent):
        """處理 Postback 事件"""
        try:
            data = event.postback.data
            reply_token = event.reply_token
            user_id = event.source.user_id
            
            logger.info(f"收到 Postback 事件: {data}")
            
            # 先發送確認訊息
            try:
                confirmation_message = "🔍 正在查詢電影資訊，請稍候..."
                self.line_bot_service.reply_message(reply_token, confirmation_message)
                # 由於已發送確認訊息，後續需要使用 push_message
                use_push = True
            except Exception as e:
                logger.warning(f"發送確認訊息失敗: {e}，將直接回覆結果")
                use_push = False
            
            # 根據 postback data 處理不同動作
            if data.startswith("movie_info_"):
                # 解析電影資訊請求
                parts = data.replace("movie_info_", "").split("_", 1)
                if len(parts) >= 2:
                    movie_id = parts[0]
                    movie_title = parts[1]
                    response = self.handle_movie_info_request(movie_id, movie_title, user_id)
                else:
                    response = "抱歉，無法獲取電影資訊。"
            else:
                response = "收到你的操作請求！"
            
            # 根據是否發送確認訊息決定使用 reply_message 或 push_message
            if use_push:
                self.line_bot_service.push_message(user_id, response)
            else:
                self.line_bot_service.reply_message(reply_token, response)
            
        except Exception as e:
            logger.error(f"處理 Postback 事件時發生錯誤: {e}")
            error_message = "抱歉，系統發生錯誤，請稍後再試。"
            self.line_bot_service.reply_message(event.reply_token, error_message)
    
    def handle_follow(self, event: FollowEvent):
        """處理加入好友事件"""
        try:
            user_id = event.source.user_id
            reply_token = event.reply_token
            
            logger.info(f"新用戶加入: {user_id}")
            
            # 創建歡迎訊息
            welcome_message = self._create_welcome_message()
            
            # 發送歡迎訊息
            self.line_bot_service.reply_message(reply_token, welcome_message)
            
            # 初始化用戶偏好（如果不存在）
            user_prefs = self.user_preference_service.load_user_preferences(user_id)
            if not user_prefs:
                self.user_preference_service.save_user_preferences(user_id, self.user_preference_service._default_preferences())
            
        except Exception as e:
            logger.error(f"處理加入好友事件時發生錯誤: {e}")
            if reply_token:
                error_message = "歡迎！我是電影推薦機器人，很高興認識你！"
                self.line_bot_service.reply_message(reply_token, error_message)
    
    def handle_unfollow(self, event: UnfollowEvent):
        """處理取消追蹤事件"""
        try:
            user_id = event.source.user_id
            logger.info(f"用戶取消追蹤: {user_id}")
            # 這裡可以做清理工作，例如標記用戶為非活躍狀態
        except Exception as e:
            logger.error(f"處理取消追蹤事件時發生錯誤: {e}")
    
    def _create_welcome_message(self) -> str:
        """創建歡迎訊息"""
        message = """🎬 歡迎使用電影推薦機器人！

嗨！我是你的智能電影推薦助手，我可以根據你的喜好推薦最適合的電影給你。

✨ 主要功能：

🎯 電影推薦
   • 告訴我你想看的類型（喜劇、動作、劇情...）
   • 也可以指定年份（如「2023年的電影」）
   • 或排除不喜歡的類型（如「我不喜歡恐怖片」）

📚 快速上手指南：

💬 試試這些指令：
   • "推薦電影" - 開始推薦
   • "我想看喜劇電影" - 指定類型
   • "2023年的電影" - 按年份推薦
   • "怎麼用" - 查看完整說明
   • "查看偏好" - 查看你的偏好設定

🎭 個人化功能：
   • 系統會記住你的喜好，越用越懂你
   • 說「查看偏好」可以查看目前的偏好設定
   • 說「重置偏好」可以清除偏好重新開始

💡 現在就試試說「推薦電影」或「我想看喜劇電影」來開始吧！"""
        
        return message
