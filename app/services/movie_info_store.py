import json
import os
from typing import Optional, Dict, Any


class MovieInfoStoreService:
    """本地電影資訊儲存（優先於外部 API 使用）。

    採用單一 JSON 檔作為簡易 KV 儲存：key = f"{title.lower().strip()}::{year or ''}"，
    亦支援以 movieId 查找的輔助索引。
    """

    def __init__(self, base_dir: Optional[str] = None):
        project_root = base_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.store_dir = os.path.join(project_root, "data", "movie_info")
        self.index_path = os.path.join(self.store_dir, "index.json")
        self._ensure_store()

    def _ensure_store(self) -> None:
        os.makedirs(self.store_dir, exist_ok=True)
        if not os.path.exists(self.index_path):
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump({"by_key": {}, "by_id": {}}, f, ensure_ascii=False)

    def _load(self) -> Dict[str, Any]:
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"by_key": {}, "by_id": {}}

    def _save(self, data: Dict[str, Any]) -> None:
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _make_key(title: Optional[str], year: Optional[int]) -> Optional[str]:
        if not title:
            return None
        title_key = str(title).strip().lower()
        year_str = str(year).strip() if year not in (None, "", "未知") else ""
        return f"{title_key}::{year_str}"

    def get_by_title_year(self, title: str, year: Optional[int]) -> Dict[str, Any]:
        data = self._load()
        key = self._make_key(title, year)
        if not key:
            return {}
        return data.get("by_key", {}).get(key, {})

    def get_by_id(self, movie_id: Optional[int]) -> Dict[str, Any]:
        if not movie_id:
            return {}
        data = self._load()
        key = str(movie_id)
        ref = data.get("by_id", {}).get(key)
        if not ref:
            return {}
        # ref 內容已經是詳細 payload
        return ref

    def upsert(self, payload: Dict[str, Any]) -> None:
        """新增或更新電影資訊。
        支援欄位：movieId, title, year, runtime, cast, trailer_url, watch_providers, synopsis, genres(EN/CN)...
        不會刪除既有欄位，僅覆蓋提供的欄位。
        """
        if not payload:
            return

        title = payload.get("title")
        year = payload.get("year")
        movie_id = payload.get("movieId")

        data = self._load()

        # 以 title+year 作為主鍵
        tkey = self._make_key(title, year)
        if tkey:
            base = data.setdefault("by_key", {}).get(tkey, {})
            base.update({k: v for k, v in payload.items() if v is not None})
            data["by_key"][tkey] = base

        # 以 movieId 作為輔助索引（若存在）
        if movie_id is not None:
            id_key = str(movie_id)
            base_id = data.setdefault("by_id", {}).get(id_key, {})
            base_id.update({k: v for k, v in payload.items() if v is not None})
            data["by_id"][id_key] = base_id

        self._save(data)


