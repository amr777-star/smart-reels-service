import subprocess
import logging
from pathlib import Path

log = logging.getLogger("downloader")


def download_video(url: str, output_dir: Path) -> Path:
    output_path = output_dir / "source.mp4"
    cmd = [
        "yt-dlp",
        "--format", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--output", str(output_path),
        "--no-playlist",
        "--quiet",
        url,
    ]
    log.info(f"Downloading: {url}")
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    if not output_path.exists():
        mp4s = list(output_dir.glob("source.*"))
        if mp4s:
            output_path = mp4s[0]
    log.info(f"Downloaded: {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return output_path
