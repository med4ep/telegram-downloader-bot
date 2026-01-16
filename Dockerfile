FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ✅ تحديث دائم لأحدث yt-dlp
RUN python -m pip install --no-cache-dir -U yt-dlp

COPY . .

CMD ["python", "bot.py"]
