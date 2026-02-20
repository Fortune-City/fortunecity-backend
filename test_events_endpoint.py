from fastapi.testclient import TestClient
from main import app
import traceback

client = TestClient(app)

def test_get_events():
    print("Testing GET /events...")
    try:
        response = client.get("/events")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 500:
            print("Response Content:", response.text)
        else:
            print("Response JSON:", response.json())
    except Exception as e:
        print("EXCEPTION CAUGHT:")
        traceback.print_exc()

if __name__ == "__main__":
    test_get_events()
