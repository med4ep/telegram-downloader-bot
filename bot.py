import os
import re
import asyncio
from yt_dlp import YoutubeDL
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

URL_REGEX = r"(https?://\S+)"
MAX_MB = 48  # تقريبًا حد إرسال الفيديو للبوتات


def _write_youtube_cookies_if_exists():
    cookies = os.getenv("YOUTUBE_COOKIES")
    if not cookies:
        return None
    path = "cookies.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(cookies)
    return path


def download_media(url: str) -> str:
    cookies_path = _write_youtube_cookies_if_exists()

    user_agent = "Mozilla/5.0"

    common_opts = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title).80s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "extractor_retries": 3,
        "fragment_retries": 3,
        "retries": 3,
        "http_headers": {"User-Agent": user_agent},
    }

    if cookies_path:
        common_opts["cookiefile"] = cookies_path

    # خطة 1: أفضل جودة (تحتاج ffmpeg للدمج)
    plan1 = {
        **common_opts,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
    }

    # خطة 2: ملف واحد جاهز (أفضل لتيك توك أحيانًا)
    plan2 = {**common_opts, "format": "best"}

    # خطة 3: أقل جودة لضمان التحميل
    plan3 = {**common_opts, "format": "worst"}

    plans = [plan1, plan2, plan3]
    last_error = None

    for opts in plans:
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)

                base, _ = os.path.splitext(file_path)
                mp4_path = base + ".mp4"
                if os.path.exists(mp4_path):
                    return mp4_path

                if os.path.exists(file_path):
                    return file_path

        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"Download failed. Last error: {last_error}")


def _cleanup_file(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً!\n"
        "أرسل رابط TikTok / YouTube / Instagram / X / Facebook وسأحمله لك ✅\n\n"
        "⚠️ بعض روابط YouTube قد تحتاج Cookies إذا طلب تسجيل دخول."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    match = re.search(URL_REGEX, text)

    if not match:
        await update.message.reply_text("❌ أرسل رابط صحيح.")
        return

    url = match.group(1)
    status = await update.message.reply_text("⏳ جاري التحميل...")

    file_path = None
    try:
        file_path = await asyncio.to_thread(download_media, url)

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        await status.edit_text(f"✅ تم التحميل ({size_mb:.1f}MB) .. جاري الإرسال...")

        if size_mb > MAX_MB:
            with open(file_path, "rb") as f:
                await update.message.reply_document(document=f, filename=os.path.basename(file_path))
        else:
            with open(file_path, "rb") as f:
                await update.message.reply_video(video=f)

        await status.edit_text("✅ تم الإرسال ✅")

    except Exception as e:
        await status.edit_text(f"❌ فشل التحميل.\n🔧 الخطأ: {e}")

    finally:
        if file_path:
            _cleanup_file(file_path)


def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set in environment variables!")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
