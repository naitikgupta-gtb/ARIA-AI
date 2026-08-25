"""
modules/voice_gender.py — lightweight speaker-gender estimation from
raw microphone audio, used to drive the "reply in the opposite gender's
voice" feature.

This is NOT voice conversion/cloning — it doesn't touch or transform
the user's actual voice at all. It only estimates whether the current
speaker sounds male or female (via fundamental-frequency/pitch
estimation) so the engine can pick one of Gemini's own built-in voices
(Aoede = female-leaning, Puck = male-leaning) for ARIA's reply. Real
voice conversion (making YOUR voice sound like someone else's) is a
separate, much heavier ML system (e.g. RVC/so-vits-svc) — not what
this does.

Method: autocorrelation-based pitch detection over a ~1 second rolling
window. Human speech F0 roughly: male ~85-180Hz, female ~165-255Hz.
The 165-180Hz band is genuinely ambiguous for any pitch-only method —
this is a real accuracy limitation, not a bug.
"""
from collections import deque

import numpy as np

SAMPLE_RATE = 16000
WINDOW_SECONDS = 1.0
WINDOW_SAMPLES = int(SAMPLE_RATE * WINDOW_SECONDS)
MIN_RMS = 300  # int16 scale — below this, treat as silence, not a voice
FEMALE_THRESHOLD_HZ = 165.0  # >= this → classified female-leaning
MIN_F0, MAX_F0 = 70.0, 300.0  # plausible human voice range


class GenderTracker:
    """Keeps a rolling audio buffer + a short history of recent
    detections, and only reports a stable flip (not every noisy
    single-window guess) via `stable_gender()`."""

    def __init__(self, history_len: int = 5, required_majority: int = 4):
        self._buffer = deque(maxlen=WINDOW_SAMPLES)
        self._history = deque(maxlen=history_len)
        self._required_majority = required_majority
        self._current_stable = None

    def push_samples(self, pcm_int16: np.ndarray):
        self._buffer.extend(pcm_int16.tolist())

    def _estimate_f0(self) -> float | None:
        if len(self._buffer) < WINDOW_SAMPLES:
            return None
        signal = np.array(self._buffer, dtype=np.float64)
        rms = np.sqrt(np.mean(signal ** 2))
        if rms < MIN_RMS:
            return None  # silence / too quiet to judge

        signal = signal - signal.mean()
        corr = np.correlate(signal, signal, mode="full")
        corr = corr[len(corr) // 2:]

        min_lag = int(SAMPLE_RATE / MAX_F0)
        max_lag = int(SAMPLE_RATE / MIN_F0)
        if max_lag >= len(corr):
            return None
        segment = corr[min_lag:max_lag]
        if segment.size == 0:
            return None
        peak_lag = min_lag + int(np.argmax(segment))
        if peak_lag == 0:
            return None
        f0 = SAMPLE_RATE / peak_lag
        return f0

    def sample_and_classify(self) -> str | None:
        """Call periodically (e.g. once per second). Returns 'male',
        'female', or None (not enough signal/silence) for THIS window —
        use stable_gender() for the debounced result to actually act on."""
        f0 = self._estimate_f0()
        if f0 is None:
            return None
        gender = "female" if f0 >= FEMALE_THRESHOLD_HZ else "male"
        self._history.append(gender)
        return gender

    def stable_gender(self) -> str | None:
        """Only returns a value when the recent history has a clear
        majority for one gender — avoids flip-flopping the voice on
        every noisy frame. Returns None if not yet confident."""
        if len(self._history) < self._history.maxlen:
            return None
        counts = {"male": 0, "female": 0}
        for g in self._history:
            counts[g] += 1
        for gender, count in counts.items():
            if count >= self._required_majority:
                self._current_stable = gender
                return gender
        return None
