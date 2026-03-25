#!/usr/bin/env python3
"""
燒錄字幕到影片
使用 FFmpeg libass，支援自訂字型和樣式
"""

import sys
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


# 預設樣式
STYLES = {
    'coolscholar': {
        'font_name': 'GenSenRounded TW B',
        'font_size': 16,
        'bold': 1,
        'shadow': 1.5,
        'margin_v': 80,
        'outline': 1,
    },
    'default': {
        'font_name': '',
        'font_size': 24,
        'bold': 0,
        'shadow': 0,
        'margin_v': 30,
        'outline': 2,
    },
}


def build_force_style(font_name='', font_size=24, bold=0, shadow=0,
                      margin_v=30, outline=2):
    """建立 force_style 字串"""
    parts = []
    if font_name:
        parts.append(f'FontName={font_name}')
    parts.append(f'FontSize={font_size}')
    if bold:
        parts.append(f'Bold={bold}')
    if shadow:
        parts.append(f'Shadow={shadow}')
    parts.append(f'MarginV={margin_v}')
    parts.append('PrimaryColour=&H00FFFFFF')
    parts.append('OutlineColour=&H00000000')
    if shadow:
        parts.append('BackColour=&H80000000')
    parts.append(f'Outline={outline}')
    return ','.join(parts)


def burn_subtitles(video_path, subtitle_path, output_path,
                   style='default', fontsdir=None, force_style=None):
    """
    燒錄字幕到影片

    Args:
        video_path: 輸入影片路徑
        subtitle_path: 字幕檔路徑（SRT）
        output_path: 輸出影片路徑
        style: 預設樣式名稱（'default' 或 'coolscholar'）
        fontsdir: 字型目錄路徑（使用自訂字型時需要）
        force_style: 自訂 force_style 字串（覆蓋 style 參數）
    """
    video_path = Path(video_path)
    subtitle_path = Path(subtitle_path)
    output_path = Path(output_path)

    if not video_path.exists():
        raise FileNotFoundError(f"影片不存在: {video_path}")
    if not subtitle_path.exists():
        raise FileNotFoundError(f"字幕不存在: {subtitle_path}")

    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path:
        raise RuntimeError("FFmpeg 未安裝")

    # 建立 force_style
    if force_style is None:
        if style in STYLES:
            force_style = build_force_style(**STYLES[style])
        else:
            force_style = build_force_style()

    print(f"🎬 燒錄字幕...")
    print(f"   影片: {video_path.name}")
    print(f"   字幕: {subtitle_path.name}")

    # 用 symlink 解決路徑空格問題
    temp_dir = tempfile.mkdtemp(prefix='clipper_')
    try:
        temp_video = os.path.join(temp_dir, 'video.mp4')
        temp_sub = os.path.join(temp_dir, 'subtitle.srt')

        os.symlink(str(video_path.resolve()), temp_video)
        shutil.copy(subtitle_path, temp_sub)

        # 建立 subtitles 濾鏡
        sub_filter = f"subtitles={temp_sub}"
        if fontsdir:
            sub_filter += f":fontsdir={fontsdir}"
        sub_filter += f":force_style='{force_style}'"

        cmd = [
            ffmpeg_path,
            '-i', temp_video,
            '-vf', sub_filter,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-c:a', 'copy',
            '-y', str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ FFmpeg 失敗:\n{result.stderr[-500:]}")
            raise RuntimeError("FFmpeg failed")

        output_size = output_path.stat().st_size / (1024 * 1024)
        print(f"✅ 完成: {output_path} ({output_size:.1f} MB)")
        return str(output_path)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='燒錄字幕到影片')
    parser.add_argument('video', help='輸入影片路徑')
    parser.add_argument('subtitle', help='字幕檔路徑（SRT）')
    parser.add_argument('output', help='輸出影片路徑')
    parser.add_argument('--style', default='default',
                        choices=list(STYLES.keys()),
                        help='預設樣式（default 或 coolscholar）')
    parser.add_argument('--font_name', default=None, help='字型名稱')
    parser.add_argument('--font_size', type=int, default=None, help='字體大小')
    parser.add_argument('--margin_v', type=int, default=None, help='底部邊距')
    parser.add_argument('--shadow', type=float, default=None, help='陰影大小')
    parser.add_argument('--fontsdir', default=None, help='字型目錄路徑')
    parser.add_argument('--force_style', default=None, help='自訂 force_style 字串')

    args = parser.parse_args()

    # 如果有個別參數，建立自訂 force_style
    custom_style = args.force_style
    if custom_style is None and any([args.font_name, args.font_size,
                                      args.margin_v, args.shadow]):
        base = STYLES.get(args.style, STYLES['default']).copy()
        if args.font_name is not None:
            base['font_name'] = args.font_name
        if args.font_size is not None:
            base['font_size'] = args.font_size
        if args.margin_v is not None:
            base['margin_v'] = args.margin_v
        if args.shadow is not None:
            base['shadow'] = args.shadow
        custom_style = build_force_style(**base)

    burn_subtitles(
        args.video, args.subtitle, args.output,
        style=args.style,
        fontsdir=args.fontsdir,
        force_style=custom_style,
    )


if __name__ == '__main__':
    main()
