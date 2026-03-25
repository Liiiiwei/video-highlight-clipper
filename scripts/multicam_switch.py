#!/usr/bin/env python3
"""
多機位自動切換
自動同步多機位影片、辨識說話者、生成切換清單、合成影片
"""

import sys
import os
import subprocess
import shutil
import json
import tempfile
import numpy as np
from pathlib import Path
from datetime import datetime
from utils import get_video_duration


def extract_audio_envelope(video_path, sr=16000, hop_ms=50):
    """
    提取影片音訊的能量包絡
    用 FFmpeg 提取原始 PCM，再計算每個 hop 的 RMS 能量
    """
    ffmpeg = shutil.which('ffmpeg')
    cmd = [
        ffmpeg, '-i', str(video_path),
        '-vn', '-ac', '1', '-ar', str(sr),
        '-f', 's16le', '-acodec', 'pcm_s16le', '-'
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"無法提取音訊: {video_path}")

    audio = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32)
    audio /= 32768.0

    hop_samples = int(sr * hop_ms / 1000)
    n_hops = len(audio) // hop_samples
    envelope = np.array([
        np.sqrt(np.mean(audio[i * hop_samples:(i + 1) * hop_samples] ** 2))
        for i in range(n_hops)
    ])

    return envelope


def cross_correlate_envelopes(env1, env2, hop_ms=50):
    """
    用交叉相關找兩個能量包絡的最佳偏移
    回傳 (偏移秒數, 相關度)
    """
    env1 = (env1 - np.mean(env1)) / (np.std(env1) + 1e-10)
    env2 = (env2 - np.mean(env2)) / (np.std(env2) + 1e-10)

    correlation = np.correlate(env1, env2, mode='full')
    correlation /= max(len(env1), len(env2))

    best_idx = np.argmax(correlation)
    best_corr = correlation[best_idx]
    # 正值代表 env2 相對 env1 延遲（env2 需要往前移）
    offset_hops = (len(env2) - 1) - best_idx
    offset_seconds = offset_hops * hop_ms / 1000.0

    return offset_seconds, best_corr


def sync_cameras(video_paths, manual_offsets=None):
    """
    同步多個機位影片，回傳各機位的時間偏移
    第一個機位為基準（偏移 = 0）
    """
    if manual_offsets is None:
        manual_offsets = {}

    base = video_paths[0]
    base_name = Path(base).name
    offsets = {base_name: 0.0}

    # 檢查是否所有機位都有手動偏移（不需要提取音訊）
    all_manual = all(
        Path(p).name in manual_offsets
        for p in video_paths[1:]
    )

    if not all_manual:
        # 預先提取 base 的 envelope
        env_base_coarse = extract_audio_envelope(base, hop_ms=50)
        env_base_fine = extract_audio_envelope(base, hop_ms=10)

    for cam_path in video_paths[1:]:
        cam_name = Path(cam_path).name
        if cam_name in manual_offsets:
            offsets[cam_name] = manual_offsets[cam_name]
            print(f"   {cam_name}: 使用手動偏移 {manual_offsets[cam_name]:.3f}s")
            continue

        print(f"   同步 {cam_name}...")

        # Coarse pass: 50ms hop
        env_cam = extract_audio_envelope(cam_path, hop_ms=50)
        coarse_offset, coarse_corr = cross_correlate_envelopes(env_base_coarse, env_cam, hop_ms=50)

        if coarse_corr < 0.5:
            print(f"   ⚠️ {cam_name} 自動同步失敗（相關度 {coarse_corr:.3f}），請用 --offset 手動指定")
            offsets[cam_name] = 0.0
            continue

        # Fine pass: 10ms hop，只在 coarse 結果附近 ±2 秒搜尋
        env_cam_fine = extract_audio_envelope(cam_path, hop_ms=10)

        coarse_hop_fine = int(coarse_offset * 1000 / 10)
        search_range = int(2000 / 10)  # ±2 秒 = ±200 hop
        cam_start = max(0, coarse_hop_fine - search_range)
        cam_end = min(len(env_cam_fine), coarse_hop_fine + len(env_base_fine) + search_range)
        env_cam_crop = env_cam_fine[cam_start:cam_end]

        fine_offset_local, fine_corr = cross_correlate_envelopes(env_base_fine, env_cam_crop, hop_ms=10)
        fine_offset = fine_offset_local + cam_start * 10 / 1000.0

        offsets[cam_name] = fine_offset
        print(f"   {cam_name}: 偏移 {fine_offset:.3f}s（相關度 {fine_corr:.3f}）")

    return offsets
