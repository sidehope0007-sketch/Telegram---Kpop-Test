# Filename: main.py
import os
import asyncio
import logging
from aiohttp import web
from bot_logic import dp, bot, setup_bot_commands
from ai_service import session as ai_session # Use the global session
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

PORT = int(os.getenv("PORT", 10000))

async def health_check(request):
    return web.Response(text="Bot is running!", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"[Web Server] Started on port {PORT}")

async def main():
    logger.info("[System] Starting...")
    server_task = asyncio.create_task(start_web_server())
    
    try:
        await setup_bot_commands(bot)
        await bot.delete_webhook(drop_pending_updates=True) 
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"[Critical Error] {e}")
    finally:
        await bot.session.close()
        # Close the global AI session to be clean
        from ai_service import session
        if session:
            await session.close()
        server_task.cancel()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("[System] Shutting down.")
