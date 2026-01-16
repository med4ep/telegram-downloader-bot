import os
import threading
from fastapi import FastAPI
import uvicorn

# استدعاء البوت
def run_bot():
    import bot
    bot.main()

app = FastAPI()

@app.get("/")
def home():
    return {"status": "ok", "message": "Bot is running"}

if __name__ == "__main__":
    # تشغيل البوت في Thread
    threading.Thread(target=run_bot, daemon=True).start()

    # فتح البورت المطلوب من Koyeb
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
