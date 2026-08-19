# Filename: bot_logic.py
import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from aiogram.enums import ChatAction
from dotenv import load_dotenv

from db_manager import (
    check_usage_allowed, 
    update_usage, 
    get_or_create_user, 
    save_chat, 
    get_chat_history, 
    clear_history, 
    set_user_plan,
    FREE_CHAR_LIMIT
)
from ai_service import generate_response

load_dotenv()
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_upgrade_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Pro Plan ဝယ်ယူရန်", callback_data="buy_pro")]
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
        logger.error(f"[Start Command Error] Video ပို့ရာတွင် အမှားရှိသည်: {e}")
        await message.answer(welcome_text)

async def setup_bot_commands(bot: Bot):
    bot_commands = [
        BotCommand(command="/new_chat", description="🔄 New Chat စတင်ရန်"),
        BotCommand(command="/admin", description="👨‍💻 Admin နှင့် ဆက်သွယ်ရန်"),
        BotCommand(command="/status", description="📊 အသုံးပြုမှု စစ်ဆေးရန်"),
        BotCommand(command="/givepro7", description="💎 ၇ ရက် Pro ပေးရန်"),
        BotCommand(command="/givepro30", description="💎 ၁ လ Pro ပေးရန်"),
    ]
    await bot.set_my_commands(bot_commands)

@dp.message(Command("new_chat"))
async def cmd_new_chat(message: types.Message):
    user_id = message.from_user.id
    if await clear_history(user_id):
        await message.answer("✅ မှတ်ဉာဏ်ဟောင်းများကို အောင်မြင်စွာ ဖျက်လင်းလိုက်ပါပြီ။")
    else:
        await message.answer("⚠️ အမှားတစ်ခု ဖြစ်ပွားခဲ့ပါသည်။")

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    await message.answer("👨‍💻 Admin နှင့် ဆက်သွယ်ရန် လိုအပ်ပါက အောက်ပါ လင့်ခ်မှတစ်ဆင့် ဆက်သွယ်နိုင်ပါသည်:\n\n👉 @slipme_mm")

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    user_id = message.from_user.id
    is_allowed, reason, char_limit = await check_usage_allowed(user_id)
    
    from db_manager import SUPABASE_URL, HEADERS
    import aiohttp
    from ai_service import get_session
    
    url = f"{SUPABASE_URL}/rest/v1/users?telegram_id=eq.{user_id}"
    session = await get_session()
    
    async with session.get(url, headers=HEADERS) as response:
        if response.status == 200:
            data = await response.json()
            if data:
                user = data[0]
                plan = user.get('plan_type', 'free')
                count = user.get('message_count', 0)
                status_text = (
                    f"📊 **သင်၏ အသုံးပြုမှု အခြေအနေ**\n\n"
                    f"👤 User ID: `{user_id}`\n"
                    f"💎 Plan: `{plan.upper()}`\n"
                    f"💬 အသုံးပြုပြီးသမျှ: `{count}` messages\n"
                    f"📏 တစ်ကြိမ်စာ စာလုံးရေ ကန့်သတ်ချက်: `{char_limit}`"
                )
                await message.answer(status_text, parse_mode="Markdown")
            else:
                await message.answer("⚠️ အချက်အလက် ရှာမတွေ့ပါ။")
        else:
            await message.answer("❌ Database ချိတ်ဆက်မှု အမှားရှိနေပါသည်။")

@dp.message(Command("givepro7"))
async def cmd_give_pro_7days(message: types.Message):
    if str(message.from_user.id) != ADMIN_ID:
        return await message.answer("❌ သင်သည် ဤ Command ကို အသုံးပြုခွင့်မရှိပါ။")
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("⚠️ အသုံးပြုပုံ: `/givepro7 12345678`", parse_mode="Markdown")
    try:
        target_user_id = int(args[1])
        success = await set_user_plan(target_user_id, "pro", days=7)
        if success:
            await message.answer(f"✅ User `{target_user_id}` ကို ၇ ရက် Pro Plan ပေးပြီးပါပြီ။", parse_mode="Markdown")
            try:
                await bot.send_message(target_user_id, "🎉 ဂုဏ်ယူပါတယ်! သင့်ကို ၇ ရက်တာ Pro Plan အဆင့်မြှင့်ပေးလိုက်ပါပြီ။")
            except: pass
        else:
            await message.answer("❌ အမှားတစ်ခု ဖြစ်ပွားခဲ့ပါသည်။")
    except ValueError:
        await message.answer("❌ User ID သည် နံပါတ်ဖြစ်ရပါမည်။")

@dp.message(Command("givepro30"))
async def cmd_give_pro_30days(message: types.Message):
    if str(message.from_user.id) != ADMIN_ID:
        return await message.answer("❌ သင်သည် ဤ Command ကို အသုံးပြုခွင့်မရှိပါ။")
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("⚠️ အသုံးပြုပုံ: `/givepro30 12345678`", parse_mode="Markdown")
    try:
        target_user_id = int(args[1])
        success = await set_user_plan(target_user_id, "pro", days=30)
        if success:
            await message.answer(f"✅ User `{target_user_id}` ကို ၁ လ Pro Plan ပေးပြီးပါပြီ။", parse_mode="Markdown")
            try:
                await bot.send_message(target_user_id, "🎉 ဂုဏ်ယူပါတယ်! သင့်ကို ၁ လတာ Pro Plan အဆင့်မြှင့်ပေးလိုက်ပါပြီ။")
            except: pass
        else:
            await message.answer("❌ အမှားတစ်ခု ဖြစ်ပွားခဲ့ပါသည်။")
    except ValueError:
        await message.answer("❌ User ID သည် နံပါတ်ဖြစ်ရပါမည်။")

@dp.message(F.text)
async def handle_user_message(message: types.Message):
    user_id = message.from_user.id
    user_text = message.text
    
    is_allowed, reason, char_limit = await check_usage_allowed(user_id)
    
    # 📌 ပြင်ဆင်ချက် (Fix): Database Error နှင့် Limit ကို တိကျစွာ ခွဲခြားခြင်း
    if not is_allowed:
        if reason in ["Supabase Error", "Database Exception"]:
            return await message.answer(f"❌ Database နှင့် ချိတ်ဆက်၍ မရပါ။ (Reason: {reason})\nAdmin သို့ အကြောင်းကြားပေးပါ။")
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
        
        if not chunks:
            chunks = [ai_response.strip()]

        allowed_chunks = []
        current_len = 0
        for chunk in chunks:
            if current_len + len(chunk) > char_limit:
                remaining = char_limit - current_len
                if remaining > 0:
                    allowed_chunks.append(chunk[:remaining])
                break
            allowed_chunks.append(chunk)
            current_len += len(chunk)
            
        final_chunks = allowed_chunks
        
        await update_usage(user_id, current_len)
        await save_chat(user_id, "user", user_text)
        await save_chat(user_id, "assistant", " ".join(final_chunks))

        admin_username = "slipme_mm" 
        custom_keyboard = None
        if char_limit == FREE_CHAR_LIMIT:
            custom_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Pro Plan ဝယ်ယူရန် ", url=f"https://t.me/{admin_username}")]
            ])

        for index, chunk in enumerate(final_chunks):
            is_last_chunk = (index == len(final_chunks) - 1)
            
            await bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
            typing_delay = min(max(len(chunk) * 0.03, 1.0), 4.0)
            await asyncio.sleep(typing_delay)

            if len(chunk) > 4096:
                for x in range(0, len(chunk), 4096):
                    is_sub_last = (x + 4096 >= len(chunk))
                    keyboard_to_send = custom_keyboard if (is_last_chunk and is_sub_last) else None
                    await message.answer(chunk[x:x+4096], reply_markup=keyboard_to_send)
            else:
                await message.answer(chunk, reply_markup=custom_keyboard if is_last_chunk else None)

    except Exception as e:
        logger.error(f"[Bot Logic Error] {e}")
        try:
            await processing_msg.edit_text("❌ အမှားအယွင်းတစ်ခု ဖြစ်ပွားခဲ့ပါသည်။")
        except: pass
