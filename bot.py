import os
import re
import asyncio
from yt_dlp import YoutubeDL
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

URL_REGEX = r"(https?://\S+)"

# حد تيليجرام للبوتات (تقريبًا 50MB للـ Bot API في كثير من الحالات)
MAX_MB = 48


def _write_youtube_cookies_if_exists() -> str | None:
    """
    إذا كان متغير البيئة YOUTUBE_COOKIES موجود
    سنكتب ملف cookies.txt ونرجع مساره.
    """
    cookies = os.getenv("YOUTUBE_COOKIES")
    if not cookies:
        return None

    path = "cookies.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(cookies)
    return path


def download_media(url: str) -> str:
    """
    يحاول تحميل الفيديو بأفضل جودة.
    إذا فشل بسبب دمج الصوت/الفيديو أو استخراج تيكتوك.. يجرب خطط بديلة.
    يرجع مسار الملف النهائي.
    """
    cookies_path = _write_youtube_cookies_if_exists()

    common_opts = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title).80s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "extractor_retries": 3,
        "fragment_retries": 3,
        "retries": 3,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "Appl
