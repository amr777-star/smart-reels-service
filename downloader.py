import subprocess
import logging
from pathlib import Path

log = logging.getLogger("downloader")


def download_video(url: str, output_dir: Path) -> Path:
    output_path = output_dir / "source.mp4"
    cmd = [
        "yt-dlp",
        "--format", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "--merge-output-format", "mp4",
        "--output", str(output_path),
        "--no-playlist",
        "--geo-bypass",
        "--retries", "3",
        url,
    ]
    log.info(f"Downloading: {url}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"yt-dlp stderr: {result.stderr}")
        raise RuntimeError(f"yt-dlp failed: {result.stderr[-500:]}")
    if not output_path.exists():
        mp4s = list(output_dir.glob("source.*"))
        if mp4s:
            output_path = mp4s[0]
    log.info(f"Downloaded: {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return output_path
