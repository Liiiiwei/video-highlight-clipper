#!/usr/bin/env python3
"""
移除影片中的靜音段，並同步調整字幕時間戳
使用 FFmpeg 單一指令 trim+concat 濾鏡避免時間飄移
"""

import sys
import subprocess
import shutil
import re
from pathlib import Path
from utils import get_video_duration


def detect_silences(video_path, noise_db=-30, min_duration=0.4, ffmpeg_path=None):
    """偵測影片中的靜音段"""
    if not ffmpeg_path:
        ffmpeg_path = shutil.which('ffmpeg')

    cmd = [
        ffmpeg_path, '-i', str(video_path),
        '-af', f'silencedetect=noise={noise_db}dB:d={min_duration}',
        '-f', 'null', '-'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    silences = []
    lines = result.stderr.split('\n')
    current_start = None

    for line in lines:
        if 'silence_start:' in line:
            match = re.search(r'silence_start:\s*([\d.]+)', line)
            if match:
                current_start = float(match.group(1))
        elif 'silence_end:' in line and current_start is not None:
            match = re.search(r'silence_end:\s*([\d.]+)', line)
            if match:
                silences.append((current_start, float(match.group(1))))
                current_start = None

    return silences


def get_speaking_segments(silences, total_duration, padding=0.08):
    """從靜音段計算出說話段"""
    segments = []
    current_pos = 0.0

    for silence_start, silence_end in silences:
        seg_start = current_pos
        seg_end = silence_start + padding

        if seg_end > seg_start + 0.05:
            segments.append((round(seg_start, 3), round(seg_end, 3)))

        current_pos = silence_end - padding
        current_pos = max(current_pos, silence_end - 0.1)

    if current_pos < total_duration:
        segments.append((round(current_pos, 3), round(total_duration, 3)))

    return segments


def build_trim_concat_filter(segments):
    """
    建立 FFmpeg trim+concat 濾鏡字串
    單一指令處理，避免多段拼接造成的時間飄移
    """
    n = len(segments)
    filter_parts = []

    for i, (start, end) in enumerate(segments):
        # 影片 trim
        filter_parts.append(
            f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]"
        )
        # 音頻 trim
        filter_parts.append(
            f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}]"
        )

    # concat 所有段落
    concat_inputs = ''.join(f'[v{i}][a{i}]' for i in range(n))
    filter_parts.append(
        f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]"
    )

    return ';'.join(filter_parts)


def parse_srt_time(time_str):
    """解析 SRT 時間格式"""
    parts = time_str.replace(',', '.').split(':')
    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])


def format_srt_time(seconds):
    """格式化為 SRT 時間"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    ms = int((s - int(s)) * 1000)
    return f"{h:02d}:{m:02d}:{int(s):02d},{ms:03d}"


def adjust_subtitle_timing(srt_path, segments, output_path):
    """根據剪輯段落調整字幕時間戳"""
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = content.strip().split('\n\n')
    subtitles = []
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            match = re.match(r'([\d:,]+)\s*-->\s*([\d:,]+)', lines[1])
            if match:
                start = parse_srt_time(match.group(1))
                end = parse_srt_time(match.group(2))
                text = '\n'.join(lines[2:])
                subtitles.append({'start': start, 'end': end, 'text': text})

    # 建立時間映射：原始時間 → 新時間
    new_subtitles = []
    accumulated_time = 0.0

    for seg_start, seg_end in segments:
        seg_duration = seg_end - seg_start
        for sub in subtitles:
            sub_mid = (sub['start'] + sub['end']) / 2
            # 字幕中點落在此段落內
            if sub_mid >= seg_start and sub_mid < seg_end:
                new_start = accumulated_time + max(0, sub['start'] - seg_start)
                new_end = accumulated_time + min(seg_duration, sub['end'] - seg_start)
                if new_end > new_start + 0.1:
                    new_subtitles.append({
                        'start': new_start,
                        'end': new_end,
                        'text': sub['text']
                    })
        accumulated_time += seg_duration

    # 去重（同一條字幕可能因段落重疊被加入兩次）
    seen_texts = set()
    unique_subs = []
    for sub in new_subtitles:
        key = f"{sub['start']:.2f}_{sub['text']}"
        if key not in seen_texts:
            seen_texts.add(key)
            unique_subs.append(sub)

    with open(output_path, 'w', encoding='utf-8') as f:
        for i, sub in enumerate(unique_subs, 1):
            f.write(f"{i}\n")
            f.write(f"{format_srt_time(sub['start'])} --> {format_srt_time(sub['end'])}\n")
            f.write(f"{sub['text']}\n\n")

    return len(unique_subs)


def remove_silence(video_path, srt_path, output_video, output_srt,
                   noise_db=-30, min_duration=0.4):
    """主函數：移除靜音段並調整字幕"""
    video_path = Path(video_path)
    ffmpeg_path = shutil.which('ffmpeg')

    print(f"🔇 偵測靜音段...")
    silences = detect_silences(video_path, noise_db, min_duration, ffmpeg_path)
    print(f"   找到 {len(silences)} 段靜音")

    duration = get_video_duration(video_path)
    segments = get_speaking_segments(silences, duration)
    print(f"   保留 {len(segments)} 段說話內容")

    total_speaking = sum(e - s for s, e in segments)
    saved = duration - total_speaking
    print(f"   原始時長: {duration:.1f}s → 新時長: {total_speaking:.1f}s（節省 {saved:.1f}s）")

    # 單一指令 trim+concat
    filter_complex = build_trim_concat_filter(segments)

    print(f"   處理影片（單一指令模式）...")
    cmd = [
        ffmpeg_path,
        '-i', str(video_path),
        '-filter_complex', filter_complex,
        '-map', '[outv]', '-map', '[outa]',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'aac', '-b:a', '192k',
        '-y', str(output_video)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ FFmpeg 失敗:\n{result.stderr[-500:]}")
        raise RuntimeError("FFmpeg failed")

    # 調整字幕
    if srt_path and Path(srt_path).exists():
        count = adjust_subtitle_timing(srt_path, segments, output_srt)
        print(f"   字幕已調整: {count} 條")

    output_size = Path(output_video).stat().st_size / (1024 * 1024)
    print(f"✅ 完成！輸出: {output_video} ({output_size:.1f} MB)")

    return segments


if __name__ == '__main__':
    if len(sys.argv) < 5:
        print("Usage: python remove_silence.py <video> <srt> <output_video> <output_srt> [noise_db] [min_duration]")
        sys.exit(1)

    video = sys.argv[1]
    srt = sys.argv[2]
    out_video = sys.argv[3]
    out_srt = sys.argv[4]
    noise_db = int(sys.argv[5]) if len(sys.argv) > 5 else -30
    min_dur = float(sys.argv[6]) if len(sys.argv) > 6 else 0.4

    remove_silence(video, srt, out_video, out_srt, noise_db, min_dur)
