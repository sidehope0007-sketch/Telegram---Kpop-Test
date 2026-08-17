// Filename: bot_logic.py
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

WELCOME_GIF_URL = "https://srtteanzawxfaadaoelk.supabase.co/storage/v1/object/public/Telegram%20Ai%20photo/sexgpt.gif"

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    await get_or_create_user(user_id)
    
    welcome_text = (
        f"မင်္ဂလာပါ {message.from_user.first_name}!\n\n"
        "သင့်ရဲ့ အလိုရမ္မက်တွေကို ဖြည့်ဆီးပေးဖို့ ကျွန်မ Sex GPT က သင့်အနားရှိနေပါပြီ။\n\n"
        "တူတူ မှောင်ဖို့အတွက် အဆင့်သင့်ဖြစ်နေပါပြီ။\n"
        "သင့်ရဲ့ မေးခွန်းတွေကို ယခုပဲ စတင်မေးမြန်းနိုင်ပါပြီ!"
    )
    try:
        await message.answer_animation(animation=WELCOME_GIF_URL, caption=welcome_text)
    except Exception:
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

# ... (cmd_new_chat, cmd_admin, cmd_status, cmd_give_pro_7days, cmd_give_pro_30days commands များကို မူလအတိုင်း ထားရှိပါ) ...

@dp.message(F.text)
async def handle_user_message(message: types.Message):
    user_id = message.from_user.id
    user_text = message.text
    
    is_allowed, reason, char_limit = await check_usage_allowed(user_id)
    if not is_allowed:
        return await message.answer("⚠️ Free version တွင်ပြန်ဖြေသောစာလုံးရေတွက်ကန့်သတ်ထားပါသည်။", reply_markup=get_upgrade_keyboard())

    processing_msg = await message.answer("⏳ Sex GPT တွေးနေပါသည်...")

    try:
        chat_history = await get_chat_history(user_id, limit=20)
        ai_response = await generate_response(user_text, history=chat_history)
        
        if not ai_response:
            return await processing_msg.edit_text("❌ AI စနစ် ချို့ယွင်းနေပါသည်။")
            
        await processing_msg.delete() 

        # 1. AI ပြန်လာသောစာကို [SPLIT] ဖြင့် ခွဲထုတ်ခြင်း
        raw_chunks = ai_response.split("[SPLIT]")
        chunks = [c.strip() for c in raw_chunks if c.strip()]
        
        # 2. အကယ်၍ AI က [SPLIT] မထည့်ခဲ့ပါက မူလစာသားအတိုင်း ထားရန်
        if not chunks:
            chunks = [ai_response.strip()]

        # 3. Char Limit စစ်ဆေးခြင်း (စုစုပေါင်း စာလုံးရေ)
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
        
        # Database သိမ်းဆည်းခြင်း (AI ၏ မူလတုန့်ပြန်မှုကို တစ်ခါတည်းသိမ်းမည်)
        await update_usage(user_id, current_len)
        await save_chat(user_id, "user", user_text)
        await save_chat(user_id, "assistant", " ".join(final_chunks))

        # 4. Pro Upgrade ခလုတ် ပြင်ဆင်ခြင်း
        admin_username = "slipme_mm" 
        custom_keyboard = None
        if char_limit == FREE_CHAR_LIMIT:
            custom_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Pro Plan ဝယ်ယူရန် ", url=f"https://t.me/{admin_username}")]
            ])

        # 5. သဘာဝကျကျ အချိန်ဆိုင်း၍ (Typing delay) ပို့လွှတ်ခြင်း
        for index, chunk in enumerate(final_chunks):
            is_last_chunk = (index == len(final_chunks) - 1)
            
            # Typing action ပြသခြင်း
            await bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
            
            # စာလုံးရေအပေါ်မူတည်၍ အချိန်ဆိုင်းခြင်း (အနည်းဆုံး ၁ စက္ကန့်၊ အများဆုံး ၄ စက္ကန့်)
            typing_delay = min(max(len(chunk) * 0.03, 1.0), 4.0)
            await asyncio.sleep(typing_delay)

            # Telegram ၏ 4096 limit ကိုပါ ကာကွယ်ထားခြင်း
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
