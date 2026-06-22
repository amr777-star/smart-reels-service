import logging
import random
from pathlib import Path

import httpx

import config

log = logging.getLogger("music_api")

MOOD_TO_TAGS = {
    "energetic": "energetic+upbeat",
    "calm": "calm+ambient",
    "dramatic": "dramatic+cinematic",
    "inspiring": "inspiring+motivational",
    "playful": "happy+fun",
    "dark": "dark+suspense",
}


async def fetch_bgm(mood: str, output_dir: Path) -> Path | None:
    local = _pick_local(mood)
    if local:
        return local

    if not config.JAMENDO_CLIENT_ID:
        return None

    tags = MOOD_TO_TAGS.get(mood, "ambient")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.jamendo.com/v3.0/tracks/",
                params={
                    "client_id": config.JAMENDO_CLIENT_ID,
                    "format": "json",
                    "limit": 5,
                    "fuzzytags": tags,
                    "include": "musicinfo",
                    "audioformat": "mp32",
                    "order": "popularity_total",
                },
            )
            if resp.status_code != 200:
                log.warning(f"Jamendo API error: {resp.status_code}")
                return None

            results = resp.json().get("results", [])
            if not results:
                log.warning(f"No Jamendo tracks for mood: {mood}")
                return None

            track = random.choice(results)
            audio_url = track.get("audiodownload") or track.get("audio")
            if not audio_url:
                return None

            track_path = output_dir / f"bgm_{mood}.mp3"
            dl_resp = await client.get(audio_url, follow_redirects=True, timeout=30)
            dl_resp.raise_for_status()
            track_path.write_bytes(dl_resp.content)
            log.info(f"Downloaded BGM: {track['name']} by {track['artist_name']} ({mood})")
            return track_path

    except Exception as e:
        log.error(f"Jamendo fetch failed: {e}")
        return None


def _pick_local(mood: str) -> Path | None:
    mood_dir = config.MUSIC_DIR / mood
    if mood_dir.exists():
        tracks = list(mood_dir.glob("*.mp3")) + list(mood_dir.glob("*.wav"))
        if tracks:
            return random.choice(tracks)
    all_tracks = list(config.MUSIC_DIR.glob("**/*.mp3")) + list(config.MUSIC_DIR.glob("**/*.wav"))
    return random.choice(all_tracks) if all_tracks else None
