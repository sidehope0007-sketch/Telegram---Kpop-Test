# Filename: main.py
import os
import asyncio
import logging
from aiohttp import web
from bot_logic import dp, bot, setup_bot_commands, trigger_morning_broadcast
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

PORT = int(os.getenv("PORT", 10000))

async def health_check(request):
    """Render Uptime Check အတွက်"""
    return web.Response(text="Bot is running via Long Polling Architecture!", status=200)

async def cron_morning_handler(request):
    """UptimeRobot မှ မနက်တိုင်း လှမ်းခေါ်မည့် Endpoint"""
    result = await trigger_morning_broadcast()
    return web.Response(text=f"Cron executed. Status: {result}", status=200)

async def start_web_server():
    """Background တွင် အလုပ်လုပ်မည့် Lightweight Web Server"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/cron-morning', cron_morning_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"[Web Server] Started on port {PORT} for UptimeRobot & Health Checks.")

async def main():
    logger.info("[System] Booting up Hybrid Architecture (Polling + Web Server)...")
    
    # ၁။ Web Server ကို Background Task အဖြစ် စတင်မည်
    server_task = asyncio.create_task(start_web_server())
    
    try:
        await setup_bot_commands(bot)
        # ၂။ Webhook ငြိနေပါက ဖြုတ်ချမည် (Polling အလုပ်လုပ်စေရန် မရှိမဖြစ်လိုအပ်သည်)
        await bot.delete_webhook(drop_pending_updates=True) 
        
        # ၃။ Bot ကို Long Polling ဖြင့် စတင်မည် (Timeout ပြဿနာ လုံးဝ မရှိတော့ပါ)
        logger.info("[Bot] Polling started successfully.")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"[Critical Error] {e}")
    finally:
        await bot.session.close()
        from ai_service import session
        if session:
            await session.close()
        server_task.cancel()
        logger.info("[System] Shutting down.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("[System] Manual interruption detected.")
