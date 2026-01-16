FROM python:3.11-slim

# تثبيت المكتبات الأساسية
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# إنشاء مجلد التطبيق
WORKDIR /app

# نسخ ملفات المتطلبات
COPY requirements.txt .

# تثبيت المكتبات
RUN pip install --no-cache-dir -r requirements.txt

# نسخ الكود
COPY bot.py .

# تشغيل البوت
CMD ["python", "bot.py"]
