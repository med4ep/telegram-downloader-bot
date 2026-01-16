import os
import re
import asyncio
from yt_dlp import YoutubeDL
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

URL_REGEX = r"(https?://\S+)"
MAX_MB = 48  # إذا كان الفيديو كبير نرسله كملف Document

YOUTUBE_COOKIES_FILE = "youtube_cookies.txt"
TIKTOK_COOKIES_FILE = "tiktok_cookies.txt"


def write_env_to_file(env_name: str, file_path: str) -> bool:
    """يحفظ قيمة Secret داخل ملف cookies.txt داخل السيرفر"""
    value = os.getenv(env_name)
    if not value:
        return False
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(value)
    return True


def detect_platform(url: str) -> str:
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "tiktok.com" in u:
        return "tiktok"
    if "instagram.com" in u:
        return "instagram"
    if "facebook.com" in u or "fb.watch" in u:
        return "facebook"
    if "twitter.com" in u or "x.com" in u:
        return "x"
    return "other"


def pretty_error(platform: str, err: str) -> str:
    e = (err or "").lower()

    if "sign in to confirm" in e and platform == "youtube":
        return (
            "❌ فشل التحميل من YouTube\n\n"
            "يوتيوب طلب تحقق (Sign in) بسبب الحماية.\n\n"
            "✅ الحل:\n"
            "• تأكد أن Secret (YOUTUBE_COOKIES) يحتوي cookies صحيحة من حسابك.\n"
            "• جرّب فيديو آخر."
        )

    if "unable to extract webpage video data" in e and platform == "tiktok":
        return (
            "❌ فشل التحميل من TikTok\n\n"
            "تيك توك منع التحميل بسبب الحماية.\n\n"
            "✅ الحل:\n"
            "• تأكد أن Secret (TIKTOK_COOKIES) يحتوي cookies صحيحة.\n"
            "• جرّب رابط آخر."
        )

    if "ffmpeg" in e and ("not installed" in e or "not found" in e):
        return (
            "❌ فشل التحميل\n\n"
            "السيرفر يحتاج FFmpeg لدمج الصوت مع الفيديو.\n"
            "✅ تأكد أنك تستخدم Dockerfile فيه تثبيت ffmpeg."
        )

    return (
        "❌ فشل التحميل\n\n"
        "قد يكون الرابط غير مدعوم أو الموقع يحتاج تسجيل دخول.\n"
        "🔁 جرّب رابط آخر أو حاول لاحقًا."
    )


def download_media(url: str) -> str:
    platform = detect_platform(url)

    # كتابة الكوكيز في ملفات داخل السيرفر (إذا موجودة)
    has_yt = write_env_to_file("YOUTUBE_COOKIES", YOUTUBE_COOKIES_FILE)
    has_tt = write_env_to_file("TIKTOK_COOKIES", TIKTOK_COOKIES_FILE)

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

    # تعيين cookies حسب المنصة
    if platform == "youtube" and has_yt:
        common_opts["cookiefile"] = YOUTUBE_COOKIES_FILE
    elif platform == "tiktok" and has_tt:
        common_opts["cookiefile"] = TIKTOK_COOKIES_FILE

    # خطط التحميل
    plan_best_merge = {**common_opts, "format": "bestvideo+bestaudio/best", "merge_output_format": "mp4"}
    plan_best_single = {**common_opts, "format": "best"}
    plan_worst = {**common_opts, "format": "worst"}

    # ✅ TikTok نبدأ بـ best single أولًا (أفضل حل)
    if platform == "tiktok":
        plans = [plan_best_single, plan_best_merge, plan_worst]
    else:
        plans = [plan_best_merge, plan_best_single, plan_worst]

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

    raise RuntimeError(str(last_error))


def cleanup(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً بك!\n\n"
        "📥 أرسل رابط من:\n"
        "TikTok • YouTube • Instagram • X • Facebook\n\n"
        "وسأحمله لك ✅"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛠️ المساعدة:\n\n"
        "✅ فقط أرسل الرابط.\n\n"
        "🔐 إذا YouTube أو TikTok رفض التحميل:\n"
        "تأكد أن Secrets موجودة:\n"
        "YOUTUBE_COOKIES + TIKTOK_COOKIES"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    match = re.search(URL_REGEX, text)

    if not match:
        await update.message.reply_text("❌ أرسل رابط صحيح.")
        return

    url = match.group(1)
    platform = detect_platform(url)

    status = await update.message.reply_text("⏳ جاري التحميل...")

    file_path = None
    try:
        file_path = await asyncio.to_thread(download_media, url)

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        await status.edit_text("✅ تم التحميل.. جاري الإرسال...")

        if size_mb > MAX_MB:
            with open(file_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=os.path.basename(file_path),
                    caption="📦 تم الإرسال كملف بسبب الحجم."
                )
        else:
            with open(file_path, "rb") as f:
                await update.message.reply_video(video=f)

        await status.edit_text("✅ تم الإرسال بنجاح 🎉")

    except Exception as e:
        msg = pretty_error(platform, str(e))
        # ✅ بدون Markdown حتى لا تظهر مشكلة parse entities
        await status.edit_text(msg)

    finally:
        if file_path:
            cleanup(file_path)


def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set in environment variables!")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    # ✅ مهم جدًا لأن البوت يعمل داخل Thread في Koyeb
    app.run_polling(close_loop=False, stop_signals=None)


if __name__ == "__main__":
    main()
