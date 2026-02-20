import urllib.request
import json

data = {
    "title": "Test Event",
    "description": "Test Description",
    "start_date": "2026-02-20",
    "end_date": "2026-02-21",
    "featured_image": "http://example.com/image.jpg",
    "category": "ENTERTAINMENT"
}

req = urllib.request.Request(
    "http://localhost:8000/events",
    data=json.dumps(data).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    with urllib.request.urlopen(req) as response:
        print(f"Status Code: {response.getcode()}")
        print(f"Response: {response.read().decode('utf-8')}")
except Exception as e:
    # If it's an HTTPError, we can read the body
    if hasattr(e, 'read'):
        print(f"Error Body: {e.read().decode('utf-8')}")
    print(f"Error: {e}")
