# Filename: bot_logic.py
import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from aiogram.enums import ChatAction
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

from db_manager import (
    check_usage_allowed, 
    update_usage, 
    get_or_create_user, 
    save_chat, 
    get_chat_history, 
    clear_history, 
    set_user_plan,
    get_all_users,
    update_morning_date,
    get_user_info
)
from ai_service import generate_response, generate_morning_message

load_dotenv()
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# 📌 MUTEX LOCK FOR RACE CONDITION PREVENTION
user_locks = {}

def get_user_lock(user_id: int) -> asyncio.Lock:
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    return user_locks[user_id]

def get_upgrade_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Pro Plan ဝယ်ယူရန်", url="https://t.me/slipme_mm")]
    ])

WELCOME_VIDEO_URL = "https://hvmhuqzbzsebbqymibmo.supabase.co/storage/v1/object/public/Model%20Telegram/LisaTelegram.mp4"

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    await get_or_create_user(user_id)
    welcome_text = "Hello , Lisa ရဲ့ Private Chat Bot လေးက ကြိုဆိုပါတယ်နော်။ Private Chat မို့ အပြင်လောကရဲ့ ပင်ပန်းမှုတွေကို ဒီမှာ အမောဖြေလိုက်နော်"
    try:
        await message.answer_animation(animation=WELCOME_VIDEO_URL, caption=welcome_text)
    except Exception as e:
        logger.error(f"[Start Command Error]: {e}")
        await message.answer(welcome_text)

async def setup_bot_commands(bot: Bot):
    bot_commands = [
        BotCommand(command="/new_chat", description="🔄 New Chat စတင်ရန်"),
        BotCommand(command="/admin", description="👨‍💻 Admin နှင့် ဆက်သွယ်ရန်"),
        BotCommand(command="/status", description="📊 အသုံးပြုမှု စစ်ဆေးရန်")
    ]
    await bot.set_my_commands(bot_commands)

@dp.message(Command("new_chat"))
async def cmd_new_chat(message: types.Message):
    if await clear_history(message.from_user.id):
        await message.answer("✅ မှတ်ဉာဏ်ဟောင်းများကို အောင်မြင်စွာ ဖျက်လင်းလိုက်ပါပြီ။")
    else:
        await message.answer("⚠️ အမှားတစ်ခု ဖြစ်ပွားခဲ့ပါသည်။")

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    await message.answer("👨‍💻 Admin နှင့် ဆက်သွယ်ရန်:\n\n👉 @slipme_mm")

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    user_id = message.from_user.id
    processing_msg = await message.answer("⏳ စစ်ဆေးနေပါသည်...")
    
    user_data = await get_user_info(user_id)
    if not user_data:
        return await processing_msg.edit_text("❌ အချက်အလက် ရှာမတွေ့ပါ သို့မဟုတ် Database Security Error ရှိနေပါသည်။ Admin ကို အကြောင်းကြားပါ။")
        
    plan = user_data.get('plan_type', 'free')
    count = user_data.get('message_count', 0)
    
    status_text = (
        f"📊 **သင်၏ အသုံးပြုမှု အခြေအနေ**\n\n"
        f"👤 User ID: `{user_id}`\n"
        f"💎 Plan: `{plan.upper()}`\n"
        f"💬 အသုံးပြုပြီးသမျှ: `{count}` messages\n"
    )
    await processing_msg.edit_text(status_text, parse_mode="Markdown")

@dp.message(Command("givepro7"))
async def cmd_give_pro_7days(message: types.Message):
    if str(message.from_user.id) != ADMIN_ID: return
    try:
        target = int(message.text.split()[1])
        if await set_user_plan(target, "pro", 7):
            await message.answer(f"✅ User `{target}` ကို ၇ ရက် Pro ပေးပြီးပါပြီ။")
            try: await bot.send_message(target, "🎉 ဂုဏ်ယူပါတယ်! ၇ ရက်တာ Pro Plan ရရှိပါပြီ။")
            except: pass
    except: pass

@dp.message(Command("givepro30"))
async def cmd_give_pro_30days(message: types.Message):
    if str(message.from_user.id) != ADMIN_ID: return
    try:
        target = int(message.text.split()[1])
        if await set_user_plan(target, "pro", 30):
            await message.answer(f"✅ User `{target}` ကို ၁ လ Pro ပေးပြီးပါပြီ။")
            try: await bot.send_message(target, "🎉 ဂုဏ်ယူပါတယ်! ၁ လတာ Pro Plan ရရှိပါပြီ။")
            except: pass
    except: pass

@dp.message(F.text)
async def handle_user_message(message: types.Message):
    user_id = message.from_user.id
    user_text = message.text
    
    # 📌 Strict Asynchronous Lock: Spam ကာကွယ်ရန် တန်းစီစနစ်
    lock = get_user_lock(user_id)
    async with lock:
        is_allowed, reason, char_limit = await check_usage_allowed(user_id)
        
        if not is_allowed:
            if "Error" in reason or "Exception" in reason:
                return await message.answer(f"❌ Database Error: {reason}")
            else:
                return await message.answer("⚠️ ၅ နာရီအတွင်း Free version ဖြင့် ပြောဆိုခွင့် အကြိမ်ရေ (၁၀) ကြိမ် ပြည့်သွားပါပြီ။", reply_markup=get_upgrade_keyboard())

        processing_msg = await message.answer("⏳ Lisa Typing...")

        try:
            chat_history = await get_chat_history(user_id, limit=100)
            ai_response = await generate_response(user_text, history=chat_history)
            
            if not ai_response:
                return await processing_msg.edit_text("❌ AI စနစ် ချို့ယွင်းနေပါသည်။")
                
            await processing_msg.delete() 

            raw_chunks = ai_response.split("[SPLIT]")
            chunks = [c.strip() for c in raw_chunks if c.strip()]
            if not chunks: chunks = [ai_response.strip()]

            allowed_chunks = []
            current_len = 0
            for chunk in chunks:
                if current_len + len(chunk) > char_limit:
                    remaining = char_limit - current_len
                    if remaining > 0: allowed_chunks.append(chunk[:remaining])
                    break
                allowed_chunks.append(chunk)
                current_len += len(chunk)
                
            final_chunks = allowed_chunks
            
            # Database သို့ Count အတိအကျ တိုးမည်
            await update_usage(user_id, current_len)
            await save_chat(user_id, "user", user_text)
            await save_chat(user_id, "assistant", " ".join(final_chunks))

            for index, chunk in enumerate(final_chunks):
                await bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
                typing_delay = min(max(len(chunk) * 0.03, 1.0), 4.0)
                await asyncio.sleep(typing_delay)

                if len(chunk) > 4096:
                    for x in range(0, len(chunk), 4096):
                        await message.answer(chunk[x:x+4096], reply_markup=None)
                else:
                    await message.answer(chunk, reply_markup=None)

        except Exception as e:
            logger.error(f"[Bot Logic Error] {e}")
            try: await processing_msg.edit_text("❌ အမှားအယွင်းတစ်ခု ဖြစ်ပွားခဲ့ပါသည်။")
            except: pass

# --- Morning Broadcast (ယခင်အတိုင်း) ---
async def trigger_morning_broadcast():
    try:
        yangon_tz = timezone(timedelta(hours=6, minutes=30))
        now = datetime.now(yangon_tz)
        if now.hour < 8: return "Too early"
            
        today_str = now.strftime("%Y-%m-%d")
        all_users = await get_all_users()
        target_users = [u['telegram_id'] for u in all_users if str(u.get('last_morning_msg_date')) != today_str]
        if not target_users: return "No pending users"
            
        morning_msg = await generate_morning_message()
        if not morning_msg: return "AI failed"
        morning_msg = morning_msg.replace("[SPLIT]", "\n\n")

        success_count = 0
        for uid in target_users:
            try:
                await bot.send_animation(chat_id=uid, animation=WELCOME_VIDEO_URL, caption=morning_msg)
                await update_morning_date(uid, today_str)
                success_count += 1
                await asyncio.sleep(0.1) 
            except Exception as e:
                logger.error(f"Failed morning msg to {uid}: {e}")
                
        return f"Success: {success_count}"
    except Exception as e:
        logger.error(f"[Broadcast Error] {e}")
        return "Error"
