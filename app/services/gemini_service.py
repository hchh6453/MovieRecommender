"""
Gemini AI 服務
用於自然語言理解和偏好抽取
"""
import json
import logging
from typing import Dict, List, Optional

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logging.warning("google-generativeai not installed. Gemini features will be disabled.")

from ..config import settings

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        """初始化 Gemini AI 服務"""
        if not GEMINI_AVAILABLE:
            logger.warning("Gemini AI 不可用，將使用基礎推薦")
            self.model = None
            return
            
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            # 使用最新的穩定模型
            self.model = genai.GenerativeModel('gemini-2.5-flash')
            logger.info("Gemini AI 服務初始化成功")
        except Exception as e:
            logger.error(f"Gemini AI 初始化失敗: {e}")
            self.model = None
    
    def extract_preferences(self, user_message: str) -> Dict[str, any]:
        """從使用者訊息中抽取電影偏好"""
        if not self.model:
            return self._fallback_preferences(user_message)
        
        try:
            prompt = f"""
            分析以下使用者訊息，提取電影偏好資訊，特別是年份資訊和排除的類型：
            
            使用者訊息：「{user_message}」
            
            請以 JSON 格式回傳，包含以下欄位：
            {{
                "genres": ["喜劇", "動作", "劇情"],
                "mood": "輕鬆|緊張|浪漫|刺激",
                "keywords": [],
                "era": "現代|經典|復古",
                "language": "中文|英文|日文",
                "exclude_genres": ["恐怖", "兒童"],
                "year": null
            }}
            
            **重要規則**：
            1. **年份優先**: 如果使用者提到具體年份（如"2023年"、"2022的電影"、"1995"），請在 year 欄位填入該年份（整數），並在 keywords 中排除年份數字
            2. **排除類型**: 如果使用者表達「不喜歡XXX電影」、「不要XXX」、「排除XXX」，請在 exclude_genres 中加入該類型（中文）。例如：「不喜歡兒童電影」→ exclude_genres: ["兒童"]
            3. **排除類型範例**: "我不喜歡恐怖片" → exclude_genres: ["恐怖"]
            4. **排除類型範例**: "不要兒童電影" → exclude_genres: ["兒童"]
            5. **沒有排除**: 如果沒有提到不喜歡的類型，exclude_genres 設為空陣列 []
            
            只回傳 JSON，不要其他說明文字。
            """
            
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            # 嘗試解析 JSON
            try:
                # 清理回應文字，移除可能的 markdown 格式
                result_text = result_text.strip()
                if result_text.startswith('```json'):
                    result_text = result_text[7:]
                if result_text.endswith('```'):
                    result_text = result_text[:-3]
                result_text = result_text.strip()
                
                preferences = json.loads(result_text)
                logger.info(f"成功抽取偏好: {preferences}")
                return preferences
            except json.JSONDecodeError:
                logger.warning(f"無法解析 Gemini 回應為 JSON: {result_text}")
                return self._fallback_preferences(user_message)
                
        except Exception as e:
            logger.error(f"Gemini 偏好抽取失敗: {e}")
            return self._fallback_preferences(user_message)
    
    def _fallback_preferences(self, user_message: str) -> Dict[str, any]:
        """當 Gemini 不可用時的備用偏好抽取"""
        import re
        
        preferences = {
            "genres": [],
            "mood": None,
            "keywords": [],
            "era": None,
            "language": None,
            "exclude_genres": [],
            "year": None
        }
        
        # 簡單的關鍵字匹配
        message_lower = user_message.lower()
        
        genre_keywords = {
            "喜劇": ["喜劇", "搞笑", "輕鬆", "幽默", "comedy"],
            "動作": ["動作", "刺激", "冒險", "打鬥", "action"],
            "劇情": ["劇情", "感人", "深度", "drama"],
            "愛情": ["愛情", "浪漫", "戀愛", "romance"],
            "恐怖": ["恐怖", "驚悚", "嚇人", "horror"],
            "科幻": ["科幻", "未來", "太空", "sci-fi"],
            "動畫": ["動畫", "卡通", "animation"],
            "懸疑": ["懸疑", "推理", "神秘", "mystery"]
        }
        
        for genre, keywords in genre_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                preferences["genres"].append(genre)
        
        # 抽取年份
        year_match = re.search(r'\b(19|20)\d{2}\b', user_message)
        if year_match:
            preferences["year"] = int(year_match.group())
        
        # 抽取關鍵字
        words = user_message.split()
        preferences["keywords"] = [word for word in words if len(word) > 1]
        
        return preferences
    
    def rerank_recommendations(self, candidates: List[Dict], user_preferences: Dict[str, any], user_message: str) -> List[Dict]:
        """使用 Gemini 重新排序推薦結果"""
        if not self.model or not candidates:
            return candidates
        
        try:
            # 準備候選電影資訊
            movies_info = []
            for i, movie in enumerate(candidates[:10]):  # 限制候選數量
                movies_info.append(f"{i+1}. {movie['title']} - {movie['genres']}")
            
            movies_text = "\n".join(movies_info)
            
            prompt = f"""
            使用者說：「{user_message}」
            
            使用者偏好：{json.dumps(user_preferences, ensure_ascii=False)}
            
            以下是候選電影清單：
            {movies_text}
            
            請根據使用者偏好和訊息，重新排序這些電影，並給出推薦理由。
            
            注意：推薦理由中請保持電影的英文原名，不要翻譯成中文。
            
            回傳格式：
            {{
                "ranked_indices": [3, 1, 5, 2, 4],
                "reasons": {{
                    "3": "這部電影完全符合使用者想要的輕鬆喜劇風格",
                    "1": "經典作品，符合使用者對品質的要求"
                }}
            }}
            
            只回傳 JSON，不要其他文字。
            """
            
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            try:
                # 清理回應文字，移除可能的 markdown 格式
                result_text = result_text.strip()
                if result_text.startswith('```json'):
                    result_text = result_text[7:]
                if result_text.endswith('```'):
                    result_text = result_text[:-3]
                result_text = result_text.strip()
                
                result = json.loads(result_text)
                ranked_indices = result.get("ranked_indices", list(range(len(candidates))))
                reasons = result.get("reasons", {})
                
                # 重新排序候選清單
                reranked = []
                for idx in ranked_indices:
                    if 0 <= idx < len(candidates):
                        movie = candidates[idx].copy()
                        movie["reason"] = reasons.get(str(idx), "推薦給你")
                        reranked.append(movie)
                
                logger.info(f"成功重新排序 {len(reranked)} 部電影")
                return reranked
                
            except json.JSONDecodeError:
                logger.warning(f"無法解析 Gemini 重排序回應: {result_text}")
                return candidates
                
        except Exception as e:
            logger.error(f"Gemini 重排序失敗: {e}")
            return candidates
    
    def generate_recommendation_explanation(self, user_message: str, recommendations: List[Dict]) -> str:
        """生成推薦解釋"""
        if not self.model:
            return f"根據「{user_message}」為你推薦了 {len(recommendations)} 部電影！"
        
        try:
            movies_text = "\n".join([f"- {movie['title']}" for movie in recommendations[:3]])
            
            prompt = f"""
            使用者說：「{user_message}」
            
            推薦的電影：
            {movies_text}
            
            請用友善、自然的語氣，簡短解釋為什麼推薦這些電影。
            注意：請保持電影的英文原名，不要翻譯成中文。
            回傳一段話，不要超過 50 字。
            """
            
            response = self.model.generate_content(prompt)
            explanation = response.text.strip()
            
            return explanation if explanation else f"根據「{user_message}」為你推薦了這些電影！"
            
        except Exception as e:
            logger.error(f"生成推薦解釋失敗: {e}")
            return f"根據「{user_message}」為你推薦了 {len(recommendations)} 部電影！"
    
    def generate_movie_recommendation_reason(self, movie_info: Dict[str, str]) -> str:
        """為單部電影生成推薦原因"""
        if not self.model:
            return "這是一部值得觀看的電影！"
        
        try:
            movie_title = movie_info.get("title", "這部電影")
            year = movie_info.get("year", "")
            genres = movie_info.get("genres", "")
            avg_rating = movie_info.get("avg_rating", 0)
            
            # 構建電影資訊描述
            info_parts = []
            if year and year != "未知":
                info_parts.append(f"於 {year} 年上映")
            if genres:
                info_parts.append(f"類型包含 {genres}")
            if avg_rating > 0:
                info_parts.append(f"獲得 {avg_rating:.1f} 顆星的好評")
            
            movie_context = "、".join(info_parts) if info_parts else "這部優秀的作品"
            
            prompt = f"""
            以下是電影資訊：
            
            電影名稱：{movie_title}
            {f"上映年份：{year}" if year and year != "未知" else ""}
            {f"電影類型：{genres}" if genres else ""}
            {f"平均評分：{avg_rating:.1f} / 5.0" if avg_rating > 0 else ""}
            
            請為這部電影生成一個簡潔、吸引人的推薦原因。
            
            要求：
            1. 用繁體中文回答
            2. 2-3句話即可
            3. 突出電影的亮點和特色，可以參考電影類型
            4. 語氣親切自然，像朋友推薦一樣
            5. 不要包含電影情節劇透
            6. 電影名稱請保持英文原名，不要翻譯成中文
            7. 如果知道類型，可以說明為什麼喜歡這類型的人會愛上這部電影
            8. 如果評分很高，可以強調這點
            
            請直接回傳推薦原因，不要包含其他格式或額外說明。
            """
            
            response = self.model.generate_content(prompt)
            reason = response.text.strip()
            
            logger.info(f"成功生成電影推薦原因: {movie_title}")
            return reason
            
        except Exception as e:
            logger.error(f"生成電影推薦原因失敗: {e}")
            return "這是一部值得觀看的電影！"
