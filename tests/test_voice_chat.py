import pytest
from fastapi.testclient import TestClient
from api.main import app
from chatbot.gemini_client import gemini_client
import chatbot.router as router_module
import chatbot.voice_handler as voice_module

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def mock_gemini(monkeypatch):
    async def mock_chat(*args, **kwargs):
        return "I am a simulated voice response.", 10
    monkeypatch.setattr(gemini_client, "chat", mock_chat)

@pytest.fixture
def mock_voice_handler(monkeypatch):
    async def mock_transcribe(audio_bytes: bytes) -> str:
        if not audio_bytes:
            raise ValueError("Empty audio file")
        return "this is a mocked transcription of voice"
        
    async def mock_generate(text: str, lang: str = "hi") -> str:
        return "mocked_base64_audio_data"
        
    monkeypatch.setattr(router_module, "transcribe_audio", mock_transcribe)
    monkeypatch.setattr(router_module, "generate_audio", mock_generate)

def test_voice_chat_endpoint(client, mock_gemini, mock_voice_handler):
    # Simulate a file upload
    file_content = b"dummy audio content"
    files = {
        "file": ("test.wav", file_content, "audio/wav")
    }
    data = {
        "farmer_id": "FARMER-VOICE-TEST",
        "session_id": "session-voice-123",
        "lang": "hi"
    }
    
    response = client.post("/chatbot/voice-chat", files=files, data=data)
    
    assert response.status_code == 200, response.text
    resp_data = response.json()
    
    assert resp_data["session_id"] == "session-voice-123"
    assert resp_data["reply"] == "I am a simulated voice response."
    assert resp_data["audio_base64"] == "mocked_base64_audio_data"
    assert "tokens_used" in resp_data
    assert "context_used" in resp_data

def test_voice_chat_empty_audio(client, mock_gemini, mock_voice_handler):
    files = {
        "file": ("test.wav", b"", "audio/wav")
    }
    data = {
        "farmer_id": "FARMER-VOICE-TEST",
        "session_id": "session-voice-123",
        "lang": "hi"
    }
    
    response = client.post("/chatbot/voice-chat", files=files, data=data)
    assert response.status_code == 400
    assert "Empty audio" in response.text
