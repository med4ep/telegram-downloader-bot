import os
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# الحصول على التوكن من متغيرات البيئة
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN غير موجود في متغيرات البيئة!")

# المجلد المؤقت للتحميلات
DOWNLOAD_FOLDER = "/tmp/downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# قائمة المواقع المدعومة
SUPPORTED_SITES = """
🌐 المواقع المدعومة:
• YouTube
• Facebook
• Instagram
• Twitter/X
• TikTok
• Reddit
• Vimeo
• Dailymotion
• SoundCloud
وأكثر من 1000+ موقع آخر!
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    welcome_msg = f"""
مرحباً بك في بوت التحميل! 👋

أرسل لي رابط من أي موقع تواصل اجتماعي وسأقوم بتحميله لك.

{SUPPORTED_SITES}

الأوامر المتاحة:
/start - بدء البوت
/help - المساعدة
/info - معلومات عن البوت
"""
    await update.message.reply_text(welcome_msg)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المساعدة"""
    help_text = """
📖 كيفية الاستخدام:

1️⃣ انسخ رابط الفيديو/الصورة/الموسيقى من أي موقع
2️⃣ أرسل الرابط إلى البوت
3️⃣ انتظر قليلاً حتى يتم التحميل
4️⃣ سيتم إرسال الملف إليك مباشرة!

⚠️ ملاحظات:
• حجم الملف يجب أن يكون أقل من 50 ميجابايت
• بعض الروابط قد تحتاج وقتاً أطول للتحميل
• الملفات الخاصة لا يمكن تحميلها
"""
    await update.message.reply_text(help_text)

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معلومات عن البوت"""
    info_text = """
ℹ️ معلومات البوت:

🤖 بوت التحميل الشامل
📦 يدعم أكثر من 1000+ موقع
⚡ سريع وسهل الاستخدام
🔒 آمن وموثوق
☁️ يعمل على Koyeb

تم التطوير باستخدام:
• Python
• python-telegram-bot
• yt-dlp
"""
    await update.message.reply_text(info_text)

async def download_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحميل المحتوى من الرابط"""
    url = update.message.text.strip()
    
    # التحقق من أن الرسالة تحتوي على رابط
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ من فضلك أرسل رابطاً صحيحاً يبدأ بـ http:// أو https://")
        return
    
    # إرسال رسالة انتظار
    status_msg = await update.message.reply_text("⏳ جاري التحميل... يرجى الانتظار")
    
    filename = None
    try:
        # إعدادات yt-dlp
        ydl_opts = {
            'format': 'best[filesize<50M]/best',
            'outtmpl': f'{DOWNLOAD_FOLDER}/%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'nocheckcertificate': True,
            'geo_bypass': True,
        }
        
        # تحميل الفيديو/الملف
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Downloading from: {url}")
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # التحقق من وجود الملف
            if not os.path.exists(filename):
                await status_msg.edit_text("❌ فشل التحميل. جرب رابطاً آخر.")
                return
            
            file_size = os.path.getsize(filename) / (1024 * 1024)
            logger.info(f"File size: {file_size:.2f} MB")
            
            # التحقق من حجم الملف
            if file_size > 50:
                await status_msg.edit_text("❌ الملف كبير جداً (أكثر من 50 ميجابايت). جرب رابطاً آخر.")
                if os.path.exists(filename):
                    os.remove(filename)
                return
            
            await status_msg.edit_text("📤 جاري رفع الملف...")
            
            # إرسال الملف
            with open(filename, 'rb') as file:
                title = info.get('title', 'غير متوفر')
                if len(title) > 100:
                    title = title[:97] + "..."
                caption = f"✅ تم التحميل بنجاح!\n\n📝 العنوان: {title}"
                
                # تحديد نوع الملف
                ext = filename.split('.')[-1].lower()
                
                try:
                    if ext in ['mp4', 'mkv', 'avi', 'mov', 'webm']:
                        await update.message.reply_video(
                            video=file,
                            caption=caption,
                            supports_streaming=True,
                            read_timeout=60,
                            write_timeout=60
                        )
                    elif ext in ['mp3', 'm4a', 'wav', 'ogg']:
                        await update.message.reply_audio(
                            audio=file,
                            caption=caption,
                            read_timeout=60,
                            write_timeout=60
                        )
                    elif ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                        await update.message.reply_photo(
                            photo=file,
                            caption=caption,
                            read_timeout=60,
                            write_timeout=60
                        )
                    else:
                        await update.message.reply_document(
                            document=file,
                            caption=caption,
                            read_timeout=60,
                            write_timeout=60
                        )
                except Exception as send_error:
                    logger.error(f"Error sending file: {send_error}")
                    await status_msg.edit_text("❌ فشل إرسال الملف. قد يكون الملف كبيراً جداً أو تالفاً.")
                    return
            
            # حذف رسالة الحالة والملف المؤقت
            await status_msg.delete()
            logger.info("File sent and deleted successfully")
            
    except yt_dlp.utils.DownloadError as e:
        error_msg = "❌ فشل التحميل. تأكد من:\n• صحة الرابط\n• أن المحتوى ليس خاصاً\n• أن الموقع مدعوم"
        await status_msg.edit_text(error_msg)
        logger.error(f"Download error: {e}")
        
    except Exception as e:
        error_msg = f"❌ حدث خطأ غير متوقع. حاول مرة أخرى."
        await status_msg.edit_text(error_msg)
        logger.error(f"Unexpected error: {e}")
        
    finally:
        # تنظيف الملف المؤقت
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
                logger.info(f"Cleaned up: {filename}")
            except Exception as e:
                logger.error(f"Error cleaning up file: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأخطاء العام"""
    logger.error(f"Exception while handling an update: {context.error}")

def main():
    """تشغيل البوت"""
    try:
        # إنشاء التطبيق
        application = Application.builder().token(BOT_TOKEN).build()
        
        # إضافة معالجات الأوامر
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("info", info_command))
        
        # إضافة معالج الروابط
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_media))
        
        # إضافة معالج الأخطاء
        application.add_error_handler(error_handler)
        
        # بدء البوت
        logger.info("🤖 البوت يعمل الآن على Koyeb...")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == '__main__':
    main()
