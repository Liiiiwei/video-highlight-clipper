#!/usr/bin/env python3
"""
影片語音轉錄
使用 Whisper 將影片音訊轉為 SRT 字幕，含字幕後處理
"""

import sys
import re
import subprocess
import shutil
from pathlib import Path

# 支援的影片格式
SUPPORTED_FORMATS = {'.mp4', '.mkv', '.mov', '.flv', '.ts', '.webm'}

# 純語氣詞清單
FILLER_WORDS = {'嗯', '呃', '啊', '那個', '就是', '然後', '對'}


def detect_gpu() -> str:
    """偵測可用的 GPU 加速"""
    try:
        result = subprocess.run(
            ['python3', '-c', 'import torch; print(torch.cuda.is_available())'],
            capture_output=True, text=True, timeout=10
        )
        if 'True' in result.stdout:
            return 'cuda'
    except Exception:
        pass

    try:
        result = subprocess.run(
            ['python3', '-c', 'import torch; print(torch.backends.mps.is_available())'],
            capture_output=True, text=True, timeout=10
        )
        if 'True' in result.stdout:
            return 'mps'
    except Exception:
        pass

    return 'cpu'


def select_model(device: str) -> str:
    """根據裝置選擇 Whisper 模型"""
    if device in ('cuda', 'mps'):
        return 'medium'
    return 'base'


def _convert_vtt_to_srt(vtt_path: Path, srt_path: Path):
    """將 VTT 字幕轉換為 SRT 格式"""
    with open(vtt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 移除 VTT 標頭和樣式
    content = re.sub(r'^WEBVTT.*?\n\n', '', content, flags=re.DOTALL)
    content = re.sub(r'STYLE.*?-->', '', content, flags=re.DOTALL)

    blocks = content.strip().split('\n\n')
    srt_lines = []
    index = 1

    for block in blocks:
        lines = block.strip().split('\n')
        timestamp_line = None
        text_lines = []

        for line in lines:
            if '-->' in line:
                # VTT 用 . 分隔毫秒，SRT 用 ,
                timestamp_line = line.replace('.', ',')
                # 移除位置資訊
                timestamp_line = re.sub(r'align:.*|position:.*', '', timestamp_line).strip()
            elif line and not line.isdigit():
                text_lines.append(re.sub(r'<[^>]+>', '', line))

        if timestamp_line and text_lines:
            srt_lines.append(f"{index}")
            srt_lines.append(timestamp_line)
            srt_lines.extend(text_lines)
            srt_lines.append('')
            index += 1

    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(srt_lines))

    print(f"✅ VTT → SRT 轉換完成: {srt_path}")


def transcribe(video_path: str, model_name: str = None, language: str = 'zh') -> str:
    """
    使用 Whisper 轉錄影片

    Args:
        video_path: 影片檔案路徑
        model_name: Whisper 模型名稱（可選，自動選擇）
        language: 語言代碼

    Returns:
        str: 產生的 SRT 檔案路徑
    """
    video_path = Path(video_path)

    if not video_path.exists():
        raise FileNotFoundError(f"影片檔案不存在: {video_path}")

    if video_path.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(
            f"不支援的影片格式: {video_path.suffix}\n"
            f"支援格式: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    # 檢查是否已有字幕檔
    srt_path = video_path.with_suffix('.srt')
    if srt_path.exists():
        print(f"✅ 已找到現有字幕檔: {srt_path}")
        print(f"   跳過轉錄，直接使用現有字幕")
        return str(srt_path)

    vtt_path = video_path.with_suffix('.vtt')
    if vtt_path.exists():
        print(f"✅ 已找到現有 VTT 字幕檔: {vtt_path}")
        print(f"   轉換為 SRT 格式...")
        srt_path = vtt_path.with_suffix('.srt')
        _convert_vtt_to_srt(vtt_path, srt_path)
        return str(srt_path)

    # 偵測 GPU
    device = detect_gpu()
    print(f"🔍 偵測到裝置: {device}")

    if device == 'cpu':
        print("⚠️  無 GPU 加速，轉錄速度較慢（約為 GPU 的 5-10 倍）")

    # 選擇模型
    if model_name is None:
        model_name = select_model(device)
    print(f"📦 使用 Whisper 模型: {model_name}")

    # 檢查 whisper 命令
    whisper_cmd = shutil.which('whisper')
    if not whisper_cmd:
        raise RuntimeError(
            "Whisper 未安裝。請執行:\n"
            "  pip install openai-whisper"
        )

    # 執行 Whisper 轉錄
    output_dir = str(video_path.parent)
    print(f"🎙️  開始轉錄: {video_path.name}")
    print(f"   輸出目錄: {output_dir}")
    print(f"   語言: {language}")
    print(f"   這可能需要幾分鐘，請耐心等候...")

    cmd = [
        whisper_cmd,
        str(video_path),
        '--model', model_name,
        '--language', language,
        '--output_format', 'srt',
        '--output_dir', output_dir,
    ]

    if device != 'cpu':
        cmd.extend(['--device', device])

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Whisper 轉錄失敗:")
        print(result.stderr)
        raise RuntimeError(f"Whisper 執行失敗 (return code {result.returncode})")

    # Whisper 輸出的 SRT 檔案名稱
    srt_path = video_path.with_suffix('.srt')
    if not srt_path.exists():
        raise RuntimeError(f"轉錄完成但未找到 SRT 檔案: {srt_path}")

    print(f"✅ 轉錄完成: {srt_path}")
    return str(srt_path)


def postprocess_srt(srt_path: str) -> str:
    """
    字幕後處理：合併短字幕、移除語氣詞、修正時間戳重疊

    Args:
        srt_path: SRT 檔案路徑

    Returns:
        str: 處理後的 SRT 檔案路徑（覆寫原檔）
    """
    import pysrt

    srt_path = Path(srt_path)
    print(f"🔧 字幕後處理: {srt_path.name}")

    subs = pysrt.open(str(srt_path), encoding='utf-8')
    original_count = len(subs)

    # 1. 移除純語氣詞字幕
    filtered = []
    for sub in subs:
        text = sub.text.strip()
        # 移除只包含語氣詞的字幕
        cleaned = re.sub(r'[，。、！？\s]', '', text)
        if cleaned and cleaned not in FILLER_WORDS:
            filtered.append(sub)

    # 2. 合併過短字幕（< 1 秒）
    merged = []
    i = 0
    while i < len(filtered):
        current = filtered[i]
        duration_ms = (current.end - current.start).ordinal

        if duration_ms < 1000 and i + 1 < len(filtered):
            # 合併到下一條字幕
            next_sub = filtered[i + 1]
            next_sub.text = current.text + ' ' + next_sub.text
            next_sub.start = current.start
            i += 1
            continue

        merged.append(current)
        i += 1

    # 3. 修正時間戳重疊
    for i in range(len(merged) - 1):
        if merged[i].end > merged[i + 1].start:
            merged[i].end = merged[i + 1].start

    # 重新編號
    for i, sub in enumerate(merged):
        sub.index = i + 1

    # 寫回檔案
    new_subs = pysrt.SubRipFile(items=merged)
    new_subs.save(str(srt_path), encoding='utf-8')

    removed = original_count - len(merged)
    print(f"   原始字幕: {original_count} 條")
    print(f"   處理後: {len(merged)} 條（移除/合併 {removed} 條）")
    print(f"✅ 字幕後處理完成")

    return str(srt_path)


def main():
    """命令列入口"""
    if len(sys.argv) < 2:
        print("Usage: python transcribe_video.py <video_path> [model] [language]")
        print("\nArguments:")
        print("  video_path - 影片檔案路徑")
        print("  model      - Whisper 模型（base/medium/large），預設自動選擇")
        print("  language   - 語言代碼，預設 zh")
        print(f"\n支援格式: {', '.join(sorted(SUPPORTED_FORMATS))}")
        print("\nExample:")
        print("  python transcribe_video.py livestream.mp4")
        print("  python transcribe_video.py livestream.mp4 medium zh")
        sys.exit(1)

    video_path = sys.argv[1]
    model_name = sys.argv[2] if len(sys.argv) > 2 else None
    language = sys.argv[3] if len(sys.argv) > 3 else 'zh'

    try:
        srt_path = transcribe(video_path, model_name, language)
        postprocess_srt(srt_path)
        print(f"\n✨ 完成！字幕檔案: {srt_path}")
    except Exception as e:
        print(f"\n❌ 錯誤: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
