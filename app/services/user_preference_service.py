"""
用戶偏好服務
用於儲存和管理用戶的個人偏好歷史
"""
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)


class UserPreferenceService:
    def __init__(self, storage_dir: str = "data/user_preferences"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
    
    def _get_user_file_path(self, user_id: str) -> str:
        """獲取用戶偏好檔案路徑"""
        return os.path.join(self.storage_dir, f"{user_id}.json")
    
    def load_user_preferences(self, user_id: str) -> Dict:
        """載入用戶偏好"""
        file_path = self._get_user_file_path(user_id)
        
        if not os.path.exists(file_path):
            return self._default_preferences()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                preferences = json.load(f)
            logger.info(f"成功載入用戶 {user_id} 的偏好")
            return preferences
        except Exception as e:
            logger.error(f"載入用戶偏好失敗: {e}")
            return self._default_preferences()
    
    def save_user_preferences(self, user_id: str, preferences: Dict) -> None:
        """儲存用戶偏好"""
        file_path = self._get_user_file_path(user_id)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(preferences, f, ensure_ascii=False, indent=2)
            logger.info(f"成功儲存用戶 {user_id} 的偏好")
        except Exception as e:
            logger.error(f"儲存用戶偏好失敗: {e}")
    
    def update_preferences_from_query(self, user_id: str, query_preferences: Dict) -> Dict:
        """從查詢中更新用戶偏好"""
        # 載入現有偏好
        preferences = self.load_user_preferences(user_id)
        
        # 更新偏好
        if query_preferences.get("genres"):
            preferences["favorite_genres"] = self._merge_lists(
                preferences["favorite_genres"],
                query_preferences["genres"]
            )
        
        if query_preferences.get("exclude_genres"):
            preferences["excluded_genres"] = self._merge_lists(
                preferences["excluded_genres"],
                query_preferences["exclude_genres"]
            )
        
        if query_preferences.get("mood"):
            preferences["favorite_moods"].append(query_preferences["mood"])
            preferences["favorite_moods"] = list(set(preferences["favorite_moods"]))
        
        # 記錄查詢歷史
        preferences["query_history"].append({
            "timestamp": datetime.now().isoformat(),
            "query_preferences": query_preferences
        })
        
        # 只保留最近 50 條記錄
        preferences["query_history"] = preferences["query_history"][-50:]
        
        # 計算偏好強度
        preferences = self._calculate_preference_strength(preferences)
        preferences["updated_at"] = datetime.now().isoformat()
        
        # 儲存更新後的偏好
        self.save_user_preferences(user_id, preferences)
        
        return preferences
    
    def record_movie_interaction(self, user_id: str, movie_id: str, action: str) -> None:
        """記錄用戶與電影的互動"""
        preferences = self.load_user_preferences(user_id)
        
        # 記錄互動
        preferences["interactions"].append({
            "timestamp": datetime.now().isoformat(),
            "movie_id": movie_id,
            "action": action
        })
        
        # 只保留最近 100 條記錄
        preferences["interactions"] = preferences["interactions"][-100:]
        
        # 儲存
        self.save_user_preferences(user_id, preferences)
    
    def get_personalized_preferences(self, user_id: str) -> Dict:
        """獲取個人化偏好"""
        preferences = self.load_user_preferences(user_id)
        
        # 如果用戶沒有足夠的歷史資料，返回空偏好
        if len(preferences["query_history"]) < 3:
            return {}
        
        # 提取統計偏好
        personalized = {
            "favorite_genres": preferences.get("favorite_genres", []),
            "excluded_genres": preferences.get("excluded_genres", []),
            "preferred_mood": self._get_most_common(preferences.get("favorite_moods", []))
        }
        
        return personalized
    
    def get_preference_summary(self, user_id: str) -> str:
        """獲取用戶偏好摘要（用於顯示）"""
        preferences = self.load_user_preferences(user_id)
        
        if len(preferences["query_history"]) == 0:
            return "目前還沒有偏好記錄。"
        
        summary_parts = []
        
        # 喜愛的類型
        if preferences.get("favorite_genres"):
            summary_parts.append(f"❤️ 喜愛的類型：{', '.join(preferences['favorite_genres'])}")
        
        # 排除的類型
        if preferences.get("excluded_genres"):
            summary_parts.append(f"🚫 排除的類型：{', '.join(preferences['excluded_genres'])}")
        
        # 最常詢問的情緒
        if preferences.get("favorite_moods"):
            most_common_mood = self._get_most_common(preferences["favorite_moods"])
            if most_common_mood:
                summary_parts.append(f"🎭 最常選擇的情緒：{most_common_mood}")
        
        if not summary_parts:
            return "目前還沒有明確的偏好設定。"
        
        return "\n".join(summary_parts)
    
    def reset_preferences(self, user_id: str) -> None:
        """重置用戶偏好"""
        preferences = self._default_preferences()
        preferences["user_id"] = user_id
        self.save_user_preferences(user_id, preferences)
        logger.info(f"用戶 {user_id} 的偏好已重置")
    
    def remove_genre_from_favorites(self, user_id: str, genre: str) -> bool:
        """從喜好列表中移除指定類型"""
        preferences = self.load_user_preferences(user_id)
        
        if genre in preferences["favorite_genres"]:
            preferences["favorite_genres"].remove(genre)
            preferences["updated_at"] = datetime.now().isoformat()
            self.save_user_preferences(user_id, preferences)
            return True
        return False
    
    def remove_genre_from_excluded(self, user_id: str, genre: str) -> bool:
        """從排除列表中移除指定類型"""
        preferences = self.load_user_preferences(user_id)
        
        if genre in preferences["excluded_genres"]:
            preferences["excluded_genres"].remove(genre)
            preferences["updated_at"] = datetime.now().isoformat()
            self.save_user_preferences(user_id, preferences)
            return True
        return False
    
    def _merge_lists(self, list1: List, list2: List) -> List:
        """合併兩個列表並去重"""
        merged = list1 + list2
        return list(dict.fromkeys(merged))
    
    def _calculate_preference_strength(self, preferences: Dict) -> Dict:
        """計算偏好強度"""
        genre_count = {}
        for query in preferences["query_history"]:
            for genre in query.get("query_preferences", {}).get("genres", []):
                genre_count[genre] = genre_count.get(genre, 0) + 1
        
        preferences["genre_preference_strength"] = dict(
            sorted(genre_count.items(), key=lambda x: x[1], reverse=True)
        )
        
        return preferences
    
    def _get_most_common(self, items: List) -> Optional[str]:
        """獲取最常見的項目"""
        if not items:
            return None
        return max(set(items), key=items.count)
    
    def _default_preferences(self) -> Dict:
        """返回默認偏好"""
        return {
            "user_id": "",
            "favorite_genres": [],
            "excluded_genres": [],
            "favorite_moods": [],
            "query_history": [],
            "interactions": [],
            "genre_preference_strength": {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
