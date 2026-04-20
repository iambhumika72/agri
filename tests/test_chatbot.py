import pytest
from fastapi.testclient import TestClient
from api.main import app
from chatbot.gemini_client import gemini_client
from chatbot.intent_detector import detect_intent, get_intent_instruction, detect_language

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def mock_gemini(monkeypatch):
    async def mock_chat(*args, **kwargs):
        # We simulate Gemini returning a response mentioning chemical to trigger the guardrail
        return "You should use NPK fertilizer. ⚠️ Disclaimer: Please verify any chemical dosages with a local extension worker or Krishi Vigyan Kendra before application.", 15
        
    async def mock_health(*args, **kwargs):
        return True

    monkeypatch.setattr(gemini_client, "chat", mock_chat)
    monkeypatch.setattr(gemini_client, "health_check", mock_health)

def test_intent_detector():
    assert detect_intent("meri fasal mein kida lag gaya") == "pest_disease"
    assert detect_intent("mausam kaisa hai") == "weather_query"
    assert detect_intent("subsidy for tractor") == "govt_scheme"
    assert detect_language("नमस्ते") == "hi"
    assert detect_language("hello") == "en"

def test_health_endpoint(mock_gemini, client):
    response = client.get("/chatbot/health")
    assert response.status_code == 200
    data = response.json()
    assert data["gemini_status"] == "ok"
    assert "db_status" in data

def test_chat_endpoint(mock_gemini, client):
    req = {
        "farmer_id": "FARMER-TEST",
        "session_id": "session-test-123",
        "message": "gehu mein khad kab dalna hai?",
        "lang": "hi"
    }
    response = client.post("/chatbot/chat", json=req)
    assert response.status_code == 200, response.text
    data = response.json()
    
    assert data["session_id"] == "session-test-123"
    assert data["intent"] == "fertilizer_advice"
    assert "⚠️ Disclaimer" in data["reply"]
    assert data["tokens_used"] == 15

def test_get_history(mock_gemini, client):
    response = client.get("/chatbot/history/session-test-123?farmer_id=FARMER-TEST")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2 # Should have at least user message and assistant reply
    assert data[0]["role"] in ["user", "assistant"]

def test_list_sessions(mock_gemini, client):
    response = client.get("/chatbot/sessions/FARMER-TEST")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["session_id"] == "session-test-123"
