import subprocess
import logging
import json
import random
from pathlib import Path

import cv2
import numpy as np

import config

log = logging.getLogger("video")

TARGET_W, TARGET_H = 1080, 1920


def get_video_info(path: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def get_duration(path: Path) -> float:
    info = get_video_info(path)
    return float(info["format"]["duration"])


def extract_segment(source: Path, start: float, end: float, output: Path) -> Path:
    cmd = [
        "ffmpeg", "-y", "-ss", str(start), "-to", str(end),
        "-i", str(source), "-c", "copy", "-avoid_negative_ts", "make_zero",
        str(output),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output


def detect_face_center(video_path: Path, sample_count: int = 5) -> int | None:
    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames < 1:
        cap.release()
        return None

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    centers = []

    for i in range(sample_count):
        frame_idx = int(total_frames * (i + 1) / (sample_count + 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(60, 60))
        if len(faces) > 0:
            largest = max(faces, key=lambda f: f[2] * f[3])
            centers.append(largest[0] + largest[2] // 2)

    cap.release()

    if not centers:
        return frame_width // 2
    return int(np.median(centers))


def crop_vertical(source: Path, output: Path, face_center_x: int | None = None) -> Path:
    info = get_video_info(source)
    v_stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    src_w, src_h = int(v_stream["width"]), int(v_stream["height"])

    if src_w / src_h <= 9 / 16 + 0.05:
        crop_w, crop_h = src_w, src_h
        x_off, y_off = 0, 0
    else:
        crop_h = src_h
        crop_w = int(crop_h * 9 / 16)
        if crop_w > src_w:
            crop_w = src_w
            crop_h = int(crop_w * 16 / 9)

        if face_center_x is None:
            face_center_x = detect_face_center(source) or src_w // 2

        x_off = max(0, min(face_center_x - crop_w // 2, src_w - crop_w))
        y_off = 0

    cmd = [
        "ffmpeg", "-y", "-i", str(source),
        "-vf", f"crop={crop_w}:{crop_h}:{x_off}:{y_off},scale={TARGET_W}:{TARGET_H}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        str(output),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    log.info(f"Cropped to {TARGET_W}x{TARGET_H}: {output.name}")
    return output


def burn_subtitles(video: Path, ass_file: Path, output: Path) -> Path:
    fonts_dir = str(config.FONTS_DIR)
    cmd = [
        "ffmpeg", "-y", "-i", str(video),
        "-vf", f"ass={str(ass_file)}:fontsdir={fonts_dir}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        str(output),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    log.info(f"Burned subtitles: {output.name}")
    return output


def add_hook_overlay(video: Path, hook_text: str, output: Path) -> Path:
    escaped = hook_text.replace("'", "\\'").replace(":", "\\:")
    drawtext = (
        f"drawtext=text='{escaped}'"
        f":fontsize=64:fontcolor=white"
        f":x=(w-text_w)/2:y=280"
        f":box=1:boxcolor=black@0.75:boxborderw=16"
        f":enable='between(t,0.3,3.5)'"
        f":alpha='if(lt(t,0.8),(t-0.3)/0.5,if(lt(t,3.0),1,(3.5-t)/0.5))'"
    )
    cmd = [
        "ffmpeg", "-y", "-i", str(video),
        "-vf", drawtext,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        str(output),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    log.info(f"Added hook overlay: {output.name}")
    return output


def insert_broll(main_video: Path, broll_path: Path, at_second: float, duration: float, output: Path) -> Path:
    cmd = [
        "ffmpeg", "-y", "-i", str(main_video), "-i", str(broll_path),
        "-filter_complex",
        f"[1:v]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2,"
        f"setpts=PTS-STARTPTS,format=yuva420p,"
        f"fade=t=in:st=0:d=0.3:alpha=1,"
        f"fade=t=out:st={duration - 0.3}:d=0.3:alpha=1[broll];"
        f"[0:v][broll]overlay=0:0:enable='between(t,{at_second},{at_second + duration})'[outv]",
        "-map", "[outv]", "-map", "0:a", "-c:a", "copy",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        str(output),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    log.info(f"Inserted B-roll at {at_second}s: {output.name}")
    return output


def mix_bgm(video: Path, bgm_path: Path, output: Path) -> Path:
    video_duration = get_duration(video)
    cmd = [
        "ffmpeg", "-y", "-i", str(video), "-i", str(bgm_path),
        "-filter_complex",
        f"[1:a]atrim=0:{video_duration},asetpts=PTS-STARTPTS,"
        f"afade=t=in:st=0:d=1.5,afade=t=out:st={max(0, video_duration - 2)}:d=2[bgm_trimmed];"
        f"[0:a]asplit=2[speech][sc];"
        f"[bgm_trimmed][sc]sidechaincompress=threshold=0.02:ratio=6:attack=80:release=1000[bgm_ducked];"
        f"[speech][bgm_ducked]amix=inputs=2:duration=first:weights=1 0.25",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        str(output),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    log.info(f"Mixed BGM with ducking: {output.name}")
    return output


def add_watermark(video: Path, watermark_text: str, output: Path) -> Path:
    escaped = watermark_text.replace("'", "\\'").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y", "-i", str(video),
        "-vf", f"drawtext=text='{escaped}':fontsize=28:fontcolor=white@0.5:x=w-text_w-30:y=h-50",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        str(output),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output


def pick_bgm(mood: str) -> Path | None:
    mood_dir = config.MUSIC_DIR / mood
    if not mood_dir.exists():
        all_tracks = list(config.MUSIC_DIR.glob("**/*.mp3")) + list(config.MUSIC_DIR.glob("**/*.wav"))
        return random.choice(all_tracks) if all_tracks else None
    tracks = list(mood_dir.glob("*.mp3")) + list(mood_dir.glob("*.wav"))
    return random.choice(tracks) if tracks else None
