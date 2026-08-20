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

# 📌 STRICT TOKEN BUDGETING: API ကုန်ကျစရိတ်ကို အက္ခရာ ၆၀၀၀ (Tokens အရေအတွက် ခန့်မှန်း ၁၅၀၀) ဖြင့် အတိအကျ ကန့်သတ်မည်
MAX_HISTORY_CHAR_BUDGET = 6000 

session: Optional[aiohttp.ClientSession] = None

async def get_session():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession()
    return session

def trim_history_by_budget(history: List[Dict[str, str]], budget: int = MAX_HISTORY_CHAR_BUDGET) -> List[Dict[str, str]]:
    """
    [Architect's Logic] Token Cost လေလွင့်မှု မရှိစေရန် ၃ ရက်စာ History အားလုံးကို မပို့ဘဲ၊
    သတ်မှတ်ထားသော အက္ခရာ (Character) အရေအတွက် အတွင်းသာ အသစ်ဆုံးစာများကို ရွေးချယ် ဖြတ်ယူမည်။
    """
    if not history:
        return []
    
    trimmed_history = []
    current_chars = 0
    
    # နောက်ဆုံး စာ (အသစ်ဆုံး) မှ စတင်၍ ရေတွက်ရန် Reverse လုပ်မည်
    for msg in reversed(history):
        msg_len = len(msg.get("content", ""))
        
        # Budget ပြည့်သွားပါက အဟောင်းများကို ဆက်မယူတော့ဘဲ ရပ်တန့်မည် (Token ကာကွယ်ခြင်း)
        if current_chars + msg_len > budget:
            break
            
        trimmed_history.append(msg)
        current_chars += msg_len
        
    # AI နားလည်စေရန် မူလ အစီအစဉ်အတိုင်း (အဟောင်းမှ အသစ်သို့) ပြန်လှန်ပေးမည်
    return trimmed_history[::-1]

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
        # 📌 ၃ ရက်စာ မှတ်ဉာဏ်ထဲမှ Token Budget အတွင်း ဝင်မည့် စာများကိုသာ စစ်ထုတ်ယူမည်
        budgeted_history = trim_history_by_budget(history)
        messages.extend(budgeted_history)
        
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": MODEL_ID,
        "messages": messages,
        "temperature": 0.8,
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
    prompt = "မင်္ဂလာနံနက်ခင်းပါ လီဆာ! Blink တွေကို မနက်အိပ်ရာထ ချစ်စရာကောင်းအောင် နှုတ်ဆက်ပေးပါ။ (Emoji လေးတွေနဲ့ သဘာဝကျကျ အတိုလေးပဲ ရေးပေးပါ။)"
    return await generate_response(prompt)
