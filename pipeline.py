import asyncio
import logging
import shutil
import uuid
from pathlib import Path

import config
import downloader
import transcriber
import ai_engine
import video_processor
import subtitles
import broll as broll_service
import music_api
import db

log = logging.getLogger("pipeline")


async def process_video(
    url: str,
    job_id: str,
    max_clips: int = 5,
    video_mode: str = "general",
    enable_broll: bool = True,
    enable_bgm: bool = True,
    enable_hook: bool = True,
    watermark: str = "",
):
    work_dir = config.WORKSPACE / job_id
    work_dir.mkdir(parents=True, exist_ok=True)
    clips_dir = work_dir / "clips"
    clips_dir.mkdir(exist_ok=True)

    try:
        db.update_job(job_id, "downloading")

        source = downloader.download_video(url, work_dir)
        duration = video_processor.get_duration(source)
        log.info(f"Source video: {duration:.0f}s")

        db.update_job(job_id, "transcribing")

        segments = transcriber.transcribe(str(source))
        all_words = [w for seg in segments for w in seg.words]
        full_text = " ".join(seg.text for seg in segments)

        db.update_job(job_id, "detecting_highlights")

        mode_hint = f" Content type: {video_mode}." if video_mode != "general" else ""
        highlights = ai_engine.detect_highlights(full_text + mode_hint, duration, max_clips)

        if not highlights:
            db.update_job(job_id, "failed", error="No highlights detected")
            return

        db.update_job(job_id, "processing")
        clip_paths = []

        for idx, hl in enumerate(highlights):
            clip_id = f"clip_{idx:02d}"
            clip_dir = work_dir / clip_id
            clip_dir.mkdir(exist_ok=True)
            log.info(f"Processing {clip_id}: {hl['start']:.1f}s - {hl['end']:.1f}s ({hl.get('title', '')})")

            try:
                segment_path = clip_dir / "segment.mp4"
                video_processor.extract_segment(source, hl["start"], hl["end"], segment_path)

                vertical_path = clip_dir / "vertical.mp4"
                video_processor.crop_vertical(segment_path, vertical_path)

                clip_words = [
                    transcriber.Word(text=w.text, start=w.start - hl["start"], end=w.end - hl["start"])
                    for w in all_words
                    if hl["start"] <= w.start < hl["end"]
                ]

                current_video = vertical_path

                if clip_words:
                    ass_path = clip_dir / "captions.ass"
                    subtitles.generate_ass(clip_words, ass_path)
                    sub_path = clip_dir / "with_subs.mp4"
                    current_video = video_processor.burn_subtitles(current_video, ass_path, sub_path)

                if enable_hook and config.LLM_API_KEY:
                    clip_text = " ".join(w.text for w in clip_words)
                    hook = ai_engine.generate_hook(clip_text)
                    if hook:
                        hook_path = clip_dir / "with_hook.mp4"
                        current_video = video_processor.add_hook_overlay(current_video, hook, hook_path)

                if enable_broll and config.PEXELS_API_KEY and config.LLM_API_KEY:
                    clip_text = " ".join(w.text for w in clip_words)
                    broll_hints = ai_engine.extract_broll_keywords(clip_text)
                    clip_duration = hl["end"] - hl["start"]
                    for bi, hint in enumerate(broll_hints[:1]):
                        stock_url = await broll_service.search_stock_video(hint["search_query"])
                        if stock_url:
                            broll_file = clip_dir / f"broll_{bi}.mp4"
                            await broll_service.download_stock_video(stock_url, broll_file)
                            at_sec = min(clip_duration * 0.3, clip_duration - 4)
                            broll_out = clip_dir / f"with_broll_{bi}.mp4"
                            current_video = video_processor.insert_broll(
                                current_video, broll_file, max(1, at_sec), min(3, hint.get("duration", 3)), broll_out
                            )

                if enable_bgm:
                    clip_text = " ".join(w.text for w in clip_words)
                    mood = ai_engine.pick_music_mood(clip_text) if config.LLM_API_KEY else "calm"
                    bgm_track = await music_api.fetch_bgm(mood, clip_dir)
                    if bgm_track:
                        bgm_path = clip_dir / "with_bgm.mp4"
                        current_video = video_processor.mix_bgm(current_video, bgm_track, bgm_path)

                if watermark:
                    wm_path = clip_dir / "with_watermark.mp4"
                    current_video = video_processor.add_watermark(current_video, watermark, wm_path)

                final_path = clips_dir / f"{clip_id}.mp4"
                shutil.copy2(current_video, final_path)
                clip_paths.append(str(final_path))
                log.info(f"Completed {clip_id}")

            except Exception as e:
                log.error(f"Failed processing {clip_id}: {e}")
                continue

        if clip_paths:
            db.update_job(job_id, "completed", clip_urls=clip_paths)
            log.info(f"Job {job_id} completed: {len(clip_paths)} clips")
        else:
            db.update_job(job_id, "failed", error="All clips failed to process")

    except Exception as e:
        log.error(f"Pipeline failed for {job_id}: {e}")
        db.update_job(job_id, "failed", error=str(e))
