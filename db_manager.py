# Filename: db_manager.py
import os
import time
import aiohttp
import logging
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
# ⚠️ သတိပြုရန်: RLS Error များကို ကျော်လွှားရန် ဤနေရာတွင် Service Role (Secret) Key ကို မဖြစ်မနေ သုံးပါ။
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

FREE_RESET_SECONDS = 5 * 3600 # 5 Hours
PRO_RESET_SECONDS = 4 * 3600
FREE_MSG_LIMIT = 10
PRO_MSG_LIMIT = float('inf')
FREE_CHAR_LIMIT = 500
PRO_CHAR_LIMIT = 8000

async def get_session():
    from ai_service import get_session as ai_get_session
    return await ai_get_session()

async def get_or_create_user(telegram_id: int) -> bool:
    """User အချက်အလက်ကို စစ်ဆေးမည်။ မရှိပါက အသစ်တည်ဆောက်မည် (Auto-Provision)"""
    url = f"{SUPABASE_URL}/rest/v1/users?telegram_id=eq.{telegram_id}"
    session = await get_session()
    try:
        async with session.get(url, headers=HEADERS) as response:
            if response.status == 200:
                data = await response.json()
                if not data or len(data) == 0:
                    create_url = f"{SUPABASE_URL}/rest/v1/users"
                    payload = {
                        "telegram_id": telegram_id, 
                        "plan_type": "free", 
                        "message_count": 0, 
                        "last_reset": int(time.time()),
                        "pro_expiry_date": 0
                    }
                    async with session.post(create_url, headers=HEADERS, json=payload) as post_resp:
                        if post_resp.status not in (200, 201, 204):
                            err = await post_resp.text()
                            logger.error(f"[DB Insert Error] Status: {post_resp.status}, Detail: {err}")
                            return False
                        return True
                return True
            else:
                err = await response.text()
                logger.error(f"[DB GET Error in get_or_create] Status: {response.status}, Detail: {err}")
                return False
    except Exception as e:
        logger.error(f"[DB Exception] get_or_create_user: {str(e)}")
        return False

async def get_user_info(telegram_id: int) -> Optional[Dict]:
    """Status command အတွက် User ၏ နောက်ဆုံးအခြေအနေကို ဆွဲထုတ်မည်"""
    url = f"{SUPABASE_URL}/rest/v1/users?telegram_id=eq.{telegram_id}"
    session = await get_session()
    try:
        await get_or_create_user(telegram_id) # Ensure user exists
        async with session.get(url, headers=HEADERS) as response:
            if response.status == 200:
                data = await response.json()
                if data and len(data) > 0:
                    return data[0]
            else:
                err = await response.text()
                logger.error(f"[DB Error in get_user_info] Status: {response.status}, Detail: {err}")
    except Exception as e:
        logger.error(f"[DB Exception] get_user_info: {str(e)}")
    return None

async def check_usage_allowed(telegram_id: int) -> tuple:
    """Message ပို့ခွင့် ရှိ/မရှိ စစ်ဆေးမည် (Free Limit = 10)"""
    url = f"{SUPABASE_URL}/rest/v1/users?telegram_id=eq.{telegram_id}"
    session = await get_session()
    try:
        created = await get_or_create_user(telegram_id)
        if not created:
            return False, "Database Insertion Failed (Check Service Role Key)", 0

        async with session.get(url, headers=HEADERS) as response:
            if response.status != 200:
                return False, "Database Connection Error", 0
                
            data = await response.json()
            if not data or len(data) == 0:
                return False, "User Record Not Found", 0
            
            user = data[0]
            plan = user.get('plan_type', 'free')
            expiry_date = user.get('pro_expiry_date', 0)
            now = int(time.time())

            if plan == 'pro' and expiry_date != 0 and now > expiry_date:
                update_url = f"{SUPABASE_URL}/rest/v1/users?telegram_id=eq.{telegram_id}"
                await session.patch(update_url, headers=HEADERS, json={"plan_type": "free"})
                plan = 'free'

            count = user.get('message_count', 0)
            last_reset = user.get('last_reset', 0)
            reset_time = FREE_RESET_SECONDS if plan == 'free' else PRO_RESET_SECONDS
            limit = FREE_MSG_LIMIT if plan == 'free' else PRO_MSG_LIMIT
            char_limit = FREE_CHAR_LIMIT if plan == 'free' else PRO_CHAR_LIMIT

            if now - last_reset > reset_time:
                update_url = f"{SUPABASE_URL}/rest/v1/users?telegram_id=eq.{telegram_id}"
                await session.patch(update_url, headers=HEADERS, json={"message_count": 0, "last_reset": now})
                count = 0

            if count >= limit:
                return False, "Limit exceeded", char_limit
            return True, "Allowed", char_limit
    except Exception as e:
        logger.exception(f"[DB CRITICAL ERROR] check_usage_allowed: {str(e)}")
        return False, "Database Exception", 0

async def update_usage(telegram_id: int, char_count: int):
    """Message Limit ကို အတိအကျ တိုးမည် (Atomic Logic)"""
    url = f"{SUPABASE_URL}/rest/v1/users?telegram_id=eq.{telegram_id}"
    session = await get_session()
    try:
        async with session.get(url, headers=HEADERS) as response:
            if response.status == 200:
                data = await response.json()
                if data and len(data) > 0:
                    current_count = int(data[0].get('message_count', 0))
                    new_count = current_count + 1
                    
                    patch_url = f"{SUPABASE_URL}/rest/v1/users?telegram_id=eq.{telegram_id}"
                    async with session.patch(patch_url, headers=HEADERS, json={"message_count": new_count}) as patch_resp:
                        if patch_resp.status not in (200, 204):
                            logger.error(f"[DB Patch Error] Status: {patch_resp.status}")
    except Exception as e:
        logger.error(f"[DB Exception] update_usage: {e}")

async def set_user_plan(telegram_id: int, plan: str, days: int = 30):
    url = f"{SUPABASE_URL}/rest/v1/users?telegram_id=eq.{telegram_id}"
    session = await get_session()
    try:
        now = int(time.time())
        payload = {"plan_type": plan, "message_count": 0}
        if plan == "pro":
            payload["pro_expiry_date"] = now + (days * 24 * 60 * 60)
        else:
            payload["pro_expiry_date"] = 0
        await session.patch(url, headers=HEADERS, json=payload)
        return True
    except Exception:
        return False

# 📌 မူလ chat_history ကို ပြန်လည် အသုံးပြုထားပါသည်
async def save_chat(telegram_id: int, role: str, content: str):
    url = f"{SUPABASE_URL}/rest/v1/chat_history"
    data = {"telegram_id": telegram_id, "role": role, "content": content}
    session = await get_session()
    try:
        await session.post(url, headers=HEADERS, json=data)
    except Exception as e:
        logger.error(f"[DB Exception] save_chat: {e}")

async def get_chat_history(telegram_id: int, limit: int = 100) -> List[Dict[str, str]]:
    url = f"{SUPABASE_URL}/rest/v1/chat_history?telegram_id=eq.{telegram_id}&order=created_at.desc&limit={limit}"
    session = await get_session()
    try:
        async with session.get(url, headers=HEADERS) as response:
            if response.status == 200:
                data = await response.json()
                return [{"role": row["role"], "content": row["content"]} for row in data][::-1]
    except Exception:
        return []

async def clear_history(telegram_id: int) -> bool:
    url = f"{SUPABASE_URL}/rest/v1/chat_history?telegram_id=eq.{telegram_id}"
    session = await get_session()
    try:
        async with session.delete(url, headers=HEADERS) as response:
            return response.status in (200, 204)
    except Exception:
        return False

async def get_all_users() -> List[Dict]:
    url = f"{SUPABASE_URL}/rest/v1/users?select=telegram_id,last_morning_msg_date"
    session = await get_session()
    try:
        async with session.get(url, headers=HEADERS) as response:
            if response.status == 200:
                return await response.json()
    except Exception:
        return []

async def update_morning_date(telegram_id: int, date_str: str):
    url = f"{SUPABASE_URL}/rest/v1/users?telegram_id=eq.{telegram_id}"
    session = await get_session()
    try:
        await session.patch(url, headers=HEADERS, json={"last_morning_msg_date": date_str})
    except Exception:
        pass

def is_admin(user_id: int) -> bool:
    """Environment variable မှ ADMIN_ID ကို လုံခြုံစွာ စစ်ဆေးပေးမည်"""
    admin_id_env = os.getenv("ADMIN_ID")
    if not admin_id_env:
        return False
    try:
        return int(user_id) == int(admin_id_env.strip())
    except ValueError:
        return False
