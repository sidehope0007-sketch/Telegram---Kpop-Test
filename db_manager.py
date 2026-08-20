# Filename: db_manager.py
import os
import time
import aiohttp
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta  # 👈 (၃) ရက်စာ တွက်ရန် ထပ်တိုးထားသည်
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
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

def is_admin(user_id: int) -> bool:
    admin_id_env = os.getenv("ADMIN_ID")
    if not admin_id_env: return False
    try: return int(user_id) == int(admin_id_env.strip())
    except ValueError: return False

async def get_or_create_user(telegram_id: int) -> bool:
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
                        if post_resp.status not in (200, 201, 204): return False
                        return True
                return True
            return False
    except Exception: return False

async def get_user_info(telegram_id: int) -> Optional[Dict]:
    url = f"{SUPABASE_URL}/rest/v1/users?telegram_id=eq.{telegram_id}"
    session = await get_session()
    try:
        await get_or_create_user(telegram_id)
        async with session.get(url, headers=HEADERS) as response:
            if response.status == 200:
                data = await response.json()
                if data and len(data) > 0: return data[0]
    except Exception: pass
    return None

async def check_usage_allowed(telegram_id: int) -> tuple:
    url = f"{SUPABASE_URL}/rest/v1/users?telegram_id=eq.{telegram_id}"
    session = await get_session()
    try:
        created = await get_or_create_user(telegram_id)
        if not created: return False, "DB Insert Fail", 0

        async with session.get(url, headers=HEADERS) as response:
            if response.status != 200: return False, "DB Error", 0
            data = await response.json()
            if not data: return False, "No User", 0
            
            user = data[0]
            plan = user.get('plan_type', 'free')
            expiry_date = user.get('pro_expiry_date', 0)
            now = int(time.time())

            if plan == 'pro' and expiry_date != 0 and now > expiry_date:
                await session.patch(url, headers=HEADERS, json={"plan_type": "free"})
                plan = 'free'

            count = user.get('message_count', 0)
            last_reset = user.get('last_reset', 0)
            reset_time = FREE_RESET_SECONDS if plan == 'free' else PRO_RESET_SECONDS
            limit = FREE_MSG_LIMIT if plan == 'free' else PRO_MSG_LIMIT
            char_limit = FREE_CHAR_LIMIT if plan == 'free' else PRO_CHAR_LIMIT

            if now - last_reset > reset_time:
                await session.patch(url, headers=HEADERS, json={"message_count": 0, "last_reset": now})
                count = 0

            if count >= limit: return False, "Limit exceeded", char_limit
            return True, "Allowed", char_limit
    except Exception: return False, "Exception", 0

async def update_usage(telegram_id: int, char_count: int):
    url = f"{SUPABASE_URL}/rest/v1/users?telegram_id=eq.{telegram_id}"
    session = await get_session()
    try:
        async with session.get(url, headers=HEADERS) as response:
            if response.status == 200:
                data = await response.json()
                if data:
                    new_count = int(data[0].get('message_count', 0)) + 1
                    await session.patch(url, headers=HEADERS, json={"message_count": new_count})
    except Exception: pass

async def set_user_plan(telegram_id: int, plan: str, days: int = 30):
    url = f"{SUPABASE_URL}/rest/v1/users?telegram_id=eq.{telegram_id}"
    session = await get_session()
    try:
        now = int(time.time())
        payload = {"plan_type": plan, "message_count": 0, "pro_expiry_date": now + (days * 86400) if plan == "pro" else 0}
        await session.patch(url, headers=HEADERS, json=payload)
        return True
    except Exception: return False

async def save_chat(telegram_id: int, role: str, content: str):
    url = f"{SUPABASE_URL}/rest/v1/chat_history"
    data = {"telegram_id": telegram_id, "role": role, "content": content}
    session = await get_session()
    try:
        await session.post(url, headers=HEADERS, json=data)
    except Exception as e:
        logger.error(f"[DB Exception] save_chat: {e}")

# 📌 ဤ Function ကို Time-Bound Query သို့ ပြောင်းလဲထားသည်
async def get_chat_history(telegram_id: int, days: int = 3, limit: int = 200) -> List[Dict[str, str]]:
    """(၃) ရက်စာ မှတ်ဉာဏ်များကိုသာ အတိအကျ ဆွဲထုတ်မည် (Token ကုန်ကျစရိတ် ကာကွယ်ရန်)"""
    # လွန်ခဲ့သော ၃ ရက်၏ အချိန်ကို တွက်ချက်မည် (ISO 8601 Format)
    time_threshold = datetime.now(timezone.utc) - timedelta(days=days)
    iso_time = time_threshold.isoformat()
    
    # created_at=gte.{iso_time} ကို သုံး၍ အချိန်စစ်ထုတ်မည်
    url = f"{SUPABASE_URL}/rest/v1/chat_history?telegram_id=eq.{telegram_id}&created_at=gte.{iso_time}&order=created_at.desc&limit={limit}"
    session = await get_session()
    try:
        async with session.get(url, headers=HEADERS) as response:
            if response.status == 200:
                data = await response.json()
                # အသစ်မှ အဟောင်းဖြစ်နေသဖြင့် (DESC) AI နားလည်အောင် chronological (အဟောင်းမှ အသစ်) ပြန်လှန်ပေးမည်
                return [{"role": row["role"], "content": row["content"]} for row in data][::-1]
    except Exception as e:
        logger.error(f"[DB Exception] get_chat_history: {e}")
    return []

async def clear_history(telegram_id: int) -> bool:
    url = f"{SUPABASE_URL}/rest/v1/chat_history?telegram_id=eq.{telegram_id}"
    session = await get_session()
    try:
        async with session.delete(url, headers=HEADERS) as response:
            return response.status in (200, 204)
    except Exception: return False

async def get_all_users() -> List[Dict]:
    url = f"{SUPABASE_URL}/rest/v1/users?select=telegram_id,last_morning_msg_date"
    session = await get_session()
    try:
        async with session.get(url, headers=HEADERS) as response:
            if response.status == 200: return await response.json()
    except Exception: return []

async def update_morning_date(telegram_id: int, date_str: str):
    url = f"{SUPABASE_URL}/rest/v1/users?telegram_id=eq.{telegram_id}"
    session = await get_session()
    try: await session.patch(url, headers=HEADERS, json={"last_morning_msg_date": date_str})
    except Exception: pass
