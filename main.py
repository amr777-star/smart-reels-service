import asyncio
import uuid
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
import db
import pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.GEMINI_API_KEY:
        log.warning("GEMINI_API_KEY not set — AI features disabled")
    if not config.PEXELS_API_KEY:
        log.warning("PEXELS_API_KEY not set — B-roll disabled")
    yield


app = FastAPI(title="Smart Reels Service", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.mount("/clips", StaticFiles(directory=str(config.WORKSPACE)), name="clips")


def _check_auth(api_key: str | None):
    if config.API_KEY and api_key != config.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


class ClipRequest(BaseModel):
    url: str
    max_clips: int = 5
    video_mode: str = "general"
    enable_broll: bool = True
    enable_bgm: bool = True
    enable_hook: bool = True
    watermark: str = ""
    webhook_url: str | None = None


class ClipResponse(BaseModel):
    job_id: str
    status: str


@app.post("/api/clips", response_model=ClipResponse)
async def create_clip(req: ClipRequest, bg: BackgroundTasks, x_api_key: str | None = Header(None)):
    _check_auth(x_api_key)
    if req.video_mode not in ("general", "podcast", "stream"):
        raise HTTPException(400, "video_mode must be general, podcast, or stream")

    job_id = uuid.uuid4().hex[:12]
    db.save_job(job_id, req.url, req.video_mode, req.max_clips, req.webhook_url)
    log.info(f"Created job {job_id} for {req.url}")

    async def run():
        await pipeline.process_video(
            url=req.url,
            job_id=job_id,
            max_clips=req.max_clips,
            video_mode=req.video_mode,
            enable_broll=req.enable_broll,
            enable_bgm=req.enable_bgm,
            enable_hook=req.enable_hook,
            watermark=req.watermark,
        )
        if req.webhook_url:
            job = db.get_job(job_id)
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(req.webhook_url, json=job)
            except Exception as e:
                log.error(f"Webhook failed: {e}")

    bg.add_task(run)
    return ClipResponse(job_id=job_id, status="queued")


@app.get("/api/clips/{job_id}")
async def get_clip(job_id: str, x_api_key: str | None = Header(None)):
    _check_auth(x_api_key)
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@app.get("/api/clips")
async def list_clips(limit: int = 50, offset: int = 0, x_api_key: str | None = Header(None)):
    _check_auth(x_api_key)
    return db.list_jobs(limit, offset)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "provider": "self-hosted",
        "features": {
            "ai_highlights": bool(config.GEMINI_API_KEY),
            "broll": bool(config.PEXELS_API_KEY),
            "bgm": bool(list(config.MUSIC_DIR.glob("**/*.mp3")) + list(config.MUSIC_DIR.glob("**/*.wav"))),
        },
    }
