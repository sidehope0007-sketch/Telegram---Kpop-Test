import os
import logging
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from bot_logic import dp, bot, setup_bot_commands
from dotenv import load_dotenv

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# Render က အလိုအလျောက် သတ်မှတ်ပေးသော PORT ကို ရယူခြင်း (မရှိပါက 10000)
PORT = int(os.getenv("PORT", 10000))

# Render က အလိုအလျောက် ပေးသော URL (e.g., https://lisa-telegram.onrender.com) ကို ရယူခြင်း
# RENDER_EXTERNAL_URL မရှိပါက ကိုယ်တိုင်ပေးထားသော WEBHOOK_URL ကို အသုံးပြုမည်
BASE_WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", os.getenv("WEBHOOK_URL"))

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}"

async def on_startup(dispatcher, bot):
    """Server စတင်ချိန်တွင် Webhook ကို Telegram သို့ လှမ်းချိတ်မည့် Function"""
    logger.info(f"[Webhook] Initializing Webhook URL: {WEBHOOK_URL}")
    await setup_bot_commands(bot)
    
    # drop_pending_updates=True ထားခြင်းဖြင့် Server ပိတ်ထားချိန်က ဝင်နေသော စာဟောင်းများကို ကျော်သွားမည်
    await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    logger.info("[System] Webhook successfully established.")

async def on_shutdown(dispatcher, bot):
    """Server ပိတ်ချိန်တွင် Webhook ကို ဖြုတ်ချပြီး Session များ ရှင်းလင်းမည့် Function"""
    logger.info("[Webhook] Shutting down and removing webhook...")
    await bot.delete_webhook()
    await bot.session.close()
    
    # AI Service မှ Global Session ကို လုံခြုံစွာ ပိတ်ခြင်း
    from ai_service import session as ai_session
    if ai_session:
        await ai_session.close()
        
    logger.info("[System] Shutdown operations completed flawlessly.")

async def health_check(request):
    """UptimeRobot ကဲ့သို့ Service များအတွက် 200 OK ပြန်ပေးမည့် Endpoint"""
    return web.Response(text="Bot is operational and running via Webhook Architecture!", status=200)

def main():
    if not BASE_WEBHOOK_URL:
        logger.error("[Critical] BASE_WEBHOOK_URL or WEBHOOK_URL is missing. Please set Environment Variables.")
        return

    logger.info("[System] Booting up Webhook Server Architecture...")

    # Event Hooks များကို ချိတ်ဆက်ခြင်း
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # aiohttp Web Application ကို တည်ဆောက်ခြင်း
    app = web.Application()

    # Health Check Route သတ်မှတ်ခြင်း (Root URL)
    app.router.add_get('/', health_check)

    # aiogram ၏ Webhook Handler ကို Web App သို့ ချိတ်ဆက်ခြင်း
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # Web Server စတင် Run ခြင်း
    web.run_app(app, host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("[System] Manual interruption detected. Exiting...")
