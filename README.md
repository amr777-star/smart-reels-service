# Smart Reels Service

Self-hosted AI microservice that converts long videos into short vertical clips (9:16) optimized for TikTok, Reels, and YouTube Shorts.

## Features

- **AI highlight detection** — Gemini Flash identifies the most engaging moments
- **Vertical crop** — OpenCV face tracking + smart 9:16 crop
- **Karaoke subtitles** — Word-by-word highlighting (ASS format)
- **Hook headlines** — AI-generated attention-grabbing text overlay
- **B-roll insertion** — Pexels stock footage auto-inserted at key moments
- **Background music** — Auto-matched by mood with sidechain ducking
- **Multi-platform download** — YouTube, Rutube, VK, direct .mp4 via yt-dlp
- **Watermark** — Optional text branding overlay

## Quick Start

### Docker (recommended)

```bash
cp .env.example .env
# Edit .env — add GEMINI_API_KEY and PEXELS_API_KEY

# Add BGM tracks to music/ folders (calm, energetic, dramatic, inspiring, playful, dark)

docker compose up -d
```

### Manual

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Requires: ffmpeg, yt-dlp installed system-wide
uvicorn main:app --host 0.0.0.0 --port 8100
```

## API

### Create clips

```bash
curl -X POST http://localhost:8100/api/clips \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://youtube.com/watch?v=VIDEO_ID",
    "max_clips": 3,
    "video_mode": "general",
    "enable_broll": true,
    "enable_bgm": true,
    "enable_hook": true,
    "watermark": "@mychannel"
  }'
```

**Response:**
```json
{"job_id": "abc123def456", "status": "queued"}
```

### Check status

```bash
curl http://localhost:8100/api/clips/abc123def456
```

**Response (completed):**
```json
{
  "id": "abc123def456",
  "status": "completed",
  "clip_urls": ["workspace/abc123def456/clips/clip_00.mp4", "..."],
  "source_url": "https://youtube.com/watch?v=...",
  "created_at": "2026-06-22T20:00:00Z"
}
```

### List all jobs

```bash
curl http://localhost:8100/api/clips?limit=10
```

### Health check

```bash
curl http://localhost:8100/api/health
```

### Download clips

Clips are served as static files at `/clips/{job_id}/clips/clip_00.mp4`.

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | string | required | Video URL (YouTube, Rutube, VK, or direct .mp4) |
| `max_clips` | int | 5 | Maximum number of clips to generate |
| `video_mode` | string | "general" | Content type: `general`, `podcast`, `stream` |
| `enable_broll` | bool | true | Insert stock B-roll footage |
| `enable_bgm` | bool | true | Add background music with ducking |
| `enable_hook` | bool | true | Add hook headline overlay |
| `watermark` | string | "" | Watermark text (empty = no watermark) |
| `webhook_url` | string | null | URL to POST results when job completes |

## Pipeline

```
URL → yt-dlp download
    → faster-whisper transcription (word-level timestamps)
    → Gemini Flash highlight detection (scored viral moments)
    → For each highlight:
        → Extract segment (FFmpeg)
        → Face-tracking vertical crop (OpenCV + FFmpeg)
        → Karaoke subtitles (ASS + FFmpeg burn-in)
        → Hook headline overlay (Gemini + FFmpeg drawtext)
        → B-roll insertion (Pexels API + FFmpeg fade overlay)
        → BGM mixing (FFmpeg sidechaincompress ducking)
        → Watermark (FFmpeg drawtext)
    → Final clips array
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google AI Studio API key ([free](https://aistudio.google.com/apikey)) |
| `PEXELS_API_KEY` | No | Pexels API key for B-roll ([free](https://www.pexels.com/api/)) |
| `JAMENDO_CLIENT_ID` | No | Jamendo API for auto BGM ([free](https://devportal.jamendo.com/)) |
| `API_KEY` | No | Auth key for this service (empty = no auth) |
| `WHISPER_MODEL` | No | Whisper model size: `tiny`, `base`, `small`, `medium`, `large-v3` |
| `WHISPER_DEVICE` | No | `cpu` or `cuda` |
| `CORS_ORIGINS` | No | Comma-separated CORS origins |
| `PORT` | No | Server port (default: 8100) |

## Background Music

BGM is fetched **automatically** from [Jamendo API](https://devportal.jamendo.com/) (free, 500K+ tracks) based on the clip's mood. No manual downloads needed — just set `JAMENDO_CLIENT_ID` in `.env`.

You can also place your own tracks in `music/` organized by mood as a local fallback:

```
music/
├── calm/          # relaxed, lo-fi, peaceful
├── energetic/     # driving, upbeat, hype
├── dramatic/      # tension, cinematic
├── inspiring/     # motivational, uplifting
├── playful/       # fun, light, quirky
└── dark/          # suspense, intense
```

Priority: local tracks > Jamendo API. If both are empty, BGM is skipped.

## Cost per Video

| Component | Cost |
|-----------|------|
| Gemini Flash (4 LLM calls) | ~$0.005 |
| Pexels API | Free |
| Whisper (local) | Free |
| **Total** | **~$0.005/video** |

## Integration Examples

### n8n Workflow

```json
{
  "method": "POST",
  "url": "http://your-server:8100/api/clips",
  "body": {
    "url": "{{$json.video_url}}",
    "max_clips": 3,
    "webhook_url": "https://your-n8n.com/webhook/reels-done"
  }
}
```

### Python

```python
import httpx

resp = httpx.post("http://localhost:8100/api/clips", json={
    "url": "https://youtube.com/watch?v=VIDEO_ID",
    "max_clips": 3,
})
job_id = resp.json()["job_id"]

# Poll for results
result = httpx.get(f"http://localhost:8100/api/clips/{job_id}").json()
```

## License

MIT
