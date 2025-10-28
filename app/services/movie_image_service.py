"""
電影海報圖片服務
用於從網路上搜尋電影海報圖片
"""
import logging
import re
import time
from typing import Optional, Dict
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

logger = logging.getLogger(__name__)

# 常見電影的海報 URL 映射 (可以擴展)
MOVIE_POSTER_MAP = {
    # 一些常見電影的直接鏈接作為示例
    "Toy Story (1995)": "https://m.media-amazon.com/images/M/MV5BMDU2ZWJlMjktMTRhMy00ZTA5LWEzNDgtYmNmZTEwZTViZWJkXkEyXkFqcGdeQXVyNDQ2OTk4MzI@._V1_FMjpg_UX1000_.jpg",
    "The Matrix": "https://m.media-amazon.com/images/M/MV5BNzQzOTk3OTAtNDQ0Zi00ZTVkLWI0MTEtMDllZjNkYzNjNTc4L2ltYWdlL2ltYWdlXkEyXkFqcGdeQXVyNjU0OTQ0OTY@._V1_FMjpg_UX1000_.jpg",
    "Inception": "https://m.media-amazon.com/images/M/MV5BMjAxMzY3NjcxNF5BMl5BanBnXkFtZTcwNTI5OTM0Mw@@._V1_FMjpg_UX1000_.jpg",
}

class MovieImageService:
    def __init__(self):
        """初始化電影圖片服務"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.cache = {}  # 簡單的快取機制
    
    def get_movie_poster_url(self, movie_title: str) -> Optional[str]:
        """
        獲取電影海報 URL
        
        Args:
            movie_title: 電影標題
            
        Returns:
            電影海報圖片 URL，如果找不到則返回 None
        """
        try:
            # 先檢查快取
            if movie_title in self.cache:
                logger.info(f"從快取獲取海報: {movie_title}")
                return self.cache[movie_title]
            
            # 方法1: 檢查已知的電影映射
            if movie_title in MOVIE_POSTER_MAP:
                image_url = MOVIE_POSTER_MAP[movie_title]
                logger.info(f"從映射表獲取海報: {movie_title}")
            else:
                # 方法2: 嘗試從 IMDB 構造 URL
                image_url = self._construct_imdb_url(movie_title)
                
                # 方法3: 如果失敗，使用 TMDB
                if not image_url:
                    image_url = self._search_tmdb(movie_title)
                
                # 如果還是失敗，使用 OMDb API 作為備選
                if not image_url:
                    image_url = self._search_omdb(movie_title)
                
                # 如果都失敗，使用默認圖片
                if not image_url:
                    logger.warning(f"無法找到海報，使用默認圖片: {movie_title}")
                    image_url = self._get_default_poster_url(movie_title)
            
            # 儲存到快取
            self.cache[movie_title] = image_url
            
            return image_url
            
        except Exception as e:
            logger.error(f"獲取電影海報時發生錯誤: {e}")
            return self._get_default_poster_url(movie_title)
    
    def _construct_imdb_url(self, movie_title: str) -> Optional[str]:
        """嘗試從 IMDB 構造圖片 URL"""
        # 這個方法只是演示，實際需要調用 IMDB API 或爬蟲
        # 返回 None 讓系統使用默認圖片
        return None
    
    def _search_tmdb(self, movie_title: str) -> Optional[str]:
        """使用 The Movie Database (TMDB) API 搜尋"""
        try:
            # 清理電影標題
            clean_title = re.sub(r'\s*\(\d{4}\)\s*', '', movie_title).strip()
            
            # TMDB API 搜尋 (使用免費 API，無需 API key 的搜尋)
            search_url = f"https://www.themoviedb.org/search/movie?query={quote(clean_title)}"
            
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 尋找第一個電影結果
            result_link = soup.find('div', class_='card')
            if result_link:
                # 這裡可以進一步提取海報 URL
                # TMDB 需要更複雜的爬蟲邏輯
                pass
            
            return None
            
        except Exception as e:
            logger.error(f"TMDB 搜尋失敗: {e}")
            return None
    
    def _search_omdb(self, movie_title: str) -> Optional[str]:
        """
        使用 OMDb API 搜尋電影海報
        注意: OMDb 需要 API key，這裡僅作為範例
        """
        # OMDb API 需要 API key，這裡先返回 None
        # 如果有 API key，可以使用:
        # api_key = "YOUR_API_KEY"
        # url = f"http://www.omdbapi.com/?t={quote(movie_title)}&apikey={api_key}"
        return None
    
    def _get_default_poster_url(self, movie_title: str) -> str:
        """獲取默認海報 URL"""
        # 使用占位圖服務，將電影標題編碼到 URL 中
        encoded_title = quote(movie_title)
        return f"https://via.placeholder.com/300x450/333333/FFFFFF?text={encoded_title}"
    
    def _is_valid_image_url(self, url: str) -> bool:
        """檢查圖片 URL 是否有效"""
        try:
            response = self.session.head(url, timeout=5, allow_redirects=True)
            content_type = response.headers.get('Content-Type', '')
            return 'image' in content_type
        except Exception:
            return False
    
    def cleanup(self):
        """清理資源"""
        self.session.close()
