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
                "genres": ["Comedy", "Action", "Drama"],
                "mood": "輕鬆|緊張|浪漫|刺激",
                "keywords": [],
                "era": "現代|經典|復古",
                "language": "中文|英文|日文",
                "exclude_genres": ["Horror", "Children"],
                "year": null,
                "countries": ["Japan", "Korea"],
                "exclude_countries": ["United States", "United Kingdom"]
            }}
            
            **重要規則**：
            1. **類型請使用英文**：genres 和 exclude_genres 請使用英文類型名稱，例如：
               - "浪漫"、"愛情"、"戀愛" → genres: ["Romance"]
               - "動作"、"打鬥" → genres: ["Action"]
               - "喜劇"、"搞笑" → genres: ["Comedy"]
               - "動畫"、"卡通" → genres: ["Animation"]
               - "劇情"、"感人" → genres: ["Drama"]
               - "恐怖"、"驚悚" → genres: ["Horror"]
               - "科幻" → genres: ["Sci-Fi"]
               - "兒童" → genres: ["Children"]
            2. **年份優先**: 如果使用者提到具體年份（如"2023年"、"2022的電影"、"1995"），請在 year 欄位填入該年份（整數），並在 keywords 中排除年份數字
            3. **排除類型**: 如果使用者表達「不喜歡XXX電影」、「不要XXX」、「排除XXX」，請在 exclude_genres 中加入該類型的英文。例如：「不喜歡兒童電影」→ exclude_genres: ["Children"]
            4. **國家/地區（英文）**：將地名統一為英文國名或常見地區名，例如：
               - 日本→"Japan"、韓國→"Korea"、台灣→"Taiwan"、香港→"Hong Kong"、中國→"China"
               - 美國→"United States"、英國→"United Kingdom"、法國→"France"、德國→"Germany"
            5. **沒有排除**: 如果沒有提到不喜歡的類型/國家，exclude_genres/exclude_countries 設為 []
            
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
            "year": None,
            "countries": [],
            "exclude_countries": []
        }
        
        # 簡單的關鍵字匹配
        message_lower = user_message.lower()
        
        genre_keywords = {
            "Comedy": ["喜劇", "搞笑", "輕鬆", "幽默", "comedy"],
            "Action": ["動作", "刺激", "冒險", "打鬥", "action"],
            "Drama": ["劇情", "感人", "深度", "drama"],
            "Romance": ["愛情", "浪漫", "戀愛", "romance"],
            "Horror": ["恐怖", "驚悚", "嚇人", "horror"],
            "Sci-Fi": ["科幻", "未來", "太空", "sci-fi"],
            "Animation": ["動畫", "卡通", "animation"],
            "Mystery": ["懸疑", "推理", "神秘", "mystery"],
            "Children": ["兒童", "小孩", "children"]
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

        # 簡單偵測國家/地區（中英）
        country_map = {
            "日本": "Japan", "韓國": "Korea", "韓": "Korea", "台灣": "Taiwan", "臺灣": "Taiwan", "香港": "Hong Kong", "中國": "China",
            "美國": "United States", "英國": "United Kingdom", "法國": "France", "德國": "Germany",
            "japan": "Japan", "korea": "Korea", "taiwan": "Taiwan", "hong kong": "Hong Kong", "china": "China",
            "united states": "United States", "usa": "United States", "uk": "United Kingdom", "united kingdom": "United Kingdom",
            "france": "France", "germany": "Germany"
        }
        low = user_message.lower()
        for k, v in country_map.items():
            if k in low:
                preferences["countries"].append(v)
        # 排除語句（不看/不要 X 國）
        exclude_triggers = ["不看", "不要", "排除", "no ", "not "]
        for k, v in country_map.items():
            if any(tr in low for tr in exclude_triggers) and k in low:
                preferences["exclude_countries"].append(v)
        # 去重
        preferences["countries"] = sorted(list(set(preferences["countries"])))
        preferences["exclude_countries"] = sorted(list(set(preferences["exclude_countries"])))
        
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
            
            # 檢查是否明確指定了類型
            explicit_genres = user_preferences.get("genres", [])
            has_explicit_genres = explicit_genres and len(explicit_genres) > 0
            
            prompt = f"""
            使用者說：「{user_message}」
            
            使用者偏好：{json.dumps(user_preferences, ensure_ascii=False)}
            
            以下是候選電影清單：
            {movies_text}
            
            請根據使用者偏好和訊息，重新排序這些電影，並給出推薦理由。
            
            **重要排序規則**：
            {"⚠️ 使用者明確指定了類型：" + "、".join(explicit_genres) + "，這些類型的電影必須優先排在前面！即使其他電影的歷史偏好更高，也要以使用者當前指定的類型為準。" if has_explicit_genres else "⚠️ 使用者沒有明確指定類型，這是一個模糊的請求。請優先參考使用者的歷史偏好（在 user_preferences 中），確保推薦符合使用者長期以來的喜好。如果歷史偏好中有 favorite_genres，這些類型的電影應該排在前面！"}
            另外：如果 user_preferences 中包含 "countries" 或 "exclude_countries"，請優先推薦符合 countries 的電影，並將屬於 exclude_countries 的電影排後或排除。
            
            注意：
            1. 推薦理由中請保持電影的英文原名，不要翻譯成中文
            2. 如果使用者明確指定類型，該類型電影應佔據前 3-4 個位置
            3. 如果沒有明確指定類型，可以考慮使用者的歷史偏好
            
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
    
    def generate_movie_synopsis(self, movie_title: str, year: any = None, genres: str = "", rating: float = 0) -> str:
        """生成電影大綱（不劇透）"""
        if not self.model:
            return "這是一部值得觀看的電影。"
        
        try:
            year_str = f"{year}年上映" if year and year != "未知" else ""
            genres_str = f"類型為 {genres}" if genres else ""
            rating_str = f"評分 {rating:.1f}/5.0" if rating > 0 else ""
            
            info_parts = [part for part in [year_str, genres_str, rating_str] if part]
            movie_info = "、".join(info_parts) if info_parts else "這部電影"
            
            prompt = f"""
            請為以下電影生成一個簡短的大綱描述（約 50-100 字），要求：
            
            電影名稱：{movie_title}
            資訊：{movie_info}
            
            **重要要求**：
            1. 只描述故事背景、角色設定、主要情節開端，不要透露結局或重要劇情轉折
            2. 用吸引人但不過度誇張的方式描述
            3. 保持客觀，不要過度評價
            4. 如果不知道這部電影的具體內容，可以根據類型（{genres}）和名稱合理推測背景設定
            5. 使用繁體中文，語氣自然友善
            
            只回傳大綱內容，不要其他說明或標題。
            """
            
            response = self.model.generate_content(prompt)
            synopsis = response.text.strip()
            
            # 清理可能的格式問題
            synopsis = synopsis.replace("大綱：", "").replace("概要：", "").strip()
            
            return synopsis if synopsis else "這是一部值得觀看的電影。"
            
        except Exception as e:
            logger.error(f"生成電影大綱失敗: {e}")
            return "這是一部值得觀看的電影。"

    def translate_title_to_english(self, text: str) -> Optional[str]:
        """將可能是中文/他語的片名翻成常見英文片名；不確定則回傳 None。"""
        try:
            if not self.model or not text:
                return None
            prompt = f"""
你是一個電影名稱翻譯助手。請將以下可能是中文（或其他語言）的電影名稱翻譯成常見的英文片名。
只輸出英文片名本身，如果不確定請回覆 None。

輸入：{text}
輸出：
"""
            resp = self.model.generate_content(prompt)
            result = (resp.text or "").strip()
            result = result.replace('"', '').replace("'", '').strip()
            # 若仍含中文字元，視為不確定
            if any('\u4e00' <= ch <= '\u9fff' for ch in result):
                return None
            if len(result) < 2 or len(result) > 200:
                return None
            return result
        except Exception as e:
            logger.error(f"標題翻譯失敗: {e}")
            return None
    
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
    
    def answer_movie_question(self, question: str, movie_title: str, movie_info: str) -> str:
        """回答關於特定電影的問題"""
        if not self.model:
            return f"關於《{movie_title}》，我暫時無法回答。請試試其他問題！"
        
        try:
            prompt = f"""
            你是一個友善的電影推薦助手。使用者正在詢問關於電影《{movie_title}》的問題。
            
            以下是該電影的詳細資訊（只有這些資訊可供參考）：
            {movie_info}
            
            使用者的問題：「{question}」
            
            **重要規則**：
            1. **只能使用提供的資訊回答**：如果答案在提供的資訊中，請直接回答
            2. **沒有資訊時明確告知**：如果問題的答案不在提供的資訊中，必須明確告訴使用者「我沒有這項資訊」或「我的資料庫裡沒有這個資訊」
            3. **不要猜測或推測**：絕對不要編造、推測或臆測不存在的資訊
            4. **誠實回應**：如果使用者問到劇情、詳細內容、其他演員（不在列表中的）、導演、編劇等沒有提供的資訊，請明確說明沒有這項資訊
            5. **開放性問題處理**：如果使用者問「你知道關於這部電影的全部資訊嗎」「告訴我所有資訊」「有什麼資訊」等開放性問題，請整理並列出所有已知資訊
            
            回答要求：
            - 用繁體中文回答
            - 語氣親切友善，就像朋友聊天一樣
            - **如果是開放性問題（問所有資訊），可以詳細列出所有已知資訊（3-5句話）；如果是具體問題，保持簡潔（2-4句話即可）**
            - 如果有資訊可以回答，請具體說明（例如：主要演員是 XXX、評分是 X.X 分）
            - 如果沒有資訊，明確說「關於這個問題，我的資料庫裡沒有這項資訊」或「抱歉，我沒有這個資訊」
            - 電影名稱請保持英文原名，不要翻譯成中文
            - 如果問題與電影無關（例如「今天天氣如何」），可以禮貌地引導回電影話題
            
            請直接回傳回答內容，不要包含其他格式或額外說明。
            """
            
            response = self.model.generate_content(prompt)
            answer = response.text.strip()
            
            logger.info(f"成功回答電影問題: {movie_title}")
            return answer
            
        except Exception as e:
            logger.error(f"回答電影問題失敗: {e}")
            return f"關於《{movie_title}》，我暫時無法回答。請試試其他問題，或說「推薦電影」來找新電影！"

    def classify_message(self, text: str) -> Dict[str, any]:
        """判斷訊息是否與電影相關，以及是否屬於『與電影相關但指令不正確/不完整』。

        回傳格式：{"related": bool, "malformed": bool}
        """
        if not self.model or not text:
            return {"related": False, "malformed": False}
        try:
            prompt = f"""
請閱讀下列訊息並判斷：
1) 是否與電影主題相關（推薦、搜尋、片名、演員、平台、年份、類型、評分等）
2) 是否與電影相關但使用者未使用清楚的操作指令（例如只提到關鍵詞、含糊描述、缺少必要關鍵字）

訊息："{text}"

請只輸出 JSON：{{
  "related": true/false,
  "malformed": true/false
}}
            """
            resp = self.model.generate_content(prompt)
            raw = (resp.text or "").strip()
            raw = raw.replace('```json', '').replace('```', '').strip()
            import json as _json
            data = _json.loads(raw)
            return {
                "related": bool(data.get("related", False)),
                "malformed": bool(data.get("malformed", False)),
            }
        except Exception as e:
            logger.error(f"訊息分類失敗: {e}")
            return {"related": False, "malformed": False}
