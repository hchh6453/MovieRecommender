# 🎬 電影推薦 LINE Bot

一個結合 Gemini AI 的智能電影推薦 LINE Bot，能夠理解自然語言並提供個人化電影推薦。

## ✨ 功能特色

- 🤖 **智能對話**: 使用 Google Gemini AI 理解使用者需求
- 🎯 **個人化推薦**: 基於內容的電影推薦引擎
- 📱 **LINE Bot 整合**: 友善的聊天介面
- 🎨 **美觀卡片**: 使用 Flex Message 展示電影資訊
- 🔍 **電影搜尋**: 快速找到特定電影
- ⚡ **快速回應**: 高效的推薦算法

## 🏗️ 系統架構

```
使用者 (LINE App) → LINE Messaging API → FastAPI → 推薦引擎 + Gemini AI
```

## 🚀 快速開始

### 1. 環境設定

```bash
# 克隆專案
git clone https://github.com/hchh6453/MovieRecommender.git
cd MovieRecommender

# 建立虛擬環境
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 安裝依賴
pip install -r requirements.txt
```

### 2. 設定環境變數

```bash
# 複製環境變數範例
cp .env.example .env

# 編輯 .env 檔案，填入你的 API 金鑰
nano .env
```

### 3. 啟動服務

```bash
# 啟動開發服務器
python run.py

# 或使用 uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📁 專案結構

```
MovieRecommenderSystem/
├── app/                     # 主要應用程式
│   ├── main.py             # FastAPI 主程式
│   ├── config.py           # 設定檔
│   ├── services/           # 業務邏輯服務
│   ├── handlers/           # 訊息處理器
│   ├── models/             # 資料模型
│   └── utils/              # 工具函數
├── data/                   # 資料檔案
├── notebooks/              # Jupyter notebooks
├── requirements.txt        # Python 依賴
├── .env                   # 環境變數 (需自行建立)
└── README.md              # 專案說明
```

## 🔧 主要組件

### LINE Bot Service
- 處理 LINE Messaging API 整合
- 管理 Webhook 事件
- 生成 Flex Message 卡片

### Gemini AI Service
- 自然語言理解
- 使用者偏好提取
- 智能對話生成

### Recommendation Engine
- 基於內容的推薦算法
- 電影相似度計算
- 個人化推薦邏輯

## 🎯 使用範例

```
使用者: "我想看一些輕鬆的喜劇電影"
Bot: [顯示喜劇電影推薦卡片]

使用者: "搜尋 玩具總動員"
Bot: [顯示玩具總動員相關資訊]

使用者: "再推薦一些"
Bot: [基於對話歷史提供更多推薦]
```

## 📚 功能說明

### 已實現的功能

- ✅ **個人化推薦**: 系統會記住用戶喜好並提供個人化推薦
- ✅ **年份篩選**: 支援按年份推薦電影
- ✅ **類型篩選**: 支援指定或排除電影類型
- ✅ **質量排序**: 結合評分和評分人數進行排序
- ✅ **偏好管理**: 查看、重置個人偏好設定
- ✅ **操作指示**: 隨時查詢功能和使用方法
- ✅ **中文類型**: 電影類型自動翻譯為繁體中文
- ✅ **詳細資訊**: 點擊可查看電影詳細資訊和推薦原因

### 使用範例

```
用戶: "我想看喜劇電影"
→ 推薦喜劇類型電影

用戶: "2023年的電影"
→ 推薦2023年評分最高的電影

用戶: "我不喜歡恐怖片"
→ 自動排除恐怖電影

用戶: "查看偏好"
→ 顯示目前的偏好設定

用戶: "怎麼用"
→ 顯示完整操作說明
```

## 📊 資料集

- `data/movies.csv`: 電影基本資訊
- `data/tags.csv`: 使用者標籤資料

## 🚀 部署

### 使用 Docker

```bash
# 建立 Docker 映像
docker build -t movie-recommender-bot .

# 執行容器
docker run -p 8000:8000 --env-file .env movie-recommender-bot
```

### 雲端部署

支援部署到：
- Google Cloud Run
- Heroku
- Railway
- AWS Lambda


## 📈 監控

- 健康檢查端點: `/health`
- API 文檔: `/docs`
- 日誌輸出: 控制台 + 檔案


## 📄 授權

MIT License

---

**Happy Coding! 🎬✨**



