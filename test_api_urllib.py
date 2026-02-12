import urllib.request
import json

try:
    url = "http://localhost:8000/posts?status=published"
    with urllib.request.urlopen(url) as response:
        print(f"Status Code: {response.getcode()}")
        data = response.read().decode('utf-8')
        print(f"Response Body: {data}")
except Exception as e:
    print(f"Error: {e}")
