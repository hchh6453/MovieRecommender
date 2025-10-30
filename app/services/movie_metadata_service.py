"""
電影額外中繼資料服務（片長、演員等）
 - 以 links.csv 的 tmdbId/imdbId 查詢外部 API（TMDb/OMDb）
 - 結果快取至 data/processed/runtime.json，避免重複請求
"""
import json
import os
import logging
from typing import Dict, Optional, Tuple, List

import requests

from ..config import settings

logger = logging.getLogger(__name__)


class MovieMetadataService:
    def __init__(self,
                 links_csv_path: str = "data/links.csv",
                 cache_dir: str = "data/processed",
                 runtime_cache_filename: str = "runtime.json"):
        self.links_csv_path = links_csv_path
        self.cache_dir = cache_dir
        self.runtime_cache_path = os.path.join(cache_dir, runtime_cache_filename)
        os.makedirs(self.cache_dir, exist_ok=True)
        self._runtime_cache: Dict[str, int] = {}
        self._load_runtime_cache()

    def _load_runtime_cache(self) -> None:
        try:
            if os.path.exists(self.runtime_cache_path):
                with open(self.runtime_cache_path, "r", encoding="utf-8") as f:
                    self._runtime_cache = json.load(f)
            else:
                self._runtime_cache = {}
        except Exception as e:
            logger.error(f"載入片長快取失敗: {e}")
            self._runtime_cache = {}

    def _save_runtime_cache(self) -> None:
        try:
            with open(self.runtime_cache_path, "w", encoding="utf-8") as f:
                json.dump(self._runtime_cache, f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"儲存片長快取失敗: {e}")

    def get_runtime(self, movie_id: int) -> Optional[int]:
        """取得片長（分鐘）。優先讀取快取。"""
        key = str(movie_id)
        return self._runtime_cache.get(key)

    def set_runtime(self, movie_id: int, runtime_min: int) -> None:
        self._runtime_cache[str(movie_id)] = int(runtime_min)
        self._save_runtime_cache()

    def fetch_and_cache_runtime(self, movie_id: int, tmdb_id: Optional[str], imdb_id: Optional[str]) -> Optional[int]:
        """即時查詢並快取片長。優先 TMDb，失敗則 OMDb。"""
        # 先檢查快取
        cached = self.get_runtime(movie_id)
        if cached is not None:
            return cached

        runtime = None

        # TMDb 查詢
        if not runtime and tmdb_id and settings.TMDB_API_KEY:
            try:
                url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
                params = {"api_key": settings.TMDB_API_KEY}
                resp = requests.get(url, params=params, timeout=10)
                if resp.ok:
                    data = resp.json()
                    runtime = data.get("runtime")  # minutes
            except Exception as e:
                logger.warning(f"TMDb 片長查詢失敗 movieId={movie_id}, tmdbId={tmdb_id}: {e}")

        # OMDb 查詢
        if not runtime and imdb_id and settings.OMDB_API_KEY:
            try:
                # imdbId 需要補 tt 前綴且有時要補零，links.csv 的 imdbId 通常為不帶 tt 的數字（含前導零）或去前導零數字
                imdb_tt = f"tt{int(imdb_id):07d}"
                url = "http://www.omdbapi.com/"
                params = {"i": imdb_tt, "apikey": settings.OMDB_API_KEY}
                resp = requests.get(url, params=params, timeout=10)
                if resp.ok:
                    data = resp.json()
                    runtime_str = data.get("Runtime")  # e.g., "142 min"
                    if runtime_str and runtime_str.endswith(" min"):
                        runtime = int(runtime_str.replace(" min", "").strip())
            except Exception as e:
                logger.warning(f"OMDb 片長查詢失敗 movieId={movie_id}, imdbId={imdb_id}: {e}")

        if runtime is not None:
            try:
                self.set_runtime(movie_id, int(runtime))
            except Exception:
                pass

        return runtime

    def bulk_sync_runtimes(self, limit: int = 1000) -> int:
        """批次同步片長，從 links.csv 讀取 tmdbId/imdbId。返回成功同步數量。"""
        if not os.path.exists(self.links_csv_path):
            logger.error(f"找不到 {self.links_csv_path}")
            return 0

        synced = 0
        try:
            with open(self.links_csv_path, "r", encoding="utf-8") as f:
                next(f)  # skip header
                for i, line in enumerate(f):
                    if limit and synced >= limit:
                        break
                    parts = line.strip().split(",")
                    if len(parts) < 3:
                        continue
                    movie_id_str, imdb_id, tmdb_id = parts[0], parts[1], parts[2]
                    try:
                        movie_id = int(movie_id_str)
                    except Exception:
                        continue
                    if self.get_runtime(movie_id) is not None:
                        continue
                    rt = self.fetch_and_cache_runtime(movie_id, tmdb_id or None, imdb_id or None)
                    if rt is not None:
                        synced += 1
        except Exception as e:
            logger.error(f"批次同步片長失敗: {e}")
        return synced

    # ---------- 進階資料（TMDb：演員、預告、串流平台） ----------

    def lookup_external_ids(self, movie_id: int) -> Tuple[Optional[str], Optional[str]]:
        """從 links.csv 讀取 imdbId 與 tmdbId。"""
        if not os.path.exists(self.links_csv_path):
            return None, None
        try:
            with open(self.links_csv_path, "r", encoding="utf-8") as f:
                next(f)  # skip header
                for line in f:
                    parts = line.strip().split(",")
                    if len(parts) < 3:
                        continue
                    try:
                        mid = int(parts[0])
                    except Exception:
                        continue
                    if mid == movie_id:
                        imdb_id = parts[1] or None
                        tmdb_id = parts[2] or None
                        return imdb_id, tmdb_id
        except Exception as e:
            logger.warning(f"lookup_external_ids 失敗 movieId={movie_id}: {e}")
        return None, None

    def fetch_tmdb_credits(self, tmdb_id: str) -> List[str]:
        """取得主要演員姓名（最多前 5 名）。"""
        if not settings.TMDB_API_KEY:
            return []
        try:
            url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/credits"
            params = {"api_key": settings.TMDB_API_KEY}
            resp = requests.get(url, params=params, timeout=10)
            if not resp.ok:
                return []
            data = resp.json()
            cast = data.get("cast", [])
            names = [c.get("name") for c in cast if c.get("name")]
            return names[:5]
        except Exception as e:
            logger.warning(f"TMDb credits 查詢失敗 tmdbId={tmdb_id}: {e}")
            return []

    def fetch_tmdb_trailer_url(self, tmdb_id: str, language: str = "zh-TW") -> Optional[str]:
        """取得 YouTube 預告片連結（若無則回傳 None）。"""
        if not settings.TMDB_API_KEY:
            return None
        try:
            url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/videos"
            params = {"api_key": settings.TMDB_API_KEY, "language": language}
            resp = requests.get(url, params=params, timeout=10)
            if not resp.ok:
                return None
            data = resp.json()
            results = data.get("results", [])
            # 優先找 type=Trailer 的 YouTube 影片
            for r in results:
                if r.get("site") == "YouTube" and r.get("type") == "Trailer" and r.get("key"):
                    return f"https://www.youtube.com/watch?v={r['key']}"
            # 退而求其次：任何 YouTube 影片
            for r in results:
                if r.get("site") == "YouTube" and r.get("key"):
                    return f"https://www.youtube.com/watch?v={r['key']}"
        except Exception as e:
            logger.warning(f"TMDb videos 查詢失敗 tmdbId={tmdb_id}: {e}")
        return None

    def fetch_tmdb_watch_providers(self, tmdb_id: str, country: str = "TW") -> List[str]:
        """取得在地可看平台（flatrate/rent/buy 名稱彙總）。"""
        if not settings.TMDB_API_KEY:
            return []
        try:
            url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/watch/providers"
            params = {"api_key": settings.TMDB_API_KEY}
            resp = requests.get(url, params=params, timeout=10)
            if not resp.ok:
                return []
            data = resp.json() or {}
            results = data.get("results", {})
            region = results.get(country) or {}
            providers: List[str] = []
            for key in ("flatrate", "rent", "buy"):
                items = region.get(key) or []
                providers.extend([p.get("provider_name") for p in items if p.get("provider_name")])
            # 去重保持順序
            seen = set()
            uniq = []
            for name in providers:
                if name not in seen:
                    uniq.append(name)
                    seen.add(name)
            return uniq
        except Exception as e:
            logger.warning(f"TMDb watch/providers 查詢失敗 tmdbId={tmdb_id}: {e}")
            return []

    def fetch_extras(self, movie_id: int) -> Dict[str, Optional[object]]:
        """綜合取得 extras：cast、trailer_url、watch_providers。"""
        imdb_id, tmdb_id = self.lookup_external_ids(movie_id)
        if not tmdb_id:
            return {"cast": [], "trailer_url": None, "watch_providers": []}
        return {
            "cast": self.fetch_tmdb_credits(tmdb_id),
            "trailer_url": self.fetch_tmdb_trailer_url(tmdb_id),
            "watch_providers": self.fetch_tmdb_watch_providers(tmdb_id)
        }



