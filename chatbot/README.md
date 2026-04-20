# Chatbot Module (KisanBot)

This module handles the AI-powered farming assistant chatbot using Google's Gemini LLM.

## Setup & Configuration

To use the chatbot, you must configure the Gemini API key in your `.env` file:
```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-1.5-flash
CHATBOT_MAX_HISTORY=10
CHATBOT_TIMEOUT_SECONDS=30
CHATBOT_CACHE_TTL=7200
```
*Get a free API key at [Google AI Studio](https://aistudio.google.com/).*

## Context Injection

The `context_builder.py` aggregates data concurrently from:
- **IoT Data**: Latest readings via `iot.ingestor`.
- **Weather, Crop, Historical, Profile**: Database lookup wrappers in `repository.py`.

This aggregated context is injected dynamically as a text block in the Gemini `system_instruction` prompt.

### Adding a New Data Source
1. Write a fetcher function in `repository.py`.
2. Add the fetch call to `asyncio.gather()` in `context_builder.py`.
3. Add a section to `format_context_as_text()` to format the result.

## API Usage Example

**Starting a chat (or continuing a session):**
```bash
curl -X POST "http://localhost:8000/chatbot/chat" \
     -H "Content-Type: application/json" \
     -d '{
           "farmer_id": "FARMER-001",
           "session_id": "ab123456-1234-1234-1234-123456789012",
           "message": "meri gehu ki fasal mein konsa khad dalu?",
           "lang": "hi"
         }'
```

**Response format:**
```json
{
  "session_id": "ab123456-1234-1234-1234-123456789012",
  "reply": "Gehu ki fasal mein... ⚠️ Disclaimer: Please verify any chemical dosages...",
  "reply_lang": "hi",
  "context_used": ["iot", "crop", "farmer_profile"],
  "intent": "fertilizer_advice",
  "timestamp": "2024-05-15T12:00:00Z",
  "tokens_used": 145
}
```

## Resilience and Rate Limits
- The module is Redis-first for fast memory loading, but gracefully falls back to SQLite.
- A basic in-memory rate limiter protects against Gemini's free tier limits (15 requests/minute), adding slight sleep delays if requests from the same farmer arrive too quickly.
- If an exception occurs on Gemini's end, localized error messages are returned instead of HTTP 500s.
