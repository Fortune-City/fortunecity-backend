import requests
import json

BASE_URL = "http://localhost:8000"

def test_theaters():
    print("Testing /theaters...")
    response = requests.get(f"{BASE_URL}/theaters")
    print(f"Status: {response.status_code}")
    print(f"Data: {json.dumps(response.json(), indent=2)}")
    return response.json()

def test_movies(theater_id):
    print(f"Testing /theaters/{theater_id}/movies...")
    response = requests.get(f"{BASE_URL}/theaters/{theater_id}/movies")
    print(f"Status: {response.status_code}")
    print(f"Data: {json.dumps(response.json(), indent=2)}")

if __name__ == "__main__":
    theaters = test_theaters()
    if theaters:
        test_movies(theaters[0]['id'])
