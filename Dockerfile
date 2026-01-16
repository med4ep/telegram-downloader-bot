FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m pip install --no-cache-dir -U yt-dlp

COPY . .

CMD ["python", "server.py"]
