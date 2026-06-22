import logging
import httpx
from pathlib import Path

import config

log = logging.getLogger("broll")


async def search_stock_video(query: str, orientation: str = "portrait") -> str | None:
    if not config.PEXELS_API_KEY:
        return None
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.pexels.com/videos/search",
            params={"query": query, "orientation": orientation, "per_page": 1, "size": "medium"},
            headers={"Authorization": config.PEXELS_API_KEY},
        )
        if resp.status_code != 200:
            log.warning(f"Pexels API error: {resp.status_code}")
            return None
        data = resp.json()
        videos = data.get("videos", [])
        if not videos:
            return None
        files = videos[0].get("video_files", [])
        hd = [f for f in files if f.get("quality") == "hd" and f.get("file_type") == "video/mp4"]
        if not hd:
            hd = [f for f in files if f.get("file_type") == "video/mp4"]
        return hd[0]["link"] if hd else None


async def download_stock_video(url: str, output_path: Path) -> Path:
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        output_path.write_bytes(resp.content)
    log.info(f"Downloaded B-roll: {output_path.name} ({output_path.stat().st_size / 1024:.0f} KB)")
    return output_path
