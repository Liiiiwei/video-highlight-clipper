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


def check_diarization_ready():
    """
    檢查 diarization 所需的依賴和 token
    回傳 (ready: bool, message: str)
    """
    if not os.environ.get('HF_TOKEN'):
        return False, (
            "需要 Hugging Face token (HF_TOKEN):\n"
            "1. 到 https://huggingface.co/pyannote/speaker-diarization-3.1 同意使用條款\n"
            "2. 建立 token: https://huggingface.co/settings/tokens\n"
            "3. 設定: export HF_TOKEN=hf_xxxxx"
        )

    try:
        import pyannote.audio
    except ImportError:
        return False, "pyannote-audio 未安裝。請執行: pip3 install pyannote-audio"

    return True, "OK"


def diarize(audio_path):
    """
    用 pyannote-audio 做 speaker diarization
    回傳說話者分段列表
    """
    ready, msg = check_diarization_ready()
    if not ready:
        raise RuntimeError(msg)

    from pyannote.audio import Pipeline
    import torch

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=os.environ['HF_TOKEN']
    )

    if torch.backends.mps.is_available():
        pipeline.to(torch.device("mps"))

    print(f"   執行 speaker diarization...")
    diarization_result = pipeline(audio_path)

    segments = []
    for turn, _, speaker in diarization_result.itertracks(yield_label=True):
        segments.append({
            'start': round(turn.start, 3),
            'end': round(turn.end, 3),
            'speaker': speaker
        })

    merged = []
    for seg in segments:
        if merged and merged[-1]['speaker'] == seg['speaker']:
            merged[-1]['end'] = seg['end']
        else:
            merged.append(seg.copy())

    print(f"   偵測到 {len(set(s['speaker'] for s in merged))} 位說話者，{len(merged)} 個段落")
    return merged


def slice_diarization(segments, clip_start, clip_end):
    """
    從完整 diarization 結果中擷取指定時間範圍
    時間重置為相對於 clip_start
    """
    result = []
    for seg in segments:
        if seg['end'] <= clip_start or seg['start'] >= clip_end:
            continue

        new_start = max(seg['start'], clip_start) - clip_start
        new_end = min(seg['end'], clip_end) - clip_start

        if new_end - new_start > 0.05:
            result.append({
                'start': round(new_start, 3),
                'end': round(new_end, 3),
                'speaker': seg['speaker']
            })

    return result


def compute_audio_energies(video_paths, offsets, total_duration, hop_ms=50):
    """計算每個機位在統一時間軸上的能量包絡"""
    n_hops = int(total_duration * 1000 / hop_ms)
    energies = {}

    for cam_name, path in video_paths.items():
        envelope = extract_audio_envelope(path, hop_ms=hop_ms)
        offset_hops = int(offsets.get(cam_name, 0) * 1000 / hop_ms)

        aligned = np.zeros(n_hops)
        src_start = max(0, -offset_hops)
        dst_start = max(0, offset_hops)
        length = min(len(envelope) - src_start, n_hops - dst_start)
        if length > 0:
            aligned[dst_start:dst_start + length] = envelope[src_start:src_start + length]

        energies[cam_name] = aligned

    return energies


def match_speakers_to_cameras(diarization, audio_energies, hop_ms=50, manual_map=None):
    """配對說話者到機位"""
    if manual_map:
        return manual_map.copy(), 1.0

    speakers = list(set(seg['speaker'] for seg in diarization))
    cam_names = list(audio_energies.keys())

    speaker_cam_energy = {}
    for speaker in speakers:
        speaker_cam_energy[speaker] = {}
        for cam_name, energy in audio_energies.items():
            total_energy = 0.0
            total_hops = 0
            for seg in diarization:
                if seg['speaker'] != speaker:
                    continue
                start_hop = int(seg['start'] * 1000 / hop_ms)
                end_hop = int(seg['end'] * 1000 / hop_ms)
                end_hop = min(end_hop, len(energy))
                if end_hop > start_hop:
                    total_energy += np.sum(energy[start_hop:end_hop])
                    total_hops += end_hop - start_hop

            avg = total_energy / max(total_hops, 1)
            speaker_cam_energy[speaker][cam_name] = avg

    speaker_map = {}
    confidences = []

    for speaker in speakers:
        energies = speaker_cam_energy[speaker]
        sorted_cams = sorted(energies.items(), key=lambda x: x[1], reverse=True)
        best_cam, best_energy = sorted_cams[0]
        second_energy = sorted_cams[1][1] if len(sorted_cams) > 1 else 0

        speaker_map[speaker] = best_cam

        if best_energy > 0:
            ratio = (best_energy - second_energy) / best_energy
            confidences.append(ratio)
        else:
            confidences.append(0.0)

    overall_confidence = np.mean(confidences) if confidences else 0.0

    return speaker_map, round(float(overall_confidence), 3)


def generate_switch_list(diarization, speaker_camera_map, min_segment=2.0):
    switches = []
    for seg in diarization:
        camera = speaker_camera_map.get(seg['speaker'], list(speaker_camera_map.values())[0])
        duration = seg['end'] - seg['start']
        warning = None
        if duration < min_segment:
            warning = f"很短({duration:.1f}s)，建議併入前段"
        switches.append({
            'start': seg['start'], 'end': seg['end'],
            'speaker': seg['speaker'], 'camera': camera, 'warning': warning,
        })
    return switches


def format_switch_list_display(switches):
    from utils import get_video_duration_display
    lines = ["多機位切換清單：\n"]
    lines.append(f"{'時間段':<24}{'說話者':<16}{'機位':<16}")
    lines.append("-" * 56)
    for sw in switches:
        time_range = f"{get_video_duration_display(sw['start'])} - {get_video_duration_display(sw['end'])}"
        line = f"{time_range:<24}{sw['speaker']:<16}{sw['camera']:<16}"
        if sw['warning']:
            line += f"⚠️ {sw['warning']}"
        lines.append(line)
    warnings = [sw for sw in switches if sw['warning']]
    if warnings:
        lines.append(f"\n⚠️ {len(warnings)} 個段落建議調整。")
    return '\n'.join(lines)


def save_switch_list_json(switches, cameras, offsets, speaker_map, confidence, output_path):
    data = {
        'version': 1, 'created_at': datetime.now().isoformat(),
        'base_camera': cameras[0], 'cameras': cameras,
        'offsets': offsets, 'speaker_map': speaker_map,
        'match_confidence': confidence,
        'switches': [
            {'start': sw['start'], 'end': sw['end'], 'speaker': sw['speaker'], 'camera': sw['camera']}
            for sw in switches
        ],
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return output_path


def build_multicam_filter(switches, video_inputs, offsets):
    filter_parts = []
    n = len(switches)
    for i, sw in enumerate(switches):
        cam = sw['camera']
        input_idx = video_inputs[cam]
        offset = offsets.get(cam, 0.0)
        actual_start = sw['start'] + offset
        actual_end = sw['end'] + offset
        filter_parts.append(
            f"[{input_idx}:v]trim=start={actual_start}:end={actual_end},"
            f"setpts=PTS-STARTPTS,scale=1920:1080:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2[v{i}]"
        )
    base_input = video_inputs[list(video_inputs.keys())[0]]
    for i, sw in enumerate(switches):
        filter_parts.append(
            f"[{base_input}:a]atrim=start={sw['start']}:end={sw['end']},"
            f"asetpts=PTS-STARTPTS[a{i}]"
        )
    concat_inputs = ''.join(f'[v{i}][a{i}]' for i in range(n))
    filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]")
    return ';'.join(filter_parts), n


def compose_video(switch_list, video_paths, offsets, output_path):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError("FFmpeg 未安裝")
    cam_names = list(video_paths.keys())
    video_inputs = {name: i for i, name in enumerate(cam_names)}
    filter_str, n_segments = build_multicam_filter(switch_list, video_inputs, offsets)
    cmd = [ffmpeg]
    for cam_name in cam_names:
        cmd.extend(['-i', str(video_paths[cam_name])])
    cmd.extend([
        '-filter_complex', filter_str,
        '-map', '[outv]', '-map', '[outa]',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'aac', '-b:a', '192k',
        '-y', str(output_path)
    ])
    print(f"🎬 合成多機位影片（{n_segments} 段）...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ FFmpeg 失敗:\n{result.stderr[-500:]}")
        raise RuntimeError("FFmpeg compose failed")
    output_size = Path(output_path).stat().st_size / (1024 * 1024)
    print(f"✅ 合成完成: {output_path} ({output_size:.1f} MB)")
    return str(output_path)
