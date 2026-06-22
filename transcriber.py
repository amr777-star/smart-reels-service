import logging
from dataclasses import dataclass
from faster_whisper import WhisperModel

import config

log = logging.getLogger("transcriber")

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        log.info(f"Loading Whisper model: {config.WHISPER_MODEL} on {config.WHISPER_DEVICE}")
        _model = WhisperModel(config.WHISPER_MODEL, device=config.WHISPER_DEVICE, compute_type="int8")
    return _model


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class Segment:
    text: str
    start: float
    end: float
    words: list[Word]


def transcribe(audio_path: str) -> list[Segment]:
    model = _get_model()
    segments_iter, info = model.transcribe(
        audio_path,
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
    )
    log.info(f"Detected language: {info.language} (prob {info.language_probability:.2f})")

    segments = []
    for seg in segments_iter:
        words = [Word(text=w.word.strip(), start=w.start, end=w.end) for w in (seg.words or []) if w.word.strip()]
        segments.append(Segment(text=seg.text.strip(), start=seg.start, end=seg.end, words=words))

    log.info(f"Transcribed {len(segments)} segments, {sum(len(s.words) for s in segments)} words")
    return segments
