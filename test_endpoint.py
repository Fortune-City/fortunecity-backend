import urllib.request
import json
try:
    with urllib.request.urlopen("http://localhost:8000/events") as response:
        status = response.getcode()
        body = response.read().decode('utf-8')
        print(f"Status Code: {status}")
        print(f"Response Body: {body[:500]}")
except Exception as e:
    print(f"Error: {e}")
