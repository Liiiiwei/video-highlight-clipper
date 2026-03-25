# 影片精華剪輯工具

當使用者提供影片路徑並要求剪輯精華時，按照以下流程執行。

## 環境需求

```bash
# 確認環境（首次使用時檢查）
ffmpeg -filters 2>&1 | grep subtitles  # 需要有 libass
python3 -c "import whisper"            # 需要 openai-whisper
```

缺少時提示：
- FFmpeg 無 libass → `brew uninstall ffmpeg && brew install homebrew-ffmpeg/ffmpeg/ffmpeg`
- Whisper 未安裝 → `pip3 install openai-whisper`

## 工作流程

### 1. 轉錄字幕

```bash
python3 scripts/transcribe_video.py <video_path> [model] [language]
```

- 如果影片旁已有 .srt 檔會跳過轉錄
- 長影片（>60 分鐘）建議用 `medium` 模型，較短的用 `base`
- 轉錄耗時較長，用背景執行

### 2. AI 分析精華

讀取完整 SRT 字幕，根據以下標準找出精華片段：

**判斷標準**：
- 金句/名言 — 一句話就有傳播力
- 知識密度高 — 短時間講清楚一個概念
- 情緒高點 — 語氣激動、驚訝、感動
- 故事/案例 — 有完整敘事弧
- 互動亮點 — 精彩的問答

**篩選原則**：
- 每段「自成一體」，不看前後文也能理解
- 開頭結尾是完整句子，不要中途截斷
- 目標長度 60-90 秒
- 用星級評分標示推薦程度

### 3. 剪輯影片

```bash
# 基本剪輯
ffmpeg -ss <start> -i <video> -t <duration> \
  -c:v libx264 -preset fast -crf 18 \
  -c:a aac -b:a 192k \
  -y <output>

# 9:16 直式裁切（可選，適合 Reels/Shorts）
# 需要先用 ffprobe 確認原始解析度和 rotation
ffmpeg -ss <start> -i <video> -t <duration> \
  -vf "crop=W:H:X:Y,scale=1080:1920" \
  -c:v libx264 -preset fast -crf 18 \
  -c:a aac -b:a 192k \
  -y <output>
```

注意事項：
- 用 `ffprobe -show_entries stream_side_data=rotation` 檢查影片是否有旋轉
- 有 rotation 時實際顯示尺寸與 stream 尺寸不同，裁切座標要對應顯示尺寸

### 4. 提取字幕段落

```bash
python3 scripts/extract_subtitle_segment.py <srt> <start> <end> <output_srt>
```

### 5. 去空拍（移除靜音段）

```bash
python3 scripts/remove_silence.py <video> <srt> <output_video> <output_srt> [noise_db] [min_duration]
```

**溫和模式**（推薦，保留句間呼吸空間）：
- `noise_db=-30`、`min_duration=0.7`
- 在 Python 中呼叫時設定 `padding=0.18`

**積極模式**（節奏更緊湊）：
- `noise_db=-30`、`min_duration=0.4`
- 預設 `padding=0.08`

### 6. 燒錄字幕（可選）

```bash
python3 scripts/burn_subtitles.py <video> <subtitle> <output> \
  [--font_name "GenSenRounded TW B"] \
  [--font_size 16] \
  [--margin_v 80] \
  [--shadow 1.5] \
  [--fontsdir /path/to/fonts]
```

**重要：先燒字幕再去空拍**。如果先去空拍再燒字幕，字幕時間會對不上。
正確順序：剪輯 → 提取字幕 → 燒錄字幕 → 去空拍

### 7. 濃縮長片段（可選）

當片段超過 90 秒時，分析字幕內容選出關鍵段落，用 FFmpeg trim+concat 濃縮：

```python
# 定義要保留的段落（clip.mp4 時間軸）
segments = [(0, 9.5), (23, 28.5), ...]

# 用 remove_silence.py 中的 build_trim_concat_filter() 產生濾鏡
filter_complex = build_trim_concat_filter(segments)
```

### 8. 替換音軌（可選）

當有獨立錄音檔（m4a/mp3）音質優於影片音軌時：

```bash
# 用能量包絡交叉相關找精確時間對齊
# 然後替換音軌
ffmpeg -i <video> -ss <m4a_offset> -t <duration> -i <audio_file> \
  -map 0:v -map 1:a \
  -c:v copy -c:a aac -b:a 192k \
  -y <output>
```

## 字幕樣式預設

### coolscholar（酷學家）
```
FontName=GenSenRounded TW B,FontSize=16,Bold=1,Shadow=1.5,MarginV=80,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H80000000,Outline=1
```
需要安裝「源泉圓體」字型（GenSenRounded）。

### default（預設）
```
FontSize=24,MarginV=30,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2
```

## 輸出結構

```
<output_dir>/
├── 01_<標題>/
│   ├── clip_final.mp4      # 最終影片
│   └── subtitle_final.srt  # 對應字幕
├── 02_<標題>/
│   ├── clip_final.mp4
│   └── subtitle_final.srt
└── highlights_summary.txt   # 索引檔
```

## 常見問題

- **字幕跟聲音沒對上**：嘗試對字幕加 ±0.5s 偏移，讓使用者選最佳版本
- **FFmpeg 無 subtitles 濾鏡**：改用 `brew install homebrew-ffmpeg/ffmpeg/ffmpeg`
- **路徑有空格**：用 symlink 到 /tmp 或用臨時目錄處理
- **影片有 rotation metadata**：裁切座標要基於顯示尺寸而非 stream 尺寸
