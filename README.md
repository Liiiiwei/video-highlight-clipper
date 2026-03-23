# Local Highlight Clipper

> AI 驅動的本地影片精華剪輯工具，專為 Claude Code 設計。從直播錄影中自動辨識精華片段，剪輯為 Reels 風格短片，並自動生成和燒錄中文字幕。

## 功能

- **Whisper 語音轉錄** — 自動將影片語音轉為 SRT 字幕（支援 GPU 加速）
- **AI 精華分析** — Claude AI 語義分析找出金句、知識點、情緒高點等精華片段
- **精確剪輯** — FFmpeg re-encode 模式確保 15-90 秒短片的精確切割
- **字幕燒錄** — 自動將字幕硬編碼到影片中
- **字幕後處理** — 合併短字幕、移除語氣詞、修正時間戳重疊

## 安裝

```bash
git clone https://github.com/op7418/Youtube-clipper-skill.git
cd Youtube-clipper-skill
bash install_as_skill.sh
```

安裝腳本會：
- 複製檔案到 `~/.claude/skills/local-highlight-clipper/`
- 安裝 Python 依賴（openai-whisper、pysrt）
- 檢測系統依賴（FFmpeg、Whisper）

## 系統需求

| 依賴 | 用途 | 安裝方式 |
|------|------|----------|
| Python 3.8+ | 腳本執行 | 預裝 |
| FFmpeg (含 libass) | 影片剪輯 + 字幕燒錄 | `brew install ffmpeg` |
| Whisper | 語音轉文字 | `pip install openai-whisper` |

## 使用方式

在 Claude Code 中輸入：

```
幫我把這個直播錄影剪成精華片段：/path/to/video.mp4
```

工具會自動：
1. 檢測環境依賴
2. 用 Whisper 轉錄語音為字幕
3. AI 分析找出精華片段
4. 讓你選擇要剪的段落
5. 自動剪輯 + 燒錄字幕

## 支援格式

mp4、mkv、mov、flv、ts、webm

## License

MIT
