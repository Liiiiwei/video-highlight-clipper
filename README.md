# Video Highlight Clipper

從長影片中自動找出精華片段，剪輯為短影片並加上字幕。專為 Claude Code 設計。

## 安裝

```bash
git clone <repo-url>
cd Youtube-clipper-skill
```

### 系統需求

```bash
# FFmpeg（含 libass 字幕支援）
# macOS:
brew install homebrew-ffmpeg/ffmpeg/ffmpeg

# Whisper 語音轉錄
pip3 install openai-whisper
```

### 字型（可選）

使用 `coolscholar` 樣式需要安裝[源泉圓體](https://github.com/ButTaiwan/genseki-font)。

## 使用方式

在 Claude Code 中，進入此專案目錄後直接說：

```
幫我把這個影片剪成精華片段：/path/to/video.mp4
```

Claude Code 會自動：
1. 用 Whisper 轉錄字幕
2. 分析內容找出精華
3. 剪輯 + 去空拍 + 上字幕

### 也可以單獨使用各腳本

```bash
# 轉錄
python3 scripts/transcribe_video.py video.mp4

# 剪輯片段
python3 scripts/clip_video.py video.mp4 00:15:00 00:16:30 clip.mp4

# 提取對應字幕
python3 scripts/extract_subtitle_segment.py full.srt 00:15:00 00:16:30 clip.srt

# 去空拍
python3 scripts/remove_silence.py clip.mp4 clip.srt output.mp4 output.srt

# 燒錄字幕
python3 scripts/burn_subtitles.py clip.mp4 clip.srt output.mp4 --style coolscholar
```

## 功能

- **Whisper 轉錄** — 自動產生中文字幕
- **AI 精華分析** — Claude 語義分析找出金句、知識點、故事
- **去空拍** — 移除靜音段，保留自然節奏
- **字幕燒錄** — 支援自訂字型和樣式預設
- **影片濃縮** — 長片段自動精簡到 60-90 秒
- **音軌替換** — 可用獨立錄音檔替換影片音軌
- **9:16 裁切** — 橫式影片轉直式 Reels/Shorts

## License

MIT
