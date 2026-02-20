import urllib.request
import json

try:
    with urllib.request.urlopen("http://localhost:8000/api/events") as response:
        status = response.getcode()
        body = response.read().decode()
        print(f"Status: {status}")
        print(f"Body: {body[:100]}...")
except Exception as e:
    print(f"Error: {e}")
