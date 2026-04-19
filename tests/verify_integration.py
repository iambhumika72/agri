import requests
import json

def test_recommendation_endpoint():
    url = "http://localhost:8000/recommendations/"
    payload = {
        "farm_id": "test-farm-final",
        "crop_type": "Wheat",
        "season": "kharif",
        "language": "en",
        "include_sms": True
    }
    
    print(f"Sending request to {url}...")
    try:
        response = requests.post(url, json=payload, timeout=60)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Response JSON:")
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    test_recommendation_endpoint()
