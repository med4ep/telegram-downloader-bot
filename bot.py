import os
import re
import asyncio
from yt_dlp import YoutubeDL
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

URL_REGEX = r"(https?://\S+)"
MAX_MB = 48  # حد إرسال الفيديو في كثير من البوتات

# ملفات الكوكيز داخل الكونتينر
YOUTUBE_COOKIES_FILE = "youtube_cookies.txt"
TIKTOK_COOKIES_FILE = "tiktok_cookies.txt"


def _write_file_if_env_exists(env_name: str, filepath: str) -> bool:
    """
    يكتب محتوى متغير البيئة في ملف داخل السيرفر.
    يرجع True إذا تم الكتابة.
    """
    val = os.getenv(env_name)
    if not val:
        return False
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(val)
    return True


def _detect_platform(url: str) -> str:
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


def _pretty_error(platform: str, err: str) -> str:
    """
    تحويل أخطاء yt-dlp لرسالة جميلة للمستخدم
    """
    e = (err or "").lower()

    if "sign in to confirm you’re not a bot" in e or "sign in to confirm you're not a bot" in e:
        return (
            "❌ **فشل التحميل من YouTube**\n\n"
            "🔒 يوتيوب طلب تحقق (Sign in) بسبب الحماية ضد البوتات.\n\n"
            "✅ الحل:\n"
            "• فعّل **YOUTUBE_COOKIES** في الاستضافة (Koyeb/Render)\n"
            "• أو جرّب رابط آخر / فيديو مختلف.\n"
        )

    if "unable to extract webpage video data" in e and platform == "tiktok":
        return (
            "❌ **فشل التحميل من TikTok**\n\n"
            "🛡️ تيك توك منع التحميل بسبب الحماية.\n\n"
            "✅ الحل:\n"
            "• فعّل **TIKTOK_COOKIES** في الاستضافة\n"
            "• أو جرّب رابط آخر.\n"
        )

    if "ffmpeg" in e and ("not installed" in e or "not found" in e):
        return (
            "❌ **فشل التحميل**\n\n"
            "🔧 السيرفر يحتاج FFmpeg لدمج الصوت مع الفيديو.\n"
            "✅ تأكد أنك تستخدم Dockerfile فيه تثبيت FFmpeg.\n"
        )

    return (
        "❌ **فشل التحميل**\n\n"
        "قد يكون الرابط غير مدعوم أو الموقع يحتاج تسجيل دخول.\n"
        "🔧 حاول لاحقًا أو جرّب رابط ثاني.\n"
    )


def download_media(url: str) -> str:
    """
    تحميل من الرابط مع دعم كوكيز لكل منصة.
    يرجع مسار الملف النهائي.
    """
    platform = _detect_platform(url)

    # تجهيز كوكيز لكل منصة (إذا موجودة)
    has_yt_cookies = _write_file_if_env_exists("YOUTUBE_COOKIES", YOUTUBE_COOKIES_FILE)
    has_tt_cookies = _write_file_if_env_exists("TIKTOK_COOKIES", TIKTOK_COOKIES_FILE)

    # User-Agent بسيط وآمن ضد مشاكل النسخ
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

    # اختيار cookiefile حسب المنصة
    if platform == "youtube" and has_yt_cookies:
        common_opts["cookiefile"] = YOUTUBE_COOKIES_FILE
    elif platform == "tiktok" and has_tt_cookies:
        common_opts["cookiefile"] = TIKTOK_COOKIES_FILE

    # خطة 1: أفضل جودة (دمج صوت+فيديو)
    plan1 = {**common_opts, "format": "bestvideo+bestaudio/best", "merge_output_format": "mp4"}

    # خطة 2: ملف واحد جاهز (مفيد لتجنب مشاكل TikTok أحيانًا)
    plan2 = {**common_opts, "format": "best"}

    # خطة 3: أسوأ جودة كحل أخير
    plan3 = {**common_opts, "format": "worst"}

    plans = [plan1, plan2, plan3]
    last_error = None

    for opts in plans:
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)

                # إذا أنتج mp4 بعد الدمج
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


def _cleanup_file(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **أهلاً بك!**\n\n"
        "📥 أرسل رابط فيديو من:\n"
        "TikTok • YouTube • Instagram • X • Facebook\n\n"
        "✅ وسأقوم بتحميله لك مباشرة.\n"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛠️ **المساعدة**\n\n"
        "✅ فقط أرسل الرابط.\n\n"
        "🔐 إذا واجهت YouTube أو TikTok حماية:\n"
        "• فعّل **YOUTUBE_COOKIES** و **TIKTOK_COOKIES** في الاستضافة.\n"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    match = re.search(URL_REGEX, text)

    if not match:
        await update.message.reply_text("❌ أرسل رابط صحيح.")
        return

    url = match.group(1)
    platform = _detect_platform(url)

    status = await update.message.reply_text("⏳ **جاري التحميل...**")

    file_path = None
    try:
        file_path = await asyncio.to_thread(download_media, url)

        size_mb = os.path.getsize(file_path) / (1024 * 1024)

        await status.edit_text("✅ **تم التحميل، جاري الإرسال...**")

        # إذا كبير، نرسله كملف Document
        if size_mb > MAX_MB:
            with open(file_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=os.path.basename(file_path),
                    caption="📦 تم الإرسال كملف بسبب الحجم الكبير."
                )
        else:
            with open(file_path, "rb") as f:
                await update.message.reply_video(video=f)

        await status.edit_text("✅ **تم الإرسال بنجاح!** 🎉")

    except Exception as e:
        msg = _pretty_error(platform, str(e))
        await status.edit_text(msg, parse_mode="Markdown")

    finally:
        if file_path:
            _cleanup_file(file_path)


def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set in environment variables!")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
