import os
import re
import asyncio
from yt_dlp import YoutubeDL
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

URL_REGEX = r"(https?://\S+)"


def download_video(url: str) -> str:
    ydl_opts = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title).50s.%(ext)s"),
        "format": "best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        # (اختياري) يساعد مع يوتيوب لو Node موجود
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)

        # لو تم الدمج إلى mp4
        if not file_path.endswith(".mp4"):
            base = os.path.splitext(file_path)[0]
            mp4_path = base + ".mp4"
            if os.path.exists(mp4_path):
                return mp4_path

        return file_path


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً! أرسل رابط فيديو من TikTok / YouTube / Instagram / X / Facebook وسأحمله لك ✅"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    match = re.search(URL_REGEX, text)

    if not match:
        await update.message.reply_text("❌ أرسل رابط صحيح.")
        return

    url = match.group(1)
    status = await update.message.reply_text("⏳ جاري التحميل...")

    try:
        # تشغيل التحميل في thread حتى لا يعلق البوت
        file_path = await asyncio.to_thread(download_video, url)

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > 48:
            await status.edit_text(
                f"⚠️ الفيديو كبير جدًا ({size_mb:.1f}MB) ولا يمكن إرساله كبوت.\n"
                "جرّب رابط أقصر أو جودة أقل."
            )
            os.remove(file_path)
            return

        await status.edit_text("✅ تم التحميل، جاري الإرسال...")

        with open(file_path, "rb") as f:
            await update.message.reply_video(video=f)

        os.remove(file_path)

    except Exception as e:
        await status.edit_text(
            "❌ فشل التحميل.\n"
            "قد يكون الموقع يحتاج تسجيل دخول/كوكيز أو الرابط غير مدعوم.\n\n"
            f"🔧 الخطأ: {e}"
        )


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
