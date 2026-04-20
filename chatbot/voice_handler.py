import os
import io
import base64
import logging
import speech_recognition as sr
from gtts import gTTS

logger = logging.getLogger(__name__)

async def transcribe_audio(audio_bytes: bytes) -> str:
    """
    Transcribes audio bytes into text using SpeechRecognition.
    Accepts WAV bytes primarily.
    """
    recognizer = sr.Recognizer()
    audio_file = io.BytesIO(audio_bytes)
    
    try:
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)
            
        try:
            text = recognizer.recognize_google(audio_data, language="hi-IN")
        except sr.UnknownValueError:
            # Fallback to english if hindi fails
            text = recognizer.recognize_google(audio_data, language="en-US")
            
        return text
    except sr.UnknownValueError:
        logger.warning("Google Speech Recognition could not understand audio")
        raise ValueError("Could not understand the audio. Please try again clearly.")
    except sr.RequestError as e:
        logger.error(f"Could not request results from Google Speech Recognition service; {e}")
        raise ValueError("Speech recognition service is currently unavailable.")
    except Exception as e:
        logger.error(f"Error processing audio file: {e}")
        raise ValueError(f"Error processing audio format. Please ensure it is a valid WAV file.")

async def generate_audio(text: str, lang: str = "hi") -> str:
    """
    Generates TTS MP3 from text using gTTS and returns Base64 string.
    """
    try:
        tts_lang = "hi" if "hi" in lang.lower() else "en"
        tts = gTTS(text=text, lang=tts_lang, slow=False)
        
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        
        audio_base64 = base64.b64encode(mp3_fp.read()).decode("utf-8")
        return audio_base64
    except Exception as e:
        logger.error(f"Failed to generate TTS: {e}")
        return ""
