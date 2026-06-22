import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
WORKSPACE = BASE_DIR / "workspace"
MUSIC_DIR = BASE_DIR / "music"
FONTS_DIR = BASE_DIR / "fonts"
DATA_DIR = BASE_DIR / "data"

WORKSPACE.mkdir(exist_ok=True)
MUSIC_DIR.mkdir(exist_ok=True)
FONTS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "google/gemini-2.5-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
JAMENDO_CLIENT_ID = os.getenv("JAMENDO_CLIENT_ID", "")
API_KEY = os.getenv("API_KEY", "")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")

PORT = int(os.getenv("PORT", "8100"))
