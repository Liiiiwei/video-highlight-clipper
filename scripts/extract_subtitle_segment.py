#!/usr/bin/env python3
"""
從 SRT 字幕檔擷取指定時間段
讀取 SRT 檔案，呼叫 clip_video.py 中已有的字幕擷取函數
"""

import sys
import pysrt
from pathlib import Path

from utils import time_to_seconds, seconds_to_time
from clip_video import extract_subtitle_segment, save_subtitles_as_srt


def load_srt_as_list(srt_path: str) -> list:
    """
    讀取 SRT 檔案並轉換為字幕 list 格式

    Args:
        srt_path: SRT 檔案路徑

    Returns:
        list: [{'start': float, 'end': float, 'text': str}, ...]
    """
    srt_path = Path(srt_path)
    if not srt_path.exists():
        raise FileNotFoundError(f"字幕檔案不存在: {srt_path}")

    subs = pysrt.open(str(srt_path), encoding='utf-8')
    subtitles = []

    for sub in subs:
        start = (sub.start.hours * 3600 +
                 sub.start.minutes * 60 +
                 sub.start.seconds +
                 sub.start.milliseconds / 1000.0)
        end = (sub.end.hours * 3600 +
               sub.end.minutes * 60 +
               sub.end.seconds +
               sub.end.milliseconds / 1000.0)
        subtitles.append({
            'start': start,
            'end': end,
            'text': sub.text
        })

    return subtitles


def extract_and_save(srt_path: str, start_time: str, end_time: str, output_path: str) -> str:
    """
    從 SRT 擷取指定時間段並保存

    Args:
        srt_path: 完整 SRT 檔案路徑
        start_time: 起始時間
        end_time: 結束時間
        output_path: 輸出 SRT 路徑

    Returns:
        str: 輸出檔案路徑
    """
    print(f"📝 擷取字幕片段: {start_time} - {end_time}")

    subtitles = load_srt_as_list(srt_path)
    start_sec = time_to_seconds(start_time)
    end_sec = time_to_seconds(end_time)

    segment = extract_subtitle_segment(subtitles, start_sec, end_sec, adjust_timestamps=True)

    if not segment:
        print(f"⚠️  指定時間段內沒有找到字幕")
        return output_path

    save_subtitles_as_srt(segment, output_path)
    print(f"✅ 擷取 {len(segment)} 條字幕")
    return output_path


def main():
    """命令列入口"""
    if len(sys.argv) < 5:
        print("Usage: python extract_subtitle_segment.py <srt> <start> <end> <output>")
        print("\nArguments:")
        print("  srt    - 完整 SRT 字幕檔案路徑")
        print("  start  - 起始時間（如 00:12:30）")
        print("  end    - 結束時間（如 00:13:45）")
        print("  output - 輸出 SRT 檔案路徑")
        print("\nExample:")
        print("  python extract_subtitle_segment.py full.srt 00:12:30 00:13:45 clip.srt")
        sys.exit(1)

    srt_path = sys.argv[1]
    start_time = sys.argv[2]
    end_time = sys.argv[3]
    output_path = sys.argv[4]

    try:
        extract_and_save(srt_path, start_time, end_time, output_path)
    except Exception as e:
        print(f"\n❌ 錯誤: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
