import os
import threading
import asyncio
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def home():
    return {"status": "ok", "message": "Service is running ✅"}


def run_bot():
    # ✅ إنشاء Event Loop داخل هذا الـ Thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    import bot
    bot.main()


if __name__ == "__main__":
    # تشغيل البوت في Thread
    threading.Thread(target=run_bot, daemon=True).start()

    # فتح PORT اللي يحتاجه Koyeb
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
