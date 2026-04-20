import os
import logging
import asyncio
from datetime import datetime, timezone
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.api_core.exceptions import ResourceExhausted, InvalidArgument

logger = logging.getLogger(__name__)

# Simple in-memory rate limiter: dict of farmer_id -> datetime
_rate_limits = {}

class GeminiClient:
    def __init__(self):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    def _get_model(self, system_instruction: str) -> genai.GenerativeModel:
        return genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_instruction,
            generation_config={
                "temperature": 0.4,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 1024,
            },
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )

    def build_system_prompt(self, context_text: str, intent: str, lang: str, intent_instruction: str) -> str:
        prompt = f"""You are KisanBot, an expert AI farming assistant for Indian farmers.
You work for AgriSense — an agricultural AI platform.

YOUR PERSONALITY:
- Speak like a trusted, experienced Indian agronomist
- Use simple language — farmer may have low literacy
- Be direct and specific — give exact amounts, timings, quantities
- Never say "I don't know" — give best estimate with caveat
- If no field data available, give general advice for the crop/region

LANGUAGE RULES:
- Respond in: {lang} 
- If lang=hi: respond in Hindi using simple words, avoid complex Sanskrit
- If lang=en: respond in simple English
- Mix Hindi+English naturally if that feels more helpful
- Always use Indian units: quintal, bigha, acre, rupee

CURRENT FARMER FIELD DATA:
{context_text}

QUESTION TYPE: {intent}
SPECIAL INSTRUCTION: {intent_instruction}

RESPONSE FORMAT:
- Max 150 words unless explanation truly needs more
- Use numbered steps for action items
- Put most important advice FIRST
- End with one follow-up question to help farmer more

NEVER:
- Recommend unsafe chemical doses
- Give financial advice beyond crop pricing
- Make up specific govt scheme details — say "check local Krishi Kendra"
- Pretend you have real-time mandi prices unless provided in context
"""
        return prompt

    async def _rate_limit_check(self, farmer_id: str):
        now = datetime.now(timezone.utc)
        if farmer_id in _rate_limits:
            elapsed = (now - _rate_limits[farmer_id]).total_seconds()
            if elapsed < 4.0:
                await asyncio.sleep(4.0 - elapsed)
        _rate_limits[farmer_id] = datetime.now(timezone.utc)

    async def chat(self, message: str, history: list[dict], system_prompt: str, farmer_id: str) -> tuple[str, int]:
        await self._rate_limit_check(farmer_id)
        
        model = self._get_model(system_instruction=system_prompt)
        
        try:
            chat_session = model.start_chat(history=history)
            response = await chat_session.send_message_async(message)
            
            tokens_used = 0
            if response.usage_metadata:
                tokens_used = response.usage_metadata.total_token_count
                
            reply_text = response.text
            
            # Post-processing guardrail
            lower_reply = reply_text.lower()
            if any(word in lower_reply for word in ["pesticide", "fertilizer", "chemical", "dosage", "npk", "urea", "कीटनाशक", "उर्वरक", "खाद"]):
                disclaimer = "\n\n⚠️ Disclaimer: Please verify any chemical dosages with a local extension worker or Krishi Vigyan Kendra before application."
                if disclaimer not in reply_text:
                    reply_text += disclaimer
                
            return reply_text, tokens_used
            
        except ResourceExhausted:
            logger.warning(f"Gemini ResourceExhausted for farmer {farmer_id}")
            return "Abhi server busy hai, thodi der baad try karein 🙏", 0
        except InvalidArgument as e:
            logger.error(f"Gemini InvalidArgument: {e}")
            return "Kuch galat ho gaya, dobara try karein", 0
        except Exception as e:
            logger.error(f"Gemini Chat Error: {e}")
            return "Kshama karein, abhi main uttar nahi de pa raha hoon. Kripya baad mein prayas karein.", 0

    async def health_check(self) -> bool:
        try:
            model = self._get_model(system_instruction="You are a helpful assistant.")
            chat_session = model.start_chat(history=[])
            response = await chat_session.send_message_async("Hello")
            return bool(response.text)
        except Exception as e:
            logger.error(f"Gemini Health Check Failed: {e}")
            return False

gemini_client = GeminiClient()
