# 新資料升級方案與強化能力

## 📊 新資料規模對比

| 資料集 | 電影數量 | 評分數量 | 標籤數量 | 用戶數量 |
|--------|---------|---------|---------|---------|
| **舊資料** | 9,744 | - | ~10,000 | - |
| **新資料** | **87,585** | **32,000,000+** | **2,000,000+** | **~700,000** |
| **提升** | **9倍** | **全新** | **200倍** | **全新** |

## 🚀 新增的核心資料

### 1. 評分資料 (ratings.csv) - 32M+ 評分
```
userId,movieId,rating,timestamp
```
- **用戶行為數據**: 真實用戶評分
- **時間序列數據**: 可用於分析用戶偏好變化
- **協同過濾基礎**: 實現基於用戶相似度的推薦

### 2. 鏈接資料 (links.csv) - 87K+ 電影
```
movieId,imdbId,tmdbId
```
- **IMDb 鏈接**: 可直接獲取海報和詳細資訊
- **TMDB 鏈接**: 更豐富的電影元數據
- **外部 API 整合**: 與第三方服務對接

### 3. 標籤資料 (tags.csv) - 2M+ 標籤
```
userId,movieId,tag,timestamp
```
- **用戶生成內容**: 真實用戶標籤
- **細粒度特徵**: 更豐富的電影特徵
- **個性化增強**: 捕捉個人化興趣點

## 🎯 可以實現的新功能

### 1. 協同過濾推薦 ✨ (最重要)

#### 用戶協同過濾 (User-Based CF)
- **實現**: 找相似用戶，推薦他們喜歡的電影
- **優勢**: 發現用戶未知興趣
- **應用場景**: "與你相似的人都喜歡這部電影"

#### 物品協同過濾 (Item-Based CF)
- **實現**: 找相似電影，推薦給喜歡該電影的用戶
- **優勢**: 解釋性強，推薦穩定
- **應用場景**: "看了這部電影的人也看了..."

#### 矩陣分解 (Matrix Factorization)
- **實現**: SVD、NMF、ALS 等算法
- **優勢**: 捕捉隱式特徵，降低維度
- **性能**: 處理大規模數據，推薦質量高

### 2. 混合推薦系統 🔄

```
當前 (基於內容) + 協同過濾 = 混合推薦
     ↓                    ↓
TF-IDF + 特徵          用戶評分矩陣
     ↓                    ↓
    Gemini AI        協同過濾推薦
     ↓                    ↓
   最終推薦 ← 加權融合
```

**優勢**:
- 冷啟動問題解決 (新用戶/新電影)
- 推薦多樣性提升
- 推薦質量更高

### 3. 時間感知推薦 ⏰

- **流行度衰減**: 老電影評分權重降低
- **季節性推薦**: 根據時間推薦合適電影
- **趨勢分析**: 發現爆紅電影

### 4. 個性化深度增強 🎭

#### 用戶畫像分析
```python
用戶特徵向量:
{
    "偏好類型": ["Action", "Comedy", "Sci-Fi"],
    "評分習慣": "嚴苛評分者", "寬鬆評分者",
    "活躍度": "重度用戶", "輕度用戶",
    "觀看歷史": 時間序列特徵
}
```

#### 電影特徵增強
```python
電影特徵:
{
    "IMDb 評分": 8.5,
    "TMDB 評分": 8.2,
    "評分人數": 1,200,000,
    "用戶標籤": ["mind-blowing", "twist ending"],
    "流行度": "trending"
}
```

### 5. 智能查詢系統 🔍

- **模糊搜尋**: 即使拼寫錯誤也能找到
- **語義理解**: 理解 "想找讓人哭的電影"
- **多維度篩選**: 類型、評分、年份、導演等

### 6. 推薦解釋性增強 💡

```
推薦理由:
✓ 與你觀看歷史相似的用戶也喜歡
✓ 你給 "Inception" 打了 5 星，這部電影評分相似
✓ 這部電影有你關注的導演 Christopher Nolan
✓ 喜歡 "The Matrix" 的用戶也喜歡這部
```

### 7. 社交化推薦 👥

- **好友推薦**: 基於朋友喜好
- **社區推薦**: 加入相似興趣社群
- **熱門討論**: 推薦正在熱議的電影

## 📈 技術升級架構

### 推薦引擎升級

```
當前架構:
User → Gemini AI → TF-IDF 檢索 → 推薦結果

升級後架構:
User → Gemini AI + 協同過濾 + 混合策略
  ↓
- 基於內容過濾 (當前)
- 用戶協同過濾 (新增)
- 物品協同過濾 (新增)
- 矩陣分解 (新增)
- 深度學習 (未來)
  ↓
  加權融合 → 最終推薦
```

### 資料處理管道

```
原始數據 (CSV)
    ↓
資料清洗與預處理
    ↓
特徵工程
    ↓
相似度矩陣計算
    ↓
推薦模型訓練
    ↓
結果快取 (Redis)
    ↓
API 服務 (FastAPI)
```

## 🛠️ 實作優先順序

### Phase 1: 基礎升級 (1-2週)
1. ✅ 資料替換完成
2. 整合 links.csv 獲取 IMDb/TMDB ID
3. 實現基礎協同過濾
4. 更新推薦服務以使用新資料

### Phase 2: 混合推薦 (2-3週)
1. 實現用戶協同過濾
2. 實現物品協同過濾
3. 混合策略實作
4. A/B 測試框架

### Phase 3: 進階功能 (3-4週)
1. 矩陣分解 (SVD/NMF)
2. 時間感知推薦
3. 推薦解釋性
4. 性能優化

### Phase 4: 深度學習 (未來)
1. 神經協同過濾
2. DeepFM
3. Wide & Deep
4. AutoEncoder

## 💪 預期效果提升

### 推薦質量
- **精確度**: +30-50%
- **召回率**: +40-60%
- **多樣性**: +50%
- **新穎性**: +40%

### 用戶體驗
- **個性化程度**: 從通用 → 深度個性化
- **推薦理由**: 從模糊 → 清晰可解釋
- **冷啟動**: 從困難 → 基本解決

### 系統性能
- **推薦速度**: 使用快取 < 100ms
- **可擴展性**: 支持百萬級用戶
- **實時性**: 支援實時推薦更新

## 📚 需要的技術棧

### 新增依賴
```python
# 協同過濾
surprise>=1.1.1  # 推薦系統工具包
implicit>=0.5.0  # 稀疏矩陣推薦

# 數值計算
scipy>=1.9.0    # 稀疏矩陣運算

# 資料庫 (選用)
redis>=4.5.0    # 快取系統
```

### 需要實現的新服務
- `collaborative_service.py`: 協同過濾服務
- `matrix_factorization_service.py`: 矩陣分解
- `hybrid_recommendation_service.py`: 混合推薦
- `explanation_service.py`: 推薦解釋

## 🎬 使用範例

### 協同過濾推薦
```python
# 用戶協同過濾
similar_users = find_similar_users(user_id, ratings_matrix)
recommendations = get_recommendations_from_similar_users(similar_users)

# 物品協同過濾
similar_movies = find_similar_movies(movie_id, ratings_matrix)
recommendations = recommend_similar_movies(similar_movies)
```

### 混合推薦
```python
# 基於內容
content_recs = content_based_filter(user_preferences)

# 協同過濾
cf_recs = collaborative_filter(user_id)

# 混合
hybrid_recs = weighted_combine(
    content_recs, weight=0.4,
    cf_recs, weight=0.6
)
```

## 📊 資料統計範例

執行以下命令查看資料統計：
```python
# 評分分佈
print(ratings['rating'].value_counts().sort_index())

# 最熱門電影
print(movies_with_ratings.groupby('title')['rating'].count().sort_values(ascending=False).head(10))

# 最受歡迎類型
print(genres_exploded.value_counts())
```

## 🎯 下一步行動

1. **立即開始**: 整合 links.csv 獲取圖片
2. **基礎協同**: 實現簡單的用戶相似度
3. **迭代優化**: 逐步加入更多功能
4. **用戶測試**: 收集反饋並調整

## 📖 參考資源

- [Surprise Documentation](https://surpriselib.com/)
- [Implicit Library](https://implicit.readthedocs.io/)
- [Matrix Factorization for Recommender Systems](https://towardsdatascience.com/matrix-factorization-for-recommender-systems)
- [Hybrid Recommender Systems](https://www.coursera.org/learn/matrix-factorization)
