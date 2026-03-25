# Video Highlight Clipper

從長時間錄影（直播、訪談、講座）中自動找出精華片段，剪輯為短影片並加上字幕。

搭配 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 使用，AI 負責分析內容、找精華、決定剪輯點，腳本負責影片處理。

## 快速開始

### 1. Clone 專案

```bash
git clone https://github.com/Liiiiwei/video-highlight-clipper.git
cd video-highlight-clipper
```

### 2. 安裝依賴

**FFmpeg**（含 libass 字幕燒錄支援）：

```bash
# macOS
brew install homebrew-ffmpeg/ffmpeg/ffmpeg

# 驗證 libass 支援
ffmpeg -filters 2>&1 | grep subtitles
```

> 如果你已經裝過 ffmpeg，需要先 `brew uninstall ffmpeg` 再裝上面的版本。

**Whisper**（語音轉文字）：

```bash
pip3 install openai-whisper
```

**字型**（可選，用於字幕樣式）：

如果要使用 `coolscholar` 字幕樣式，需要安裝[源泉圓體（GenSenRounded）](https://github.com/ButTaiwan/genseki-font)。

### 3. 使用

在 Claude Code 中，`cd` 到這個專案目錄，然後直接說：

```
幫我把這個影片剪成 3 段精華：/path/to/your-video.mp4
```

就這樣。Claude Code 會讀取 `CLAUDE.md` 裡的工作流指南，自動完成所有步驟。

## 工作流程

```
影片 → Whisper 轉錄 → AI 分析精華 → 剪輯 → 去空拍 → 上字幕
```

1. **轉錄** — Whisper 將影片語音轉為 SRT 字幕
2. **分析** — Claude 閱讀字幕內容，找出金句、故事、知識點等精華段落
3. **剪輯** — FFmpeg 擷取指定時間段的影片
4. **去空拍** — 自動偵測並移除靜音段，讓節奏更緊湊（保留自然呼吸空間）
5. **上字幕** — 將字幕燒錄到影片上，支援自訂字型和樣式

## 你可以跟 Claude Code 說的指令

```
# 基本
幫我剪這個影片的精華：video.mp4

# 指定數量
幫我找出 5 段精華

# 指定風格
字幕用 coolscholar 樣式（圓體 + 陰影）

# 9:16 裁切（適合 Reels / Shorts）
幫我裁切成直式，聚焦左邊的人

# 去空拍
幫我剪去空白段落，但不要剪太乾淨

# 濃縮
這段太長了，濃縮到一分鐘內

# 替換音軌（有獨立錄音檔時）
用這個錄音檔替換影片的聲音：audio.m4a
```

## 單獨使用腳本

不用 Claude Code 也可以直接用各腳本：

```bash
# 轉錄字幕
python3 scripts/transcribe_video.py video.mp4

# 剪輯片段（start ~ end）
python3 scripts/clip_video.py video.mp4 00:15:00 00:16:30 clip.mp4

# 提取對應時段的字幕
python3 scripts/extract_subtitle_segment.py full.srt 00:15:00 00:16:30 clip.srt

# 去空拍（同時調整字幕時間）
python3 scripts/remove_silence.py clip.mp4 clip.srt output.mp4 output.srt

# 燒錄字幕
python3 scripts/burn_subtitles.py clip.mp4 clip.srt output.mp4 --style coolscholar
```

### burn_subtitles.py 參數

```bash
python3 scripts/burn_subtitles.py video.mp4 subtitle.srt output.mp4 \
  --style coolscholar         # 預設樣式（coolscholar 或 default）
  --font_name "Noto Sans TC"  # 自訂字型
  --font_size 20              # 字體大小
  --margin_v 60               # 底部邊距
  --shadow 1.5                # 陰影大小
  --fontsdir /path/to/fonts   # 字型目錄
```

### remove_silence.py 參數

```bash
# 溫和模式（推薦，保留句間空間）
python3 scripts/remove_silence.py clip.mp4 clip.srt out.mp4 out.srt -30 0.7

# 積極模式（節奏更緊湊）
python3 scripts/remove_silence.py clip.mp4 clip.srt out.mp4 out.srt -30 0.4
```

## 專案結構

```
video-highlight-clipper/
├── CLAUDE.md           # Claude Code 工作流指南（核心）
├── README.md           # 你正在讀的這個
├── scripts/
│   ├── transcribe_video.py          # Whisper 語音轉錄
│   ├── clip_video.py                # 影片剪輯（支援 9:16 裁切）
│   ├── extract_subtitle_segment.py  # 字幕段落提取
│   ├── remove_silence.py            # 去空拍
│   ├── burn_subtitles.py            # 字幕燒錄
│   └── utils.py                     # 工具函式
└── references/         # FFmpeg 和字幕格式參考文件
```

## 系統需求

| 依賴 | 用途 | 必要性 |
|------|------|--------|
| Python 3.8+ | 執行腳本 | 必要 |
| FFmpeg（含 libass） | 影片處理 + 字幕燒錄 | 必要 |
| openai-whisper | 語音轉文字 | 必要 |
| Claude Code | AI 分析精華 | 建議（也可手動操作） |
| 源泉圓體 | coolscholar 字幕樣式 | 可選 |

## 注意事項

- 長影片的 Whisper 轉錄需要較長時間（110 分鐘影片約需 60-90 分鐘，視硬體而定）
- 燒錄字幕時，**先燒字幕再去空拍**，否則字幕時間會對不上
- 影片路徑有空格時，腳本會自動用臨時目錄處理
- 如果影片有 rotation metadata（常見於手機錄影），裁切座標需基於顯示尺寸

## License

MIT
