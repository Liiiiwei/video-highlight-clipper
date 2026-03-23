---
name: local-highlight-clipper
description: >
  本地影片精華剪輯工具。從直播錄影中自動辨識精華片段，剪輯為 Reels 風格短片（15-90秒），
  並自動生成和燒錄中文字幕。使用 Whisper 語音轉錄 + AI 語義分析。
  使用場景：當使用者想要從直播錄影中擷取精華、製作短影片時。
  關鍵詞：精華剪輯、直播、Reels、字幕、影片剪輯、highlight、clip
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - AskUserQuestion
model: claude-sonnet-4-5-20250514
---

# 本地影片精華剪輯工具

## 工作流程

你將按照以下 5 個階段執行精華剪輯任務：

### 階段 1: 環境檢測

**目標**: 確保所有必需工具和依賴都已安裝

1. 檢測 Whisper
   ```bash
   whisper --help 2>&1 | head -1
   ```

2. 檢測 FFmpeg 和 libass 支援
   ```bash
   # 優先檢查 ffmpeg-full（macOS）
   /opt/homebrew/opt/ffmpeg-full/bin/ffmpeg -version 2>/dev/null || ffmpeg -version

   # 驗證 libass 支援
   ffmpeg -filters 2>&1 | grep subtitles
   ```

3. 檢測 Python 依賴
   ```bash
   python3 -c "import pysrt; print('✅ pysrt available')"
   ```

**如果環境檢測失敗**:
- Whisper 未安裝: 提示 `pip install openai-whisper`
- FFmpeg 無 libass: 提示 `brew install ffmpeg-full`
- pysrt 缺失: 提示 `pip install pysrt`

---

### 階段 2: 語音轉錄

**目標**: 將影片語音轉為 SRT 字幕

1. 詢問使用者影片路徑（或從對話上下文取得）

2. 驗證影片格式（支援: mp4, mkv, mov, flv, ts, webm）

3. 檢查是否已有同名 .srt 字幕檔，有則跳過轉錄

4. 呼叫 transcribe_video.py
   ```bash
   cd ~/.claude/skills/local-highlight-clipper
   python3 scripts/transcribe_video.py <video_path>
   ```

5. 向使用者展示：
   - 轉錄狀態和使用的模型
   - 字幕條數和總時長
   - SRT 檔案路徑

---

### 階段 3: AI 精華分析（核心）

**目標**: 分析字幕內容，找出適合做成 Reels 的精華片段

1. 讀取完整 SRT 字幕內容

2. 如果字幕文本過長（預估超過 80,000 tokens），則分段處理：
   - 每段約 30 分鐘的字幕
   - 相鄰段重疊 2 分鐘
   - 分段分析後合併結果，去除重複片段

3. **你需要執行 AI 精華分析**（核心步驟）：

   閱讀完整字幕，根據以下標準找出精華片段：

   **判斷標準（按優先級）**：
   - ⭐ **金句/名言** — 一句話就有傳播力的觀點，適合獨立傳播
   - 📚 **知識密度高** — 短時間內講清楚一個概念或方法論
   - 🔥 **情緒高點** — 語氣激動、笑聲、驚訝等情緒轉折處
   - 📖 **故事/案例** — 有完整敘事弧的小故事或真實案例
   - 💬 **互動亮點** — 回答觀眾問題時的精彩回應

   **篩選原則**：
   - 每個片段必須「自成一體」— 觀眾不看前後文也能理解
   - 偏好有明確開頭和結尾的段落（不要在話講到一半時切）
   - 長度 15-90 秒，根據內容自適應
   - 從 1-2 小時影片中篩出約 5-15 個候選精華
   - 用星級評分（1-5 星）標示推薦程度

4. 向使用者展示精華列表：
   ```
   🎯 分析完成，找到 X 個精華片段：

   1. [12:30 - 13:45] ⭐⭐⭐⭐⭐ 金句
      「不要用努力來彌補方向錯誤」
      理由: 觀點犀利且濃縮，適合獨立傳播
      建議: 45 秒

   2. [28:15 - 29:30] ⭐⭐⭐⭐ 知識點
      三步驟建立個人品牌
      理由: 結構清晰，有具體方法論
      建議: 75 秒

   ... (所有精華)
   ```

---

### 階段 4: 使用者選擇 + 剪輯處理

**目標**: 讓使用者選擇要剪的片段，然後自動處理

1. 使用 AskUserQuestion 讓使用者選擇要剪輯的片段（支援多選）

2. 對每個選定片段，依序執行：

#### 4.1 剪輯影片片段
```bash
python3 scripts/clip_video.py <video_path> <start_time> <end_time> <output_path> --reencode
```
- 使用 re-encode 模式確保精確切割
- 輸出: `clip.mp4`

#### 4.2 擷取字幕片段
```bash
python3 scripts/extract_subtitle_segment.py <srt_path> <start_time> <end_time> <output_srt>
```
- 擷取對應時段字幕
- 調整時間戳從 00:00 開始
- 輸出: `subtitle.srt`

#### 4.3 燒錄字幕到影片
```bash
python3 scripts/burn_subtitles.py <clip_path> <subtitle_path> <output_path>
```
- 使用 FFmpeg libass 燒錄
- 字幕樣式：字體 24、底部邊距 30、白色 + 黑色描邊
- 輸出: `clip_with_sub.mp4`

**進度展示**:
```
🎬 處理片段 1/3: 不要用努力彌補方向錯誤

1/3 剪輯影片... ✅
2/3 擷取字幕... ✅
3/3 燒錄字幕... ✅

✨ 片段 1 處理完成
```

---

### 階段 5: 輸出結果

**目標**: 整理輸出檔案並展示

1. 建立輸出目錄
   ```
   ./highlight-clips/<日期時間>/
   ```

2. 檔案結構：
   ```
   <序號>_<標題>/
   ├── clip.mp4              # 原始剪輯（無字幕）
   ├── clip_with_sub.mp4     # 帶字幕版
   └── subtitle.srt          # 字幕檔
   ```

3. 使用 Write 工具產生 `highlights_summary.txt` 索引檔，格式如下：
   ```
   # 精華片段索引
   # 來源影片: <影片檔名>
   # 產生時間: <日期時間>

   01. [12:30-13:45] ⭐⭐⭐⭐⭐ 金句 — 不要用努力來彌補方向錯誤
   02. [28:15-29:30] ⭐⭐⭐⭐  知識點 — 三步驟建立個人品牌
   ```

4. 展示結果：
   ```
   ✨ 處理完成！

   📁 輸出目錄: ./highlight-clips/20260323_143022/

   檔案列表:
     🎬 01_不要用努力彌補方向錯誤/clip_with_sub.mp4 (5.2 MB)
     🎬 02_三步驟建立個人品牌/clip_with_sub.mp4 (8.1 MB)

   快速預覽:
   open ./highlight-clips/20260323_143022/01_不要用努力彌補方向錯誤/clip_with_sub.mp4
   ```

5. 詢問是否繼續剪輯其他片段

---

## 關鍵技術點

### FFmpeg 路徑空格問題
burn_subtitles.py 使用臨時目錄解決 FFmpeg subtitles 濾鏡的路徑空格問題。

### 短片段精確切割
精華片段只有 15-90 秒，使用 re-encode 模式（`--reencode`）確保起始畫面精確，
避免 `-c copy` 模式在 keyframe 切割造成的偏差。

### Whisper 模型自動選擇
根據 GPU 可用性自動選擇模型：有 GPU 用 medium，無 GPU 用 base。

### 字幕後處理
Whisper 產出的中文字幕常有斷句不自然、語氣詞過多的問題，
transcribe_video.py 會自動進行後處理（合併短字幕、移除語氣詞、修正重疊）。

---

## 錯誤處理

### 環境問題
- Whisper 未安裝 → 提示 pip install openai-whisper
- FFmpeg 無 libass → 引導安裝 ffmpeg-full
- Python 依賴缺失 → 提示 pip install

### 轉錄問題
- 不支援的影片格式 → 提示支援的格式清單
- 轉錄失敗 → 顯示錯誤訊息，建議換模型重試
- 已有字幕檔 → 跳過轉錄，直接使用

### 處理問題
- FFmpeg 執行失敗 → 顯示詳細錯誤
- 磁碟空間不足 → 提示清理空間

---

## 開始執行

當使用者觸發這個 Skill 時：
1. 立即開始階段 1（環境檢測）
2. 按照 5 個階段順序執行
3. 每個階段完成後自動進入下一階段
4. 遇到問題時提供清晰的解決方案
5. 最後展示完整的輸出結果

核心價值：**AI 精華篩選** + **自動字幕** + **一鍵產出 Reels 短片**
