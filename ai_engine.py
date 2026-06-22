import json
import logging
import google.generativeai as genai

import config

log = logging.getLogger("ai_engine")

_configured = False


def _ensure_configured():
    global _configured
    if not _configured:
        genai.configure(api_key=config.GEMINI_API_KEY)
        _configured = True


def _call_gemini(prompt: str) -> str:
    _ensure_configured()
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    return response.text


def detect_highlights(transcript_text: str, duration_seconds: float, max_clips: int = 5) -> list[dict]:
    prompt = f"""You are a viral video editor. Analyze this transcript and find the {max_clips} most engaging moments for short vertical clips (30-90 seconds each).

For each moment, identify:
- Hooks (questions, shocking facts, bold statements)
- Emotional peaks (laughter, surprise, conflict, revelation)
- Quotable lines and key insights
- Complete thoughts (don't cut mid-sentence)

Video duration: {duration_seconds:.0f} seconds.

Transcript:
{transcript_text[:15000]}

Return ONLY a JSON array (no markdown, no explanation):
[
  {{
    "start": 45.0,
    "end": 105.0,
    "title": "Brief descriptive title",
    "score": 85,
    "hook_reason": "Why this moment is engaging"
  }}
]

Rules:
- Clips must be 30-90 seconds
- Score 0-100 (higher = more viral potential)
- No overlapping clips
- Order by score descending
- Ensure clips start/end at natural speech boundaries"""

    raw = _call_gemini(prompt)
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        highlights = json.loads(cleaned)
        highlights.sort(key=lambda h: h.get("score", 0), reverse=True)
        log.info(f"Detected {len(highlights)} highlights")
        return highlights[:max_clips]
    except (json.JSONDecodeError, KeyError) as e:
        log.error(f"Failed to parse highlights: {e}\nRaw: {raw[:500]}")
        return []


def generate_hook(clip_transcript: str) -> str:
    prompt = f"""Generate ONE short hook headline (max 8 words) for a TikTok/Reels clip. The hook appears in the first 2 seconds to grab attention.

Clip transcript: {clip_transcript[:2000]}

Rules:
- Max 8 words, punchy and bold
- Use patterns: question, shocking stat, controversy, curiosity gap, bold claim
- No quotes, no hashtags, no emojis
- Return ONLY the hook text, nothing else

Examples of good hooks:
- "Nobody talks about this"
- "This changed everything"
- "Wait for it..."
- "The truth about productivity"
- "You're doing it wrong" """

    hook = _call_gemini(prompt).strip().strip('"').strip("'")
    log.info(f"Generated hook: {hook}")
    return hook[:60]


def extract_broll_keywords(clip_transcript: str) -> list[dict]:
    prompt = f"""Extract 2-3 moments from this clip where B-roll stock footage would enhance the video. For each moment, provide a stock video search query.

Transcript: {clip_transcript[:2000]}

Return ONLY a JSON array (no markdown):
[
  {{
    "timestamp_hint": "around 15 seconds in",
    "search_query": "office meeting team discussion",
    "duration": 3
  }}
]

Rules:
- Search queries must be concrete and visual (not abstract concepts)
- Max 3 B-roll moments per clip
- Each B-roll lasts 2-4 seconds
- Pick moments where the speaker mentions something visual"""

    raw = _call_gemini(prompt)
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(cleaned)[:3]
    except (json.JSONDecodeError, KeyError):
        log.warning("Failed to parse B-roll keywords")
        return []


def pick_music_mood(clip_transcript: str) -> str:
    prompt = f"""Based on this clip transcript, pick the best background music mood. Return ONLY one word from this list: energetic, calm, dramatic, inspiring, playful, dark

Transcript: {clip_transcript[:1000]}"""

    mood = _call_gemini(prompt).strip().lower().split()[0]
    valid = {"energetic", "calm", "dramatic", "inspiring", "playful", "dark"}
    return mood if mood in valid else "calm"
