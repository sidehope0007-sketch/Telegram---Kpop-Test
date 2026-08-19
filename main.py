# Filename: main.py
import os
import logging
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from bot_logic import dp, bot, setup_bot_commands, trigger_morning_broadcast
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

PORT = int(os.getenv("PORT", 10000))
BASE_WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", os.getenv("WEBHOOK_URL"))
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}"

async def on_startup(dispatcher, bot):
    logger.info(f"[Webhook] Initializing Webhook URL: {WEBHOOK_URL}")
    await setup_bot_commands(bot)
    await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    logger.info("[System] Webhook successfully established.")

async def on_shutdown(dispatcher, bot):
    logger.info("[Webhook] Shutting down... (Keeping webhook active for new instance)")
    await bot.session.close()
    from ai_service import session as ai_session
    if ai_session:
        await ai_session.close()
    logger.info("[System] Shutdown operations completed flawlessly.")
    
async def health_check(request):
    """UptimeRobot ကဲ့သို့ Service များအတွက် 200 OK ပြန်ပေးမည့် Endpoint"""
    return web.Response(text="Bot is operational and running via Webhook Architecture!", status=200)

async def cron_morning_handler(request):
    """UptimeRobot မှ မနက်တိုင်း လှမ်းခေါ်မည့် လျှို့ဝှက် Endpoint"""
    result = await trigger_morning_broadcast()
    return web.Response(text=f"Cron executed. Status: {result}", status=200)

def main():
    if not BASE_WEBHOOK_URL:
        logger.error("[Critical] BASE_WEBHOOK_URL or WEBHOOK_URL is missing.")
        return

    logger.info("[System] Booting up Webhook Server Architecture...")
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    
    # 🔗 API Routes များ
    app.router.add_get('/', health_check)
    app.router.add_get('/cron-morning', cron_morning_handler)

    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    web.run_app(app, host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("[System] Manual interruption detected. Exiting...")
