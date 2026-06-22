import logging
from pathlib import Path
from transcriber import Word

log = logging.getLogger("subtitles")

STYLE_TEMPLATE = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 1
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,{font},88,&H0000FFFF,&H00FFFFFF,&H00000000,&H99000000,-1,0,0,0,100,100,2,0,1,5,3,2,80,80,160,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _chunk_words(words: list[Word], max_words: int = 5, max_duration: float = 3.0) -> list[list[Word]]:
    chunks = []
    current = []
    for w in words:
        current.append(w)
        if len(current) >= max_words or (current and w.end - current[0].start >= max_duration):
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def generate_ass(words: list[Word], output_path: Path, font: str = "Arial Black") -> Path:
    chunks = _chunk_words(words)
    lines = [STYLE_TEMPLATE.format(font=font)]

    for chunk in chunks:
        if not chunk:
            continue
        start = chunk[0].start
        end = chunk[-1].end

        karaoke_parts = []
        for w in chunk:
            duration_cs = max(1, int((w.end - w.start) * 100))
            karaoke_parts.append(f"{{\\kf{duration_cs}}}{w.text} ")

        text = "{\\fad(80,80)}" + "".join(karaoke_parts).rstrip()
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Karaoke,,0,0,0,,{text}")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Generated ASS subtitles: {len(chunks)} lines -> {output_path.name}")
    return output_path
