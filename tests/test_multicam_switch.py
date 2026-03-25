#!/usr/bin/env python3
"""multicam_switch.py 單元測試"""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))


class TestExtractAudioEnvelope:
    """測試音訊能量包絡提取"""

    def test_returns_numpy_array(self, tmp_path):
        """用 FFmpeg 產生測試音訊，驗證回傳 numpy array"""
        import subprocess, shutil
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg:
            pytest.skip("FFmpeg not installed")

        test_wav = str(tmp_path / "test.wav")
        subprocess.run([
            ffmpeg, '-f', 'lavfi', '-i',
            'sine=frequency=440:duration=2',
            '-ar', '16000', '-ac', '1', '-y', test_wav
        ], capture_output=True)

        from multicam_switch import extract_audio_envelope
        envelope = extract_audio_envelope(test_wav, sr=16000, hop_ms=50)

        assert isinstance(envelope, np.ndarray)
        assert len(envelope) > 0
        assert len(envelope) == pytest.approx(40, abs=2)


class TestCrossCorrelateEnvelopes:
    """測試能量包絡交叉相關"""

    def test_identical_signals_offset_zero(self):
        from multicam_switch import cross_correlate_envelopes
        signal = np.random.rand(100)
        offset, corr = cross_correlate_envelopes(signal, signal, hop_ms=50)
        assert abs(offset) < 0.1
        assert corr > 0.99

    def test_shifted_signal(self):
        from multicam_switch import cross_correlate_envelopes
        base = np.random.rand(200)
        shifted = np.zeros(200)
        shifted[10:] = base[:-10]

        offset, corr = cross_correlate_envelopes(base, shifted, hop_ms=50)
        assert abs(offset - 0.5) < 0.15
        assert corr > 0.7


class TestSyncCameras:
    """測試多機位同步"""

    def test_manual_offsets_override(self):
        from multicam_switch import sync_cameras
        manual = {'cam2.mp4': 1.5}
        result = sync_cameras(
            ['cam1.mp4', 'cam2.mp4'],
            manual_offsets=manual
        )
        assert result['cam1.mp4'] == 0.0
        assert result['cam2.mp4'] == 1.5


class TestDiarize:
    """測試 speaker diarization"""

    def test_returns_list_of_segments(self):
        """diarize 應回傳段落列表"""
        pytest.importorskip("pyannote.audio")
        if not os.environ.get('HF_TOKEN'):
            pytest.skip("HF_TOKEN not set")
        from multicam_switch import diarize
        assert callable(diarize)

    def test_check_hf_token_missing(self):
        """缺少 HF_TOKEN 應拋出清楚的錯誤訊息"""
        from multicam_switch import check_diarization_ready
        old_token = os.environ.pop('HF_TOKEN', None)
        try:
            ready, msg = check_diarization_ready()
            assert not ready
            assert 'HF_TOKEN' in msg
        finally:
            if old_token:
                os.environ['HF_TOKEN'] = old_token


class TestSliceDiarization:
    """測試 diarization 結果切片"""

    def test_slice_within_range(self):
        """只保留指定時間範圍內的段落"""
        from multicam_switch import slice_diarization

        segments = [
            {'start': 0.0, 'end': 10.0, 'speaker': 'A'},
            {'start': 10.0, 'end': 20.0, 'speaker': 'B'},
            {'start': 20.0, 'end': 30.0, 'speaker': 'A'},
            {'start': 30.0, 'end': 40.0, 'speaker': 'B'},
        ]
        result = slice_diarization(segments, clip_start=5.0, clip_end=25.0)

        assert len(result) == 3
        assert result[0]['start'] == 0.0
        assert result[0]['end'] == 5.0
        assert result[0]['speaker'] == 'A'
        assert result[1]['start'] == 5.0
        assert result[1]['end'] == 15.0
        assert result[2]['start'] == 15.0
        assert result[2]['end'] == 20.0


class TestMatchSpeakersToCameras:
    """測試機位-說話者配對"""

    def test_basic_matching(self):
        """speaker 說話時哪個機位能量高就配對到哪個機位"""
        from multicam_switch import match_speakers_to_cameras

        diarization = [
            {'start': 0.0, 'end': 10.0, 'speaker': 'SPEAKER_00'},
            {'start': 10.0, 'end': 20.0, 'speaker': 'SPEAKER_01'},
        ]
        speaker_map, confidence = match_speakers_to_cameras(
            diarization,
            audio_energies={
                'cam1.mp4': np.array([0.8] * 10 + [0.1] * 10),
                'cam2.mp4': np.array([0.1] * 10 + [0.8] * 10),
            },
            hop_ms=1000,
        )

        assert speaker_map['SPEAKER_00'] == 'cam1.mp4'
        assert speaker_map['SPEAKER_01'] == 'cam2.mp4'
        assert confidence > 0.5

    def test_manual_map_overrides(self):
        """手動配對應覆蓋自動結果"""
        from multicam_switch import match_speakers_to_cameras

        diarization = [
            {'start': 0.0, 'end': 10.0, 'speaker': 'SPEAKER_00'},
        ]
        manual = {'SPEAKER_00': 'cam2.mp4'}
        speaker_map, confidence = match_speakers_to_cameras(
            diarization,
            audio_energies={'cam1.mp4': np.ones(10), 'cam2.mp4': np.ones(10)},
            hop_ms=1000,
            manual_map=manual,
        )
        assert speaker_map['SPEAKER_00'] == 'cam2.mp4'
        assert confidence == 1.0

    def test_low_confidence_warning(self):
        """能量差異小時信心度應偏低"""
        from multicam_switch import match_speakers_to_cameras

        diarization = [
            {'start': 0.0, 'end': 10.0, 'speaker': 'SPEAKER_00'},
        ]
        speaker_map, confidence = match_speakers_to_cameras(
            diarization,
            audio_energies={
                'cam1.mp4': np.array([0.5] * 10),
                'cam2.mp4': np.array([0.49] * 10),
            },
            hop_ms=1000,
        )
        assert confidence < 0.6


class TestGenerateSwitchList:
    def test_basic_switch_list(self):
        from multicam_switch import generate_switch_list
        diarization = [
            {'start': 0.0, 'end': 15.0, 'speaker': 'A'},
            {'start': 15.0, 'end': 30.0, 'speaker': 'B'},
            {'start': 30.0, 'end': 45.0, 'speaker': 'A'},
        ]
        speaker_map = {'A': 'cam1.mp4', 'B': 'cam2.mp4'}
        result = generate_switch_list(diarization, speaker_map, min_segment=2.0)
        assert len(result) == 3
        assert result[0]['camera'] == 'cam1.mp4'
        assert result[1]['camera'] == 'cam2.mp4'
        assert result[0]['warning'] is None

    def test_short_segment_warning(self):
        from multicam_switch import generate_switch_list
        diarization = [
            {'start': 0.0, 'end': 15.0, 'speaker': 'A'},
            {'start': 15.0, 'end': 16.5, 'speaker': 'B'},
            {'start': 16.5, 'end': 30.0, 'speaker': 'A'},
        ]
        speaker_map = {'A': 'cam1.mp4', 'B': 'cam2.mp4'}
        result = generate_switch_list(diarization, speaker_map, min_segment=2.0)
        assert result[1]['warning'] is not None
        assert '1.5' in result[1]['warning']

    def test_single_speaker_no_switch(self):
        from multicam_switch import generate_switch_list
        diarization = [{'start': 0.0, 'end': 30.0, 'speaker': 'A'}]
        speaker_map = {'A': 'cam1.mp4'}
        result = generate_switch_list(diarization, speaker_map)
        assert len(result) == 1
        assert result[0]['warning'] is None


class TestFormatSwitchList:
    def test_display_format(self):
        from multicam_switch import format_switch_list_display
        switches = [
            {'start': 0.0, 'end': 15.0, 'speaker': 'SPEAKER_00', 'camera': 'cam1.mp4', 'warning': None},
            {'start': 15.0, 'end': 30.0, 'speaker': 'SPEAKER_01', 'camera': 'cam2.mp4', 'warning': '很短(1.5s)'},
        ]
        text = format_switch_list_display(switches)
        assert 'cam1.mp4' in text
        assert 'cam2.mp4' in text
        assert '00:00' in text
        assert '很短' in text
