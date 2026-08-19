# Filename: ai_service.py
import os
import aiohttp
import logging
from typing import Optional, List, Dict
from dotenv import load_dotenv

from prompts import SYSTEM_PROMPT

load_dotenv()

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_ID = "google/gemma-4-31b-it"

session: Optional[aiohttp.ClientSession] = None

async def get_session():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession()
    return session

async def generate_response(prompt: str, history: List[Dict[str, str]] = None) -> Optional[str]:
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/EducationAIBot", 
        "X-Title": "Education AI Telegram Bot"
    }
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": MODEL_ID,
        "messages": messages,
        "temperature": 0.8, # Character မပျက်စေရန် အနည်းငယ် လျှော့ချထားသည်
        "top_p": 0.9
    }

    try:
        s = await get_session()
        async with s.post(url, headers=headers, json=payload, timeout=60) as response:
            if response.status == 200:
                data = await response.json()
                return data['choices'][0]['message']['content']
            else:
                error_text = await response.text()
                logger.error(f"[AI Service Error] Status: {response.status}, Detail: {error_text}")
                return None
    except Exception as e:
        logger.error(f"[AI Service Exception] {str(e)}")
        return None

async def generate_morning_message() -> Optional[str]:
    """AI ဆီမှ နေ့စဉ်မတူသော မောနင်းစာသား တောင်းခံမည့် Function"""
    prompt = "မင်္ဂလာနံနက်ခင်းပါ လီဆာ! Blink တွေကို မနက်အိပ်ရာထ ချစ်စရာကောင်းအောင် နှုတ်ဆက်ပေးပါ။ (Emoji လေးတွေနဲ့ သဘာဝကျကျ အတိုလေးပဲ ရေးပေးပါ။)"
    return await generate_response(prompt)
