# Filename: bot_logic.py
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from dotenv import load_dotenv

# Import necessary functions from db_manager
from db_manager import (
    check_usage_allowed, 
    update_usage, 
    get_or_create_user, 
    save_chat, 
    get_chat_history, 
    clear_history, 
    set_user_plan
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
    except Exception as e:
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
    if not is_allowed:
        return await message.answer("⚠️ Free version တွင်ပြန်ဖြေသောစာလုံးရေတွက်ကန့်သတ်ထားပါသည်။", reply_markup=get_upgrade_keyboard())

    processing_msg = await message.answer("⏳ Sex GPT Loading...")

    try:
        chat_history = await get_chat_history(user_id, limit=20)
        ai_response = await generate_response(user_text, history=chat_history)
        
        if not ai_response:
            return await processing_msg.edit_text("❌ AI စနစ် ချို့ယွင်းနေပါသည်။")
            
        # --- ပြင်ဆင်ချက် ၁: သတိပေးစာသားကို ဖျောက်ပြီး စာလုံးရေကိုပဲ ဖြတ်လိုက်သည် ---
        if len(ai_response) > char_limit:
            ai_response = ai_response[:char_limit] 
            
        await update_usage(user_id, len(ai_response))
        await save_chat(user_id, "user", user_text)
        await save_chat(user_id, "assistant", ai_response)
        
        await processing_msg.delete() 

        # --- ပြင်ဆင်ချက် ၂: Free User ဖြစ်ပါက Admin ဆီသို့တိုက်ရိုက်သွားမည့် ခလုတ်ထည့်ခြင်း ---
        # Admin username နေရာတွင် မိမိ username ကို ပြောင်းရေးပါ
        admin_username = "slipme_mm" 
        custom_keyboard = None
        
        # User က Pro မဟုတ်ဘဲ Free ဖြစ်နေလျှင် ခလုတ်ထည့်မည်
        # check_usage_allowed က return ပြန်တဲ့ char_limit ကို ကြည့်ပြီး Free လား Pro လား ခွဲခြားနိုင်သည်
        from db_manager import FREE_CHAR_LIMIT
        if char_limit == FREE_CHAR_LIMIT:
            custom_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Pro Plan ဝယ်ယူရန် ", url=f"https://t.me/{admin_username}")]
            ])
        
        if len(ai_response) > 4096:
            for x in range(0, len(ai_response), 4096):
                # စာပိုဒ်အများကြီးဖြစ်နေလျှင် နောက်ဆုံးစာပိုဒ်တွင်မှ ခလုတ်ပြမည်
                is_last_part = (x + 4096 >= len(ai_response))
                await message.answer(ai_response[x:x+4096], reply_markup=custom_keyboard if is_last_part else None)
        else:
            await message.answer(ai_response, reply_markup=custom_keyboard)
            
    except Exception as e:
        logger.error(f"[Bot Logic Error] {e}")
        await processing_msg.edit_text("❌ အမှားအယွင်းတစ်ခု ဖြစ်ပွားခဲ့ပါသည်။")
