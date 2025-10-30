"""
電影資訊提交服務
處理使用者提交的電影資訊，包含安全驗證與惡意內容檢測
"""
import json
import os
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import re

from ..config import settings
from .gemini_service import GeminiService

logger = logging.getLogger(__name__)


class MovieSubmissionService:
    def __init__(self, storage_dir: str = "data/user_submissions"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self.pending_file = os.path.join(storage_dir, "pending_submissions.json")
        self.approved_file = os.path.join(storage_dir, "approved_submissions.json")
        self.user_submission_log_file = os.path.join(storage_dir, "user_submission_log.json")
        self.appeal_file = os.path.join(storage_dir, "appeal_submissions.json")  # 申訴暫存區
        self.gemini_service = GeminiService()
        
        # 提交頻率限制設定
        self.MAX_SUBMISSIONS_PER_DAY = 3  # 每天最多3次
        self.SUBMISSION_WINDOW_HOURS = 24  # 檢查窗口：24小時
    
    def validate_and_submit(self, user_id: str, user_message: str) -> Dict[str, any]:
        """
        驗證並提交使用者提供的電影資訊
        
        返回:
            {
                "success": bool,
                "message": str,
                "submission_id": Optional[str],
                "needs_review": bool
            }
        """
        try:
            # 0. 檢查提交頻率限制（優先檢查）
            frequency_check = self._check_submission_frequency(user_id)
            if not frequency_check["allowed"]:
                return {
                    "success": False,
                    "message": frequency_check["message"],
                    "submission_id": None,
                    "needs_review": False
                }
            
            # 1. 提取電影資訊（使用 Gemini 結構化提取）
            movie_data = self._extract_movie_info(user_message)
            
            if not movie_data:
                return {
                    "success": False,
                    "message": "無法從你的訊息中提取電影資訊。請使用以下格式：\n「新增電影：電影名稱 (年份)\n類型：動作|喜劇\n描述：...」",
                    "submission_id": None,
                    "needs_review": False
                }
            
            # 2. 基本格式檢查
            format_check = self._check_basic_format(movie_data)
            if not format_check["valid"]:
                return {
                    "success": False,
                    "message": format_check["message"],
                    "submission_id": None,
                    "needs_review": False
                }
            
            # 3. 使用 Gemini AI 進行安全性與真實性驗證
            validation_result = self._validate_with_ai(movie_data, user_message)
            
            # AI 驗證結果處理（採用保守策略）：
            # - 只有 AI 非常確定是安全且真實的（safe=true 且 confidence >= 0.8）→ 允許提交
            # - 其他情況（不確定、可疑、不安全）→ 全部拒絕，保護系統安全
            validation_safe = validation_result.get("safe", False)
            validation_confidence = validation_result.get("confidence", 0.5)
            validation_reason = validation_result.get("reason", "")
            
            # 嚴格驗證：只有 AI 非常確定是安全且真實的才允許
            if not validation_safe or validation_confidence < 0.8:
                # AI 不確定或不安全，直接拒絕（保守策略）
                if not validation_safe:
                    reason_msg = f"\n\n原因：{validation_reason}"
                else:
                    reason_msg = f"\n\nAI 驗證信心度不足（{validation_confidence:.1%}），為保護系統安全，此提交已被拒絕。"
                
                # 儲存被拒絕的提交（供申訴使用）
                rejected_submission = {
                    "submission_id": f"rejected_{user_id}_{int(datetime.now().timestamp())}",
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat(),
                    "movie_data": movie_data,
                    "original_message": user_message,
                    "validation_safe": validation_safe,
                    "validation_confidence": validation_confidence,
                    "validation_reason": validation_reason,
                    "status": "rejected",
                    "can_appeal": True
                }
                self._save_rejected_submission(rejected_submission)
                
                return {
                    "success": False,
                    "message": f"❌ 提交的資訊未通過安全驗證。{reason_msg}\n\n💡 如你認為這是誤判，可以回覆「申訴」或「我要申訴」，管理員會重新審核。",
                    "submission_id": rejected_submission["submission_id"],
                    "needs_review": False,
                    "can_appeal": True,
                    "appeal_submission_id": rejected_submission["submission_id"]
                }
            
            # 4. 檢查是否與現有電影重複（或非常相似）
            duplicate_check = self._check_duplicates(movie_data)
            if duplicate_check["is_duplicate"]:
                return {
                    "success": False,
                    "message": f"⚠️ 這個電影可能已經存在於資料庫中。\n{duplicate_check.get('message', '')}",
                    "submission_id": None,
                    "needs_review": False
                }
            
            # 5. 記錄本次提交時間（更新提交日誌）
            self._record_submission(user_id)
            
            # 6. 儲存到待審核列表（不影響現有推薦系統）
            
            # 由於採用保守策略，只有到達這裡的都是 AI 非常確定的安全內容
            # 但仍建議人工審核以確保品質（可選）
            needs_review = validation_confidence < 0.95  # 只有極高信心度（95%+）才可能自動通過
            
            submission = {
                "submission_id": f"{user_id}_{int(datetime.now().timestamp())}",
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
                "movie_data": movie_data,
                "validation_safe": validation_safe,
                "validation_confidence": validation_confidence,
                "validation_reason": validation_reason,
                "status": "pending",  # pending, approved, rejected
                "needs_manual_review": needs_review,  # 特別標記是否需要人工判斷
                "reviewed_by": None,
                "reviewed_at": None
            }
            
            self._save_submission(submission)
            
            # 根據審核需求生成不同的回應訊息
            if needs_review:
                review_message = "📋 資訊已提交，管理員會審核後加入資料庫。"
            else:
                review_message = "✨ 資訊已通過高標準驗證，將盡快加入資料庫。"
            
            return {
                "success": True,
                "message": f"✅ 電影資訊已提交！\n\n{review_message}",
                "submission_id": submission["submission_id"],
                "needs_review": needs_review
            }
            
        except Exception as e:
            logger.error(f"處理電影提交失敗: {e}")
            return {
                "success": False,
                "message": "❌ 處理提交時發生錯誤，請稍後再試。",
                "submission_id": None,
                "needs_review": False
            }
    
    def _extract_movie_info(self, user_message: str) -> Optional[Dict]:
        """使用 Gemini 提取電影資訊"""
        try:
            prompt = f"""
            從以下使用者訊息中提取電影資訊：
            
            「{user_message}」
            
            請以 JSON 格式回傳，包含以下欄位：
            {{
                "title": "電影名稱（必須是英文）",
                "year": 年份（整數，可選）,
                "genres": ["類型1", "類型2"]（可以是中文或英文）,
                "description": "電影描述（可選）",
                "tags": ["標籤1", "標籤2"]（可選）
            }}
            
            重要規則：
            1. title（電影名稱）必須是英文，如果是中文請翻譯成英文
            2. genres（類型）可以是中文，我們會自動翻譯
            3. 如果無法提取完整資訊，回傳 null。
            
            只回傳 JSON，不要其他說明。
            """
            
            response = self.gemini_service.model.generate_content(prompt)
            result_text = response.text.strip()
            
            # 清理 JSON
            result_text = result_text.replace('```json', '').replace('```', '').strip()
            
            movie_data = json.loads(result_text)
            if movie_data.get("title"):
                # 將中文類型翻譯成英文
                genres = movie_data.get("genres", [])
                if genres:
                    from ..services.line_bot_service import translate_genres_to_english
                    movie_data["genres"] = translate_genres_to_english(genres)
                
                return movie_data
            return None
            
        except Exception as e:
            logger.error(f"提取電影資訊失敗: {e}")
            return None
    
    def _check_basic_format(self, movie_data: Dict) -> Dict[str, any]:
        """基本格式檢查"""
        title = movie_data.get("title", "").strip()
        
        # 檢查標題長度
        if not title or len(title) < 2:
            return {"valid": False, "message": "❌ 電影名稱太短，請提供完整的電影名稱。\n⚠️ 注意：電影名稱必須使用英文！"}
        
        if len(title) > 200:
            return {"valid": False, "message": "❌ 電影名稱太長，請檢查是否正確。"}
        
        # 檢查電影名稱是否為英文（不允許中文）
        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in title)
        if has_chinese:
            return {
                "valid": False, 
                "message": "❌ 電影名稱必須使用英文！請將中文電影名稱翻譯成英文後再提交。\n例如：「玩具總動員」→ 「Toy Story」"
            }
        
        # 檢查是否包含明顯的垃圾字詞
        spam_keywords = ["http://", "https://", "www.", "買", "賣", "折扣", "優惠", "立即點擊"]
        title_lower = title.lower()
        if any(keyword in title_lower for keyword in spam_keywords):
            return {"valid": False, "message": "❌ 標題包含不被允許的內容。"}
        
        # 檢查年份（如果提供）
        year = movie_data.get("year")
        if year:
            try:
                year_int = int(year)
                if year_int < 1888 or year_int > datetime.now().year + 2:
                    return {"valid": False, "message": "❌ 年份不合理，請檢查。"}
            except:
                return {"valid": False, "message": "❌ 年份格式不正確。"}
        
        # 檢查類型（如果提供）
        genres = movie_data.get("genres", [])
        if genres:
            valid_genres = ["動作", "喜劇", "劇情", "愛情", "恐怖", "驚悚", "科幻", "懸疑", "冒險", 
                          "戰爭", "動畫", "音樂", "紀錄片", "西部", "奇幻", "犯罪", "兒童"]
            # 部分匹配檢查
            if not any(any(vg in g for vg in valid_genres) for g in genres):
                return {"valid": False, "message": "❌ 電影類型不符合常見類型，請檢查。"}
        
        return {"valid": True, "message": ""}
    
    def _validate_with_ai(self, movie_data: Dict, original_message: str) -> Dict[str, any]:
        """使用 Gemini AI 進行安全性與真實性驗證"""
        try:
            prompt = f"""
            請驗證以下電影資訊是否為真實、安全且合理的電影資訊。
            
            電影資訊：
            {json.dumps(movie_data, ensure_ascii=False, indent=2)}
            
            原始訊息：
            「{original_message}」
            
            請檢查：
            1. **安全性**：是否包含惡意內容、垃圾資訊、廣告、連結、個人資訊等
            2. **真實性**：是否像真實存在的電影（標題、類型、年份是否合理搭配）
            3. **合理性**：內容是否符合電影資訊的格式和常見結構
            4. **惡意行為**：是否有意圖誤導、垃圾訊息、重複提交等跡象
            
            **重要規則（保守策略）**：
            - 只有當你**非常確定**（confidence >= 0.8）資訊是安全且真實的電影時，才設 safe=true
            - 如果你**有絲毫疑慮**或**不確定**資訊的真實性或安全性，設 safe=false，confidence 設為較低值（0.0-0.7）
            - 如果你**確定**是惡意、垃圾或廣告內容，設 safe=false，confidence 設為較高值（0.8-1.0）
            - **寧可過度嚴格，不要放過可疑內容**：保護系統安全優先於方便使用者
            
            請以 JSON 格式回傳：
            {{
                "safe": true/false,
                "confidence": 0.0-1.0（信心度：1.0=非常確定安全，0.5=不確定，0.8=較確定不安全）,
                "reason": "驗證理由（如果不確定，請說明原因）"
            }}
            
            只回傳 JSON，不要其他說明。
            """
            
            response = self.gemini_service.model.generate_content(prompt)
            result_text = response.text.strip()
            result_text = result_text.replace('```json', '').replace('```', '').strip()
            
            validation = json.loads(result_text)
            return validation
            
        except Exception as e:
            logger.error(f"AI 驗證失敗: {e}")
            # 驗證失敗時，出於安全考慮，返回不安全
            return {
                "safe": False,
                "confidence": 0.0,
                "reason": "驗證過程發生錯誤"
            }
    
    def _check_duplicates(self, movie_data: Dict) -> Dict[str, any]:
        """檢查是否與現有電影重複"""
        try:
            # 簡單的標題相似度檢查（可以在後續改進為更複雜的算法）
            title = movie_data.get("title", "").lower()
            
            # 檢查是否與資料庫中的電影非常相似（這裡簡化處理，實際可以整合到 recommendation_service）
            # 暫時只檢查完全相同的標題
            from ..services.recommendation_service import RecommendationService
            rec_service = RecommendationService()
            
            if rec_service.movies is not None:
                # 移除年份來比較
                title_clean = re.sub(r'\((\d{4})\)', '', title).strip()
                existing_titles = rec_service.movies["title"].str.lower().str.replace(r'\((\d{4})\)', '', regex=True).str.strip()
                
                # 檢查是否有相同或非常相似的標題
                matches = existing_titles[existing_titles == title_clean]
                if len(matches) > 0:
                    return {
                        "is_duplicate": True,
                        "message": "資料庫中可能已經有相同或相似的電影。"
                    }
            
            return {"is_duplicate": False, "message": ""}
            
        except Exception as e:
            logger.error(f"檢查重複失敗: {e}")
            return {"is_duplicate": False, "message": ""}
    
    def _save_rejected_submission(self, submission: Dict) -> None:
        """儲存被拒絕的提交（供申訴使用）"""
        try:
            # 載入現有被拒絕列表
            if os.path.exists(self.appeal_file):
                with open(self.appeal_file, 'r', encoding='utf-8') as f:
                    rejected_list = json.load(f)
            else:
                rejected_list = []
            
            # 添加新被拒絕的提交
            rejected_list.append(submission)
            
            # 保存
            with open(self.appeal_file, 'w', encoding='utf-8') as f:
                json.dump(rejected_list, f, ensure_ascii=False, indent=2)
            
            logger.info(f"被拒絕的提交已保存（可申訴）: {submission['submission_id']}")
            
        except Exception as e:
            logger.error(f"保存被拒絕提交失敗: {e}")
            raise
    
    def _save_submission(self, submission: Dict) -> None:
        """儲存提交的電影資訊"""
        try:
            # 載入現有待審核列表
            if os.path.exists(self.pending_file):
                with open(self.pending_file, 'r', encoding='utf-8') as f:
                    pending = json.load(f)
            else:
                pending = []
            
            # 添加新提交
            pending.append(submission)
            
            # 保存
            with open(self.pending_file, 'w', encoding='utf-8') as f:
                json.dump(pending, f, ensure_ascii=False, indent=2)
            
            logger.info(f"電影提交已保存: {submission['submission_id']}")
            
        except Exception as e:
            logger.error(f"保存提交失敗: {e}")
            raise
    
    def _check_submission_frequency(self, user_id: str) -> Dict[str, any]:
        """檢查使用者提交頻率是否超過限制"""
        try:
            # 載入使用者提交日誌
            if os.path.exists(self.user_submission_log_file):
                with open(self.user_submission_log_file, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
            else:
                log_data = {}
            
            # 取得該使用者的提交記錄
            user_log = log_data.get(user_id, [])
            
            # 計算最近24小時內的提交次數
            now = datetime.now()
            window_start = now - timedelta(hours=self.SUBMISSION_WINDOW_HOURS)
            
            recent_submissions = [
                sub_time for sub_time in user_log
                if datetime.fromisoformat(sub_time) >= window_start
            ]
            
            submission_count = len(recent_submissions)
            
            if submission_count >= self.MAX_SUBMISSIONS_PER_DAY:
                # 計算下次可提交的時間
                oldest_submission = min(recent_submissions)
                oldest_time = datetime.fromisoformat(oldest_submission)
                next_available = oldest_time + timedelta(hours=self.SUBMISSION_WINDOW_HOURS)
                hours_until_next = (next_available - now).total_seconds() / 3600
                
                return {
                    "allowed": False,
                    "message": f"⚠️ 提交頻率限制\n\n你已經在過去24小時內提交了 {submission_count} 次電影資訊。\n為了維持系統品質，每位用戶24小時內最多只能提交 {self.MAX_SUBMISSIONS_PER_DAY} 次。\n\n⏰ 請在 {int(hours_until_next)} 小時後再試，或稍後再提交。"
                }
            
            return {
                "allowed": True,
                "message": "",
                "remaining": self.MAX_SUBMISSIONS_PER_DAY - submission_count
            }
            
        except Exception as e:
            logger.error(f"檢查提交頻率失敗: {e}")
            # 出於安全考慮，如果檢查失敗，允許提交（但會記錄錯誤）
            return {"allowed": True, "message": "", "remaining": self.MAX_SUBMISSIONS_PER_DAY}
    
    def _record_submission(self, user_id: str) -> None:
        """記錄使用者的提交時間"""
        try:
            # 載入日誌
            if os.path.exists(self.user_submission_log_file):
                with open(self.user_submission_log_file, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
            else:
                log_data = {}
            
            # 更新使用者的提交記錄
            if user_id not in log_data:
                log_data[user_id] = []
            
            # 添加本次提交時間
            log_data[user_id].append(datetime.now().isoformat())
            
            # 只保留最近30天的記錄（節省空間）
            cutoff_date = datetime.now() - timedelta(days=30)
            log_data[user_id] = [
                sub_time for sub_time in log_data[user_id]
                if datetime.fromisoformat(sub_time) >= cutoff_date
            ]
            
            # 保存
            with open(self.user_submission_log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"記錄使用者 {user_id} 的提交時間")
            
        except Exception as e:
            logger.error(f"記錄提交時間失敗: {e}")
    
    def get_user_submission_status(self, user_id: str) -> Dict[str, any]:
        """獲取使用者的提交狀態（剩餘次數等）"""
        try:
            frequency_check = self._check_submission_frequency(user_id)
            return {
                "remaining_submissions": frequency_check.get("remaining", self.MAX_SUBMISSIONS_PER_DAY),
                "max_per_day": self.MAX_SUBMISSIONS_PER_DAY,
                "window_hours": self.SUBMISSION_WINDOW_HOURS
            }
        except Exception as e:
            logger.error(f"獲取提交狀態失敗: {e}")
            return {
                "remaining_submissions": self.MAX_SUBMISSIONS_PER_DAY,
                "max_per_day": self.MAX_SUBMISSIONS_PER_DAY,
                "window_hours": self.SUBMISSION_WINDOW_HOURS
            }
    
    def get_user_recent_rejected_submissions(self, user_id: str, limit: int = 5) -> List[Dict]:
        """獲取使用者最近被拒絕的提交（供申訴使用）"""
        try:
            if not os.path.exists(self.appeal_file):
                return []
            
            with open(self.appeal_file, 'r', encoding='utf-8') as f:
                rejected_list = json.load(f)
            
            # 過濾出該使用者的被拒絕提交，按時間倒序
            user_rejected = [
                sub for sub in rejected_list
                if sub.get("user_id") == user_id and sub.get("status") == "rejected"
            ]
            
            # 排序並限制數量
            user_rejected.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return user_rejected[:limit]
            
        except Exception as e:
            logger.error(f"獲取使用者被拒絕提交失敗: {e}")
            return []
    
    def appeal_rejected_submission(self, user_id: str, submission_id: str = None) -> Dict[str, any]:
        """
        申訴被拒絕的提交
        如果提供 submission_id，申訴指定的提交；否則申訴最近的提交
        """
        try:
            # 獲取可申訴的提交
            recent_rejected = self.get_user_recent_rejected_submissions(user_id, limit=10)
            
            if not recent_rejected:
                return {
                    "success": False,
                    "message": "❌ 你目前沒有可申訴的提交記錄。"
                }
            
            # 如果提供了 submission_id，找對應的提交；否則用最近的
            if submission_id:
                target_submission = next(
                    (sub for sub in recent_rejected if sub.get("submission_id") == submission_id),
                    None
                )
                if not target_submission:
                    return {
                        "success": False,
                        "message": "❌ 找不到指定的提交記錄。請使用「申訴」申訴最近的提交。"
                    }
            else:
                target_submission = recent_rejected[0]  # 最近的提交
            
            # 將提交移到申訴暫存區（status 改為 appeal）
            target_submission["status"] = "appeal"
            target_submission["appeal_timestamp"] = datetime.now().isoformat()
            target_submission["appeal_note"] = "使用者申請管理員重新審核"
            
            # 更新申訴列表
            if os.path.exists(self.appeal_file):
                with open(self.appeal_file, 'r', encoding='utf-8') as f:
                    appeal_list = json.load(f)
            else:
                appeal_list = []
            
            # 移除舊的並添加新的（更新狀態）
            appeal_list = [sub for sub in appeal_list if sub.get("submission_id") != target_submission["submission_id"]]
            appeal_list.append(target_submission)
            
            with open(self.appeal_file, 'w', encoding='utf-8') as f:
                json.dump(appeal_list, f, ensure_ascii=False, indent=2)
            
            # 構建回應訊息
            movie_title = target_submission.get("movie_data", {}).get("title", "未知電影")
            validation_reason = target_submission.get("validation_reason", "AI 驗證未通過")
            
            return {
                "success": True,
                "message": f"✅ 申訴已提交！\n\n"
                          f"📋 電影資訊：{movie_title}\n"
                          f"❓ 拒絕原因：{validation_reason}\n\n"
                          f"📌 提交ID：{target_submission['submission_id']}\n\n"
                          f"管理員會重新審核此提交，請耐心等待。審核結果將通知你。",
                "submission_id": target_submission["submission_id"],
                "movie_data": target_submission.get("movie_data", {})
            }
            
        except Exception as e:
            logger.error(f"處理申訴失敗: {e}")
            return {
                "success": False,
                "message": "❌ 處理申訴時發生錯誤，請稍後再試。"
            }
    
    def get_submission_instructions(self) -> str:
        """獲取提交電影資訊的說明"""
        return """📝 如何新增或更新電影資訊：

你可以使用以下格式提交新電影或更新現有電影（更新也走相同審核與頻率限制流程）：

【格式一：簡短格式】
新增電影：Movie Title (年份)
類型：動作|喜劇

【格式二：詳細格式】
新增電影：Movie Title (年份)
類型：動作|喜劇|劇情
描述：電影簡介...

【格式三：更新提案（修改既有電影資訊）】
更新電影：Movie Title (年份)
欄位：runtime=175 分鐘; genres=犯罪|劇情; 備註：修正片長

【範例】
新增電影：The Matrix (1999)
類型：動作|科幻
描述：這是一部關於未來的動作科幻片

更新電影：The Godfather (1972)
欄位：runtime=175 分鐘; genres=犯罪|劇情

⚠️ **重要要求**：
• **電影名稱必須使用英文！**（例如：「Toy Story」而不是「玩具總動員」）
• 類型可以使用中文或英文（系統會自動翻譯成英文）
• 年份請提供正確的發行年份
• 所有資訊在加入資料庫前都會轉換成英文格式

💡 其他注意事項：
• 請提供真實存在的電影資訊
• 類型請選擇常見的電影類型（動作、喜劇、劇情等）
• ⚠️ 頻率限制：每位用戶24小時內最多只能提交3次

提交後，系統會自動驗證資訊的真實性和安全性。

📌 重要提醒：
• 提交的電影資訊（包含更新）需要經過審核才會加入資料庫
• 在審核完成前，推薦系統仍以現有資料為主
• 不會因為有人提交新電影而影響推薦結果

🔍 AI 判斷標準說明：
系統使用 AI 驗證時會檢查：
1. **安全性**：是否包含惡意內容、垃圾資訊、廣告、連結等
2. **真實性**：是否像真實存在的電影（標題、類型、年份搭配是否合理）
3. **合理性**：內容是否符合電影資訊的格式和常見結構
4. **惡意行為**：是否有誤導、垃圾訊息、重複提交等跡象

⚙️ 驗證標準（保守策略）：
• 只有 AI 非常確定（confidence ≥ 80%）資訊是安全且真實時才允許提交
• 其他情況（不確定、可疑、不安全）會拒絕，保護系統安全

📝 申訴機制：
如果提交被拒絕，你可以回覆「申訴」或「我要申訴」，管理員會重新審核你的提交。"""

