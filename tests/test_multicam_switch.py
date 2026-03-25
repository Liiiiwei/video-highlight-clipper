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
