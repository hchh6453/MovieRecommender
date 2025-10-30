"""
AI-powered recommendation service.

Combines TF-IDF retrieval with Gemini AI for preference extraction and reranking.
"""
from __future__ import annotations

import os
import logging
from typing import List, Dict, Optional, Union

import pandas as pd
import numpy as np
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .gemini_service import GeminiService

logger = logging.getLogger(__name__)


class RecommendationService:
    def __init__(self, data_dir: str = "data") -> None:
        self.data_dir = data_dir
        self.movies: Optional[pd.DataFrame] = None
        self.ratings: Optional[pd.DataFrame] = None
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.doc_matrix = None
        self.gemini_service = GeminiService()
        self._load_and_build()

    def _load_and_build(self) -> None:
        movies_path = os.path.join(self.data_dir, "movies.csv")
        tags_path = os.path.join(self.data_dir, "tags.csv")
        ratings_path = os.path.join(self.data_dir, "ratings.csv")

        movies = pd.read_csv(movies_path)
        
        # 提取年份
        movies["year"] = movies["title"].str.extract(r'\((\d{4})\)')
        movies["year"] = movies["year"].astype(float).astype("Int64")
        
        # Aggregate tags per movie
        if os.path.exists(tags_path):
            tags = pd.read_csv(tags_path)
            tags_grouped = (
                tags.groupby("movieId")["tag"].apply(lambda x: " ".join(map(str, x))).reset_index()
            )
            movies = movies.merge(tags_grouped, on="movieId", how="left")
        else:
            movies["tag"] = ""

        movies["tag"] = movies["tag"].fillna("")
        # Normalize genres separator to spaces
        movies["genres"] = movies["genres"].fillna("").astype(str).str.replace("|", " ")

        # Build a simple free-text field
        movies["doc"] = (
            movies["title"].fillna("").astype(str)
            + " "
            + movies["genres"].fillna("").astype(str)
            + " "
            + movies["tag"].fillna("").astype(str)
        )

        # Fit TF-IDF on docs
        vectorizer = TfidfVectorizer(stop_words="english")
        doc_matrix = vectorizer.fit_transform(movies["doc"]).astype("float32")

        # Load ratings for scoring
        if os.path.exists(ratings_path):
            self.ratings = pd.read_csv(ratings_path)
            # Calculate average rating per movie
            movie_ratings = self.ratings.groupby("movieId").agg({
                "rating": ["mean", "count"]
            }).reset_index()
            movie_ratings.columns = ["movieId", "avg_rating", "rating_count"]
            # Merge with movies
            movies = movies.merge(movie_ratings, on="movieId", how="left")
            movies["avg_rating"] = movies["avg_rating"].fillna(0)
            movies["rating_count"] = movies["rating_count"].fillna(0)
        else:
            movies["avg_rating"] = 0
            movies["rating_count"] = 0

        self.movies = movies
        self.vectorizer = vectorizer
        self.doc_matrix = doc_matrix

    def recommend_by_text(self, user_text: str, top_k: int = 5) -> List[Dict[str, str]]:
        """使用 AI 驅動的推薦系統"""
        if not user_text or self.vectorizer is None or self.doc_matrix is None or self.movies is None:
            return []

        # 1. 使用 Gemini 抽取使用者偏好
        preferences = self.gemini_service.extract_preferences(user_text)
        
        # 2. 檢查是否有年份需求
        requested_year = preferences.get("year")
        
        if requested_year:
            # 如果指定年份，直接按評分排序篩選
            candidates = self._get_movies_by_year(requested_year, top_k * 2)
        else:
            # 3. 根據偏好調整查詢
            enhanced_query = self._enhance_query_with_preferences(user_text, preferences)
            
            # 4. TF-IDF 檢索候選電影
            query_vec = self.vectorizer.transform([enhanced_query])
            sims = cosine_similarity(query_vec, self.doc_matrix)[0]
            
            # 5. 取得更多候選進行重排序
            candidate_count = min(20, len(self.movies))
            top_idx = sims.argsort()[::-1][:candidate_count]
            
            candidates = []
            for idx in top_idx:
                row = self.movies.iloc[idx]
                candidates.append({
                    "movieId": str(row["movieId"]),
                    "title": str(row["title"]),
                    "genres": str(row["genres"]),
                    "avg_rating": float(row.get("avg_rating", 0)) if "avg_rating" in row else 0,
                    "rating_count": int(row.get("rating_count", 0)) if "rating_count" in row else 0
                })
            
            # 6. 過濾排除的類型
            candidates = self._filter_excluded_genres(candidates, preferences)
            
            # 7. 對候選電影進行質量排序
            candidates = self._rank_candidates_by_quality(candidates)
            
            # 8. 使用 Gemini 重新排序（處理前面 10 部）
            candidates = self.gemini_service.rerank_recommendations(
                candidates[:10], preferences, user_text
            ) + candidates[10:]
        
        # 9. 回傳前 top_k 個結果
        return candidates[:top_k]
    
    def search_exact_movie(self, search_term: str) -> Optional[Dict]:
        """精確搜尋電影（用於搜尋功能）"""
        if not search_term or self.movies is None:
            return None
        
        search_term = search_term.strip().lower()
        
        # 嘗試各種匹配方式
        # 1. 完全匹配（忽略大小寫）
        exact_matches = self.movies[
            self.movies["title"].str.lower() == search_term
        ]
        
        if not exact_matches.empty:
            movie = exact_matches.iloc[0]
            return {
                "movieId": int(movie["movieId"]),
                "title": str(movie["title"]),
                "genres": str(movie.get("genres", "")),
                "year": int(movie.get("year")) if pd.notna(movie.get("year")) else None,
                "avg_rating": float(movie.get("avg_rating", 0)) if "avg_rating" in movie else 0
            }
        
        # 2. 移除年份後匹配（例如搜尋 "Toy Story" 應該能找到 "Toy Story (1995)"）
        search_term_no_year = re.sub(r'\s*\([0-9]{4}\)', '', search_term).strip()
        
        # 移除標題中的年份來比較
        movies_no_year = self.movies.copy()
        movies_no_year["title_no_year"] = movies_no_year["title"].str.replace(
            r'\s*\([0-9]{4}\)', '', regex=True
        ).str.lower().str.strip()
        
        matches = movies_no_year[
            movies_no_year["title_no_year"] == search_term_no_year
        ]
        
        if not matches.empty:
            movie = matches.iloc[0]
            return {
                "movieId": int(movie["movieId"]),
                "title": str(movie["title"]),
                "genres": str(movie.get("genres", "")),
                "year": int(movie.get("year")) if pd.notna(movie.get("year")) else None,
                "avg_rating": float(movie.get("avg_rating", 0)) if "avg_rating" in movie else 0
            }
        
        # 3. 部分匹配（標題包含搜尋詞）
        partial_matches = movies_no_year[
            movies_no_year["title_no_year"].str.contains(search_term_no_year, case=False, na=False)
        ]
        
        if not partial_matches.empty:
            # 優先選擇最相似的（最短標題通常最接近）
            movie = partial_matches.loc[partial_matches["title_no_year"].str.len().idxmin()]
            return {
                "movieId": int(movie["movieId"]),
                "title": str(movie["title"]),
                "genres": str(movie.get("genres", "")),
                "year": int(movie.get("year")) if pd.notna(movie.get("year")) else None,
                "avg_rating": float(movie.get("avg_rating", 0)) if "avg_rating" in movie else 0
            }
        
        return None
    
    def search_similar_movies(self, search_term: str, top_k: int = 5) -> List[Dict]:
        """搜尋類似電影（用於找不到時的推薦）"""
        if not search_term or self.vectorizer is None or self.doc_matrix is None or self.movies is None:
            return []
        
        # 使用 TF-IDF 搜尋類似電影
        query_vec = self.vectorizer.transform([search_term])
        sims = cosine_similarity(query_vec, self.doc_matrix)[0]
        
        # 取得最相似的幾部
        top_idx = sims.argsort()[::-1][:top_k * 2]  # 取得更多候選以過濾
        
        candidates = []
        for idx in top_idx:
            row = self.movies.iloc[idx]
            # 提取年份
            year = None
            if pd.notna(row.get("year")):
                year = int(row["year"])
            
            candidates.append({
                "movieId": str(row["movieId"]),
                "title": str(row["title"]),
                "genres": str(row["genres"]),
                "year": year,
                "avg_rating": float(row.get("avg_rating", 0)) if "avg_rating" in row else 0,
                "rating_count": int(row.get("rating_count", 0)) if "rating_count" in row else 0,
                "similarity": float(sims[idx])
            })
        
        # 按相似度和評分排序
        candidates.sort(key=lambda x: (x["similarity"], x["avg_rating"]), reverse=True)
        
        return candidates[:top_k]
    
    def _filter_excluded_genres(self, candidates: List[Dict], preferences: Dict) -> List[Dict]:
        """過濾掉包含排除類型的電影"""
        exclude_genres = preferences.get("exclude_genres", [])
        
        if not exclude_genres:
            return candidates
        
        # 將中文類型轉換為英文（用於比對）
        genre_mapping = {
            "兒童": "Children",
            "恐怖": "Horror",
            "驚悚": "Thriller",
            "血腥": "Crime",
            "懸疑": "Mystery",
            "動作": "Action",
            "冒險": "Adventure",
            "動畫": "Animation",
            "喜劇": "Comedy",
            "犯罪": "Crime",
            "劇情": "Drama",
            "奇幻": "Fantasy",
            "音樂": "Musical",
            "浪漫": "Romance",
            "科幻": "Sci-Fi",
            "戰爭": "War",
            "西部": "Western"
        }
        
        exclude_genres_en = [genre_mapping.get(genre, genre) for genre in exclude_genres]
        
        filtered_candidates = []
        for candidate in candidates:
            movie_genres = str(candidate.get("genres", "")).lower()
            
            # 檢查是否包含任何排除的類型
            should_exclude = False
            for exclude_genre in exclude_genres_en:
                if exclude_genre.lower() in movie_genres or movie_genres.replace(" ", "").replace("|", "") in exclude_genre.lower():
                    should_exclude = True
                    break
            
            if not should_exclude:
                filtered_candidates.append(candidate)
        
        excluded_count = len(candidates) - len(filtered_candidates)
        if excluded_count > 0:
            logger.info(f"排除了 {excluded_count} 部包含 {exclude_genres} 類型的電影")
        
        return filtered_candidates
    
    def _rank_candidates_by_quality(self, candidates: List[Dict]) -> List[Dict]:
        """根據質量標準排序候選電影"""
        # 計算綜合分數
        for candidate in candidates:
            avg_rating = candidate.get("avg_rating", 0)
            rating_count = candidate.get("rating_count", 0)
            
            # 評分質量分數 (0-1)
            rating_score = (avg_rating / 5.0) if avg_rating > 0 else 0
            
            # 評分數量分數 (0-1) - 使用對數縮放
            if rating_count > 0:
                count_score = min(1.0, np.log10(rating_count + 1) / np.log10(1000))
            else:
                count_score = 0
            
            # 綜合分數：評分權重 60%，評分數量權重 40%
            quality_score = rating_score * 0.6 + count_score * 0.4
            
            candidate["quality_score"] = quality_score
            candidate["rating_score"] = rating_score
            candidate["count_score"] = count_score
        
        # 按綜合分數排序
        candidates.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
        
        logger.info(f"質量排序完成，最高分: {candidates[0].get('quality_score', 0):.3f}")
        return candidates
    
    def _get_movies_by_year(self, year: int, top_k: int = 10) -> List[Dict[str, str]]:
        """根據年份獲取評分最高的電影"""
        if self.movies is None:
            return []
        
        # 篩選指定年份的電影
        year_movies = self.movies[self.movies["year"] == year].copy()
        
        if year_movies.empty:
            logger.warning(f"找不到 {year} 年的電影")
            return []
        
        # 按評分排序（需要至少 10 個評分）
        year_movies = year_movies[year_movies["rating_count"] >= 10]
        
        # 計算綜合分數
        year_movies["rating_score"] = year_movies["avg_rating"] / 5.0
        year_movies["count_score"] = np.log10(year_movies["rating_count"] + 1) / np.log10(1000)
        year_movies["count_score"] = year_movies["count_score"].clip(0, 1)
        year_movies["quality_score"] = year_movies["rating_score"] * 0.6 + year_movies["count_score"] * 0.4
        
        # 排序：按綜合分數
        year_movies = year_movies.sort_values("quality_score", ascending=False)
        
        # 轉換為字典列表
        candidates = []
        for _, row in year_movies.head(top_k).iterrows():
            candidates.append({
                "movieId": str(row["movieId"]),
                "title": str(row["title"]),
                "genres": str(row["genres"]),
                "avg_rating": float(row["avg_rating"]),
                "rating_count": int(row["rating_count"]),
            })
        
        logger.info(f"找到 {year} 年排名前 {len(candidates)} 的電影（綜合分數: {year_movies.iloc[0]['quality_score']:.3f}）")
        return candidates
    
    def _enhance_query_with_preferences(self, user_text: str, preferences: Dict) -> str:
        """根據偏好增強查詢文字"""
        enhanced_parts = [user_text]
        
        # 如果使用者明確指定了類型，加強該類型的權重（重複多次以提高 TF-IDF 權重）
        if preferences.get("genres"):
            genres_text = " ".join(preferences["genres"])
            # 重複類型詞以增強 TF-IDF 權重（明確指定的類型需要優先）
            enhanced_parts.append(genres_text)
            enhanced_parts.append(genres_text)  # 重複一次加強權重
        
        # 加入關鍵字
        if preferences.get("keywords"):
            keywords_text = " ".join(preferences["keywords"])
            enhanced_parts.append(keywords_text)
        
        # 加入情緒描述
        if preferences.get("mood"):
            enhanced_parts.append(preferences["mood"])

        # 加入國家/地區（提升對應關鍵詞權重）；排除國家目前僅作為重排序參考
        if preferences.get("countries"):
            countries_text = " ".join(preferences["countries"])  # 英文國名/地區名
            enhanced_parts.append(countries_text)
            enhanced_parts.append(countries_text)  # 再次加權
        
        return " ".join(enhanced_parts)
    
    def get_recommendation_explanation(self, user_text: str, recommendations: List[Dict]) -> str:
        """獲取推薦解釋"""
        return self.gemini_service.generate_recommendation_explanation(user_text, recommendations)



