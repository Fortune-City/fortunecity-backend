import requests
import json

# Test creating a blog post
API_BASE_URL = "http://localhost:8000"

# First login to get token
login_data = {
    "username": "admin@123",
    "password": "fortunecityadmin@123"
}

print("Logging in...")
response = requests.post(f"{API_BASE_URL}/login", json=login_data)
print(f"Login status: {response.status_code}")

if response.status_code == 200:
    token = response.json()["access_token"]
    print(f"Token: {token[:20]}...")
    
    # Create a test post
    post_data = {
        "title": "Test Post",
        "content": "<p>Test content</p>",
        "excerpt": "Test excerpt",
        "featured_image": "",
        "status": "draft",
        "slug": "test-post",
        "seo": {
            "title": "Test SEO Title",
            "description": "Test SEO Description",
            "focusKeywords": ["test"],
        }
    }
    
    print("\nCreating post...")
    print(f"Payload: {json.dumps(post_data, indent=2)}")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{API_BASE_URL}/posts", json=post_data, headers=headers)
    
    print(f"\nResponse status: {response.status_code}")
    print(f"Response: {response.text}")
else:
    print(f"Login failed: {response.text}")
